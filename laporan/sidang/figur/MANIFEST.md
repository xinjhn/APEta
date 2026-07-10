# Paket Figur Sidang — kurasi 2026-07-10

16 figur diurutkan mengikuti alur presentasi (5 babak). Kolom **Status deck** dibanding isi
`Sidang_TA_APE_JeihanIlham.pptx` per 2026-07-08 (verifikasi hash media): deck sudah memuat 6 dari 16;
**10 lainnya baru** — terutama seluruh figur sintesis (Gambar V.3–V.8) yang dibuat 2026-07-10.

Inti minimal jika waktu sempit (8 figur): 03, 04, 05, 08, 09, 10, 11, 15.

## Babak 1 — Apa yang diuji & bagaimana (metodologi, 2 figur)

| # | File | Di laporan | Status deck | Kalimat pengantar sidang | Pertanyaan penguji yang dijawab |
|---|---|---|---|---|---|
| 01 | fig_17_sequence_rest_vs_graphql_roundtrip | Bab IV | **baru** | "Inilah mekanisme yang diadu: REST membayar K round-trip untuk satu operasi logis, GraphQL merakitnya di server dalam satu permintaan." | "Apa sebenarnya yang berbeda antara kedua protokol yang Anda uji?" |
| 02 | fig_18_deployment_experiment_topology | Bab IV | sudah | "Seluruh eksperimen berjalan terisolasi: network namespace, emulasi netem, CPU pinning — supaya yang terukur adalah protokol, bukan noise lingkungan." | "Bagaimana Anda mengendalikan variabel eksternal?" |

## Babak 2 — Hasil utama RQ1: REST unggul default (4 figur)

| # | File | Di laporan | Status deck | Kalimat pengantar sidang | Pertanyaan penguji yang dijawab |
|---|---|---|---|---|---|
| 03 | fig_rq1_lat_p50_r80 | Bab V (RQ1) | sudah | "Pada beban objek-tunggal M1–M4, REST unggul di setiap sel dengan pemisahan sempurna — δ = −1,00 di 36 dari 36 sel." | "Apa hasil utama Anda?" |
| 04 | fx_mot_maineffect_lat_p50 | Gambar V.3 | **baru** | "Dari tiga variabel bebas, densitas objek-lah yang paling memperlebar selisih (GraphQL 12,3→15,5 ms vs REST 7,2→8,2 ms); laju kedatangan hampir tidak berpengaruh — bukti biayanya per-objek-terserialisasi." | "Faktor apa yang paling memengaruhi hasil? Kenapa gap-nya sebesar itu?" |
| 05 | fig_rq1_cpu_r80 | Bab V (RQ1) | sudah | "Keunggulan latensi REST tidak gratis dibayar di tempat lain: GraphQL justru memakai ±3× CPU untuk kerja yang sama — kini juga tervalidasi di grid caching (Tabel L.2, re-run phase2-core-clean)." | "Apakah selisih latensi ditebus efisiensi sumber daya?" |
| 06 | fig_rq1_lat_p50_r120_overload | Bab V (RQ1) | sudah | "Saat laju dinaikkan melampaui saturasi, GraphQL kolaps lebih dulu pada sel terberat (M1-high) — margin kapasitasnya lebih tipis." | "Bagaimana perilaku di beban ekstrem?" |

## Babak 3 — Batas & mekanisme crossover RQ2 (4 figur — jantung tesis)

| # | File | Di laporan | Status deck | Kalimat pengantar sidang | Pertanyaan penguji yang dijawab |
|---|---|---|---|---|---|
| 07 | fig_rq2_m5_window_r40 | Bab V (RQ2) | sudah | "Penghematan satu round-trip (M5) belum cukup membalik keadaan: GraphQL hanya seri di window terkecil, kalah saat window membesar." | "Kapan penghematan round-trip mulai terasa?" |
| 08 | fig_rq2_m6_crossover_r40 | Bab V (RQ2) | sudah | "Di sinilah pemenang berbalik: begitu fan-out K ≥ 5, GraphQL menang penuh; titik impasnya terinterpolasi di K* ≈ 2." | "Jadi kapan GraphQL layak dipilih?" (figur kunci) |
| 09 | fx_mot_mechanism_roundtrip | Gambar V.6 | **baru** | "Mengapa berbalik? Bukan karena GraphQL menjadi lebih cepat per-permintaan — tetapi karena REST membayar K perjalanan bolak-balik; ini murni ekonomi round-trip." | "Apa mekanisme di balik crossover itu?" |
| 10 | fx_mot_delta_heatmap_page | Gambar V.7 | **baru** | "Satu peta merangkum semua: biru = REST menang, merah = GraphQL menang — hanya M6 K≥5 yang merah penuh, dan satu-satunya sel imbang sejati adalah M5·w2·r40." | "Bisa tunjukkan keseluruhan hasil dalam satu gambar?" |

## Babak 4 — Dua klaim populer yang tidak terbukti (3 figur — kontribusi non-temuan)

| # | File | Di laporan | Status deck | Kalimat pengantar sidang | Pertanyaan penguji yang dijawab |
|---|---|---|---|---|---|
| 11 | fx_mot_overfetch | Gambar V.5 | **baru** | "Klaim paling terkenal GraphQL — hemat bandwidth lewat anti-over-fetching — tidak terbukti pada API yang dirancang setara: rasio payload median 1,04." | "Bukankah GraphQL menghemat bandwidth?" |
| 12 | fx_mot_decoupling | Gambar V.4 | **baru** | "Throughput yang 'signifikan secara statistik' ternyata berbeda kurang dari 0,03% — contoh nyata signifikansi statistik ≠ signifikansi praktis, karena itu kami memakai Cliff's δ, bukan hanya p-value." | "Kenapa Anda pakai effect size, bukan p-value saja?" |
| 16 | fig_factA_load_invariance | Lampiran/cadangan | **baru** | "Robustness lintas beban: δ = +1,00 di seluruh 48 sel studi faktorial awal — arah temuan tidak pernah berbalik oleh konkurensi." | "Apakah temuan Anda kebetulan pada satu konfigurasi beban?" (slide cadangan) |

## Babak 5 — Caching RQ3 (3 figur)

| # | File | Di laporan | Status deck | Kalimat pengantar sidang | Pertanyaan penguji yang dijawab |
|---|---|---|---|---|---|
| 13 | fig_21_rq3_cache_hit_rate | Bab V (RQ3) | **baru** | "Hit rate ditentukan pola akses, bukan protokol: zipfian ±0,4, unique nol — dan δ hit-rate ≈ 0 membuktikan lapisan cache adil terhadap kedua protokol (fairness N4)." | "Apakah perbandingan caching Anda adil?" |
| 14 | fig_22_rq3_latency_delta | Bab V (RQ3) | sudah | "Manfaat caching hanya muncul pada pola zipfian; pada pola lain overhead proxy justru terlihat." | "Kapan caching membantu?" |
| 15 | fx_cache_delta_heatmap | Gambar V.8 | **baru** | "Dan yang terpenting: tidak ada satu pun kombinasi caching × pola akses × payload yang membalik pemenang latensi — REST δ = −1,00 di 12 dari 12 blok." | "Apakah caching mengubah kesimpulan utama?" |

---
Sumber: `laporan/figures/export/` (fx_* = figur sintesis 2026-07-10; fig_rq*/fig_2x = pipeline per-RQ; fig_factA = factorial-A).
Angka pendukung: `results/mot-scenarios-core/analysis/mot_comparisons.csv`, `results/phase2-core-real/analysis/`, `results/phase2-core-clean/analysis/` (CPU/RSS valid).
