"""
core/selection.py
=================
Pemilihan citra dilakukan SERVER, bukan klien (PANDUAN Bagian 5).

Alasan (semuanya berlaku setara untuk REST & GraphQL):
(a) mencegah caching artifact pada titik yang benar,
(b) realistis: klien meminta KONDISI (tier), server memilih RECORD,
(c) menjaga k6 ringan (hanya mengirim parameter tier),
(d) adil untuk kedua protokol (mekanisme identik via modul bersama ini).

Determinisme: seed pemilihan boleh diset per-run agar reprodusibel, sementara
struktur JSON untuk image_id yang sama tetap konstan (YOLO26 NMS-free).
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional

Record = Dict


def pick_record(
    tier_records: List[Record],
    rng: Optional[random.Random] = None,
) -> Record:
    """Memilih satu record acak dari daftar record sebuah tier.

    rng opsional memungkinkan reproducibility (mis. seed per-run). Bila None,
    memakai modul random global. Pemilihan O(1) (random.choice).
    """
    if not tier_records:
        raise ValueError("Tier kosong: tidak ada citra untuk dipilih.")
    chooser = rng.choice if rng is not None else random.choice
    return chooser(tier_records)


# --- MOT scenario study (M5/M6): seeded track picker -------------------------
# Tier eligibility follows design/mot_profile.json's trajectory_window_tiers:
# a track is eligible for window W iff it has >= 2W+1 detections (point count
# tiers 5/17/47 anchored on the detections-per-track median/Q3/p90).
TRAJECTORY_WINDOW_TIERS = {"small": 2, "medium": 8, "large": 23}


def eligible_point_count(window: int) -> int:
    """Minimum detections a track needs to be in window W's eligibility pool."""
    return 2 * window + 1


def pick_track_id(
    eligible_ids: List[int],
    seed: Optional[int] = None,
) -> int:
    """Memilih satu track_id deterministik dari pool eligibility sebuah tier.

    Mekanisme identik dengan pick_record()/pick_random_image(): pemilihan di
    Python atas daftar id TERURUT (bukan SQL RANDOM()) supaya (pool, seed)
    yang sama menghasilkan track yang sama di REST maupun GraphQL -- syarat
    uji paritas M5/M6 yang deterministik.
    """
    if not eligible_ids:
        raise ValueError("Pool track kosong: tidak ada track eligible untuk window ini.")
    rng = random.Random(seed) if seed is not None else random
    return rng.choice(eligible_ids)


def track_center_frame(first_frame: int, last_frame: int) -> int:
    """center_frame kanonik M5 = titik tengah track (design doc S4/M5)."""
    return (first_frame + last_frame) // 2
