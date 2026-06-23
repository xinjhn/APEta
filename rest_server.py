"""
rest_server.py
==============
Server REST (FastAPI) -- salah satu dari dua server yang dijalankan BERGANTIAN.
Saat menguji REST, hanya server ini yang hidup (PANDUAN Bagian 3).

Memenuhi FR-01..FR-04 (4 pola kueri) di atas In-Memory Pool (FR-05).
Setiap endpoint melakukan kerja sisi-server yang NYATA dan setara dengan padanan
GraphQL-nya; tidak ada pola "kirim penuh lalu klien membuang".

FAKTORIAL DESAIN (Path B - Symmetric Baselines):
- MODE_DEFAULT = "passthrough"   -> REST tanpa rekonstruksi objek (baseline cepat)
- MODE_DEFAULT = "typed"         -> REST dengan Pydantic models (simetris dengan GraphQL typed)

Mode dikontrol via env var APE_REST_MODE=passthrough|typed untuk memungkinkan
eksperimen 2x2: Protocol (REST/GraphQL) × Type Safety (yes/no).

Menjalankan (single worker, sesuai PANDUAN Bagian 3):
    APE_POOL_JSON=/path/ke/inferensi.json \
    APE_REST_MODE=passthrough \  # atau "typed"
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
from typing import List, Optional

from fastapi import FastAPI, Query
from pydantic import BaseModel
from starlette.responses import JSONResponse

from core import aggregate, filters, projection
from core.access import get_image
from core.config import PATTERN_SPEC
from core.pool import InMemoryPool
from core.timing import add_process_time_middleware

app = FastAPI(title="APE REST", docs_url=None, redoc_url=None)
add_process_time_middleware(app)

# --- Kontrol mode implementasi (faktor Type Safety dalam desain faktorial) -----
REST_MODE = os.environ.get("APE_REST_MODE", "passthrough").lower()
if REST_MODE not in ("passthrough", "typed"):
    raise ValueError(f"APE_REST_MODE must be 'passthrough' or 'typed', got '{REST_MODE}'")


# --- Pydantic models untuk mode "typed" (simetris dengan GraphQL types) --------
class DimensionsModel(BaseModel):
    width: int
    height: int


class DetectionModel(BaseModel):
    class_label: str
    confidence_score: float
    bounding_box: Optional[List[float]] = None


class ImageEnvelopeModel(BaseModel):
    image_id: str
    dimensions: DimensionsModel
    detections: List[DetectionModel]


class ClassCountModel(BaseModel):
    class_name: str
    count: int


class AggregateModel(BaseModel):
    image_id: str
    class_counts: List[ClassCountModel]


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


def _envelope_typed(record: dict, detections: list) -> ImageEnvelopeModel:
    """Versi typed: merekonstruksi objek Pydantic (biaya simetris dengan GraphQL).

    Ini menambahkan overhead alokasi objek ~70-90ms/request untuk meniru biaya
    resolver GraphQL, memungkinkan isolasi efek protokol vs implementasi.
    """
    return ImageEnvelopeModel(
        image_id=record["image_id"],
        dimensions=DimensionsModel(
            width=record["dimensions"]["width"],
            height=record["dimensions"]["height"],
        ),
        detections=[
            DetectionModel(
                class_label=d["class_label"],
                confidence_score=d["confidence_score"],
                bounding_box=list(d["bounding_box"]),
            )
            for d in detections
        ],
    )


# --- S1: Baseline (full) -------------------------------------------------------
@app.get("/baseline")
def baseline(density: str = Query(...), seed: Optional[int] = Query(None)):
    rec = get_image(density, seed=seed)
    if REST_MODE == "typed":
        return _envelope_typed(rec, rec.get("detections", []))
    return _envelope(rec, rec.get("detections", []))


# --- S2: Partial field (proyeksi NYATA di server) ------------------------------
@app.get("/partial")
def partial(density: str = Query(...), seed: Optional[int] = Query(None)):
    rec = get_image(density, seed=seed)
    fields = PATTERN_SPEC["partial"]["fields"]
    projected = projection.project_detections(rec.get("detections", []), fields)
    if REST_MODE == "typed":
        # Untuk partial, projected sudah hanya punya class_label + confidence_score
        # (bounding_box di-strip oleh project_detections SEBELUM objek dibangun --
        # simetris dgn GraphQL setelah audit, lihat graphql_server.py). bounding_box
        # diset None (bukan []) dan di-exclude saat serialisasi (exclude_none=True)
        # agar key TIDAK muncul di wire sama sekali -- simetris dgn mode passthrough
        # yang juga tak punya key tersebut (lihat audit "Finding C/bounding_box leak").
        model = ImageEnvelopeModel(
            image_id=rec["image_id"],
            dimensions=DimensionsModel(
                width=rec["dimensions"]["width"],
                height=rec["dimensions"]["height"],
            ),
            detections=[
                DetectionModel(
                    class_label=d["class_label"],
                    confidence_score=d["confidence_score"],
                    bounding_box=d.get("bounding_box"),
                )
                for d in projected
            ],
        )
        return JSONResponse(content=model.model_dump(exclude_none=True))
    return _envelope(rec, projected)


# --- S3: Filtered (predikat tetap car AND conf>=0.5; array kosong = valid) ------
# FAIRNESS: class_label/min_confidence TIDAK berdefault ke PATTERN_SPEC di sini --
# default None (= tidak memfilter), SIMETRIS dengan resolver GraphQL
# `image_detections` (graphql_server.py) yang juga default None. Pemanggil
# (k6/load.js, tests/test_parity.py) WAJIB mengirim nilai PATTERN_SPEC secara
# EKSPLISIT untuk memicu pola S3 yang sesungguhnya -- mencegah REST "diam-diam"
# memfilter saat parameter tak dikirim sementara GraphQL tidak.
@app.get("/filtered")
def filtered(
    density: str = Query(...),
    class_label: Optional[str] = Query(None),
    min_confidence: Optional[float] = Query(None),
    seed: Optional[int] = Query(None),
):
    rec = get_image(density, seed=seed)
    kept = filters.filter_detections(
        rec.get("detections", []),
        class_label=class_label,
        min_confidence=min_confidence,
    )
    if REST_MODE == "typed":
        return _envelope_typed(rec, kept)
    return _envelope(rec, kept)


# --- S4: Aggregation (ringkasan per kelas; payload minimal) ---------------------
@app.get("/aggregate")
def aggregate_endpoint(density: str = Query(...), seed: Optional[int] = Query(None)):
    rec = get_image(density, seed=seed)
    counts = aggregate.count_per_class(rec.get("detections", []))
    if REST_MODE == "typed":
        return AggregateModel(
            image_id=rec["image_id"],
            class_counts=[
                ClassCountModel(class_name=c["class_name"], count=c["count"])
                for c in counts
            ],
        )
    return {"image_id": rec["image_id"], "class_counts": counts}


@app.get("/health")
def health():
    return {"status": "ok", "pool": InMemoryPool.instance().summary(), "mode": REST_MODE}
