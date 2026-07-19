"""
tools/analyze_mot_scenarios.py
================================
Statistical analysis for the MOT scenario study (results/mot-scenarios-<arm>/
results.csv, orchestrator run with APE_GRID=mot). Same nonparametric
methodology as tools/analyze_phase2.py -- per-cell Mann-Whitney U +
Vargha-Delaney A12/Cliff's delta, Holm-Bonferroni corrected per hypothesis
family (Arcuri & Briand, ICSE 2011) -- with the MOT grid's own cell axes and
the overload-tier rules from design/SCENARIO_DESIGN.md / design/CALIBRATION.md:

  * Cell = (scenario, tier, rate_label). REST vs GraphQL compared within cell.
  * r120_overload rows are NEVER pooled with r40/r80. Sub-saturation cells
    form one Holm family per metric; overload cells form separate Holm
    families per (metric, scenario family) -- family = image (M1-M4) /
    track (M5) / page (M6), per orchestrator/config.py's mot_family() --
    because the overload rate was calibrated per family and only guarantees
    super-saturation relative to the calibrated heaviest-tier ceiling
    (design/CALIBRATION.md GO condition 1). Each overload row carries
    overload_saturates = which protocol's ceiling defined the family's rate.
  * Primary metric lat_p95; secondaries lat_p50, throughput_rps,
    payload_bytes_med, round_trip_count, cpu_mean, rss_mean_mb, and
    page_latency_med where populated (M5/M6 -- the multi-round-trip flows).
  * round_trip_count is CONSTANT BY DESIGN within protocol x scenario
    (M5: rest=2 vs graphql=1; M6: rest=K vs graphql=1; M1-M4: 1 vs 1), so a
    rank test on it is degenerate -- cells where both groups are constant are
    reported descriptively (medians) and marked 'degenerate_constant', not
    tested.

Usage:
    python tools/analyze_mot_scenarios.py \
        --input results/mot-scenarios-core/results.csv \
        --output-dir results/mot-scenarios-core/analysis
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import mannwhitneyu, rankdata
from statsmodels.stats.multitest import multipletests

CELL_COLS = ["scenario", "tier", "rate_label"]
METRICS = ["lat_p95", "lat_p50", "throughput_rps", "payload_bytes_med",
           "round_trip_count", "cpu_mean", "rss_mean_mb", "page_latency_med"]
MIN_N_PER_GROUP = 3
OVERLOAD_LABEL = "r120_overload"


def mot_family(scenario: str) -> str:
    # mirror of orchestrator/config.py's mapping (kept inline so this script
    # runs against archived results without importing orchestrator state)
    if scenario in ("M1", "M2", "M3", "M4"):
        return "image"
    if scenario in ("M5", "M5E"):
        return "track"
    return "page"


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
    if n1 < MIN_N_PER_GROUP or n2 < MIN_N_PER_GROUP:
        return {"n1": n1, "n2": n2, "u_stat": np.nan, "p_value": np.nan,
                "a12": np.nan, "cliffs_delta": np.nan, "magnitude": "insufficient_n"}
    if np.ptp(x) == 0 and np.ptp(y) == 0:
        # both groups constant (round_trip_count by design): rank test is
        # degenerate -- report medians, no p-value
        a12 = 0.5 if x[0] == y[0] else (0.0 if x[0] < y[0] else 1.0)
        delta = 2 * a12 - 1
        return {"n1": n1, "n2": n2, "u_stat": np.nan, "p_value": np.nan,
                "a12": a12, "cliffs_delta": delta, "magnitude": "degenerate_constant"}
    u_stat, p_value = mannwhitneyu(x, y, alternative="two-sided")
    a12 = vargha_delaney_a12(x, y)
    delta = 2 * a12 - 1
    return {"n1": n1, "n2": n2, "u_stat": u_stat, "p_value": p_value,
            "a12": a12, "cliffs_delta": delta, "magnitude": cliffs_delta_magnitude(delta)}


def compare_cells(df: pd.DataFrame, metric: str, family_label: str) -> pd.DataFrame:
    rows = []
    for cell, cell_df in df.groupby(CELL_COLS, observed=True):
        a = cell_df[cell_df["protocol"] == "rest"][metric]
        b = cell_df[cell_df["protocol"] == "graphql"][metric]
        if a.dropna().empty and b.dropna().empty:
            continue  # metric not populated in this cell (e.g. page_latency_med outside M5/M6)
        result = pairwise_compare(a, b)
        row = dict(zip(CELL_COLS, cell))
        row.update({"metric": metric, "family": family_label,
                    "group_a": "rest", "group_b": "graphql"})
        sat = cell_df["overload_saturates"].dropna().unique()
        row["overload_saturates"] = sat[0] if len(sat) else ""
        row.update(result)
        row["rest_median"] = a.median() if len(a) else np.nan
        row["graphql_median"] = b.median() if len(b) else np.nan
        rows.append(row)
    out = pd.DataFrame(rows)
    if not out.empty:
        valid = out["p_value"].notna()
        out["p_value_holm"] = np.nan
        if valid.any():
            _, p_adj, _, _ = multipletests(out.loc[valid, "p_value"], method="holm")
            out.loc[valid, "p_value_holm"] = p_adj
    return out


def analyze_metric(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    """One Holm family for all sub-saturation cells; separate Holm families
    per scenario family for overload cells (never pooled -- GO condition 1)."""
    sub = df[df["rate_label"] != OVERLOAD_LABEL]
    over = df[df["rate_label"] == OVERLOAD_LABEL]
    tables = [compare_cells(sub, metric, "sub_saturation")]
    for fam, fam_df in over.groupby(over["scenario"].map(mot_family)):
        tables.append(compare_cells(fam_df, metric, f"overload_{fam}"))
    tables = [t for t in tables if not t.empty]
    return pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()


def plot_latency_by_scenario(df: pd.DataFrame, output_dir: Path) -> None:
    sub = df[df["rate_label"] != OVERLOAD_LABEL]
    sns.set_style("whitegrid")
    scenarios = sorted(sub["scenario"].unique())
    hue_order = ["rest", "graphql"]
    protocol_palette = {"rest": "#e99572", "graphql": "#67b7a1"}
    fig, axes = plt.subplots(2, 3, figsize=(18, 9))
    for idx, sc in enumerate(scenarios):
        ax = axes[idx // 3][idx % 3]
        d = sub[sub["scenario"] == sc]
        tiers = sorted(d["tier"].unique())
        sns.boxplot(data=d, x="tier", y="lat_p95", hue="protocol",
                    order=tiers, hue_order=hue_order, palette=protocol_palette,
                    showfliers=False, ax=ax)
        # Keep the individual runs visible. This makes small demo samples
        # interpretable and prevents a one-observation box from looking like
        # an unexplained line, while the box still carries the median/IQR.
        sns.stripplot(data=d, x="tier", y="lat_p95", hue="protocol",
                      order=tiers, hue_order=hue_order, palette=protocol_palette,
                      dodge=True, jitter=0.08, alpha=0.8, size=4,
                      legend=False, ax=ax)
        rate_order = [r for r in ("r40", "r80") if r in set(d["rate_label"])]
        ax.set_title(f"{sc} (sub-saturation {'+'.join(rate_order)})",
                     fontsize=11, fontweight="bold")
        ax.set_ylabel("lat_p95 (ms)")
    fig.suptitle("REST vs GraphQL p95 latency per scenario/tier -- boxes show median/IQR; dots show runs",
                 fontsize=11, y=1.0)
    plt.tight_layout()
    plt.savefig(output_dir / "fig_mot_latency_by_scenario.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved {output_dir / 'fig_mot_latency_by_scenario.png'}")


def plot_throughput_attainment(df: pd.DataFrame, output_dir: Path) -> None:
    """Plot achieved throughput as a percentage of each cell's target rate."""
    sub = df[df["rate_label"] != OVERLOAD_LABEL].copy()
    sub["throughput_rps"] = pd.to_numeric(sub["throughput_rps"], errors="coerce")
    sub["target_rps"] = pd.to_numeric(sub["concurrency"], errors="coerce")
    sub["round_trip_count"] = pd.to_numeric(sub["round_trip_count"], errors="coerce")
    sub = sub[(sub["target_rps"] > 0) & (sub["round_trip_count"] > 0)]
    # throughput_rps counts HTTP requests. REST M5 uses two requests per
    # scenario iteration and REST M6 uses K, while GraphQL uses one. Convert
    # back to completed scenario iterations before comparing with the
    # configured scenario-arrival target.
    sub["scenario_throughput_rps"] = sub["throughput_rps"] / sub["round_trip_count"]
    sub["target_attainment_pct"] = 100 * sub["scenario_throughput_rps"] / sub["target_rps"]

    scenarios = sorted(sub["scenario"].dropna().unique())
    if not scenarios:
        return
    ncols = min(3, len(scenarios))
    nrows = int(np.ceil(len(scenarios) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(6 * ncols, 4.5 * nrows), squeeze=False)
    axes_flat = axes.ravel()
    hue_order = ["rest", "graphql"]
    protocol_palette = {"rest": "#e99572", "graphql": "#67b7a1"}

    for idx, sc in enumerate(scenarios):
        ax = axes_flat[idx]
        d = sub[sub["scenario"] == sc]
        tiers = sorted(d["tier"].unique())
        sns.boxplot(data=d, x="tier", y="target_attainment_pct", hue="protocol",
                    order=tiers, hue_order=hue_order, palette=protocol_palette,
                    showfliers=False, ax=ax)
        sns.stripplot(data=d, x="tier", y="target_attainment_pct", hue="protocol",
                      order=tiers, hue_order=hue_order, palette=protocol_palette,
                      dodge=True, jitter=0.08, alpha=0.8, size=4,
                      legend=False, ax=ax)
        ax.axhline(100, color="#667085", linestyle="--", linewidth=1,
                   label="configured target")
        rate_order = [r for r in ("r40", "r80") if r in set(d["rate_label"])]
        targets = "/".join(f"{v:g}" for v in sorted(d["target_rps"].unique()))
        ax.set_title(f"{sc} ({'+'.join(rate_order)}; target {targets} rps)",
                     fontsize=11, fontweight="bold")
        ax.set_ylabel("Achieved / target scenario throughput (%)")
        ax.set_xlabel("tier")
    for ax in axes_flat[len(scenarios):]:
        ax.set_visible(False)

    fig.suptitle("Scenario-throughput target attainment -- request throughput normalized by round trips; 100% = target sustained",
                 fontsize=11, y=1.0)
    plt.tight_layout()
    path = output_dir / "fig_mot_throughput_by_scenario.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved {path}")


