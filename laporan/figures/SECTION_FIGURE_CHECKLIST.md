# SECTION_FIGURE_CHECKLIST — peta bab → figur, dengan status (2026-07-04)

Status: **READY** (sumber + render final ada di `figures/export/`) ·
**SCRIPT-READY** (skrip teruji dry-run; menunggu results.csv lengkap
~2026-07-06) · **REVISE** (figur lama, isi benar, perlu perbaikan yang
tercatat di FIGURE_AUDIT.md) · **RETIRED** (tidak dipakai sebagai metode/
hasil utama; paling banter pembanding [BG]).

## BAB I — Pendahuluan
| Figur | Status | Catatan |
|---|---|---|
| fig_01 alur besar penelitian | REVISE | tambah node studi MOT (lihat FIGURE_AUDIT §A) |
| fig_02 pilot → eksperimen utama | REVISE | eksperimen utama = mot-scenarios-core, bukan grid entropy phase2 |

## BAB II — Dasar Teori
| Figur | Status | Catatan |
|---|---|---|
| fig_10 cache hit/miss/revalidasi (konsep RFC 9111) | READY (KEEP) | dipakai juga BAB IV |
| fig_15 selection set → payload (konsep GraphQL) | READY (KEEP) | |
| fig_17 sequence REST K-RT vs GraphQL 1-RT | **READY (BARU)** | juga menopang A.3.2 (model biaya round-trip); render: `export/fig_17_...png/svg` |

