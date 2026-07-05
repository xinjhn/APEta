# Alat Pembantu Eksperimen (APE) — REST vs GraphQL atas Output YOLO26

Implementasi server, modul inti, dan instrumen untuk eksperimen perbandingan
REST API vs GraphQL pada penyajian data deteksi objek (skema VCD, dataset
VisDrone). Kode ini mewujudkan keputusan desain yang sudah dikunci; tiap berkas
diberi komentar yang menautkannya ke laporan/PANDUAN agar dapat dipertanggungjawabkan.

## FAKTORIAL DESAIN (Path B - Symmetric Baselines)

Eksperimen ini menggunakan **desain faktorial 2×2** untuk mengisolasi efek protokol
dari efek implementasi:

| Faktor | Level 1 | Level 2 |
|--------|---------|---------|
| **Protocol** | REST | GraphQL |
| **Type Safety** | passthrough (zero-copy) | typed (object reconstruction) |

Ini menghasilkan **4 kondisi eksperimental**:
1. REST + passthrough (baseline cepat)
2. REST + typed (biaya type safety di REST)
3. GraphQL + typed (baseline lambat)
4. GraphQL + passthrough (biaya protokol murni GraphQL)

**Kontrol via environment variables:**
- `APE_IMPL_MODE_REST=passthrough|typed`
- `APE_IMPL_MODE_GRAPHQL=typed|passthrough`

Lihat bagian **"Menjalankan Eksperimen Faktorial"** di bawah untuk detail.

## Struktur

```
ape/
├── core/                    # SELURUH logika non-protokol (dipakai identik 2 server)
│   ├── config.py            # tier densitas, spesifikasi 4 pola (KONSTAN lintas tier)
│   ├── pool.py              # In-Memory Pool: Singleton, load deterministik, stratifikasi
│   ├── selection.py         # pemilihan citra acak sisi-server (anti-cache)
│   ├── access.py            # titik akses data tunggal (Shared Funnel) + seed
│   ├── filters.py           # predikat S3 (BERSAMA -> paritas filter by construction)
│   ├── projection.py        # proyeksi field S2 (BERSAMA -> sparse fieldset REST nyata)
│   ├── aggregate.py         # agregasi S4 (BERSAMA)
│   └── timing.py            # middleware X-Process-Time (simetris kedua server)
├── rest_server.py           # FastAPI: 4 endpoint, kerja sisi-server nyata (+ mode typed/passthrough)
├── graphql_server.py        # Strawberry: tipe & resolver NYATA, snake_case, JSON kompak (+ mode typed/passthrough)
├── telemetry/sampler.py     # psutil per-proses (proses terpisah, di-taskset)
├── tools/make_synthetic_pool.py   # data sintetis (HANYA smoke test)
├── tests/test_parity.py     # validasi paritas data REST vs GraphQL (4 pola)
└── requirements.txt         # versi terkunci (PANDUAN Bagian 3)
```

## Prinsip fairness yang diwujudkan kode

1. **Shared-core**: filter/proyeksi/agregasi/akses berada di `core/` dan dipanggil
   IDENTIK oleh kedua server. Satu-satunya beda sistematis = lapisan protokol +
   serialisasi. (PANDUAN Bagian 8; matriks justifikasi Blok C.)
2. **REST memfilter/memproyeksi NYATA di server** (bukan kirim-penuh-lalu-buang).
3. **GraphQL memakai tipe & resolver Strawberry sungguhan** (bukan kembalikan
   `dict` mentah) -> overhead resolusi yang dihipotesiskan benar-benar terjadi.
4. **Paritas penamaan & payload**: `auto_camel_case=False` + encoder GraphQL
   dibuat KOMPAK menyamai REST. Hasil verifikasi: selisih payload (RESPONS saja,
   lihat catatan di bawah) untuk S1-S3 (field GraphQL `image_detections`) tinggal
   **30 byte konstan** = amplop `{"data":{...}}` GraphQL; untuk S4 (field
   `aggregate`, nama lebih pendek) selisihnya **23 byte** -- konstan PER POLA,
   bukan satu angka tunggal lintas pola, dan TIDAK menskala dengan densitas.
   Catatan scope: angka ini mengukur RESPONS (downlink) saja. GraphQL juga
   menanggung overhead REQUEST (uplink) tambahan ~68-133 byte (mengirim teks
   query penuh per request) yang tidak terukur oleh metrik `payload_bytes_med`
   k6 -- lihat keterbatasan di laporan/PANDUAN Bagian fairness.
5. **Server-side selection + seed**: server memilih citra acak; `seed` opsional
   membuat pilihan deterministik (untuk reproducibility & uji paritas).
