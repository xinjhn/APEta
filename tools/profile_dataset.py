"""
tools/profile_dataset.py
=========================
Profil densitas dari JSON inferensi (Tahap [B]). Memakai pemuat & penghitung
kuartil yang SAMA dengan yang dipakai server (`core.pool`) agar angka yang
keluar di sini dijamin konsisten dengan ambang yang akan dipakai saat eksekusi.

Hasil Q1/Q3 di sini dimaksudkan untuk memperbarui Tabel IV.1 di laporan.

Pemakaian:
    python tools/profile_dataset.py --json /path/inferensi.json \
        --out results/density_profile.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.pool import compute_quartiles, detection_count, load_records, stratify  # noqa: E402


def profile(records: list) -> dict:
    counts = [detection_count(r) for r in records]
    q1, q3 = compute_quartiles(records)
    tiers = stratify(records, q1, q3)

    return {
        "n_images": len(records),
        "min": min(counts),
        "max": max(counts),
        "mean": statistics.fmean(counts),
        "median": statistics.median(counts),
        "std": statistics.pstdev(counts) if len(counts) > 1 else 0.0,
        "q1": q1,
        "q3": q3,
        "tier_counts": {tier: len(recs) for tier, recs in tiers.items()},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", required=True, help="path JSON inferensi (format core.pool.load_records)")
    ap.add_argument("--out", default="results/density_profile.json")
    args = ap.parse_args()

    records = load_records(args.json)
    if not records:
        raise SystemExit("Dataset kosong -- tidak ada record untuk diprofilkan.")

    result = profile(records)

    print(f"N citra       : {result['n_images']}")
    print(f"min / max     : {result['min']} / {result['max']}")
    print(f"mean / median : {result['mean']:.2f} / {result['median']:.2f}")
    print(f"std           : {result['std']:.2f}")
    print(f"Q1 / Q3       : {result['q1']:.2f} / {result['q3']:.2f}")
    print(f"Tier (low/medium/high): {result['tier_counts']}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"\nDitulis ke {out_path}")


if __name__ == "__main__":
    main()
