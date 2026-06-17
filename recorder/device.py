"""Free up space on the recorder — safely.

The hardware recorder has limited storage; once clips are imported we want to
wipe them off the device so it's ready for the next all-day session. But the
captures are irreplaceable, so deletion is gated hard (design principle #1,
reliability of capture):

A device clip is deleted ONLY when, at delete time, a fresh SHA-256 of the
device file equals a fresh SHA-256 of its library copy (and sizes match). Any
mismatch / missing copy / unrecognized file → left on the device, reported.
AppleDouble `._*` junk on the FAT volume is the one safe-to-remove exception.

Nothing here runs automatically — the app calls `clear_device` only after the
user confirms (see the Mac app's "Free up space" button).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import db
from .ingest import sha256_of


@dataclass
class DeviceFile:
    path: Path
    size: int


@dataclass
class Classification:
    clearable: list[DeviceFile] = field(default_factory=list)  # verified-copied
    blocked: list[tuple[DeviceFile, str]] = field(default_factory=list)  # (file, why)
    junk: list[DeviceFile] = field(default_factory=list)  # ._* AppleDouble cruft

    @property
    def freeable_bytes(self) -> int:
        return sum(f.size for f in self.clearable) + sum(f.size for f in self.junk)


def scan_device(source: Path) -> tuple[list[DeviceFile], list[DeviceFile]]:
    """Return (real wavs, AppleDouble junk) found on the device."""
    reals: list[DeviceFile] = []
    junk: list[DeviceFile] = []
    for p in sorted(source.rglob("*.wav")):
        try:
            size = p.stat().st_size
        except OSError:
            continue
        (junk if p.name.startswith("._") else reals).append(DeviceFile(p, size))
    return reals, junk


def classify(conn, source: Path) -> Classification:
    """Decide, without deleting anything, what is safe to free.

    A real wav is `clearable` when its yap row exists, the library copy is on
    disk, the stored size matches the device size, and a stored hash exists.
    The authoritative byte-for-byte hash check is deferred to delete time
    (`clear_device`) — this pass is the fast summary the UI shows.
    """
    result = Classification()
    reals, junk = scan_device(source)
    result.junk = junk

    for f in reals:
        row = db.get_by_filename(conn, f.path.name)
        if row is None:
            result.blocked.append((f, "not yet imported"))
            continue
        lib = row["raw_audio_path"]
        if not lib or not Path(lib).exists():
            result.blocked.append((f, "library copy missing"))
            continue
        if row["size_bytes"] != f.size:
            result.blocked.append((f, "size mismatch with library copy"))
            continue
        if not row["sha256"]:
            result.blocked.append((f, "library copy not yet hashed"))
            continue
        result.clearable.append(f)
    return result


@dataclass
class ClearReport:
    deleted: int = 0
    junk_deleted: int = 0
    bytes_freed: int = 0
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (name, why)
    dry_run: bool = False

    def summary(self) -> str:
        verb = "would delete" if self.dry_run else "deleted"
        lines = [
            f"  {verb} clips:     {self.deleted}",
            f"  {verb} junk:      {self.junk_deleted}",
            f"  bytes freed:      {self.bytes_freed:,}",
            f"  skipped (kept):   {len(self.skipped)}",
        ]
        for name, why in self.skipped:
            lines.append(f"    ! {name}: {why}")
        return "\n".join(lines)


def clear_device(conn, source: Path, *, dry_run: bool = False) -> ClearReport:
    """Delete verified-copied clips (and AppleDouble junk) off the device.

    Re-verifies every clip with a fresh dual hash immediately before deleting —
    the classification summary can go stale, the hash check cannot.
    """
    report = ClearReport(dry_run=dry_run)
    cls = classify(conn, source)

    for f in cls.clearable:
        row = db.get_by_filename(conn, f.path.name)
        if row is None:
            report.skipped.append((f.path.name, "row vanished"))
            continue
        lib = Path(row["raw_audio_path"]) if row["raw_audio_path"] else None
        # Belt and suspenders: confirm the library copy still hashes to the
        # stored value AND the device file matches it, right now.
        try:
            if lib is None or not lib.exists():
                report.skipped.append((f.path.name, "library copy vanished"))
                continue
            lib_hash = sha256_of(lib)
            if lib_hash != row["sha256"]:
                report.skipped.append((f.path.name, "library copy changed since import"))
                continue
            if sha256_of(f.path) != lib_hash:
                report.skipped.append((f.path.name, "device file differs from copy"))
                continue
        except OSError as e:
            report.skipped.append((f.path.name, f"read error: {e}"))
            continue

        if not dry_run:
            try:
                f.path.unlink()
            except OSError as e:
                report.skipped.append((f.path.name, f"delete failed: {e}"))
                continue
        report.deleted += 1
        report.bytes_freed += f.size

    for f in cls.junk:
        if not dry_run:
            try:
                f.path.unlink()
            except OSError:
                continue
        report.junk_deleted += 1
        report.bytes_freed += f.size

    # Report anything we refused to free so the user knows it's still on device.
    for f, why in cls.blocked:
        report.skipped.append((f.path.name, why))

    return report


def status(conn, source: Path) -> dict:
    """Machine-readable snapshot for the app (and the CLI's --json)."""
    if not source.exists():
        return {"connected": False, "total": 0, "clearable": 0,
                "blocked": 0, "junk": 0, "freeable_bytes": 0}
    cls = classify(conn, source)
    return {
        "connected": True,
        "total": len(cls.clearable) + len(cls.blocked),
        "clearable": len(cls.clearable),
        "blocked": len(cls.blocked),
        "junk": len(cls.junk),
        "freeable_bytes": cls.freeable_bytes,
    }
