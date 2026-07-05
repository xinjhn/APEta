# Study A vs Study B — audit of what exists on disk

Audited: 2026-07-03 (read-only; nothing modified, no runs touched).
Auditor scope: `results/`, code at commits `7c91a73` / `824b195` / `8b6c44b` / `83d364a`,
design docs, `laporan/`. All numbers below were computed from the actual CSVs
and logs on this VM, not from documentation claims.

**Live run notice:** `mot-scenarios-core` is RUNNING right now (tmux `mot-core`;
uvicorn `graphql_server:app` in netns `ape-origin` under systemd scope with
CPUQuota=400%, taskset 0-7; k6 `workload_mot.js` active). The "646/3240"
observation corresponds to this session at 2026-07-03T08:53:15 (block B0063);
at audit time it had advanced to 739/3240 (11:18:34) — progressing, not stalled.
It was left untouched.

---

## 1. Inventory and completeness

### Study A — "isolation" (DET, in-memory JSON pool, loopback, k6 closed-loop)

Code lineage: initial commit `7c91a73` (run-sesi-1, run-sesi-2) → audit-fix
commit `824b195` 2026-06-23 (factorial-A). Data: `results/inferensi_vcd.json`
(VisDrone-DET detections) loaded by `core/pool.py` into memory; servers on
loopback `127.0.0.1:8000`, no netns/netem; k6 `load.js` with `vus`+`duration`
(default closed-loop executor).

| Session | Where | Planned (measured) | Actual | % | Error rate | Dates | Status |
|---|---|---:|---:|---:|---|---|---|
| run-sesi-1 | `results/archive_run-sesi-1/` (+78 MB tarball at repo root) | 2,160 (plan 2,376 incl. 216 warmup) | 2,160 | 100% | 0 in all rows | Jun 20 22:17 → Jun 22 14:17 | **Complete** (but see §4 GraphQL in-band errors) |
| run-sesi-2 | `results/results.csv` (root; logs in `archive_pre_factorial/`) | 2,160 | 1,057 | 48.9% | 0 | Jun 22 15:00 → Jun 23 10:34 | **Aborted / censored.** 36 of 72 (pattern×density×concurrency×protocol) combos present; 35 with full n=30, 1 partial. The other half never started. |
| factorial-A | `results/factorial-A/` | 2,880 (plan 3,168 incl. 288 warmup) | 2,880 | 100% | 0 | Jun 23 22:29 → Jun 25 01:23 | **Complete.** 4 patterns × 3 densities × 4 concurrency (1/10/50/100) × 2 protocols × 30 runs; `impl_mode=passthrough` only. |
| factorial-B (typed/typed) | — | 2,880 (per design) | 0 | 0% | — | — | **Never run** (confirmed in `design/IMPL_MODE_JUSTIFICATION.md`). |
| pilots | `archive_pre_pilot/` (24/80), `archive_pilot_final/` (128/160) | — | — | — | 0 | Jun 20 | Pilot-scale, superseded. |

Run-sesi-1 and run-sesi-2 were intended as two replicate sessions of the same
36-cell design; only sesi-1 finished. All Study A sessions executed strictly
serially (0 overlapping run windows within each session).

### Study B — "realistic/MOT" (SQLite `mot_detections.db`, DAL, Varnish, netem, k6 open-loop)

