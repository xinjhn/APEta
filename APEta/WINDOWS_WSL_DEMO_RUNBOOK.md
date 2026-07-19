# APE Windows/WSL Demo Runbook

This runbook demonstrates the APE MOT experiment locally on Windows through
WSL2 Ubuntu. It covers dataset profiling, ID-pool generation, REST/GraphQL
parity, experiment execution with `tmux`, result validation, statistical
analysis, and visualization.

> **Scope:** WSL results are suitable for demonstrations and functional
> verification. Do not combine them with the VM experiment results because
> the CPU topology, WSL scheduler, storage path, and software versions differ.

## 1. Enter Ubuntu WSL

Run this from PowerShell:

```powershell
wsl -d Ubuntu
```

All remaining commands are Bash commands run inside Ubuntu WSL.

## 2. Install dependencies

```bash
sudo apt-get update
sudo apt-get install -y \
  python3-venv python3-pip tmux varnish sqlite3 \
  iproute2 util-linux curl gnupg ca-certificates
```

Install k6 from its official Ubuntu repository:

```bash
curl -fsSL https://dl.k6.io/key.gpg |
  sudo gpg --dearmor -o /usr/share/keyrings/k6-archive-keyring.gpg

echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" |
  sudo tee /etc/apt/sources.list.d/k6.list

sudo apt-get update
sudo apt-get install -y k6
```

Enable the user-level systemd instance required by the orchestrator:

```bash
sudo loginctl enable-linger "$USER"
systemctl --user is-system-running
```

If the last command cannot connect, exit WSL and run this from PowerShell:

```powershell
wsl --shutdown
wsl -d Ubuntu
```

## 3. Prepare the workspace

```bash
cd '/mnt/d/TA/APE VM/APEta'

# Keep the Linux virtual environment on WSL's native filesystem. Creating it
# directly under /mnt/d can leave pip partially copied or otherwise corrupt.
mkdir -p "$HOME/.venvs"
python3 -m venv "$HOME/.venvs/apeta"
"$HOME/.venvs/apeta/bin/python" -m ensurepip --upgrade
"$HOME/.venvs/apeta/bin/python" -m pip install --upgrade pip
"$HOME/.venvs/apeta/bin/python" -m pip install -r requirements.txt pytest

# Project scripts expect venv/bin/python. Point that path at the native WSL
# environment. On a fresh setup, the first branch is skipped.
if [ -e venv ] || [ -L venv ]; then
  mv venv "venv.broken.$(date +%Y%m%d-%H%M%S)"
fi
ln -s "$HOME/.venvs/apeta" venv

DB='/mnt/d/TA/APE VM/training/mot_detections.db'
```

Check the required tools and files:

```bash
test -r "$DB" && echo "database: OK"
venv/bin/python --version
k6 version
varnishd -V
tmux -V
nproc
```

Confirm that Linux shell scripts use LF line endings. A Windows checkout
with CRLF endings makes `/usr/bin/env` look for `bash\r` and the namespace
launcher exits with status 127.

```bash
file tools/netns_topology.sh

# Run this only if `file` reports "with CRLF line terminators".
sed -i 's/\r$//' tools/*.sh
file tools/netns_topology.sh
```

If `varnishd: command not found` appears, install it before starting tmux:

```bash
sudo apt-get update
sudo apt-get install -y varnish
command -v varnishd
varnishd -V
```

The local machine has 12 logical CPUs. The local demonstration uses:

- Server: CPUs `0-3`
- k6: CPUs `4-9`
- Telemetry sampler: CPU `10`
- CPU `11` remains available for the host

## 3A. Optional dashboard

After completing the dependency and temporary-sudo setup in this runbook,
launch the local control panel from WSL:

```bash
cd '/mnt/d/TA/APE VM/APEta'

export APE_DB_PATH='/mnt/d/TA/APE VM/training/mot_detections.db'
export APE_RESULTS_DIR="$PWD/results/wsl-analysis-m6cache"

venv/bin/python tools/demo_ui.py
```

Open this address in Windows:

```text
http://localhost:8090
```

The dashboard provides fixed buttons for profiling, parity, experiment
start/stop, validation, and analysis; it also streams logs, reports progress
and median metrics, and displays generated figures. It does not accept shell
commands or passwords. Keep the dashboard terminal open while using it.

To record a completely fresh run instead of displaying/resuming the existing
54-row demo, choose a new session and results directory before launching:

