"""
tools/combine_all_sessions.py
===============================
Combines all 10 Phase 2 results.csv files (core grid + 9 drill-in/
interaction/re-run sessions) into one master dataset for full-design
statistical analysis and figures.

Handling notes:
  - phase2-core-real and phase2-core-cpu-rerun are TWO independent
    replications of the IDENTICAL core-grid factor combinations (same
    protocol x caching x access_pattern x payload_weight at core values).
    Combining both is legitimate for latency/cache-hit/throughput metrics
    (genuine repeated measurement, n=60 instead of n=30 per core cell) --
    but phase2-core-real's cpu_mean/cpu_p95/rss_mean_mb/rss_p95_mb are
    DOCUMENTED INVALID (sudo-wrapper telemetry bug, see tools/analyze_phase2.py's
    SCOPE NOTES) and are nulled out here so they never contaminate any
    CPU/RSS-based statistic or figure -- only phase2-core-cpu-rerun's (and
    every other post-fix session's) CPU/RSS values are trusted.
  - Earlier sessions (core-real, entropy-drillin, density-drillin) predate
    the page_size/page_latency_med columns (the round-trip-savings arm) --
    pandas fills these as NaN on concat, correctly representing "not
    applicable" for non-batch-grid rows.
  - A `source_session` column is added so any downstream analysis can still
    filter/attribute rows back to their originating session.

Usage:
    python tools/combine_all_sessions.py --out results/phase2-combined/results.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

SESSIONS = [
    "phase2-core-real",
    "phase2-core-cpu-rerun",
    "phase2-entropy-drillin",
    "phase2-density-drillin",
    "phase2-network-drillin",
    "phase2-concurrency-drillin",
    "phase2-concurrency100-drillin",
    "phase2-batch-real",
    "phase2-entropy-concurrency-interaction",
    "phase2-network-concurrency-interaction",
]

CPU_RSS_COLS = ["cpu_mean", "cpu_p95", "rss_mean_mb", "rss_p95_mb"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/phase2-combined/results.csv")
    args = ap.parse_args()

    frames = []
    for session in SESSIONS:
        path = ROOT / "results" / session / "results.csv"
        if not path.exists():
            print(f"  [skip] {session}: no results.csv")
            continue
        df = pd.read_csv(path)
        df["source_session"] = session
        if session == "phase2-core-real":
            for col in CPU_RSS_COLS:
                if col in df.columns:
                    df[col] = pd.NA
        frames.append(df)
        print(f"  [loaded] {session}: {len(df)} rows")

    combined = pd.concat(frames, ignore_index=True, sort=False)
    # page_size=NaN (sessions predating the batch/round-trip-savings arm)
    # means "not in page mode" -- fill with 0, the same convention already
    # used by orchestrator/make_run_plan.py's core/full grid blocks. Without
    # this, pandas' default groupby(...) silently DROPS NaN-key rows
    # entirely, which would make every non-batch session vanish from any
    # analysis that groups by page_size.
    if "page_size" in combined.columns:
        combined["page_size"] = combined["page_size"].fillna(0).astype(int)
    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(out_path, index=False)
    print(f"\nTotal combined rows: {len(combined)}")
    print(f"Written to {out_path}")


if __name__ == "__main__":
    main()
