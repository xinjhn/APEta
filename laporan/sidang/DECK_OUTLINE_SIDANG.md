# OUTLINE DECK SIDANG — Phase 1 (menunggu persetujuan)

Disusun: 2026-07-12. Semua fakta diekstrak dari file workspace; tidak ada angka
dari luar file. Format per slide: **Judul (kalimat klaim)** → isi → visual →
sumber. Catatan pembicara (Phase 2) akan memuat talking points + path sumber
per fakta, sesuai aturan traceability.

Deliverable Phase 2: **satu .pptx baru** — usulan
`laporan/sidang/Sidang_TA_APE_JeihanIlham_v2.pptx` (deck lama 33-slide tidak
ditimpa; 6 figur yang sudah ada di deck lama dipakai ulang, 10 figur kurasi
baru ditambahkan sesuai `laporan/sidang/figur/MANIFEST.md`).

**Palet:** 2 netral (abu gelap teks, abu muda latar aksen) + 1 aksen; warna
protokol dikunci mengikuti warna figur ekspor: **REST = biru, GraphQL =
merah/oranye** (konvensi eksplisit di MANIFEST.md: "biru = REST menang, merah =
GraphQL menang"). 16:9, satu font family, body ≥18pt.

**Deviasi sadar dari aturan ≤40 kata:** slide RQ (M5) dan hipotesis (M7–M8)
melebihi 40 kata karena aturan verbatim (hard rule 1 & 4 mengalahkan budget
kata); teks lain dipadatkan.

---

## BAGIAN A — MAIN DECK (37 slide, 30 menit)

### Babak 0 — Pembuka (2)

**M1. Judul & Identitas**
- Judul verbatim halaman sampul: "ANALISIS PERFORMA KOMUNIKASI DATA REST API
  DAN GRAPHQL DALAM PENYAJIAN DATA DETEKSI OBJEK MENGGUNAKAN YOLO"
  ⚠ **[VERIFY: varian judul — sampul menulis "…YOLO"; lembar pengesahan &
  pernyataan penulis menulis "…YOLO26". Pilih satu.]**
- Jeihan Ilham Kusumawardhana — 221524042; Program Sarjana Terapan Teknik
  Informatika, JTK, Politeknik Negeri Bandung, 2026. Tipe TA: Riset
  (Experiment tools).
- Pembimbing: **[VERIFY: nama & NIP Pembimbing I dan II — placeholder template
  di docx, tidak ada di file workspace mana pun]**
- SRC: `laporan/515_Laporan TA_[R].docx` halaman sampul & pengesahan.

**M2. Agenda** — 6 butir alur (latar → RQ/hipotesis → metodologi → hasil per
RQ → validitas → kesimpulan). SRC: struktur docx Bab I–VII.

### Babak 1 — Latar & Masalah (4)

**M3. "Nilai model deteksi tidak berhenti di inferensi — hasilnya harus
disajikan lewat API."**
- Output YOLO = metadata nested (class, confidence, bounding box, track), bukan
  tabel datar; penyajian lambat menggerus manfaat real-time.
- SRC: docx Bab I Latar Belakang (¶1–2); sitasi Redmon et al. 2016, Sapkota &
  Karkee 2025, Nieto et al. 2021.

**M4. "Klien heterogen memaksa pilihan: over-/under-fetching REST vs biaya
eksekusi GraphQL."**
- Mitra industri PT Ganesha Digital Solusi: dashboard web butuh data utuh;
  mobile/IoT butuh ringkasan. REST kaku → over-/under-fetching; GraphQL
  declarative tapi default POST tidak cacheable.
- SRC: docx Bab I ¶3–4; Brito et al. 2019; Hartig & Pérez 2018.

**M5. Rumusan masalah: tiga celah** (parafrase pendek di slide, teks verbatim
3 butir di notes)
- (1) belum ada bukti empiris perbandingan *fair* (sumber data, jalur akses,
  caching setara); (2) ketidakpastian pengaruh caching/pola akses/entropi —
  GraphQL default tidak cacheable HTTP; (3) titik trade-off payload ×
  cache-hit × resource belum teridentifikasi.
- SRC: docx Bab I §Rumusan Masalah (3 butir).

**M6. Research Question (verbatim, 3 butir)**
- RQ1, RQ2, RQ3 persis dari docx §I.3.1 (response time, throughput, sumber
  daya; caching/pola akses/entropi/bobot payload/konsolidasi round-trip; titik
  crossover + matriks rekomendasi arsitektural).
- SRC: docx Bab I §Research Question (kalimat RQ1–RQ3 verbatim).

### Babak 2 — Scope & Hipotesis (3)

**M7. "Perubahan scope terdokumentasi: uji pendahuluan in-memory DET →
eksperimen utama MOT relasional."**
- Batasan §Sumber Data (verbatim inti): SQLite `mot_detections.db` + shared
  DAL "menggantikan rancangan uji pendahuluan yang sebelumnya tidak menggunakan
  basis data (in-memory data pool), karena rancangan tersebut tidak dapat
  merepresentasikan kondisi caching maupun pola akses data yang realistis".
- VisDrone-MOT dipilih (bukan DET) karena anotasi track lintas frame membentuk
  payload heavy natural. Batasan lain: bukan evaluasi mAP; hanya REST &
  GraphQL; read-only tanpa autentikasi.
- Framing: keputusan metodologis yang terdokumentasi (audit migrasi:
  `laporan/phase2_migration/DRAFT_AUDIT_PHASE2.md`).
- SRC: docx Bab I §Batasan (butir 1–5); docx Bab III (VisDrone-MOT vs DET);
  `APEta/design/STUDY_COMPARISON.md` §4.

**M8. Hipotesis H1–H2 (verbatim)** + kalimat framing verbatim: empat hipotesis
substantif; per sel diuji Mann-Whitney U dengan H0 "tidak terdapat perbedaan
kinerja yang signifikan" vs Ha.
- SRC: docx Bab I §I.3.2 Hipotesa (kalimat framing + H1 + H2).
- ⚠ Catatan: prompt tugas menyebut "3 pasangan H0/H1", tetapi tesis memuat
  **empat** hipotesis H1–H4 — file menang.

**M9. Hipotesis H3–H4 (verbatim)**
- SRC: docx Bab I §I.3.2 (H3 + H4).

### Babak 3 — Metodologi (8)

**M10. "Dua tahap: uji pendahuluan mengungkap confounder → eksperimen utama
memperbaikinya."**
- Tahap 1 in-memory: (a) tidak merepresentasikan akses realistis, (b) caching
  belum dikontrol → dasar redesign. Pilot = kalibrasi instrumen, bukan hasil.
- SRC: docx Bab I ¶ terakhir Latar Belakang; docx Bab V §Hasil Uji Pendahuluan.

**M11. Pipeline data (diagram 1 baris):** VisDrone-MOT → fine-tune YOLO26n →
inferensi + tracking ByteTrack (offline, sekali) → SQLite `mot_detections.db`
(7 sequence · 2.846 image · 5.429 track · 104.767 detection; tier densitas
kuartil low/medium/high).
- Semua parameter → lampiran L2–L6. Diagram dibangun dari shape pptx.
- SRC: docx Bab I §Dukungan Data + Bab III §Data Penelitian;
  `training/build_detection_db.py` (docstring "CORPUS DEFINITION");
  verifikasi langsung DB (query count, 2026-07-12).

**M12. Arsitektur sistem (figur 02 `fig_18_deployment_experiment_topology`):**
k6 open-loop (core 8–15) → netns `ape-origin` + netem veth → [Varnish] →
REST **atau** GraphQL (bergantian, port 8000, single worker, core 0–7,
CPUQuota 400% / MemoryMax 2048M) → shared `DetectionDAL` → SQLite.
- SRC: figur + caption `laporan/figures/FIGURE_CAPTIONS.md` §fig_18;
  `APEta/design/CALIBRATION.md` §Setup; docx Bab IV §Arsitektur.

**M13. "Fairness dibuktikan, bukan diasumsikan" (figur 01
`fig_17_sequence_rest_vs_graphql_roundtrip`):**
- Shared DAL (nol SQL di lapisan penyajian), header cache dari satu fungsi,
  JSON compact + snake_case dua sisi; acceptance test A1 (paritas deep-equal),
  A2 (diff SQL via APE_LOG_SQL), A3 (fairness cache Varnish nyata) — semuanya
  lolos.
- SRC: docx Bab IV §IV.5 (A1–A3); `APEta/design/PARITY_REPORT_MOT.md`
  (18 passed / 2 skipped).

**M14. "APQ-over-GET membuat GraphQL cacheable setara REST."**
- POST /graphql tidak cacheable → klien kirim sha256(query) via GET; registrasi
  sekali (PERSISTED_QUERY_NOT_FOUND); Varnish hanya membaca Cache-Control dari
  backend (protokol-agnostik); endpoint random dipaksa no-store dua sisi.
- SRC: docx Bab III (konfigurasi caching setara) + Bab IV Increment 3;
  `APEta/cache/varnish.vcl`.

**M15. Grid eksperimen: dua korpus saling melengkapi.**
- Studi skenario MOT M1–M6: 2 protokol × 6 skenario × 3 tier × 3 laju × 30 run
  = **3.240 run terukur** (54 sel × 2; RQ1 + RQ2 round-trip).
- Grid inti caching: 2 × 2 caching × 3 pola akses × 2 bobot payload = 24 blok
  × 30 = **720 run** (RQ2 caching + RQ3).
- Robustness: factorial-A 48 sel × 30 × 2 = 2.880 run.
- SRC: docx Bab III Tabel III.6–III.8 + sumber tabel L.1;
  `APEta/design/STUDY_COMPARISON.md` §1.

**M16. "Laju dikalibrasi ke titik jenuh; overload dianalisis terpisah."**
- Probe ceiling per keluarga (heaviest tier): image/track 62 iter/s (GraphQL),
  page 43 (REST) → r40/r80/r120_overload = 25/50/74 dan 17/34/52 iter/s.
- Open-loop constant-arrival-rate (anti coordinated omission); 1 warm-up
  dibuang + 30 run terukur 90 s per sel; seed 42.
- SRC: `APEta/design/CALIBRATION.md`; docx Bab III §Pelaksanaan (Tene 2015;
  Crankshaw et al.).

**M17. Analisis: uji dua lapis.**
- Shapiro-Wilk (non-normal) → Mann-Whitney U per sel + effect size rank-biserial
  ≡ Cliff's δ (arah: δ<0 = REST unggul) → koreksi Holm per keluarga metrik.
- Interpretasi ganda: bermakna hanya jika p<0,05 **dan** |r| ≥ medium; n=30/sel
  membuat hampir semua p signifikan → keputusan bertumpu effect size.
- SRC: docx Bab III §Analisis Data + §Formulasi MWU + §Interpretasi; sumber
  Tabel L.1 ("Uji Mann-Whitney U, ukuran efek Cliff's δ, koreksi Holm").

### Babak 4 — Hasil RQ1: REST unggul default (4)

**M18. "REST unggul di seluruh 36/36 sel M1–M4 — pemisahan sempurna δ = −1,00."**
(figur 03 `fig_rq1_lat_p50_r80`)
- Selisih GraphQL +51% s.d. +141% pada r80; contoh M1|high r80: REST 8,70 ms
  vs GraphQL 20,94 ms. Mendukung H1.
- SRC: docx Bab V §Hasil RQ1; Tabel L.1; MANIFEST butir 03.

**M19. "Densitas objek — bukan laju kedatangan — yang memperlebar selisih."**
(figur 04 `fx_mot_maineffect_lat_p50`)
- GraphQL 12,3 → 15,5 ms (low→high) vs REST 7,2 → 8,2 ms; laju sub-saturasi
  hampir tak menggeser selisih → biaya per-objek-terserialisasi.
- SRC: docx Bab V §Hasil RQ1 (efek marginal); `figures/export/effects_stats.json`.

**M20. "Keunggulan latensi REST tidak dibayar di tempat lain: GraphQL memakai
CPU jauh lebih besar."** (figur 05 `fig_rq1_cpu_r80`)
- M1|high r80: CPU REST 17,96% vs GraphQL 79,45% (≈4,4×); sumber biaya:
  parsing kueri, validasi skema, resolver traversal. Tervalidasi ulang di grid
  caching (Tabel L.2, re-run phase2-core-clean).
- SRC: docx Bab V §Hasil RQ1 (CPU); docx §Ancaman Validitas (L.2); MANIFEST 05.

**M21. "Pada overload, GraphQL kolaps lebih dulu."** (figur 06
`fig_rq1_lat_p50_r120_overload`)
- r120: M1|high GraphQL 6.725,32 ms vs REST 8,64 ms (dua orde besaran); baris
  overload tidak pernah digabung dengan r40/r80.
- SRC: docx Bab V §Hasil RQ1 (overload); MANIFEST 06.

### Babak 5 — Dua klaim populer yang tidak terbukti (2)

**M22. "Anti-over-fetching GraphQL tidak terbukti pada API yang dirancang
setara."** (figur 11 `fx_mot_overfetch`)
- Rasio payload GraphQL/REST median ≈1,04 (terburuk 1,22, M4 low; 17 sel tak
  terpisah statistik); factorial-A: selisih ≈ +30 byte amplop `{"data":…}`,
  REST lebih kecil di 46/48 sel.
- SRC: docx Bab V §Hasil RQ1 (payload); MANIFEST 11.

**M23. "Signifikan secara statistik ≠ bermakna praktis: selisih throughput
<0,03%."** (figur 12 `fx_mot_decoupling`)
- Open-loop: kedua protokol mengikuti laju target (M1|high r80: 50,01 vs
  50,00 req/s); δ latensi terkunci −1,00 pada 39 sel round-trip sebanding —
  alasan memakai Cliff's δ, bukan p-value semata.
- SRC: docx Bab V §Hasil RQ1 (throughput); MANIFEST 12.

### Babak 6 — RQ2: batas & mekanisme crossover (puncak narasi, 4)

**M24. "Menghemat satu round-trip belum membalik keadaan (M5)."** (figur 07
`fig_rq2_m5_window_r40`)
- w2: GraphQL 14,73 ms ≈ REST 14,79 ms (seri; satu-satunya sel imbang sejati:
  M5|w2|r40, δ +0,32, selisih median 0,1 ms); w23: GraphQL 20,07 ms vs REST
  15,67 ms — biaya resolusi melampaui penghematan.
- SRC: docx Bab V §Hasil RQ2 bagian pertama; `figures/export/rq2_stats.json`.

**M25. ★ "Pemenang berbalik di fan-out: titik impas K* ≈ 2; K ≥ 5 GraphQL
menang penuh (M6)."** (figur 08 `fig_rq2_m6_crossover_r40`; **region crossover
ditandai eksplisit** — anotasi K*≈2 di antara K=1 dan K=5)
- K=1: REST 7,75 vs GraphQL 14,33 ms; K=5: 36,57 vs 16,88; K=10: 75,13 vs
  19,86 ms. REST tumbuh ~linear terhadap K; GraphQL landai.
