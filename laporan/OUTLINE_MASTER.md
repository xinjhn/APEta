# OUTLINE MASTER — Dasar Teori · Metodologi · Analisis Hasil

Generated 2026-07-04 by read-only workspace scan. **Outlines only — no chapter
prose.** Every node carries (a) the RQ or role it serves and (b) its on-disk
source, or an honest gap flag.

Tag legend:
- `[RQ1]` protocol difference (latency/throughput/CPU/RSS) over shared DAL,
  across query complexity (M1–M4) and object density → data: `APEta/results/mot-scenarios-core/`
- `[RQ2]` round-trip consolidation & crossover — M5 nested trajectory, M6 paged
  fetch (REST K calls vs GraphQL 1) → data: `mot-scenarios-core` M5/M6. **MAIN CONTRIBUTION.**
- `[RQ3]` caching effect under controlled conditions (network=constrained,
  concurrency=10, density=medium) across access patterns × payload weight
  → data: `APEta/results/phase2-core-real/` (12 clean cells, 720 runs, fully serial)
- `[METHOD]` justifies a methodological choice; `[BG]` background/comparison
  only (retired design: in-memory DET, closed-loop, factorial) — never center it.
- `SRC:` on-disk source · `MUST-LEARN:` external study needed, nothing on disk
  · `MUST-WRITE:` no script/text exists yet.

Data status at scan time (2026-07-04 10:50):
- `mot-scenarios-core` **LIVE — 1,642/3,240 measured runs (~51%), ETA ≈ 2026-07-06**
  (progress.log; STUDY_COMPARISON.md ETA table). Do not touch; analysis outlines
  below assume the completed CSV.
- `phase2-core-real` complete (720/720) with analysis in
  `results/phase2-core-real/analysis/` — but its **CPU/RSS columns are INVALID**
  (documented telemetry PID bug; fixed before the MOT run).
- Approved follow-up arms not yet on disk: `m6cache → m5embed → m1mem`
  (GO order in `design/CALIBRATION.md` §Methods note). Outline nodes that
  depend on them are marked conditional.

---

## OUTLINE A — DASAR TEORI (BAB II)

**No BAB II draft exists** (`laporan/chapters/` has BAB I/III/IV/V only);
skeleton suggestions in `laporan/REPORT_MAP.md` §BAB II. Everything below is
therefore MUST-WRITE as prose; tags mark where the *material* lives.

### A.1 Arsitektur REST
- A.1.1 Resource, representation, endpoint, metode HTTP, statelessness
  — [RQ1] why: REST arm's contract is per-resource GET endpoints.
  SRC: `laporan/REFERENCES_BASIS.md` items 5–6 (RFC 9110/9111);
  `APEta/rest_server.py` (concrete endpoints). MUST-LEARN: Fielding's
  architectural-constraints framing (dissertation, 2000) — only the RFCs are
  in the citation bank.
- A.1.2 Cacheability of GET: Cache-Control, ETag, validation/304, cache key
  = URL — [RQ3] why: the mechanism that gives REST its "native caching"
  advantage. SRC: RFC 9111 (item 6); `APEta/core/caching.py` (shared
  ETag/Cache-Control implementation); `APEta/cache/varnish.vcl`.
- A.1.3 Under-fetching as a structural REST property: one resource per call,
  related data ⇒ K round trips — [RQ2] why: this is the mechanism M5/M6
  measure. SRC: `APEta/METHODOLOGICAL_VERIFICATION.md:115-118`;
  `design/SCENARIO_DESIGN.md` §2 rows M5/M6 (Jin et al. 2024 as cited there).

### A.2 GraphQL
- A.2.1 Single endpoint, schema/type system, query & selection set — [RQ1][RQ2]
  why: defines how one composite query replaces K REST calls.
  SRC: GraphQL Spec Oct 2021 (`REFERENCES_BASIS.md` item 7);
  `APEta/graphql_server.py` (Strawberry schema: `image`, `track`, `tracks(ids)`).
- A.2.2 Resolver execution model and why it costs CPU (per-field resolution,
  envelope construction) — [RQ1] why: explains GraphQL's flat ~62 iter/s
  ceiling across ALL families in calibration. SRC: `design/CALIBRATION.md`
  §Observations item 1 (empirical); GraphQL Spec §Execution. MUST-LEARN:
  literature on GraphQL server execution overhead beyond the workspace's
  citations (e.g. framework benchmarking papers) — the workspace asserts the
  effect empirically but has no theory source for *why*.
