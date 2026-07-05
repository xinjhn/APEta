#!/usr/bin/env python3
"""
infer_mot_track.py
==================
Run YOLO26 with native ByteTrack tracking on VisDrone-MOT dataset.

This script uses Ultralytics' built-in tracking (ByteTrack/BoT-SORT) to produce
self-consistent track IDs from the model itself, rather than stitching GT tracks.

USAGE
-----
  # Default: ByteTrack tracker
  python infer_mot_track.py \
      --images /home/ubuntu/datasets/VisDrone/VisDrone2019-MOT-val/sequences \
      --output mot_val_predictions_tracked

  # Use BoT-SORT instead
  python infer_mot_track.py --images ... --tracker botsort

  # Custom confidence and tracking thresholds
  python infer_mot_track.py --images ... --conf 0.3 --track_conf 0.5

  # Process specific sequences
  python infer_mot_track.py --images ... --sequences uav0000137_00458_v
"""

import argparse
import csv
from pathlib import Path

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


def process_sequence_with_tracking(model, seq_path, output_dir, conf_threshold, 
                                    track_conf, iou_threshold, tracker):
    """
    Process a single sequence using YOLO's native tracking mode.
    
    Args:
        model: YOLO model instance
        seq_path: Path to sequence folder containing frame images
        output_dir: Directory to write output .txt file
        conf_threshold: Detection confidence threshold
        track_conf: Tracking confidence threshold
        iou_threshold: IoU threshold for tracking association
        tracker: Tracker type ('bytetrack' or 'botsort')
    
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
    
    print(f"  [info] Processing {seq_name}: {len(image_files)} frames (tracker={tracker})")
    
    stats = {
        'sequence': seq_name,
        'frames': len(image_files),
        'total_detections': 0,
        'classes_detected': {}
    }
    
    # Open output file
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Use YOLO's native tracking - pass entire sequence as video source
        # This is more efficient and produces consistent track IDs
        results = model.track(
            source=str(seq_path),
            imgsz=1280,
            conf=conf_threshold,
            iou=iou_threshold,
            tracker=tracker,
            verbose=False,
            persist=True,  # Maintain tracker state across frames
        )
        
        for frame_idx, result in enumerate(results, start=1):
            # Extract tracked detections
            if result.boxes is None or len(result.boxes) == 0:
                continue
            
            xyxy = result.boxes.xyxy.cpu().numpy()
            conf = result.boxes.conf.cpu().numpy()
            cls = result.boxes.cls.cpu().numpy().astype(int)
            track_ids = result.boxes.id.cpu().numpy().astype(int) if result.boxes.id is not None else None
            
            for i in range(len(cls)):
                x1, y1, x2, y2 = xyxy[i]
                w = x2 - x1
                h = y2 - y1
                
                # Convert Ultralytics class ID to VisDrone category ID
                visdrone_cat = ULTRALYTICS_TO_VISDRONE.get(int(cls[i]), 0)
                
                # Get track ID (if tracking failed, use detection index)
                tid = int(track_ids[i]) if track_ids is not None else i + 1
                
                row = [
                    frame_idx,              # frame_index
                    tid,                    # target_id (from ByteTrack/BoT-SORT)
                    round(float(x1), 2),   # bbox_left
                    round(float(y1), 2),   # bbox_top
                    round(float(w), 2),    # bbox_width
                    round(float(h), 2),    # bbox_height
                    round(float(conf[i]), 4),  # score
                    visdrone_cat,           # object_category (VisDrone ID)
                    0,                      # truncation
                    0                       # occlusion
                ]
                writer.writerow(row)
                
                stats['total_detections'] += 1
                stats['classes_detected'][visdrone_cat] = \
                    stats['classes_detected'].get(visdrone_cat, 0) + 1
    
    print(f"  [ok] Predictions saved: {output_file} ({stats['total_detections']} detections)")
    return stats


def main():
    ap = argparse.ArgumentParser(
        description="Run YOLO26 with native ByteTrack/BoT-SORT on VisDrone-MOT"
    )
    ap.add_argument(
        "--model",
        default="/home/ubuntu/training/runs/detect/visdrone_finetune/yolo26n_t4_run2/weights/best.pt",
        help="Path to trained YOLO model (.pt file)"
    )
    ap.add_argument(
        "--images",
        required=True,
        help="Path to MOT sequences directory (containing sequence subfolders)"
    )
    ap.add_argument(
        "--output",
        default="mot_val_predictions_tracked",
        help="Output directory for prediction .txt files"
    )
    ap.add_argument(
        "--conf",
        type=float,
        default=0.25,
        help="Detection confidence threshold (default: 0.25)"
    )
    ap.add_argument(
        "--track_conf",
        type=float,
        default=0.5,
        help="Tracking confidence threshold (default: 0.5)"
    )
    ap.add_argument(
        "--iou",
        type=float,
        default=0.7,
        help="IoU threshold for tracking association (default: 0.7)"
    )
    ap.add_argument(
        "--tracker",
        choices=['bytetrack', 'botsort'],
        default='bytetrack',
        help="Tracker algorithm (default: bytetrack)"
    )
    ap.add_argument(
        "--imgsz",
        type=int,
        default=1280,
        help="Image size for inference (default: 1280)"
    )
    ap.add_argument(
        "--sequences",
        default=None,
        help="Comma-separated list of sequence names to process (default: all)"
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
    print(f"[info] Settings: imgsz={args.imgsz}, conf={args.conf}, "
          f"track_conf={args.track_conf}, iou={args.iou}, tracker={args.tracker}")
    
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
    
    print(f"\n[info] Found {len(seq_folders)} sequences to process\n")
    
    # Process each sequence
    all_stats = []
    for seq_path in seq_folders:
        try:
            stats = process_sequence_with_tracking(
                model, seq_path, output_dir, 
                args.conf, args.track_conf, args.iou, args.tracker
            )
            
            if stats:
                all_stats.append(stats)
                
        except Exception as e:
            print(f"  [error] Failed to process {seq_path.name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Print summary
    print("\n" + "="*70)
    print("TRACKING INFERENCE SUMMARY")
    print("="*70)
    
    total_frames = sum(s['frames'] for s in all_stats)
    total_dets = sum(s['total_detections'] for s in all_stats)
    
    print(f"Sequences processed : {len(all_stats)}")
    print(f"Total frames        : {total_frames}")
    print(f"Total detections    : {total_dets}")
    print(f"Avg detections/frame: {total_dets/total_frames:.2f}" if total_frames > 0 else "N/A")
    
    # Per-class statistics
    class_totals = {}
    for stats in all_stats:
        for cls, count in stats['classes_detected'].items():
            class_totals[cls] = class_totals.get(cls, 0) + count
    
    print("\nDetections per class:")
    for cls in sorted(class_totals.keys()):
        cat_name = CLASS_NAMES.get(cls, f"class_{cls}")
        count = class_totals[cls]
        pct = (count / total_dets * 100) if total_dets > 0 else 0
        print(f"  {cls:2d} ({cat_name:20s}): {count:6d} ({pct:5.1f}%)")
    
    print(f"\nPredictions saved to: {output_dir.absolute()}")
    print(f"\nTo analyze density and track lengths, run:")
    print(f"  python mot_compute_density.py --dir {output_dir.absolute()}")
    

if __name__ == "__main__":
    main()
