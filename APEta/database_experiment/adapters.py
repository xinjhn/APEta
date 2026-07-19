from __future__ import annotations

import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Iterable

from .common import DETECTION_FIELDS, IMAGE_FIELDS, TRACK_FIELDS, TRAJECTORY_FIELDS


class Backend(ABC):
    name: str

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def version(self) -> str: ...

    @abstractmethod
    def image_detections(self, image_id: int) -> dict | None: ...

    @abstractmethod
    def filtered_detections(
        self, image_id: int, class_id: int, min_confidence: float
    ) -> dict | None: ...

    @abstractmethod
    def class_counts(self, image_id: int) -> dict | None: ...

    @abstractmethod
    def trajectory(self, track_id: int, window: int) -> dict | None: ...

    @abstractmethod
    def trajectories(self, track_ids: list[int], window: int) -> list[dict | None]: ...

    def execute(self, case: dict) -> Any:
        op = case["operation"]
        if op == "image_detections":
            return self.image_detections(case["image_id"])
        if op == "filtered_detections":
            return self.filtered_detections(
                case["image_id"], case["class_id"], case["min_confidence"]
            )
        if op == "class_counts":
            return self.class_counts(case["image_id"])
        if op == "trajectory":
            return self.trajectory(case["track_id"], case["window"])
        if op == "trajectories":
            return self.trajectories(case["track_ids"], case["window"])
        raise ValueError(f"unknown operation: {op}")


def _dict(row: Any, fields: Iterable[str]) -> dict:
    return {field: row[field] for field in fields}


