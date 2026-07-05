// k6/workload_mot.js
// ===================
// MOT scenario-study workload (M1-M6 from design/SCENARIO_DESIGN.md).
// Separate file from k6/workload.js ON PURPOSE: workload.js is the fixed
// contract of the already-recorded phase2 sessions (entropy/access-pattern
// grid) -- this study's scenarios don't share its shape-pool machinery, so
// they get their own script following the same conventions:
//   * open-loop constant-arrival-rate executor (VUS env = TARGET RATE in
//     req/s, NOT concurrent VUs -- coordinated-omission rationale documented
//     in workload.js's LOAD MODEL note, identical here);
//   * GraphQL via the real Apollo-style APQ-over-GET client flow;
//   * no per-request disk logging, only handleSummary.
//
// Env:
//   PROTOCOL       rest | graphql                              (required)
//   BASE_URL       raw server port or Varnish port              (required)
//   SCENARIO       M1 | M2 | M3 | M4 | M5 | M5E | M6            (required)
//   TIER           M1-M4: low|medium|high   (image density tier)
//                  M5/M5E: w2|w8|w23        (trajectory window tier)
//                  M6:     k1|k5|k10        (page size K)        (required)
//   ACCESS_PATTERN uniform | zipfian | unique                   (required)
//   ID_POOL_JSON   scratch/id_pool_mot.json (tools/build_id_pool.py)
//   VUS            target arrival rate req/s, DURATION, SUMMARY_FILE
//   ENTITY_OFFSET  cross-run cursor continuation for 'unique' (see
//                  workload.js's ENTITY_OFFSET comment -- same trap)
//   ZIPF_THETA     default 0.99
//
// Scenario contracts (kept byte-comparable across protocols -- REST bodies
// and GraphQL data.* carry the SAME fields in the SAME order; the fields=
// projection on M1/M3 pins REST to the canonical 6 DETECTION_FIELDS so
// neither arm ships extra columns the other doesn't):
//   M1  full object     REST /images/{id}/detections?fields=<all 6>
//   M2  sparse fields   REST ?fields=class_id,confidence
//   M3  filtered        REST ?class_id=4&min_confidence=0.5&fields=<all 6>
//   M4  aggregate       REST /images/{id}/class_counts
//   M5  nested 2-RT     REST /tracks/{id} THEN /tracks/{id}/trajectory
//                       (center_frame = track midpoint from the pool) --
//                       page_latency = sum of both, round_trip_count = 2
//   M5E embed 1-RT      REST /tracks/{id}?embed=trajectory (counterfactual)
//   M6  track page      REST Kx /tracks/{id}/trajectory?window=2 vs ONE
//                       GraphQL tracks(ids) composite call

import http from "k6/http";
import crypto from "k6/crypto";
import exec from "k6/execution";
import { check } from "k6";
import { Trend, Rate, Counter } from "k6/metrics";
import { SharedArray } from "k6/data";

const PROTOCOL = __ENV.PROTOCOL;
const BASE_URL = __ENV.BASE_URL;
const SCENARIO = __ENV.SCENARIO;
const TIER = __ENV.TIER;
const ACCESS_PATTERN = __ENV.ACCESS_PATTERN || "uniform";
const ID_POOL_JSON = __ENV.ID_POOL_JSON || "scratch/id_pool_mot.json";
const ZIPF_THETA = __ENV.ZIPF_THETA ? parseFloat(__ENV.ZIPF_THETA) : 0.99;
const ENTITY_OFFSET = __ENV.ENTITY_OFFSET ? parseInt(__ENV.ENTITY_OFFSET, 10) : 0;

const TARGET_RATE = parseInt(__ENV.VUS, 10);
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
const pageLatency = new Trend("page_latency");
const roundTripCount = new Trend("round_trip_count");

// --- entity pool for this (SCENARIO, TIER) cell -------------------------------
// M1-M4 draw image ids from a density tier; M5/M5E draw {id, center} track
// entries from a window-eligibility pool; M6 draws FIXED pages of K track
// ids from the W=2 pool (fixed pages so the same composite id set can recur
// -- same rationale as workload.js's page mode).
const IS_IMAGE_SCENARIO = ["M1", "M2", "M3", "M4"].indexOf(SCENARIO) >= 0;
const IS_TRACK_SCENARIO = SCENARIO === "M5" || SCENARIO === "M5E";
const IS_PAGE_SCENARIO = SCENARIO === "M6";

const WINDOW = IS_TRACK_SCENARIO ? parseInt(TIER.slice(1), 10) : 2; // w2|w8|w23
const PAGE_SIZE = IS_PAGE_SCENARIO ? parseInt(TIER.slice(1), 10) : 0; // k1|k5|k10

const ENTITIES = new SharedArray("entities", function () {
  const pool = JSON.parse(open(ID_POOL_JSON));
  if (IS_IMAGE_SCENARIO) return pool.images[TIER];
  if (IS_TRACK_SCENARIO) return pool.tracks_by_window[String(WINDOW)];
  return pool.track_pages[String(PAGE_SIZE)];
});

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
  return [buildZipfCdf(ENTITIES.length, ZIPF_THETA)];
})[0];

function pickIndex() {
  if (ACCESS_PATTERN === "zipfian") {
    const u = Math.random();
    let lo = 0, hi = zipfCdf.length - 1;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (zipfCdf[mid] >= u) hi = mid;
      else lo = mid + 1;
    }
    return lo;
  }
  if (ACCESS_PATTERN === "unique") {
    return (ENTITY_OFFSET + exec.scenario.iterationInTest) % ENTITIES.length;
  }
  return Math.floor(Math.random() * ENTITIES.length); // uniform
}

