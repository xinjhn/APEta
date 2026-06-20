"""
core/access.py
==============
Titik akses data tunggal yang dipakai IDENTIK oleh REST & GraphQL: mengambil
satu record citra dari tier densitas yang diminta klien.

Inilah simpul "Shared Funnel": apa pun protokolnya, jalur menuju data sama.
Transformasi spesifik-pola (proyeksi / filter / agregasi) dilakukan SETELAH ini
oleh masing-masing server memakai primitif bersama di core.* -- sehingga logika
bisnis tidak pernah berbeda antar-protokol, hanya cara membungkus & menserialisasi.

Parameter seed (PANDUAN Bagian 5):
- seed=None  -> pemilihan acak murni (anti-cache pada beban nyata).
- seed=<int> -> pemilihan deterministik & reprodusibel. Karena pool dimuat
  identik di kedua server, (density, seed) yang sama menghasilkan citra yang
  SAMA pada REST maupun GraphQL -- inilah yang memungkinkan uji paritas data.
"""
from __future__ import annotations

import random
from typing import Dict, Optional

from .pool import InMemoryPool
from .selection import pick_record

Record = Dict


def get_image(density: str, seed: Optional[int] = None) -> Record:
    """Memilih satu citra (sisi server) dari tier densitas yang diminta.

    Bila seed diberikan, pemilihan bersifat deterministik & reprodusibel.
    """
    pool = InMemoryPool.instance()
    rng = random.Random(seed) if seed is not None else None
    return pick_record(pool.tier(density), rng=rng)
