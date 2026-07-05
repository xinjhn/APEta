# Peta Laporan Berdasarkan Template TA

Peta ini mengikuti struktur template `2026 Template Laporan TA JTK-[R]-STr TI
(RevMei2026)`. Tujuannya adalah menjaga laporan tetap sesuai template, sambil
memastikan narasi penelitian APE runtut untuk pembaca non-spesialis.

## Judul Sementara

Judul Indonesia:

> Analisis Perbandingan Kinerja REST dan GraphQL pada Penyajian Data Deteksi
> Objek Berbasis YOLO dengan Variasi Caching dan Pola Akses

Judul Inggris:

> Performance Analysis of REST and GraphQL for YOLO-Based Object Detection Data
> Delivery under Caching and Access Pattern Variations

Catatan: judul dapat dipadatkan agar sesuai batas 12-15 kata pada template.

## Front Matter

- Abstrak: latar belakang REST vs GraphQL, masalah fairness benchmark, metode
  dua fase, dataset VisDrone/YOLO, APE sebagai instrument eksperimen, hasil
  utama setelah analisis.
- Abstract: versi bahasa Inggris dari abstrak.
- Daftar Istilah dan Singkatan: REST, GraphQL, API, APQ, ETag, TTL, VU, k6,
  Varnish, YOLO, MOT, SSD, BPMN, ERD.

## BAB I Pendahuluan

### I.1 Latar Belakang

Isi yang disarankan:

- Pertumbuhan kebutuhan API untuk menyajikan data hasil computer vision.
- REST dan GraphQL sama-sama populer, tetapi klaim performanya sering tidak
  mudah dibandingkan karena perbedaan payload, resolver, caching, dan query
  shape.
- Data deteksi objek dari YOLO/VisDrone memiliki karakteristik density,
  bounding box, class, confidence, dan track yang cocok untuk menguji payload
  light/heavy.
- Uji pendahuluan dilakukan sebagai kalibrasi instrument dan benchmark awal dan menghasilkan temuan tak
  terduga: hasil tidak cukup dapat diklaim sebagai efek protokol murni.
- Phase 2 dirancang sebagai perbaikan metodologi.

Gambar pendukung:

- `Gambar I.1` Alur besar penelitian APE.
- `Gambar I.2` Alur uji pendahuluan menuju eksperimen utama.

### I.2 Rumusan Masalah

Masalah utama:

- Perbandingan REST dan GraphQL sering bias jika implementasi, cache, akses
  data, dan bentuk payload tidak dikontrol.
- Dibutuhkan instrument eksperimen yang membuat dua protokol memakai sumber
  data dan data-access path yang sama.

### I.3 Research Question dan Hipotesis

RQ awal yang dapat disesuaikan:

- RQ1: Bagaimana perbedaan kinerja REST dan GraphQL pada penyajian data
  deteksi objek ketika menggunakan akses data yang sama?
- RQ2: Bagaimana pengaruh caching, pola akses, bobot payload, dan entropi query
  terhadap perbedaan kinerja REST dan GraphQL?
- RQ3: Dalam kondisi apa GraphQL berpotensi mendekati atau melampaui REST, dan
  dalam kondisi apa REST tetap lebih unggul?

Hipotesis awal untuk Phase 2:

- H1: Pada cache off dan payload ringan, REST memiliki latency lebih rendah
  karena request dapat dipetakan langsung ke endpoint.
- H2: Pada cache on dan akses berulang, perbedaan latency kedua protokol
  berkurang karena respons cache mengurangi kerja origin server.
- H3: Entropi query yang lebih tinggi menurunkan cache-hit rate, terutama pada
  GraphQL APQ karena variasi selection set menghasilkan cache key yang berbeda.

### I.4 Tujuan dan Manfaat Penelitian

Tujuan:

- Menentukan kondisi eksperimen yang membuat REST atau GraphQL lebih efisien
  untuk penyajian data deteksi objek.
- Menyusun instrument eksperimen yang replikabel untuk membandingkan API
  berdasarkan latency, throughput, payload, cache-hit rate, dan resource usage.

Manfaat:

- Bagi pengembang API: pedoman pemilihan pendekatan API.
- Bagi peneliti: contoh desain benchmark yang lebih fair.
- Bagi organisasi: dasar keputusan arsitektur untuk sistem computer vision.

### I.5 Pemangku Kepentingan Produk Akhir

- Peneliti atau mahasiswa yang melakukan benchmark API.
- Pengembang backend/API.
- Pengembang sistem computer vision yang perlu menyajikan hasil inference.
- Dosen/penguji sebagai evaluator metodologi.

### I.6 Dukungan Data

- Dataset: VisDrone DET/MOT.
- Model: YOLO fine-tuned pada VisDrone.
- Korpus eksperimen: SQLite `mot_detections.db`.
- Ringkasan saat ini: 7 sequences, 2.846 images, 5.429 tracks, 104.767
  detections.

### I.7 Ruang Lingkup dan Batasan

- Lingkup: API read-only untuk data deteksi/tracking, REST vs GraphQL, caching,
  workload k6, telemetry server.
- Batasan: bukan evaluasi akurasi model YOLO, bukan produksi API multi-user
  dengan autentikasi, bukan klaim umum untuk seluruh implementasi REST/GraphQL.

### I.8 Sistematika Penulisan

Ikuti template, dengan Bab IV difokuskan pada APE sebagai aplikasi pendukung
eksperimen.

## BAB II Tinjauan Pustaka

Subbab yang disarankan:

