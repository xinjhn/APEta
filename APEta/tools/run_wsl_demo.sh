#!/usr/bin/env bash
# Short, analysis-capable APE demo for Ubuntu WSL2.
# The VM experiment remains unchanged; this launcher uses a distinct results
# directory and disables netem because the stock WSL kernel lacks sch_netem.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export APE_DB_PATH="${APE_DB_PATH:-/mnt/d/TA/APE VM/training/mot_detections.db}"
export APE_ID_POOL_JSON="${APE_ID_POOL_JSON:-$ROOT/scratch/id_pool_mot.json}"
export APE_GRID=mot
export APE_MOT_ARM="${APE_MOT_ARM:-m6cache}"
export APE_SESSION_ID="${APE_SESSION_ID:-wsl-analysis-${APE_MOT_ARM}}"
export APE_RESULTS_DIR="${APE_RESULTS_DIR:-$ROOT/results/$APE_SESSION_ID}"

export APE_RUN_DURATION="${APE_RUN_DURATION:-5s}"
export APE_N_WARMUP="${APE_N_WARMUP:-1}"
export APE_N_MEASURED="${APE_N_MEASURED:-3}"
export APE_SEED="${APE_SEED:-42}"

export APE_ENABLE_PINNING="${APE_ENABLE_PINNING:-1}"
export APE_DISABLE_NETEM="${APE_DISABLE_NETEM:-1}"
export APE_SERVER_CORES="${APE_SERVER_CORES:-0-3}"
export APE_K6_CORES="${APE_K6_CORES:-4-9}"
export APE_SAMPLER_CORE="${APE_SAMPLER_CORE:-10}"
export APE_CPU_QUOTA_PCT="${APE_CPU_QUOTA_PCT:-400}"
export APE_RUN_AS_USER="${APE_RUN_AS_USER:-$USER}"

export APE_MOT_RATES_IMAGE="${APE_MOT_RATES_IMAGE:-25,50,74}"
export APE_MOT_RATES_TRACK="${APE_MOT_RATES_TRACK:-25,50,74}"
export APE_MOT_RATES_PAGE="${APE_MOT_RATES_PAGE:-17,34,52}"

mkdir -p "$APE_RESULTS_DIR"

echo "APE WSL demo: arm=$APE_MOT_ARM results=$APE_RESULTS_DIR"
echo "DEMO-ONLY: netem disabled; do not combine these results with VM data."

if ! sudo -n true >/dev/null 2>&1; then
  echo "ERROR: non-interactive sudo is unavailable."
  echo "Create /etc/sudoers.d/apeta-wsl-demo as documented in WINDOWS_WSL_DEMO_RUNBOOK.md."
  exit 2
fi

if [ ! -f "$APE_ID_POOL_JSON" ]; then
  echo "Building MOT ID pool..."
  venv/bin/python tools/build_id_pool.py --db "$APE_DB_PATH" --out "$APE_ID_POOL_JSON" || exit $?
fi

if [ ! -f "$APE_RESULTS_DIR/run_plan.csv" ]; then
  echo "Generating run plan..."
  venv/bin/python orchestrator/make_run_plan.py || exit $?
fi

echo "Running preflight..."
venv/bin/python orchestrator/run_experiment.py --preflight \
  2>&1 | tee "$APE_RESULTS_DIR/preflight.log"
preflight_rc=${PIPESTATUS[0]}
if [ "$preflight_rc" -ne 0 ]; then
  echo "ERROR: preflight failed (rc=$preflight_rc)."
  exit "$preflight_rc"
fi

echo "Starting resumable experiment..."
venv/bin/python -u orchestrator/run_experiment.py \
  2>&1 | tee -a "$APE_RESULTS_DIR/orchestrator_console.log"
exit ${PIPESTATUS[0]}
