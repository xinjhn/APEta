# Table Register

Daftar tabel ini melengkapi figure register. Tabel dipilih karena membantu
pembaca mengecek definisi, parameter, dan replikasi eksperimen.

| Rencana Nomor | Judul | Bab | Tujuan | Sumber Data |
|---|---|---|---|---|
| Tabel I.1 | Ringkasan masalah, dampak, dan solusi penelitian | I | Menjelaskan problem statement secara padat | Narasi penelitian |
| Tabel I.2 | Stakeholder dan manfaat penelitian | I | Menjawab bagian pemangku kepentingan | Analisis penulis |
| Tabel II.1 | Literatur sejenis REST vs GraphQL | II | Membandingkan penelitian terdahulu | Paper REST/GraphQL |
| Tabel II.2 | Ringkasan standar dan dokumentasi teknis | II | Menjelaskan basis RFC, GraphQL, UML, BPMN, APQ | `REFERENCES_BASIS.md` |
| Tabel III.1 | Variabel penelitian Phase 1 | III | Mendokumentasikan pilot study | `results/run_plan.csv`, `results/results.csv` |
| Tabel III.2 | Variabel penelitian Phase 2 | III | Mendokumentasikan desain utama | `orchestrator/config.py` |
| Tabel III.3 | Metrik eksperimen dan cara pengukurannya | III | Menjelaskan DV dan asal metrik | `k6/workload.js`, `telemetry/sampler.py`, `run_experiment.py` |
| Tabel III.4 | Ringkasan korpus SQLite | III | Menjelaskan data penelitian | `mot_detections.db` |
| Tabel III.5 | Controlled variables | III | Menjaga fairness eksperimen | Implementasi APE |
| Tabel III.6 | Pilot pemilihan optimizer training YOLO26 (laju iterasi di T4) | III | Mendokumentasikan pemilihan konfigurasi training detektor secara empiris | `reproducibility/PILOT_TRAINING_YOLO26.md`, `training/pilots/2026-07-07_optimizer_pace/pace_summary.csv` |
| Tabel IV.1 | Endpoint REST dan query GraphQL yang ekuivalen | IV | Membuktikan parity fungsional | `rest_server.py`, `graphql_server.py`, `k6/workload.js` |
| Tabel IV.2 | Modul APE dan tanggung jawabnya | IV | Menjelaskan implementasi aplikasi pendukung | Workspace inventory |
| Tabel IV.3 | Konfigurasi environment variable | IV | Membantu replikasi | `orchestrator/config.py`, `k6/workload.js` |
| Tabel IV.4 | Acceptance checks dan status validasi | IV | Menjelaskan parity/fairness tests | `tests/`, `tools/verify_*` |
| Tabel V.1 | Ringkasan hasil Phase 1 | V | Mendokumentasikan hasil awal dan temuan tak terduga | `results/results.csv` |
| Tabel V.2 | Ringkasan hasil Phase 2 per cell | V | Hasil utama eksperimen | `results/phase2/results.csv` jika sudah lengkap |
| Tabel V.3 | Hasil uji statistik per metrik | V | Menjawab RQ secara inferensial | `tools/analyze_phase2.py` |
| Tabel V.4 | Threats to validity dan mitigasi | V/VI | Transparansi ilmiah | Analisis penulis |
| Tabel VII.1 | Saran penelitian lanjutan | VII | Menutup laporan dengan future work | Pembahasan |

| Tabel L.1 | Hasil per-sel REST vs GraphQL — studi skenario MOT | Lampiran 4 | Detail per-sel pendukung Bab V | `results/mot-scenarios-core/analysis/mot_comparisons.csv` |
| Tabel L.2 | Hasil per-blok REST vs GraphQL — grid inti caching; baris CPU/RSS dari re-run phase2-core-clean (telemetri valid, ditambahkan 2026-07-10) | Lampiran 5 | Detail per-blok RQ2 + sumber daya server | `results/phase2-core-real/analysis/`, `results/phase2-core-clean/analysis/phase2_comparisons.csv` |
