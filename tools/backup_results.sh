#!/usr/bin/env bash
# tools/backup_results.sh
# ========================
# Cron-driven snapshot of the SMALL, thesis-critical result files into the
# `results-backup` branch (worktree ~/APE/APEta-backup), committed locally
# every run and pushed to origin when credentials exist (push failure is
# non-fatal: local history still accumulates and syncs on the first
# successful push). Never touches the experiment's own working tree.
#
# Bulky artifacts (k6_summaries/, telemetry/) are NOT snapshotted here --
# they get archived once per completed arm by the Stage-6/7 process.
set -u
SRC=/home/ubuntu/APE/APEta/results
WT=/home/ubuntu/APE/APEta-backup

for arm in core m6cache m5embed m1mem calibration; do
    d="$SRC/mot-scenarios-$arm"
    [ -d "$d" ] || continue
    out="$WT/backup/mot-scenarios-$arm"
    mkdir -p "$out"
    for f in results.csv run_plan.csv calibration.json orchestrator_console.log; do
        [ -f "$d/$f" ] && cp -f "$d/$f" "$out/"
    done
    [ -f "$d/logs/progress.log" ] && cp -f "$d/logs/progress.log" "$out/"
    [ -d "$d/env_snapshot" ] && cp -rf "$d/env_snapshot" "$out/"
done

cd "$WT" || exit 1
git add -A backup 2>/dev/null
if ! git diff --cached --quiet 2>/dev/null; then
    git commit -q -m "results snapshot $(date -Is)"
fi
# Push whatever local snapshot history exists; harmless no-op if up to date,
# silent skip if no credentials yet.
git push -q origin results-backup 2>/dev/null || true
