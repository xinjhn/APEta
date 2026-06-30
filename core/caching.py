"""
core/caching.py
================
Shared cache-header logic used IDENTICALLY by REST (rest_server.py) and
GraphQL's APQ-over-GET route (graphql_server.py) -- same fairness principle
as core/dal.py: one function decides ETag/Cache-Control semantics so the two
protocols cannot silently diverge in how "cacheable" is defined (N4).

cacheable=False is for anti-cache-by-design endpoints (REST's /images/random,
GraphQL's randomImage) -- these vary their underlying selection per call
behind a STABLE url/persisted-query-hash, so caching them would silently
collapse the access-pattern IV (Phase 2b) into nonsense. They must be
no-store at every layer, not just "not specially cached".
"""
from __future__ import annotations

import hashlib
from typing import Optional

DEFAULT_MAX_AGE = 30


def compute_etag(body: bytes) -> str:
    return '"' + hashlib.sha256(body).hexdigest() + '"'


def cache_headers(body: bytes, cacheable: bool, max_age: int = DEFAULT_MAX_AGE) -> dict:
    if not cacheable:
        return {"Cache-Control": "no-store"}
    return {
        "Cache-Control": f"public, max-age={max_age}",
        "ETag": compute_etag(body),
    }


def is_fresh(if_none_match: Optional[str], etag: str) -> bool:
    """True if the client's If-None-Match already matches our ETag -- both
    servers use this to decide whether to answer 304 instead of resending
    the body (reduces bytes on cache revalidation after Varnish's TTL
    expires, identically on both protocols)."""
    if not if_none_match:
        return False
    return etag in {tag.strip() for tag in if_none_match.split(",")}
