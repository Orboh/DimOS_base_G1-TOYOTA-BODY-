#!/usr/bin/env bash
# Send a natural-language command into the running agentic container.
# Pairs with `docker/run.sh` (which starts the container as `go2-agentic`).
#
# Usage:
#   docker/say.sh "前に進んで"
#   docker/say.sh "Sit down and wave hello."
set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 \"<command>\"" >&2
    exit 1
fi

exec docker exec -it go2-agentic dimos agent-send "$*"
