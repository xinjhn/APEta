# BAB I PENDAHULUAN

Bab ini menjelaskan latar belakang penelitian, rumusan masalah, research
question, tujuan, manfaat, dukungan data, ruang lingkup, serta sistematika
penulisan laporan. Penelitian ini membahas perbandingan kinerja REST dan
GraphQL dalam penyajian data deteksi objek berbasis YOLO, dengan perhatian
khusus pada fairness eksperimen, caching, pola akses, bobot payload, dan
entropi query.

[Gambar I.1 Alur besar penelitian APE]

## I.1 Latar Belakang

Sistem computer vision modern tidak hanya menghasilkan prediksi pada saat
inference, tetapi juga perlu menyajikan hasil prediksi tersebut ke sistem lain
melalui API. Pada kasus deteksi objek, data yang disajikan dapat berupa kelas
objek, nilai confidence, koordinat bounding box, frame, sequence, dan track
objek dari waktu ke waktu. Bentuk data tersebut membuat desain API menjadi
penting karena payload dapat berubah dari ringan sampai berat, bergantung pada
jumlah objek, tingkat kepadatan frame, serta kedalaman data yang diminta.

REST dan GraphQL merupakan dua pendekatan populer untuk menyajikan data melalui
API. REST umumnya memetakan resource ke endpoint HTTP, sedangkan GraphQL
memungkinkan client menentukan field yang diperlukan melalui query dan selection
set. Perbedaan tersebut sering menimbulkan pertanyaan praktis: pendekatan mana
yang lebih efisien untuk menyajikan data deteksi objek? Jawaban terhadap
pertanyaan tersebut tidak dapat diperoleh hanya dengan membandingkan dua server
secara langsung, karena hasil benchmark dapat dipengaruhi oleh banyak faktor,
seperti strategi implementasi, bentuk payload, caching, resolver, pola akses,
dan kondisi jaringan.

Pada penelitian ini, eksperimen awal atau Phase 1 dilakukan untuk membandingkan
REST dan GraphQL pada penyajian data hasil deteksi objek. Phase 1 menghasilkan
temuan awal yang kuat secara statistik, tetapi hasil tersebut juga memunculkan
pertanyaan metodologis: apakah selisih kinerja benar-benar berasal dari
perbedaan protokol, atau berasal dari confounder lain seperti struktur
implementasi, caching, dan bentuk query? Oleh karena itu, Phase 1 tidak
dibuang, melainkan didokumentasikan sebagai studi pendahuluan yang menjadi
dasar perbaikan metodologi.

Phase 2 kemudian dirancang sebagai eksperimen utama. Pada fase ini, REST dan
GraphQL menggunakan data-access layer yang sama, korpus SQLite yang sama,
kontrol caching yang eksplisit, GraphQL APQ-over-GET, workload k6, serta faktor
eksperimen seperti caching, access pattern, entropy, payload weight, network,
density, dan concurrency. Dengan demikian, penelitian ini tidak hanya bertujuan
menunjukkan protokol mana yang lebih cepat, tetapi juga menjelaskan kondisi apa
yang membuat perbedaan kinerja tersebut muncul.

[Gambar I.2 Alur uji pendahuluan menuju eksperimen utama]

## I.2 Rumusan Masalah

Perbandingan performa REST dan GraphQL sering dilakukan dengan cara menjalankan
dua API dan membandingkan latency atau throughput. Pendekatan tersebut berisiko
menghasilkan kesimpulan yang bias jika dua API tidak menggunakan akses data,
bentuk payload, caching, dan kondisi workload yang setara. Dalam konteks data
deteksi objek, risiko bias semakin besar karena jumlah deteksi per frame,
field yang diminta client, dan kebutuhan mengambil track dapat mengubah ukuran
payload serta kerja server secara signifikan.

Masalah penelitian ini dapat dirumuskan sebagai berikut:

1. Diperlukan instrument eksperimen yang dapat menyajikan data deteksi objek
   melalui REST dan GraphQL dengan akses data yang sama.
2. Diperlukan desain eksperimen yang mengontrol faktor caching, pola akses,
   bobot payload, entropi query, kepadatan data, dan concurrency.
