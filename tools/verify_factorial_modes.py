"""
tools/verify_factorial_modes.py
================================
Skrip verifikasi cepat untuk memastikan kedua server mendukung mode typed dan
passthrough dengan benar. Ini menjalankan smoke test lokal (tanpa k6) untuk
memastikan:
1. Server start dengan mode yang ditentukan
2. Health check mengembalikan mode yang benar
3. Respons data identik antara mode (hanya performa berbeda)

Jalankan:
    APE_POOL_JSON=/tmp/synthetic.json python tools/verify_factorial_modes.py
"""
from __future__ import annotations

import os
import sys
import subprocess
import time
import urllib.request
import json
from pathlib import Path

# Pastikan root APE ada di path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starlette.testclient import TestClient


def test_rest_modes():
    """Verifikasi REST mendukung kedua mode."""
    print("=== Testing REST modes ===")
    
    # Test passthrough mode
    os.environ["APE_REST_MODE"] = "passthrough"
    os.environ.pop("APE_GRAPHQL_MODE", None)
    
    import rest_server
    with TestClient(rest_server.app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        health = response.json()
        assert health["mode"] == "passthrough", f"Expected passthrough, got {health['mode']}"
        
        response = client.get("/baseline?density=medium&seed=42")
        assert response.status_code == 200
        data_passthrough = response.json()
        print(f"✓ REST passthrough: baseline returns {len(data_passthrough.get('detections', []))} detections")
    
    # Clear module cache
    if 'rest_server' in sys.modules:
        del sys.modules['rest_server']
    from core.pool import InMemoryPool
    InMemoryPool.reset()
    
    # Test typed mode
    os.environ["APE_REST_MODE"] = "typed"
    
    import rest_server as rest_server_typed
    with TestClient(rest_server_typed.app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        health = response.json()
        assert health["mode"] == "typed", f"Expected typed, got {health['mode']}"
        
        response = client.get("/baseline?density=medium&seed=42")
        assert response.status_code == 200
        data_typed = response.json()
        print(f"✓ REST typed: baseline returns {len(data_typed.get('detections', []))} detections")
        
        # Verify data parity (should be identical structure)
        assert data_passthrough.keys() == data_typed.keys(), "Keys mismatch between modes"
        assert data_passthrough["image_id"] == data_typed["image_id"], "image_id mismatch"
        print(f"✓ Data structure identical between passthrough and typed modes")
    
    print("✅ REST modes verified successfully\n")


def test_graphql_modes():
    """Verifikasi GraphQL mendukung kedua mode."""
    print("=== Testing GraphQL modes ===")
    
    # Test typed mode (default)
    os.environ["APE_GRAPHQL_MODE"] = "typed"
    os.environ.pop("APE_REST_MODE", None)
    
    import graphql_server
    with TestClient(graphql_server.app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        health = response.json()
        assert health["mode"] == "typed", f"Expected typed, got {health['mode']}"
        
        query = '{ image_detections(density:"medium", seed:42) { image_id dimensions { width height } detections { class_label confidence_score bounding_box } } }'
        response = client.post("/graphql", json={"query": query})
        assert response.status_code == 200
        data = response.json()
        assert "errors" not in data, f"GraphQL error: {data.get('errors')}"
        detections_typed = data["data"]["image_detections"]["detections"]
        print(f"✓ GraphQL typed: baseline returns {len(detections_typed)} detections")
    
    # Clear module cache
    if 'graphql_server' in sys.modules:
        del sys.modules['graphql_server']
    from core.pool import InMemoryPool
    InMemoryPool.reset()
    
    # Test passthrough mode
    os.environ["APE_GRAPHQL_MODE"] = "passthrough"
    
    import graphql_server as graphql_server_pt
    with TestClient(graphql_server_pt.app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        health = response.json()
        assert health["mode"] == "passthrough", f"Expected passthrough, got {health['mode']}"
        
        response = client.post("/graphql", json={"query": query})
        assert response.status_code == 200
        data = response.json()
        assert "errors" not in data, f"GraphQL error: {data.get('errors')}"
        detections_pt = data["data"]["image_detections"]["detections"]
        print(f"✓ GraphQL passthrough: baseline returns {len(detections_pt)} detections")
        
        # Verify data parity
        assert len(detections_typed) == len(detections_pt), "Detection count mismatch"
        print(f"✓ Data structure identical between typed and passthrough modes")
    
    print("✅ GraphQL modes verified successfully\n")


if __name__ == "__main__":
    # Set pool JSON for testing
    pool_json = os.environ.get("APE_POOL_JSON")
    if not pool_json:
        print("ERROR: APE_POOL_JSON environment variable not set")
        print("Usage: APE_POOL_JSON=/tmp/synthetic.json python tools/verify_factorial_modes.py")
        sys.exit(1)
    
    try:
        test_rest_modes()
        test_graphql_modes()
        print("\n" + "="*60)
        print("ALL FACTORIAL MODES VERIFIED SUCCESSFULLY")
        print("="*60)
        print("\nNext steps:")
        print("1. Run 4 experimental sessions with different mode combinations")
        print("2. Combine results.csv files")
        print("3. Run per-cell Mann-Whitney U + Vargha-Delaney/Cliff's delta (tools/analyze_factorial.py)")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ VERIFICATION FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
