"""
train_yolo26.py
===============
Fine-tuning YOLO26 pada VisDrone-DET dengan PROTOKOL RESMI:
  - train : seluruh split TRAIN resmi (6.471 citra)
  - val   : split VAL resmi (548 citra)
Bobot awal: pretrained COCO (fresh), BUKAN melanjutkan run sebelumnya --
satu tahap training yang bersih dan mudah dipertahankan di sidang.

Riwayat protokol:
  - run1/run2  : split internal 90/10 dari TRAIN (visdrone.yaml); DET-val
                 dicadangkan untuk eksperimen API.
  - run3       : protokol resmi (visdrone_official.yaml). DET-val bebas
                 dipakai karena eksperimen final memakai korpus MOT-val.

Konteks penting:
  - Tujuan training BUKAN mengejar mAP tertinggi, melainkan menghasilkan model
    yang stabil & realistis sebagai penghasil nested JSON berkepadatan tinggi.
    Karena itu setelan dijaga sederhana & dekat default (mudah dipertahankan).
  - Hardware target: Tesla T4 (16GB VRAM).

Cara pakai:
  # 1) Pastikan label val sudah dikonversi:
  #    python prepare_visdrone.py --root /home/ubuntu/datasets/VisDrone --convert-val
  # 2) Jalankan:
  #    python train_yolo26.py
"""

from ultralytics import YOLO

MODEL_SIZE = "yolo26n.pt"   # ganti ke "yolo26s.pt" bila perlu

RUN_NAME = f"{MODEL_SIZE.replace('.pt', '')}_t4_run3_official"


def main():
    # Muat bobot pretrained COCO (.pt = fine-tuning; head kelas diinisialisasi
    # ulang otomatis untuk 10 kelas VisDrone, backbone & neck ditransfer).
    model = YOLO(MODEL_SIZE)

    model.train(
        # --- Data ---
        data="visdrone_official.yaml",  # protokol resmi: train penuh, val resmi

        # --- Durasi & penghentian ---
        epochs=200,                # plafon dinaikkan dari 100: run2 mencapai 100/100
                                   # tanpa sempat early-stop (mAP masih naik tipis),
                                   # jadi plafon lama yang memotong, bukan plateau.
        patience=15,               # berhenti bila val plateau 15 epoch

        # --- Resolusi & batch (disetel untuk T4 16GB) ---
        imgsz=1280,                # WAJIB untuk objek kecil VisDrone (default 640 terlalu kasar)
        batch=4,                   # aman untuk T4 16GB @ 1280
        cache=False,

        # --- Hardware ---
        device=0,                  # GPU index (T4)
        workers=8,                 # dataloader workers
        amp=True,                  # mixed precision; T4 (Turing) punya Tensor Cores

        # --- Optimizer (EKSPLISIT, bukan "auto") ---
        # optimizer="auto" memilih MuSGD bila total iterasi > 10k, dan MuSGD
        # terukur ~4x lebih lambat per iterasi di T4 ini (1.2 s/it vs 0.28 s/it
        # dengan SGD; diverifikasi A/B satu-variabel, epochs=200, 2026-07-07).
        # SGD klasik = resep YOLO standar, cepat, dan mudah dipertahankan.
        optimizer="SGD",
        lr0=0.01,
        momentum=0.937,

        # --- Strategi transfer ---
        freeze=None,               # JANGAN freeze: domain drone jauh dari COCO
        warmup_epochs=3.0,

        # --- Reprodusibilitas ---
        seed=42,
        deterministic=False,       # kernel deterministik sedikit lebih lambat pada
                                   # masked-scatter (microbench ~1.8x) dan tidak
                                   # diperlukan; seed tetap mengunci urutan data &
                                   # augmentasi. (Penyebab utama kelambatan 4x adalah
                                   # MuSGD dari optimizer="auto", lihat di atas.)

        # --- Output ---
        project="/home/ubuntu/training/runs/detect/visdrone_finetune",
        name=RUN_NAME,
        exist_ok=False,            # jangan timpa run sebelumnya tanpa sadar
        plots=True,                # simpan kurva loss/PR untuk lampiran laporan
    )

    print(f"Training selesai. Bobot terbaik: "
          f"runs/detect/visdrone_finetune/{RUN_NAME}/weights/best.pt")


if __name__ == "__main__":
    main()
