"""
core/filters.py
===============
Penyaringan predikat (pola S3 'Filtered'). Modul BERSAMA yang dipanggil
identik oleh REST dan GraphQL.

Justifikasi fairness (titik paling rawan dikritik, PANDUAN Bagian 8):
karena kedua protokol memanggil fungsi yang SAMA PERSIS ini, predikat dijamin
identik secara semantik (operator perbandingan, pencocokan kelas, penanganan
batas/tie pada threshold) BY CONSTRUCTION. Tidak mungkin satu protokol
"diam-diam" memfilter berbeda dari yang lain.

Predikat default eksperimen (KONSTAN lintas tier): class_label='car' AND
confidence_score >= 0.5 (lihat core/config.py PATTERN_SPEC).
"""
from __future__ import annotations

from typing import Dict, List, Optional

Detection = Dict


def filter_detections(
    detections: List[Detection],
    class_label: Optional[str] = None,
    min_confidence: Optional[float] = None,
) -> List[Detection]:
    """Mengembalikan subset deteksi yang memenuhi predikat.

    - class_label=None      -> tidak memfilter berdasarkan kelas
    - min_confidence=None   -> tidak memfilter berdasarkan confidence
    - Keduanya digabung dengan AND.
    - Batas threshold inklusif: confidence_score >= min_confidence.

    Hasil array KOSONG adalah luaran VALID (mis. tidak ada 'car' ber-conf>=0.5
    pada citra terpilih) dan harus dikembalikan apa adanya oleh kedua protokol,
    bukan dijadikan error -- agar paritas tetap terjaga.
    """
    result = detections
    if class_label is not None:
        result = [d for d in result if d.get("class_label") == class_label]
    if min_confidence is not None:
        result = [
            d for d in result if d.get("confidence_score", 0.0) >= min_confidence
        ]
    return result
