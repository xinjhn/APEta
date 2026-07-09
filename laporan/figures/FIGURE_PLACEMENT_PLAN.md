# FIGURE PLACEMENT PLAN — Bab I s.d. Bab V

Rencana penempatan gambar untuk `515_Laporan TA_[R].docx`. Urut per bab agar
bisa dikerjakan atas-ke-bawah di Word. Nomor gambar TIDAK ditulis tegas di
caption — pakai *Insert Caption* Word (SEQ field) supaya penomoran otomatis
konsisten dengan caption lain yang sudah berupa field.

Status:
- **READY** — file PNG final ada di `figures/export/`, tinggal paste.
- **RENDER** — sumber `.mmd`/`.puml` ada, perlu dirender dulu (mermaid.live /
  `mmdc`, atau PlantUML) ke PNG.
- **EMBEDDED** — sudah ada di dokumen, tidak perlu apa-apa.
- **REVIEW** — sudah ada di dokumen tapi kemungkinan stale, cek isinya.

Prioritas: ★★★ pembawa benang merah (wajib) · ★★ memperkuat argumen ·
★ opsional/lampiran.

---

## BAB I — Pendahuluan

### ☐ ★★ Alur besar penelitian APE
- **Anchor:** akhir I.1 Latar Belakang, setelah paragraf "…rekomendasi
  arsitektural bagi Enterprise AI Integrator…" (paragraf penutup latar belakang).
- **File:** `figures/src/fig_01_research_workflow_bpmn_style.mmd` — **RENDER**
- **Caption:** *Alur besar penelitian APE dari studi literatur, pengembangan
  instrumen eksperimen, pelaksanaan uji pendahuluan, audit metodologi,
  perancangan eksperimen utama, sampai analisis hasil. Sumber: diolah penulis;
  notasi proses mengacu pada BPMN 2.0.2.*

### ☐ ★★★ Konsep selection set GraphQL terhadap payload — **ORPHAN REF, WAJIB**
- **Anchor:** Bab I Latar Belakang — kalimat *"Konsep dasar selection set
  GraphQL terhadap bentuk payload yang dikembalikan ditunjukkan pada gambar
  berikut."* saat ini **menjanjikan gambar yang tidak ada**. Tempel tepat
  setelah kalimat itu (atau hapus kalimatnya bila memilih tidak memasang).
- **File:** `figures/src/fig_15_graphql_selection_set_payload.mmd` — **RENDER**
- **Caption:** *Konsep selection set GraphQL: klien mendeklarasikan field yang
  dibutuhkan dan server mengembalikan payload sesuai deklarasi tersebut.
  Sumber: diolah penulis berdasarkan spesifikasi GraphQL.*

### ☐ ★ Alur uji pendahuluan → eksperimen utama
- **Anchor:** Bab I Latar Belakang, setelah kalimat "…Temuan ini mendorong
  dilakukannya tahap kedua…" (alternatif: awal Bab III Penjelasan Penelitian).
- **File:** `figures/src/fig_02_pilot_to_main_experiment.mmd` — **RENDER**
- **Caption:** *Alur uji pendahuluan menuju eksperimen utama. Uji pendahuluan
  diposisikan sebagai validasi instrumen; eksperimen utama menambahkan kontrol
  caching, pola akses, entropi query, bobot payload, dan profil jaringan.
  Sumber: diolah penulis berdasarkan hasil audit implementasi APE.*

## BAB II — Tinjauan Pustaka

Semua gambar Bab II (II.1 arsitektur client-server, II.2 mekanisme REST vs
GraphQL, II.3 over/under-fetching, II.4 payload nested, II.5 pipeline YOLO26)
sudah **EMBEDDED**. Tidak ada tindakan. (Penomoran II.4 ganda akan beres saat
caption diseragamkan ke SEQ field + F9.)

## BAB III — Metodologi

### ☐ ★★★ Desain faktor grid inti — **ORPHAN REF, WAJIB**
- **Anchor:** III Perancangan Matriks Skenario — kalimat *"Desain faktor grid
  inti beserta nilai yang dikunci pada eksperimen utama digambarkan pada gambar
  berikut."* **menjanjikan gambar yang tidak ada.** Tempel tepat setelahnya,
  sebelum Tabel Matriks Skenario.
- **File:** `figures/src/fig_11_phase2_factor_grid.mmd` — **RENDER**
- **Caption:** *Desain faktor grid inti eksperimen utama: protokol × caching ×
  pola akses × bobot payload (24 blok), dengan entropi, densitas, jaringan, dan
  concurrency dikunci pada nilai inti. Sumber: diolah penulis.*

