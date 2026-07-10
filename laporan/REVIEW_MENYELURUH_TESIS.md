# Review Menyeluruh Tesis — Latar Belakang sampai Hasil

**Tanggal:** 2026-07-10 · **Metode:** teks lengkap laporan (Bab I–VII, 189 rb karakter) dibaca utuh; seluruh 38 PDF di `~/APE/papers/` diekstrak teksnya dan setiap klaim literatur diverifikasi terhadap **kalimat verbatim** dari paper — bukan dari ingatan. Kutipan bahasa Inggris di bawah adalah salinan persis dari teks PDF.

---

## 1. Ringkasan Eksekutif

Tesis ini secara substansi **sehat dan defensible**: gap-nya nyata, keputusan metodologisnya hampir semua tertelusur ke literatur primer dengan benar, dan hasilnya konsisten dengan arah mayoritas studi terdahulu sambil menyumbang hal yang studi-studi itu tidak punya (kuantifikasi batas crossover, fairness-by-construction, dan dua non-temuan yang jujur). Namun review ini menemukan **satu kontradiksi literatur yang belum dikonfrontasi** (temuan CPU Lawi et al. berlawanan arah dengan temuan tesis dan dibiarkan tanpa pembahasan), **satu atribusi yang tidak ada di sumbernya** (prinsip "core grid → drill-in" dikaitkan ke Wohlin dkk. 2024, padahal frasa/konsep itu tidak ada di buku tersebut), **satu hipotesis yang tidak pernah diberi vonis** (H4), **satu hipotesis yang diklaim "konsisten secara mekanistis" padahal data empirisnya sudah dikumpulkan tetapi tidak dilaporkan** (H3; drill-in entropi 1.440 run ada di `results/`), serta sejumlah inkonsistensi internal yang lebih kecil (§7).

---

## 2. Apa yang Sebenarnya Diteliti (Rekonstruksi)

**Satu kalimat:** mengukur *pada kondisi beban kerja apa* keunggulan arsitektural GraphQL (satu round-trip komposit, query selektif, APQ-cacheable) melampaui biaya eksekusinya (parse–validate–resolve per permintaan), untuk penyajian data hasil deteksi objek YOLO/VisDrone-MOT, pada instrumen yang memaksa kedua protokol melalui sumber data, jalur akses, dan logika caching yang **identik**.

**Struktur logis penelitian** (Bab I → V):

