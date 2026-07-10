# Ringkasan Analisis Statistik

- Total run terukur: 2880 | metrik dianalisis: lat_p95, throughput_rps, payload_bytes_med, xproc_p95

## Normalitas (Shapiro-Wilk)
49.2% grup non-normal (p<0.05) -> mendukung pemilihan uji non-parametrik (lih. III.7).

## REST vs GraphQL (Mann-Whitney U + Cliff's delta, pasca BH-FDR)

- **lat_p95**: 48/48 sel signifikan (BH). Favored: REST=48, GraphQL=0. Effect size non-negligible: 48 sel.

- **throughput_rps**: 48/48 sel signifikan (BH). Favored: REST=48, GraphQL=0. Effect size non-negligible: 48 sel.

- **payload_bytes_med**: 44/48 sel signifikan (BH). Favored: REST=46, GraphQL=2. Effect size non-negligible: 48 sel.

- **xproc_p95**: 48/48 sel signifikan (BH). Favored: REST=48, GraphQL=0. Effect size non-negligible: 48 sel.

## Tren (Jonckheere-Terpstra)
Lihat trend_density.csv & trend_concurrency.csv: kolom rest_trend/graphql_trend (arah monotonik tiap protokol) + gap_delta_* (evolusi Cliff's delta gap lintas level). Gap-moderation dibaca dari kombinasi keduanya.
