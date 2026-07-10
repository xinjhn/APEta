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

# Every session/arm directory under results/, not just the MOT arms: the
# per-run results.csv and the derived analysis/ CSVs are what the laporan
# cites, and they are small; the bulky raw dirs are excluded by the
# whitelist below.
for d in "$SRC"/*/; do
    d="${d%/}"
    arm="$(basename "$d")"
    out="$WT/backup/$arm"
    mkdir -p "$out"
    for f in results.csv run_plan.csv calibration.json orchestrator_console.log; do
        [ -f "$d/$f" ] && cp -f "$d/$f" "$out/"
    done
    [ -f "$d/logs/progress.log" ] && cp -f "$d/logs/progress.log" "$out/"
    [ -d "$d/env_snapshot" ] && cp -rf "$d/env_snapshot" "$out/"
    [ -d "$d/analysis" ] && cp -rf "$d/analysis" "$out/"
    rmdir "$out" 2>/dev/null || true   # drop dirs that yielded nothing (raw-only)
done

# Small top-level derived-output dirs (each <1 MB): early-session analysis,
# phase2 figure exports, and the visualize/ analysis scripts.
for extra in analysis_factorialA analysis_session1_preliminary phase2-figures visualize; do
    if [ -d "$SRC/$extra" ]; then
        mkdir -p "$WT/backup/$extra"
        cp -rf "$SRC/$extra/." "$WT/backup/$extra/"
    fi
done

cd "$WT" || exit 1
git add -A backup 2>/dev/null
if ! git diff --cached --quiet 2>/dev/null; then
    git commit -q -m "results snapshot $(date -Is)"
fi
# Push whatever local snapshot history exists; harmless no-op if up to date,
# silent skip if no credentials yet.
git push -q origin results-backup 2>/dev/null || true
