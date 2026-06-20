"""
graphql_server.py
=================
Server GraphQL (Strawberry) -- dijalankan BERGANTIAN dengan REST (PANDUAN Bagian 3).

PERBAIKAN penting atas draf laporan (Increment 2-3): resolver TIDAK mengembalikan
`dict` mentah. Ia membangun objek tipe Strawberry yang sesungguhnya sehingga biaya
resolusi (AST parse + resolver traversal + perakitan objek per-request) yang
menjadi HIPOTESIS MEKANISTIK penelitian benar-benar terjadi dan terukur. Bila
GraphQL hanya mem-bulk-serialize dict, kedua protokol runtuh ke perilaku yang
sama dan eksperimen tak dapat mendeteksi overhead yang ingin diuji.

FAIRNESS - auto_camel_case=False:
Strawberry secara default mengubah class_label -> classLabel. Itu akan membuat
nama field (dan UKURAN PAYLOAD) berbeda dari REST, membiaskan metrik payload_size.
Maka auto-camelCase DINONAKTIFKAN -> nama field snake_case identik dengan REST,
sehingga (a) payload byte-comparable dan (b) paritas data bersifat literal.

Pola kueri pada GraphQL = SATU endpoint fleksibel + selection set klien:
- baseline : imageDetections(density){ image_id dimensions{...} detections{ semua } }
- partial  : imageDetections(density){ ... detections{ class_label confidence_score } }
- filtered : imageDetections(density, class_label:"car", min_confidence:0.5){ ... }
- aggregate: aggregate(density){ image_id class_counts{ class_name count } }

Menjalankan (single worker):
    APE_POOL_JSON=/path/ke/inferensi.json \
    uvicorn graphql_server:app --workers 1 --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import json
import os
from typing import List, Optional

import strawberry
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
from strawberry.schema.config import StrawberryConfig

from core import aggregate as core_aggregate
from core import filters as core_filters
from core.access import get_image
from core.pool import InMemoryPool
from core.timing import add_process_time_middleware


# --- Paritas serialisasi (FAIRNESS payload_size) -------------------------------
# Strawberry default: json.dumps(data) -> menyisipkan spasi ("a": 1, "b": 2).
# Starlette JSONResponse (REST): kompak ("a":1,"b":2). Selisih spasi ini akan
# membiaskan payload_size. Maka encoder GraphQL disamakan ke format KOMPAK.
# Yang TERSISA sebagai selisih (amplop {"data":{...}}) adalah overhead wire
# format GraphQL yang SAH dan memang patut dilaporkan apa adanya.
class CompactGraphQLRouter(GraphQLRouter):
    def encode_json(self, data: object) -> str:
        return json.dumps(data, separators=(",", ":"))


# --- Tipe GraphQL (nama field snake_case mengikuti skema VCD) -------------------
@strawberry.type
class Dimensions:
    width: int
    height: int


@strawberry.type
class Detection:
    class_label: str
    confidence_score: float
    bounding_box: List[float]


@strawberry.type
class ImageDetections:
    image_id: str
    dimensions: Dimensions
    detections: List[Detection]


@strawberry.type
class ClassCount:
    class_name: str
    count: int


@strawberry.type
class AggregateResult:
    image_id: str
    class_counts: List[ClassCount]


# --- Perakitan objek tipe dari dict pool (INI biaya resolusi GraphQL nyata) -----
def _build_image_detections(record: dict, detections: list) -> ImageDetections:
    return ImageDetections(
        image_id=record["image_id"],
        dimensions=Dimensions(
            width=record["dimensions"]["width"],
            height=record["dimensions"]["height"],
        ),
        # Objek Detection dirakit penuh per-request; Strawberry lalu menserialisasi
        # HANYA field yang ada di selection set klien (mekanisme seleksi native).
        detections=[
            Detection(
                class_label=d["class_label"],
                confidence_score=d["confidence_score"],
                bounding_box=list(d["bounding_box"]),
            )
            for d in detections
        ],
    )


# --- Query (resolver memanggil primitif core.* yang SAMA dengan REST) ----------
@strawberry.type
class Query:
    @strawberry.field
    def image_detections(
        self,
        density: str,
        class_label: Optional[str] = None,
        min_confidence: Optional[float] = None,
        seed: Optional[int] = None,
    ) -> ImageDetections:
        """Melayani S1/S2/S3.

        - S1 baseline & S2 partial : argumen filter None; klien mengatur field
          via selection set (baseline pilih semua, partial pilih subset).
        - S3 filtered : argumen class_label & min_confidence diisi -> resolver
          memanggil core.filters.filter_detections (FUNGSI YANG SAMA dgn REST).
        """
        rec = get_image(density, seed=seed)
        dets = rec.get("detections", [])
        if class_label is not None or min_confidence is not None:
            dets = core_filters.filter_detections(
                dets, class_label=class_label, min_confidence=min_confidence
            )
        return _build_image_detections(rec, dets)

    @strawberry.field
    def aggregate(self, density: str, seed: Optional[int] = None) -> AggregateResult:
        """Melayani S4. Memanggil core.aggregate.count_per_class (sama dgn REST)."""
        rec = get_image(density, seed=seed)
        counts = core_aggregate.count_per_class(rec.get("detections", []))
        return AggregateResult(
            image_id=rec["image_id"],
            class_counts=[
                ClassCount(class_name=c["class_name"], count=c["count"])
                for c in counts
            ],
        )


schema = strawberry.Schema(
    query=Query,
    # snake_case dipertahankan demi paritas payload & data dengan REST.
    config=StrawberryConfig(auto_camel_case=False),
)

app = FastAPI(title="APE GraphQL", docs_url=None, redoc_url=None)
add_process_time_middleware(app)
app.include_router(CompactGraphQLRouter(schema), prefix="/graphql")


@app.on_event("startup")
def _startup() -> None:
    json_path = os.environ["APE_POOL_JSON"]
    recompute = os.environ.get("APE_RECOMPUTE_Q", "0") == "1"
    InMemoryPool.initialize(json_path, recompute_quartiles=recompute)


@app.get("/health")
def health():
    return {"status": "ok", "pool": InMemoryPool.instance().summary()}
