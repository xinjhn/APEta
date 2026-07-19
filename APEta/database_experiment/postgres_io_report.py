#!/usr/bin/env python3
"""Collect PostgreSQL server-side execution and buffer/I/O statistics."""
from __future__ import annotations

import argparse
import csv
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

from .adapters import PostgreSQLBackend, SQLiteBackend
from .common import read_json, result_hash


HERE = Path(__file__).resolve().parent
DEFAULT_DB = HERE.parents[1] / "training" / "mot_detections.db"
DEFAULT_DSN = "postgresql://ape:ape-experiment@127.0.0.1:5433/ape_db_experiment"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workload", type=Path, default=HERE / "workload.json")
    parser.add_argument("--sqlite", type=Path, default=DEFAULT_DB)
    parser.add_argument("--postgres-dsn", default=DEFAULT_DSN)
    parser.add_argument("--rounds", type=int, default=30)
    parser.add_argument("--seed", type=int, default=91731)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=False)

    manifest = read_json(args.workload)
    cases = manifest["cases"]
    sqlite = SQLiteBackend(args.sqlite)
    expected = {case["case_id"]: result_hash(sqlite.execute(case)) for case in cases}
    sqlite.close()
    postgres = PostgreSQLBackend(args.postgres_dsn)

    # Populate PostgreSQL shared buffers and driver prepared-statement state,
    # then reset statement statistics so diagnostics describe measured rounds.
    for case in cases:
        if result_hash(postgres.execute(case)) != expected[case["case_id"]]:
            raise RuntimeError(f"warmup parity failure: {case['case_id']}")
    with postgres.conn.cursor() as cur:
        cur.execute("SELECT current_setting('track_io_timing') AS value")
        io_timing = cur.fetchone()["value"]
        cur.execute(
            "SELECT current_setting('pg_stat_statements.track_planning') AS value"
        )
        track_planning = cur.fetchone()["value"]
        cur.execute("SELECT pg_stat_statements_reset()")

    rng = random.Random(args.seed)
    started = time.perf_counter()
    for round_index in range(1, args.rounds + 1):
        shuffled = list(cases)
        rng.shuffle(shuffled)
        for case in shuffled:
            actual = result_hash(postgres.execute(case))
            if actual != expected[case["case_id"]]:
                raise RuntimeError(f"measured parity failure: {case['case_id']}")
        print(f"completed I/O diagnostic round {round_index}/{args.rounds}")
    wall_seconds = time.perf_counter() - started

    with postgres.conn.cursor() as cur:
        cur.execute(
            """SELECT query, calls, plans, total_plan_time, total_exec_time, rows,
                      shared_blks_hit, shared_blks_read, shared_blks_dirtied,
                      shared_blks_written, temp_blks_read, temp_blks_written,
                      shared_blk_read_time, shared_blk_write_time
               FROM pg_stat_statements
               WHERE query ILIKE '%FROM detection%'
                  OR query ILIKE '%FROM image%'
                  OR query ILIKE '%FROM track%'
               ORDER BY query"""
        )
        raw = list(cur)

    def statement_label(query: str) -> str:
        normalized = " ".join(query.lower().split())
        if normalized.startswith("select image.id"):
            return "image_envelope"
        if normalized.startswith("select class_id, count"):
            return "class_counts"
        if normalized.startswith("select id, track_id"):
            return "filtered_detections" if "and class_id=" in normalized else "image_detections"
        if normalized.startswith("select detection.track_id"):
            return "trajectories_points"
        if normalized.startswith("select detection.id"):
            return "trajectory"
        if normalized.startswith("select track.id"):
            return "trajectories_tracks" if "=any(" in normalized else "track_envelope"
        return "unknown"

    output_rows: list[dict] = []
    for row in raw:
        label = statement_label(row["query"])
        calls = int(row["calls"])
        hits = int(row["shared_blks_hit"])
        reads = int(row["shared_blks_read"])
        denom = hits + reads
        output_rows.append({
            "statement": label,
            "calls": calls,
            "plans": int(row["plans"]),
            "rows": int(row["rows"]),
            "mean_plan_ms_per_call": float(row["total_plan_time"]) / calls,
            "mean_plan_ms_per_plan": (
                float(row["total_plan_time"]) / int(row["plans"])
                if int(row["plans"]) else 0.0
            ),
            "mean_exec_ms": float(row["total_exec_time"]) / calls,
            "shared_blks_hit": hits,
            "shared_blks_read": reads,
            "shared_blks_hit_per_call": hits / calls,
            "shared_blks_read_per_call": reads / calls,
            "shared_blks_dirtied": int(row["shared_blks_dirtied"]),
            "shared_blks_written": int(row["shared_blks_written"]),
            "temp_blks_read": int(row["temp_blks_read"]),
            "temp_blks_written": int(row["temp_blks_written"]),
            "shared_read_ms": float(row["shared_blk_read_time"]),
            "shared_write_ms": float(row["shared_blk_write_time"]),
            "buffer_hit_fraction": (hits / denom) if denom else "",
        })
    fields = list(output_rows[0]) if output_rows else []
    with (args.out_dir / "postgres_statement_io.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)

    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "postgresql_version": postgres.version(),
        "track_io_timing": io_timing,
        "pg_stat_statements_track_planning": track_planning,
        "workload": str(args.workload.resolve()),
        "rounds": args.rounds,
        "logical_cases_per_round": len(cases),
        "parity_checks": args.rounds * len(cases),
        "parity_pass": True,
        "diagnostic_wall_seconds": wall_seconds,
        "interpretation": (
            "shared_blks_hit/read are PostgreSQL buffer events. A hit avoided a PostgreSQL "
            "file read; a read can still be served by the operating-system page cache."
        ),
    }
    (args.out_dir / "postgres_io_metadata.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    postgres.close()
    print(f"wrote PostgreSQL diagnostics to {args.out_dir}")


if __name__ == "__main__":
    main()
