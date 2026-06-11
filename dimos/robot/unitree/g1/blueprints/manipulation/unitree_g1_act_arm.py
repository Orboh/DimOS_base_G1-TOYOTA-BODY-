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

"""LIVE okra-ACT upper-body control: arms MOVE via rt/arm_sdk.

⚠️ This MOVES the real robot's arms. Legs stay on the onboard balance
controller (sport mode NOT released). Safety is built into
``G1ArmSdkConnection``: weight ramps 0→1, the command slews at most
``max_arm_vel`` rad/s, motion starts from the current arm pose. Keep an e-stop
in hand and clear space around the arms.

Wiring (autoconnect by stream name):
    ZmqCamera.color_image ──▶ ActBridge.color_image
    G1ArmSdkConnection.motor_states ──▶ ActBridge.motor_states
    ActBridge.arm_target ──▶ G1ArmSdkConnection.arm_target ──▶ rt/arm_sdk

Run (all three, in order):
    # NX:      /usr/bin/python3 ~/uvc_zmq_publisher.py --device -1
    # laptop:  ~/act-okura/.venv_act/bin/python ~/act-okura/act_service.py --serve
    # laptop:  ROBOT_INTERFACE=<nic> dimos run unitree-g1-act-arm
"""

from __future__ import annotations

import os

from dimos.core.coordination.blueprints import autoconnect
from dimos.core.transport import LCMTransport
from dimos.msgs.sensor_msgs.Image import Image
from dimos.msgs.sensor_msgs.JointState import JointState
from dimos.robot.unitree.g1.act.act_bridge import ActBridge
from dimos.robot.unitree.g1.act.g1_arm_sdk_connection import G1ArmSdkConnection
from dimos.robot.unitree.g1.camera.zmq_camera_module import ZmqCamera

unitree_g1_act_arm = autoconnect(
    ZmqCamera.blueprint(),
    G1ArmSdkConnection.blueprint(
        network_interface=os.getenv("ROBOT_INTERFACE", ""),
    ),
    ActBridge.blueprint(dry_run=False),
).transports(
    {
        ("color_image", Image): LCMTransport("/color_image", Image),
        ("motor_states", JointState): LCMTransport("/g1/motor_states", JointState),
        ("arm_target", JointState): LCMTransport("/g1/arm_target", JointState),
    }
)

__all__ = ["unitree_g1_act_arm"]
