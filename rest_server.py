"""
rest_server.py
===============
REST (FastAPI) server for the Phase 1 REST-vs-GraphQL caching study. Run
ALTERNATELY with graphql_server.py (single worker at a time).

Both servers call core/dal.py's DetectionDAL identically (N2: same DB, same
access path -- the API surface is the only systematic difference).

Endpoints:
    GET /images/{image_id}
    GET /images/{image_id}/detections?fields=&class_id=&min_confidence=
    GET /images/random?density_tier=&seed=
    GET /tracks/{track_id}
    GET /tracks/{track_id}/trajectory?center_frame=&window=

`fields=` on /detections is a real server-side sparse fieldset (projection
happens before serialization, not "send everything and let the client
discard") -- the same fairness principle as the retired Path-B study, just
reapplied to the new schema via core/projection.py.

Caching (N4): every cacheable GET below carries Cache-Control + ETag computed
by core/caching.py (the SAME function GraphQL's APQ-over-GET route uses) and
answers 304 on a matching If-None-Match. /images/random is force-no-store --
it's anti-cache by design (server re-selects on every call behind a stable
URL), so caching it would silently collapse the access-pattern IV.

Run:
    APE_DB_PATH=/home/ubuntu/training/mot_detections.db \
    uvicorn rest_server:app --workers 1 --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import json
import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import Response

from core.caching import cache_headers, is_fresh
from core.config import DEFAULT_TRAJECTORY_WINDOW, DETECTION_FIELDS
from core.dal import DetectionDAL
from core.timing import add_process_time_middleware

app = FastAPI(title="APE REST", docs_url=None, redoc_url=None)
add_process_time_middleware(app)


@app.on_event("startup")
def _startup() -> None:
    DetectionDAL.initialize(os.environ.get("APE_DB_PATH"))


def _project(detection: dict, fields: Optional[List[str]]) -> dict:
    if fields is None:
        return detection
    allowed = [f for f in DETECTION_FIELDS if f in fields]
    return {f: detection[f] for f in allowed if f in detection}


def _respond(request: Request, data: dict, cacheable: bool) -> Response:
    body = json.dumps(data, separators=(",", ":")).encode("utf-8")
    headers = cache_headers(body, cacheable=cacheable)
    if cacheable and is_fresh(request.headers.get("if-none-match"), headers["ETag"]):
        return Response(status_code=304, headers=headers)
    return Response(content=body, media_type="application/json", headers=headers)


@app.get("/images/random")
def random_image(
    request: Request,
    density_tier: str = Query(...),
    seed: Optional[int] = Query(None),
):
    # Registered BEFORE /images/{image_id} -- Starlette matches routes in
    # registration order, and a static path must win over a path-param
    # route or "random" gets swallowed as {image_id} (404/422 instead of
    # the random-selection handler -- caught during Phase 2a verification).
    rec = DetectionDAL.instance().pick_random_image(density_tier, seed=seed)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"no images in tier {density_tier!r}")
    return _respond(request, rec, cacheable=False)


@app.get("/images/{image_id}")
def get_image(image_id: int, request: Request):
    rec = DetectionDAL.instance().get_image(image_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="image not found")
    return _respond(request, rec, cacheable=True)


@app.get("/images/{image_id}/detections")
def get_image_detections(
    image_id: int,
    request: Request,
    fields: Optional[str] = Query(None, description="comma-separated subset of DETECTION_FIELDS"),
    class_id: Optional[int] = Query(None),
    min_confidence: Optional[float] = Query(None),
):
    rec = DetectionDAL.instance().get_image_with_detections(
        image_id, class_id=class_id, min_confidence=min_confidence
    )
    if rec is None:
        raise HTTPException(status_code=404, detail="image not found")
    field_list = fields.split(",") if fields else None
    rec["detections"] = [_project(d, field_list) for d in rec["detections"]]
    return _respond(request, rec, cacheable=True)


@app.get("/tracks/{track_id}")
def get_track(track_id: int, request: Request):
    rec = DetectionDAL.instance().get_track(track_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="track not found")
    return _respond(request, rec, cacheable=True)


@app.get("/tracks/{track_id}/trajectory")
def get_track_trajectory(
    track_id: int,
    request: Request,
    center_frame: Optional[int] = Query(None),
    window: int = Query(DEFAULT_TRAJECTORY_WINDOW),
):
    rec = DetectionDAL.instance().get_track_trajectory(
        track_id, center_frame=center_frame, window=window
    )
    if rec is None:
        raise HTTPException(status_code=404, detail="track not found")
    return _respond(request, rec, cacheable=True)


@app.get("/health")
def health():
    return {"status": "ok", "db": DetectionDAL.instance().summary()}
