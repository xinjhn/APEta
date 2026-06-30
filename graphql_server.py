"""
graphql_server.py
==================
GraphQL (Strawberry) server for the Phase 1 REST-vs-GraphQL caching study.
Run ALTERNATELY with rest_server.py (single worker at a time).

Both servers call core/dal.py's DetectionDAL identically (N2: same DB, same
access path -- the API surface is the only systematic difference). Field
names stay snake_case (auto_camel_case=False) and the JSON encoder is forced
compact, matching REST's payload bytes (no naming/whitespace confound).

Schema:
    Query.image(id) -> Image { id frame_index width height density_tier
                                sequence_name detections(class_id, min_confidence) }
    Detection { id class_id confidence bbox_x bbox_y bbox_w bbox_h track }
    Track { id class_id class_name first_frame last_frame
            trajectory(window) -> [TrajectoryPoint] }

Detection.track is resolved through a per-request DataLoader (N5: real
batching, default ON) so multiple detections sharing a track in one query
issue ONE IN-clause SQL call instead of one per detection. Set
APE_GRAPHQL_BATCHING=off to run the deliberately non-batched (N+1) arm for
the side study quantifying the N+1 penalty -- never use that as the headline
comparison against REST.

Caching (N4): the POST /graphql route (Strawberry's default, used unchanged
by the Phase 1 A1/A2 tests) is NOT cached -- POST isn't cacheable by HTTP
semantics, and that's the whole reason GraphQL needs a separate mechanism.
Caching is via Automatic Persisted Queries (APQ) over GET, implemented by
hand below (Strawberry has no built-in APQ support -- checked
strawberry.extensions and strawberry.http, neither mentions persisted
queries). The GET /graphql route here is registered directly on `app`
BEFORE the router is included, so Starlette's first-match routing picks it
over the router's own internal GET handler for the exact "/graphql" path.

APQ wire protocol (Apollo's, the de facto standard):
    GET /graphql?extensions={"persistedQuery":{"version":1,"sha256Hash":"<h>"}}
        -> hash known: execute stored query. hash unknown: PersistedQueryNotFound.
    GET /graphql?query=<text>&extensions={"persistedQuery":{...,"sha256Hash":"<h>"}}
        -> verify sha256(query)==h, store it, execute (the "registration" call).
randomImage gets cacheable=False from core/caching.py for the same
anti-cache-by-design reason as REST's /images/random.

Run:
    APE_DB_PATH=/home/ubuntu/training/mot_detections.db \
    uvicorn graphql_server:app --workers 1 --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import List, Optional

import strawberry
from fastapi import FastAPI, Request
from fastapi.responses import Response
from strawberry.dataloader import DataLoader
from strawberry.fastapi import GraphQLRouter
from strawberry.schema.config import StrawberryConfig
from strawberry.types import Info

from core.caching import cache_headers, is_fresh
from core.config import DEFAULT_TRAJECTORY_WINDOW
from core.dal import DetectionDAL
from core.timing import add_process_time_middleware

GRAPHQL_BATCHING = os.environ.get("APE_GRAPHQL_BATCHING", "on").lower() != "off"


class CompactGraphQLRouter(GraphQLRouter):
    """Matches Starlette JSONResponse's compact separators (no payload-size
    confound from GraphQL's default `json.dumps` whitespace)."""

    def encode_json(self, data: object) -> str:
        return json.dumps(data, separators=(",", ":"))


# --- GraphQL types (snake_case fields mirror the DB columns 1:1) --------------
@strawberry.type
class TrajectoryPoint:
    id: int
    image_id: int
    frame_index: int
    confidence: float
    bbox_x: float
    bbox_y: float
    bbox_w: float
    bbox_h: float


@strawberry.type
class Track:
    id: int
    local_track_id: int
    class_id: int
    class_name: str
    first_frame: int
    last_frame: int

    @strawberry.field
    def trajectory(self, window: int = DEFAULT_TRAJECTORY_WINDOW) -> List[TrajectoryPoint]:
        dal = DetectionDAL.instance()
        full = dal.get_track_trajectory(self.id, window=window)
        points = full["trajectory"] if full else []
        fields = ("id", "image_id", "frame_index", "confidence", "bbox_x", "bbox_y", "bbox_w", "bbox_h")
        return [TrajectoryPoint(**{f: p[f] for f in fields}) for p in points]


