#!/usr/bin/env python3
"""Generate a deterministic, stratified logical-query manifest from SQLite."""
from __future__ import annotations

import argparse
import random
import sqlite3
from pathlib import Path

from .common import write_json


HERE = Path(__file__).resolve().parent
DEFAULT_DB = HERE.parents[1] / "training" / "mot_detections.db"


def sample(rng: random.Random, values: list[int], n: int) -> list[int]:
    if len(values) < n:
        raise ValueError(f"requested {n} values from a pool of {len(values)}")
    return sorted(rng.sample(values, n))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=HERE / "workload.json")
    parser.add_argument("--samples-per-cell", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260719)
    args = parser.parse_args()
    rng = random.Random(args.seed)
    conn = sqlite3.connect(f"file:{args.source.resolve().as_posix()}?mode=ro", uri=True)

    cases: list[dict] = []
    for tier in ("low", "medium", "high"):
        pool = [row[0] for row in conn.execute(
            "SELECT id FROM image WHERE density_tier=? ORDER BY id", (tier,)
        )]
        for image_id in sample(rng, pool, args.samples_per_cell):
            cases.extend([
                {"operation": "image_detections", "image_id": image_id, "tier": tier},
                {"operation": "filtered_detections", "image_id": image_id, "tier": tier,
                 "class_id": 4, "min_confidence": 0.5},
                {"operation": "class_counts", "image_id": image_id, "tier": tier},
            ])

    for window in (2, 8, 23):
        need = 2 * window + 1
        pool = [row[0] for row in conn.execute(
            """SELECT track_id FROM detection WHERE track_id IS NOT NULL
               GROUP BY track_id HAVING COUNT(*)>=? ORDER BY track_id""",
            (need,),
        )]
        for track_id in sample(rng, pool, args.samples_per_cell):
            cases.append({"operation": "trajectory", "track_id": track_id, "window": window})

    batch_pool = [row[0] for row in conn.execute(
        """SELECT track_id FROM detection WHERE track_id IS NOT NULL
           GROUP BY track_id HAVING COUNT(*)>=5 ORDER BY track_id"""
    )]
    for k in (1, 5, 10):
        for index in range(args.samples_per_cell):
            cases.append({
                "operation": "trajectories", "track_ids": sample(rng, batch_pool, k),
                "window": 2, "k": k, "sample_index": index,
            })

    for index, case in enumerate(cases, 1):
        case["case_id"] = f"Q{index:04d}"
    manifest = {
        "schema_version": 1,
        "seed": args.seed,
        "source": str(args.source.resolve()),
        "samples_per_cell": args.samples_per_cell,
        "case_count": len(cases),
        "cases": cases,
    }
    write_json(args.out, manifest)
    print(f"wrote {len(cases)} cases to {args.out}")
    conn.close()


if __name__ == "__main__":
    main()
