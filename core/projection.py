"""
core/projection.py
==================
Proyeksi field tingkat-deteksi (pola S2 'Partial Field'). Modul BERSAMA.

Justifikasi fairness (PANDUAN Bagian 8):
Pada REST, pencegahan over-fetching dilakukan dengan proyeksi NYATA di server
(padanan sparse fieldsets, spesifikasi JSON:API) -- BUKAN mengirim payload penuh
lalu membiarkan klien membuang field. Bila REST kirim-penuh sementara GraphQL
memfilter, GraphQL menang tidak adil.

Pada GraphQL, proyeksi terjadi secara native melalui selection set klien; server
GraphQL memanggil modul ini hanya bila perlu menyiapkan bentuk data yang setara
(lihat graphql_server.py). Yang penting: LUARAN keduanya identik.

Field yang diizinkan dibatasi ke whitelist skema VCD (core/config.py) untuk
mencegah kebocoran field tak terduga.
"""
from __future__ import annotations

from typing import Dict, Iterable, List

from .config import DETECTION_FIELDS

Detection = Dict


def project_detection(detection: Detection, fields: Iterable[str]) -> Detection:
    """Menyalin satu deteksi hanya dengan field yang diminta (urutan whitelist)."""
    allowed = [f for f in DETECTION_FIELDS if f in set(fields)]
    return {f: detection[f] for f in allowed if f in detection}


def project_detections(
    detections: List[Detection], fields: Iterable[str]
) -> List[Detection]:
    """Proyeksi seluruh array deteksi ke subset field tertentu."""
    fields = tuple(fields)
    return [project_detection(d, fields) for d in detections]