// --- REST ----------------------------------------------------------------------
const ALL_FIELDS = "class_id,confidence,bbox_x,bbox_y,bbox_w,bbox_h";

function restGet(path) {
  const res = http.get(`${BASE_URL}${path}`);
  check(res, { "status is 200": (r) => r.status === 200 });
  latency.add(res.timings.duration);
  payloadBytes.add(res.body ? res.body.length : 0);
  const hit = res.headers["X-Cache"];
  if (hit !== undefined) cacheHitRate.add(hit === "HIT");
  return res;
}

function restIteration() {
  const entity = ENTITIES[pickIndex()];
  if (SCENARIO === "M1") {
    restGet(`/images/${entity}/detections?fields=${ALL_FIELDS}`);
    roundTripCount.add(1);
  } else if (SCENARIO === "M2") {
    restGet(`/images/${entity}/detections?fields=class_id,confidence`);
    roundTripCount.add(1);
  } else if (SCENARIO === "M3") {
    restGet(`/images/${entity}/detections?class_id=4&min_confidence=0.5&fields=${ALL_FIELDS}`);
    roundTripCount.add(1);
  } else if (SCENARIO === "M4") {
    restGet(`/images/${entity}/class_counts`);
    roundTripCount.add(1);
  } else if (SCENARIO === "M5") {
    // The honest REST client flow for "track then its trajectory": the
    // first response is what tells a real client the track exists/what it
    // is; the second fetches the nested collection. Scenario latency =
    // BOTH round trips (page_latency), per-call latency still recorded
    // per sub-request by restGet.
    const r1 = restGet(`/tracks/${entity.id}`);
    const r2 = restGet(`/tracks/${entity.id}/trajectory?center_frame=${entity.center}&window=${WINDOW}`);
    pageLatency.add(r1.timings.duration + r2.timings.duration);
    roundTripCount.add(2);
  } else if (SCENARIO === "M5E") {
    const res = restGet(`/tracks/${entity.id}?embed=trajectory&center_frame=${entity.center}&window=${WINDOW}`);
    pageLatency.add(res.timings.duration);
    roundTripCount.add(1);
  } else if (SCENARIO === "M6") {
    let total = 0;
    for (const id of entity) {
      const res = restGet(`/tracks/${id}/trajectory?window=2`);
      total += res.timings.duration;
    }
    pageLatency.add(total);
    roundTripCount.add(entity.length);
  }
}

// --- GraphQL (APQ-over-GET, same client flow as workload.js) --------------------
// Selection sets mirror the REST bodies key-for-key AND in the same key
// order (REST's dict order comes from the shared DAL's SELECT column order),
// so payload bytes differ only by the constant protocol envelope.
const GQL_QUERIES = {
  M1: "query M1($id: Int!) { image(id: $id) { id frame_index width height density_tier sequence_name detections { class_id confidence bbox_x bbox_y bbox_w bbox_h } } }",
  M2: "query M2($id: Int!) { image(id: $id) { id frame_index width height density_tier sequence_name detections { class_id confidence } } }",
  M3: "query M3($id: Int!) { image(id: $id) { id frame_index width height density_tier sequence_name detections(class_id: 4, min_confidence: 0.5) { class_id confidence bbox_x bbox_y bbox_w bbox_h } } }",
  M4: "query M4($id: Int!) { image(id: $id) { id class_counts { class_id count } } }",
  M5: "query M5($id: Int!, $w: Int!, $c: Int!) { track(id: $id) { id sequence_id local_track_id class_id first_frame last_frame class_name trajectory(window: $w, center_frame: $c) { id image_id frame_index confidence bbox_x bbox_y bbox_w bbox_h } } }",
  M6: "query M6($ids: [Int!]!) { tracks(ids: $ids) { id sequence_id local_track_id class_id first_frame last_frame class_name trajectory(window: 2) { id image_id frame_index confidence bbox_x bbox_y bbox_w bbox_h } } }",
};

function apqGet(query, variablesObj) {
  const hash = crypto.sha256(query, "hex");
  const variables = JSON.stringify(variablesObj);
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
      `${BASE_URL}/graphql?query=${encodeURIComponent(query)}` +
      `&extensions=${encodeURIComponent(extensions)}&variables=${encodeURIComponent(variables)}`
    );
  }
  check(res, {
    "status is 200": (r) => r.status === 200,
    "no graphql errors": (r) => r.status === 200 && r.body.indexOf('"errors"') === -1,
  });
  latency.add(res.timings.duration);
  payloadBytes.add(res.body ? res.body.length : 0);
  const hit = res.headers["X-Cache"];
  if (hit !== undefined) cacheHitRate.add(hit === "HIT");
  return res;
}

function gqlIteration() {
  const entity = ENTITIES[pickIndex()];
  if (IS_IMAGE_SCENARIO) {
    apqGet(GQL_QUERIES[SCENARIO], { id: entity });
    roundTripCount.add(1);
  } else if (SCENARIO === "M5") {
    const res = apqGet(GQL_QUERIES.M5, { id: entity.id, w: WINDOW, c: entity.center });
    pageLatency.add(res.timings.duration);
    roundTripCount.add(1);
  } else if (SCENARIO === "M6") {
    const res = apqGet(GQL_QUERIES.M6, { ids: entity });
    pageLatency.add(res.timings.duration);
    roundTripCount.add(1);
  }
  // M5E is REST-only by design (the REST-optimized counterfactual arm).
}

export default function () {
  if (PROTOCOL === "graphql") gqlIteration();
  else restIteration();
}

export function handleSummary(data) {
  const summaryFile = __ENV.SUMMARY_FILE;
  const out = {};
  out[summaryFile] = JSON.stringify(data, null, 2);
  return out;
}