def plot_payload_by_scenario(df: pd.DataFrame, output_dir: Path) -> None:
    """Compare measured response payload size within each demo scenario."""
    sub = df[df["rate_label"] != OVERLOAD_LABEL].copy()
    sub["payload_kib"] = pd.to_numeric(sub["payload_bytes_med"], errors="coerce") / 1024
    scenarios = sorted(sub["scenario"].dropna().unique())
    if not scenarios:
        return
    ncols = min(3, len(scenarios))
    nrows = int(np.ceil(len(scenarios) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(6 * ncols, 4.5 * nrows), squeeze=False)
    axes_flat = axes.ravel()
    hue_order = ["rest", "graphql"]
    palette = {"rest": "#e99572", "graphql": "#67b7a1"}
    for idx, sc in enumerate(scenarios):
        ax = axes_flat[idx]
        d = sub[sub["scenario"] == sc]
        tiers = sorted(d["tier"].unique())
        sns.boxplot(data=d, x="tier", y="payload_kib", hue="protocol",
                    order=tiers, hue_order=hue_order, palette=palette,
                    showfliers=False, ax=ax)
        sns.stripplot(data=d, x="tier", y="payload_kib", hue="protocol",
                      order=tiers, hue_order=hue_order, palette=palette,
                      dodge=True, jitter=0.08, alpha=0.8, size=4,
                      legend=False, ax=ax)
        ax.set_title(f"{sc} response payload", fontsize=11, fontweight="bold")
        ax.set_ylabel("Median response payload (KiB)")
        ax.set_xlabel("tier")
    for ax in axes_flat[len(scenarios):]:
        ax.set_visible(False)
    fig.suptitle("Measured response payload by demo scenario -- boxes show median/IQR; dots show runs",
                 fontsize=11, y=1.0)
    plt.tight_layout()
    path = output_dir / "fig_mot_payload_by_scenario.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved {path}")


