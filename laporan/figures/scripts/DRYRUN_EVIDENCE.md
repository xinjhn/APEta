# Bukti dry-run skrip figur RQ1/RQ2 (2026-07-04)

Ketiga skrip dieksekusi nyata (bukan ditinjau-baca saja) dengan interpreter
`APEta/venv/bin/python` (matplotlib 3.10.9, pandas terpasang).

## 1. rq3_caching_figures.py — run PENUH (data lengkap)

    $ venv/bin/python scripts/rq3_caching_figures.py \
        --input APEta/results/phase2-core-real/results.csv --outdir export
    OK: fig_21 + fig_22 (PNG+SVG) dan rq3_caching_figures_stats.json ditulis ke export

720 baris; angka terverifikasi terhadap phase2_analysis_report.txt
(zipfian ~0,37–0,43; uniform ~0,02–0,06; unique 0,00; n=30/cell).

## 2. rq1_scenario_figures.py — dry-run pada CSV phase2-core-real

    $ ... --input results/phase2-core-real/results.csv --outdir <scratch>/rq1 --dry-run
    [schema] kolom tidak ada di results.csv: ['scenario', 'tier', 'rate_label']
    [schema] dry-run: kolom disintesis deterministik (seed 42) — angka TIDAK bermakna.
    OK: figur RQ1 (PNG+SVG) + rq1_stats.json ditulis ke .../rq1

**Beda skema yang dilaporkan** (phase2-core-real vs mot-scenarios-core):
kolom `scenario`, `tier`, `rate_label` tidak ada. Kolom lain yang dipakai
(lat_p50/p95, throughput_rps, cpu_mean, rss_mean_mb, dropped_iterations)
ada di kedua skema. 30 file PNG+SVG (5 metrik × 3 rate) + sidecar dihasilkan;
judul diberi watermark [DRY-RUN — DATA SINTETIS, BUKAN HASIL]; output ke
scratch, TIDAK ke export/.

## 3. rq2_crossover_figures.py — dry-run pada CSV phase2-core-real

    $ ... --input results/phase2-core-real/results.csv --outdir <scratch>/rq2 --dry-run
    [schema] kolom tidak ada di results.csv:
      ['scenario', 'tier', 'rate_label', 'page_latency_med']
    [schema] dry-run: kolom disintesis deterministik (seed 42) — angka TIDAK bermakna.
    OK: figur RQ2 (PNG+SVG) + rq2_stats.json ditulis ke .../rq2

**Beda skema tambahan**: `page_latency_med` (variabel pembanding RQ2) tidak
ada di phase2 — di dry-run disintesis dari lat_p50. `round_trip_count` ADA di
phase2 tapi konstan = 1 (didokumentasikan analyze_phase2.py), sehingga
disintesis ulang agar jalur anotasi RT teruji. 18 file PNG+SVG + sidecar
(m5_window, m6_crossover dengan deteksi K*, delta_vs_round_trip) dihasilkan.

## 4. Guard data parsial — diuji NYATA terhadap CSV MOT yang sedang berjalan

    $ ... rq1_scenario_figures.py --input results/mot-scenarios-core/results.csv --outdir <scratch>/guard
    [schema] semua kolom wajib ada.
    Cell belum lengkap (31):
       M1/low/r40/rest: 0/30
       ...
    Berhenti: data parsial tidak boleh di-chart (aturan studi). ...

    $ ... rq2_crossover_figures.py --input results/mot-scenarios-core/results.csv ...
    Cell belum lengkap (...)
    Berhenti: data parsial tidak boleh di-chart (aturan studi).

Kedua skrip MENOLAK CSV live (1.809/3.240 saat uji) — aturan "jangan chart
data parsial" ditegakkan oleh kode, bukan sekadar konvensi. (CSV hanya
DIBACA; proses eksperimen tidak disentuh.)

## Perintah final saat mot-scenarios-core selesai (~2026-07-06)

    cd /home/ubuntu/APE/laporan/figures
    P=/home/ubuntu/APE/APEta/venv/bin/python
    CSV=/home/ubuntu/APE/APEta/results/mot-scenarios-core/results.csv
    $P scripts/rq1_scenario_figures.py --input $CSV --outdir export
    $P scripts/rq2_crossover_figures.py --input $CSV --outdir export

Guard kelengkapan lolos otomatis saat 3.240 run terpenuhi. Sebelum memakai
figur CPU/RSS: cek kewajaran variasinya (outline C.9, pasca-perbaikan bug
sampler). Periksa juga sidecar `rows_with_dropped_iterations` per cell
sebelum menyebut cell overload "tersaturasi".

## 5. RUN FINAL (2026-07-07) — data lengkap 3.240/3.240

Kedua skrip dieksekusi pada CSV final; guard kelengkapan lolos otomatis
(108 cell × 30 run, `[schema] semua kolom wajib ada`, dry_run=false pada
kedua sidecar). Angka sidecar dicek silang terhadap analisis pandas
independen (median/IQR cocok). Uji kewajaran CPU/RSS (C.9) LULUS:
CV dalam-cell median 1,3%, CPU monoton naik terhadap rate, rasio r80/r40
= 1,93. `rows_with_dropped_iterations` > 0 hanya pada cell overload:
M1-high GraphQL (30/30), M5-w23 GraphQL (30/30), M6-k10 REST (30/30),
M4-high REST (1/30, ambang).

**Dua perbaikan skrip setelah inspeksi visual PNG** (regenerasi penuh):

1. Panel latensi r120_overload tidak terbaca pada sumbu linier (bar 6,7 dtk
   M1-high meratakan 23 bar lain) → sumbu-y log untuk lat_p50/p95 (RQ1)
   dan m5_window/m6_crossover (RQ2) KHUSUS rate overload; delta_rtc
   overload memakai symlog (linthresh 10 ms) karena memuat Δ dua tanda.
   Dicatat di judul figur ("sumbu-y logaritmik"/"symlog").
2. Catatan overload pada judul melebihi kanvas (terpotong dua sisi) →
   dipindah ke baris judul sendiri; judul delta_rtc dipecah + fontsize 9;
   margins(y=0.2) mencegah marker M6-k10 terpotong.

Figur sub-saturasi (r40/r80) TIDAK berubah skala — tetap linier.
Caption final: `FIGURE_CAPTIONS.md` bagian "Figur hasil mot-scenarios-core";
register: `laporan/FIGURE_REGISTER.md` baris 27–32 (status `generated`).
