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

---

## Figur hasil mot-scenarios-core (fig_rq1_*, fig_rq2_*) — dibuat 2026-07-07

Sumber data semua figur di bawah: `results/mot-scenarios-core/results.csv`
(3.240 run terukur, 108 cell × 30 run, eksekusi serial penuh 2026-07-02 s.d.
2026-07-06, error_rate = 0; drift dalam-cell awal-vs-akhir ~0%, CV replikasi
median 0,5%). Sidecar statistik: `export/rq1_stats.json`, `export/rq2_stats.json`.
Varian per rate: `_r40`, `_r80` (sub-saturasi), `_r120_overload` (dianalisis
terpisah). Telemetri CPU/RSS sesi ini valid dan lolos uji kewajaran
(CV dalam-cell median 1,3%; CPU naik monoton terhadap rate, rasio r80/r40 =
1,93 ≈ 2). Kolom `lat_p50/lat_p95` pada M5/M6 sisi REST adalah latensi
per-round-trip; figur M5/M6 memakai `page_latency_med` (per halaman/skenario).

## fig_rq1_lat_p50 / fig_rq1_lat_p95 — waktu respons M1–M4 · usulan: BAB V

> Median waktu respons per skenario M1–M4 × tier densitas objek. Pada kedua
> rate sub-saturasi REST lebih cepat pada seluruh 12 kombinasi skenario×tier
> dengan pemisahan lengkap (Cliff's δ = −1,00 pada tiap cell; p50 REST
> 6,9–9,7 ms vs GraphQL 10,8–20,9 ms; rasio 1,4×–2,7×). Selisih terkecil pada
> M4 (agregasi, payload ratusan byte), terbesar pada M1-high (payload ~7,2 KB).
> Varian r120_overload (sumbu-y logaritmik): hanya GraphQL M1-high yang
> kolaps saturasi (p50 ~6,7 detik; 30/30 run mencatat dropped_iterations),
> REST tetap ≤8,7 ms pada seluruh cell. Batang = median 30 run per cell;
> whisker = rentang interkuartil.

## fig_rq1_throughput — pemenuhan laju kedatangan · usulan: BAB V (atau lampiran)

> Median throughput per skenario × tier. Pada r40/r80 kedua protokol memenuhi
> laju kedatangan target k6 (open-loop constant-arrival-rate) sehingga
> perbandingan waktu respons antar protokol dilakukan pada beban tervalidasi
> sama; pada r120_overload throughput protokol yang tersaturasi turun di bawah
> target (lihat `rows_with_dropped_iterations` pada sidecar sebelum menyebut
> cell "tersaturasi").

## fig_rq1_cpu / fig_rq1_rss — biaya sumber daya server · usulan: BAB V

> Median CPU dan RSS proses server per skenario × tier. Pada rate sama,
> GraphQL memakai ~2,4×–3,9× CPU REST pada M1–M4 (mis. M1-high r80: 17,9%
> vs 79,5%); RSS keduanya stabil. Catatan kewajaran (outline C.9): CV
> dalam-cell median 1,3% dan CPU naik proporsional terhadap rate (rasio
> median r80/r40 = 1,93). Satu cell ber-CV tinggi (68%): M4-high
> r120_overload REST — cell ambang saturasi dengan 1 run dropped_iterations.

## fig_rq2_m5_window — M5 trajektori bersarang (under-fetching) · usulan: BAB V

> Waktu respons skenario M5 per halaman: REST dipaksa 2 round-trip
> (GET /tracks/{id} + GET .../trajectory) vs GraphQL 1 kueri bersarang.
> Penghematan satu round-trip GraphQL hanya menghasilkan seri pada window
> terkecil w2 (r80: 14,5 vs 14,6 ms; satu-satunya cell studi tanpa pemisahan
> lengkap — δ = +0,32 pada r40, −0,82 pada r80); pada w8 GraphQL +9% dan w23
> +28–34% lebih lambat karena overhead eksekusi GraphQL tumbuh lebih cepat
> daripada biaya satu round-trip LAN (delay netem 5 ms). Varian
> r120_overload: GraphQL w23 kolaps (~5,1 detik; 30/30 dropped_iterations).
> Catatan lingkup: kesimpulan terikat profil "lan"; pada latensi jaringan
> lebih tinggi biaya round-trip membesar dan hasil w2 dapat berbalik.

## fig_rq2_m6_crossover — M6 K round-trip vs 1 kueri komposit · usulan: BAB V (figur kunci RQ2)

> Waktu respons halaman M6: REST menyelesaikan halaman K id track lewat K
> panggilan berurutan, GraphQL lewat satu kueri komposit `tracks(ids)`.
> Biaya REST linier terhadap K (~7,5 ms per panggilan); GraphQL nyaris datar
> (14,2→19,9 ms). Titik silang hasil interpolasi linier K* ≈ 2,0 pada ketiga
> rate (K = 2 TIDAK diukur — grid K ∈ {1,5,10}); pada K = 5 GraphQL 2,2×
> lebih cepat, pada K = 10 3,8–4,1× (δ = +1,00, pemisahan lengkap — satu-
> satunya keunggulan GraphQL berpemisahan lengkap dalam studi ini). Varian
> r120_overload (sumbu-y logaritmik): giliran REST yang kolaps pada k10
> (~13,1 detik per halaman; CPU ~168%) karena 52 halaman/s × 10 panggilan =
> 520 request/s melampaui kapasitas origin.

## fig_rq2_delta_rtc — konsolidasi round-trip M5+M6 · usulan: BAB V (ringkasan RQ2)

> Selisih median waktu respons REST − GraphQL terhadap jumlah round-trip
> REST per iterasi (GraphQL selalu 1). Δ < 0 (REST unggul) pada 1–2
> round-trip; Δ menjadi positif dan membesar pada 5 dan 10 round-trip
> (+20,9 ms dan +60,5 ms pada r80; +19,7 dan +55,3 ms pada r40). Whisker = CI bootstrap 95% selisih
> median (2.000 resampel, seed 42). Varian r120_overload memakai sumbu-y
> symlog (linier di ±10 ms) karena memuat +13,1 detik (M6-k10, REST kolaps)
> dan −5,0 detik (M5-w23, GraphQL kolaps) sekaligus nilai ±milidetik.
