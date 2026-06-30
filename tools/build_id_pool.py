#!/usr/bin/env python3
"""
tools/build_id_pool.py
========================
Exports the entity-id pools the Phase 2 k6 workload generator (k6/workload.js)
samples from. k6 (a JS/goja sandbox) can't talk to SQLite directly, so this
script is the one-time (well, one-per-corpus) bridge: read mot_detections.db,
write a flat JSON file k6 loads via open() + SharedArray.

Output shape:
{
  "images": {"low": [id, ...], "medium": [...], "high": [...]},
  "tracks": [{"id": ..., "first_frame": ..., "span": last_frame-first_frame}, ...],
  "pages": {"low": {"5": [[id,...5 ids...], ...], "10": [[...10 ids...], ...]}, "medium": {...}, "high": {...}}
}

`tracks` is filtered to span > 0 (multi-frame) only -- a single-frame track's
trajectory query is a degenerate case (1 point window), not representative
of the "deep nesting" payload-weight condition this corpus is for.

`pages` backs the round-trip-vs-cacheability arm (page/batch-size factor K):
FIXED, deterministic groups of K consecutive ids per density tier, so the
SAME page (same K-id set) can recur across iterations -- giving GraphQL's
single composite cache entry (keyed by the exact id SET) a genuine chance to
be reused, instead of K independently-random ids that would almost never
repeat as an exact set by construction. k6/workload.js's access_pattern then
selects WHICH page (page index), not which individual ids. K=1 IS included
in PAGE_SIZES below despite being a degenerate single-id "page" -- k6/
workload.js's page-mode path unconditionally looks up pool.pages[DENSITY]
[String(PAGE_SIZE)], so a missing "1" key crashes k6 (caught live: every
page_size=1 row failed with k6_rc=107/no_summary_file during verification --
the original assumption that K=1 "needs no precomputed list" was never
actually implemented as a workload.js special case, just asserted here).

Usage:
    python tools/build_id_pool.py --db /home/ubuntu/training/mot_detections.db \
        --out scratch/id_pool.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

PAGE_SIZES = (1, 5, 10)


def _build_pages(ids: list, page_size: int) -> list:
    return [ids[i:i + page_size] for i in range(0, len(ids) - page_size + 1, page_size)]


def build(db_path: str, out_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    images = {}
    for tier in ("low", "medium", "high"):
        rows = conn.execute(
            "SELECT id FROM image WHERE density_tier = ? ORDER BY id", (tier,)
        ).fetchall()
        images[tier] = [r["id"] for r in rows]

    track_rows = conn.execute(
        "SELECT id, first_frame, last_frame FROM track WHERE last_frame > first_frame"
    ).fetchall()
    tracks = [
        {"id": r["id"], "first_frame": r["first_frame"], "span": r["last_frame"] - r["first_frame"]}
        for r in track_rows
    ]

    pages = {
        tier: {str(k): _build_pages(ids, k) for k in PAGE_SIZES}
        for tier, ids in images.items()
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"images": images, "tracks": tracks, "pages": pages}))

    print(f"[done] images: {{{', '.join(f'{k}={len(v)}' for k, v in images.items())}}}")
    print(f"[done] tracks (multi-frame): {len(tracks)}")
    print(f"[done] pages: {{{', '.join(f'{tier}={ {k: len(v) for k, v in ks.items()} }' for tier, ks in pages.items())}}}")
    print(f"[done] wrote {out_path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    build(args.db, args.out)


if __name__ == "__main__":
    main()
