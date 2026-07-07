#!/usr/bin/env python3
"""
rq1_scenario_figures.py — figur RQ1 dari results.csv mot-scenarios-core.
JALANKAN HANYA SETELAH RUN SELESAI (3.240 run terukur). Skrip menolak data
parsial kecuali --allow-partial diberikan secara eksplisit.

Menghasilkan per rate sub-saturasi (r40, r80) — dan TERPISAH untuk
r120_overload (tidak pernah dipool, judul diberi label overload):
  fig_rq1_lat_p50_<rate>       — median lat_p50 per skenario M1–M4 × tier
                                 densitas, REST vs GraphQL (whisker = IQR)
  fig_rq1_lat_p95_<rate>       — sama untuk lat_p95
  fig_rq1_throughput_<rate>    — median throughput_rps per skenario × tier
  fig_rq1_cpu_<rate>           — median cpu_mean per skenario × tier
  fig_rq1_rss_<rate>           — median rss_mean_mb per skenario × tier
  + sidecar rq1_stats.json     — n, median, IQR per cell per metrik,
                                 jumlah baris dropped_iterations>0 per cell

Konvensi: matplotlib polos, satu Axes per figur, tanpa seaborn, tanpa warna
eksplisit (protokol = siklus warna default). Terminologi: waktu respons,
throughput. CPU/RSS di sesi MOT valid (bug sampler diperbaiki sebelum run) —
tetap cek kewajaran variasinya sebelum melaporkan (catatan outline C.9).

Pakai (setelah run selesai):
  venv/bin/python rq1_scenario_figures.py \
      --input .../mot-scenarios-core/results.csv --outdir .../figures/export

Dry-run (membuktikan skrip jalan; TIDAK menghasilkan figur laporan):
  venv/bin/python rq1_scenario_figures.py \
      --input .../phase2-core-real/results.csv --outdir /tmp/dryrun --dry-run
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SCENARIOS = ["M1", "M2", "M3", "M4"]
TIERS = ["low", "medium", "high"]
SUBSAT_RATES = ["r40", "r80"]
OVERLOAD_RATE = "r120_overload"
PROTOCOLS = ["rest", "graphql"]
PROTO_LABEL = {"rest": "REST", "graphql": "GraphQL"}
N_EXPECTED_PER_CELL = 30

REQUIRED_COLS = [
    "protocol", "scenario", "tier", "rate_label",
    "lat_p50", "lat_p95", "throughput_rps",
    "cpu_mean", "rss_mean_mb", "dropped_iterations",
]

METRICS = {
    "lat_p50": ("Median waktu respons p50 (ms)", "fig_rq1_lat_p50"),
    "lat_p95": ("Median waktu respons p95 (ms)", "fig_rq1_lat_p95"),
    "throughput_rps": ("Median throughput (request/s)", "fig_rq1_throughput"),
    "cpu_mean": ("Median CPU server (%)", "fig_rq1_cpu"),
    "rss_mean_mb": ("Median RSS server (MB)", "fig_rq1_rss"),
}


def schema_report(df: pd.DataFrame) -> list:
    return [c for c in REQUIRED_COLS if c not in df.columns]


def synthesize_for_dry_run(df: pd.DataFrame) -> pd.DataFrame:
    """Melengkapi kolom MOT yang tidak ada di CSV non-MOT HANYA untuk
    membuktikan jalur plotting berjalan. Pemetaan deterministik (seed 42);
    angka hasilnya TIDAK bermakna."""
    df = df.copy()
    rng = np.random.default_rng(42)
    n = len(df)
    if "scenario" not in df.columns:
        df["scenario"] = rng.choice(SCENARIOS, n)
    if "tier" not in df.columns:
        df["tier"] = rng.choice(TIERS, n)
    if "rate_label" not in df.columns:
        df["rate_label"] = rng.choice(SUBSAT_RATES + [OVERLOAD_RATE], n)
    if "dropped_iterations" not in df.columns:
        df["dropped_iterations"] = 0
    for col in ("cpu_mean", "rss_mean_mb"):
        if col not in df.columns:
            df[col] = np.nan
    return df


def completeness_check(df: pd.DataFrame) -> list:
    """Daftar cell RQ1 yang kurang dari N_EXPECTED_PER_CELL run."""
    problems = []
    sub = df[df.scenario.isin(SCENARIOS)]
    for sc in SCENARIOS:
        for tier in TIERS:
            for rate in SUBSAT_RATES + [OVERLOAD_RATE]:
                for proto in PROTOCOLS:
                    n = len(sub[(sub.scenario == sc) & (sub.tier == tier)
                                & (sub.rate_label == rate) & (sub.protocol == proto)])
                    if n < N_EXPECTED_PER_CELL:
                        problems.append(f"{sc}/{tier}/{rate}/{proto}: {n}/{N_EXPECTED_PER_CELL}")
    return problems


def style_axes(ax) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", linewidth=0.4, alpha=0.4)
    ax.set_axisbelow(True)


def plot_metric_for_rate(df: pd.DataFrame, metric: str, rate: str,
                         outdir: Path, dry_run: bool) -> dict:
    ylabel, stem = METRICS[metric]
    sub = df[(df.scenario.isin(SCENARIOS)) & (df.rate_label == rate)]
    fig, ax = plt.subplots(figsize=(9.5, 4.6))
    stats = {}
    group_w, bar_w, gap = 1.0, 0.36, 0.05
    xticks, xticklabels = [], []
    seen = set()
    for gi, (sc, tier) in enumerate([(s, t) for s in SCENARIOS for t in TIERS]):
        xticks.append(gi * group_w)
        xticklabels.append(f"{sc}\n{tier}")
        for pi, proto in enumerate(PROTOCOLS):
            cell = sub[(sub.scenario == sc) & (sub.tier == tier)
                       & (sub.protocol == proto)][metric].dropna().to_numpy()
            key = f"{sc}|{tier}|{rate}|{proto}"
            if len(cell) == 0:
                stats[key] = {"n": 0}
                continue
            med = float(np.median(cell))
            q1, q3 = np.percentile(cell, [25, 75])
            x = gi * group_w + (pi - 0.5) * (bar_w + gap)
            label = PROTO_LABEL[proto] if proto not in seen else None
            seen.add(proto)
            ax.bar(x, med, width=bar_w, color=f"C{pi}",
                   edgecolor="white", linewidth=0.5, label=label)
            ax.errorbar(x, med, yerr=[[med - q1], [q3 - med]], fmt="none",
                        ecolor="0.25", capsize=2, linewidth=0.9)
            n_drop = int((sub[(sub.scenario == sc) & (sub.tier == tier)
                              & (sub.protocol == proto)].dropped_iterations > 0).sum())
            stats[key] = {"n": int(len(cell)), "median": round(med, 3),
                          "q1": round(float(q1), 3), "q3": round(float(q3), 3),
                          "rows_with_dropped_iterations": n_drop}
    ax.set_xticks(xticks)
    ax.set_xticklabels(xticklabels, fontsize=8)
    ax.set_xlabel("Skenario × tier densitas objek")
    ax.set_ylabel(ylabel)
    style_axes(ax)
    ax.legend(frameon=False, fontsize=9)
    log_note = ""
    if rate == OVERLOAD_RATE and metric in ("lat_p50", "lat_p95"):
        # kolaps saturasi (mis. M1-high GraphQL ~6,7 dtk) meratakan bar lain
        # pada sumbu linier — log satu-satunya cara semua cell tetap terbaca
        ax.set_yscale("log")
        log_note = "; sumbu-y logaritmik"
    overload_note = ("\n— TIER OVERLOAD (r120): dianalisis TERPISAH, "
                     "jangan bandingkan dengan r40/r80"
                     if rate == OVERLOAD_RATE else "")
    dry_note = "  [DRY-RUN — DATA SINTETIS, BUKAN HASIL]" if dry_run else ""
    ax.set_title(f"RQ1 — {ylabel} per skenario M1–M4, rate {rate}{dry_note}"
                 f"{overload_note}\n"
                 f"n = {N_EXPECTED_PER_CELL} run per cell; whisker = IQR{log_note}",
                 fontsize=10)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(outdir / f"{stem}_{rate}.{ext}", dpi=200)
    plt.close(fig)
    return stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--outdir", required=True, type=Path)
    ap.add_argument("--dry-run", action="store_true",
                    help="buktikan eksekusi pada CSV non-MOT; sintesis kolom, watermark, tanpa guard kelengkapan")
    ap.add_argument("--allow-partial", action="store_true",
                    help="lewati guard kelengkapan (JANGAN dipakai untuk figur laporan)")
    args = ap.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.input)
    missing = schema_report(df)
    if missing:
        print(f"[schema] kolom tidak ada di {args.input.name}: {missing}")
        if not args.dry_run:
            raise SystemExit("Berhenti: bukan CSV MOT lengkap. Pakai --dry-run untuk uji eksekusi.")
        print("[schema] dry-run: kolom disintesis deterministik (seed 42) — angka TIDAK bermakna.")
        df = synthesize_for_dry_run(df)
    else:
        print("[schema] semua kolom wajib ada.")

    if not args.dry_run:
        problems = completeness_check(df)
        if problems and not args.allow_partial:
            print(f"Cell belum lengkap ({len(problems)}):")
            for p in problems[:20]:
                print("  ", p)
            raise SystemExit("Berhenti: data parsial tidak boleh di-chart (aturan studi). "
                             "--allow-partial hanya untuk inspeksi, bukan figur laporan.")

    sidecar = {"source_csv": str(args.input), "n_rows": int(len(df)),
               "dry_run": bool(args.dry_run), "metrics": {}}
    for metric in METRICS:
        sidecar["metrics"][metric] = {}
        for rate in SUBSAT_RATES + [OVERLOAD_RATE]:
            sidecar["metrics"][metric][rate] = plot_metric_for_rate(
                df, metric, rate, args.outdir, args.dry_run)
    (args.outdir / "rq1_stats.json").write_text(json.dumps(sidecar, indent=2))
    print(f"OK: figur RQ1 (PNG+SVG) + rq1_stats.json ditulis ke {args.outdir}")


if __name__ == "__main__":
    main()
