"""
tests/test_cache_fairness.py
==============================
Acceptance criterion A3 (BUILD SPEC §5): with caching on, BOTH arms must
actually populate and serve from the cache layer -- not just carry the right
headers in isolation, but be PROVEN to MISS then HIT through a real Varnish
instance sitting in front of a real server subprocess.

This needs real TCP (Varnish has to fetch from an actual backend port), so
unlike tests/test_parity.py it can't run in-process via TestClient. It also
needs `varnishd` installed and is comparatively slow (subprocess startup),
so it's gated behind APE_RUN_CACHE_TESTS=1 -- Phase 1's fast tests stay fast
by default.

Run:
    APE_RUN_CACHE_TESTS=1 APE_DB_PATH=/home/ubuntu/training/mot_detections.db \
        python -m pytest tests/test_cache_fairness.py -v
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("APE_DB_PATH", "/home/ubuntu/training/mot_detections.db")
# MUST be 8000 -- cache/varnish.vcl hardcodes its backend to 127.0.0.1:8000
# (the project's "REST/GraphQL always run on :8000, alternately" convention).
# An earlier version of this test used 18000 and got silent 503s from Varnish
# (backend fetch failed -> error path, never reaches the HIT/MISS logic at
# all) because the VCL was pointed at a port nothing was listening on.
REST_PORT = 8000
VARNISH_PORT = 18080
VARNISH_WORKDIR = ROOT / "scratch" / "test-varnish-instance"

pytestmark = pytest.mark.skipif(
    os.environ.get("APE_RUN_CACHE_TESTS") != "1",
    reason="set APE_RUN_CACHE_TESTS=1 to run (needs varnishd + real subprocesses)",
)


def _wait_port(port: int, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as s:
            s.settimeout(0.2)
            try:
                s.connect(("127.0.0.1", port))
                return
            except OSError:
                time.sleep(0.1)
    raise TimeoutError(f"port {port} never opened")


def _free_port(port: int) -> None:
    """Best-effort: kill anything already bound to `port` before we start a
    fixture server there. Dev environments accumulate stray uvicorn/varnishd
    processes across manual verification sessions -- without this, a leftover
    process silently steals the port and every request in the test goes to
    the WRONG backend (or none), which manifests as confusing 503s rather
    than a clear "port in use" error."""
    subprocess.run(["fuser", "-k", f"{port}/tcp"], stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL)
    time.sleep(0.3)


def _start_uvicorn(app_module: str) -> subprocess.Popen:
    _free_port(REST_PORT)
    env = dict(os.environ, APE_DB_PATH=DB_PATH)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", f"{app_module}:app",
         "--host", "127.0.0.1", "--port", str(REST_PORT)],
        cwd=ROOT, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    _wait_port(REST_PORT)
    return proc


def _start_varnish() -> subprocess.Popen:
    if shutil.which("varnishd") is None:
        pytest.skip("varnishd not installed")
    _free_port(VARNISH_PORT)
    shutil.rmtree(VARNISH_WORKDIR, ignore_errors=True)
    proc = subprocess.Popen(
        ["varnishd", "-n", str(VARNISH_WORKDIR), "-f", str(ROOT / "cache" / "varnish.vcl"),
         "-a", f"127.0.0.1:{VARNISH_PORT}", "-s", "malloc,64m", "-F"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    _wait_port(VARNISH_PORT)
    return proc


@pytest.fixture
def varnish():
    proc = _start_varnish()
    yield f"http://127.0.0.1:{VARNISH_PORT}"
    proc.terminate()
    proc.wait(timeout=5)
    shutil.rmtree(VARNISH_WORKDIR, ignore_errors=True)


@pytest.fixture
def rest_backend(varnish):
    proc = _start_uvicorn("rest_server")
    yield varnish
    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture
def graphql_backend(varnish):
    proc = _start_uvicorn("graphql_server")
    yield varnish
    proc.terminate()
    proc.wait(timeout=5)


def test_a3_rest_cache_miss_then_hit(rest_backend):
    base = rest_backend
    r1 = requests.get(f"{base}/images/1/detections")
    r2 = requests.get(f"{base}/images/1/detections")
    assert r1.headers["X-Cache"] == "MISS"
    assert r2.headers["X-Cache"] == "HIT"
    assert r1.content == r2.content
    assert r1.headers["ETag"] == r2.headers["ETag"]


def test_a3_rest_random_never_cached(rest_backend):
    base = rest_backend
    for _ in range(3):
        r = requests.get(f"{base}/images/random?density_tier=low")
        assert r.status_code == 200
        assert r.headers["X-Cache"] == "MISS"
        assert r.headers["Cache-Control"] == "no-store"


def test_a3_graphql_apq_miss_then_hit(graphql_backend):
    base = graphql_backend
    query = "{ image(id:1) { id density_tier } }"
    sha = hashlib.sha256(query.encode()).hexdigest()
    ext = json.dumps({"persistedQuery": {"version": 1, "sha256Hash": sha}})

    # 1. hash-only, unknown to the server yet -> PersistedQueryNotFound, no-store
    r1 = requests.get(f"{base}/graphql", params={"extensions": ext})
    assert r1.json()["errors"][0]["extensions"]["code"] == "PERSISTED_QUERY_NOT_FOUND"
    assert r1.headers["Cache-Control"] == "no-store"

    # 2. hash+query registers it and executes (own cache key, first hit = MISS)
    r2 = requests.get(f"{base}/graphql", params={"query": query, "extensions": ext})
    assert r2.json()["data"]["image"]["id"] == 1
    assert r2.headers["X-Cache"] == "MISS"

    # 3. hash-only, now known: a DIFFERENT URL (no query param) -> its own
    # cache key, so first call here is also a MISS, but repeating the SAME
    # hash-only URL must HIT.
    r3 = requests.get(f"{base}/graphql", params={"extensions": ext})
    r4 = requests.get(f"{base}/graphql", params={"extensions": ext})
    assert r3.json() == r2.json()
    assert r4.headers["X-Cache"] == "HIT"
    assert r3.content == r4.content


def test_a3_graphql_random_never_cached(graphql_backend):
    base = graphql_backend
    query = '{ randomImage: random_image(density_tier:"low") { id } }'
    for _ in range(3):
        r = requests.get(f"{base}/graphql", params={"query": query})
        assert r.status_code == 200
        assert r.headers["X-Cache"] == "MISS"
        assert r.headers["Cache-Control"] == "no-store"


def test_a3_graphql_hash_mismatch_rejected(graphql_backend):
    base = graphql_backend
    query = "{ image(id:1) { id } }"
    ext = json.dumps({"persistedQuery": {"version": 1, "sha256Hash": "deadbeef"}})
    r = requests.get(f"{base}/graphql", params={"query": query, "extensions": ext})
    assert r.json()["errors"][0]["extensions"]["code"] == "PERSISTED_QUERY_HASH_MISMATCH"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