- SRC: docx Bab V §Hasil RQ2 (kuantifikasi crossover);
  `rq2_stats.json` (k_star = 2.0).

**M26. "Mekanismenya ekonomi round-trip — bukan GraphQL menjadi lebih cepat."**
(figur 09 `fx_mot_mechanism_roundtrip`)
- REST membayar K perjalanan (M5: 2; M6: 1/5/10), GraphQL selalu 1;
  keunggulan fan-out tinggi bersumber dari penghematan round-trip.
- SRC: docx Bab V §Hasil RQ2; `effects_stats.json` (fx_mot_mechanism_roundtrip).

**M27. "Satu peta merangkum semua sel M5–M6."** (figur 10
`fx_mot_delta_heatmap_page`)
- Biru = REST menang, merah = GraphQL; hanya M6 K≥5 merah penuh (δ +1,00 di
  ketiga laju); M5|w2|r40 satu-satunya sel imbang.
- SRC: `effects_stats.json` (fx_mot_delta_heatmap_page); docx Bab V.

### Babak 7 — RQ3: caching (3)

**M28. "Lapisan cache adil: hit rate ditentukan pola akses, bukan protokol."**
(figur 13 `fig_21_rq3_cache_hit_rate`)
- Zipfian light: REST 0,43 vs GraphQL 0,42; heavy ~0,37; uniform 0,02–0,06;
  unique 0,00. δ hit-rate ≈ 0 → bukti empiris fairness N4.
