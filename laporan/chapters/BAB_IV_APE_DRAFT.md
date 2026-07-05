# BAB IV HASIL PENGEMBANGAN APLIKASI PENDUKUNG EKSPERIMEN

Bab ini membahas APE sebagai aplikasi pendukung eksperimen. APE dikembangkan
untuk membuat pengujian REST dan GraphQL lebih terkontrol, replikabel, dan
terukur.

## IV.1 Analisis Problem Domain / Kebutuhan Eksperimen

Benchmark REST vs GraphQL membutuhkan kontrol yang ketat. Jika REST dan GraphQL
mengambil data dari jalur berbeda, memakai cache behavior berbeda, atau
menghasilkan payload yang tidak setara, hasil eksperimen dapat dipengaruhi
oleh faktor selain paradigma API. Oleh karena itu, APE harus memenuhi kebutuhan:

- REST dan GraphQL memakai data source yang sama.
- REST dan GraphQL memakai data-access layer yang sama.
- Cache header dihitung dengan fungsi yang sama.
- Workload dapat mengontrol entity id, query shape, payload weight, dan
  protocol.
- Orchestrator dapat menjalankan eksperimen secara terulang dan melanjutkan
  run yang terputus.
- Telemetry CPU/RSS dikumpulkan terpisah dari server.

## IV.2 Pengembangan Aplikasi

### IV.2.1 Arsitektur Umum APE

APE terdiri dari beberapa komponen utama: orchestrator, k6 workload generator,
server REST, server GraphQL, shared core, SQLite corpus, Varnish cache, dan
telemetry sampler. Orchestrator membaca `run_plan.csv`, menjalankan server yang
sesuai, mengatur cache dan network profile, menjalankan k6, lalu menulis
hasil ke `results.csv`.

[Gambar IV.1 Arsitektur komponen APE]

### IV.2.2 REST Server

REST server dibuat dengan FastAPI. Endpoint utama mencakup:

- `GET /images/random`
- `GET /images/{image_id}`
- `GET /images/{image_id}/detections`
- `GET /tracks/{track_id}`
- `GET /tracks/{track_id}/trajectory`
- `GET /health`

Endpoint REST memanggil `DetectionDAL` untuk membaca data. Response dikodekan
sebagai JSON compact dan diberi header cache melalui `core/caching.py` jika
resource bersifat cacheable.

[Gambar IV.2 SSD request REST]

### IV.2.3 GraphQL Server

GraphQL server dibuat dengan Strawberry. Schema utama berisi `Image`,
`Detection`, `Track`, dan `TrajectoryPoint`. Resolver GraphQL juga menggunakan
`DetectionDAL`, sehingga jalur akses data REST dan GraphQL tetap sama.

GraphQL menyediakan dua jalur:

- POST `/graphql` untuk query GraphQL biasa.
- GET `/graphql` untuk APQ-over-GET agar GraphQL dapat diuji dengan cache HTTP.

[Gambar IV.3 SSD request GraphQL POST]
[Gambar IV.4 SSD GraphQL APQ over GET]

### IV.2.4 Shared DAL dan SQLite Corpus

`core/dal.py` menyediakan akses read-only ke SQLite. DAL menggunakan connection
per thread agar aman untuk request concurrent. Tabel utama adalah `sequence`,
`image`, `track`, `detection`, dan `class`.

[Gambar III.4 ERD korpus deteksi MOT]

### IV.2.5 Cache Layer

Cache layer menggunakan Varnish. REST dan GraphQL APQ-over-GET sama-sama dapat
melewati Varnish saat `caching=on`. Cacheable response diberi `Cache-Control`
dan `ETag`, sedangkan endpoint anti-cache seperti random image diberi
`no-store`.

[Gambar IV.5 Sequence cache hit dan cache miss]

### IV.2.6 Workload Generator

Workload k6 pada `k6/workload.js` mengontrol:

- protocol REST atau GraphQL.
- access pattern unique, uniform, atau zipfian.
- entropy low, medium, atau high.
- payload weight light atau heavy.
- density untuk payload light.

Untuk GraphQL, workload menggunakan APQ flow: request hash-only terlebih dahulu,
kemudian melakukan registration jika server belum mengenal hash query.

### IV.2.7 Orchestrator dan Telemetry

`orchestrator/run_experiment.py` menjalankan seluruh blok eksperimen. Per blok,
orchestrator dapat mengganti server REST/GraphQL, mengatur cache on/off,
mengatur network profile, menjalankan telemetry sampler, menjalankan k6 warmup,
menjalankan measured run, lalu menulis hasil ke CSV.

[Gambar IV.6 Orkestrasi eksperimen APE]
[Gambar IV.7 Topologi network namespace dan cache]
[Gambar IV.8 Aliran metrik eksperimen]

### IV.2.8 Validasi dan Fairness

Validasi dilakukan melalui test parity, cache fairness, health check, dan
preflight. Prinsip fairness utama adalah shared data source, shared data-access
layer, cache behavior yang eksplisit, dan dokumentasi faktor eksperimen.

[Tabel IV.4 Acceptance checks dan status validasi]

