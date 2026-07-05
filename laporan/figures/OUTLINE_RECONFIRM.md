# OUTLINE_RECONFIRM — verifikasi klaim OUTLINE_MASTER.md terhadap workspace

Tanggal verifikasi: 2026-07-04 (± 15:10 WIB). Metode: setiap klaim outline yang
menjadi dasar figur dicek langsung ke sumber di disk (kode, CSV, design doc).
Aturan: bila outline dan kode/data tidak cocok, **kode/data menang**.

Status verdict: **CONFIRMED** (klaim cocok dengan sumber), **WRONG** (klaim salah),
**STALE** (menunjuk desain lama/Phase-1), **NO-SOURCE** (sumber tidak ada di disk),
**CORRECTED** (cocok setelah koreksi kecil — koreksi dicantumkan).

## 1. Status data (dasar keputusan "boleh di-chart sekarang atau tidak")

| Klaim outline | Verifikasi | Verdict |
|---|---|---|
| `mot-scenarios-core` LIVE, 1.642/3.240 (~51%), ETA ≈ 2026-07-06 | tmux `mot-core` aktif; orchestrator PID 581043 jalan; k6 aktif di blok B0038; `logs/progress.log` (bukan root dir): `done=1809/3240 eta_min=2166` per 15:12 — **JANGAN di-chart** | CONFIRMED (angka bergerak; progress.log ada di `logs/`, bukan root) |
| `phase2-core-real` lengkap 720/720, analisis di `analysis/` | `results.csv` = 720 baris data + header; `analysis/` berisi report + 3 PNG + comparisons.csv | CONFIRMED |
| CPU/RSS `phase2-core-real` INVALID (bug PID sampler) | `phase2_analysis_report.txt` SCOPE NOTES bullet terakhir; kolom cpu_mean berisi 0.0 di sampel yang dicek | CONFIRMED — jangan pernah memfigurkan CPU/RSS dari sesi ini |
| Arms lanjutan `m6cache → m5embed → m1mem` belum ada di disk | Tidak ada `results/mot-scenarios-m6cache` dst.; GO order tercatat di `design/CALIBRATION.md` §Methods note | CONFIRMED (figur untuk arm ini = kondisional, jangan disiapkan sebagai "pasti") |

## 2. Klaim yang menjadi dasar figur UML/diagram

