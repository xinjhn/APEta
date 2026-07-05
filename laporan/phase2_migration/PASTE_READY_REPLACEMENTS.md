# Paste-Ready Replacements untuk Draft Phase 2

Bagian ini berisi teks yang dapat langsung dipindahkan ke draft Word lalu disesuaikan gaya sitasi dan nomor gambar/tabelnya.

## Judul Indonesia

ANALISIS KINERJA REST DAN GRAPHQL PADA PENYAJIAN DATA DETEKSI OBJEK DENGAN VARIASI CACHING DAN POLA AKSES

## Judul Inggris

PERFORMANCE ANALYSIS OF REST AND GRAPHQL FOR OBJECT DETECTION DATA DELIVERY UNDER CACHING AND ACCESS PATTERN VARIATIONS

## Latar Belakang - Versi Pengganti

Perkembangan sistem computer vision membuat hasil deteksi objek tidak hanya digunakan di dalam proses inference, tetapi juga perlu disajikan kepada aplikasi lain melalui Application Programming Interface (API). Data hasil deteksi objek memiliki karakteristik yang berbeda dari data transaksional sederhana karena dapat memuat informasi frame, kelas objek, confidence, bounding box, sequence, serta track objek lintas frame. Karakteristik tersebut menyebabkan ukuran payload dan kompleksitas akses data dapat berubah secara signifikan antar permintaan.

REST dan GraphQL merupakan dua pendekatan yang umum digunakan dalam pengembangan API. REST menyajikan resource melalui endpoint HTTP, sedangkan GraphQL memungkinkan client menentukan field yang dibutuhkan melalui query. Secara konseptual, GraphQL dapat mengurangi over-fetching karena client dapat memilih field tertentu. Namun, GraphQL juga memiliki overhead eksekusi seperti parsing query, validasi, resolver traversal, serta tantangan caching karena request GraphQL umumnya dikirim melalui POST. Sebaliknya, REST lebih selaras dengan mekanisme HTTP caching, tetapi dapat membutuhkan endpoint atau parameter tambahan untuk memenuhi variasi kebutuhan data client.

Perbandingan performa REST dan GraphQL tidak cukup dilakukan hanya dengan menjalankan dua server dan membandingkan latency. Hasil benchmark dapat dipengaruhi oleh banyak faktor, seperti sumber data yang digunakan, pola akses, bobot payload, variasi bentuk query, mekanisme caching, serta kondisi jaringan. Oleh karena itu, penelitian ini merancang Alat Pembantu Eksperimen (APE) yang menyajikan corpus deteksi objek yang sama melalui REST dan GraphQL, menggunakan data-access layer yang sama, serta menjalankan workload yang terkontrol.

Penelitian dilakukan dalam dua tahap. Tahap pertama merupakan uji pendahuluan untuk memvalidasi instrument eksperimen, memastikan server REST dan GraphQL dapat menyajikan data secara fungsional, serta membaca variabilitas awal metrik performa. Tahap kedua merupakan eksperimen utama yang memasukkan faktor caching, pola akses, entropi query, bobot payload, profil jaringan, kepadatan data, dan concurrency. Dengan rancangan tersebut, penelitian ini tidak hanya membandingkan REST dan GraphQL secara umum, tetapi juga menganalisis kondisi eksperimen yang memengaruhi keunggulan masing-masing pendekatan.

## Rumusan Masalah - Versi Pengganti

Berdasarkan latar belakang tersebut, rumusan masalah penelitian ini adalah sebagai berikut:

1. Perbandingan performa REST dan GraphQL dapat menjadi bias apabila kedua API tidak menggunakan sumber data, data-access path, serta konfigurasi caching yang setara.
2. Data deteksi objek memiliki variasi payload dan struktur relasional image-detection-track yang dapat memengaruhi latency, throughput, payload size, cache-hit rate, dan penggunaan sumber daya server.
3. Belum jelas bagaimana caching, pola akses, entropi query, bobot payload, kondisi jaringan, dan concurrency memengaruhi perbedaan performa REST dan GraphQL pada penyajian data deteksi objek.

