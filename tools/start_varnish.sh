#!/usr/bin/env bash
# tools/start_varnish.sh
# =======================
# Manual/test-time launcher for the Varnish cache layer (Phase 2a). Not
# orchestrator-wired yet (that's Phase 2c) -- used directly by
# tests/test_cache_fairness.py and for ad-hoc curl verification.
#
# Listens on :8080, backend is whatever's currently live on :8000 (REST or
# GraphQL, per the existing "run alternately" convention -- cache/varnish.vcl
# doesn't care which).
#
# Usage:
#   tools/start_varnish.sh start   # foreground-detached; prints PID
#   tools/start_varnish.sh stop
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VCL="$ROOT/cache/varnish.vcl"
WORKDIR="$ROOT/scratch/varnish-instance"
LISTEN="${APE_VARNISH_LISTEN:-127.0.0.1:8080}"
STORAGE_MB="${APE_VARNISH_STORAGE_MB:-64}"

case "${1:-start}" in
  start)
    mkdir -p "$WORKDIR"
    rm -rf "$WORKDIR"/*
    varnishd -n "$WORKDIR" -f "$VCL" -a "$LISTEN" \
      -s "malloc,${STORAGE_MB}m" -F &
    echo $! > "$WORKDIR.pid"
    echo "varnishd started, pid=$(cat "$WORKDIR.pid"), listening on $LISTEN" >&2
    ;;
  stop)
    if [ -f "$WORKDIR.pid" ]; then
      kill "$(cat "$WORKDIR.pid")" 2>/dev/null || true
      rm -f "$WORKDIR.pid"
    fi
    ;;
  *)
    echo "usage: $0 {start|stop}" >&2
    exit 1
    ;;
esac
