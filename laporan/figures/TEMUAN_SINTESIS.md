# Temuan analitik sintesis — efek variabel, peta pemenang, dan pembacaan efek non-ekstrem

Ringkasan variabel yang dianalisis:

- **Variabel bebas (faktor):** Protokol (REST vs GraphQL) — perlakuan utama; Skenario akses (M1–M6); Tier densitas objek (rendah/sedang/tinggi pada M1–M4, ukuran window w2/w8/w23 pada M5, fan-out K=1/5/10 pada M6); Laju kedatangan (r40/r80/r120-overload). Untuk grid caching: status caching (off/on), pola akses (uniform/unique/zipfian), bobot payload (light/heavy).
- **Variabel terikat (metrik):** waktu respons p50/p95/p99, page-latency (M5–M6), throughput, ukuran payload, jumlah round-trip, cache hit rate, error rate. CPU/RSS valid pada sesi MOT.

---

## 1. Efek marginal tiap variabel bebas terhadap waktu respons (Gambar A — `fx_mot_maineffect_lat_p50/p95`)

Membaca panel per faktor (marginal, M1–M4):

- **Skenario:** garis REST datar-rendah (~7,4–7,9 ms) di semua skenario; GraphQL bervariasi (tertinggi di M1 ≈15,8 ms, terendah di M4 ≈11,3 ms). Jadi *besar* keunggulan REST bergantung skenario, tetapi arah keunggulan tidak.
- **Tier densitas:** kedua protokol naik seiring densitas, tetapi **GraphQL naik jauh lebih curam** (≈12,3→15,5 ms) dibanding REST (≈7,2→8,2 ms). Densitas objek adalah faktor yang paling merugikan GraphQL — selisih melebar dari ~5 ms (low) ke ~7 ms (high). Ini interaksi densitas×protokol yang nyata: biaya serialisasi/resolver GraphQL tumbuh dengan jumlah objek per respons.
- **Laju kedatangan:** kedua garis nyaris datar dari r40 ke r120 (sub-saturasi); selisih antar-protokol praktis konstan. Beban tidak mengubah selisih per-permintaan selama sistem belum jenuh — konsisten dengan model closed/arrival-rate.

**Kesimpulan efek:** protokol dan densitas adalah penggerak dominan waktu respons; laju hanya menggeser level absolut sedikit tanpa mengubah pemenang; skenario memodulasi *besar* selisih.

## 2. Peta pemenang per sel (Gambar B1/B2 — `fx_mot_delta_heatmap_rt/page`)

- **M1–M4 (round-trip, p50):** seluruh 36 sel bernilai **δ = −1,00** — REST unggul dengan pemisahan sempurna di setiap kombinasi tier×laju. Tidak ada satu sel pun yang imbang atau berbalik. Ini temuan yang kuat sekaligus monoton: pada beban objek-tunggal, REST menang total.
- **M5–M6 (page-latency):** di sinilah seluruh dinamika crossover terlihat dalam satu gambar:
  - `M5·w2·r40` = **+0,32** (satu-satunya sel warna hangat lemah — GraphQL *sangat tipis* di depan, lihat §4),
  - `M5·w2·r80` = −0,82 (REST kembali unggul dalam window kecil yang sama saat laju naik),
  - `M5·w8/w23` = −1,00 (REST unggul penuh saat window membesar),
  - `M6·k1` = −1,00 (REST unggul saat fan-out=1),
  - `M6·k5` dan `M6·k10` = **+1,00** (GraphQL unggul penuh — kemenangan complete-separation pertama untuk GraphQL, saat fan-out ≥ 5).

**Kesimpulan pemenang:** REST default menang; GraphQL hanya menang ketika satu operasi logis memerlukan banyak round-trip pada sisi REST (fan-out tinggi M6). Titik balik ada di sekitar K\*≈2.

## 3. Mekanisme crossover (Gambar C — `fx_mot_mechanism_roundtrip`)

Jumlah round-trip per operasi menjelaskan §2 secara mekanistik: M1–M4 dan M6·k1 = 1 round-trip untuk kedua protokol (REST menang murni karena overhead per-permintaan lebih rendah); M5 = REST 2 vs GraphQL 1; **M6 = REST K (1/5/10) vs GraphQL 1**. Keunggulan GraphQL di M6·k5/k10 bukan karena GraphQL lebih cepat per-permintaan, melainkan karena REST membayar K perjalanan bolak-balik untuk merakit satu halaman, sedangkan GraphQL merakitnya di server dalam satu permintaan. Crossover adalah efek **penghematan round-trip**, bukan efisiensi protokol intrinsik.

## 4. Pembacaan efek non-ekstrem — δ yang bukan ±1 dan p-Holm yang bukan <0,001

