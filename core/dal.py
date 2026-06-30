"""
core/dal.py
===========
Single shared data-access layer over the relational SQLite store built by
~/training/build_detection_db.py. REST and GraphQL servers call these methods
IDENTICALLY (N2: same DB, same access path -- only the API surface differs).

Every method logs the exact SQL + params it executes when APE_LOG_SQL=1, so
acceptance criterion A2 ("same access path proven") is testable by diffing
logged statements between a REST call and its GraphQL equivalent, instead of
just being asserted because both call "the same module".

Thread safety: FastAPI's sync (`def`, not `async def`) route handlers run in
a worker threadpool, so multiple threads call into this DAL concurrently
under any real load (k6 with VUS>1 reproduces this immediately). A single
shared sqlite3.Connection is NOT safe for concurrent execute() calls from
different threads even with check_same_thread=False -- that flag only lifts
the same-thread assertion, it does not add locking. Caught during Phase 2b
workload-generator smoke testing: concurrent requests produced intermittent
404/500s on otherwise-valid ids. Fixed with one connection PER THREAD
(thread-local), which is also more representative of real concurrent-reader
behavior than serializing every query behind a lock would have been.
"""
from __future__ import annotations

import os
import random
import sqlite3
import threading
from dataclasses import dataclass, field
from typing import List, Optional

from .config import DEFAULT_DB_PATH, DEFAULT_TRAJECTORY_WINDOW

LOG_SQL = os.environ.get("APE_LOG_SQL", "0") == "1"


@dataclass
class SqlLogEntry:
    sql: str
    params: tuple


# Process-local log of executed statements (for tests; not for production load).
SQL_LOG: List[SqlLogEntry] = []


def reset_sql_log() -> None:
    SQL_LOG.clear()