6. **Faktorial simetri**: Kedua server mendukung mode `typed` (rekonstruksi objek)
   dan `passthrough` (zero-copy), memungkinkan isolasi efek protokol dari efek
   implementasi melalui desain 2×2.

## Cara menjalankan

### 1. Siapkan data
Eksperimen: pakai JSON inferensi YOLO26 final (Tahap [A]). Untuk smoke test:
```bash
python tools/make_synthetic_pool.py --out /tmp/synthetic.json --n 300 --seed 42
```

### 2. Validasi paritas (WAJIB sebelum eksekusi beban)
```bash
APE_POOL_JSON=/tmp/synthetic.json python tests/test_parity.py
# -> "Paritas: 48/48 kombinasi identik."
```

### 3. Jalankan server (BERGANTIAN, single worker)
REST:
```bash
APE_POOL_JSON=/path/inferensi.json uvicorn rest_server:app \
    --workers 1 --host 127.0.0.1 --port 8000
```
GraphQL (matikan REST dulu):
```bash
APE_POOL_JSON=/path/inferensi.json uvicorn graphql_server:app \
    --workers 1 --host 127.0.0.1 --port 8000
```
Dengan CPU pinning (PANDUAN Bagian 2), bungkus dengan `taskset -c 0-15`.

### 4. Telemetri (proses terpisah, core cadangan)
```bash
taskset -c 31 python telemetry/sampler.py --pid <PID_SERVER> \
    --out results/telemetry.csv --interval 1.0
```

## Menjalankan Eksperimen Faktorial (Path B)

**KOREKSI (audit metodologis, lihat METHODOLOGICAL_VERIFICATION.md):** versi
sebelumnya dokumen ini menjalankan 4 sesi yang HANYA mengisi SATU dari dua env
var mode per sesi, membiarkan var lainnya jatuh ke default
(`APE_IMPL_MODE_REST` default `passthrough`, `APE_IMPL_MODE_GRAPHQL` default
`typed`). Karena `run_experiment.py` SELALU menjalankan REST+GraphQL bergantian
dalam satu sesi, itu sebenarnya mengumpulkan sel `(rest,passthrough)` TIGA
KALI (redundan) dan tidak pernah sengaja menjangkau seluruh 4 sel 2x2. Cukup
**2 sesi**, dgn KEDUA env var diisi eksplisit setiap kali:

**KRITIS -- WAJIB pakai `APE_RESULTS_DIR` TERPISAH per sesi:** `_run_uid()`
(make_run_plan.py) hash dari `protocol|pattern|density|concurrency|is_warmup|
run_index` -- TIDAK menyertakan `session_id` atau `impl_mode`. Bila Sesi A & B
berbagi `results_dir` yang sama, run_uid Sesi B akan IDENTIK dgn run_uid Sesi A.
`find_resume_index()` akan melihat semuanya "sudah selesai" dari results.csv
Sesi A dan Sesi B akan SELESAI INSTan TANPA MENULIS BARIS APAPUN -- gagal
senyap, tanpa error, kehilangan seluruh waktu run. WAJIB direktori terpisah:

### Sesi A: REST & GraphQL keduanya passthrough
```bash
APE_POOL_JSON=/path/to/inferensi.json \
APE_IMPL_MODE_REST=passthrough APE_IMPL_MODE_GRAPHQL=passthrough \
APE_SESSION_ID=factorial-A APE_RESULTS_DIR=results/factorial-A \
python orchestrator/run_experiment.py
```
Menghasilkan sel `(rest,passthrough)` + `(graphql,passthrough)`.

### Sesi B: REST & GraphQL keduanya typed
```bash
APE_POOL_JSON=/path/to/inferensi.json \
APE_IMPL_MODE_REST=typed APE_IMPL_MODE_GRAPHQL=typed \
APE_SESSION_ID=factorial-B APE_RESULTS_DIR=results/factorial-B \
python orchestrator/run_experiment.py
```
Menghasilkan sel `(rest,typed)` + `(graphql,typed)`.

Sesi A + Sesi B bersama-sama menjangkau SEMUA 4 sel 2x2 tanpa duplikasi
(pasangan mode yang didekopel, mis. A=(passthrough,typed) + B=(typed,passthrough),
juga valid -- yang penting KEDUA env var selalu diisi eksplisit per sesi).

