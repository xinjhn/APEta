# Why the typed/passthrough `impl_mode` axis is not in the MOT scenario study

Status: approved decision Q2 of `design/SCENARIO_DESIGN.md` — axis **dropped**.

## The axis, historically

Phase 1 (DET, in-memory VCD pool) parameterized each server's internal
representation: `passthrough` (serve the pooled dicts as-is) vs `typed`
(rehydrate into typed objects before serialization). The 2×2 factorial
(protocol × impl_mode) was designed to separate protocol cost from
object-construction cost. Only **factorial-A** (rest=passthrough,
graphql=passthrough) was executed (`results/factorial-A/results.csv`, 2,880
rows); factorial-B (typed/typed) was never run.

## Why it is dropped here

1. **Phase-2 servers are dict-passthrough by construction.** The MOT servers
   serve `core/dal.py` row-dicts straight into the compact JSON encoder
   (REST: `_respond()`; GraphQL: Strawberry types constructed 1:1 from the
   row dict with no intermediate domain model). There is no second "typed"
   implementation to compare against — resurrecting the axis would mean
   writing new speculative server variants, which is out of scope for a
   study whose purpose is the scenario/tier/rate grid.
2. **Factorial-A already showed GraphQL mode-insensitivity on this stack.**
   In the completed factorial-A data, the GraphQL arm's latency profile was
   dominated by resolver/framework overhead, not by how the source objects
   were represented (see `FACTORIAL_DESIGN_SUMMARY.md` and
   `results/analysis_session1_preliminary/`): the passthrough fix (commit
   `824b195`) equalized the modes' data path, and the remaining REST-GraphQL
   gap persisted unchanged — i.e. the interesting variance is between
   protocols, not between impl modes.
3. **The serialization-isolation question Q2 gestured at is covered by Q1's
   memory-backend probe instead** (`APE_DATA_BACKEND=memory`, arm
   `mot-scenarios-m1mem`): it removes the storage layer while holding the
   passthrough data path constant, which isolates protocol+serialization
   cost more directly than a typed-rehydration arm would.

## What to state in the thesis

The Phase-2/MOT comparison is **dict-passthrough on both protocols by
construction**; the typed/passthrough axis from the Phase-1 design was
retired after factorial-A, and factorial-B (typed/typed) was never executed.
Any claim about object-rehydration cost must cite factorial-A only, not this
study.
