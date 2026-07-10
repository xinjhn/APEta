"""
analysis/plots.py
=================
Visualisasi hasil eksperimen. SETIAP figur dipetakan ke satu temuan/pertanyaan,
dan jenis plotnya dipilih berdasarkan rekomendasi literatur (bukan estetika):

- Box/violin (distribusi, bukan bar chart untuk data kontinu)
    -> Weissgerber et al. (2015), PLoS Biology; ditegaskan ulang oleh praktik
       effect-size visualization terkini (Ho et al. 2019, Nature Methods;
       Durga, J. Evol. Biol. 2024).
- ECDF latensi (fokus EKOR p95/p99)
    -> Dean & Barroso (2013), "The Tail at Scale".
- Heatmap Cliff's delta (lanskap effect size, bukan sekadar p-value)
    -> filosofi estimation graphics (Ho et al. 2019).
- Plot tren/moderation (median lintas faktor terurut, garis per protokol)
    -> visualisasi langsung uji tren Jonckheere-Terpstra (1954).
- Payload per pola (over-fetching)
    -> Brito et al. (2019).

Pakai:
    python analysis/plots.py --results results/results.csv --out results/analysis/figures
"""
from __future__ import annotations

import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from stats_core import cliffs_delta

sns.set_theme(style="whitegrid", context="talk")
DENSITY_ORDER = ["low", "medium", "high"]
PROTO_ORDER = ["rest", "graphql"]
PALETTE = {"rest": "#2c7fb8", "graphql": "#d95f0e"}
LOWER_BETTER = {"lat_p95", "lat_p50", "lat_p99", "payload_bytes_med",
                "xproc_p95", "xproc_med", "cpu_mean", "rss_mean_mb"}


