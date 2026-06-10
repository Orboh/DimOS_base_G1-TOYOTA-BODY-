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

from dimos.core.coordination.blueprints import autoconnect
from dimos.perception.perceive_loop_skill import PerceiveLoopSkill
from dimos.perception.spatial_perception import SpatialMemory
from dimos.robot.unitree.go2.blueprints.smart.unitree_go2 import unitree_go2
<<<<<<< HEAD
=======
from dimos.robot.unitree.go2.connection import GO2Connection
from dimos.utils.logging_config import setup_logger
>>>>>>> orboh/main

logger = setup_logger()


def _security_blueprint_if_available() -> object | None:
    try:
        import torch
    except Exception:
        logger.warning("PyTorch is unavailable, skipping SecurityModule in unitree_go2_spatial")
        return None

    if not torch.cuda.is_available():
        logger.warning("CUDA is unavailable, skipping SecurityModule in unitree_go2_spatial")
        return None

    return SecurityModule.blueprint(camera_info=GO2Connection.camera_info_static)

_modules = [
    unitree_go2,
    SpatialMemory.blueprint(),
    PerceiveLoopSkill.blueprint(),
<<<<<<< HEAD
).global_config(n_workers=8)
=======
]

_security_blueprint = _security_blueprint_if_available()
if _security_blueprint is not None:
    _modules.append(_security_blueprint)

unitree_go2_spatial = autoconnect(*_modules).global_config(n_workers=8)
>>>>>>> orboh/main

__all__ = ["unitree_go2_spatial"]
