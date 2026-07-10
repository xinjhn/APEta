"""
analysis/analyze.py
===================
Pipeline analisis statistik (Tahap [I]) yang mengubah results.csv menjadi temuan.
Mengikuti rencana di laporan Subbab III.7 dan matriks justifikasi metodologis.

Alur (tiap langkah ber-rujukan; sumber-asli metode = sitasi pendiri):
  1. Shapiro-Wilk (1965)              -> cek normalitas; justifikasi non-parametrik.
  2. Mann-Whitney U (1947) + Cliff's  -> REST vs GraphQL per sel + effect size
     delta (Cliff 1993; ambang Romano    (signifikansi statistik + praktis).
     et al. 2006).
  3. Benjamini-Hochberg (1995) FDR    -> koreksi perbandingan ganda (q=0.05).
  4. Jonckheere-Terpstra (1954/1952)  -> tren monotonik lintas densitas & konkurensi
     + Cliff's delta per level           (operasionalisasi: tren PER-PROTOKOL yang
                                          tak terkonfound + evolusi effect size gap).
  5. Kruskal-Wallis (1952)            -> uji efek antar-sesi (session_id).

CATATAN OPERASIONALISASI TREN (untuk dikonfirmasi ke pembimbing/laporan):
Karena run REST & GraphQL bersifat INDEPENDEN (tak berpasangan), "tren gap" tidak
bisa diuji JT tunggal pada selisih berpasangan. Maka gap-moderation dibaca dari
KOMBINASI: (a) JT tren tiap protokol secara terpisah (tak terkonfound faktor lain),
dan (b) Cliff's delta REST-vs-GraphQL pada tiap level untuk melihat gap membesar/
mengecil. Ini operasionalisasi yang defensible; alternatif (ART-ANOVA interaksi)
bisa didiskusikan bila ingin satu uji interaksi langsung.

Pakai:
    python analysis/analyze.py --results results/results.csv --out results/analysis
"""
from __future__ import annotations

import argparse
import os
from typing import Dict, List

import numpy as np
import pandas as pd
from scipy.stats import false_discovery_control, kruskal, mannwhitneyu, shapiro

from stats_core import cliffs_delta, interpret_cliffs, jonckheere_terpstra

# --- Metrik & arah "lebih baik" ------------------------------------------------
# lower_is_better: latensi, payload, waktu proses, CPU, memori. throughput: higher.
METRICS = {
    "lat_p95": "lower",
    "lat_p50": "lower",
    "lat_p99": "lower",
    "throughput_rps": "higher",
    "payload_bytes_med": "lower",
    "xproc_p95": "lower",
    "xproc_med": "lower",
    "cpu_mean": "lower",
    "rss_mean_mb": "lower",
}
PRIMARY = ["lat_p95", "throughput_rps", "payload_bytes_med", "xproc_p95"]

DENSITY_ORDER = ["low", "medium", "high"]
ALPHA = 0.05


# --------------------------------------------------------------------------- #
def _clean(df: pd.DataFrame) -> pd.DataFrame:
    for m in METRICS:
        if m in df.columns:
            df[m] = pd.to_numeric(df[m], errors="coerce")
    if "concurrency" in df.columns:
        df["concurrency"] = pd.to_numeric(df["concurrency"], errors="coerce")
    return df


# --- 1. Normalitas -------------------------------------------------------------
def normality(df: pd.DataFrame, metrics: List[str]) -> pd.DataFrame:
    rows = []
    keys = ["protocol", "pattern", "density", "concurrency"]
    for m in metrics:
        for key, g in df.groupby(keys):
            vals = g[m].dropna().values
            if len(vals) >= 3 and np.ptp(vals) > 0:
                stat, p = shapiro(vals)
                rows.append(dict(zip(keys, key)) | {
                    "metric": m, "n": len(vals), "shapiro_p": p,
                    "non_normal": bool(p < ALPHA)})
    return pd.DataFrame(rows)