```bash
export APE_SESSION_ID=wsl-ui-demo-02
export APE_RESULTS_DIR="$PWD/results/$APE_SESSION_ID"
venv/bin/python tools/demo_ui.py
```

## 4. Profile the MOT dataset

### Database-level counts

```bash
sqlite3 "$DB" <<'SQL'
.headers on
.mode column

SELECT 'sequence' AS entity, COUNT(*) AS records FROM sequence
UNION ALL
SELECT 'image', COUNT(*) FROM image
UNION ALL
SELECT 'track', COUNT(*) FROM track
UNION ALL
SELECT 'detection', COUNT(*) FROM detection
UNION ALL
SELECT 'class', COUNT(*) FROM "class";
SQL
```

Expected headline values:

- 7 sequences
- 2,846 images
- 5,429 tracks
- 104,767 detections
- 10 classes

### Image-density distribution

```bash
sqlite3 "$DB" <<'SQL'
.headers on
.mode column

SELECT density_tier, COUNT(*) AS image_count
FROM image
GROUP BY density_tier
ORDER BY CASE density_tier
  WHEN 'low' THEN 1
  WHEN 'medium' THEN 2
  WHEN 'high' THEN 3
END;
SQL
```

Expected density populations:

- Low: 579 images
- Medium: 1,555 images
- High: 712 images

### Detection class distribution

```bash
sqlite3 "$DB" <<'SQL'
.headers on
.mode column

SELECT
  class_id,
  COUNT(*) AS detection_count,
  ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM detection), 2) AS percentage
FROM detection
GROUP BY class_id
ORDER BY detection_count DESC;
SQL
```

Display the complete stored MOT profile:

```bash
venv/bin/python -m json.tool design/mot_profile.json | less
```

`tools/profile_dataset.py` is not used for the current MOT experiment. It
belongs to the retired JSON-based study.

## 5. Generate and inspect the experiment ID pool

```bash
venv/bin/python tools/build_id_pool.py \
  --db "$DB" \
  --out scratch/id_pool_mot.json
```

This creates:

- Image IDs for each density tier
- Eligible tracks for trajectory windows `W=2`, `W=8`, and `W=23`
- Fixed track pages for `K=1`, `K=5`, and `K=10`

Inspect the generated artifact:

```bash
ls -lh scratch/id_pool_mot.json
md5sum scratch/id_pool_mot.json
venv/bin/python -m json.tool scratch/id_pool_mot.json | less
```

## 6. Verify REST/GraphQL parity

```bash
APE_DB_PATH="$DB" \
venv/bin/python tests/test_parity_mot.py
```

The suite verifies:

- M1: full detections
- M2: sparse field projection
- M3: server-side filtering
- M4: aggregation
- M5: trajectories
- M6: batched track pages
- SQLite versus in-memory backend parity

Do not continue if the parity suite fails.

## 7. Start an analysis-capable local experiment

The statistical analyzer requires at least three measurements per protocol
group. The configuration below uses one warmup, three measured runs, and a
five-second duration. This is for demonstration only; the thesis experiment
uses 30 measured runs and 90 seconds per run.

Start tmux:

```bash
cd '/mnt/d/TA/APE VM/APEta'
tmux new-session -s ape-wsl-demo
```

The orchestrator launches the server in a detached process group. A cached
sudo password is not sufficient because that process has no terminal on
which to prompt. Create a temporary WSL-only sudo rule for the lifecycle
commands used by APE:

```bash
printf '%s\n' \
  "$USER ALL=(root) NOPASSWD: /usr/sbin/ip, /usr/bin/env, /usr/bin/kill, /usr/bin/true" |
  sudo tee /etc/sudoers.d/apeta-wsl-demo >/dev/null

sudo chmod 0440 /etc/sudoers.d/apeta-wsl-demo
sudo visudo -cf /etc/sudoers.d/apeta-wsl-demo

sudo -n true && echo "non-interactive sudo: OK"
sudo -n ip netns list
```

Do not proceed until `visudo` reports that the file parsed successfully and
the non-interactive check prints `OK`. Granting `/usr/bin/env` is powerful,
so this rule is intentionally temporary and should be removed after the
local demonstration.

Then paste the following commands. The `m6cache` arm is recommended because
it exercises REST, GraphQL, Varnish, k6, network emulation, telemetry, page
sizes, and multiple arrival rates.

