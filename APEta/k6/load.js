// k6/load.js
// ==========
// SATU skrip k6 parameterized untuk REST & GraphQL -- logika request/metrik/
// check IDENTIK di kedua protokol; satu-satunya beda sistematis adalah lapisan
// protokol itu sendiri (sesuai invarian fairness APE).
//
// Env yang dibaca:
//   PROTOCOL    rest | graphql                         (wajib)
//   PATTERN     baseline | partial | filtered | aggregate (wajib)
//   DENSITY     low | medium | high                    (wajib)
//   VUS         jumlah virtual user                     (wajib)
//   DURATION    durasi k6, mis. "10s"                   (wajib)
//   BASE_URL    mis. http://127.0.0.1:8000               (wajib)
//   SEED        opsional -- bila diisi, pemilihan citra deterministik
//   SUMMARY_FILE  path keluaran JSON ringkasan run (wajib, dibaca orchestrator)
//
// TIDAK ada log per-request ke disk (observer effect) -- hanya ringkasan akhir
// run (handleSummary) yang ditulis, sesuai unit analisis = RUN.

import http from "k6/http";
import { check } from "k6";
import { Trend } from "k6/metrics";

const PROTOCOL = __ENV.PROTOCOL;
const PATTERN = __ENV.PATTERN;
const DENSITY = __ENV.DENSITY;
const BASE_URL = __ENV.BASE_URL;
const SEED = __ENV.SEED;
const PROCESS_TIME_HEADER = "X-Process-Time";

// Predikat S3 KONSTAN lintas tier densitas (samakan dengan core/config.py PATTERN_SPEC).
const FILTER_CLASS_LABEL = "car";
const FILTER_MIN_CONFIDENCE = 0.5;

export const options = {
  vus: parseInt(__ENV.VUS, 10),
  duration: __ENV.DURATION,
  // p99 tidak termasuk statistik bawaan k6 -- minta eksplisit agar tersedia
  // utk metrik primer lat_p99/xproc_*, identik utk REST & GraphQL.
  summaryTrendStats: ["avg", "min", "med", "max", "p(50)", "p(95)", "p(99)"],
};

const xprocTime = new Trend("xproc_time");
const payloadBytes = new Trend("payload_bytes");

function restRequest() {
  const params = { density: DENSITY };
  if (SEED) params.seed = SEED;
  if (PATTERN === "filtered") {
    params.class_label = FILTER_CLASS_LABEL;
    params.min_confidence = String(FILTER_MIN_CONFIDENCE);
  }
  const qs = Object.keys(params)
    .map((k) => `${k}=${encodeURIComponent(params[k])}`)
    .join("&");
  return http.get(`${BASE_URL}/${PATTERN}?${qs}`);
}

function graphqlSelectionSet(pattern) {
  if (pattern === "aggregate") {
    return "{ image_id class_counts { class_name count } }";
  }
  const fields =
    pattern === "partial"
      ? "class_label confidence_score"
      : "class_label confidence_score bounding_box";
  return `{ image_id dimensions { width height } detections { ${fields} } }`;
}

function graphqlRequest() {
  const args = [`density:"${DENSITY}"`];
  if (PATTERN === "filtered") {
    args.push(`class_label:"${FILTER_CLASS_LABEL}"`, `min_confidence:${FILTER_MIN_CONFIDENCE}`);
  }
  if (SEED) args.push(`seed:${SEED}`);

  const field = PATTERN === "aggregate" ? "aggregate" : "image_detections";
  const query = `{ ${field}(${args.join(", ")}) ${graphqlSelectionSet(PATTERN)} }`;

  return http.post(`${BASE_URL}/graphql`, JSON.stringify({ query }), {
    headers: { "Content-Type": "application/json" },
  });
}

export default function () {
  const res = PROTOCOL === "rest" ? restRequest() : graphqlRequest();

  check(res, {
    "status 200": (r) => r.status === 200,
    "X-Process-Time hadir": (r) => r.headers[PROCESS_TIME_HEADER] !== undefined,
  });

  const xproc = parseFloat(res.headers[PROCESS_TIME_HEADER]);
  if (!Number.isNaN(xproc)) xprocTime.add(xproc);
  payloadBytes.add(res.body ? res.body.length : 0);
}

export function handleSummary(data) {
  const out = {};
  out[__ENV.SUMMARY_FILE] = JSON.stringify(data);
  return out;
}
