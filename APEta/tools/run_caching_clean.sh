#!/usr/bin/env bash
# tools/run_caching_clean.sh
# ===========================
# Launcher for the CLEAN caching core-grid session (phase2-core-clean):
# the rerun of the caching/core grid with k6/workload.js's "no graphql
# errors" body check in place (run-sesi-1 is demoted -- its error_rate=0
# hid in-band GraphQL errors that only a body check catches).
#
# Mirrors tools/run_mot_arm.sh's conventions exactly: strictly serial
# (one orchestrator, one cell / one server / one k6 at a time), same
# pinning map as mot-scenarios-core's env snapshot, seed 42, same DB,
# netns topology + env snapshot before the first run. 24 blocks x
# (1 warmup + 30 measured) x 90 s -- ~19 h based on phase2-core-real.
set -euo pipefail
cd "$(dirname "$0")/.."

export APE_GRID=core
export APE_SESSION_ID=phase2-core-clean
export APE_RESULTS_DIR="$PWD/results/phase2-core-clean"
export APE_ID_POOL_JSON="$PWD/scratch/id_pool.json"
export APE_RUN_DURATION=90s APE_N_WARMUP=1 APE_N_MEASURED=30 APE_SEED=42
export APE_ENABLE_PINNING=1 APE_SERVER_CORES=0-7 APE_K6_CORES=8-15 APE_SAMPLER_CORE=31
export APE_CPU_QUOTA_PCT=400

# Hard rule: never write into an existing results dir (silent-resume trap).
if [ -e "$APE_RESULTS_DIR/results.csv" ]; then
  echo "FATAL: $APE_RESULTS_DIR already has results.csv -- refusing to reuse" >&2
  exit 1
fi
mkdir -p "$APE_RESULTS_DIR"

if [ ! -f "$APE_RESULTS_DIR/run_plan.csv" ]; then
  venv/bin/python orchestrator/make_run_plan.py
fi

venv/bin/python orchestrator/run_experiment.py --preflight

NETNS_ENV="NETNS=${APE_NETNS_NAME:-ape-origin} VETH_HOST=${APE_NETNS_VETH_HOST:-veth-ape-h} \
VETH_NS=${APE_NETNS_VETH_NS:-veth-ape-n} IP_HOST=${APE_NETNS_HOST_IP:-10.200.0.1} IP_NS=${APE_NETNS_NS_IP:-10.200.0.2}"
sudo env $NETNS_ENV tools/netns_topology.sh up
# core grid runs network=constrained -- snapshot the qdisc the runs will see
sudo env $NETNS_ENV tools/netns_topology.sh apply-netem constrained
if [ ! -d "$APE_RESULTS_DIR/env_snapshot" ]; then
  APE_ID_POOL_JSON="$APE_ID_POOL_JSON" tools/env_snapshot.sh "$APE_RESULTS_DIR"
fi

exec venv/bin/python -u orchestrator/run_experiment.py
