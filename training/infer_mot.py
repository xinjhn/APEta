#!/usr/bin/env python3
"""
infer_mot.py
============
Run YOLO26 inference on VisDrone-MOT dataset and output predictions in MOT format.

This script:
  1. Loads the best trained model (yolo26n_t4_run2/weights/best.pt)
  2. Processes all frames from VisDrone-MOT sequences
  3. Outputs detections in VisDrone-MOT annotation format (10 columns):
     frame_index, target_id, bbox_left, bbox_top, bbox_w, bbox_h,
     score, object_category, truncation, occlusion

INPUT STRUCTURE
---------------
Expected directory structure:
  /path/to/MOT-val/
    ├── images/
    │   ├── seq001/
    │   │   ├── 000001.jpg
    │   │   ├── 000002.jpg
    │   │   └── ...
    │   ├── seq002/
    │   └── ...
    └── annotations/   (optional, for comparison)
        ├── seq001.txt
        └── ...

USAGE
-----
  # Basic usage - process all sequences
  python infer_mot.py \
      --model /home/ubuntu/training/runs/detect/visdrone_finetune/yolo26n_t4_run2/weights/best.pt \
      --images /path/to/MOT-val/images \
      --output mot_predictions

  # With custom confidence threshold
  python infer_mot.py --images /path/to/MOT-val/images --conf 0.3

  # Limit to specific sequences
  python infer_mot.py --images /path/to/MOT-val/images --sequences seq001,seq002

NOTES
-----
  - The model was trained on VisDrone-DET (10 classes), so it can detect all
    VisDrone categories in MOT sequences.
  - Output uses raw VisDrone category IDs (1-10), NOT Ultralytics remapped IDs (0-9).
  - Track IDs are assigned sequentially per class per sequence (simple tracking).
  - For proper multi-object tracking, consider using ByteTrack or similar tracker.
"""

import argparse
import csv
import os
from collections import defaultdict
from pathlib import Path

import numpy as np
from ultralytics import YOLO


# Mapping from Ultralytics class indices (0-9) to raw VisDrone category IDs (1-10)
ULTRALYTICS_TO_VISDRONE = {
    0: 1,   # pedestrian
    1: 2,   # people
    2: 3,   # bicycle
    3: 4,   # car
    4: 5,   # van
    5: 6,   # truck
    6: 7,   # tricycle
    7: 8,   # awning-tricycle
    8: 9,   # bus
    9: 10,  # motor
}

CLASS_NAMES = {
    1: "pedestrian", 2: "people", 3: "bicycle", 4: "car", 5: "van",
    6: "truck", 7: "tricycle", 8: "awning-tricycle", 9: "bus", 10: "motor"
}


def simple_track(detections, prev_tracks, track_counter, min_iou=0.3):
    """
    Simple IoU-based tracking across frames.
    
    Args:
        detections: List of detection dicts with 'bbox', 'class_id', 'confidence'
        prev_tracks: Dict mapping track_id -> {'bbox': [x1,y1,x2,y2], 'class': int}
        track_counter: Current max track ID
        min_iou: Minimum IoU to consider match
    
    Returns:
        Updated detections with track IDs, updated prev_tracks, updated track_counter
    """
    def compute_iou(box1, box2):
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])
        
        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0
    
    # Try to match detections to existing tracks
    used_tracks = set()
    for det in detections:
        best_track = None
        best_iou = min_iou
        
        for tid, track_info in prev_tracks.items():
            if tid in used_tracks:
                continue
            if track_info['class'] != det['class_id']:
                continue
            
            iou = compute_iou(det['bbox'], track_info['bbox'])
            if iou > best_iou:
                best_iou = iou
                best_track = tid
        
        if best_track is not None:
            det['track_id'] = best_track
            used_tracks.add(best_track)
            prev_tracks[best_track] = {
                'bbox': det['bbox'],
                'class': det['class_id']
            }
        else:
            # Assign new track ID
            track_counter += 1
            det['track_id'] = track_counter
            prev_tracks[track_counter] = {
                'bbox': det['bbox'],
                'class': det['class_id']
            }
    
    return detections, prev_tracks, track_counter


