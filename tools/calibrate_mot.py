#!/usr/bin/env python3
"""
tools/calibrate_mot.py
=======================
Stage-3 saturation-ceiling calibration for the MOT scenario study
(design/SCENARIO_DESIGN.md §5, approved Q4). CALIBRATION runs only --
labeled, written to their own results dir, excluded from analysis.

For each protocol x probe cell {M1-high, M5-w23, M6-k10} (the heaviest cell
of each scenario family), inside the SAME topology real runs will use
(netns + veth + `lan` netem, systemd-run CPU/memory caps, CPU pinning,
alternated single-worker server on port 8000):

  1. stepped-rate ladder of short open-loop k6 runs (constant-arrival-rate,
     k6/workload_mot.js -- the exact benchmark script), rate doubling from
     START_RATE until SATURATED;
  2. two bisection steps between the last clean and first saturated rate;
  3. ceiling = highest rate that ran clean.

SATURATED := dropped_iterations > 0 (the executor couldn't sustain the
target arrival rate) OR error rate > 1% OR p95 latency beyond the knee
threshold max(5 x baseline_p95, 150 ms) -- under an open-loop generator
p95 explodes by orders of magnitude past capacity, so any threshold in that
region finds the same knee; the exact constants only affect resolution.

Rate semantics: SCENARIO ITERATIONS per second (a "page" for M6 is one
iteration = K REST calls or 1 GraphQL call) -- the unit is identical across
protocols, which is what makes "lower of the two ceilings" meaningful.

Per scenario family the derived measured rates are {40%, 80%, 120%} of
min(rest_ceiling, graphql_ceiling), rounded to integers >= 1.

Usage:
    venv/bin/python tools/calibrate_mot.py \
        --out results/mot-scenarios-calibration
(needs passwordless sudo for ip netns, same as the orchestrator)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator import run_experiment as rx  # noqa: E402
from orchestrator.config import get_config  # noqa: E402

PROBES = (  # (scenario, tier, family) -- heaviest cell per family
    ("M1", "high", "image"),
    ("M5", "w23", "track"),
    ("M6", "k10", "page"),
)
PROTOCOLS = ("rest", "graphql")
START_RATE = 25
MAX_RATE = 3200
STEP_DURATION = "12s"
ERROR_RATE_LIMIT = 0.01
KNEE_FLOOR_MS = 150.0
KNEE_FACTOR = 5.0


def run_step(cfg, protocol: str, scenario: str, tier: str, rate: int,
             summary_path: Path) -> dict:
    env = os.environ.copy()
    env.update({
        "PROTOCOL": protocol,
        "BASE_URL": cfg.base_url_direct,
        "SCENARIO": scenario,
        "TIER": tier,
        "ACCESS_PATTERN": "uniform",
        "ID_POOL_JSON": cfg.id_pool_json,
        "VUS": str(rate),
        "DURATION": STEP_DURATION,
        "SUMMARY_FILE": str(summary_path),
        "ENTITY_OFFSET": "0",
    })
    cmd = ["k6", "run", str(PROJECT_ROOT / "k6" / "workload_mot.js")]
    if cfg.pinning_active() and cfg.k6_cores:
        cmd = ["taskset", "-c", cfg.k6_cores] + cmd
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, timeout=120)
    with open(summary_path, encoding="utf-8") as f:
        data = json.load(f)

    def metric(name, key):
        try:
            return data["metrics"][name]["values"][key]
        except KeyError:
            return None

    return {
        "rate": rate,
        "p50_ms": metric("req_latency", "p(50)"),
        "p95_ms": metric("req_latency", "p(95)"),
        "http_rps": metric("http_reqs", "rate"),
        "iterations": metric("iterations", "count"),
        "dropped_iterations": metric("dropped_iterations", "count") or 0,
        "error_rate": metric("http_req_failed", "rate") or 0.0,
        "checks_fail": (data["metrics"].get("checks", {}) or {}).get("values", {}).get("fails", 0),
    }


def saturated(step: dict, baseline_p95: float) -> tuple:
    reasons = []
    if step["dropped_iterations"] > 0:
        reasons.append(f"dropped_iterations={int(step['dropped_iterations'])}")
    if step["error_rate"] > ERROR_RATE_LIMIT:
        reasons.append(f"error_rate={step['error_rate']:.3f}")
    knee = max(KNEE_FACTOR * baseline_p95, KNEE_FLOOR_MS)
    if step["p95_ms"] is not None and step["p95_ms"] > knee:
        reasons.append(f"p95={step['p95_ms']:.1f}ms>knee={knee:.1f}ms")
    return (bool(reasons), ";".join(reasons))


def probe(cfg, executor: "rx.Executor", protocol: str, scenario: str, tier: str,
          out_dir: Path) -> dict:
    executor.ensure_server(protocol, "sqlite")
    executor.ensure_network("lan")
    curve = []
    baseline_p95 = None
    last_ok, first_bad = None, None

    def step_at(rate: int) -> dict:
        summary = out_dir / "k6_summaries" / f"cal_{protocol}_{scenario}_{tier}_r{rate}.json"
        s = run_step(cfg, protocol, scenario, tier, rate, summary)
        sat, why = saturated(s, baseline_p95 if baseline_p95 is not None else s["p95_ms"])
        s["saturated"] = sat
        s["saturation_reason"] = why
        curve.append(s)
        print(f"    rate={rate:>5} p50={s['p50_ms'] and round(s['p50_ms'],1)}ms "
              f"p95={s['p95_ms'] and round(s['p95_ms'],1)}ms dropped={int(s['dropped_iterations'])} "
              f"err={s['error_rate']:.3f} {'SATURATED('+why+')' if sat else 'ok'}")
        return s

    rate = START_RATE
    while rate <= MAX_RATE:
        s = step_at(rate)
        if baseline_p95 is None:
            baseline_p95 = s["p95_ms"]
        if s["saturated"]:
            first_bad = rate
            break
        last_ok = rate
        rate *= 2
    if first_bad is None:
        print(f"    no saturation up to {MAX_RATE} -- using {last_ok} as ceiling (conservative)")
    else:
        lo, hi = (last_ok or START_RATE // 2), first_bad
        for _ in range(2):  # two bisection steps
            mid = (lo + hi) // 2
            if mid in (lo, hi):
                break
            s = step_at(mid)
            if s["saturated"]:
                hi = mid
            else:
                lo = mid
                last_ok = mid
    return {"protocol": protocol, "scenario": scenario, "tier": tier,
            "baseline_p95_ms": baseline_p95, "ceiling_rate": last_ok,
            "first_saturated_rate": first_bad, "curve": curve}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/mot-scenarios-calibration")
    args = ap.parse_args()

    os.environ.setdefault("APE_SESSION_ID", "mot-calibration")
    os.environ.setdefault("APE_ID_POOL_JSON", str(PROJECT_ROOT / "scratch" / "id_pool_mot.json"))
    os.environ.setdefault("APE_RESULTS_DIR", str(PROJECT_ROOT / args.out))
    cfg = get_config()
    out_dir = Path(cfg.results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[netns] bringing up {cfg.netns_name}")
    rx.ensure_netns_topology(cfg)
    executor = rx.Executor(cfg, out_dir / "unused_results.csv")
    results = []
    t0 = time.time()
    try:
        for scenario, tier, family in PROBES:
            for protocol in PROTOCOLS:
                print(f"  [probe] {protocol} {scenario}-{tier} (family={family})")
                r = probe(cfg, executor, protocol, scenario, tier, out_dir)
                r["family"] = family
                results.append(r)
    finally:
        executor.shutdown()

    families = {}
    for family in ("image", "track", "page"):
        ceilings = {r["protocol"]: r["ceiling_rate"] for r in results if r["family"] == family}
        lower = min(v for v in ceilings.values() if v)
        families[family] = {
            "ceilings": ceilings,
            "lower_ceiling": lower,
            "rates": {"r40": max(1, round(0.4 * lower)),
                      "r80": max(1, round(0.8 * lower)),
                      "r120_overload": max(1, round(1.2 * lower))},
        }

    out = {"calibrated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "topology": "netns+veth, netem lan (5ms +/-1ms, 100mbit), CPUQuota "
                       f"{cfg.cpu_quota_pct}%, MemoryMax {cfg.memory_max_mb}M, "
                       f"pinning server={cfg.server_cores} k6={cfg.k6_cores}",
           "step_duration": STEP_DURATION,
           "saturation_rule": f"dropped>0 or err>{ERROR_RATE_LIMIT} or "
                              f"p95>max({KNEE_FACTOR}x baseline, {KNEE_FLOOR_MS}ms)",
           "probes": results, "families": families,
           "elapsed_s": round(time.time() - t0, 1)}
    out_path = out_dir / "calibration.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\n[done] {out_path}")
    for fam, f in families.items():
        print(f"  {fam}: ceilings={f['ceilings']} -> lower={f['lower_ceiling']} rates={f['rates']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