### ☐ ★★★ Activity alur eksekusi eksperimen (studi skenario MOT)
- **Anchor:** akhir sub-bab Perancangan Matriks Skenario, setelah tiga paragraf
  baru studi skenario MOT (M1–M6, kalibrasi r40/r80/r120) — memberi wajah pada
  studi yang baru saja ditambahkan ke Bab III.
- **File:** `figures/export/fig_19_activity_execution_flow.png` — **READY**
- **Caption:** *Alur eksekusi eksperimen: kalibrasi laju, pembangkitan run
  plan, eksekusi serial per blok (server → cache → jaringan → k6 → telemetri),
  hingga penulisan results.csv. Sumber: diolah penulis; notasi activity diagram
  mengacu pada UML 2.5.1.*

### ☐ ★★★ ERD korpus deteksi MOT — **dirujuk prosa, belum terpasang**
- **Anchor:** III Data Penelitian, setelah paragraf "…terdiri dari 7 sequence,
  2.846 image, 5.429 track, dan 104.767 detection." (Prosa Bab IV memanggilnya
  "Gambar III.4"; setelah terpasang di sini rujukan itu menjadi sah — cukup
  perbarui nomornya via cross-reference.)
- **File:** `figures/export/fig_20_erd_mot_schema.png` — **READY**
- **Caption:** *Entity Relationship Diagram korpus deteksi MOT
  (mot_detections.db): tabel sequence, image, detection, track, dan class
  beserta kardinalitasnya. Sumber: diolah penulis berdasarkan skema SQLite;
  notasi crow's foot mengacu pada Elmasri & Navathe.*

### ☐ ★★ Pipeline persiapan data VisDrone → YOLO → SQLite
- **Anchor:** III Data Penelitian, setelah paragraf "Struktur data inferensi
  yang dihasilkan oleh YOLO26…" (sebelum paragraf VisDrone-MOT vs DET).
- **File:** `figures/src/fig_04_data_preparation_pipeline.mmd` — **RENDER**
- **Caption:** *Pipeline persiapan data: dataset VisDrone-MOT diinferensikan
  YOLO26 hasil fine-tuning, di-tracking lintas frame, lalu disimpan sebagai
  corpus relasional SQLite yang dibaca kedua protokol. Sumber: diolah penulis.*

### ☐ ★ Pemetaan variabel bebas–kontrol–terikat
- **Anchor:** III Variabel Penelitian — dokumen sudah punya Gambar III.1
  "Variabel Penelitian" (**EMBEDDED**). Pasang fig_16 hanya bila gambar lama
  belum memuat pemisahan IV/DV/kontrol; kalau sudah, lewati.
- **File:** `figures/src/fig_16_variables_metrics_map.mmd` — **RENDER**

## BAB IV — Analisis & Perancangan APE

Sudah **EMBEDDED**: IV.1 arsitektur komponen, IV.2 SSD REST, IV.3 SSD GraphQL
POST, IV.4 SSD APQ, IV.5 cache hit/miss, IV.6 sequence alur data.

### ☐ ★★★ Aliran metrik eksperimen — **caption sudah ada, gambarnya belum**
- **Anchor:** Increment 5 — caption *"Aliran metrik eksperimen: k6 menghasilkan
  ringkasan latency/throughput per run…"* sudah ada di dokumen TANPA gambar di
  atasnya. Tempel gambar tepat di atas caption tersebut.
- **File:** `figures/src/fig_14_measurement_streams.mmd` — **RENDER**

### ☐ ★★★ Aktivitas orkestrasi eksperimen — **caption sudah ada, gambarnya belum**
- **Anchor:** Orkestrasi Matriks Eksperimen — caption *"Aktivitas orkestrasi
  eksperimen: pembacaan run plan, penyalaan server sesuai protokol…"* sudah ada
  TANPA gambar. Tempel di atas caption tersebut.
- **File:** `figures/src/fig_06_experiment_orchestration_activity.mmd` —
  **RENDER** *(alternatif cepat: pakai ulang `fig_19_activity_execution_flow.png`
  bila dirasa cukup mewakili — jangan dipasang dua kali di III dan IV; pilih
  satu tempat)*

### ☐ ★★ Sequence REST K round-trip vs GraphQL komposit (M5/M6)
- **Anchor:** IV — akhir sub-bab Sequence Diagram Alur Data (setelah paragraf
  "Pada sisi REST API, alur permintaan mengikuti rute statis…"), sebagai
  penjelas mekanisme yang hasilnya dibahas di RQ2 Bab V.
