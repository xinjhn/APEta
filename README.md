# Alat Pembantu Eksperimen (APE) — REST vs GraphQL atas Output YOLO26

Implementasi server, modul inti, dan instrumen untuk eksperimen perbandingan
REST API vs GraphQL pada penyajian data deteksi objek (skema VCD, dataset
VisDrone). Kode ini mewujudkan keputusan desain yang sudah dikunci; tiap berkas
diberi komentar yang menautkannya ke laporan/PANDUAN agar dapat dipertanggungjawabkan.

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
├── rest_server.py           # FastAPI: 4 endpoint, kerja sisi-server nyata
├── graphql_server.py        # Strawberry: tipe & resolver NYATA, snake_case, JSON kompak
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
   dibuat KOMPAK menyamai REST. Hasil verifikasi: selisih payload REST vs GraphQL
   tinggal **30 byte konstan** = amplop `{"data":{...}}` GraphQL (genuine, tidak
   menskala dengan densitas).
5. **Server-side selection + seed**: server memilih citra acak; `seed` opsional
   membuat pilihan deterministik (untuk reproducibility & uji paritas).

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
  overhead resolver — Cha et al., 2020).
- Sinyal over-fetching: payload S2 turun ~44% dari S1 (membuang `bounding_box`).
- Payload S4 ≈ 396 byte vs S1 ≈ 11 KB (pola agregasi mengukur proses, bukan transfer).
- Filtered kasus langka -> array kosong VALID (bukan error).

> Angka di atas dari DATA SINTETIS untuk verifikasi fungsional, bukan hasil
> eksperimen. Hasil eksperimen sebenarnya menggunakan JSON inferensi final dan
> dieksekusi via k6 + orchestrator (tahap berikutnya).

## Yang BELUM dibuat (tahap berikut)

- Skrip k6 per pola (kirim `density`, baca header `X-Process-Time`).
- Orchestrator 3-lapis (run_plan.csv seed 42 + resume + results.csv inkremental).
- `tools/profile_dataset.py` final (verifikasi Q1/Q3 dari output model -> Tabel IV.1).
