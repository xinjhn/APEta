# Relational sensitivity: SQLite vs PostgreSQL

## What the earlier result does and does not mean

The SQLite-MongoDB-Neo4j result does **not** prove that a relational data model
reduces database I/O. It showed that SQLite had lower client-observed
database-call latency in the measured local deployment. That measurement mixed:

- data model and query engine;
- embedded versus client/server architecture;
- driver encoding/decoding and loopback transport;
- process scheduling; and
- database execution and cache access.

The correct term for that outcome is **database access-path overhead**, not
physical database I/O overhead.

## Audit of Lawi et al. (2021)

The paper reports one database engine hosting two identical isolated schemas.
REST and GraphQL requests are distributed to separate API paths, and response
time is calculated from request/response timestamps at each API gateway. CPU
and memory are recorded for API-service activity.

| Method item | Reported by Lawi et al.? |
|---|---|
| End-to-end gateway response time | Yes |
| Throughput | Yes |
| API-service CPU and memory | Yes |
| Database execution time | No separate measurement reported |
| Logical/physical block reads and cache hits | No |
| Database I/O wait time | No |
| Query plans or rows examined | No |
| Database-server CPU/RSS | No |
| Cold/warm cache protocol | No |
| DBMS product and version in the paper text/architecture figure | Not identified |

Therefore, database work is **inside** their end-to-end response time, but it is
not isolated or attributed. Their shared engine is a control for the REST versus
GraphQL comparison, not a database-I/O experiment. If PostgreSQL was identified
from source code or another artifact, cite that artifact separately; the local
paper PDF itself does not state “PostgreSQL.” See Lawi et al., pp. 3-4, 7, and 9
in `papers/Lawi et al. - 2021 - Evaluating GraphQL and REST API Services
Performance in a Massive and Intensive Accessible Informati.pdf`.

## Our relational comparison

The new experiment holds the relational schema, indexes, source rows, query
semantics, workload cases, and result ordering constant. It changes only:

- SQLite 3.50.4, embedded in the benchmark process; and
- PostgreSQL 18.4, persistent connection over host loopback to Docker.

Design: 150 deterministic cases, 30 interleaved randomized blocks, 4,500 calls
per backend, and canonical result hashing before performance interpretation.

### Client-observed database-call latency

| Backend | n | Median (ms) | Mean (ms) | p95 (ms) | p99 (ms) |
|---|---:|---:|---:|---:|---:|
| SQLite | 4,500 | **0.181** | **0.288** | **0.921** | **1.360** |
| PostgreSQL | 4,500 | 1.368 | 1.661 | 3.672 | 4.534 |

- Result parity: **9,000/9,000 PASS**.
- SQLite had the lower block median in all 30 blocks across all 15 cells.
- PostgreSQL/SQLite paired median ratio: **3.65x to 12.50x** by cell.
- Paired absolute difference: **+0.55 to +2.78 ms**.
- All 15 paired Wilcoxon tests remained significant after Holm correction;
  largest corrected p-value: **1.73 x 10^-6**.

### PostgreSQL server-side I/O diagnostic

After one warm-up pass, `pg_stat_statements` was reset and the 150 cases were
executed for another 30 rounds. `track_io_timing=on`.

- All eight measured statement shapes reported **100% PostgreSQL shared-buffer
  hits**.
- `shared_blks_read = 0` for every statement shape.
- `shared_blk_read_time = 0 ms`; no temporary reads/writes or dirty/written
  blocks were recorded.
- Mean server execution time ranged from about **0.029 ms** for envelope lookup
  to **1.070 ms** for batched trajectory points.
- The batched trajectory-point statement also incurred about **0.348 ms mean
  planning time** per call in the steady-state diagnostic; the other statements
  reused plans prepared during warm-up.

This is the important interpretation: **PostgreSQL was slower even though the
measured warm phase performed no PostgreSQL file reads.** The observed difference
therefore cannot be described as physical disk-I/O overhead. It primarily
reflects the client/server boundary plus driver conversion, process scheduling,
planning where applicable, and engine execution/cache-access costs.

PostgreSQL documents `pg_stat_statements` as reporting planning/execution time,
rows, shared-block hits/reads, and I/O timing. It also warns that a PostgreSQL
block read can still be satisfied by the operating-system page cache, so even
`shared_blks_read` is not automatically a physical disk read:

- https://www.postgresql.org/docs/current/pgstatstatements.html
- https://www.postgresql.org/docs/current/runtime-config-statistics.html
- https://www.postgresql.org/docs/18/monitoring-stats.html

## Defensible conclusion

For the present small, read-only, same-host experiment, SQLite remains the more
appropriate control database. PostgreSQL does not improve the tested query
semantics or latency, while it adds a server/driver boundary. PostgreSQL would
become the stronger architectural candidate if the requirements changed to
multiple application servers, remote database access, centralized operations,
or substantial concurrent writes.

This remains a database-selection sensitivity study. It does not estimate a
REST/GraphQL-by-database interaction. That question requires a crossed 2x2
experiment: `REST/GraphQL x SQLite/PostgreSQL` with the same response contracts.

## Authoritative artifacts

- `results/relational-main-20260719/measurements.csv`
- `results/relational-main-20260719/metadata.json`
- `results/relational-main-20260719/analysis/paired_summary.csv`
- `results/relational-main-20260719/analysis/latency_by_cell.png`
- `results/relational-main-20260719/postgres_io_final/postgres_statement_io.csv`
- `results/relational-main-20260719/postgres_io_final/postgres_io_metadata.json`
