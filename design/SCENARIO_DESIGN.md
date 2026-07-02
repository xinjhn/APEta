# MOT Scenario Design — REST vs GraphQL over `mot_detections.db`

Status: **DESIGN FOR APPROVAL — nothing implemented, nothing benchmarked.**
Branch: `mot-scenarios-design`. All prior results/sessions/archives untouched.
Companion data file: [`design/mot_profile.json`](mot_profile.json).

---

## 1. Recovery-check verdict (Stage 1)

**Yes — the Phase-1 DET servers are fully recoverable from git history. Nothing was lost.**

| Commit | Date | Contents |
|---|---|---|
| `824b195` | 2026-06-23 | **Post-audit Phase-1 code, the recommended recovery point.** `rest_server.py` with `GET /baseline\|/partial\|/filtered\|/aggregate` (verified via `git show 824b195:rest_server.py`), `graphql_server.py` with `image_detections`/`aggregate` Strawberry fields and both `typed`/`passthrough` impl modes (fixed `SimpleNamespace` passthrough), the full shared `core/` (pool/selection/filters/projection/aggregate/timing), Phase-1 `orchestrator/config.py`, `k6/load.js`, `k6/load_batch.js`, `tests/test_parity.py`, and the factorial tools. |
| `7c91a73` | 2026-06-20 | Pre-audit Phase-1 version (contains the GraphQL-passthrough crash bug documented in `METHODOLOGICAL_VERIFICATION.md`) — historical only, do not use. |
| `8b6c44b` | 2026-06-30 (HEAD of main) | The overwrite: MOT relational servers (`/images/{id}`, `/tracks/{id}`, `/tracks/{id}/trajectory`, GraphQL `image/track/images(ids)` schema), Phase-2 orchestrator. |

`git log --follow` confirms the same three-commit history for `rest_server.py`,
`graphql_server.py`, `orchestrator/config.py`, and `core/`. Recovery, if ever
wanted, is `git show 824b195:<path>` — **no checkout over the working tree was
performed and none is needed for this design.**

---

## 2. Literature dimension → scenario mapping (Stage 2a)

Research questions and hypotheses (verbatim source: `laporan/chapters/BAB_I_PENDAHULUAN_DRAFT.md` §I.3, mirrored in `laporan/REPORT_MAP.md` §I.3):
RQ1 protocol difference under a shared data-access path; RQ2 effect of caching,
access pattern, payload weight, query entropy on latency/throughput/payload/
cache-hit/resources; RQ3 conditions where GraphQL closes the gap. H1 (REST faster,
cache-off/light), H2 (cache shrinks the gap), H3 (entropy lowers hit rate).

Comparison dimensions claimed in workspace documents, with the papers the
workspace itself cites (no external citations added):