def _clean(df):
    for c in ("lat_p50", "lat_p95", "lat_p99", "throughput_rps",
              "payload_bytes_med", "xproc_p95", "xproc_med", "cpu_mean",
              "rss_mean_mb", "concurrency"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["density"] = pd.Categorical(df["density"], DENSITY_ORDER, ordered=True)
    return df


# 1) Distribusi REST vs GraphQL (box) -- Weissgerber et al. (2015) ---------------
def fig_distribution(df, metric, out, concurrency=None):
    conc = concurrency or int(df["concurrency"].max())  # default: stress load
    sub = df[df["concurrency"] == conc]
    g = sns.catplot(
        data=sub, x="density", y=metric, hue="protocol", col="pattern",
        order=DENSITY_ORDER, hue_order=PROTO_ORDER, palette=PALETTE,
        kind="box", col_wrap=2, height=3.6, aspect=1.25, fliersize=2,
    )
    g.set_titles("{col_name}")
    g.figure.suptitle(
        f"Distribusi {metric} REST vs GraphQL per pola (konkurensi={conc} VUs)\n"
        f"box plot menampilkan distribusi penuh (Weissgerber et al., 2015)",
        y=1.04, fontsize=13)
    p = f"{out}/fig_dist_{metric}.png"
    g.savefig(p, dpi=130, bbox_inches="tight"); plt.close(g.figure)
    return p


# 2) ECDF latensi (fokus ekor) -- Dean & Barroso (2013) -------------------------
def fig_ecdf_latency(df, out, metric="lat_p95"):
    conc = int(df["concurrency"].max())
    sub = df[(df.pattern == "baseline") & (df.density == "high") & (df.concurrency == conc)]
    fig, ax = plt.subplots(figsize=(7, 5))
    for proto in PROTO_ORDER:
        vals = np.sort(sub[sub.protocol == proto][metric].dropna().values)
        if len(vals):
            ax.step(vals, np.arange(1, len(vals) + 1) / len(vals), where="post",
                    label=proto, color=PALETTE[proto], lw=2.2)
    ax.set(xlabel=f"{metric} (ms)", ylabel="ECDF",
           title=f"ECDF {metric} — baseline/high/{conc}VUs\n"
                 f"fokus ekor latensi (Dean & Barroso, 2013)")
    ax.legend(title="protokol")
    p = f"{out}/fig_ecdf_latency.png"
    fig.savefig(p, dpi=130, bbox_inches="tight"); plt.close(fig)
    return p


# 3) Moderation: median metric vs faktor terurut, garis per protokol ------------
def fig_moderation(df, metric, factor, out):
    if factor == "density":
        order, hold, hold_val = DENSITY_ORDER, "concurrency", int(df["concurrency"].max())
        sub = df[df[hold] == hold_val]
        xlab = f"densitas (konkurensi={hold_val} VUs)"
    else:
        order = sorted(df["concurrency"].dropna().unique())
        hold, hold_val = "density", "high"
        sub = df[df[hold] == hold_val]
        xlab = "konkurensi (VUs, densitas=high)"
    g = sns.relplot(
        data=sub, x=factor, y=metric, hue="protocol", col="pattern",
        hue_order=PROTO_ORDER, palette=PALETTE, kind="line",
        estimator="median", errorbar=("pi", 50),  # pita IQR
        col_wrap=2, height=3.6, aspect=1.25, marker="o",
    )
    if factor == "density":
        for ax in g.axes.flat:
            ax.set_xticks(range(len(order))); ax.set_xticklabels(order)
    g.set_titles("{col_name}")
    g.set_axis_labels(xlab, f"median {metric}")
    g.figure.suptitle(
        f"Tren {metric}: REST vs GraphQL lintas {factor}\n"
        f"visualisasi tren Jonckheere-Terpstra; lebar gap = moderation",
        y=1.04, fontsize=13)
    p = f"{out}/fig_moderation_{metric}_{factor}.png"
    g.savefig(p, dpi=130, bbox_inches="tight"); plt.close(g.figure)
    return p


# 4) Heatmap Cliff's delta (lanskap effect size) -- Ho et al. (2019) ------------
def fig_cliffs_heatmap(df, metric, out):
    concs = sorted(df["concurrency"].dropna().unique())
    patterns = list(df["pattern"].unique())
    rows, idx = [], []
    for pat in patterns:
        for dens in DENSITY_ORDER:
            idx.append(f"{pat}\n{dens}")
            row = []
            for c in concs:
                cell = df[(df.pattern == pat) & (df.density == dens) & (df.concurrency == c)]
                r = cell[cell.protocol == "rest"][metric].dropna().values
                q = cell[cell.protocol == "graphql"][metric].dropna().values
                row.append(cliffs_delta(r, q) if len(r) and len(q) else np.nan)
            rows.append(row)
    M = pd.DataFrame(rows, index=idx, columns=[f"{c}VUs" for c in concs])
    fig, ax = plt.subplots(figsize=(1.6 + 1.2 * len(concs), 0.5 * len(idx) + 1.5))
    sns.heatmap(M, annot=True, fmt=".2f", cmap="RdBu_r", center=0, vmin=-1, vmax=1,
                linewidths=.5, cbar_kws={"label": "Cliff's δ (REST−GraphQL)"}, ax=ax)
    direction = "δ<0: REST lebih kecil" if metric in LOWER_BETTER else "δ>0: REST lebih tinggi"
    ax.set_title(f"Effect size Cliff's δ — {metric}\n{direction} (|δ|: 0.15 kecil / 0.33 sedang / 0.47 besar, Romano et al. 2006)",
                 fontsize=12)
    p = f"{out}/fig_cliffs_{metric}.png"
    fig.savefig(p, dpi=130, bbox_inches="tight"); plt.close(fig)
    return p


# 5) Over-fetching: payload per pola -- Brito et al. (2019) ----------------------
def fig_payload_overfetching(df, out):
    sub = df[df.density == "high"]
    order = [p for p in ["baseline", "filtered", "partial", "aggregate"]
             if p in sub.pattern.unique()]
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.boxplot(data=sub, x="pattern", y="payload_bytes_med", hue="protocol",
                order=order, hue_order=PROTO_ORDER, palette=PALETTE, ax=ax, fliersize=2)
    ax.set(xlabel="pola kueri", ylabel="payload (byte, median per-run)",
           title="Over-fetching: ukuran payload per pola (densitas=high)\n"
                 "seleksi field & agregasi menekan payload (Brito et al., 2019)")
    p = f"{out}/fig_payload_overfetching.png"
    fig.savefig(p, dpi=130, bbox_inches="tight"); plt.close(fig)
    return p


# 6) Evolusi gap: Cliff's delta vs faktor terurut -------------------------------
def fig_gap_evolution(df, metric, out):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    for ax, factor in zip(axes, ["density", "concurrency"]):
        if factor == "density":
            order, hold, hv = DENSITY_ORDER, "concurrency", int(df["concurrency"].max())
        else:
            order, hold, hv = sorted(df["concurrency"].dropna().unique()), "density", "high"
        sub = df[df[hold] == hv]
        for pat in df["pattern"].unique():
            deltas = []
            for lvl in order:
                cell = sub[(sub.pattern == pat) & (sub[factor] == lvl)]
                r = cell[cell.protocol == "rest"][metric].dropna().values
                q = cell[cell.protocol == "graphql"][metric].dropna().values
                deltas.append(cliffs_delta(r, q) if len(r) and len(q) else np.nan)
            ax.plot(range(len(order)), deltas, marker="o", lw=2, label=pat)
        ax.axhline(0, color="grey", ls="--", lw=1)
        ax.set_xticks(range(len(order))); ax.set_xticklabels([str(o) for o in order])
        ax.set(xlabel=factor, ylabel="Cliff's δ (REST−GraphQL)", ylim=(-1.05, 1.05))
        ax.set_title(f"vs {factor} ({hold}={hv})")
        ax.legend(title="pola", fontsize=9)
    fig.suptitle(f"Evolusi gap (effect size) {metric}: apakah keunggulan membesar/mengecil?",
                 y=1.02, fontsize=13)
    p = f"{out}/fig_gap_{metric}.png"
    fig.savefig(p, dpi=130, bbox_inches="tight"); plt.close(fig)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", default="results/analysis/figures")
    args = ap.parse_args()
    df = _clean(pd.read_csv(args.results))
    os.makedirs(args.out, exist_ok=True)

    made = []
    made.append(fig_distribution(df, "lat_p95", args.out))
    made.append(fig_ecdf_latency(df, args.out))
    made.append(fig_moderation(df, "lat_p95", "density", args.out))
    made.append(fig_moderation(df, "lat_p95", "concurrency", args.out))
    made.append(fig_cliffs_heatmap(df, "lat_p95", args.out))
    if "throughput_rps" in df.columns:
        made.append(fig_cliffs_heatmap(df, "throughput_rps", args.out))
    if "payload_bytes_med" in df.columns:
        made.append(fig_payload_overfetching(df, args.out))
    made.append(fig_gap_evolution(df, "lat_p95", args.out))

    print(f"{len(made)} figur dibuat di {args.out}/:")
    for p in made:
        print("  -", os.path.basename(p))


if __name__ == "__main__":
    main()
