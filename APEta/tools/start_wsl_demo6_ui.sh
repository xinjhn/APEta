#!/usr/bin/env bash
# Launch the dashboard for a fast, demonstration-only M1-M6 smoke run.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export APE_DB_PATH="${APE_DB_PATH:-/mnt/d/TA/APE VM/training/mot_detections.db}"
export APE_GRID=mot
export APE_MOT_ARM=demo6
export APE_SESSION_ID="${APE_SESSION_ID:-wsl-demo6-n3}"
export APE_RESULTS_DIR="${APE_RESULTS_DIR:-$ROOT/results/$APE_SESSION_ID}"
export APE_RUN_DURATION="${APE_RUN_DURATION:-2s}"
export APE_N_WARMUP="${APE_N_WARMUP:-0}"
export APE_N_MEASURED="${APE_N_MEASURED:-3}"
export APE_DISABLE_NETEM=1

echo "Starting APE dashboard: demo6 arm, M1-M6, 12 cells x 3 measured = 36 runs"
echo "Results: $APE_RESULTS_DIR"
exec "$ROOT/venv/bin/python" "$ROOT/tools/demo_ui.py" "$@"
