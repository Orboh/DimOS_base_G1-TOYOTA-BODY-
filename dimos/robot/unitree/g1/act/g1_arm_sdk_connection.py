# Copyright 2025-2026 Dimensional Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""G1 upper-body arm control via the Unitree ``rt/arm_sdk`` DDS interface.

Publishes arm joint targets to ``rt/arm_sdk`` (LowCmd_, unitree_hg) WITHOUT
releasing sport mode — the onboard controller keeps the legs balancing while
arm_sdk overrides only the 14 arm joints (left 15-21, right 22-28), blended by
the ``weight`` register at ``motor_cmd[29]`` (0→1). Protocol mirrors
unitree_lerobot's robot_arm.py (topic, weight, CRC, mode_machine, gains).

SAFETY (first real motion):
- weight ramps 0→1 over ``weight_ramp_s`` (gradual authority handover).
- the commanded angle slews toward the target at most ``max_arm_vel`` rad/s, so
  the arms move slowly regardless of how far the ACT target jumps.
- the target is initialised to the CURRENT arm pose (hold) until arm_target
  messages arrive; if they stop, the last target is held.
- gripper joints are NOT touched here (Dex1 is a separate path).
"""

from __future__ import annotations

import threading
from threading import Thread
import time
from typing import TYPE_CHECKING, Any

from pydantic import Field
from reactivex.disposable import Disposable

if TYPE_CHECKING:
    from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber
    from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_, LowState_
    from unitree_sdk2py.utils.crc import CRC

from dimos.control.components import make_humanoid_joints
from dimos.core.core import rpc
from dimos.core.module import Module, ModuleConfig
from dimos.core.stream import In, Out
from dimos.msgs.sensor_msgs.JointState import JointState
from dimos.utils.logging_config import setup_logger

logger = setup_logger()

_NUM_MOTORS = 29
_NUM_MOTOR_SLOTS = 35
_WEIGHT_IDX = 29  # kNotUsedJoint0: arm_sdk authority weight (0..1)
_MODE_MACHINE_WAIT_S = 10.0

# Arm joints in the canonical 29-DOF order: left 15-21, right 22-28.
_ARM_IDX = list(range(15, 29))
_WRIST_IDX = {19, 20, 21, 26, 27, 28}
_G1_JOINTS = make_humanoid_joints("g1")
_ARM_JOINT_NAMES = _G1_JOINTS[15:29]


class G1ArmSdkConnectionConfig(ModuleConfig):
    network_interface: str = Field(default="")
    publish_rate_hz: float = 250.0
    # Proven arm gains (unitree_lerobot): shoulder/elbow vs wrist.
    kp_arm: float = 80.0
    kd_arm: float = 3.0
    kp_wrist: float = 40.0
    kd_wrist: float = 1.5
    # SAFETY knobs.
    weight_ramp_s: float = 5.0       # 0->1 authority handover time [s]
    max_arm_vel: float = 0.5         # slew limit [rad/s]
    motor_states_rate_hz: float = 50.0
    frame_id: str = "g1_pelvis"


class G1ArmSdkConnection(Module):
    """Arm-only DDS control via rt/arm_sdk (legs stay on the onboard controller)."""

    config: G1ArmSdkConnectionConfig

    arm_target: In[JointState]      # 14 arm joint targets (left 7, right 7) [rad]
    motor_states: Out[JointState]   # full 29-DOF state, for the ACT observation

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._publisher: ChannelPublisher | None = None
        self._subscriber: ChannelSubscriber | None = None
        self._low_cmd: LowCmd_ | None = None
        self._low_state: Any = None
        self._crc: CRC | None = None
        self._mode_machine: int | None = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Thread | None = None
        # 14-vector commanded (slewed) and target arm angles.
        self._commanded_q: list[float] | None = None
        self._target_q: list[float] | None = None
        self._t_start: float = 0.0

    @rpc
    def start(self) -> None:
        super().start()
        from unitree_sdk2py.core.channel import (
            ChannelFactoryInitialize,
            ChannelPublisher,
            ChannelSubscriber,
        )
        from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_
        from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_, LowState_
        from unitree_sdk2py.utils.crc import CRC

        nic = self.config.network_interface
        logger.info(f"Initializing DDS (G1 arm_sdk) interface={nic!r}...")
        try:
            ChannelFactoryInitialize(0, nic) if nic else ChannelFactoryInitialize(0)
        except Exception as e:
            logger.debug(f"ChannelFactoryInitialize raised (likely already init'd): {e}")

        self._publisher = ChannelPublisher("rt/arm_sdk", LowCmd_)
        self._publisher.Init()
        self._subscriber = ChannelSubscriber("rt/lowstate", LowState_)
        self._subscriber.Init(self._on_low_state, 10)
        self._crc = CRC()

        self._low_cmd = unitree_hg_msg_dds__LowCmd_()
        self._low_cmd.mode_pr = 0
        # arm_sdk: only the arm joints carry gains; legs/waist left at zero gain so
        # the onboard controller keeps them. weight slot starts at 0 (no authority).
        for i in _ARM_IDX:
            self._low_cmd.motor_cmd[i].mode = 1
        self._low_cmd.motor_cmd[_WEIGHT_IDX].q = 0.0

        # Wait for the first LowState: capture mode_machine + current arm pose.
        logger.info("Waiting for first LowState (mode_machine + current arm pose)...")
        t0 = time.time()
        while time.time() - t0 < _MODE_MACHINE_WAIT_S:
            with self._lock:
                if self._mode_machine is not None and self._low_state is not None:
                    break
            time.sleep(0.05)
        with self._lock:
            if self._mode_machine is None or self._low_state is None:
                raise RuntimeError("No LowState received; cannot start arm_sdk safely")
            cur = [float(self._low_state.motor_state[i].q) for i in _ARM_IDX]
            self._commanded_q = list(cur)
            self._target_q = list(cur)  # hold current pose until ACT sends targets
        logger.info(f"arm_sdk ready (mode_machine={self._mode_machine}); holding current arm pose")

        self.register_disposable(Disposable(self.arm_target.subscribe(self._on_arm_target)))
        self._t_start = time.perf_counter()
        self._stop_event.clear()
        self._thread = Thread(target=self._control_loop, name="g1-arm-sdk", daemon=True)
        self._thread.start()
        logger.info(
            "G1ArmSdkConnection started",
            rate_hz=self.config.publish_rate_hz,
            weight_ramp_s=self.config.weight_ramp_s,
            max_arm_vel=self.config.max_arm_vel,
        )

    @rpc
    def stop(self) -> None:
        # Ramp weight back to 0 to hand the arms back to the onboard controller.
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            self._thread = None
        try:
            if self._publisher is not None and self._low_cmd is not None and self._crc is not None:
                for w in [x / 20.0 for x in range(20, -1, -1)]:  # 1.0 -> 0.0 over ~ steps
                    with self._lock:
                        self._low_cmd.motor_cmd[_WEIGHT_IDX].q = w
                        if self._mode_machine is not None:
                            self._low_cmd.mode_machine = self._mode_machine
                        self._low_cmd.crc = self._crc.Crc(self._low_cmd)
                        self._publisher.Write(self._low_cmd)
                    time.sleep(0.02)
        except Exception as e:
            logger.warning(f"weight ramp-down on stop failed: {e}")
        if self._subscriber is not None:
            try:
                self._subscriber.Close()
            except (OSError, RuntimeError):
                pass
        if self._publisher is not None:
            try:
                self._publisher.Close()
            except (OSError, RuntimeError):
                pass
        self._publisher = self._subscriber = self._low_cmd = self._low_state = self._crc = None
        self._mode_machine = None
        logger.info("G1ArmSdkConnection disconnected")
        super().stop()

    def _on_low_state(self, msg: Any) -> None:
        with self._lock:
            self._low_state = msg
            if self._mode_machine is None:
                self._mode_machine = msg.mode_machine

    def _on_arm_target(self, msg: JointState) -> None:
        pos = list(msg.position)
        if len(pos) < len(_ARM_IDX):
            logger.warning(f"arm_target has {len(pos)} joints; expected {len(_ARM_IDX)}; ignoring")
            return
        with self._lock:
            self._target_q = [float(x) for x in pos[: len(_ARM_IDX)]]

    def _control_loop(self) -> None:
        period = 1.0 / float(self.config.publish_rate_hz)
        max_step = self.config.max_arm_vel * period  # slew per cycle [rad]
        ms_period = 1.0 / float(self.config.motor_states_rate_hz)
        next_tick = time.perf_counter()
        last_ms = 0.0

        while not self._stop_event.is_set():
            now = time.perf_counter()
            weight = min(1.0, (now - self._t_start) / max(1e-3, self.config.weight_ramp_s))

            with self._lock:
                if self._low_cmd is None or self._crc is None or self._publisher is None:
                    break
                target = list(self._target_q or [])
                cmd = self._commanded_q
                if cmd is not None and target:
                    # slew each joint toward target, clipped to max_step
                    for k in range(len(cmd)):
                        d = target[k] - cmd[k]
                        if d > max_step:
                            d = max_step
                        elif d < -max_step:
                            d = -max_step
                        cmd[k] += d
                    for k, i in enumerate(_ARM_IDX):
                        is_wrist = i in _WRIST_IDX
                        self._low_cmd.motor_cmd[i].q = cmd[k]
                        self._low_cmd.motor_cmd[i].dq = 0.0
                        self._low_cmd.motor_cmd[i].tau = 0.0
                        self._low_cmd.motor_cmd[i].kp = (
                            self.config.kp_wrist if is_wrist else self.config.kp_arm
                        )
                        self._low_cmd.motor_cmd[i].kd = (
                            self.config.kd_wrist if is_wrist else self.config.kd_arm
                        )
                    self._low_cmd.motor_cmd[_WEIGHT_IDX].q = weight
                    if self._mode_machine is not None:
                        self._low_cmd.mode_machine = self._mode_machine
                    self._low_cmd.crc = self._crc.Crc(self._low_cmd)
                    self._publisher.Write(self._low_cmd)

                # publish motor_states for the ACT observation (downsampled)
                if self._low_state is not None and (now - last_ms) >= ms_period:
                    last_ms = now
                    names = list(_G1_JOINTS)
                    pos = [float(self._low_state.motor_state[i].q) for i in range(_NUM_MOTORS)]
                    vel = [float(self._low_state.motor_state[i].dq) for i in range(_NUM_MOTORS)]
                    js = JointState(name=names, position=pos, velocity=vel, effort=[0.0] * _NUM_MOTORS)
                    js.frame_id = self.config.frame_id
                    self.motor_states.publish(js)

            next_tick += period
            sleep_for = next_tick - time.perf_counter()
            if sleep_for > 0:
                self._stop_event.wait(sleep_for)
            else:
                next_tick = time.perf_counter()


__all__ = ["G1ArmSdkConnection", "G1ArmSdkConnectionConfig"]
