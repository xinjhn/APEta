"""
core/pool.py
============
In-Memory Data Pool (arsitektur Zero-DB / Shared Funnel).

Memenuhi:
- FR-05 / NFR-01 (Zero-DB I/O)            -> Laporan Increment 1
- Variabel Kontrol "Shared Funnel"        -> Laporan Subbab III.2.3
- PANDUAN Bagian 5 (struktur & determinisme)

Prinsip yang dijaga:
1. Dimuat SEKALI saat startup (pola Singleton); konstan sepanjang hidup server.
2. Load DETERMINISTIK: REST & GraphQL (restart bergantian) wajib memuat pool
   identik -- file sumber sama, ambang stratifikasi sama, urutan sama.
3. Ter-indeks per tier densitas untuk pengambilan O(1).
4. Pemilihan citra acak dilakukan SERVER (lihat core/selection.py), bukan klien.

Catatan determinisme vs pengacakan (PANDUAN Bagian 5): struktur JSON untuk
image_id yang sama selalu identik (sifat YOLO26 NMS-free). Yang acak hanyalah
*citra mana* yang dipilih per request (untuk anti-cache).
"""
from __future__ import annotations

import json
import statistics
from typing import Dict, List, Optional, Tuple

from .config import DEFAULT_Q1, DEFAULT_Q3, DENSITY_TIERS

# Tipe alias untuk keterbacaan
Record = Dict          # satu record VCD (image_id, dimensions, detections[])
PoolByTier = Dict[str, List[Record]]


def load_records(json_path: str) -> List[Record]:
    """Membaca file JSON hasil inferensi.

    Mendukung dua bentuk umum:
    - list of records:            [ {image_id, dimensions, detections}, ... ]
    - dict ter-index per image_id: { "img1": {dimensions, detections}, ... }

    Bila berbentuk dict, image_id disuntikkan ke tiap record agar konsisten.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        records = []
        for image_id, rec in data.items():
            rec = dict(rec)
            rec.setdefault("image_id", image_id)
            records.append(rec)
        return records
    if isinstance(data, list):
        return data
    raise ValueError("Format JSON tidak dikenal: harus list atau dict.")


def detection_count(record: Record) -> int:
    """Jumlah objek terdeteksi pada satu citra (dasar stratifikasi densitas)."""
    return len(record.get("detections", []))


def compute_quartiles(records: List[Record]) -> Tuple[float, float]:
    """Menghitung Q1 dan Q3 dari distribusi jumlah deteksi per citra.

    Dipakai pada Tahap [B] (profiling) untuk MEMPERBARUI angka kuartil di laporan
    (Tabel IV.1) langsung dari output model, menggantikan placeholder.
    """
    counts = sorted(detection_count(r) for r in records)
    if not counts:
        raise ValueError("Tidak ada record untuk dihitung kuartilnya.")
    # quantiles(method='inclusive') -> q1 = persentil 25, q3 = persentil 75
    q1, _med, q3 = statistics.quantiles(counts, n=4, method="inclusive")
    return q1, q3


def stratify(
    records: List[Record],
    q1: float = DEFAULT_Q1,
    q3: float = DEFAULT_Q3,
) -> PoolByTier:
    """Mengelompokkan record ke tiga tier densitas berbasis kuartil.

    low    : count < Q1
    medium : Q1 <= count <= Q3
    high   : count > Q3
    """
    pool: PoolByTier = {tier: [] for tier in DENSITY_TIERS}
    for rec in records:
        c = detection_count(rec)
        if c < q1:
            pool["low"].append(rec)
        elif c > q3:
            pool["high"].append(rec)
        else:
            pool["medium"].append(rec)
    return pool


class InMemoryPool:
    """Singleton penampung pool ter-stratifikasi.

    Pola Singleton menjamin pembacaan disk hanya sekali; seluruh request
    diarahkan ke referensi memori yang sama (Laporan Increment 1).
    """

    _instance: Optional["InMemoryPool"] = None

    def __init__(self, pool: PoolByTier, q1: float, q3: float):
        self.pool = pool
        self.q1 = q1
        self.q3 = q3

    # --- API kelas (dipakai identik oleh kedua server) -------------------------
    @classmethod
    def initialize(
        cls,
        json_path: str,
        q1: Optional[float] = None,
        q3: Optional[float] = None,
        recompute_quartiles: bool = False,
    ) -> "InMemoryPool":
        """Memuat & menstratifikasi pool sekali. Idempotent (Singleton).

        recompute_quartiles=True -> hitung Q1/Q3 dari data (Tahap [B]).
        Selain itu memakai ambang tetap (DEFAULT_Q1/Q3 atau argumen) agar
        REST & GraphQL DIJAMIN memakai ambang identik.
        """
        if cls._instance is None:
            records = load_records(json_path)
            if recompute_quartiles:
                _q1, _q3 = compute_quartiles(records)
            else:
                _q1 = DEFAULT_Q1 if q1 is None else q1
                _q3 = DEFAULT_Q3 if q3 is None else q3
            pool = stratify(records, _q1, _q3)
            cls._instance = cls(pool, _q1, _q3)
        return cls._instance

    @classmethod
    def instance(cls) -> "InMemoryPool":
        if cls._instance is None:
            raise RuntimeError("InMemoryPool belum di-initialize().")
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Hanya untuk pengujian (mis. memuat pool sintetis)."""
        cls._instance = None

    # --- Akses data ------------------------------------------------------------
    def tier(self, density: str) -> List[Record]:
        if density not in self.pool:
            raise KeyError(f"Tier densitas tidak dikenal: {density!r}")
        return self.pool[density]

    def summary(self) -> Dict[str, int]:
        """Jumlah citra per tier (untuk verifikasi keseimbangan & laporan)."""
        return {tier: len(recs) for tier, recs in self.pool.items()}
