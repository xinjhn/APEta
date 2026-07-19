from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


DETECTION_FIELDS = (
    "id", "track_id", "class_id", "confidence",
    "bbox_x", "bbox_y", "bbox_w", "bbox_h",
)
TRAJECTORY_FIELDS = (
    "id", "image_id", "frame_index", "confidence",
    "bbox_x", "bbox_y", "bbox_w", "bbox_h",
)
IMAGE_FIELDS = (
    "id", "frame_index", "width", "height", "density_tier", "sequence_name",
)
TRACK_FIELDS = (
    "id", "sequence_id", "local_track_id", "class_id",
    "first_frame", "last_frame", "class_name",
)


def canonical_json(value: Any) -> str:
    """Stable representation used to prove cross-backend result parity."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def result_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
