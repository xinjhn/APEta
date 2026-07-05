# Figure Register

Register ini berfungsi sebagai kendali mutu gambar. Setiap gambar harus punya
alasan, dasar referensi, dan caption yang siap dipindahkan ke template Word.

Status:

- `draft`: sudah ada konsep/sumber awal, masih perlu review visual.
- `ready-source`: sumber diagram awal tersedia di `figures/src`.
- `later`: dibuat setelah data hasil final tersedia.

| No. | Rencana Nomor | Judul | Bab | Jenis | Tujuan | Basis Referensi | File Sumber | Status |
|---|---|---|---|---|---|---|---|---|
| 1 | Gambar I.1 | Alur besar penelitian APE | I | BPMN-style process | Membantu pembaca melihat perjalanan dari studi literatur sampai laporan | OMG BPMN 2.0.2 | `figures/src/fig_01_research_workflow_bpmn_style.mmd` | ready-source |
| 2 | Gambar I.2 | Alur uji pendahuluan menuju eksperimen utama | I/III | BPMN-style process | Menjelaskan kenapa Phase 1 tetap dicatat tetapi Phase 2 menjadi desain utama | OMG BPMN 2.0.2 | `figures/src/fig_02_pilot_to_main_experiment.mmd` | ready-source |
| 3 | Gambar II.1 | Konsep HTTP cache freshness dan validation | II | Conceptual sequence | Menjelaskan cache hit, stale, validation, ETag, dan 304 | RFC 9111 | `figures/src/fig_10_cache_hit_miss_sequence.mmd` | ready-source |
| 4 | Gambar II.2 | Konsep GraphQL selection set terhadap payload | II | Conceptual diagram | Menjelaskan bahwa client menentukan field response | GraphQL Spec | `figures/src/fig_15_graphql_selection_set_payload.mmd` | ready-source |
| 5 | Gambar III.1 | Desain faktor eksperimen Phase 2 | III | Factor map | Menunjukkan variabel bebas dan kombinasi cell | Metodologi eksperimen APE | `figures/src/fig_11_phase2_factor_grid.mmd` | ready-source |
| 6 | Gambar III.2 | Pemetaan variabel bebas, kontrol, dan metrik | III | Concept map | Memisahkan IV, DV, dan controlled variables | Metodologi eksperimen | `figures/src/fig_16_variables_metrics_map.mmd` | ready-source |
| 7 | Gambar III.3 | Pipeline persiapan data VisDrone-YOLO-SQLite | III | BPMN-style process | Menjelaskan asal data dan transformasi corpus | VisDrone, Ultralytics, ByteTrack, SQLite | `figures/src/fig_04_data_preparation_pipeline.mmd` | ready-source |
| 8 | Gambar III.4 | ERD korpus deteksi MOT | III/IV | ERD | Menjelaskan struktur data sequence-image-detection-track-class | Chen ER model, SQLite schema | `figures/src/fig_05_sqlite_erd.mmd` | ready-source |
| 9 | Gambar IV.1 | Arsitektur komponen APE | IV | UML component-style | Menunjukkan REST, GraphQL, DAL, SQLite, Varnish, k6, telemetry | UML 2.5.1 | `figures/src/fig_03_system_architecture_component.mmd` | ready-source |
| 10 | Gambar IV.2 | SSD request REST | IV | SSD | Menjelaskan skenario permintaan REST dari k6 sampai DB | Larman, UML, RFC 9110 | `figures/src/fig_07_rest_ssd.mmd` | ready-source |
| 11 | Gambar IV.3 | SSD request GraphQL POST | IV | SSD | Menjelaskan GraphQL default non-cacheable POST route | Larman, UML, GraphQL Spec | `figures/src/fig_08_graphql_post_ssd.mmd` | ready-source |
| 12 | Gambar IV.4 | SSD GraphQL APQ over GET | IV | SSD | Menjelaskan hash-only request, registration, dan execution | Larman, UML, Apollo APQ | `figures/src/fig_09_graphql_apq_cache_flow_ssd.mmd` | ready-source |
| 13 | Gambar IV.5 | Sequence cache hit dan cache miss | IV | Sequence | Menjelaskan Varnish/origin/cache response | UML, RFC 9111, Varnish docs | `figures/src/fig_10_cache_hit_miss_sequence.mmd` | ready-source |
| 14 | Gambar IV.6 | Orkestrasi eksperimen APE | IV | UML activity/BPMN-style | Menjelaskan run plan, server switching, cache, netem, k6, telemetry, result append | UML/BPMN, k6 docs | `figures/src/fig_06_experiment_orchestration_activity.mmd` | ready-source |
| 15 | Gambar IV.7 | Topologi network namespace dan cache | IV | Deployment/topology | Menjelaskan posisi k6, Varnish, server, dan emulated network | UML deployment-style, RFC 9110 intermediaries | `figures/src/fig_13_network_namespace_topology.mmd` | ready-source |
| 16 | Gambar IV.8 | Aliran metrik eksperimen | IV/V | Data-flow style | Menjelaskan asal latency, payload, cache-hit, CPU/RSS, CSV | k6 docs, psutil/tool implementation | `figures/src/fig_14_measurement_streams.mmd` | ready-source |
| 17 | Gambar V.1 | Pipeline analisis hasil | V | Activity/data pipeline | Menjelaskan results.csv menjadi statistik dan figure hasil | Mann-Whitney, Vargha-Delaney, Arcuri & Briand | `figures/src/fig_12_analysis_pipeline.mmd` | ready-source |
| 18 | Gambar V.2 | Crossover surface latency | V | Heatmap | Menampilkan REST-minus-GraphQL terhadap cache-hit dan payload | Hasil `tools/analyze_phase2.py` | generated after final run | later |
| 19 | Gambar V.3 | Entropy vs cache-hit rate | V | Bar/box plot | Menguji H3 tentang variasi query shape dan cache-hit | Hasil `tools/analyze_phase2.py` | generated after final run | later |
| 20 | Lampiran | Struktur file workspace eksperimen | Lampiran | Tree/table | Membantu replikasi oleh pembaca | Implementasi workspace | `reproducibility/WORKSPACE_INVENTORY.md` | ready-source |

