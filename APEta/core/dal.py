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
from .selection import eligible_point_count, pick_track_id

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
            path = db_path or os.environ.get("APE_DB_PATH", DEFAULT_DB_PATH)
            backend = os.environ.get("APE_DATA_BACKEND", "sqlite").strip().lower()
            if backend == "memory":
                # M1-only serialization-isolation probe (approved Q1): every
                # row preloaded into dicts at startup, behind the SAME
                # interface and with the SAME result ordering as the SQL
                # paths (see MemoryDetectionDAL). Servers/tests don't know
                # which backend is live -- only this dispatch point does.
                cls._instance = MemoryDetectionDAL(path)
            elif backend == "sqlite":
                cls._instance = cls(path)
            else:
                raise ValueError(f"APE_DATA_BACKEND must be sqlite|memory, got {backend!r}")
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

    def list_eligible_track_ids(self, window: int) -> List[int]:
        """Eligibility pool untuk tier window W (design/mot_profile.json):
        track dengan >= 2W+1 deteksi, terurut id (determinisme seeded pick)."""
        rows = self._query(
            """SELECT track_id FROM detection
               GROUP BY track_id HAVING COUNT(*) >= ?
               ORDER BY track_id""",
            (eligible_point_count(window),),
        )
        return [r["track_id"] for r in rows]

    def pick_random_track(self, window: int, seed: Optional[int] = None) -> Optional[dict]:
        """Seeded track picker (M5/M6): server-side, deterministik per
        (window, seed) -- padanan pick_random_image() untuk entitas track,
        pemilihan di Python via core/selection.py (modul BERSAMA)."""
        ids = self.list_eligible_track_ids(window)
        if not ids:
            return None
        return self.get_track(pick_track_id(ids, seed=seed))

    def get_tracks_with_trajectories(
        self, track_ids: List[int], window: int = DEFAULT_TRAJECTORY_WINDOW,
    ) -> List[Optional[dict]]:
        """Batch track+trajectory fetch untuk satu "page" id TETAP -- sisi
        GraphQL dari arm M6 (tracks(ids) prefetch), cermin kontrak
        get_images_with_detections(): DUA query total berapa pun K (tracks
        IN-clause + detections IN-clause), urutan hasil = urutan track_ids,
        None untuk id yang tidak ada.

        center_frame per track = first_frame track itu (default yang sama
        dipakai REST /tracks/{id}/trajectory tanpa center_frame), dihitung di
        SQL via JOIN track sehingga bound-nya identik dengan jalur
        get_track_trajectory() per-track. Urutan titik: frame_index menaik
        per track (ORDER BY track_id, frame_index).
        """
        if not track_ids:
            return []
        tracks = self.get_tracks(track_ids)
        by_id = {t["id"]: t for t in tracks if t}
        for t in by_id.values():
            t["trajectory"] = []
        if by_id:
            placeholders = ",".join("?" for _ in by_id)
            rows = self._query(
                f"""SELECT detection.track_id, detection.id, detection.image_id,
                           image.frame_index, detection.confidence,
                           detection.bbox_x, detection.bbox_y,
                           detection.bbox_w, detection.bbox_h
                    FROM detection
                    JOIN image ON image.id = detection.image_id
                    JOIN track ON track.id = detection.track_id
                    WHERE detection.track_id IN ({placeholders})
                      AND image.frame_index
                          BETWEEN track.first_frame - ? AND track.first_frame + ?
                    ORDER BY detection.track_id, image.frame_index""",
                tuple(by_id.keys()) + (window, window),
            )
            for r in rows:
                point = dict(r)
                tid = point.pop("track_id")
                by_id[tid]["trajectory"].append(point)
        return [by_id.get(tid) for tid in track_ids]

    # ------------------------------------------------------------------ misc
    def summary(self) -> dict:
        counts = {}
        for table in ("sequence", "image", "track", "detection"):
            row = self._query(f"SELECT COUNT(*) AS n FROM {table}")
            counts[table] = row[0]["n"]
        return counts


