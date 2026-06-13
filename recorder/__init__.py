"""Recorder — ingest a hardware voice recorder into a reliable local store.

The first slice: detect/point at the recorder, copy clips into a local library
(never mutating the device), repair + normalize the audio, transcribe it, and
land everything in a SQLite source-of-truth. Capture is committed BEFORE
transcription so a clip is never lost if transcription fails.
"""

__version__ = "0.1.0"
