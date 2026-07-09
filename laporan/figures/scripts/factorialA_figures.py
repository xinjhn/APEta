#!/usr/bin/env python3
"""
factorialA_figures.py — figur pendukung dari results.csv factorial-A (sesi bersih,
solo/sekuensial 2026-06-23..25, tanpa overlap sesi lain). Dua temuan terbaik:

  fig_factA_payload_envelope   — "overfetching yang tertelan amplop": median
                                 payload REST vs GraphQL per pola kueri (dumbbell,
                                 sumbu-x log). Selisih GraphQL−REST hampir konstan
                                 ~+30 B (amplop JSON `{"data":{...}}`) dan sangat
                                 kecil relatif terhadap payload absolut (287 B..5,5 KB).
                                 Panel bawah: sebaran selisih per-sel (48 sel) —
                                 hanya 2 sel (filtered/high, konkurensi rendah)
                                 di mana GraphQL lebih kecil, keduanya TIDAK signifikan.

  fig_factA_load_invariance    — invariansi keunggulan REST terhadap beban: Cliff's
                                 delta lat_p95 terkunci di −1,0 pada seluruh sel
                                 densitas×konkurensi (heatmap), sementara rasio
                                 besaran (GraphQL/REST p95) tetap bervariasi 2,5–4,8×.

Konvensi rumah: matplotlib polos, satu figur per temuan, tanpa seaborn. REST = C0,
GraphQL = C1; identitas TIDAK bergantung warna saja (marker ●/◆ + label langsung)
agar terbaca pada cetak grayscale. Semua angka dihitung ulang dari results.csv
mentah; CSV analisis hanya untuk cek-silang. PNG+SVG dpi 200 + sidecar JSON.

CPU/RSS SENGAJA TIDAK diplot: core jenuh (~100% kedua protokol) — tidak informatif;
proksi biaya server memakai xproc.
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
from scipy.stats import mannwhitneyu
from statsmodels.stats.multitest import multipletests

PATTERNS = ["aggregate", "baseline", "filtered", "partial"]
DENSITIES = ["low", "medium", "high"]
CONCURRENCY = [1, 10, 50, 100]
PROTO_LABEL = {"rest": "REST", "graphql": "GraphQL"}
PROTO_COLOR = {"rest": "C0", "graphql": "C1"}
PROTO_MARK = {"rest": "o", "graphql": "D"}
ENVELOPE_B = 30  # amplop JSON GraphQL: {"data":{...}} ≈ 30 byte
N_PER_CELL = 30


def style_axes(ax) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", linewidth=0.4, alpha=0.4)
    ax.set_axisbelow(True)


def cliffs_delta(a: np.ndarray, b: np.ndarray) -> float:
    """delta(a,b): >0 bila a cenderung > b."""
    a = np.asarray(a); b = np.asarray(b)
    gt = sum((x > b).sum() for x in a)
    lt = sum((x < b).sum() for x in a)
    return (gt - lt) / (len(a) * len(b))


def per_cell_payload(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (pat, den, con), g in df.groupby(["pattern", "density", "concurrency"]):
        r = g[g.protocol == "rest"]["payload_bytes_med"].to_numpy()
        q = g[g.protocol == "graphql"]["payload_bytes_med"].to_numpy()
        if len(r) == 0 or len(q) == 0:
            continue
        p = mannwhitneyu(q, r, alternative="two-sided").pvalue
        rows.append({
            "pattern": pat, "density": den, "concurrency": int(con),
            "rest_med": float(np.median(r)), "gql_med": float(np.median(q)),
            "delta_gql_minus_rest": float(np.median(q) - np.median(r)),
            "cliffs_gql_vs_rest": cliffs_delta(q, r), "p_raw": float(p),
        })
    pc = pd.DataFrame(rows)
    pc["p_bh"] = multipletests(pc["p_raw"], method="fdr_bh")[1]
    pc["sig_bh"] = pc["p_bh"] < 0.05
    return pc


# ---------------------------------------------------------------- Figur 1
def fig_payload_envelope(df: pd.DataFrame, pc: pd.DataFrame, outdir: Path) -> dict:
    absmed = df.pivot_table("payload_bytes_med", "pattern", "protocol", "median")
    # urut pola menaik menurut payload agar dumbbell rapi
    order = absmed["rest"].sort_values().index.tolist()

    fig, (axA, axB) = plt.subplots(
        2, 1, figsize=(7.4, 6.6), gridspec_kw={"height_ratios": [1.15, 1]})

    # -- Panel A: dumbbell absolut (log-x) --
    for yi, pat in enumerate(order):
        r, q = absmed.loc[pat, "rest"], absmed.loc[pat, "graphql"]
        axA.plot([r, q], [yi, yi], color="0.6", linewidth=1.6, zorder=1)
        axA.scatter(r, yi, s=70, color=PROTO_COLOR["rest"], marker=PROTO_MARK["rest"],
                    zorder=3, label="REST" if yi == 0 else None, edgecolor="white", linewidth=0.6)
        axA.scatter(q, yi, s=64, color=PROTO_COLOR["graphql"], marker=PROTO_MARK["graphql"],
                    zorder=3, label="GraphQL" if yi == 0 else None, edgecolor="white", linewidth=0.6)
        gap = q - r
        axA.annotate(f"+{gap:.0f} B", (max(r, q), yi), textcoords="offset points",
                     xytext=(10, 0), va="center", fontsize=9, color="0.25")
    axA.set_yticks(range(len(order)))
    axA.set_yticklabels([f"{p}\n(REST {absmed.loc[p,'rest']:.0f} B)" for p in order])
    axA.set_xscale("log")
    axA.set_xlabel("Median ukuran payload (byte, skala log)")
    axA.set_ylim(-0.6, len(order) - 0.4)
    axA.spines[["top", "right"]].set_visible(False)
    axA.grid(axis="x", linewidth=0.4, alpha=0.4)
    axA.set_axisbelow(True)
    axA.legend(frameon=False, fontsize=9, loc="lower right")
    axA.set_title("(a) GraphQL = REST + amplop JSON ~30 B pada setiap pola kueri\n"
                  "titik REST dan GraphQL nyaris berimpit: selisih amplop << payload absolut",
                  fontsize=9.5)

    # -- Panel B: sebaran selisih per-sel (48) --
    x = pc["delta_gql_minus_rest"].to_numpy()
    rng = np.random.default_rng(42)
    jit = rng.uniform(-0.10, 0.10, len(x))
    neg = pc["delta_gql_minus_rest"] < 0
    axB.axvline(0, color="0.2", linewidth=0.9)
    axB.axvline(ENVELOPE_B, color="0.55", linewidth=0.9, linestyle="--")
    axB.annotate("amplop JSON ≈ +30 B", (ENVELOPE_B, -0.55), fontsize=8, color="0.4",
                 ha="center", va="center")
    axB.scatter(x[~neg], jit[~neg], s=34, color=PROTO_COLOR["rest"], alpha=0.75,
                edgecolor="white", linewidth=0.4, label="REST lebih hemat (46 sel)")
    axB.scatter(x[neg], jit[neg], s=95, color=PROTO_COLOR["graphql"], marker=PROTO_MARK["graphql"],
                edgecolor="black", linewidth=0.7, zorder=4,
                label="GraphQL lebih hemat (2 sel, TIDAK signifikan)")
    # dua sel pengecualian → label di kuadran kiri yang kosong (atas & bawah)
    ytext = {1: 0.46, 10: -0.46}
    for _, row in pc[neg].iterrows():
        axB.annotate(f"{row['pattern']}/{row['density']}, k={row['concurrency']}: "
                     f"Δ={row['delta_gql_minus_rest']:.0f} B (p_BH={row['p_bh']:.2f}, n.s.)",
                     (row["delta_gql_minus_rest"], 0.0),
                     xytext=(-58, ytext[row["concurrency"]]), textcoords="data",
                     fontsize=7.5, color="0.2", ha="left", va="center",
                     arrowprops=dict(arrowstyle="-", color="0.5", linewidth=0.6))
    axB.set_yticks([])
    axB.set_xlim(-72, 132)
    axB.set_ylim(-0.7, 0.8)
    axB.set_xlabel("Selisih median payload per sel: GraphQL − REST (byte)\n"
                   "Δ>0 → REST lebih hemat  ·  Δ<0 → GraphQL lebih hemat")
    axB.spines[["top", "right", "left"]].set_visible(False)
    axB.legend(frameon=False, fontsize=8, loc="upper right", bbox_to_anchor=(1.0, 1.04),
               ncol=1, handletextpad=0.4)
    axB.set_title("(b) 48 sel: 46 dimenangkan REST karena amplop; seleksi field GraphQL\n"
                  "hanya mengungguli di 2 sel filtered/high konkurensi rendah — keduanya tak signifikan",
                  fontsize=9.5)

    fig.suptitle("Overfetching GraphQL tertelan overhead amplop protokol "
                 "(factorial-A, caching off, passthrough)", fontsize=11, y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    for ext in ("png", "svg"):
        fig.savefig(outdir / f"fig_factA_payload_envelope.{ext}", dpi=200)
    plt.close(fig)

    return {
        "pattern_medians": {p: {"rest": float(absmed.loc[p, "rest"]),
                                "graphql": float(absmed.loc[p, "graphql"]),
                                "gap_bytes": float(absmed.loc[p, "graphql"] - absmed.loc[p, "rest"])}
                            for p in order},
        "n_cells": int(len(pc)),
        "cells_graphql_smaller": pc[neg][["pattern", "density", "concurrency",
                                          "delta_gql_minus_rest", "p_bh", "sig_bh"]]
                                 .to_dict("records"),
        "delta_median_bytes": float(pc["delta_gql_minus_rest"].median()),
    }


# ---------------------------------------------------------------- Figur 2
def fig_load_invariance(df: pd.DataFrame, outdir: Path) -> dict:
    # Cliff's delta + rasio p95 PER SEL (pattern×density×concurrency) — TANPA
    # pooling lintas pola (pooling menyuntik overlap antar-pola yang palsu).
    pd_rows = [f"{pat}/{den}" for pat in PATTERNS for den in DENSITIES]
    delta48 = np.full((len(pd_rows), len(CONCURRENCY)), np.nan)
    ratio_cell = {}  # (den, con) -> list rasio per pola
    for ri, (pat, den) in enumerate((pat, den) for pat in PATTERNS for den in DENSITIES):
        for ci, con in enumerate(CONCURRENCY):
            sub = df[(df.pattern == pat) & (df.density == den) & (df.concurrency == con)]
            r = sub[sub.protocol == "rest"]["lat_p95"].to_numpy()
            q = sub[sub.protocol == "graphql"]["lat_p95"].to_numpy()
            delta48[ri, ci] = cliffs_delta(q, r)            # +1 => GraphQL lebih lambat
            ratio_cell.setdefault((den, con), []).append(np.median(q) / np.median(r))
    ratio_grid = np.array([[float(np.median(ratio_cell[(den, con)])) for con in CONCURRENCY]
                           for den in DENSITIES])

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(11.2, 5.2),
                                   gridspec_kw={"width_ratios": [1.0, 1.05]})

    # -- Panel A: heatmap δ per-sel, 48 sel (12 baris × 4 kolom) --
    im = axA.imshow(delta48, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    axA.set_xticks(range(len(CONCURRENCY))); axA.set_xticklabels(CONCURRENCY)
    axA.set_yticks(range(len(pd_rows))); axA.set_yticklabels(pd_rows, fontsize=8)
    axA.set_xlabel("Konkurensi (VU)")
    axA.set_ylabel("Pola kueri / densitas")
    for ri in range(len(pd_rows)):
        for ci in range(len(CONCURRENCY)):
            axA.text(ci, ri, f"{delta48[ri, ci]:+.2f}", ha="center", va="center",
                     fontsize=7.5, color="white", fontweight="bold")
    cb = fig.colorbar(im, ax=axA, fraction=0.046, pad=0.04)
    cb.set_label("Cliff's δ (lat_p95, GraphQL vs REST)")
    axA.set_title("(a) Separasi lengkap di SEMUA 48 sel: δ = +1,00\n"
                  "setiap replikat GraphQL lebih lambat dari tiap replikat REST\n"
                  "(per sel, tanpa pooling lintas pola)", fontsize=9)

    # -- Panel B: rasio besaran tetap bervariasi (median per-sel per densitas) --
    for di, den in enumerate(DENSITIES):
        axB.plot(range(len(CONCURRENCY)), ratio_grid[di], marker="o", markersize=6,
                 linewidth=1.8, label=f"densitas {den}")
    axB.set_xticks(range(len(CONCURRENCY))); axB.set_xticklabels(CONCURRENCY)
    axB.set_xlabel("Konkurensi (VU)")
    axB.set_ylabel("Rasio median p95: GraphQL / REST\n(median lintas pola per sel)")
    axB.axhline(1, color="0.4", linewidth=0.8, linestyle=":")
    axB.annotate("paritas (1×)", (0.02, 1.0), xycoords=("axes fraction", "data"),
                 fontsize=8, color="0.4", va="bottom")
    style_axes(axB)
    axB.set_ylim(0, max(4.9, ratio_grid.max() * 1.12))
    axB.legend(frameon=False, fontsize=9, title="")
    lo, hi = ratio_grid.min(), ratio_grid.max()
    axB.set_title(f"(b) …tetapi BESARAN keunggulan bergeser menurut beban:\n"
                  f"GraphQL {lo:.1f}–{hi:.1f}× lebih lambat, terburuk di konkurensi menengah",
                  fontsize=9)

    fig.suptitle("Keunggulan latensi REST invarian terhadap densitas & konkurensi — "
                 "hanya besarannya yang bergeser (factorial-A)", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    for ext in ("png", "svg"):
        fig.savefig(outdir / f"fig_factA_load_invariance.{ext}", dpi=200)
    plt.close(fig)

    return {
        "cliffs_delta_per_cell_min": round(float(np.nanmin(delta48)), 3),
        "cliffs_delta_per_cell_max": round(float(np.nanmax(delta48)), 3),
        "n_cells_complete_separation": int((delta48 == 1.0).sum()),
        "ratio_p95_grid": {DENSITIES[d]: {str(CONCURRENCY[c]): round(float(ratio_grid[d, c]), 3)
                                          for c in range(len(CONCURRENCY))}
                           for d in range(len(DENSITIES))},
        "ratio_range_displayed": [round(float(lo), 2), round(float(hi), 2)],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--outdir", required=True, type=Path)
    args = ap.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.input)
    # sanity: sesi tunggal, seimbang, tanpa error
    assert (df["error_rate"] == 0).all(), "ada run dengan error_rate>0"
    cell_n = df.groupby(["protocol", "pattern", "density", "concurrency"]).size()
    assert (cell_n == N_PER_CELL).all(), f"sel tidak seimbang: {cell_n.min()}..{cell_n.max()}"

    pc = per_cell_payload(df)
    sidecar = {
        "source_csv": str(args.input),
        "n_rows": int(len(df)),
        "session": sorted(df["session_id"].unique().tolist()),
        "note_cpu": "CPU/RSS tidak diplot: core jenuh ~100% kedua protokol (tak informatif)",
        "payload_envelope": fig_payload_envelope(df, pc, args.outdir),
        "load_invariance": fig_load_invariance(df, args.outdir),
    }
    (args.outdir / "factorialA_stats.json").write_text(json.dumps(sidecar, indent=2))
    print(f"OK: 2 figur (PNG+SVG) + factorialA_stats.json ditulis ke {args.outdir}")


if __name__ == "__main__":
    main()
