#!/usr/bin/env bash
# Launch the agentic blueprint (GPU build) inside Docker against the real Go2.
#
# Usage:
#   docker-gpu/run.sh                       # dimos run unitree-go2-agentic
#   docker-gpu/run.sh humancli              # dimos humancli (Textual TUI)
#   docker-gpu/run.sh shell                 # interactive bash inside container
#   docker-gpu/run.sh say_robot             # lightweight NL REPL (skip agent stack)
#   docker-gpu/run.sh -- dimos run ...      # pass-through any dimos command
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE not found. Required keys: ROBOT_IP, OPENAI_API_KEY" >&2
    exit 1
fi

IMAGE="go2-agentic-gpu:latest"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "Building $IMAGE (first run only)…"
    docker build -t "$IMAGE" -f "$SCRIPT_DIR/Dockerfile" "$REPO_ROOT/dimensional-applications"
fi

COMMON_ARGS=(
    --rm -it
    --name go2-agentic-gpu
    --network host
    --cap-add NET_ADMIN
    --gpus all
    --env-file "$ENV_FILE"
)

case "${1:-}" in
    shell|bash)
        exec docker run "${COMMON_ARGS[@]}" "$IMAGE" bash
        ;;
    humancli)
        exec docker run "${COMMON_ARGS[@]}" "$IMAGE" dimos humancli
        ;;
    say_robot)
        exec docker run "${COMMON_ARGS[@]}" "$IMAGE" python say_robot.py
        ;;
    --)
        shift
        exec docker run "${COMMON_ARGS[@]}" "$IMAGE" "$@"
        ;;
    "")
        exec docker run "${COMMON_ARGS[@]}" "$IMAGE"
        ;;
    *)
        exec docker run "${COMMON_ARGS[@]}" "$IMAGE" "$@"
        ;;
esac
