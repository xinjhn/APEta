# REWRITE V3 — INDEX HASIL REKONFIRMASI (2026-07-13)

> **STATUS: DIEKSEKUSI 2026-07-13** via `rewrite_v3.py` (scratchpad sesi).
> Backup pra-edit: scratchpad `515_Laporan_pre_v3_backup.docx`. Hasil: 37 figur
> (I:2 II:5 III:5 IV:9 V:16), semua caption SEQ, updateFields aktif. Sisa
> keputusan pengguna: (a) DAFTAR PUSTAKA ganda (daftar APA 1245+ vs daftar bank
> 1276+ — hapus salah satu); (b) tabel "matriks rekomendasi arsitektural"
> (produk akhir yang dijanjikan Bab I/V/VII) belum berwujud tabel di Bab V.

Basis: ekstraksi struktural segar `515_Laporan TA_[R].docx` (mod. 2026-07-12
23:08; 1.843 paragraf; 25 gambar embedded; 53 caption, 40 ber-SEQ-field),
diperiksa silang terhadap `OUTLINE_MASTER.md`, `figures/OUTLINE_RECONFIRM.md`
(verifikasi kode 2026-07-04 — masih berlaku), `FIGURE_REGISTER.md`,
`figures/FIGURE_AUDIT.md`, `figures/FIGURE_PLACEMENT_PLAN.md`, dan
`REVIEW_MENYELURUH_TESIS.md` (papan prioritas F1–F9).
Nomor baris di bawah merujuk ekstraksi `docx_struct.txt` (scratchpad sesi ini).

## 1. Temuan rekonfirmasi yang MENGUBAH rencana lama

1. **Gambar V.2 salah gambar.** Caption "crossover surface
   latency-vs-cache-hit-rate" (baris 1152, image17.png) berisi **diagram
   topologi netns** (render fig_13, bahasa Inggris) — bukan crossover surface.
   Tindakan: ganti image dengan
   `APEta/results/phase2-core-real/analysis/fig_crossover_surface.png`
   (caption tetap sah) — atau regenerasi berlabel ID.
2. **Gambar III.1 "Variabel Penelitian" stale proposal** (baris 584,
   image8.png): kontrolnya "model YOLO / Dataset coco2017" — bertentangan
   dengan teks tesis sendiri (YOLO26, VisDrone-MOT). Ganti dengan render
   fig_16 revisi.
3. **Gambar IV.1 "Diagram Arsitektur Sistem" stale Phase-1** (baris 990,
   image10.png): memory_pool.py / Python Dictionary RAM / loopback — desain
   in-memory yang sudah diretire. Ganti dengan render fig_03 revisi.
4. **Gambar IV.6 "Sequence Diagram Alur Data" stale Phase-1** (baris 1017,
   image15.png): RAM Pool (memory_pool.py), POST /graphql. Ganti dengan
   `figures/export/fig_17_sequence_rest_vs_graphql_roundtrip.png` + caption
   baru (mekanisme K round-trip vs 1 kueri komposit — penjelas RQ3/crossover).
5. **Dua caption tanpa gambar** (klaim placement-plan TERKONFIRMASI):
   baris 1075 "Aliran metrik eksperimen" (← render fig_14 revisi) dan
   baris 1082 "Aktivitas orkestrasi eksperimen"
   (← `export/fig_19_activity_execution_flow.png`; fig_19 dipasang HANYA di
   sini, tidak digandakan di Bab III).
6. **Dua orphan reference TERKONFIRMASI masih ada**: baris 289 (Bab I,
   janji gambar selection set → render fig_15, sudah diuji render OK) dan
   baris 708 (Bab III, janji gambar grid faktor → render fig_11 revisi
   dua panel: grid MOT RQ1 + grid caching).
7. **Penomoran caption**: 6 figur fx_* tertulis "Gambar V.9" semua (cache
   SEQ stale), II.4 dobel, IV.1/IV.2 dobel, DAFTAR GAMBAR stale, dan
   "Table III.1/III.2" (bhs Inggris). Solusi: caption baru pakai
   STYLEREF 1 \s + SEQ Gambar \* ARABIC \s 1 (pola persis caption existing),
   set `<w:updateFields/>` di settings.xml agar Word merefresh semua field +
   TOC saat dibuka.
8. **OUTLINE_MASTER sebagian besar SUDAH terserap di docx** (Bab II 13
   sub-bab; netns/netem, kalibrasi, open-loop+coordinated omission,
   Shapiro/Holm/Jonckheere semuanya ada). Yang belum: pembelaan HTTP/1.1
   (RFC 9113) — opsional satu kalimat; catatan: label RQ outline lama
   (RQ2=crossover, RQ3=caching) TERBALIK vs docx kanonik (RQ2=caching dkk.,
   RQ3=crossover) — selalu ikuti docx.

## 2. Matriks figur (aksi per item)