class SQLiteBackend(Backend):
    name = "sqlite"

    def __init__(self, path: Path):
        self.path = path.resolve()
        self.conn = sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA query_only=1")

    def close(self) -> None:
        self.conn.close()

    def version(self) -> str:
        return self.conn.execute("SELECT sqlite_version()").fetchone()[0]

    def _image(self, image_id: int) -> dict | None:
        row = self.conn.execute(
            """SELECT image.id, image.frame_index, image.width, image.height,
                      image.density_tier, sequence.name AS sequence_name
               FROM image JOIN sequence ON sequence.id=image.sequence_id
               WHERE image.id=?""",
            (image_id,),
        ).fetchone()
        return _dict(row, IMAGE_FIELDS) if row else None

    def image_detections(self, image_id: int) -> dict | None:
        image = self._image(image_id)
        if image is None:
            return None
        rows = self.conn.execute(
            """SELECT id, track_id, class_id, confidence,
                      bbox_x, bbox_y, bbox_w, bbox_h
               FROM detection WHERE image_id=? ORDER BY id""",
            (image_id,),
        )
        image["detections"] = [_dict(row, DETECTION_FIELDS) for row in rows]
        return image

    def filtered_detections(
        self, image_id: int, class_id: int, min_confidence: float
    ) -> dict | None:
        image = self._image(image_id)
        if image is None:
            return None
        rows = self.conn.execute(
            """SELECT id, track_id, class_id, confidence,
                      bbox_x, bbox_y, bbox_w, bbox_h
               FROM detection
               WHERE image_id=? AND class_id=? AND confidence>=?
               ORDER BY id""",
            (image_id, class_id, min_confidence),
        )
        image["detections"] = [_dict(row, DETECTION_FIELDS) for row in rows]
        return image

    def class_counts(self, image_id: int) -> dict | None:
        rows = list(self.conn.execute(
            """SELECT class_id, COUNT(*) AS count FROM detection
               WHERE image_id=? GROUP BY class_id ORDER BY class_id""",
            (image_id,),
        ))
        # Every image in this canonical corpus has >=1 detection. Thus an empty
        # group means a missing id, without paying a second existence query.
        if not rows:
            return None
        return {
            "image_id": image_id,
            "class_counts": [
                {"class_id": row["class_id"], "count": row["count"]} for row in rows
            ],
        }

    def _track(self, track_id: int) -> dict | None:
        row = self.conn.execute(
            """SELECT track.id, track.sequence_id, track.local_track_id,
                      track.class_id, track.first_frame, track.last_frame,
                      class.name AS class_name
               FROM track JOIN class ON class.id=track.class_id
               WHERE track.id=?""",
            (track_id,),
        ).fetchone()
        return _dict(row, TRACK_FIELDS) if row else None

    def trajectory(self, track_id: int, window: int) -> dict | None:
        track = self._track(track_id)
        if track is None:
            return None
        rows = self.conn.execute(
            """SELECT detection.id, detection.image_id, image.frame_index,
                      detection.confidence, detection.bbox_x, detection.bbox_y,
                      detection.bbox_w, detection.bbox_h
               FROM detection JOIN image ON image.id=detection.image_id
               WHERE detection.track_id=?
                 AND image.frame_index BETWEEN ? AND ?
               ORDER BY image.frame_index, detection.id""",
            (track_id, track["first_frame"] - window, track["first_frame"] + window),
        )
        track["trajectory"] = [_dict(row, TRAJECTORY_FIELDS) for row in rows]
        return track

    def trajectories(self, track_ids: list[int], window: int) -> list[dict | None]:
        if not track_ids:
            return []
        placeholders = ",".join("?" for _ in track_ids)
        rows = self.conn.execute(
            f"""SELECT track.id, track.sequence_id, track.local_track_id,
                       track.class_id, track.first_frame, track.last_frame,
                       class.name AS class_name
                FROM track JOIN class ON class.id=track.class_id
                WHERE track.id IN ({placeholders})""",
            tuple(track_ids),
        )
        by_id = {_row["id"]: _dict(_row, TRACK_FIELDS) for _row in rows}
        for track in by_id.values():
            track["trajectory"] = []
        if by_id:
            found_placeholders = ",".join("?" for _ in by_id)
            points = self.conn.execute(
                f"""SELECT detection.track_id, detection.id, detection.image_id,
                           image.frame_index, detection.confidence,
                           detection.bbox_x, detection.bbox_y,
                           detection.bbox_w, detection.bbox_h
                    FROM detection
                    JOIN image ON image.id=detection.image_id
                    JOIN track ON track.id=detection.track_id
                    WHERE detection.track_id IN ({found_placeholders})
                      AND image.frame_index >= track.first_frame-?
                      AND image.frame_index <= track.first_frame+?
                    ORDER BY detection.track_id, image.frame_index, detection.id""",
                tuple(by_id) + (window, window),
            )
            for point in points:
                by_id[point["track_id"]]["trajectory"].append(
                    _dict(point, TRAJECTORY_FIELDS)
                )
        return [by_id.get(track_id) for track_id in track_ids]


