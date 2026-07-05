// k6/workload.js
// ===============
// Phase 2 workload generator. Replaces the retired k6/load.js (which targeted
// the old flat S1-S4 endpoints) -- this drives the new relational schema's
// endpoints with the BUILD SPEC's two decoupled IV axes:
//
//   ACCESS_PATTERN  controls WHICH entity id gets requested (unique/zipfian/
//                   uniform) -- the spec's access-pattern IV (Section 3).
//   ENTROPY         controls the VARIETY of query shapes drawn from (low/
//                   medium/high) -- the spec's query-shape-entropy IV. This
//                   is the knob that makes H3 (aggregation depth up => hit
//                   rate down) testable: more distinct shapes => more
//                   distinct cache keys => lower achieved hit rate for the
//                   SAME access pattern.
//
// These are independent knobs by construction: shape selection and id
// selection are drawn from separate RNG calls against separate pools.
//
// PAYLOAD_WEIGHT (light/heavy) picks the ENDPOINT family, not a query
// parameter: light = flat image detections, heavy = track trajectory
// (bounded +/-window, spec Section 7) -- this is the payload/nesting-depth
// driver, deliberately orthogonal to entropy and access pattern.
//
// Caching itself is NOT a script parameter: point BASE_URL at the raw
// server port (caching off) or the Varnish port (caching on, cache/varnish.vcl)
// -- the script doesn't need to know which, it just measures what happens.
//
// GraphQL uses a REAL Apollo-style APQ client flow (graphql_server.py's
// GET /graphql route from Phase 2a): try hash-only first, and only send the
// full query text on a PersistedQueryNotFound reply -- exactly what a real
// caching-aware GraphQL client does, so the round-trip/registration cost is
// part of what gets measured, not assumed away.
//
// Env:
//   PROTOCOL        rest | graphql                          (required)
//   BASE_URL        e.g. http://127.0.0.1:8000 or :8080      (required)
//   ACCESS_PATTERN  unique | zipfian | uniform                (required)
//   ENTROPY         low | medium | high                       (required)
//   PAYLOAD_WEIGHT  light | heavy                             (required)
//   DENSITY         low | medium | high (light weight only, ignored for heavy)
//   ID_POOL_JSON    path to scratch/id_pool.json (tools/build_id_pool.py)
//   ZIPF_THETA      default 0.99
//   VUS             target arrival rate in req/s (NOT concurrent VUs -- see
//                   LOAD MODEL note below), DURATION, SUMMARY_FILE (required)
//
// No per-request disk logging (observer effect) -- only the run summary
// (handleSummary) is written, same convention as the retired k6/load.js.
//
// LOAD MODEL: open-loop (k6 constant-arrival-rate executor), not the default
// closed-loop "looping VUs" model. Closed-loop generators wait for each
// response before issuing the next request per VU -- when the server (or the
// constrained network profile) slows down, the client automatically slows
// its OWN request rate too, so exactly the period that should inflate tail
// latency instead just produces fewer samples. This is coordinated omission
// (Gil Tene, "How NOT to Measure Latency", Strange Loop 2015) and it
// systematically under-reports p95/p99 during any backpressure. With
// constant-arrival-rate, request ISSUANCE is decoupled from response time:
// k6 keeps firing at the target rate regardless of how slow the backend is,
// spinning up additional VUs (up to maxVUs) to do so -- a slow period
// correctly produces MORE in-flight requests and shows up in the tail, not
// fewer samples.
//
// VUS now means TARGET ARRIVAL RATE in requests/second (not concurrent
// connections) -- this is the unavoidable semantic shift of switching load
// models. preAllocatedVUs/maxVUs are sized generously off that rate so the
// executor doesn't drop iterations under the constrained-network profile's
// added latency (k6 reports any shortfall as the `dropped_iterations`
// metric -- orchestrator/run_experiment.py surfaces it into `notes` so a
// maxVUs shortfall is visible in results.csv, not silently absorbed).

import http from "k6/http";
import crypto from "k6/crypto";
import exec from "k6/execution";
import { check } from "k6";
import { Trend, Rate, Counter } from "k6/metrics";
import { SharedArray } from "k6/data";

