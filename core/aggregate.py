"""
core/aggregate.py
=================
Agregasi sisi server (pola S4 'Aggregation'). Modul BERSAMA.

Spesifikasi terkunci (KONSTAN lintas tier): jumlah objek per kelas.
Payload sengaja minimal -> pola ini praktis mengukur SERVER-SIDE PROCESSING TIME
(header X-Process-Time) dan paling mungkin memunculkan overhead resolusi GraphQL
(Cha et al., 2020; SLR 2026), bukan waktu transfer.

Bentuk luaran distandarkan agar identik di kedua protokol: daftar terurut
{class_name, count}, diurutkan menurun lalu alfabetis untuk determinisme.
"""
from __future__ import annotations

from collections import Counter
from typing import Dict, List

Detection = Dict


def count_per_class(detections: List[Detection]) -> List[Dict]:
    """Menghitung jumlah objek per kelas.

    Mengiterasi seluruh array deteksi (beban komputasi menskala dengan densitas,
    sementara payload tetap kecil -- itulah tujuan desain pola ini).

    Urutan deterministik: count menurun, lalu nama kelas menaik. Penting agar
    perbandingan paritas REST vs GraphQL bersifat literal deep-equality.
    """
    counter = Counter(d.get("class_label") for d in detections)
    items = sorted(counter.items(), key=lambda kv: (-kv[1], str(kv[0])))
    return [{"class_name": cls, "count": cnt} for cls, cnt in items]
