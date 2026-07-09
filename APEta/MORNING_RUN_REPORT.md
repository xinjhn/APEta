# MORNING RUN REPORT — 2026-07-09

Session goal: verify + back up `mot-scenarios-core`, replace run-sesi-1-based
analysis with `factorial-A`, launch the one clean caching session
(`phase2-core-clean`) with the in-band GraphQL error check in place.

---

## Verdicts (one line per dataset)

| Dataset | Verdict | Notes |
|---|---|---|
| `results/mot-scenarios-core` | **PASS** | all acceptance criteria met; 2 disclosures below |
| `results/factorial-A` | **PASS** (analysis rerun) | replaces run-sesi-1 numbers |
| `results/phase2-core-real` | backed up (tarball) | not re-audited today (out of scope) |
| run-sesi-1 | **DEMOTED** | hidden in-band errors; superseded by factorial-A + phase2-core-clean |
| `results/phase2-core-clean` | LAUNCHED — see Phase 4 | audit pending completion |

---

## Phase 0 — Preconditions

- **Nothing running:** `tmux ls` — no server; `pgrep -af 'uvicorn|k6|varnishd'` — no experiment processes.
- **Git:** HEAD `3b629b0` on `main`. Tree dirty: `APEta/.gitignore` modified, `APEta/results/` untracked (expected — results are backed up via the `results-backup` worktree branch, not main).
- **`results-backup` branch** (worktree `~/APE/APEta-backup`, cron `*/30`): already held mot-scenarios-core's **full `results.csv` (3,241 lines, md5 identical to live copy)**, `run_plan.csv`, `env_snapshot/`, console + progress logs — but NOT `k6_summaries/`, `telemetry/`, or server logs. Completed in Phase 2.
- Cron backup job is healthy; it stopped committing after Jul 6 05:00 simply because nothing changed since the run finished.

## Phase 1 — mot-scenarios-core integrity: **PASS**

All in `results/mot-scenarios-core/`:

1. **results.csv**: 3,241 lines (header + 3,240) ✅ — md5 `94866487d535a014f185cafe0679acb5`.
2. **Cell completeness** (pandas, group by scenario×tier×rate_label×protocol): **108 cells × exactly 30 runs** ✅, no missing cells. `run_plan.csv`: 3,348 rows = 108 warmup + 3,240 measured ✅. NaN columns are only the axes this grid doesn't use (entropy/payload_weight/density/cache_hit_rate all-NaN by design; `overload_saturates` empty on sub-saturation rows by design; `page_latency_med` populated exactly for M5+M6, the multi-request flows).
3. **Column sanity**: `error_rate == 0` in all 3,240 rows ✅. `dropped_iterations > 0` in **91 rows, all `r120_overload`** ✅ (none outside): M1-high/graphql ×30, M5-w23/graphql ×30, M6-k10/rest ×30, M4-high/rest ×1. Expected by design — the overload rate exceeds the ceiling-defining protocol's capacity in the heaviest tiers; `notes` carries the per-run counts.
4. **In-band error audit**: all **3,240/3,240 k6 summaries parsed, 0 files with any failed check, 0 total fails**. `status is 200` present in all 3,240; `no graphql errors` present in exactly the 1,620 GraphQL runs ✅.
5. **Server logs** (2.8 GB): `Traceback` / `ValueError` / `GraphQLError` = **0 / 0 / 0** in `server_graphql.log` (1.7 GB), `server_rest.log` (1.1 GB), `progress.log` ✅.
6. **env_snapshot**: all files non-empty **except `cpu_governor.txt` (0 bytes — VM exposes no cpufreq; disclose, harmless)**. k6 v2.0.0, git SHA `83d364a` (mot-scenarios-impl), netem `delay 5ms 1ms rate 100Mbit` (lan) recorded.
   **DB md5 finding (disclose):** `db_md5.txt` = `5db8d5ca…` but today's `/home/ubuntu/training/mot_detections.db` = `f621173e…`. Root cause: on Jul 7 `/home/ubuntu/training` became a **symlink** to `/home/ubuntu/APE/training` (re-copied tree; original preserved at `~/training.bak-presymlink/`, whose file md5 matches the snapshot exactly). **Logical content verified identical**: `sqlite3 .dump | md5sum` = `cdb7c9f42b03fbfda82b004ddf6dc576` for BOTH files, same table counts. The corpus itself is unchanged; only the physical file bytes/location moved after the run. Thesis disclosure: verify DB identity by logical dump hash, not file hash.

## Phase 2 — Backup (done BEFORE any new run)

Tarballs in `/home/ubuntu/` — verify from Windows with `certutil -hashfile <file> MD5`:

```
a2241acfb1e7b7b133416ddb90c662ae  mot-scenarios-core_FINAL.tar.gz   (115 MB)
953a809c8165973a4f4a5d2b468021e5  phase2-core-real_FINAL.tar.gz     (3.9 MB)
5c9a5ff331fe46b1b32c411f72f0191f  factorial-A_FINAL.tar.gz          (35 MB)
```