Ini menjawab langsung permintaan "analisis lebih dalam" pada sel yang tidak terpisah sempurna. Kebenaran pahitnya: **untuk latensi, hanya ada tiga sel yang benar-benar tidak terpisah**; sisanya ada pada metrik struktural.

| Sel | Metrik | δ | p-Holm | REST | GraphQL | Pembacaan |
|---|---|---|---|---|---|---|
| M5·w2·r40 | page-latency | **+0,316** | 0,036 | 14,8 ms | 14,7 ms | Satu-satunya laga imbang sejati. GraphQL unggul 0,1 ms — magnitudo *negligible*, dan p-Holm 0,036 lolos ambang 0,05 tetapi rapuh. Jangan diklaim sebagai kemenangan GraphQL. |
| M5·w2·r80 | page-latency | −0,816 | <0,001 | 14,5 ms | 14,6 ms | REST unggul konsisten secara peringkat meski median hampir identik — contoh δ besar dengan selisih median kecil (efek distribusional, bukan mean). |
| M4·high·r120 | p95 | −0,933 | <0,001 | 9,4 ms | 15,5 ms | REST tetap unggul di overload, tetapi ekor GraphQL mulai tumpang-tindih — satu-satunya sel latensi non-±1 di luar M5·w2. |

Sisa ~105 sel δ non-±1 terletak pada **throughput (38), round-trip-count (39), payload (17), RSS (10)** — bukan "laga ketat" tetapi perbedaan **struktural**:

- **Throughput bukan metrik pembeda (Gambar D — `fx_mot_decoupling`).** Pada sel round-trip sebanding (M1–M4, M6·k1), selisih median throughput GraphQL−REST **< 0,03%** (mis. 25,000 vs 25,008 rps) — keduanya sekadar mengikuti laju tawaran di sub-saturasi. δ Cliff yang "signifikan" (+0,5…+0,9, p-Holm kecil) di sini adalah **artefak peringkat pada nilai praktis identik** — ilustrasi telak signifikansi statistik ≠ signifikansi praktis. Satu-satunya simpangan besar (−17,5%) muncul di sel **overload**, saat protokol yang kolaps kehilangan throughput. (δ=+1,0 throughput pada M6·k5/k10 dikecualikan: itu artefak penghitungan — REST mencatat K sub-permintaan per halaman, 85–340 rps vs 17–34 rps, untuk kerja halaman yang sama.)
- **Klaim over-fetching TIDAK terbukti (Gambar E — `fx_mot_overfetch`).** Rasio payload GraphQL/REST pada M1–M4 bermedian ≈**1,04** (GraphQL hanya ~4% lebih besar karena envelope `{"data":…}`), 17 sel tidak terpisah secara statistik (mis. M1·high δ=−0,33, p-Holm=0,154). Query GraphQL yang dirancang untuk mengambil field yang sama dengan REST **tidak** menghasilkan payload yang lebih ramping — narasi umum "GraphQL menghemat bandwidth dengan menghindari over-fetching" tidak didukung data ini. Selisih bandwidth bukan pembeda; latensi dan round-trip yang pembeda.

## 5. Faktor caching (Gambar F1/F2 — `fx_cache_maineffect`, `fx_cache_delta_heatmap`)

- **Latensi:** REST unggul penuh (δ=−1,00) di **seluruh 12 kombinasi** caching×pola-akses×payload — status caching, pola akses, maupun bobot payload **tidak membalik** pemenang latensi. Caching menurunkan level absolut kedua protokol tetapi tidak mengubah urutan.
- **Cache hit rate:** δ ≈ 0 (−0,22…+0,13) di semua sel caching-on — lapisan cache **adil antar-protokol** (mengonfirmasi N4); tidak ada protokol yang diuntungkan cache secara sistematis.
- **Payload:** campuran — δ=+1 (GraphQL lebih besar) pada payload heavy, tetapi berbalik (−0,98/−0,87) pada beberapa payload light; menegaskan lagi bahwa payload bukan sumbu keunggulan yang konsisten.
- **Throughput:** δ lemah positif (+0,2…+0,5) — selaras temuan §4, throughput tak diskriminatif.

---

### Implikasi untuk laporan
1. Framing hasil sebaiknya: **REST unggul latensi secara default dan tahan terhadap densitas, laju, dan caching; GraphQL hanya unggul ketika operasi logis memaksa banyak round-trip pada REST (fan-out tinggi).**
2. Dua "non-temuan" yang justru bernilai ilmiah: **over-fetching tidak terbukti** dan **throughput tidak diskriminatif** (signifikansi statistik ≠ praktis). Keduanya layak dinyatakan eksplisit sebagai kontribusi, bukan disembunyikan.
3. Satu sel imbang sejati (M5·w2·r40) harus dilaporkan jujur sebagai imbang, bukan kemenangan GraphQL.
