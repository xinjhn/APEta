"""
train_run3.py — Kaggle kernel: YOLO26n run3, official VisDrone-DET protocol.
Pushed/monitored via Kaggle API (see training/KAGGLE_RUN3.md).

Deviation ledger vs train_yolo26.py (VM run3 plan) — report these in laporan:
  - batch 8 on T4x2 (4/GPU, same per-GPU batch), auto-falls back to 4 on 1 GPU
  - workers 4 (Kaggle vCPU count)
  - time=10.0h session cap (Kaggle kills sessions at 12h WITHOUT saving output;
    ultralytics time-budget training adapts the LR schedule to the budget)
Everything else identical: SGD lr0=0.01 momentum=0.937, imgsz=1280, seed=42,
patience=15, epochs ceiling 200, freeze=None, warmup 3.0, amp.

Resume: if a previous version's output (last.pt) is mounted as an input
(kernel_sources includes this kernel), training resumes automatically.
"""
import glob
import os
import shutil
import subprocess
import sys

subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                "ultralytics==8.4.15"], check=True)

DST = "/kaggle/working/VisDrone"
RUN_NAME = "yolo26n_kaggle_run3_official"
RUN_DIR = f"/kaggle/working/runs/detect/visdrone_finetune/{RUN_NAME}"
SPLITS = {"VisDrone2019-DET-train": 6471, "VisDrone2019-DET-val": 548}


def locate(split: str) -> tuple[str, str]:
    """Find images+annotations for a split; prefer ape-training-assets over
    the public mirror (mirror's val annotations are incomplete: 150/548)."""
    hits = sorted(set(
        glob.glob(f"/kaggle/input/**/{split}/**/images", recursive=True) +
        glob.glob(f"/kaggle/input/**/{split}/images", recursive=True)),
        key=lambda p: ("ape-training-assets" not in p, len(p)))
    assert hits, f"{split}: no images dir found under /kaggle/input"
    img_dir = hits[0]
    ann_dir = os.path.join(os.path.dirname(img_dir), "annotations")
    assert os.path.isdir(ann_dir), f"{split}: no annotations next to {img_dir}"
    return img_dir, ann_dir


def stage_and_convert() -> None:
    if os.path.exists(DST):
        shutil.rmtree(DST)
    for split, expect in SPLITS.items():
        img_dir, ann_dir = locate(split)
        n_img, n_ann = len(os.listdir(img_dir)), len(os.listdir(ann_dir))
        print(f"{split}: SOURCE images={n_img} annotations={n_ann} ({img_dir})", flush=True)
        assert n_img == expect, f"{split}: {n_img} images, expected {expect}"
        assert n_ann == expect, f"{split}: only {n_ann} annotations — defective source"
        shutil.copytree(img_dir, f"{DST}/{split}/images")
        shutil.copytree(ann_dir, f"{DST}/{split}/annotations")

    script = glob.glob("/kaggle/input/**/prepare_visdrone.py", recursive=True)
    assert script, "prepare_visdrone.py not found in inputs"
    r = subprocess.run([sys.executable, script[0], "--root", DST, "--convert-val"],
                       capture_output=True, text=True)
    print(r.stdout[-2000:], r.stderr[-1000:], flush=True)
    assert r.returncode == 0, "converter crashed"

    for split, expect in SPLITS.items():
        lbls = glob.glob(f"{DST}/{split}/labels/*.txt")
        nonempty = sum(1 for f in lbls if os.path.getsize(f) > 0)
        print(f"{split}: {len(lbls)} label files, {nonempty} non-empty", flush=True)
        assert len(lbls) == expect and nonempty > expect * 0.9, f"{split}: label gate FAILED"
    for c in glob.glob(f"{DST}/**/labels.cache", recursive=True):
        os.remove(c)


def write_yaml() -> str:
    path = "/kaggle/working/visdrone_official.yaml"
    names = ["pedestrian", "people", "bicycle", "car", "van", "truck",
             "tricycle", "awning-tricycle", "bus", "motor"]
    with open(path, "w") as f:
        f.write(f"path: {DST}\n"
                "train: VisDrone2019-DET-train/images\n"
                "val: VisDrone2019-DET-val/images\n"
                "nc: 10\nnames:\n")
        f.writelines(f"  {i}: {n}\n" for i, n in enumerate(names))
    return path


def main() -> None:
    import torch
    from ultralytics import YOLO

    stage_and_convert()
    data_yaml = write_yaml()

    prev = glob.glob(f"/kaggle/input/**/{RUN_NAME}/weights/last.pt", recursive=True)
    if prev:
        print(f"RESUMING from {prev[0]}", flush=True)
        os.makedirs(os.path.dirname(RUN_DIR), exist_ok=True)
        shutil.copytree(os.path.dirname(os.path.dirname(prev[0])), RUN_DIR)
        model = YOLO(f"{RUN_DIR}/weights/last.pt")
        model.train(resume=True, time=10.0)
    else:
        two_gpus = torch.cuda.device_count() >= 2
        print(f"FRESH START | GPUs: {torch.cuda.device_count()}", flush=True)
        weights = glob.glob("/kaggle/input/**/yolo26n.pt", recursive=True)
        assert weights, "yolo26n.pt not found in inputs"
        model = YOLO(sorted(weights, key=len)[0])
        model.train(
            data=data_yaml,
            epochs=200, patience=15,
            imgsz=1280,
            batch=8 if two_gpus else 4,
            device=[0, 1] if two_gpus else 0,
            cache=False, workers=4, amp=True,
            optimizer="SGD", lr0=0.01, momentum=0.937,
            freeze=None, warmup_epochs=3.0,
            seed=42, deterministic=False,
            time=10.0,
            project="/kaggle/working/runs/detect/visdrone_finetune",
            name=RUN_NAME, exist_ok=False, plots=True,
        )

    # keep the saved output lean: drop the staged dataset copy (1.5 GB),
    # keep runs/ (weights, curves, results.csv)
    shutil.rmtree(DST, ignore_errors=True)
    print("SESSION DONE. Weights under:", RUN_DIR, flush=True)


if __name__ == "__main__":
    main()
