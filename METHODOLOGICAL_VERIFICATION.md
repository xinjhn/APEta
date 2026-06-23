# Methodological Verification Checklist

## Pre-Experiment Verification (REQUIRED)

Before running 4,320 factorial experiments, execute these checks:

### **1. Symmetry Verification**
```bash
APE_POOL_JSON=/path/to/inferensi_vcd.json python tools/verify_factorial_symmetry.py
```

This verifies:
- ✅ REST passthrough produces identical data structures as REST typed
- ✅ GraphQL typed produces identical data structures as GraphQL passthrough
- ✅ Cross-protocol parity maintained (REST ≡ GraphQL for same query)

**If this fails:** DO NOT PROCEED. Fix implementation bugs first.

---

### **2. Parity Test (Existing)**
```bash
APE_POOL_JSON=/path/to/inferensi_vcd.json python tests/test_parity.py
```

Expected output: `Paritas: 48/48 kombinasi identik.`

**If this fails:** Data structures differ between protocols → invalid comparison.

---

### **3. Health Check Verification**
Start each server and verify `/health` endpoint returns correct mode:

```bash
# REST passthrough
APE_REST_MODE=passthrough uvicorn rest_server:app --port 8000
curl http://localhost:8000/health | jq .mode
# Expected: "passthrough"

# REST typed
APE_REST_MODE=typed uvicorn rest_server:app --port 8000
curl http://localhost:8000/health | jq .mode
# Expected: "typed"

# GraphQL typed
APE_GRAPHQL_MODE=typed uvicorn graphql_server:app --port 8000
curl http://localhost:8000/health | jq .mode
# Expected: "typed"

# GraphQL passthrough
APE_GRAPHQL_MODE=passthrough uvicorn graphql_server:app --port 8000
curl http://localhost:8000/health | jq .mode
# Expected: "passthrough"
```

---

## Methodological Requirements Met

### **✅ Requirement 1: Symmetric Implementation Support**
Both protocols support both modes:
- REST: `passthrough` (dict) and `typed` (Pydantic objects)
- GraphQL: `typed` (Strawberry objects) and `passthrough` (generic `SimpleNamespace`, NOT a raw dict)

**CORRECTION (post-audit):** GraphQL passthrough originally returned a raw `dict`.
This crashed 100% of requests -- Strawberry resolves fields via `getattr()`, not
`Mapping.get()`, so a bare dict is not a valid resolver return value for a typed
field. Confirmed by actually running `tools/verify_factorial_modes.py`, which
failed with `AttributeError` before the fix. Now fixed: passthrough builds a
nested `SimpleNamespace` (attribute-accessible, but no schema/type annotations --
the closest functional equivalent of REST's untyped dict under Strawberry's
resolution model). See `graphql_server.py`'s module docstring for detail.

**Verification:** Code inspection + health endpoint check + actually running
`tools/verify_factorial_modes.py` (don't just read the code -- it was previously
believed correct without ever having been executed)

---

### **✅ Requirement 2: Identical Data Structures Within Protocol**
Both modes within each protocol produce byte-identical payloads:
- REST passthrough JSON ≡ REST typed JSON (after serialization)
- GraphQL typed JSON ≡ GraphQL passthrough JSON (after serialization)

**Verification:** `tools/verify_factorial_symmetry.py`

**CORRECTION (post-audit) -- this was NOT actually acceptable, it was a real bug:**
The original partial-pattern resolver built the FULL `Detection` object
(including `bounding_box`) on every call regardless of GraphQL's selection set,
relying on Strawberry to filter fields only at serialization time. REST's
`partial` endpoint, by contrast, strips `bounding_box` via `core/projection.py`
BEFORE building any response object. This was not "~1-2ms negligible" -- it
meant GraphQL's `partial` pattern paid the SAME server-side construction cost
as `baseline` while REST paid less, contaminating any latency comparison for
that pattern specifically (the wire payload was unaffected, only the
server-side compute cost). Fixed: the resolver now inspects
`info.selected_fields` and strips unrequested fields BEFORE construction,
mirroring REST's projection. Wire payload size is unaffected by this fix
(confirmed identical bytes before/after); only server-side construction cost
changed.

---

### **✅ Requirement 3: No Cherry-Picking**
The factorial design prevents cherry-picking because:
1. All 4 conditions use the **same experimental matrix** (patterns, densities, concurrency)
2. All 4 conditions use the **same pool JSON** (identical data source)
3. All 4 conditions use the **same k6 load test** (identical client behavior)
4. Implementation mode is controlled via environment variables, not code changes

**What could still be criticized:**
- Single dataset (YOLO on VisDrone) → limited generalizability
- ~~Localhost testing → no network RTT effects~~ ADDRESSED: see RQ2 sub-study
  (`tools/run_batch_study.py` + `tools/netem.sh`) -- tests N+1 batching under
  `tc netem`-emulated RTT/bandwidth (Lighthouse Fast/Slow 3G presets). This
  study cannot answer RQ1's question (single-resource server-processing
  overhead) and RQ1 cannot answer RQ2's (multi-resource round-trip avoidance)
  -- they are deliberately separate, complementary RQs, not redundant.
