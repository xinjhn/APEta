# BAB III METODOLOGI PENELITIAN

Bab ini menjelaskan desain penelitian, variabel eksperimen, data penelitian,
objek penelitian, perangkat pendukung, dan tahapan pelaksanaan. Penelitian
dirancang sebagai eksperimen empiris dua fase. Phase 1 berperan sebagai studi
pendahuluan, sedangkan Phase 2 menjadi desain utama yang diperbaiki berdasarkan
audit Phase 1.

## III.1 Penjelasan Penelitian

Penelitian ini menggunakan pendekatan eksperimental. Objek yang dibandingkan
adalah performa REST dan GraphQL dalam menyajikan data deteksi objek. Agar
perbandingan tidak hanya bergantung pada satu skenario, penelitian memvariasikan
beberapa faktor workload dan sistem.

Phase 1 dilakukan dengan matrix awal yang terdiri dari `protocol`, `pattern`,
`density`, dan `concurrency`. Pattern pada Phase 1 meliputi baseline, partial,
filtered, dan aggregate. Hasil Phase 1 menunjukkan REST unggul pada seluruh
cell yang dianalisis, tetapi hasil ini memunculkan kebutuhan audit karena
selisih performa dapat dipengaruhi oleh confounder implementasi dan caching.

Phase 2 dirancang untuk memperbaiki hal tersebut. Pada Phase 2, REST dan GraphQL
menggunakan `DetectionDAL` yang sama, database SQLite yang sama, dan cache
logic yang sama. GraphQL diberi jalur APQ-over-GET agar dapat diuji dengan
cache HTTP, sedangkan Varnish digunakan sebagai shared reverse proxy cache.

[Gambar I.2 Alur uji pendahuluan menuju eksperimen utama]

## III.2 Variabel Penelitian

Variabel Phase 1:

- `protocol`: REST dan GraphQL.
- `pattern`: baseline, partial, filtered, aggregate.
- `density`: low, medium, high.
- `concurrency`: jumlah virtual users.

Variabel Phase 2:

- `protocol`: REST dan GraphQL.
- `caching`: on dan off.
- `access_pattern`: unique, uniform, zipfian.
- `entropy`: low, medium, high.
- `payload_weight`: light dan heavy.
- `network`: lan dan constrained.
- `density`: low, medium, high.
- `concurrency`: jumlah virtual users.

Metrik yang diukur:

- latency p50, p95, p99.
- throughput requests per second.
- median payload bytes.
- cache-hit rate.
- error rate.
- APQ registrations.
- CPU mean/p95.
- RSS mean/p95.

[Gambar III.1 Desain faktor eksperimen Phase 2]
[Gambar III.2 Pemetaan variabel bebas, kontrol, dan metrik]
[Tabel III.2 Variabel penelitian Phase 2]
[Tabel III.3 Metrik eksperimen dan cara pengukurannya]

## III.3 Data Penelitian

Data penelitian berasal dari VisDrone MOT dan hasil tracking YOLO. Proses data
dimulai dari sequence image, dilanjutkan dengan inference/tracking, lalu
prediction file dikonversi menjadi database SQLite. Database ini menjadi corpus
bersama bagi REST dan GraphQL.

Pipeline data:

1. Sequence image VisDrone MOT dibaca oleh script inference.
2. YOLO menghasilkan deteksi objek.
3. Tracker menghasilkan track id untuk objek lintas frame.
4. File prediksi format MOT dibangun.
5. `build_detection_db.py` membentuk schema relational.
6. `build_id_pool.py` membentuk pool ID untuk workload k6.

[Gambar III.3 Pipeline persiapan data VisDrone-YOLO-SQLite]
[Gambar III.4 ERD korpus deteksi MOT]

## III.4 Objek Penelitian

Objek penelitian adalah performa API REST dan GraphQL pada penyajian data
deteksi objek. Unit analisis adalah satu measured run pada satu experimental
cell. Satu cell ditentukan oleh kombinasi faktor eksperimen, misalnya
`protocol=graphql`, `caching=on`, `access_pattern=zipfian`,
`payload_weight=heavy`, dan seterusnya.

## III.5 Perangkat Pendukung

Perangkat lunak yang digunakan:

- Python untuk server, tools, dan orchestrator.
- FastAPI untuk REST.
- Strawberry GraphQL untuk GraphQL.
- SQLite untuk corpus relasional.
- Varnish untuk reverse proxy cache.
- k6 untuk workload dan load testing.
- psutil untuk telemetry CPU/RSS.
- Ultralytics YOLO untuk inference/tracking.

[Tabel IV.2 Modul APE dan tanggung jawabnya]

## III.6 Tahapan Pelaksanaan Penelitian

Tahapan penelitian:

1. Studi literatur REST, GraphQL, caching, APQ, load testing, dan VisDrone.
2. Persiapan dataset dan model.
3. Pengembangan Phase 1.
4. Eksekusi dan analisis Phase 1.
5. Evaluasi hasil uji pendahuluan.
6. Perancangan Phase 2.
7. Pengembangan APE Phase 2.
8. Eksekusi eksperimen Phase 2.
9. Analisis statistik.
10. Penyusunan laporan.

[Gambar I.1 Alur besar penelitian APE]