| # | Klaim outline (node) | Sumber dicek | Hasil | Verdict |
|---|---|---|---|---|
| 2.1 | A.1.3/A.3.2 — REST under-fetching ⇒ K round trip; M5 REST = 2 panggilan berurutan, M6 REST = K panggilan vs GraphQL 1 query komposit | `k6/workload_mot.js:167-189` (M5: GET `/tracks/{id}` LALU GET `/tracks/{id}/trajectory`, `roundTripCount.add(2)`; M6: loop K× GET `/tracks/{id}/trajectory?window=2`, `roundTripCount.add(K)`), `gqlIteration()` M5/M6 = 1 `apqGet` (`roundTripCount.add(1)`) | Persis seperti klaim; page_latency = jumlah sub-call REST / 1 call GraphQL | CONFIRMED |
| 2.2 | A.2.3 — GraphQL M6 = SATU batch DAL (2 SQL IN-clause), bukan N+1 | `graphql_server.py::Query.tracks` (prefetch via `get_tracks_with_trajectories`), `core/dal.py:284-325` (2 query total), `tests/test_parity_mot.py:273 test_m6_single_dal_batch` PASS (PARITY_REPORT_MOT.md) | Benar; fallback lazy hanya bila `center_frame` non-default | CONFIRMED |
| 2.3 | A.2.4 — alur APQ-over-GET: hash-first, `PERSISTED_QUERY_NOT_FOUND`, registrasi `query+hash` | `graphql_server.py:367-417` (route GET manual), `workload_mot.js::apqGet()` | Persis; store proses-lokal `_PERSISTED_QUERIES` | CONFIRMED |
| 2.4 | B.2 — substrat fairness: shared DAL (`core/dal.py`, thread-local sqlite, `PRAGMA query_only=1`), shared caching (`core/caching.py` max-age=30/no-store), encoder kompak dua sisi, `auto_camel_case=False`, HTTP/1.1 single worker, server bergantian port 8000 | Semua file dibaca; `rest_server.py:64` `json.dumps(separators…)`, `graphql_server.py:72-77` CompactGraphQLRouter, `:343` StrawberryConfig, `run_experiment.py::ensure_server/stop_server` | Persis | CONFIRMED |
| 2.5 | B.4.2 — topologi netns: netem HANYA di veth sisi host; varnish→backend lewat loopback namespace; perbaikan artefak double-delay | `tools/netns_topology.sh` header (diagram + pengukuran 2×→1×), `tools/netem.sh` THREAT note, `orchestrator/config.py:145-158` | Persis; IP 10.200.0.1 (host) / 10.200.0.2 (ns), veth-ape-h/veth-ape-n | CONFIRMED |
| 2.6 | B.4.3 — profil netem run MOT = `lan` 5 ms ± 1 ms, 100 Mbit | `env_snapshot/netem_qdisc.txt`: `delay 5ms 1ms rate 100Mbit`; CALIBRATION.md §Setup | Persis (catatan: header `netem.sh` menyebut "lan RTT~10ms" = 5 ms/arah — konsisten) | CONFIRMED |
| 2.7 | B.4.4 — caps & pinning: CPUQuota=400%, MemoryMax=2048M, server core 0-7, k6 8-15, sampler 31 | `env_snapshot/ape_env.txt`; ps live menunjukkan `systemd-run … -p CPUQuota=400% -p MemoryMax=2048M … taskset -c 0-7 … uvicorn rest_server:app --workers 1` | Persis | CONFIRMED |
| 2.8 | B.6/B.7 — kalibrasi: probe 12 s bertingkat pada cell terberat per family + 2 bisection; saturasi = dropped>0 ∨ err>1% ∨ p95>max(5×baseline,150ms); rate 40/80/120% dari ceiling protokol TERENDAH: image/track 25/50/74, page 17/34/52; unit = iterasi skenario/s | `design/CALIBRATION.md` seluruhnya; `ape_env.txt` APE_MOT_RATES_* persis | Persis; `overload_saturates`: image/track=graphql (62), page=rest (43) | CONFIRMED |
| 2.9 | B.7.4/B.8 — 1 warmup/blok (dibuang), 30 run terukur/cell, 90 s/run, seed 42, serial ketat (1 lock, 1 server, 1 k6 blocking), blok terandomisasi | `ape_env.txt` (APE_N_WARMUP=1, APE_N_MEASURED=30, APE_RUN_DURATION=90s, APE_SEED=42); `run_experiment.py::run_block` (warmup lalu measured, `acquire_orchestrator_lock`) | Persis. Catatan: default `config.py` = 20s tapi env run = 90s — figur harus pakai 90 s (nilai env snapshot) | CONFIRMED |
| 2.10 | B.1.2/A.5.2 — skema & jumlah: sequence 7 / image 2.846 / track 5.429 / detection 104.767 / class 10 | `design/mot_profile.json` counts; DDL di `~/training/build_detection_db.py:55-104` | Persis. **KOREKSI penting untuk ERD: TIDAK ADA tabel `trajectory`** — trajectory adalah turunan (window ±W atas detection JOIN image). Entitas riil: sequence, image, track, detection, class. `detection.track_id` nullable (di data: 0 baris NULL) | CORRECTED |
| 2.11 | B.1.3 — tier: density low ≤4 / medium 5–53 / high ≥54 (det@conf.25); window W∈{2,8,23} (5/17/47 titik); page K∈{1,5,10}; filter class_id=4 "car", min_conf 0.5 | `mot_profile.json` (low [1,4] n=579, medium [5,53] n=1555, high [54,134] n=712; eligible tracks 2806/1385/563) | Persis | CONFIRMED |
| 2.12 | B.9.3 — header X-Process-Time ada di kedua server tapi TIDAK dipanen ke results.csv Study B | `core/timing.py` (middleware terpasang dua sisi); header results.csv mot-scenarios-core: tidak ada kolom xproc | Benar — figur aliran metrik lama (fig_14) menyiratkan k6 memakai header ini; harus dikoreksi | CONFIRMED |
| 2.13 | B.10 — tabel beda dua sumber data (lan vs constrained, kalibrasi vs fixed 10 req/s, workload_mot.js vs workload.js, CPU valid vs invalid, snapshot ada vs tidak) | `phase2-core-real/run_plan.csv` (network=constrained, concurrency=10), `env_snapshot/` hanya ada di mot-scenarios-core | Persis | CONFIRMED |

## 3. Klaim yang menjadi dasar figur hasil (chartable vs menunggu)