- SRC: docx Bab V §Hasil RQ2 bagian kedua;
  `figures/export/rq3_caching_figures_stats.json`.

**M29. "Manfaat caching asimetris — lebih besar bagi GraphQL — dan bersyarat
pola akses berulang."** (figur 14 `fig_22_rq3_latency_delta`)
- Zipfian light: GraphQL −3,09 ms (34,91→31,82) vs REST −0,41 ms (28,45→28,04);
  uniform: overhead proxy +0,68 ms (REST light). H2 didukung sebagian.
- SRC: docx Bab V §Hasil RQ2 bagian kedua + §Pembahasan RQ3; rq3 stats json.

**M30. "Tidak ada kombinasi caching × pola akses × payload yang membalik
pemenang latensi."** (figur 15 `fx_cache_delta_heatmap`)
- REST δ = −1,00 di 12/12 blok; δ hit-rate −0,22…+0,13.
- SRC: docx Bab V (rangkuman grid caching); `effects_stats.json` /
  MANIFEST 15.

### Babak 8 — Robustness + Validitas (3)

**M31. "Arah temuan tidak pernah berbalik oleh beban: 48/48 sel, konkurensi
1–100."** (figur 16 `fig_factA_load_invariance`)
- Factorial-A (2.880 run): |δ| lat_p95 = 1,00 di seluruh 48 sel; besaran
  2,2×–7,1× (median 2,7×).