@strawberry.type
class Detection:
    id: int
    class_id: int
    confidence: float
    bbox_x: float
    bbox_y: float
    bbox_w: float
    bbox_h: float
    _track_id: strawberry.Private[Optional[int]]

    @strawberry.field
    async def track(self, info: Info) -> Optional[Track]:
        if self._track_id is None:
            return None
        if GRAPHQL_BATCHING:
            # DataLoader's load_fn already returns Track objects (see
            # _batch_load_tracks below), not raw rows.
            return await info.context["track_loader"].load(self._track_id)
        row = DetectionDAL.instance().get_track(self._track_id)
        return _row_to_track(row) if row else None


@strawberry.type
class Image:
    id: int
    frame_index: int
    width: int
    height: int
    density_tier: str
    sequence_name: str
    # Populated only by the batch `images(ids)` path (page/round-trip-vs-
    # cacheability arm) so its single composite query doesn't turn into K
    # separate DAL calls when the client selects `detections` on each item
    # in the list -- that would defeat the whole point of measuring ONE
    # HTTP round trip (real batching, N5's principle, applied here too).
    # The singular `image(id)` path leaves this None and resolves lazily,
    # unchanged from before.
    _prefetched_detections: strawberry.Private[Optional[List[dict]]] = None

    @strawberry.field
    def detections(
        self, class_id: Optional[int] = None, min_confidence: Optional[float] = None
    ) -> List[Detection]:
        if self._prefetched_detections is not None and class_id is None and min_confidence is None:
            return [_row_to_detection(r) for r in self._prefetched_detections]
        dal = DetectionDAL.instance()
        full = dal.get_image_with_detections(
            self.id, class_id=class_id, min_confidence=min_confidence
        )
        rows = full["detections"] if full else []
        return [_row_to_detection(r) for r in rows]


def _row_to_detection(row: dict) -> Detection:
    return Detection(
        id=row["id"],
        class_id=row["class_id"],
        confidence=row["confidence"],
        bbox_x=row["bbox_x"],
        bbox_y=row["bbox_y"],
        bbox_w=row["bbox_w"],
        bbox_h=row["bbox_h"],
        _track_id=row["track_id"],
    )


def _row_to_track(row: dict) -> Track:
    return Track(
        id=row["id"],
        local_track_id=row["local_track_id"],
        class_id=row["class_id"],
        class_name=row["class_name"],
        first_frame=row["first_frame"],
        last_frame=row["last_frame"],
    )


def _row_to_image(row: dict, prefetched_detections: Optional[List[dict]] = None) -> Image:
    return Image(
        id=row["id"],
        frame_index=row["frame_index"],
        width=row["width"],
        height=row["height"],
        density_tier=row["density_tier"],
        sequence_name=row["sequence_name"],
        _prefetched_detections=prefetched_detections,
    )


@strawberry.type
class Query:
    @strawberry.field
    def image(self, id: int) -> Optional[Image]:
        row = DetectionDAL.instance().get_image(id)
        return _row_to_image(row) if row else None

    @strawberry.field
    def random_image(self, density_tier: str, seed: Optional[int] = None) -> Optional[Image]:
        """Server-side selection (anti-cache), mirrors REST's /images/random."""
        row = DetectionDAL.instance().pick_random_image(density_tier, seed=seed)
        return _row_to_image(row) if row else None

    @strawberry.field
    def images(self, ids: List[int]) -> List[Optional[Image]]:
        """Batch fetch -- the round-trip-vs-cacheability arm's GraphQL side:
        ONE HTTP round trip for a whole "page" of K ids, vs REST's K
        separate /images/{id}/detections calls for the same page. Pre-fetches
        detections in the SAME DB round trip (see Image._prefetched_detections)
        so this stays a genuine single composite fetch end to end."""
        rows = DetectionDAL.instance().get_images_with_detections(ids)
        return [_row_to_image(r, prefetched_detections=r["detections"]) if r else None for r in rows]

    @strawberry.field
    def track(self, id: int) -> Optional[Track]:
        row = DetectionDAL.instance().get_track(id)
        return _row_to_track(row) if row else None


