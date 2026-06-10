# Go2 × DimOS — Docker (実機向け)

このディレクトリは `unitree-go2-agentic` ブループリント(DimOS の自然言語エージェント)を
**他PCでもそのまま動かす**ためのコンテナ一式です。ホスト側の `sudo`/Python/uv 設定や
PyPI 上の packaging gap (`dimensional-interface` 欠落) を全部内包しているので、
docker さえあれば動きます。

## 前提

- 他PC側:
  - Docker Engine **24+** と Compose v2 (Ubuntu 22.04+ / Debian 12+ 推奨)
  - LANで Unitree Go2 と同一サブネット(`192.168.123.0/24`)。有線で `192.168.123.x/24` の
    IP が振られていること(`ip -br addr show` で確認)
- リポジトリ直下の `.env` に以下が入っていること:
  - `ROBOT_IP=192.168.123.161` (Go2 メインコンピュータ。EDU/Proの場合)
  - `OPENAI_API_KEY=sk-...`
  - 必要に応じて `ANTHROPIC_API_KEY=...`
- 注意: コンテナは `--network host` で動きます。Linux ホスト前提
  (macOS / Windows Docker Desktop では host network が機能しないため動きません)

## クイックスタート

```bash
# 1. 他PCにこのリポジトリを clone or scp
git clone <repo> && cd dimos-go2
# (または `scp -r dimos-go2 user@other-pc:~/`)

# 2. .env を作る(リポジトリ直下)
cat > .env <<'EOF'
ROBOT_IP=192.168.123.161
OPENAI_API_KEY=sk-...
EOF

# 3. ビルド + 起動(初回は10-15分かかる、依存361パッケージ)
cd dimensional-applications
./docker/run.sh
```

ターミナル A で agentic スタックが立ち上がり、しばらく(モジュールロードに30〜90秒)後に
ready 状態になります。

## 自然言語コマンドを送る

別ターミナルで:

```bash
cd dimos-go2/dimensional-applications
./docker/say.sh "こんにちはと言って"
./docker/say.sh "前に少し進んで"
./docker/say.sh "FrontPounce をやって"
./docker/say.sh "立ち上がって、前に進んで、座って"
```

内部的には `docker exec go2-agentic dimos agent-send "..."` を実行しています。

## 動かない時のフォールバック(LLM不要、軽量NL)

agentic スタックが重すぎる/落ちる時の代替として、`say_robot.py` (LLM なしのキーワード
ベース NL → WebRTC 直叩き) をコンテナ内から実行できます。CPU 負荷ほぼゼロ:

```bash
./docker/run.sh say_robot
# > 前に2秒進んで
# > 右に曲がって
# > 歩き回って      # 30秒の自動徘徊(Go2本体の障害物回避ON)
```

## 構成ファイル

| ファイル | 役割 |
|---|---|
| `Dockerfile` | Ubuntu 24.04 + Python 3.12 + uv で依存をインストール |
| `requirements.txt` | 動作確認済みの pip freeze (361パッケージ、`dimos==0.0.12.post2` 等を固定) |
| `dimos_interface_stub/` | `dimos.web.dimos_interface` 用ダミー (上流 packaging gap 回避) |
| `entrypoint.sh` | LCM multicast 設定 + Go2 疎通チェック後に CMD 実行 |
| `docker-compose.yml` | `docker compose up` 派向け |
| `run.sh` | プレーン docker 派向け、初回はビルドも兼ねる |
| `say.sh` | 起動済みコンテナに NL コマンドを送る |

## どこを直したか(他PC で「動かない」になったら見るところ)

1. **`requirements.txt`** — `uv pip freeze` で固定。CUDA/AMD など環境依存パッケージは
   入っていないので CPU 環境ならそのまま動く想定。
2. **`dimos.web.dimos_interface` スタブ** — `pip install dimos==0.0.12.post2` だけだと
   `dimensional-interface` の import で落ちる。スタブを `site-packages` に差し込んで回避。
3. **LCM multicast** — `dimos` の起動時 sudo を回避するため、コンテナ root から
   `ip link set lo multicast on` + `ip route add 224.0.0.0/4 dev lo` を冪等に実行。
   `--network host` + `--cap-add NET_ADMIN` 必須。
4. **`PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python`** — chromadb の `_pb2.py` が古く、
   dimos の protobuf と非互換になる。環境変数で pure-Python 実装に切り替え。

## トラブルシュート

- **`port 9991 closed` の WARN** — Go2 メインコンピュータの WebRTC が見えていない。
  - LAN ケーブル両端を挿し直す(EDU/Pro なら底面のシルバーポート)
  - `ip -br addr show` でホストに `192.168.123.x/24` が振られているか確認
  - `ping 192.168.123.161` が通るか
- **`CalledProcessError: ip link set lo multicast on`** — `--cap-add NET_ADMIN` 抜け。
  `docker/run.sh` 経由なら自動で付くが、直接 `docker run` する場合は付け忘れ注意。
- **ビルドが OOM** — `requirements.txt` のインストール時に2GB以上のメモリが要る場面あり。
  4GB以上のRAM、推奨は8GB+。Docker Desktop のリソース上限も確認。
- **`docker compose` が古いエラー** — Compose v1 ではなく v2 (`docker compose ...`、
  ハイフン無し) を使ってください。
- **macOS / Windows で動かない** — `--network host` が機能しないので、aiortc が
  ICE candidate を解決できず WebRTC が貼れません。Linux ホストで動かしてください。

## 関連ドキュメント

- 親ディレクトリの `../README.md` — シミュレーション側の起動手順
- `../say_robot.py` — Docker 不要の軽量 NL スクリプト(WebRTC 直叩き、LLM 不要)