def plot_round_trips_by_scenario(df: pd.DataFrame, output_dir: Path) -> None:
    """Visualize the measured/design round-trip count for each scenario."""
    data = df.copy()
    data["round_trip_count"] = pd.to_numeric(data["round_trip_count"], errors="coerce")
    scenarios = sorted(data["scenario"].dropna().unique())
    if not scenarios:
        return
    ncols = min(3, len(scenarios))
    nrows = int(np.ceil(len(scenarios) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(6 * ncols, 4.2 * nrows), squeeze=False)
    axes_flat = axes.ravel()
    protocols = ["rest", "graphql"]
    colors = {"rest": "#e99572", "graphql": "#67b7a1"}
    width = 0.34
    for idx, sc in enumerate(scenarios):
        ax = axes_flat[idx]
        d = data[data["scenario"] == sc]
        tiers = sorted(d["tier"].unique())
        x = np.arange(len(tiers))
        for offset, protocol in enumerate(protocols):
            values = [d[(d["tier"] == tier) & (d["protocol"] == protocol)]
                      ["round_trip_count"].median() for tier in tiers]
            bars = ax.bar(x + (offset - 0.5) * width, values, width,
                          color=colors[protocol], label=protocol)
            ax.bar_label(bars, fmt="%g", padding=3, fontsize=9)
        ax.set_xticks(x, tiers)
        ax.set_title(sc, fontsize=11, fontweight="bold")
        ax.set_ylabel("HTTP round trips / scenario iteration")
        ax.set_xlabel("tier")
        ax.set_ylim(0, max(2, d["round_trip_count"].max() + 1))
        ax.legend()
    for ax in axes_flat[len(scenarios):]:
        ax.set_visible(False)
    fig.suptitle("Round-trip structure by scenario -- M5 and M6 expose REST's multi-request client flow",
                 fontsize=11, y=1.0)
    plt.tight_layout()
    path = output_dir / "fig_mot_round_trips_by_scenario.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved {path}")


