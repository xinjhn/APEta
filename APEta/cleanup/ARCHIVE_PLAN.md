# ARCHIVE PLAN — /home/ubuntu/APE/APEta (vm-kota515-jeihan)

Generated: 2026-07-04 · Branch: `workspace-cleanup` (created from `mot-scenarios-impl` @ eb0323a)
Mode: **PROPOSE-ONLY. Nothing moved. Awaiting approval.**

Live-run status at time of writing: `orchestrator/run_experiment.py` (PID 581043)
**RUNNING**, run 1573/3240, writing `results/mot-scenarios-core/`. Not touched.

---

## 0. TWO BLOCKERS YOU MUST DECIDE BEFORE ANY MOVE (bitter truth first)

### Blocker A — `git mv` is impossible for essentially everything we'd archive
`results/` is **entirely untracked by git** (`git ls-files results/` → 0 files;
`.gitignore` only excludes a few oversized `*.log`). The tarball and `scratch/`
are also untracked. `git mv` **errors on untracked paths** — so the Step-4 hard
rule "git mv only, reversible via `git revert`" **cannot be honored** for any
candidate here. Options:
  - (A1) Use plain `mv` into `archive/2026-07-03/…` (preserves paths, fully
    reversible by moving back — but no git history/atomic revert). Recommended,
    since git never tracked these anyway.
  - (A2) `git add` each candidate first, then `git mv` (pollutes history with a
    one-time add of large binaries; adds ~90 MB+ to the repo). Not recommended.
  - (A3) Do nothing until you decide.
I did **not** pick for you. No moves happen until you choose.

### Blocker B — the reference rule blocks almost every large candidate
The hard rule says: never archive anything referenced by a KEEP markdown, the
thesis (`laporan/`), an analysis script, or an orchestrator config. When applied
literally, **most superseded material is referenced** — chiefly by
`design/STUDY_COMPARISON.md`, a provenance ledger (created Jun/Jul, NOT itself
cited by the thesis) that catalogs every session including the superseded ones,
and by `laporan/reproducibility/WORKSPACE_INVENTORY.md`.

Consequence: the only *cleanly* archivable material is ~**90 MB** of untracked
scratch + un-referenced pilots + one redundant tarball. The headline space hog,
`archive_pre_factorial/` (1.4 GB), is **referenced** and therefore lands in
UNSURE, not ARCHIVE-CANDIDATE. You must decide whether a *provenance-ledger
mention* (documentation of a superseded dir) counts as a blocking reference. I
treated it as blocking, per the rule as written.

---

## 1. Counts per bucket

| Bucket | Items | Size |
|---|---|---|
| KEEP | live core + 10 real sessions + combined + factorial-A + sesi-1 + calibration + design/ + all source + cited loose files | ~9.5 GB (untouched) |
| ARCHIVE-CANDIDATE (cleanly safe) | 8 groups | **~90 MB** |
| UNSURE (referenced or ambiguous → your call) | 6 items | ~1.41 GB |

Total that would move **if only the safe candidates are approved: ~90 MB.**

---

## 2. ARCHIVE-CANDIDATE list (safe: not path-referenced by thesis / script / config)

Reference-check performed via `grep -rIn` across `laporan/`, `APEta/tools`,
`orchestrator`, `core`, `k6`, `design`, and all KEEP `*.md`.

