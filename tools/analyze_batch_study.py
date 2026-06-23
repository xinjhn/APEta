"""
tools/analyze_batch_study.py
=============================
Analisis statistik utk sub-studi "batch" (N+1 round-trip avoidance, lihat
k6/load_batch.js, tools/run_batch_study.py). TERPISAH dari
tools/analyze_factorial.py -- skema kolom & unit analisisnya berbeda
(batch_wall_time per-K, network_profile sbg faktor, BUKAN impl_mode).

Pendekatan sama dgn analyze_factorial.py (lihat catatan metodologis di sana):
Mann-Whitney U + Vargha-Delaney A12/Cliff's delta PER SEL (density, batch_k),
dikoreksi Holm-Bonferroni TERPISAH per network_profile (krn pertanyaannya
justru "apakah efek protocol berbeda arah/besaran antar profil jaringan" --
mencampur semua profil jadi satu pool akan menutupi titik crossover yang
dicari).

Laporan juga menyajikan "crossover table": utk tiap (network_profile, batch_k),
protokol mana yang median batch_wall_time lebih rendah -- ini visualisasi
langsung dari klaim utama RQ2 (GraphQL menang hanya pada profil+K tertentu).

Cara pakai:
    python tools/analyze_batch_study.py --input results/batch_study/results.csv \
        --output-dir results/batch_study/analysis
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

CELL_COLS = ["density", "batch_k"]
METRIC = "batch_wall_time_p95"
MIN_N_PER_GROUP = 3


def load_data(input_path: Path) -> pd.DataFrame:
    df = pd.read_csv(input_path)
    required = ["protocol", "network_profile", "density", "batch_k", METRIC]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Kolom yang diperlukan tidak ditemukan: {missing}")
    print(f"Data loaded: {len(df)} runs")
    print(f"Network profiles: {sorted(df['network_profile'].unique())}")
    print(f"Batch sizes: {sorted(df['batch_k'].unique())}")
    print(df.groupby(["network_profile", "protocol", "batch_k"]).size())
    return df


def vargha_delaney_a12(x: np.ndarray, y: np.ndarray) -> float:
    n1, n2 = len(x), len(y)
    ranks = rankdata(np.concatenate([x, y]))
    r1 = ranks[:n1].sum()
    return (r1 / n1 - (n1 + 1) / 2) / n2


def cliffs_delta_magnitude(delta: float) -> str:
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
    # Median/winner tetap deskriptif walau n kurang utk uji formal (mis. saat
    # pilot n=2) -- HANYA p_value/effect size yang butuh MIN_N_PER_GROUP.
    median_rest = float(np.median(x)) if n1 else np.nan
    median_graphql = float(np.median(y)) if n2 else np.nan
    if n1 < MIN_N_PER_GROUP or n2 < MIN_N_PER_GROUP:
        return {"n1": n1, "n2": n2, "median_rest": median_rest, "median_graphql": median_graphql,
                "p_value": np.nan, "a12": np.nan, "cliffs_delta": np.nan, "magnitude": "insufficient_n"}
    u_stat, p_value = mannwhitneyu(x, y, alternative="two-sided")
    a12 = vargha_delaney_a12(x, y)
    delta = 2 * a12 - 1
    return {"n1": n1, "n2": n2, "median_rest": float(np.median(x)), "median_graphql": float(np.median(y)),
            "p_value": p_value, "a12": a12, "cliffs_delta": delta, "magnitude": cliffs_delta_magnitude(delta)}


def analyze_profile(df: pd.DataFrame, network_profile: str) -> pd.DataFrame:
    sub = df[df["network_profile"] == network_profile]
    rows = []
    for cell, cell_df in sub.groupby(CELL_COLS):
        rest = cell_df[cell_df["protocol"] == "rest"][METRIC]
        graphql = cell_df[cell_df["protocol"] == "graphql"][METRIC]
        result = pairwise_compare(rest, graphql)  # group_a=rest(x), group_b=graphql(y)
        row = dict(zip(CELL_COLS, cell))
        row["network_profile"] = network_profile
        row.update(result)
        if not np.isnan(result["median_rest"]) and not np.isnan(result["median_graphql"]):
            row["winner"] = "rest" if result["median_rest"] < result["median_graphql"] else "graphql"
        else:
            row["winner"] = "no_data"
        rows.append(row)
    out = pd.DataFrame(rows)
    if not out.empty:
        valid = out["p_value"].notna()
        if valid.any():
            _, p_adj, _, _ = multipletests(out.loc[valid, "p_value"], method="holm")
            out.loc[valid, "p_value_holm"] = p_adj
    return out


def plot_crossover(df: pd.DataFrame, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    sns.set_style("whitegrid")
    profiles = sorted(df["network_profile"].unique())
    fig, axes = plt.subplots(1, len(profiles), figsize=(6 * len(profiles), 5), sharey=False)
    if len(profiles) == 1:
        axes = [axes]
    for ax, profile in zip(axes, profiles):
        sub = df[df["network_profile"] == profile]
        agg = sub.groupby(["batch_k", "protocol"])[METRIC].median().reset_index()
        sns.lineplot(data=agg, x="batch_k", y=METRIC, hue="protocol", marker="o", ax=ax)
        ax.set_title(f"network_profile={profile}")
        ax.set_xlabel("batch_k")
        ax.set_ylabel(f"median {METRIC} (ms)")
    plt.tight_layout()
    plt.savefig(output_dir / "batch_crossover.png", dpi=300, bbox_inches="tight")
    print(f"Plot saved to {output_dir / 'batch_crossover.png'}")
    plt.close()


def generate_report(all_results: dict, output_dir: Path):
    report_path = output_dir / "batch_study_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("BATCH STUDY (N+1 round-trip avoidance) ANALYSIS REPORT\n")
        f.write("Per-cell Mann-Whitney U + Vargha-Delaney A12 / Cliff's delta\n")
        f.write("=" * 70 + "\n\n")

        f.write("CROSSOVER TABLE (median batch_wall_time_p95, winner = lower median)\n")
        f.write("-" * 70 + "\n")
        for profile, table in all_results.items():
            f.write(f"\nnetwork_profile={profile}\n")
            if table.empty:
                f.write("  (no cells)\n")
                continue
            for _, row in table.sort_values("batch_k").iterrows():
                if row["winner"] == "no_data":
                    f.write(f"  density={row['density']} batch_k={row['batch_k']}: no data\n")
                    continue
                base = (f"  density={row['density']} batch_k={row['batch_k']}: "
                        f"rest_median={row['median_rest']:.1f}ms graphql_median={row['median_graphql']:.1f}ms "
                        f"winner={row['winner']}")
                if row["magnitude"] == "insufficient_n":
                    f.write(f"  [ ] {base} (n={row['n1']},{row['n2']} -- below n={MIN_N_PER_GROUP}, descriptive only, no test)\n")
                else:
                    sig = "*" if row.get("p_value_holm", 1.0) < 0.05 else " "
                    f.write(f"  [{sig}] {base} p_holm={row['p_value_holm']:.4f} "
                             f"delta={row['cliffs_delta']:.3f} ({row['magnitude']})\n")

        f.write("\n" + "=" * 70 + "\n")
        f.write("NOTE\n" + "-" * 70 + "\n")
        f.write("'*' = significant after Holm correction WITHIN this network_profile's\n")
        f.write("family of cells (correction is NOT pooled across profiles -- the research\n")
        f.write("question is whether the winner flips BETWEEN profiles, so each profile's\n")
        f.write("family is tested independently. See tools/analyze_factorial.py for the\n")
        f.write("same rationale applied to the main factorial study.)\n")
        f.write("=" * 70 + "\n")
    print(f"Report saved to {report_path}")

    all_rows = [t for t in all_results.values() if not t.empty]
    if all_rows:
        pd.concat(all_rows, ignore_index=True).to_csv(output_dir / "batch_comparisons.csv", index=False)
        print(f"Raw comparisons saved to {output_dir / 'batch_comparisons.csv'}")


def main():
    ap = argparse.ArgumentParser(description="Per-cell nonparametric analysis of the batch/N+1 sub-study")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output-dir", default="results/batch_study/analysis")
    args = ap.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: File not found: {input_path}")
        sys.exit(1)

    output_dir = Path(args.output_dir)
    df = load_data(input_path)

    all_results = {}
    for profile in sorted(df["network_profile"].unique()):
        all_results[profile] = analyze_profile(df, profile)

    plot_crossover(df, output_dir)
    generate_report(all_results, output_dir)

    print("\nANALYSIS COMPLETE")
    print(f"Results saved to: {output_dir}")


if __name__ == "__main__":
    main()
