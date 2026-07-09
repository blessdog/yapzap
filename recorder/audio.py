"""Audio helpers: parse the capture timestamp from the filename, and repair +
normalize the recorder's WAV files for transcription."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

# Recorder filenames are the capture time: YYYYMMDD-HHMMSS.wav
_TS_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})$")


def _find_ffmpeg() -> str:
    """Locate ffmpeg even under the minimal PATH a GUI-spawned process gets.

    When YapZapp launches the engine, PATH lacks /opt/homebrew/bin, so a bare
    "ffmpeg" fails despite a healthy install. Check PATH first, then the
    standard Homebrew locations (Apple Silicon, then Intel).
    """
    found = shutil.which("ffmpeg")
    if found:
        return found
    for candidate in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"):
        if Path(candidate).is_file():
            return candidate
    raise RuntimeError("ffmpeg not found — install it (brew install ffmpeg).")


def captured_at_from_filename(filename: str) -> str | None:
    """'20260613-095412.wav' -> '2026-06-13T09:54:12' (local time), or None."""
    stem = Path(filename).stem
    m = _TS_RE.match(stem)
    if not m:
        return None
    y, mo, d, hh, mm, ss = m.groups()
    return f"{y}-{mo}-{d}T{hh}:{mm}:{ss}"


def normalize_to_tempwav(src: Path) -> Path:
    """Repair the broken WAV header and downmix to mono 16 kHz PCM.

    The recorder writes WAVs with bad size fields that Core Audio refuses to
    open; ffmpeg rewrites the container and resamples to Deepgram's preferred
    input. Returns a temp path the caller is responsible for deleting.
    """
    fd, tmp_name = tempfile.mkstemp(prefix="recorder.", suffix=".wav")
    import os

    os.close(fd)
    tmp = Path(tmp_name)
    try:
        ffmpeg = _find_ffmpeg()
        subprocess.run(
            [
                ffmpeg, "-y", "-loglevel", "error",
                "-i", str(src),
                "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
                "-f", "wav", str(tmp),
            ],
            check=True,
            capture_output=True,
        )
    except RuntimeError:
        tmp.unlink(missing_ok=True)
        raise
    except subprocess.CalledProcessError as e:
        tmp.unlink(missing_ok=True)
        msg = e.stderr.decode("utf-8", "replace").strip() if e.stderr else str(e)
        raise RuntimeError(f"ffmpeg failed on {src.name}: {msg}") from e
    return tmp