const PROTOCOL = __ENV.PROTOCOL;
const BASE_URL = __ENV.BASE_URL;
const ACCESS_PATTERN = __ENV.ACCESS_PATTERN;
const ENTROPY = __ENV.ENTROPY;
const PAYLOAD_WEIGHT = __ENV.PAYLOAD_WEIGHT;
const DENSITY = __ENV.DENSITY || "medium";
const ID_POOL_JSON = __ENV.ID_POOL_JSON || "scratch/id_pool.json";
const ZIPF_THETA = __ENV.ZIPF_THETA ? parseFloat(__ENV.ZIPF_THETA) : 0.99;
// Round-trip-vs-cacheability arm (page/batch-size factor K): when set,
// REPLACES the normal single-resource request entirely with a "page" of K
// FIXED ids -- REST issues K separate /images/{id}/detections calls (each
// independently cacheable), GraphQL issues ONE images(ids:[...]) call (one
// composite cache entry keyed by the exact id SET). Light-payload only --
// page semantics don't extend to the heavy/track arm in this design.
// PAGE_SIZE=0 (default/unset) is the original, unmodified single-resource
// behavior below; this is strictly additive.
const PAGE_SIZE = __ENV.PAGE_SIZE ? parseInt(__ENV.PAGE_SIZE, 10) : 0;
const PAGE_MODE = PAGE_SIZE > 0;
// Cross-run continuation for the "unique" cursor -- see uniqueSample() below.
// Each warmup/measured row is a SEPARATE `k6 run` process, so
// exec.scenario.iterationInTest alone resets to 0 every time; without this
// offset every run in a block would request the identical starting id
// sequence as the run before it, which the previous run had just warmed.
const ENTITY_OFFSET = __ENV.ENTITY_OFFSET ? parseInt(__ENV.ENTITY_OFFSET, 10) : 0;

const TARGET_RATE = parseInt(__ENV.VUS, 10);
// Sized off the target rate, not a fixed constant -- generous enough to
// absorb the constrained-network profile's added latency (and GraphQL's
// occasional APQ registration round trip) without hitting maxVUs and
// silently dropping iterations. preAllocatedVUs covers normal steady state;
// maxVUs covers a worst-case backlog (e.g. several seconds of in-flight
// requests piling up under network=constrained).
const PRE_ALLOCATED_VUS = Math.max(TARGET_RATE * 2, 10);
const MAX_VUS = Math.max(TARGET_RATE * 10, 50);

export const options = {
  scenarios: {
    default: {
      executor: "constant-arrival-rate",
      rate: TARGET_RATE,
      timeUnit: "1s",
      duration: __ENV.DURATION,
      preAllocatedVUs: PRE_ALLOCATED_VUS,
      maxVUs: MAX_VUS,
    },
  },
  summaryTrendStats: ["avg", "min", "med", "max", "p(50)", "p(95)", "p(99)"],
};

const latency = new Trend("req_latency");
const payloadBytes = new Trend("payload_bytes");
const cacheHitRate = new Rate("cache_hit");
const apqRegistrations = new Counter("apq_registrations");
// Page-mode only: total time to render the whole K-id page (sum of K REST
// round trips, or the single GraphQL round trip) -- the actual quantity the
// round-trip-vs-cacheability claim is about, distinct from req_latency
// (per-HTTP-call latency, which `latency` already captures per sub-request
// for REST and per-call for GraphQL via the existing add() calls below).
const pageLatency = new Trend("page_latency");
// Real per-iteration round trip count: K for REST page mode, 1 for GraphQL
// page mode (and implicitly 1 for the non-page-mode path, though that path
// doesn't add to this metric -- orchestrator/run_experiment.py only reads
// this metric when PAGE_SIZE>0, see its updated round_trip_count handling).
const roundTripCount = new Trend("round_trip_count");

// --- id pool (loaded once, shared read-only across VUs) -----------------------
const pool = new SharedArray("id_pool", function () {
  return [JSON.parse(open(ID_POOL_JSON))];
})[0];

const imageIds = pool.images[DENSITY];
const trackIds = pool.tracks.map((t) => t.id);
const ENTITY_IDS = PAYLOAD_WEIGHT === "heavy" ? trackIds : imageIds;

// --- Zipfian rank -> cumulative-probability table (built once, shared) --------
// Rank = index in ENTITY_IDS as given (arbitrary but fixed) -- the spec's
// access-pattern factor only needs A skewed hot-set, not a semantically
// meaningful popularity ranking.
function buildZipfCdf(n, theta) {
  const weights = new Array(n);
  let total = 0;
  for (let i = 0; i < n; i++) {
    weights[i] = 1.0 / Math.pow(i + 1, theta);
    total += weights[i];
  }
  const cdf = new Array(n);
  let running = 0;
  for (let i = 0; i < n; i++) {
    running += weights[i];
    cdf[i] = running / total;
  }
  return cdf;
}

const zipfCdf = new SharedArray("zipf_cdf", function () {
  return [buildZipfCdf(ENTITY_IDS.length, ZIPF_THETA)];
})[0];

