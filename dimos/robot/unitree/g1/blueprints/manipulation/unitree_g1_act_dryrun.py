#!/usr/bin/env python3
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

"""Live DRY-RUN for the okra ACT: real camera + real joint angles, NO motion.

Wires the head camera (NX ZMQ) and the G1 low-level state into ActBridge, which
ships the observation to the external lerobot ACT service and **logs** the
predicted action. Nothing is written to the motors.

SAFETY:
- `G1WholeBodyConnection(release_sport_mode=False)` => sport mode is NOT released,
  so the legs stay on the onboard balance controller (robot keeps standing). We
  only subscribe rt/lowstate to publish `motor_states`.
- `ActBridge(dry_run=True)` => action is logged only; no rt/lowcmd / rt/arm_sdk write.

Run (all three, in order):
    # 1) on the NX: head camera publisher
    ~/.venv_cam/bin/python ~/realsense_zmq_publisher.py

    # 2) on the laptop: the ACT inference service (lerobot venv)
    ~/act-okura/.venv_act/bin/python ~/act-okura/act_service.py --serve

    # 3) on the laptop: this blueprint (pin the NIC to the robot LAN)
    ROBOT_INTERFACE=<nic> dimos run unitree-g1-act-dryrun
"""

from __future__ import annotations

import os

from dimos.core.coordination.blueprints import autoconnect
from dimos.core.transport import LCMTransport
from dimos.msgs.sensor_msgs.Image import Image
from dimos.msgs.sensor_msgs.JointState import JointState
from dimos.robot.unitree.g1.act.act_bridge import ActBridge
from dimos.robot.unitree.g1.camera.zmq_camera_module import ZmqCamera
from dimos.robot.unitree.g1.wholebody_connection import G1WholeBodyConnection

unitree_g1_act_dryrun = autoconnect(
    ZmqCamera.blueprint(),
    G1WholeBodyConnection.blueprint(
        release_sport_mode=False,  # SAFETY: keep legs on the onboard controller
        network_interface=os.getenv("ROBOT_INTERFACE", ""),
    ),
    ActBridge.blueprint(dry_run=True),
).transports(
    {
        ("color_image", Image): LCMTransport("/color_image", Image),
        ("motor_states", JointState): LCMTransport("/g1/motor_states", JointState),
    }
)

__all__ = ["unitree_g1_act_dryrun"]
