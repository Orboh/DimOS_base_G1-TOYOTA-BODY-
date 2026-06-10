#!/usr/bin/env bash
# Launch the Unitree G1 agentic blueprint in simulation.
# No real G1 required; uses dimos's bundled G1 sim connection.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

set -a
[ -f .env ] && . ./.env
PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
set +a

export PATH="$SCRIPT_DIR/.venv/bin:$PATH"

exec "$SCRIPT_DIR/.venv/bin/dimos" --simulation run unitree-g1-agentic-sim "$@"
