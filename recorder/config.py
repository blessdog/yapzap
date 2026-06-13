"""Paths, constants, and .env loading. No external dependencies."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LIBRARY_DIR = PROJECT_ROOT / "library"
RAW_DIR = LIBRARY_DIR / "raw"
DB_PATH = LIBRARY_DIR / "recorder.db"

# Where the device mounts. The recorder writes flat into <mount>/record/*.wav,
# but ingest recurses, so this can also point at an already-organized backup
# (e.g. ~/yapzap/raw) for testing when the device is unplugged.
DEFAULT_SOURCE = Path("/Volumes/Recorder/record")

DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"
DEEPGRAM_MODEL = "nova-3"

# The recorder writes broken WAV headers (bad size fields) + stereo; ffmpeg both
# repairs the header and downmixes to Deepgram's preferred mono 16 kHz PCM.
NORMALIZE_SAMPLE_RATE = 16000
NORMALIZE_CHANNELS = 1


def load_env() -> None:
    """Load KEY=VALUE pairs from PROJECT_ROOT/.env into os.environ.

    Existing environment variables win, so a real export overrides the file.
    """
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def deepgram_api_key() -> str:
    load_env()
    key = os.environ.get("DEEPGRAM_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "DEEPGRAM_API_KEY not set. Add it to "
            f"{PROJECT_ROOT / '.env'} (see .env.example)."
        )
    return key


def anthropic_api_key() -> str:
    load_env()
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Add it to "
            f"{PROJECT_ROOT / '.env'} (see .env.example)."
        )
    return key


# The mind: Claude model + extraction prompt version.
ORGANIZE_MODEL = "claude-opus-4-8"
ORGANIZE_PROMPT_VERSION = "v1"
