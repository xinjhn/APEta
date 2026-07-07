"""
rerun_pilot.py
==============
Reproduksi pilot laju iterasi training YOLO26 di T4
(lihat laporan/reproducibility/PILOT_TRAINING_YOLO26.md).

Menjalankan tiga sel dengan SATU variabel berbeda (optimizer); semua sel
memakai epochs=200 agar aturan optimizer="auto" memilih MuSGD seperti pada
run sesungguhnya. Laju dibaca dari progress bar pada iterasi >= 100 lalu
proses dihentikan.

JALANKAN HANYA SAAT GPU IDLE. Butuh ~10 menit total.

Cara pakai:
  cd ~/training && python pilots/2026-07-07_optimizer_pace/rerun_pilot.py
"""

import re
import subprocess
import sys
from pathlib import Path

PILOT_DIR = Path(__file__).parent
TRAIN_DIR = PILOT_DIR.parent.parent  # ~/training
PY = sys.executable

CELLS = {
    # nama sel -> argumen optimizer (None = "auto" -> MuSGD karena >10k iterasi)
    "auto_musgd": 'optimizer="auto"',
    "sgd": 'optimizer="SGD", lr0=0.01, momentum=0.937',
    "adamw": 'optimizer="AdamW"',
}

TEMPLATE = """
from ultralytics import YOLO
YOLO("yolo26n.pt").train(
    data="visdrone_official.yaml", epochs=200, patience=15,
    imgsz=1280, batch=4, cache=False, device=0, workers=8, amp=True,
    {opt}, freeze=None, warmup_epochs=3.0,
    seed=42, deterministic=False,
    project="{proj}", name="{name}", exist_ok=True, plots=False, val=False,
)
"""

PACE_RE = re.compile(r" (\d+)/\d+ (\d+(?:\.\d+)?)(s/it|it/s) ")
OPT_RE = re.compile(r"optimizer: (\S+)\(")


def run_cell(name: str, opt: str, min_iter: int = 100, timeout: int = 420):
    script = PILOT_DIR / f"_cell_{name}.py"
    script.write_text(TEMPLATE.format(opt=opt, proj=PILOT_DIR / "rerun_runs", name=name))
    proc = subprocess.Popen(
        [PY, "-u", str(script)], cwd=TRAIN_DIR,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    chosen, pace = "?", None
    try:
        for line in proc.stdout:
            for chunk in line.split("\r"):
                m = OPT_RE.search(chunk)
                if m:
                    chosen = m.group(1)
                m = PACE_RE.search(chunk)
                if m and int(m.group(1)) >= min_iter:
                    val, unit = float(m.group(2)), m.group(3)
                    pace = f"{val} {unit}"
                    s_per_it = val if unit == "s/it" else 1.0 / val
                    proc.kill()
                    return chosen, pace, s_per_it
    finally:
        proc.kill()
        proc.wait()
        script.unlink(missing_ok=True)
    return chosen, pace, None


def main():
    out = PILOT_DIR / "rerun_results.csv"
    rows = ["cell,optimizer_resolved,pace,s_per_it"]
    for name, opt in CELLS.items():
        print(f"[cell {name}] {opt} ...", flush=True)
        chosen, pace, s_per_it = run_cell(name, opt)
        print(f"  -> optimizer={chosen}  pace={pace}", flush=True)
        rows.append(f"{name},{chosen},{pace},{s_per_it}")
    out.write_text("\n".join(rows) + "\n")
    print(f"\nHasil ditulis ke {out}")


if __name__ == "__main__":
    main()
