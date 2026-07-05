"""
tools/analyze_factorial.py
===========================
Analisis statistik untuk desain faktorial 2x2 (Protocol x Type Safety).

KOREKSI METODOLOGIS (audit lanjutan, lihat _review/): versi awal skrip ini
melakukan two-way ANOVA (`metric ~ C(protocol) + C(impl_mode) + interaction`)
dengan SELURUH baris results.csv dipool menjadi satu model -- tanpa
memperhitungkan pattern/density/concurrency sebagai faktor. Itu pseudo-
replikasi: kondisi yang berbeda (mis. baseline@concurrency=100 vs
aggregate@concurrency=1) diperlakukan sebagai ulangan dari kondisi yang sama,
merusak asumsi derajat-kebebasan ANOVA. ANOVA juga mengasumsikan residu
ber-distribusi normal & homoskedastik -- asumsi yang hampir pasti dilanggar
oleh latency (right-skewed akibat queueing), justru alasan awal proyek ini
ingin memakai Mann-Whitney U.

Pendekatan baru (sesuai Arcuri & Briand, "A Practical Guide for Using
Statistical Tests to Assess Randomized Algorithms in Software Engineering",
ICSE 2011): untuk SETIAP sel (pattern, density, concurrency) yang identik,
lakukan:
  1. Mann-Whitney U (Wilcoxon rank-sum) -- non-parametrik, tak berasumsi normal.
  2. Vargha-Delaney A12 / Cliff's delta -- ukuran efek non-parametrik
     (delta = 2*A12 - 1; identik informasinya dgn Cliff's delta yg sudah
     dipakai proyek ini, lihat METHODOLOGICAL_VERIFICATION.md).
  3. Koreksi Holm-Bonferroni LINTAS SEL dalam satu keluarga hipotesis (mis.
     semua sel utk "efek protocol pada lat_p95 saat impl_mode=typed") agar
     false-discovery rate terkendali -- bukan satu p-value tunggal yg dipool.

Dua keluarga hipotesis dianalisis terpisah per metrik:
  A. Efek PROTOCOL (rest vs graphql), pada impl_mode tetap (passthrough, typed)
  B. Efek TYPE SAFETY (passthrough vs typed), pada protocol tetap (rest, graphql)

Efek interaksi (apakah biaya type-safety berbeda antar protokol) TIDAK diuji
formal di sini -- non-parametric ANOVA faktorial penuh butuh Aligned Rank
Transform (Wobbrock et al., CHI 2011; R package ARTool), di luar lingkup
skrip Python ini. Bagian 4 laporan menyajikan estimasi titik (selisih median)
utk interaksi sebagai deskriptif, BUKAN klaim signifikansi.

Prasyarat:
    pip install pandas numpy scipy statsmodels seaborn matplotlib

Cara pakai:
    1. Gabungkan results.csv dari sesi-sesi eksperimental jadi satu file. TIDAK
       perlu skrip combine khusus -- run_experiment.py SUDAH mencatat impl_mode
       yang benar per-baris (lihat fix bug cfg/self.cfg di audit), jadi cukup:
           python -c "import pandas as pd; pd.concat([pd.read_csv(f) for f in
               ['results/sesi-A/results.csv','results/sesi-B/results.csv']],
               ignore_index=True).to_csv('results_combined.csv', index=False)"
       (tools/combine_factorial_results.py DIHAPUS -- skrip itu mengasumsikan
       tiap file hasil HANYA berisi satu protokol, padahal run_experiment.py
       SELALU menjalankan rest+graphql bergantian dalam satu sesi. Memakainya
       akan salah label protocol/impl_mode pada data nyata.)
       CATATAN DESAIN: krn satu sesi sudah memuat KEDUA protokol, 2x2 penuh
       cukup 2 SESI dgn pasangan mode yang saling melengkapi, BUKAN 4 sesi
       per-protokol-tunggal (lihat METHODOLOGICAL_VERIFICATION.md utk koreksi
       rencana sesi). Mis.: Sesi A (rest=passthrough, graphql=passthrough) +
       Sesi B (rest=typed, graphql=typed) -> 4 sel unik, tanpa duplikasi.
    2. Jalankan: python tools/analyze_factorial.py --input results_combined.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import mannwhitneyu, rankdata
from statsmodels.stats.multitest import multipletests

CELL_COLS = ["pattern", "density", "concurrency"]
METRICS = ["lat_p95", "xproc_p95", "throughput_rps", "cpu_mean"]
MIN_N_PER_GROUP = 3  # Mann-Whitney U tak bermakna di bawah ini -- lapor sebagai 'insufficient_n'


def load_and_prepare_data(input_path: Path) -> pd.DataFrame:
    """Memuat dan mempersiapkan data untuk analisis."""
    df = pd.read_csv(input_path)

    required_cols = ["protocol", "impl_mode", "lat_p95", "xproc_p95", "throughput_rps",
                      "cpu_mean", "rss_mean_mb", "payload_bytes_med"] + CELL_COLS
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Kolom yang diperlukan tidak ditemukan: {missing}")

    df = df[df["impl_mode"].notna()].copy()
    if df.empty:
        raise ValueError("Tidak ada data dengan impl_mode terisi. Pastikan Anda menjalankan eksperimen faktorial.")

    print(f"Data loaded: {len(df)} runs")
    print(f"Protocols: {sorted(df['protocol'].unique())}")
    print(f"Implementation modes: {sorted(df['impl_mode'].unique())}")
    print(f"Cells (pattern x density x concurrency): {df.groupby(CELL_COLS).ngroups}")
    print("Conditions breakdown:")
    print(df.groupby(["protocol", "impl_mode"]).size())
    print()
    return df


def vargha_delaney_a12(x: np.ndarray, y: np.ndarray) -> float:
    """A12: P(x diambil acak dari x > y diambil acak dari y) + tie-adjustment.

    Formula rank-sum standar (Vargha & Delaney, 2000); identik dgn implementasi
    `VD.A` pada paket R `effsize` yang umum dirujuk pada studi SE.
    """
    n1, n2 = len(x), len(y)
    ranks = rankdata(np.concatenate([x, y]))
    r1 = ranks[:n1].sum()
    return (r1 / n1 - (n1 + 1) / 2) / n2


def cliffs_delta_magnitude(delta: float) -> str:
    """Ambang Romano et al. (2006), dipakai luas pada laporan Cliff's delta SE."""
    d = abs(delta)
    if d < 0.147:
        return "negligible"
    if d < 0.33:
        return "small"
    if d < 0.474:
        return "medium"
    return "large"