def process_sequence(model, seq_path, output_dir, conf_threshold, imgsz):
    """
    Process a single sequence folder and write MOT-format predictions.
    
    Args:
        model: YOLO model instance
        seq_path: Path to sequence folder containing frame images
        output_dir: Directory to write output .txt file
        conf_threshold: Confidence threshold for detections
        imgsz: Image size for inference
    
    Returns:
        Dict with statistics about the sequence
    """
    seq_name = seq_path.name
    output_file = output_dir / f"{seq_name}.txt"
    
    # Get all image files sorted by name
    image_files = sorted([
        f for f in seq_path.iterdir() 
        if f.suffix.lower() in ['.jpg', '.jpeg', '.png']
    ])
    
    if not image_files:
        print(f"  [warn] No images found in {seq_path}")
        return None
    
    print(f"  [info] Processing {seq_name}: {len(image_files)} frames")
    
    stats = {
        'sequence': seq_name,
        'frames': len(image_files),
        'total_detections': 0,
        'classes_detected': defaultdict(int)
    }
    
    # Tracking state
    prev_tracks = {}
    track_counter = 0
    
    # Open output file
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        
        for frame_idx, img_path in enumerate(image_files, start=1):
            # Run inference
            results = model.predict(
                source=str(img_path),
                imgsz=imgsz,
                conf=conf_threshold,
                verbose=False
            )[0]
            
            # Extract detections
            detections = []
            if results.boxes is not None and len(results.boxes) > 0:
                xyxy = results.boxes.xyxy.cpu().numpy()
                conf = results.boxes.conf.cpu().numpy()
                cls = results.boxes.cls.cpu().numpy().astype(int)
                
                for i in range(len(cls)):
                    x1, y1, x2, y2 = xyxy[i]
                    w = x2 - x1
                    h = y2 - y1
                    
                    # Convert Ultralytics class ID to VisDrone category ID
                    visdrone_cat = ULTRALYTICS_TO_VISDRONE.get(int(cls[i]), 0)
                    
                    detections.append({
                        'bbox': [float(x1), float(y1), float(x2), float(y2)],
                        'bbox_mot': [float(x1), float(y1), float(w), float(h)],
                        'confidence': float(conf[i]),
                        'class_id': visdrone_cat,
                    })
                    
                    stats['classes_detected'][visdrone_cat] += 1
            
            stats['total_detections'] += len(detections)
            
            # Apply simple tracking
            if detections:
                detections, prev_tracks, track_counter = simple_track(
                    detections, prev_tracks, track_counter
                )
            
            # Write detections in MOT format
            for det in detections:
                x1, y1, w, h = det['bbox_mot']
                row = [
                    frame_idx,              # frame_index
                    det['track_id'],        # target_id (track ID)
                    round(x1, 2),          # bbox_left
                    round(y1, 2),          # bbox_top
                    round(w, 2),           # bbox_width
                    round(h, 2),           # bbox_height
                    round(det['confidence'], 4),  # score
                    det['class_id'],        # object_category (VisDrone ID)
                    0,                      # truncation (not computed)
                    0                       # occlusion (not computed)
                ]
                writer.writerow(row)
    
    print(f"  [ok] Predictions saved: {output_file}")
    return stats


