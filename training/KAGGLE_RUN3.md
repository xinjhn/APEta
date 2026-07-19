# Kaggle run3 (official protocol) — start tonight

> **FINAL STATUS (verified 2026-07-14): DO NOT RESUME.** The current Kaggle
> notebook version is 2, and its latest session is complete after reaching the
> protocol's terminal early-stopping condition:
> 133 epochs in 9.844 hours, with the best result at epoch 118 and no
> improvement for the following 15 epochs. The saved checkpoints were
> optimizer-stripped (`epoch=-1`, `optimizer=None`), so they are final
> inference checkpoints rather than resumable optimizer state. Outputs and
> hashes are archived in
> [`kaggle/run3_official_final/RUN3_FINAL.md`](kaggle/run3_official_final/RUN3_FINAL.md).
> Starting again from `best.pt` would be a separately named extension with a
> reset optimizer/scheduler, not a continuation of `run3_official`.

> **SUPERSEDED IN PART (2026-07-09, late night):** the manual notebook workflow
> below hit three avoidable failures (nested mirror dirs, converter path never
> existing because `ape-training-assets` was never uploaded, DST pointed at
> read-only input). Everything now runs via the **Kaggle API** from this repo:
>
> - Code: `training/kaggle/train_run3.py` + `kernel-metadata.json`
>   (staging + verification + convert + gate + train + auto-resume, one script)
> - Launch:   `python -m kaggle kernels push -p training/kaggle`
> - Status:   `python -m kaggle kernels status jeihanilham/ape-yolo26-run3-official`
> - Log:      `python -m kaggle kernels output jeihanilham/ape-yolo26-run3-official -p <dir>`
> - Resume session: add `"kernel_sources": ["jeihanilham/ape-yolo26-run3-official"]`
>   to kernel-metadata.json (after version 1 exists) and push again — the script
>   detects the previous `last.pt` and resumes automatically.
> - Auth: KGAT token in `~/.kaggle/access_token` (NOT kaggle.json's `key` field).
> - Mirror defect found: `kushagrapandya/visdrone-dataset` val split has only
>   150/548 annotation files. Our own complete val (from `d:/TA/APEv2`) ships
>   inside `ape-training-assets`; the script prefers it automatically.
>
> The notebook cells below are kept as reference for what the script encodes.

Goal: train `yolo26n` with the OFFICIAL VisDrone-DET protocol (train = full
6,471; val = official 548), identical hyperparameters to
`train_yolo26.py` run3, on Kaggle GPUs. Nothing here touches the VM.

## Step 1 — Data: public mirror + one tiny private upload

Images/annotations come from the public Kaggle dataset
`kushagrapandya/visdrone-dataset` (add it via Notebook → Add Input). No 1.5 GB
upload needed. RULES for using a mirror you didn't build:

- The notebook MUST verify it matches the official protocol before training
  (Cell 2v below): train = 6,471 images, val = 548, and `annotations/*.txt`
  in RAW VisDrone format (8 comma-separated fields per line).
- If the mirror ships pre-converted YOLO `labels/`, IGNORE them. Labels must
  come from YOUR `prepare_visdrone.py`, same as run2, or the run2-vs-run3
  comparison gains a hidden variable (different ignored-region/class handling).

You still upload ONE tiny PRIVATE dataset, name it `ape-training-assets`
(a few MB, minutes):

```
prepare_visdrone.py                       (from d:/TA/APE VM/training/)
yolo26n.pt                                (pins the exact COCO init weights —
                                           don't rely on auto-download)
best_run2.pt                              (run2 weights, for the later
                                           model-comparison inference)
```

## Step 2 — Notebook settings (before running anything)

- Accelerator: **GPU T4 x2** (falls back to single T4 fine)
- Internet: **ON** (needed for `pip install`)
- Requires a phone-verified Kaggle account for GPU + internet.

## Step 3 — Notebook cells (Session 1)

**Cell 1 — environment (pin the version from the VM's env snapshot):**
```python
!pip install -q ultralytics==8.4.15
import torch, ultralytics
print(ultralytics.__version__, torch.cuda.device_count(), torch.cuda.get_device_name(0))
```

**Cell 2 — stage + verify + convert + gate, ONE idempotent cell (evolved
through three real failures: nested mirror dirs, a skipped converter whose
error scrolled by, and a DST accidentally pointed at read-only /kaggle/input):**
```python
import glob, os, shutil, subprocess, sys

DST = "/kaggle/working/VisDrone"   # writable workspace — NEVER a /kaggle/input path
SPLITS = {"VisDrone2019-DET-train": 6471, "VisDrone2019-DET-val": 548}

# --- stage fresh (clean slate kills all partial-copy traps) ---
if os.path.exists(DST):
    shutil.rmtree(DST)
for split, expect in SPLITS.items():
    hits = sorted(set(
        glob.glob(f"/kaggle/input/**/{split}/**/images", recursive=True) +
        glob.glob(f"/kaggle/input/**/{split}/images",   recursive=True)), key=len)
    assert hits, f"{split}: no images dir found under /kaggle/input"
    img_dir = hits[0]
    ann_dir = os.path.join(os.path.dirname(img_dir), "annotations")
    n_img, n_ann = len(os.listdir(img_dir)), len(os.listdir(ann_dir))
    print(f"{split}: SOURCE images={n_img} annotations={n_ann}  ({img_dir})")
    assert n_img == expect,  f"{split}: source has {n_img} images, expected {expect} — STOP"
    assert n_ann == expect,  f"{split}: source has only {n_ann} annotations — defective mirror, STOP"
    shutil.copytree(img_dir, f"{DST}/{split}/images")
    shutil.copytree(ann_dir, f"{DST}/{split}/annotations")

# --- convert with YOUR script (path self-located, output shown, rc checked) ---
script = glob.glob("/kaggle/input/**/prepare_visdrone.py", recursive=True)
assert script, "prepare_visdrone.py not found in any attached dataset"
r = subprocess.run([sys.executable, script[0], "--root", DST, "--convert-val"],
                   capture_output=True, text=True)
print(r.stdout[-2000:]); print(r.stderr[-1000:])
assert r.returncode == 0, "converter crashed — read stderr above"

# --- label gate ---
for split, expect in SPLITS.items():
    lbls = glob.glob(f"{DST}/{split}/labels/*.txt")
    nonempty = sum(1 for f in lbls if os.path.getsize(f) > 0)
    print(f"{split}: {len(lbls)} label files, {nonempty} non-empty")
    assert len(lbls) == expect and nonempty > expect * 0.9, f"{split}: label gate FAILED"
for c in glob.glob(f"{DST}/**/labels.cache", recursive=True):
    os.remove(c)
print("DATA READY — proceed to yaml + train")
```

If the SOURCE annotation assert fails on val (mirror ships <548 annotation
files): upload `VisDrone2019-DET-val` (images + annotations) from
`d:/TA/APEv2/datasets/VisDrone` into `ape-training-assets` (~80 MB) and re-run
— the glob picks it up automatically.

**LESSONS (each cost a real aborted attempt):**
- Every fresh Kaggle session wipes `/kaggle/working` — this cell + yaml cell
  must re-run at the start of EVERY session, including resume sessions.
- When training starts, READ the dataset scan line: it must say roughly
  `6448 images, 23 backgrounds`. "0 images, 6471 backgrounds" = training on
  nothing — kill the run immediately.

**Cell 4 — dataset yaml (same content as visdrone_official.yaml, Kaggle paths):**
```python
yaml_text = """
path: /kaggle/working/VisDrone
train: VisDrone2019-DET-train/images
val: VisDrone2019-DET-val/images
nc: 10
names:
  0: pedestrian
  1: people
  2: bicycle
  3: car
  4: van
  5: truck
  6: tricycle
  7: awning-tricycle
  8: bus
  9: motor
"""
open("/kaggle/working/visdrone_official.yaml", "w").write(yaml_text)
```

**Cell 5 — train (run3 args verbatim, three deliberate deviations, all noted):**
```python
from ultralytics import YOLO
import torch

model = YOLO("/kaggle/input/ape-training-assets/yolo26n.pt")

two_gpus = torch.cuda.device_count() >= 2
model.train(
    data="/kaggle/working/visdrone_official.yaml",
    epochs=200, patience=15,
    imgsz=1280,
    # DEVIATION 1: batch 8 on T4x2 (4/GPU — same per-GPU batch as the VM plan);
    # falls back to the original batch=4 on a single T4.
    batch=8 if two_gpus else 4,
    device=[0, 1] if two_gpus else 0,
    cache=False, workers=4,          # DEVIATION 2: Kaggle gives 4 vCPU, not 8
    amp=True,
    optimizer="SGD", lr0=0.01, momentum=0.937,   # explicit — never "auto"/MuSGD
    freeze=None, warmup_epochs=3.0,
    seed=42, deterministic=False,
    # DEVIATION 3: stop cleanly BEFORE Kaggle's 12 h hard kill so the commit
    # completes and /kaggle/working is saved as a resumable output.
    time=10.0,                       # hours; overrides epochs if hit first
    project="/kaggle/working/runs/detect/visdrone_finetune",
    name="yolo26n_kaggle_run3_official",
    exist_ok=False, plots=True,
)
```

**Cell 6 — package what matters (runs even if training stopped on `time=`):**
```python
!ls /kaggle/working/runs/detect/visdrone_finetune/yolo26n_kaggle_run3_official/weights
# best.pt + last.pt are inside the saved output of this notebook version.
```

Run with **"Save & Run All (Commit)"** — NOT interactive — so it executes in
the background with your browser closed. A committed run that finishes (which
`time=10.0` guarantees) persists all of `/kaggle/working` as versioned output.
Interactive sessions that disconnect lose everything.

## Step 4 — Session 2+ (resume, tomorrow)

1. Notebook → Add Input → your own notebook's **previous version output**.
2. Replace Cell 5 with:
```python
import shutil, os
from ultralytics import YOLO
# Recreate the EXACT same paths the checkpoint remembers:
# (Cells 2–4 must have run first — same staging, same yaml path.)
PREV = "/kaggle/input/<your-notebook-slug>/runs/detect/visdrone_finetune/yolo26n_kaggle_run3_official"
DEST = "/kaggle/working/runs/detect/visdrone_finetune/yolo26n_kaggle_run3_official"
os.makedirs(os.path.dirname(DEST), exist_ok=True)
shutil.copytree(PREV, DEST)
model = YOLO(f"{DEST}/weights/last.pt")
model.train(resume=True, time=10.0)
```
3. Commit again. Repeat until it early-stops (`patience=15`) or reaches 200.
   Budget: ~25 h worst case ≈ 2–3 sessions; weekly GPU quota is 30 h — fits,
   and T4x2 halves the wall-clock estimate.

## Step 5 — after training: the two pinned inference passes (model comparison)

Same notebook, new session, GPU on. For BOTH `best_run2.pt` (already in
`ape-training-assets`) and the new `best.pt`, with IDENTICAL args:

```
python infer_mot.py --model <weights> --images <MOT-val>/images \
    --conf 0.25 --output preds_<runname>
python mot_compute_density.py ... (same tier thresholds as the corpus)
```

This needs MOT-val frames uploaded too (or run this part on the laptop — 2,846
frames is light). Record in a manifest: weights md5, ultralytics 8.4.15,
imgsz, conf 0.25, NMS IoU. Both models must go through the same pass — do NOT
reuse the old mot_predictions_density.csv as run2's side of the comparison.

## Hard rules (same spirit as the VM prompt)

- `mot_detections.db` is frozen. Nothing from this training regenerates it.
- One deviation ledger: batch 8 (T4x2), workers 4, `time=10.0` session cap —
  everything else byte-identical to train_yolo26.py run3. Report these in the
  laporan's training section.
- If DDP on T4x2 misbehaves in the notebook (rare but possible), drop to
  `device=0, batch=4` — that is then ZERO deviations from the original plan,
  just slower (~2 sessions more).