- SRC: docx Bab V (studi faktorial tambahan); `APEta/MORNING_RUN_REPORT.md` §3b.

**M32. "Dua insiden ditemukan, diisolasi, dan diperbaiki — bukti kontrol
kualitas data." (disclosure, frame = rigor)**
- run-sesi-1: 345.879 error serialisasi in-band GraphQL (HTTP 200 → tak
  terlihat error_rate) → sesi DIDEMOSI, diganti factorial-A yang bersih; k6
  body-check "no graphql errors" ditambahkan permanen.
- Grid caching phase2: 92,6% baris phase2 lain terkontaminasi eksekusi paralel
  (2–8 sesi) → RQ3 memakai HANYA phase2-core-real (720 run, serial penuh).
- Telemetri CPU/RSS phase2-core-real invalid (sampler memantau PID pembungkus)
  → diperbaiki sebelum studi MOT; re-run phase2-core-clean (720 run) mereplikasi
  δ latensi −1,00 dgn pergeseran median ≤0,25 ms → CPU/RSS valid di Tabel L.2.
- SRC: `APEta/design/STUDY_COMPARISON.md` §3/§5; `APEta/MORNING_RUN_REPORT.md`;
  docx Bab V §Ancaman Validitas (butir telemetri).

**M33. Ancaman validitas lain (jujur, ringkas).**
- netem = emulasi (bukan WAN); konstruk cache-hit = X-Cache Varnish; 1 mesin,
  1 corpus (7 sequence efektif), FastAPI+Strawberry saja; profil lan (MOT) vs
  constrained (caching) → tidak dibandingkan lintas korpus; X-Process-Time
  tidak dipanen.
- SRC: docx Bab V §Ancaman terhadap Validitas (6 butir).

### Babak 9 — Kesimpulan & Penutup (4)

**M34. Kesimpulan RQ1.** REST konsisten lebih rendah median latency + CPU jauh
lebih kecil di seluruh M1–M4; selisih melebar dgn densitas; CPU ≈4× di sel
terpadat; overload menegaskan. **H1 didukung.**
- SRC: docx Bab VII Kesimpulan ¶RQ1.

**M35. Kesimpulan RQ2.** Konsolidasi round-trip termonetisasi hanya bila biaya
resolusi < penghematan RT; pada LAN teremulasi (≈5 ms) crossover cepat
tercapai; keunggulan GraphQL kondisional pada ukuran payload & latensi
jaringan.
- SRC: docx Bab VII ¶RQ2.

**M36. Kesimpulan RQ3 + kontribusi.** Caching mempersempit, tidak menghapus;
APQ-over-GET menyetarakan cacheability (**H2 didukung sebagian**; H3 konsisten
mekanistis); manfaat asimetris pro-GraphQL. Kontribusi utama: metodologi
benchmark fair + instrumen APE replikabel; hasil scoped, bukan klaim universal.
⚠ Vonis H4 di slide: **[VERIFY: vonis H4 tidak eksplisit di Bab V/VII docx —
opsi: tambah dari review F2 ("didukung sebagian dan dipertajam") atau tunggu
revisi docx]**
- SRC: docx Bab VII ¶RQ3 + ¶penutup; `laporan/REVIEW_MENYELURUH_TESIS.md` §7.1/F2.

**M37. Saran & penutup (Q&A).** WAN nyata; autentikasi; sub-studi batching
N+1 (APE_GRAPHQL_BATCHING); replikasi corpus lain; keberlanjutan: paket
replikasi + dashboard + evaluasi rilis corpus. Terima kasih.
- SRC: docx Bab VII §Saran + §Rencana Keberlanjutan.

---

## BAGIAN B — LAMPIRAN (±31 slide, grup berjudul)

### Grup L-A: Training & Model (3)

**L1. Konfigurasi fine-tuning lengkap (Tabel III.2 verbatim).**
Fine-tuning dari bobot COCO; YOLO26n; imgsz 1280; freeze None; SGD eksplisit
lr0=0,01 momentum=0,937; epochs 200 (plafon)/patience 15; batch 4 (T4 16GB,
amp); seed 42, deterministic False. Kriteria penerimaan dua lapis: konvergensi
early-stopping + kecukupan densitas keluaran.
- Split dataset: protokol resmi VisDrone-DET train 6.471 / val 548
  (`visdrone_official.yaml`); run sebelumnya memakai split internal 90/10 dari
  train (`visdrone.yaml`).
