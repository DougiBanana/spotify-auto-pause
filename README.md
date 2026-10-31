# spotify-auto-pause

Pauses Spotify automatically when another app starts playing audio, and resumes it when that audio stops. Like audio focus on a phone, but for the Linux desktop.

Português: veja [README.pt-BR.md](README.pt-BR.md).

## How it works

A small background service (systemd user service) watches the audio streams of your system. When an app on your trigger list (a browser, VLC, mpv, a call...) starts playing sound, Spotify is paused. When that sound stops, Spotify is resumed.


*this tool is Linux only, feel free to fork it to windows*

- Only Spotify is ever controlled. The app that triggered the pause is never touched.
- Spotify's own audio never counts as a trigger.
- Apps that are not on the trigger list (games, for example) never pause Spotify.
- Spotify is resumed only if the script was the one that paused it, so it will not start music you stopped yourself.
- A short delay (0.5 s by default) filters out notification sounds and streams that open and close quickly.

## Requirements

| Needed | Package (Arch) | Package (Debian/Ubuntu, Fedora, openSUSE) |
|---|---|---|
| Python 3 | `python` | `python3` |
| `playerctl` | `playerctl` | `playerctl` |
| `pactl` with JSON output (PulseAudio 15+ or PipeWire with `pipewire-pulse`) | `libpulse` | `pulseaudio-utils` |
| systemd user session | included | included |

The installer checks these and offers to install the missing ones (pacman, apt, dnf and zypper are supported).

## Install

```bash
git clone https://github.com/DougiBanana/spotify-auto-pause.git
cd spotify-auto-pause
./install.sh
```

If `./install.sh` says permission denied, run `bash install.sh` instead.

The installer:
- copies the script to `~/.local/share/spotify-auto-pause/`
- creates `~/.config/spotify-auto-pause/config.json` (an existing config is never overwritten)
- creates a command `~/.local/bin/spotify-auto-pause` for diagnostics
- creates, enables and starts the user service, so it runs at every login

## Configuration

Edit `~/.config/spotify-auto-pause/config.json`, then run `systemctl --user restart spotify-auto-pause`.

| Key | Default | Meaning |
|---|---|---|
| `player` | `"spotify"` | MPRIS player to control (the name shown by `playerctl -l`). |
| `trigger_apps` | browsers, `vlc`, `mpv`, `webrtc` | Texts to look for in a stream's app name, executable name or stream title (case-insensitive). A match means "this app should pause Spotify". |
| `ignore_apps` | `[]` | Streams matching any of these never trigger a pause. Checked before `trigger_apps`. |
| `debounce_seconds` | `0.5` | The audio must last this long before Spotify is paused. |
| `verbose` | `false` | Log every audio event (useful when debugging). |

Matching is by substring: `"chrom"` covers Chrome and Chromium, `"firefox"` covers `firefox`, `firefox-esr` and `firefox-developer-edition`, and `"webrtc"` covers browser and Discord calls.

### Finding the right names

Play something in the app you want to use as a trigger, then run:

```bash
spotify-auto-pause --list
```

It shows every audio stream playing right now and how it is treated:

```
APP NAME               BINARY             STREAM TITLE             CORKED  RESULT
spotify                spotify                                     False   player itself
firefox                firefox            audioipc server          False   TRIGGER
```

Add a piece of the app name or binary to `trigger_apps` to make an app a trigger.

## Troubleshooting

- **Check that it is running:** `systemctl --user status spotify-auto-pause`
- **Read the log:** `journalctl --user -u spotify-auto-pause -f`. Each pause is logged with the stream that caused it.
- **Nothing happens with a video:** the video must be playing sound. Muted videos (autoplaying clips on social media, for example) create no audio stream. Use `--list` while the video plays with sound.
- **Spotify pauses when it should not:** run `--list` or read the log to see which stream triggered it, then add a piece of its name to `ignore_apps`.
- **A game should not pause Spotify but does:** a `trigger_apps` entry is matching it. Narrow that entry or add the game to `ignore_apps`.
- **Spotify from Flatpak:** it also exposes the `spotify` MPRIS name, so the default config should work. Check with `playerctl -l`.

## Uninstall

```bash
./uninstall.sh          # keeps your config
./uninstall.sh --purge  # also deletes the config
```

## Limitations

- It reacts to audio streams, not to windows. Anything that plays sound through PipeWire or PulseAudio can trigger a pause if it matches `trigger_apps`.
- Only one player is controlled (`player`).
- Works on Wayland and X11, since it only talks to the audio server and MPRIS.
