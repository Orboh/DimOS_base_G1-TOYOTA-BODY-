# Stage B — オクラ ACT の DimOS 移植 計画

> 前提：Stage A（公式 `unitree_lerobot/eval_g1.py` での実機検証）は **2026-06-11 に成功**。
> このドキュメントは、その動作を **DimOS フレームワーク経由**で再現するための実装計画。
> 開始時はまず本ブランチの WIP 3ファイルを再読込して現状確認すること。

---

## 0. ゴールと位置づけ

- **Stage A（完了）**：公式 `eval_g1.py`（単体スクリプト）で「学習済みオクラ ACT が実機 G1 上半身で正しく動く」ことを確認したリファレンス実装。
- **Stage B（本計画）**：同じ動作を **DimOS（Module/Stream/Blueprint＋エージェント層）** で再現する製品統合。ACT を 1 つの skill として扱い、ナビ/知覚/coordinator と合成可能にし、Jetson 単体で動かす本番形にする。

### Stage A で確証が取れた事実（Stage B の設計根拠）
1. **モデルは正しい**（公式経路でオクラ把持成功）。問題が出れば DimOS 統合側を疑う。
2. **制御経路は `rt/arm_sdk`（motion control mode）**：脚はオンボード自立制御に委譲。Unitree 仕様で LowCmd の有効 index は **12–28（腰+腕）と 29（weight）のみ、脚 0–11 は無視**。→ 脚に司令を送る必要も競合もない（`rt/lowcmd` 全身経路だと脚 kp_high 保持で発振＝振動）。
3. **追従速度が鍵**：`eval_g1.py` の `G1_29_ArmController` は **250Hz** publish、毎周期 `clip_arm_q_target(target, velocity_limit=20 rad/s)`。ACT は 30Hz。
4. **カメラは単眼 RGB 480×640 `cam_left_high`**（頭部 D435i）。
5. **右手 Dex1 のみ**：`rt/dex1/right/state` のみ存在。学習データでも state[14]（左 grip）は **mean=std=0 の定数**＝左は未使用。

---

## 1. 目標アーキテクチャ（DimOS モジュールグラフ）

```
G1Connection (lowstate源) ──JointState──┐
ZmqCamera (ego_view, BGR) ───Image──────┤
                                         ▼
                                    ActBridge ──(ZMQ REQ)──> ACT service (別venv, lerobot ACTPolicy)
                                    ├ state[16] 組立(腕14 + 右grip1 + 左grip=0)        └ action[16]
                                    └ BGR→RGB 480x640 変換
                                         │ Out[JointState] arm_target
                                         ▼
                              G1ArmSdkConnection ──CycloneDDS── rt/arm_sdk (motor_cmd[15-28], weight@29)
                              (+ gripper) ─────────────────────  rt/dex1/right/cmd (MotorCmds_)
```
autoconnect で Out↔In を名前一致で結線。

### 既存ファイル（本ブランチ `feat/g1-act-arm-sdk`）
- `act_bridge.py` … ActBridge（In[Image] color_image / In[JointState] motor_states → Out[JointState] arm_target、ZMQ REQ で外部 ACT サービス、30Hz worker）。**dry-run 済**（DDS 書込なし）。
- `g1_arm_sdk_connection.py` … G1ArmSdkConnection（rt/arm_sdk publisher、weight ramp、slew limit、kp_arm=80/kd=3・kp_wrist=40/kd=1.5）。**WIP・以前ドリフト**。
- `blueprints/manipulation/unitree_g1_act_arm.py` … 統合 blueprint。**WIP**。
- 参考：`~/act-okura/act_service.py`（ZMQ REP, lerobot ACTPolicy）、`~/act-okura/act_g1_direct.py`（dimos 非経由の単一プロセス ACT→arm_sdk 閉ループ＝**ほぼ正解形のロジック**）。
- リファレンス：Orboh/unitree_lerobot **PR #1** / **Issue #2**（Stage A の修正一式）。

---

## 2. 主要タスク

### ① 追従ループの修正（最重要・ドリフト根治）
- **原因**：`g1_arm_sdk_connection.py` の slew=0.5 rad/s が遅すぎ → 腕が ACT ターゲットに追従できず → 観測 OOD → 暴走。
- **修正**：
  - 速度上限を **~20 rad/s** に（`eval_g1.py` の clip 同等）。
  - arm_sdk publish を **250Hz** に上げ、ACT(30Hz) とループ分離（最新ターゲットへ高速補間）。
  - weight は 0→1 を数百 ms ランプ後 1 固定。
  - ゲインは現状値で可（バグは slew であってゲインではない）。
  - `~/act-okura/act_g1_direct.py` の閉ループ実装を DimOS モジュールへ移植するのが近道。

