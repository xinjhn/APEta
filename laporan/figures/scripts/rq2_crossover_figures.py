#!/usr/bin/env python3
"""
rq2_crossover_figures.py — figur RQ2 (KONTRIBUSI UTAMA) dari results.csv
mot-scenarios-core. JALANKAN HANYA SETELAH RUN SELESAI; menolak data parsial
kecuali --allow-partial.

Variabel pembanding = page_latency_med (latensi level-skenario: REST = jumlah
K atau 2 sub-panggilan; GraphQL = 1 panggilan), BUKAN lat_p* per-HTTP-call —
semantik dari k6/workload_mot.js (pageLatency/roundTripCount).

Menghasilkan per rate sub-saturasi (r40, r80) — r120_overload TERPISAH:
  fig_rq2_m5_window_<rate>     — median page_latency M5: REST (2 round-trip)
                                 vs GraphQL (1 kueri) per tier window w2/w8/w23
  fig_rq2_m6_crossover_<rate>  — median page_latency M6 vs K (1/5/10):
                                 garis REST (round_trip_count = K) vs GraphQL
                                 (= 1); titik silang K* ditandai bila garis
                                 berpotongan (interpolasi linier tanda Δ)
  fig_rq2_delta_rtc_<rate>     — Δ = REST − GraphQL (median page_latency)
                                 terhadap jumlah round-trip REST {1,2,5,10}
                                 gabungan M5+M6 (sumbu penjelas konsolidasi
                                 round-trip; CI bootstrap 95% selisih median)
  + sidecar rq2_stats.json     — n, median, IQR, Δ, CI, K* per rate

Konvensi: matplotlib polos, satu Axes per figur, tanpa seaborn, tanpa warna
eksplisit. Terminologi: waktu respons, jumlah round-trip.

Dry-run: --dry-run pada CSV non-MOT — melaporkan beda skema, mensintesis
kolom (seed 42) hanya untuk membuktikan eksekusi, watermark pada judul.
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

WINDOW_TIERS = ["w2", "w8", "w23"]
PAGE_TIERS = ["k1", "k5", "k10"]
SUBSAT_RATES = ["r40", "r80"]
OVERLOAD_RATE = "r120_overload"
PROTOCOLS = ["rest", "graphql"]
PROTO_LABEL = {"rest": "REST", "graphql": "GraphQL"}
N_EXPECTED_PER_CELL = 30
SEED = 42
N_BOOT = 2000

REQUIRED_COLS = ["protocol", "scenario", "tier", "rate_label",
                 "page_latency_med", "round_trip_count", "dropped_iterations"]


def bootstrap_median_diff_ci(x: np.ndarray, y: np.ndarray) -> tuple:
    rng = np.random.default_rng(SEED)
    diffs = np.empty(N_BOOT)
    for i in range(N_BOOT):
        diffs[i] = (np.median(rng.choice(x, len(x), replace=True))
                    - np.median(rng.choice(y, len(y), replace=True)))
    return float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))


def schema_report(df: pd.DataFrame) -> list:
    return [c for c in REQUIRED_COLS if c not in df.columns]


def synthesize_for_dry_run(df: pd.DataFrame) -> pd.DataFrame:
    """Kolom MOT sintetis deterministik (seed 42) — angka TIDAK bermakna,
    hanya membuktikan jalur plotting berjalan."""
    df = df.copy()
    rng = np.random.default_rng(SEED)
    n = len(df)
    if "scenario" not in df.columns:
        df["scenario"] = rng.choice(["M5", "M6"], n)
    if "tier" not in df.columns:
        df["tier"] = np.where(df["scenario"] == "M5",
                              rng.choice(WINDOW_TIERS, n), rng.choice(PAGE_TIERS, n))
    if "rate_label" not in df.columns:
        df["rate_label"] = rng.choice(SUBSAT_RATES + [OVERLOAD_RATE], n)
    if "page_latency_med" not in df.columns:
        base = df["lat_p50"] if "lat_p50" in df.columns else pd.Series(rng.uniform(20, 40, n))
        df["page_latency_med"] = base * np.where(df["protocol"] == "rest", 2.0, 1.0)
    if "round_trip_count" not in df.columns or df["round_trip_count"].nunique() <= 1:
        k = df["tier"].str.lstrip("wk").astype(float).fillna(1)
        df["round_trip_count"] = np.where(
            df["protocol"] == "rest",
            np.where(df["scenario"] == "M5", 2, k), 1)
    if "dropped_iterations" not in df.columns:
        df["dropped_iterations"] = 0
    return df


def completeness_check(df: pd.DataFrame) -> list:
    problems = []
    for sc, tiers in (("M5", WINDOW_TIERS), ("M6", PAGE_TIERS)):
        for tier in tiers:
            for rate in SUBSAT_RATES + [OVERLOAD_RATE]:
                for proto in PROTOCOLS:
                    n = len(df[(df.scenario == sc) & (df.tier == tier)
                               & (df.rate_label == rate) & (df.protocol == proto)])
                    if n < N_EXPECTED_PER_CELL:
                        problems.append(f"{sc}/{tier}/{rate}/{proto}: {n}/{N_EXPECTED_PER_CELL}")
    return problems


def style_axes(ax) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", linewidth=0.4, alpha=0.4)
    ax.set_axisbelow(True)


def cell_values(df, sc, tier, rate, proto) -> np.ndarray:
    return df[(df.scenario == sc) & (df.tier == tier) & (df.rate_label == rate)
              & (df.protocol == proto)].page_latency_med.dropna().to_numpy()


def title_suffix(rate: str, dry_run: bool) -> str:
    s = ""
    if rate == OVERLOAD_RATE:
        s += " — TIER OVERLOAD (r120): dianalisis TERPISAH"
    if dry_run:
        s += "  [DRY-RUN — DATA SINTETIS, BUKAN HASIL]"
    return s


def fig_m5_window(df, rate, outdir, dry_run) -> dict:
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    stats = {}
    bar_w, gap = 0.34, 0.05
    for pi, proto in enumerate(PROTOCOLS):
        for gi, tier in enumerate(WINDOW_TIERS):
            vals = cell_values(df, "M5", tier, rate, proto)
            key = f"M5|{tier}|{rate}|{proto}"
            if len(vals) == 0:
                stats[key] = {"n": 0}
                continue
            med = float(np.median(vals))
            q1, q3 = np.percentile(vals, [25, 75])
            x = gi + (pi - 0.5) * (bar_w + gap)
            rtc = 2 if proto == "rest" else 1
            ax.bar(x, med, width=bar_w, color=f"C{pi}",
                   edgecolor="white", linewidth=0.5,
                   label=f"{PROTO_LABEL[proto]} ({rtc} round-trip)" if gi == 0 else None)
            ax.errorbar(x, med, yerr=[[med - q1], [q3 - med]], fmt="none",
                        ecolor="0.25", capsize=2.5, linewidth=1)
            stats[key] = {"n": int(len(vals)), "median": round(med, 3),
                          "q1": round(float(q1), 3), "q3": round(float(q3), 3),
                          "round_trip_count": rtc}
    ax.set_xticks(range(len(WINDOW_TIERS)))
    ax.set_xticklabels([f"{t}\n({2*int(t[1:])+1} titik)" for t in WINDOW_TIERS])
    ax.set_xlabel("Tier window trajektori")
    ax.set_ylabel("Median waktu respons skenario (ms)\n(page_latency: REST = jumlah 2 sub-panggilan)")
    style_axes(ax)
    ax.legend(frameon=False, fontsize=9)
    ax.set_title(f"RQ2 — M5 trajektori bersarang: 2 round-trip REST vs 1 kueri GraphQL, "
                 f"rate {rate}{title_suffix(rate, dry_run)}\n"
                 f"n = {N_EXPECTED_PER_CELL} run per cell; whisker = IQR", fontsize=10)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(outdir / f"fig_rq2_m5_window_{rate}.{ext}", dpi=200)
    plt.close(fig)
    return stats


def fig_m6_crossover(df, rate, outdir, dry_run) -> dict:
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    stats = {}
    ks = [int(t[1:]) for t in PAGE_TIERS]
    med_by_proto = {}
    for pi, proto in enumerate(PROTOCOLS):
        meds, los, his = [], [], []
        for tier in PAGE_TIERS:
            vals = cell_values(df, "M6", tier, rate, proto)
            key = f"M6|{tier}|{rate}|{proto}"
            if len(vals) == 0:
                stats[key] = {"n": 0}
                meds.append(np.nan), los.append(np.nan), his.append(np.nan)
                continue
            med = float(np.median(vals))
            q1, q3 = np.percentile(vals, [25, 75])
            meds.append(med), los.append(q1), his.append(q3)
            rtc = int(tier[1:]) if proto == "rest" else 1
            stats[key] = {"n": int(len(vals)), "median": round(med, 3),
                          "q1": round(float(q1), 3), "q3": round(float(q3), 3),
                          "round_trip_count": rtc}
        med_by_proto[proto] = np.array(meds)
        ax.errorbar(ks, meds, yerr=[np.array(meds) - np.array(los),
                                    np.array(his) - np.array(meds)],
                    marker="o", markersize=6, linewidth=1.8, capsize=3,
                    color=f"C{pi}", label=PROTO_LABEL[proto])
        for k, m in zip(ks, meds):
            rtc = k if proto == "rest" else 1
            ax.annotate(f"{rtc} RT", (k, m), textcoords="offset points",
                        xytext=(6, 6 if proto == "rest" else -12), fontsize=8,
                        color=f"C{pi}")
    # Titik silang K*: interpolasi linier tanda Δ(K) = REST − GraphQL
    k_star = None
    d = med_by_proto["rest"] - med_by_proto["graphql"]
    for i in range(len(ks) - 1):
        if np.isfinite(d[i]) and np.isfinite(d[i + 1]) and d[i] * d[i + 1] < 0:
            k_star = ks[i] + (ks[i + 1] - ks[i]) * abs(d[i]) / (abs(d[i]) + abs(d[i + 1]))
            ax.axvline(k_star, linestyle="--", linewidth=1, color="0.35")
            ax.annotate(f"crossover K* ≈ {k_star:.1f}",
                        (k_star, float(np.nanmax([med_by_proto['rest'].max(),
                                                  med_by_proto['graphql'].max()]))),
                        textcoords="offset points", xytext=(6, -2), fontsize=9)
            break
    ax.set_xticks(ks)
    ax.set_xlabel("Ukuran halaman K (id track per iterasi)")
    ax.set_ylabel("Median waktu respons halaman (ms)\n(page_latency: REST = jumlah K sub-panggilan)")
    style_axes(ax)
    ax.legend(frameon=False, fontsize=9)
    ax.set_title(f"RQ2 — M6: K round-trip REST vs 1 kueri GraphQL, rate {rate}"
                 f"{title_suffix(rate, dry_run)}\n"
                 f"anotasi = jumlah round-trip (RT) per iterasi; "
                 f"n = {N_EXPECTED_PER_CELL} run per titik; whisker = IQR", fontsize=9)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(outdir / f"fig_rq2_m6_crossover_{rate}.{ext}", dpi=200)
    plt.close(fig)
    return {"cells": stats, "k_star": None if k_star is None else round(float(k_star), 2)}


def fig_delta_vs_rtc(df, rate, outdir, dry_run) -> dict:
    """Δ = REST − GraphQL (median page_latency) terhadap jumlah round-trip
    REST pada cell yang sama: M6-k1 → 1, M5 (per window, Δ dirata-mediankan
    per tier lalu ditampilkan per tier) → 2, M6-k5 → 5, M6-k10 → 10."""
    points = []  # (rtc, label, delta, lo, hi, n_rest, n_gql)
    cells = [("M6", "k1", 1), ("M5", "w2", 2), ("M5", "w8", 2), ("M5", "w23", 2),
             ("M6", "k5", 5), ("M6", "k10", 10)]
    for sc, tier, rtc in cells:
        r = cell_values(df, sc, tier, rate, "rest")
        g = cell_values(df, sc, tier, rate, "graphql")
        if len(r) == 0 or len(g) == 0:
            continue
        delta = float(np.median(r) - np.median(g))
        lo, hi = bootstrap_median_diff_ci(r, g)
        points.append((rtc, f"{sc}-{tier}", delta, lo, hi, len(r), len(g)))
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    stats = {}
    for rtc, label, delta, lo, hi, nr, ng in points:
        ax.errorbar(rtc, delta, yerr=[[delta - lo], [hi - delta]], marker="o",
                    markersize=7, capsize=3, linewidth=1.2, color="C0")
        ax.annotate(label, (rtc, delta), textcoords="offset points",
                    xytext=(7, 4), fontsize=8)
        stats[label] = {"round_trip_count_rest": rtc, "delta_ms": round(delta, 3),
                        "ci95": [round(lo, 3), round(hi, 3)],
                        "n_rest": nr, "n_graphql": ng}
    ax.axhline(0, color="0.2", linewidth=0.8)
    ax.annotate("Δ > 0: GraphQL lebih cepat", xy=(0.99, 0.97), xycoords="axes fraction",
                ha="right", va="top", fontsize=8, color="0.35")
    ax.annotate("Δ < 0: REST lebih cepat", xy=(0.99, 0.03), xycoords="axes fraction",
                ha="right", va="bottom", fontsize=8, color="0.35")
    ax.set_xticks([1, 2, 5, 10])
    ax.set_xlabel("Jumlah round-trip REST per iterasi (GraphQL selalu 1)")
    ax.set_ylabel("Δ median waktu respons skenario (ms)\nREST − GraphQL, cell yang sama")
    style_axes(ax)
    ax.set_title(f"RQ2 — konsolidasi round-trip: selisih REST−GraphQL terhadap jumlah "
                 f"round-trip, rate {rate}{title_suffix(rate, dry_run)}\n"
                 f"gabungan M5+M6 pada rate sama; whisker = CI bootstrap 95% selisih median",
                 fontsize=10)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(outdir / f"fig_rq2_delta_rtc_{rate}.{ext}", dpi=200)
    plt.close(fig)
    return stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--outdir", required=True, type=Path)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--allow-partial", action="store_true")
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
            raise SystemExit("Berhenti: data parsial tidak boleh di-chart (aturan studi).")

    sidecar = {"source_csv": str(args.input), "n_rows": int(len(df)),
               "dry_run": bool(args.dry_run),
               "comparison_variable": "page_latency_med (bukan lat_p* per-HTTP-call)",
               "rates": {}}
    for rate in SUBSAT_RATES + [OVERLOAD_RATE]:
        sidecar["rates"][rate] = {
            "m5_window": fig_m5_window(df, rate, args.outdir, args.dry_run),
            "m6_crossover": fig_m6_crossover(df, rate, args.outdir, args.dry_run),
            "delta_vs_round_trip": fig_delta_vs_rtc(df, rate, args.outdir, args.dry_run),
        }
    (args.outdir / "rq2_stats.json").write_text(json.dumps(sidecar, indent=2))
    print(f"OK: figur RQ2 (PNG+SVG) + rq2_stats.json ditulis ke {args.outdir}")


if __name__ == "__main__":
    main()