Code lineage: commit `8b6c44b` ("experiments", Jun 30 — the phase2 code state)
and branch `mot-scenarios-impl` @ `83d364a` (live run; working-tree HEAD is
`eb0323a`, one commit ahead of the run's env snapshot). At `8b6c44b`,
`core/dal.py` is SQLite-only — **all phase2 sessions used the SQLite MOT DB**
(confirmed also by `/tracks/{id}/trajectory` traffic in their server logs).
k6 `workload.js` / `workload_mot.js`: `constant-arrival-rate` executor
(open-loop); the `concurrency` column in phase2 CSVs is a target arrival rate,
not VU count (per `orchestrator/run_experiment.py` comment).

| Session | Planned | Actual | % | Error rate | Dates | Concurrent sessions during its runs (see §4) |
|---|---:|---:|---:|---|---|---|
| phase2-pilot … v5 (5 sessions) | 48 each | 48 each | 100% | 0 | Jun 25–27 | serial (except v-pilots overlap none) |
| phase2-core-real | 720 | 720 | 100% | 0 | Jun 26 03:12 → 22:01 | **1 (fully serial)** |
| phase2-density-drillin | 720 | 720 | 100% | 0 | Jun 27 06:16 → Jun 28 16:01 | 1–8, varying |
| phase2-entropy-drillin | 1,440 | 1,440 | 100% | 0 | Jun 27 05:33 → Jun 29 10:33 | 1–8, varying |
| phase2-batch-pilot | 72 | 72 | 100% | 0 | Jun 28 | 2–3 |
| phase2-batch-real | 1,080 | 1,080 | 100% | 0 | Jun 28 03:36 → Jun 29 07:55 | 2–8, varying |
| phase2-core-cpu-rerun | 720 | 720 | 100% | 0 | Jun 28 05:03 → 23:55 | 4–8, varying |
| phase2-concurrency-drillin | 1,440 | 1,440 | 100% | 0 | Jun 28 05:05 → Jun 29 19:03 | 1–8, varying |
| phase2-network-drillin | 720 | 720 | 100% | 0 | Jun 28 05:04 → 23:55 | 5–8 |
| phase2-network-concurrency-interaction | 720 | 720 | 100% | 0 | Jun 28 05:18 → Jun 29 00:17 | 4–8 |
| phase2-entropy-concurrency-interaction | 1,440 | 1,440 | 100% | 0 | Jun 28 05:08 → Jun 29 19:06 | 1–8, varying |
| phase2-concurrency100-drillin | 720 | 720 | 100% | 0 | Jun 29 12:18 → Jun 30 07:40 | mostly 1; 234 runs at 3 |
| phase2-combined | — | 9,720 rows (union of the 10 "real" sessions above) | — | 0 | Jun 30 | aggregation only |
| mot-scenarios-calibration | probes | probes | — | — | Jul 2 | calibration only, excluded from analysis by design |
| **mot-scenarios-core** | **3,240** (plan 3,348 incl. 108 warmup) | **739 (and counting)** | **22.8%** | 0 | Jul 2 10:48 → **LIVE** | **1 (fully serial)** |

Of the 9,720 rows in `phase2-combined`, only the 720 from `phase2-core-real`
(7.4%) were collected with no other session running on the VM.

### Which study is fully analyzable today

- **Study A:** run-sesi-1 (2,160 runs) and factorial-A (2,880 runs) are 100%
  complete on disk today, with an existing statistical analysis for run-sesi-1.
  run-sesi-2 is censored at 48.9%. (Quality caveats in §4.)
- **Study B:** all 10 phase2 sessions are 100% complete (9,720 runs) with an
  existing statistical analysis; the MOT scenario session (`mot-scenarios-core`)
  is 22.8% complete and running.

### ETA for mot-scenarios-core (from measured rate, 2,501 runs remaining at 739)

| Basis | Rate | ETA |
|---|---|---|
| Whole-session average (Jul 2 10:50 → Jul 3 11:12) | 30.1 runs/h | ~83 h → **~Jul 6, late evening** |
| Last 6 h | 38.3 runs/h | ~65 h → **~Jul 6, early morning** |
| Orchestrator's own eta_min (11:18) | — | 3,793 min ≈ 63.2 h → ~Jul 6 ~02:30 |

So roughly **2.6–3.5 more days**, finishing ~Jul 5–7, assuming the rate holds
and the VM stays up. (A cron snapshot to `results-backup` branch and @reboot
resume were added in `eb0323a` per its commit message.)

---

## 2. Capability matrix — what each dataset can and cannot answer

| Capability | Study A (run-sesi-1 / factorial-A) | Study B phase2 (9,720) | Study B mot-scenarios-core (in progress) |
|---|---|---|---|
| Dataset shape | DET, flat detection arrays, in-memory pool (no DB) | MOT relational (image/detection/track) via shared `DetectionDAL` over SQLite | same MOT DB, scenario grid M1–M6 |
| DB-free "isolation" measurement | **Yes** (by construction) | No (SQLite in path) | No for the data on disk (an `APE_DATA_BACKEND=memory` toggle exists in current code and is parity-tested, but no memory-backend session has been run) |
| Partial-field over-fetching | Yes (`partial` vs `baseline` patterns) | Yes (`payload_weight`, access patterns) | Yes (M2 sparse vs M1 baseline) |
| Nested / relational round-trip | No | Partially (batch arm, `round_trip_count`) | **Yes by design** (M5 nested track = REST 2 calls vs GraphQL 1; M6 paged batch, K calls vs 1) |
| Caching measurement | No (no cache layer) | **Yes** (Varnish on/off, `cache_hit_rate`, APQ-over-GET) | No in this arm (caching=off only; design Q3 chose to lean on phase2 cache data) |
| Network profiles | No (loopback only) | Yes (netns+veth, netem `lan`/`constrained`) | `lan` only (5 ms ± 1 ms, 100 Mbit netem, verified in env snapshot) |
| Load model | Closed-loop (k6 default VU loop; coordinated-omission-prone) | Open-loop `constant-arrival-rate` | Open-loop `constant-arrival-rate`, incl. deliberate overload rate tier |
| Latency percentiles (p50/p95/p99), throughput, payload bytes | Yes | Yes | Yes |
| Server processing time (`xproc_p95/med`) | **Yes** (unique to Study A) | No | No |
| CPU / RSS telemetry | Yes | Yes | Yes |
| `cache_hit_rate` / `round_trip_count` / `apq_registrations` | No | Yes (hit-rate populated when caching=on) | round_trip_count yes; cache_hit_rate empty (caching off) |
| `dropped_iterations` (open-loop saturation signal) | n/a | Yes (all 0) | Yes (30 rows > 0, all in M1 GraphQL `r120_overload` — the designed overload tier) |
| typed vs passthrough impl axis | factorial-A = passthrough only; typed arm never run | Not applicable (servers dict-passthrough by construction, per `design/IMPL_MODE_JUSTIFICATION.md`) | same |

### Existing statistical analyses

- **Study A:** `results/analysis_session1_preliminary/ANALYSIS_SUMMARY.md`
  (on run-sesi-1's 2,160 runs): Shapiro-Wilk, Mann-Whitney U + Cliff's delta
  with BH-FDR, Jonckheere-Terpstra trends. Result recorded there: REST favored
  36/36 cells on lat_p95, throughput, payload, xproc. No equivalent analysis
  directory found for factorial-A (only `FACTORIAL_DESIGN_SUMMARY.md`).
- **Study B:** `results/phase2-combined/analysis/phase2_analysis_report.txt`
  (+ same report inside `phase2-core-real/analysis/`): per-cell Mann-Whitney U
  + Vargha-Delaney A12/Cliff's delta, Holm-corrected, 150 cells over 9,720 runs
  (e.g. lat_p50: 149/150 cells significant). Figures in `phase2-figures/`.
  **No analysis exists yet for mot-scenarios-core** (still running).

---

## 3. Validity signals (facts, no verdicts)

### Study B parallelism — the known open question

Reconstructed from `ts_start`/`ts_end` of every run in every session CSV
(cross-checked against progress.logs and per-session server logs):

- **Within every session, runs are strictly serial** (0 overlapping windows in
  all 17 sessions checked, Study A and B alike).
- **Across sessions, up to 8 sessions ran concurrently** on this VM. Peak of 8
  concurrent runs first reached 2026-06-28 05:18:54. Each parallel session had
  its own network namespace — server logs show 8 distinct client subnets
  (10.200.0.1 … 10.207.0.1), matching `tools/netns_topology.sh`'s documented
  multi-namespace mode — so networking/netem was isolated per session, but all
  sessions shared the same 32-core (AMD EPYC 7302) VM's CPUs, memory bus, and
  the same SQLite file.
- **Concurrency was NOT constant.** Per-session distribution of co-running
  sessions (sampled at each run's midpoint):
  - phase2-core-real: 1 for all 720 runs (clean).
  - phase2-density-drillin: from 1 up to 8 (332 of 720 runs at 8).
  - phase2-entropy-drillin: 1→8 varying across its 2-day window.
  - phase2-core-cpu-rerun (the CPU-metric rerun): 4–8 throughout — never serial.
  - network-drillin 5–8; network×concurrency 4–8; concurrency-drillin and
    entropy×concurrency 1–8; batch-real 2–8; concurrency100-drillin mostly 1
    with 234/720 runs at 3.
  - mot-scenarios-core (live): 1 for all runs so far (clean).
- Whether the parallel sessions pinned their servers to disjoint core sets is
  **not verifiable from disk**: phase2 sessions have no `env_snapshot/`
  (only mot-scenarios-core does). The live run pins server=0-7, k6=8-15,
  sampler=31 with CPUQuota=400%; distinct systemd scopes per session
  (`ape-server-<pid>`) and 21 per-scope varnish scratch dirs confirm separate
  server/varnish instances per session, but their core masks are unrecorded.

### Study A signals

- **Closed-loop executor** (`k6/load.js`: `vus` + `duration`, no `executor`
  set) — the coordinated-omission-prone load model; concurrency levels are VU
  counts (10/50/100; factorial-A adds 1).
- **run-sesi-1 GraphQL in-band errors:** the archived GraphQL server log
  (1.34 GB) contains **345,879** paired
  `ValueError: could not convert string to float: 'x1'` /
  `GraphQLError: Float cannot represent non numeric value: 'x1'` tracebacks
  (bounding_box field serialization), spanning from ~0.1% to **59.5%** of the
  log by byte offset, then stopping. GraphQL returns HTTP 200 for partial-error
  responses and `load.js`'s only check is `status === 200`, so these do not
  appear in `error_rate` (0 everywhere in the CSV). Total GraphQL iterations in
  run-sesi-1: 7,947,457 (of which baseline+filtered — the patterns whose
  selection includes `bounding_box` — total 3,297,716). How many *requests*
  the 345,879 field errors map to is not derivable from the log (one error per
  affected field occurrence, potentially several per response). Payload medians
  for the affected patterns look ordinary (GraphQL ≈ REST + ~30 B), so the
  responses were not empty; their per-field content during the error window is
  not verifiable from the CSVs. **run-sesi-2's GraphQL log has 0 such errors**,
  and **factorial-A's has 0** — the errors are unique to (part of) run-sesi-1.
  The existing Study A statistical analysis (§2) is computed over run-sesi-1.
- **Documented pre-fix asymmetries** (from `METHODOLOGICAL_VERIFICATION.md`,
  written Jun 23 after run-sesi-1/2): the pre-`824b195` GraphQL `partial`
  resolver built the full Detection object regardless of the selection set,
  while REST stripped fields before construction — i.e. run-sesi-1/2's GraphQL
  `partial` cells paid baseline-level server-side construction cost (wire
  payload unaffected). Fixed for factorial-A. factorial-A ran both protocols
  as `passthrough` (typed/typed factorial-B never run).
- Warmup: 3 discarded warmup runs per block (216 in sesi-1, 288 in factorial-A).
  Seed: env default 42. Duration: 30 s/run. Serial execution, single server at
  a time on port 8000 (one `server.pid` lock; the lock file still on disk is a
  stale Jun 23 artifact). CPU pinning is supported in the Phase-1 orchestrator
  but no per-session env record exists to confirm it was enabled for Study A
  sessions.

### Study B signals (other than parallelism)

- Open-loop executor with recorded `dropped_iterations` (all zero except the
  30 designed M1-GraphQL overload runs in mot-scenarios-core).
- mot-scenarios-core has a full `env_snapshot/` (git SHA, DB md5, id-pool md5,
  netem qdisc, k6 v2.0.0, pip freeze, seed 42, pinning map) — the only session
  with one.
- Warmup: 1 discarded warmup per block (per env: `APE_N_WARMUP=1`; phase2 plan
  vs. results row deltas match 1/block). 90 s runs (mot), seed 42.
- Servers alternated, never co-resident within a session (single scope per
  protocol, alternation documented as carried protocol in
  `design/SCENARIO_DESIGN.md`).
- MOT parity gate: `design/PARITY_REPORT_MOT.md` — 18 passed / 2 skipped
  (skips are sqlite-only SQL-log assertions on the memory backend), byte-level
  envelope deltas constant (19 B for M1–M3, 13 B M4); rate grid calibrated per
  protocol (`design/CALIBRATION.md`, probes excluded from analysis).
- mot-scenarios-core arm choices on record: reduced 3-rate grid, caching off,
  `lan` netem only (approved Q3/Q4/Q5 per `SCENARIO_DESIGN.md`); the caching
  axis for Study B therefore lives entirely in the phase2 sessions.
- error_rate = 0 in every row of every Study B session on disk.

---

## 4. Alignment with the approved RQs (mapping only)

Approved RQs (as given for this audit): (1) response time/throughput
**without database overhead**; (2) partial-field-selection over-fetching;
(3) transfer-vs-resource trade-off.

| RQ element | Study A | Study B |
|---|---|---|
| "Without database overhead" | Matches: in-memory pool, no DB in path | Does not match as-collected: SQLite in path for every stored run. Current code has a parity-tested `memory` backend toggle, but no session used it. |
| Partial-field over-fetching | Matches: `baseline` vs `partial` patterns, payload_bytes captured | Expressible (M1 vs M2 sparse; payload_weight in phase2) but framed inside a larger caching/entropy/network design |
| Transfer-vs-resource trade-off | Matches: payload_bytes + cpu/rss + `xproc` (server processing time) captured | Payload + cpu/rss captured; no `xproc` equivalent |
| RQ revision needed? | No — data was designed for these RQs | Yes — documented by the researcher's own migration audit (`laporan/phase2_migration/DRAFT_AUDIT_PHASE2.md`): title, RQs, scope ("tanpa basis data" → "SQLite read-only"), data-support section, and BAB III–V changes are listed as required. |

Note on the current draft state: `laporan/chapters/BAB_I_PENDAHULUAN_DRAFT.md`
§I.3 **already contains the revised, Study-B-shaped RQs** (caching, access
pattern, payload weight, query entropy; cache-hit and resource metrics) — i.e.
the thesis draft as it stands today is written toward Study B, while the
"approved" RQ set as stated above describes Study A. Choosing Study A would
mean the current BAB I draft text needs to be walked back; choosing Study B
means the approved RQ set needs formal revision. Both directions are documented
facts of the workspace, not recommendations.

---

## 5. Open gaps

### Study A
1. run-sesi-2 censored at 1,057/2,160; only 1 of 2 planned replicate sessions
   completed.
2. factorial-B (typed/typed) never run; the typed/passthrough axis is
   half-measured (factorial-A = passthrough only).
3. run-sesi-1's GraphQL arm contains 345,879 in-band field-serialization
   errors over roughly the first 60% of its server log (invisible to
   `error_rate`); the only existing Study A statistical analysis is built on
   this session. factorial-A is clean of these errors but has no analysis
   directory of its own.
4. run-sesi-1/2 predate the `824b195` fairness fixes (GraphQL `partial`
   construction-cost asymmetry documented by the researcher).
5. Closed-loop load model; no caching, network, or nested-query axes exist in
   the data.

### Study B
1. mot-scenarios-core is 22.8% complete; ~2.6–3.5 days of runtime remain
   (finishing ~Jul 5–7 at observed rates). No statistics for it yet.
2. 9,000 of the 9,720 phase2 rows (92.6%) were collected while 2–8 sessions
   ran concurrently on the same VM with non-constant concurrency; only
   phase2-core-real is contention-free. Per-session core-pinning during the
   parallel window is unrecorded (no env snapshots for phase2 sessions).
3. The caching axis exists only in the (parallelism-affected) phase2 data;
   the clean-execution MOT arm runs caching=off, `lan` only.
4. No memory-backend ("isolation") session exists in Study B, so the
   "without database overhead" phrasing of the approved RQs has no
   corresponding Study B data on disk.
5. mot-scenarios-core's env snapshot pins the run to `83d364a` while the
   working tree is one commit ahead (`eb0323a`, VM-loss mitigations) — a
   bookkeeping note for reproducibility statements.

*End of report. Facts only — the choice of which study to write up is the
researcher's.*