(md5 list also saved at `~/FINAL_tarballs.md5`.)

**Git:** commit `0e84cc8` on `results-backup`, **pushed to origin** — adds `k6_summaries/` (3,240 JSONs), `telemetry/`, and gzipped server logs (56 MB + 60 MB, under GitHub's 100 MB cap) to the already-present results.csv/run_plan/env_snapshot. The branch now holds the ENTIRE mot-scenarios-core session; the VM is no longer the only holder of the complete data.

## Phase 3 — Analysis

### 3a. mot-scenarios-core → `results/mot-scenarios-core/analysis/`

New script `tools/analyze_mot_scenarios.py` (same methodology as `tools/analyze_phase2.py` — per-cell Mann-Whitney U + Vargha-Delaney A12/Cliff's delta, Holm-corrected — with the MOT rules enforced: cells = scenario×tier×rate_label, **r120_overload never pooled with r40/r80**, overload analyzed in separate Holm families per scenario family (image/track/page) with `overload_saturates` carried through; `round_trip_count` reported descriptively where constant-by-design). Outputs: `mot_analysis_report.txt`, `mot_comparisons.csv`, `fig_mot_latency_by_scenario.png`, `fig_mot_overload.png`.

**Headline findings:**

- **RQ1 (protocol difference, M1–M4 sub-saturation):** REST wins essentially everywhere. lat_p95: 36/36 sub-saturation cells significant after Holm, all REST-favored, median |Cliff's delta| = 1.0 (complete separation). Median GraphQL/REST p95 ratio: M1 ≈ 2.0×, M2 ≈ 1.7×, M3 ≈ 1.9×, M4 ≈ 1.5× (range 1.46–3.14 across tiers). Same direction for lat_p50 (36/36), CPU (34/36 REST-favored), RSS (31/36). Per-request payload is near-parity by construction on M1–M4 (GraphQL/REST ratio 0.98–1.22 — the envelope, not over-fetching).
- **RQ2 (multi-round-trip consolidation, M5/M6):** per-HTTP-request metrics still favor REST (M5/M6 p95 ratios ~2.0–2.2×), but **page-level latency flips to GraphQL exactly where the design predicts**: `page_latency_med` GraphQL-favored in M6 k5/k10 at both r40 and r80 (e.g. k10: REST ~75–80 ms vs GraphQL ~20 ms per page, |delta|=1.0) and CPU at M6-k10 also flips to GraphQL. M5 (2 REST round trips vs 1 GraphQL query) is nearly a wash at the page level (w2/r40 marginally GraphQL-favored) — REST's 2 fast calls ≈ GraphQL's 1 slow call.
- **RQ3 (conditions where GraphQL closes the gap / overload):** at the family overload rate, **M6-k10 REST collapses while GraphQL doesn't**: REST per-request p95 1,603 ms vs GraphQL 37.8 ms; page latency REST **13.1 s** vs GraphQL **20 ms**; REST CPU 168% vs 79%; RSS 177 MB vs 61 MB. This is the k-round-trips amplification under saturation (`overload_saturates=rest` — the page family's rate was set by REST's lower per-page ceiling; at 120% of it, REST's k10 sub-request fan-out is 10× the arrival rate). Conversely in image/track families (`overload_saturates=graphql`) GraphQL is the protocol that saturates (M1-high/M5-w23 GraphQL drops iterations and loses throughput: e.g. M5 achieved 148 rps REST vs 64.8–74 rps GraphQL). **The overload story is symmetric: whichever protocol defined the family ceiling degrades first — but the failure mode is much more dramatic for REST-under-k10 (13 s pages) than for GraphQL (throughput clipping).**

### 3b. factorial-A → `results/analysis_factorialA/`

Ran the Study-A pipeline (`results/visualize/analyze.py` + `plots.py`, the same one that produced `analysis_session1_preliminary/`) on `results/factorial-A/results.csv` (2,880 clean runs, 48 cells, passthrough). **This replaces the run-sesi-1-based numbers in the thesis.**

- **188/192 pairwise comparisons significant after BH-FDR.** lat_p95: 48/48 REST-favored; throughput: 48/48 REST-favored; xproc_p95: 48/48 REST-favored; payload: 44/48 significant, 46 REST-favored (the 2 GraphQL-favored cells are non-significant).
- Magnitudes: median GraphQL/REST lat_p95 ratio by pattern — aggregate 3.6×, filtered 2.9×, partial 2.7×, baseline 2.7× (max 7.1× at aggregate/high-concurrency). Server-side processing (xproc_p95) ratios 3.1–4.7× — the gap is execution cost, not payload (payload ratios ~1.0–1.1).
- Trends (Jonckheere-Terpstra): lat_p95 increases monotonically with concurrency for BOTH protocols in all 12 pattern×density panels (JT p ≈ 1e-36), with the REST-vs-GraphQL gap already at |delta|=1.0 at every concurrency level — the gap does not close anywhere in this grid.
- Normality: 49% of groups non-normal (Shapiro-Wilk) — non-parametric choice justified.

### 3c. Where this leaves the thesis narrative

Sub-saturation, per-request: REST is uniformly faster on this stack (Strawberry/GraphQL execution overhead dominates; payload near-parity by design). GraphQL's measurable wins are **structural, not per-request**: (a) page-level latency whenever one composite query replaces K≥5 REST round trips (M6), (b) graceful behavior when REST's round-trip fan-out saturates under overload, (c) CPU at high K. That is precisely the H-under-fetching mechanism, now demonstrated with clean data and effect sizes of 1.0.

## Phase 4 — Clean caching session (phase2-core-clean)

- **Gate:** Phases 1–2 PASSED; nothing else running → **launched**.
- **4a. workload.js patch:** added `"no graphql errors"` body check to BOTH GraphQL paths in `k6/workload.js` (single-resource `gqlRequest` path and `gqlPageRequest`), mirroring `workload_mot.js`: the check runs on the FINAL response only, i.e. after the APQ registration retry has replaced any legitimate `PERSISTED_QUERY_NOT_FOUND` reply — registration cannot fail the check. REST branches unchanged (status-only).
- **4b. Smoke test** (`results/smoke-caching-check/`, throwaway): 3 blocks (graphql+cache-on/zipfian/heavy, rest+cache-on/uniform/heavy, graphql+cache-off/unique/light), 20 s runs, n=3 → **PASS on every criterion**:
  - 9/9 rows written, `error_rate=0` everywhere, no dropped iterations.
  - k6 summaries: 9/9 parsed, **0 failed checks**; `no graphql errors` present in exactly the 6 GraphQL runs.
  - `/health` gating is built into every server start (`wait_health`) and all servers came up; Varnish served on the cached base URL — `cache_hit_rate` populated exactly when caching=on (GraphQL zipfian ≈ 0.31–0.35, REST uniform ≈ 0.02–0.03) and `None` when off.
  - Server logs: 0 Tracebacks / GraphQLErrors.
  - **APQ nuance verified directly** (measured smoke runs had `apq_registrations=0` because the warmup had already registered all hashes, so I forced the path): fresh server with empty APQ store + 10 s k6 run → `apq_registrations=7`, `no graphql errors` **51 passes / 0 fails** — registration does NOT trip the check. Negative control: an invalid-field query returns **HTTP 200 with an in-band `"errors"` body** (curl-verified) — exactly the class of failure `error_rate` cannot see and the new check catches.
- **4c. Real session: LAUNCHED** at 2026-07-09 04:38 UTC in tmux session `phase2-core-clean` via new launcher `tools/run_caching_clean.sh` (mirrors `run_mot_arm.sh`): `APE_GRID=core`, `APE_SESSION_ID=phase2-core-clean`, `APE_RESULTS_DIR=results/phase2-core-clean` (fresh dir, launcher hard-refuses a pre-existing results.csv), 24 blocks × (1 warmup + 30 measured) × 90 s, seed 42, same DB, `APE_ENABLE_PINNING=1` server 0–7 / k6 8–15 / sampler 31 / CPUQuota 400%, netns topology + constrained netem. Preflight: all PASS. `env_snapshot/` written automatically by the launcher (db_md5 = today's `f621173e…`, id_pool md5, git state incl. the workload.js patch, netem qdisc, k6 version). Pinning verified live: uvicorn worker affinity 0–7, k6 affinity 8–15. **ETA ≈ 23:30 UTC 2026-07-09 (~19 h, based on phase2-core-real's 18h48m).**
- **4d. Post-launch checks:** RESULTS_PLACEHOLDER_MONITOR

## Threats-to-validity disclosures (add to thesis)

1. **DB file relocation post-run** (mot-scenarios-core): file md5 changed Jul 7 because `/home/ubuntu/training` became a symlink to a re-copied tree; logical dump hash proven identical (`cdb7c9f4…`). No effect on data; disclose the verification method.
2. **`cpu_governor.txt` empty** in the env snapshot — the VM exposes no cpufreq interface; CPU frequency scaling state is unrecorded (cloud VM, governor not under guest control).
3. **Overload asymmetry by design**: `r120_overload` = 120% of the LOWER protocol ceiling per family; lighter-tier overload cells may not saturate either protocol (design/CALIBRATION.md). Never compare overload cells across families.
4. **`round_trip_count` is a design descriptor** (REST=2 in M5, =K in M6), not a measured outcome — excluded from hypothesis testing.
5. **Effective N for cross-scene claims is ~7** (7 MOT sequences), not the row count.
6. run-sesi-1 is excluded from all thesis numbers (in-band GraphQL errors invisible to `error_rate`); factorial-A (2,880 runs, clean audit) is the Study-A dataset; phase2-core-clean (with the body check) supersedes the caching-grid data.
