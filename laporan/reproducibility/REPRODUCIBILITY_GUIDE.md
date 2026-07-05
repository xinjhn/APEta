# Reproducibility Guide

Panduan ini menjelaskan cara mereplikasi alur eksperimen berdasarkan workspace
yang ada. Perintah perlu dijalankan dari `/home/ubuntu/APE/APEta` kecuali
disebutkan lain.

## 1. Prinsip Replikasi

- Gunakan direktori hasil terpisah untuk setiap sesi eksperimen.
- Jangan menimpa `results/results.csv` lama sebelum disalin/diarsipkan.
- Bedakan Phase 1 sebagai studi pendahuluan dan Phase 2 sebagai desain utama.
- Catat semua environment variables yang digunakan.
- Jalankan server dengan single worker untuk menjaga fairness.
- Gunakan corpus SQLite yang sama untuk REST dan GraphQL.

## 2. Environment Python

Dependensi APE tercatat pada:

```bash
requirements.txt
```

Instalasi umum:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Jika memakai conda environment yang sudah ada, dokumentasikan nama environment,
versi Python, dan hasil `pip freeze`.

## 3. Corpus Data

Corpus utama:

```bash
/home/ubuntu/training/mot_detections.db
```

Membangun ulang corpus dari prediction files:

```bash
cd /home/ubuntu/training
python build_detection_db.py \
  --pred-dir mot_val_predictions_tracked_conf001 \
  --out mot_detections.db
```

Membangun ID pool untuk k6 Phase 2:

```bash
cd /home/ubuntu/APE/APEta
python tools/build_id_pool.py \
  --db /home/ubuntu/training/mot_detections.db \
  --out scratch/id_pool.json
```

Verifikasi ringkas corpus:

```bash
sqlite3 /home/ubuntu/training/mot_detections.db \
  "select 'sequence', count(*) from sequence union all select 'image', count(*) from image union all select 'track', count(*) from track union all select 'detection', count(*) from detection;"
```

## 4. Phase 1 - Studi Pendahuluan

Phase 1 menggunakan matrix lama:

- `protocol`: REST, GraphQL.
- `pattern`: baseline, partial, filtered, aggregate.
- `density`: low, medium, high.
- `concurrency`: level VU.

File hasil yang ada:

```bash
results/run_plan.csv
results/results.csv
```

Dalam laporan, Phase 1 direkomendasikan sebagai:

- preliminary experiment,
- methodological audit,
- dasar perubahan ke Phase 2,
- bukan klaim final utama.

## 5. Phase 2 - Desain Utama

Konfigurasi utama ada di:

```bash
orchestrator/config.py
orchestrator/make_run_plan.py
orchestrator/run_experiment.py
k6/workload.js
```

Faktor Phase 2:

- `protocol`: rest, graphql.
- `caching`: on, off.
- `access_pattern`: unique, uniform, zipfian.
- `entropy`: low, medium, high.
- `payload_weight`: light, heavy.
- `network`: lan, constrained.
- `density`: low, medium, high.
- `concurrency`: VU levels.

Membuat run plan core grid:

```bash
APE_RESULTS_DIR=results/phase2 \
APE_GRID=core \
python orchestrator/make_run_plan.py
```

Menjalankan preflight:

```bash
APE_DB_PATH=/home/ubuntu/training/mot_detections.db \
APE_ID_POOL_JSON=/home/ubuntu/APE/APEta/scratch/id_pool.json \
APE_RESULTS_DIR=results/phase2 \
python orchestrator/run_experiment.py --preflight
```

Menjalankan eksperimen:

```bash
APE_DB_PATH=/home/ubuntu/training/mot_detections.db \
APE_ID_POOL_JSON=/home/ubuntu/APE/APEta/scratch/id_pool.json \
APE_RESULTS_DIR=results/phase2 \
APE_SESSION_ID=phase2-main \
python orchestrator/run_experiment.py
```

Catatan:

- Network namespace, Varnish, netem, dan systemd-run dapat membutuhkan akses
  `sudo` atau kapabilitas OS tertentu.
- Gunakan hasil `--preflight` untuk memastikan tooling tersedia sebelum run.

## 6. Manual Server Smoke Test

REST:

```bash
APE_DB_PATH=/home/ubuntu/training/mot_detections.db \
uvicorn rest_server:app --workers 1 --host 127.0.0.1 --port 8000
```

GraphQL:

```bash
APE_DB_PATH=/home/ubuntu/training/mot_detections.db \
uvicorn graphql_server:app --workers 1 --host 127.0.0.1 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

## 7. Analisis Hasil

Analisis Phase 2:

```bash
python tools/analyze_phase2.py \
  --input results/phase2/results.csv \
  --output-dir results/phase2/analysis
```

Output yang diharapkan:

- tabel pairwise per metrik,
- report analisis,
- plot deskriptif,
- crossover surface,
- entropy vs cache-hit rate.

## 8. Checklist Bukti untuk Lampiran

Simpan atau screenshot:

- commit hash atau `git status`.
- `requirements.txt` dan/atau `pip freeze`.
- `run_plan.csv`.
- `results.csv`.
- folder `k6_summaries`.
- folder `telemetry`.
- command run yang dipakai.
- konfigurasi environment variables.
- hasil analysis report.

## 9. Risiko Replikasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Phase 1 dan Phase 2 tercampur | Klaim hasil menjadi tidak jelas | Pisahkan bab/subbab dan results directory |
| Run plan diregenerasi di tengah eksperimen | Resume tidak valid | Gunakan fresh results dir per grid |
| Cache layer salah port | Caching on/off tertukar | Log `BASE_URL` dan `caching` per row |
| Query shape entropy tidak dikontrol | Cache-hit rate bias | Gunakan `k6/workload.js` sesuai env |
| Network emulation menunda hop yang salah | Kesimpulan jaringan bias | Gunakan netns topology untuk run utama |
| Dataset berubah | Hasil tidak replikabel | Catat hash/ukuran DB dan counts |

