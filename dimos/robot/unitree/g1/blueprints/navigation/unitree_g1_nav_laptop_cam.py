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

"""``unitree-g1-nav-laptop`` plus the G1 head camera over WebRTC.

Adds ``G1Connection`` (webrtc) on top of the laptop navigation stack, used
**only** as a camera source: its ``cmd_vel`` input is remapped away so that
``G1HighLevelDdsSdk`` stays the single locomotion command path (otherwise both
modules would drive the robot simultaneously).

Extra requirements over ``unitree-g1-nav-laptop``:

- ``ROBOT_IP=192.168.123.164`` must be set (WebRTC signaling address).
- The G1 must expose the Unitree WebRTC service on that address. NOTE: not yet
  verified on real hardware; ``UnitreeWebRTCConnection`` blocks forever during
  connect if the service is unreachable — if startup hangs at G1Connection,
  fall back to ``unitree-g1-nav-laptop``.

Usage::

    ROBOT_IP=192.168.123.164 dimos run unitree-g1-nav-laptop-cam
"""

from __future__ import annotations

from dimos.core.coordination.blueprints import autoconnect
from dimos.core.transport import LCMTransport
from dimos.msgs.sensor_msgs.Image import Image
from dimos.robot.unitree.g1.blueprints.navigation.unitree_g1_nav_laptop import (
    unitree_g1_nav_laptop,
)
from dimos.robot.unitree.g1.connection import G1Connection

unitree_g1_nav_laptop_cam = (
    autoconnect(
        unitree_g1_nav_laptop,
        # enable_video is an explicit opt-in (off by default so stacks with a
        # CameraModule don't get two producers on one color_image topic).
        G1Connection.blueprint(enable_video=True),
    )
    .remappings(
        [
            # G1HighLevelDdsSdk owns locomotion — keep the WebRTC link video-only.
            (G1Connection, "cmd_vel", "_g1conn_cmd_vel_unused"),
        ]
    )
    .transports(
        {
            # LCM (not pSHM) so the LCM-listening RerunBridge shows the feed,
            # matching uintree_g1_primitive_no_nav's camera transport.
            ("color_image", Image): LCMTransport("/color_image", Image),
        }
    )
)

__all__ = ["unitree_g1_nav_laptop_cam"]