| Path | Size | Reason | Reference check |
|---|---|---|---|
| `scratch/varnish-*` (24 dirs) | 168 KB | Stale Varnish work dirs from past runs; gitignored; **no varnish process running now**, live core run does not use them (all pre-date Jul 2 run) | none |
| `scratch/id_pool.json` | 240 KB | Stale Phase-2 id pool; gitignored. Live run uses `id_pool_mot.json` (updated Jul 2 10:13) — that one is KEEP | none |
| `scratch/k6_summaries/` | 60 KB | Gitignored transient k6 summary scratch | none |
| `results/phase2-pilot-v2` | 8.8 MB | Superseded pilot iteration | not path-referenced (only "pilot … v5" collectively named in STUDY_COMPARISON) |
| `results/phase2-pilot-v3` | 1.7 MB | Superseded pilot iteration | not path-referenced |
| `results/phase2-pilot-v4` | 1.7 MB | Superseded pilot iteration | not path-referenced |
| `results/phase2-pilot-v5` | 1.7 MB | Superseded pilot iteration | not path-referenced |
| `results/archive_pre_pilot/` | 16 KB | Pre-pilot archive, labeled "Pilot-scale, superseded" | mentioned **only** in `design/STUDY_COMPARISON.md` ledger |
| `results/archive_pilot_final/` | 44 KB | Pilot archive, labeled "superseded" | mentioned **only** in `design/STUDY_COMPARISON.md` ledger |
| `ape_results_run-sesi-1_20260622_143624.tar.gz` | 75 MB | Redundant tarball snapshot of `results/archive_run-sesi-1/` (a KEEP dir); untracked | none — **but confirm it isn't your intentional off-tree backup before archiving** |

Note: `archive_pre_pilot` / `archive_pilot_final` are referenced by the
STUDY_COMPARISON ledger only. If you consider a ledger mention non-blocking
(recommended — the ledger documents that they are superseded), they stay here.
If blocking, move them to UNSURE.

---

## 3. Markdown dedup (PROPOSE-ONLY — no merges, no content edits)

`laporan/` (the thesis, a sibling of `APEta/`, KEEP entirely) is **out of scope**
for moves. Within `APEta/` there are very few `.md` files and **no true
duplicates**:

| Path | Size | Modified | Summary | Superseded by? | Verdict |
|---|---|---|---|---|---|
| `README.md` | 11 KB | Jun 23 | Repo overview | — | canonical KEEP |
| `METHODOLOGICAL_VERIFICATION.md` | 14 KB | Jun 23 | Methodology audit | — | canonical KEEP (audit) |
| `LOCAL_VERIFICATION_GUIDE.md` | 8.9 KB | Jun 23 | Local repro guide | — | canonical KEEP |
| `FACTORIAL_DESIGN_SUMMARY.md` | 9.2 KB | Jun 23 | Factorial design summary (`*_SUMMARY`) | — | canonical KEEP |
| `orchestrator/VM_SETUP.md` | 5.6 KB | Jun 20 | VM setup notes | — | canonical KEEP |
| `design/SCENARIO_DESIGN.md` | 15 KB | Jul 2 | Scenario design | — | canonical KEEP (keep-list) |
| `design/CALIBRATION.md` | 6.1 KB | Jul 2 | Calibration method | — | canonical KEEP (keep-list) |
| `design/PARITY_REPORT_MOT.md` | 4.1 KB | Jul 2 | REST/GraphQL parity | — | canonical KEEP (keep-list) |
| `design/IMPL_MODE_JUSTIFICATION.md` | 2.4 KB | Jul 2 | Impl-mode justification | — | canonical KEEP (keep-list) |
| `design/STUDY_COMPARISON.md` | 18 KB | Jul 3 | Provenance ledger of all sessions | — | canonical KEEP (newest; drives this plan) |
| `results/analysis_session1_preliminary/ANALYSIS_SUMMARY.md` | 1.0 KB | Jun 23 | Study-A summary | — | see UNSURE (part of a referenced dir) |
| `results/visualize/README.md` | 4.2 KB | Jun 23 | Viz tooling readme | — | see UNSURE |
| `.pytest_cache/README.md` | 0.3 KB | — | Auto-generated | — | ignore (gitignored) |

**No markdown archived. No content touched.** Nothing to dedup within `APEta/`.

---

## 4. UNSURE — needs your decision (left in place)

