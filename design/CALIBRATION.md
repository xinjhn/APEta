# MOT scenario study — Stage-3 calibration (saturation ceilings → measured rates)

Date: 2026-07-02 · Branch: `mot-scenarios-impl` · Tool: `tools/calibrate_mot.py`
Raw data: `results/mot-scenarios-calibration/calibration.json` (+ per-step k6
summaries in `k6_summaries/`). Total probe time: 512.8 s.
**CALIBRATION runs only — excluded from all analysis.**

## Setup (identical to what the measured runs will use)

netns `ape-origin` + veth, netem **lan** on the veth host side (5 ms ± 1 ms
normal, 100 Mbit — approved Q5); server under `systemd-run --user --scope`
with CPUQuota 400% / MemoryMax 2048M, `taskset` server=0-7, k6=8-15;
single-worker uvicorn on port 8000 inside the netns, sqlite backend;
workload = `k6/workload_mot.js` (the exact benchmark script), open-loop
constant-arrival-rate, uniform access over the tier pool.

Probe procedure per protocol × heaviest family cell {M1-high, M5-w23,
M6-k10}: 12 s steps at 25→50→100→…(×2) until saturated, then 2 bisection
steps. **Saturated** := `dropped_iterations > 0` OR error rate > 1% OR
p95 > max(5 × baseline p95, 150 ms). Rate unit = **scenario iterations/s**
(an M6 "page" = 1 iteration = K REST calls or 1 GraphQL call), so ceilings
are directly comparable across protocols.

## Probe curves (p50/p95 in ms; dropped = k6 dropped_iterations)

### image family — probe M1-high (~7.2 KB payload, ≥54 detections/image)
| rate | REST p50 / p95 / dropped | GraphQL p50 / p95 / dropped |
|---:|---|---|
| 25  | 9.4 / 11.7 / 0 | 20.7 / 28.9 / 0 |
| 50  | 8.8 / 10.7 / 0 | 21.2 / 32.2 / 0 |
| 62  | — | 31.2 / 94.6 / 0 ← GraphQL ceiling |
| 75  | — | 2,030 / 2,913 / 39 **SAT** |
| 100 | 9.0 / 11.4 / 0 ← REST ceiling | 4,253 / 6,763 / 212 **SAT** |
| 125 | 5,107 / 7,265 / 278 **SAT** | — |
| 150 | 6,163 / 9,777 / 383 **SAT** | — |
| 200 | 23,208 / 28,310 / 857 **SAT** | — |

### track family — probe M5-w23 (47-point trajectory; REST = 2 round trips/iter)
| rate | REST p50 / p95 / dropped | GraphQL p50 / p95 / dropped |
|---:|---|---|
| 25  | 8.0 / 10.1 / 0 | 20.1 / 23.2 / 0 |
| 50  | 7.6 / 9.5 / 0 | 20.4 / 24.7 / 0 |
| 62  | — | 21.2 / 68.4 / 0 ← GraphQL ceiling |
| 75  | — | 1,520 / 2,290 / 17 **SAT** |
| 100 | 8.0 / 10.8 / 0 ← REST ceiling | 3,691 / 6,127 / 182 **SAT** |
| 125 | 9.9 / **1,277** / 0 **SAT** (p95-knee only — p50 still 9.9 ms: bimodal onset of queueing) | — |
| 150/200 | 2,283–3,676 p50, 323–603 dropped **SAT** | — |

### page family — probe M6-k10 (1 iteration = 10 REST calls vs 1 composite GraphQL call)
| rate | REST p50 / p95 / dropped | GraphQL p50 / p95 / dropped |
|---:|---|---|
| 25 | 7.7 / 10.5 / 0 | 19.9 / 24.1 / 0 |
| 37 | 8.1 / 11.1 / 0 | — |
| 43 | 8.7 / 13.1 / 0 ← REST ceiling | — |
| 50 | 291 / 448 / 58 **SAT** | 19.9 / 25.7 / 0 |
| 62 | — | 20.4 / 59.5 / 0 ← GraphQL ceiling |
| 75/100 | — | 1,455–3,547 p50, 14–177 dropped **SAT** |

## Ceilings and derived rates (40% / 80% / 120% of the LOWER protocol ceiling)

| Family (scenarios) | REST ceiling | GraphQL ceiling | Lower | **r40** | **r80** | **r120_overload** |
|---|---:|---:|---:|---:|---:|---:|
| image (M1–M4) | 100 | 62 | **62** | **25** | **50** | **74** |
| track (M5, M5E) | 100 | 62 | **62** | **25** | **50** | **74** |
| page (M6) | 43 | 62 | **43** | **17** | **34** | **52** |

Env values for run-plan generation:

    APE_MOT_RATES_IMAGE=25,50,74
    APE_MOT_RATES_TRACK=25,50,74
    APE_MOT_RATES_PAGE=17,34,52

## Observations (descriptive, for the report's context — not conclusions)

1. **GraphQL's ceiling is ~62 iter/s in ALL three families**, regardless of
   whether the query is a 7 KB detection list, a 47-point trajectory, or a
   10-track composite — consistent with a framework/resolver-bound cap
   rather than a data-volume-bound one. (Same pattern as the Phase-1 DET
   ceiling ~117 req/s on loopback without netem/CPU caps; the absolute
   number here is lower under the 400% CPUQuota + netns + lan topology.)
2. **REST's per-HTTP-call capacity is workload-dependent**: ~100 rps on the
   heavy M1-high/M5-w23 calls but ~430 rps on the light w2 trajectory calls
   (43 pages/s × 10 calls) — so in the page family REST, not GraphQL, is the
   binding ceiling. K round trips is exactly the regime the M6 arm measures.
3. The knee is a sharp open-loop queueing collapse (p50 9 ms → 5 s between
   100 and 125 iter/s for REST-image), so the ±(one bisection step)
   uncertainty on each ceiling (≤ 13 iter/s) does not move the derived
   sub-saturation rates into the unstable region: r80 sits ≥ 20% below every
   observed clean rate's knee.
4. REST M5-w23@125 saturated on the p95 knee alone (p95 1.28 s, p50 9.9 ms,
   0 dropped) — the earliest, most sensitive symptom of capacity; supports
   the knee rule rather than dropped-only detection.

**Next: Stage-4 STOP. No measured runs until explicit go-ahead.**
