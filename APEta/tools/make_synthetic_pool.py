"""
tools/make_synthetic_pool.py
============================
PERINGATAN: data SINTETIS, hanya untuk smoke test fungsional & uji paritas
sebelum JSON inferensi nyata tersedia. JANGAN dipakai sebagai data eksperimen.
Data eksperimen WAJIB berasal dari inferensi model YOLO26 final (Tahap [A]).

Menghasilkan record berbentuk skema VCD dengan jumlah deteksi yang sengaja
menyebar agar ketiga tier densitas terisi (low <42, medium 42-96, high >96).

Pemakaian:
    python tools/make_synthetic_pool.py --out /tmp/synthetic.json --n 300 --seed 42
"""
from __future__ import annotations

import argparse
import json
import random

# 10 kelas VisDrone (untuk realisme struktural, bukan akurasi)
VISDRONE_CLASSES = [
    "pedestrian", "people", "bicycle", "car", "van",
    "truck", "tricycle", "awning-tricycle", "bus", "motor",
]


def make_detection(rng: random.Random) -> dict:
    x, y = rng.uniform(0, 600), rng.uniform(0, 400)
    w, h = rng.uniform(10, 80), rng.uniform(10, 80)
    return {
        "class_label": rng.choice(VISDRONE_CLASSES),
        "confidence_score": round(rng.uniform(0.25, 0.99), 2),  # floor 0.25
        "bounding_box": [round(x, 1), round(y, 1), round(w, 1), round(h, 1)],
    }


def make_record(rng: random.Random, idx: int, n_det: int) -> dict:
    return {
        "image_id": f"SYN_{idx:07d}",
        "dimensions": {"width": 640, "height": 480},
        "detections": [make_detection(rng) for _ in range(n_det)],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    records = []
    for i in range(args.n):
        # Sebar jumlah deteksi: ~1/3 low, 1/3 medium, 1/3 high
        bucket = i % 3
        if bucket == 0:
            n_det = rng.randint(1, 41)      # low
        elif bucket == 1:
            n_det = rng.randint(42, 96)     # medium
        else:
            n_det = rng.randint(97, 341)    # high
        records.append(make_record(rng, i, n_det))

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(records, f)
    print(f"Ditulis {len(records)} record sintetis ke {args.out}")


if __name__ == "__main__":
    main()
