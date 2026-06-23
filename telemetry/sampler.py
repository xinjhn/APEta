"""
telemetry/sampler.py
====================
Sampler utilisasi CPU & memori berbasis psutil (FR-08), dijalankan sebagai
PROSES TERPISAH yang menyampel PID server.

Keputusan operasionalisasi (Keputusan 2, metrik sekunder):
1. CPU PER-PROSES, bukan system-wide. Karena k6 berbagi mesin, cpu_percent
   system-wide akan terkontaminasi beban k6. `psutil.Process(pid).cpu_percent()`
   mengisolasi konsumsi server saja.
2. Proses TERPISAH yang di-`taskset` ke core cadangan (di luar core server & k6)
   -> meminimalkan observer effect sekaligus menghindari kontaminasi.
3. Sampling 1 Hz; tiap baris ber-timestamp UNIX agar dapat di-JOIN ke jendela
   waktu tiap run (orchestrator mencatat ts_start/ts_end di sekitar proses k6
   penuh -- lihat `run_experiment.py::telemetry_stats()`). CATATAN AKURASI:
   jendela ini adalah batas wall-clock proses k6 SECARA UTUH, BUKAN jendela
   steady-state yang sudah ditrim dari transien startup (mis. pembukaan koneksi
   serentak oleh puluhan VU di awal run). Pada interval sampling 1 Hz dan durasi
   run 60s, transien ini mencakup ~1-2 sampel dari ~60 -- dampaknya kecil tapi
   TIDAK NOL, terutama pada `cpu_p95`/`rss_p95_mb`. Bila ingin jendela
   steady-state murni, tambahkan logam pencatatan ts_steady_start/end terpisah
   di orchestrator sebelum mengandalkan klaim ini.

Pemakaian (dipanggil orchestrator, idealnya dengan taskset):
    taskset -c 31 python telemetry/sampler.py --pid <PID_SERVER> \
        --out results/telemetry.csv --interval 1.0
"""
from __future__ import annotations

import argparse
import csv
import os
import time

import psutil


def sample_loop(pid: int, out_path: str, interval: float) -> None:
    proc = psutil.Process(pid)
    # Priming: panggilan cpu_percent pertama selalu 0.0 (butuh baseline interval).
    proc.cpu_percent(interval=None)

    new_file = not os.path.exists(out_path)
    with open(out_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["unix_ts", "pid", "cpu_percent", "rss_mb"])
        try:
            while proc.is_running():
                ts = time.time()
                cpu = proc.cpu_percent(interval=None)  # per-proses, bisa >100% (multi-core)
                rss_mb = proc.memory_info().rss / (1024 * 1024)
                writer.writerow([f"{ts:.3f}", pid, f"{cpu:.2f}", f"{rss_mb:.2f}"])
                f.flush()  # tulis inkremental: aman bila VM mati mendadak
                time.sleep(interval)
        except (psutil.NoSuchProcess, KeyboardInterrupt):
            pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, required=True, help="PID proses server")
    ap.add_argument("--out", required=True, help="path CSV keluaran")
    ap.add_argument("--interval", type=float, default=1.0, help="detik antar sampel")
    args = ap.parse_args()
    sample_loop(args.pid, args.out, args.interval)


if __name__ == "__main__":
    main()
