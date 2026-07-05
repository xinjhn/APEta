#!/usr/bin/env python3
"""
build_detection_db.py
======================
Build the single relational SQLite store shared by both the REST and GraphQL
servers in ~/APE/APEta (N2: same DB, same access path, only the API surface
differs between arms).

Source: VisDrone-MOT tracked predictions written by infer_mot_track.py
(10-column VisDrone-MOT format: frame_index, target_id, bbox_left, bbox_top,
bbox_w, bbox_h, score, object_category, truncation, occlusion). Track IDs in
that format are only unique WITHIN a sequence file, so this script forms a
global track key as (sequence_name, target_id).

CORPUS DEFINITION (report verbatim in the writeup):
- Detection confidence stored: conf >= 0.001 (near-everything; threshold is a
  pure query-time knob, not baked into the corpus -- spec BUILD SPEC.md S0.4).
- Tracker: Ultralytics ByteTrack, track_high_thresh=0.5, iou=0.7 (the
  --track_conf/--iou defaults of infer_mot_track.py at generation time).
  These govern which boxes the TRACKER associates into tracks; they do not
  filter which boxes are STORED (all conf>=0.001 boxes are stored, tracked
  or not -- untracked boxes get track_id = NULL).
- Track->class rule (S0.5): majority vote of per-frame class_id over all
  detections sharing a track_id; ties broken by lowest class_id.
- Density tiering (image.density_tier): computed from per-image detection
  COUNT AT CONF>=0.25 (not the stored conf>=0.001 rows -- at conf=0.001
  virtually every image is "high density", which destroys the tiering signal).
  This mirrors the quartile thresholds already established in
  mot_predictions_tracked_density.csv. The 0.25 cut is a REPORTING/STRATIFICATION
  threshold only; query-time confidence filtering in the API is unaffected and
  still operates over the full conf>=0.001 stored set.

USAGE
-----
  python build_detection_db.py \
      --pred-dir mot_val_predictions_tracked_conf001 \
      --out mot_detections.db
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

CLASS_NAMES = {
    1: "pedestrian", 2: "people", 3: "bicycle", 4: "car", 5: "van",
    6: "truck", 7: "tricycle", 8: "awning-tricycle", 9: "bus", 10: "motor",
}

SCHEMA = """
CREATE TABLE class (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE sequence (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL UNIQUE,
    n_frames INTEGER NOT NULL
);

CREATE TABLE track (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence_id INTEGER NOT NULL REFERENCES sequence(id),
    local_track_id INTEGER NOT NULL,
    class_id    INTEGER NOT NULL REFERENCES class(id),
    first_frame INTEGER NOT NULL,
    last_frame  INTEGER NOT NULL,
    UNIQUE(sequence_id, local_track_id)
);

CREATE TABLE image (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence_id   INTEGER NOT NULL REFERENCES sequence(id),
    frame_index   INTEGER NOT NULL,
    width         INTEGER NOT NULL,
    height        INTEGER NOT NULL,
    density_tier  TEXT NOT NULL,
    density_count_conf25 INTEGER NOT NULL,
    UNIQUE(sequence_id, frame_index)
);

CREATE TABLE detection (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id    INTEGER NOT NULL REFERENCES image(id),
    track_id    INTEGER REFERENCES track(id),
    class_id    INTEGER NOT NULL REFERENCES class(id),
    confidence  REAL NOT NULL,
    bbox_x      REAL NOT NULL,
    bbox_y      REAL NOT NULL,
    bbox_w      REAL NOT NULL,
    bbox_h      REAL NOT NULL
);

CREATE INDEX idx_image_sequence ON image(sequence_id, frame_index);
CREATE INDEX idx_image_tier ON image(density_tier);
CREATE INDEX idx_detection_image ON detection(image_id);
CREATE INDEX idx_detection_track ON detection(track_id);
CREATE INDEX idx_track_sequence ON track(sequence_id, local_track_id);
"""

# VisDrone-MOT images for these 7 sequences are all 1920x1080 (confirm not
# hard-coded silently -- see --imgsz note below). If a sequence ever differs,
# pass real per-sequence dimensions via --dims-csv instead of this default.
DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080


def parse_mot_file(path: Path) -> List[Tuple[int, int, float, float, float, float, float, int]]:
    """Parse one VisDrone-MOT prediction file.

    Returns list of (frame_index, target_id, x, y, w, h, score, class_id).
    target_id == -1 means untracked (no tracker association at this conf).
    """
    rows = []
    with open(path, "r", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 8:
                continue
            frame = int(row[0])
            tid = int(row[1])
            x, y, w, h = float(row[2]), float(row[3]), float(row[4]), float(row[5])
            score = float(row[6])
            cls = int(row[7])
            rows.append((frame, tid, x, y, w, h, score, cls))
    return rows


def majority_class(class_ids: List[int]) -> int:
    """Majority vote; ties broken by lowest class_id (S0.5)."""
    counts = Counter(class_ids)
    best_count = max(counts.values())
    winners = sorted(c for c, n in counts.items() if n == best_count)
    return winners[0]


def quartile_tiers(counts: List[int]) -> Tuple[float, float]:
    q1, _med, q3 = statistics.quantiles(sorted(counts), n=4, method="inclusive")
    return q1, q3


def tier_for(count: int, q1: float, q3: float) -> str:
    if count < q1:
        return "low"
    if count > q3:
        return "high"
    return "medium"


def build(pred_dir: Path, out_path: Path, density_conf_cut: float = 0.25) -> None:
    seq_files = sorted(pred_dir.glob("*.txt"))
    if not seq_files:
        raise FileNotFoundError(f"No .txt prediction files found in {pred_dir}")

    if out_path.exists():
        out_path.unlink()

    conn = sqlite3.connect(out_path)
    conn.executescript(SCHEMA)

    conn.executemany(
        "INSERT INTO class (id, name) VALUES (?, ?)",
        list(CLASS_NAMES.items()),
    )

    # Pass 1: parse everything, compute per-image density-at-conf25 counts
    # globally (across all sequences) so tiers are corpus-wide, not per-sequence.
    per_seq_rows: Dict[str, List[Tuple]] = {}
    density_counts: Dict[Tuple[str, int], int] = {}
    for path in seq_files:
        seq_name = path.stem
        rows = parse_mot_file(path)
        per_seq_rows[seq_name] = rows
        per_frame_conf25 = defaultdict(int)
        for frame, tid, x, y, w, h, score, cls in rows:
            if score >= density_conf_cut:
                per_frame_conf25[frame] += 1
        for frame, count in per_frame_conf25.items():
            density_counts[(seq_name, frame)] = count

    all_counts = list(density_counts.values())
    q1, q3 = quartile_tiers(all_counts)
    print(f"[info] density-at-conf{density_conf_cut} quartiles: Q1={q1:.1f} Q3={q3:.1f} "
          f"over {len(all_counts)} images")

    # Pass 2: write sequence/image/track/detection rows.
    for path in seq_files:
        seq_name = path.stem
        rows = per_seq_rows[seq_name]
        frames_present = sorted({r[0] for r in rows})
        n_frames = max(frames_present) if frames_present else 0

        cur = conn.execute(
            "INSERT INTO sequence (name, n_frames) VALUES (?, ?)", (seq_name, n_frames)
        )
        seq_id = cur.lastrowid

        # image rows (every frame that has at least one row in the pred file)
        image_id_by_frame: Dict[int, int] = {}
        for frame in frames_present:
            count25 = density_counts.get((seq_name, frame), 0)
            tier = tier_for(count25, q1, q3)
            cur = conn.execute(
                """INSERT INTO image
                   (sequence_id, frame_index, width, height, density_tier, density_count_conf25)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (seq_id, frame, DEFAULT_WIDTH, DEFAULT_HEIGHT, tier, count25),
            )
            image_id_by_frame[frame] = cur.lastrowid

        # group detections by local_track_id (excluding -1 = untracked)
        by_track: Dict[int, List[Tuple]] = defaultdict(list)
        for r in rows:
            frame, tid, x, y, w, h, score, cls = r
            if tid is not None and tid >= 0:
                by_track[tid].append(r)

        track_db_id: Dict[int, int] = {}
        for local_tid, trows in by_track.items():
            class_id = majority_class([r[7] for r in trows])
            first_frame = min(r[0] for r in trows)
            last_frame = max(r[0] for r in trows)
            cur = conn.execute(
                """INSERT INTO track
                   (sequence_id, local_track_id, class_id, first_frame, last_frame)
                   VALUES (?, ?, ?, ?, ?)""",
                (seq_id, local_tid, class_id, first_frame, last_frame),
            )
            track_db_id[local_tid] = cur.lastrowid

        detection_rows = []
        for frame, tid, x, y, w, h, score, cls in rows:
            img_id = image_id_by_frame[frame]
            trk_id = track_db_id.get(tid) if (tid is not None and tid >= 0) else None
            detection_rows.append((img_id, trk_id, cls, score, x, y, w, h))

        conn.executemany(
            """INSERT INTO detection
               (image_id, track_id, class_id, confidence, bbox_x, bbox_y, bbox_w, bbox_h)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            detection_rows,
        )

        print(f"[info] {seq_name}: {len(frames_present)} images, "
              f"{len(detection_rows)} detections, {len(by_track)} tracks")

    conn.commit()

    # Sanity totals
    n_img = conn.execute("SELECT COUNT(*) FROM image").fetchone()[0]
    n_det = conn.execute("SELECT COUNT(*) FROM detection").fetchone()[0]
    n_trk = conn.execute("SELECT COUNT(*) FROM track").fetchone()[0]
    n_seq = conn.execute("SELECT COUNT(*) FROM sequence").fetchone()[0]
    print(f"[done] sequences={n_seq} images={n_img} detections={n_det} tracks={n_trk}")
    print(f"[done] wrote {out_path}")

    conn.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--density-conf-cut", type=float, default=0.25)
    args = ap.parse_args()
    build(args.pred_dir, args.out, args.density_conf_cut)


if __name__ == "__main__":
    main()
