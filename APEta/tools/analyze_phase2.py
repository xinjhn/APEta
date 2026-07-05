"""
tools/analyze_phase2.py
=========================
Statistical analysis for the Phase 2 cache-vs-paradigm study's results.csv
(orchestrator/run_experiment.py). Reuses the same nonparametric methodology
as the retired Path-B analysis (tools/analyze_factorial.py) -- Mann-Whitney U
+ Vargha-Delaney A12/Cliff's delta, Holm-Bonferroni corrected PER CELL FAMILY
-- since that methodology choice (Arcuri & Briand, ICSE 2011) was already
correct for this kind of right-skewed latency data and isn't specific to the
old factor set.

Cell = a unique (caching, access_pattern, payload_weight, entropy, network,
density, concurrency) combination. Within each cell, REST vs GraphQL is the
comparison (spec's headline question). With the CORE grid (default
orchestrator output), entropy/network/density/concurrency are constant
across all rows, so cells effectively reduce to (caching, access_pattern,
payload_weight) -- 12 cells, 2 protocol groups each.

Central figures (spec Section 6):
  1. Crossover surface: REST-minus-GraphQL median latency over
     (achieved cache-hit-rate x payload-weight), sign-flip marked --
     fig_crossover_surface.png.
  2. Coupling plot: achieved cache-hit-rate vs query-shape entropy level --
     fig_coupling_entropy_hitrate.png. NOTE this is NOT literally "GraphQL
     round-trips vs hit rate as aggregation depth rises" as worded in spec
     Section 6 -- this study's schema issues exactly ONE round trip per
     request on BOTH protocols (round_trip_count is a constant column, see
     orchestrator/run_experiment.py's comment), so a round-trip-vs-hit-rate
     plot would just be a flat line. Entropy-vs-hit-rate is the practical
     operationalization of the SAME underlying claim (H3: more aggregation/
     query variety => lower achieved hit rate) given this design -- a round-
     trip-count-bearing batch sub-study would need the retired "K resources
     per page" pattern reintroduced as its own arm, out of scope here.

Usage:
    python tools/analyze_phase2.py --input results/phase2/results.csv \
        --output-dir results/phase2/analysis
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

CELL_COLS = ["caching", "access_pattern", "payload_weight", "entropy", "network", "density", "concurrency", "page_size"]
# page_size=0 means "not in page mode" (core/full grid blocks) -- distinct
# from page_size=1/5/10 (the round-trip-savings arm's single-resource vs
# K-resource pages). Including it in CELL_COLS keeps those request shapes
# from being silently pooled together in any per-cell comparison.
METRICS = ["lat_p50", "lat_p95", "lat_p99", "throughput_rps", "payload_bytes_med",
           "cache_hit_rate", "error_rate", "cpu_mean", "rss_mean_mb"]
MIN_N_PER_GROUP = 3  # Mann-Whitney U is meaningless below this -- reported as 'insufficient_n'


def load_and_prepare_data(input_path: Path) -> pd.DataFrame:
    df = pd.read_csv(input_path)
    required = ["protocol"] + CELL_COLS + ["lat_p95", "throughput_rps", "error_rate"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Required columns not found: {missing}")

    print(f"Data loaded: {len(df)} runs")
    print(f"Protocols: {sorted(df['protocol'].unique())}")
    print(f"Cells ({'/'.join(CELL_COLS)}): {df.groupby(CELL_COLS).ngroups}")
    print(df.groupby(["protocol", "caching"]).size())
    print()
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
    if n1 < MIN_N_PER_GROUP or n2 < MIN_N_PER_GROUP:
        return {"n1": n1, "n2": n2, "u_stat": np.nan, "p_value": np.nan,
                "a12": np.nan, "cliffs_delta": np.nan, "magnitude": "insufficient_n"}
    u_stat, p_value = mannwhitneyu(x, y, alternative="two-sided")
    a12 = vargha_delaney_a12(x, y)
    delta = 2 * a12 - 1
    return {"n1": n1, "n2": n2, "u_stat": u_stat, "p_value": p_value,
            "a12": a12, "cliffs_delta": delta, "magnitude": cliffs_delta_magnitude(delta)}


def bootstrap_median_ci(x: pd.Series, n_boot: int = 2000, seed: int = 42) -> tuple:
    x = x.dropna().to_numpy()
    if len(x) < MIN_N_PER_GROUP:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    boots = [np.median(rng.choice(x, size=len(x), replace=True)) for _ in range(n_boot)]
    return (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)))


def run_family(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    """REST vs GraphQL, separately per cell (spec's headline comparison)."""
    rows = []
    for cell, cell_df in df.groupby(CELL_COLS):
        a = cell_df[cell_df["protocol"] == "rest"][metric]
        b = cell_df[cell_df["protocol"] == "graphql"][metric]
        result = pairwise_compare(a, b)
        row = dict(zip(CELL_COLS, cell))
        row.update({"metric": metric, "group_a": "rest", "group_b": "graphql"})
        row.update(result)
        row["rest_median"] = a.median() if len(a) else np.nan
        row["graphql_median"] = b.median() if len(b) else np.nan
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


def analyze_metric(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    return run_family(df, metric)


def plot_crossover_surface(df: pd.DataFrame, output_dir: Path) -> None:
    """REST-minus-GraphQL median lat_p95 over (achieved hit-rate bucket x
    payload-weight), sign-flip marked. Hit rate only exists for caching=on
    rows -- caching=off rows get hit_rate treated as 0 (the "uncached
    regime" H2 refers to).

    page_size>0 rows (the round-trip-savings/batch arm) are EXCLUDED here.
    Caught via real inspection: pooling them into this surface silently
    blended single-resource requests (page_size=0, ~6.6ms REST-vs-GraphQL
    gap) with K=5/K=10 page requests (~56ms/~96ms gap -- a fundamentally
    different request shape with much higher absolute latency) into the
    same "light payload" hit-rate-bucket cell, producing a misleading -56ms
    outlier that had nothing to do with hit-rate or payload-weight as such.
    The batch arm has its own correctly-scoped figure
    (tools/visualize_phase2_full.py's fig_roundtrip_savings) -- this surface
    should only describe genuine single-resource requests.
    """
    d = df[df.get("page_size", 0) == 0].copy() if "page_size" in df.columns else df.copy()
    d["hit_rate_bucket"] = pd.cut(
        d["cache_hit_rate"].fillna(0.0), bins=[-0.01, 0.1, 0.3, 0.5, 0.7, 0.9, 1.01],
        labels=["~0%", "10-30%", "30-50%", "50-70%", "70-90%", "90-100%"],
    )
    pivot_rows = []
    for (hb, pw), g in d.groupby(["hit_rate_bucket", "payload_weight"]):
        rest_med = g[g["protocol"] == "rest"]["lat_p95"].median()
        gql_med = g[g["protocol"] == "graphql"]["lat_p95"].median()
        if pd.notna(rest_med) and pd.notna(gql_med):
            pivot_rows.append({"hit_rate_bucket": hb, "payload_weight": pw, "diff": rest_med - gql_med})
    if not pivot_rows:
        print("  [skip] crossover surface: no overlapping cells")
        return
    pdf = pd.DataFrame(pivot_rows)
    pivot = pdf.pivot(index="payload_weight", columns="hit_rate_bucket", values="diff")

    fig, ax = plt.subplots(figsize=(9, 4))
    sns.heatmap(pivot, annot=True, fmt=".1f", center=0, cmap="RdBu_r",
                cbar_kws={"label": "REST-minus-GraphQL median lat_p95 (ms)"}, ax=ax)
    ax.set_title("Crossover surface: REST-minus-GraphQL latency\n(negative = REST faster, positive = GraphQL faster)")
    plt.tight_layout()
    plt.savefig(output_dir / "fig_crossover_surface.png", dpi=150)
    plt.close()
    print(f"  Saved {output_dir / 'fig_crossover_surface.png'}")


def plot_coupling_entropy_hitrate(df: pd.DataFrame, output_dir: Path) -> None:
    """H3 operationalization for this design -- see module docstring for why
    this substitutes for a literal round-trips-vs-hit-rate plot."""
    d = df[df["caching"] == "on"].copy()
    if d.empty:
        print("  [skip] coupling plot: no caching=on rows")
        return
    fig, ax = plt.subplots(figsize=(7, 4))
    sns.barplot(data=d, x="entropy", y="cache_hit_rate", hue="protocol",
                order=["low", "medium", "high"], ax=ax)
    ax.set_title("H3 coupling: query-shape entropy vs achieved cache-hit rate")
    ax.set_ylabel("Achieved cache-hit rate")
    plt.tight_layout()
    plt.savefig(output_dir / "fig_coupling_entropy_hitrate.png", dpi=150)
    plt.close()
    print(f"  Saved {output_dir / 'fig_coupling_entropy_hitrate.png'}")


def plot_descriptive_boxplots(df: pd.DataFrame, output_dir: Path) -> None:
    """Only facets by `caching` -- on a single, homogeneous grid (the
    original 24-block core grid) that's enough, since network/concurrency/
    page_size were constant. On the COMBINED multi-session dataset this is
    NOT enough: page_size=5/10 (round-trip-savings arm, ~150-310ms) and
    concurrency=100 (saturation outliers, up to 257ms) and network=lan
    (~7-20ms) all get thrown onto the same y-axis as the ~30-50ms "normal"
    cells, visually squashing a real, large, statistically significant
    REST-vs-GraphQL gap into an illegible band. Caught when the user looked
    at this exact figure and said the difference wasn't visible -- the
    underlying Mann-Whitney tests were never wrong (149/150 cells
    significant, large effect size), the PLOT was scoped wrong.

    Restricts to the core-grid-equivalent slice (page_size=0, network=
    constrained, concurrency=10) so this figure shows what it was always
    meant to show. The other axes (concurrency, network, page_size) each
    have their own dedicated, correctly-scoped figure in
    tools/visualize_phase2_full.py -- this one isn't meant to carry them too.
    """
    d = df.copy()
    if "page_size" in d.columns:
        d = d[d["page_size"] == 0]
    if "network" in d.columns:
        d = d[d["network"] == "constrained"]
    if "concurrency" in d.columns:
        d = d[d["concurrency"] == 10]
    if d.empty:
        print("  [skip] descriptive boxplots: no rows in the core-grid-equivalent slice")
        return

    sns.set_style("whitegrid")
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    panels = [
        ("lat_p95", "Latency P95 (ms)"), ("throughput_rps", "Throughput (req/s)"),
        ("cache_hit_rate", "Cache hit rate"), ("error_rate", "Error rate"),
        ("cpu_mean", "CPU % (mean)"), ("payload_bytes_med", "Payload bytes (median)"),
    ]
    for idx, (metric, title) in enumerate(panels):
        ax = axes[idx // 3][idx % 3]
        if metric not in d.columns:
            continue
        sns.boxplot(data=d, x="caching", y=metric, hue="protocol", ax=ax)
        ax.set_title(title, fontsize=11, fontweight="bold")
    fig.suptitle("Core-grid-equivalent slice only (network=constrained, concurrency=10, page_size=0) --\n"
                 "see fig_concurrency_scaling/fig_network_profile_comparison/fig_roundtrip_savings for the other axes",
                 fontsize=10, y=1.02)
    plt.tight_layout()
    plt.savefig(output_dir / "fig_descriptive_boxplots.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved {output_dir / 'fig_descriptive_boxplots.png'}")


def generate_report(df: pd.DataFrame, all_results: dict, output_dir: Path) -> None:
    report_path = output_dir / "phase2_analysis_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("PHASE 2 ANALYSIS REPORT -- REST vs GraphQL, per-cell Mann-Whitney U\n")
        f.write("+ Vargha-Delaney A12 / Cliff's delta, Holm-corrected within metric\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Total runs: {len(df)}\n")
        f.write(f"Cells: {df.groupby(CELL_COLS).ngroups}\n\n")

        for metric, table in all_results.items():
            f.write(f"\n{'=' * 70}\nMETRIC: {metric}\n{'=' * 70}\n")
            if table.empty:
                f.write("  (no cells found)\n")
                continue
            n_insufficient = (table["magnitude"] == "insufficient_n").sum()
            if n_insufficient:
                f.write(f"  WARNING: {n_insufficient}/{len(table)} cells have n<{MIN_N_PER_GROUP}/group, excluded\n")
            tested = table[table["magnitude"] != "insufficient_n"]
            n_sig = (tested["p_value_holm"] < 0.05).sum() if "p_value_holm" in tested else 0
            f.write(f"  Cells tested: {len(tested)}, significant after Holm correction (p<0.05): {n_sig}\n")
            for _, row in tested.iterrows():
                cell_label = ",".join(f"{c}={row[c]}" for c in CELL_COLS)
                sig = "*" if row.get("p_value_holm", 1.0) < 0.05 else " "
                f.write(f"  [{sig}] {cell_label}: rest_med={row['rest_median']:.3g} "
                        f"gql_med={row['graphql_median']:.3g} n=({row['n1']},{row['n2']}) "
                        f"p_holm={row['p_value_holm']:.4f} delta={row['cliffs_delta']:.3f} ({row['magnitude']})\n")

        f.write("\n" + "=" * 70 + "\n")
        f.write("SCOPE NOTES (disclose, don't bury)\n" + "-" * 70 + "\n")
        f.write("- round_trip_count is constant=1 for both protocols in this design --\n")
        f.write("  the coupling figure uses entropy-vs-hit-rate as the practical stand-in\n")
        f.write("  for H3, not a literal round-trip count (see analyze_phase2.py docstring).\n")
        f.write("- Corpus is 7 independent MOT sequences -- effective N for any claim about\n")
        f.write("  variety-across-scenes is ~7, not the row count in results.csv.\n")
        f.write("- With >=30 reps/cell, everything tends toward 'significant' -- read the\n")
        f.write("  Cliff's delta magnitude column, not just the Holm-corrected p-value.\n")
        f.write("- Runs use tools/netns_topology.sh: server+varnish live inside a network\n")
        f.write("  namespace, netem applies only to the single client<->edge veth hop, and\n")
        f.write("  the varnish<->backend hop stays on the namespace's own loopback. This\n")
        f.write("  fixes an earlier double-delay artifact (whole-`lo` netem, now retired --\n")
        f.write("  see tools/netem.sh's header) where a cache MISS paid the emulated network\n")
        f.write("  delay twice. Verified directly: MISS-through-Varnish latency went from\n")
        f.write("  ~2x direct to ~1x direct under the same `constrained` profile after the\n")
        f.write("  fix. Results in this report should NOT carry that bias.\n")
        f.write("- access_pattern='unique' is a finite-pool no-repeat cursor\n")
        f.write("  (exec.scenario.iterationInTest in k6/workload.js, global across VUs, not\n")
        f.write("  per-VU offset). Its achieved cache_hit_rate has a derivable floor of\n")
        f.write("  max(0, 1 - pool_size / iterations_in_run) once a single run's iteration\n")
        f.write("  count exceeds the entity pool size -- a hit rate above ~0 for 'unique' is\n")
        f.write("  expected once that happens, not evidence the access-pattern IV failed.\n")
        f.write("- cpu_mean/cpu_p95/rss_mean_mb/rss_p95_mb in this dataset are INVALID and\n")
        f.write("  should not be reported or interpreted. find_server_pid_in_tree() matched\n")
        f.write("  on the outer `sudo` wrapper's cmdline (which contains the full nested\n")
        f.write("  command as text) instead of the actual Python/uvicorn worker several\n")
        f.write("  exec/fork layers deeper, so the telemetry sampler watched an idle wrapper\n")
        f.write("  process for the entire run (confirmed: flat 0% CPU, ~7MB RSS across all\n")
        f.write("  720 rows -- a real worker under load showed ~98% CPU, ~48MB RSS in direct\n")
        f.write("  verification). Bug is fixed in orchestrator/run_experiment.py post-hoc;\n")
        f.write("  re-verified through a fresh pilot showing sane, varying CPU/RSS. The fix\n")
        f.write("  cannot retroactively recover this run's already-elapsed sampling windows.\n")
        f.write("  All other metrics (lat_p50/p95/p99, throughput_rps, cache_hit_rate,\n")
        f.write("  error_rate, payload_bytes_med) come from k6's own client-side measurement,\n")
        f.write("  not the sampler, and are unaffected.\n")
        f.write("=" * 70 + "\n")
    print(f"Report saved to {report_path}")

    all_rows = [t for t in all_results.values() if not t.empty]
    if all_rows:
        combined = pd.concat([t.assign(metric=t["metric"]) for t in all_rows], ignore_index=True)
        combined.to_csv(output_dir / "phase2_comparisons.csv", index=False)
        print(f"Raw comparisons saved to {output_dir / 'phase2_comparisons.csv'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output-dir", default="results/phase2/analysis")
    args = ap.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if not input_path.exists():
        print(f"ERROR: file not found: {input_path}")
        sys.exit(1)

    print("Loading data...")
    df = load_and_prepare_data(input_path)

    print("Running per-cell Mann-Whitney U + Vargha-Delaney A12 / Cliff's delta...")
    all_results = {m: analyze_metric(df, m) for m in METRICS if m in df.columns}

    print("Generating figures...")
    plot_descriptive_boxplots(df, output_dir)
    plot_crossover_surface(df, output_dir)
    plot_coupling_entropy_hitrate(df, output_dir)

    print("Generating report...")
    generate_report(df, all_results, output_dir)

    print("\nDone. Output in:", output_dir)


if __name__ == "__main__":
    main()
