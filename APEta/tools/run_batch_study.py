"""
tools/run_batch_study.py
=========================
Runner BERDIRI SENDIRI utk sub-studi "batch" (N+1 round-trip avoidance, lihat
k6/load_batch.js). SENGAJA dipisah dari orchestrator/run_experiment.py: skema
hasil & metriknya (batch_wall_time per-K, bukan lat_p95 per-request) berbeda
unit analisisnya dari studi faktorial utama, dan run_plan.csv pipeline utama
adalah "kontrak tetap" (lihat make_run_plan.py) yang tidak boleh disenggol demi
menambah sumbu batch_k. Menulis ke file CSV TERPISAH (default
results/batch_study/results.csv), tidak menyentuh results/results.csv.

Memakai ulang helper start_server/wait_health/kill_tree dari
orchestrator.run_experiment (server REST/GraphQL TIDAK diubah -- batching
GraphQL memakai field alias pada query yang sudah ada, lihat load_batch.js).

Cara pakai (jalankan sekali PER profil jaringan -- terapkan tc/netem dulu,
lihat tools/netem.sh -- agar kolom network_profile konsisten dgn qdisc aktif):
    sudo tools/netem.sh apply lan
    python tools/run_batch_study.py \
        --pool-json scratch/synthetic.json \
        --batch-sizes 1,10,30,100 --densities medium --vus 10 --duration 30s \
        --n-measured 30 --network-profile lan \
        --output results/batch_study/results.csv
    sudo tools/netem.sh apply fast3g
    python tools/run_batch_study.py ... --network-profile fast3g \
        --output results/batch_study/results.csv   # file SAMA, baris ditambahkan
    sudo tools/netem.sh apply slow3g
    python tools/run_batch_study.py ... --network-profile slow3g \
        --output results/batch_study/results.csv
    sudo tools/netem.sh clear
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.config import Config  # noqa: E402
from orchestrator.run_experiment import (  # noqa: E402
    start_server, wait_health, wait_port_free, find_listening_pid, kill_tree, metric,
)

FIELDNAMES = [
    "run_uid", "protocol", "network_profile", "density", "batch_k", "vus", "run_index",
    "ts_start", "ts_end",
    "batch_wall_time_p50", "batch_wall_time_p95", "batch_wall_time_p99",
    "batch_payload_bytes_med", "throughput_rps", "error_rate", "k6_iterations",
]


def make_cfg(pool_json: str, host: str, port: int) -> Config:
    return Config(
        pool_json=pool_json, seed=42, n_warmup=0, n_measured=0, run_duration="0s",
        concurrency_levels=[], densities=[], patterns=[], host=host, port=port,
        session_id="batch-study", results_dir=PROJECT_ROOT / "results", pilot=False,
        pilot_patterns=[], pilot_densities=[], pilot_concurrency=[],
        enable_pinning=False, server_cores=None, k6_cores=None, sampler_core=None,
        impl_mode_rest="passthrough", impl_mode_graphql="typed",
    )


def run_k6_batch(protocol: str, density: str, batch_k: int, vus: int, duration: str,
                  base_url: str, summary_path: Path) -> tuple:
    env = os.environ.copy()
    env.update({
        "PROTOCOL": protocol, "DENSITY": density, "BATCH_K": str(batch_k),
        "VUS": str(vus), "DURATION": duration, "BASE_URL": base_url,
        "SUMMARY_FILE": str(summary_path),
    })
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    ts_start = time.time()
    result = subprocess.run(["k6", "run", str(PROJECT_ROOT / "k6" / "load_batch.js")],
                             cwd=PROJECT_ROOT, env=env,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ts_end = time.time()
    return ts_start, ts_end, result.returncode


def ensure_server(cfg: Config, protocol: str, current: dict) -> None:
    if current.get("protocol") == protocol and current.get("proc") and current["proc"].poll() is None:
        return
    if current.get("proc"):
        pid = current["proc"].pid
        kill_tree(pid)
        current["proc"] = None
    wait_port_free(cfg.host, cfg.port)
    log_path = cfg.results_dir / "logs" / f"batch_study_server_{protocol}.log"
    proc = start_server(cfg, protocol, log_path)
    wait_health(cfg.base_url)
    current["proc"] = proc
    current["protocol"] = protocol


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool-json", required=True)
    ap.add_argument("--batch-sizes", default="1,5,20")
    ap.add_argument("--densities", default="low,high")
    ap.add_argument("--vus", type=int, default=10)
    ap.add_argument("--duration", default="10s")
    ap.add_argument("--n-measured", type=int, default=5)
    ap.add_argument("--network-profile", default="unspecified",
                     help="Label dicatat per-baris (mis. lan/fast3g/slow3g) -- harus cocok dgn profil "
                          "tc/netem yang SEDANG AKTIF (lihat tools/netem.sh); skrip ini TIDAK menerapkan "
                          "netem sendiri, hanya mencatat label apa yang sedang berlaku saat run.")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--output", default=str(PROJECT_ROOT / "results" / "batch_study" / "results.csv"))
    args = ap.parse_args()

    batch_sizes = [int(x) for x in args.batch_sizes.split(",")]
    densities = [d.strip() for d in args.densities.split(",")]
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_dir = output_path.parent / "k6_summaries"

    cfg = make_cfg(args.pool_json, args.host, args.port)
    current_server: dict = {}
    new_file = not output_path.exists() or output_path.stat().st_size == 0

    with open(output_path, "a", newline="", encoding="utf-8") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=FIELDNAMES)
        if new_file:
            writer.writeheader()

        run_idx = 0
        for protocol in ("rest", "graphql"):
            ensure_server(cfg, protocol, current_server)
            for density in densities:
                for batch_k in batch_sizes:
                    for rep in range(args.n_measured):
                        run_idx += 1
                        summary_path = summary_dir / f"{protocol}_{density}_k{batch_k}_{rep}.json"
                        ts_start, ts_end, rc = run_k6_batch(
                            protocol, density, batch_k, args.vus, args.duration, cfg.base_url, summary_path)
                        if rc != 0 or not summary_path.exists():
                            print(f"  WARNING: k6 failed protocol={protocol} density={density} batch_k={batch_k} rep={rep}")
                            continue
                        data = json.loads(summary_path.read_text(encoding="utf-8"))
                        checks_pass_rate = metric(data, "checks", "rate")
                        error_rate = (1.0 - checks_pass_rate) if checks_pass_rate is not None else None
                        row = {
                            "run_uid": f"{args.network_profile}_{protocol[:1]}{density[:1]}{batch_k}_{rep}",
                            "protocol": protocol, "network_profile": args.network_profile,
                            "density": density, "batch_k": batch_k,
                            "vus": args.vus, "run_index": rep,
                            "ts_start": f"{ts_start:.3f}", "ts_end": f"{ts_end:.3f}",
                            "batch_wall_time_p50": metric(data, "batch_wall_time", "p(50)"),
                            "batch_wall_time_p95": metric(data, "batch_wall_time", "p(95)"),
                            "batch_wall_time_p99": metric(data, "batch_wall_time", "p(99)"),
                            "batch_payload_bytes_med": metric(data, "batch_payload_bytes", "med"),
                            "throughput_rps": metric(data, "iterations", "rate"),
                            "error_rate": error_rate,  # checks "rate" = fraksi LULUS, bukan gagal -- dibalik
                            "k6_iterations": metric(data, "iterations", "count"),
                        }
                        writer.writerow(row)
                        out_f.flush()
                        print(f"  protocol={protocol} density={density} batch_k={batch_k} rep={rep} "
                              f"wall_p95={row['batch_wall_time_p95']}")

    if current_server.get("proc"):
        kill_tree(current_server["proc"].pid)

    print(f"\nDone. Results written to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
