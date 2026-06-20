"""
rest_server.py
==============
Server REST (FastAPI) -- salah satu dari dua server yang dijalankan BERGANTIAN.
Saat menguji REST, hanya server ini yang hidup (PANDUAN Bagian 3).

Memenuhi FR-01..FR-04 (4 pola kueri) di atas In-Memory Pool (FR-05).
Setiap endpoint melakukan kerja sisi-server yang NYATA dan setara dengan padanan
GraphQL-nya; tidak ada pola "kirim penuh lalu klien membuang".

Menjalankan (single worker, sesuai PANDUAN Bagian 3):
    APE_POOL_JSON=/path/ke/inferensi.json \
    uvicorn rest_server:app --workers 1 --host 127.0.0.1 --port 8000

Catatan serializer (fairness): memakai JSONResponse bawaan Starlette (modul
`json` stdlib), BUKAN orjson, agar tidak memberi REST jalur cepat yang tidak
dimiliki jalur GraphQL standar. Penamaan field snake_case identik dengan GraphQL.

Parameter `seed` (opsional) di tiap endpoint: bila diisi, pemilihan citra
deterministik (untuk reproducibility per-run & uji paritas). Bila kosong,
pemilihan acak murni (anti-cache pada beban nyata).
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI, Query

from core import aggregate, filters, projection
from core.access import get_image
from core.config import PATTERN_SPEC
from core.pool import InMemoryPool
from core.timing import add_process_time_middleware

app = FastAPI(title="APE REST", docs_url=None, redoc_url=None)
add_process_time_middleware(app)


@app.on_event("startup")
def _startup() -> None:
    """Memuat pool SEKALI (deterministik) saat server dinyalakan."""
    json_path = os.environ["APE_POOL_JSON"]
    recompute = os.environ.get("APE_RECOMPUTE_Q", "0") == "1"
    InMemoryPool.initialize(json_path, recompute_quartiles=recompute)


def _envelope(record: dict, detections: list) -> dict:
    """Membungkus respons pola pembawa-deteksi dengan amplop konstan.

    Amplop (image_id + dimensions) dijaga TETAP di S1/S2/S3 sehingga seleksi
    field/filter hanya bekerja pada array detections -- mengisolasi variabel
    payload yang menskala dengan densitas.
    """
    return {
        "image_id": record["image_id"],
        "dimensions": record["dimensions"],
        "detections": detections,
    }


# --- S1: Baseline (full) -------------------------------------------------------
@app.get("/baseline")
def baseline(density: str = Query(...), seed: Optional[int] = Query(None)):
    rec = get_image(density, seed=seed)
    return _envelope(rec, rec.get("detections", []))


# --- S2: Partial field (proyeksi NYATA di server) ------------------------------
@app.get("/partial")
def partial(density: str = Query(...), seed: Optional[int] = Query(None)):
    rec = get_image(density, seed=seed)
    fields = PATTERN_SPEC["partial"]["fields"]
    projected = projection.project_detections(rec.get("detections", []), fields)
    return _envelope(rec, projected)


# --- S3: Filtered (predikat tetap car AND conf>=0.5; array kosong = valid) ------
@app.get("/filtered")
def filtered(
    density: str = Query(...),
    class_label: str = Query(PATTERN_SPEC["filtered"]["filter"]["class_label"]),
    min_confidence: float = Query(
        PATTERN_SPEC["filtered"]["filter"]["min_confidence"]
    ),
    seed: Optional[int] = Query(None),
):
    rec = get_image(density, seed=seed)
    kept = filters.filter_detections(
        rec.get("detections", []),
        class_label=class_label,
        min_confidence=min_confidence,
    )
    return _envelope(rec, kept)


# --- S4: Aggregation (ringkasan per kelas; payload minimal) ---------------------
@app.get("/aggregate")
def aggregate_endpoint(density: str = Query(...), seed: Optional[int] = Query(None)):
    rec = get_image(density, seed=seed)
    counts = aggregate.count_per_class(rec.get("detections", []))
    return {"image_id": rec["image_id"], "class_counts": counts}


@app.get("/health")
def health():
    return {"status": "ok", "pool": InMemoryPool.instance().summary()}
