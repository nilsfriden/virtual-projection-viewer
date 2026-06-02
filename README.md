# Virtual Projection Viewer

Preview NDI video content projected onto a 3D room model in real-time. A virtual walkthrough tool for immersive projection rooms.

Built as a lightweight alternative to TouchDesigner for previewing multi-surface projection layouts during editing.

## What it does

- Receives a live NDI video stream (DaVinci Resolve, Premiere, OBS, etc.)
- Maps the video as a texture onto a `.obj` 3D model of the room
- Provides a Maya-style orbit camera to navigate the space
- On-screen controls for camera, model transform, texture rotation, and resolution scaling
- Saves/loads all settings between sessions

## Requirements

- Python 3.10+ (3.12 recommended)
- [NDI Runtime](https://ndi.video/tools/) installed (free — the app works without it using a test pattern, but you need it for actual NDI input)

## Quick start

```bash
pip install -r requirements.txt
pip install ndi-python    # optional, for NDI input
python main.py
python main.py --model room.obj
```

## Controls

| Input | Action |
|---|---|
| Alt + LMB drag | Orbit (tumble) |
| Alt + MMB drag | Pan |
| Alt + RMB drag / Scroll | Dolly |
| F | Fit camera to model |
| Escape | Quit |

## Pre-built binaries

Download from [Releases](../../releases). The NDI Runtime must be installed separately on the target machine.

## Building from source

```bash
pip install pyinstaller
# Windows
build.bat
# See .github/workflows/build.yml for macOS build
```

## Architecture

```
main.py        — Application loop, UI, input handling, settings
renderer.py    — OpenGL shaders, texture management, scene rendering
camera.py      — Maya-style orbit camera (target + azimuth/elevation/distance)
ndi_input.py   — NDI discovery + frame capture (with test-pattern fallback)
obj_loader.py  — Wavefront .obj parser with bounding box calculation
settings.py    — JSON settings persistence
```

## License

MIT
