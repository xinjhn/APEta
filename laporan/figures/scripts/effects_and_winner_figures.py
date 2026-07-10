#!/usr/bin/env python3
"""
effects_and_winner_figures.py — figur analitik sintesis untuk laporan TA.

Menghasilkan (dari CSV komparasi yang sudah dianalisis, bukan raw):
  MOT (mot-scenarios-core/analysis/mot_comparisons.csv):
    fx_mot_maineffect_lat_p50   — efek marginal tiap variabel bebas (skenario,
                                  tier densitas, laju) terhadap median waktu
                                  respons p50, REST vs GraphQL.
    fx_mot_maineffect_lat_p95   — idem untuk p95.
    fx_mot_delta_heatmap_rt     — peta pemenang: signed Cliff's delta lat_p50,
                                  M1-M4 (round-trip). Biru=REST unggul,
                                  merah=GraphQL unggul, putih=imbang.
    fx_mot_delta_heatmap_page   — idem page_latency_med untuk M5-M6.
    fx_mot_mechanism_roundtrip  — median round_trip_count REST vs GraphQL per
                                  skenario-tier (mekanisme crossover M6).
    fx_mot_overfetch            — payload_bytes REST vs GraphQL M1-M4
                                  (uji klaim over-fetching).
    fx_mot_decoupling           — sebar delta latensi vs delta throughput per
                                  sel (dekopling latensi-throughput).
  Caching (phase2-core-real/analysis/phase2_comparisons.csv):
    fx_cache_maineffect         — efek marginal caching/access_pattern/
                                  payload_weight pada lat_p50 & cache_hit_rate.
    fx_cache_delta_heatmap      — peta pemenang signed delta untuk metrik kunci.

Sidecar: effects_stats.json (angka mentah tiap figur untuk verifikasi).

Konvensi: matplotlib polos, RdBu_r untuk delta (vmin=-1,vmax=1). Sign delta
latensi: <0 REST lebih cepat (unggul), >0 GraphQL lebih cepat.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REST_C, GQL_C = "#1f77b4", "#d62728"
PROTO_KW = dict(marker="o", linewidth=2, markersize=6)


def num(s):
    return pd.to_numeric(s, errors="coerce")


def load_mot(path):
    df = pd.read_csv(path)
    for c in ["rest_median", "graphql_median", "cliffs_delta", "p_value_holm"]:
        df[c] = num(df[c])
    return df


# ---------- MOT main-effect (marginal) ----------
def mot_maineffect(df, metric, ylabel, outpath, stats):
    sub = df[(df["metric"] == metric) & df["scenario"].isin(["M1", "M2", "M3", "M4"])].copy()
    factors = [
        ("scenario", ["M1", "M2", "M3", "M4"], "Skenario"),
        ("tier", ["low", "medium", "high"], "Tier densitas"),
        ("rate_label", ["r40", "r80", "r120_overload"], "Laju (arrival rate)"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    rec = {}
    for ax, (col, order, label) in zip(axes, factors):
        r_med = sub.groupby(col)["rest_median"].median().reindex(order)
        g_med = sub.groupby(col)["graphql_median"].median().reindex(order)
        x = np.arange(len(order))
        xt = [o.replace("r120_overload", "r120*").replace("r", "") if col == "rate_label" else o for o in order]
        ax.plot(x, r_med.values, color=REST_C, label="REST", **PROTO_KW)
        ax.plot(x, g_med.values, color=GQL_C, label="GraphQL", **PROTO_KW)
        ax.set_xticks(x); ax.set_xticklabels(xt)
        ax.set_xlabel(label); ax.grid(True, alpha=0.3)
        if ax is axes[0]:
            ax.set_ylabel(ylabel); ax.legend(frameon=False)
        rec[col] = {"levels": order, "rest": r_med.round(2).tolist(), "graphql": g_med.round(2).tolist()}
    fig.suptitle(f"Efek marginal variabel bebas terhadap {ylabel} (M1–M4)", y=1.02)
    fig.tight_layout()
    fig.savefig(outpath, dpi=150, bbox_inches="tight"); plt.close(fig)
    stats[outpath.stem] = rec


# ---------- signed delta heatmap ----------
def delta_heatmap(df, metric, scenarios, tier_order_map, outpath, title, stats):
    sub = df[(df["metric"] == metric) & df["scenario"].isin(scenarios)].copy()
    rates = ["r40", "r80", "r120_overload"]
    rows, rowlabels = [], []
    for sc in scenarios:
        tiers = tier_order_map[sc]
        for t in tiers:
            vals = []
            for rt in rates:
                cell = sub[(sub["scenario"] == sc) & (sub["tier"] == t) & (sub["rate_label"] == rt)]
                vals.append(cell["cliffs_delta"].iloc[0] if len(cell) else np.nan)
            rows.append(vals); rowlabels.append(f"{sc}·{t}")
    M = np.array(rows, float)
    fig, ax = plt.subplots(figsize=(5.2, 0.42 * len(rowlabels) + 1.2))
    im = ax.imshow(M, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(len(rates))); ax.set_xticklabels(["r40", "r80", "r120*"])
    ax.set_yticks(range(len(rowlabels))); ax.set_yticklabels(rowlabels, fontsize=8)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            if not np.isnan(M[i, j]):
                ax.text(j, i, f"{M[i,j]:+.2f}", ha="center", va="center",
                        fontsize=7, color="white" if abs(M[i, j]) > 0.55 else "black")
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label("Cliff's δ  (biru: REST unggul · merah: GraphQL unggul)", fontsize=8)
    ax.set_title(title, fontsize=10)
    fig.tight_layout(); fig.savefig(outpath, dpi=150, bbox_inches="tight"); plt.close(fig)
    stats[outpath.stem] = {"rowlabels": rowlabels, "rates": rates, "delta": np.where(np.isnan(M), None, M).tolist()}


# ---------- mechanism: round trips ----------
def mot_roundtrip(df, outpath, stats):
    sub = df[(df["metric"] == "round_trip_count") & (df["rate_label"] == "r40")].copy()
    order = ["M1·low", "M2·low", "M3·low", "M4·low", "M5·w2", "M5·w8", "M5·w23",
             "M6·k1", "M6·k5", "M6·k10"]
    sub["key"] = sub["scenario"] + "·" + sub["tier"]
    sub = sub.set_index("key").reindex(order)
    x = np.arange(len(order)); w = 0.38
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.bar(x - w / 2, sub["rest_median"], w, color=REST_C, label="REST")
    ax.bar(x + w / 2, sub["graphql_median"], w, color=GQL_C, label="GraphQL")
    ax.set_xticks(x); ax.set_xticklabels(order, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Median round-trip per operasi"); ax.legend(frameon=False)
    ax.set_title("Mekanisme: jumlah round-trip REST vs GraphQL (r40)")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(outpath, dpi=150, bbox_inches="tight"); plt.close(fig)
    stats[outpath.stem] = {"order": order, "rest": sub["rest_median"].tolist(), "graphql": sub["graphql_median"].tolist()}


# ---------- over-fetching test ----------
def mot_overfetch(df, outpath, stats):
    sub = df[(df["metric"] == "payload_bytes_med") & df["scenario"].isin(["M1", "M2", "M3", "M4"]) & (df["rate_label"] == "r40")].copy()
    sub["key"] = sub["scenario"] + "·" + sub["tier"]
    sub = sub.sort_values(["scenario", "tier"])
    sub["ratio"] = sub["graphql_median"] / sub["rest_median"]
    x = np.arange(len(sub))
    fig, ax = plt.subplots(figsize=(10, 3.6))
    ax.bar(x, sub["ratio"], color="#7f7f7f")
    ax.axhline(1.0, color="black", linewidth=1, linestyle="--")
    ax.set_xticks(x); ax.set_xticklabels(sub["key"], rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("Rasio payload GraphQL / REST")
    ax.set_ylim(0.9, max(1.15, sub["ratio"].max() * 1.05))
    ax.set_title("Uji over-fetching: payload GraphQL relatif REST (M1–M4, r40) — garis=paritas")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(outpath, dpi=150, bbox_inches="tight"); plt.close(fig)
    stats[outpath.stem] = {"key": sub["key"].tolist(), "ratio": sub["ratio"].round(3).tolist(),
                           "median_ratio": round(float(sub["ratio"].median()), 3)}


# ---------- throughput is not a discriminating metric ----------
def mot_decoupling(df, outpath, stats):
    # Bandingkan HANYA sel dengan round_trip_count sama antar protokol (apple-to-apple
    # throughput): M1-M4 dan M6-k1. M5 (REST=2,GQL=1) & M6-k5/k10 (REST=K) dikecualikan
    # karena throughput_rps mereka menghitung sub-request REST, bukan operasi setara.
    rt = df[df["metric"] == "round_trip_count"].set_index(["scenario", "tier", "rate_label"])
    comparable = rt[(rt["rest_median"] == rt["graphql_median"])].index
    lat = df[df["metric"] == "lat_p50"].set_index(["scenario", "tier", "rate_label"])
    thr = df[df["metric"] == "throughput_rps"].set_index(["scenario", "tier", "rate_label"])
    idx = lat.index.intersection(thr.index).intersection(comparable)
    latd = lat.reindex(idx)["cliffs_delta"].values
    tpct = ((thr.reindex(idx)["graphql_median"] - thr.reindex(idx)["rest_median"]) /
            thr.reindex(idx)["rest_median"] * 100).values
    is_ovl = np.array([k[2] == "r120_overload" for k in idx])
    fig, ax = plt.subplots(figsize=(5.6, 5))
    ax.axhline(0, color="gray", lw=0.8); ax.axvline(0, color="gray", lw=0.8)
    ax.scatter(latd[~is_ovl], tpct[~is_ovl], alpha=0.6, color="#2ca02c",
               edgecolor="k", linewidth=0.3, label="sub-saturasi (r40/r80)")
    ax.scatter(latd[is_ovl], tpct[is_ovl], alpha=0.75, color="#ff7f0e",
               edgecolor="k", linewidth=0.3, label="overload (r120)")
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    ax.set_xlabel("Cliff's δ  waktu respons p50  (−1 = REST unggul penuh)")
    ax.set_ylabel("Selisih throughput GraphQL−REST (%)")
    ax.set_xlim(-1.1, 1.1)
    lim = max(0.1, np.nanmax(np.abs(tpct)) * 1.3)
    ax.set_ylim(-lim, lim)
    ax.set_title("Throughput bukan metrik pembeda: latensi terpisah\n"
                 "penuh, throughput setara (sel round-trip sebanding)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout(); fig.savefig(outpath, dpi=150, bbox_inches="tight"); plt.close(fig)
    stats[outpath.stem] = {"n_comparable_cells": len(idx),
                           "throughput_pct_diff_min": round(float(np.nanmin(tpct)), 4),
                           "throughput_pct_diff_max": round(float(np.nanmax(tpct)), 4),
                           "note": "hanya sel round_trip_count REST==GraphQL (M1-M4, M6-k1)"}


# ---------- caching main effect ----------
def cache_maineffect(df, outpath, stats):
    factors = [("caching", ["off", "on"], "Caching"),
               ("access_pattern", ["uniform", "unique", "zipfian"], "Pola akses"),
               ("payload_weight", ["light", "heavy"], "Bobot payload")]
    metrics = [("lat_p50", "Median waktu respons p50 (ms)"),
               ("cache_hit_rate", "Median cache hit rate")]
    fig, axes = plt.subplots(2, 3, figsize=(12, 6.5))
    rec = {}
    for row, (metric, ylabel) in enumerate(metrics):
        sub = df[df["metric"] == metric]
        for col, (fcol, order, flabel) in enumerate(factors):
            ax = axes[row][col]
            r_med = sub.groupby(fcol)["rest_median"].median().reindex(order)
            g_med = sub.groupby(fcol)["graphql_median"].median().reindex(order)
            x = np.arange(len(order))
            ax.plot(x, r_med.values, color=REST_C, label="REST", **PROTO_KW)
            ax.plot(x, g_med.values, color=GQL_C, label="GraphQL", **PROTO_KW)
            ax.set_xticks(x); ax.set_xticklabels(order); ax.grid(True, alpha=0.3)
            if row == 1: ax.set_xlabel(flabel)
            if col == 0: ax.set_ylabel(ylabel)
            if row == 0 and col == 0: ax.legend(frameon=False)
            rec[f"{metric}|{fcol}"] = {"levels": order, "rest": r_med.round(3).tolist(), "graphql": g_med.round(3).tolist()}
    fig.suptitle("Efek marginal faktor caching terhadap latensi & cache hit rate", y=1.0)
    fig.tight_layout(); fig.savefig(outpath, dpi=150, bbox_inches="tight"); plt.close(fig)
    stats[outpath.stem] = rec


def cache_delta_heatmap(df, outpath, stats):
    metrics = ["lat_p50", "lat_p95", "lat_p99", "throughput_rps", "payload_bytes_med", "cache_hit_rate"]
    combos = df[["caching", "access_pattern", "payload_weight"]].drop_duplicates()
    combos = combos.sort_values(["caching", "access_pattern", "payload_weight"])
    rowlabels, rows = [], []
    for _, c in combos.iterrows():
        rowlabels.append(f"{c.caching}·{c.access_pattern}·{c.payload_weight}")
        vals = []
        for m in metrics:
            cell = df[(df["metric"] == m) & (df["caching"] == c.caching) &
                      (df["access_pattern"] == c.access_pattern) & (df["payload_weight"] == c.payload_weight)]
            vals.append(cell["cliffs_delta"].iloc[0] if len(cell) else np.nan)
        rows.append(vals)
    M = np.array(rows, float)
    fig, ax = plt.subplots(figsize=(7.5, 0.42 * len(rowlabels) + 1.4))
    im = ax.imshow(M, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(len(metrics))); ax.set_xticklabels(metrics, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(range(len(rowlabels))); ax.set_yticklabels(rowlabels, fontsize=8)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            if not np.isnan(M[i, j]):
                ax.text(j, i, f"{M[i,j]:+.2f}", ha="center", va="center",
                        fontsize=7, color="white" if abs(M[i, j]) > 0.55 else "black")
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label("Cliff's δ (biru: REST unggul · merah: GraphQL unggul)", fontsize=8)
    ax.set_title("Peta pemenang grid caching (signed δ per metrik)", fontsize=10)
    fig.tight_layout(); fig.savefig(outpath, dpi=150, bbox_inches="tight"); plt.close(fig)
    stats[outpath.stem] = {"rowlabels": rowlabels, "metrics": metrics,
                           "delta": np.where(np.isnan(M), None, M).tolist()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mot", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()
    out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    stats = {}
    mot = load_mot(a.mot)
    cache = load_mot(a.cache)

    mot_maineffect(mot, "lat_p50", "median waktu respons p50 (ms)", out / "fx_mot_maineffect_lat_p50.png", stats)
    mot_maineffect(mot, "lat_p95", "median waktu respons p95 (ms)", out / "fx_mot_maineffect_lat_p95.png", stats)

    tier_map = {s: ["low", "medium", "high"] for s in ["M1", "M2", "M3", "M4"]}
    tier_map.update({"M5": ["w2", "w8", "w23"], "M6": ["k1", "k5", "k10"]})
    delta_heatmap(mot, "lat_p50", ["M1", "M2", "M3", "M4"], tier_map,
                  out / "fx_mot_delta_heatmap_rt.png",
                  "Peta pemenang — waktu respons p50 (M1–M4, round-trip)", stats)
    delta_heatmap(mot, "page_latency_med", ["M5", "M6"], tier_map,
                  out / "fx_mot_delta_heatmap_page.png",
                  "Peta pemenang — page latency (M5–M6)", stats)

    mot_roundtrip(mot, out / "fx_mot_mechanism_roundtrip.png", stats)
    mot_overfetch(mot, out / "fx_mot_overfetch.png", stats)
    mot_decoupling(mot, out / "fx_mot_decoupling.png", stats)

    cache_maineffect(cache, out / "fx_cache_maineffect.png", stats)
    cache_delta_heatmap(cache, out / "fx_cache_delta_heatmap.png", stats)

    (out / "effects_stats.json").write_text(json.dumps(stats, indent=2))
    print("wrote", len(stats), "figures to", out)


if __name__ == "__main__":
    main()