class MongoBackend(Backend):
    name = "mongodb"

    def __init__(self, uri: str, database: str = "ape_db_experiment"):
        try:
            from pymongo import MongoClient
            from pymongo.server_api import ServerApi
        except ImportError as exc:
            raise RuntimeError("Install database_experiment/requirements.txt") from exc
        self.client = MongoClient(uri, server_api=ServerApi("1"), serverSelectionTimeoutMS=5000)
        self.client.admin.command("ping")
        self.db = self.client[database]

    def close(self) -> None:
        self.client.close()

    def version(self) -> str:
        return self.client.server_info()["version"]

    @staticmethod
    def _clean(document: dict | None, fields: Iterable[str]) -> dict | None:
        if document is None:
            return None
        return {field: document[field] for field in fields}

    def image_detections(self, image_id: int) -> dict | None:
        doc = self.db.images.find_one({"_id": image_id})
        if doc is None:
            return None
        out = self._clean(doc, IMAGE_FIELDS)
        out["detections"] = [
            {field: det.get(field) for field in DETECTION_FIELDS}
            for det in doc.get("detections", [])
        ]
        return out

    def filtered_detections(
        self, image_id: int, class_id: int, min_confidence: float
    ) -> dict | None:
        # $filter keeps this server-side; the client never fetches then discards.
        rows = list(self.db.images.aggregate([
            {"$match": {"_id": image_id}},
            {"$project": {
                **{field: 1 for field in IMAGE_FIELDS},
                "detections": {"$filter": {
                    "input": "$detections", "as": "d",
                    "cond": {"$and": [
                        {"$eq": ["$$d.class_id", class_id]},
                        {"$gte": ["$$d.confidence", min_confidence]},
                    ]},
                }},
            }},
        ]))
        if not rows:
            return None
        doc = rows[0]
        out = self._clean(doc, IMAGE_FIELDS)
        out["detections"] = [
            {field: det.get(field) for field in DETECTION_FIELDS}
            for det in doc.get("detections", [])
        ]
        return out

    def class_counts(self, image_id: int) -> dict | None:
        rows = list(self.db.images.aggregate([
            {"$match": {"_id": image_id}},
            {"$unwind": "$detections"},
            {"$group": {"_id": "$detections.class_id", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ]))
        if not rows:
            return None
        return {
            "image_id": image_id,
            "class_counts": [
                {"class_id": row["_id"], "count": row["count"]} for row in rows
            ],
        }

    def trajectory(self, track_id: int, window: int) -> dict | None:
        rows = list(self.db.tracks.aggregate([
            {"$match": {"_id": track_id}},
            {"$project": {
                **{field: 1 for field in TRACK_FIELDS},
                "trajectory": {"$filter": {
                    "input": "$trajectory", "as": "p",
                    "cond": {"$and": [
                        {"$gte": ["$$p.frame_index", {"$subtract": ["$first_frame", window]}]},
                        {"$lte": ["$$p.frame_index", {"$add": ["$first_frame", window]}]},
                    ]},
                }},
            }},
        ]))
        if not rows:
            return None
        doc = rows[0]
        out = self._clean(doc, TRACK_FIELDS)
        out["trajectory"] = [
            {field: point.get(field) for field in TRAJECTORY_FIELDS}
            for point in doc.get("trajectory", [])
        ]
        return out

    def trajectories(self, track_ids: list[int], window: int) -> list[dict | None]:
        cursor = self.db.tracks.aggregate([
            {"$match": {"_id": {"$in": track_ids}}},
            {"$project": {
                **{field: 1 for field in TRACK_FIELDS},
                "trajectory": {"$filter": {
                    "input": "$trajectory", "as": "p",
                    "cond": {"$and": [
                        {"$gte": ["$$p.frame_index", {"$subtract": ["$first_frame", window]}]},
                        {"$lte": ["$$p.frame_index", {"$add": ["$first_frame", window]}]},
                    ]},
                }},
            }},
        ])
        docs = {doc["_id"]: doc for doc in cursor}
        out: list[dict | None] = []
        for track_id in track_ids:
            doc = docs.get(track_id)
            if doc is None:
                out.append(None)
                continue
            track = self._clean(doc, TRACK_FIELDS)
            track["trajectory"] = [
                {field: point.get(field) for field in TRAJECTORY_FIELDS}
                for point in doc.get("trajectory", [])
            ]
            out.append(track)
        return out


class Neo4jBackend(Backend):
    name = "neo4j"

    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j"):
        try:
            from neo4j import GraphDatabase
        except ImportError as exc:
            raise RuntimeError("Install database_experiment/requirements.txt") from exc
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.driver.verify_connectivity()
        self.database = database

    def close(self) -> None:
        self.driver.close()

    def version(self) -> str:
        rows, _, _ = self.driver.execute_query(
            "CALL dbms.components() YIELD versions RETURN versions[0] AS version",
            database_=self.database,
        )
        return rows[0]["version"]

    def _one(self, query: str, **params: Any) -> dict | None:
        rows, _, _ = self.driver.execute_query(query, parameters_=params, database_=self.database)
        return dict(rows[0]) if rows else None

    def image_detections(self, image_id: int) -> dict | None:
        row = self._one(
            """MATCH (s:Sequence)-[:HAS_IMAGE]->(i:Image {id:$image_id})
               OPTIONAL MATCH (i)-[:HAS_DETECTION]->(d:Detection)
               WITH s, i, d ORDER BY d.id
               WITH s, i, collect(CASE WHEN d IS NULL THEN null ELSE
                    d{.id,.track_id,.class_id,.confidence,.bbox_x,.bbox_y,.bbox_w,.bbox_h}
                    END) AS detections
               RETURN i{.id,.frame_index,.width,.height,.density_tier,
                        sequence_name:s.name,
                        detections:[x IN detections WHERE x IS NOT NULL]} AS result""",
            image_id=image_id,
        )
        if row is None:
            return None
        result = row["result"]
        result["detections"] = [d for d in result["detections"] if d is not None]
        return result

    def filtered_detections(
        self, image_id: int, class_id: int, min_confidence: float
    ) -> dict | None:
        row = self._one(
            """MATCH (s:Sequence)-[:HAS_IMAGE]->(i:Image {id:$image_id})
               OPTIONAL MATCH (i)-[:HAS_DETECTION]->(d:Detection)
               WHERE d.class_id=$class_id AND d.confidence >= $min_confidence
               WITH s, i, d ORDER BY d.id
               WITH s, i, collect(CASE WHEN d IS NULL THEN null ELSE
                    d{.id,.track_id,.class_id,.confidence,.bbox_x,.bbox_y,.bbox_w,.bbox_h}
                    END) AS detections
               RETURN i{.id,.frame_index,.width,.height,.density_tier,
                        sequence_name:s.name,
                        detections:[x IN detections WHERE x IS NOT NULL]} AS result""",
            image_id=image_id, class_id=class_id, min_confidence=min_confidence,
        )
        if row is None:
            return None
        result = row["result"]
        result["detections"] = [d for d in result["detections"] if d is not None]
        return result

    def class_counts(self, image_id: int) -> dict | None:
        row = self._one(
            """MATCH (i:Image {id:$image_id})
               OPTIONAL MATCH (i)-[:HAS_DETECTION]->(d:Detection)
               WITH i, d.class_id AS class_id, count(d) AS count ORDER BY class_id
               WITH i, collect(CASE WHEN class_id IS NULL THEN null ELSE
                    {class_id:class_id, count:count} END) AS counts
               RETURN {image_id:i.id, class_counts:[x IN counts WHERE x IS NOT NULL]} AS result""",
            image_id=image_id,
        )
        return row["result"] if row else None

    def trajectory(self, track_id: int, window: int) -> dict | None:
        row = self._one(
            """MATCH (s:Sequence)-[:HAS_TRACK]->(t:Track {id:$track_id})-[:OF_CLASS]->(c:Class)
               OPTIONAL MATCH (t)-[:HAS_POINT]->(d:Detection)<-[:HAS_DETECTION]-(i:Image)
               WHERE i.frame_index >= t.first_frame-$window
                 AND i.frame_index <= t.first_frame+$window
               WITH s, t, c, d, i ORDER BY i.frame_index, d.id
               WITH s, t, c, collect(CASE WHEN d IS NULL THEN null ELSE
                    d{.id, image_id:i.id, frame_index:i.frame_index,
                      .confidence,.bbox_x,.bbox_y,.bbox_w,.bbox_h}
                    END) AS trajectory
               RETURN t{.id,.sequence_id,.local_track_id,.class_id,.first_frame,.last_frame,
                        class_name:c.name,
                        trajectory:[x IN trajectory WHERE x IS NOT NULL]} AS result""",
            track_id=track_id, window=window,
        )
        if row is None:
            return None
        result = row["result"]
        result["trajectory"] = [p for p in result["trajectory"] if p is not None]
        return result

    def trajectories(self, track_ids: list[int], window: int) -> list[dict | None]:
        rows, _, _ = self.driver.execute_query(
            """UNWIND range(0, size($track_ids)-1) AS pos
               WITH pos, $track_ids[pos] AS track_id
               OPTIONAL MATCH (s:Sequence)-[:HAS_TRACK]->(t:Track {id:track_id})-[:OF_CLASS]->(c:Class)
               OPTIONAL MATCH (t)-[:HAS_POINT]->(d:Detection)<-[:HAS_DETECTION]-(i:Image)
               WHERE i.frame_index >= t.first_frame-$window
                 AND i.frame_index <= t.first_frame+$window
               WITH pos, track_id, s, t, c, d, i ORDER BY pos, i.frame_index, d.id
               WITH pos, track_id, s, t, c,
                    collect(CASE WHEN d IS NULL THEN null ELSE
                      d{.id, image_id:i.id, frame_index:i.frame_index,
                        .confidence,.bbox_x,.bbox_y,.bbox_w,.bbox_h} END) AS trajectory
               RETURN pos, CASE WHEN t IS NULL THEN null ELSE
                 t{.id,.sequence_id,.local_track_id,.class_id,.first_frame,.last_frame,
                   class_name:c.name,
                   trajectory:[x IN trajectory WHERE x IS NOT NULL]}
                 END AS result ORDER BY pos""",
            parameters_={"track_ids": track_ids, "window": window},
            database_=self.database,
        )
        return [row["result"] for row in rows]


class PostgreSQLBackend(Backend):
    name = "postgresql"

    def __init__(self, dsn: str):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("Install database_experiment/requirements.txt") from exc
        self.conn = psycopg.connect(dsn, autocommit=True, row_factory=dict_row)

    def close(self) -> None:
        self.conn.close()

    def version(self) -> str:
        with self.conn.cursor() as cur:
            cur.execute("SHOW server_version")
            return cur.fetchone()["server_version"]

    def _image(self, image_id: int) -> dict | None:
        with self.conn.cursor() as cur:
            cur.execute(
                """/* ape:image_envelope */
                   SELECT image.id, image.frame_index, image.width, image.height,
                          image.density_tier, sequence.name AS sequence_name
                   FROM image JOIN sequence ON sequence.id=image.sequence_id
                   WHERE image.id=%s""",
                (image_id,),
            )
            row = cur.fetchone()
        return _dict(row, IMAGE_FIELDS) if row else None

    def image_detections(self, image_id: int) -> dict | None:
        image = self._image(image_id)
        if image is None:
            return None
        with self.conn.cursor() as cur:
            cur.execute(
                """/* ape:image_detections */
                   SELECT id, track_id, class_id, confidence,
                          bbox_x, bbox_y, bbox_w, bbox_h
                   FROM detection WHERE image_id=%s ORDER BY id""",
                (image_id,),
            )
            image["detections"] = [_dict(row, DETECTION_FIELDS) for row in cur]
        return image

    def filtered_detections(
        self, image_id: int, class_id: int, min_confidence: float
    ) -> dict | None:
        image = self._image(image_id)
        if image is None:
            return None
        with self.conn.cursor() as cur:
            cur.execute(
                """/* ape:filtered_detections */
                   SELECT id, track_id, class_id, confidence,
                          bbox_x, bbox_y, bbox_w, bbox_h
                   FROM detection
                   WHERE image_id=%s AND class_id=%s AND confidence>=%s
                   ORDER BY id""",
                (image_id, class_id, min_confidence),
            )
            image["detections"] = [_dict(row, DETECTION_FIELDS) for row in cur]
        return image

    def class_counts(self, image_id: int) -> dict | None:
        with self.conn.cursor() as cur:
            cur.execute(
                """/* ape:class_counts */
                   SELECT class_id, COUNT(*) AS count FROM detection
                   WHERE image_id=%s GROUP BY class_id ORDER BY class_id""",
                (image_id,),
            )
            rows = list(cur)
        if not rows:
            return None
        return {
            "image_id": image_id,
            "class_counts": [
                {"class_id": row["class_id"], "count": row["count"]} for row in rows
            ],
        }

    def _track(self, track_id: int) -> dict | None:
        with self.conn.cursor() as cur:
            cur.execute(
                """/* ape:track_envelope */
                   SELECT track.id, track.sequence_id, track.local_track_id,
                          track.class_id, track.first_frame, track.last_frame,
                          class.name AS class_name
                   FROM track JOIN class ON class.id=track.class_id
                   WHERE track.id=%s""",
                (track_id,),
            )
            row = cur.fetchone()
        return _dict(row, TRACK_FIELDS) if row else None

    def trajectory(self, track_id: int, window: int) -> dict | None:
        track = self._track(track_id)
        if track is None:
            return None
        with self.conn.cursor() as cur:
            cur.execute(
                """/* ape:trajectory */
                   SELECT detection.id, detection.image_id, image.frame_index,
                          detection.confidence, detection.bbox_x, detection.bbox_y,
                          detection.bbox_w, detection.bbox_h
                   FROM detection JOIN image ON image.id=detection.image_id
                   WHERE detection.track_id=%s
                     AND image.frame_index >= %s
                     AND image.frame_index <= %s
                   ORDER BY image.frame_index, detection.id""",
                (track_id, track["first_frame"] - window, track["first_frame"] + window),
            )
            track["trajectory"] = [_dict(row, TRAJECTORY_FIELDS) for row in cur]
        return track

    def trajectories(self, track_ids: list[int], window: int) -> list[dict | None]:
        if not track_ids:
            return []
        with self.conn.cursor() as cur:
            cur.execute(
                """/* ape:trajectories_tracks */
                   SELECT track.id, track.sequence_id, track.local_track_id,
                          track.class_id, track.first_frame, track.last_frame,
                          class.name AS class_name
                   FROM track JOIN class ON class.id=track.class_id
                   WHERE track.id=ANY(%s)""",
                (track_ids,),
            )
            by_id = {row["id"]: _dict(row, TRACK_FIELDS) for row in cur}
        for track in by_id.values():
            track["trajectory"] = []
        if by_id:
            with self.conn.cursor() as cur:
                cur.execute(
                    """/* ape:trajectories_points */
                       SELECT detection.track_id, detection.id, detection.image_id,
                              image.frame_index, detection.confidence,
                              detection.bbox_x, detection.bbox_y,
                              detection.bbox_w, detection.bbox_h
                       FROM detection
                       JOIN image ON image.id=detection.image_id
                       JOIN track ON track.id=detection.track_id
                       WHERE detection.track_id=ANY(%s)
                         AND image.frame_index >= track.first_frame-%s
                         AND image.frame_index <= track.first_frame+%s
                       ORDER BY detection.track_id, image.frame_index, detection.id""",
                    (list(by_id), window, window),
                )
                for point in cur:
                    by_id[point["track_id"]]["trajectory"].append(
                        _dict(point, TRAJECTORY_FIELDS)
                    )
        return [by_id.get(track_id) for track_id in track_ids]


def open_backend(name: str, *, sqlite_path: Path, mongo_uri: str,
                 neo4j_uri: str, neo4j_user: str, neo4j_password: str,
                 postgres_dsn: str) -> Backend:
    if name == "sqlite":
        return SQLiteBackend(sqlite_path)
    if name == "mongodb":
        return MongoBackend(mongo_uri)
    if name == "neo4j":
        return Neo4jBackend(neo4j_uri, neo4j_user, neo4j_password)
    if name == "postgresql":
        return PostgreSQLBackend(postgres_dsn)
    raise ValueError(f"backend must be sqlite|postgresql|mongodb|neo4j, got {name!r}")
