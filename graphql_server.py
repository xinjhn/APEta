"""
graphql_server.py
=================
Server GraphQL (Strawberry) -- dijalankan BERGANTIAN dengan REST (PANDUAN Bagian 3).

FAKTORIAL DESAIN (Path B - Symmetric Baselines):
- MODE_DEFAULT = "typed"      -> GraphQL dengan rekonstruksi objek Strawberry (baseline lambat)
- MODE_DEFAULT = "passthrough" -> GraphQL mengembalikan dict mentah (simetris dengan REST passthrough)

Mode dikontrol via env var APE_GRAPHQL_MODE=typed|passthrough untuk memungkinkan
eksperimen 2x2: Protocol (REST/GraphQL) × Type Safety (yes/no).

PERBAIKAN penting atas draf laporan (Increment 2-3): resolver TIDAK mengembalikan
`dict` mentah. Ia membangun objek tipe Strawberry yang sesungguhnya sehingga biaya
resolusi (AST parse + resolver traversal + perakitan objek per-request) yang
menjadi HIPOTESIS MEKANISTIK penelitian benar-benar terjadi dan terukur. Bila
GraphQL hanya mem-bulk-serialize dict, kedua protokol runtuh ke perilaku yang
sama dan eksperimen tak dapat mendeteksi overhead yang ingin diuji.

KOREKSI (audit lanjutan): mode "passthrough" SEMPAT mengembalikan `dict` Python
mentah langsung dari resolver. Ini SALAH dan crash saat dijalankan -- Strawberry
meresolusi field via `getattr(source, field_name)`, BUKAN `Mapping.get()` (tidak
seperti default resolver graphql-core murni). Dibuktikan dengan
`tools/verify_factorial_modes.py` (AttributeError sebelum perbaikan). Mode
"passthrough" kini membangun `types.SimpleNamespace` bertingkat -- objek generik
tanpa skema/anotasi tipe (analog `dict` REST passthrough: TANPA Pydantic), namun
tetap mendukung resolusi atribut yang dibutuhkan Strawberry. Sisa biaya
konstruksi atribut (`SimpleNamespace(**kwargs)`) sebanding dengan `dict` literal
REST -- kontras dgn mode "typed" yang membangun dataclass Strawberry bertipe.

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
    APE_GRAPHQL_MODE=typed \  # atau "passthrough"
    uvicorn graphql_server:app --workers 1 --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import json
import os
from types import SimpleNamespace
from typing import List, Optional

import strawberry
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
from strawberry.schema.config import StrawberryConfig
from strawberry.types import Info

from core import aggregate as core_aggregate
from core import filters as core_filters
from core import projection as core_projection
from core.access import get_image
from core.pool import InMemoryPool
from core.timing import add_process_time_middleware


# --- Kontrol mode implementasi (faktor Type Safety dalam desain faktorial) -----
GRAPHQL_MODE = os.environ.get("APE_GRAPHQL_MODE", "typed").lower()
if GRAPHQL_MODE not in ("typed", "passthrough"):
    raise ValueError(f"APE_GRAPHQL_MODE must be 'typed' or 'passthrough', got '{GRAPHQL_MODE}'")


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
    """Rekonstruksi objek typed (mode default, simetris dengan REST typed)."""
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
                bounding_box=list(d.get("bounding_box", [])),
            )
            for d in detections
        ],
    )


def _build_aggregate(record: dict, counts: list) -> AggregateResult:
    """Rekonstruksi objek typed untuk agregasi."""
    return AggregateResult(
        image_id=record["image_id"],
        class_counts=[
            ClassCount(class_name=c["class_name"], count=c["count"])
            for c in counts
        ],
    )


# --- Helper untuk mode passthrough: SimpleNamespace generik (BUKAN dict) -------
# Strawberry meresolusi field via getattr(), sehingga dict mentah TIDAK valid
# (lihat catatan KOREKSI di docstring modul). SimpleNamespace mendukung getattr
# tanpa skema/tipe -- analog `dict` REST passthrough yang juga tanpa Pydantic.
def _ns_image_detections(record: dict, detections: list) -> SimpleNamespace:
    """Versi passthrough: rakitan atribut generik tanpa tipe Strawberry."""
    return SimpleNamespace(
        image_id=record["image_id"],
        dimensions=SimpleNamespace(
            width=record["dimensions"]["width"],
            height=record["dimensions"]["height"],
        ),
        detections=[
            SimpleNamespace(
                class_label=d["class_label"],
                confidence_score=d["confidence_score"],
                bounding_box=list(d.get("bounding_box", [])),
            )
            for d in detections
        ],
    )


def _ns_aggregate(record: dict, counts: list) -> SimpleNamespace:
    """Versi passthrough untuk agregasi."""
    return SimpleNamespace(
        image_id=record["image_id"],
        class_counts=[
            SimpleNamespace(class_name=c["class_name"], count=c["count"])
            for c in counts
        ],
    )


# --- Kesadaran selection-set (FAIRNESS pola "partial" S2) -----------------------
# Tanpa ini, resolver membangun field `bounding_box` walau klien tak memintanya
# (Strawberry hanya MEMFILTER saat serialisasi) -- padahal REST (core/projection.py)
# men-strip field SEBELUM objek respons dibangun. Membiarkan resolver tetap
# membangun field yang tak diminta membuat pola "partial" GraphQL membayar biaya
# konstruksi yang SAMA dengan "baseline", sehingga klaim latency utk pola ini
# tak bisa dibandingkan adil dengan REST (lihat audit). Di sini kita inspeksi
# info.selected_fields dan strip bounding_box SEBELUM membangun objek -- simetris
# dengan core.projection.project_detections yang dipakai REST.
def _requested_detection_fields(info: Info) -> Optional[set]:
    try:
        for top in info.selected_fields:
            for nested in top.selections:
                if nested.name == "detections":
                    return {f.name for f in nested.selections}
    except Exception:
        return None
    return None


# --- Query (resolver memanggil primitif core.* yang SAMA dengan REST) ----------
@strawberry.type
class Query:
    @strawberry.field
    def image_detections(
        self,
        info: Info,
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

        # Strip field tak diminta SEBELUM membangun objek -- simetris dengan
        # REST core/projection.py (lihat catatan di atas fungsi ini).
        requested = _requested_detection_fields(info)
        if requested is not None and "bounding_box" not in requested:
            dets = core_projection.project_detections(dets, requested)

        if GRAPHQL_MODE == "passthrough":
            # Mode passthrough: objek generik tanpa tipe (simetris REST passthrough).
            return _ns_image_detections(rec, dets)  # type: ignore[return-value]

        # Mode typed: rekonstruksi objek penuh (baseline)
        return _build_image_detections(rec, dets)

    @strawberry.field
    def aggregate(self, density: str, seed: Optional[int] = None) -> AggregateResult:
        """Melayani S4. Memanggil core.aggregate.count_per_class (sama dgn REST)."""
        rec = get_image(density, seed=seed)
        counts = core_aggregate.count_per_class(rec.get("detections", []))

        if GRAPHQL_MODE == "passthrough":
            return _ns_aggregate(rec, counts)  # type: ignore[return-value]

        return _build_aggregate(rec, counts)


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
    return {"status": "ok", "pool": InMemoryPool.instance().summary(), "mode": GRAPHQL_MODE}
