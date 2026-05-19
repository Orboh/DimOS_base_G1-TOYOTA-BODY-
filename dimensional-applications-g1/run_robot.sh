#!/usr/bin/env bash
# Launch the Unitree G1 agentic blueprint against the real robot via WebRTC.
# Natural-language input goes via `./say.sh "<command>"` or `dimos humancli`.
# Requires ROBOT_IP_G1 set in ../.env (G1's IP on your LAN).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

set -a
[ -f .env ] && . ./.env
PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
set +a

# G1 uses ROBOT_IP_G1 to keep its address distinct from the Go2's ROBOT_IP.
if [ -z "${ROBOT_IP_G1:-}" ]; then
    echo "ROBOT_IP_G1 is not set in .env. Set it to the G1's IP before running." >&2
    echo "Tip: $SCRIPT_DIR/.venv/bin/dimos go2tool discover" >&2
    exit 1
fi

# Override the global ROBOT_IP just for this launch (dimos reads ROBOT_IP).
export ROBOT_IP="$ROBOT_IP_G1"
export PATH="$SCRIPT_DIR/.venv/bin:$PATH"

exec "$SCRIPT_DIR/.venv/bin/dimos" run unitree-g1-agentic "$@"
