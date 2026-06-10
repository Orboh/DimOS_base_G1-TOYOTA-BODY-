# Unitree G1 × DimOS — 自然言語で動かす

`../dimensional-applications/`(Go2)と並列に置いた G1 専用ディレクトリです。
**venv と GPU docker イメージは Go2 側と共有**しています(dimos の同じインストールに
G1 用 blueprint が同梱されているため、再ビルド不要)。

## 共有しているもの

- `.venv/` → `../dimensional-applications/.venv` への symlink
- Docker image: `go2-agentic-gpu:latest`(イメージ名はそのまま使う。中身は機体非依存)

## 機体固有のもの

- `.env` の `ROBOT_IP_G1` ←→ Go2 側の `ROBOT_IP`(両方を残しておけば共存可)
- 起動コマンドの blueprint: `unitree-g1-agentic` / `unitree-g1-agentic-sim`
- ほかにも dimos には `unitree-g1-basic`, `unitree-g1-joystick`, `unitree-g1-coordinator`,
  `unitree-g1-detection`, `unitree-g1-full`, `unitree-g1-shm` 等多数。

## セットアップ

1. `../.env` に `ROBOT_IP_G1=<G1の IP>` を追加(`ROBOT_IP=192.168.123.161` は Go2 用に残しておく)
2. PC を G1 と同 LAN に置く。IP がわからなければ `.venv/bin/dimos go2tool discover` で探索

## 起動 — venv 直叩き

ターミナル A(エージェント起動):

```bash
./run_robot.sh           # 実機
# または
./run_sim.sh             # シミュレーション
```

ターミナル B(言語入力):

```bash
.venv/bin/dimos humancli            # Textual TUI(推奨)
# または
./say.sh "立って"
./say.sh "右手を上げて"
```

停止:

```bash
.venv/bin/dimos stop
```

## 起動 — Docker

```bash
./docker-gpu/run.sh                  # dimos run unitree-g1-agentic
./docker-gpu/run.sh humancli         # TUI 直結
./docker-gpu/run.sh shell            # 中で何でも
```

Go2 のコンテナと同時起動はできません(コンテナ名は `go2-agentic-gpu-g1` で別ですが、
`--network host` + LCM の都合で 2 つは衝突します)。切り替えて使ってください。

## 注意

- G1 は二足歩行なので、Go2 の「FrontPounce」のような sport コマンドはありません。
  `UnitreeG1SkillContainer` が公開するスキルは別物(`stand_up`, `bow`, `wave_hand` 系)。
- システムプロンプトは blueprint 側に同梱されているので、humancli 起動時に
  自動で G1 用のものに切り替わります。
- WebRTC のポートや認証フローは Go2 と異なる可能性があり、初回接続でエラーが出たら
  `.venv/lib/python3.12/site-packages/dimos/robot/unitree/g1/connection.py` を参照。
