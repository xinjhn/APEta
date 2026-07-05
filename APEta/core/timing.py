"""
core/timing.py
==============
Middleware pengukur server-side processing time, dipasang IDENTIK di kedua server.

Mekanisme (PANDUAN Bagian 7):
- Catat perf_counter() di awal & akhir penanganan request.
- Tulis selisihnya ke response header X-Process-Time (detik, presisi tinggi).
- k6 membaca header itu -> memisahkan waktu proses murni dari waktu transfer.
- TIDAK menulis log per-request ke file (menghindari observer effect / I/O).

Fairness (penting untuk laporan III.2.2):
Middleware ini membungkus SELURUH penanganan HTTP request. Untuk REST ia
mencakup route-match + handler; untuk GraphQL ia mencakup parse AST + validasi
+ eksekusi resolver. Isi yang berbeda itu justru TREATMENT yang diukur, bukan
bias -- overhead middleware itu sendiri sangat kecil dan SIMETRIS di kedua sisi.
"""
from __future__ import annotations

import time

from starlette.types import ASGIApp

from .config import PROCESS_TIME_HEADER


def add_process_time_middleware(app: ASGIApp) -> None:
    """Memasang middleware X-Process-Time pada aplikasi FastAPI/Starlette."""

    @app.middleware("http")
    async def _process_time(request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        # detik dengan presisi mikro; format konsisten agar mudah diparse k6
        response.headers[PROCESS_TIME_HEADER] = f"{elapsed:.6f}"
        return response
