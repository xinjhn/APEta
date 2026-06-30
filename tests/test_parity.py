"""
tests/test_parity.py
=====================
Acceptance criteria A1 and A2 (BUILD SPEC §5) as automated tests, replacing
the retired Path-B parity test (which checked the old flat S1-S4 patterns
against the in-memory JSON pool -- not applicable to this schema).

A1 -- byte-identical underlying data: for the same image_id/track_id, REST
and GraphQL must return deep-equal records (modulo protocol envelope, e.g.
GraphQL's {"data": {...}} wrapper and field selection vs REST's fixed shape).

A2 -- same access path proven: with APE_LOG_SQL=1, the DAL logs every SQL
statement it executes. For an equivalent REST call and GraphQL query, the
tables and predicate columns referenced must match -- not just "trust the
shared DAL," actually diff what each protocol caused it to run.

Run:
    APE_DB_PATH=/home/ubuntu/training/mot_detections.db APE_LOG_SQL=1 \
        python -m pytest tests/test_parity.py -v
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("APE_DB_PATH", "/home/ubuntu/training/mot_detections.db")
os.environ["APE_LOG_SQL"] = "1"

import pytest  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from core import dal as dal_module  # noqa: E402
from core.dal import DetectionDAL  # noqa: E402


def _sample_ids():
    """Pull a few real image_ids (one per density tier) and track_ids
    (one single-frame, one multi-frame) directly from the DB for the test
    fixtures -- avoids hard-coding ids that could drift if the corpus is
    regenerated."""
    DetectionDAL.reset()
    d = DetectionDAL.initialize()
    image_ids = {}
    for tier in ("low", "medium", "high"):
        rows = d._query("SELECT id FROM image WHERE density_tier = ? LIMIT 1", (tier,))
        image_ids[tier] = rows[0]["id"]
    track_rows = d._query(
        "SELECT id FROM track WHERE last_frame > first_frame LIMIT 1"
    )
    track_id = track_rows[0]["id"]
    DetectionDAL.reset()
    return image_ids, track_id


IMAGE_IDS, TRACK_ID = _sample_ids()


@pytest.fixture(scope="module")
def clients():
    import graphql_server
    import rest_server

    with TestClient(rest_server.app) as rest, TestClient(graphql_server.app) as gql:
        yield rest, gql


def _gql(client: TestClient, query: str) -> dict:
    r = client.post("/graphql", json={"query": query})
    r.raise_for_status()
    body = r.json()
    assert "errors" not in body, f"GraphQL error: {body.get('errors')}"
    return body["data"]


# --------------------------------------------------------------------------- A1

@pytest.mark.parametrize("tier", ["low", "medium", "high"])
def test_a1_image_detections_parity(clients, tier):
    rest, gql = clients
    image_id = IMAGE_IDS[tier]

    r = rest.get(f"/images/{image_id}/detections").json()
    g = _gql(
        gql,
        f"{{ image(id:{image_id}) {{ id frame_index width height density_tier "
        f"sequence_name detections {{ id class_id confidence "
        f"bbox_x bbox_y bbox_w bbox_h }} }} }}",
    )["image"]

    assert r["id"] == g["id"]
    assert r["frame_index"] == g["frame_index"]
    assert r["density_tier"] == g["density_tier"]
    # GraphQL deliberately doesn't expose the raw track_id foreign key scalar
    # (clients traverse via the resolved `track` object instead); REST's
    # unfiltered endpoint returns the full DB row including it. Strip it
    # before comparing -- this is a protocol envelope difference, not a data
    # divergence (covered separately by test_a1_track_trajectory_parity).
    r_dets = sorted(
        ({k: v for k, v in d.items() if k != "track_id"} for d in r["detections"]),
        key=lambda d: d["id"],
    )
    g_dets = sorted(g["detections"], key=lambda d: d["id"])
    assert r_dets == g_dets, f"detection sets differ for image {image_id} ({tier})"


def test_a1_image_detections_filtered_parity(clients):
    rest, gql = clients
    image_id = IMAGE_IDS["high"]

    r = rest.get(f"/images/{image_id}/detections?class_id=4&min_confidence=0.5").json()
    g = _gql(
        gql,
        f"{{ image(id:{image_id}) {{ id detections(class_id:4, min_confidence:0.5) "
        f"{{ id class_id confidence bbox_x bbox_y bbox_w bbox_h }} }} }}",
    )["image"]

    r_dets = sorted(r["detections"], key=lambda d: d["id"])
    g_dets = sorted(g["detections"], key=lambda d: d["id"])
    assert r_dets == g_dets
    # Empty result is valid (no matching detections) -- must not be treated
    # as an error by either protocol.
    for d in r_dets:
        assert d["class_id"] == 4 and d["confidence"] >= 0.5


def test_a1_track_trajectory_parity(clients):
    rest, gql = clients

    r = rest.get(f"/tracks/{TRACK_ID}/trajectory?window=5").json()
    g = _gql(
        gql,
        f"{{ track(id:{TRACK_ID}) {{ id class_id class_name first_frame last_frame "
        f"trajectory(window:5) {{ id image_id frame_index confidence "
        f"bbox_x bbox_y bbox_w bbox_h }} }} }}",
    )["track"]

    assert r["class_id"] == g["class_id"]
    r_traj = sorted(r["trajectory"], key=lambda p: p["frame_index"])
    g_traj = sorted(g["trajectory"], key=lambda p: p["frame_index"])
    assert r_traj == g_traj


def test_a1_404_parity(clients):
    rest, gql = clients
    missing_id = 99_999_999

    r = rest.get(f"/images/{missing_id}")
    assert r.status_code == 404

    g_body = gql.post(
        "/graphql", json={"query": f"{{ image(id:{missing_id}) {{ id }} }}"}
    ).json()
    assert g_body["data"]["image"] is None


# --------------------------------------------------------------------------- A2

_TABLE_RE = re.compile(r"\bFROM\s+(\w+)|\bJOIN\s+(\w+)", re.IGNORECASE)


def _tables_referenced(sql: str) -> set:
    tables = set()
    for m in _TABLE_RE.finditer(sql):
        tables.add((m.group(1) or m.group(2)).lower())
    return tables


def test_a2_same_access_path_for_detections(clients):
    """REST's /images/{id}/detections and GraphQL's image{detections} must
    hit the same tables with the same predicate shape -- proven by diffing
    the SQL the shared DAL actually executed for each call, not asserted
    because "they call the same module"."""
    rest, gql = clients
    image_id = IMAGE_IDS["medium"]

    dal_module.reset_sql_log()
    rest.get(f"/images/{image_id}/detections?class_id=4&min_confidence=0.5")
    rest_sql = list(dal_module.SQL_LOG)

    dal_module.reset_sql_log()
    _gql(
        gql,
        f"{{ image(id:{image_id}) {{ id detections(class_id:4, min_confidence:0.5) "
        f"{{ id }} }} }}",
    )
    gql_sql = list(dal_module.SQL_LOG)

    assert rest_sql, "no SQL logged for REST call -- check APE_LOG_SQL=1"
    assert gql_sql, "no SQL logged for GraphQL call -- check APE_LOG_SQL=1"

    rest_tables = set().union(*(_tables_referenced(e.sql) for e in rest_sql))
    gql_tables = set().union(*(_tables_referenced(e.sql) for e in gql_sql))
    assert rest_tables == gql_tables, (
        f"REST touched {rest_tables} but GraphQL touched {gql_tables} "
        f"for the same logical request -- access path diverged"
    )

    # Same predicate columns in the detection query specifically (class_id +
    # confidence threshold), regardless of protocol-specific extra columns.
    rest_detection_sql = [e for e in rest_sql if "detection" in e.sql.lower()]
    gql_detection_sql = [e for e in gql_sql if "detection" in e.sql.lower()]
    assert rest_detection_sql and gql_detection_sql
    assert "class_id = ?" in rest_detection_sql[0].sql
    assert "class_id = ?" in gql_detection_sql[0].sql
    assert "confidence >= ?" in rest_detection_sql[0].sql
    assert "confidence >= ?" in gql_detection_sql[0].sql
    assert rest_detection_sql[0].params == gql_detection_sql[0].params


def test_a2_track_batching_uses_in_clause(clients):
    """N5: GraphQL's Track resolver must batch via DataLoader -- one IN-clause
    query for a request that resolves multiple detections' tracks, not one
    query per detection."""
    rest, gql = clients
    image_id = IMAGE_IDS["high"]

    dal_module.reset_sql_log()
    _gql(
        gql,
        f"{{ image(id:{image_id}) {{ detections {{ id track {{ id class_name }} }} }} }}",
    )
    gql_sql = list(dal_module.SQL_LOG)
    track_queries = [e for e in gql_sql if "FROM track" in e.sql]
    assert len(track_queries) <= 1, (
        f"expected track lookups to batch into <=1 query, got {len(track_queries)} "
        f"-- DataLoader batching may not be wired up (check APE_GRAPHQL_BATCHING)"
    )
    if track_queries:
        assert " IN (" in track_queries[0].sql


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
