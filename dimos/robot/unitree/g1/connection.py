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

from abc import ABC, abstractmethod
import time
from threading import Event, Thread
from typing import TYPE_CHECKING, Any

from pydantic import Field
from reactivex.disposable import Disposable, SerialDisposable

from dimos.constants import DEFAULT_THREAD_JOIN_TIMEOUT
from dimos.core.coordination.module_coordinator import ModuleCoordinator
from dimos.core.core import rpc
from dimos.core.module import Module, ModuleConfig
from dimos.core.stream import In, Out
from dimos.msgs.geometry_msgs.Twist import Twist
from dimos.msgs.sensor_msgs.CameraInfo import CameraInfo
from dimos.msgs.sensor_msgs.Image import Image
from dimos.robot.unitree.connection import UnitreeWebRTCConnection
from dimos.spec.control import LocalPlanner
from dimos.utils.logging_config import setup_logger

if TYPE_CHECKING:
    from dimos.core.rpc_client import ModuleProxy

logger = setup_logger()

# G1 front camera approximate intrinsics (1280x720, ~90° FOV).
# These are rough estimates — run camera calibration for accurate values.
_G1_CAMERA_INFO = CameraInfo.from_intrinsics(
    fx=800.0,
    fy=800.0,
    cx=640.0,
    cy=360.0,
    width=1280,
    height=720,
    frame_id="camera_optical",
)


class G1Config(ModuleConfig):
    ip: str = Field(default_factory=lambda m: m["g"].robot_ip)
    connection_type: str = Field(default_factory=lambda m: m["g"].unitree_connection_type)


class G1ConnectionBase(Module, ABC):
    """Abstract base for G1 connections (real hardware and simulation).

    Modules that depend on G1 connection RPC methods should reference this
    base class so the blueprint wiring works regardless of which concrete
    connection is deployed.
    """

    config: ModuleConfig

    @rpc
    @abstractmethod
    def start(self) -> None:
        super().start()

    @rpc
    @abstractmethod
    def stop(self) -> None:
        super().stop()

    @rpc
    @abstractmethod
    def move(self, twist: Twist, duration: float = 0.0) -> None: ...

    @rpc
    @abstractmethod
    def publish_request(self, topic: str, data: dict[str, Any]) -> dict[Any, Any]: ...


class G1Connection(G1ConnectionBase):
    config: G1Config
    cmd_vel: In[Twist]
    color_image: Out[Image]
    camera_info: Out[CameraInfo]
    connection: UnitreeWebRTCConnection | None = None
    _camera_info_thread: Thread | None = None
    _video_subscription_thread: Thread | None = None
    _video_subscription: SerialDisposable | None = None
    _stop_event: Event | None = None

    @rpc
    def start(self) -> None:
        super().start()

        match self.config.connection_type:
            case "webrtc":
                self.connection = UnitreeWebRTCConnection(self.config.ip)
            case "replay":
                raise ValueError("Replay connection not implemented for G1 robot")
            case "mujoco":
                raise ValueError(
                    "This module does not support simulation, use G1SimConnection instead"
                )
            case _:
                raise ValueError(f"Unknown connection type: {self.config.connection_type}")

        assert self.connection is not None
        self.connection.start()

        self.register_disposable(Disposable(self.cmd_vel.subscribe(self.move)))

        self._stop_event = Event()
        self._camera_info_thread = Thread(target=self._publish_camera_info, daemon=True)
        self._camera_info_thread.start()

        self._video_subscription = SerialDisposable()
        self.register_disposable(self._video_subscription)
        self._video_subscription_thread = Thread(target=self._subscribe_video_stream, daemon=True)
        self._video_subscription_thread.start()

    @rpc
    def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()

        if self._video_subscription is not None:
            self._video_subscription.dispose()
        if self._video_subscription_thread and self._video_subscription_thread.is_alive():
            self._video_subscription_thread.join(timeout=DEFAULT_THREAD_JOIN_TIMEOUT)

        if self._camera_info_thread and self._camera_info_thread.is_alive():
            self._camera_info_thread.join(timeout=DEFAULT_THREAD_JOIN_TIMEOUT)

        assert self.connection is not None
        self.connection.stop()
        super().stop()

    def _subscribe_video_stream(self) -> None:
        assert self.connection is not None
        assert self._video_subscription is not None
        logger.info("Starting G1 WebRTC video stream subscription")

        frame_count = 0

        def on_image(image: Image) -> None:
            nonlocal frame_count
            frame_count += 1
            if frame_count == 1:
                logger.info(
                    "Received first G1 camera frame",
                    width=image.width,
                    height=image.height,
                    encoding=image.encoding,
                )
            self.color_image.publish(image)

        def on_error(error: Exception) -> None:
            logger.error("G1 WebRTC video stream subscription failed", error=repr(error))

        self._video_subscription.disposable = self.connection.video_stream().subscribe(
            on_image,
            on_error,
        )
        logger.info("G1 WebRTC video stream subscription installed")

    def _publish_camera_info(self) -> None:
        logger.info("Starting G1 camera_info publisher")
        while self._stop_event is None or not self._stop_event.is_set():
            self.camera_info.publish(_G1_CAMERA_INFO)
            time.sleep(1.0)
        logger.info("Stopped G1 camera_info publisher")

    @rpc
    def move(self, twist: Twist, duration: float = 0.0) -> None:
        assert self.connection is not None
        self.connection.move(twist, duration)

    @rpc
    def publish_request(self, topic: str, data: dict[str, Any]) -> dict[Any, Any]:
        logger.info(f"Publishing request to topic: {topic} with data: {data}")
        assert self.connection is not None
        return self.connection.publish_request(topic, data)  # type: ignore[no-any-return]


def deploy(dimos: ModuleCoordinator, ip: str, local_planner: LocalPlanner) -> "ModuleProxy":
    connection = dimos.deploy(G1Connection, ip=ip)
    connection.cmd_vel.connect(local_planner.cmd_vel)
    connection.start()
    return connection
