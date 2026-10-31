#!/usr/bin/env python3
"""
spotify-auto-pause

Pauses Spotify when another app starts playing audio and resumes it when that
audio stops, like audio focus on a phone.

How it works:
  * `pactl subscribe` reports every change in the audio streams (sink inputs).
  * On each change, the script lists the streams and checks whether one of the
    configured "trigger" apps is actively playing (not corked).
  * Rising edge (a trigger starts, and stays active for `debounce_seconds`):
    Spotify is paused with `playerctl`.
  * Falling edge (no trigger left): Spotify is resumed, but only if this
    script was the one that paused it.

Only the configured player is ever controlled. Other media players are never
touched, so the app that triggered the pause is not affected.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

VERSION = "1.0.0"

DEFAULT_CONFIG = {
    # MPRIS player name (what `playerctl -l` prints). Its own audio stream is
    # never counted as a trigger.
    "player": "spotify",
    # An audio stream is a trigger when any of these texts appears in its app
    # name, executable name or stream title (case-insensitive).
    "trigger_apps": [
        "firefox", "chrom", "brave", "vivaldi", "opera",
        "vlc", "mpv", "webrtc",
    ],
    # Streams matching any of these texts never trigger a pause (checked first).
    "ignore_apps": [],
    # The audio must stay active this long (seconds) before Spotify is paused.
    # Filters out notification sounds and streams that open and close quickly.
    "debounce_seconds": 0.5,
    # Print every audio event to the log (journalctl).
    "verbose": False,
}


def log(message):
    print(message, flush=True)


def config_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "spotify-auto-pause", "config.json")


def clean_list(values):
    if not isinstance(values, list):
        return []
    return [str(v).strip().lower() for v in values if str(v).strip()]


def load_config(path):
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(path, encoding="utf-8") as f:
            user = json.load(f)
        if not isinstance(user, dict):
            raise ValueError("top level must be a JSON object")
    except FileNotFoundError:
        user = {}
    except (OSError, ValueError) as err:
        log(f"[warn] could not read {path}: {err} - using defaults")
        user = {}

    for key in DEFAULT_CONFIG:
        if key in user:
            cfg[key] = user[key]
    for key in user:
        if key not in DEFAULT_CONFIG:
            log(f"[warn] unknown config key ignored: {key}")

    cfg["player"] = str(cfg["player"]).strip().lower() or "spotify"
    cfg["trigger_apps"] = clean_list(cfg["trigger_apps"])
    cfg["ignore_apps"] = clean_list(cfg["ignore_apps"])
    try:
        cfg["debounce_seconds"] = max(0.0, float(cfg["debounce_seconds"]))
    except (TypeError, ValueError):
        cfg["debounce_seconds"] = DEFAULT_CONFIG["debounce_seconds"]
    cfg["verbose"] = bool(cfg["verbose"])
    return cfg


def require_tools():
    missing = [t for t in ("pactl", "playerctl") if shutil.which(t) is None]
    if missing:
        sys.exit(
            "error: missing required tool(s): " + ", ".join(missing) + "\n"
            "  playerctl -> package 'playerctl'\n"
            "  pactl     -> package 'libpulse' (Arch) or 'pulseaudio-utils' (Debian/Fedora)"
        )


def list_streams():
    """Return the active audio streams as a list of simple dicts."""
    try:
        out = subprocess.check_output(
            ["pactl", "-f", "json", "list", "sink-inputs"],
            stderr=subprocess.DEVNULL,
        )
        data = json.loads(out) if out.strip() else []
    except (subprocess.CalledProcessError, ValueError):
        return []

    streams = []
    for item in data:
        props = item.get("properties", {})
        streams.append({
            "name": str(props.get("application.name", "")).lower(),
            "binary": str(props.get("application.process.binary", "")).lower(),
            "media": str(props.get("media.name", "")).lower(),
            "corked": bool(item.get("corked", False)),
        })
    return streams


def classify(stream, cfg):
    """Explain what the script does with a stream."""
    if stream["name"] == cfg["player"]:
        return "player itself"
    fields = (stream["name"], stream["binary"], stream["media"])
    if any(ign in f for ign in cfg["ignore_apps"] for f in fields):
        return "ignored"
    if not any(t in f for t in cfg["trigger_apps"] for f in fields):
        return "not a trigger"
    if stream["corked"]:
        return "trigger, but idle"
    return "TRIGGER"


def find_trigger(cfg):
    """Description of the stream that is triggering a pause, or None."""
    for stream in list_streams():
        if classify(stream, cfg) == "TRIGGER":
            return "{name} | binary={binary} | media={media}".format(**stream)
    return None


def player_status(player):
    result = subprocess.run(
        ["playerctl", "-p", player, "status"],
        capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def player_do(player, action):
    subprocess.run(["playerctl", "-p", player, action],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def print_streams(cfg):
    streams = list_streams()
    if not streams:
        print("No audio streams right now. Start playing something and run this again.")
        return
    print(f"{'APP NAME':<22} {'BINARY':<18} {'STREAM TITLE':<24} {'CORKED':<7} RESULT")
    for s in streams:
        print(f"{s['name'][:21]:<22} {s['binary'][:17]:<18} {s['media'][:23]:<24} "
              f"{str(s['corked']):<7} {classify(s, cfg)}")


def run(cfg):
    player = cfg["player"]
    was_active = False
    paused_by_script = False

    log(f"[info] spotify-auto-pause {VERSION} started | player={player} | "
        f"triggers={cfg['trigger_apps']} | ignore={cfg['ignore_apps']} | "
        f"debounce={cfg['debounce_seconds']}s")

    proc = subprocess.Popen(
        ["pactl", "subscribe"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, bufsize=1,
    )

    for line in proc.stdout:
        if "sink-input" not in line:
            continue

        culprit = find_trigger(cfg)

        # Rising edge: only act if the audio is still there after the debounce.
        if culprit and not was_active:
            first_seen = culprit
            if cfg["debounce_seconds"] > 0:
                time.sleep(cfg["debounce_seconds"])
            culprit = find_trigger(cfg)
            if not culprit:
                if cfg["verbose"]:
                    log(f"[debug] too short, ignored (was: {first_seen})")
                continue

        now_active = culprit is not None

        if now_active and not was_active:
            status = player_status(player)
            log(f"[info] triggered by: {culprit} | {player} status: {status}")
            if status == "Playing":
                player_do(player, "pause")
                paused_by_script = True
                log(f"[info] paused {player}")

        elif not now_active and was_active:
            if cfg["verbose"]:
                log("[debug] trigger audio stopped")
            if paused_by_script:
                # Resume only if nobody started or stopped it in the meantime.
                if player_status(player) == "Paused":
                    player_do(player, "play")
                    log(f"[info] resumed {player}")
                paused_by_script = False

        was_active = now_active

    sys.exit("error: 'pactl subscribe' ended unexpectedly (is the audio server running?)")


def main():
    parser = argparse.ArgumentParser(
        description="Pause Spotify when another app plays audio, resume when it stops.")
    parser.add_argument("--list", action="store_true",
                        help="show the audio streams playing right now and how each one is treated, then exit")
    parser.add_argument("--config", metavar="FILE",
                        help=f"config file (default: {config_path()})")
    parser.add_argument("--version", action="version", version=VERSION)
    args = parser.parse_args()

    cfg = load_config(args.config or config_path())
    require_tools()

    if args.list:
        print_streams(cfg)
    else:
        run(cfg)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