For a much shorter recording that visibly executes **all six scenarios**, use
the separate `demo6` smoke arm. It runs REST and GraphQL for M1-M6 at one
representative middle tier and the r40 rate: 12 protocol/scenario cells, 0
warmups, 3 measured runs per cell, and 2-second windows. That is 36
measurements total, or 6 per scenario. This is still a short-window
demonstration, not a replacement for the full study:

```bash
cd '/mnt/d/TA/APE VM/APEta'
bash tools/start_wsl_demo6_ui.sh
```

Open <http://localhost:8090>, then click **Start**. Use **Validate** and
**Analyze** afterward for the demo flow, but describe the output as a smoke-run
visualization. Three observations per protocol meet the analyzer's minimum N,
and the latency figure overlays the individual runs on its boxes. Use
`APE_MOT_ARM=core` with the full tier/rate grid for an actual six-scenario
experiment.

```bash
# Do not enable `set -e` in the interactive tmux shell. A failed preflight
# would otherwise terminate the shell and make the entire tmux session vanish.
set -uo pipefail

cd '/mnt/d/TA/APE VM/APEta'

export APE_DB_PATH='/mnt/d/TA/APE VM/training/mot_detections.db'
export APE_ID_POOL_JSON="$PWD/scratch/id_pool_mot.json"

export APE_GRID=mot
export APE_MOT_ARM=m6cache
export APE_SESSION_ID=wsl-analysis-m6cache
export APE_RESULTS_DIR="$PWD/results/wsl-analysis-m6cache"

export APE_RUN_DURATION=5s
export APE_N_WARMUP=1
export APE_N_MEASURED=3
export APE_SEED=42

export APE_ENABLE_PINNING=1
export APE_DISABLE_NETEM=1
export APE_SERVER_CORES=0-3
export APE_K6_CORES=4-9
export APE_SAMPLER_CORE=10
export APE_CPU_QUOTA_PCT=400
export APE_RUN_AS_USER="$USER"

export APE_MOT_RATES_IMAGE=25,50,74
export APE_MOT_RATES_TRACK=25,50,74
export APE_MOT_RATES_PAGE=17,34,52

mkdir -p "$APE_RESULTS_DIR"

if [ ! -f "$APE_RESULTS_DIR/run_plan.csv" ]; then
  venv/bin/python orchestrator/make_run_plan.py
fi

if ! venv/bin/python orchestrator/run_experiment.py --preflight \
  2>&1 | tee "$APE_RESULTS_DIR/preflight.log"; then
  echo "Preflight failed. Read $APE_RESULTS_DIR/preflight.log before retrying."
else
  venv/bin/python -u orchestrator/run_experiment.py \
    2>&1 | tee -a "$APE_RESULTS_DIR/orchestrator_console.log"
fi
```

Detach without stopping the experiment:

```text
Ctrl+B, then D
```

The launcher is resumable. It uses `run_uid` values to skip measured rows
that are already recorded.

## 8. Monitor the experiment

```bash
tmux ls
tmux attach -t ape-wsl-demo
```

Capture recent output without attaching:

```bash
tmux capture-pane -pt ape-wsl-demo -S -50
```

Follow the console log:

```bash
tail -f results/wsl-analysis-m6cache/orchestrator_console.log
```

Show structured progress:

```bash
venv/bin/python orchestrator/run_experiment.py --status \
  --run-plan results/wsl-analysis-m6cache/run_plan.csv \
  --results results/wsl-analysis-m6cache/results.csv
```

To stop safely, attach to the session and press `Ctrl+C`.

## 9. Inspect raw results

```bash
RESULTS_DIR="$PWD/results/wsl-analysis-m6cache"

wc -l "$RESULTS_DIR/run_plan.csv"
wc -l "$RESULTS_DIR/results.csv"
head -n 5 "$RESULTS_DIR/results.csv"
find "$RESULTS_DIR" -maxdepth 2 -type f | sort
```

Important artifacts:

```text
run_plan.csv
results.csv
orchestrator_console.log
logs/
k6_summaries/
telemetry/
```

## 10. Validate result integrity

```bash
venv/bin/python tools/validate_results.py \
  --run-plan "$RESULTS_DIR/run_plan.csv" \
  --results "$RESULTS_DIR/results.csv"
```

The validator checks:

