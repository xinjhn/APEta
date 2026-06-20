"""
tests/test_parity.py
====================
Validasi Paritas Data (Laporan Subbab IV.5.1 & IV.5.3).

Prasyarat mutlak fairness: untuk (density, seed) yang sama, REST dan GraphQL
HARUS mengembalikan struktur & nilai data yang 100% identik pada tiap pola kueri.
Jika tidak, overhead yang dibandingkan adalah artefak perbedaan output, bukan
perbedaan protokol.

Pendekatan: kedua aplikasi ASGI dijalankan IN-PROCESS via Starlette TestClient
(tanpa port nyata). Keduanya berbagi Singleton InMemoryPool yang sama, sehingga
pool dijamin identik. Seed dipakai agar pemilihan citra deterministik & sama.

Karena auto_camel_case dinonaktifkan di GraphQL, nama field snake_case identik,
sehingga perbandingan dapat berupa deep-equality literal.

Jalankan:
    APE_POOL_JSON=/tmp/synthetic.json python -m pytest tests/test_parity.py -v
atau langsung:
    APE_POOL_JSON=/tmp/synthetic.json python tests/test_parity.py
"""
from __future__ import annotations

import os
import sys

# Pastikan root APE ada di path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from starlette.testclient import TestClient  # noqa: E402

DENSITIES = ("low", "medium", "high")
SEEDS = (1, 7, 42, 123)


def _gql(client: TestClient, query: str) -> dict:
    r = client.post("/graphql", json={"query": query})
    r.raise_for_status()
    body = r.json()
    assert "errors" not in body, f"GraphQL error: {body.get('errors')}"
    return body["data"]


def run_parity():
    import graphql_server
    import rest_server

    # Context manager memicu event startup -> InMemoryPool.initialize().
    # Singleton dibagi kedua app, jadi init pertama (REST) cukup; init GraphQL
    # bersifat idempotent (no-op) -> menjamin pool IDENTIK untuk keduanya.
    with TestClient(rest_server.app) as rest, TestClient(graphql_server.app) as gql:
        return _compare(rest, gql)


def _compare(rest, gql):
    total, ok = 0, 0
    for density in DENSITIES:
        for seed in SEEDS:
            checks = []

            # S1 baseline
            r = rest.get(f"/baseline?density={density}&seed={seed}").json()
            g = _gql(gql, f'{{ image_detections(density:"{density}", seed:{seed}) '
                          f'{{ image_id dimensions {{ width height }} '
                          f'detections {{ class_label confidence_score bounding_box }} }} }}'
                     )["image_detections"]
            checks.append(("baseline", r, g))

            # S2 partial (field subset via selection set GraphQL)
            r = rest.get(f"/partial?density={density}&seed={seed}").json()
            g = _gql(gql, f'{{ image_detections(density:"{density}", seed:{seed}) '
                          f'{{ image_id dimensions {{ width height }} '
                          f'detections {{ class_label confidence_score }} }} }}'
                     )["image_detections"]
            checks.append(("partial", r, g))

            # S3 filtered (predikat tetap car AND conf>=0.5)
            r = rest.get(f"/filtered?density={density}&seed={seed}").json()
            g = _gql(gql, f'{{ image_detections(density:"{density}", '
                          f'class_label:"car", min_confidence:0.5, seed:{seed}) '
                          f'{{ image_id dimensions {{ width height }} '
                          f'detections {{ class_label confidence_score bounding_box }} }} }}'
                     )["image_detections"]
            checks.append(("filtered", r, g))

            # S4 aggregate
            r = rest.get(f"/aggregate?density={density}&seed={seed}").json()
            g = _gql(gql, f'{{ aggregate(density:"{density}", seed:{seed}) '
                          f'{{ image_id class_counts {{ class_name count }} }} }}'
                     )["aggregate"]
            checks.append(("aggregate", r, g))

            for pattern, rest_resp, gql_resp in checks:
                total += 1
                if rest_resp == gql_resp:
                    ok += 1
                else:
                    print(f"[MISMATCH] {pattern} density={density} seed={seed}")
                    print("  REST:", str(rest_resp)[:200])
                    print("  GQL :", str(gql_resp)[:200])

    print(f"\nParitas: {ok}/{total} kombinasi identik.")
    return ok == total


def test_parity():
    assert run_parity(), "Paritas data REST vs GraphQL GAGAL."


if __name__ == "__main__":
    sys.exit(0 if run_parity() else 1)