function zipfSample() {
  const u = Math.random();
  // Binary search smallest i such that cdf[i] >= u.
  let lo = 0, hi = zipfCdf.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (zipfCdf[mid] >= u) hi = mid;
    else lo = mid + 1;
  }
  return ENTITY_IDS[lo];
}

// True no-repeat cursor: exec.scenario.iterationInTest is a single counter
// shared across ALL VUs for this k6 run (not per-VU) -- k6/execution docs:
// "globally unique, incremental ... across all VUs". A per-VU offset cursor
// (the original implementation) does NOT give this: with concurrency>1, N
// independently-offset VUs cycling through the SAME pool collide on the
// same ids at different wall-clock times, so the cache sees plenty of
// repeat keys even under "unique" -- defeating the whole point of this
// access-pattern level (it's supposed to be the compulsory-miss floor that
// contrasts against zipfian/uniform's deliberate reuse).
//
// ENTITY_OFFSET (passed by orchestrator/run_experiment.py, see its
// per-block cursor comment) continues this counter ACROSS separate k6
// process invocations within the same block -- without it, every
// warmup/measured run in a block restarts iterationInTest at 0 and
// re-requests the IDENTICAL starting id sequence the previous run in that
// block just warmed, which is what caused 'unique' to read ~32% hit rate in
// manual verification -- statistically indistinguishable from 'zipfian' at
// the same pool/duration, when it should have read near 0%. Caught during
// integration verification (not visible in the earlier isolated/single-run
// smoke test, which only ever ran one k6 process).
//
// This still isn't *infinite* no-repeat: once (ENTITY_OFFSET + iterationInTest)
// exceeds ENTITY_IDS.length, the modulo wraps and ids start recurring --
// that's an inherent ceiling of "unique" against a finite pool over a whole
// block's reps, not a code defect. Expect cache_hit_rate under "unique" to
// track max(0, 1 - pool_size / cumulative_iterations_this_block), i.e. ~0
// until the block's cumulative requests exceed the pool size, then rising
// -- a predictable, derivable floor instead of an inflated number from
// either cross-VU collisions or cross-run repetition.
function uniqueSample() {
  const it = ENTITY_OFFSET + exec.scenario.iterationInTest;
  return ENTITY_IDS[it % ENTITY_IDS.length];
}

function uniformSample() {
  return ENTITY_IDS[Math.floor(Math.random() * ENTITY_IDS.length)];
}

function pickEntityId() {
  if (ACCESS_PATTERN === "zipfian") return zipfSample();
  if (ACCESS_PATTERN === "unique") return uniqueSample();
  return uniformSample(); // "uniform"
}

// --- page selection (round-trip-vs-cacheability arm) ---------------------
// Mirrors pickEntityId()'s three access-pattern branches exactly, but over
// PAGE INDICES instead of individual entity ids -- access_pattern now
// controls WHICH FIXED PAGE recurs, not which id. This is what gives
// GraphQL's composite cache entry (keyed by the page's exact id set) a real
// chance to be reused under zipfian (a "hot page" recurring), instead of
// being trivially ~0% by construction.
const PAGES = PAGE_MODE ? pool.pages[DENSITY][String(PAGE_SIZE)] : null;
const pageZipfCdf = PAGE_MODE
  ? new SharedArray("page_zipf_cdf", function () { return [buildZipfCdf(PAGES.length, ZIPF_THETA)]; })[0]
  : null;

function zipfPageIndex() {
  const u = Math.random();
  let lo = 0, hi = pageZipfCdf.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (pageZipfCdf[mid] >= u) hi = mid;
    else lo = mid + 1;
  }
  return lo;
}

function uniquePageIndex() {
  const it = ENTITY_OFFSET + exec.scenario.iterationInTest;
  return it % PAGES.length;
}

function uniformPageIndex() {
  return Math.floor(Math.random() * PAGES.length);
}

function pickPage() {
  let idx;
  if (ACCESS_PATTERN === "zipfian") idx = zipfPageIndex();
  else if (ACCESS_PATTERN === "unique") idx = uniquePageIndex();
  else idx = uniformPageIndex();
  return PAGES[idx];
}

// --- REST page request: K separate, independently-cacheable round trips ---
function restPageRequest(ids) {
  let totalLatency = 0;
  let lastRes = null;
  for (const id of ids) {
    const res = http.get(`${BASE_URL}/images/${id}/detections`);
    check(res, { "status is 200": (r) => r.status === 200 });
    latency.add(res.timings.duration);
    payloadBytes.add(res.body ? res.body.length : 0);
    const hit = res.headers["X-Cache"];
    if (hit !== undefined) cacheHitRate.add(hit === "HIT");
    totalLatency += res.timings.duration;
    lastRes = res;
  }
  pageLatency.add(totalLatency);
  roundTripCount.add(ids.length);
  return lastRes;
}

