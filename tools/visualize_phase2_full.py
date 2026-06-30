"""
tools/visualize_phase2_full.py
================================
Figures for the full Phase 2 design (core grid + 9 drill-in/interaction
sessions), beyond what tools/analyze_phase2.py already covers (crossover
surface, entropy-coupling, descriptive boxplots -- Gambar V.2/V.3).

Chart-type choices follow domain convention in systems/empirical-SE papers,
not a single normative citation:
  - box plots for distributional comparison (Wohlin et al. 2024, PB-61,
    on controlled-experiment reporting generally)
  - line/scaling charts for trend-over-load data (matches how PB-25/PB-28
    -- Lloyd et al. -- present their own 1-100 concurrency scaling)
  - bar charts for simple categorical main effects (entropy, density)

Usage:
    python tools/visualize_phase2_full.py --out-dir results/phase2-figures
"""
from __future__ import annotations

import argparse
import csv
import statistics
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

ROOT = Path(__file__).resolve().parent.parent
sns.set_style("whitegrid")


def load(path: Path) -> list:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fig_concurrency_scaling(out_dir: Path) -> None:
    """REST vs GraphQL latency across concurrency=1,10,50,100 -- combines
    core grid (10) + concurrency-drillin (1,50) + concurrency100-drillin (100)."""
    core = load(ROOT / "results/phase2-core-real/results.csv")
    conc = load(ROOT / "results/phase2-concurrency-drillin/results.csv")
    conc100 = load(ROOT / "results/phase2-concurrency100-drillin/results.csv")

    levels = ["1", "10", "50", "100"]
    sources = {"1": conc, "10": core, "50": conc, "100": conc100}
    data = {"rest": [], "graphql": []}
    for lvl in levels:
        rows = sources[lvl]
        for proto in ("rest", "graphql"):
            vals = [float(r["lat_p95"]) for r in rows
                    if r.get("concurrency") == lvl and r["protocol"] == proto and r["lat_p95"]]
            data[proto].append(statistics.median(vals) if vals else None)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    x = range(len(levels))
    for proto, marker, color in [("rest", "o", "tab:blue"), ("graphql", "s", "tab:orange")]:
        ys = data[proto]
        xs = [xi for xi, y in zip(x, ys) if y is not None]
        ys_clean = [y for y in ys if y is not None]
        ax.plot(xs, ys_clean, marker=marker, label=proto.upper(), color=color, linewidth=2, markersize=8)
    ax.set_xticks(list(x))
    ax.set_xticklabels(levels)
    ax.set_xlabel("Concurrency (target arrival rate, req/s)")
    ax.set_ylabel("Median Latency P95 (ms)")
    ax.set_title("REST vs GraphQL latency across concurrency levels\n"
                 "REST flat throughout; GraphQL gap widens sharply at VUS=100\n"
                 "(REST wins at every level, divergence emerges under high load)")
    ax.legend()
    plt.tight_layout()
    out = out_dir / "fig_concurrency_scaling.png"
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  Saved {out}")


def fig_roundtrip_savings(out_dir: Path) -> None:
    """page_latency_med vs page_size K -- the cleanest finding: REST scales
    ~linearly with K, GraphQL sub-linearly (round-trip consolidation)."""
    rows = load(ROOT / "results/phase2-batch-real/results.csv")
    sizes = ["1", "5", "10"]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for proto, marker, color in [("rest", "o", "tab:blue"), ("graphql", "s", "tab:orange")]:
        ys = []
        for k in sizes:
            vals = [float(r["page_latency_med"]) for r in rows
                    if r["protocol"] == proto and r["page_size"] == k and r["page_latency_med"]]
            ys.append(statistics.mean(vals) if vals else None)
        ax.plot([int(k) for k in sizes], ys, marker=marker, label=proto.upper(),
                 color=color, linewidth=2, markersize=8)
    ax.set_xlabel("Page size K (number of resources per page)")
    ax.set_ylabel("Mean page latency (ms)")
    ax.set_title("Round-trip savings: REST pays K round trips, GraphQL pays 1\n"
                 "(REST ~linear scaling, GraphQL sub-linear)")
    ax.set_xticks([1, 5, 10])
    ax.legend()
    plt.tight_layout()
    out = out_dir / "fig_roundtrip_savings.png"
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  Saved {out}")