- REST dan HTTP Semantics.
- GraphQL dan model eksekusi query.
- HTTP caching, ETag, Cache-Control, dan reverse proxy cache.
- Automatic Persisted Queries.
- Load testing dan metrik performa API.
- YOLO, VisDrone, dan multi-object tracking.
- UML/SSD, BPMN, dan ERD sebagai dasar pemodelan laporan.
- Karya ilmiah sejenis tentang REST vs GraphQL dan benchmark API.

Gambar pendukung:

- `Gambar II.1` Konsep cache freshness dan validation.
- `Gambar II.2` Konsep GraphQL selection set terhadap bentuk payload.

## BAB III Metodologi Penelitian

### III.1 Penjelasan Penelitian

Jelaskan penelitian sebagai eksperimen empiris berbasis instrument APE:

- Uji pendahuluan: benchmark awal REST vs GraphQL pada output YOLO/VCD flat.
- Evaluasi uji pendahuluan: temuan tak terduga dan confounder metodologis.
- Phase 2: desain revisi dengan database relasional, shared DAL, cache layer,
  APQ-over-GET, access pattern, entropy, payload weight, dan network profile.

### III.2 Variabel Penelitian

Phase 1:

- Variabel bebas: protocol, pattern, density, concurrency.
- Variabel terikat: latency, throughput, payload bytes, X-Process-Time, CPU,
  RSS.

Phase 2:

- Variabel bebas: protocol, caching, access pattern, entropy, payload weight,
  network, density, concurrency.
- Variabel terikat: latency p50/p95/p99, throughput, payload bytes, cache-hit
  rate, error rate, APQ registrations, CPU, RSS.

Gambar pendukung:

- `Gambar III.1` Desain faktor eksperimen Phase 2.
- `Gambar III.2` Pemetaan variabel bebas dan variabel terikat.

### III.3 Data Penelitian

- Sumber dataset, proses inference, tracking, dan transformasi ke SQLite.
- Jelaskan ambang confidence untuk penyimpanan dan density tier.

Gambar pendukung:

- `Gambar III.3` Pipeline persiapan data VisDrone-YOLO-SQLite.
- `Gambar III.4` ERD korpus deteksi.

### III.4 Objek Penelitian

- Objek: kinerja dua paradigma API dalam penyajian data deteksi objek.
- Unit analisis: satu run k6 pada satu cell eksperimen.

### III.5 Perangkat Pendukung

- Python/FastAPI, Strawberry GraphQL, SQLite, Varnish, k6, psutil telemetry,
  netem/network namespace, YOLO/Ultralytics.

### III.6 Tahapan Pelaksanaan Penelitian

Gunakan BPMN/activity:

- Studi literatur.
- Phase 1 implementation and run.
- Evaluasi hasil uji pendahuluan.
- Redesign Phase 2.
- Bangun corpus relasional.
- Bangun APE server, cache, workload, orchestrator.
- Eksekusi eksperimen.
- Analisis statistik.
- Pembahasan dan laporan.

## BAB IV Hasil Pengembangan Aplikasi Pendukung Eksperimen

### IV.1 Analisis Problem Domain / Kebutuhan Eksperimen

Kebutuhan:

- Shared data access untuk REST dan GraphQL.
- Cache control identik.
- Workload generator yang mengontrol access pattern dan query shape.
- Orchestrator yang membuat run plan, menjalankan server, k6, telemetry, dan
  menulis results.csv.
- Reproducibility dan resume.

### IV.2 Pengembangan Aplikasi

Subbab yang disarankan:

- Arsitektur umum APE.
- REST server.
- GraphQL server dan APQ-over-GET.
- Shared DAL dan SQLite corpus.
- Cache layer Varnish.
- k6 workload generator.
- Orchestrator dan telemetry.
- Validasi parity/fairness.

Gambar pendukung:

- `Gambar IV.1` Arsitektur komponen APE.
- `Gambar IV.2` SSD request REST.
- `Gambar IV.3` SSD request GraphQL POST.
- `Gambar IV.4` SSD GraphQL APQ over GET.
- `Gambar IV.5` Sequence cache hit/miss.
- `Gambar IV.6` Orkestrasi eksperimen.
- `Gambar IV.7` Topologi network namespace dan cache.

## BAB V Hasil dan Pembahasan Eksperimen

### V.1 Hasil Eksperimen

- Sajikan Phase 1 sebagai preliminary/pilot.
- Sajikan Phase 2 sebagai hasil utama jika run sudah lengkap.
- Gunakan tabel ringkasan per cell dan visualisasi latency/throughput/cache.

### V.2 Pembahasan Hasil Eksperimen

- Jelaskan apakah hasil menjawab RQ.
- Bedakan latency end-to-end, processing time server, payload bytes, dan cache
  hit rate.
- Bahas mengapa uji pendahuluan dipisahkan dari hasil utama.

Gambar pendukung:

- `Gambar V.1` Pipeline analisis hasil.
- `Gambar V.2` Crossover surface latency vs cache-hit rate dan payload.
- `Gambar V.3` Entropy vs cache-hit rate.

## BAB VI Analisis Dampak Hasil Penelitian

Fokus:

- Dampak bagi pengembang API computer vision.
- Dampak bagi desain benchmark API.
- Potensi adopsi APE sebagai toolkit pembelajaran/riset.

## BAB VII Penutup

Isi:

- Kesimpulan berdasarkan RQ.
- Saran: perluasan dataset, remote network, autentikasi, deployment multi-node,
  GraphQL batching sub-study, workload produksi.
- Keberlanjutan: paket APE, dokumentasi replikasi, dashboard hasil, dataset
  release jika lisensi mengizinkan.