def plot_client_flow_latency(df: pd.DataFrame, output_dir: Path) -> None:
    """Compare end-to-end client-flow latency where M5/M6 populate it."""
    data = df.copy()
    data["page_latency_med"] = pd.to_numeric(data["page_latency_med"], errors="coerce")
    data = data[data["page_latency_med"].notna()]
    scenarios = sorted(data["scenario"].dropna().unique())
    if not scenarios:
        return
    fig, axes = plt.subplots(1, len(scenarios), figsize=(7 * len(scenarios), 4.8), squeeze=False)
    axes_flat = axes.ravel()
    hue_order = ["rest", "graphql"]
    palette = {"rest": "#e99572", "graphql": "#67b7a1"}
    for idx, sc in enumerate(scenarios):
        ax = axes_flat[idx]
        d = data[data["scenario"] == sc]
        tiers = sorted(d["tier"].unique())
        sns.boxplot(data=d, x="tier", y="page_latency_med", hue="protocol",
                    order=tiers, hue_order=hue_order, palette=palette,
                    showfliers=False, ax=ax)
        sns.stripplot(data=d, x="tier", y="page_latency_med", hue="protocol",
                      order=tiers, hue_order=hue_order, palette=palette,
                      dodge=True, jitter=0.08, alpha=0.8, size=5,
                      legend=False, ax=ax)
        ax.set_title(f"{sc} client flow", fontsize=11, fontweight="bold")
        ax.set_ylabel("Median end-to-end flow latency (ms)")
        ax.set_xlabel("tier")
    fig.suptitle("Client-visible multi-request latency -- REST sequence versus one GraphQL operation",
                 fontsize=11, y=1.0)
    plt.tight_layout()
    path = output_dir / "fig_mot_client_flow_latency.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved {path}")


def plot_overload(df: pd.DataFrame, output_dir: Path) -> None:
    over = df[df["rate_label"] == OVERLOAD_LABEL].copy()
    if over.empty:
        return
    over["cell"] = over["scenario"] + "/" + over["tier"]
    sns.set_style("whitegrid")
    fig, axes = plt.subplots(1, 2, figsize=(16, 5))
    sns.boxplot(data=over, x="cell", y="lat_p95", hue="protocol", ax=axes[0])
    axes[0].set_title("Overload tier: p95 latency")
    axes[0].tick_params(axis="x", rotation=45)
    sns.boxplot(data=over, x="cell", y="throughput_rps", hue="protocol", ax=axes[1])
    axes[1].set_title("Overload tier: achieved throughput")
    axes[1].tick_params(axis="x", rotation=45)
    fig.suptitle("r120_overload cells (rate = 120% of the family's LOWER protocol ceiling; "
                 "see overload_saturates column)", fontsize=10)
    plt.tight_layout()
    plt.savefig(output_dir / "fig_mot_overload.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved {output_dir / 'fig_mot_overload.png'}")


