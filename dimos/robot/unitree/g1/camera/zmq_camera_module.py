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

"""Module wrapper around :class:`ZmqImageSource` (RealSense-on-NX camera).

The G1's head D435i is USB-wired to the onboard NX and is NOT reachable
from an external PC (no WebRTC camera server — verified 2026-06-05, see
docs/platforms/humanoid/g1/index_orboh_make.md). The working path is the
GEAR-SONIC ZMQ transport from the Orboh add-vla branch:

    NX:  scripts/realsense_zmq_publisher.py  (pyrealsense2 → JPEG → tcp://*:5555)
    PC:  this module                          (ZMQ SUB → color_image)
"""

from __future__ import annotations

import os

from pydantic import Field

from dimos.core.core import rpc
from dimos.core.module import Module, ModuleConfig
from dimos.core.stream import Out
from dimos.msgs.sensor_msgs.Image import Image
from dimos.robot.unitree.g1.camera.zmq_image_source import ZmqCameraConfig, ZmqImageSource
from dimos.utils.logging_config import setup_logger

logger = setup_logger()


class ZmqCameraModuleConfig(ModuleConfig):
    host: str = Field(default_factory=lambda: os.getenv("ZMQ_CAMERA_HOST", "192.168.123.164"))
    port: int = Field(default_factory=lambda: int(os.getenv("ZMQ_CAMERA_PORT", "5555")))
    topic: str = "ego_view"


class ZmqCamera(Module):
    """Publishes RealSense frames from the NX ZMQ publisher on color_image."""

    config: ZmqCameraModuleConfig
    color_image: Out[Image]

    _source: ZmqImageSource | None = None

    @rpc
    def start(self) -> None:
        super().start()
        self._source = ZmqImageSource(
            ZmqCameraConfig(
                host=self.config.host,
                port=self.config.port,
                topic=self.config.topic,
            )
        )
        self._source.start()
        self.register_disposable(
            self._source.video_stream().subscribe(self.color_image.publish)
        )
        logger.info(
            "ZmqCamera started",
            endpoint=f"tcp://{self.config.host}:{self.config.port}",
            topic=self.config.topic,
        )

    @rpc
    def stop(self) -> None:
        if self._source is not None:
            self._source.stop()
            self._source = None
        super().stop()


__all__ = ["ZmqCamera", "ZmqCameraModuleConfig"]