**Setelah kedua sesi selesai**, gabungkan `results.csv` dari masing-masing sesi
(`pd.concat`, TIDAK perlu skrip combine khusus -- `impl_mode` sudah benar
per-baris) dan jalankan **per-cell Mann-Whitney U + Vargha-Delaney A12/Cliff's
delta** (BUKAN two-way ANOVA -- pooling semua sel pattern/density/concurrency
ke satu model adalah pseudo-replikasi, dan ANOVA mengasumsikan normalitas yang
hampir pasti dilanggar latency; lihat `tools/analyze_factorial.py` utk
rasionale & sitasi lengkap) untuk mengisolasi:
- Main effect of protocol (REST vs GraphQL), per sel
- Main effect of implementation (passthrough vs typed), per sel
- Indikasi interaksi (deskriptif -- konfirmasi formal butuh Aligned Rank
  Transform, Wobbrock et al. CHI 2011, di luar lingkup skrip Python ini)

Jalankan: `python tools/analyze_factorial.py --input results_combined.csv`

## Endpoint / Query per pola

| Pola | REST | GraphQL (selection set mengatur field) |
|---|---|---|
| S1 Baseline | `GET /baseline?density=high` | `imageDetections(density){ ...semua field }` |
| S2 Partial | `GET /partial?density=high` | `imageDetections(density){ detections{ class_label confidence_score } }` |
| S3 Filtered | `GET /filtered?density=high` | `imageDetections(density, class_label:"car", min_confidence:0.5){ ... }` |
| S4 Aggregate | `GET /aggregate?density=high` | `aggregate(density){ image_id class_counts{ class_name count } }` |

Parameter `density` ∈ {low, medium, high}. `seed` opsional di semua endpoint/query.

## Hasil verifikasi awal (data sintetis)

- Paritas data: **48/48** kombinasi (3 densitas × 4 seed × 4 pola) identik.
- `X-Process-Time` hadir di kedua server; GraphQL > REST (konsisten dgn hipotesis
  overhead resolver — lihat Seabra, Nazario & Pinto, "REST or GraphQL?: A
  Performance Comparative Study", SBCARS 2019, ACM, DOI 10.1145/3357141.3357149).
- Sinyal over-fetching: payload S2 turun ~44% dari S1 (membuang `bounding_box`).
- Payload S4 ≈ 396 byte vs S1 ≈ 11 KB (pola agregasi mengukur proses, bukan transfer).
- Filtered kasus langka -> array kosong VALID (bukan error).

> Angka di atas dari DATA SINTETIS untuk verifikasi fungsional, bukan hasil
> eksperimen. Hasil eksperimen sebenarnya menggunakan JSON inferensi final dan
> dieksekusi via k6 + orchestrator (tahap berikutnya).

## Rujukan domain (REST vs GraphQL performa empiris)

| Klaim | Rujukan | Venue |
|---|---|---|
| REST unggul di throughput tinggi (>3000 req/s); GraphQL unggul di sebagian aplikasi pada beban rendah | Seabra, Nazario & Pinto (2019), "REST or GraphQL?: A Performance Comparative Study" | SBCARS'19, ACM (DOI 10.1145/3357141.3357149) |
| REST lebih cepat di latency/throughput; GraphQL lebih efisien CPU/memori pada sistem informasi relasional intensif | Lawi, Panggabean & Yoshida (2021) | *Computers* (MDPI), Vol. 10, Art. 138 |
| GraphQL unggul pada konkurensi rendah berkat konsolidasi round-trip pada data relasional; REST unggul pada konkurensi tinggi | Jin, Cordingly, Zhao & Lloyd (2024) | ACM WoSC10 |
| Migrasi REST->GraphQL memangkas ukuran payload median ~99% (byte), ~94% (field) | Brito, Mombach & Valente (2019), "Migrating to GraphQL: A Practical Assessment" | arXiv:1906.07535 / SANER'19 |
| Pemetaan sistematis riset GraphQL (untuk klaim tren riset, bukan satu studi tunggal) | "GraphQL: A Systematic Mapping Study" | *ACM Computing Surveys*, DOI 10.1145/3561818 |

Catatan scope APE: keempat pola (S1-S4) menguji akses satu-sumber non-relasional
pada localhost (RTT jaringan ~0). Keunggulan GraphQL pada literatur di atas
umumnya muncul pada kondisi yang TIDAK diuji di sini -- fan-out relasional
(Jin et al., 2024) atau RTT jaringan signifikan (studi serverless WoSC). Hasil
APE karenanya scoped ke kondisi non-relasional/low-latency, bukan klaim umum
"REST selalu lebih cepat dari GraphQL".

## Yang BELUM dibuat (tahap berikut)

- Skrip k6 per pola (kirim `density`, baca header `X-Process-Time`).
- Orchestrator 3-lapis (run_plan.csv seed 42 + resume + results.csv inkremental).
- `tools/profile_dataset.py` final (verifikasi Q1/Q3 dari output model -> Tabel IV.1).
- `tools/analyze_factorial.py` untuk two-way ANOVA pada hasil 4 kondisi eksperimental.
