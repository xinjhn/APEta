"""
orchestrator/make_run_plan.py
==============================
Deterministic run-plan generator for the Phase 2 cache-vs-paradigm study.
Replaces the retired Path-B plan (block = protocol x pattern x density x
concurrency against the JSON pool).

BLOCK = one full combination of (protocol, caching, access_pattern, entropy,
payload_weight, network, density, concurrency). Block execution order is
shuffled with a fixed seed (spec A5: cell order randomized) so "which block
runs near which" isn't confounded with thermal drift/time-of-day.

CORE GRID (default, spec Section 3): protocol x caching x access_pattern x
payload_weight, with entropy/density/network/concurrency fixed at the
config's "core_*" values -- 2x2x3x2 = 24 blocks. FULL GRID (APE_GRID=full)
additionally varies entropy/density/network/concurrency -- combinatorially
larger, opt-in only. BATCH GRID (APE_GRID=batch) is a separate, narrow arm
for the round-trip-vs-cacheability question (page_size factor K -- see
build_batch_grid_blocks()): protocol x caching x access_pattern x page_size,
light payload only, everything else held at core values.

run_plan.csv is a FIXED CONTRACT once written -- do not regenerate mid-session
(orchestrator/run_experiment.py's resume logic depends on row order/run_uid
staying stable). Use a fresh APE_RESULTS_DIR per distinct grid/seed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import random
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.config import (  # noqa: E402
    ACCESS_PATTERNS,
    CACHING_LEVELS,
    PAYLOAD_WEIGHTS,
    PROTOCOLS,
    get_config,
)

FIELDNAMES = [
    "run_uid",
    "block_id",
    "block_order",
    "protocol",
    "caching",
    "access_pattern",
    "entropy",
    "payload_weight",
    "network",
    "density",
    "concurrency",
    "page_size",
    "run_index",
    "is_warmup",
]

_FACTOR_KEYS = (
    "protocol", "caching", "access_pattern", "entropy",
    "payload_weight", "network", "density", "concurrency", "page_size",
)
# page_size=0 means "not in page mode" -- core/full grid blocks set this so
# their schema matches the batch grid's (page_size only varies in build_
# batch_grid_blocks()). Keeping it in _FACTOR_KEYS (not bolting it on
# separately) means it's part of the run_uid hash too, consistent with every
# other factor.
_NOT_PAGE_MODE = 0


def _run_uid(block: dict, is_warmup: bool, run_index: int) -> str:
    key = "|".join(str(block[k]) for k in _FACTOR_KEYS) + f"|{int(is_warmup)}|{run_index}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def build_core_grid_blocks(cfg) -> List[dict]:
    """2x2x3x2 = 24 blocks: protocol x caching x access_pattern x
    payload_weight, entropy/density/network/concurrency held fixed."""
    blocks = []
    combos = itertools.product(PROTOCOLS, CACHING_LEVELS, ACCESS_PATTERNS, PAYLOAD_WEIGHTS)
    for idx, (protocol, caching, access_pattern, payload_weight) in enumerate(combos):
        blocks.append({
            "block_id": f"B{idx:04d}",
            "protocol": protocol,
            "caching": caching,
            "access_pattern": access_pattern,
            "entropy": cfg.core_entropy,
            "payload_weight": payload_weight,
            "network": cfg.core_network,
            "density": cfg.core_density,
            "concurrency": cfg.core_concurrency,
            "page_size": _NOT_PAGE_MODE,
        })
    return blocks


def build_full_grid_blocks(cfg) -> List[dict]:
    """Drill-in grid: also varies entropy, density, network, concurrency.
    Combinatorially large -- opt-in via APE_GRID=full, not the default path.

    density only matters for payload_weight=light -- k6/workload.js ignores
    the DENSITY env var entirely when payload_weight=heavy (heavy draws from
    the track pool, not an image density tier). Crossing density with
    payload_weight=heavy anyway would produce blocks that are functionally
    IDENTICAL to a heavy block at any other density value (same requests,
    same pool, just a different label) -- wasted runtime that pads the plan
    without adding information. heavy blocks get exactly ONE density value
    (cfg.core_density, labelled honestly) regardless of how many densities
    are configured; light blocks get the full cross.
    """
    blocks = []
    seen_heavy_keys = set()
    combos = itertools.product(
        PROTOCOLS, CACHING_LEVELS, ACCESS_PATTERNS, cfg.entropy_levels,
        PAYLOAD_WEIGHTS, cfg.network_profiles, cfg.densities, cfg.concurrency_levels,
    )
    idx = 0
    for protocol, caching, access_pattern, entropy, payload_weight, network, density, concurrency in combos:
        if payload_weight == "heavy":
            density = cfg.core_density
            heavy_key = (protocol, caching, access_pattern, entropy, network, concurrency)
            if heavy_key in seen_heavy_keys:
                continue
            seen_heavy_keys.add(heavy_key)
        blocks.append({
            "block_id": f"B{idx:04d}",
            "protocol": protocol,
            "caching": caching,
            "access_pattern": access_pattern,
            "entropy": entropy,
            "payload_weight": payload_weight,
            "network": network,
            "density": density,
            "concurrency": concurrency,
            "page_size": _NOT_PAGE_MODE,
        })
        idx += 1
    return blocks


def build_batch_grid_blocks(cfg) -> List[dict]:
    """Round-trip-SAVINGS arm: protocol x caching x access_pattern x
    page_size, light payload only (page semantics don't extend to heavy/
    track requests in this design). entropy/network/density/concurrency held
    at core values -- this arm isolates the K-round-trips-vs-1-composite-
    round-trip LATENCY tradeoff, not a drill-in on those other factors.
    page_size=1 is a deliberate sanity baseline: a "page of 1" should
    closely match the core grid's existing single-image light-payload data,
    validating the new images(ids) GraphQL field and page-mode k6 path
    before trusting page_size=5/10's results.

    SCOPE NOTE (verified via pilot, 2026-06-28): this arm's `pages` are
    FIXED, non-overlapping id partitions (build_id_pool.py) -- an id never
    appears in more than one page. That gives GraphQL's composite cache
    entry a fair chance to be reused (a hot page recurring), but it also
    means REST's per-id cache never benefits from an id being SHARED across
    different page compositions, since pages never share ids by
    construction. Pilot data confirmed this: REST and GraphQL hit rates
    track closely together (e.g. 0.79 vs 0.82 at K=10) instead of showing
    REST's hoped-for granularity advantage. This arm answers "how much does
    aggregating into fewer round trips cost in latency" cleanly (REST scales
    ~linearly with K, GraphQL sub-linearly) -- it does NOT demonstrate the
    cache-granularity-loss half of the round-trip-vs-cacheability coupling;
    that would need overlapping page composition (e.g. sliding windows),
    deliberately out of scope for this arm."""
    blocks = []
    combos = itertools.product(PROTOCOLS, CACHING_LEVELS, ACCESS_PATTERNS, cfg.page_sizes)
    for idx, (protocol, caching, access_pattern, page_size) in enumerate(combos):
        blocks.append({
            "block_id": f"B{idx:04d}",
            "protocol": protocol,
            "caching": caching,
            "access_pattern": access_pattern,
            "entropy": cfg.core_entropy,
            "payload_weight": "light",
            "network": cfg.core_network,
            "density": cfg.core_density,
            "concurrency": cfg.core_concurrency,
            "page_size": page_size,
        })
    return blocks


def build_plan_rows(blocks: List[dict], n_warmup: int, n_measured: int, seed: int) -> List[dict]:
    shuffled = list(blocks)
    random.Random(seed).shuffle(shuffled)

    rows = []
    for block_order, block in enumerate(shuffled):
        for run_index in range(n_warmup):
            rows.append(_row(block, block_order, run_index, is_warmup=True))
        for run_index in range(n_measured):
            rows.append(_row(block, block_order, run_index, is_warmup=False))
    return rows


def _row(block: dict, block_order: int, run_index: int, is_warmup: bool) -> dict:
    row = {"run_uid": _run_uid(block, is_warmup, run_index), "block_order": block_order}
    row.update({k: block[k] for k in _FACTOR_KEYS})
    row["block_id"] = block["block_id"]
    row["run_index"] = run_index
    row["is_warmup"] = int(is_warmup)
    return row


def write_plan(rows: List[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    cfg = get_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(cfg.run_plan_csv))
    args = ap.parse_args()

    if cfg.grid == "full":
        blocks = build_full_grid_blocks(cfg)
    elif cfg.grid == "batch":
        blocks = build_batch_grid_blocks(cfg)
    else:
        blocks = build_core_grid_blocks(cfg)
    rows = build_plan_rows(blocks, cfg.n_warmup, cfg.n_measured, cfg.seed)

    out_path = Path(args.out)
    write_plan(rows, out_path)

    n_measured_rows = sum(1 for r in rows if not r["is_warmup"])
    n_warmup_rows = sum(1 for r in rows if r["is_warmup"])
    print(f"Grid: {cfg.grid}")
    print(f"Blocks: {len(blocks)}")
    print(f"Warmup rows: {n_warmup_rows} | Measured rows: {n_measured_rows} | Total: {len(rows)}")
    print(f"Seed: {cfg.seed}")
    print(f"Written to {out_path}")


if __name__ == "__main__":
    main()