# --- 2-3. Pairwise REST vs GraphQL + BH ---------------------------------------
def pairwise(df: pd.DataFrame, metrics: List[str]) -> pd.DataFrame:
    rows = []
    keys = ["pattern", "density", "concurrency"]
    for m in metrics:
        for key, g in df.groupby(keys):
            r = g[g.protocol == "rest"][m].dropna().values
            q = g[g.protocol == "graphql"][m].dropna().values
            if len(r) < 3 or len(q) < 3:
                continue
            try:
                U, p = mannwhitneyu(r, q, alternative="two-sided")
            except ValueError:
                U, p = np.nan, np.nan
            d = cliffs_delta(r, q)  # >0 -> REST lebih besar
            better = _better(m, np.median(r), np.median(q))
            rows.append(dict(zip(keys, key)) | {
                "metric": m, "n_rest": len(r), "n_graphql": len(q),
                "median_rest": float(np.median(r)),
                "median_graphql": float(np.median(q)),
                "mwu_U": float(U), "p_raw": float(p),
                "cliffs_delta": d, "magnitude": interpret_cliffs(d),
                "favored": better})
    out = pd.DataFrame(rows)
    # BH-FDR per METRIK (tiap metrik = satu keluarga hipotesis terkait)
    out["p_bh"] = np.nan
    for m, idx in out.groupby("metric").groups.items():
        ps = out.loc[idx, "p_raw"].values
        mask = ~np.isnan(ps)
        if mask.sum() > 0:
            adj = np.full(len(ps), np.nan)
            adj[mask] = false_discovery_control(ps[mask], method="bh")
            out.loc[idx, "p_bh"] = adj
    out["significant_bh"] = out["p_bh"] < ALPHA
    return out


def _better(metric: str, med_rest: float, med_gql: float) -> str:
    if med_rest == med_gql:
        return "tie"
    rest_smaller = med_rest < med_gql
    if METRICS[metric] == "lower":
        return "rest" if rest_smaller else "graphql"
    return "graphql" if rest_smaller else "rest"


# --- 4. Tren Jonckheere-Terpstra (tak terkonfound) + gap per level ------------
def trend(df: pd.DataFrame, metrics: List[str], factor: str) -> pd.DataFrame:
    """factor='density' -> tren lintas densitas (tiap level konkurensi, terpisah).
       factor='concurrency' -> tren lintas konkurensi (tiap level densitas)."""
    if factor == "density":
        order, hold = DENSITY_ORDER, "concurrency"
    else:
        order = sorted(df["concurrency"].dropna().unique())
        hold = "density"
    rows = []
    for m in metrics:
        for pattern, gp in df.groupby("pattern"):
            for hold_val, gh in gp.groupby(hold):
                # per-protokol JT (tren monotonik tiap protokol)
                jt = {}
                for proto in ("rest", "graphql"):
                    groups = [gh[(gh.protocol == proto) & (gh[factor] == lvl)][m]
                              .dropna().values for lvl in order]
                    jt[proto] = jonckheere_terpstra(groups)
                # Cliff's delta gap (REST vs GraphQL) per level -> evolusi gap
                deltas = {}
                for lvl in order:
                    r = gh[(gh.protocol == "rest") & (gh[factor] == lvl)][m].dropna().values
                    q = gh[(gh.protocol == "graphql") & (gh[factor] == lvl)][m].dropna().values
                    deltas[str(lvl)] = cliffs_delta(r, q) if len(r) and len(q) else np.nan
                rows.append({
                    "metric": m, "pattern": pattern, hold: hold_val,
                    "rest_JT_z": jt["rest"].z, "rest_JT_p": jt["rest"].p_two_sided,
                    "rest_trend": jt["rest"].direction,
                    "graphql_JT_z": jt["graphql"].z, "graphql_JT_p": jt["graphql"].p_two_sided,
                    "graphql_trend": jt["graphql"].direction,
                    **{f"gap_delta_{lvl}": deltas[str(lvl)] for lvl in order},
                })
    return pd.DataFrame(rows)


