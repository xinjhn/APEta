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
