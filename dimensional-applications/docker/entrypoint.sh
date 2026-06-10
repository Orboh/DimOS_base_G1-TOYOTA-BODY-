#!/usr/bin/env bash
# Container entrypoint — prepares LCM multicast on the (host-shared) loopback,
# verifies WebRTC reachability, then execs the command.
set -euo pipefail

# Required env passed via --env-file / -e:
: "${ROBOT_IP:?ROBOT_IP must be set (e.g. 192.168.123.161)}"

# LCM multicast: dimos publishes/subscribes on 224.0.0.0/4 over `lo`.
# `--network host` means we share the host's loopback, so this also affects the
# host (idempotent — no-op if already set).
if ! ip -d link show lo 2>/dev/null | grep -q '\<MULTICAST\>'; then
    ip link set lo multicast on || true
fi
if ! ip route show 224.0.0.0/4 2>/dev/null | grep -q '\<dev lo\>'; then
    ip route add 224.0.0.0/4 dev lo 2>/dev/null || true
fi

# Pre-flight: warn (don't fail) if Go2 WebRTC port is unreachable.
if ! nc -z -w 2 "${ROBOT_IP}" 9991 2>/dev/null; then
    echo "WARN: ${ROBOT_IP}:9991 is unreachable — check LAN cable / Go2 power."
    echo "      Continuing anyway; dimos will fail to connect if the port stays closed."
fi

cd /app/dimensional-applications
exec "$@"
