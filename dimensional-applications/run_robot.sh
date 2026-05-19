#!/usr/bin/env bash
# Launch the Unitree Go2 agentic blueprint against the real robot via WebRTC.
# Natural-language input goes via `./say.sh "<command>"` from another terminal.
# Requires ROBOT_IP set in ../.env (and the laptop on the same network as Go2).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

set -a
[ -f .env ] && . ./.env
PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
set +a

if [ -z "${ROBOT_IP:-}" ]; then
  echo "ROBOT_IP is not set in .env. Set it to the Go2's IP (e.g. 192.168.123.18) before running." >&2
  exit 1
fi

export PATH="$SCRIPT_DIR/.venv/bin:$PATH"

exec "$SCRIPT_DIR/.venv/bin/dimos" run unitree-go2-agentic "$@"
