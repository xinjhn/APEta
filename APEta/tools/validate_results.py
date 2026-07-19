"""
tools/validate_results.py
===========================
Sanity-check kelengkapan & kewarasan results.csv terhadap run_plan.csv. BUKAN
analisis statistik (itu tahap terpisah) -- hanya memastikan tiap sel sudah
mencapai N_MEASURED, tidak ada error_rate tinggi, dan tidak ada metrik primer
yang NaN/kosong.

Pemakaian:
    python tools/validate_results.py --run-plan results/run_plan.csv \
        --results results/results.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

PRIMARY_METRICS = ["lat_p50", "lat_p95", "lat_p99", "throughput_rps", "payload_bytes_med", "xproc_p95", "xproc_med"]
MOT_PRIMARY_METRICS = ["lat_p50", "lat_p95", "lat_p99", "throughput_rps",
                       "payload_bytes_med", "round_trip_count"]
MOT_PAGE_LATENCY_SCENARIOS = {"M5", "M5E", "M6"}
ERROR_RATE_THRESHOLD = 0.01


def load_csv(path: Path) -> list:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def required_primary_metrics(row: dict, is_mot: bool) -> list[str]:
    metrics = list(MOT_PRIMARY_METRICS if is_mot else PRIMARY_METRICS)
    if is_mot and row.get("scenario") in MOT_PAGE_LATENCY_SCENARIOS:
        metrics.append("page_latency_med")
    return metrics


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-plan", required=True)
    ap.add_argument("--results", required=True)
    args = ap.parse_args()

    plan_rows = load_csv(Path(args.run_plan))
    results_rows = load_csv(Path(args.results)) if Path(args.results).exists() else []

    # Validate both the retired pattern/density schema and the current MOT
    # scenario/tier/rate schema. Using the measured run_uid contract is the
    # authoritative completeness check; cell summaries are diagnostic.
    factor_candidates = [
        "protocol", "scenario", "tier", "rate_label", "caching", "backend",
        "pattern", "density", "concurrency", "access_pattern", "page_size",
    ]
    headers = set(plan_rows[0]) if plan_rows else set()
    cell_keys = [key for key in factor_candidates if key in headers]

    measured_plan_rows = [r for r in plan_rows if r.get("is_warmup") == "0"]
    expected_uids = {r["run_uid"] for r in measured_plan_rows}
    expected_per_cell = defaultdict(int)
    for r in measured_plan_rows:
        cell = tuple(r.get(key, "") for key in cell_keys)
        expected_per_cell[cell] += 1

    actual_per_cell = defaultdict(int)
    by_uid = {}
    for r in results_rows:
        cell = tuple(r.get(key, "") for key in cell_keys)
        actual_per_cell[cell] += 1
        by_uid[r["run_uid"]] = r

    problems = []

    # 1. Duplikat run_uid
    seen = set()
    for r in results_rows:
        if r["run_uid"] in seen:
            problems.append(f"DUPLIKAT run_uid={r['run_uid']}")
        seen.add(r["run_uid"])

    missing_uids = expected_uids - seen
    unexpected_uids = seen - expected_uids
    for uid in sorted(missing_uids):
        problems.append(f"RUN TERUKUR HILANG run_uid={uid}")
    for uid in sorted(unexpected_uids):
        problems.append(f"RUN TAK DIRENCANAKAN run_uid={uid}")

    # 2. Kelengkapan per sel
    incomplete_cells = 0
    for cell, expected in expected_per_cell.items():
        actual = actual_per_cell.get(cell, 0)
        if actual < expected:
            incomplete_cells += 1
            problems.append(f"BELUM LENGKAP {cell}: {actual}/{expected}")
        elif actual > expected:
            problems.append(f"LEBIH BANYAK DARI RENCANA {cell}: {actual}/{expected}")

    # 3. error_rate tinggi
    high_error_runs = 0
    for r in results_rows:
        try:
            er = float(r["error_rate"]) if r["error_rate"] not in ("", "None") else None
        except ValueError:
            er = None
        if er is None or er > ERROR_RATE_THRESHOLD:
            high_error_runs += 1
            problems.append(f"error_rate tinggi/kosong run_uid={r['run_uid']} error_rate={r['error_rate']}")

    # 4. NaN/kosong di metrik primer
    is_mot = "scenario" in headers and any(r.get("scenario") for r in plan_rows)
    missing_metric_runs = 0
    for r in results_rows:
        # page_latency_med measures the combined client-visible latency of
        # multi-request flows. It exists for M5/M5E (trajectory + metadata)
        # and M6 (K-item page), but is intentionally blank for the single-
        # request M1-M4 scenarios.
        primary_metrics = required_primary_metrics(r, is_mot)
        missing = [m for m in primary_metrics if r.get(m) in ("", "None", None)]
        if missing:
            missing_metric_runs += 1
            problems.append(f"metrik primer kosong run_uid={r['run_uid']}: {missing}")

    print(f"Faktor sel: {', '.join(cell_keys)}")
    print(f"Sel direncanakan: {len(expected_per_cell)} | Run terukur tercatat: {len(results_rows)}")
    print(f"Run UID hilang/tak direncanakan: {len(missing_uids)}/{len(unexpected_uids)}")
    print(f"Sel belum lengkap: {incomplete_cells}/{len(expected_per_cell)}")
    print(f"Run dengan error_rate tinggi/kosong: {high_error_runs}")
    print(f"Run dengan metrik primer kosong: {missing_metric_runs}")

    if problems:
        print(f"\n{len(problems)} masalah ditemukan:")
        for p in problems[:50]:
            print(f"  - {p}")
        if len(problems) > 50:
            print(f"  ... dan {len(problems) - 50} lainnya")
        return 1

    print("\nOK -- semua sel lengkap, tidak ada error_rate tinggi, tidak ada metrik primer kosong.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
