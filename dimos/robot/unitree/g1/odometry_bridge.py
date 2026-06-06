# Copyright 2026 Dimensional Inc.
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

"""Bridge FAST-LIO odometry into the G1 stack's expected odom streams."""

from __future__ import annotations

from reactivex.disposable import Disposable

from dimos.core.core import rpc
from dimos.core.module import Module
from dimos.core.stream import In, Out
from dimos.msgs.geometry_msgs.PoseStamped import PoseStamped
from dimos.msgs.nav_msgs.Odometry import Odometry


class G1FastLioOdometryBridge(Module):
    """Republish FAST-LIO odometry as both PoseStamped odom and state_estimation."""

    odometry: In[Odometry]
    odom: Out[PoseStamped]
    state_estimation: Out[Odometry]

    @rpc
    def start(self) -> None:
        super().start()
        self.register_disposable(Disposable(self.odometry.subscribe(self._on_odometry)))

    @rpc
    def stop(self) -> None:
        super().stop()

    def _on_odometry(self, msg: Odometry) -> None:
        self.state_estimation.publish(msg)
        self.odom.publish(
            PoseStamped(
                ts=msg.ts,
                frame_id=msg.frame_id,
                position=msg.position,
                orientation=msg.orientation,
            )
        )
