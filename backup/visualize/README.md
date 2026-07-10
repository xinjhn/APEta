# Modul Analisis Statistik (Tahap [I])

Mengubah `results.csv` menjadi temuan. Sudah diuji end-to-end terhadap data
sintetis ber-efek-diketahui (pipeline berhasil mendeteksi seluruh efek yang ditanam).

## Cara pakai
```bash
# (uji) bangkitkan data sintetis ber-efek-diketahui
python analysis/make_synthetic_results.py        # -> results_synth.csv

# jalankan analisis (metrik primer)
python analysis/analyze.py --results results/results.csv --out results/analysis
# semua metrik (+ sekunder cpu/rss):
python analysis/analyze.py --results results/results.csv --out results/analysis --all-metrics
```
Keluaran: `normality.csv`, `pairwise_rest_vs_graphql.csv`, `trend_density.csv`,
`trend_concurrency.csv`, `session_effect.csv`, `ANALYSIS_SUMMARY.md`.

## Uji & rujukan (sumber-asli = sitasi pendiri; pelengkap terkini ditandai)
| Tahap | Uji | Rujukan |
|---|---|---|
| Normalitas | Shapiro-Wilk | Shapiro & Wilk (1965) |
| REST vs GraphQL | Mann-Whitney U | Mann & Whitney (1947) |
| Effect size | Cliff's delta | Cliff (1993); ambang Romano et al. (2006) |
| | | terkini: Meissel & Yao (2024); Macbeth et al. (2011) |
| Koreksi ganda | Benjamini-Hochberg FDR | Benjamini & Hochberg (1995) |
| Tren terurut | Jonckheere-Terpstra | Jonckheere (1954); Terpstra (1952) |
| Efek antar-sesi | Kruskal-Wallis | Kruskal & Wallis (1952) |

Kombinasi Mann-Whitney U + Cliff's delta + ambang Romano adalah praktik standar di
riset empiris CS terkini (mis. studi 2022-2024 yang memakainya secara rutin).

## DUA CATATAN METODOLOGIS (penting untuk pertahanan)

**1. Operasionalisasi tren "gap" (untuk dikonfirmasi ke pembimbing).**
Run REST & GraphQL INDEPENDEN (tak berpasangan), sehingga "tren gap" tak bisa diuji
JT tunggal atas selisih berpasangan. Pipeline mengukurnya via KOMBINASI: (a) JT tren
TIAP protokol terpisah (`rest_trend`/`graphql_trend`, tak terkonfound karena faktor
lain ditahan), dan (b) Cliff's delta REST-vs-GraphQL per level (`gap_delta_*`) untuk
melihat gap membesar/mengecil. Gap-moderation dibaca dari kombinasi keduanya. Bila
ingin SATU uji interaksi langsung, alternatifnya ART-ANOVA (interaksi protokol x
faktor) — bisa didiskusikan; namun laporan saat ini berkomitmen pada Jonckheere-
Terpstra, jadi pendekatan kombinasi ini yang dipakai.

**2. Cliff's delta mengukur DOMINANCE (overlap), bukan besar selisih absolut.**
Selisih kecil-tapi-konsisten bisa menghasilkan |delta|=1. Karena itu, untuk
**payload**, SELALU laporkan selisih absolut (byte/%) di samping Cliff's delta
(kolom `median_rest`/`median_graphql` menyediakannya). Catatan terkait desain:
karena server memilih citra ACAK per request, variansi payload antar-run mencerminkan
keragaman citra; akibatnya overhead amplop GraphQL yang kecil-konstan (~30 B) secara
benar menjadi NEGLIGIBLE, sedangkan sinyal payload yang bermakna adalah over-fetching
antar-POLA (baseline vs partial vs aggregate) yang berukuran ribuan byte. Bila ingin
mengisolasi overhead byte protokol yang presisi, gunakan sampling ber-seed (citra
identik ke kedua protokol) khusus untuk metrik payload.
```

## Visualisasi (`plots.py`)
Setiap figur dipetakan ke satu temuan; jenis plot dipilih berdasar literatur.
```bash
python analysis/plots.py --results results/results.csv --out results/analysis/figures
```
| Figur | Menunjukkan | Rujukan jenis plot |
|---|---|---|
| `fig_dist_<metric>` | distribusi penuh REST vs GraphQL per pola (box, bukan bar) | Weissgerber et al. (2015) |
| `fig_ecdf_latency` | bentuk & EKOR distribusi latensi | Dean & Barroso (2013) |
| `fig_moderation_<metric>_density/concurrency` | tren median lintas faktor + pelebaran gap (moderation) | visualisasi tren Jonckheere-Terpstra (1954) |
| `fig_cliffs_<metric>` | lanskap effect size (Cliff's δ) lintas 36 sel | estimation graphics (Ho et al. 2019); ambang Romano et al. (2006) |
| `fig_payload_overfetching` | reduksi payload oleh seleksi field/agregasi | Brito et al. (2019) |
| `fig_gap_<metric>` | evolusi effect size gap: keunggulan membesar/mengecil? | Ho et al. (2019) |

## Dependensi
`numpy, pandas, scipy` (uji statistik) + `matplotlib, seaborn` (plot).
Versi uji: scipy 1.17, pandas 3.0, matplotlib 3.10, seaborn 0.13.
