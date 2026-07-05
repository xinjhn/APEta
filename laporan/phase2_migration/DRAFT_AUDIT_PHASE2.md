# Audit Draft `laporan_revised (2).docx` untuk Migrasi Phase 2

Audit ini dibuat dari ekstraksi paragraf draft DOCX. Tujuannya adalah menunjukkan bagian yang perlu diperbaiki agar selaras dengan eksperimen utama Phase 2.

## Struktur Draft Saat Ini

Draft saat ini berisi:

- BAB I Pendahuluan
- BAB II Tinjauan Pustaka
- BAB III Metodologi Penelitian
- BAB IV Analisis dan Perancangan Alat Pembantu Eksperimen
- Daftar Pustaka
- Lampiran

Draft belum memiliki Bab V, VI, dan VII yang lengkap sesuai template final. Ini perlu ditambahkan nanti, terutama Bab V untuk hasil eksperimen utama.

## Narasi Lama yang Masih Dominan

Draft masih kuat memakai framing Phase 1:

- output YOLO26 sebagai VCD/nested JSON;
- data disimpan dalam in-memory data pool;
- tidak memakai database agar menghindari I/O bottleneck;
- skenario utama S1-S4: baseline, partial, filtered, aggregate;
- matrix protocol x pattern x density x concurrency;
- VisDrone-DET val 548 citra sebagai data utama;
- endpoint `/api/baseline/{image_id}`, `/api/partial/{image_id}`, dan sejenisnya;
- 72 skenario sebagai desain utama;
- random image selection untuk mencegah bias L3 CPU cache.

Semua poin tersebut perlu diturunkan statusnya menjadi konteks uji pendahuluan/pilot, atau diganti dengan desain Phase 2.

## Koreksi Besar yang Harus Dilakukan

| Area | Draft Saat Ini | Harus Menjadi Phase 2 |
|---|---|---|
| Peran Phase 1 | Eksperimen utama | Uji pendahuluan/pilot untuk validasi instrument dan variabilitas awal |
| Data utama | VisDrone-DET val / VCD JSON / in-memory pool | VisDrone-MOT processed corpus in SQLite `mot_detections.db` |
| Unit data | Citra dan array detection JSON | Sequence, image, detection, track, class |
| Data access | In-memory pool | Shared `DetectionDAL` over SQLite |
| API REST | `/api/baseline`, `/api/partial`, `/api/filter`, `/api/aggregate` | `/images`, `/images/{id}/detections`, `/tracks/{id}`, `/tracks/{id}/trajectory` |
| GraphQL | Resolver untuk baseline/partial/filter/aggregate | Schema `Image`, `Detection`, `Track`, `TrajectoryPoint` plus APQ-over-GET |
| Cache | Hampir tidak menjadi faktor utama | Variabel bebas `caching=on/off`, Varnish, Cache-Control, ETag, APQ |
| Workload | pattern/density/concurrency | protocol, caching, access_pattern, entropy, payload_weight, network, density, concurrency |
| Payload | baseline/partial/filter/aggregate | light image detections vs heavy track trajectory |
| Jaringan | loopback saja | lan vs constrained via topology/netem |
| Metrik | latency, throughput, payload, CPU/RAM | plus cache_hit_rate, APQ registrations, round_trip_count, error_rate |

## Bagian yang Perlu Diubah Secara Prioritas

1. Judul
   - Judul lama terlalu menonjolkan YOLO26 dan komunikasi data umum.
   - Judul baru perlu memasukkan caching/pola akses atau setidaknya "variasi caching dan pola akses".

2. Bab I Latar Belakang
   - Kurangi klaim bahwa masalah utama hanya over-fetching/partial field.
   - Tambahkan masalah fairness benchmark, cacheability REST vs GraphQL, APQ, dan query shape.

3. Rumusan Masalah dan RQ
   - RQ lama hanya satu: perbedaan REST vs GraphQL.
   - Phase 2 butuh RQ yang menanyakan pengaruh caching, access pattern, payload, entropy, dan kondisi kapan REST/GraphQL unggul.

4. Dukungan Data
   - Ganti VisDrone-DET val 548 citra sebagai data utama.
   - Gunakan VisDrone-MOT corpus SQLite: 7 sequence, 2.846 image, 5.429 track, 104.767 detection.

5. Ruang Lingkup dan Batasan
   - Ganti "tanpa basis data" menjadi "basis data SQLite read-only yang sama untuk kedua API".
   - Tambahkan bahwa akurasi model bukan fokus penelitian.

6. Bab III Variabel Penelitian
   - Hapus S1-S4 sebagai variabel utama.
   - Masukkan faktor Phase 2.

7. Bab III Data Penelitian
   - Ganti VCD/in-memory menjadi pipeline VisDrone-MOT -> YOLO tracking -> MOT prediction txt -> SQLite.

8. Bab IV Analisis Domain
   - Ganti "Karakteristik Output YOLO26 beserta Skema VCD" menjadi "Karakteristik Korpus Deteksi MOT dan Relasi Image-Detection-Track".

9. Bab IV Arsitektur
   - Ganti InMemoryPool menjadi DetectionDAL + SQLite.
   - Tambahkan Varnish, APQ-over-GET, k6/workload.js, telemetry sampler, orchestrator.

10. Bab V
   - Tambahkan Bab V sesuai template.
   - Phase 1 dilaporkan ringkas sebagai uji pendahuluan.
   - Phase 2 menjadi hasil utama.

## Istilah yang Harus Dicari dan Direvisi

Gunakan fitur Find di Word untuk istilah berikut:

- `VCD`
- `In-Memory`
- `InMemoryPool`
- `Tanpa Basis Data`
- `SQLite` jika konteksnya "tidak digunakan"
- `baseline`
- `partial`
- `filtered`
- `aggregate`
- `S1`, `S2`, `S3`, `S4`
- `72 skenario`
- `VisDrone-DET`
- `548 citra`
- `/api/baseline`
- `/api/partial`
- `/api/aggregate`
- `L3 CPU Cache` jika dipakai sebagai justifikasi utama desain data

## Framing yang Disarankan

Gunakan framing berikut:

> Penelitian dilaksanakan dalam dua tahap. Tahap pertama merupakan uji pendahuluan yang digunakan untuk memvalidasi instrument, menguji kesetaraan respons dasar REST dan GraphQL, serta mengamati variabilitas awal. Tahap kedua merupakan eksperimen utama yang menggunakan desain faktor lebih lengkap dengan memasukkan caching, pola akses, entropi query, bobot payload, profil jaringan, dan concurrency.

Hindari framing:

- "Phase 1 gagal".
- "Metodologi sebelumnya salah".
- "Penelitian pivot".
- "Phase 2 muncul karena hasil tidak sesuai harapan".

Gunakan istilah:

- uji pendahuluan,
- pilot experiment,
- kalibrasi instrument,
- eksperimen utama,
- desain faktor utama,
- validasi readiness.
