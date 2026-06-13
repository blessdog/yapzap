"""Deepgram nova-3 batch transcription via stdlib urllib (no dependencies)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

from . import config


@dataclass
class Transcription:
    transcript: str
    duration_sec: float
    confidence: float
    model: str

    @property
    def is_empty(self) -> bool:
        return not self.transcript.strip()


def transcribe_wav(wav_path: Path, api_key: str) -> Transcription:
    """POST a normalized WAV to Deepgram and parse the top alternative."""
    query = urlencode(
        {"model": config.DEEPGRAM_MODEL, "smart_format": "true", "punctuate": "true"}
    )
    url = f"{config.DEEPGRAM_URL}?{query}"
    body = wav_path.read_bytes()
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Token {api_key}",
            "Content-Type": "audio/wav",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"Deepgram HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Deepgram unreachable: {e.reason}") from e

    try:
        alt = payload["results"]["channels"][0]["alternatives"][0]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected Deepgram response shape: {payload}") from e

    return Transcription(
        transcript=alt.get("transcript", "") or "",
        duration_sec=float(payload.get("metadata", {}).get("duration", 0.0)),
        confidence=float(alt.get("confidence", 0.0)),
        model=config.DEEPGRAM_MODEL,
    )
