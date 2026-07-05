# BAB V HASIL DAN PEMBAHASAN EKSPERIMEN

Bab ini menyajikan hasil eksperimen dan pembahasan terhadap research question.
Penulisan Bab V perlu membedakan Phase 1 sebagai preliminary study dan Phase 2
sebagai desain eksperimen utama.

## V.1 Hasil Eksperimen

### V.1.1 Hasil Phase 1 sebagai Studi Pendahuluan

Phase 1 menghasilkan 2.160 measured runs. Analisis awal menggunakan Shapiro-
Wilk untuk normalitas, Mann-Whitney U untuk perbandingan REST vs GraphQL, dan
Cliff's delta untuk effect size. Ringkasan awal menunjukkan:

- 42,3 persen grup tidak normal pada Shapiro-Wilk, sehingga uji non-parametrik
  sesuai digunakan.
- Untuk `lat_p95`, 36 dari 36 cell signifikan dan seluruhnya favor REST.
- Untuk `throughput_rps`, 36 dari 36 cell signifikan dan seluruhnya favor REST.
- Untuk `payload_bytes_med`, 35 dari 36 cell signifikan dan seluruh cell favor
  REST.
- Untuk `xproc_p95`, 36 dari 36 cell signifikan dan seluruhnya favor REST.

Hasil ini menunjukkan sinyal kuat bahwa REST lebih unggul pada desain Phase 1.
Namun, laporan tidak boleh langsung menyimpulkan bahwa REST selalu lebih unggul
daripada GraphQL. Setelah audit metodologi, Phase 1 diposisikan sebagai
preliminary study karena desainnya belum cukup memisahkan efek protokol dari
faktor lain seperti bentuk implementasi, cache behavior, dan query shape.

[Tabel V.1 Ringkasan hasil Phase 1]

### V.1.2 Hasil Phase 2 sebagai Eksperimen Utama

TODO: isi setelah run Phase 2 lengkap tersedia.

Hasil Phase 2 perlu disajikan per experimental cell, bukan hanya agregat global.
Setiap cell membandingkan REST dan GraphQL pada kombinasi faktor yang sama.
Metrik utama yang disajikan:

- latency p95.
- throughput.
- payload bytes.
- cache-hit rate.
- error rate.
- CPU/RSS.

[Tabel V.2 Ringkasan hasil Phase 2 per cell]
[Gambar V.2 Crossover surface latency]
[Gambar V.3 Entropy vs cache-hit rate]

## V.2 Pembahasan Hasil Eksperimen

Pembahasan perlu mengikuti RQ:

### Pembahasan RQ1

RQ1 membahas perbedaan kinerja REST dan GraphQL ketika akses data dibuat sama.
Phase 1 memberi sinyal awal bahwa REST lebih cepat, tetapi Phase 2 diperlukan
untuk melihat apakah sinyal tersebut bertahan ketika cache, APQ, access pattern,
payload weight, dan query entropy dikontrol.

### Pembahasan RQ2

RQ2 membahas efek caching, pola akses, bobot payload, dan entropi query. Dalam
Phase 2, `cache_hit_rate` menjadi metrik penting karena efek cache dapat
mengubah latency end-to-end tanpa mengubah kerja origin server. Entropi query
juga penting karena variasi shape dapat menghasilkan cache key berbeda.

### Pembahasan RQ3

RQ3 membahas kondisi kapan REST unggul dan kapan GraphQL mendekati REST. Jawaban
akhir harus berdasarkan cell-level analysis, bukan rata-rata semua kondisi.
Jika GraphQL mendekati REST pada cache-hit tinggi atau payload berat tertentu,
hal tersebut perlu dijelaskan sebagai kondisi spesifik.

### Validitas dan Keterbatasan

Threats to validity yang perlu dibahas:

- Dataset hanya VisDrone/YOLO.
- Server berjalan lokal atau pada VM tertentu.
- Implementasi memakai FastAPI dan Strawberry, sehingga tidak mewakili semua
  framework REST/GraphQL.
- Workload sintetis tidak sepenuhnya sama dengan trafik produksi.
- Phase 1 dan Phase 2 memiliki desain berbeda, sehingga hasilnya tidak boleh
  dicampur sebagai satu eksperimen.

[Tabel V.4 Threats to validity dan mitigasi]

### Pipeline Analisis

Hasil dianalisis dari `results.csv` menggunakan `tools/analyze_phase2.py`.
Analisis membandingkan REST dan GraphQL per cell menggunakan Mann-Whitney U,
Vargha-Delaney A12, Cliff's delta, dan koreksi Holm.

[Gambar V.1 Pipeline analisis hasil]