### ② カメラ形式変換
- DimOS `ZmqCamera` = GEAR-SONIC `ego_view`（BGR, :5555）。ACT = RGB 480×640 `cam_left_high`。
- ActBridge で `cv2.cvtColor(BGR→RGB)` ＋必要なら resize→480×640。**GEAR-SONIC の実解像度を実測**し teleimager(480×640) と一致するか確認。
- ⚠️ D435i は 1 台。DimOS publisher と teleimager は同時起動不可 → DimOS 経路なら ZmqCamera に統一。

### ③ 観測 state[16] の組立（実機グリッパー対応）
- 腕14（恒等写像、dimos 順＝G1_29_JointArmIndex で検証済）＋ **左grip=0 固定**（右手のみ・学習の定数0と一致）＋ **右grip=`rt/dex1/right/state`**。
- dry-run では grip=0 だったので、**右 grip 状態の購読を追加**。

### ④ グリッパー駆動経路
- `action[15]` → `rt/dex1/right/cmd`（`MotorCmds_`, `cmds[0].q`, kp=5/kd=0.05）。左 cmd は送らない。

### ⑤ arm_sdk 送信モジュール（送信の継ぎ目）
- `rt/arm_sdk` に `motor_cmd[15-28]=腕target`、`motor_cmd[29].q=weight`、**脚(0-11) は触らない**（仕様上無視）。`mode_machine` は lowstate から、CRC 付与、250Hz。
- **sport mode 解除しない**（脚はオンボード loco）。motion control mode 前提（Stage A と同じ）。

### ⑥ Blueprint ＋ 配線
- `unitree_g1_act_arm.py`：lowstate源(coordinator系) ＋ ZmqCamera ＋ ActBridge ＋ G1ArmSdkConnection ＋ gripper を合成 → `all_blueprints.py` 登録。
- ⚠️ 既存 blueprint の lowcmd publisher と arm_sdk が**二重に司令を出さない**ことを確認。

### ⑦ ACT 推論サービス（別venv）
- `act_service.py`（ZMQ REP, lerobot ACTPolicy）。lerobot `select_action` は chunk queue＋temporal ensembling のステートフル処理のため、当面 **ONNX 化せず ZMQ サービスで隔離**（dimos venv との依存衝突回避）。loopback で REQ-REP レイテンシ **<30ms** を確認。

---

## 3. 検証（段階的・安全第一）

| 段階 | 内容 | 安全 |
|---|---|---|
| **B0** | dry-run（DDS書込なし）：state[16]組立・ACT出力・カメラ形式をログ確認 | 動かない |
| **B1** | arm_sdk LIVE・**周囲クリア**・weight ランプ・**追従誤差(commanded vs measured)監視** → ドリフト無しを確認 | 自立・e-stop |
| **B2** | motion control mode 自立で**オクラ把持フル試行**（Stage A を DimOS で再現） | 自立・e-stop |

各段で `eval_g1.py` のリファレンス挙動と比較する。

---

## 4. リスク / 未確定

- GEAR-SONIC `ego_view` の解像度が 480×640 でない可能性（→ resize 必須）。
- ZMQ サービスのレイテンシが 30Hz ループに乗るか。
- coordinator 系 blueprint の既存送信経路（lowcmd 等）と arm_sdk の競合。
- ACT 観測の closed-loop：腕が追従しないと obs が OOD 化（①が効くか B1 で要確認）。

---

## 5. 着手順序（推奨）

1. **送信の継ぎ目だけ単体テスト**：ACT 無しで「現在姿勢→指定ターゲットへ arm_sdk 追従」させ、**追従誤差が小さくドリフトしない**ことを確認（`act_g1_direct.py` ロジック移植）。
2. ②カメラ変換を B0 dry-run で検証。
3. ③④⑤を結線し B1。
4. ⑥⑦で blueprint 化し B2。

---

## 6. 参照

- Stage A 実装：Orboh/unitree_lerobot PR #1（`feat/okura-act-realrobot-eval`）/ Issue #2
- 手順書：unitree_lerobot `docs/OKURA_ACT_REALROBOT.md`
- FleetSeek：debug exp_01KTV1MCPZ8NFP6VPEYGY6TMY5 / skill exp_01KTV4TDQRW9WRC77QMZ1GEN1Y
- モデル：`sotata/act-okura-pick-06102026`、データセット `Orboh/okura-sub-lerobot`
- 実機制約：右手 Dex1 のみ / motion control mode / NIC `enx6c1ff771dc67` / cyclonedds 0.10.5