- ⚠ **[VERIFY: jumlah citra train efektif untuk run yang menghasilkan
  checkpoint korpus — run2 memakai split 90/10 (jumlah persis tidak tercatat
  di file lokal); run3 resmi 6.471 (log scan "6448 images, 23 backgrounds").]**
- ⚠ **[VERIFY: checkpoint yang menghasilkan korpus — default
  `infer_mot_track.py` = `yolo26n_t4_run2/weights/best.pt`
  (MOT_INFERENCE_GUIDE.md), tetapi `mot_detections.db` dinyatakan frozen
  sebelum run3; tidak ada manifest inference yang mengunci bobot+md5.]**
- SRC: docx Bab III Tabel III.2; `training/visdrone.yaml`,
  `training/visdrone_official.yaml`,
  `training/runs/detect/visdrone_finetune/*/args.yaml`,
  `training/KAGGLE_RUN3.md`, `training/MOT_INFERENCE_GUIDE.md`.

**L2. Pilot optimizer (kronologi):** optimizer="auto" memilih MuSGD → 1,2
s/iterasi (~4× lambat, GPU idle); eliminasi penyebab sistem satu-per-satu; A/B
satu-variabel → SGD eksplisit, 3,6–4,1 it/s (~28 jam plafon 200 epoch).
- SRC: docx Bab III (¶ pilot optimizer);
  `laporan/reproducibility/PILOT_TRAINING_YOLO26.md`;
  `training/pilots/2026-07-07_optimizer_pace/`.

**L3. Deviasi Kaggle run3 (ledger):** batch 8 hanya jika T4×2 (aktual: device
'0' tunggal → batch 4 = nol deviasi), workers 4, time=10.0 h/sesi; mirror val
defect 150/548 → val sendiri; `mot_detections.db` FROZEN — training ini tidak
meregenerasi korpus.
- SRC: `training/KAGGLE_RUN3.md`; `training/runs/.../yolo26n_t4_run3_official/args.yaml`.

### Grup L-B: Dataset & Korpus (3)

**L4. Statistik korpus** — 7 sequence, 2.846 image, 5.429 track, 104.767
detection (diverifikasi query langsung DB); objek/citra: min 1, maks 134, mean
36,53, median 36,0, SD 32,31, Q1 5, Q3 54; tier: low 579 (20,3%), medium 1.555
(54,6%), high 712 (25,0%); kelas top-5: pedestrian 37.166 (35,5%), car 29.609
(28,3%), people 13.254 (12,7%), motor 10.445 (10,0%), bicycle 5.545 (5,3%).
- SRC: docx Bab I §Dukungan Data, Bab III Tabel densitas, Bab IV Tabel
  IV.1–IV.2; verifikasi `training/mot_detections.db` (0 baris track_id NULL).

**L5. Skema korpus / ERD** (figur `fig_20_erd_mot_schema`) + definisi korpus
verbatim build script: simpan conf ≥ 0,001 (ambang = knob query-time); tier
densitas dihitung pada conf ≥ 0,25; track→class = majority vote (tie: class_id
terkecil); kunci track global (sequence_name, target_id).
- SRC: `training/build_detection_db.py` (docstring + SCHEMA);
  `laporan/figures/FIGURE_CAPTIONS.md` §fig_20; `APEta/design/mot_profile.json`.

**L6. Parameter ByteTrack & asal track_id (item yang sering ditanya).**
- Tracker: **Ultralytics ByteTrack** (bukan join ground-truth) —
  `infer_mot_track.py`: "self-consistent track IDs from the model itself,
  rather than stitching GT tracks"; default conf 0,25, track_high_thresh 0,5,
  iou 0,7, tracker bytetrack, imgsz 1280; korpus dari output
  `mot_val_predictions_tracked_conf001`.
- Data aktual: 104.767/104.767 deteksi ber-track (0 NULL — skema mengizinkan
  NULL untuk kotak tak ter-track).
- SRC: `training/infer_mot_track.py` (docstring + defaults),
  `training/build_detection_db.py` ("CORPUS DEFINITION"), verifikasi DB.

### Grup L-C: Lingkungan & Beban (5)

**L7. Perangkat keras & lunak (Tabel III.2–III.4 docx).** AMD EPYC 7302 KVM 32
vCPU (pin server 0–7, k6 8–15, sampler 31); RAM 64 GB + swap 8 GB; T4 16GB
(luring, mesin terpisah); NVMe 512 GB; Ubuntu kernel 6.8.0-124-generic; Python
3.12.3; FastAPI 0.137.2; Strawberry 0.317.2; Grafana k6 2.0.0; psutil 7.2.2.
- SRC: docx Bab III §Perangkat Pendukung.

**L8. Isolasi resource:** systemd-run scope CPUQuota 400% / MemoryMax 2048M;
taskset; server bergantian port 8000, tidak pernah co-resident; urutan blok
diacak seed 42.
- SRC: `APEta/design/CALIBRATION.md` §Setup; docx Bab III §Mitigasi; Cuplikan
  Kode IV.9 (shuffle seed).

**L9. Profil netem & topologi:** lan = delay 5 ms ± 1 ms (normal) rate
100 Mbit; constrained = delay 25 ms ± 5 ms rate 10 Mbit (RTT ≈ 50 ms); netem
hanya di veth host-side (1 hop klien↔edge; hop Varnish↔backend tak tersentuh —
perbaikan dari artefak double-delay loopback yang terukur MISS 2×→1×).
- SRC: `APEta/tools/netns_topology.sh` (apply_netem); `APEta/tools/netem.sh`
  (header); docx Bab I §Batasan (lan/constrained).