- **File:** `figures/export/fig_17_sequence_rest_vs_graphql_roundtrip.png` —
  **READY**
- **Caption:** *Perbandingan mekanisme K round-trip REST (masing-masing
  cacheable) dengan satu kueri komposit GraphQL untuk kebutuhan data yang sama.
  Sumber: diolah penulis; notasi sequence diagram mengacu pada UML 2.5.1.*

### ☐ ★★ Topologi deployment eksperimen (netns, pinning, systemd)
- **Anchor:** IV — setelah paragraf orkestrator ("…menulis hasil dan telemetry
  ke direktori results."), atau di Increment 5 setelah paragraf telemetri.
- **File:** `figures/export/fig_18_deployment_experiment_topology.png` — **READY**
- **Caption:** *Topologi deployment eksperimen: k6 di root namespace, server
  dan Varnish di network namespace terisolasi dengan emulasi netem satu hop
  veth, kuota CPU/memori via systemd scope, dan sampler telemetri pada core
  terpisah. Sumber: diolah penulis; notasi deployment mengacu pada UML 2.5.1.*

### ☐ ★ Profil distribusi densitas corpus
- **Anchor:** IV Profil Distribusi Dataset VisDrone, setelah Tabel IV.1
  (statistik deskriptif per citra).
- **File:** `training/mot_predictions_tracked_density.png` — **READY**
  *(verifikasi dulu bahwa PNG ini dihitung dari prediksi tracked yang sama
  dengan isi mot_detections.db; kandidat lain: `training/density_tier_counts.png`)*
- **Caption:** *Distribusi jumlah objek per citra pada corpus deteksi MOT
  beserta batas tier densitas (kuartil Q1 dan Q3). Sumber: diolah penulis dari
  mot_detections.db.*

## BAB V — Hasil dan Pembahasan

Sudah **EMBEDDED**: V.1 pipeline analisis. **REVIEW:** V.2 "crossover surface"
— gambar yang terpasang kemungkinan placeholder lama (register menandai figur
ini `later`); pastikan isinya diganti/diselaraskan dengan figur final di bawah.

Prosa hasil (RQ1/RQ2/RQ3) sudah merujuk seri figur berikut secara eksplisit.
Rekomendasi: pasang **varian r80** sebagai representatif sub-saturasi +
**r120_overload** untuk narasi kolaps; varian r40 cukup di Lampiran.

### ☐ ★★★ RQ1 — Latency M1–M4 (sub-saturasi)
- **Anchor:** paragraf "Hasil RQ1 … Selisih median GraphQL terhadap REST
  berkisar antara +51% hingga +141% pada laju r80…" — tempel setelah paragraf.
- **File:** `figures/export/fig_rq1_lat_p50_r80.png` — **READY**
  *(pendamping opsional: `fig_rq1_lat_p95_r80.png`)*
- **Caption:** *Median latency p50 REST vs GraphQL per skenario M1–M4 dan tier
  densitas pada laju r80 (n=30 run per sel, bar = median, whisker = IQR).
  Sumber: diolah penulis dari mot-scenarios-core/results.csv.*

### ☐ ★★★ RQ1 — Kolaps GraphQL pada overload
- **Anchor:** paragraf "Pada laju r120 yang dirancang sebagai kondisi
  overload…" — tempel setelahnya.
- **File:** `figures/export/fig_rq1_lat_p50_r120_overload.png` — **READY**
- **Caption:** *Median latency p50 pada laju r120 (overload): GraphQL mengalami
  saturasi antrean pada sel M1-high sementara REST tetap stabil. Baris overload
  dianalisis terpisah dari sel sub-saturasi. Sumber: diolah penulis dari
  mot-scenarios-core/results.csv.*

### ☐ ★★★ RQ1 — CPU server
- **Anchor:** paragraf "…Pembeda sumber daya yang konsisten pada seluruh laju
  adalah penggunaan CPU…" — tempel setelahnya.
- **File:** `figures/export/fig_rq1_cpu_r80.png` — **READY**
  *(pendamping opsional untuk memori: `fig_rq1_rss_r80.png`)*
- **Caption:** *Rata-rata utilisasi CPU server REST vs GraphQL per skenario
  pada laju r80. Sumber: diolah penulis dari mot-scenarios-core/results.csv.*

### ☐ ★★ RQ1 — Throughput pemenuhan laju target
- **Anchor:** paragraf yang sama (open-loop, throughput setara di sub-saturasi)
  — atau cukup di Lampiran sesuai register.
- **File:** `figures/export/fig_rq1_throughput_r80.png` — **READY**

### ☐ ★★★ RQ2 — Crossover jendela trajektori M5
- **Anchor:** paragraf "Hasil RQ2, bagian pertama (konsolidasi round-trip) …
  crossover yang jelas: pada jendela kecil w2…" — tempel setelahnya.
- **File:** `figures/export/fig_rq2_m5_window_r40.png` — **READY**
- **Caption:** *Page-latency M5 (track + trajectory) REST dua round-trip vs
  GraphQL satu kueri komposit per ukuran jendela (w2/w8/w23) pada laju r40:
  penghematan round-trip GraphQL hanya seimbang pada jendela kecil. Sumber:
  diolah penulis dari mot-scenarios-core/results.csv.*

### ☐ ★★★ RQ2 — Crossover paginasi M6 (figur kunci)
- **Anchor:** kalimat "Skenario paginasi M6 memperlihatkan tuning round-trip
  yang sama…" — tempel setelahnya.
- **File:** `figures/export/fig_rq2_m6_crossover_r40.png` — **READY**
- **Caption:** *Crossover M6: total page-latency K round-trip REST vs satu
  kueri komposit GraphQL terhadap ukuran halaman K (k1/k5/k10) pada laju r40;
  titik silang K*≈2 dan GraphQL unggul penuh pada K≥5. Sumber: diolah penulis
  dari mot-scenarios-core/results.csv.*

### ☐ ★★ RQ2 — Ringkasan Δ vs jumlah round-trip (M5+M6)
- **Anchor:** setelah figur M6, menutup bagian RQ2.
- **File:** `figures/export/fig_rq2_delta_rtc_r40.png` — **READY**
- **Caption:** *Selisih page-latency (GraphQL − REST) terhadap jumlah
  round-trip REST yang digantikan: tanda selisih berbalik antara 2 dan 5
  round-trip. Sumber: diolah penulis dari mot-scenarios-core/results.csv.*

### ☐ ★★★ RQ2/RQ3 — Cache-hit rate per pola akses
- **Anchor:** paragraf "Hasil RQ2, bagian kedua (caching…) … median cache-hit
  rate REST 0,43 dan GraphQL 0,42 praktis setara." — tempel setelahnya.
- **File:** `figures/export/fig_21_rq3_cache_hit_rate.png` — **READY**
- **Caption:** *Cache-hit rate per pola akses (zipfian/uniform/unique), protokol,
  dan bobot payload pada grid inti caching: APQ-over-GET menyetarakan
  cacheability GraphQL dengan REST. Sumber: diolah penulis dari
  phase2-core-real/results.csv.*

### ☐ ★★★ RQ3 — Efek caching terhadap latency (delta)
- **Anchor:** kalimat "…Manfaat caching bersifat asimetris dan lebih besar bagi
  GraphQL…" — tempel setelahnya. *(Sekaligus kandidat pengganti isi Gambar V.2
  "crossover surface" yang berstatus REVIEW.)*