## Research Question - Versi Pengganti

RQ1: Bagaimana perbedaan kinerja REST dan GraphQL dalam menyajikan data deteksi objek ketika keduanya menggunakan corpus dan data-access layer yang sama?

RQ2: Bagaimana pengaruh caching, pola akses, bobot payload, entropi query, profil jaringan, kepadatan data, dan concurrency terhadap latency, throughput, payload size, cache-hit rate, dan penggunaan sumber daya server?

RQ3: Pada kondisi eksperimen apa REST lebih unggul, dan pada kondisi apa GraphQL dapat mendekati atau mengurangi selisih kinerja terhadap REST?

## Hipotesis - Versi Pengganti

H1: Pada kondisi cache off, REST memiliki latency lebih rendah dibandingkan GraphQL karena request REST dapat dipetakan langsung ke endpoint dan tidak memerlukan parsing serta eksekusi selection set GraphQL.

H2: Pada kondisi cache on dengan pola akses berulang, selisih latency REST dan GraphQL berkurang karena sebagian request dapat dilayani oleh cache tanpa perlu memproses ulang data pada origin server.

H3: Entropi query yang lebih tinggi menurunkan cache-hit rate karena variasi bentuk request menghasilkan cache key yang lebih beragam.

H4: Payload heavy berupa track trajectory menghasilkan perbedaan performa yang lebih besar dibandingkan payload light karena server perlu mengambil dan menyerialisasi struktur data yang lebih dalam.

## Tujuan Penelitian - Versi Pengganti

Tujuan penelitian ini adalah menentukan kondisi yang memengaruhi perbedaan kinerja REST dan GraphQL pada penyajian data deteksi objek berbasis YOLO. Secara khusus, penelitian ini bertujuan:

1. Mengembangkan APE sebagai instrument eksperimen yang menyajikan corpus deteksi objek yang sama melalui REST dan GraphQL.
2. Mengukur kinerja REST dan GraphQL berdasarkan latency, throughput, payload size, cache-hit rate, error rate, APQ registrations, CPU usage, dan memory usage.
3. Menganalisis pengaruh caching, pola akses, entropi query, bobot payload, profil jaringan, kepadatan data, dan concurrency terhadap performa API.
4. Menyusun rekomendasi kondisi penggunaan REST atau GraphQL pada sistem penyajian data deteksi objek.

## Dukungan Data - Versi Pengganti

Data penelitian bersumber dari dataset VisDrone-MOT yang diproses menggunakan model YOLO dan mekanisme tracking. Hasil tracking dikonversi ke dalam corpus relasional SQLite agar REST dan GraphQL dapat membaca sumber data yang sama melalui data-access layer yang sama. Corpus utama penelitian disimpan pada `mot_detections.db` dan terdiri dari 7 sequence, 2.846 image, 5.429 track, serta 104.767 detection. Struktur data meliputi tabel `sequence`, `image`, `detection`, `track`, dan `class`, sehingga eksperimen dapat menguji payload ringan berupa image detections serta payload berat berupa track trajectory.

## Ruang Lingkup - Versi Pengganti

Ruang lingkup penelitian ini adalah evaluasi kinerja REST dan GraphQL sebagai delivery layer untuk data deteksi objek. Pengujian berfokus pada API read-only, corpus deteksi objek berbasis SQLite, workload k6, cache layer Varnish, GraphQL APQ-over-GET, serta telemetry CPU dan memory. Faktor eksperimen mencakup protocol, caching, access pattern, entropy, payload weight, network profile, density, dan concurrency.

## Batasan - Versi Pengganti