def pairwise_compare(x: pd.Series, y: pd.Series) -> dict:
    x = x.dropna().to_numpy()
    y = y.dropna().to_numpy()
    n1, n2 = len(x), len(y)
    if n1 < MIN_N_PER_GROUP or n2 < MIN_N_PER_GROUP:
        return {"n1": n1, "n2": n2, "u_stat": np.nan, "p_value": np.nan,
                "a12": np.nan, "cliffs_delta": np.nan, "magnitude": "insufficient_n"}
    u_stat, p_value = mannwhitneyu(x, y, alternative="two-sided")
    a12 = vargha_delaney_a12(x, y)
    delta = 2 * a12 - 1
    return {"n1": n1, "n2": n2, "u_stat": u_stat, "p_value": p_value,
            "a12": a12, "cliffs_delta": delta, "magnitude": cliffs_delta_magnitude(delta)}


def run_family(df: pd.DataFrame, metric: str, group_col: str, group_a: str, group_b: str,
               fixed_col: str, fixed_value: str) -> pd.DataFrame:
    """Bandingkan group_a vs group_b pada `group_col`, dgn `fixed_col`==fixed_value
    tetap, terpisah PER SEL (pattern, density, concurrency)."""
    sub = df[df[fixed_col] == fixed_value]
    rows = []
    for cell, cell_df in sub.groupby(CELL_COLS):
        a = cell_df[cell_df[group_col] == group_a][metric]
        b = cell_df[cell_df[group_col] == group_b][metric]
        result = pairwise_compare(a, b)
        row = dict(zip(CELL_COLS, cell))
        row.update({"metric": metric, fixed_col: fixed_value,
                     "group_a": group_a, "group_b": group_b})
        row.update(result)
        rows.append(row)
    out = pd.DataFrame(rows)
    if not out.empty:
        valid = out["p_value"].notna()
        if valid.any():
            _, p_adj, _, _ = multipletests(out.loc[valid, "p_value"], method="holm")
            out.loc[valid, "p_value_holm"] = p_adj
        else:
            out["p_value_holm"] = np.nan
    return out