**L10. Konfigurasi Varnish (varnish.vcl):** backend 127.0.0.1:8000; hanya GET
cacheable (POST pass); vcl_builtin_backend_response dipanggil eksplisit (bug
no-store tertelan — ditemukan saat verifikasi Phase 2a); X-Cache HIT/MISS untuk
A3.
- SRC: `APEta/cache/varnish.vcl` (komentar in-file).

**L11. k6 workload & definisi skenario:** executor constant-arrival-rate
(rate = target, bukan VU); summaryTrendStats p50/p95/p99; skenario M1–M6
dgn kontrak query/endpoint (M1 full, M2 sparse fields, M3 filter class_id=4
& min_confidence=0,5, M4 agregasi class_counts, M5 track→trajectory window,
M6 tracks(ids) K=1/5/10); pola akses unique/uniform/zipfian; payload
light/heavy; rates via env APE_MOT_RATES_*.
- SRC: docx Cuplikan Kode IV.8; `APEta/k6/workload_mot.js`, `workload.js`;
  `APEta/design/SCENARIO_DESIGN.md` §4 (konstanta filter, ukuran payload
  0,3/3,9/7,2 KB; trajectory ≈100 B/titik).

### Grup L-D: Grid & Kalibrasi (3)

**L12. Grid inti caching penuh (Tabel III.6):** 24 blok = 2×2×3×2; nilai
terkunci: entropi sedang, densitas sedang, network constrained, 10 rps;
24 × 31 (1 warm-up + 30) = 744 eksekusi.
- SRC: docx Bab III Tabel III.6 + ¶ pengulangan eksekusi.

**L13. Matriks M1–M6 rinci (Tabel III.7/III.8):** tier & laju per keluarga —
M1–M4 densitas 25/50/74 rps; M5 window w2/w8/w23 (5/17/47 titik; pool 2.806/
1.385/563 track) 25/50/74; M6 halaman k1/k5/k10 17/34/52; 54 sel × 2 × 30 =
3.240.
- SRC: docx Tabel III.7–III.8; `APEta/design/SCENARIO_DESIGN.md` §3.

**L14. Kalibrasi ceiling (tabel probe):** aturan saturasi (dropped>0 ∨ err>1%
∨ p95 > max(5×baseline, 150 ms)); ceiling REST/GraphQL per keluarga
(100/62, 100/62, 43/62); GraphQL ~62 iter/s di ketiga keluarga
(framework-bound); REST 43 halaman/s di M6-k10 (≈430 call/s); kolom
overload_saturates.
- SRC: `APEta/design/CALIBRATION.md` (tabel probe + observasi + methods note).

### Grup L-E: Tabel Statistik per RQ (5)

**L15. RQ1 — Tabel L.1 subset M1–M4** (per sel: median REST/GraphQL, Cliff's
δ, magnitudo, p Holm; contoh M1|low|r40 lat_p50 7,63 vs 12,86, δ −1,00,
p<0,001) + rasio p95 per skenario (M1 ≈2,0×, M2 ≈1,7×, M3 ≈1,9×, M4 ≈1,5×;
CPU 34/36, RSS 31/36 pro-REST).
- SRC: docx Lampiran 4 Tabel L.1; `APEta/MORNING_RUN_REPORT.md` §3a
  (headline); results/mot-scenarios-core/analysis (mot_comparisons.csv, di VM;
  salinan angka di docx).

**L16. RQ1 — Tabel V.1 (tier tinggi r80):** M1 8,70/20,94 ms CPU 18,0/79,5%;
M2 8,22/15,57, 15,4/54,0; M3 7,67/15,21, 12,5/51,9; M4 7,82/11,78, 13,4/34,8.
- SRC: docx Bab V Tabel V.1.

**L17. RQ2 — sel M5/M6 lengkap (page_latency_med, n=30, median+IQR):** M5 w2/w8/w23
REST 14,795/15,139/15,672 vs GraphQL 14,732/16,228/20,072; M6 k1/k5/k10 REST
7,746/36,574/75,128 vs GraphQL 14,325/16,883/19,860; K*=2,0; Δ vs
round-trip (M6-k1 −6,58 ms CI [−6,90, −6,49]; M5-w2 +0,064 CI [−0,006,
+0,099]).
- SRC: `laporan/figures/export/rq2_stats.json`; docx Tabel L.1 (M5/M6).

**L18. RQ3 — grid caching (Tabel L.2 subset):** hit rate & delta latency per
blok (zipfian/uniform/unique × light/heavy × on/off); CPU/RSS valid dari
phase2-core-clean: REST ≈2,8% CPU ≈49 MB RSS vs GraphQL ≈8,7% ≈59 MB;
replikasi 12/12 blok δ −1,00, pergeseran ≤0,25 ms, hit rate identik 3 desimal.
- SRC: docx Lampiran 5 Tabel L.2 + §Ancaman Validitas;
  `laporan/figures/export/rq3_caching_figures_stats.json`.

**L19. Factorial-A (robustness) statistik:** 2.880 run, 48 sel; 188/192
perbandingan signifikan (BH-FDR); lat_p95 48/48, throughput 48/48, xproc
48/48 pro-REST; rasio per pattern aggregate 3,6× / filtered 2,9× / partial
2,7× / baseline 2,7× (maks 7,1×); payload ~1,0–1,1; JT trend monoton
konkurensi; 49% grup non-normal (justifikasi non-parametrik).
- SRC: `APEta/MORNING_RUN_REPORT.md` §3b;
  `laporan/figures/export/factorialA_stats.json`.

