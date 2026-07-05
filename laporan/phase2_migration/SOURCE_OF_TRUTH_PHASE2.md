# Source of Truth - Eksperimen Utama Phase 2

Dokumen ini adalah rujukan internal agar laporan tidak kembali ke asumsi Phase 1.

## Workspace Utama

- Kode APE: `/home/ubuntu/APE/APEta`
- Dataset: `/home/ubuntu/datasets/VisDrone`
- Pipeline training/inference/corpus: `/home/ubuntu/training`
- Corpus SQLite utama: `/home/ubuntu/training/mot_detections.db`
- Draft laporan lama: `/home/ubuntu/APE/laporan_revised (2).docx`

## Data Penelitian Aktual

Eksperimen utama memakai data VisDrone-MOT yang sudah diproses menjadi corpus relasional SQLite, bukan VCD JSON in-memory.

Corpus `mot_detections.db` berisi:

| Tabel | Jumlah |
|---|---:|
| sequence | 7 |
| image | 2.846 |
| track | 5.429 |
| detection | 104.767 |

Distribusi `image.density_tier`:

| Tier | Jumlah image |
|---|---:|
| high | 712 |
| low | 579 |
| medium | 1.555 |

Jumlah track multi-frame yang masuk ke ID pool Phase 2: 3.848.

## Schema Data Aktual

Tabel utama:

- `class(id, name)`
- `sequence(id, name, n_frames)`
- `image(id, sequence_id, frame_index, width, height, density_tier, density_count_conf25)`
- `track(id, sequence_id, local_track_id, class_id, first_frame, last_frame)`
- `detection(id, image_id, track_id, class_id, confidence, bbox_x, bbox_y, bbox_w, bbox_h)`

Catatan: `detection.track_id` nullable karena sebagian detection dapat tidak punya track.

## Server Aktual

REST:

- File: `rest_server.py`
- Framework: FastAPI
- Endpoint utama:
  - `GET /images/random`
  - `GET /images/{image_id}`
  - `GET /images/{image_id}/detections`
  - `GET /tracks/{track_id}`
  - `GET /tracks/{track_id}/trajectory`
  - `GET /health`

GraphQL:

- File: `graphql_server.py`
- Framework: Strawberry GraphQL
- Schema utama: `Image`, `Detection`, `Track`, `TrajectoryPoint`
- Route:
  - `POST /graphql` untuk GraphQL biasa
  - `GET /graphql` untuk APQ-over-GET
  - `GET /health`

Shared core:

- `core/dal.py`: shared DetectionDAL over SQLite
- `core/caching.py`: shared Cache-Control/ETag logic
- `core/timing.py`: X-Process-Time middleware

## Cache Aktual

Phase 2 memasukkan cache sebagai variabel eksperimen.

- Cache layer: Varnish
- Config: `cache/varnish.vcl`
- REST memakai HTTP GET cacheable endpoints.
- GraphQL memakai APQ-over-GET agar dapat diuji dengan mekanisme HTTP caching.
- Response cacheable memakai `Cache-Control` dan `ETag`.
- Anti-cache endpoint seperti random image memakai `Cache-Control: no-store`.

## Workload Aktual

File: `k6/workload.js`

Faktor workload:

- `PROTOCOL`: `rest` atau `graphql`
- `BASE_URL`: direct server atau Varnish
- `ACCESS_PATTERN`: `unique`, `uniform`, `zipfian`
- `ENTROPY`: `low`, `medium`, `high`
- `PAYLOAD_WEIGHT`: `light`, `heavy`
- `DENSITY`: `low`, `medium`, `high` untuk payload light
- `VUS`, `DURATION`, `SUMMARY_FILE`

GraphQL workload memakai APQ client flow:

1. request hash-only;
2. jika `PersistedQueryNotFound`, kirim query text untuk registration;
3. request berikutnya dapat memakai hash yang sama.

## Desain Faktor Phase 2

Berdasarkan `orchestrator/config.py` dan `make_run_plan.py`:

- `protocol`: REST, GraphQL
- `caching`: on, off
- `access_pattern`: unique, uniform, zipfian
- `entropy`: low, medium, high
- `payload_weight`: light, heavy
- `network`: lan, constrained
- `density`: low, medium, high
- `concurrency`: VU levels

Core grid default memvariasikan:

- protocol x caching x access_pattern x payload_weight

dengan entropy, density, network, dan concurrency dapat dikunci pada nilai core.

## Metrik Phase 2

Kolom hasil di `results/phase2-pilot/results.csv`:

- `lat_p50`, `lat_p95`, `lat_p99`
- `throughput_rps`
- `payload_bytes_med`
- `cache_hit_rate`
- `round_trip_count`
- `error_rate`
- `apq_registrations`
- `cpu_mean`, `cpu_p95`
- `rss_mean_mb`, `rss_p95_mb`
- `k6_iterations`

## Hal yang Tidak Lagi Tepat untuk Eksperimen Utama

Jangan jadikan hal berikut sebagai desain utama Phase 2:

- VCD JSON sebagai corpus utama.
- In-memory pool sebagai data source utama.
- Klaim tanpa basis data untuk menghindari SQLite/PostgreSQL.
- Matrix utama S1-S4 baseline/partial/filtered/aggregate.
- Endpoint `/api/baseline/{image_id}`, `/api/partial/{image_id}`, `/api/aggregate/{image_id}` sebagai endpoint utama.
- VisDrone-DET val 548 citra sebagai corpus utama.
- Densitas berdasarkan split DET-val saja.
- 72 skenario sebagai angka utama, kecuali hanya disebut sebagai pilot lama.
