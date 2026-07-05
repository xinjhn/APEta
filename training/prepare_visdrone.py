"""
prepare_visdrone.py
===================
Persiapan dataset VisDrone-DET untuk fine-tuning YOLO26.

Script ini melakukan DUA hal:
  1. Konversi anotasi VisDrone (format kustom) -> format label YOLO (.txt).
  2. Membagi split TRAIN menjadi 90% (latih bobot) dan 10% (val internal /
     monitoring early stopping), sesuai keputusan metodologis penelitian.

CATATAN BENANG MERAH (penting untuk laporan & sidang):
  - Split TRAIN  -> dipakai untuk fine-tuning (dibagi 90/10 di sini).
  - Split VAL    -> TIDAK disentuh script ini. Dicadangkan untuk eksperimen API.
                    (Diproses terpisah pada tahap inferensi -> In-Memory Data Pool.)
  - Split TEST-DEV -> tidak digunakan.

Struktur folder VisDrone-DET yang diasumsikan (hasil ekstraksi resmi):
  <ROOT>/
    VisDrone2019-DET-train/
      images/        *.jpg
      annotations/   *.txt   (format VisDrone)
    VisDrone2019-DET-val/     <- biarkan, untuk eksperimen
      images/
      annotations/

Cara pakai:
  python prepare_visdrone.py --root /path/ke/VisDrone --val-ratio 0.10 --seed 42
"""

import argparse
import os
import random
from pathlib import Path

# ---------------------------------------------------------------------------
# 10 kelas deteksi VisDrone (kategori 1..10 dipetakan ke indeks YOLO 0..9).
# Kategori 0 (ignored regions) dan 11 (others) DIBUANG, sesuai konvensi resmi.
# ---------------------------------------------------------------------------
VISDRONE_NAMES = [
    "pedestrian",       # 0
    "people",           # 1
    "bicycle",          # 2
    "car",              # 3
    "van",              # 4
    "truck",            # 5
    "tricycle",         # 6
    "awning-tricycle",  # 7
    "bus",              # 8
    "motor",            # 9
]


def convert_box(img_w, img_h, left, top, w, h):
    """Konversi kotak VisDrone (left,top,w,h px) -> YOLO (xc,yc,w,h ternormalisasi)."""
    dw, dh = 1.0 / img_w, 1.0 / img_h
    xc = (left + w / 2.0) * dw
    yc = (top + h / 2.0) * dh
    return xc, yc, w * dw, h * dh


def visdrone2yolo(split_dir: Path):
    """
    Konversi semua anotasi pada satu split (mis. VisDrone2019-DET-train)
    menjadi label YOLO di folder 'labels/'.
    """
    from PIL import Image  # pip install pillow

    ann_dir = split_dir / "annotations"
    img_dir = split_dir / "images"
    lbl_dir = split_dir / "labels"
    lbl_dir.mkdir(parents=True, exist_ok=True)

    ann_files = sorted(ann_dir.glob("*.txt"))
    if not ann_files:
        raise FileNotFoundError(f"Tidak ada anotasi di {ann_dir}")

    n_ok = 0
    for ann in ann_files:
        img_path = (img_dir / ann.name).with_suffix(".jpg")
        if not img_path.exists():
            print(f"  [lewati] gambar tidak ditemukan: {img_path.name}")
            continue
        img_w, img_h = Image.open(img_path).size

        lines = []
        for row in ann.read_text().strip().splitlines():
            parts = row.split(",")
            if len(parts) < 6:
                continue
            left, top, w, h = map(int, parts[:4])
            score = parts[4]
            category = int(parts[5])

            # Buang anotasi yang ditandai diabaikan (score 0) atau di luar 10 kelas.
            if score == "0":
                continue
            if category < 1 or category > 10:   # 0=ignored, 11=others
                continue
            if w <= 0 or h <= 0:
                continue

            cls = category - 1  # 1..10 -> 0..9
            xc, yc, bw, bh = convert_box(img_w, img_h, left, top, w, h)
            lines.append(f"{cls} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")

        out = lbl_dir / ann.name
        out.write_text("\n".join(lines))
        n_ok += 1

    print(f"  Konversi selesai: {n_ok} label ditulis ke {lbl_dir}")


def split_train(train_dir: Path, val_ratio: float, seed: int, out_dir: Path):
    """
    Bagi citra TRAIN menjadi train_sub (90%) dan val_internal (10%).
    Tidak memindahkan file; cukup menulis daftar path ke dua file .txt.
    """
    img_dir = train_dir / "images"
    images = sorted(str(p.resolve()) for p in img_dir.glob("*.jpg"))
    if not images:
        raise FileNotFoundError(f"Tidak ada gambar di {img_dir}")

    random.seed(seed)
    random.shuffle(images)

    n_val = int(round(len(images) * val_ratio))
    val_internal = images[:n_val]
    train_sub = images[n_val:]

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "train_sub.txt").write_text("\n".join(train_sub) + "\n")
    (out_dir / "val_internal.txt").write_text("\n".join(val_internal) + "\n")

    print(f"  Total train  : {len(images)} citra")
    print(f"  -> train_sub : {len(train_sub)} citra (90%) untuk melatih bobot")
    print(f"  -> val_intern: {len(val_internal)} citra (10%) untuk monitoring/early stopping")
    print(f"  Daftar ditulis ke {out_dir}/train_sub.txt & val_internal.txt")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="Folder ROOT VisDrone-DET")
    ap.add_argument("--val-ratio", type=float, default=0.10, help="Rasio val internal dari train")
    ap.add_argument("--seed", type=int, default=42, help="Seed untuk reprodusibilitas split")
    ap.add_argument("--convert-val", action="store_true",
                    help="(Opsional) konversi label split VAL juga, untuk sanity-check. "
                         "VAL tetap TIDAK dipakai untuk training.")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    train_dir = root / "VisDrone2019-DET-train"
    val_dir = root / "VisDrone2019-DET-val"

    print("[1/2] Konversi anotasi TRAIN -> label YOLO ...")
    visdrone2yolo(train_dir)

    if args.convert_val:
        print("[opsional] Konversi anotasi VAL -> label YOLO (hanya sanity-check) ...")
        visdrone2yolo(val_dir)

    print("[2/2] Membagi TRAIN menjadi 90/10 ...")
    split_train(train_dir, args.val_ratio, args.seed, out_dir=root / "splits")

    print("\nSelesai. Selanjutnya: sesuaikan 'path' di visdrone.yaml lalu jalankan train_yolo26.py")


if __name__ == "__main__":
    main()
