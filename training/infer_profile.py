"""
infer_profile.py
=================
Tahap INFERENSI LURING + PROFILING DENSITAS untuk penelitian komparasi
REST API vs GraphQL dalam menyajikan output deteksi objek (nested JSON).

Apa yang dikerjakan script ini:
  1. Memuat best.pt (model YOLO26 hasil fine-tuning) dan menjalankan inferensi ke
     SELURUH citra val RESMI VisDrone (548 citra), pada imgsz=1280
     (KONSISTEN dengan resolusi training).
  2. Menyusun output deteksi tiap citra menjadi JSON NESTED (skema VCD):
     citra -> array deteksi -> tiap deteksi {class, confidence, bbox{...}}.
     Inilah sumber In-Memory Data Pool yang disajikan REST & GraphQL.
  3. Menghitung JUMLAH DETEKSI PER CITRA -> kuartil Q1/Q3 -> tier densitas:
       Rendah  : count <  Q1
       Sedang  : Q1 <= count <= Q3   (interquartile range)
       Tinggi  : count >  Q3

CATATAN BENANG MERAH (penting untuk laporan & sidang):
  - Kuartil DIHITUNG DARI OUTPUT MODEL (best.pt), BUKAN dari anotasi ground-truth.
    Angka inilah yang menggantikan placeholder sementara (42/96) di laporan.
  - 'conf' (ambang confidence) DIKUNCI & DIDOKUMENTASIKAN. Payload yang dihasilkan
    di sini adalah payload yang SAMA yang nanti disajikan REST maupun GraphQL,
    sehingga komparasi adil (perbedaan hanya di protokol/serialisasi).
  - YOLO26 bersifat end-to-end NMS-FREE: prediksi sudah final tanpa Non-Maximum
    Suppression. Jadi jumlah deteksi mencerminkan KARAKTERISTIK OUTPUT MODEL itu
    sendiri, sesuai mekanisme yang dijelaskan di Konteks Penelitian.

Cara pakai:
  python infer_profile.py \
      --weights /home/ubuntu/training/runs/detect/visdrone_finetune/yolo26n_t4_run2/weights/best.pt \
      --images  /home/ubuntu/datasets/VisDrone/VisDrone2019-DET-val/images \
      --imgsz 1280 --conf 0.25
"""

import json
import argparse
from pathlib import Path
from datetime import datetime

import numpy as np
from ultralytics import YOLO