def fig_cpu_efficiency_crossover(out_dir: Path) -> None:
    """cpu_mean vs page_size K -- shows GraphQL's RELATIVE CPU efficiency
    improving as K grows, reconciling the Lawi et al. (PB-12) divergence at
    K=1 with a workload-dependent explanation."""
    rows = load(ROOT / "results/phase2-batch-real/results.csv")
    sizes = ["1", "5", "10"]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for proto, marker, color in [("rest", "o", "tab:blue"), ("graphql", "s", "tab:orange")]:
        ys = []
        for k in sizes:
            vals = [float(r["cpu_mean"]) for r in rows
                    if r["protocol"] == proto and r["page_size"] == k and r["cpu_mean"]]
            ys.append(statistics.mean(vals) if vals else None)
        ax.plot([int(k) for k in sizes], ys, marker=marker, label=proto.upper(),
                 color=color, linewidth=2, markersize=8)
    ax.set_xlabel("Page size K (number of resources per page)")
    ax.set_ylabel("Mean CPU usage (%)")
    ax.set_title("CPU efficiency vs batch size\n(GraphQL's relative CPU cost shrinks as K grows -- cf. Lawi et al. 2021)")
    ax.set_xticks([1, 5, 10])
    ax.legend()
    plt.tight_layout()
    out = out_dir / "fig_cpu_efficiency_crossover.png"
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  Saved {out}")


def fig_network_profile_comparison(out_dir: Path) -> None:
    """lan vs constrained latency, boxplot."""
    core = load(ROOT / "results/phase2-core-real/results.csv")
    net = load(ROOT / "results/phase2-network-drillin/results.csv")
    import pandas as pd
    rows = []
    for r in core:
        rows.append({"network": "constrained", "lat_p95": float(r["lat_p95"]), "protocol": r["protocol"]})
    for r in net:
        rows.append({"network": "lan", "lat_p95": float(r["lat_p95"]), "protocol": r["protocol"]})
    df = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    sns.boxplot(data=df, x="network", y="lat_p95", hue="protocol", ax=ax)
    ax.set_title("Latency P95 under lan vs constrained network profiles")
    ax.set_ylabel("Latency P95 (ms)")
    plt.tight_layout()
    out = out_dir / "fig_network_profile_comparison.png"
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  Saved {out}")


def fig_entropy_concurrency_interaction(out_dir: Path) -> None:
    """cache_hit_rate vs concurrency, grouped by entropy -- shows the actual
    (non-eviction-driven) mechanism: more traffic = more reuse before TTL
    expiry, for both entropy levels, not a compounding-eviction effect."""
    rows = load(ROOT / "results/phase2-entropy-concurrency-interaction/results.csv")
    import pandas as pd
    data = []
    for r in rows:
        if r["caching"] == "on" and r["access_pattern"] == "zipfian" and r["cache_hit_rate"]:
            data.append({"entropy": r["entropy"], "concurrency": r["concurrency"],
                         "hit_rate": float(r["cache_hit_rate"])})
    if not data:
        print("  [skip] entropy x concurrency interaction: no data yet")
        return
    df = pd.DataFrame(data)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    sns.barplot(data=df, x="concurrency", y="hit_rate", hue="entropy", order=["1", "50"],
                hue_order=["low", "high"], ax=ax)
    ax.set_title("Entropy x Concurrency interaction (exploratory, PB-91)\n"
                 "Hit rate rises with concurrency at BOTH entropy levels --\n"
                 "traffic-volume effect, not compounding eviction (cache never saturates)")
    ax.set_ylabel("Achieved cache-hit rate")
    plt.tight_layout()
    out = out_dir / "fig_entropy_concurrency_interaction.png"
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  Saved {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="results/phase2-figures")
    args = ap.parse_args()
    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Generating figures...")
    fig_concurrency_scaling(out_dir)
    fig_roundtrip_savings(out_dir)
    fig_cpu_efficiency_crossover(out_dir)
    fig_network_profile_comparison(out_dir)
    fig_entropy_concurrency_interaction(out_dir)
    print(f"\nDone. Figures in {out_dir}")


if __name__ == "__main__":
    main()