// --- GraphQL page request: ONE composite round trip, one cache entry -----
const GQL_PAGE_QUERY =
  "query Page($ids: [Int!]!) { images(ids: $ids) { id detections { id class_id confidence bbox_x bbox_y bbox_w bbox_h } } }";

function gqlPageRequest(ids) {
  const hash = gqlShapeHash(GQL_PAGE_QUERY);
  const variables = JSON.stringify({ ids });
  const extensions = JSON.stringify({ persistedQuery: { version: 1, sha256Hash: hash } });

  let res = http.get(
    `${BASE_URL}/graphql?extensions=${encodeURIComponent(extensions)}&variables=${encodeURIComponent(variables)}`
  );
  const body = res.status === 200 ? JSON.parse(res.body) : null;
  const notFound = body && body.errors && body.errors[0] &&
    body.errors[0].extensions && body.errors[0].extensions.code === "PERSISTED_QUERY_NOT_FOUND";

  if (notFound) {
    apqRegistrations.add(1);
    res = http.get(
      `${BASE_URL}/graphql?query=${encodeURIComponent(GQL_PAGE_QUERY)}` +
      `&extensions=${encodeURIComponent(extensions)}&variables=${encodeURIComponent(variables)}`
    );
  }
  check(res, { "status is 200": (r) => r.status === 200 });
  latency.add(res.timings.duration);
  payloadBytes.add(res.body ? res.body.length : 0);
  const hit = res.headers["X-Cache"];
  if (hit !== undefined) cacheHitRate.add(hit === "HIT");
  pageLatency.add(res.timings.duration);
  roundTripCount.add(1);
  return res;
}

// --- query-shape pools (entropy controls how many of these are in play) -------
// REST shapes operate on /images/{id}/detections (light) via fields=/class_id/
// min_confidence, or /tracks/{id}/trajectory (heavy) via window. GraphQL
// shapes are query TEXT templates with a $id variable -- the persisted-query
// hash is a function of TEXT only, so the same shape across different ids
// keeps the same hash (realistic APQ reuse), while different shapes are
// genuinely different cache entries (the H3 mechanism).
const REST_LIGHT_SHAPES = [
  (id) => `/images/${id}/detections`,
  (id) => `/images/${id}/detections?fields=class_id,confidence`,
  (id) => `/images/${id}/detections?fields=bbox_x,bbox_y,bbox_w,bbox_h`,
  (id) => `/images/${id}/detections?class_id=4`,
  (id) => `/images/${id}/detections?class_id=1`,
  (id) => `/images/${id}/detections?min_confidence=0.5`,
  (id) => `/images/${id}/detections?class_id=4&min_confidence=0.5`,
  (id) => `/images/${id}/detections?fields=class_id&min_confidence=0.25`,
];

const REST_HEAVY_SHAPES = [
  (id) => `/tracks/${id}/trajectory?window=2`,
  (id) => `/tracks/${id}/trajectory?window=5`,
  (id) => `/tracks/${id}/trajectory?window=10`,
  (id) => `/tracks/${id}/trajectory?window=20`,
  (id) => `/tracks/${id}/trajectory?window=2&center_frame=1`,
  (id) => `/tracks/${id}/trajectory?window=5&center_frame=1`,
  (id) => `/tracks/${id}/trajectory?window=10&center_frame=1`,
  (id) => `/tracks/${id}/trajectory?window=20&center_frame=1`,
];

const GQL_LIGHT_SHAPES = [
  "query Q($id: Int!) { image(id: $id) { id detections { id class_id confidence bbox_x bbox_y bbox_w bbox_h } } }",
  "query Q($id: Int!) { image(id: $id) { id detections { id class_id confidence } } }",
  "query Q($id: Int!) { image(id: $id) { id detections { id bbox_x bbox_y bbox_w bbox_h } } }",
  "query Q($id: Int!) { image(id: $id) { id detections(class_id: 4) { id class_id confidence } } }",
  "query Q($id: Int!) { image(id: $id) { id detections(class_id: 1) { id class_id confidence } } }",
  "query Q($id: Int!) { image(id: $id) { id detections(min_confidence: 0.5) { id class_id confidence } } }",
  "query Q($id: Int!) { image(id: $id) { id detections(class_id: 4, min_confidence: 0.5) { id class_id confidence } } }",
  "query Q($id: Int!) { image(id: $id) { id density_tier detections { id class_id } } }",
];