| # | Klaim outline | Verifikasi terhadap CSV | Verdict |
|---|---|---|---|
| 3.1 | C.8 — cache_hit_rate: zipfian ~0.37–0.43, uniform ~0.02–0.06, unique ~0 | Dihitung ulang dari `phase2-core-real/results.csv`: median per (caching=on, pattern): zipfian 0.400–0.403, uniform 0.039–0.041, unique 0.000 (REST dan GraphQL setara) | CONFIRMED |
| 3.2 | C.4 — REST lebih cepat di 12/12 cell, δ=−1.0 (large), lat_p50 28–29 vs 32–35 ms | `phase2_analysis_report.txt`: 12/12 signifikan Holm, δ=−1.000 semua cell, median persis pada rentang itu | CONFIRMED |
| 3.3 | C.4 — throughput terpaku di target 10 rps (open loop) — interpretasi "keduanya sanggup", bukan "kapasitas sama" | CSV: throughput_rps ≈ 9.9998–10.008 di semua baris yang dicek | CONFIRMED |
| 3.4 | C.8 — hit-rate unique nonzero floor formula; APQ registrations | Kolom `apq_registrations` ada; unique hit = 0.000 di data ini | CONFIRMED |
| 3.5 | C.6 — variabel pembanding RQ2 = `page_latency_med` (bukan lat_p*); `round_trip_count` ∈ {1,2,5,10} | Header results.csv mot-scenarios-core memuat `page_latency_med`, `round_trip_count`; semantik di `workload_mot.js` | CONFIRMED (menunggu data lengkap untuk di-chart) |
| 3.6 | C.7 — 30 baris dropped>0 sejauh ini, semua M1-GraphQL overload | Tidak dihitung ulang penuh (CSV live, dibaca minimal); aturan "jangan pool r120_overload" tetap dipegang di skrip Step-3 | PLAUSIBLE — cek ulang saat run selesai |
| 3.7 | C.10 — figur RQ3 yang ada: `fig_descriptive_boxplots/crossover_surface/coupling_entropy_hitrate` di `phase2-core-real/analysis/` | Ketiga PNG ada; catatan outline bahwa coupling-entropy konstanta entropi (kandidat drop) masuk akal — entropy=medium konstan di 720 baris | CONFIRMED |
| 3.8 | C.6.5 — `results/phase2-figures/` (5 PNG dari `visualize_phase2_full.py`) = data 2–8 sesi paralel, korroborasi kualitatif saja | 5 PNG ada; STUDY_COMPARISON §3 mendokumentasikan paralelisme | CONFIRMED — jangan pernah tampilkan sebagai hasil utama |

## 4. Klaim outline yang SALAH / perlu koreksi

| # | Klaim | Masalah | Koreksi yang dipakai |
|---|---|---|---|
| 4.1 | (bukan dari outline, dari brief figur) ERD = "sequence/image/detection/track/**trajectory**" | Tidak ada tabel trajectory di DDL; outline sendiri benar (class(10)) | ERD digambar dengan 5 tabel riil: sequence, image, track, detection, class; trajectory dicatat sebagai konsep turunan (query window), bukan entitas |
| 4.2 | Outline header: "progress.log" di root results dir | File sebenarnya `results/mot-scenarios-core/logs/progress.log` | Path dikoreksi di semua rujukan |
| 4.3 | A.6.2 hit-rate "zipfian ~0.40 / uniform ~0.04 / unique 0.00" pada brief; outline C.8 "~0.37–0.43 / 0.02–0.06 / ~0" | Keduanya cocok data (median 0.40 / 0.04 / 0.00) | Caption figur memakai angka terukur dari CSV, n=30/cell/protokol |
| 4.4 | Kutipan buku: Sommerville / Fowler / Elmasri & Navathe diminta brief | TIDAK ada di `REFERENCES_BASIS.md` (bank punya: Larman #1, OMG UML 2.5.1 #2, RFC 9110 #5 / 9111 #6, GraphQL Spec #7, Apollo APQ #8) | Caption memakai OMG UML 2.5.1 (#2, sudah di bank) + tambahan Sommerville/Fowler/Elmasri ditandai [VERIFY EDITION] — peneliti harus menambahkan ke bank sebelum dipakai |
| 4.5 | Register lama menyebut ERD "Chen ER model" | Notasi yang dipakai fig_05 (dan figur baru) adalah crow's foot, bukan notasi Chen (Chen = diamond/oval) | Caption baru menyebut notasi crow's foot dengan rujukan teks basis data [VERIFY EDITION]; label "Chen" dihapus |

## 5. Konsekuensi untuk pembangunan figur

1. **Boleh dibangun sekarang**: 4 diagram UML/ERD (dari kode terverifikasi §2) +
   figur RQ3 caching (dari `phase2-core-real/results.csv`, §3.1–3.4).
2. **Harus menunggu** (`mot-scenarios-core` selesai ~2026-07-06): semua figur
   RQ1 (M1–M4 × density × rate) dan RQ2 (M5 window, M6 K, crossover Δ vs K,
   Δ vs round_trip_count) — disiapkan sebagai skrip parametrik (Step 3).
3. **Jangan pernah**: chart CPU/RSS dari phase2-core-real; pool r120_overload
   dengan r40/r80; tampilkan artefak DET/Phase-1/factorial-A sebagai metode
   berjalan; chart parsial mot-scenarios-core.
4. Terminologi figur mengikuti judul terkunci: **waktu respons**, **throughput**,
   **jumlah round-trip** (tanpa sinonim campuran).
