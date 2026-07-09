# Paste-ready agent prompt (run on the VM)

Copy everything below the line into the agent session on the VM.

---

You are operating on the experiment VM for my D4 thesis (REST vs GraphQL benchmark).
Work at `/home/ubuntu/APE/APEta`. Corpus DB: `/home/ubuntu/training/mot_detections.db`.
Design docs that govern everything: `design/SCENARIO_DESIGN.md`, `design/CALIBRATION.md`,
`design/STUDY_COMPARISON.md`, `METHODOLOGICAL_VERIFICATION.md`.

## Established facts — verify, don't rediscover

- Session `results/mot-scenarios-core/` COMPLETED: its `orchestrator_console.log`
  ends with `run 29 ... (3240/3240)` then `[server] stop graphql` (~Jul 5).
  Expect `results.csv` = 3,241 lines (header + 3,240 measured rows) and 3,240
  k6 summary JSONs.
- My local Windows copy of this session is CORRUPT (results.csv truncated at
  exactly 524,288 bytes = 2,112 rows; every k6 summary synced as 0 bytes;
  `env_snapshot/ape_env.txt` empty). The VM is currently the ONLY holder of the
  complete data. Treat it as irreplaceable until Phase 2 below is done.
- `k6/workload_mot.js` HAS the `"no graphql errors"` body check;
  `k6/workload.js` (used by the caching/core grid) does NOT — only
  `status is 200`. The CSV `error_rate` column comes from k6 `http_req_failed`,
  so in-band GraphQL errors NEVER appear in it; they only appear in the k6
  summaries' checks section and in server logs. (Lesson from run-sesi-1, which
  hid 345,879 in-band errors behind error_rate=0.)
- `_run_uid()` hashes only `protocol|pattern|density|concurrency|is_warmup|run_index`
  — reusing an existing `APE_RESULTS_DIR` for a new session makes the resume
  logic mark everything "done" and exit instantly with zero rows written.
  NEVER reuse a results dir.

## Hard rules (each one maps to a past failure in this repo)

1. NEVER run two experiment sessions at once. Before starting anything:
   `tmux ls; pgrep -af 'uvicorn|k6|varnishd'` must show nothing experiment-related.
   (8-way parallel sessions previously contaminated 92.6% of phase2 data.)
2. NEVER write into an existing `results/*` directory. New session = new
   `APE_SESSION_ID` + new `APE_RESULTS_DIR`.
3. Do not modify, move, or delete anything under `results/` except ADDING new
   session dirs or analysis output dirs.
4. No new experimental axes, no design changes, no "improvements" to the grid.
   Scope is frozen: verify → back up → analyze → one clean caching session.
5. If any verification below fails, STOP that phase, record the failure in the
   report, and continue with the phases that don't depend on it. Do not
   improvise fixes to data.

## Phase 0 — Preconditions (read-only, ~5 min)

- Confirm nothing is running (rule 1).
- `git -C /home/ubuntu/APE status` and current SHA; note if the tree is dirty.
- Check whether the `results-backup` branch (cron snapshot added in commit
  `eb0323a`) already contains mot-scenarios-core's full results.csv.

## Phase 1 — Verify mot-scenarios-core integrity (read-only, ~20 min)

All in `results/mot-scenarios-core/`:

1. `wc -l results.csv` → expect 3,241. `md5sum results.csv` → record it.
2. Cell completeness with pandas: group by
   `(scenario, tier, rate_label, protocol)` → expect exactly 108 cells × 30
   runs each, no NaN cells. Also confirm `run_plan.csv` measured-run count
   matches 3,240.
3. Column sanity: `error_rate` == 0 in every row; `dropped_iterations` > 0
   ONLY in `rate_label == "r120_overload"` rows (expected there by design —
   note which cells).
4. In-band error audit: parse ALL 3,240 k6 summaries; for every file, every
   check must have `fails == 0` (both `status is 200` and, on GraphQL runs,
   `no graphql errors`). Report totals: files parsed / files with any failed
   check / total fails.
5. `grep -c` server logs (`logs/`) for `Traceback|ValueError|GraphQLError` —
   expect 0; report counts per log file.
6. Confirm `env_snapshot/` files are non-empty (git SHA, db_md5, pip freeze,
   netem qdisc, k6 version); confirm `db_md5.txt` matches
   `md5sum /home/ubuntu/training/mot_detections.db` today.

## Phase 2 — Back up and export (do BEFORE any new run)

1. `tar czf ~/mot-scenarios-core_FINAL.tar.gz -C /home/ubuntu/APE/APEta/results mot-scenarios-core`
   and `md5sum` the tarball. Do the same for `results/phase2-core-real` and
   `results/factorial-A` if they are not already in git.
