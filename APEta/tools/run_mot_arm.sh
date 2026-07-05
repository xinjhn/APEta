#!/usr/bin/env bash
# tools/run_mot_arm.sh <core|m6cache|m5embed|m1mem>
# ==================================================
# Stage-5 launcher for one MOT scenario arm (GO 2026-07-02). Strictly
# serial by construction: it execs ONE orchestrator, which runs one cell /
# one server / one k6 at a time. Resume-safe: run_plan.csv is generated
# only once (fixed contract), results.csv appends by run_uid.
#
# Rates below are the Stage-3 calibrated values (design/CALIBRATION.md):
# {40%,80%,120%} of the lower protocol ceiling per family.
set -euo pipefail
cd "$(dirname "$0")/.."
ARM="${1:?usage: run_mot_arm.sh <core|m6cache|m5embed|m1mem>}"

export APE_GRID=mot APE_MOT_ARM="$ARM"
export APE_SESSION_ID="mot-scenarios-$ARM"
export APE_RESULTS_DIR="$PWD/results/mot-scenarios-$ARM"
export APE_ID_POOL_JSON="$PWD/scratch/id_pool_mot.json"
export APE_RUN_DURATION=90s APE_N_WARMUP=1 APE_N_MEASURED=30 APE_SEED=42
export APE_ENABLE_PINNING=1 APE_SERVER_CORES=0-7 APE_K6_CORES=8-15 APE_SAMPLER_CORE=31
export APE_MOT_RATES_IMAGE=25,50,74
export APE_MOT_RATES_TRACK=25,50,74
export APE_MOT_RATES_PAGE=17,34,52

mkdir -p "$APE_RESULTS_DIR"

if [ ! -f "$APE_RESULTS_DIR/run_plan.csv" ]; then
  venv/bin/python orchestrator/make_run_plan.py
fi

# Preflight FIRST (it tears the probe topology down when done) ...
venv/bin/python orchestrator/run_experiment.py --preflight

# ... then bring the real topology up with the lan profile so the env
# snapshot records the actual qdisc the runs will see (snapshot once per
# arm, before the first run -- not refreshed on resume).
NETNS_ENV="NETNS=${APE_NETNS_NAME:-ape-origin} VETH_HOST=${APE_NETNS_VETH_HOST:-veth-ape-h} \
VETH_NS=${APE_NETNS_VETH_NS:-veth-ape-n} IP_HOST=${APE_NETNS_HOST_IP:-10.200.0.1} IP_NS=${APE_NETNS_NS_IP:-10.200.0.2}"
sudo env $NETNS_ENV tools/netns_topology.sh up
sudo env $NETNS_ENV tools/netns_topology.sh apply-netem lan
if [ ! -d "$APE_RESULTS_DIR/env_snapshot" ]; then
  tools/env_snapshot.sh "$APE_RESULTS_DIR"
fi

exec venv/bin/python -u orchestrator/run_experiment.py
