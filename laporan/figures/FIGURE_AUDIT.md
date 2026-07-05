# FIGURE_AUDIT — inventaris & verdict semua figur yang ada (2026-07-04)

Basis pembanding: OUTLINE_RECONFIRM.md (outline terverifikasi) + kode aktual.
Verdict: **KEEP** (dipakai apa adanya) / **REVISE** (isi benar, perlu perbaikan
label/notasi/scope) / **RETIRE** (desain lama — hanya boleh sebagai pembanding
[BG], tidak pernah sebagai metode/hasil utama) / **MISSING** (dibutuhkan outline,
belum ada). Verdict figur baru yang menggantikan tercatat di kolom terakhir.

## A. Sumber diagram — laporan/figures/src/*.mmd (16 file, semua Mermaid)

| File | Isi | Milik desain | Akurasi vs kode | Verdict |
|---|---|---|---|---|
| fig_01_research_workflow_bpmn_style.mmd | Alur besar penelitian (BPMN-style) | Lintas | Alur benar, tapi framing berhenti di "Phase 2" — studi utama sekarang = studi skenario MOT | **REVISE**: tambah node studi MOT (redesign → kalibrasi → run M1–M6); pertahankan disclaimer "BPMN-style, bukan BPMN strict" |
| fig_02_pilot_to_main_experiment.mmd | Pilot → eksperimen utama | phase2 (entropy framing) | Menyebut entropy/payload/network sebagai kontrol utama eksperimen utama — itu grid phase2 lama, bukan studi MOT | **REVISE**: eksperimen utama = mot-scenarios-core (M1–M6, tier, rate terkalibrasi); phase2-core-real diposisikan sebagai subset RQ3 |
| fig_03_system_architecture_component.mmd | Arsitektur komponen APE | phase2 + MOT (shared) | Struktur benar; artefak usang: `k6/workload.js` (MOT pakai `workload_mot.js`), `scratch/id_pool.json` (MOT: `id_pool_mot.json`); modul shared belum lengkap (filters/aggregate/projection/selection tak tampak); Varnish tampil selalu-ada padahal run MOT caching=off | **REVISE** — ini padanan sah "class diagram sebagai struktur komponen server" yang diizinkan brief; perbarui artefak + beri catatan "Varnish hanya jalur RQ3" |
| fig_04_data_preparation_pipeline.mmd | VisDrone→YOLO/ByteTrack→SQLite | MOT (berlaku) | Semua skrip terverifikasi ada di ~/training/ (infer_mot_track.py, mot_compute_density.py, build_detection_db.py); id_pool: sebut juga id_pool_mot.json | **KEEP** (opsional: tambah id_pool_mot.json) |
| fig_05_sqlite_erd.mmd | ERD korpus MOT | MOT (berlaku) | Struktur/kolom persis DDL build_detection_db.py (termasuk detection.track_id nullable `|o--o{`); kurang: jumlah baris per tabel, dan register lama melabelinya "Chen ER model" padahal notasinya crow's foot | **REVISE** → digantikan **fig_20 (baru)**: ERD crow's foot + counts dari mot_profile.json + sitasi teks basis data |
| fig_06_experiment_orchestration_activity.mmd | Alur orkestrasi | phase2/MOT campur | Logika cocok run_experiment.py, tapi flowchart Mermaid ≠ notasi UML activity (tak ada initial/final node standar, fork, dsb.); tak memuat kalibrasi→derivasi rate | **REVISE** → digantikan **fig_19 (baru)**: UML 2.5 activity diagram alur eksekusi MOT lengkap |
| fig_07_rest_ssd.mmd | "SSD" request REST | MOT (berlaku) | Alur cocok rest_server.py; catatan notasi: menampilkan partisipan internal (DAL, DB) sehingga bukan *System* Sequence Diagram Larman murni — ini sequence diagram biasa | **REVISE** (ganti label "SSD"→"sequence diagram"); tetap berguna di BAB IV |
| fig_08_graphql_post_ssd.mmd | "SSD" GraphQL POST | MOT (konteks) | Cocok kode; POST route TIDAK dipakai benchmark MOT (klien = APQ-over-GET) — berguna justru untuk menjelaskan kenapa APQ diperlukan | **KEEP** dengan caption yang menyatakan perannya sebagai baseline non-cacheable, bukan jalur benchmark |
| fig_09_graphql_apq_cache_flow_ssd.mmd | APQ over GET | MOT (berlaku) | Cocok graphql_server.py:367-417 + apqGet() | **KEEP** (relabel "SSD"→sequence diagram) |
| fig_10_cache_hit_miss_sequence.mmd | Cache hit/miss/revalidasi Varnish | RQ3 (berlaku) | Cocok varnish.vcl + core/caching.py semantik | **KEEP** |
| fig_11_phase2_factor_grid.mmd | Faktor eksperimen phase2 | phase2 (stale) | Menampilkan 8 faktor seolah semua divariasikan; phase2-core-real hanya memvariasikan caching×access_pattern×payload_weight (12 cell), MOT run memvariasikan scenario×tier×rate | **REVISE**: pecah dua panel — grid MOT (RQ1/RQ2) dan grid caching RQ3; jangan tampilkan grid penuh yang tak pernah dijalankan |
| fig_12_analysis_pipeline.mmd | Pipeline analisis | RQ3 (berlaku) | Cocok analyze_phase2.py | **KEEP** untuk RQ3; varian MOT menyusul saat analyze_mot.py ditulis |
| fig_13_network_namespace_topology.mmd | Topologi netns | MOT+RQ3 (berlaku) | Isi benar tapi panah k6→NsIP digambar melewati veth secara visual; netem-nya tidak tampak "di veth host" | **REVISE** → digantikan **fig_18 (baru)**: UML deployment diagram | 
| fig_14_measurement_streams.mmd | Aliran metrik | MOT+RQ3 | Menampilkan X-Process-Time → k6 tanpa catatan bahwa header itu TIDAK dipanen ke results.csv Study B (OUTLINE B.9.3) | **REVISE**: beri anotasi "tersedia, tidak direkam (limitasi)" |
| fig_15_graphql_selection_set_payload.mmd | Konsep selection set | Konsep BAB II | Sesuai spec + graphql_server | **KEEP** |
| fig_16_variables_metrics_map.mmd | Peta IV/kontrol/DV | phase2 (stale) | IV list = grid phase2 penuh; untuk tesis terkunci IV-nya: protokol + kompleksitas query (skenario/tier) + rate [RQ1/RQ2]; caching×pattern [RQ3] | **REVISE**: re-scope ke RQ1/RQ2/RQ3 terkunci |