2. Commit the full `results/mot-scenarios-core` contents (results.csv,
   run_plan.csv, k6_summaries, telemetry, env_snapshot, logs if size permits —
   if a log is >100 MB, gzip it first) to the `results-backup` branch and push.
3. Print the tarball path + md5 prominently in the report so I can download
   and verify it from Windows (`certutil -hashfile <file> MD5`).

## Phase 3 — Analysis (no new data needed)

1. Locate the analysis script used for `results/phase2-combined/analysis/`
   (per-cell Mann-Whitney U + Vargha-Delaney A12/Cliff's delta,
   Holm-corrected). Run the equivalent for mot-scenarios-core into
   `results/mot-scenarios-core/analysis/`, with these non-negotiable rules
   from `design/SCENARIO_DESIGN.md` / `config.py`:
   - NEVER pool `r120_overload` rows with r40/r80 (analyze the overload tier
     separately, per family, using `overload_saturates`).
   - Compare protocols per `(scenario, tier, rate_label)` cell.
   - Primary metric `lat_p95`; also `lat_p50`, `throughput_rps`,
     `payload_bytes_med`, `round_trip_count`, `cpu_mean`, `rss_mean_mb`;
     `page_latency_med` for M6.
2. Run the Study-A analysis pipeline (the one used for
   `results/analysis_session1_preliminary/`) on `results/factorial-A/`
   (2,880 clean runs) into `results/analysis_factorialA/`. This REPLACES the
   run-sesi-1-based numbers in my thesis; run-sesi-1 is demoted (hidden
   in-band errors).
3. Summarize per-RQ headline findings in the report (direction + effect sizes,
   which cells significant after Holm) — plain sentences, not just tables.

## Phase 4 — Clean caching session (the ONLY new data collection)

Gate: Phases 1–2 passed and nothing else running. The ~20–24 h time budget is
CONFIRMED — do not skip Phase 4 for time reasons. Skip ONLY if Phase 1 or 2
failed, and say exactly why in the report.

1. Patch `k6/workload.js`: add a `"no graphql errors"` check on GraphQL
   response bodies, mirroring `workload_mot.js`. CRITICAL nuance: the APQ flow
   legitimately receives `PERSISTED_QUERY_NOT_FOUND` error responses during
   hash registration — that registration response must NOT fail the check
   (follow how workload_mot.js structures it). REST branches keep status-only.
2. Smoke test: 10-minute mini-plan (2–3 blocks) into a throwaway results dir
   (`results/smoke-caching-check/`). Verify: rows written, checks present in
   summaries, zero fails, `/health` returns expected mode, Varnish serving on
   the cached base URL, `cache_hit_rate` populated when caching=on.
3. Launch the real session, strictly serial, in tmux:
   - `APE_GRID=core` (2 protocols × caching on/off × 3 access patterns ×
     2 payload weights = 24 cells, n=30 → 720 measured runs; ~19 h based on
     phase2-core-real)
   - `APE_SESSION_ID=phase2-core-clean`
     `APE_RESULTS_DIR=results/phase2-core-clean` (must not pre-exist)
   - `APE_ENABLE_PINNING=1` with the same core map as mot-scenarios-core's
     env snapshot (server 0-7, k6 8-15, sampler 31, CPUQuota=400%)
   - netns topology up (`tools/netns_topology.sh`), same seed 42, same DB.
   - Confirm the orchestrator writes an `env_snapshot/` for this session; if
     it doesn't automatically, create one the same way mot-scenarios-core's
     was made.
4. After the first ~30 min: check progress.log rate, confirm rows appearing,
   run the Phase-1-style check audit on the summaries so far, grep server log
   for tracebacks. Then let it run; check roughly hourly. When complete, run
   the same integrity audit (Phase 1 steps 1–5) + back up (Phase 2) + the
   per-cell analysis into `results/phase2-core-clean/analysis/`.

## Deliverable

Write `MORNING_RUN_REPORT.md` at `/home/ubuntu/APE/APEta/` containing:
- Phase 0–2 results: row counts, md5s, cell-completeness table, check-audit
  totals, backup locations (branch + tarball path + md5).
- Phase 3: where each analysis landed + the headline findings per RQ.
- Phase 4: launched or skipped (and why), ETA, and — if finished — its audit
  + analysis results.
- A verdict line per dataset: PASS / FAIL against the acceptance criteria
  above, and anything I must disclose in the thesis' threats-to-validity.

Commit the report (and the workload.js patch) with message
`Morning salvage: verify+backup mot-scenarios-core, factorial-A analysis, clean caching session`.
