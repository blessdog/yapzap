"""CLI entry point.  Run with:  python -m recorder <command>

Commands:
  ingest [--source DIR] [--no-transcribe] [--limit N]
  stats
  list [--limit N]
  show <id>
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

from . import config, db, ingest


def cmd_ingest(args: argparse.Namespace) -> int:
    source = Path(args.source).expanduser() if args.source else config.DEFAULT_SOURCE
    print(f"Ingesting from: {source}")
    report = ingest.run(
        source, transcribe=not args.no_transcribe, limit=args.limit
    )
    print("Done:")
    print(report.summary())
    return 1 if report.errors else 0


def cmd_stats(_args: argparse.Namespace) -> int:
    conn = db.connect(config.DB_PATH)
    try:
        counts = db.stats(conn)
        frag_counts = db.fragment_type_counts(conn)
    finally:
        conn.close()
    if not counts:
        print("No yaps yet. Run: python -m recorder ingest")
        return 0
    total = sum(counts.values())
    print(f"{total} yap(s) in {config.DB_PATH}")
    for status, n in sorted(counts.items()):
        print(f"  {status:14} {n}")
    if frag_counts:
        print(f"{sum(frag_counts.values())} fragment(s):")
        for t, n in sorted(frag_counts.items()):
            print(f"  {t:14} {n}")
    return 0


def cmd_organize(args: argparse.Namespace) -> int:
    from . import organize

    print(f"Organizing with {config.ORGANIZE_MODEL} (prompt {organize.PROMPT_VERSION})")
    report = organize.run(limit=args.limit)
    print("Done:")
    print(report.summary())
    return 1 if report.errors else 0


def cmd_fragments(args: argparse.Namespace) -> int:
    conn = db.connect(config.DB_PATH)
    try:
        rows = db.recent_fragments(conn, type_=args.type, limit=args.limit)
    finally:
        conn.close()
    for r in rows:
        text = (r["text"] or "").replace("\n", " ")
        if len(text) > 64:
            text = text[:61] + "..."
        captured = (r["captured_at"] or "?")[:10]
        print(f"[{r['id']:>3}] {captured}  {r['type']:<9} {text}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    conn = db.connect(config.DB_PATH)
    try:
        rows = db.recent(conn, limit=args.limit)
    finally:
        conn.close()
    for r in rows:
        preview = (r["transcript"] or "").replace("\n", " ")
        if len(preview) > 70:
            preview = preview[:67] + "..."
        captured = r["captured_at"] or "?"
        print(f"[{r['id']:>3}] {captured}  {r['status']:<11} {preview}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    conn = db.connect(config.DB_PATH)
    try:
        cur = conn.execute("SELECT * FROM yaps WHERE id = ?", (args.id,))
        row = cur.fetchone()
    finally:
        conn.close()
    if row is None:
        print(f"No yap with id {args.id}")
        return 1
    print(f"id:            {row['id']}")
    print(f"captured_at:   {row['captured_at']}")
    print(f"status:        {row['status']}")
    print(f"duration_sec:  {row['duration_sec']}")
    print(f"confidence:    {row['confidence']}")
    print(f"model:         {row['model']}")
    print(f"audio:         {row['raw_audio_path']}")
    if row["error"]:
        print(f"error:         {row['error']}")
    print("transcript:")
    print(textwrap.indent(row["transcript"] or "(none)", "  "))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="recorder", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_ing = sub.add_parser("ingest", help="copy + transcribe new recordings")
    p_ing.add_argument("--source", help=f"source dir (default {config.DEFAULT_SOURCE})")
    p_ing.add_argument("--no-transcribe", action="store_true", help="import only")
    p_ing.add_argument("--limit", type=int, help="max clips to transcribe")
    p_ing.set_defaults(func=cmd_ingest)

    sub.add_parser("stats", help="counts by status").set_defaults(func=cmd_stats)

    p_org = sub.add_parser("organize", help="extract fragments from transcripts (LLM)")
    p_org.add_argument("--limit", type=int, help="max yaps to organize")
    p_org.set_defaults(func=cmd_organize)

    p_frag = sub.add_parser("fragments", help="list extracted fragments")
    p_frag.add_argument("--type", choices=["joke", "idea", "insight", "practical"])
    p_frag.add_argument("--limit", type=int, default=50)
    p_frag.set_defaults(func=cmd_fragments)

    p_list = sub.add_parser("list", help="recent yaps")
    p_list.add_argument("--limit", type=int, default=20)
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="full transcript for one yap")
    p_show.add_argument("id", type=int)
    p_show.set_defaults(func=cmd_show)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
