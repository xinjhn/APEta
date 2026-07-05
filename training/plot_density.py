"""
plot_density.py
===============
Visualisasi distribusi densitas output deteksi (untuk lampiran laporan &
"plot densitas" yang disebut pada panduan).

Membaca 'density_counts.csv' (keluaran infer_profile.py) dan menghasilkan:
  1. density_distribution.png : histogram jumlah deteksi/citra + garis Q1/Median/Q3
                                + pewarnaan per tier, disandingkan dengan boxplot ringkas.
  2. density_tier_counts.png  : bar jumlah citra per tier (Rendah/Sedang/Tinggi).

CATATAN BENANG MERAH:
  - Kuartil Q1/Q3 dihitung ulang dari data yang sama (output model best.pt),
    konsisten dengan tier pada Tabel III.1/IV.1.
  - Figur ini menjadi BUKTI VISUAL kriteria penerimaan #2 (distribusi lebar & bervariasi).

Cara pakai (di VM, env yolo_env):
  python plot_density.py --counts density_counts.csv
"""

import csv
import argparse
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")  # headless: VM tanpa display
import matplotlib.pyplot as plt
from matplotlib.patches import Patch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--counts", default="density_counts.csv", help="CSV keluaran infer_profile.py")
    ap.add_argument("--out", default="density_distribution.png", help="nama file figur utama")
    args = ap.parse_args()

    # --- Baca data ---
    counts = []
    with open(args.counts) as f:
        reader = csv.DictReader(f)
        for row in reader:
            counts.append(int(row["num_detections"]))
    counts = np.array(counts)
    if len(counts) == 0:
        raise ValueError("CSV kosong / kolom 'num_detections' tidak ditemukan.")

    q1 = float(np.percentile(counts, 25))
    med = float(np.percentile(counts, 50))
    q3 = float(np.percentile(counts, 75))

    # warna tier (lembut, ramah cetak)
    c_low, c_mid, c_high = "#6BAED6", "#74C476", "#FB6A4A"

    # ======================= FIGUR 1: histogram + boxplot =======================
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), gridspec_kw={"width_ratios": [2.4, 1]})

    # (1a) Histogram
    ax = axes[0]
    step = 5
    bins = np.arange(0, counts.max() + step, step)
    _, edges, patches = ax.hist(counts, bins=bins, edgecolor="white", linewidth=0.5)
    for patch, left in zip(patches, edges[:-1]):
        center = left + step / 2.0
        if center < q1:
            patch.set_facecolor(c_low)
        elif center > q3:
            patch.set_facecolor(c_high)
        else:
            patch.set_facecolor(c_mid)

    ymax = ax.get_ylim()[1]
    for x, lab, col in [(q1, f"Q1 = {q1:.0f}", "#08519C"),
                        (med, f"Median = {med:.0f}", "#000000"),
                        (q3, f"Q3 = {q3:.0f}", "#A50F15")]:
        ax.axvline(x, color=col, linestyle="--", linewidth=1.5)
        ax.text(x, ymax * 0.96, lab, rotation=90, va="top", ha="right", fontsize=9, color=col)

    ax.set_xlabel("Jumlah deteksi per citra")
    ax.set_ylabel("Frekuensi (jumlah citra)")
    ax.set_title(f"Distribusi Densitas Output Deteksi (val resmi, N = {len(counts)})")
    legend = [Patch(facecolor=c_low, label=f"Rendah (< {q1:.0f})"),
              Patch(facecolor=c_mid, label=f"Sedang ({q1:.0f}–{q3:.0f})"),
              Patch(facecolor=c_high, label=f"Tinggi (> {q3:.0f})")]
    ax.legend(handles=legend, title="Tier densitas")

    # (1b) Boxplot ringkas + anotasi statistik
    ax2 = axes[1]
    bp = ax2.boxplot(counts, widths=0.5, patch_artist=True, showfliers=True)
    bp["boxes"][0].set_facecolor("#D9D9D9")
    ax2.set_ylabel("Jumlah deteksi per citra")
    ax2.set_xticks([1])
    ax2.set_xticklabels(["Semua citra"])
    ax2.set_title("Ringkasan (boxplot)")
    stats = (f"Min {int(counts.min())}  |  Max {int(counts.max())}\n"
             f"Q1 {q1:.0f}  |  Med {med:.0f}  |  Q3 {q3:.0f}\n"
             f"Mean {counts.mean():.1f}  |  Std {counts.std():.1f}")
    ax2.text(1.0, counts.max() * 0.98, stats, fontsize=8, va="top", ha="center",
             bbox=dict(boxstyle="round", fc="white", ec="0.7"))

    fig.tight_layout()
    fig.savefig(args.out, dpi=200, bbox_inches="tight")
    print(f"[ok] Figur utama tersimpan: {args.out}")

    # ======================= FIGUR 2: bar jumlah citra per tier =======================
    n_low = int((counts < q1).sum())
    n_mid = int(((counts >= q1) & (counts <= q3)).sum())
    n_high = int((counts > q3).sum())

    fig2, axb = plt.subplots(figsize=(5, 4))
    bars = axb.bar(["Rendah", "Sedang", "Tinggi"], [n_low, n_mid, n_high],
                   color=[c_low, c_mid, c_high], edgecolor="white")
    for rect, v in zip(bars, [n_low, n_mid, n_high]):
        axb.text(rect.get_x() + rect.get_width() / 2, v + max(counts) * 0.005 + 1,
                 str(v), ha="center", fontsize=10)
    axb.set_ylabel("Jumlah citra")
    axb.set_title("Komposisi Citra per Tier Densitas")
    fig2.tight_layout()
    out2 = str(Path(args.out).with_name("density_tier_counts.png"))
    fig2.savefig(out2, dpi=200, bbox_inches="tight")
    print(f"[ok] Figur tier tersimpan: {out2}")

    print(f"\nRingkasan: Q1={q1:.0f}, Q3={q3:.0f} | "
          f"Rendah={n_low}, Sedang={n_mid}, Tinggi={n_high}")


if __name__ == "__main__":
    main()
