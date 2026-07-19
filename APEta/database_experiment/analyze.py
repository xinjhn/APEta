#!/usr/bin/env python3
"""Paired analysis for the interleaved database experiment."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon
import matplotlib.pyplot as plt


def cell_label(row: pd.Series) -> str:
    suffix = ""
    if pd.notna(row.get("tier")):
        suffix = f"/{row['tier']}"
    elif pd.notna(row.get("k")):
        suffix = f"/k{int(row['k'])}"
    elif pd.notna(row.get("window")):
        suffix = f"/w{int(row['window'])}"
    return f"{row['operation']}{suffix}"


def holm(p_values: list[float]) -> list[float]:
    order = np.argsort(p_values)
    adjusted = np.empty(len(p_values), dtype=float)
    running = 0.0
    m = len(p_values)
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p_values[index]))
        adjusted[index] = running
    return adjusted.tolist()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()
    out_dir = args.out_dir or args.input.parent / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    data = pd.read_csv(args.input)
    if not data["parity_ok"].astype(bool).all():
        raise SystemExit("parity gate failed; performance analysis is invalid")
    data["cell"] = data.apply(cell_label, axis=1)
    # Cases are repeated within each randomized block. Treating all request
    # calls as independent would be pseudo-replication. Collapse cases to one
    # median per block x cell x backend, then pair the 30 block summaries.
    block_cells = (
        data.groupby(["backend", "block", "cell"], as_index=False)
        .agg(latency_ms=("latency_ms", "median"), cases=("case_id", "nunique"))
    )
    sqlite = block_cells[block_cells.backend == "sqlite"][["block", "cell", "latency_ms", "cases"]]
    if sqlite.empty:
        raise SystemExit("SQLite measurements are required as the paired reference")

    rows: list[dict] = []
    for backend in sorted(set(data.backend) - {"sqlite"}):
        other = block_cells[block_cells.backend == backend][["block", "cell", "latency_ms", "cases"]]
        paired = sqlite.merge(other, on=["block", "cell"], suffixes=("_sqlite", "_other"))
        for cell, group in paired.groupby("cell", sort=True):
            left = group.latency_ms_sqlite.to_numpy()
            right = group.latency_ms_other.to_numpy()
            delta = right - left
            try:
                p_value = float(wilcoxon(right, left, alternative="two-sided").pvalue)
            except ValueError:
                p_value = 1.0
            rows.append({
                "backend": backend, "cell": cell, "n_pairs": len(group),
                "cases_per_block": int(group.cases_sqlite.min()),
                "sqlite_median_ms": float(np.median(left)),
                "backend_median_ms": float(np.median(right)),
                "median_paired_delta_ms": float(np.median(delta)),
                "median_paired_ratio": float(np.median(right / left)),
                "backend_faster_fraction": float(np.mean(right < left)),
                "wilcoxon_p_raw": p_value,
            })
    summary = pd.DataFrame(rows)
    summary["wilcoxon_p_holm"] = holm(summary.wilcoxon_p_raw.tolist())
    summary["significant_0_05"] = summary.wilcoxon_p_holm < 0.05
    summary.to_csv(out_dir / "paired_summary.csv", index=False)

    overall = data.groupby("backend").latency_ms.agg(
        n="count", median_ms="median", mean_ms="mean",
        p95_ms=lambda s: s.quantile(0.95), p99_ms=lambda s: s.quantile(0.99),
    ).reset_index()
    overall.to_csv(out_dir / "overall_summary.csv", index=False)

    cell_medians = data.groupby(["backend", "cell"], as_index=False).latency_ms.median()
    preferred_order = [
        f"{op}/{level}"
        for op, levels in (
            ("image_detections", ("low", "medium", "high")),
            ("filtered_detections", ("low", "medium", "high")),
            ("class_counts", ("low", "medium", "high")),
            ("trajectory", ("w2", "w8", "w23")),
            ("trajectories", ("k1", "k5", "k10")),
        )
        for level in levels
    ]
    cells = [cell for cell in preferred_order if cell in set(cell_medians.cell)]
    fig, ax = plt.subplots(figsize=(13, 6.2))
    fig.subplots_adjust(left=0.09, right=0.985, bottom=0.34, top=0.90)
    colors = {
        "sqlite": "#2563eb", "postgresql": "#7c3aed",
        "mongodb": "#16a34a", "neo4j": "#dc2626",
    }
    for backend in ("sqlite", "postgresql", "mongodb", "neo4j"):
        subset = cell_medians[cell_medians.backend == backend].set_index("cell")
        if subset.empty:
            continue
        ax.plot(
            range(len(cells)), [subset.loc[cell, "latency_ms"] for cell in cells],
            marker="o", linewidth=2, label=backend, color=colors[backend],
        )
    ax.set_yscale("log")
    ax.set_ylabel("Median database-call latency (ms, log scale)")
    ax.set_xticks(range(len(cells)), cells, rotation=42, ha="right")
    ax.grid(axis="y", which="both", alpha=0.25)
    ax.legend(frameon=False, ncols=3)
    ax.set_title("Database sensitivity on parity-equivalent APE MOT queries")
    fig.savefig(out_dir / "latency_by_cell.png", dpi=220)
    plt.close(fig)
    report = {
        "parity_pass": True,
        "measurement_rows": int(len(data)),
        "backends": sorted(data.backend.unique().tolist()),
        "cells": sorted(data.cell.unique().tolist()),
        "interpretation_guardrail": (
            "A faster engine is not automatically the best data model. Combine paired latency "
            "with model fit, deployment complexity, storage cost, write/concurrency needs, and "
            "whether the REST-vs-GraphQL conclusion changes by backend."
        ),
    }
    (out_dir / "analysis_manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(overall.to_string(index=False))
    print(f"wrote analysis to {out_dir}")


if __name__ == "__main__":
    main()