- Every planned measured run is present
- No unexpected or duplicate `run_uid` values exist
- Each cell has the expected repetitions
- Primary metrics are populated
- Error rates remain acceptable

A successful validation ends with:

```text
OK -- semua sel lengkap, tidak ada error_rate tinggi, tidak ada metrik primer kosong.
```

## 11. Run statistical analysis

```bash
venv/bin/python tools/analyze_mot_scenarios.py \
  --input "$RESULTS_DIR/results.csv" \
  --output-dir "$RESULTS_DIR/analysis"
```

The analysis performs:

- Per-cell Mann-Whitney U tests
- Holm-Bonferroni correction
- Vargha-Delaney A12
- Cliff's delta and effect-size classification
- Separate overload analysis

Show the report and comparison table:

```bash
sed -n '1,160p' "$RESULTS_DIR/analysis/mot_analysis_report.txt"
head -n 10 "$RESULTS_DIR/analysis/mot_comparisons.csv"
```

Analysis outputs:

```text
mot_analysis_report.txt
mot_comparisons.csv
fig_mot_latency_by_scenario.png
fig_mot_throughput_by_scenario.png
fig_mot_payload_by_scenario.png
fig_mot_round_trips_by_scenario.png
fig_mot_client_flow_latency.png
fig_mot_overload.png
```

## 12. Open visualizations in Windows

```bash
ls -lh "$RESULTS_DIR/analysis"/*.png
explorer.exe "$(wslpath -w "$RESULTS_DIR/analysis")"
```

The main MOT figures are:

- `fig_mot_latency_by_scenario.png`: REST versus GraphQL p95 latency
- `fig_mot_throughput_by_scenario.png`: achieved throughput as a percentage
  of each scenario/tier cell's configured request-rate target
- `fig_mot_payload_by_scenario.png`: measured REST versus GraphQL response
  payload size for each scenario
- `fig_mot_round_trips_by_scenario.png`: HTTP round trips per scenario
  iteration, highlighting the M5/M6 multi-request REST paths
- `fig_mot_client_flow_latency.png`: end-to-end client-visible latency for the
  multi-request M5/M6 flows
- `fig_mot_overload.png`: overload latency and achieved throughput

## 13. Optional archived Phase 2 visualizations

This command uses the existing archived Phase 2 datasets, not the new WSL
demonstration results:

```bash
venv/bin/python tools/visualize_phase2_full.py \
  --out-dir results/phase2-figures-demo

explorer.exe "$(wslpath -w "$PWD/results/phase2-figures-demo")"
```

It creates figures for:

- Concurrency scaling
- Round-trip savings
- CPU-efficiency crossover
- LAN versus constrained-network comparison
- Entropy-concurrency interaction

During the recording, label these as results from the previous complete
experiment. Label `wsl-analysis-m6cache` as the local end-to-end demo.

## 14. Simulate resume or reset results (optional)

For a short recording, click **Simulate skip** instead of **Start**. This runs
the orchestrator's real run-UID resume calculation in read-only mode and shows
which completed blocks would be skipped. It does not start services, run k6,
require sudo, or modify `results.csv`. The equivalent command is:

```bash
venv/bin/python orchestrator/run_experiment.py --simulate-resume \
  --run-plan "$RESULTS_DIR/run_plan.csv" \
  --results "$RESULTS_DIR/results.csv"
```

Use **Start** only when you want to capture new measurements.

The dashboard's **Reset results** button requires typing `RESET`. It moves the
current session into `results/.trash/<session>-<UTC timestamp>` and creates a
fresh empty session directory. It refuses to run while an experiment or other
dashboard workflow is active, so recorded results are never deleted in place.

## 15. Remove the temporary sudo rule

After the experiment has stopped and the namespace has been cleaned up:

```bash
sudo rm -f /etc/sudoers.d/apeta-wsl-demo
sudo -k
```

## 16. Suggested recording sequence

1. Show `design/mot_profile.json` and the SQLite counts.
2. Run `tools/build_id_pool.py` and explain density/window/page tiers.
3. Run `tests/test_parity_mot.py` and show the passing scenarios.
4. Start the tmux experiment and detach it.
5. Show `--status`, progress output, k6 summaries, and telemetry files.
6. Validate `results.csv` with `tools/validate_results.py`.
7. Run `tools/analyze_mot_scenarios.py`.
8. Show the report, statistical CSV, and generated PNG figures.
9. Optionally show the broader archived Phase 2 figures.
