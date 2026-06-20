"""
scratch/concurrency_liveness.py
================================
Throwaway liveness check (BUKAN benchmark): pastikan REST & GraphQL bertahan
di bawah request bersamaan. Hanya assert 0 error/timeout dan X-Process-Time
selalu ada. TIDAK menyimpulkan kecepatan relatif.
"""
from __future__ import annotations

import asyncio

import httpx

N_REQUESTS = 300
CONCURRENCY = 10


async def hit_rest(client: httpx.AsyncClient, sem: asyncio.Semaphore, i: int) -> tuple[bool, bool]:
    async with sem:
        try:
            r = await client.get(
                "http://127.0.0.1:8000/baseline", params={"density": "high", "seed": i}
            )
            return r.status_code == 200, "x-process-time" in r.headers
        except httpx.RequestError:
            return False, False


async def hit_graphql(client: httpx.AsyncClient, sem: asyncio.Semaphore, i: int) -> tuple[bool, bool]:
    query = (
        '{ image_detections(density:"high", seed:%d) '
        "{ image_id dimensions { width height } "
        "detections { class_label confidence_score bounding_box } } }" % i
    )
    async with sem:
        try:
            r = await client.post(
                "http://127.0.0.1:8001/graphql", json={"query": query}
            )
            ok = r.status_code == 200 and "errors" not in r.json()
            return ok, "x-process-time" in r.headers
        except httpx.RequestError:
            return False, False


async def run_target(name: str, hit_fn) -> None:
    sem = asyncio.Semaphore(CONCURRENCY)
    async with httpx.AsyncClient(timeout=10.0) as client:
        results = await asyncio.gather(
            *(hit_fn(client, sem, i) for i in range(N_REQUESTS))
        )
    errors = sum(1 for ok, _ in results if not ok)
    missing_header = sum(1 for _, has_header in results if not has_header)
    print(f"[{name}] requests={len(results)} errors={errors} missing_header={missing_header}")
    assert errors == 0, f"{name}: {errors} request(s) failed/timed out"
    assert missing_header == 0, f"{name}: {missing_header} response(s) missing X-Process-Time"


async def main() -> None:
    await run_target("REST", hit_rest)
    await run_target("GraphQL", hit_graphql)
    print("Liveness OK: 0 error/timeout, X-Process-Time selalu ada di kedua server.")


if __name__ == "__main__":
    asyncio.run(main())