Penelitian ini tidak mengevaluasi akurasi model deteksi objek, seperti mAP atau precision-recall, karena model YOLO diposisikan sebagai penghasil corpus data. Penelitian juga tidak membahas autentikasi, authorization, deployment multi-node produksi, maupun protokol lain seperti gRPC dan WebSocket. Hasil penelitian dibatasi pada implementasi REST menggunakan FastAPI, GraphQL menggunakan Strawberry, cache menggunakan Varnish, dan corpus data VisDrone-MOT yang tersedia pada lingkungan eksperimen.

## Penjelasan Penelitian - Bab III

Penelitian ini menggunakan pendekatan eksperimen empiris dengan dua tahap pelaksanaan. Tahap pertama adalah uji pendahuluan yang digunakan untuk memvalidasi kesiapan instrument APE, memastikan parity fungsional antara REST dan GraphQL, serta membaca variasi awal metrik performa. Tahap kedua adalah eksperimen utama yang menggunakan desain faktor lebih lengkap untuk menjawab research question.

Eksperimen utama menggunakan corpus deteksi objek yang disimpan dalam SQLite. REST dan GraphQL membaca data melalui `DetectionDAL` yang sama agar perbedaan hasil tidak disebabkan oleh perbedaan jalur akses data. Selain itu, cache behavior dikontrol secara eksplisit melalui Varnish dan header HTTP yang sama. GraphQL diuji melalui APQ-over-GET agar dapat dibandingkan dalam konteks HTTP caching, sedangkan REST diuji melalui endpoint GET yang cacheable.

## Variabel Penelitian - Bab III

Variabel bebas penelitian utama adalah protocol, caching, access pattern, entropy, payload weight, network, density, dan concurrency. Protocol terdiri dari REST dan GraphQL. Caching terdiri dari on dan off. Access pattern terdiri dari unique, uniform, dan zipfian. Entropy terdiri dari low, medium, dan high, yang merepresentasikan variasi bentuk query. Payload weight terdiri dari light dan heavy. Network terdiri dari lan dan constrained. Density terdiri dari low, medium, dan high. Concurrency direpresentasikan melalui jumlah virtual users pada k6.

Variabel terikat adalah latency p50, latency p95, latency p99, throughput, median payload bytes, cache-hit rate, error rate, APQ registrations, CPU usage, dan memory usage. Variabel kontrol meliputi corpus SQLite yang sama, data-access layer yang sama, single worker server, run duration, seed/run plan, serta konfigurasi workload yang dicatat melalui environment variables.

## Data Penelitian - Bab III

Data penelitian dibentuk melalui pipeline VisDrone-MOT, YOLO tracking, dan konversi ke SQLite. Sequence citra VisDrone-MOT diproses menggunakan model YOLO dengan tracking untuk menghasilkan file prediksi dalam format MOT. File prediksi tersebut kemudian diproses oleh `build_detection_db.py` menjadi database SQLite. Database ini menyimpan hubungan antara sequence, image, detection, track, dan class. Untuk kebutuhan k6, `build_id_pool.py` mengekspor daftar image id per density tier dan daftar track multi-frame ke `scratch/id_pool.json`.

## Bab IV - Pembuka APE

APE dikembangkan sebagai aplikasi pendukung eksperimen yang memastikan REST dan GraphQL diuji pada kondisi yang setara. APE terdiri dari REST server, GraphQL server, shared data-access layer, SQLite corpus, cache layer Varnish, workload generator k6, orchestrator eksperimen, dan telemetry sampler. Dengan komponen tersebut, eksperimen dapat dijalankan secara berulang, dikontrol melalui run plan, serta menghasilkan metrik yang dapat dianalisis secara statistik.

## Bab V - Framing Hasil

Hasil penelitian disajikan dalam dua kelompok. Kelompok pertama adalah hasil uji pendahuluan yang digunakan untuk memvalidasi kesiapan instrument dan membaca kecenderungan awal performa REST dan GraphQL. Kelompok kedua adalah hasil eksperimen utama yang menjadi dasar pembahasan research question. Pemisahan ini dilakukan agar hasil pilot tidak dicampur dengan hasil utama yang memiliki desain faktor lebih lengkap.