- **File:** `figures/export/fig_22_rq3_latency_delta.png` — **READY**
- **Caption:** *Selisih median latency (cache on − cache off) per pola akses,
  protokol, dan bobot payload dengan interval kepercayaan bootstrap 95%:
  manfaat cache terkonsentrasi pada pola zipfian dan lebih besar pada GraphQL.
  Sumber: diolah penulis dari phase2-core-real/results.csv.*

---

## Ringkasan tindakan

| Kategori | Jumlah | Item |
|---|---|---|
| READY (tinggal paste) | 12 | fig_19, fig_20, fig_17, fig_18, 1 training PNG, fig_rq1×3(+1 ops), fig_rq2×3, fig_21, fig_22 |
| RENDER dulu (.mmd) | 6–7 | fig_01, fig_15 (**orphan ref**), fig_02, fig_11 (**orphan ref**), fig_04, fig_14, fig_06 |
| REVIEW isi lama | 1 | Gambar V.2 crossover surface (kemungkinan placeholder) |
| Lampiran (opsional) | ~12 | varian r40/r120 yang tidak dipakai di badan bab |

**Cara render .mmd:** buka https://mermaid.live → paste isi file → export PNG
(atau `npx -y @mermaid-js/mermaid-cli -i fig_xx.mmd -o fig_xx.png -s 3`).

**Dua orphan reference paling mendesak** (prosa menjanjikan gambar yang belum
ada): fig_15 di Bab I dan fig_11 di Bab III — pasang gambarnya, atau ubah
kalimat "ditunjukkan pada gambar berikut"-nya.