def analyze_metric(df: pd.DataFrame, metric: str) -> dict:
    """Dua keluarga hipotesis per metrik, masing-masing dikoreksi Holm SENDIRI."""
    families = {}
    # A. Efek protocol, pada impl_mode tetap
    for impl_mode in sorted(df["impl_mode"].unique()):
        key = f"protocol_effect__impl_mode={impl_mode}"
        families[key] = run_family(df, metric, "protocol", "rest", "graphql", "impl_mode", impl_mode)
    # B. Efek type safety, pada protocol tetap
    for protocol in sorted(df["protocol"].unique()):
        key = f"impl_mode_effect__protocol={protocol}"
        families[key] = run_family(df, metric, "impl_mode", "passthrough", "typed", "protocol", protocol)
    return families


def plot_results(df: pd.DataFrame, output_dir: Path):
    """Visualisasi deskriptif (boxplot) -- TIDAK membawa klaim signifikansi."""
    output_dir.mkdir(parents=True, exist_ok=True)
    sns.set_style("whitegrid")
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))

    metrics = [
        ("lat_p95", "Latency P95 (ms)"),
        ("xproc_p95", "Server Processing Time P95 (s)"),
        ("throughput_rps", "Throughput (req/s)"),
        ("cpu_mean", "CPU Usage (%)"),
        ("rss_mean_mb", "Memory Usage (MB)"),
        ("payload_bytes_med", "Payload Size (bytes)"),
    ]

    for idx, (metric, title) in enumerate(metrics):
        ax = axes[idx // 3][idx % 3]
        df_plot = df.copy()
        df_plot["condition"] = df_plot["protocol"] + " + " + df_plot["impl_mode"]
        sns.boxplot(data=df_plot, x="condition", y=metric, ax=ax, hue="condition",
                    palette="viridis", legend=False)
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.tick_params(axis="x", rotation=45)

    plt.tight_layout()
    plt.savefig(output_dir / "factorial_results.png", dpi=300, bbox_inches="tight")
    print(f"Plot saved to {output_dir / 'factorial_results.png'}")
    plt.close()


def generate_report(df: pd.DataFrame, all_results: dict, output_dir: Path):
    """Laporan teks: per-sel Mann-Whitney U + Vargha-Delaney/Cliff's delta,
    dikoreksi Holm PER KELUARGA HIPOTESIS (bukan satu ANOVA terpool)."""
    report_path = output_dir / "factorial_analysis_report.txt"

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("FACTORIAL DESIGN ANALYSIS REPORT (per-cell Mann-Whitney U + A12/Cliff's delta)\n")
        f.write("Protocol (REST/GraphQL) x Type Safety (passthrough/typed)\n")
        f.write("=" * 70 + "\n\n")

        f.write("1. DATA SUMMARY\n" + "-" * 70 + "\n")
        f.write(f"Total runs: {len(df)}\n")
        f.write(f"Cells (pattern x density x concurrency): {df.groupby(CELL_COLS).ngroups}\n")
        for (proto, mode), count in df.groupby(["protocol", "impl_mode"]).size().items():
            f.write(f"  - {proto} + {mode}: {count} runs\n")
        f.write("\n")

        for metric, families in all_results.items():
            f.write(f"\n{'=' * 70}\nMETRIC: {metric}\n{'=' * 70}\n")
            for family_name, table in families.items():
                f.write(f"\n  Family: {family_name}\n  " + "-" * 66 + "\n")
                if table.empty:
                    f.write("    (no cells found)\n")
                    continue
                n_insufficient = (table["magnitude"] == "insufficient_n").sum()
                if n_insufficient:
                    f.write(f"    WARNING: {n_insufficient}/{len(table)} cells have n<{MIN_N_PER_GROUP} per group, excluded from inference\n")
                tested = table[table["magnitude"] != "insufficient_n"]
                n_sig = (tested["p_value_holm"] < 0.05).sum() if "p_value_holm" in tested else 0
                f.write(f"    Cells tested: {len(tested)}, significant after Holm correction (p<0.05): {n_sig}\n")
                for _, row in tested.iterrows():
                    cell_label = ",".join(f"{c}={row[c]}" for c in CELL_COLS)
                    sig_marker = "*" if row.get("p_value_holm", 1.0) < 0.05 else " "
                    f.write(f"    [{sig_marker}] {cell_label}: n=({row['n1']},{row['n2']}) "
                            f"p_holm={row['p_value_holm']:.4f} delta={row['cliffs_delta']:.3f} ({row['magnitude']})\n")

        f.write("\n" + "=" * 70 + "\n")
        f.write("NOTE ON INTERACTION EFFECT\n" + "-" * 70 + "\n")
        f.write("This script does not test the protocol x type-safety interaction\n")
        f.write("formally (that requires a nonparametric factorial method, e.g. the\n")
        f.write("Aligned Rank Transform -- Wobbrock et al., CHI 2011, R package ARTool).\n")
        f.write("Use the per-cell deltas above descriptively to spot interaction\n")
        f.write("candidates (e.g. type-safety cost differing in sign/magnitude between\n")
        f.write("protocols), then confirm with ART before claiming an interaction.\n")
        f.write("=" * 70 + "\n")

    print(f"Report saved to {report_path}")

    # CSV mentah semua perbandingan, untuk audit/lampiran
    all_rows = []
    for metric, families in all_results.items():
        for family_name, table in families.items():
            if table.empty:
                continue
            t = table.copy()
            t["family"] = family_name
            all_rows.append(t)
    if all_rows:
        combined = pd.concat(all_rows, ignore_index=True)
        combined.to_csv(output_dir / "factorial_comparisons.csv", index=False)
        print(f"Raw comparisons saved to {output_dir / 'factorial_comparisons.csv'}")


def main():
    parser = argparse.ArgumentParser(description="Per-cell nonparametric analysis of factorial design experiment results")
    parser.add_argument("--input", type=str, required=True, help="Path to combined results.csv")
    parser.add_argument("--output-dir", type=str, default="results/factorial_analysis",
                         help="Output directory for plots and reports")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)

    if not input_path.exists():
        print(f"ERROR: File not found: {input_path}")
        sys.exit(1)

    print("Loading data...")
    df = load_and_prepare_data(input_path)

    print("Running per-cell Mann-Whitney U + Vargha-Delaney A12 / Cliff's delta...")
    all_results = {}
    for metric in METRICS:
        try:
            all_results[metric] = analyze_metric(df, metric)
        except Exception as e:
            print(f"Warning: analysis failed for {metric}: {e}")

    print("Generating visualizations...")
    plot_results(df, output_dir)

    print("Generating report...")
    generate_report(df, all_results, output_dir)

    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)
    print(f"\nResults saved to: {output_dir}")
    print("Files generated:")
    print("  - factorial_results.png (descriptive box plots per condition)")
    print("  - factorial_analysis_report.txt (per-cell Mann-Whitney U + effect sizes)")
    print("  - factorial_comparisons.csv (raw per-cell comparison table)")


if __name__ == "__main__":
    main()
