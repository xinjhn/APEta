"""
tests/test_parity_mot.py
=========================
Parity gate for the MOT scenario study (design/SCENARIO_DESIGN.md §4) --
HARD GATE: no benchmark runs until this whole file is green on BOTH data
backends (APE_DATA_BACKEND=sqlite and =memory).

Criteria implemented, per scenario:
  M1  field-level equality of REST body vs GraphQL data.image (minus the
      protocol envelope), identical detection ordering, and CONSTANT
      byte-level envelope delta across all sampled (tier, seed) cells.
  M2  as M1, plus: both bodies carry EXACTLY the 2 projected fields
      (class_id, confidence) -- proves REST projects server-side rather
      than send-full-and-strip.
  M3  as M1 with the shared filter constants (class_id=4, min_confidence
      =0.5); an empty filtered result is VALID and must be 200+[] on both.
  M4  aggregate list equality with identical class_id-ascending ordering
      (REST's {"image_id":...} vs GraphQL's image{id ...} is a documented
      constant envelope difference).
  M5  union of REST call #1 (/tracks/{id}) and call #2 (trajectory) must
      field-equal GraphQL data.track; same trajectory ordering/length;
      envelope delta between REST call #2 and the GraphQL body constant.
      M5-embed (?embed=trajectory) must byte-map to the same content.
  M6  concatenation of the K REST bodies field-equals the GraphQL tracks
      list in the same order; GraphQL side must resolve the whole page in
      ONE DAL batch (2 SQL statements -- the N5 no-lazy-N+1 guarantee).

Sampling: seeded ids x all tiers x 4 seeds, ids drawn through the SAME
shared seeded pickers the study uses (core/selection.py + core/dal.py), so
the test exercises exactly the entity-selection path of the benchmark.

Extra guards:
  * the GraphQL query TEXTS here are asserted identical to the ones
    embedded in k6/workload_mot.js -- a parity pass is meaningless if the
    benchmark then sends different queries;
  * cross-backend consistency: the memory backend must return
    byte-identical REST bodies to the sqlite backend for the same requests.

Run:
    venv/bin/python -m pytest tests/test_parity_mot.py -v
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("APE_DB_PATH", "/home/ubuntu/training/mot_detections.db")
os.environ["APE_LOG_SQL"] = "1"

import pytest  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from core import dal as dal_module  # noqa: E402
from core.dal import DetectionDAL, MemoryDetectionDAL  # noqa: E402
from core.selection import (  # noqa: E402
    TRAJECTORY_WINDOW_TIERS,
    pick_track_id,
    track_center_frame,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SEEDS = (42, 43, 44, 45)
DENSITY_TIERS = ("low", "medium", "high")
WINDOWS = tuple(sorted(TRAJECTORY_WINDOW_TIERS.values()))  # (2, 8, 23)
PAGE_SIZES = (1, 5, 10)
ALL_FIELDS = "class_id,confidence,bbox_x,bbox_y,bbox_w,bbox_h"

# MUST stay textually identical to k6/workload_mot.js's GQL_QUERIES --
# enforced by test_queries_match_k6_workload below.
GQL_QUERIES = {
    "M1": "query M1($id: Int!) { image(id: $id) { id frame_index width height density_tier sequence_name detections { class_id confidence bbox_x bbox_y bbox_w bbox_h } } }",
    "M2": "query M2($id: Int!) { image(id: $id) { id frame_index width height density_tier sequence_name detections { class_id confidence } } }",
    "M3": "query M3($id: Int!) { image(id: $id) { id frame_index width height density_tier sequence_name detections(class_id: 4, min_confidence: 0.5) { class_id confidence bbox_x bbox_y bbox_w bbox_h } } }",
    "M4": "query M4($id: Int!) { image(id: $id) { id class_counts { class_id count } } }",
    "M5": "query M5($id: Int!, $w: Int!, $c: Int!) { track(id: $id) { id sequence_id local_track_id class_id first_frame last_frame class_name trajectory(window: $w, center_frame: $c) { id image_id frame_index confidence bbox_x bbox_y bbox_w bbox_h } } }",
    "M6": "query M6($ids: [Int!]!) { tracks(ids: $ids) { id sequence_id local_track_id class_id first_frame last_frame class_name trajectory(window: 2) { id image_id frame_index confidence bbox_x bbox_y bbox_w bbox_h } } }",
}


# ------------------------------------------------------------------ fixtures

@pytest.fixture(scope="module", params=["sqlite", "memory"])
def stack(request):
    """(backend_name, rest_client, gql_client) -- the whole suite runs once
    per backend; servers share the process-wide DAL singleton, re-initialized
    per param via the same APE_DATA_BACKEND dispatch the orchestrator uses."""
    os.environ["APE_DATA_BACKEND"] = request.param
    DetectionDAL.reset()
    import graphql_server
    import rest_server

    with TestClient(rest_server.app) as rest, TestClient(graphql_server.app) as gql:
        yield request.param, rest, gql
    DetectionDAL.reset()
    os.environ["APE_DATA_BACKEND"] = "sqlite"


def _gql(client: TestClient, query: str, variables: dict) -> tuple:
    """Returns (data_dict, raw_body_bytes_len). POST /graphql goes through
    CompactGraphQLRouter -- the same compact encoder the benchmark's GET
    route uses, so byte deltas here are representative."""
    r = client.post("/graphql", json={"query": query, "variables": variables})
    r.raise_for_status()
    body = r.json()
    assert "errors" not in body, f"GraphQL error: {body.get('errors')}"
    return body["data"], len(r.content)


def _sample_image_ids(seed: int) -> dict:
    dal = DetectionDAL.instance()
    return {tier: dal.pick_random_image(tier, seed=seed)["id"] for tier in DENSITY_TIERS}


def _sample_track(window: int, seed: int) -> tuple:
    dal = DetectionDAL.instance()
    pool = dal.list_eligible_track_ids(window)
    tid = pick_track_id(pool, seed=seed)
    t = dal.get_track(tid)
    return tid, track_center_frame(t["first_frame"], t["last_frame"])


def _sample_page(k: int, seed: int) -> list:
    pool = DetectionDAL.instance().list_eligible_track_ids(2)
    start = random.Random(seed).randrange(0, len(pool) - k + 1)
    return pool[start:start + k]


def _assert_constant(deltas: list, scenario: str) -> None:
    assert len(set(deltas)) == 1, (
        f"{scenario}: envelope delta not constant across samples: {deltas} "
        f"-- a varying delta means one side serializes data the other doesn't "
        f"(serialization leak), not a fixed protocol envelope"
    )


# ------------------------------------------------------------------ M1 / M2 / M3

def _image_scenario_roundtrip(rest, gql, scenario: str, image_id: int) -> tuple:
    if scenario == "M1":
        r = rest.get(f"/images/{image_id}/detections?fields={ALL_FIELDS}")
    elif scenario == "M2":
        r = rest.get(f"/images/{image_id}/detections?fields=class_id,confidence")
    else:  # M3
        r = rest.get(f"/images/{image_id}/detections?class_id=4&min_confidence=0.5&fields={ALL_FIELDS}")
    assert r.status_code == 200
    g, g_len = _gql(gql, GQL_QUERIES[scenario], {"id": image_id})
    return r.json(), len(r.content), g["image"], g_len


@pytest.mark.parametrize("scenario", ["M1", "M2", "M3"])
def test_image_scenario_parity(stack, scenario):
    _, rest, gql = stack
    deltas = []
    for seed in SEEDS:
        for tier, image_id in _sample_image_ids(seed).items():
            r_body, r_len, g_body, g_len = _image_scenario_roundtrip(rest, gql, scenario, image_id)
            # Field-level, order-preserving equality: same image envelope
            # keys, same detections in the same order.
            assert r_body == g_body, f"{scenario} {tier} seed={seed} image={image_id}: bodies differ"
            deltas.append(g_len - r_len)
            if scenario == "M2":
                for side, body in (("REST", r_body), ("GraphQL", g_body)):
                    for d in body["detections"]:
                        assert set(d.keys()) == {"class_id", "confidence"}, (
                            f"M2 {side}: detection carries {set(d.keys())} -- projection leak"
                        )
            if scenario == "M3":
                for d in r_body["detections"]:
                    assert d["class_id"] == 4 and d["confidence"] >= 0.5
    _assert_constant(deltas, scenario)


def test_m3_empty_result_is_valid(stack):
    """An image with NO car>=0.5 detections must yield 200 + [] on both
    protocols (Phase-1 rule: empty is data, not an error)."""
    _, rest, gql = stack
    dal = DetectionDAL.instance()
    empty_id = None
    for tier in DENSITY_TIERS:  # low tier almost always has one
        for seed in range(100):
            iid = dal.pick_random_image(tier, seed=seed)["id"]
            full = dal.get_image_with_detections(iid, class_id=4, min_confidence=0.5)
            if not full["detections"]:
                empty_id = iid
                break
        if empty_id:
            break
    assert empty_id is not None, "corpus unexpectedly has no filter-empty image"
    r = rest.get(f"/images/{empty_id}/detections?class_id=4&min_confidence=0.5&fields={ALL_FIELDS}")
    assert r.status_code == 200 and r.json()["detections"] == []
    g, _ = _gql(gql, GQL_QUERIES["M3"], {"id": empty_id})
    assert g["image"]["detections"] == []


# ------------------------------------------------------------------ M4

def test_m4_aggregate_parity(stack):
    _, rest, gql = stack
    deltas = []
    for seed in SEEDS:
        for tier, image_id in _sample_image_ids(seed).items():
            r = rest.get(f"/images/{image_id}/class_counts")
            assert r.status_code == 200
            r_body = r.json()
            g, g_len = _gql(gql, GQL_QUERIES["M4"], {"id": image_id})
            g_body = g["image"]
            # image_id (REST) vs id (GraphQL) is the documented constant
            # envelope difference; the aggregate payload itself must match
            # exactly, including class_id-ascending order.
            assert r_body["image_id"] == g_body["id"]
            assert r_body["class_counts"] == g_body["class_counts"], (
                f"M4 {tier} seed={seed}: aggregates differ"
            )
            ids = [c["class_id"] for c in r_body["class_counts"]]
            assert ids == sorted(ids), "M4: class ordering not class_id-ascending"
            deltas.append(g_len - len(r.content))
    _assert_constant(deltas, "M4")


# ------------------------------------------------------------------ M5

def test_m5_nested_parity_and_embed(stack):
    _, rest, gql = stack
    deltas = []
    for seed in SEEDS:
        for window in WINDOWS:
            tid, center = _sample_track(window, seed)
            r1 = rest.get(f"/tracks/{tid}")
            r2 = rest.get(f"/tracks/{tid}/trajectory?center_frame={center}&window={window}")
            assert r1.status_code == 200 and r2.status_code == 200
            union = dict(r1.json())
            union.update(r2.json())
            g, g_len = _gql(gql, GQL_QUERIES["M5"], {"id": tid, "w": window, "c": center})
            g_body = g["track"]
            assert union == g_body, f"M5 W={window} seed={seed} track={tid}: union != GraphQL"
            assert [p["frame_index"] for p in g_body["trajectory"]] == sorted(
                p["frame_index"] for p in g_body["trajectory"]
            ), "M5: trajectory not frame-ordered"
            # Envelope delta: REST call #2's body carries the same content as
            # the GraphQL body minus the {"data":{"track":...}} wrapper.
            deltas.append(g_len - len(r2.content))
            # M5-embed (Q6 counterfactual): single call, same content as the
            # 2-round-trip union, byte-identical to REST call #2.
            re_ = rest.get(f"/tracks/{tid}?embed=trajectory&center_frame={center}&window={window}")
            assert re_.status_code == 200
            assert re_.content == r2.content, "M5E: embed body != trajectory body"
    _assert_constant(deltas, "M5")


# ------------------------------------------------------------------ M6

def test_m6_page_parity(stack):
    _, rest, gql = stack
    for seed in SEEDS:
        for k in PAGE_SIZES:
            ids = _sample_page(k, seed)
            rest_bodies, rest_bytes = [], 0
            for tid in ids:
                r = rest.get(f"/tracks/{tid}/trajectory?window=2")
                assert r.status_code == 200
                rest_bodies.append(r.json())
                rest_bytes += len(r.content)
            g, g_len = _gql(gql, GQL_QUERIES["M6"], {"ids": ids})
            g_list = g["tracks"]
            assert rest_bodies == g_list, f"M6 K={k} seed={seed}: concatenation != GraphQL list"


def test_m6_single_dal_batch(stack):
    """The N5 guarantee: one composite tracks(ids) query = ONE DAL batch
    (2 IN-clause SQL statements: tracks + detections), never K lazy
    per-item resolutions. SQL log only exists on the sqlite backend."""
    backend, _, gql = stack
    if backend != "sqlite":
        pytest.skip("SQL log is a sqlite-backend concept")
    ids = _sample_page(10, SEEDS[0])
    dal_module.reset_sql_log()
    _gql(gql, GQL_QUERIES["M6"], {"ids": ids})
    stmts = list(dal_module.SQL_LOG)
    assert len(stmts) == 2, (
        f"M6 GraphQL page resolved in {len(stmts)} SQL statements, expected 2 "
        f"-- trajectory prefetch fell back to lazy N+1"
    )
    assert all(" IN (" in s.sql for s in stmts)


def test_m5_same_access_path(stack):
    """A2 for M5: the REST 2-call flow and the GraphQL nested query must
    touch the same tables for the same logical request."""
    backend, rest, gql = stack
    if backend != "sqlite":
        pytest.skip("SQL log is a sqlite-backend concept")
    tid, center = _sample_track(8, SEEDS[0])
    table_re = re.compile(r"\bFROM\s+(\w+)|\bJOIN\s+(\w+)", re.IGNORECASE)

    def tables(entries):
        out = set()
        for e in entries:
            for m in table_re.finditer(e.sql):
                out.add((m.group(1) or m.group(2)).lower())
        return out

    dal_module.reset_sql_log()
    rest.get(f"/tracks/{tid}")
    rest.get(f"/tracks/{tid}/trajectory?center_frame={center}&window=8")
    rest_tables = tables(dal_module.SQL_LOG)
    dal_module.reset_sql_log()
    _gql(gql, GQL_QUERIES["M5"], {"id": tid, "w": 8, "c": center})
    gql_tables = tables(dal_module.SQL_LOG)
    assert rest_tables == gql_tables, f"M5 access path diverged: {rest_tables} vs {gql_tables}"


# ------------------------------------------------------------------ guards

def test_queries_match_k6_workload():
    """The benchmark must send EXACTLY the queries this suite verified."""
    js = (PROJECT_ROOT / "k6" / "workload_mot.js").read_text(encoding="utf-8")
    found = dict(re.findall(r'^\s*(M\d): "((?:[^"\\]|\\.)*)",?$', js, re.MULTILINE))
    assert found == GQL_QUERIES, (
        "GQL query drift between tests/test_parity_mot.py and k6/workload_mot.js"
    )


def test_memory_backend_matches_sqlite_bytes():
    """Backend equivalence, byte level: for the same seeded requests the
    memory backend must produce identical DAL outputs (hence identical JSON
    bytes) to sqlite -- ordering included."""
    db = os.environ["APE_DB_PATH"]
    sql = DetectionDAL(db)
    mem = MemoryDetectionDAL(db)
    for seed in SEEDS:
        for tier in DENSITY_TIERS:
            a = sql.pick_random_image(tier, seed=seed)
            b = mem.pick_random_image(tier, seed=seed)
            assert a == b
            fa = sql.get_image_with_detections(a["id"])
            fb = mem.get_image_with_detections(b["id"])
            assert json.dumps(fa, separators=(",", ":")) == json.dumps(fb, separators=(",", ":"))
        for window in WINDOWS:
            assert sql.list_eligible_track_ids(window) == mem.list_eligible_track_ids(window)
            tid = pick_track_id(sql.list_eligible_track_ids(window), seed=seed)
            t = sql.get_track(tid)
            c = track_center_frame(t["first_frame"], t["last_frame"])
            ta = sql.get_track_trajectory(tid, center_frame=c, window=window)
            tb = mem.get_track_trajectory(tid, center_frame=c, window=window)
            assert json.dumps(ta, separators=(",", ":")) == json.dumps(tb, separators=(",", ":"))
        ids = sql.list_eligible_track_ids(2)[:10]
        pa = sql.get_tracks_with_trajectories(ids, window=2)
        pb = mem.get_tracks_with_trajectories(ids, window=2)
        assert json.dumps(pa, separators=(",", ":")) == json.dumps(pb, separators=(",", ":"))


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
