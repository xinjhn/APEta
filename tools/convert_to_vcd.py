"""
tools/convert_to_vcd.py
========================
Konversi output mentah inferensi YOLO26 (skema model: image_id, width, height,
detections[{class_name, confidence, bbox}]) ke skema VCD yang dibaca core/pool.py
(image_id, dimensions{width,height}, detections[{class_label, confidence_score,
bounding_box}]).

Pemakaian:
    python tools/convert_to_vcd.py --input /home/ubuntu/training/data_pool.json \
        --output /path/ke/inferensi_vcd.json
"""
from __future__ import annotations

import argparse
import json


BBOX_KEYS = ("x1", "y1", "x2", "y2", "width", "height")


def convert_record(rec: dict) -> dict:
    detections = [
        {
            "class_label": d["class_name"],
            "confidence_score": d["confidence"],
            # List[float], bukan dict -- graphql_server.py melakukan
            # list(d["bounding_box"]) untuk mengisi tipe GraphQL List[float];
            # dict akan menghasilkan list KEYS ('x1', ...), bukan nilai.
            "bounding_box": [d["bbox"][k] for k in BBOX_KEYS],
        }
        for d in rec.get("detections", [])
    ]
    return {
        "image_id": rec["image_id"],
        "dimensions": {"width": rec["width"], "height": rec["height"]},
        "detections": detections,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    images = data["images"] if isinstance(data, dict) and "images" in data else data
    records = [convert_record(rec) for rec in images]

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(records, f)

    print(f"Wrote {len(records)} records to {args.output}")


if __name__ == "__main__":
    main()