async def _batch_load_tracks(track_ids: List[int]) -> List[Optional[Track]]:
    rows = DetectionDAL.instance().get_tracks(track_ids)
    return [_row_to_track(r) if r else None for r in rows]


async def get_context() -> dict:
    return {"track_loader": DataLoader(load_fn=_batch_load_tracks)}


schema = strawberry.Schema(
    query=Query,
    config=StrawberryConfig(auto_camel_case=False),
)

app = FastAPI(title="APE GraphQL", docs_url=None, redoc_url=None)
add_process_time_middleware(app)

# Process-local persisted-query store (hash -> query text). Fine for the
# existing single-worker uvicorn convention; a multi-worker deployment would
# need a shared store (e.g. the cache layer itself), out of scope here.
_PERSISTED_QUERIES: dict = {}


def _encode_compact(data: object) -> bytes:
    return json.dumps(data, separators=(",", ":")).encode("utf-8")


def _graphql_error_response(message: str, code: str) -> Response:
    body = _encode_compact({"errors": [{"message": message, "extensions": {"code": code}}]})
    # Never cache an error -- a client about to register/retry a query must
    # not have a stale "not found" served back to it by the cache layer.
    return Response(content=body, media_type="application/json",
                     headers={"Cache-Control": "no-store"})


@app.get("/graphql")
async def graphql_get(request: Request):
    """APQ-over-GET (N4) -- see module docstring for the wire protocol.
    Registered before app.include_router below so it wins over the
    Strawberry router's own internal GET handler at the same path.
    """
    query_param = request.query_params.get("query")
    extensions_raw = request.query_params.get("extensions")
    variables_raw = request.query_params.get("variables")
    operation_name = request.query_params.get("operationName")

    variables = json.loads(variables_raw) if variables_raw else None
    extensions = json.loads(extensions_raw) if extensions_raw else None
    persisted = (extensions or {}).get("persistedQuery") if extensions else None

    if persisted is not None:
        sha256_hash = persisted.get("sha256Hash")
        if query_param is not None:
            computed = hashlib.sha256(query_param.encode("utf-8")).hexdigest()
            if computed != sha256_hash:
                return _graphql_error_response(
                    "provided sha does not match query", "PERSISTED_QUERY_HASH_MISMATCH"
                )
            _PERSISTED_QUERIES[sha256_hash] = query_param
            query = query_param
        else:
            query = _PERSISTED_QUERIES.get(sha256_hash)
            if query is None:
                return _graphql_error_response(
                    "PersistedQueryNotFound", "PERSISTED_QUERY_NOT_FOUND"
                )
    elif query_param is not None:
        query = query_param
    else:
        return _graphql_error_response("no query or persisted query hash provided", "BAD_REQUEST")

    context = await get_context()
    result = await schema.execute(
        query, variable_values=variables, operation_name=operation_name, context_value=context
    )
    if result.errors:
        return _graphql_error_response(str(result.errors[0]), "GRAPHQL_EXECUTION_ERROR")

    body = _encode_compact({"data": result.data})
    # randomImage is anti-cache-by-design (mirrors REST's /images/random) --
    # detect it from the query text itself, same shared-function semantics.
    cacheable = "randomImage" not in query and "random_image" not in query
    headers = cache_headers(body, cacheable=cacheable)
    if cacheable and is_fresh(request.headers.get("if-none-match"), headers["ETag"]):
        return Response(status_code=304, headers=headers)
    return Response(content=body, media_type="application/json", headers=headers)


app.include_router(
    CompactGraphQLRouter(schema, context_getter=get_context), prefix="/graphql"
)


@app.on_event("startup")
def _startup() -> None:
    DetectionDAL.initialize(os.environ.get("APE_DB_PATH"))


@app.get("/health")
def health():
    return {
        "status": "ok",
        "db": DetectionDAL.instance().summary(),
        "batching": "on" if GRAPHQL_BATCHING else "off",
    }