# --- 5. Efek antar-sesi (Kruskal-Wallis) --------------------------------------
def session_effect(df: pd.DataFrame, metrics: List[str]) -> pd.DataFrame:
    rows = []
    keys = ["protocol", "pattern", "density", "concurrency"]
    if "session_id" not in df.columns or df["session_id"].nunique() < 2:
        return pd.DataFrame(rows)
    for m in metrics:
        for key, g in df.groupby(keys):
            sgroups = [s[m].dropna().values for _, s in g.groupby("session_id")]
            sgroups = [s for s in sgroups if len(s) >= 2]
            if len(sgroups) >= 2:
                try:
                    H, p = kruskal(*sgroups)
                    rows.append(dict(zip(keys, key)) | {
                        "metric": m, "n_sessions": len(sgroups),
                        "kw_H": float(H), "p_raw": float(p)})
                except ValueError:
                    pass
    out = pd.DataFrame(rows)
    if not out.empty:
        ps = out["p_raw"].values
        mask = ~np.isnan(ps)
        adj = np.full(len(ps), np.nan)
        if mask.sum() > 0:
            adj[mask] = false_discovery_control(ps[mask], method="bh")
        out["p_bh"] = adj
        out["session_bias"] = out["p_bh"] < ALPHA
    return out


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", default="results/analysis")
    ap.add_argument("--all-metrics", action="store_true",
                    help="analisis semua metrik (default: primer saja)")
    args = ap.parse_args()

    metrics = list(METRICS) if args.all_metrics else PRIMARY
    df = _clean(pd.read_csv(args.results))
    metrics = [m for m in metrics if m in df.columns]
    os.makedirs(args.out, exist_ok=True)

    norm_df = normality(df, metrics)
    pair_df = pairwise(df, metrics)
    td = trend(df, metrics, "density")
    tc = trend(df, metrics, "concurrency")
    sess = session_effect(df, metrics)

    norm_df.to_csv(f"{args.out}/normality.csv", index=False)
    pair_df.to_csv(f"{args.out}/pairwise_rest_vs_graphql.csv", index=False)
    td.to_csv(f"{args.out}/trend_density.csv", index=False)
    tc.to_csv(f"{args.out}/trend_concurrency.csv", index=False)
    if not sess.empty:
        sess.to_csv(f"{args.out}/session_effect.csv", index=False)

    _write_summary(args.out, df, norm_df, pair_df, td, tc, sess, metrics)
    print(f"Analisis selesai -> {args.out}/")
    _print_console(norm_df, pair_df, sess)


def _print_console(norm_df, pair_df, sess):
    if not norm_df.empty:
        nn = norm_df["non_normal"].mean() * 100
        print(f"  Normalitas: {nn:.0f}% grup non-normal (p<0.05) -> non-parametrik tepat.")
    if not pair_df.empty:
        sig = pair_df["significant_bh"].sum()
        print(f"  Pairwise: {sig}/{len(pair_df)} perbandingan signifikan setelah BH.")
    if sess is not None and not sess.empty:
        sb = sess["session_bias"].sum()
        print(f"  Efek sesi: {sb}/{len(sess)} sel menunjukkan bias sesi setelah BH.")


def _write_summary(out, df, norm_df, pair_df, td, tc, sess, metrics):
    L = ["# Ringkasan Analisis Statistik\n"]
    L.append(f"- Total run terukur: {len(df)} | metrik dianalisis: {', '.join(metrics)}\n")
    if not norm_df.empty:
        L.append(f"## Normalitas (Shapiro-Wilk)\n"
                 f"{norm_df['non_normal'].mean()*100:.1f}% grup non-normal (p<0.05) "
                 f"-> mendukung pemilihan uji non-parametrik (lih. III.7).\n")
    if not pair_df.empty:
        L.append("## REST vs GraphQL (Mann-Whitney U + Cliff's delta, pasca BH-FDR)\n")
        for m in metrics:
            sub = pair_df[pair_df.metric == m]
            if sub.empty:
                continue
            sig = sub[sub.significant_bh]
            L.append(f"- **{m}**: {len(sig)}/{len(sub)} sel signifikan (BH). "
                     f"Favored: REST={int((sub.favored=='rest').sum())}, "
                     f"GraphQL={int((sub.favored=='graphql').sum())}. "
                     f"Effect size non-negligible: "
                     f"{int((sub.magnitude!='negligible').sum())} sel.\n")
    if sess is not None and not sess.empty:
        L.append(f"## Efek antar-sesi (Kruskal-Wallis)\n"
                 f"{sess['session_bias'].sum()}/{len(sess)} sel menunjukkan perbedaan "
                 f"antar-sesi signifikan (BH). Idealnya rendah -> tidak ada bias sesi "
                 f"sistematis (validitas multi-sesi terjaga).\n")
    L.append("## Tren (Jonckheere-Terpstra)\n"
             "Lihat trend_density.csv & trend_concurrency.csv: kolom rest_trend/"
             "graphql_trend (arah monotonik tiap protokol) + gap_delta_* (evolusi "
             "Cliff's delta gap lintas level). Gap-moderation dibaca dari kombinasi "
             "keduanya.\n")
    with open(f"{out}/ANALYSIS_SUMMARY.md", "w", encoding="utf-8") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    main()
