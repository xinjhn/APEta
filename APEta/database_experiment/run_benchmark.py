#!/usr/bin/env python3
"""Interleaved, parity-gated database benchmark over one logical workload."""
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .adapters import Backend, SQLiteBackend, open_backend
from .common import canonical_json, read_json, result_hash, write_json


HERE = Path(__file__).resolve().parent
DEFAULT_DB = HERE.parents[1] / "training" / "mot_detections.db"
FIELDNAMES = (
    "session_id", "block", "sequence_in_block", "backend", "case_id", "operation",
    "tier", "window", "k", "latency_ms", "result_bytes", "result_hash", "parity_ok",
)


def open_selected(args: argparse.Namespace) -> dict[str, Backend]:
    selected: dict[str, Backend] = {}
    for name in args.backends.split(","):
        name = name.strip()
        if not name:
            continue
        selected[name] = open_backend(
            name, sqlite_path=args.sqlite, mongo_uri=args.mongo_uri,
            neo4j_uri=args.neo4j_uri, neo4j_user=args.neo4j_user,
            neo4j_password=args.neo4j_password, postgres_dsn=args.postgres_dsn,
        )
    if not selected:
        raise ValueError("select at least one backend")
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workload", type=Path, default=HERE / "workload.json")
    parser.add_argument("--sqlite", type=Path, default=DEFAULT_DB)
    parser.add_argument("--backends", default="sqlite,postgresql,mongodb,neo4j")
    parser.add_argument("--blocks", type=int, default=30)
    parser.add_argument("--warmup-rounds", type=int, default=1)
    parser.add_argument("--seed", type=int, default=731947)
    parser.add_argument("--out-dir", type=Path, default=HERE / "results")
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--mongo-uri", default=os.getenv("APE_MONGO_URI", "mongodb://127.0.0.1:27018"))
    parser.add_argument("--neo4j-uri", default=os.getenv("APE_NEO4J_URI", "bolt://127.0.0.1:7688"))
    parser.add_argument("--neo4j-user", default=os.getenv("APE_NEO4J_USER", "neo4j"))
    parser.add_argument("--neo4j-password", default=os.getenv("APE_NEO4J_PASSWORD", "ape-experiment"))
    parser.add_argument(
        "--postgres-dsn",
        default=os.getenv(
            "APE_POSTGRES_DSN",
            "postgresql://ape:ape-experiment@127.0.0.1:5433/ape_db_experiment",
        ),
    )
    args = parser.parse_args()
    if args.blocks < 1 or args.warmup_rounds < 0:
        parser.error("--blocks must be >=1 and --warmup-rounds must be >=0")

    manifest = read_json(args.workload)
    cases = manifest["cases"]
    session_id = args.session_id or datetime.now(timezone.utc).strftime("db-%Y%m%dT%H%M%SZ")
    out_dir = args.out_dir / session_id
    out_dir.mkdir(parents=True, exist_ok=False)

    # SQLite is the canonical corpus. Reference execution is outside the timed
    # region and makes a wrong/partial result an immediate experiment failure.
    reference = SQLiteBackend(args.sqlite)
    references = {case["case_id"]: result_hash(reference.execute(case)) for case in cases}
    reference.close()

    backends = open_selected(args)
    metadata = {
        "session_id": session_id,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python": sys.version,
        "processor": platform.processor(),
        "workload": str(args.workload.resolve()),
        "workload_seed": manifest.get("seed"),
        "case_count": len(cases),
        "blocks": args.blocks,
        "warmup_rounds": args.warmup_rounds,
        "interleaving_seed": args.seed,
        "backend_versions": {name: backend.version() for name, backend in backends.items()},
        "note": "Latency includes each backend's native client boundary; SQLite is embedded, MongoDB/Neo4j use loopback.",
    }
    write_json(out_dir / "metadata.json", metadata)
    write_json(out_dir / "workload.snapshot.json", manifest)

    rng = random.Random(args.seed)
    try:
        for _ in range(args.warmup_rounds):
            warm_cases = list(cases)
            rng.shuffle(warm_cases)
            for case in warm_cases:
                order = list(backends.values())
                rng.shuffle(order)
                for backend in order:
                    actual = result_hash(backend.execute(case))
                    if actual != references[case["case_id"]]:
                        raise RuntimeError(
                            f"parity failure during warmup: {backend.name} {case['case_id']}"
                        )

        csv_path = out_dir / "measurements.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
            writer.writeheader()
            handle.flush()
            for block in range(1, args.blocks + 1):
                block_cases = list(cases)
                rng.shuffle(block_cases)
                sequence = 0
                for case in block_cases:
                    order = list(backends.values())
                    rng.shuffle(order)
                    for backend in order:
                        sequence += 1
                        started = time.perf_counter_ns()
                        result = backend.execute(case)
                        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
                        digest = result_hash(result)
                        parity_ok = digest == references[case["case_id"]]
                        writer.writerow({
                            "session_id": session_id, "block": block,
                            "sequence_in_block": sequence, "backend": backend.name,
                            "case_id": case["case_id"], "operation": case["operation"],
                            "tier": case.get("tier", ""), "window": case.get("window", ""),
                            "k": case.get("k", ""), "latency_ms": f"{elapsed_ms:.6f}",
                            "result_bytes": len(canonical_json(result).encode("utf-8")),
                            "result_hash": digest, "parity_ok": int(parity_ok),
                        })
                        if not parity_ok:
                            handle.flush()
                            raise RuntimeError(f"parity failure: {backend.name} {case['case_id']}")
                handle.flush()
                print(f"completed block {block}/{args.blocks}")
        metadata["completed_utc"] = datetime.now(timezone.utc).isoformat()
        metadata["status"] = "complete"
        write_json(out_dir / "metadata.json", metadata)
        print(f"wrote {csv_path}")
    except BaseException:
        metadata["status"] = "failed"
        metadata["ended_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(out_dir / "metadata.json", metadata)
        raise
    finally:
        for backend in backends.values():
            backend.close()


if __name__ == "__main__":
    main()
