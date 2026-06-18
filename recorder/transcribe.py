"""Deepgram nova-3 batch transcription via stdlib urllib (no dependencies)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

from . import config

# Transient network failures (dropped connection, broken pipe on a big upload)
# shouldn't strand a clip. Retry a few times with backoff before giving up; a
# clip that still fails is left status='error' and retried on the next ingest.
_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = (2, 5)  # waits between attempts 1→2 and 2→3


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

    payload = None
    for attempt in range(_MAX_ATTEMPTS):
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
            break
        except urllib.error.HTTPError as e:
            # 5xx is worth retrying; 4xx (bad request/auth) won't improve.
            if 500 <= e.code < 600 and attempt < _MAX_ATTEMPTS - 1:
                time.sleep(_BACKOFF_SECONDS[attempt])
                continue
            detail = e.read().decode("utf-8", "replace")[:500]
            raise RuntimeError(f"Deepgram HTTP {e.code}: {detail}") from e
        except (urllib.error.URLError, OSError) as e:
            # Dropped connection / broken pipe / timeout — retry with backoff.
            if attempt < _MAX_ATTEMPTS - 1:
                time.sleep(_BACKOFF_SECONDS[attempt])
                continue
            reason = getattr(e, "reason", e)
            raise RuntimeError(
                f"Deepgram unreachable after {_MAX_ATTEMPTS} tries: {reason}"
            ) from e

    assert payload is not None
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
