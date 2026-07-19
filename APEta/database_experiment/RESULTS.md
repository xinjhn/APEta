# Results — authoritative session `db-main-audited-20260719`

## Acceptance and environment

- 150 deterministic cases × 30 measured blocks × 3 backends = **13,500
  measurements**.
- Canonical result parity: **13,500/13,500 PASS**.
- Workload seed: `20260719`; interleaving seed: `731947`.
- SQLite 3.50.4, MongoDB 8.0.26, Neo4j Community 5.26.28.
- Windows 11 host, Python 3.13.14; MongoDB and Neo4j accessed over host
  loopback into Docker Desktop.
- Docker image IDs: MongoDB
  `sha256:3ce3de7f40e914034b03b7dec654005ab54f7dc8306937e44ec6760d9e9409a1`;
  Neo4j `sha256:362542416de6c09a971484d1893878016cc3b5cdec166e54b1c824a220ecd6b9`.

## Descriptive result across all parity-equivalent calls

| Backend | n | Median (ms) | Mean (ms) | p95 (ms) | p99 (ms) |
|---|---:|---:|---:|---:|---:|
| SQLite | 4,500 | **0.226** | **0.337** | **0.985** | **1.475** |
| MongoDB | 4,500 | 1.474 | 1.548 | 2.184 | 2.772 |
| Neo4j | 4,500 | 3.314 | 3.546 | 5.402 | 6.814 |

The pooled row is descriptive only because it combines different workloads.
The inferential analysis was performed separately for 15 workload cells.

## Paired cell result

Cases were first collapsed to a median for each `backend × block × cell`.
Each cell therefore has 30 paired block summaries, avoiding pseudo-replication
from the ten repeated entities inside a block.

- SQLite had the lower block median in **all 30/30 blocks in all 15 cells**
  versus both alternatives.
- MongoDB/SQLite paired median ratio ranged from **1.79× to 9.58×**; absolute
  paired median difference ranged from **+0.86 to +1.35 ms**.
- Neo4j/SQLite paired median ratio ranged from **4.74× to 19.19×**; absolute
  paired median difference ranged from **+2.59 to +4.29 ms**.
- All 30 backend-by-cell Wilcoxon comparisons remained significant after Holm
  correction. The largest corrected p-value was **1.73×10^-6**.

The smallest relative MongoDB gap occurred at `trajectories/k10`, where batching
reduced its fixed client/server cost; SQLite still retained the lower block
median (paired ratio 1.79×).

## Decision

For this corpus and deployment, the evidence supports SQLite as the most
appropriate backing store for the REST-vs-GraphQL experiment:

1. all engines produced identical logical results;
2. SQLite was practically fast (sub-millisecond overall median) and had the
   lowest median in every workload cell;
3. the experiment is local, read-only, single-node, and about 9 MiB;
4. the data are naturally relational and queries use shallow, bounded joins;
5. MongoDB requires a query-optimized duplicated representation of detections,
   while Neo4j's deep-traversal strengths are not exercised.

This result does **not** establish that SQLite is universally faster or more
suitable for production systems. The measurement includes native architecture:
SQLite is embedded, whereas MongoDB and Neo4j cross a loopback client/server
boundary. It also does not test high write concurrency, remote/multi-node
deployment, deep graph traversal, or a protocol-by-database interaction.

## Files to cite or inspect

- Raw data: `results/db-main-audited-20260719/measurements.csv`
- Frozen run metadata: `results/db-main-audited-20260719/metadata.json`
- Cell analysis: `results/db-main-audited-20260719/analysis/paired_summary.csv`
- Overall descriptive table: `results/db-main-audited-20260719/analysis/overall_summary.csv`
- Figure: `results/db-main-audited-20260719/analysis/latency_by_cell.png`
