# Pilot: Pemilihan Konfigurasi Training YOLO26 (Optimizer & Laju Iterasi)

Tanggal: 2026-07-07 · Hardware: Tesla T4 16GB (VM 32 vCPU) ·
Artefak: `training/pilots/2026-07-07_optimizer_pace/` ·
Kandidat register: **Tabel III.6**

## 1. Latar Belakang

Retraining YOLO26n dengan protokol resmi VisDrone-DET (run3: train = seluruh
split TRAIN 6.471 citra, val = split VAL resmi 548 citra) dimulai dengan
konfigurasi yang identik dengan run1/run2 (Juni 2026). Laju iterasi yang
terukur adalah **1,2 s/iterasi**, sekitar **4× lebih lambat** dari baseline
Juni (run2: ~0,31 s/iterasi pada batch dan resolusi yang sama, dihitung dari
kolom `time` di `results.csv`). Pada laju itu, plafon 200 epoch berarti ~5 hari
wall-clock di T4. Pilot ini dijalankan untuk menemukan penyebabnya dan
menetapkan konfigurasi training final secara empiris.

## 2. Metode

1. **Profiling proses hidup.** Sampling stack thread utama (py-spy) menunjukkan
   waktu dominan di assigner TAL (`ultralytics/utils/tal.py:get_box_metrics`),
   dengan CPU utama ~100% satu core, GPU mayoritas idle.
2. **Eliminasi penyebab tingkat sistem.** Setiap kandidat diperiksa langsung
   (bukan diasumsikan) — lihat Tabel B.
3. **A/B satu variabel.** Sel-sel pengukuran dijalankan sebagai training
   singkat pada data dan resolusi sungguhan (imgsz=1280, batch=4, mosaic
   aktif); laju dibaca pada iterasi ke-100+ epoch pertama, cukup jauh dari
   fase pemanasan dataloader. GPU dipastikan kosong di antara sel.

Catatan metodologis yang jujur: hipotesis pertama (flag `deterministic`)
ternyata **keliru** karena pengujian awal tidak sengaja mengubah dua variabel
sekaligus (`deterministic` dan `epochs`). Kekeliruan itu baru terlihat ketika
"perbaikan" tersebut tidak mengubah laju pada run sesungguhnya, dan bisect
diulang dengan disiplin satu-variabel. Rangkaian sel di bawah adalah hasil
bisect yang sudah bersih.

## 3. Hasil

### Tabel A — Sel pengukuran laju (data lengkap: `pace_summary.csv`)

| Sel | Optimizer terpilih | epochs (arg) | Laju terukur | Bukti |
|---|---|---|---|---|
| A1 | MuSGD (via `auto`) | 200 | 1,2 s/it | catatan sesi |
| A2 (det=False) | MuSGD (via `auto`) | 200 | 1,1–1,2 s/it | catatan sesi |
| B2 | AdamW (via `auto`) | 1 | 3,4–3,6 it/s | `logs/ab_tmux_tee.log` |
| C1 (val+plots on) | MuSGD (via `auto`) | 200 | 1,2 s/it | `logs/ab_full_cfg.log` |
| C2 (val+plots off) | MuSGD (via `auto`) | 200 | 1,2 s/it | `logs/ab_ep200.log` |
| D1 | **SGD (eksplisit)** | 200 | **3,5–3,6 it/s** | `logs/ab_ep200_sgd.log` |
| FINAL (run3) | SGD (eksplisit) | 200 | 3,6–4,1 it/s | `run3_console.log` |

Perbandingan sel C2 vs D1 mengisolasi optimizer sebagai satu-satunya variabel:
**MuSGD ≈ 4× lebih lambat per iterasi daripada SGD di T4** untuk beban ini.
Perbandingan B2 vs C2 menjelaskan mengapa uji singkat menyesatkan: dengan
`optimizer="auto"`, ultralytics memilih optimizer berdasarkan **total
iterasi** (epochs × batch/epoch) — di bawah ~10k iterasi memilih AdamW
(cepat), di atasnya memilih MuSGD (lambat di T4). Uji pendek (epochs=1)
otomatis jatuh ke AdamW sehingga menyembunyikan masalah.

