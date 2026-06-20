"""
orchestrator/make_run_plan.py
==============================
Pembangkit run plan -- DETERMINISTIK, dijalankan sekali per sesi eksperimen.

BLOK = (protocol, pattern, density, concurrency). Urutan eksekusi blok diacak
dengan seed tetap (PANDUAN Bagian 4) sehingga "protokol mana duluan" otomatis
seimbang tanpa perlu logika tambahan -- blok REST & GraphQL dari satu sel
pembanding ikut teracak posisinya secara independen.

run_plan.csv adalah KONTRAK TETAP: jangan diregenerasi di tengah sesi
eksekusi (lihat orchestrator/run_experiment.py untuk logika RESUME yang
bergantung pada urutan baris file ini tidak berubah).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import random
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.config import PROTOCOLS, get_config  # noqa: E402

FIELDNAMES = [
    "run_uid",
    "block_id",
    "block_order",
    "protocol",
    "pattern",
    "density",
    "concurrency",
    "run_index",
    "is_warmup",
]


def _run_uid(protocol: str, pattern: str, density: str, concurrency: int, is_warmup: bool, run_index: int) -> str:
    key = f"{protocol}|{pattern}|{density}|{concurrency}|{int(is_warmup)}|{run_index}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def build_blocks(patterns: List[str], densities: List[str], concurrency_levels: List[int]) -> List[dict]:
    """Enumerasi KANONIK (urutan stabil, sebelum diacak) -> block_id stabil."""
    blocks = []
    for idx, (protocol, pattern, density, concurrency) in enumerate(
        itertools.product(PROTOCOLS, patterns, densities, concurrency_levels)
    ):
        blocks.append(
            {
                "block_id": f"B{idx:04d}",
                "protocol": protocol,
                "pattern": pattern,
                "density": density,
                "concurrency": concurrency,
            }
        )
    return blocks


def build_plan_rows(blocks: List[dict], n_warmup: int, n_measured: int, seed: int) -> List[dict]:
    shuffled = list(blocks)
    random.Random(seed).shuffle(shuffled)

    rows = []
    for block_order, block in enumerate(shuffled):
        for run_index in range(n_warmup):
            rows.append(_row(block, block_order, run_index, is_warmup=True))
        for run_index in range(n_measured):
            rows.append(_row(block, block_order, run_index, is_warmup=False))
    return rows


def _row(block: dict, block_order: int, run_index: int, is_warmup: bool) -> dict:
    return {
        "run_uid": _run_uid(
            block["protocol"], block["pattern"], block["density"], block["concurrency"], is_warmup, run_index
        ),
        "block_id": block["block_id"],
        "block_order": block_order,
        "protocol": block["protocol"],
        "pattern": block["pattern"],
        "density": block["density"],
        "concurrency": block["concurrency"],
        "run_index": run_index,
        "is_warmup": int(is_warmup),
    }


def write_plan(rows: List[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    cfg = get_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(cfg.run_plan_csv))
    args = ap.parse_args()

    patterns = cfg.active_patterns()
    densities = cfg.active_densities()
    concurrency = cfg.active_concurrency()

    blocks = build_blocks(patterns, densities, concurrency)
    rows = build_plan_rows(blocks, cfg.n_warmup, cfg.n_measured, cfg.seed)

    out_path = Path(args.out)
    write_plan(rows, out_path)

    n_blocks = len(blocks)
    n_measured_rows = sum(1 for r in rows if not r["is_warmup"])
    n_warmup_rows = sum(1 for r in rows if r["is_warmup"])
    print(f"Mode: {'PILOT' if cfg.pilot else 'FULL'}")
    print(f"Blok: {n_blocks} (protocols={len(PROTOCOLS)} x patterns={len(patterns)} x "
          f"densities={len(densities)} x concurrency={len(concurrency)})")
    print(f"Baris warmup: {n_warmup_rows} | Baris terukur: {n_measured_rows} | Total: {len(rows)}")
    print(f"Seed: {cfg.seed}")
    print(f"Ditulis ke {out_path}")


if __name__ == "__main__":
    main()
