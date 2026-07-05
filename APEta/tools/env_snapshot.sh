#!/usr/bin/env bash
# tools/env_snapshot.sh <arm_results_dir>
# ========================================
# Environment snapshot taken into each MOT arm's results dir BEFORE its
# first measured run (Stage 5 protocol). Assumes the netns topology is up
# and the lan netem profile applied (so the tc dump shows the real qdisc
# the runs will see).
set -u
DIR="${1:?usage: tools/env_snapshot.sh <arm_results_dir>}"
OUT="$DIR/env_snapshot"
mkdir -p "$OUT"
cd "$(dirname "$0")/.."

date -Is                                   > "$OUT/timestamp.txt"
uname -a                                   > "$OUT/kernel.txt"
k6 version                                 > "$OUT/k6_version.txt" 2>&1
venv/bin/pip freeze                        > "$OUT/pip_freeze.txt"
venv/bin/python --version                  > "$OUT/python_version.txt" 2>&1
lscpu                                      > "$OUT/lscpu.txt"
free -m                                    > "$OUT/memory.txt"
{ cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor 2>/dev/null | sort | uniq -c; } \
                                           > "$OUT/cpu_governor.txt" || echo "no cpufreq" > "$OUT/cpu_governor.txt"
{ git rev-parse HEAD; git branch --show-current; git status --short; } \
                                           > "$OUT/git_state.txt"
md5sum "${APE_DB_PATH:-/home/ubuntu/training/mot_detections.db}" \
                                           > "$OUT/db_md5.txt"
md5sum "${APE_ID_POOL_JSON:-scratch/id_pool_mot.json}" \
                                           > "$OUT/id_pool_md5.txt"
tc qdisc show dev "${APE_NETNS_VETH_HOST:-veth-ape-h}" \
                                           > "$OUT/netem_qdisc.txt" 2>&1
env | grep '^APE_' | sort                  > "$OUT/ape_env.txt"
echo "[done] snapshot -> $OUT"
