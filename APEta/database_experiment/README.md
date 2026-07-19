# Database-sensitivity experiment: SQLite, PostgreSQL, MongoDB, and Neo4j

This experiment answers a narrower and more defensible question than “which
database is fastest?”:

> For the actual APE MOT corpus and read patterns, is SQLite an appropriate
> controlled backing store for the REST-vs-GraphQL experiment, and would a
> MongoDB or Neo4j model provide a material workload-fit advantage?

It is deliberately separate from the main API experiment. Changing protocol
and database in the same uncontrolled comparison would make their effects
indistinguishable. In the main experiment, REST and GraphQL use the same DAL,
queries, SQLite file, and ordering. SQLite is therefore a **controlled
variable**, not an explanation for a REST-vs-GraphQL difference.

## Evidence already fixed by the real corpus

| Property | Observed value |
|---|---:|
| SQLite file | 9,416,704 bytes (about 9.0 MiB) |
| Sequences | 7 |
| Images | 2,846 |
| Tracks | 5,429 |
| Detections | 104,767 |
| Mean / maximum detections per image | 36.81 / 300 |
| API-time writes | 0 (read-only corpus) |
| Deployment | one API process and a local database |
| Relationship depth in M1-M6 | point lookup or bounded one/two-hop traversal |

These conditions match SQLite's documented fit: device/local application data,
low write concurrency, and data colocated with the application server. SQLite's
own selection guide says a client/server engine is preferable for many concurrent
writers, network-separated data, and multi-server/write-intensive deployments;
none is present here. See [SQLite: Appropriate Uses](https://www.sqlite.org/whentouse.html)
and [SQLite Is Serverless](https://www.sqlite.org/serverless.html).

## Models compared (native, not deliberately handicapped)

- **SQLite:** normalized `sequence`, `image`, `track`, `detection`, and `class`
  tables with the indexes already used in APE.
- **PostgreSQL:** the same normalized tables, keys, indexes, rows, and native SQL
  query shapes behind a persistent loopback client/server connection. PostgreSQL
  diagnostics use `pg_stat_statements` and `track_io_timing=on`.
- **MongoDB:** one image document embeds its detections; one track document
  embeds its trajectory. This follows MongoDB's query-driven embedding guidance
  and permits one-document reads. It duplicates trajectory data, a deliberate
  document-model trade-off. The corpus remains far below MongoDB's 16 MiB
  per-document limit. See [MongoDB embedded data](https://www.mongodb.com/docs/manual/data-modeling/embedding/).
- **Neo4j:** `Sequence`, `Image`, `Track`, `Detection`, and `Class` nodes linked
  by explicit relationships. This is a real property-graph model with indexed
  entry nodes. See [Neo4j relational-to-graph modeling](https://neo4j.com/docs/getting-started/data-modeling/relational-to-graph-modeling/).

The five measured logical operations map to existing APE scenarios:

| Operation | APE analogue | Logical result |
|---|---|---|
| `image_detections` | M1/M2 | image and all detections |
| `filtered_detections` | M3 | image and server-side filtered detections |
| `class_counts` | M4 | grouped counts by class |
| `trajectory` | M5 | track and bounded trajectory, W in {2,8,23} |
| `trajectories` | M6 | batch of K tracks, K in {1,5,10} |

Every result is normalized and SHA-256 hashed. A mismatch against SQLite stops
the run before it can be interpreted as a performance result.

## Design

- Factor: database backend (`sqlite`, `postgresql`, `mongodb`, `neo4j`).
- Blocking factors: exact logical case and measured block.
- Workload strata: image density, trajectory window, and batch size.
- Default: 10 deterministic cases per cell, one warm-up round, 30 measured
  randomized blocks.
- Execution: for every logical case, backend order is shuffled. Thus machine
  drift does not always favor the same engine.
- Primary outcome: client-observed database latency in milliseconds.
- Validity gate: 100% canonical-result parity.
- Analysis: cases are collapsed to one median per randomized block and workload
  cell; 30 block summaries are then compared with paired Wilcoxon signed-rank,
  Holm correction, paired median delta/ratio, and backend-faster fraction. This
  avoids treating repeated calls to the same cases as independent observations.

Latency includes each engine's native architecture. SQLite executes embedded in
the Python process; MongoDB and Neo4j cross a loopback client/server boundary.
That is relevant to the deployment decision but means this is **not** a pure
storage-engine microbenchmark. Cold-cache claims are excluded because clearing
OS, Docker VM, JVM, and engine caches equivalently is not credible here.

## Reproduce

Run commands from `APEta`:

```powershell
..\.venv\Scripts\python.exe -m pip install -r database_experiment\requirements.txt
docker compose -f database_experiment\compose.yaml up -d --wait
..\.venv\Scripts\python.exe -m database_experiment.load_backends --backend all
..\.venv\Scripts\python.exe -m database_experiment.prepare_workload
..\.venv\Scripts\python.exe -m database_experiment.run_benchmark
..\.venv\Scripts\python.exe -m database_experiment.analyze database_experiment\results\<session>\measurements.csv
```

For the focused relational comparison and PostgreSQL I/O diagnostic:

```powershell
..\.venv\Scripts\python.exe -m database_experiment.run_benchmark --backends sqlite,postgresql --session-id relational-main
..\.venv\Scripts\python.exe -m database_experiment.postgres_io_report --out-dir database_experiment\results\relational-main\postgres_io
```

Quick code/parity smoke test before the main run:

```powershell
..\.venv\Scripts\python.exe -m database_experiment.prepare_workload --samples-per-cell 2 --out database_experiment\workload.smoke.json
..\.venv\Scripts\python.exe -m database_experiment.run_benchmark --workload database_experiment\workload.smoke.json --blocks 2 --session-id smoke
```

Do not overwrite a result directory. The runner refuses to reuse a session ID.
After the experiment, capture immutable container digests with:

```powershell
docker inspect ape-db-mongodb ape-db-neo4j --format '{{.Name}} {{.Image}}'
```

## Decision rule

Call SQLite “the most appropriate choice for this experiment” only when all of
the following hold:

1. all backends pass result parity;
2. SQLite has no practically unacceptable latency on any APE workload cell;
3. MongoDB does not provide a material benefit that justifies duplicated data
   and a server dependency;
4. Neo4j does not provide a material benefit on the actual bounded traversal
   workload; and
5. the scope remains local, read-mostly/read-only, single-node, and small.

If future requirements add multi-server deployment, high concurrent write load,
unbounded/deep relationship traversal, path finding, or graph analytics, this
decision must be revisited. The correct conclusion is scoped; it is not
“SQLite is universally better than MongoDB or Neo4j.”

## Relation to the REST-vs-GraphQL conclusion

This direct database study justifies the **database choice**. It does not by
itself estimate a protocol-by-database interaction. If an examiner requires
evidence that the REST-vs-GraphQL ranking generalizes across engines, run a
separate crossed `2 protocols x 3 databases` sensitivity experiment using the
same API contracts and parity gates. That is an external-validity extension,
not a prerequisite for the internal validity of the current shared-SQLite study.