1. **Motivasi domain** — hasil deteksi objek bukan data tabular: "metadata nested yang memuat label kelas, nilai confidence, dan koordinat bounding box" (Bab I, merujuk Nieto et al. 2021), dan kebutuhan klien heterogen di mitra industri (dashboard butuh utuh; mobile/IoT butuh ringkas).
2. **Gap** — studi REST-vs-GraphQL terdahulu (a) memakai data relasional generik, (b) mencampur latensi API dengan I/O basis data, (c) tidak mengontrol caching sebagai variabel, dan (d) tidak pernah menguji payload khas computer vision.
3. **Instrumen** — APE: shared `DetectionDAL` di atas SQLite, shared `core/caching.py`, Varnish + APQ-over-GET, k6 open-loop, telemetri cgroup-pinned; paritas dibuktikan otomatis (acceptance test A1–A3).
4. **Desain** — dua korpus saling melengkapi: grid inti caching 24 blok × 30 run (caching × pola akses × bobot payload) dan studi skenario MOT M1–M6 3.240 run (skenario × tier × laju, dengan r120 overload dianalisis terpisah); plus factorial-A 48 sel sebagai verifikasi ketahanan-beban.
5. **Analisis** — Mann-Whitney U + effect size peringkat (rank-biserial ≡ Cliff's δ) + koreksi Holm per keluarga metrik; interpretasi ganda (p < 0,05 **dan** magnitudo ≥ medium).
6. **Hasil** — REST unggul default (δ = −1,00 di semua sel latensi M1–M4 dan 12/12 blok caching; CPU GraphQL ~3–4,4×); GraphQL menang hanya saat operasi logis memaksa REST membayar K round-trip (M6, K* ≈ 2); over-fetching tidak terbukti (rasio payload 1,04); throughput tidak diskriminatif; caching adil dan asimetris manfaatnya.

---

## 3. Research Gap & Novelty — Diadu dengan Bukti Primer

### 3.1 Klaim gap tesis vs isi paper

**Gap 1 — "belum ada perbandingan fair dengan sumber data, jalur akses, dan caching setara" (Rumusan Masalah 1). TERDUKUNG.** Tidak satu pun studi komparasi di bank paper membangun shared data-access layer atau menyetarakan cacheability. Pembanding terkuat metodologinya pun lemah di sini: Stępień & Skublewska-Paszkowska (2025) hanya menjalankan *"each configuration was executed 6 times and average values across all runs were calculated"* — 6 repetisi, rata-rata, tanpa effect size; bandingkan 30 run + median + δ + Holm pada tesis ini. Lawi et al. (2021) mengukur di API gateway tanpa isolasi jalur data. Tidak ada satu pun yang menguji fairness cache (APQ-over-GET vs HTTP caching) secara eksplisit.

**Gap 2 — "konteks payload computer vision belum diuji". TERDUKUNG.** Seluruh studi empiris komparasi di bank memakai data sistem informasi generik (Lawi: sistem informasi akademik; Stępień: NestJS + data relasional; Niswar: microservice CRUD; Elghazal: microservice; Jin: serverless image pipeline — paling dekat, tapi payload-nya citra, bukan metadata deteksi bersarang). Justifikasi bahwa pola akses M1–M6 (filter/agregasi/limit) adalah beban nyata didukung kuat dari domain VDBMS: Kang et al. (BlazeIt) — *"Prior work uses approximate filtering to reduce the cost of video analytics, but does not handle two important classes of queries, aggregation and limit queries"* — dan Bang et al. (Seiden) menjawab *"both retrieval and aggregate queries"*. Kritik tesis terhadap klaster ini (VDBMS tidak membahas delivery layer) akurat.

**Gap 3 — "latensi terukur bercampur I/O basis data". TERDUKUNG SEBAGIAN — dan tesis sendiri jujur di sini.** Kritik ke studi terdahulu valid, tetapi solusi tesis bukan menghilangkan basis data melainkan *menyetarakan* jalurnya (shared DAL + argumen OS page cache pada korpus moderat, Bab III). Ini pilihan yang lebih baik daripada in-memory (uji pendahuluan membuktikan in-memory tidak realistis), namun secara ketat gap-nya "terisolasi dari *perbedaan* I/O", bukan "terisolasi dari I/O". Redaksi Bab I ("mengisolasi dan membandingkan kinerja murni dari lapisan API") sedikit lebih kuat daripada yang didemonstrasikan; redaksi Bab VII ("fairness by construction") lebih akurat.

### 3.2 Vonis novelty

**Genuinely novel** (tidak ada padanan di 38 paper bank):
1. Instrumen fairness-by-construction dengan paritas terverifikasi otomatis (shared DAL + shared cache-header + encoder + penamaan field), dan pembuktian fairness cache lewat δ cache-hit-rate ≈ 0.
2. Kuantifikasi **batas** crossover (K* ≈ 2 pada fan-out; monetisasi round-trip sebagai fungsi RTT) — literatur hanya punya arah kualitatif.
3. Dua non-temuan yang dilaporkan jujur: over-fetching tidak terbukti pada API yang dirancang setara (median rasio 1,04; +30 byte amplop), dan throughput non-diskriminatif di sub-saturasi (<0,03%) — keduanya koreksi empiris terhadap narasi populer.
4. Konteks payload deteksi objek + interaksi densitas×protokol (biaya per-objek-terserialisasi).

**Bukan novel — dan jangan diklaim sebagai novel:** arah temuan "REST lebih cepat per-permintaan". Empat studi di bank sudah menemukannya: Lawi (*"REST is still faster up to 50.50% in response time and 37.16% for throughput"*), Niswar (*"gRPC has a faster response time, followed by REST and GraphQL"*), Elghazal (*"REST APIs demonstrate superior memory efficiency and faster response times, particularly under high-load conditions"*), Stępień (*"REST is more efficient in simple and high-load scenarios, while GraphQL performs better in complex data structures"*). Kontribusi tesis adalah **batas dan mekanismenya**, bukan arahnya — Bab VII sudah memframe ini dengan benar ("kontribusi utama... metodologi benchmark yang adil"); pertahankan framing itu di sidang.

---

## 4. Verifikasi Klaim Literatur Satu per Satu

| # | Klaim di tesis | Kalimat persis di paper | Vonis |
|---|---|---|---|
| 1 | "Brito dan Valente (2020), melalui eksperimen terkontrol terhadap 22 partisipan... GraphQL membutuhkan waktu implementasi lebih singkat" (Bab II) | *"a controlled experiment with 22 students (10 undergraduate and 12 graduate)... GraphQL requires less effort to implement remote service queries, when compared to REST (9 vs 6 minutes, median times)"* | ✅ Akurat |
| 2 | "Lawi et al. (2021) dan Brito et al. (2019) memberikan landasan metrik dan **pembuktian bahwa GraphQL secara signifikan mereduksi over-fetching**" (Bab II, klaster 1) | Brito 2019: *"GraphQL can reduce the size of the JSON documents returned by REST APIs in 94% (in number of fields) and in 99% (in number of bytes), both median results."* Lawi 2021: tidak mengukur reduksi over-fetching; temuannya *"REST is still faster up to 50.50%..."* | ⚠️ **Setengah benar.** Pembuktian over-fetching hanya milik Brito 2019; menyeret Lawi ke klaim itu tidak didukung teksnya. Perbaiki jadi "Brito et al. (2019) membuktikan; Lawi et al. (2021) memberikan landasan metrik QoS". |
| 3 | Variabel CPU/memori dirujuk ke "(Lawi dkk., 2021)" (Bab III), dan hasil tesis: GraphQL ~3–4,4× CPU REST | Lawi: *"**GraphQL is very efficient in resource utilization**, i.e., 37.26% for CPU load and 39.74% for memory utilization"* — GraphQL **lebih hemat** CPU/memori di studi Lawi | ❌ **Kontradiksi arah yang tidak pernah dibahas.** Tabel II.1 memuat hasil Lawi, tetapi Pembahasan RQ1/Bab V tidak sekali pun mengonfrontasi mengapa temuan resource tesis berlawanan (kandidat penjelasan: stack Node/Express+gateway vs Python Strawberry; beban closed vs open-loop; titik ukur gateway vs cgroup proses server). **Ini serangan penguji paling mudah — siapkan paragraf pembahasannya.** |
| 4 | "Jin et al. ... keunggulan kinerja masing-masing protokol bersifat context-dependent" & crossover RTT (Bab III & V) | *"GraphQL generally outperforms REST with respect to pipeline RTT, especially when there is high network latency"* | ✅ Akurat, dan memperkuat prediksi pergeseran crossover pada RTT besar (Pembahasan RQ2) |
| 5 | "Niswar dkk. (2024)... tidak ada satu protokol yang unggul secara universal" (Bab III) | *"The experimental results indicate that gRPC has a faster response time, followed by REST and GraphQL."* + evaluasi CPU per protokol | ✅ Konsisten (REST > GraphQL pada response time) |
| 6 | Kutipan biaya resolver GraphQL "(Hartig & Pérez, 2018; Cha et al., 2020)" untuk selisih yang proporsional terhadap jumlah objek (Bab V) | Wittern 2019 (dikutip bersama): *"nested object lists can lead to an explosion in response size"*; Cha 2020: *"Resolvers can return lists of objects which can result in arbitrarily large responses — bounded only by the size of the underlying data"* | ✅ Grounding mekanistik kuat dan tepat sasaran (interaksi densitas) |
| 7 | "Mengikuti prinsip **core grid kemudian drill-in (Wohlin dkk., 2024)**" (Bab III) | Frasa/konsep "core grid", "drill-in", maupun strategi bertahap semacam itu **tidak ada** di teks lengkap buku (685 rb karakter diperiksa). Yang ada: desain faktorial 2\*2 dan variannya, taksonomi validitas | ❌ **Atribusi tidak berdasar.** Strategi bertahapnya sendiri bagus — tapi itu keputusan rekayasa penulis, bukan prinsip Wohlin. Ganti rujukan ke desain faktorial Wohlin (yang memang ada) atau hapus atribusinya dan akui sebagai keputusan desain sendiri. |
| 8 | Pemilihan Mann-Whitney U + effect size (Bab II/III, Arcuri & Briand 2011) | *"we suggest to use Mann-Whitney U-test rather than t-test and Welch test"*; *"The t-test measures the difference in mean values whereas the Mann-Whitney U-test deals with their stochastic ranking"* | ✅ Akurat. Catatan: karena Arcuri & Briand merekomendasikan non-parametrik langsung, gerbang Shapiro-Wilk sebenarnya redundan (tidak salah, hanya tidak perlu diframe sebagai "gerbang logis") |
| 9 | Pola akses zipfian "(Breslau dkk., 1999)" (Bab III) | *"the distribution does not follow Zipf's law precisely, but instead follows a Zipf-like distribution with the exponent varying from trace to trace"* | ✅ Akurat — dan istilah tesis "mirip-Zipf" justru lebih presisi daripada banyak paper |
| 10 | Rank-biserial ≡ A12/Cliff's δ; ambang magnitudo (Bab III) | Fiel Peres: *"In the context of the Mann–Whitney U test, rg is equivalent to Cliff's delta (δ)"*; ambangnya *"Small: \|rg\| ≥ 0.11 Medium: \|rg\| ≥ 0.28 Large: \|rg\| ≥ 0.43"* | ⚠️ Ekuivalensi benar; **ambang tidak konsisten tiga arah**: Bab III menulis 0,10/0,30/0,50 (Kerby), Fiel Peres yang dikutip 0,11/0,28/0,43, dan pipeline (`analyze_phase2.py`) memakai 0,147/0,33/0,474 (Romano) — kolom "Magnitudo" di Tabel L.1/L.2 dihasilkan ambang ketiga. Pilih satu (rekomendasi: Romano, sebutkan eksplisit) dan selaraskan teks Bab III. Dampak praktis nol karena hampir semua \|δ\| = 1,00, tapi penguji teliti bisa menangkapnya. |
| 11 | Ala-Laurinaho et al. (2022) — dikutip 1× (tabel kajian) | *"GraphQL offers better performance than REST when multiple values are read or written, whereas REST is faster with single values"* | ⚠️ **Amunisi terbaik yang kurang dimanfaatkan** — ini persis crossover M6 (K=1 vs K≥5) di domain lain (OPC UA/industri). Kutip di Pembahasan RQ2 sebagai bukti konvergen lintas domain. |
| 12 | Elghazal et al. (2025) | *"REST APIs demonstrate superior memory efficiency and faster response times, particularly under high-load conditions"* | ⚠️ Konvergen dengan temuan resource tesis (dan penyeimbang Lawi #3) — layak dikutip di pembahasan CPU/RSS, saat ini tidak dipakai di sana. |

---

## 5. Sintesis Setiap Keputusan Metodologis

Format: **Keputusan → dasar yang diklaim tesis → verifikasi → penilaian.**

1. **Eksperimen komparatif terkontrol, satu faktor perlakuan (protokol) + faktor lingkungan** — dasar: Wohlin dkk. (definisi eksperimen: *"manipulates one factor or variable of the studied setting. Based on randomization, different treatments are applied... while keeping other variables constant"*). ✅ Sesuai definisi buku; variabel kontrol (Bab III) dirinci dengan disiplin di atas rata-rata skripsi.
2. **Dua tahap (uji pendahuluan in-memory → eksperimen utama relasional)** — dasar: temuan sendiri (in-memory tak realistis + caching belum terkontrol). ✅ Kuat justru karena *self-correcting*; Bab V memposisikan pilot sebagai kalibrasi instrumen, bukan hasil. Ini praktik yang baik dan jarang.
3. **Korpus VisDrone-MOT + YOLO26 black-box** — dasar: Zhu et al. (*"a large-scale drone captured dataset, VisDrone, which includes four tracks... (4) multi-object tracking"*), densitas tinggi natural; track lintas-frame memungkinkan payload heavy tanpa simulasi. ✅ Tepat; batasan 7 sequence diakui jujur di Ancaman Validitas.
4. **Fine-tuning dengan resep default + pilot optimizer (SGD vs auto/MuSGD)** — dasar: dokumentasi pilot laju iterasi sendiri. ✅ Metodologi debugging-nya solid (eliminasi penyebab sistem → uji A/B satu variabel). ⚠️ Rujukan "(Khanam et al., 2026)" pada Tabel III.2 **masih tidak ada di DAFTAR PUSTAKA**.
5. **Stratifikasi tier densitas berbasis kuartil (Q1/Q3)** — mekanis, bebas seleksi peneliti; argumen anti-sirkularitas ditulis eksplisit (Bab III). ✅ Salah satu paragraf pertahanan terbaik di tesis.
6. **SQLite + shared DetectionDAL (bukan in-memory, bukan dual-path)** — dasar: fairness + argumen OS page cache. ✅ Defensible; lihat catatan Gap 3 soal redaksi "isolasi".
7. **FastAPI vs Strawberry, HTTP/1.1, tanpa kompresi, satu worker** — dasar: menyamakan substrat transport agar efek round-trip tidak terkontaminasi multiplexing. ✅ Logis dan dinyatakan eksplisit; konsekuensinya (hasil spesifik-stack) diakui di Validitas eksternal.
8. **Varnish + APQ-over-GET untuk cacheability GraphQL** — dasar: GraphQL via POST default tidak cacheable (dokumentasi Apollo/GraphQL Foundation). ✅ Ini keputusan desain paling penting untuk fairness RQ2, dan diverifikasi hasilnya (hit rate setara, δ ≈ 0 — bukti empiris N4).
9. **Pola akses unique/uniform/zipfian** — dasar: Breslau et al. 1999 (verbatim di §4.9). ✅.
10. **Beban open-loop constant-arrival-rate (k6), bukan closed-loop** — dasar: Tene (2015), coordinated omission. ✅ Pilihan yang benar dan *terbayar* di hasil: justru karena open-loop, tesis bisa membuktikan throughput non-diskriminatif dan mendeteksi kolaps overload sebagai antrean (6.725 ms). Referensi Tene adalah presentasi konferensi — kelaziman akademiknya lemah, tapi ini memang sumber kanonis topik tersebut.
11. **1 warm-up dibuang + 30 run terukur independen per sel** — dasar: Crankshaw et al. 2017 (steady-state) + Arcuri & Briand (menolak pengukuran sekali jalan) + verifikasi pilot. ✅ Kokoh. Catatan kecil: klaim "ambang konvensional n=30" adalah konvensi praktis, bukan hasil kalkulasi power formal — jika ditanya, jawabannya adalah verifikasi pilot + complete separation yang membuat post-hoc power tidak relevan.
12. **Kalibrasi laju 40/80/120% dari ceiling protokol-terlemah; overload dianalisis terpisah** — desain sendiri. ✅ Cerdas (menghindari perbandingan apel-jeruk di saturasi); pemisahan r120 disebut konsisten di Bab III dan V.
13. **Isolasi: netns + netem (lan/constrained), cgroup systemd-run, CPU pinning terpisah (server 0-7, k6 8-15, sampler 31)** — dasar: De Rosa et al. (isolasi variabel komputasi pada evaluasi serving). ✅; plus pengakuan jujur bahwa dua korpus memakai profil jaringan berbeda sehingga tidak dibandingkan lintas korpus.
14. **MWU + rank-biserial/A12 + Holm per keluarga metrik + interpretasi ganda (p dan magnitudo)** — dasar: Arcuri & Briand, Vargha & Delaney, Tomczak, Kerby, Fiel Peres. ✅ Di atas standar; dua inkonsistensi redaksi: (a) ambang magnitudo tiga versi (§4.10), (b) **Bab V Ancaman Validitas menyebut "koreksi Benjamini-Hochberg" untuk grid inti padahal Bab III §Interpretasi dan pipeline memakai Holm** (BH hanya untuk uji pendahuluan). Satu kalimat perlu dikoreksi.
15. **Visualisasi heatmap + boxplot** — dasar: Lawi et al. memakai boxplot untuk distribusi kinerja. ✅ (dan sudah diperkuat 6 figur sintesis Gambar V.3–V.8).
16. **Skenario M1–M6 sebagai operasionalisasi pola kebutuhan klien** — dasar: klaster VDBMS (Bang, Kang — kutipan di §3.1) + kasus mitra industri. ✅ Jembatan domain yang menjadi salah satu klaim novelty; M5/M6 (round-trip) adalah desain yang menghasilkan temuan crossover utama.
17. **SDLC Incremental untuk APE** — dasar: Pressman & Maxim (2014). ✅ Standar; acceptance test paritas per increment adalah nilai tambah nyata (fairness bukan asumsi, tapi diuji).

**Kesimpulan §5:** dari 17 keputusan, 15 tertelusur benar ke sumber primer atau ke justifikasi empiris internal; 2 bermasalah pada *atribusi* (core-grid→drill-in ke Wohlin; ambang magnitudo), bukan pada substansi keputusannya.

---

## 6. Hasil: Apakah Menjawab Gap?

Ya, dengan peta yang bersih: **RQ1** terjawab penuh (REST unggul semua sel, complete separation, CPU 3–4,4×, overload kolaps GraphQL 6.725 ms vs 8,64 ms); **RQ2** terjawab dengan mekanisme (monetisasi round-trip; crossover M5 w2; K* ≈ 2 di M6; caching asimetris — GraphQL turun 3,09 ms vs REST 0,41 ms pada zipfian-light; hit rate setara membuktikan fairness); **RQ3** menghasilkan matriks rekomendasi berbasis sel. Dua non-temuan (over-fetching 1,04; throughput <0,03%) diklaim eksplisit sebagai temuan — benar secara ilmiah dan selaras dengan Brito 2019 yang, menariknya, juga menemukan *"GraphQL does not lead to a reduction in the number of queries performed by API clients"* — nuansa yang bisa dikutip sebagai preseden non-temuan.

Hasil juga **konsisten eksternal**: arah cocok dengan Lawi/Niswar/Elghazal/Stępień (latensi), Jin 2024 (RTT tinggi menguntungkan GraphQL — prediksi pergeseran crossover), Ala-Laurinaho (multiple vs single values), dan Elghazal (resource). Satu-satunya kontradiksi eksternal adalah CPU/memori Lawi (§4.3) — *harus* dibahas, bukan didiamkan.

---

## 7. Daftar Inkonsistensi Internal (urut prioritas)

1. **H4 tidak pernah diberi vonis.** Bab I mendefinisikan empat hipotesis; Pembahasan RQ2 berjanji menguji H2, H3, H4, tetapi tidak ada kalimat vonis H4 di Bab V maupun Kesimpulan (yang hanya menyebut H1, H2, H3). Datanya ada: payload heavy memang tidak konsisten memperbesar selisih (grid caching: heavy justru sedikit menurunkan hit rate dan δ payload berbalik pada beberapa sel light) — tulis vonisnya eksplisit (kemungkinan: "didukung sebagian" via M5 window besar & tier densitas, "tidak didukung" pada grid caching).
2. **H3 diklaim "konsisten secara mekanistis" padahal data empirisnya sudah ada dan tidak dipakai.** `results/phase2-entropy-drillin/` (1.440 run) dan `phase2-entropy-concurrency-interaction/` (1.440 run) selesai sejak 29 Juni. Pilihannya dua: laporkan hasil drill-in entropi (satu paragraf + satu figur) sehingga H3 berstatus empiris, atau turunkan H3 secara eksplisit menjadi proposisi mekanistis yang diuji sebagian. Status sekarang (hipotesis penuh, jawaban mekanistis) adalah celah sidang.
3. **Holm vs Benjamini-Hochberg** — Ancaman Validitas (Validitas kesimpulan) menyebut BH untuk grid inti; Bab III dan pipeline memakai Holm (BH hanya di uji pendahuluan). Koreksi satu kalimat.
4. **Kontradiksi Lawi (CPU/memori) tidak dikonfrontasi** — lihat §4.3.
5. **Atribusi "core grid → drill-in (Wohlin dkk., 2024)"** — lihat §4.7.
6. **Referensi figur yang tidak ada di dokumen:** Bab V menyebut "Gambar V.x (seri fig_rq1_lat_p50)" (placeholder literal "V.x" belum diganti), serta "seri fig_rq1_throughput/cpu/rss", "seri fig_rq2_m5_window/m6_crossover/delta_rtc", "Gambar fig_21", "fig_22" — file-file ini ada di `figures/export/` tetapi **tidak disisipkan** ke dokumen. Putuskan: sisipkan yang dirujuk (minimal fig_rq2_m6_crossover — figur kunci; fig_rq1_cpu; fig_21/22) atau ubah rujukannya ke Gambar V.3–V.8/Lampiran.
7. **"Selisih 7–13 ms yang konsisten" (Pembahasan RQ1)** — pada r80 tier tinggi memang 7,4–12,2 ms, tetapi M4 (agregasi) hanya ±4 ms; rentang klaim tidak menutup semua sel yang dicakup kalimatnya. Ganti dengan rentang persentase yang sudah dipakai di Hasil (+51% s.d. +141%) atau sebutkan pengecualian M4.
8. **Ambang magnitudo effect size tiga versi** — lihat §4.10.
9. **"(Khanam et al., 2026)" belum ada di DAFTAR PUSTAKA** (dikutip di Tabel III.2 dan tabel perangkat III.4).
10. Minor: Fiel Peres ditulis "(2025)" di pustaka tetapi DOI/terbitannya 2026 (dan sitasi Bab V menulis 2025); Kang dkk. ditulis 2020 (PVLDB 13(4) terbit Des 2019 — lazim ditulis 2020, cek gaya sitasi); caption Gambar V.3–V.8 masih menampilkan nilai cache "V.9" sampai F9 dijalankan di Word (bukan isu konten).

---

## 8. Serangan Penguji Paling Mungkin (dan amunisinya)

1. *"Lawi menemukan GraphQL lebih hemat CPU — Anda 4×. Siapa yang benar?"* → Keduanya mengukur hal berbeda: Lawi mengukur di gateway pada stack Node dengan beban berbeda; tesis mengukur proses server langsung via cgroup + psutil pada beban open-loop yang identik antar-protokol, dan angkanya direplikasi dua run independen (core-clean, cpu-rerun) + konvergen dengan Elghazal 2025. Tetap: tulis ini di Bab V sebelum sidang.
2. *"REST Anda dirancang pas kebutuhan klien — GraphQL tak diberi kesempatan menang lewat field selection."* → Benar dan by design: yang diukur overhead protokol pada fungsionalitas setara; keunggulan konsolidasi GraphQL tetap terukur dan menang di M6 K≥5. Preseden: Brito 2019 mengukur skenario sebaliknya (REST generik) dan dapat 99% — dua ujung spektrum yang sama.
3. *"Kenapa hampir semua δ = ±1,00? Itu mencurigakan."* → δ jenuh pada gap konsisten + varians kecil (n=30, lingkungan terkontrol); justru bukti kontrol eksperimen; selisih praktisnya dilaporkan terpisah dalam ms/persen. Non-temuan throughput menunjukkan penulis paham perbedaan signifikansi statistik vs praktis.
4. *"H3/H4?"* → selesaikan #1–2 di §7 dulu.
5. *"Generalisasi?"* → Ancaman Validitas sudah menuliskannya (satu mesin, satu stack, netem, 7 sequence); jawaban tambahan: prediksi arah pergeseran crossover pada RTT besar sudah dinyatakan dan sejalan Jin 2024.

---

## 9. Rekomendasi Prioritas

| Prioritas | Aksi | Lokasi |
|---|---|---|
| 1 | Tambah paragraf konfrontasi Lawi (CPU/memori) di Pembahasan RQ1, kutip Elghazal sebagai konvergen | Bab V |
| 2 | Vonis eksplisit H4; putuskan status H3 (laporkan drill-in entropi atau turunkan klaim) | Bab V + VII |
| 3 | Perbaiki atribusi "core grid → drill-in"; koreksi BH→Holm di Validitas kesimpulan | Bab III + V |
| 4 | Bereskan rujukan figur: "Gambar V.x", seri fig_rq1/rq2, fig_21/22 (sisipkan atau ubah rujukan) | Bab V |
| 5 | Pecah klaim ganda Lawi+Brito soal over-fetching (§4.2); tambahkan Khanam ke pustaka | Bab II + Pustaka |
| 6 | Satukan ambang magnitudo (rekomendasi: Romano 0,147/0,33/0,474, sebut eksplisit); rapikan "7–13 ms"; tahun Fiel Peres | Bab III + V |
| 7 | Kutip Ala-Laurinaho di Pembahasan RQ2 sebagai konvergensi lintas domain | Bab V |

---

*Sumber verifikasi: `~/APE/papers/` (38 PDF, teks diekstrak penuh; Wohlin 282 hal. penuh), teks laporan hasil ekstraksi python-docx, `results/*/analysis/*.csv`, `tools/analyze_phase2.py`. Semua kutipan bahasa Inggris adalah verbatim dari PDF; kesalahan OCR/ekstraksi kecil mungkin ada pada spasi/tanda hubung.*

---

# ITERASI 2 (v2) — Sintesis Jawaban Siap-Tempel

> Versi visual + papan prioritas: https://claude.ai/code/artifact/97d91432-ea19-4908-9244-faf28f0b346f
> **Koreksi proveniensi:** temuan §4.7/§7.5 ("core grid → drill-in (Wohlin)") diketahui berasal dari teks yang ditulis asisten AI pada sesi penulisan terdahulu — bukan fabrikasi penulis. Dikeluarkan dari daftar kesalahan penulis; tindakan korektifnya tetap berlaku (F4 di bawah).

**F1 — Konfrontasi Lawi (Bab V, Pembahasan RQ1):** tambah paragraf yang menjelaskan tiga perbedaan desain ukur — (1) titik ukur gateway pada sistem utuh vs proses server langsung via cgroup+sampler ter-pin; (2) JMeter closed-loop (protokol lambat otomatis menerima lebih sedikit kerja → utilisasi tampak rendah) vs open-loop constant-arrival pada laju identik; (3) stack berbeda — lalu tutup dengan konvergensi Elghazal 2025 dan replikasi internal dua run independen. Teks lengkap di artifact v2 §F1.

**F2 — Vonis H4 (Bab V + VII):** "didukung sebagian dan dipertajam" — mekanismenya jumlah objek/titik data yang diresolusi per respons (densitas M1–M4: gap 5→7 ms; window M5: w2 seri → w23 kalah), bukan label bobot payload (grid caching: δ=−1,00 pada kedua bobot dengan besaran serupa). Teks lengkap di artifact v2 §F2.

**F3 — Status H3:** nyatakan eksplisit sebagai prediksi mekanistis yang belum diuji (faktor entropi dikunci medium pada grid inti); tambah butir Saran Bab VII untuk pengujian gradien entropi. Teks lengkap di artifact v2 §F3.

**F4 — Atribusi Wohlin (Bab III):** ganti "prinsip core grid kemudian drill-in (Wohlin dkk., 2024)" → "desain faktorial penuh pada empat faktor inti (Wohlin dkk., 2024), dengan faktor lain dikunci…; perluasan diposisikan sebagai kerja lanjutan". Desain faktorial memang ada di Wohlin; strategi bertahap adalah keputusan penelitian sendiri.

**F5 — BH→Holm (Bab V, Validitas kesimpulan):** "koreksi Holm diterapkan per keluarga metrik…; Benjamini-Hochberg (FDR, q=0,05) hanya digunakan pada analisis uji pendahuluan."

**F6 — Split Lawi/Brito (Bab II):** bukti reduksi 94%/99% milik Brito 2019 **terhadap endpoint REST generik**; Lawi menyumbang landasan metrik QoS. Tambahkan catatan konteks yang menyiapkan non-temuan over-fetching Bab V (endpoint tailored menyempitkan ruang penghematan).

**F7 — Rujukan figur Bab V:** ganti "Gambar V.x"→Gambar V.3; "seri fig_rq1_*"→Tabel V.1+Lampiran (atau sisipkan fig_rq1_cpu_r80); "seri fig_rq2_*"→Gambar V.6–V.7 (atau sisipkan fig_rq2_m6_crossover_r40); "Gambar fig_21/fig_22"→sisipkan sebagai Gambar V.9–V.10. Eksekusi docx = iterasi v3.

**F8 — Ambang magnitudo (Bab III):** standarkan ke ambang pipeline (Romano et al. 2006: 0,147/0,33/0,474), sebutkan kesetaraan praktisnya dengan Kerby/Fiel Peres karena |δ|=1,00 hampir di semua sel; tambah entri Romano ke pustaka.

**F9 — Kecil:** (a) ganti "(Khanam et al., 2026)" → "(Jocher et al., 2026)" + entri pustaka "Jocher, G., Qiu, J., Liu, M., Lyu, S., Akyon, F. C., & Kalfaoglu, M. E. (2026). Ultralytics YOLO26: Unified Real-Time End-to-End Vision Models. arXiv."; (b) "selisih 7–13 ms" → "+51% hingga +141% (sekitar 4–12 ms pada r80; terkecil pada M4)".