## BAB III — Metodologi
| Figur | Status | Catatan |
|---|---|---|
| fig_19 activity diagram alur eksekusi (UML 2.5) | **READY (BARU)** | menggantikan peran fig_06 untuk alur MOT |
| fig_20 ERD korpus MOT + jumlah baris (crow's foot) | **READY (BARU)** | menggantikan fig_05; sitasi Elmasri & Navathe [VERIFY EDITION] |
| fig_04 pipeline persiapan data | READY (KEEP) | |
| fig_11 grid faktor | REVISE | pecah: grid MOT (RQ1/RQ2) vs grid caching RQ3 |
| fig_16 peta variabel | REVISE | re-scope ke RQ terkunci |
| fig_18 deployment topologi | **READY (BARU)** | dirujuk dari III (lingkungan) dan IV |

## BAB IV — APE (implementasi)
| Figur | Status | Catatan |
|---|---|---|
| fig_03 arsitektur komponen | REVISE | perbarui artefak (workload_mot.js, id_pool_mot.json); catat Varnish = jalur RQ3 saja |
| fig_07 sequence REST | REVISE (label) | ganti sebutan "SSD" → sequence diagram |
| fig_08 sequence GraphQL POST | READY (KEEP) | caption: baseline non-cacheable, bukan jalur benchmark |
| fig_09 sequence APQ-over-GET | READY (KEEP) | relabel "SSD" |
| fig_18 deployment topologi eksperimen | **READY (BARU)** | supersedes fig_13 |
| fig_14 aliran metrik | REVISE | anotasi X-Process-Time "tersedia, tidak direkam" |

## BAB V — Hasil dan Pembahasan
| Figur | Status | Catatan |
|---|---|---|
| fig_21 tingkat cache hit per pola akses (RQ3) | **READY (BARU)** | data lengkap phase2-core-real; n=30/cell |
| fig_22 Δ waktu respons caching on−off (RQ3) | **READY (BARU)** | CI bootstrap 95%; CPU/RSS sengaja absen (invalid) |
| fig_crossover_surface (RQ3, analysis/) | READY (KEEP) | regenerasi dengan label ID bila dipakai |
| fig_rq1_lat_p50/p95 × {r40,r80} | **SCRIPT-READY** | `scripts/rq1_scenario_figures.py` |
| fig_rq1_throughput × {r40,r80} | **SCRIPT-READY** | idem |
| fig_rq1_cpu / fig_rq1_rss × {r40,r80} | **SCRIPT-READY** | cek kewajaran CPU/RSS dulu (C.9) |
| fig_rq1_* _r120_overload | **SCRIPT-READY** | selalu figur TERPISAH berlabel overload |
| fig_rq2_m5_window × {r40,r80} | **SCRIPT-READY** | `scripts/rq2_crossover_figures.py` |
| fig_rq2_m6_crossover × {r40,r80} (K* otomatis) | **SCRIPT-READY** | KONTRIBUSI UTAMA |
| fig_rq2_delta_rtc × {r40,r80} (Δ vs jumlah round-trip) | **SCRIPT-READY** | figur "konsolidasi round-trip" literal |
| fig_rq2_* _r120_overload | **SCRIPT-READY** | terpisah, tidak pernah dipool |
| fig_coupling_entropy_hitrate | RETIRED | entropi konstan di data RQ3 |
| results/phase2-figures/* (5 PNG) | RETIRED | hanya fig_roundtrip_savings boleh sebagai korroborasi [BG] + disclosure paralelisme |
| analysis_session1_preliminary/* (9 PNG) | RETIRED | data run-sesi-1 [BG] |
| phase2-pilot & phase2-combined analysis PNG | RETIRED | pilot / pooling sesi paralel |

## Baris siap-tempel untuk laporan/FIGURE_REGISTER.md
(di luar lingkup tulis tugas ini — laporan/ root; tempel manual oleh peneliti)

    | 21 | Gambar (BAB II/IV) | Sequence REST K round-trip vs GraphQL 1 kueri (M5/M6) | II/IV/V | UML sequence | Inti RQ2: konsolidasi round-trip | OMG UML 2.5.1 | `figures/src/fig_17_sequence_rest_vs_graphql_roundtrip.puml` | ready-source |
    | 22 | Gambar (BAB III/IV) | Deployment topologi eksperimen mot-scenarios-core | III/IV | UML deployment | Substrat fairness + netem lan | OMG UML 2.5.1 | `figures/src/fig_18_deployment_experiment_topology.puml` | ready-source |
    | 23 | Gambar (BAB III) | Activity alur eksekusi eksperimen MOT | III | UML activity | Kalibrasi→rate→serial→results.csv | OMG UML 2.5.1 | `figures/src/fig_19_activity_execution_flow.puml` | ready-source |
    | 24 | Gambar (BAB III) | ERD korpus MOT (crow's foot + jumlah baris) | III/IV | ERD | Struktur relasional yang RQ2 andalkan | Elmasri & Navathe [VERIFY EDITION] | `figures/src/fig_20_erd_mot_schema.puml` | ready-source |
    | 25 | Gambar (BAB V) | Tingkat cache hit per pola akses (RQ3) | V | Bar chart | Efek pola akses pada hit rate | hasil phase2-core-real | `figures/scripts/rq3_caching_figures.py` | ready-source |
    | 26 | Gambar (BAB V) | Δ waktu respons caching on−off per pola akses (RQ3) | V | Bar chart + CI | Kapan caching menguntungkan | hasil phase2-core-real | `figures/scripts/rq3_caching_figures.py` | ready-source |
    | 27 | Gambar (BAB V) | RQ1 waktu respons/throughput/CPU/RSS per skenario | V | Bar chart | Jawaban RQ1 | mot-scenarios-core (menunggu) | `figures/scripts/rq1_scenario_figures.py` | later |
    | 28 | Gambar (BAB V) | RQ2 M5/M6 crossover + Δ vs jumlah round-trip | V | Line/point chart | Jawaban RQ2 (kontribusi utama) | mot-scenarios-core (menunggu) | `figures/scripts/rq2_crossover_figures.py` | later |

## Catatan operasional
- Toolchain diagram: PlantUML 1.2025.4 (jar diunduh saat sesi; untuk
  regenerasi, unduh ulang `plantuml-1.2025.4.jar` dan jalankan
  `java -jar plantuml.jar -tpng -o ../export src/fig_1*.puml`). Sumber .puml
  tetap teks yang mudah direview, sejalan konvensi src/ + export/.
- Sumber Mermaid lama tetap utuh di `figures/src/*.mmd` (tidak ada yang dihapus).
- Semua angka pada figur baru berasal dari CSV/kode terverifikasi
  (OUTLINE_RECONFIRM.md); tidak ada klaim outline yang belum dicek yang
  dipropagasikan ke figur.
