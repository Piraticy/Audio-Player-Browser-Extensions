# Audio Player

Music Player app and extensions for all browsers.

Audio Player is a local-first music project with a desktop app, Docker web app, and browser-extension foundation.

The project is built for files and media the user owns or is authorized to convert. It does not remove ads, bypass YouTube or streaming-service playback, or extract protected media.

## Desktop App

Run the Python desktop app:

```sh
python3 desktop/audio_player_app.py
```

The app can:

- Play local audio files with FFplay or macOS afplay
- Convert local or authorized media files to MP3, M4A, WAV, FLAC, or OGG with FFmpeg
- Manage a simple playlist

Install FFmpeg for broad media support:

```sh
brew install ffmpeg
```

## Docker Testing

Build and run the smoke test container:

```sh
docker compose run --rm audio-player-test
```

Show a running project container in Docker Desktop:

```sh
docker compose up -d audio-player
```

Open the Docker app in your browser:

```sh
open http://localhost:8091
```

Or without Compose:

```sh
docker build -t audio-player:local .
docker run --rm audio-player:local
```

The container verifies the Python app, browser-extension JavaScript, manifest JSON, and FFmpeg conversion support. The desktop UI itself should still be run on the host.

## Docker Web App

The Docker container serves a browser app on port `8091`.

- Play selected local audio files in the browser
- Add files with a picker or drag-and-drop
- Generate a built-in demo track for quick testing
- Skip backward or forward by 10 or 20 seconds
- Use keyboard shortcuts: Space, ArrowLeft, ArrowRight, `N`, and `P`
- Pick visualizer modes: bars, wave, halo, or off
- Convert selected local or authorized media files through FFmpeg in Docker
- Export MP3 by default at 320 kbps
- Search YouTube and open official results in a new tab
- Fetch YouTube search suggestions through the Docker app
- Save and remember searches in the browser
- Download converted output files

## Browser Extension

A lightweight Manifest V3 browser extension for playing local audio files from a polished popup UI.

### Features

- Add multiple local audio files from the popup
- Play, pause, skip, seek, and adjust volume
- See current track metadata and playback progress
- Continue playback after the popup closes using an offscreen document
- Install-free vanilla HTML, CSS, and JavaScript

### Load The Extension

1. Open `chrome://extensions` in Chrome or another Chromium-based browser.
2. Enable Developer mode.
3. Choose Load unpacked.
4. Select this project folder.

## Files

- `desktop/audio_player_app.py` is the desktop player and converter.
- `manifest.json` configures the extension.
- `popup.html`, `styles.css`, and `popup.js` power the visible player.
- `background.js` manages extension messages and offscreen playback.
- `offscreen.html` and `offscreen.js` host persistent audio playback.
