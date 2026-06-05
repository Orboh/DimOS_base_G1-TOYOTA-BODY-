# Unitree G1 — ラップトップ単体でのクリック移動（Orboh版手順）

**検証済み: 2026-06-05（実機G1）** — PCのdimosだけでG1をクリックナビゲーションさせる手順。
公式の [`index.md`](./index.md) はロボットのNX上でdimosを動かす構成（`unitree-g1-nav-onboard`）だが、本手順は **G1側に何もインストールしない**。

使用ブループリント: **`unitree-g1-nav-laptop`**
（`unitree-g1-nav-onboard` のバリアント。LiDAR受信IPとDDSのNICをPC側で自動検出する）

## 構成

```
Mid-360 LiDAR (192.168.123.120) ──UDP(~5MB/s)──> PC: FastLIO2 (SLAM)
                                                      ↓
                                  navスタック (TerrainAnalysis / SimplePlanner /
                                   LocalPlanner / PathFollower / PGO)
                                                      ↓ cmd_vel
PC: Rerun viewer クリック → MovementManager → G1HighLevelDdsSdk ──DDS──> G1歩行
```

## 前提条件

- Unitree G1 EDU、PC は Ubuntu 22.04/24.04
- PC を G1 に **Ethernet 直結**し、固定IPを設定（例: `192.168.123.212/24`）
  - 確認: `ping 192.168.123.164`（NX）と `ping 192.168.123.120`（LiDAR）が両方通ること
- dimos のインストール（このリポジトリ、`uv sync` 済みの venv）

## 1. nix のインストール（初回のみ）

ネイティブモジュール（C++）のビルドに必要：

```bash
curl -fsSL https://install.determinate.systems/nix | sh -s -- install
# インストール後、新しいターミナルを開くか:
. /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
```

## 2. ネイティブモジュールの事前ビルド（初回のみ）

⚠️ **5モジュール全部**が必要。`dimos run` 内の自動ビルドに任せると、nixがPATHにないシェルでは
`nix: not found (exit 127)` で全モジュール巻き添えクラッシュする
（[FleetSeek exp_01KTASFAEVY95HY2CFZ13VNWFE 参照](https://web-ebon-zeta-33.vercel.app/experience/exp_01KTASFAEVY95HY2CFZ13VNWFE)）。

```bash
. /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
cd dimos/hardware/sensors/lidar/fastlio2/cpp && nix build .#fastlio2_native && cd -
cd dimos/navigation/nav_stack/modules
(cd local_planner    && nix build "github:dimensionalOS/dimos-module-local-planner/v0.6.0"    --no-write-lock-file)
(cd terrain_analysis && nix build "github:dimensionalOS/dimos-module-terrain-analysis/v0.1.1" --no-write-lock-file)
(cd path_follower    && nix build "github:dimensionalOS/dimos-module-path-follower/v0.2.0"    --no-write-lock-file)
(cd pgo/cpp          && nix build .#default --no-write-lock-file)
```

各モジュールの**自分のディレクトリ内**で実行すること（`result/` シンボリックリンクの位置を
`dimos/core/native_module.py` がモジュールファイル基準で解決するため）。
ビルド済みなら以後 `dimos run` にnixは不要。

## 3. G1 をバランス立ちさせる

コントローラーで: **L2+B → L2+Up →（立たせて）R2+A**
起動ログに `Current motion mode: ai` が出ればOK。立っていないと歩行コマンドは効かない。

## 4. 起動

```bash
source .venv/bin/activate
dimos run unitree-g1-nav-laptop
# 初回はLCM multicast / socket bufferのシステム設定を聞かれるので y
```

ネットワークは自動検出される。手動で上書きしたい場合：

```bash
ROBOT_INTERFACE=<NIC名> LIDAR_HOST_IP=<PCのIP> LIDAR_IP=192.168.123.120 dimos run unitree-g1-nav-laptop
```

**正常起動の目印（ログ）:**
- `FastLio2 network check passed host_ip=<PCのIP>`
- `Initializing DDS on interface: <NIC名>` → `Motion switcher initialized` → `G1 DDS SDK connection started`
- 起動直後の `No direct transform found between 'map' and 'body'` 警告は最初のスキャン処理までの一過性のもの

## 5. クリックで移動

dimosが**Rerun viewerを自動で開く**。3Dビューに点群と地図が出たら、床をクリック → 経路が引かれてG1が歩く。

viewerを別途開く場合（Python 3.13のwheelが無いので3.12指定が必須）：

```bash
uvx --python 3.12 dimos-viewer --connect rerun+http://localhost:9877/proxy --ws-url ws://localhost:3030/ws
```

## トラブルシューティング

| 症状 | 対処 |
|---|---|
| `nix: not found (exit 127)` で全NativeModuleがクラッシュ | 手順1のprofileをsourceするか新ターミナル。または手順2の事前ビルド |
| `uvx dimos-viewer` が `cp313` ABIエラー | `--python 3.12` を付ける |
| 地図が出ない / 点群が来ない | `cat /sys/class/net/<NIC>/statistics/rx_bytes` を2回見て差分確認（Mid-360は約5MB/s）。0ならLiDARへの疎通(.120へping)と固定IPを確認 |
| クリックしても歩かない | ロボットがバランス立ちか確認（手順3）。ログの `MovementManager` が `Ignored out-of-range click` を出していないか確認 |
| viewerクラッシュ | ブループリント内 `vis_throttle=0.5` を 0.3 に下げる |

## オプション: 頭部カメラ（WebRTC）— ⚠️ 実機未検証

`unitree-g1-nav-laptop-cam` は上記スタックに `G1Connection`（WebRTC）をカメラ専用で追加する
（`cmd_vel` はremapで切断済み — 歩行コマンドはDDS側の一本のみ）。

```bash
ROBOT_IP=192.168.123.164 dimos run unitree-g1-nav-laptop-cam
```

- G1のRealSense (USB接続のdepth等) はネットワークに流れないため取得不可。これはUnitreeアプリと同じWebRTC映像
- **G1のWebRTCサービスが映像トラックを返すかは未検証**。`UnitreeWebRTCConnection` は接続不能時に
  タイムアウト無しで永久ブロックするため、起動がG1Connectionで止まる場合はWebRTC非対応と判断し
  `unitree-g1-nav-laptop` に戻ること
- モジュール側は `G1Connection` の `enable_video`（デフォルトFalse）でオプトイン。既存スタック
  （`unitree-g1` 等）でWebカメラと映像が混流しないようにするため

## 安全上の注意

- 最初のクリックは**1〜2m先**、コントローラーを手元に
- 有線テザー接続のままロボットが歩くので、ケーブルの取り回しに注意

## 記録

- FleetSeek (skill): [exp_01KTATP3CEFK59MMZ25XWTP81H](https://web-ebon-zeta-33.vercel.app/experience/exp_01KTATP3CEFK59MMZ25XWTP81H)
- FleetSeek (debug_note): [exp_01KTASFAEVY95HY2CFZ13VNWFE](https://web-ebon-zeta-33.vercel.app/experience/exp_01KTASFAEVY95HY2CFZ13VNWFE)
