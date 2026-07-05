# FACTORIAL DESIGN IMPLEMENTATION SUMMARY (Path B)

> **SUPERSEDED IN PART -- see `METHODOLOGICAL_VERIFICATION.md` for corrections.**
> This document describes the design AS ORIGINALLY WRITTEN, before an audit
> found and fixed real bugs in it (never having been executed end-to-end
> before the audit). Specifically wrong below: GraphQL passthrough described
> as "returns raw dictionaries" -- this crashed 100% of requests (Strawberry
> resolves via `getattr`, not dict access); `_dict_image_detections()` /
> `_dict_aggregate()` were renamed `_ns_image_detections()` / `_ns_aggregate()`
> and now build `SimpleNamespace`, not dicts. Treat this file as historical
> intent, not current implementation truth -- read the actual code or
> `METHODOLOGICAL_VERIFICATION.md` for what's actually running.

## Overview

This document summarizes the implementation of the **2×2 factorial design** that isolates protocol overhead from implementation strategy effects in the REST vs. GraphQL benchmark.

---

## What Was Changed

### 1. Server Implementations

#### [`rest_server.py`](file:///home/ubuntu/APE/APEta/rest_server.py)
- **Added:** Pydantic models for typed mode (`DimensionsModel`, `DetectionModel`, `ImageEnvelopeModel`, etc.)
- **Added:** Environment variable `APE_REST_MODE` with two values:
  - `passthrough`: Returns raw dictionaries (zero-copy, fast baseline)
  - `typed`: Reconstructs Pydantic objects (~70-90ms overhead, symmetric with GraphQL)
- **Modified:** All endpoints now check `REST_MODE` and branch accordingly

#### [`graphql_server.py`](file:///home/ubuntu/APE/APEta/graphql_server.py)
- **Added:** Environment variable `APE_GRAPHQL_MODE` with two values:
  - `typed`: Full Strawberry object reconstruction (slow baseline)
  - `passthrough`: Returns raw dictionaries without type instantiation (symmetric with REST)
- **Added:** Helper functions `_dict_image_detections()` and `_dict_aggregate()` for passthrough mode
- **Modified:** Resolvers now check `GRAPHQL_MODE` and bypass object creation in passthrough mode

### 2. Orchestrator Updates

#### [`orchestrator/config.py`](file:///home/ubuntu/APE/APEta/orchestrator/config.py)
- **Added:** Config fields `impl_mode_rest` and `impl_mode_graphql`
- **Added:** Environment variables `APE_IMPL_MODE_REST` and `APE_IMPL_MODE_GRAPHQL`
- **Default values:** `rest=passthrough`, `graphql=typed` (reproduces original asymmetric experiment)