### Grup L-F: Metode Statistik (2)

**L20. Formulasi & ambang:** U = min(U1,U2); rank-biserial simple-difference
(Kerby); ekuivalen A12 (Vargha-Delaney) & Cliff's δ; ambang pipeline (Romano)
|δ| 0,147 kecil / 0,33 sedang / 0,474 besar; catatan konsistensi: Bab III
menulis 0,10/0,30/0,50 (Kerby), Fiel Peres 0,11/0,28/0,43 — dampak praktis
nol karena hampir semua |δ| = 1,00.
- SRC: docx Bab III §Formulasi; `laporan/REVIEW_MENYELURUH_TESIS.md` §4.10/F8.

**L21. Koreksi berganda & pemisahan overload:** Holm per keluarga metrik
(eksperimen utama); Benjamini-Hochberg FDR q=0,05 (uji pendahuluan saja);
overload dianalisis dalam keluarga Holm terpisah per family; r120 tidak pernah
dipool.
- SRC: docx Bab III §Interpretasi (¶ koreksi); `APEta/MORNING_RUN_REPORT.md`
  §3a; REVIEW F5 (catatan satu kalimat Bab V yang masih menulis BH).

### Grup L-G: Insiden & Integritas Data (5)

**L22. Taksonomi error run-sesi-1:** 345.879 pasangan traceback
`ValueError: could not convert string to float: 'x1'` +
`GraphQLError: Float cannot represent non numeric value: 'x1'` (serialisasi
field bounding_box); rentang ~0,1%–59,5% offset log 1,34 GB lalu berhenti;
HTTP 200 in-band → error_rate = 0 di seluruh CSV; total iterasi GraphQL
7.947.457 (baseline+filtered 3.297.716); run-sesi-2 & factorial-A: 0 error;
run-sesi-1/2 juga pra-perbaikan fairness 824b195 (asimetri konstruksi
partial).
- SRC: `APEta/design/STUDY_COMPARISON.md` §3 Study A signals + §5.

**L23. Konsekuensi & mitigasi run-sesi-1:** DEMOTED — dikeluarkan dari semua
angka tesis; pengganti: factorial-A (2.880 run, audit bersih, 0 error);
guard permanen: k6 body-check "no graphql errors" (final response, aman
terhadap registrasi APQ; kontrol negatif diverifikasi: invalid field = HTTP
200 + body errors → tertangkap).
- SRC: `APEta/MORNING_RUN_REPORT.md` (verdicts + Phase 4a/4b).

**L24. Timeline kontaminasi konkurensi phase2:** dalam-sesi selalu serial
(0 overlap, 17 sesi); antar-sesi hingga 8 sesi paralel (puncak 2026-06-28
05:18); 9.000/9.720 baris phase2 (92,6%) terkumpul saat 2–8 sesi berjalan;
phase2-core-real = satu-satunya sesi caching bebas kontensi (720 run, 1 sesi
sepanjang 26 Jun); core-cpu-rerun 4–8 paralel (tidak pernah serial);
mot-scenarios-core serial penuh.
- **Definisi subset bersih:** RQ3 = phase2-core-real saja; drill-in
  (density/entropy/network/concurrency) = korroborasi paling banter, tidak
  masuk klaim utama.
- SRC: `APEta/design/STUDY_COMPARISON.md` §1 + §3; `laporan/OUTLINE_MASTER.md`
  (Outline C scope notes).

**L25. Bug telemetri & re-run phase2-core-clean:** sampler memantau PID
pembungkus (sudo) bukan proses server → CPU/RSS phase2-core-real invalid;
ditemukan & diperbaiki sebelum studi MOT; phase2-core-clean (720 run, desain
identik, launcher menolak results.csv pra-ada, pinning terverifikasi live)
mereplikasi 12/12 blok; angka konsisten dgn run verifikasi independen kedua
(phase2-core-cpu-rerun).
- SRC: docx Bab V §Ancaman Validitas; `APEta/MORNING_RUN_REPORT.md` Phase 4.

**L26. Audit integritas mot-scenarios-core:** 3.241 baris (md5
94866487…); 108 sel × tepat 30; error_rate 0 di 3.240; dropped_iterations>0
hanya 91 baris r120_overload (by design; M1-high/gql, M5-w23/gql, M6-k10/rest,
M4-high/rest×1); 3.240/3.240 k6 summaries, 0 failed checks; log server 2,8 GB:
0 Traceback/ValueError/GraphQLError; env_snapshot lengkap (k6 2.0.0, SHA
83d364a, netem lan diverifikasi); disclosure DB md5: file berpindah lokasi
pasca-run — identitas dibuktikan hash dump logis (cdb7c9f4…), bukan hash file;
cpu_governor.txt kosong (VM tanpa cpufreq).
- SRC: `APEta/MORNING_RUN_REPORT.md` Phase 0–2 + disclosures.

### Grup L-H: Fairness & Protokol (3)

**L27. Acceptance tests A1–A3 (bukti, bukan klaim):** A1 deep-equal 3 tier +
filter + 404; A2 diff SQL (APE_LOG_SQL) tabel+predikat; A3 Varnish nyata
MISS→HIT ETag sama, no-store dihormati, hash mismatch ditolak
(PERSISTED_QUERY_HASH_MISMATCH); MOT parity gate 18 passed / 2 skipped (skip =
asersi SQL-log khusus sqlite pada backend memory); delta envelope konstan 19 B
(M1–M3) / 13 B (M4); drift guard query test ≡ query k6.
- SRC: docx Bab IV §Pengujian; `APEta/design/PARITY_REPORT_MOT.md`;
  `APEta/design/STUDY_COMPARISON.md` §3.