class DetectionDAL:
    """Read-only access to the detection DB. One instance per server process."""

    _instance: Optional["DetectionDAL"] = None

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()

    @property
    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.execute("PRAGMA query_only = 1")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    @classmethod
    def initialize(cls, db_path: Optional[str] = None) -> "DetectionDAL":
        if cls._instance is None:
            cls._instance = cls(db_path or os.environ.get("APE_DB_PATH", DEFAULT_DB_PATH))
        return cls._instance

    @classmethod
    def instance(cls) -> "DetectionDAL":
        if cls._instance is None:
            raise RuntimeError("DetectionDAL not initialized -- call initialize() at startup.")
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    # -- internal: every read goes through this so SQL is logged uniformly --
    def _query(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        if LOG_SQL:
            SQL_LOG.append(SqlLogEntry(sql=sql, params=params))
        cur = self._conn.execute(sql, params)
        return cur.fetchall()

    # ------------------------------------------------------------------ images
    def get_image(self, image_id: int) -> Optional[dict]:
        """Flat image envelope, no detections (light payload, N2 control point)."""
        rows = self._query(
            """SELECT image.id, image.frame_index, image.width, image.height,
                      image.density_tier, sequence.name AS sequence_name
               FROM image JOIN sequence ON sequence.id = image.sequence_id
               WHERE image.id = ?""",
            (image_id,),
        )
        return dict(rows[0]) if rows else None

    def get_images_with_detections(self, image_ids: List[int]) -> List[Optional[dict]]:
        """Batch image+detections fetch for a FIXED set of ids (a "page") --
        the round-trip-vs-cacheability arm (BUILD SPEC gap: GraphQL's single
        composite query trades K round trips for one cache entry keyed by
        the exact id SET, vs REST's K independently-cacheable per-id calls).
        Two queries total (images IN-clause, detections IN-clause) regardless
        of K -- mirrors get_tracks()'s batching contract: same order as
        image_ids, None for missing ids.
        """
        if not image_ids:
            return []
        placeholders = ",".join("?" for _ in image_ids)
        img_rows = self._query(
            f"""SELECT image.id, image.frame_index, image.width, image.height,
                       image.density_tier, sequence.name AS sequence_name
                FROM image JOIN sequence ON sequence.id = image.sequence_id
                WHERE image.id IN ({placeholders})""",
            tuple(image_ids),
        )
        by_id = {r["id"]: dict(r) for r in img_rows}
        det_rows = self._query(
            f"""SELECT id, image_id, track_id, class_id, confidence, bbox_x, bbox_y, bbox_w, bbox_h
                FROM detection WHERE image_id IN ({placeholders})""",
            tuple(image_ids),
        )
        dets_by_image: dict = {}
        for r in det_rows:
            dets_by_image.setdefault(r["image_id"], []).append(dict(r))
        for img in by_id.values():
            img["detections"] = dets_by_image.get(img["id"], [])
        return [by_id.get(iid) for iid in image_ids]

    def get_image_with_detections(
        self,
        image_id: int,
        class_id: Optional[int] = None,
        min_confidence: Optional[float] = None,
    ) -> Optional[dict]:
        """Image + its detections, with an optional shared filter predicate.

        class_id/min_confidence default to None (no filtering) on BOTH
        protocols -- callers must pass them explicitly to exercise the
        filtered pattern, so neither arm silently filters while the other
        doesn't.
        """
        img = self.get_image(image_id)
        if img is None:
            return None

        sql = (
            "SELECT id, track_id, class_id, confidence, bbox_x, bbox_y, bbox_w, bbox_h "
            "FROM detection WHERE image_id = ?"
        )
        params: list = [image_id]
        if class_id is not None:
            sql += " AND class_id = ?"
            params.append(class_id)
        if min_confidence is not None:
            sql += " AND confidence >= ?"
            params.append(min_confidence)

        rows = self._query(sql, tuple(params))
        img["detections"] = [dict(r) for r in rows]
        return img

    def pick_random_image(self, density_tier: str, seed: Optional[int] = None) -> Optional[dict]:
        """Server-side selection of one image_id within a density tier.

        Mirrors the old core/selection.py anti-cache rationale: client asks
        for a CONDITION (tier), server picks the RECORD. Selection itself is
        done in Python (not SQL ORDER BY RANDOM()) so a given seed yields the
        same image_id regardless of SQLite's RNG/version -- required for the
        REST/GraphQL parity test (A1) to be deterministic.
        """
        rows = self._query(
            "SELECT id FROM image WHERE density_tier = ? ORDER BY id", (density_tier,)
        )
        if not rows:
            return None
        ids = [r["id"] for r in rows]
        rng = random.Random(seed) if seed is not None else random
        chosen = rng.choice(ids)
        return self.get_image(chosen)

    # ------------------------------------------------------------------ tracks
    def get_tracks(self, track_ids: List[int]) -> List[Optional[dict]]:
        """Batch fetch by id, used by GraphQL's DataLoader (N5: real batching,
        not a strawman N+1) -- one IN-clause query for the whole batch.
        Returns results in the SAME ORDER as track_ids (None for missing ids),
        which is the contract strawberry.dataloader.DataLoader.load_fn expects.
        """
        if not track_ids:
            return []
        placeholders = ",".join("?" for _ in track_ids)
        rows = self._query(
            f"""SELECT track.id, track.sequence_id, track.local_track_id,
                       track.class_id, track.first_frame, track.last_frame,
                       class.name AS class_name
                FROM track JOIN class ON class.id = track.class_id
                WHERE track.id IN ({placeholders})""",
            tuple(track_ids),
        )
        by_id = {r["id"]: dict(r) for r in rows}
        return [by_id.get(tid) for tid in track_ids]

    def get_track(self, track_id: int) -> Optional[dict]:
        rows = self._query(
            """SELECT track.id, track.sequence_id, track.local_track_id,
                      track.class_id, track.first_frame, track.last_frame,
                      class.name AS class_name
               FROM track JOIN class ON class.id = track.class_id
               WHERE track.id = ?""",
            (track_id,),
        )
        return dict(rows[0]) if rows else None

    def get_track_trajectory(
        self, track_id: int, center_frame: Optional[int] = None,
        window: int = DEFAULT_TRAJECTORY_WINDOW,
    ) -> Optional[dict]:
        """Track + its detections within a bounded +/-window frame range.

        Bounded per spec S7 so trajectory length doesn't become an
        uncontrolled second payload-weight driver alongside density.
        center_frame defaults to the track's first_frame if not given.
        """
        track = self.get_track(track_id)
        if track is None:
            return None
        center = center_frame if center_frame is not None else track["first_frame"]
        lo, hi = center - window, center + window

        rows = self._query(
            """SELECT detection.id, detection.image_id, image.frame_index,
                      detection.confidence, detection.bbox_x, detection.bbox_y,
                      detection.bbox_w, detection.bbox_h
               FROM detection JOIN image ON image.id = detection.image_id
               WHERE detection.track_id = ?
                 AND image.frame_index BETWEEN ? AND ?
               ORDER BY image.frame_index""",
            (track_id, lo, hi),
        )
        track["trajectory"] = [dict(r) for r in rows]
        return track

    # ------------------------------------------------------------------ misc
    def summary(self) -> dict:
        counts = {}
        for table in ("sequence", "image", "track", "detection"):
            row = self._query(f"SELECT COUNT(*) AS n FROM {table}")
            counts[table] = row[0]["n"]
        return counts