def generate_report(df: pd.DataFrame, all_results: dict, output_dir: Path) -> None:
    report_path = output_dir / "mot_analysis_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("MOT SCENARIO ANALYSIS -- REST vs GraphQL, per-cell Mann-Whitney U\n")
        f.write("+ Vargha-Delaney A12 / Cliff's delta, Holm-corrected per family\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Total runs: {len(df)}\n")
        f.write(f"Cells ({'/'.join(CELL_COLS)} x protocol): "
                f"{df.groupby(CELL_COLS + ['protocol']).ngroups}\n")
        f.write("Families: sub_saturation (r40+r80 pooled Holm family per metric);\n")
        f.write("          overload_image / overload_track / overload_page (separate\n")
        f.write("          Holm families -- r120_overload never pooled with r40/r80).\n\n")

        for metric, table in all_results.items():
            f.write(f"\n{'=' * 70}\nMETRIC: {metric}\n{'=' * 70}\n")
            if table.empty:
                f.write("  (no cells with data)\n")
                continue
            for fam, ft in table.groupby("family"):
                tested = ft[~ft["magnitude"].isin(["insufficient_n", "degenerate_constant"])]
                n_sig = (tested["p_value_holm"] < 0.05).sum() if len(tested) else 0
                f.write(f"\n  [{fam}] cells tested: {len(tested)}, "
                        f"significant after Holm (p<0.05): {n_sig}\n")
                degen = ft[ft["magnitude"] == "degenerate_constant"]
                if len(degen):
                    f.write(f"  ({len(degen)} cells constant-by-design, reported descriptively)\n")
                for _, row in ft.iterrows():
                    cell_label = ",".join(f"{c}={row[c]}" for c in CELL_COLS)
                    if row["magnitude"] == "degenerate_constant":
                        f.write(f"  [c] {cell_label}: rest={row['rest_median']:.3g} "
                                f"gql={row['graphql_median']:.3g} (constant by design)\n")
                        continue
                    sig = "*" if pd.notna(row.get("p_value_holm")) and row["p_value_holm"] < 0.05 else " "
                    sat = f" sat={row['overload_saturates']}" if row["overload_saturates"] else ""
                    f.write(f"  [{sig}] {cell_label}{sat}: rest_med={row['rest_median']:.4g} "
                            f"gql_med={row['graphql_median']:.4g} n=({row['n1']},{row['n2']}) "
                            f"p_holm={row['p_value_holm']:.4f} delta={row['cliffs_delta']:.3f} "
                            f"({row['magnitude']})\n")

        f.write("\n" + "=" * 70 + "\n")
        f.write("SCOPE NOTES (disclose, don't bury)\n" + "-" * 70 + "\n")
        f.write("- r120_overload guarantees super-saturation only relative to the\n")
        f.write("  calibrated heaviest-tier ceiling of its family; lighter-tier overload\n")
        f.write("  cells may not themselves saturate (design/CALIBRATION.md). Read\n")
        f.write("  overload cells as 'behavior at the family's shared overload rate',\n")
        f.write("  not 'both protocols saturated'.\n")
        f.write("- dropped_iterations > 0 occurs ONLY in overload cells (expected):\n")
        f.write("  the arrival rate exceeds service rate there by construction.\n")
        f.write("- round_trip_count differs by protocol BY DESIGN in M5 (rest=2) and\n")
        f.write("  M6 (rest=K); it is a design descriptor, not a measured outcome --\n")
        f.write("  reported descriptively only.\n")
        f.write("- page_latency_med exists only for M5/M6 (multi-request client flows).\n")
        f.write("- Corpus is 7 independent MOT sequences -- effective N for claims about\n")
        f.write("  variety-across-scenes is ~7, not the row count.\n")
        f.write("- With n=30/cell, tiny differences reach significance -- read the\n")
        f.write("  Cliff's delta magnitude column, not just p_holm.\n")
        f.write("=" * 70 + "\n")
    print(f"Report saved to {report_path}")

    tables = [t for t in all_results.values() if not t.empty]
    if tables:
        pd.concat(tables, ignore_index=True).to_csv(
            output_dir / "mot_comparisons.csv", index=False)
        print(f"Raw comparisons saved to {output_dir / 'mot_comparisons.csv'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if not input_path.exists():
        print(f"ERROR: file not found: {input_path}")
        sys.exit(1)

    df = pd.read_csv(input_path)
    print(f"Data loaded: {len(df)} runs, "
          f"{df.groupby(CELL_COLS + ['protocol']).ngroups} protocol-cells")

    all_results = {m: analyze_metric(df, m) for m in METRICS if m in df.columns}

    plot_latency_by_scenario(df, output_dir)
    plot_throughput_attainment(df, output_dir)
    plot_payload_by_scenario(df, output_dir)
    plot_round_trips_by_scenario(df, output_dir)
    plot_client_flow_latency(df, output_dir)
    plot_overload(df, output_dir)
    generate_report(df, all_results, output_dir)
    print("Done. Output in:", output_dir)


if __name__ == "__main__":
    main()