| Path | Size | Why unsure |
|---|---|---|
| `results/archive_pre_factorial/` | **1.4 GB** | Holds the server logs for `results/results.csv` (run-sesi-2), which the thesis reproducibility/figure docs cite. Referenced in `STUDY_COMPARISON.md` and labeled "Aborted / censored." Biggest space win **if** you accept archiving it. |
| `results/phase2-pilot/` (v1) | 5.8 MB | Path-referenced in `laporan/phase2_migration/SOURCE_OF_TRUTH_PHASE2.md` and `laporan/reproducibility/WORKSPACE_INVENTORY.md` — thesis reads/lists it. Its v2–v5 siblings are safe candidates; v1 is cited. |
| `results/phase2-batch-pilot/` | 3.5 MB | Pilot; mentioned in `STUDY_COMPARISON.md` ledger only. Archive if ledger mention is non-blocking. |
| `results/analysis_session1_preliminary/` | 888 KB | "Study A" source cited in `design/STUDY_COMPARISON.md` and `design/IMPL_MODE_JUSTIFICATION.md` (methodology). Likely KEEP. |
| `results/visualize/` | 388 KB | 0 external references, but it is visualization tooling/output with its own README — not clearly redundant. |
| `results/logs/` | 2.0 MB | Old top-level logs; referenced once. Provenance unclear. |

---

## 5. Confirmed KEEP (for the record — never archived)

- **NO-TOUCH / LIVE:** `results/mot-scenarios-core/`, `results/.locks/server.pid`,
  tmux `mot-core`, netns/systemd scope, cron backup + `results-backup` branch, `.git/`.
- **10 "real" sessions + combined (720-run caching data):** `phase2-core-real`,
  `phase2-batch-real`, `phase2-concurrency-drillin`, `phase2-concurrency100-drillin`,
  `phase2-density-drillin`, `phase2-entropy-drillin`, `phase2-network-drillin`,
  `phase2-entropy-concurrency-interaction`, `phase2-network-concurrency-interaction`,
  `phase2-core-cpu-rerun` (**actively read by `tools/combine_all_sessions.py`**),
  plus `phase2-combined`.
- `results/factorial-A/`, `results/archive_run-sesi-1/`.
- `results/mot-scenarios-calibration/` + its console log — referenced by
  `tools/calibrate_mot.py` and design docs; tied to the live core calibration.
- `results/phase2-figures/` (thesis figures), `results/telemetry/`,
  `results/k6_summaries/` — referenced by thesis/tools.
- Cited loose files: `results/results.csv`, `run_plan.csv`, `inferensi_vcd.json`,
  `density_profile.json`; `scratch/synthetic.json` (referenced 7×),
  `scratch/id_pool_mot.json` (live), `scratch/concurrency_liveness.py`.
- All source: `core/`, `orchestrator/`, `k6/`, `tools/`, `tests/`, top-level
  `*.py`, `cache/`, top-level `telemetry/`, `venv/`, and all KEEP `*.md`.

---

## 6. Target layout (if approved)

Everything archived goes under, preserving relative path (reversible):

```
archive/2026-07-03/
├── ape_results_run-sesi-1_20260622_143624.tar.gz
├── results/
│   ├── phase2-pilot-v2/  phase2-pilot-v3/  phase2-pilot-v4/  phase2-pilot-v5/
│   ├── archive_pre_pilot/
│   └── archive_pilot_final/
└── scratch/
    ├── varnish-*/  (24)
    ├── id_pool.json
    └── k6_summaries/
```

(UNSURE items are NOT in this tree until you rule on them.)

---

## STOP — awaiting your decisions

1. **Blocker A:** plain `mv` (A1, recommended) / `git add`+`git mv` (A2) / hold (A3)?
2. **Blocker B:** does a `STUDY_COMPARISON.md` provenance-ledger mention count as a
   *blocking* reference? If **no**, `archive_pre_factorial/` (1.4 GB),
   `phase2-batch-pilot/`, `archive_pre_pilot/`, `archive_pilot_final/` become
   archivable. If **yes**, only the ~90 MB safe set moves.
3. Confirm the `.tar.gz` is **not** your intentional off-tree backup.
4. Approve the ARCHIVE-CANDIDATE set (§2) as-is, or edit it.

No file will be moved until you reply. I will re-verify the live run is running
immediately before and after each move batch, and skip any move that would race it.
