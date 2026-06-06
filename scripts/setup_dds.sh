#!/usr/bin/env bash
# Cyclone DDS + dimos[unitree-dds] セットアップスクリプト
# Ubuntu 22.04 + Python 3.12 (uv) 想定
# 中国ネット環境では Tsinghua mirror を使用

set -e

INSTALL_PREFIX="$HOME/cyclonedds-install"
SRC_DIR="$HOME/cyclonedds-src"
DIMOS_DIR="$HOME/Desktop/dimos-hackathon"
PYPI_MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"
CYCLONEDDS_VERSION="0.10.5"

echo "=========================================="
echo "STEP 0: 前提チェック"
echo "=========================================="
[ -d "$DIMOS_DIR" ] || { echo "❌ $DIMOS_DIR が無い"; exit 1; }
command -v cmake >/dev/null || { echo "⚠️  cmake が無い → apt install します"; sudo apt-get update && sudo apt-get install -y build-essential cmake git; }
echo "✅ 前提OK"
echo ""

echo "=========================================="
echo "STEP 1: Cyclone DDS C++ ${CYCLONEDDS_VERSION} をビルド"
echo "=========================================="
if [ -f "$INSTALL_PREFIX/lib/libddsc.so" ] || [ -f "$INSTALL_PREFIX/lib/x86_64-linux-gnu/libddsc.so" ]; then
    echo "✅ 既にビルド済み ($INSTALL_PREFIX) → スキップ"
else
    if [ ! -d "$SRC_DIR" ]; then
        git clone --branch "$CYCLONEDDS_VERSION" --depth 1 \
            https://github.com/eclipse-cyclonedds/cyclonedds.git "$SRC_DIR"
    fi
    mkdir -p "$SRC_DIR/build"
    cd "$SRC_DIR/build"
    cmake -DCMAKE_INSTALL_PREFIX="$INSTALL_PREFIX" \
          -DBUILD_EXAMPLES=OFF \
          -DBUILD_TESTING=OFF \
          -DBUILD_IDLC=ON \
          ..
    make -j"$(nproc)"
    make install
    echo "✅ Cyclone DDS ビルド＆インストール完了 → $INSTALL_PREFIX"
fi
echo ""

echo "=========================================="
echo "STEP 2: 環境変数を ~/.bashrc に永続化"
echo "=========================================="
if grep -q "CYCLONEDDS_HOME" "$HOME/.bashrc"; then
    echo "✅ 既に .bashrc に登録済み → スキップ"
else
    cat >> "$HOME/.bashrc" <<EOF

# Cyclone DDS (dimos[unitree-dds])
export CYCLONEDDS_HOME=\$HOME/cyclonedds-install
export LD_LIBRARY_PATH=\$HOME/cyclonedds-install/lib:\$LD_LIBRARY_PATH
EOF
    echo "✅ .bashrc に追記完了"
fi

# 現在のシェルにも反映
export CYCLONEDDS_HOME="$INSTALL_PREFIX"
export LD_LIBRARY_PATH="$INSTALL_PREFIX/lib:${LD_LIBRARY_PATH:-}"
echo "  CYCLONEDDS_HOME=$CYCLONEDDS_HOME"
echo ""

echo "=========================================="
echo "STEP 3: uv sync で unitree-dds extra を追加"
echo "=========================================="
cd "$DIMOS_DIR"
uv sync --frozen --extra all --extra unitree-dds \
    --index-url "$PYPI_MIRROR"
echo "✅ uv sync 完了"
echo ""

echo "=========================================="
echo "STEP 4: 動作確認"
echo "=========================================="
cd "$DIMOS_DIR"
# shellcheck disable=SC1091
source .venv/bin/activate
python - <<'PYEOF'
import sys
ok = True
try:
    from cyclonedds.domain import DomainParticipant
    print("✅ cyclonedds import OK")
except Exception as e:
    print(f"❌ cyclonedds import failed: {e}")
    ok = False

try:
    import unitree_sdk2py
    print("✅ unitree_sdk2py import OK")
except Exception as e:
    print(f"❌ unitree_sdk2py import failed: {e}")
    ok = False

sys.exit(0 if ok else 1)
PYEOF

echo ""
echo "=========================================="
echo "🎉 全ステップ成功"
echo "=========================================="
echo "次のターミナルからは 'source ~/.bashrc' or 新規ターミナルで自動有効化されます"
