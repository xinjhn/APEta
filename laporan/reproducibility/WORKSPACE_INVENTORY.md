# Workspace Inventory

Inventaris ini menjelaskan folder dan file utama yang perlu diketahui pembaca
untuk mereplikasi atau mengaudit penelitian.

## Root Workspace

- `/home/ubuntu/APE/APEta`: kode utama APE.
- `/home/ubuntu/training`: pipeline YOLO/VisDrone, hasil inference, dan corpus
  SQLite.
- `/home/ubuntu/datasets`: dataset VisDrone dan COCO8.
- `/home/ubuntu/miniconda3`: environment dan package lokal, bukan bagian
  laporan kecuali untuk replikasi versi environment.
- `/home/ubuntu/yolov8n.pt`: model YOLO dasar.

## APEta Project

### Server API

- `rest_server.py`: FastAPI REST server dengan endpoint image, detections,
  tracks, trajectory, random image, dan health.
- `graphql_server.py`: Strawberry GraphQL server dengan schema Image,
  Detection, Track, APQ-over-GET, dan health.

### Shared Core

- `core/dal.py`: data-access layer tunggal untuk REST dan GraphQL.
- `core/caching.py`: Cache-Control, ETag, dan freshness check bersama.
- `core/config.py`: konstanta density, field detection, default DB path.
- `core/timing.py`: middleware `X-Process-Time`.

### Experiment Orchestration

- `orchestrator/config.py`: konfigurasi Phase 2 dan environment variables.
- `orchestrator/make_run_plan.py`: pembuat `run_plan.csv`.
- `orchestrator/run_experiment.py`: executor eksperimen, server switching,
  cache, netem, k6, telemetry, resume, dan results append.

### Load Testing

- `k6/workload.js`: workload Phase 2 dengan protocol, access pattern, entropy,
  payload weight, density, APQ, dan metrik k6.
- `k6/load.js`: workload lama Phase 1.
- `k6/load_batch.js`: batch-study workload.

### Tools

- `tools/build_id_pool.py`: membuat `scratch/id_pool.json` dari SQLite.
- `tools/analyze_phase2.py`: analisis statistik Phase 2.
- `tools/analyze_factorial.py`: analisis lama/factorial.
- `tools/analyze_batch_study.py`: analisis batch-study.
- `tools/netns_topology.sh`: setup topology namespace.
- `tools/netem.sh`: network emulation lama/historical.
- `tools/start_varnish.sh`: menjalankan Varnish.
- `tools/validate_results.py`: validasi hasil.
- `tools/verify_factorial_modes.py` dan `tools/verify_factorial_symmetry.py`:
  verifikasi mode pada studi lama.

### Tests

- `tests/test_parity.py`: parity data REST vs GraphQL untuk studi lama.
- `tests/test_cache_fairness.py`: fairness terkait cache.

### Results

- `results/run_plan.csv`: run plan Phase 1 lama yang sudah ada.
- `results/results.csv`: hasil Phase 1 yang sudah ada.
- `results/phase2-pilot/`: pilot kecil Phase 2.
- `results/k6_summaries/`: output ringkasan k6.
- `results/telemetry/`: output sampler CPU/RSS.

## Training and Dataset

- `training/infer_mot_track.py`: menjalankan YOLO tracking pada VisDrone MOT.
- `training/build_detection_db.py`: membangun `mot_detections.db`.
- `training/mot_detections.db`: corpus relasional utama.
- `training/visdrone.yaml`: konfigurasi dataset untuk training YOLO.
- `training/yolo26n.pt`: model YOLO.
- `datasets/VisDrone/VisDrone2019-DET-train`: dataset DET train.
- `datasets/VisDrone/VisDrone2019-DET-val`: dataset DET val.
- `datasets/VisDrone/VisDrone2019-MOT-val`: dataset MOT val.

## Current Corpus Counts

Hasil query terhadap `training/mot_detections.db`:

| Tabel | Jumlah |
|---|---:|
| sequence | 7 |
| image | 2.846 |
| track | 5.429 |
| detection | 104.767 |