**L28. Protokol wire APQ:** GET hash-only → PERSISTED_QUERY_NOT_FOUND →
registrasi (+query, verifikasi sha256) → reuse; apq_registrations terukur;
store proses-lokal single-worker.
- SRC: docx Bab IV Increment 3; slide 31 deck lama; Apollo GraphQL (paper
  bank).

**L29. DataLoader & arm N+1:** Detection.track() via strawberry.dataloader →
1 query IN per batch; APE_GRAPHQL_BATCHING=off = arm studi sisipan penalti
N+1 (saran Bab VII, belum dikuantifikasi terpisah).
- SRC: docx Bab IV Analisis Domain + Increment 4 + Bab VII Saran.

### Grup L-I: Q&A & Referensi (4)

**L30. Antisipasi pertanyaan penguji (5 serangan + amunisi):** (1) kontradiksi
CPU Lawi 2021 → beda titik ukur (gateway vs cgroup+psutil proses), beda load
model (closed vs open-loop), beda stack; konvergen Elghazal 2025; replikasi
2 run independen. (2) "δ = ±1,00 mencurigakan" → separasi konsisten + varians
kecil = bukti kontrol; interpretasi tetap via selisih praktis. (3) "REST
tailored, GraphQL tak diberi kesempatan" → by design (overhead protokol pada
fungsionalitas setara); GraphQL tetap menang M6 K≥5. (4) status H3/H4 (lihat
L31). (5) generalisasi → ancaman validitas + prediksi crossover RTT (Jin 2024).
- SRC: `laporan/REVIEW_MENYELURUH_TESIS.md` §8 + F1.

**L31. Peta vonis hipotesis:** H1 didukung (Bab VII); H2 didukung sebagian
(Bab VII); H3 "konsisten secara mekanistis" (Bab VII) — catatan: drill-in
entropi 1.440 run ada di results/ (klausa 1 terdukung empiris, klausa "lebih
menekan GraphQL" tidak — data kontaminasi paralelisme, korroborasi saja); H4
**[VERIFY: vonis final — belum eksplisit di docx]**.
- SRC: docx Bab VII; `laporan/REVIEW_MENYELURUH_TESIS.md` §7.1–7.2, F2–F3;
  memori proyek (mismatch terbuka).

**L32–L33. Daftar pustaka (2 slide, reproduksi persis pasca-audit):** 45 entri
DAFTAR PUSTAKA docx (daftar kedua/final, halaman Lampiran) — tidak ada
referensi baru; bank paper 42 entri (PB-01…PB-42) sebagai cross-check.
- SRC: docx DAFTAR PUSTAKA (blok final); `scratch_paperbank.json`;
  `paper_bank_verified.xlsx`; `papers/` (38 PDF).

---

## DAFTAR [VERIFY] TERANTISIPASI (lengkap)

| # | Slide | Placeholder | Alasan |
|---|---|---|---|
| 1 | M1 | [VERIFY: varian judul "YOLO" vs "YOLO26"] | Sampul docx: "…MENGGUNAKAN YOLO"; lembar pengesahan & pernyataan: "…YOLO26" — konflik internal docx; aturan terminologi butuh satu judul terkunci |
| 2 | M1 | [VERIFY: nama & NIP Pembimbing I/II] | Placeholder template di docx; tidak ditemukan di file workspace mana pun |
| 3 | M36/L31 | [VERIFY: vonis H4] | Bab V/VII tidak memuat kalimat vonis H4 (temuan REVIEW §7.1); review menyarankan "didukung sebagian & dipertajam" tapi belum masuk docx |
| 4 | L1 | [VERIFY: jumlah citra train fine-tuning efektif] | Known-unresolved (a). run2 = split internal 90/10 dari 6.471 (jumlah persis tidak tercatat lokal — splits/*.txt di VM); run3 resmi = 6.471 train/548 val ("6448 images, 23 backgrounds" saat scan) |
| 5 | L1 | [VERIFY: checkpoint penghasil korpus (run2 vs run3)] | `MOT_INFERENCE_GUIDE.md` menunjuk run2 best.pt; `KAGGLE_RUN3.md` menyatakan db frozen; tidak ada manifest inference (weights md5) yang mengunci ini |
| — | — | Known-unresolved (b): asal track_id | **TERSELESAIKAN dari file** — ByteTrack Ultralytics (bukan GT join): docstring `infer_mot_track.py` + "CORPUS DEFINITION" `build_detection_db.py` (track_high_thresh 0,5, iou 0,7) + verifikasi DB (0 NULL). Disajikan dengan sumber, tanpa [VERIFY] |

Placeholder tambahan hanya akan muncul jika saat build ada angka yang ternyata
tidak bisa direproduksi dari file (dilaporkan di tabel akhir Phase 2).

## KEPUTUSAN YANG DIMINTA SEBELUM PHASE 2

1. **Judul slide 1:** "YOLO" (sampul + deck lama) atau "YOLO26" (pengesahan)?
2. **File output:** buat baru `Sidang_TA_APE_JeihanIlham_v2.pptx` (deck lama
   utuh) — atau timpa file lama?
3. **H4 di kesimpulan:** tampilkan [VERIFY] apa adanya, atau pakai rumusan
   review F2 dengan label sumber review?
4. **Jumlah slide main deck 37** (≤60 OK) — setuju, atau minta lebih ramping
   (mis. gabung M22–M23, M34–M36 → ~33)?
