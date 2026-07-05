"""
core/config.py
==============
Centralized constants for the new (Phase 1) REST-vs-GraphQL caching study.

Replaces the retired flat-image/4-pattern config from the prior "Path B"
experiment (see git history for that version). This study's unit of analysis
is the relational graph image -> detection -> track -> class built by
~/training/build_detection_db.py, not a flat in-memory JSON pool.
"""

DENSITY_TIERS = ("low", "medium", "high")

# Canonical field names -- identical on REST and GraphQL (snake_case, no
# auto-camelCase on the GraphQL side) so payload bytes are comparable without
# a naming-length confound.
DETECTION_FIELDS = ("class_id", "confidence", "bbox_x", "bbox_y", "bbox_w", "bbox_h")

PROCESS_TIME_HEADER = "X-Process-Time"

# Default trajectory window (frames before/after the queried frame) for
# Track.trajectory / /tracks/{id}/trajectory -- spec S7: bounded, not full
# track history, so density stays the controlled payload driver.
DEFAULT_TRAJECTORY_WINDOW = 5

DEFAULT_DB_PATH = "/home/ubuntu/training/mot_detections.db"