| Aksi | Figur | Sumber | Target di docx |
|---|---|---|---|
| GANTI image | III.1 variabel | fig_16 **revisi** (re-scope IV/DV/kontrol terkunci) | baris 583 |
| GANTI image | IV.1 arsitektur | fig_03 **revisi** (workload_mot.js, id_pool_mot.json, modul shared, "Varnish hanya jalur caching") | baris 989 |
| GANTI image | IV.6 sequence | export fig_17 (READY) + caption baru | baris 1016 |
| GANTI image | V.2 surface | analysis/fig_crossover_surface.png | baris 1151 |
| PASANG di caption kosong | IV "aliran metrik" | fig_14 **revisi** (anotasi X-Process-Time "tersedia, tidak direkam") | atas baris 1075 |
| PASANG di caption kosong | IV "orkestrasi" | export fig_19 (READY) | atas baris 1082 |
| SISIP baru | Bab I selection set (orphan ref) | fig_15 render (KEEP) | setelah 289 |
| SISIP baru | Bab I alur penelitian | fig_01 **revisi** (tambah node studi MOT) | akhir I.1 (≈292) |
| SISIP baru | Bab III grid faktor (orphan ref) | fig_11 **revisi** (2 panel) | setelah 708 |
| SISIP baru | Bab III ERD korpus | export fig_20 (READY) | setelah 618 |
| SISIP baru | Bab III pipeline data | fig_04 render (KEEP) | setelah 616 |
| SISIP baru | Bab IV deployment | export fig_18 (READY) | setelah ¶ orkestrator (≈1088) |
| SISIP baru | Bab V RQ1 lat r80 | export fig_rq1_lat_p50_r80 | setelah 1154 |
| SISIP baru | Bab V RQ1 overload | export fig_rq1_lat_p50_r120_overload | setelah 1157 |
| SISIP baru | Bab V RQ1 CPU | export fig_rq1_cpu_r80 | setelah 1158 |
| SISIP baru | Bab V RQ2 M5 window | export fig_rq2_m5_window_r40 | dalam 1165 (setelah ¶) |
| SISIP baru | Bab V RQ2 M6 crossover (KUNCI) | export fig_rq2_m6_crossover_r40 | setelah 1168 |
| SISIP baru | Bab V RQ2 Δ vs RT | export fig_rq2_delta_rtc_r40 | setelah M6 |
| SISIP baru | Bab V cache-hit | export fig_21_rq3_cache_hit_rate | setelah 1171 (bag. hit rate) |
| SISIP baru | Bab V Δ caching | export fig_22_rq3_latency_delta | setelah 1171 (bag. delta) |
| SKIP (lampiran saja) | rq1_throughput, rss, varian r40/r80 lain | — | dirujuk teks sebagai lampiran |
| BIARKAN | II.1–II.4b, IV.2–IV.5 (image11 dicek: benar & current), V.1 pipeline | — | — |

Caption siap pakai: `figures/FIGURE_PLACEMENT_PLAN.md` (anchor semua
TERVERIFIKASI ada di teks 2026-07-13) + `figures/FIGURE_CAPTIONS.md`.

## 3. Edit prosa F1–F9 (REVIEW_MENYELURUH_TESIS.md Iterasi 2) — lokasi terverifikasi

| # | Edit | Lokasi (baris struct) |
|---|---|---|
| F1 | ¶ konfrontasi Lawi CPU (gateway+closed-loop vs cgroup+open-loop; konvergen Elghazal; replikasi core-clean/cpu-rerun) | Pembahasan RQ1, setelah 1180 |
| F2 | Vonis H4 eksplisit "didukung sebagian dan dipertajam" (mekanisme = jumlah objek/titik diresolusi, bukan label bobot) | akhir Pembahasan RQ2 (1183) + Kesimpulan (1224) |
| F3 | Status H3: klausa hit-rate DIDUKUNG drill-in entropi (1.440 run); klausa "lebih menekan GraphQL" TIDAK didukung (paritas APQ) — verifikasi angka dari results/ dulu | 1186 + 1224 |
| F4 | "core grid → drill-in (Wohlin)" → desain faktorial (Wohlin) + keputusan sendiri | 697/701/707/718–719/874/924 |
| F5 | BH → Holm di Validitas kesimpulan | 1200 |
| F6 | Split klaim Lawi/Brito over-fetching | 546 |
| F7 | Rujukan figur: "Gambar V.x"/"seri fig_*"/"Gambar fig_21/22" → nomor riil hasil sisipan §2 | 1154, 1158, 1165, 1171, 1185 |
| F8 | Ambang magnitudo → Romano 0,147/0,33/0,474 (+ entri pustaka Romano) | 857 (formulasi), cek 850/871 |
| F9 | Khanam→Jocher (628–631, 669) + entri pustaka; "7–13 ms" → "+51% s.d. +141% (≈4–12 ms r80, terkecil M4)" (1180); tahun Fiel Peres (1253/1289) | tsb. |

## 4. Mekanika eksekusi

- Toolchain: mermaid-cli 11.16.0 via `npx --yes @mermaid-js/mermaid-cli -i src.mmd -o out.png -s 3` (teruji: fig_15 OK). PlantUML tidak perlu (fig_17–20 sudah dirender).
- Backup docx → scratchpad sebelum edit; edit in-place via skrip python
  (python-docx/lxml), caption = pola SEQ persis §1.7.
- Verifikasi purna-edit: re-ekstraksi struktur + export PDF LibreOffice
  headless + inspeksi visual halaman tersisip.
- Sesudah selesai: perbarui status FIGURE_REGISTER.md; TOC/nomor final =
  buka di Word (updateFields aktif) lalu simpan.