def main():
    ap = argparse.ArgumentParser(
        description="Run YOLO26 inference on VisDrone-MOT dataset"
    )
    ap.add_argument(
        "--model",
        default="/home/ubuntu/training/runs/detect/visdrone_finetune/yolo26n_t4_run2/weights/best.pt",
        help="Path to trained YOLO model (.pt file)"
    )
    ap.add_argument(
        "--images",
        required=True,
        help="Path to MOT images directory (containing sequence subfolders)"
    )
    ap.add_argument(
        "--output",
        default="mot_predictions",
        help="Output directory for prediction .txt files"
    )
    ap.add_argument(
        "--conf",
        type=float,
        default=0.25,
        help="Confidence threshold (default: 0.25, same as DET training)"
    )
    ap.add_argument(
        "--imgsz",
        type=int,
        default=1280,
        help="Image size for inference (default: 1280, same as training)"
    )
    ap.add_argument(
        "--sequences",
        default=None,
        help="Comma-separated list of sequence names to process (default: all)"
    )
    ap.add_argument(
        "--no-tracking",
        action="store_true",
        help="Disable tracking; assign unique ID per detection"
    )
    args = ap.parse_args()
    
    # Validate inputs
    model_path = Path(args.model)
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")
    
    images_dir = Path(args.images)
    if not images_dir.exists():
        raise FileNotFoundError(f"Images directory not found: {images_dir}")
    
    # Load model
    print(f"[info] Loading model: {model_path}")
    model = YOLO(str(model_path))
    print(f"[info] Model classes: {model.names}")
    print(f"[info] Inference settings: imgsz={args.imgsz}, conf={args.conf}")
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get sequence folders
    seq_folders = sorted([
        d for d in images_dir.iterdir() 
        if d.is_dir() and not d.name.startswith('.')
    ])
    
    if not seq_folders:
        raise FileNotFoundError(f"No sequence folders found in {images_dir}")
    
    # Filter sequences if specified
    if args.sequences:
        seq_names = {s.strip() for s in args.sequences.split(',')}
        seq_folders = [d for d in seq_folders if d.name in seq_names]
        if not seq_folders:
            raise ValueError(f"None of the specified sequences found: {seq_names}")
    
    print(f"\n[info] Found {len(seq_folders)} sequences to process")
    
    # Process each sequence
    all_stats = []
    for seq_path in seq_folders:
        try:
            if args.no_tracking:
                # Disable tracking by passing empty state each frame
                old_simple_track = simple_track
                def no_tracking(dets, prev, counter, **kwargs):
                    for i, det in enumerate(dets):
                        det['track_id'] = i + 1
                    return dets, {}, counter + len(dets)
                
                # Temporarily replace tracking function
                import builtins
                globals()['simple_track'] = no_tracking
            
            stats = process_sequence(
                model, seq_path, output_dir, args.conf, args.imgsz
            )
            
            if stats:
                all_stats.append(stats)
                
        except Exception as e:
            print(f"  [error] Failed to process {seq_path.name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Print summary
    print("\n" + "="*70)
    print("INFERENCE SUMMARY")
    print("="*70)
    
    total_frames = sum(s['frames'] for s in all_stats)
    total_dets = sum(s['total_detections'] for s in all_stats)
    
    print(f"Sequences processed : {len(all_stats)}")
    print(f"Total frames        : {total_frames}")
    print(f"Total detections    : {total_dets}")
    print(f"Avg detections/frame: {total_dets/total_frames:.2f}" if total_frames > 0 else "N/A")
    
    # Per-class statistics
    class_totals = defaultdict(int)
    for stats in all_stats:
        for cls, count in stats['classes_detected'].items():
            class_totals[cls] += count
    
    print("\nDetections per class:")
    for cls in sorted(class_totals.keys()):
        cat_name = CLASS_NAMES.get(cls, f"class_{cls}")
        count = class_totals[cls]
        pct = (count / total_dets * 100) if total_dets > 0 else 0
        print(f"  {cls:2d} ({cat_name:20s}): {count:6d} ({pct:5.1f}%)")
    
    print(f"\nPredictions saved to: {output_dir.absolute()}")
    print(f"\nTo analyze density and track lengths, run:")
    print(f"  python visdrone_mot_density.py --ann_dir {output_dir.absolute()}")
    

if __name__ == "__main__":
    main()
