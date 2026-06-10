# Go2 × DimOS — 言語コマンドで動かす (シミュレーション)

`dimos` をシミュレーションモード (`--simulation`) で起動し、MuJoCo 上の
Unitree Go2 に自然言語で指示を出すための最小構成です。LLM は OpenAI gpt-4o、
スキルは `UnitreeSkillContainer`(relative_move / wait / execute_sport_command 等)。

## 前提

- `.env`(リポジトリ直下)に `OPENAI_API_KEY` がセット済み
- `dimensional-applications/.venv` に `dimos` と `mujoco` / `mujoco_playground` がインストール済み
- GUI 用に `DISPLAY=:0` がセット済み(`.env` で設定済み)

## このリポジトリで施した手当 (dimos==0.0.12.post2 用)

1. **`unitree-webrtc-connect` を追加インストール** — `dimos.robot.unitree.connection` が
   依存しているがメタデータに無く、欠落していたため。
   ```bash
   VIRTUAL_ENV=.venv uv pip install unitree-webrtc-connect
   ```
2. **`dimos.web.dimos_interface` のスタブを追加** — 上流の `dimensional-interface`
   配布物が PyPI で見つからず、`WebInput` の import が落ちるため
   `.venv/lib/python3.12/site-packages/dimos/web/dimos_interface/` 配下に最小限の
   `FastAPIServer` ダミーを置いている。**ブラウザ UI は無効化されており、
   `dimos agent-send "..."` 経由で指示を送ってください。**
3. **`PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python` を export** — `SpatialMemory`
   が pulls する chromadb → opentelemetry の `_pb2.py` が古く、dimos 6.x の
   protobuf と非互換 (`TypeError: Descriptors cannot be created directly.`)。
   `run_sim.sh` 側で設定済み。
4. **`PATH` に `.venv/bin` を追加** — `RerunBridgeModule` が `rerun` バイナリを
   `subprocess` で起動する際に PATH を見るため。`run_sim.sh` 側で設定済み。

## 起動

ターミナル A —— シミュレーション + agentic スタックを起動:

```bash
./run_sim.sh
```

初回起動時は `mujoco_sim` データのダウンロードが走るため数十秒〜数分かかります。

> 上流側の packaging 不備により、現状はブラウザの WebInput UI は使えません(上の手当参照)。
> 言語入力は次の `agent-send` 経由で行ってください。

ターミナル B —— CLI から自然言語で指示:

```bash
./say.sh "Say hello and then sit down."
./say.sh "Stand up and walk forward a little."
./say.sh "FrontPounce をやって"
```

確認済みの動作: `speak` / `execute_sport_command("Sit"/"RecoveryStand"等)` /
`begin_exploration` 等は sim 上ですぐ動きます。`relative_move` は SLAM の odom
収束が必要で起動直後は "Failed to get the position of the robot." を返すことが
あるため、しばらく(またはマップ生成)してから使用してください。

停止:

```bash
.venv/bin/dimos stop
```

## 使えるスキル

- `relative_move(forward, left, degrees)` — 並進・回転
- `wait(seconds)` — 待機
- `execute_sport_command("FrontPounce"等)` — Unitree のプリセット動作

スキル一覧は実行中に確認できます:

```bash
.venv/bin/dimos mcp list-tools
```

## 実機切り替え

`.env` の `ROBOT_IP=<Go2 の IP>` をセットしたうえで、`run_sim.sh` から
`--simulation` フラグを外す(または `dimos run unitree-go2-agentic` を直接実行)。
IP がわからない場合は `.venv/bin/dimos go2tool discover` で BLE / LAN 検出可。