#### [`orchestrator/run_experiment.py`](file:///home/ubuntu/APE/APEta/orchestrator/run_experiment.py)
- **Modified:** [`start_server()`](file:///home/ubuntu/APE/APEta/orchestrator/run_experiment.py#L379-L396) now passes mode env vars to server processes
- **Modified:** `RESULTS_FIELDNAMES` includes new `impl_mode` column
- **Modified:** Result row construction records which implementation mode was used

### 3. New Tools

#### [`tools/verify_factorial_modes.py`](file:///home/ubuntu/APE/APEta/tools/verify_factorial_modes.py)
- Smoke test script to verify both servers support both modes correctly
- Checks health endpoint returns correct mode
- Verifies data parity between modes (structure identical, only performance differs)
- **Usage:** `APE_POOL_JSON=/tmp/synthetic.json python tools/verify_factorial_modes.py`

#### [`tools/analyze_factorial.py`](file:///home/ubuntu/APE/APEta/tools/analyze_factorial.py)
- Statistical analysis script for 2×2 factorial design
- Performs **two-way ANOVA** on key metrics (latency, throughput, CPU, memory)
- Generates visualizations (box plots, interaction effects)
- Produces automated report with key findings
- **Prerequisites:** `pip install pandas statsmodels seaborn matplotlib`
- **Usage:** `python tools/analyze_factorial.py --input results_combined.csv`

### 4. Documentation

#### [`README.md`](file:///home/ubuntu/APE/APEta/README.md)
- Updated with factorial design explanation
- Added execution instructions for all 4 experimental conditions
- Documented the statistical analysis workflow

---

## The 4 Experimental Conditions

| Condition | Protocol | Implementation Mode | Purpose | Expected Latency |
|-----------|----------|-------------------|---------|------------------|
| 1 | REST | `passthrough` | Baseline (fastest) | ~30ms |
| 2 | REST | `typed` | Cost of type safety in REST | ~100-120ms |
| 3 | GraphQL | `typed` | Baseline (slowest) | ~130ms |
| 4 | GraphQL | `passthrough` | Pure protocol overhead | ~40-50ms |

---

## How to Run the Factorial Experiment

### Step 1: Verify Modes Work
```bash
APE_POOL_JSON=/path/to/inferensi.json python tools/verify_factorial_modes.py
```

### Step 2: Run 4 Separate Sessions

**Session 1: REST passthrough**
```bash
APE_POOL_JSON=/path/to/inferensi.json \
APE_IMPL_MODE_REST=passthrough \
APE_SESSION_ID=factorial-rest-passthrough \
python orchestrator/run_experiment.py
```

**Session 2: REST typed**
```bash
APE_POOL_JSON=/path/to/inferensi.json \
APE_IMPL_MODE_REST=typed \
APE_SESSION_ID=factorial-rest-typed \
python orchestrator/run_experiment.py
```

**Session 3: GraphQL typed**
```bash
APE_POOL_JSON=/path/to/inferensi.json \
APE_IMPL_MODE_GRAPHQL=typed \
APE_SESSION_ID=factorial-graphql-typed \
python orchestrator/run_experiment.py
```

**Session 4: GraphQL passthrough**
```bash
APE_POOL_JSON=/path/to/inferensi.json \
APE_IMPL_MODE_GRAPHQL=passthrough \
APE_SESSION_ID=factorial-graphql-passthrough \
python orchestrator/run_experiment.py
```

### Step 3: Combine Results
```bash
# Concatenate all 4 results.csv files
cat results/factorial-rest-passthrough/results.csv \
    results/factorial-rest-typed/results.csv \
    results/factorial-graphql-typed/results.csv \
    results/factorial-graphql-passthrough/results.csv \
    > results_combined.csv
```

### Step 4: Analyze
```bash
pip install pandas statsmodels seaborn matplotlib
python tools/analyze_factorial.py --input results_combined.csv
```

---

## Expected Outcomes

Based on the initial audit, we expect:

1. **Main effect of implementation mode (type safety):** ~70-90ms
   - This explains most of the original 100ms gap
   - Similar cost for both REST and GraphQL when using typed models

2. **Main effect of protocol (GraphQL vs REST):** ~10-30ms
   - After controlling for implementation, pure protocol overhead is small
   - Due to AST parsing, validation, resolver traversal

3. **Interaction effect:** <5ms (not significant)
   - Type safety costs similar amount regardless of protocol
   - Suggests object allocation overhead is framework-independent

4. **Statistical significance:**
   - Implementation mode will explain >80% of variance in latency
   - Protocol will explain <15% of variance
   - Interaction will be non-significant (p > 0.05)

---

## Research Reframing

With this factorial design, your research question shifts from:

**Old (invalid):** "What is the protocol overhead of GraphQL vs REST?"

**New (valid):** "What are the trade-offs between type safety and performance in API architecture, and how do these trade-offs manifest across REST and GraphQL protocols?"

This reframing:
- ✅ Acknowledges implementation strategy matters more than protocol choice
- ✅ Provides actionable guidance for API designers
- ✅ Generalizes beyond specific frameworks to broader architectural principles
- ✅ Addresses a real engineering trade-off (developer ergonomics vs. raw performance)

---

## Publication Strategy

With the factorial design completed, target venues:

| Venue | Fit | Reason |
|-------|-----|--------|
| **IEEE ICSA** | ★★★★★ | Architecture-focused, values empirical studies of design trade-offs |
| **ACM ESEC/FSE** | ★★★★☆ | Empirical software engineering, rigorous methodology required |
| **IEEE ICSE-SEIP** | ★★★★☆ | Software engineering in practice, practitioner-focused findings |
| **ACM SAC** | ★★★☆☆ | General software architecture, lower bar for novelty |

**Key selling point:** You're not just benchmarking two frameworks; you're quantifying a fundamental tension in API design (type safety vs. performance) that applies to any typed API framework.

---

## Next Steps

1. ✅ **Completed:** Implement factorial design in code
2. ⏳ **To Do:** Run verification script (`verify_factorial_modes.py`)
3. ⏳ **To Do:** Execute 4 experimental sessions (estimated 2-3 hours total)
4. ⏳ **To Do:** Combine results and run statistical analysis
5. ⏳ **To Do:** Reframe paper around "type safety vs. performance trade-off"
6. ⏳ **To Do:** Submit to target venue

**Estimated time to completion:** 3-5 days (including re-running benchmarks and rewriting paper)

---

## Files Modified/Created

### Modified:
- `/home/ubuntu/APE/APEta/rest_server.py`
- `/home/ubuntu/APE/APEta/graphql_server.py`
- `/home/ubuntu/APE/APEta/orchestrator/config.py`
- `/home/ubuntu/APE/APEta/orchestrator/run_experiment.py`
- `/home/ubuntu/APE/APEta/README.md`

### Created:
- `/home/ubuntu/APE/APEta/tools/verify_factorial_modes.py`
- `/home/ubuntu/APE/APEta/tools/analyze_factorial.py`
- `/home/ubuntu/APE/APEta/FACTORIAL_DESIGN_SUMMARY.md` (this file)

---

**Implementation Date:** 2026-06-23  
**Status:** ✅ Code complete, ready for experimental execution  
**Next Action:** Run verification script, then execute 4 experimental sessions