## Caption Siap Pakai

### Gambar I.1

Alur besar penelitian APE dari studi literatur, pengembangan instrument
eksperimen, pelaksanaan Phase 1, audit metodologi, perancangan Phase 2, sampai
analisis hasil. Sumber: diolah penulis berdasarkan proses penelitian; notasi
proses mengacu pada BPMN 2.0.2.

### Gambar I.2

Alur uji pendahuluan menuju eksperimen utama. Uji pendahuluan diposisikan
sebagai tahap validasi instrument dan pembacaan variabilitas awal, sedangkan
Phase 2 menjadi eksperimen utama dengan kontrol caching, pola akses, payload,
entropi query, dan jaringan. Sumber: diolah penulis berdasarkan hasil audit
implementasi APE; notasi proses mengacu pada BPMN 2.0.2.

### Gambar III.4

Entity Relationship Diagram korpus deteksi MOT yang digunakan oleh APE. Tabel
`sequence`, `image`, `detection`, `track`, dan `class` disusun dari hasil
tracking YOLO/VisDrone ke dalam SQLite. Sumber: diolah penulis berdasarkan
schema `mot_detections.db`; konsep ERD mengacu pada Chen.

### Gambar IV.2

System Sequence Diagram permintaan data melalui REST. Aktor eksternal memanggil
endpoint REST, server mengambil data melalui shared DAL, lalu mengembalikan
representasi JSON dengan header cache yang sesuai. Sumber: diolah penulis
berdasarkan implementasi APE; pemodelan SSD mengacu pada Larman dan notasi
sequence diagram mengacu pada UML 2.5.1.

### Gambar IV.4

System Sequence Diagram GraphQL APQ over GET. Client mencoba request hash-only,
server mengembalikan `PersistedQueryNotFound` jika hash belum dikenali, lalu
client melakukan registrasi query dan request berikutnya dapat memakai hash
yang sama. Sumber: diolah penulis berdasarkan implementasi APE dan dokumentasi
Apollo APQ; pemodelan SSD mengacu pada Larman dan UML 2.5.1.

### Gambar IV.5

Urutan cache hit dan cache miss pada eksperimen dengan Varnish. Cache hit
mengembalikan respons dari cache, sedangkan cache miss meneruskan request ke
origin server dan menyimpan respons cacheable. Sumber: diolah penulis
berdasarkan implementasi APE, Varnish, dan RFC 9111.