3. Diperlukan dokumentasi hasil yang mampu membedakan antara temuan awal
   Phase 1 dan hasil utama Phase 2.

## I.3 Research Question dan Hipotesis

Research question yang digunakan pada penelitian ini adalah:

- RQ1: Bagaimana perbedaan kinerja REST dan GraphQL dalam menyajikan data
  deteksi objek ketika keduanya menggunakan sumber data dan data-access path
  yang sama?
- RQ2: Bagaimana pengaruh caching, pola akses, bobot payload, dan entropi query
  terhadap latency, throughput, payload bytes, cache-hit rate, dan penggunaan
  sumber daya?
- RQ3: Dalam kondisi eksperimen apa REST lebih unggul, dan dalam kondisi apa
  GraphQL dapat mendekati atau mengurangi selisih kinerja terhadap REST?

Hipotesis awal Phase 2:

- H1: Pada kondisi cache off dan payload ringan, REST memiliki latency lebih
  rendah dibandingkan GraphQL karena pemetaan endpoint lebih langsung.
- H2: Pada kondisi cache on dan akses berulang, selisih latency REST dan
  GraphQL berkurang karena cache mengurangi kerja origin server.
- H3: Entropi query yang lebih tinggi menurunkan cache-hit rate karena semakin
  banyak variasi bentuk request yang menghasilkan cache key berbeda.

## I.4 Tujuan dan Manfaat Penelitian

Tujuan penelitian ini adalah menentukan kondisi eksperimen yang memengaruhi
perbedaan kinerja REST dan GraphQL pada penyajian data deteksi objek berbasis
YOLO. Penelitian ini juga bertujuan menghasilkan aplikasi pendukung eksperimen
yang replikabel untuk mengukur latency, throughput, payload bytes, cache-hit
rate, error rate, APQ registrations, CPU, dan RSS.

Manfaat penelitian ini adalah:

- Memberikan dasar empiris bagi pengembang API dalam memilih REST atau GraphQL
  untuk data computer vision.
- Memberikan contoh desain benchmark API yang lebih terkontrol.
- Menyediakan instrument eksperimen yang dapat dikembangkan ulang untuk studi
  performa API lain.

## I.5 Pemangku Kepentingan Produk Akhir

Pemangku kepentingan penelitian ini meliputi:

- Pengembang backend yang memilih arsitektur API.
- Pengembang sistem computer vision yang perlu menyajikan hasil inference.
- Peneliti atau mahasiswa yang melakukan benchmark API.
- Dosen dan penguji yang mengevaluasi desain metodologi eksperimen.

[Tabel I.2 Stakeholder dan manfaat penelitian]

## I.6 Dukungan Data

Data penelitian berasal dari dataset VisDrone dan hasil inference/tracking YOLO.
Data tracking kemudian dikonversi menjadi korpus SQLite yang digunakan bersama
oleh server REST dan GraphQL. Korpus saat ini berisi 7 sequence, 2.846 image,
5.429 track, dan 104.767 detection.

[Tabel III.4 Ringkasan korpus SQLite]

## I.7 Ruang Lingkup dan Batasan

Ruang lingkup penelitian:

- API read-only untuk data deteksi dan tracking.
- REST dan GraphQL sebagai protokol/paradigma penyajian API.
- Pengukuran performa menggunakan k6 dan telemetry proses.
- Eksperimen caching dengan Varnish dan APQ-over-GET.

Batasan penelitian:

- Penelitian tidak mengevaluasi akurasi model YOLO.
- Penelitian tidak membahas autentikasi, authorization, atau multi-tenant API.
- Hasil tidak digeneralisasi ke seluruh implementasi REST dan GraphQL.
- Phase 1 diperlakukan sebagai preliminary study, bukan hasil utama.

## I.8 Sistematika Penulisan

Laporan ini disusun dalam tujuh bab sesuai template. Bab I menjelaskan konteks
dan perumusan masalah. Bab II membahas teori dan penelitian terkait. Bab III
menjelaskan metodologi penelitian. Bab IV menjelaskan pengembangan APE sebagai
aplikasi pendukung eksperimen. Bab V menyajikan hasil dan pembahasan. Bab VI
membahas dampak hasil penelitian. Bab VII berisi kesimpulan, saran, dan rencana
keberlanjutan.

