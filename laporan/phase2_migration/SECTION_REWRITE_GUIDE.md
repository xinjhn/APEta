# Section Rewrite Guide - Dari Draft Phase 1 ke Phase 2

Panduan ini menjelaskan bagaimana setiap bagian utama di draft perlu diarahkan ulang.

## Judul

Judul lama:

> ANALISIS PERFORMA KOMUNIKASI DATA REST API DAN GRAPHQL DALAM PENYAJIAN DATA DETEKSI OBJEK MENGGUNAKAN YOLO26

Rekomendasi judul baru:

> ANALISIS KINERJA REST DAN GRAPHQL PADA PENYAJIAN DATA DETEKSI OBJEK DENGAN VARIASI CACHING DAN POLA AKSES

Alternatif lebih teknis:

> ANALISIS KINERJA REST DAN GRAPHQL PADA KORPUS DETEKSI OBJEK BERBASIS YOLO DENGAN VARIASI CACHING

Catatan: judul baru menghindari klaim bahwa penelitian berfokus pada YOLO26 sebagai kontribusi utama. YOLO tetap menjadi sumber data/corpus, tetapi objek penelitian adalah delivery API.

## Bab I - Latar Belakang

Arah baru:

- Mulai dari kebutuhan menyajikan data hasil computer vision melalui API.
- Jelaskan REST dan GraphQL memiliki karakteristik berbeda.
- Jelaskan perbandingan performa harus mengontrol caching, query shape, access pattern, payload, dan shared data source.
- Jelaskan pilot experiment dilakukan sebelum eksperimen utama untuk memvalidasi instrument.

Kurangi:

- penekanan VCD sebagai skema utama;
- klaim GraphQL pasti lebih efisien karena partial field;
- pembahasan terlalu panjang tentang YOLO26 NMS-free jika tidak langsung memengaruhi API experiment.

## Bab I - Rumusan Masalah

Rumusan masalah Phase 2 harus mencakup:

1. Bagaimana membandingkan REST dan GraphQL secara fair ketika keduanya menyajikan data deteksi objek yang sama?
2. Bagaimana caching dan pola akses memengaruhi latency, throughput, payload, dan resource usage?
3. Bagaimana query shape/entropy dan payload weight memengaruhi cache-hit rate serta performa REST/GraphQL?

## Bab I - RQ dan Hipotesis

Gunakan RQ/H pada `PASTE_READY_REPLACEMENTS.md`.

## Bab I - Dukungan Data

Ganti dengan data aktual:

- VisDrone-MOT sebagai sumber sequence;
- YOLO/Ultralytics tracking menghasilkan prediction files;
- `build_detection_db.py` membangun SQLite corpus;
- corpus berisi 7 sequence, 2.846 image, 5.429 track, 104.767 detection.

## Bab II - Dasar Teori

Pertahankan:

- Web service, HTTP, REST, GraphQL.
- Over-fetching/under-fetching, tetapi jangan jadikan satu-satunya pusat penelitian.
- Deteksi objek dan YOLO sebagai konteks data.
- Parameter evaluasi performa.

Tambahkan/perkuat:

- HTTP caching: Cache-Control, ETag, validation, freshness.
- GraphQL APQ-over-GET.
- Access pattern: unique, uniform, zipfian.
- Query shape entropy.
- Reverse proxy cache/Varnish.
- SQLite/relational corpus sebagai shared data source.
- BPMN/UML/SSD jika digunakan sebagai dasar gambar.

## Bab III - Penjelasan Penelitian

Jangan menulis bahwa Phase 2 adalah perubahan arah mendadak. Tulis:

- penelitian dua tahap;
- pilot untuk validasi instrument;
- eksperimen utama untuk menjawab RQ.

## Bab III - Variabel Penelitian

Ganti matrix lama:

- protocol x pattern x density x concurrency

menjadi:

- protocol,
- caching,
- access_pattern,
- entropy,
- payload_weight,
- network,
- density,
- concurrency.

Metrik:

- latency p50/p95/p99,
- throughput,
- payload_bytes_med,
- cache_hit_rate,
- error_rate,
- APQ registrations,
- CPU,
- RSS.

## Bab III - Data Penelitian

Ganti narasi VCD/in-memory dengan pipeline:

VisDrone-MOT -> YOLO tracking -> MOT prediction txt -> SQLite corpus -> ID pool k6 -> REST/GraphQL experiment.

## Bab III - Tahapan Pelaksanaan

Urutan yang disarankan:

1. Studi literatur.
2. Persiapan corpus deteksi MOT.
3. Pengembangan APE.
4. Uji pendahuluan/pilot.
5. Kalibrasi run plan dan workload.
6. Eksperimen utama Phase 2.
7. Analisis statistik.
8. Interpretasi dan laporan.

## Bab IV - APE

Ganti struktur Bab IV lama:

- Karakteristik Output YOLO26 beserta Skema VCD
- Profil Distribusi Dataset VisDrone
- InMemoryPool
- baseline/partial/filter/aggregate

menjadi:

- Karakteristik corpus deteksi MOT.
- ERD SQLite.
- REST server.
- GraphQL server dengan APQ-over-GET.
- Shared DetectionDAL.
- Shared cache logic.
- Varnish cache layer.
- k6 workload generator.
- orchestrator dan telemetry.
- validasi parity/fairness.

## Bab V - Hasil dan Pembahasan

Bab V perlu ditambahkan atau dikembangkan.

Struktur yang disarankan:

- V.1 Hasil Uji Pendahuluan.
- V.2 Hasil Eksperimen Utama Phase 2.
- V.3 Analisis Statistik Per Cell.
- V.4 Pembahasan RQ.
- V.5 Threats to Validity.

## Gambar yang Perlu Diganti

Gunakan figure sources di `/home/ubuntu/APE/laporan/figures/src`:

- `fig_01_research_workflow_bpmn_style.mmd`
- `fig_02_pilot_to_main_experiment.mmd`
- `fig_03_system_architecture_component.mmd`
- `fig_04_data_preparation_pipeline.mmd`
- `fig_05_sqlite_erd.mmd`
- `fig_06_experiment_orchestration_activity.mmd`
- `fig_07_rest_ssd.mmd`
- `fig_08_graphql_post_ssd.mmd`
- `fig_09_graphql_apq_cache_flow_ssd.mmd`
- `fig_10_cache_hit_miss_sequence.mmd`
- `fig_11_phase2_factor_grid.mmd`
- `fig_12_analysis_pipeline.mmd`
- `fig_13_network_namespace_topology.mmd`
- `fig_14_measurement_streams.mmd`
- `fig_15_graphql_selection_set_payload.mmd`
- `fig_16_variables_metrics_map.mmd`
