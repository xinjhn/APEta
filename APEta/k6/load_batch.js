// k6/load_batch.js
// =================
// Skrip k6 KHUSUS untuk sub-studi "batch" (N+1 round-trip avoidance) -- TIDAK
// dipakai oleh pipeline faktorial utama (k6/load.js, orchestrator/run_experiment.py)
// dan TIDAK mengubah results.csv/run_plan.csv (kontrak tetap pipeline utama).
// Lihat tools/run_batch_study.py untuk runner-nya.
//
// Pertanyaan yang diuji: REST tanpa endpoint batch khusus membutuhkan K round
// trip berurutan untuk mengambil K resource; GraphQL bisa menggabungkan K
// permintaan jadi SATU dokumen kueri (field alias) dalam SATU round trip. Ini
// klaim "supremasi GraphQL" yang TIDAK bisa diuji oleh 4 pola FR-01..FR-04
// (yang semuanya single-resource per request untuk kedua protokol) -- lihat
// audit METHODOLOGICAL_VERIFICATION.md.
//
// Metrik utama: batch_wall_time (total waktu utk mendapatkan SEMUA K resource,
// BUKAN rata-rata per-request) -- ini metrik yang relevan bagi klien nyata yang
// butuh K resource sebelum bisa lanjut (mis. render halaman galeri).
//
// Env:
//   PROTOCOL  rest | graphql   (wajib)
//   DENSITY   low | medium | high (wajib)
//   BATCH_K   jumlah resource per "batch" (wajib, mis. 5, 20)
//   VUS, DURATION, BASE_URL, SUMMARY_FILE (wajib, sama dgn load.js)
//   SEED_BASE opsional -- basis seed deterministik (tiap anggota batch SEED_BASE+i)

import http from "k6/http";
import { check } from "k6";
import { Trend } from "k6/metrics";

const PROTOCOL = __ENV.PROTOCOL;
const DENSITY = __ENV.DENSITY;
const BATCH_K = parseInt(__ENV.BATCH_K, 10);
const BASE_URL = __ENV.BASE_URL;
const SEED_BASE = __ENV.SEED_BASE ? parseInt(__ENV.SEED_BASE, 10) : 1000;

export const options = {
  vus: parseInt(__ENV.VUS, 10),
  duration: __ENV.DURATION,
  summaryTrendStats: ["avg", "min", "med", "max", "p(50)", "p(95)", "p(99)"],
};

// Total waktu utk seluruh batch (K resource) -- metrik utama studi ini.
const batchWallTime = new Trend("batch_wall_time");
const batchPayloadBytes = new Trend("batch_payload_bytes");

function restBatch() {
  const start = Date.now();
  let totalBytes = 0;
  let allOk = true;
  for (let i = 0; i < BATCH_K; i++) {
    // Seed berbeda per anggota batch -> K resource BERBEDA, bukan cache hit identik.
    const res = http.get(`${BASE_URL}/baseline?density=${DENSITY}&seed=${SEED_BASE + i}`);
    if (res.status !== 200) allOk = false;
    totalBytes += res.body ? res.body.length : 0;
  }
  const elapsed = Date.now() - start;
  return { elapsed, totalBytes, allOk };
}

function graphqlBatch() {
  // SATU dokumen kueri, K field beralias -- SATU round trip HTTP utk K resource.
  const fields = "{ image_id dimensions { width height } detections { class_label confidence_score bounding_box } }";
  const aliasedFields = [];
  for (let i = 0; i < BATCH_K; i++) {
    aliasedFields.push(`img${i}: image_detections(density:"${DENSITY}", seed:${SEED_BASE + i}) ${fields}`);
  }
  const query = `{ ${aliasedFields.join(" ")} }`;
  const start = Date.now();
  const res = http.post(`${BASE_URL}/graphql`, JSON.stringify({ query }), {
    headers: { "Content-Type": "application/json" },
  });
  const elapsed = Date.now() - start;
  let allOk = res.status === 200;
  if (allOk) {
    const body = JSON.parse(res.body);
    if (body.errors) allOk = false;
  }
  return { elapsed, totalBytes: res.body ? res.body.length : 0, allOk };
}

export default function () {
  const result = PROTOCOL === "rest" ? restBatch() : graphqlBatch();

  check(result, { "batch semua sukses": (r) => r.allOk });

  batchWallTime.add(result.elapsed);
  batchPayloadBytes.add(result.totalBytes);
}

export function handleSummary(data) {
  const out = {};
  out[__ENV.SUMMARY_FILE] = JSON.stringify(data);
  return out;
}