const GQL_HEAVY_SHAPES = [
  "query Q($id: Int!) { track(id: $id) { id trajectory(window: 2) { id frame_index confidence bbox_x bbox_y bbox_w bbox_h } } }",
  "query Q($id: Int!) { track(id: $id) { id trajectory(window: 5) { id frame_index confidence bbox_x bbox_y bbox_w bbox_h } } }",
  "query Q($id: Int!) { track(id: $id) { id trajectory(window: 10) { id frame_index confidence bbox_x bbox_y bbox_w bbox_h } } }",
  "query Q($id: Int!) { track(id: $id) { id trajectory(window: 20) { id frame_index confidence bbox_x bbox_y bbox_w bbox_h } } }",
  "query Q($id: Int!) { track(id: $id) { id class_name trajectory(window: 2) { id frame_index confidence } } }",
  "query Q($id: Int!) { track(id: $id) { id class_name trajectory(window: 5) { id frame_index confidence } } }",
  "query Q($id: Int!) { track(id: $id) { id class_name trajectory(window: 10) { id frame_index confidence } } }",
  "query Q($id: Int!) { track(id: $id) { id class_name trajectory(window: 20) { id frame_index confidence } } }",
];

function entropyPoolSize() {
  if (ENTROPY === "low") return 1;
  if (ENTROPY === "medium") return 4;
  return 8; // "high"
}

function pickShapeIndex() {
  return Math.floor(Math.random() * entropyPoolSize());
}

// --- REST request ---------------------------------------------------------
function restRequest() {
  const id = pickEntityId();
  const shapes = PAYLOAD_WEIGHT === "heavy" ? REST_HEAVY_SHAPES : REST_LIGHT_SHAPES;
  const path = shapes[pickShapeIndex()](id);
  const res = http.get(`${BASE_URL}${path}`);
  return { res, cacheHeader: res.headers["X-Cache"] };
}

// --- GraphQL request (real APQ client flow) --------------------------------
function gqlShapeHash(query) {
  return crypto.sha256(query, "hex");
}

function gqlRequest() {
  const id = pickEntityId();
  const shapes = PAYLOAD_WEIGHT === "heavy" ? GQL_HEAVY_SHAPES : GQL_LIGHT_SHAPES;
  const query = shapes[pickShapeIndex()];
  const hash = gqlShapeHash(query);
  const variables = JSON.stringify({ id });
  const extensions = JSON.stringify({ persistedQuery: { version: 1, sha256Hash: hash } });

  // 1. Try hash-only first (the steady-state APQ path a real client takes
  // once a shape's hash is known -- which, client-side, is ALWAYS, since the
  // hash is just sha256 of text we already have; no client-side cache needed
  // to know the hash, only the SERVER needs to have seen it before).
  let res = http.get(
    `${BASE_URL}/graphql?extensions=${encodeURIComponent(extensions)}&variables=${encodeURIComponent(variables)}`
  );
  const body = res.status === 200 ? JSON.parse(res.body) : null;
  const notFound = body && body.errors && body.errors[0] &&
    body.errors[0].extensions && body.errors[0].extensions.code === "PERSISTED_QUERY_NOT_FOUND";

  if (notFound) {
    apqRegistrations.add(1);
    // 2. Register: hash+query+variables in one call.
    res = http.get(
      `${BASE_URL}/graphql?query=${encodeURIComponent(query)}` +
      `&extensions=${encodeURIComponent(extensions)}&variables=${encodeURIComponent(variables)}`
    );
  }
  return { res, cacheHeader: res.headers["X-Cache"] };
}

export default function () {
  if (PAGE_MODE) {
    const ids = pickPage();
    if (PROTOCOL === "graphql") gqlPageRequest(ids);
    else restPageRequest(ids);
    return;
  }

  const { res, cacheHeader } = PROTOCOL === "graphql" ? gqlRequest() : restRequest();

  check(res, { "status is 200": (r) => r.status === 200 });
  latency.add(res.timings.duration);
  payloadBytes.add(res.body ? res.body.length : 0);
  // X-Cache only exists when the request went through Varnish (BASE_URL
  // pointed at the cache port); when caching is "off" (BASE_URL = raw
  // server port) the header is absent and this Rate simply never samples --
  // the orchestrator tags caching on/off separately in the results row
  // rather than inferring it from this metric.
  if (cacheHeader !== undefined) {
    cacheHitRate.add(cacheHeader === "HIT");
  }
}

export function handleSummary(data) {
  const summaryFile = __ENV.SUMMARY_FILE;
  const out = {};
  out[summaryFile] = JSON.stringify(data, null, 2);
  return out;
}