def build_detection_array(boxes, names):
    """
    Susun array deteksi NESTED untuk satu citra.
    Tiap elemen = satu objek terdeteksi, dengan bbox sebagai sub-objek bersarang.
    Field sengaja dibuat beragam (class_id, class_name, confidence, bbox{...})
    agar mendukung keempat pola retrieval eksperimen:
      - baseline           : kembalikan seluruh field
      - filtered field     : pilih subset field (mis. bbox + class saja)
      - filtered param+field: filter record (mis. by class/conf) + pilih field
      - aggregation        : hitung ringkasan (mis. count per kelas)
    """
    detections = []
    if boxes is None or len(boxes) == 0:
        return detections

    xyxy = boxes.xyxy.cpu().numpy()     # koordinat piksel [x1, y1, x2, y2]
    conf = boxes.conf.cpu().numpy()     # skor confidence
    cls = boxes.cls.cpu().numpy().astype(int)  # indeks kelas (0..9)

    for i in range(len(cls)):
        x1, y1, x2, y2 = (float(v) for v in xyxy[i])
        detections.append({
            "id": i,
            "class_id": int(cls[i]),
            "class_name": names[int(cls[i])],
            "confidence": round(float(conf[i]), 4),
            "bbox": {                       # sub-objek bersarang (sumber kompleksitas nested)
                "x1": round(x1, 2),
                "y1": round(y1, 2),
                "x2": round(x2, 2),
                "y2": round(y2, 2),
                "width": round(x2 - x1, 2),
                "height": round(y2 - y1, 2),
            },
        })
    return detections


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True, help="path ke best.pt")
    ap.add_argument("--images", required=True, help="folder citra val RESMI VisDrone (548 citra)")
    ap.add_argument("--imgsz", type=int, default=1280, help="WAJIB sama dengan resolusi training")
    ap.add_argument("--conf", type=float, default=0.25,
                    help="ambang confidence (DIKUNCI untuk seluruh eksperimen; dokumentasikan)")
    ap.add_argument("--out", default="data_pool.json", help="output JSON pool (In-Memory Data Pool)")
    ap.add_argument("--counts-out", default="density_counts.csv",
                    help="output CSV: jumlah deteksi per citra + tier")
    args = ap.parse_args()

    # --- Muat model ---
    model = YOLO(args.weights)
    names = model.names  # dict {0:'pedestrian', ..., 9:'motor'} -> nama VisDrone

    img_dir = Path(args.images)
    images = sorted(img_dir.glob("*.jpg"))
    if not images:
        raise FileNotFoundError(f"Tidak ada citra .jpg di {img_dir}")
    print(f"[info] Jumlah citra val resmi: {len(images)} (harap 548)")
    print(f"[info] imgsz={args.imgsz}, conf={args.conf}, NMS-free (YOLO26 end-to-end)")

    # --- Metadata pool (untuk reprodusibilitas & dokumentasi) ---
    pool = {
        "metadata": {
            "model_weights": str(args.weights),
            "imgsz": args.imgsz,
            "conf_threshold": args.conf,
            "nms_free": True,
            "num_images": len(images),
            "class_names": {int(k): v for k, v in names.items()},
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
        "images": [],
    }

    # --- Inferensi: SATU CITRA per panggilan (batch=1) ---
    # Penting: JANGAN memberi seluruh daftar path ke predict() sekaligus, karena
    # Ultralytics akan membentuk batch besar dan VRAM T4 (~14.5GiB) bisa OOM.
    # Memproses satu per satu menjamin memori tetap minimal & urutan terjaga.
    counts = []
    total = len(images)
    for idx, img_path in enumerate(images, 1):
        res = model.predict(
            source=str(img_path),
            imgsz=args.imgsz,
            conf=args.conf,
            verbose=False,
        )[0]
        n = len(res.boxes) if res.boxes is not None else 0
        counts.append(n)
        pool["images"].append({
            "image_id": Path(res.path).stem,
            "file_name": Path(res.path).name,
            "width": int(res.orig_shape[1]),
            "height": int(res.orig_shape[0]),
            "num_detections": n,                         # field yang menentukan tier densitas
            "detections": build_detection_array(res.boxes, names),
        })
        if idx % 50 == 0 or idx == total:
            print(f"  [infer] {idx}/{total} citra selesai")

    # --- Simpan pool JSON (sumber In-Memory Data Pool) ---
    Path(args.out).write_text(json.dumps(pool, indent=2))
    print(f"[ok] Pool JSON tersimpan: {args.out}")

    # ------------------------------------------------------------------
    # PROFILING DENSITAS  (kuartil dari OUTPUT MODEL, bukan ground-truth)
    # ------------------------------------------------------------------
    counts = np.array(counts)
    q1 = float(np.percentile(counts, 25))
    med = float(np.percentile(counts, 50))
    q3 = float(np.percentile(counts, 75))

    def assign_tier(c):
        if c < q1:
            return "Rendah"
        if c > q3:
            return "Tinggi"
        return "Sedang"

    # --- Tulis CSV: image_id, jumlah deteksi, tier (bahan Tabel III.1/IV.1 & plot densitas) ---
    csv_lines = ["image_id,num_detections,tier"]
    for img in pool["images"]:
        c = img["num_detections"]
        csv_lines.append(f'{img["image_id"]},{c},{assign_tier(c)}')
    Path(args.counts_out).write_text("\n".join(csv_lines) + "\n")
    print(f"[ok] CSV densitas tersimpan: {args.counts_out}")

    # --- Ringkasan distribusi ---
    n_low = int((counts < q1).sum())
    n_mid = int(((counts >= q1) & (counts <= q3)).sum())
    n_high = int((counts > q3).sum())

    print("\n=== PROFILING DENSITAS (dari output best.pt) ===")
    print(f"  N citra          : {len(counts)}")
    print(f"  Min / Max        : {int(counts.min())} / {int(counts.max())}")
    print(f"  Mean / Std       : {counts.mean():.2f} / {counts.std():.2f}")
    print(f"  Q1 (persentil 25): {q1:.1f}")
    print(f"  Median           : {med:.1f}")
    print(f"  Q3 (persentil 75): {q3:.1f}")
    print(f"  IQR (Q3-Q1)      : {q3 - q1:.1f}")
    print("  --- Tier densitas ---")
    print(f"  Rendah (< {q1:.1f})            : {n_low} citra")
    print(f"  Sedang ({q1:.1f} - {q3:.1f})   : {n_mid} citra")
    print(f"  Tinggi (> {q3:.1f})            : {n_high} citra")
    print(f"\n  >> ANGKA FINAL: Q1={q1:.0f}, Q3={q3:.0f} "
          f"(menggantikan placeholder 42/96 di laporan).")
    print("  >> Cek kriteria penerimaan #2: distribusi cukup LEBAR & bervariasi?")
    print("     (rentang Min-Max lebar & IQR memadai = tier kontras. "
          "Jika menyempit -> pertimbangkan yolo26s.)")


if __name__ == "__main__":
    main()