- FastAPI/Strawberry may not represent all REST/GraphQL implementations

**Mitigation:** Explicitly acknowledge these limitations in "Threats to Validity" section

---

### **✅ Requirement 4: Controlled Variables**
Variables held constant across all 4 conditions:
- Pool JSON file (same inferensi_vcd.json)
- Seed value (APE_SEED=42)
- Concurrency levels (10, 50, 100)
- Density levels (low, medium, high)
- Pattern definitions (baseline, partial, filtered, aggregate)
- Runs per cell (30)
- Server configuration (1 worker, host 127.0.0.1, port 8000)
- k6 version and test script
- Python package versions
- OS environment

**Variables that differ (by design):**
- Protocol (REST vs GraphQL)
- Implementation mode (passthrough vs typed)

---

## Potential Issues to Watch For

### **Issue 1: Batch Effects Between Sessions**
If you run sessions on different days or after system updates:
- Python packages may update
- OS state may change (background processes, CPU frequency scaling)
- Pool JSON may be regenerated with different random seed

**Mitigation:**
- Run all 4 sessions consecutively without interruption
- Verify package versions before/after (`pip freeze > requirements_before.txt`, then compare)
- Use same pool JSON file for all sessions

---

### **Issue 2: Incomplete Factorial Matrix**
If one session fails or is interrupted:
- ANOVA requires balanced design (equal runs per cell)
- Missing cells reduce statistical power

**Mitigation:**
- Monitor progress.log during each session
- Verify results.csv has expected row count after each session:
  ```bash
  wc -l results/factorial-c*/results.csv
  # Each should have ~1,081 lines (1 header + 1,080 data rows)
  ```

---

### **Issue 3: Mode Misconfiguration**
If environment variables are set incorrectly:
- Session runs with wrong mode → contaminates factorial design
- Hard to detect after the fact

**Mitigation:**
- Always verify `/health` endpoint before starting k6 load test
- Log mode in session log (already done via `write_session_log`)
- Check impl_mode column in results.csv after completion

---

## Statistical Analysis Plan

**CORRECTION (post-audit): only 2 sessions are needed, not 4.** The original
plan above assumed 4 single-protocol sessions (mirrored by the now-deleted
`tools/combine_factorial_results.py`, which assumed each results.csv held only
one protocol). That never matched reality: `run_experiment.py` ALWAYS
alternates REST and GraphQL blocks within one session. Since each session
already yields data for BOTH protocols, 2 sessions with complementary
`impl_mode` pairs cover all 4 cells of the 2x2 with zero redundancy:

**CRITICAL -- separate `APE_RESULTS_DIR` per session is not optional.**
`_run_uid()` in `make_run_plan.py` hashes `protocol|pattern|density|concurrency|
is_warmup|run_index` only -- `session_id` and `impl_mode` are NOT part of the
hash. If both sessions share a `results_dir`, Session B's run_uids are
byte-identical to Session A's; `load_done_uids()` will see them all already
present in Session A's `results.csv` and `find_resume_index()` returns
immediately -- Session B finishes instantly, writes zero rows, no error raised.
This is a silent full-session data loss, found by tracing the resume logic
before launching the real run (not by running it and discovering it empty).

```bash
# Session A: both passthrough -> covers (rest,passthrough) + (graphql,passthrough)
APE_IMPL_MODE_REST=passthrough APE_IMPL_MODE_GRAPHQL=passthrough \
APE_SESSION_ID=factorial-A APE_RESULTS_DIR=results/factorial-A \
python orchestrator/run_experiment.py

# Session B: both typed -> covers (rest,typed) + (graphql,typed)
APE_IMPL_MODE_REST=typed APE_IMPL_MODE_GRAPHQL=typed \
APE_SESSION_ID=factorial-B APE_RESULTS_DIR=results/factorial-B \
python orchestrator/run_experiment.py
```

(Decoupled pairs, e.g. A=(passthrough,typed) + B=(typed,passthrough), work
identically well -- either way, 2 sessions x 2 protocols = 4 unique cells.)

After completing both sessions:

### **Step 1: Combine Results**
No dedicated script needed -- `run_experiment.py` already records the correct
`impl_mode` per row (this required fixing a `cfg`/`self.cfg` `NameError` bug
found by actually running a pilot session, see audit). Just concatenate:
```python
import pandas as pd
df = pd.concat([pd.read_csv("results/factorial-A/results.csv"),
                pd.read_csv("results/factorial-B/results.csv")], ignore_index=True)
df.to_csv("results_combined.csv", index=False)
```

### **Step 2: Verify Balance**
```python
import pandas as pd
df = pd.read_csv('results_combined.csv')
print(df.groupby(['protocol', 'impl_mode']).size())
# Should show ~1,080 runs per condition (2,160 measured rows per session / 2 protocols)
```

