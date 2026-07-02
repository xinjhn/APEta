"""
core/aggregate.py
=================
Agregasi sisi server (pola S4 'Aggregation'). Modul BERSAMA.

Spesifikasi terkunci (KONSTAN lintas tier): jumlah objek per kelas.
Payload sengaja minimal -> pola ini praktis mengukur SERVER-SIDE PROCESSING TIME
(header X-Process-Time) dan paling mungkin memunculkan overhead resolusi GraphQL,
bukan waktu transfer (lihat empiris: Seabra, Nazario & Pinto, "REST or GraphQL?:
A Performance Comparative Study", SBCARS 2019, ACM, DOI 10.1145/3357141.3357149 --
REST mengungguli GraphQL di atas ~3000 req/s, konsisten dengan hipotesis overhead
resolusi mendominasi pada beban tinggi).

Bentuk luaran distandarkan agar identik di kedua protokol: daftar terurut
{class_name, count}, diurutkan menurun lalu alfabetis untuk determinisme.
"""
from __future__ import annotations

from collections import Counter
from typing import Dict, List

Detection = Dict


def class_counts(detections: List[Detection]) -> List[Dict]:
    """Agregasi M4 (skema relasional MOT): jumlah deteksi per class_id.

    Dipanggil oleh KEDUA server (REST /images/{id}/class_counts dan GraphQL
    Image.class_counts) atas daftar deteksi yang sama dari core/dal.py --
    fairness by construction, sama seperti count_per_class() pada skema lama.

    Urutan deterministik: class_id menaik (parity criterion M4: "identical
    class ordering, ORDER BY class_id").
    """
    counter = Counter(d["class_id"] for d in detections)
    return [{"class_id": cid, "count": counter[cid]} for cid in sorted(counter)]


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
