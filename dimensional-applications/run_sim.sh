#!/usr/bin/env bash
# Launch the Unitree Go2 agentic blueprint in MuJoCo simulation.
# Natural-language input goes via the WebInput UI (printed below) or
# via `./say.sh "<command>"` from another terminal.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

set -a
[ -f .env ] && . ./.env
# chromadb -> opentelemetry ships _pb2.py incompatible with protobuf 6.x;
# fall back to pure-Python parsing so SpatialMemory's chromadb import works.
PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
set +a

# RerunBridge launches the `rerun` binary via subprocess and needs it on PATH.
export PATH="$SCRIPT_DIR/.venv/bin:$PATH"

exec "$SCRIPT_DIR/.venv/bin/dimos" --simulation run unitree-go2-agentic "$@"
