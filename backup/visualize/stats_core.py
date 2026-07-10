"""
analysis/stats_core.py
======================
Implementasi uji yang tidak tersedia di SciPy: Cliff's delta dan Jonckheere-
Terpstra. Yang tersedia di SciPy dipakai langsung (Mann-Whitney U, Shapiro-Wilk,
Kruskal-Wallis, Benjamini-Hochberg via false_discovery_control).

RUJUKAN (sumber-asli metode = sitasi pendiri; pelengkap terkini ditandai):
- Cliff's delta          : N. Cliff (1993), Psychological Bulletin 114(3).
  Ambang interpretasi    : J. Romano et al. (2006).
  Pelengkap terkini      : Meissel & Yao (2024), web app & R tutorial Cliff's d;
                            Macbeth et al. (2011), Cliff's delta calculator.
  Praktik standar CS     : digunakan luas pada studi empiris 2022-2024 (mis.
                            arXiv:2205.01842, 2209.14057) bersama Mann-Whitney U.
- Jonckheere-Terpstra    : A. R. Jonckheere (1954), Biometrika 41; T. J. Terpstra
                            (1952), Indagationes Mathematicae 14.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

import numpy as np
from scipy.stats import norm


# --------------------------------------------------------------------------- #
# Cliff's delta
# --------------------------------------------------------------------------- #
# Ambang Romano et al. (2006), konvensi yang dipakai luas di riset empiris CS.
_CLIFF_THRESHOLDS = ((0.147, "negligible"), (0.330, "small"), (0.474, "medium"))


def interpret_cliffs(delta: float) -> str:
    """Mengklasifikasikan |delta| menurut Romano et al. (2006)."""
    a = abs(delta)
    for thr, label in _CLIFF_THRESHOLDS:
        if a < thr:
            return label
    return "large"


def cliffs_delta(x: Sequence[float], y: Sequence[float]) -> float:
    """Cliff's delta = P(x>y) - P(x<y), rentang [-1, 1].

    delta > 0  -> nilai x cenderung LEBIH BESAR dari y.
    Mengikuti definisi dominance (Cliff, 1993). Penanganan ties: sign(0)=0.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.size == 0 or y.size == 0:
        return float("nan")
    diff = np.sign(x[:, None] - y[None, :])  # +1 / 0 / -1
    return float(diff.sum() / (x.size * y.size))


# --------------------------------------------------------------------------- #
# Jonckheere-Terpstra (aproksimasi normal, uji tren terurut)
# --------------------------------------------------------------------------- #
@dataclass
class JTResult:
    J: float            # statistik Jonckheere-Terpstra
    z: float            # statistik terstandar
    p_two_sided: float  # p-value dua sisi (tren naik ATAU turun)
    direction: str      # "increasing" / "decreasing" / "none"
    n_total: int
    k_groups: int


def _mann_whitney_count(a: np.ndarray, b: np.ndarray) -> float:
    """Hitung U_{ab} = jumlah pasangan (i in a, j in b) dengan b_j > a_i,
    plus 0.5 untuk ties. Vektorisasi penuh."""
    d = b[None, :] - a[:, None]
    return float((d > 0).sum() + 0.5 * (d == 0).sum())


def jonckheere_terpstra(groups_in_order: Sequence[Sequence[float]]) -> JTResult:
    """Uji tren Jonckheere-Terpstra untuk k kelompok TERURUT.

    groups_in_order: daftar array, sudah disusun menurut urutan faktor yang diuji
    (mis. [low, medium, high] atau [10, 50, 100] VUs).

    Hipotesis: ada tren MONOTONIK pada lokasi distribusi lintas urutan kelompok.
    Karena arah tren tidak diasumsikan a priori (latensi bisa naik ATAU turun
    terhadap densitas), p-value dilaporkan DUA SISI; arah ditunjukkan via tanda z.

    Aproksimasi normal (Jonckheere, 1954; Terpstra, 1952). Varians memakai formula
    tanpa-ties; untuk metrik kontinu (latency/throughput) ties sangat jarang.
    Bila satu metrik banyak ties (mis. count integer), pertimbangkan uji permutasi.
    """
    groups = [np.asarray(g, dtype=float) for g in groups_in_order]
    groups = [g for g in groups if g.size > 0]
    k = len(groups)
    if k < 2:
        return JTResult(float("nan"), float("nan"), float("nan"), "none", 0, k)

    ns = np.array([g.size for g in groups], dtype=float)
    N = float(ns.sum())

    # Statistik J = sum_{u<v} U_{uv} (hitungan v > u)
    J = 0.0
    for u in range(k):
        for v in range(u + 1, k):
            J += _mann_whitney_count(groups[u], groups[v])

    mu = (N**2 - np.sum(ns**2)) / 4.0
    var = (N**2 * (2 * N + 3) - np.sum(ns**2 * (2 * ns + 3))) / 72.0

    if var <= 0:
        return JTResult(J, float("nan"), float("nan"), "none", int(N), k)

    z = (J - mu) / np.sqrt(var)
    p = 2.0 * norm.sf(abs(z))
    direction = "increasing" if z > 0 else "decreasing" if z < 0 else "none"
    return JTResult(float(J), float(z), float(p), direction, int(N), k)