- A.2.3 The N+1 problem and batching (DataLoader-style prefetch) — [RQ2]
  why: M6's fairness depends on one composite query = ONE DAL batch, not K
  lazy resolutions. SRC: `graphql_server.py` (`images(ids)`/`tracks(ids)`
  prefetch, "real batching" comment); `tests/test_parity_mot.py::test_m6_single_dal_batch`
  (proof: exactly 2 IN-clause SQL statements). MUST-LEARN: DataLoader
  pattern origin (Facebook's dataloader docs / Jin et al. 2024 §background).
- A.2.4 GraphQL over HTTP: POST default vs APQ-over-GET, persisted-query hash
  as cache key — [RQ3] why: the mechanism that makes GraphQL cacheable at all
  in this study. SRC: Apollo APQ doc (item 8); `k6/workload_mot.js` `apqGet()`
  (hash-first flow, `PERSISTED_QUERY_NOT_FOUND` retry); `laporan/figures/src/fig_09_graphql_apq_cache_flow_ssd.mmd`.

### A.3 Over-fetching, under-fetching, dan konsolidasi round-trip — [RQ2 core]
- A.3.1 Over-fetching & field selection (payload reduction) — [RQ1] via M2.
  SRC: `APEta/README.md` reference row 4 (Brito, Mombach & Valente 2019);
  `design/SCENARIO_DESIGN.md` §4 M2.
- A.3.2 Under-fetching → multi-round-trip consolidation; latency cost model
  of K sequential HTTP calls over nonzero RTT vs 1 composite call — [RQ2]
  why: the a-priori reason a crossover should exist and shift with K.
  SRC: `design/SCENARIO_DESIGN.md` §2 (Jin, Cordingly, Zhao & Lloyd 2024,
  ACM WoSC10) + §6 Q5 (RTT-visibility rationale for netns). MUST-LEARN: a
  simple analytic model (K·RTT + K·service vs 1·RTT + composite-service) to
  present the expected crossover — not written anywhere on disk.
- A.3.3 The cacheability trade-off of consolidation: K small cacheable
  responses vs 1 composite cache entry keyed by the exact id-set — [RQ2][RQ3]
  SRC: `tools/build_id_pool.py` docstring (fixed pages rationale);
  `design/SCENARIO_DESIGN.md` M6. Conditional: measured evidence arrives only
  with the `m6cache` arm (not yet run).

### A.4 Transport equalization: HTTP/1.1 vs HTTP/2 — [METHOD]
- Why both arms are pinned to HTTP/1.1, no compression, single worker:
  transport multiplexing would confound the round-trip effect RQ2 measures.
  SRC: `design/SCENARIO_DESIGN.md` §4 fairness substrate (the *decision*).
  MUST-LEARN: HTTP/2 multiplexing basics (RFC 9113) to *defend* the decision —
  no source on disk explains what HTTP/2 would have changed.

### A.5 Model data deteksi objek & MOT — [RQ2 enabler + dataset]
- A.5.1 YOLO detection output (bbox, class, confidence); DET vs MOT; VisDrone
  — SRC: `REFERENCES_BASIS.md` items 9–11 (VisDrone, Ultralytics, ByteTrack);
  `laporan/chapters/BAB_I_PENDAHULUAN_DRAFT.md` §I.6.
- A.5.2 Tracks & trajectories as *relational* structure (sequence → image →
  detection ← track) and why flat DET data could not test RQ2 — [RQ2]
  SRC: `METHODOLOGICAL_VERIFICATION.md:115-118`; `design/mot_profile.json`
  (counts: 7 seq / 2,846 images / 5,429 tracks / 104,767 detections);
  `laporan/phase2_migration/SOURCE_OF_TRUTH_PHASE2.md` §Schema;
  ERD source `laporan/figures/src/fig_05_sqlite_erd.mmd`.
- A.5.3 Density/window/page-size tiers as operationalization of "object
  density" and "query complexity" — [RQ1][RQ2] SRC: `design/mot_profile.json`
  (quartile-anchored cut points), `design/SCENARIO_DESIGN.md` §3.

### A.6 Teori caching (depth capped to RQ3 — do not over-expand)
- A.6.1 HTTP caching semantics: freshness (TTL/max-age), validation (ETag/304),
  reverse-proxy cache — [RQ3] SRC: RFC 9111; `core/caching.py`
  (DEFAULT_MAX_AGE=30, no-store for anti-cache endpoints); `cache/varnish.vcl`
  (X-Cache HIT/MISS header, builtin Cache-Control parsing note).
- A.6.2 Cache hit rate and access-pattern dependence: zipfian / uniform /
  unique — [RQ3] why: the IV of RQ3. SRC: `k6/workload.js` +
  `k6/workload_mot.js` (`pickIndex()`: zipf CDF θ=0.99, uniform, finite-pool
  no-repeat cursor). MUST-LEARN: theoretical grounding for zipfian web-access
  modeling (e.g. Breslau et al. 1999) — the θ=0.99 choice has no citation on disk.
- A.6.3 GraphQL caching via APQ: hash+variables as cache key — [RQ3]
  SRC: Apollo APQ doc; `graphql_server.py` APQ route; measured parity of
  hit rates in `results/phase2-core-real/analysis/phase2_analysis_report.txt`
  (cache_hit_rate: no significant REST-vs-GraphQL difference in any cell).

### A.7 Konsep load testing — [METHOD]
- A.7.1 Closed-loop vs open-loop load; coordinated omission; why
  constant-arrival-rate was chosen — SRC: `k6/workload.js` LOAD-MODEL note
  (referenced by `workload_mot.js` header); `design/SCENARIO_DESIGN.md` §5.
  MUST-LEARN: the canonical coordinated-omission argument (Tene, "How NOT to
  Measure Latency") — the workspace applies it but cites no source.
- A.7.2 Arrival rate, saturation, the p95 knee, dropped iterations as
  saturation signal — SRC: `design/CALIBRATION.md` (saturation rule:
  dropped>0 ∨ err>1% ∨ p95>max(5×baseline,150ms); knee observations).
- A.7.3 Warmup, repetition, seeding — SRC: `orchestrator/config.py`
  (`APE_N_WARMUP=1`, `APE_N_MEASURED=30`, seed 42); `design/SCENARIO_DESIGN.md` §5.

### A.8 Statistika untuk analisis hasil — [ANALYSIS support]
- A.8.1 Right-skewed latency distributions; median/IQR over mean — SRC:
  `tools/analyze_phase2.py` docstring (Arcuri & Briand ICSE 2011 rationale,
  `REFERENCES_BASIS.md` item 17).
- A.8.2 Normality check (Shapiro-Wilk) as gateway to non-parametrics — SRC:
  precedent in `results/analysis_session1_preliminary/ANALYSIS_SUMMARY.md`
  + `normality.csv` [BG: computed on Study A data; method reusable].
- A.8.3 Mann-Whitney U; Vargha-Delaney A12; Cliff's delta (δ=2·A12−1) and
  magnitude thresholds 0.147/0.33/0.474 — SRC: `tools/analyze_phase2.py`
  (implementation); `REFERENCES_BASIS.md` items 15–16.
- A.8.4 Multiple-comparison correction: Holm (phase2 analysis) vs BH-FDR
  (Study A analysis) — state which is used where. SRC: `analyze_phase2.py`
  (Holm within metric); `ANALYSIS_SUMMARY.md` (BH-FDR) [BG].
- A.8.5 Trend tests across ordered tiers (Jonckheere-Terpstra) — SRC:
  precedent `results/analysis_session1_preliminary/trend_density.csv` /
  `trend_concurrency.csv` [BG precedent]. MUST-LEARN: J-T test theory (no
  reference in the citation bank).
- A.8.6 Bootstrap CI for medians — SRC: `analyze_phase2.py::bootstrap_median_ci`.
- A.8.7 Effect size vs p-value under n=30/cell ("everything is significant") —
  SRC: `phase2_analysis_report.txt` SCOPE NOTES bullet 3.

---

## OUTLINE B — METODOLOGI (BAB III)

Existing draft: `laporan/chapters/BAB_III_METODOLOGI_DRAFT.md` (III.1–III.6,
written toward the phase2 entropy/caching framing) — **must be re-scoped** to
the MOT study + phase2-core-real caching subset; template map in
`laporan/REPORT_MAP.md` §BAB III. Numbered as reproducible steps; each step =
a candidate subsection. Steps marked ⚠ differ between the clean MOT run
(RQ1/RQ2) and the phase2-core-real caching subset (RQ3).

1. **Dataset & korpus** [RQ1][RQ2][RQ3]
   1.1 Provenance: VisDrone-MOT → YOLO/ByteTrack inference →
       `~/training/build_detection_db.py` → SQLite `mot_detections.db`
       (path in `orchestrator/config.py` default `APE_DB_PATH`).
       SRC: `core/dal.py` docstring; `REFERENCES_BASIS.md` 9–11;
       BAB III draft §III.3. NOTE: the build script lives *outside* APEta
       (`~/training/`) — verify it is archived before the defense (MUST-CHECK).
   1.2 Schema & counts: sequence(7) / image(2,846) / track(5,429) /
       detection(104,767) / class(10). SRC: `design/mot_profile.json`;
       `SOURCE_OF_TRUTH_PHASE2.md` §Schema; integrity via
       `results/mot-scenarios-core/env_snapshot/db_md5.txt`.
   1.3 Tier definitions (quartile-anchored): density low ≤4 / medium 5–53 /
       high ≥54 det@conf.25; trajectory window W∈{2,8,23} (5/17/47 pts);
       page size K∈{1,5,10}; filter constants class_id=4 ("car"),
       min_confidence=0.5. SRC: `design/mot_profile.json` (incl. rationale
       strings); profiler `tools/profile_dataset.py`.

2. **Substrat fairness (identik kedua protokol)** [RQ1 validity]
   2.1 Shared DAL: `core/dal.py` (`DetectionDAL`, thread-local sqlite
       connections; SQL logging via `APE_LOG_SQL=1` proves same access path —
       `tests/test_parity_mot.py::test_m5_same_access_path`).
   2.2 Shared projection: `core/projection.py` (`DETECTION_FIELDS` = 6 canonical
       fields); shared filters `core/filters.py`; shared aggregate `core/aggregate.py`.
   2.3 Encoding parity: GraphQL `auto_camel_case=False` + compact encoder;
       REST `json.dumps(separators=(",",":"))`; no compression; HTTP/1.1;
       uvicorn `--workers 1`. SRC: `design/SCENARIO_DESIGN.md` §4;
       `rest_server.py`, `graphql_server.py`.
   2.4 Shared cache semantics: `core/caching.py` (one function decides
       ETag/Cache-Control for both). [RQ3]
   2.5 Server alternation on port 8000, never co-resident.
       SRC: `orchestrator/run_experiment.py` (`ensure_server`/`stop_server`);
       `design/CALIBRATION.md` §Methods note 3.
   2.6 Seeded server-side entity selection: `core/selection.py` (server picks
       record, client sends condition) + seeded track picker.
   2.7 Impl-mode stance: both servers dict-passthrough **by construction**;
       typed/passthrough axis retired after factorial-A [BG].
       SRC: `design/IMPL_MODE_JUSTIFICATION.md` (contains "what to state in
       the thesis" paragraph verbatim).

3. **Definisi skenario M1–M6** [RQ1: M1–M4 · RQ2: M5/M6]
   3.1 Contracts (REST URL + GraphQL query per scenario, tiers, parity
       criteria): SRC: `design/SCENARIO_DESIGN.md` §4 (design) +
       `k6/workload_mot.js` GQL_QUERIES / restIteration() (as-executed truth) +
       `design/PARITY_REPORT_MOT.md` §Contract decisions (5 locked deviations
       from the design sketch — cite the *report*, not the sketch: e.g. M1/M3
       REST uses explicit `fields=<all 6>`; M5/M6 selections include
       trajectory-point `id`,`image_id`).
   3.2 Parity gate results: 18 passed / 2 skipped; envelope delta constant
       19 B (M1–M3) / 13 B (M4). SRC: `design/PARITY_REPORT_MOT.md`;
       suite `tests/test_parity_mot.py`; k6↔test drift guard
       (`test_queries_match_k6_workload`).
   3.3 M5 contract honesty: REST = 2 sequential round trips (the real client
       flow); M5E embed counterfactual is a separate FUTURE arm (`m5embed`,
       not in core data). SRC: `workload_mot.js` M5/M5E branches;
       `CALIBRATION.md` GO note.

4. **Lingkungan eksekusi** [METHOD, all RQs]
   4.1 VM: 32-core AMD EPYC 7302 (SRC: `design/STUDY_COMPARISON.md` §3;
       `env_snapshot/lscpu.txt`); CPU governor `performance`
       (`orchestrator/VM_SETUP.md` §1, `env_snapshot/cpu_governor.txt`).
   4.2 Network namespace topology: `ape-origin` netns + veth; netem applied
       ONLY on host-side veth (single client↔edge hop); varnish→backend hop on
       the namespace's own loopback — fixes the documented double-delay
       artifact. SRC: `tools/netns_topology.sh` header (topology diagram);
       `tools/netem.sh` header (the retired whole-`lo` threat, measured 2×→1×).
   4.3 ⚠ Netem profiles: MOT run = `lan` (5 ms ± 1 ms, 100 Mbit);
       phase2-core-real = `constrained`. SRC: `CALIBRATION.md` §Setup;
       `env_snapshot/netem_qdisc.txt`; `run_plan.csv` network columns.
   4.4 Resource caps & pinning: systemd-run scope CPUQuota=400% /
       MemoryMax=2048M; taskset server=0–7, k6=8–15, sampler=31.
       SRC: `env_snapshot/ape_env.txt` (exact values); `orchestrator/config.py`.
   4.5 Versions frozen: k6 v2.0.0, pip freeze, git SHA, DB md5, id-pool md5 —
       all in `results/mot-scenarios-core/env_snapshot/` (the ONLY session
       with a snapshot; ⚠ phase2-core-real has none — disclose).

5. **Pool entitas untuk k6** [RQ1][RQ2][RQ3]
   - `tools/build_id_pool.py` → `scratch/id_pool_mot.json`: per-tier image ids,
     window-eligible track {id, center} entries, FIXED K-id pages (so composite
     cache entries can recur — [RQ2]/[RQ3] rationale in the docstring).
     Integrity: `env_snapshot/id_pool_md5.txt`.

6. **Kalibrasi laju (rate)** [RQ1][RQ2 validity] — MOT run only ⚠
   6.1 Procedure: per protocol × heaviest family cell (M1-high, M5-w23,
       M6-k10), 12 s stepped probe 25→50→100→… + 2 bisection steps; saturation
       rule as in A.7.2. SRC: `tools/calibrate_mot.py`; `design/CALIBRATION.md`
       (probe curves, raw JSON in `results/mot-scenarios-calibration/`).
   6.2 Derived rates = 40/80/120% of the LOWER protocol ceiling per family:
       image/track 25/50/74, page 17/34/52 iter/s; overload labeled, analyzed
       separately; `overload_saturates` column semantics. SRC: `CALIBRATION.md`
       §Ceilings + §Methods notes 1–2; `env_snapshot/ape_env.txt` (APE_MOT_RATES_*).
   6.3 Rate unit = scenario iterations/s (one M6 page = K REST calls = 1
       iteration) — makes ceilings protocol-comparable. SRC: `CALIBRATION.md` §Setup.
   ⚠ phase2-core-real instead fixed arrival rate at concurrency=10 req/s
     (uncalibrated, deep sub-saturation) — SRC: `phase2-core-real/run_plan.csv`.

7. **Pembangkitan beban (k6)** [all RQs]
   7.1 Open-loop `constant-arrival-rate` executor; VUS env = target RATE not
       VU count; preAllocatedVUs/maxVUs formula. SRC: `k6/workload_mot.js`
       options block; ⚠ RQ3 uses `k6/workload.js` (same executor convention).
   7.2 Access patterns: uniform (MOT core run) ⚠ vs uniform/zipfian(θ=0.99)/
       unique (RQ3 grid); unique = global no-repeat cursor with ENTITY_OFFSET
       cross-run continuation. SRC: `pickIndex()` in both workload scripts.
   7.3 GraphQL client flow = APQ-over-GET (hash-first, register on
       PERSISTED_QUERY_NOT_FOUND, `apq_registrations` counter). SRC: `apqGet()`.
   7.4 Protocol fixed values: 1 warmup/block (discarded), 30 measured
       runs/cell, 90 s/run, seed 42. SRC: `env_snapshot/ape_env.txt`;
       `design/STUDY_COMPARISON.md` §3 (confirms same for phase2).

8. **Protokol eksekusi & reproducibility** [METHOD]
   8.1 Grid → run plan: `orchestrator/make_run_plan.py` (`APE_GRID=mot`,
       `APE_MOT_ARM=core`; refuses empty rate lists). Core grid = 2 protocols ×
       6 scenarios × 3 tiers × 3 rates × 30 runs = 3,240 measured (+108 warmup).
   8.2 Strictly serial: one orchestrator lock, one server, one blocking k6 at
       a time; block-randomized order (`block_id`/`block_order`).
       SRC: `orchestrator/run_experiment.py` (acquire_orchestrator_lock,
       run_block); `CALIBRATION.md` §Methods note 3.
   8.3 Resume machinery: `progress.log`, done-uid scan, warmup re-run on
       partial blocks, results-tail cleaning; run_uid hash includes session_id
       (the documented sesi-A/B silent-resume trap — `APEta/README.md` §KRITIS).
       SRC: `run_experiment.py::find_resume_index/clean_results_tail`.
   8.4 Env snapshot at session start (`tools/env_snapshot.sh`); results backup
       cron to `results-backup` branch (commit `eb0323a`, per STUDY_COMPARISON).
   8.5 Lifecycle per block: netns up → netem apply → server in systemd scope →
       health check → (varnish if caching=on ⚠ RQ3 only, `tools/start_varnish.sh`
       + `cache/varnish.vcl`) → sampler start → k6 runs → teardown.
       SRC: `run_experiment.py` SessionRunner methods.

9. **Metrik per run & asalnya** [all RQs]
   9.1 From k6 summary JSON (client-side): lat_p50/p95/p99, throughput_rps,
       payload_bytes_med, cache_hit_rate (X-Cache header), round_trip_count,
       page_latency_med (M5/M6 scenario latency = sum of sub-calls),
       error_rate, apq_registrations, k6_iterations, dropped_iterations.
       SRC: `workload_mot.js` custom Trends/Rates/Counters;
       `run_experiment.py` summary extraction; results.csv header.
   9.2 From telemetry sampler (1 Hz, separate pinned process, per-PID):
       cpu_mean/cpu_p95/rss_mean_mb/rss_p95_mb joined on ts_start/ts_end.
       SRC: `telemetry/sampler.py`; `run_experiment.py::telemetry_stats`.
       ⚠ VALID in mot-scenarios-core (bug fixed & re-verified with a pilot);
       **INVALID in phase2-core-real** (sampler watched the sudo wrapper —
       `phase2_analysis_report.txt` SCOPE NOTES, final bullet).
   9.3 X-Process-Time server header exists (`core/timing.py`, both servers)
       but is **not harvested** into Study B results.csv (no xproc column —
       `design/STUDY_COMPARISON.md` capability matrix). State as limitation:
       server-processing-time isolation is available only in Study A [BG].

10. **⚠ Ringkasan perbedaan dua sumber data** (present as one table)
    | Aspect | mot-scenarios-core (RQ1/RQ2) | phase2-core-real (RQ3) |
    |---|---|---|
    | Grid | scenario×tier×rate, M1–M6 | caching×access_pattern×payload_weight (12 cells) |
    | Network | lan | constrained |
    | Caching | off only | on/off (Varnish) |
    | Access pattern | uniform | uniform/zipfian/unique |
    | Rate | calibrated 40/80/120% | fixed 10 req/s |
    | Workload script | `k6/workload_mot.js` | `k6/workload.js` |
    | CPU/RSS | valid | INVALID |
    | Env snapshot | yes | no |
    | Serial | yes (verified) | yes (verified — only fully-serial phase2 session) |
    SRC: `design/STUDY_COMPARISON.md` §1–3; both sessions' run_plan.csv.

11. **Posisi data baseline** [BG — one short subsection, no more]
    - factorial-A (DET in-memory, closed-loop, passthrough) and run-sesi-1:
      preliminary/instrument-calibration only; run-sesi-1 additionally carries
      345,879 in-band GraphQL field errors invisible to error_rate.
      SRC: `design/STUDY_COMPARISON.md` §3 Study A signals;
      `FACTORIAL_DESIGN_SUMMARY.md`; `METHODOLOGICAL_VERIFICATION.md`.
      Never pool with main-study data; cite only as motivation for the redesign
      (BAB I/III narrative already frames this — `BAB_I_PENDAHULUAN_DRAFT.md` §I.1).

---

## OUTLINE C — ANALISIS HASIL (BAB V)

Existing draft: `laporan/chapters/BAB_V_HASIL_DAN_PEMBAHASAN_DRAFT.md`
(structure reusable; content keyed to old RQ wording — re-scope).
**No analysis exists yet for mot-scenarios-core** (run incomplete) — the
RQ1/RQ2 pipeline below is MUST-WRITE, with `tools/analyze_phase2.py` as the
proven template. RQ3 analysis already exists and is reusable as-is.

### C.1 Unit analisis & agregasi [all RQs]
- One k6 run = one data point (one results.csv row); 30 runs/cell;
  MIN_N_PER_GROUP=3 guard. SRC: `analyze_phase2.py` (constants);
  `BAB_III` draft §III.4 (already states this).
- Cell definition: RQ1/RQ2 = (scenario, tier, rate_label); RQ3 =
  (caching, access_pattern, payload_weight) with the other 4 factors constant.
  SRC: `analyze_phase2.py` CELL_COLS + docstring ("cells effectively reduce
  to… 12 cells"). MUST-WRITE: `analyze_mot.py` variant with MOT cell columns
  (incl. keeping overload rows out of the default family — see C.7).

### C.2 Statistik deskriptif [all RQs]
- Per-cell median + bootstrap 95% CI (2,000 resamples, seed 42), IQR;
  per-cell tables REST vs GraphQL per metric. SRC:
  `analyze_phase2.py::bootstrap_median_ci`; report format in
  `results/phase2-core-real/analysis/phase2_analysis_report.txt`.
- Boxplot faceting rule: keep incomparable request shapes off one axis
  (the documented mis-scoped-boxplot lesson). SRC:
  `analyze_phase2.py::plot_descriptive_boxplots` docstring.

### C.3 Uji normalitas → justifikasi non-parametrik [METHOD]
- Precedent A: Shapiro-Wilk per cell then non-parametrics
  (`results/analysis_session1_preliminary/normality.csv` [BG]).
- Precedent B (current): skip straight to non-parametrics citing Arcuri &
  Briand for right-skewed latency (`analyze_phase2.py` docstring).
- Decision to state in thesis: run Shapiro-Wilk on the MOT data as
  confirmation, report, then use non-parametrics regardless. MUST-WRITE
  (small; port from the Study A script pattern).

### C.4 Uji hipotesis per cell [RQ1][RQ3]
- Mann-Whitney U two-sided, REST vs GraphQL per cell per metric;
  Vargha-Delaney A12; Cliff's δ=2·A12−1 with magnitude labels
  (0.147/0.33/0.474); Holm correction within metric family.
  SRC: `analyze_phase2.py::pairwise_compare/run_family` (RQ3: already
  executed — `phase2_comparisons.csv`). RQ1: MUST-WRITE (same functions,
  MOT cell columns).
- Metrics per RQ:
  - RQ1: lat_p50/p95/p99, throughput_rps, payload_bytes_med, cpu_mean,
    rss_mean_mb (valid here), error_rate — across M1–M4 × density × rate.
  - RQ3: lat percentiles, throughput, payload, cache_hit_rate, error_rate;
    **exclude cpu/rss (invalid)**. Existing headline results to carry: REST
    faster in all 12 cells (δ=−1.0 large, lat_p50 28–29 vs 32–35 ms);
    cache_hit_rate protocol-equal; throughput pinned at target 10 rps (open
    loop — interpret as "both kept up", not "equal capacity").
    SRC: `phase2_analysis_report.txt`.
- Interpretation rule: with n=30/cell read δ magnitude, not p (report's own
  scope note).

### C.5 Uji tren lintas tier [RQ1][RQ2]
- Jonckheere-Terpstra (or equivalent ordered-alternative test) for latency
  across density low→medium→high (RQ1), window w2→w8→w23 (RQ2/M5), page
  K=1→5→10 (RQ2/M6), and across rate r40→r80. Precedent: Study A
  `trend_density.csv`/`trend_concurrency.csv` [BG]. MUST-WRITE for MOT data;
  MUST-LEARN J-T theory (A.8.5).

### C.6 Identifikasi crossover RQ2 (MAIN CONTRIBUTION) — all MUST-WRITE
- C.6.1 Comparison variable: `page_latency_med` (scenario-level: REST = sum of
  K or 2 calls; GraphQL = its 1 call), NOT per-HTTP-call `lat_p*`
  (which still describes individual calls). SRC of semantics:
  `workload_mot.js` pageLatency/roundTripCount; `run_experiment.py`
  round_trip_count comment block.
- C.6.2 M5: Δ = REST(2-RT) − GraphQL(1-RT) per window tier × rate; test per
  cell (C.4 machinery); effect of window size on Δ (C.5 trend).
- C.6.3 M6: Δ(K) = REST(K·RT) − GraphQL(1) for K∈{1,5,10} × rate; the
  crossover point = K* where Δ changes sign (fit/interpolate Δ vs K; report
  with bootstrap CI). Expectation setting from calibration [context only,
  not conclusions]: REST per-call capacity ~430 rps on light calls but the
  page family ceiling was REST-bound (43 pages/s vs GraphQL 62) —
  `CALIBRATION.md` §Observations 2.
- C.6.4 round_trip_count as the explanatory axis: plot Δ vs round_trip_count
  {1,2,5,10} pooled across M5/M6 at matched rate — the literal
  "round-trip consolidation" figure the phase2 design could not draw
  (round_trip_count was constant=1 there — `analyze_phase2.py` docstring).
- C.6.5 Comparison-only overlay [BG]: `phase2-batch-real` round-trip savings
  (`tools/visualize_phase2_full.py::fig_roundtrip_savings`,
  `results/phase2-figures/`) — collected under 2–8 parallel sessions; use as
  qualitative corroboration only, never pooled.
- C.6.6 Conditional (future arms): M5E embed counterfactual (`m5embed`) and
  M6 with caching (`m6cache`) — outline placeholders only; data not on disk.

### C.7 Penanganan tier overload [RQ1][RQ2 validity]
- r120_overload rows: labeled, analyzed per family, NEVER pooled with
  r40/r80; rates calibrated on the heaviest tier ⇒ lighter-tier overload
  cells may not saturate — check per-cell `dropped_iterations` before calling
  a cell "overloaded" (30 rows >0 so far, all M1-GraphQL overload —
  `STUDY_COMPARISON.md` capability matrix). `overload_saturates` column says
  which protocol's ceiling defined the family rate. SRC: `CALIBRATION.md`
  §Methods notes 1–2; `orchestrator/config.py` comments.

### C.8 Pengukuran efek cache RQ3
- cache_hit_rate by access pattern (achieved values on disk: zipfian
  ~0.37–0.43, uniform ~0.02–0.06, unique ~0) and payload weight;
  on-vs-off latency delta per matched cell; APQ registration counts.
  SRC: `phase2_analysis_report.txt`; raw `phase2-core-real/results.csv`.
- Unique-pattern hit-rate floor formula max(0, 1 − pool/iterations) — report
  it, don't treat nonzero unique hits as IV failure (SCOPE NOTES bullet 5).
- Crossover-surface figure (REST−GraphQL lat_p95 over hit-rate bucket ×
  payload weight) + its page_size exclusion rationale. SRC:
  `analyze_phase2.py::plot_crossover_surface` (+ existing
  `fig_crossover_surface.png`).
- Scope honesty: 12 cells at ONE network/density/concurrency point; hit
  rates far from 90%+ CDN regimes; caching axis absent from the MOT run by
  approved decision (SCENARIO_DESIGN §6 Q3) ⇒ RQ3 claims are conditional on
  the controlled point, not general.

### C.9 Ancaman validitas (dedicated subsection — disclose, don't bury)
- Phase2 parallelism: up to 8 concurrent sessions on the VM; ONLY
  phase2-core-real (and mot-scenarios-core) are fully serial — that is WHY
  RQ3 is scoped to those 720 runs; other phase2 sessions are corroboration
  at most. SRC: `design/STUDY_COMPARISON.md` §3 (reconstructed from timestamps).
- lan (RQ1/RQ2) vs constrained (RQ3) network profiles ⇒ no direct
  cross-RQ latency comparison; state explicitly.
- CPU/RSS invalid in phase2-core-real (mechanism + why other metrics
  unaffected). SRC: `phase2_analysis_report.txt` final scope note.
- No server-processing-time (xproc) metric in the main study (B.9.3).
- Effective N for scene variety = 7 sequences, not row count.
- Closed-loop legacy data (Study A) excluded from all inference [BG];
  run-sesi-1's in-band GraphQL errors as the cautionary detail.
- Netem double-delay artifact: affected only retired whole-`lo` runs; current
  topology verified (MISS 2×→1×). SRC: `netns_topology.sh` header;
  scope note bullet 4.
- Single VM, single SQLite file, single implementation pair (FastAPI/
  Strawberry) ⇒ generalization limits (BAB I §I.7 already bounds this).
- Live-run caveat for the thesis timeline: mot-scenarios-core completes
  ~2026-07-06; all RQ1/RQ2 numbers are placeholders until then; re-verify
  CPU/RSS columns vary sanely before reporting (post-fix check).

### C.10 Peta figur hasil (target list)
- Existing now: RQ3 set (`fig_descriptive_boxplots/crossover_surface/
  coupling_entropy_hitrate` in `phase2-core-real/analysis/`; note the
  coupling figure is entropy-constant here — likely drop for RQ3 as locked).
- MUST-WRITE (blocked on run completion): RQ1 per-scenario boxplots
  (scenario×tier×rate), RQ1 CPU/RSS comparison, RQ2 Δ-vs-K crossover chart,
  RQ2 Δ-vs-round_trip_count chart, overload-tier annotated latency chart.
- Register every new figure in `laporan/FIGURE_REGISTER.md` (existing QC
  process) before embedding.

---

## LEARNING GAPS (theory with no on-disk source — study externally)

1. REST architectural constraints as theory (Fielding 2000 dissertation) —
   the bank has only RFC 9110/9111. (A.1.1)
2. Why GraphQL resolver execution costs CPU — server execution-model
   literature beyond the spec; needed to explain the flat 62 iter/s ceiling
   rather than just report it. (A.2.2)
3. DataLoader/batching pattern origin & theory for the N+1 discussion. (A.2.3)
4. Analytic round-trip cost model (K·RTT vs 1·RTT) to frame the expected
   RQ2 crossover before showing data. (A.3.2)
5. HTTP/2 multiplexing basics (RFC 9113) — to defend pinning HTTP/1.1. (A.4)
6. Zipfian access-pattern justification for web caching (e.g. Breslau et al.
   1999) — θ=0.99 currently uncited. (A.6.2)
7. Coordinated omission canonical source (Tene) — applied but uncited. (A.7.1)
8. Jonckheere-Terpstra trend test theory. (A.8.5 / C.5)
9. (Check, likely gap) Formal source for Holm's procedure — implementation
   cites statsmodels only.

## MUST-WRITE inventory (code/text, not theory)

- BAB II prose (whole chapter — no draft exists).
- `tools/analyze_mot.py` (or extension): MOT cell columns, overload
  segregation, trend tests, crossover computation + figures (C.1, C.4–C.7).
- Shapiro-Wilk confirmation pass on MOT data (C.3).
- Re-scope of BAB III / BAB V drafts from old RQ wording to the locked
  RQ1/RQ2/RQ3 (drafts exist; framing is stale).
- Archive-check: `~/training/build_detection_db.py` provenance script sits
  outside the repo (B.1.1).
