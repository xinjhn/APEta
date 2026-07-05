# VisDrone-MOT Inference Guide

## Dataset Status
The VisDrone-MOT dataset is **NOT** currently in `/home/ubuntu/datasets/`. You need to download it first.

## Download VisDrone-MOT

### Option 1: Official Website
Visit: http://www.visdrone.org/downloads.html

Download:
- **VisDrone2019-MOT-val** (for validation/testing)
- Or **VisDrone2019-MOT-train** (for training)

### Option 2: Direct Download (if available)
```bash
cd /home/ubuntu/datasets
wget <VISDRONE_MOT_URL>
unzip VisDrone2019-MOT-val.zip
```

## Expected Directory Structure

After extraction, you should have:
```
/home/ubuntu/datasets/VisDrone/
├── VisDrone2019-DET-train/    (already exists)
├── VisDrone2019-DET-val/      (already exists)
└── VisDrone2019-MOT-val/      (needs to be added)
    ├── images/
    │   ├── uav0000137_00458_v/
    │   │   ├── 0000001.jpg
    │   │   ├── 0000002.jpg
    │   │   └── ...
    │   ├── uav0000137_00459_v/
    │   └── ...
    └── annotations/           (optional, for comparison)
        ├── uav0000137_00458_v.txt
        └── ...
```

## Running Inference

Once you have the MOT dataset, run:

```bash
cd /home/ubuntu/training

# Basic inference with default settings
python infer_mot.py \
    --images /home/ubuntu/datasets/VisDrone/VisDrone2019-MOT-val/images \
    --output mot_val_predictions

# With custom confidence threshold
python infer_mot.py \
    --images /home/ubuntu/datasets/VisDrone/VisDrone2019-MOT-val/images \
    --conf 0.3 \
    --output mot_val_predictions_conf30

# Process specific sequences only
python infer_mot.py \
    --images /home/ubuntu/datasets/VisDrone/VisDrone2019-MOT-val/images \
    --sequences uav0000137_00458_v,uav0000137_00459_v \
    --output mot_val_subset

# Without tracking (each detection gets unique ID)
python infer_mot.py \
    --images /home/ubuntu/datasets/VisDrone/VisDrone2019-MOT-val/images \
    --no-tracking \
    --output mot_val_no_track
```

## Output Format

The script generates `.txt` files in VisDrone-MOT annotation format (10 columns):
```
frame_index, target_id, bbox_left, bbox_top, bbox_w, bbox_h, score, object_category, truncation, occlusion
```

Example line:
```
1,1,234.5,123.8,45.2,67.3,0.8523,4,0,0
```

Where:
- `frame_index`: Frame number (1-based)
- `target_id`: Track ID (assigned by simple IoU tracker)
- `bbox_left/top/w/h`: Bounding box coordinates
- `score`: Detection confidence
- `object_category`: VisDrone category ID (1-10, NOT 0-9)
- `truncation`: Always 0 (not computed)
- `occlusion`: Always 0 (not computed)

## Analyzing Results

After inference, use the density analysis script:

```bash
# Analyze per-frame density and track lengths
python visdrone_mot_density.py \
    --ann_dir mot_val_predictions \
    --classes mot5 \
    --drop_heavy_occlusion

# For all 10 classes
python visdrone_mot_density.py \
    --ann_dir mot_val_predictions \
    --classes all
```

## Model Details

- **Model**: YOLO26n fine-tuned on VisDrone-DET
- **Location**: `/home/ubuntu/training/runs/detect/visdrone_finetune/yolo26n_t4_run2/weights/best.pt`
- **Classes**: 10 VisDrone categories (pedestrian, people, bicycle, car, van, truck, tricycle, awning-tricycle, bus, motor)
- **Training resolution**: 1280x1280
- **Default confidence**: 0.25

## Important Notes

1. **Category IDs**: The model outputs Ultralytics indices (0-9), which are converted to raw VisDrone IDs (1-10) in the output.

2. **Tracking**: The script uses a simple IoU-based tracker. For production-quality tracking, consider integrating ByteTrack, DeepSORT, or similar trackers.

3. **Memory**: Processing at imgsz=1280 requires ~8-10GB VRAM. The T4 GPU should handle this comfortably.

4. **Speed**: Expect ~2-5 FPS per sequence depending on image size and GPU utilization.

5. **No Ground Truth Required**: This script only needs the image sequences. Annotations are optional for comparison.
