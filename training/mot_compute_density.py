#!/usr/bin/env python3
"""
mot_compute_density.py
=======================
Compute per-frame object counts from VisDrone-MOT predictions and ground truth.

Generates CSV files compatible with plot_density.py:
  image_id,num_detections,tier

USAGE
-----
# From predictions (after running infer_mot.py)
python mot_compute_density.py --dir mot_val_predictions --output mot_predictions_density.csv

# From ground truth annotations
python mot_compute_density.py \
    --dir /home/ubuntu/datasets/VisDrone/VisDrone2019-MOT-val/annotations \
    --output mot_ground_truth_density.csv

# With class filtering (MOT-5 classes)
python mot_compute_density.py --dir mot_val_predictions --classes 1,4,5,6,9
"""

import argparse
import csv
import glob
import os
from collections import defaultdict
from pathlib import Path

import numpy as np


def parse_mot_file(filepath, classes=None, min_score=0.0, drop_heavy_occlusion=False):
    """
    Parse a VisDrone-MOT annotation/prediction file.
    
    Format (10 columns):
      frame_index, target_id, bbox_left, bbox_top, bbox_w, bbox_h,
      score, object_category, truncation, occlusion
    
    Returns:
        Dict mapping "seq_frame" -> count of objects
    """
    frame_counts = defaultdict(int)
    
    with open(filepath, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 10:
                continue
            
            try:
                frame = int(row[0])
                # tid = int(row[1])  # track ID (not used for density)
                score = float(row[6])
                category = int(row[7])
                occlusion = int(row[9])
            except (ValueError, IndexError):
                continue
            
            # Apply filters
            if classes is not None and category not in classes:
                continue
            
            if score < min_score:
                continue
            
            if drop_heavy_occlusion and occlusion == 2:
                continue
            
            # Get sequence name from filename
            seq_name = Path(filepath).stem
            frame_key = f"{seq_name}_frame{frame:07d}"
            frame_counts[frame_key] += 1
    
    return frame_counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True,
                    help="Directory containing .txt files (predictions or annotations)")
    ap.add_argument("--output", default="mot_density.csv",
                    help="Output CSV file")
    ap.add_argument("--classes", default=None,
                    help="Comma-separated list of category IDs to include (e.g., 1,4,5,6,9 for MOT-5)")
    ap.add_argument("--min_score", type=float, default=0.0,
                    help="Minimum confidence score (for predictions)")
    ap.add_argument("--drop_heavy_occlusion", action="store_true",
                    help="Exclude boxes with occlusion==2")
    args = ap.parse_args()
    
    # Parse class filter
    classes = None
    if args.classes:
        classes = {int(x) for x in args.classes.split(',')}
    
    # Find all .txt files
    txt_files = sorted(glob.glob(os.path.join(args.dir, "*.txt")))
    if not txt_files:
        raise FileNotFoundError(f"No .txt files found in {args.dir}")
    
    print(f"[info] Processing {len(txt_files)} files from {args.dir}")
    print(f"[info] Classes: {classes if classes else 'all'}")
    print(f"[info] min_score={args.min_score}, drop_heavy_occlusion={args.drop_heavy_occlusion}")
    
    # Parse all files
    all_counts = {}
    total_frames = 0
    total_objects = 0
    
    for filepath in txt_files:
        frame_counts = parse_mot_file(
            filepath, 
            classes=classes,
            min_score=args.min_score,
            drop_heavy_occlusion=args.drop_heavy_occlusion
        )
        all_counts.update(frame_counts)
        total_frames += len(frame_counts)
        total_objects += sum(frame_counts.values())
    
    print(f"[info] Total frames: {total_frames}")
    print(f"[info] Total objects: {total_objects}")
    print(f"[info] Avg objects/frame: {total_objects/total_frames:.2f}" if total_frames > 0 else "N/A")
    
    # Compute quartiles
    counts_array = np.array(list(all_counts.values()))
    q1 = float(np.percentile(counts_array, 25))
    med = float(np.percentile(counts_array, 50))
    q3 = float(np.percentile(counts_array, 75))
    
    def assign_tier(c):
        if c < q1:
            return "Rendah"
        if c > q3:
            return "Tinggi"
        return "Sedang"
    
    # Write CSV in format expected by plot_density.py
    csv_lines = ["image_id,num_detections,tier"]
    for frame_key in sorted(all_counts.keys()):
        count = all_counts[frame_key]
        tier = assign_tier(count)
        csv_lines.append(f"{frame_key},{count},{tier}")
    
    Path(args.output).write_text("\n".join(csv_lines) + "\n")
    print(f"\n[ok] CSV saved: {args.output}")
    
    # Print summary
    n_low = int((counts_array < q1).sum())
    n_mid = int(((counts_array >= q1) & (counts_array <= q3)).sum())
    n_high = int((counts_array > q3).sum())
    
    print(f"\n=== DENSITY DISTRIBUTION ===")
    print(f"  N frames         : {len(counts_array)}")
    print(f"  Min / Max        : {int(counts_array.min())} / {int(counts_array.max())}")
    print(f"  Mean / Std       : {counts_array.mean():.2f} / {counts_array.std():.2f}")
    print(f"  Q1 (25th pct)    : {q1:.1f}")
    print(f"  Median           : {med:.1f}")
    print(f"  Q3 (75th pct)    : {q3:.1f}")
    print(f"  IQR              : {q3 - q1:.1f}")
    print(f"  --- Tier counts ---")
    print(f"  Rendah (< {q1:.1f})     : {n_low} frames")
    print(f"  Sedang ({q1:.1f}-{q3:.1f}): {n_mid} frames")
    print(f"  Tinggi (> {q3:.1f})     : {n_high} frames")
    print(f"\n>> To visualize: python plot_density.py --counts {args.output}")


if __name__ == "__main__":
    main()
