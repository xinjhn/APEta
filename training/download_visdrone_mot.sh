#!/bin/bash
# download_visdrone_mot.sh
# =========================
# Helper script to download VisDrone2019-MOT-val dataset
#
# The dataset is hosted on BaiduYun and GoogleDrive (not direct HTTP).
# You must download it manually from one of these sources:
#
# Option 1: Google Drive (recommended for international users)
#   Visit: https://github.com/VisDrone/VisDrone-Dataset
#   Navigate to: Task 4: Multi-Object Tracking -> valset -> GoogleDrive
#   Download the file and place it in: /home/ubuntu/datasets/VisDrone/
#
# Option 2: BaiduYun (for users in China)
#   Visit: https://github.com/VisDrone/VisDrone-Dataset
#   Navigate to: Task 4: Multi-Object Tracking -> valset -> BaiduYun
#
# After downloading, extract:
#   cd /home/ubuntu/datasets/VisDrone
#   unzip VisDrone2019-MOT-val.zip
#
# Expected structure after extraction:
#   VisDrone2019-MOT-val/
#     ├── sequences/
#     │   ├── uav0000137_00458_v/
#     │   │   ├── 0000001.jpg
#     │   │   ├── 0000002.jpg
#     │   │   └── ...
#     │   └── ...
#     └── annotations/
#         ├── uav0000137_00458_v.txt
#         └── ...

echo "VisDrone2019-MOT-val Download Instructions"
echo "==========================================="
echo ""
echo "The dataset cannot be downloaded via wget/curl due to hosting on:"
echo "  - Google Drive (requires browser authentication)"
echo "  - BaiduYun (requires Chinese account)"
echo ""
echo "Steps to download:"
echo "1. Visit: https://github.com/VisDrone/VisDrone-Dataset"
echo "2. Scroll to 'Task 4: Multi-Object Tracking'"
echo "3. Click 'GoogleDrive' link next to 'valset (1.48 GB)'"
echo "4. Download the ZIP file"
echo "5. Move it to: /home/ubuntu/datasets/VisDrone/"
echo "6. Run: unzip VisDrone2019-MOT-val.zip"
echo ""
echo "After extraction, verify structure:"
echo "  ls /home/ubuntu/datasets/VisDrone/VisDrone2019-MOT-val/sequences/"
echo ""
echo "Then run inference:"
echo "  cd /home/ubuntu/training"
echo "  ~/miniconda3/envs/yolo_env/bin/python infer_mot.py \\"
echo "      --images /home/ubuntu/datasets/VisDrone/VisDrone2019-MOT-val/sequences \\"
echo "      --output mot_val_predictions"
echo ""
