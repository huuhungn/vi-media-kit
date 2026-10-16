# vi-media-kit

A small Python library for Vietnamese speech and subtitle applications. No GUI, no bundled models, no bundled ffmpeg.
All code in this repository is newly written; the repository contains no code, data, icons or executables from third-party applications.

User-facing messages are written in Vietnamese, and most function and variable names are Vietnamese without diacritics.

## What's inside

| Module | Purpose |
|---|---|
| `vimediakit.srt` | Read/write `.srt`: tolerates CRLF, missing sequence numbers, and `.` used instead of `,` in timestamps |
| `vimediakit.subtitles` | Export `srt/vtt/txt`, merge/split sentences, detect the right encoding (UTF-8, UTF-16, cp1258), diacritic-insensitive search |
| `vimediakit.dubbing` | Experimental dubbing: each subtitle cue → TTS (a function you pass in) → placed at the exact timestamps, automatically sped up when a cue is too long (requires ffmpeg) |
| `vimediakit.render_min` | Burn subtitles into a video and/or replace the audio track, with progress reporting and cancellation (requires ffmpeg) |
| `vimediakit.modeldl` | Download faster-whisper models from Hugging Face: resume after interruption, sha256 verification, progress reporting, cancellable |
| `vimediakit.hwprofile` | Detect CPU/RAM/NVIDIA GPU and recommend a model, thread count and beam size |
| `vimediakit.diagnostics` | Zip diagnostic bundle that automatically redacts sensitive values (keys, tokens, passwords) |
| `vimediakit.errors` | Turn technical exceptions into clear Vietnamese messages |
| `vimediakit.netmode` | Offline mode (environment variable `VIMEDIA_OFFLINE=1`) |
| `vimediakit.history`, `applog`, `procutil`, `mediainfo` | Atomic history writes, rotating log + crash log, running subprocesses without flashing a console window, reading video size/duration without ffprobe |
| `vimediakit.jobs`, `theme` | Cancellable background jobs for PySide6 and a light/dark color palette (requires `PySide6`) |

## Install and run the tests

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt     # Windows: .venv\Scripts\pip
python -m pytest                                  # runs fully offline
```

Tests that need ffmpeg are skipped automatically if ffmpeg is not on your PATH.

## Example

```python
from vimediakit import subtitles

cues = subtitles.doc("phu_de.srt")      # read the subtitle file ("phu_de" = "subtitles")
subtitles.ghi(cues, "phu_de.vtt")       # write it back out as WebVTT
```

## License and third-party components

The code in this repository is licensed under the [MIT License](LICENSE) (copyright held by the author, `anhtahaylove`) and is provided as is, without warranty.

The repository **does not bundle** any third-party components; anything you install or download yourself is covered by its own license:

- **ffmpeg**: a separate program that you install yourself. Depending on the build, ffmpeg may be GPL or LGPL; check the license of the build you use before redistributing it together with ffmpeg.
- **Whisper models**: `modeldl` only downloads from Hugging Face when you call it; each model has its own license, stated on that model's repository page.
- **PySide6** (optional, for `jobs` and `theme`): LGPL/commercial, from The Qt Company. **numpy, soundfile, psutil**: BSD license.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The change history is in [CHANGELOG.md](CHANGELOG.md).
