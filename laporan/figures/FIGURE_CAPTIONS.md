# FIGURE_CAPTIONS — draf caption figur baru (fig_17 – fig_22)

Konvensi: caption Bahasa Indonesia, menyebut notasi + sitasi HANYA bila
notasinya memang bersumber dari referensi tersebut; chart hasil statistik
TIDAK diberi sitasi buku SE. Nomor "Gambar X.Y" final ditetapkan saat
penempatan bab; di bawah ini disarankan penempatan. Rujukan bank sitasi:
`laporan/REFERENCES_BASIS.md` (#2 = OMG UML 2.5.1, #1 = Larman). Entri
bertanda [VERIFY EDITION] belum ada di bank — tambahkan dulu sebelum dipakai.

---

## fig_17 — Sequence diagram REST vs GraphQL (inti RQ2) · usulan: BAB IV (rujuk ulang di BAB V)

> Diagram sequence perbandingan jumlah round-trip pada skenario M6: REST
> menyelesaikan satu halaman berisi K id track melalui K panggilan HTTP
> berurutan (round_trip_count = K), sedangkan GraphQL menyelesaikan halaman
> yang sama melalui satu kueri komposit `tracks(ids)` (round_trip_count = 1)
> yang tetap memicu hanya dua kueri SQL IN-clause pada DAL bersama. Pada
> skenario M5, pola yang sama berlaku dengan K = 2 pada sisi REST. Sumber:
> diolah penulis berdasarkan implementasi `k6/workload_mot.js`,
> `rest_server.py`, `graphql_server.py`, dan `core/dal.py`; notasi sequence
> diagram mengacu pada OMG UML 2.5.1 [#2] (lihat juga Fowler, *UML
> Distilled* [VERIFY EDITION]).

Catatan kejujuran: kedua protokol tidak pernah berjalan bersamaan — dua
frame pada figur membandingkan dua eksekusi terpisah pada port yang sama.

## fig_18 — Deployment diagram topologi eksperimen · usulan: BAB IV (dirujuk BAB III lingkungan)

> Diagram deployment topologi eksperimen mot-scenarios-core pada satu VM:
> k6 (open-loop constant-arrival-rate, core 8–15) berada di namespace
> jaringan root; server REST/GraphQL bergantian sebagai satu proses uvicorn
> single-worker (HTTP/1.1, port 8000) di dalam namespace `ape-origin`,
> dibatasi systemd scope (CPUQuota 400%, MemoryMax 2048M, core 0–7);
> keduanya terhubung melalui satu pasang veth dengan emulasi jaringan netem
> "lan" (delay 5 ms ± 1 ms, 100 Mbit) yang dipasang hanya pada sisi host.
> Kedua protokol membaca artefak DAL (`core/dal.py`) dan SQLite
> (`mot_detections.db`) yang sama — substrat fairness studi ini. Sumber:
> diolah penulis berdasarkan `tools/netns_topology.sh`,
> `orchestrator/config.py`, dan snapshot lingkungan
> `results/mot-scenarios-core/env_snapshot/`; notasi deployment diagram
> mengacu pada OMG UML 2.5.1 [#2] (lihat juga Sommerville, *Software
> Engineering*, bab System Modeling [VERIFY EDITION]).

## fig_19 — Activity diagram alur eksekusi · usulan: BAB III (prosedur eksperimen)

> Diagram activity alur eksekusi eksperimen: kalibrasi ceiling saturasi per
> family skenario, derivasi laju kedatangan 40%/80%/120% dari ceiling
> protokol terendah (label r120_overload), pembangkitan run plan
> terandomisasi (3.240 run terukur), lalu eksekusi serial per blok — satu
> warmup yang dibuang diikuti 30 run terukur 90 detik per cell — hingga
> agregasi ke results.csv dengan mekanisme resume berbasis run_uid. Sumber:
> diolah penulis berdasarkan `tools/calibrate_mot.py`,
> `design/CALIBRATION.md`, `orchestrator/make_run_plan.py`, dan
> `orchestrator/run_experiment.py`; notasi activity diagram mengacu pada
> OMG UML 2.5.1 [#2] (lihat juga Sommerville, bab System Modeling
> [VERIFY EDITION]).

## fig_20 — ERD korpus MOT · usulan: BAB III (data penelitian; dirujuk BAB IV)

> Entity Relationship Diagram korpus deteksi MOT `mot_detections.db`
> dengan kardinalitas notasi crow's foot: 7 sequence memuat 2.846 image dan
> 5.429 track; 104.767 detection merujuk image (wajib), track (opsional
> menurut skema; pada data aktual seluruh deteksi memiliki track), dan
> class (10 kategori). Trajektori yang dipakai skenario M5/M6 bukan tabel,
> melainkan hasil kueri turunan atas detection–image yang dibatasi jendela
> frame ±W. Sumber: diolah penulis berdasarkan DDL
> `training/build_detection_db.py` dan profil `design/mot_profile.json`;
> notasi ERD mengacu pada Elmasri & Navathe, *Fundamentals of Database
> Systems* [VERIFY EDITION].

## fig_21 — Tingkat cache hit per pola akses (RQ3) · usulan: BAB V

> Tingkat cache hit per pola akses pada kondisi caching aktif (Varnish),
> sesi phase2-core-real: pola zipfian (θ = 0,99) mencapai median 0,37–0,43;
> pola uniform 0,02–0,06; pola unique 0,00 — setara antara REST dan GraphQL
> (APQ-over-GET) pada setiap kombinasi payload. Batang = median 30 run per
> cell; whisker = rentang interkuartil. Data:
> `results/phase2-core-real/results.csv` (720 run, eksekusi serial penuh).

## fig_22 — Efek caching terhadap waktu respons (RQ3) · usulan: BAB V

> Selisih median waktu respons p50 antara kondisi caching aktif dan
> nonaktif per pola akses (negatif = caching mempercepat): manfaat caching
> hanya muncul pada pola zipfian — terbesar pada GraphQL (−2,2 s.d. −3,1 ms)
> dan kecil pada REST (−0,3 s.d. −0,4 ms) — sedangkan pola uniform dan
> unique justru membayar overhead proxy sebesar ~+0,7 s.d. +1,1 ms.
> n = 30 run per kondisi per cell; whisker = CI bootstrap 95% selisih
> median (2.000 resampel, seed 42). Data:
> `results/phase2-core-real/results.csv`. Catatan lingkup: satu titik
> jaringan (constrained), densitas medium, laju tetap 10 request/s; kolom
> CPU/RSS sesi ini invalid dan tidak digunakan.

---

## Caption figur lama yang direvisi statusnya (rujukan singkat)

- **fig_05 (ERD lama)** → digantikan fig_20; jangan pakai label "Chen ER
  model" (notasi yang dipakai crow's foot, bukan Chen).
- **fig_07/fig_09 ("SSD")** → pertahankan isi, ganti sebutan "System
  Sequence Diagram" menjadi "sequence diagram" (partisipan internal DAL/DB
  membuatnya bukan SSD Larman murni); sitasi notasi tetap OMG UML 2.5.1
  [#2] + Larman [#1] untuk konsep interaksi sistem.
- **fig_08 (GraphQL POST)** → tambahkan kalimat caption: "Rute POST ini
  bukan jalur benchmark; ia baseline non-cacheable yang memotivasi
  APQ-over-GET (fig_09)."
- **fig_14 (aliran metrik)** → tambahkan kalimat: "Header X-Process-Time
  tersedia dari kedua server tetapi tidak dipanen ke results.csv studi
  utama (limitasi, lihat BAB V ancaman validitas)."