## B. Figur hasil yang sudah dirender (PNG di results/)

| Path | Isi | Milik desain | Verdict |
|---|---|---|---|
| phase2-core-real/analysis/fig_descriptive_boxplots.png | Boxplot deskriptif 12 cell | RQ3 (data valid) | **REVISE** → dibangun ulang sebagai figur laporan (fig_21/fig_22 baru, Bahasa Indonesia, n per cell dinyatakan); PNG analisis tetap sebagai artefak kerja |
| phase2-core-real/analysis/fig_crossover_surface.png | Surface REST−GraphQL lat_p95 vs hit-rate×payload | RQ3 | **KEEP** (kandidat Gambar V; regenerasi dgn label ID bila dipakai) |
| phase2-core-real/analysis/fig_coupling_entropy_hitrate.png | Entropy vs hit-rate | RQ3 — tapi entropy konstan (medium) di 720 baris | **RETIRE** (figur tanpa variasi IV; outline C.10 sudah menandai drop) |
| phase2-figures/*.png (5: roundtrip_savings, concurrency_scaling, cpu_efficiency_crossover, entropy_concurrency_interaction, network_profile_comparison) | Visual gabungan sesi phase2 | phase2 multi-sesi PARALEL (2–8 sesi) | **RETIRE** dari hasil utama; hanya fig_roundtrip_savings boleh muncul sebagai korroborasi kualitatif [BG] per C.6.5, dengan disclosure paralelisme |
| phase2-pilot/analysis/*.png (3) | Analisis pilot | phase2 pilot | **RETIRE** (pilot) |
| phase2-combined/analysis/*.png (3) | Analisis gabungan sesi paralel | phase2 multi-sesi | **RETIRE** (pooling lintas sesi paralel — dilarang oleh C.9) |
| analysis_session1_preliminary/figures/*.png (9) | ECDF, Cliff's δ, moderation, overfetching | Study A / run-sesi-1 [BG] | **RETIRE** (data run-sesi-1 membawa 345.879 in-band GraphQL error; preseden metode boleh dikutip, figurnya tidak) |

## C. Tabel di draft bab (cakupan singkat — tabel bukan target utama audit ini)

TABLE_REGISTER.md masih ber-framing "Phase 1 pilot / Phase 2 utama"
(Tabel III.1/III.2/V.1/V.2). Sejalan dengan OUTLINE B (re-scope BAB III), tabel
variabel harus diganti ke: skenario M1–M6 & tier (Tabel definisi skenario),
rate terkalibrasi per family, dan tabel perbedaan dua sumber data (OUTLINE B.10)
— di luar lingkup tugas figur ini, dicatat agar tidak hilang.

## D. MISSING — dibutuhkan outline terverifikasi, belum ada di mana pun

| Kebutuhan | Outline node | Status |
|---|---|---|
| Sequence diagram REST K-RT vs GraphQL 1-RT (M5/M6) — figur inti RQ2 | A.1.3, A.3.2, C.6 | **DIBANGUN SEKARANG → fig_17** |
| UML deployment diagram topologi eksperimen (netns, veth+netem, systemd caps, DAL, SQLite) | B.2, B.4 | **DIBANGUN SEKARANG → fig_18** |
| UML activity diagram alur eksekusi (kalibrasi → rate 40/80/120% → warmup 1 → 30 run → resume/progress) | B.6–B.8 | **DIBANGUN SEKARANG → fig_19** |
| ERD dengan kardinalitas crow's foot + jumlah baris | B.1.2 | **DIBANGUN SEKARANG → fig_20** (supersedes fig_05) |
| RQ3: cache_hit_rate per access pattern per protokol | C.8 | **DIBANGUN SEKARANG → fig_21** |
| RQ3: delta waktu respons caching on-vs-off per pattern per protokol | C.8 | **DIBANGUN SEKARANG → fig_22** |
| RQ1: boxplot/latensi p50-p95 M1–M4 × density × rate; throughput; CPU/RSS | C.10 | **SCRIPT-READY (Step 3)** — data belum lengkap |
| RQ2: M5 2-RT vs 1-RT per window; M6 Δ(K) crossover; Δ vs round_trip_count; overload terpisah | C.6, C.7 | **SCRIPT-READY (Step 3)** — data belum lengkap |

Diagram yang secara sadar TIDAK dibuat (sesuai brief): use case diagram (satu
aktor klien API — tidak menambah informasi), class diagram aplikasi (digantikan
struktur komponen fig_03 yang direvisi).
