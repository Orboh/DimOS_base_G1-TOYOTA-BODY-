#!/usr/bin/env python3
"""Natural-language control for the Unitree Go2 via WebRTC.

Usage:
    say_robot.py "前に進んで"      # one-shot
    say_robot.py                    # interactive REPL
    say_robot.py wander             # ~30s explore mode (built-in obstacle avoidance)

Lightweight alternative to `dimos run unitree-go2-agentic`: connects to ROBOT_IP
once, enables the Go2's onboard obstacle-avoidance, then maps Japanese/English
keywords to direct WebRTC commands. No forkserver pool, no agent loop.
"""
import os
import random
import re
import sys
import time
from pathlib import Path

_env = Path(__file__).resolve().parent.parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

from dimos.msgs.geometry_msgs.Twist import Twist  # noqa: E402
from dimos.robot.unitree.connection import UnitreeWebRTCConnection  # noqa: E402
from unitree_webrtc_connect.constants import RTC_TOPIC, SPORT_CMD  # noqa: E402

DEFAULT_SPEED = 0.35   # m/s, indoor-safe
DEFAULT_YAW   = 0.8    # rad/s
DEFAULT_DUR   = 2.0    # seconds per directional command

PRESETS = {
    "hello":       "Hello",
    "wave":        "Hello",
    "こんにちは":  "Hello",
    "挨拶":        "Hello",
    "手を振":      "Hello",
    "stretch":     "Stretch",
    "ストレッチ":  "Stretch",
    "伸び":        "Stretch",
    "dance":       "Dance1",
    "dance1":      "Dance1",
    "dance2":      "Dance2",
    "踊":          "Dance1",
    "wiggle":      "WiggleHips",
    "お尻":        "WiggleHips",
    "heart":       "FingerHeart",
    "ハート":      "FingerHeart",
    "pounce":      "FrontPounce",
    "前飛び":      "FrontPounce",
    "sit":         "Sit",
    "座":          "Sit",
}


def parse_duration(text: str) -> float:
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:秒|s\b|sec)", text)
    return float(m.group(1)) if m else DEFAULT_DUR


def parse_speed(text: str) -> float:
    if any(k in text for k in ("ゆっくり", "slow", "そっと")):
        return DEFAULT_SPEED * 0.5
    if any(k in text for k in ("速く", "fast", "急い", "ダッシュ")):
        return min(DEFAULT_SPEED * 1.5, 0.6)
    return DEFAULT_SPEED


def send_move(conn, forward=0.0, strafe=0.0, yaw=0.0, duration=DEFAULT_DUR):
    """Send a velocity command. dimos Twist convention (see KeyboardTeleop):
    linear.x = forward(+)/back(-), linear.y = strafe left(+)/right(-),
    angular.z = turn left(+)/right(-).
    """
    t = Twist()
    t.linear.x = forward
    t.linear.y = strafe
    t.angular.z = yaw
    return conn.move(t, duration=duration)


def wander(conn, total_seconds=30):
    print(f"  wandering ~{total_seconds}s (onboard avoidance on, ctrl-C to stop)…", flush=True)
    end = time.time() + total_seconds
    try:
        while time.time() < end:
            send_move(conn, forward=DEFAULT_SPEED, duration=3.0)
            yaw = random.choice([-1, 1]) * DEFAULT_YAW * random.uniform(0.4, 1.0)
            send_move(conn, yaw=yaw, duration=random.uniform(0.4, 1.2))
    except KeyboardInterrupt:
        print("  (interrupted)")
    conn.stop_movement()
    return "wander done"


def dispatch(conn, text):
    raw = text.strip()
    low = raw.lower()
    dur = parse_duration(raw)
    v = parse_speed(raw)

    if any(k in raw for k in ("止ま", "停止", "stop")):
        conn.stop_movement()
        return "stop"

    if any(k in raw for k in ("立っ", "立て", "立ち上", "standup", "stand up")):
        conn.standup()
        return "standup"
    if any(k in raw for k in ("伏せ", "liedown", "lie down", "lay down")):
        conn.liedown()
        return "liedown"
    if any(k in raw for k in ("バランス", "balance")):
        conn.balance_stand()
        return "balance_stand"

    for kw, preset in PRESETS.items():
        if kw in low or kw in raw:
            conn.publish_request(RTC_TOPIC["SPORT_MOD"], {"api_id": SPORT_CMD[preset]})
            return f"preset:{preset}"

    if any(k in raw for k in ("歩き回", "探検", "散歩", "うろうろ", "wander", "explore", "patrol")):
        return wander(conn, total_seconds=30)

    is_turn = any(k in raw for k in ("回", "曲が", "ターン", "turn", "rotate"))
    if any(k in raw for k in ("左", "left")):
        if is_turn:
            send_move(conn, yaw=+DEFAULT_YAW, duration=dur)
            return f"turn left {dur}s"
        send_move(conn, strafe=+v, duration=dur)
        return f"strafe left {dur}s"
    if any(k in raw for k in ("右", "right")):
        if is_turn:
            send_move(conn, yaw=-DEFAULT_YAW, duration=dur)
            return f"turn right {dur}s"
        send_move(conn, strafe=-v, duration=dur)
        return f"strafe right {dur}s"
    if any(k in raw for k in ("前", "進", "forward", "ahead", "go")):
        send_move(conn, forward=+v, duration=dur)
        return f"forward {dur}s @ {v:.2f}m/s"
    if any(k in raw for k in ("後", "戻", "back")):
        send_move(conn, forward=-v, duration=dur)
        return f"back {dur}s @ {v:.2f}m/s"

    return None


def main():
    ip = os.environ.get("ROBOT_IP", "192.168.123.161")
    print(f"connecting to Go2 at {ip}…", flush=True)
    conn = UnitreeWebRTCConnection(ip=ip)
    print("connected. balance_stand + obstacle avoidance ON.", flush=True)
    try:
        conn.balance_stand()
        time.sleep(0.4)
        try:
            conn.set_obstacle_avoidance(True)
        except Exception as e:
            print(f"  (avoidance toggle failed, continuing: {e})")

        if len(sys.argv) > 1:
            text = " ".join(sys.argv[1:])
            result = dispatch(conn, text)
            if result is None:
                print(f"? 認識できませんでした: {text!r}")
                return 2
            print(f"→ {result}")
            return 0

        print("type a command (jp/en). 'quit' to exit.")
        print("examples: 前に進んで / 右に曲がって / こんにちは / 歩き回って / stop")
        while True:
            try:
                text = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not text:
                continue
            if text in ("quit", "exit", "q", "終了"):
                break
            try:
                result = dispatch(conn, text)
                print(f"  → {result}" if result else "  (?) 認識できませんでした")
            except Exception as e:
                print(f"  error: {e}")
        return 0
    finally:
        print("disconnecting…", flush=True)
        try:
            conn.stop_movement()
        except Exception:
            pass
        try:
            conn.set_obstacle_avoidance(False)
        except Exception:
            pass
        try:
            conn.stop()
        except Exception as e:
            print(f"disconnect err (non-fatal): {e}")


if __name__ == "__main__":
    sys.exit(main())
