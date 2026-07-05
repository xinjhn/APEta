#!/usr/bin/env python3
"""
rq3_caching_figures.py — figur RQ3 (efek caching) dari results.csv
phase2-core-real (data LENGKAP, 720 run, 12 cell serial penuh).

Menghasilkan (PNG + SVG + sidecar statistik JSON):
  fig_21_rq3_cache_hit_rate      — cache_hit_rate per pola akses × payload,
                                   REST vs GraphQL (caching=on)
  fig_22_rq3_latency_delta       — Δ median lat_p50 (caching on − off) per
                                   pola akses × payload, REST vs GraphQL,
                                   dengan CI bootstrap 95% selisih median

Konvensi (mengikuti keputusan desain studi):
  * TIDAK menggabungkan payload_weight light/heavy pada satu batang
    (pelajaran mis-scoped boxplot — bentuk request berbeda tidak dipool).
  * n per cell dinyatakan pada anotasi figur.
  * matplotlib polos: satu Axes per figur, tanpa seaborn, tanpa warna
    eksplisit (protokol memakai siklus warna default; payload dibedakan
    hatch sebagai encoding sekunder).
  * CPU/RSS TIDAK pernah diplot dari sesi ini (kolom invalid).

Pakai:
  venv/bin/python rq3_caching_figures.py \
      --input  .../phase2-core-real/results.csv \
      --outdir .../laporan/figures/export
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

PATTERNS = ["zipfian", "uniform", "unique"]  # urutan: dari hit-rate tertinggi
PROTOCOLS = ["rest", "graphql"]
PAYLOADS = ["light", "heavy"]
PROTO_LABEL = {"rest": "REST", "graphql": "GraphQL"}
PAYLOAD_LABEL = {"light": "ringan", "heavy": "berat"}
SEED = 42
N_BOOT = 2000


def bootstrap_median_diff_ci(x: np.ndarray, y: np.ndarray,
                             n_boot: int = N_BOOT, seed: int = SEED) -> tuple:
    """CI persentil 95% untuk (median(x) - median(y))."""
    rng = np.random.default_rng(seed)
    diffs = np.empty(n_boot)
    for i in range(n_boot):
        diffs[i] = (np.median(rng.choice(x, len(x), replace=True))
                    - np.median(rng.choice(y, len(y), replace=True)))
    return float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))


def load(input_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(input_csv)
    required = {"protocol", "caching", "access_pattern", "payload_weight",
                "cache_hit_rate", "lat_p50"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"Kolom wajib tidak ada di {input_csv}: {sorted(missing)}")
    return df


def bar_positions() -> tuple:
    """12 batang: 3 grup pola akses × (2 protokol × 2 payload)."""
    group_w, bar_w, gap = 1.0, 0.19, 0.03
    xs, metas = [], []
    for gi, pat in enumerate(PATTERNS):
        for bi, (proto, pay) in enumerate(
            [(pr, pa) for pr in PROTOCOLS for pa in PAYLOADS]
        ):
            xs.append(gi * group_w + (bi - 1.5) * (bar_w + gap))
            metas.append((pat, proto, pay))
    return np.array(xs), metas, bar_w


def style_axes(ax) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", linewidth=0.4, alpha=0.4)
    ax.set_axisbelow(True)


def fig21_hit_rate(df: pd.DataFrame, outdir: Path) -> dict:
    on = df[df.caching == "on"]
    xs, metas, bw = bar_positions()
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    stats = {}
    seen_labels = set()
    for x, (pat, proto, pay) in zip(xs, metas):
        cell = on[(on.access_pattern == pat) & (on.protocol == proto)
                  & (on.payload_weight == pay)].cache_hit_rate.to_numpy()
        med = float(np.median(cell))
        q1, q3 = np.percentile(cell, [25, 75])
        # protokol -> siklus warna default (REST=C0, GraphQL=C1);
        # payload -> hatch (encoding sekunder, aman CVD/cetak)
        color = f"C{PROTOCOLS.index(proto)}"
        label = f"{PROTO_LABEL[proto]} — payload {PAYLOAD_LABEL[pay]}"
        ax.bar(x, med, width=bw, color=color,
               hatch="//" if pay == "light" else None,
               edgecolor="white", linewidth=0.6,
               label=label if label not in seen_labels else None)
        seen_labels.add(label)
        ax.errorbar(x, med, yerr=[[med - q1], [q3 - med]],
                    fmt="none", ecolor="0.25", capsize=2.5, linewidth=1)
        if med >= 0.005:
            ax.annotate(f"{med:.2f}", (x, q3), textcoords="offset points",
                        xytext=(0, 4), ha="center", fontsize=8)
        else:
            ax.annotate("0.00", (x, 0), textcoords="offset points",
                        xytext=(0, 4), ha="center", fontsize=8, color="0.35")
        stats[f"{pat}|{proto}|{pay}"] = {
            "n": int(len(cell)), "median": round(med, 4),
            "q1": round(float(q1), 4), "q3": round(float(q3), 4),
        }
    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels([p.capitalize() for p in PATTERNS])
    ax.set_xlabel("Pola akses")
    ax.set_ylabel("Tingkat cache hit (proporsi request)")
    ax.set_ylim(0, 0.55)
    style_axes(ax)
    ax.legend(frameon=False, fontsize=8, ncol=2, loc="upper right")
    ax.set_title("Tingkat cache hit per pola akses — caching aktif (Varnish)\n"
                 "median 30 run per cell; whisker = IQR", fontsize=10)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(outdir / f"fig_21_rq3_cache_hit_rate.{ext}", dpi=200)
    plt.close(fig)
    return stats


def fig22_latency_delta(df: pd.DataFrame, outdir: Path) -> dict:
    xs, metas, bw = bar_positions()
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    stats = {}
    seen_labels = set()
    for x, (pat, proto, pay) in zip(xs, metas):
        sel = (df.access_pattern == pat) & (df.protocol == proto) & (df.payload_weight == pay)
        on = df[sel & (df.caching == "on")].lat_p50.to_numpy()
        off = df[sel & (df.caching == "off")].lat_p50.to_numpy()
        delta = float(np.median(on) - np.median(off))
        lo, hi = bootstrap_median_diff_ci(on, off)
        color = f"C{PROTOCOLS.index(proto)}"
        label = f"{PROTO_LABEL[proto]} — payload {PAYLOAD_LABEL[pay]}"
        ax.bar(x, delta, width=bw, color=color,
               hatch="//" if pay == "light" else None,
               edgecolor="white", linewidth=0.6,
               label=label if label not in seen_labels else None)
        seen_labels.add(label)
        ax.errorbar(x, delta, yerr=[[delta - lo], [hi - delta]],
                    fmt="none", ecolor="0.25", capsize=2.5, linewidth=1)
        va, off_pt = ("bottom", 3) if delta >= 0 else ("top", -3)
        ax.annotate(f"{delta:+.1f}", (x, delta), textcoords="offset points",
                    xytext=(0, off_pt + (10 if delta >= 0 else -10)),
                    ha="center", va=va, fontsize=8)
        stats[f"{pat}|{proto}|{pay}"] = {
            "n_on": int(len(on)), "n_off": int(len(off)),
            "median_on_ms": round(float(np.median(on)), 3),
            "median_off_ms": round(float(np.median(off)), 3),
            "delta_ms": round(delta, 3),
            "ci95": [round(lo, 3), round(hi, 3)],
        }
    ax.axhline(0, color="0.2", linewidth=0.8)
    lo_all = min(v["ci95"][0] for v in stats.values())
    hi_all = max(v["ci95"][1] for v in stats.values())
    ax.set_ylim(lo_all - 0.6, hi_all + 0.5)
    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels([p.capitalize() for p in PATTERNS])
    ax.set_xlabel("Pola akses")
    ax.set_ylabel("Δ median waktu respons p50 (ms)\ncaching aktif − caching nonaktif")
    style_axes(ax)
    ax.legend(frameon=False, fontsize=8, ncol=1, loc="upper left")
    ax.set_title("Efek caching terhadap waktu respons per pola akses\n"
                 "negatif = caching mempercepat; n = 30 run per kondisi per cell; "
                 "whisker = CI bootstrap 95% selisih median", fontsize=10)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(outdir / f"fig_22_rq3_latency_delta.{ext}", dpi=200)
    plt.close(fig)
    return stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--outdir", required=True, type=Path)
    args = ap.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    df = load(args.input)
    sidecar = {
        "source_csv": str(args.input),
        "n_rows": int(len(df)),
        "fig_21_cache_hit_rate": fig21_hit_rate(df, args.outdir),
        "fig_22_latency_delta": fig22_latency_delta(df, args.outdir),
        "notes": "CPU/RSS sengaja tidak diplot (kolom invalid di phase2-core-real).",
    }
    sidecar_path = args.outdir / "rq3_caching_figures_stats.json"
    sidecar_path.write_text(json.dumps(sidecar, indent=2))
    print(f"OK: fig_21 + fig_22 (PNG+SVG) dan {sidecar_path.name} ditulis ke {args.outdir}")


if __name__ == "__main__":
    main()