### **Step 3: Per-Cell Mann-Whitney U + Vargha-Delaney A12 / Cliff's delta**
```bash
python tools/analyze_factorial.py --input results_combined.csv
```

**CORRECTION (post-audit): this is NOT a two-way ANOVA anymore.** The original
script pooled every `pattern x density x concurrency` cell into one `ols` call
-- pseudo-replication, plus ANOVA's normality assumption is almost certainly
violated by right-skewed latency data (queueing effects). Rewritten to run
Mann-Whitney U + Â₁₂/Cliff's delta PER `(pattern, density, concurrency)` cell,
Holm-corrected within each hypothesis family (protocol effect, impl_mode
effect), per Arcuri & Briand (ICSE 2011). See script docstring for full
rationale and citations. Reports on:
- lat_p95 (primary metric)
- xproc_p95 (server processing time)
- throughput_rps
- cpu_mean
- rss_mean_mb

### **Step 4: Interpret Results**

**CORRECTION (post-audit):** the variance-decomposition table below assumed
ANOVA's `sum_sq`/`PR(>F)` output, which the rewritten script does not produce
(no pooled model = no variance-% to report). Interpret the per-cell report
(`factorial_analysis_report.txt`) instead:

| Pattern across cells | Interpretation |
|---|---|
| `protocol_effect` family: most cells significant (Holm-corrected) AND same direction (e.g. always negative delta = rest faster) | Protocol effect is robust across patterns/densities/concurrency |
| `protocol_effect` family: significant in some cells, not others, or sign flips | Protocol effect is conditional on pattern/density/concurrency -- report which cells, don't generalize |
| `impl_mode_effect` family: consistently larger \|delta\| than `protocol_effect` for the same cells | Implementation (type safety) explains more than protocol -- matches the original confound hypothesis |
| `impl_mode_effect` delta sign/magnitude differs between `protocol=rest` and `protocol=graphql` | Descriptive evidence of interaction (type-safety cost is protocol-dependent) -- confirm formally with ART (Wobbrock et al., CHI 2011) before claiming significance |

---

## Decision Criteria

**Proceed with experiment if:**
- ✅ `verify_factorial_symmetry.py` passes
- ✅ `verify_factorial_modes.py` passes (don't just read the code -- RUN it; this caught a real `AttributeError` crash in passthrough mode that the code looked correct without)
- ✅ `test_parity.py` shows 48/48 identical
- ✅ All 4 (protocol x impl_mode) health endpoint combinations return correct modes
- ✅ You can commit uninterrupted time for 2 full sessions (each session's duration scales with N_MEASURED x concurrency levels x patterns x densities x 2 protocols -- check `orchestrator/run_experiment.py`'s progress.log ETA early in a real run rather than assuming a fixed number)

**Do NOT proceed if:**
- ❌ Any verification script fails
- ❌ You cannot guarantee consistent environmental conditions
- ❌ You need results immediately (cannot afford reruns if something fails)

---

## Post-Experiment Validation

After completing both sessions:

1. **Check row counts (2 sessions, not 4):**
   ```bash
   for f in results/factorial-A/results.csv results/factorial-B/results.csv; do echo "$f: $(wc -l < $f)"; done
   ```

2. **Verify impl_mode column:**
   ```bash
   python3 -c "import pandas as pd; df=pd.read_csv('results_combined.csv'); print(df.groupby(['protocol','impl_mode']).size())"
   # Should show all 4 (protocol, impl_mode) combinations present, roughly equal counts
   ```

3. **Sanity check latency distributions:**
   ```bash
   python3 << 'EOF'
   import pandas as pd
   df = pd.read_csv('results_combined.csv')
   summary = df.groupby(['protocol', 'impl_mode'])['lat_p95'].describe()
   print(summary)
   EOF
   ```
   **CORRECTION (post-audit):** don't anchor on specific magnitude numbers --
   the small pilot run in the audit (n=4/cell, 2 patterns only) showed REST
   passthrough/typed nearly indistinguishable (~28-33ms both) and GraphQL
   passthrough/typed also nearly indistinguishable (~116-159ms both), i.e. the
   `impl_mode` effect was small/noisy at pilot scale -- it may or may not
   separate cleanly at full scale and n=30. What DOES need checking:
   - If `protocol` shows no separation at all (rest ≈ graphql): mode switching
     or server startup likely failed silently -- check `/health` mode field
     and `error_rate` column before trusting any number.
   - If `impl_mode` shows no separation within a protocol across the FULL
     dataset (not just one pilot's noise): that itself is a valid finding for
     GraphQL specifically (Strawberry's `@strawberry.type` does no runtime
     validation, unlike Pydantic's `BaseModel` for REST's typed mode) -- see
     audit notes on this asymmetry, don't assume it's a bug.

---

**This checklist ensures methodological rigor. Do not skip any step.**
