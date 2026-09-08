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

"""F-07 腹部固定かごへの投入（同期版・右腕のみ・IKのみ）— LangGraph の grasp_sequence 用。

``place_basket.py``（左手に持つ籠、``LEFT_PRESENT_BASKET`` で左腕を提示する両腕版）
の腹部固定かご版。かごを G1 の腹部（pelvis）に固定するYokoteさんの設計
（Obsidian ``Free-space/yokote/20260825/腹部かご搭載_方針書.md`` + 8/25-8/27作業ログ）
に合わせ、**左腕は一切動かさず右腕のみ**で entry→drop→retreat の3点をIKで運び、
グリッパを開いてリリースする。

``act/basket_deposit_bridge.py``（LCM 経由の非同期 Module 版、クリック/YOLOブリッジ
直結の ``unitree-g1-okra-ik-only-grasp-zed`` 用）と同じ考え方・同じ投入座標
（``ENTRY_TORSO``/``DROP_TORSO``/``RETREAT_TORSO`` をそこから import）だが、
こちらは ``GraspSequence.place_basket_fn``（``() -> None`` の同期呼び出し）として
差し込めるよう、``IkApproachSkill`` を使った同期関数の形で提供する。

⚠️ SAFETY: ``basket_deposit_bridge.py`` と同じ注意 — この3点直接経路はMuJoCoでのみ
自己衝突検証済み。実機Phase 5デモでは右脚接触を避けるため追加の退避ウェイポイントが
使われた。実オクラでのLIVE実行前に必ずDRY-RUNでq_solを確認すること。
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
import time

from dimos.robot.unitree.g1.act.basket_deposit_bridge import (
    BASKET_OPEN_Q,
    DROP_TORSO,
    ENTRY_TORSO,
    RETREAT_TORSO,
)
from dimos.robot.unitree.g1.harvest.ik_approach import IkApproachSkill
from dimos.utils.logging_config import setup_logger

logger = setup_logger()


def make_basket_deposit_fn(
    *,
    send_arm: Callable[[list[float], float], None],
    open_gripper: Callable[[float, float], None],
    get_measured: Callable[[], Sequence[float]],
    entry_torso: Sequence[float] = ENTRY_TORSO,
    drop_torso: Sequence[float] = DROP_TORSO,
    retreat_torso: Sequence[float] = RETREAT_TORSO,
    q_open: float = BASKET_OPEN_Q,
    settle_secs: float = 1.2,
    ik: IkApproachSkill | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Callable[[], bool]:
    """F-07（腹部かご版）投入動作を行う ``() -> bool``（成功=True）を組み立てて返す。

    Args:
        send_arm: ``(arm14, secs)`` — 14関節目標（左7+右7, 正準順）へ ``secs`` 秒で
            スルーして保持する。左腕側は現在角のまま（IkApproachSkill.solve が
            hold する）なので、呼び出し側は特別な左腕制御をしなくてよい。
        open_gripper: ``(q, secs)`` — グリッパ目標角 ``q`` を ``secs`` 秒送出（開き＝リリース）。
        get_measured: ``() -> 29-DOF 現在角``（warm-start に使う）。
        entry_torso / drop_torso / retreat_torso: torso_link フレームの3点 [m]。
            既定は ``basket_deposit_bridge.py`` と共有（同じ物理かごを指す）。
        q_open: リリース時のグリッパ開き角 [rad]。
        settle_secs: 開き整定時間 [s]。
        ik: 投入用の IK スキル。None なら standoff=0（真上を狙う）・投入向けの
            タイトな許容誤差（0.02m）で既定生成する。

    Returns:
        ``place() -> bool``。3点いずれかで IK が解けなければ False（呼び出し側で
        リトライ/スキップ）。solved なら entry→drop→retreat の順にスルーしてから
        グリッパを開き True。
    """
    if ik is None:
        ik = IkApproachSkill(
            standoff_m=0.0,  # かご開口の真上を狙う（切断リーチのような手前止めは不要）
            max_reach_pos_err_m=0.02,  # 投入はかご開口部が狭いので把持リーチより厳しめ
        )

    legs = (("entry", entry_torso), ("drop", drop_torso), ("retreat", retreat_torso))

    def place() -> bool:
        for label, target in legs:
            meas = list(get_measured())
            res = ik.solve(target, meas)
            if res is None:
                logger.warning(
                    f"[basket-deposit] {label} 目標 {list(target)} へ IK 解けず"
                    "（投入中止・要リトライ/スキップ）"
                )
                return False
            logger.info(
                f"[basket-deposit] {label}: torso{list(target)} err={res.err:.4f} m "
                f"wait={res.wait_s:.2f}s"
            )
            send_arm(res.arm14, res.wait_s)
            sleep_fn(res.wait_s)

        open_gripper(q_open, settle_secs)
        sleep_fn(settle_secs)
        logger.info(f"[basket-deposit] 投入完了 — グリッパ q={q_open:.3f} で開放")
        return True

    return place


__all__ = ["make_basket_deposit_fn"]