### Tabel B — Kandidat penyebab yang dieliminasi

| Kandidat | Cara diperiksa | Hasil |
|---|---|---|
| Versi ultralytics/torch berubah | mtime site-packages vs tanggal run2 | Sama (8.4.66 / 2.6.0+cu124, terpasang 12 Jun, run2 16 Jun) |
| Driver NVIDIA berubah | log dpkg/apt | 580.159.03 sejak 11 Jun, tidak berubah |
| Kernel Linux berubah | `last reboot`, dpkg | 6.8.0-124 sejak sebelum run2 |
| Link PCIe terdegradasi (VM pindah host) | `nvidia-smi`/`lspci` LnkSta | x16 Gen3 penuh |
| Throttling GPU (termal/daya) | `nvidia-smi -q -d PERFORMANCE` | Tidak aktif, P0 |
| Frekuensi/quota CPU | `/proc/cpuinfo`, cgroup | 3,0 GHz, tanpa quota |
| I/O disk | pengukur akses ultralytics | 2,2 GB/s, bukan bottleneck |
| tmux + tee (launcher) | sel B2 (config cepat via tmux+tee) | Tetap cepat → bukan penyebab |
| `deterministic=True` | microbench masked index_put; sel A2 | Hanya ~1,8× pada kernel tertentu; laju run tetap 1,2 s/it → bukan penyebab utama |
| `val=True` / `plots=True` | sel C1 vs C2 | Tidak berpengaruh |

## 4. Keputusan Konfigurasi Final (run3)

```
optimizer = "SGD", lr0 = 0.01, momentum = 0.937   # eksplisit, bukan "auto"
epochs = 200, patience = 15                        # early stopping jadi kriteria henti
deterministic = False, seed = 42                   # seed tetap mengunci urutan data
imgsz = 1280, batch = 4, amp = True                # tidak diubah dari run2
```

Alasan: (i) SGD klasik adalah resep YOLO yang terdokumentasi luas dan terbukti
3,5–4,1 it/s di T4 ini (≈8,5 menit/epoch termasuk validasi, plafon 200 epoch
≈ 28 jam); (ii) mengunci optimizer secara eksplisit menghilangkan perilaku
tersembunyi aturan `auto`; (iii) plafon 100 epoch pada run2 terbukti memotong
training sebelum early stopping sempat bekerja (mAP masih naik tipis di epoch
100), sehingga plafon dinaikkan ke 200 dengan patience=15.

## 5. Ancaman Validitas & Batasan

1. **Satu ulangan per sel.** Laju per sel hanya diukur sekali (±100 iterasi),
   namun stabil (variasi <10%) dan selisih antar kelompok ~4× jauh di atas
   noise.
2. **Laju ≠ kualitas konvergensi.** Pilot ini hanya mengukur waktu per
   iterasi. MuSGD (resep bawaan YOLO26) tidak dievaluasi sampai konvergen
   karena biaya wall-clock 4×; klaim pilot ini terbatas pada *kecepatan*,
   bukan mAP akhir.
3. **Anomali historis tak terjelaskan.** run1/run2 (Juni) juga memakai
   `optimizer="auto"` dengan total iterasi >10k — seharusnya MuSGD — namun
   laju terukurnya cepat. Console log training Juni tidak diarsipkan sehingga
   optimizer yang benar-benar terpakai tidak dapat diverifikasi. Justru karena
   itu konfigurasi final mengunci optimizer secara eksplisit.
4. **Sebagian sel awal tanpa log terarsip.** Sel A1/A2/B1 tercatat dari sesi
   interaktif (lognya tertimpa/terhapus); semua sel kunci untuk kesimpulan
   (B2, C1, C2, D1) memiliki log tersimpan di `logs/`.

## 6. Reproduksi

Jalankan saat GPU idle (jangan bersamaan dengan training):

```
cd ~/training && python pilots/2026-07-07_optimizer_pace/rerun_pilot.py
```

Skrip menjalankan tiga sel (auto→MuSGD, SGD, AdamW; epochs=200, ~130 iterasi
per sel) dan menulis laju terukur ke stdout + CSV.
