# Setup VM (Linux) untuk eksekusi APE

Langkah ini dijalankan SEKALI per VM (governor & versi k6) dan SEKALI per sesi
eksekusi (urutan preflight -> selftest pinning -> pilot -> eksekusi penuh).
Tidak ada langkah ber-`sudo` yang dijalankan otomatis oleh skrip -- semua
perintah di bawah dijalankan manual oleh operator.

## 1. CPU governor = `performance`

Governor non-`performance` (mis. `powersave`, `ondemand`) membuat frekuensi
CPU naik-turun mengikuti beban -- ini sumber noise yang TIDAK BOLEH ada di
data eksperimen (sebuah run bisa lambat hanya karena CPU belum naik clock).

Cek governor saat ini (semua core):
```bash
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

Set ke `performance` (butuh sudo, paket `linux-tools-common`/`cpupower` atau
tulis langsung ke sysfs):
```bash
sudo cpupower frequency-set -g performance
# atau, bila cpupower tidak ada:
for f in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
  echo performance | sudo tee "$f" > /dev/null
done
```
Verifikasi ulang dengan perintah cek di atas -- semua baris harus `performance`.
`orchestrator/run_experiment.py --preflight` membaca `cpu0` dan akan **FAIL**
bila bukan `performance` saat `APE_ENABLE_PINNING=1`.

> Catatan: pada beberapa VM cloud, governor mungkin terkunci `performance`
> secara default oleh hypervisor (tidak ada `cpufreq` sama sekali) -- dalam
> kasus itu `scaling_governor` tidak akan terbaca; preflight akan FAIL dengan
> pesan "tidak bisa membaca scaling_governor", yang aman untuk diabaikan
> SETELAH dikonfirmasi manual bahwa clock CPU memang tetap (mis. cek
> `lscpu | grep MHz`).

## 2. Bekukan versi k6

Jangan jalankan `apt upgrade`/`k6 upgrade` di antara sesi -- versi k6 yang
berbeda bisa mengubah karakteristik beban (lihat catatan kompatibilitas
`URLSearchParams` yang sudah ditemukan di pilot Windows). `run_experiment.py`
mencatat `k6 version` ke `results/logs/session_<id>.log` setiap sesi --
**bandingkan log antar sesi**; bila berbeda, jangan gabungkan datanya tanpa
catatan tambahan di laporan.

Cara mengunci versi (Debian/Ubuntu, contoh dengan APT pin):
```bash
k6 version   # catat versi yang sedang terpasang
echo 'Package: k6
Pin: version <versi-yang-tercatat>
Pin-Priority: 1001' | sudo tee /etc/apt/preferences.d/k6-pin
```
Atau lebih sederhana: jangan jalankan `apt update && apt upgrade` sama sekali
selama masa eksperimen berjalan di VM ini.

## 3. Template `APE_*` untuk eksekusi penuh

```bash
export APE_POOL_JSON="/path/ke/inferensi_final.json"   # WAJIB ganti dari data sintetis
export APE_SEED=42
export APE_N_WARMUP=3
export APE_N_MEASURED=30                                 # final dari hasil pilot, bukan 3
export APE_RUN_DURATION=30s                               # final dari hasil pilot, bukan 10s
export APE_CONCURRENCY_LEVELS=10,50,100
export APE_DENSITIES=low,medium,high
export APE_PATTERNS=baseline,partial,filtered,aggregate
export APE_HOST=127.0.0.1
export APE_PORT=8000
export APE_SESSION_ID="vm-session-01"                      # unik per sesi (uji efek antar-sesi)
export APE_RESULTS_DIR="/path/ke/results"
export APE_PILOT=0
export APE_ENABLE_PINNING=1
export APE_SERVER_CORES="0-7"     # contoh -- sesuaikan topologi VM, JANGAN tumpang tindih
export APE_K6_CORES="8-15"
export APE_SAMPLER_CORE="31"
```
Pastikan `APE_SERVER_CORES`/`APE_K6_CORES`/`APE_SAMPLER_CORE` TIDAK tumpang
tindih satu sama lain -- `--preflight` memeriksa ini otomatis.

## 4. Urutan wajib sebelum eksekusi penuh

```bash
cd /path/ke/ape

# 1) Preflight -- harus PASS sebelum lanjut
python orchestrator/run_experiment.py --preflight

# 2) Selftest pinning -- HANYA berlaku/berarti di Linux dengan ENABLE_PINNING=1
python orchestrator/run_experiment.py --selftest-pinning
#   Output yang diharapkan: "PASS" + cpu_affinity tercetak sama dengan
#   APE_SERVER_CORES. Bila FAIL, JANGAN lanjut ke eksekusi penuh.

# 3) Pilot pendek (subset kecil, untuk kalibrasi N_MEASURED/RUN_DURATION final)
APE_PILOT=1 python orchestrator/make_run_plan.py
APE_PILOT=1 python orchestrator/run_experiment.py
APE_PILOT=1 python tools/validate_results.py --run-plan results/run_plan.csv --results results/results.csv

# 4) Paritas tetap wajib hijau sebelum eksekusi penuh
python tests/test_parity.py

# 5) Eksekusi penuh (APE_PILOT=0, knob final dari bagian 3 di atas)
python orchestrator/make_run_plan.py
python orchestrator/run_experiment.py
#   Bila terputus (hard-kill/reboot/listrik), JALANKAN ULANG perintah yang
#   SAMA -- reaping orphan + resume berjalan otomatis, TIDAK perlu
#   membebaskan port manual.

# Selama berjalan (sesi terpisah, mis. lewat `tmux`/`screen` lain):
python orchestrator/run_experiment.py --status
tail -f results/logs/progress.log
```

## 5. Perintah yang HARUS dijalankan sekali oleh operator (belum teruji di Windows)

Dua hal ini secara desain hanya bermakna di Linux dan tidak bisa divalidasi
di laptop Windows lokal -- jalankan SEKALI di VM dan laporkan outputnya:

```bash
# (a) Preflight penuh dengan pinning aktif
APE_ENABLE_PINNING=1 APE_SERVER_CORES="0-7" APE_K6_CORES="8-15" APE_SAMPLER_CORE="31" \
    python orchestrator/run_experiment.py --preflight
# Harapan: "PREFLIGHT PASS", termasuk baris [PASS] cpu_governor: performance
# dan [PASS] cores_overlap: tidak ada tumpang tindih.

# (b) Pinning self-test
APE_ENABLE_PINNING=1 APE_SERVER_CORES="0-7" \
    python orchestrator/run_experiment.py --selftest-pinning
# Harapan: baris "Actual cpu_affinity(pid=...): [0, 1, 2, 3, 4, 5, 6, 7]"
# lalu "PASS".
```
Jangan menganggap pinning "sudah teruji" sampai kedua perintah di atas
benar-benar dijalankan di VM dan outputnya PASS.
