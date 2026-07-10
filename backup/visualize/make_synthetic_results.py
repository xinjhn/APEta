"""
analysis/make_synthetic_results.py
==================================
HANYA untuk MENGUJI pipeline analisis. Menyuntik efek yang DIKETAHUI agar bisa
diverifikasi apakah analisis mendeteksinya dengan benar:
  - GraphQL latensi > REST, dengan GAP MEMBESAR seiring densitas & konkurensi
    (menguji deteksi tren/moderation).
  - payload GraphQL = REST + ~30 byte (gap kecil KONSTAN; tak membesar).
  - throughput GraphQL < REST.
  - session_id diacak -> TIDAK ada efek sesi (KW harus mayoritas tak signifikan).
Distribusi latency dibuat right-skewed (lognormal) -> Shapiro-Wilk harus menandai
non-normal.
"""
import csv, random, numpy as np

rng = np.random.default_rng(42)
PATTERNS = ["baseline", "partial", "filtered", "aggregate"]
DENS = {"low": 0, "medium": 1, "high": 2}
CONC = [10, 50, 100]
SESSIONS = ["s1", "s2", "s3"]
N = 30

dens_mult = {0: 1.0, 1: 1.3, 2: 1.8}
conc_mult = {10: 1.0, 50: 1.5, 100: 2.2}
patt_mult = {"baseline": 1.0, "partial": 0.7, "filtered": 0.8, "aggregate": 0.5}
patt_payload = {"baseline": 1.0, "partial": 0.56, "filtered": 0.6, "aggregate": 0.04}
base_payload = {0: 3000, 1: 8000, 2: 18000}

rows = []
for pattern in PATTERNS:
    for dname, didx in DENS.items():
        for conc in CONC:
            gap = 0.04 + 0.05 * didx + 0.04 * CONC.index(conc)  # membesar
            base_lat = 15 * dens_mult[didx] * conc_mult[conc] * patt_mult[pattern]
            for proto in ("rest", "graphql"):
                mult = (1 + gap) if proto == "graphql" else 1.0
                for run in range(N):
                    mean_lat = base_lat * mult
                    p50 = float(rng.lognormal(np.log(mean_lat), 0.18))
                    p95 = p50 * float(rng.uniform(1.2, 1.4))
                    p99 = p95 * float(rng.uniform(1.1, 1.3))
                    thr = conc / (p50 / 1000.0) * float(rng.uniform(0.95, 1.05))
                    payload = base_payload[didx] * patt_payload[pattern] * float(rng.normal(1.0, 0.12))  # variansi sampling citra acak
                    if proto == "graphql" and pattern != "aggregate":
                        payload += 30  # amplop konstan
                    xproc95 = p95 * 0.6 / 1000.0
                    rows.append({
                        "run_uid": f"{pattern[:2]}{dname[:1]}{conc}{proto[:1]}{run:02d}",
                        "block_id": f"{pattern}-{dname}-{conc}-{proto}",
                        "protocol": proto, "pattern": pattern, "density": dname,
                        "concurrency": conc, "run_index": run,
                        "session_id": SESSIONS[rng.integers(0, 3)],
                        "ts_start": 0, "ts_end": 0,
                        "lat_p50": round(p50, 4), "lat_p95": round(p95, 4),
                        "lat_p99": round(p99, 4), "throughput_rps": round(thr, 2),
                        "payload_bytes_med": int(payload),
                        "xproc_p95": round(xproc95, 6), "xproc_med": round(xproc95 * 0.8, 6),
                        "error_rate": 0,
                        "cpu_mean": round(min(100, 40 + 20 * CONC.index(conc) + rng.normal(0, 3)), 2),
                        "cpu_p95": round(min(105, 45 + 22 * CONC.index(conc)), 2),
                        "rss_mean_mb": round(400 + rng.normal(0, 5), 2),
                        "rss_p95_mb": round(405 + rng.normal(0, 5), 2),
                        "k6_iterations": int(thr * 60), "notes": "",
                    })

with open("results_synth.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print(f"Ditulis {len(rows)} baris ke results_synth.csv "
      f"({len(PATTERNS)*3*3*2} sel x {N} run)")
