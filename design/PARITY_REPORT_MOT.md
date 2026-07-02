# MOT scenario parity report (Stage-2 hard gate)

Date: 2026-07-02 · Branch: `mot-scenarios-impl` · Suite: `tests/test_parity_mot.py`
Command: `venv/bin/python -m pytest tests/test_parity_mot.py -v`

## Verdict: **GREEN — 18 passed, 2 skipped, 0 failed** (skips are by design:
the two SQL-log assertions are sqlite-backend concepts and are skipped on the
memory backend, where they are meaningless rather than unverified).

The whole suite runs **once per data backend** (`APE_DATA_BACKEND=sqlite` and
`=memory`) via a parametrized fixture using the same dispatch the orchestrator
uses. Sampling per scenario: seeded ids × all 3 tiers × 4 seeds (42–45), ids
drawn through the same shared pickers the benchmark uses
(`core/selection.py`, `core/dal.py`).

## What each criterion measured

| Criterion (design §4) | Test | Result |
|---|---|---|
| M1/M2/M3 field-level equality incl. ordering, both backends | `test_image_scenario_parity[{backend}-{M1,M2,M3}]` | PASS ×6 |
| Constant envelope delta per scenario | same tests + `test_m4_aggregate_parity` | PASS — **19 B** constant for M1/M2/M3 (`{"data":{"image":` + `}}`) across REST payloads spanning 130–12,149 B; **13 B** for M4 (19 − 6 for `image_id` vs `id`) |
| M2 exactly-2-fields on BOTH sides (no send-full-and-strip) | inside `test_image_scenario_parity[..-M2]` | PASS |
| M3 empty filtered result = 200 + `[]`, both protocols | `test_m3_empty_result_is_valid` | PASS ×2 backends |
| M4 aggregate equality + class_id-ascending order | `test_m4_aggregate_parity` | PASS ×2 |
| M5 union(REST #1, REST #2) == GraphQL `data.track`; trajectory ordered; delta constant | `test_m5_nested_parity_and_embed` | PASS ×2 |
| M5-embed byte-identical to the 2-RT content | same test (`embed body == trajectory body`) | PASS ×2 |
| M6 concatenated K REST bodies == GraphQL `tracks` list, same order (K ∈ 1,5,10) | `test_m6_page_parity` | PASS ×2 |
| M6 one composite query = ONE DAL batch (exactly 2 IN-clause SQL stmts, no lazy N+1) | `test_m6_single_dal_batch` | PASS (sqlite) / SKIP (memory, no SQL) |
| M5 same access path (table set REST-2-calls == GraphQL) | `test_m5_same_access_path` | PASS (sqlite) / SKIP (memory) |
| Benchmark sends the exact verified queries (k6 ↔ test drift guard) | `test_queries_match_k6_workload` | PASS |
| Memory backend byte-identical to sqlite (ordering incl.) for images, trajectories, batches, seeded picks | `test_memory_backend_matches_sqlite_bytes` | PASS |

Legacy suites re-run unchanged: `tests/test_parity.py` 8/8 PASS;
`test_batch_fairness.py` / `test_cache_fairness.py` skips are the
pre-existing `APE_RUN_CACHE_TESTS=1` env gates, not regressions.

## Contract decisions locked in by this gate (deviations from the design doc's sketches)

1. **M1/M3 REST uses an explicit `fields=<all 6>` projection.** The bare
   `/detections` endpoint also returns `id` and `track_id`; without the
   projection, key-for-key parity fails and REST carries extra payload bytes
   GraphQL doesn't. The design doc's payload estimates were computed on the
   canonical 6 `DETECTION_FIELDS`, which this contract now enforces on both
   protocols. (The bare endpoint is unchanged for phase-2 compatibility.)
2. **M1 image envelope uses `sequence_name`,** not the design doc's
   `sequence_id` slip — `sequence_name` is what the shared DAL/REST body
   actually contains.
3. **M5/M6 GraphQL selections include trajectory-point `id` and `image_id`**
   (REST's trajectory endpoint returns them unprojected; parity requires the
   union/concatenation to match key-for-key).
4. **GraphQL `Track` gained `sequence_id`; `trajectory` gained
   `center_frame`** — both parity-required (REST's M5 second call passes
   `center_frame` = track midpoint).
5. **M4 REST body is `{"image_id":…,"class_counts":[…]}`** exactly per the
   design doc; the `image_id`↔`id` rename is part of the constant 13 B
   envelope delta, verified constant across all samples.

**Gate status: OPEN for calibration (Stage 3). Measured runs remain blocked
pending explicit go-ahead (Stage 4).**