class MemoryDetectionDAL(DetectionDAL):
    """APE_DATA_BACKEND=memory: dict-backed variant of the DAL for the
    M1-only serialization-isolation probe (approved Q1 of the MOT scenario
    design). Preloads every row from the SQLite file ONCE at construction,
    then serves all reads from Python dicts -- no SQL engine in the request
    path, so the protocol comparison isolates serialization + framework cost
    the way the retired Phase-1 in-memory study did.

    Contract: identical query semantics AND identical result ordering to the
    SQL paths above --
      * detections of an image: id ascending (matches SQLite's index-scan
        rowid order on `WHERE image_id = ?`);
      * trajectory points: frame_index ascending (matches ORDER BY);
      * batch methods: result order = input id order, None for missing;
      * filters: class_id equality, confidence >= threshold (inclusive);
      * pick_random_image/pick_random_track: same Python RNG over the same
        ordered id list, so a given seed picks the SAME entity as sqlite.
    Verified per-scenario by tests/test_parity_mot.py, which runs the whole
    M1-M6 parity suite once per backend rather than trusting this docstring.

    SQL logging (A2) does not apply -- there is no SQL; A2 tests run on the
    sqlite backend only.
    """

    def __init__(self, db_path: str):
        super().__init__(db_path)
        src = sqlite3.connect(db_path)
        src.execute("PRAGMA query_only = 1")
        src.row_factory = sqlite3.Row

        class_names = {r["id"]: r["name"] for r in src.execute("SELECT id, name FROM class")}
        seq_names = {r["id"]: r["name"] for r in src.execute("SELECT id, name FROM sequence")}

        self._images: dict = {}
        for r in src.execute(
            "SELECT id, sequence_id, frame_index, width, height, density_tier FROM image"
        ):
            self._images[r["id"]] = {
                "id": r["id"], "frame_index": r["frame_index"],
                "width": r["width"], "height": r["height"],
                "density_tier": r["density_tier"],
                "sequence_name": seq_names[r["sequence_id"]],
            }

        self._tracks: dict = {}
        for r in src.execute(
            "SELECT id, sequence_id, local_track_id, class_id, first_frame, last_frame FROM track"
        ):
            self._tracks[r["id"]] = {
                "id": r["id"], "sequence_id": r["sequence_id"],
                "local_track_id": r["local_track_id"], "class_id": r["class_id"],
                "first_frame": r["first_frame"], "last_frame": r["last_frame"],
                "class_name": class_names[r["class_id"]],
            }

        self._dets_by_image: dict = {}
        self._dets_by_track: dict = {}
        self._track_det_count: dict = {}
        for r in src.execute(
            """SELECT id, image_id, track_id, class_id, confidence,
                      bbox_x, bbox_y, bbox_w, bbox_h FROM detection ORDER BY id"""
        ):
            d = dict(r)
            self._dets_by_image.setdefault(d["image_id"], []).append(d)
            if d["track_id"] is not None:
                self._dets_by_track.setdefault(d["track_id"], []).append(d)
                self._track_det_count[d["track_id"]] = self._track_det_count.get(d["track_id"], 0) + 1
        # Trajectory lookups need frame_index; precompute (frame_index, point)
        # per track sorted by frame_index -- same ORDER BY as the SQL path.
        self._traj_by_track: dict = {}
        for tid, dets in self._dets_by_track.items():
            pts = [
                (self._images[d["image_id"]]["frame_index"], {
                    "id": d["id"], "image_id": d["image_id"],
                    "frame_index": self._images[d["image_id"]]["frame_index"],
                    "confidence": d["confidence"], "bbox_x": d["bbox_x"],
                    "bbox_y": d["bbox_y"], "bbox_w": d["bbox_w"], "bbox_h": d["bbox_h"],
                })
                for d in dets
            ]
            pts.sort(key=lambda fp: fp[0])
            self._traj_by_track[tid] = pts
        self._image_ids_by_tier: dict = {}
        for img in self._images.values():
            self._image_ids_by_tier.setdefault(img["density_tier"], []).append(img["id"])
        for ids in self._image_ids_by_tier.values():
            ids.sort()
        src.close()

    # -- images ---------------------------------------------------------------
    def get_image(self, image_id: int) -> Optional[dict]:
        img = self._images.get(image_id)
        return dict(img) if img else None

    def get_image_with_detections(
        self, image_id: int,
        class_id: Optional[int] = None, min_confidence: Optional[float] = None,
    ) -> Optional[dict]:
        img = self.get_image(image_id)
        if img is None:
            return None
        dets = self._dets_by_image.get(image_id, [])
        if class_id is not None:
            dets = [d for d in dets if d["class_id"] == class_id]
        if min_confidence is not None:
            dets = [d for d in dets if d["confidence"] >= min_confidence]
        img["detections"] = [
            {k: d[k] for k in ("id", "track_id", "class_id", "confidence",
                                "bbox_x", "bbox_y", "bbox_w", "bbox_h")}
            for d in dets
        ]
        return img

    def get_images_with_detections(self, image_ids: List[int]) -> List[Optional[dict]]:
        out = []
        for iid in image_ids:
            img = self.get_image(iid)
            if img is not None:
                img["detections"] = [dict(d) for d in self._dets_by_image.get(iid, [])]
            out.append(img)
        return out

    def pick_random_image(self, density_tier: str, seed: Optional[int] = None) -> Optional[dict]:
        ids = self._image_ids_by_tier.get(density_tier, [])
        if not ids:
            return None
        rng = random.Random(seed) if seed is not None else random
        return self.get_image(rng.choice(ids))

    # -- tracks ---------------------------------------------------------------
    def get_track(self, track_id: int) -> Optional[dict]:
        t = self._tracks.get(track_id)
        return dict(t) if t else None

    def get_tracks(self, track_ids: List[int]) -> List[Optional[dict]]:
        return [self.get_track(tid) for tid in track_ids]

    def get_track_trajectory(
        self, track_id: int, center_frame: Optional[int] = None,
        window: int = DEFAULT_TRAJECTORY_WINDOW,
    ) -> Optional[dict]:
        track = self.get_track(track_id)
        if track is None:
            return None
        center = center_frame if center_frame is not None else track["first_frame"]
        lo, hi = center - window, center + window
        track["trajectory"] = [
            dict(p) for f, p in self._traj_by_track.get(track_id, []) if lo <= f <= hi
        ]
        return track

    def list_eligible_track_ids(self, window: int) -> List[int]:
        need = eligible_point_count(window)
        return sorted(tid for tid, n in self._track_det_count.items() if n >= need)

    def get_tracks_with_trajectories(
        self, track_ids: List[int], window: int = DEFAULT_TRAJECTORY_WINDOW,
    ) -> List[Optional[dict]]:
        return [
            self.get_track_trajectory(tid, window=window) if tid in self._tracks else None
            for tid in track_ids
        ]

    # -- misc -----------------------------------------------------------------
    def summary(self) -> dict:
        return {
            "sequence": len({t["sequence_id"] for t in self._tracks.values()}),
            "image": len(self._images),
            "track": len(self._tracks),
            "detection": sum(len(v) for v in self._dets_by_image.values()),
            "backend": "memory",
        }
