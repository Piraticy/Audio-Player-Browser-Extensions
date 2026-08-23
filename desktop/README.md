# Auralith Studio Desktop App

This is the first desktop app for the project. It plays local or authorized media files and converts media files to audio formats through FFmpeg.

## Run

```sh
python3 desktop/audio_player_app.py
```

## Media Engines

- Playback uses `ffplay` when FFmpeg is installed.
- On macOS, playback falls back to `/usr/bin/afplay` for formats supported by the system.
- Conversion requires `ffmpeg`.

Install FFmpeg on macOS with Homebrew:

```sh
brew install ffmpeg
```

## Supported Conversion Outputs

- MP3
- M4A
- WAV
- FLAC
- OGG

## Scope

Use this app for local files or media you are authorized to convert. It does not remove ads, bypass YouTube or streaming-service playback, or extract protected media.
