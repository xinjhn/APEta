"""
train_yolo26.py
===============
Fine-tuning YOLO26s pada VisDrone-DET (split train 90/10) untuk menghasilkan
model penghasil payload deteksi padat pada penelitian komparasi REST vs GraphQL.

Konteks penting:
  - Tujuan training BUKAN mengejar mAP tertinggi, melainkan menghasilkan model
    yang stabil & realistis sebagai penghasil nested JSON berkepadatan tinggi.
    Karena itu setelan dijaga sederhana & dekat default (mudah dipertahankan).
  - Hardware target: Tesla T4 (16GB VRAM). RTX 3050 laptop hanya untuk debug.

Cara pakai:
  # 1) Siapkan data lebih dulu:
  #    python prepare_visdrone.py --root /path/ke/VisDrone --seed 42
  # 2) Sesuaikan 'path' di visdrone.yaml
  # 3) Jalankan:
  #    python train_yolo26.py

Prasyarat:
  pip install ultralytics
"""

from ultralytics import YOLO

# ---------------------------------------------------------------------------
# UKURAN MODEL — fleksibel. Mulai dari "n" (nano); naikkan ke "s"/"m" hanya bila
# profiling densitas output model menunjukkan deteksi terlalu jarang sehingga
# rentang tier (Rendah/Sedang/Tinggi) menjadi sempit / kurang kontras.
#   "yolo26n.pt" = nano  (paling ringan, training & inferensi tercepat di T4)
#   "yolo26s.pt" = small (kapasitas lebih besar, deteksi objek kecil lebih baik)
# ---------------------------------------------------------------------------
MODEL_SIZE = "yolo26n.pt"   # ganti ke "yolo26s.pt" bila perlu


def main():
    # Muat bobot pretrained COCO (.pt = fine-tuning; head kelas diinisialisasi
    # ulang otomatis untuk 10 kelas VisDrone, backbone & neck ditransfer).
    model = ~/training/runs/detect/visdrone_finetune/yolo26n_t4_run1/weights/last.pt

    model.train(
        # --- Data ---
        data="visdrone.yaml",      # menunjuk ke split train 90/10 (val resmi dicadangkan)

        # --- Durasi & penghentian ---
        epochs=100,                # plafon; early stopping yang menentukan kapan berhenti
        patience=15,               # berhenti bila val internal plateau 15 epoch.
                                   # Agresif untuk menghemat waktu T4 (akurasi bukan tujuan).

        # --- Resolusi & batch (disetel untuk T4 16GB) ---
        imgsz=1280,                # WAJIB untuk objek kecil VisDrone (default 640 terlalu kasar)
        batch=4,                   # aman untuk T4 16GB @ 1280. Jika OOM -> 4; jika longgar -> 12.
        cache=False,               # mulai False; jika I/O lambat & RAM longgar, coba "ram"

        # --- Hardware ---
        device=0,                  # GPU index (T4)
        workers=8,                 # dataloader workers (CPU 32-core punya ruang lebih)
        amp=True,                  # mixed precision; T4 (Turing) punya Tensor Cores -> lebih cepat

        # --- Optimizer (biarkan otomatis) ---
        optimizer="auto",          # ~5.800 citra x 100 epoch > 10k iter -> MuSGD lr=0.01 (resep YOLO26)
        # lr0, momentum diabaikan saat optimizer=auto.

        # --- Strategi transfer ---
        freeze=None,               # JANGAN freeze: domain drone jauh dari COCO,
                                   # backbone perlu beradaptasi (rekomendasi dok. Ultralytics).
        warmup_epochs=3.0,         # default; lindungi fitur pretrained di awal training

        # --- Reprodusibilitas ---
        seed=42,                   # split & training dapat direproduksi
        deterministic=True,        # operasi deterministik saat training

        # --- Output ---
        project="visdrone_finetune",
        name=f"{MODEL_SIZE.replace('.pt','')}_t4_run1",
        exist_ok=False,            # jangan timpa run sebelumnya tanpa sadar
        plots=True,                # simpan kurva loss/PR untuk lampiran laporan
    )

    # -----------------------------------------------------------------------
    # Setelah training, bobot terbaik ada di:
    #   visdrone_finetune/<model>_t4_run1/weights/best.pt
    # Inilah checkpoint yang DIBEKUKAN dan dipakai pada tahap inferensi luring
    # untuk menghasilkan payload eksperimen (split VAL VisDrone).
    #
    # CATATAN BENANG MERAH: kuartil densitas (Q1/Q3) untuk Tabel III.1 & IV.1
    # harus dihitung dari JUMLAH DETEKSI per citra pada output best.pt ini,
    # BUKAN dari anotasi ground-truth. Lihat tahap inferensi+profiling.
    # -----------------------------------------------------------------------
    name = f"{MODEL_SIZE.replace('.pt','')}_t4_run1"
    print(f"Training selesai. Bobot terbaik: visdrone_finetune/{name}/weights/best.pt")


if __name__ == "__main__":
    main()
