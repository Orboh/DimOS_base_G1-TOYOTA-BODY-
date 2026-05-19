#!/usr/bin/env python3
"""Minimal direct-control script for Go2 via dimos's WebRTC wrapper.

Usage:
    standup.py standup        # StandUp
    standup.py balance_stand  # BalanceStand (neutral standing)
    standup.py liedown        # Lie down
    standup.py hello          # Wave a paw (preset)

Connects to ROBOT_IP from .env (defaults to 192.168.123.161). Disconnects cleanly
on exit so the WebRTC peer slot is freed for the next run.
"""
import os
import sys
import time
from pathlib import Path

# Load .env so ROBOT_IP / PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION are set before imports.
_env = Path(__file__).resolve().parent.parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

from dimos.robot.unitree.connection import UnitreeWebRTCConnection  # noqa: E402

# Map argv → (method_name, kwargs) or (publish_request, topic_key, data) for presets.
SPORT_PRESETS = {
    "hello":         "Hello",
    "stretch":       "Stretch",
    "front_pounce":  "FrontPounce",
    "front_flip":    "FrontFlip",
    "dance1":        "Dance1",
    "dance2":        "Dance2",
}


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "balance_stand"
    ip = os.environ.get("ROBOT_IP", "192.168.123.161")
    if not ip:
        print("ROBOT_IP not set in .env", file=sys.stderr)
        return 2

    print(f"[+0.0s] Connecting to Go2 at {ip}…", flush=True)
    t0 = time.time()
    conn = UnitreeWebRTCConnection(ip=ip)
    print(f"[+{time.time()-t0:.1f}s] connected, sending {cmd!r}", flush=True)

    try:
        if cmd == "standup":
            ok = conn.standup()
        elif cmd == "balance_stand":
            ok = conn.balance_stand()
        elif cmd == "liedown":
            ok = conn.liedown()
        elif cmd in SPORT_PRESETS:
            from unitree_webrtc_connect.constants import RTC_TOPIC, SPORT_CMD
            ok = bool(conn.publish_request(
                RTC_TOPIC["SPORT_MOD"],
                {"api_id": SPORT_CMD[SPORT_PRESETS[cmd]]},
            ))
        else:
            print(f"unknown command: {cmd!r}", file=sys.stderr)
            print(f"available: standup, balance_stand, liedown, {', '.join(SPORT_PRESETS)}", file=sys.stderr)
            return 2

        print(f"[+{time.time()-t0:.1f}s] command sent (ok={ok}); waiting 3s for motion…", flush=True)
        time.sleep(3.0)
    finally:
        print(f"[+{time.time()-t0:.1f}s] disconnecting…", flush=True)
        try:
            conn.stop()
        except Exception as e:
            print(f"disconnect error (non-fatal): {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
