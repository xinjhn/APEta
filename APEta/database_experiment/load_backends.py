#!/usr/bin/env python3
"""Load the canonical SQLite MOT corpus into query-native MongoDB/Neo4j models."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Iterable, Iterator


HERE = Path(__file__).resolve().parent
DEFAULT_DB = HERE.parents[1] / "training" / "mot_detections.db"


def chunks(rows: Iterable[dict], size: int) -> Iterator[list[dict]]:
    batch: list[dict] = []
    for row in rows:
        batch.append(row)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def source(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=1")
    return conn


def load_mongodb(path: Path, uri: str, database: str, batch_size: int) -> None:
    try:
        from pymongo import MongoClient
        from pymongo.server_api import ServerApi
    except ImportError as exc:
        raise SystemExit("Install requirements.txt first") from exc

    src = source(path)
    client = MongoClient(uri, server_api=ServerApi("1"), serverSelectionTimeoutMS=10000)
    client.admin.command("ping")
    db = client[database]
    db.images.drop()
    db.tracks.drop()

    seq_names = {row["id"]: row["name"] for row in src.execute("SELECT id,name FROM sequence")}
    dets_by_image: dict[int, list[dict]] = {}
    trajectory_by_track: dict[int, list[dict]] = {}
    for row in src.execute(
        """SELECT d.id,d.image_id,d.track_id,d.class_id,d.confidence,
                  d.bbox_x,d.bbox_y,d.bbox_w,d.bbox_h,i.frame_index
           FROM detection d JOIN image i ON i.id=d.image_id ORDER BY d.id"""
    ):
        dets_by_image.setdefault(row["image_id"], []).append({
            "id": row["id"], "track_id": row["track_id"], "class_id": row["class_id"],
            "confidence": row["confidence"], "bbox_x": row["bbox_x"],
            "bbox_y": row["bbox_y"], "bbox_w": row["bbox_w"], "bbox_h": row["bbox_h"],
        })
        if row["track_id"] is not None:
            trajectory_by_track.setdefault(row["track_id"], []).append({
                "id": row["id"], "image_id": row["image_id"],
                "frame_index": row["frame_index"], "confidence": row["confidence"],
                "bbox_x": row["bbox_x"], "bbox_y": row["bbox_y"],
                "bbox_w": row["bbox_w"], "bbox_h": row["bbox_h"],
            })

    images = (
        {
            "_id": row["id"], "id": row["id"], "frame_index": row["frame_index"],
            "width": row["width"], "height": row["height"],
            "density_tier": row["density_tier"],
            "sequence_name": seq_names[row["sequence_id"]],
            "detections": dets_by_image.get(row["id"], []),
        }
        for row in src.execute("SELECT * FROM image ORDER BY id")
    )
    for batch in chunks(images, batch_size):
        db.images.insert_many(batch, ordered=True)

    class_names = {row["id"]: row["name"] for row in src.execute("SELECT id,name FROM class")}
    tracks = (
        {
            "_id": row["id"], "id": row["id"], "sequence_id": row["sequence_id"],
            "local_track_id": row["local_track_id"], "class_id": row["class_id"],
            "first_frame": row["first_frame"], "last_frame": row["last_frame"],
            "class_name": class_names[row["class_id"]],
            "trajectory": trajectory_by_track.get(row["id"], []),
        }
        for row in src.execute("SELECT * FROM track ORDER BY id")
    )
    for batch in chunks(tracks, batch_size):
        db.tracks.insert_many(batch, ordered=True)

    # _id indexes cover point lookups and $in page lookups. This secondary
    # index supports the declared density-stratified access pattern.
    db.images.create_index("density_tier", name="idx_image_tier")
    print(f"[mongodb] images={db.images.count_documents({})} tracks={db.tracks.count_documents({})}")
    src.close()
    client.close()


def load_neo4j(path: Path, uri: str, user: str, password: str,
               database: str, batch_size: int) -> None:
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise SystemExit("Install requirements.txt first") from exc

    src = source(path)
    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()

    def run(query: str, rows: list[dict] | None = None) -> None:
        driver.execute_query(query, parameters_={"rows": rows or []}, database_=database)

    run("MATCH (n) DETACH DELETE n")
    for label in ("Sequence", "Image", "Track", "Detection", "Class"):
        run(f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE")
    run("CREATE INDEX image_density IF NOT EXISTS FOR (n:Image) ON (n.density_tier)")
    run("CALL db.awaitIndexes(300)")

    for table, label in (("class", "Class"), ("sequence", "Sequence")):
        rows = [dict(row) for row in src.execute(f"SELECT * FROM {table} ORDER BY id")]
        run(f"UNWIND $rows AS row CREATE (n:{label}) SET n += row", rows)

    image_rows = (dict(row) for row in src.execute("SELECT * FROM image ORDER BY id"))
    for batch in chunks(image_rows, batch_size):
        run(
            """UNWIND $rows AS row
               MATCH (s:Sequence {id:row.sequence_id})
               CREATE (i:Image) SET i += row
               CREATE (s)-[:HAS_IMAGE]->(i)""",
            batch,
        )

    track_rows = (dict(row) for row in src.execute("SELECT * FROM track ORDER BY id"))
    for batch in chunks(track_rows, batch_size):
        run(
            """UNWIND $rows AS row
               MATCH (s:Sequence {id:row.sequence_id}), (c:Class {id:row.class_id})
               CREATE (t:Track) SET t += row
               CREATE (s)-[:HAS_TRACK]->(t)
               CREATE (t)-[:OF_CLASS]->(c)""",
            batch,
        )

    det_sql = """SELECT id,image_id,track_id,class_id,confidence,
                        bbox_x,bbox_y,bbox_w,bbox_h
                 FROM detection ORDER BY id"""
    for batch in chunks((dict(row) for row in src.execute(det_sql)), batch_size):
        run(
            """UNWIND $rows AS row
               MATCH (i:Image {id:row.image_id}), (c:Class {id:row.class_id})
               CREATE (d:Detection) SET d += row
               CREATE (i)-[:HAS_DETECTION]->(d)
               CREATE (d)-[:OF_CLASS]->(c)""",
            batch,
        )
    tracked_sql = "SELECT id,track_id FROM detection WHERE track_id IS NOT NULL ORDER BY id"
    for batch in chunks((dict(row) for row in src.execute(tracked_sql)), batch_size):
        run(
            """UNWIND $rows AS row
               MATCH (t:Track {id:row.track_id}), (d:Detection {id:row.id})
               CREATE (t)-[:HAS_POINT]->(d)""",
            batch,
        )

    records, _, _ = driver.execute_query(
        """MATCH (i:Image) WITH count(i) AS images
           MATCH (t:Track) WITH images,count(t) AS tracks
           MATCH (d:Detection) RETURN images,tracks,count(d) AS detections""",
        database_=database,
    )
    print(f"[neo4j] {dict(records[0])}")
    src.close()
    driver.close()


def load_postgresql(path: Path, dsn: str) -> None:
    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit("Install requirements.txt first") from exc

    src = source(path)
    conn = psycopg.connect(dsn)
    schema = """
    DROP TABLE IF EXISTS detection, image, track, sequence, class CASCADE;
    CREATE TABLE class (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE
    );
    CREATE TABLE sequence (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        n_frames INTEGER NOT NULL
    );
    CREATE TABLE track (
        id INTEGER PRIMARY KEY,
        sequence_id INTEGER NOT NULL REFERENCES sequence(id),
        local_track_id INTEGER NOT NULL,
        class_id INTEGER NOT NULL REFERENCES class(id),
        first_frame INTEGER NOT NULL,
        last_frame INTEGER NOT NULL,
        UNIQUE(sequence_id, local_track_id)
    );
    CREATE TABLE image (
        id INTEGER PRIMARY KEY,
        sequence_id INTEGER NOT NULL REFERENCES sequence(id),
        frame_index INTEGER NOT NULL,
        width INTEGER NOT NULL,
        height INTEGER NOT NULL,
        density_tier TEXT NOT NULL,
        density_count_conf25 INTEGER NOT NULL,
        UNIQUE(sequence_id, frame_index)
    );
    CREATE TABLE detection (
        id INTEGER PRIMARY KEY,
        image_id INTEGER NOT NULL REFERENCES image(id),
        track_id INTEGER REFERENCES track(id),
        class_id INTEGER NOT NULL REFERENCES class(id),
        confidence DOUBLE PRECISION NOT NULL,
        bbox_x DOUBLE PRECISION NOT NULL,
        bbox_y DOUBLE PRECISION NOT NULL,
        bbox_w DOUBLE PRECISION NOT NULL,
        bbox_h DOUBLE PRECISION NOT NULL
    );
    CREATE INDEX idx_image_sequence ON image(sequence_id, frame_index);
    CREATE INDEX idx_image_tier ON image(density_tier);
    CREATE INDEX idx_detection_image ON detection(image_id);
    CREATE INDEX idx_detection_track ON detection(track_id);
    CREATE INDEX idx_track_sequence ON track(sequence_id, local_track_id);
    """
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")
        cur.execute(schema)
        tables = (
            ("class", ("id", "name")),
            ("sequence", ("id", "name", "n_frames")),
            (
                "track",
                ("id", "sequence_id", "local_track_id", "class_id", "first_frame", "last_frame"),
            ),
            (
                "image",
                ("id", "sequence_id", "frame_index", "width", "height",
                 "density_tier", "density_count_conf25"),
            ),
            (
                "detection",
                ("id", "image_id", "track_id", "class_id", "confidence",
                 "bbox_x", "bbox_y", "bbox_w", "bbox_h"),
            ),
        )
        for table, columns in tables:
            column_sql = ",".join(columns)
            select_sql = f"SELECT {column_sql} FROM {table} ORDER BY id"
            with cur.copy(f"COPY {table} ({column_sql}) FROM STDIN") as copy:
                for row in src.execute(select_sql):
                    copy.write_row(tuple(row[column] for column in columns))
        cur.execute("ANALYZE")
        cur.execute(
            """SELECT
                 (SELECT count(*) FROM image) AS images,
                 (SELECT count(*) FROM track) AS tracks,
                 (SELECT count(*) FROM detection) AS detections"""
        )
        counts = cur.fetchone()
    conn.commit()
    print(f"[postgresql] images={counts[0]} tracks={counts[1]} detections={counts[2]}")
    src.close()
    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_DB)
    parser.add_argument(
        "--backend", choices=("mongodb", "neo4j", "postgresql", "all"), default="all"
    )
    parser.add_argument("--mongo-uri", default="mongodb://127.0.0.1:27018")
    parser.add_argument("--mongo-database", default="ape_db_experiment")
    parser.add_argument("--neo4j-uri", default="bolt://127.0.0.1:7688")
    parser.add_argument("--neo4j-user", default="neo4j")
    parser.add_argument("--neo4j-password", default="ape-experiment")
    parser.add_argument("--neo4j-database", default="neo4j")
    parser.add_argument(
        "--postgres-dsn",
        default="postgresql://ape:ape-experiment@127.0.0.1:5433/ape_db_experiment",
    )
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args()
    if args.backend in ("mongodb", "all"):
        load_mongodb(args.source, args.mongo_uri, args.mongo_database, args.batch_size)
    if args.backend in ("neo4j", "all"):
        load_neo4j(
            args.source, args.neo4j_uri, args.neo4j_user, args.neo4j_password,
            args.neo4j_database, args.batch_size,
        )
    if args.backend in ("postgresql", "all"):
        load_postgresql(args.source, args.postgres_dsn)


if __name__ == "__main__":
    main()
