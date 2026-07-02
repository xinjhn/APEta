#!/usr/bin/env bash
# tools/resume_current_arm.sh
# ============================
# @reboot recovery: find the first MOT arm (GO order core -> m6cache ->
# m5embed -> m1mem) whose run plan exists but whose measured rows are
# incomplete, and resume it inside tmux. Arms whose plan doesn't exist yet
# are NOT started -- launching a new arm remains a deliberate Stage-5/6/7
# decision, this script only resumes interrupted work.
set -u
cd /home/ubuntu/APE/APEta

for arm in core m6cache m5embed m1mem; do
    d="results/mot-scenarios-$arm"
    plan="$d/run_plan.csv"
    [ -f "$plan" ] || continue
    total=$(awk -F, 'NR>1 && $NF==0' "$plan" | wc -l)
    done_rows=0
    [ -f "$d/results.csv" ] && done_rows=$(($(wc -l < "$d/results.csv") - 1))
    if [ "$done_rows" -lt "$total" ]; then
        if ! tmux has-session -t "mot-$arm" 2>/dev/null; then
            tmux new-session -d -s "mot-$arm" \
                "tools/run_mot_arm.sh $arm 2>&1 | tee -a $d/orchestrator_console.log"
            echo "$(date -Is) resumed arm=$arm (done=$done_rows/$total)"
        fi
        exit 0
    fi
done
echo "$(date -Is) nothing to resume"
