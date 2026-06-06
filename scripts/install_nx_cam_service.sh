#!/usr/bin/env bash
# Install the G1 head-camera ZMQ publisher as a boot-time systemd service
# on the NX. Run FROM THE LAPTOP; prompts for the NX password (ssh + sudo).
#
# Usage: scripts/install_nx_cam_service.sh [user@host]   (default: unitree@192.168.123.164)
set -euo pipefail

NX="${1:-unitree@192.168.123.164}"
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "==> Copying publisher + unit file to $NX"
scp "$HERE/uvc_zmq_publisher.py" "$HERE/g1-cam-publisher.service" "$NX:/tmp/"

echo "==> Installing service (sudo password will be asked on the NX)"
ssh -t "$NX" '
  set -e
  install -m 755 /tmp/uvc_zmq_publisher.py "$HOME/uvc_zmq_publisher.py"
  sudo install -m 644 /tmp/g1-cam-publisher.service /etc/systemd/system/g1-cam-publisher.service
  sudo systemctl daemon-reload
  sudo systemctl enable --now g1-cam-publisher
  sleep 3
  systemctl status g1-cam-publisher --no-pager -l | head -12
'

echo "==> Verifying ZMQ port from the laptop"
HOST="${NX#*@}"
if timeout 3 bash -c "echo > /dev/tcp/$HOST/5555" 2>/dev/null; then
    echo "✅ g1-cam-publisher is up — tcp://$HOST:5555 open"
else
    echo "❌ port 5555 still closed — check: ssh $NX journalctl -u g1-cam-publisher -n 20"
    exit 1
fi