| Dimension | Workspace source | Cited prior work (as named in workspace) | New scenario |
|---|---|---|---|
| Protocol/serialization overhead at equal payload | `APEta/README.md` §"Rujukan domain" rows 1–2; §"Hasil verifikasi awal" | Seabra, Nazario & Pinto 2019 (SBCARS'19, DOI 10.1145/3357141.3357149); Lawi, Panggabean & Yoshida 2021 (*Computers* 10:138) | **M1** baseline |
| Over-fetching / payload reduction via field selection | `APEta/README.md` line 180 ("payload S2 turun ~44% dari S1") + row 4 of the reference table | Brito, Mombach & Valente 2019 (SANER'19 / arXiv:1906.07535) | **M2** sparse |
| Server-side filtering parity | `APEta/README.md` §Endpoint table (S3); `core/filters.py` "shared predicate by construction" | (design control, not a single paper) | **M3** filtered |
| Aggregation / server-side processing cost | `APEta/README.md` S4 note "pola agregasi mengukur proses, bukan transfer"; Lawi 2021 row (CPU/memory efficiency claim) | Lawi et al. 2021 | **M4** aggregate |
| Under-fetching / multi-round-trip consolidation on relational data | `APEta/METHODOLOGICAL_VERIFICATION.md:115-118` ("tests N+1 batching…RQ1 cannot answer RQ2's multi-resource round-trip avoidance"); `APEta/README.md` row 3 | Jin, Cordingly, Zhao & Lloyd 2024 (ACM WoSC10) | **M5** nested trajectory |
| K-round-trips vs 1 composite query, interaction with cacheability | `laporan/phase2_migration/SOURCE_OF_TRUTH_PHASE2.md` §Workload (PAGE_SIZE arm); existing `results/phase2-batch-real` | Jin et al. 2024; Apollo APQ doc (`laporan/REFERENCES_BASIS.md` item 8) | **M6** track page |
| HTTP caching semantics (cache key, ETag/304) | `laporan/REFERENCES_BASIS.md` items 5–6 (RFC 9110/9111), item 7 (GraphQL Spec Oct 2021) | RFCs / spec | carried as optional `caching` axis (§6 Q3) |
| Research-trend framing | `APEta/README.md` reference row 5 | "GraphQL: A Systematic Mapping Study", ACM CSUR, DOI 10.1145/3561818 | narrative only |

Constraint honored from `SOURCE_OF_TRUTH_PHASE2.md` §"Hal yang Tidak Lagi Tepat":
the retired S1–S4 matrix **over the in-memory VCD pool** must not return as the
main design. The M-scenarios below are DB-backed over MOT and reuse the Phase-2
server surface — they restore the *dimension coverage* of S1–S4 without
resurrecting the retired corpus or endpoints.

---

## 3. Dataset profile and tier cut points (Stage 2b)

Full numbers in [`design/mot_profile.json`](mot_profile.json). Audit counts
**verified exactly**: 7 sequences, 2,846 images, 5,429 tracks, 104,767
detections (+10 classes; every detection has a track).

Tier systems (all quartile-anchored):

| Tier axis | Cut points | Population | Used by |
|---|---|---|---|
| Image density (existing `image.density_tier`) | low ≤4, medium 5–53, high ≥54 detections@conf.25 — matches Q1=5/Q3=54 of detections-per-image | 579 / 1,555 / 712 images | M1–M4 |
| Trajectory window (NEW) | W=2 (5 pts ≈ track median), W=8 (17 pts ≈ Q3), W=23 (47 pts ≈ p90) | eligible tracks 2,806 / 1,385 / 563 | M5 |
| Page size (aligned to `phase2-batch-real`) | K ∈ {1, 5, 10} | tracks sampled from the W=2-eligible pool | M6 |

Payload size classes (compact JSON, measured on random samples):
image full detections ≈ **301 B (low) / 3.9 KB (medium) / 7.2 KB (high)**;
trajectory ≈ **100 B/point** → ≈0.5 / 1.7 / 4.7 KB for W=2/8/23.
Filter constants: `class_id=4` ("car", 28% of detections), `min_confidence=0.5`
(between confidence Q1 0.434 and median 0.608) — same role as Phase-1 S3's
constant predicate.

---

## 4. Scenario specifications (Stage 2c)

Shared fairness substrate for ALL scenarios (unchanged from what is already
running on `main`, i.e. the Phase-2 servers): both servers call the same
`core/dal.py` (`DetectionDAL` over SQLite), `core/projection.py`
(`DETECTION_FIELDS = class_id, confidence, bbox_x, bbox_y, bbox_w, bbox_h`),
`core/caching.py` (Cache-Control/ETag), `core/timing.py` (X-Process-Time).
GraphQL: `auto_camel_case=False`, compact encoder (`_encode_compact`); REST:
`json.dumps(separators=(",",":"))`. No compression middleware either side,
HTTP/1.1, uvicorn `--workers 1`, servers alternated on port 8000, never
co-resident. New code needed is marked **[NEW]**; everything new that computes
must live in `core/` and be called by both servers.

For every scenario: identical filter/projection semantics by construction
(shared module), seed-deterministic entity selection via the existing
`/images/random`-style seeded picker extended to tracks **[NEW: seeded track
picker in `core/selection.py`, shared]**.

### M1 — `image_full` (parity anchor / protocol overhead; old-S1 analog)
- REST: `GET /images/{id}/detections` (no `fields`, no filters) — exists today.
- GraphQL:
  ```graphql
  query M1($id: Int!) { image(id: $id) {
      id sequence_id frame_index width height density_tier
      detections { class_id confidence bbox_x bbox_y bbox_w bbox_h } } }
  ```
- Tiers: image density low/medium/high. Payload class: 0.3 / 3.9 / 7.2 KB.
- Parity: field-level — GraphQL `data.image` JSON minus envelope must equal the
  REST body key-for-key, value-for-value (same test style as Phase-1
  `tests/test_parity.py`, seeded IDs × 3 tiers × 4 seeds). Byte-level: envelope
  delta must be a **constant** per scenario (Phase-1 precedent: 23–30 B).

### M2 — `image_sparse` (over-fetching; old-S2 analog)
- REST: `GET /images/{id}/detections?fields=class_id,confidence` — exists today.
- GraphQL: same as M1 with selection set `detections { class_id confidence }`.
- Tiers: density low/medium/high. Expected payload ≈ ⅓ of M1 (4 of 6 detection
  fields dropped; Phase-1 analog measured −44% when dropping bbox only).
- Parity: as M1; additionally assert both bodies contain **exactly** the 2
  projected fields (projection happens in shared `core/projection.py`, so
  REST must not send-full-and-strip).

### M3 — `image_filtered` (server-side filter; old-S3 analog)
- REST: `GET /images/{id}/detections?class_id=4&min_confidence=0.5` — exists today.
- GraphQL: `detections(class_id: 4, min_confidence: 0.5) { ...all 6 fields }`.
- Constants from §3; empty result arrays are VALID (Phase-1 rule).
- Tiers: density low/medium/high. Payload: ≤ M1, tier-dependent.
- Parity: as M1 + identical detection ordering (shared DAL query ORDER BY).

### M4 — `image_aggregate` **[NEW endpoint + field]** (aggregation; old-S4 analog)
- REST: `GET /images/{id}/class_counts` → `{"image_id":…,"class_counts":[{"class_id":…,"count":…},…]}`.
- GraphQL: `image(id){ id class_counts { class_id count } }`.
- Both MUST call one **[NEW]** shared `core/aggregate.py` function (module
  already exists from Phase 1; needs a DAL-backed variant).
- Tiers: density low/medium/high (aggregation cost scales with row count;
  payload stays small — measures processing, not transfer, per README S4 note).
- Parity: field-level equality + identical class ordering (ORDER BY class_id).

### M5 — `track_trajectory` (nested traversal / under-fetching — MOT-enabled, DET could not test)
- REST (models the REST client's forced under-fetch, 2 round trips):
  1. `GET /tracks/{id}` (exists), then 2. `GET /tracks/{id}/trajectory?center_frame=c&window=W` (exists).
  k6 measures **sum of both** as scenario latency and reports `round_trip_count=2`.
- GraphQL (1 round trip):
  ```graphql
  query M5($id: Int!, $w: Int!) { track(id: $id) {
      id sequence_id local_track_id class_id first_frame last_frame
      trajectory(window: $w) { frame_index bbox_x bbox_y bbox_w bbox_h confidence } } }
  ```
- Tiers: window W ∈ {2, 8, 23} (5/17/47 points); track sampled from the
  eligibility pool for its tier (2,806/1,385/563 tracks), `center_frame` =
  track midpoint, seeded.
- Parity: union of REST body #1 + #2 must field-equal GraphQL `data.track`;
  trajectory point lists identical and same length.
- This is the H-under-fetching/N+1 dimension flagged in
  `METHODOLOGICAL_VERIFICATION.md:115-118` as unanswerable by the Phase-1 design.

### M6 — `track_page` (K round trips vs 1 composite — aligns with `phase2-batch-real`)
- REST: K sequential `GET /tracks/{id}/trajectory?window=2` calls (cacheable,
  ETag-bearing — the RFC 9111 cacheability advantage REST keeps).
- GraphQL: **[NEW]** `tracks(ids: [Int!]!)` list field with trajectory
  prefetch, mirroring the existing `images(ids)` prefetch pattern
  (`graphql_server.py` comment: "real batching, N5's principle") so one HTTP
  round trip stays one DAL batch, not K lazy resolutions:
  ```graphql
  query M6($ids: [Int!]!) { tracks(ids: $ids) {
      id class_id trajectory(window: 2) { frame_index bbox_x bbox_y bbox_w bbox_h confidence } } }
  ```
- Tiers: K ∈ {1, 5, 10} (same PAGE_SIZE grid as `phase2-batch-real`, so the
  new numbers are directly comparable to the recovered
  `results/phase2-batch-real/results.csv`). Metric: `page_latency_med` +
  `round_trip_count`, identical to the existing batch arm.
- Parity: concatenated K REST bodies field-equal the GraphQL `tracks` list,
  same order.

---

## 5. Proposed factorial and cost (Stage 2d + 3.5)

**Executor:** k6 open-loop constant-arrival-rate (Phase-2 `workload.js`
convention; closed-loop rejected for coordinated omission, as documented there).

**Calibration first (cheap, labeled CALIBRATION, excluded from analysis):**
for each protocol × {M1-high, M5-large, M6-K10} run a 60 s stepped-rate probe
to find the saturation ceiling (p95 knee / dropped_iterations > 0). Take the
**lower** of the two protocol ceilings per scenario family; set measured rates
at **20 / 40 / 60 / 80 %** of it plus one **overload** rate at 120 % (labeled,
analyzed separately). DET's ~117 req/s GraphQL ceiling does not transfer —
these queries hit SQLite.

**Data source stance:** scenarios are **DB-backed (SQLite via shared DAL)**.
This study **replaces** the retired in-memory isolation study; it does not
rerun it. Consequence: serialization-only isolation is lost — protocol effect
is now measured *including* a realistic storage layer. Optional recovery of
that isolation: a `APE_DATA_BACKEND=memory` toggle that preloads all 104,767
rows (~10 MB) into dicts behind the same DAL interface at startup — cheap,
reuses the existing env-var plumbing pattern (see Q1 below).

**Fixed protocol (carried over):** 1 warmup + 30 measured runs/cell, 90 s/run,
seed 42, pinning server 0–7 / k6 8–15 / sampler 31, servers alternated and
never co-resident, resumable `progress.log`, results to **new** session dirs
`results/mot-scenarios-<arm>/` only. run_uid hash MUST include session_id
(the documented sesi-A/B silent-resume trap in README §KRITIS).

**Grid:** protocol (2) × scenario (6) × tier (3) × rate (4 sub-saturation + 1 overload = 5)

| Variant | Cells | Measured runs | Wall-clock @ ~95 s/run |
|---|---:|---:|---|
| Full (5 rates) | 2×6×3×5 = 180 | 5,400 (+180 warmup) | ≈ **147 h ≈ 6.1 days** |
| Reduced (3 rates: 40/80/overload) | 108 | 3,240 (+108) | ≈ 88 h ≈ 3.7 days |
| Reduced + 60 s runs | 108 | 3,240 | ≈ 59 h ≈ 2.4 days |

(Caching axis NOT included above; adding Varnish on/off doubles every figure — see Q3.)

---

## 6. Open questions for approval (Stage 3)

1. **In-memory backend toggle** (`APE_DATA_BACKEND=memory|sqlite`): include as
   a 7th-scenario-free axis on M1 only (cheap serialization-isolation probe,
   +30 cells), full axis, or drop entirely?
2. **typed/passthrough impl_mode axis:** the 2×2 factorial from Phase 1 was
   never completed (factorial-B never ran). Resurrect it here (doubles runs),
   run a *small* typed-only arm on M1 to close that thread, or drop the axis
   and state Phase-2 servers are dict-passthrough by construction?
3. **Caching axis:** include Varnish on/off (ties M6 directly to H2/H3 and the
   existing phase2-batch-real numbers, but doubles wall-clock), or run
   cache-off only and lean on the already-recovered Phase-2 cache data?
4. **Rate grid:** full 5-rate (6.1 days) vs reduced 3-rate (3.7 days) vs
   reduced + 60 s runs (2.4 days)?
5. **Network:** run inside the netns/veth topology with the `constrained`
   profile (comparable to Phase-2 sessions) or direct loopback (comparable to
   Phase-1)? Recommend netns+constrained for M5/M6 (round-trip effects need
   nonzero RTT to be visible) — confirm.
6. **M5 REST contract:** keep the honest 2-round-trip client flow (proposed),
   or also add an embedded `?embed=trajectory` single-call variant as a third
   arm (REST-optimized counterfactual)?

**STOP. Awaiting approval before any implementation, k6 execution, or session creation.**
