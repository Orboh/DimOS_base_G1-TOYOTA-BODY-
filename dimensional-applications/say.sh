#!/usr/bin/env bash
# Send a natural-language command to the running DimOS agent.
# Requires `./run_sim.sh` (or `dimos run ...`) to be running in another terminal.

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 \"<command>\"" >&2
  echo "Example: $0 \"少し前に進んで\"" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/.venv/bin/dimos" agent-send "$*"
