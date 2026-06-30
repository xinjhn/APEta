vcl 4.1;
// cache/varnish.vcl
// ==================
// Shared cache layer for the REST-vs-GraphQL caching study (BUILD SPEC N4/C4).
// Single backend on 127.0.0.1:8000 -- REST and GraphQL run ALTERNATELY on
// that port (existing project convention), so Varnish doesn't need to know
// which protocol is currently live: it caches whatever the live backend
// marks cacheable via Cache-Control (core/caching.py decides that
// identically for both arms).
//
// What's deliberately simple here: TTL comes entirely from the backend's
// Cache-Control header (Varnish's default vcl_backend_response already
// does this -- no override needed). The only behavior added on top of
// Varnish's defaults is the X-Cache hit/miss header in vcl_deliver, which
// is what acceptance test A3 (tests/test_cache_fairness.py) reads.

import std;

backend default {
    .host = "127.0.0.1";
    .port = "8000";
}

sub vcl_recv {
    // Only GET is ever cacheable in this study (REST's reads, GraphQL's
    // APQ-over-GET). Everything else (POST /graphql, introspection, etc.)
    // passes straight through -- not cached, not an error.
    if (req.method != "GET") {
        return (pass);
    }
}

sub vcl_backend_response {
    // MUST explicitly call the builtin logic -- defining vcl_backend_response
    // at all suppresses Varnish's default Cache-Control parsing unless you
    // invoke it yourself. Without this line, "Cache-Control: no-store" on
    // /images/random and randomImage is silently IGNORED and Varnish caches
    // them anyway (caught during Phase 2a verification: random endpoint hit
    // HIT on the 2nd+ call despite no-store). vcl_builtin_backend_response
    // is what reads Cache-Control/Surrogate-Control and sets
    // beresp.uncacheable for no-store/no-cache/private.
    call vcl_builtin_backend_response;
    return (deliver);
}

sub vcl_deliver {
    if (obj.hits > 0) {
        set resp.http.X-Cache = "HIT";
    } else {
        set resp.http.X-Cache = "MISS";
    }
    set resp.http.X-Cache-Hits = obj.hits;
}
