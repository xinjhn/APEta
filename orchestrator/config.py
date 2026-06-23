"""
orchestrator/config.py
=======================
Knob terpusat untuk eksekusi eksperimen. Saat pindah ke VM, HANYA file/ENV ini
yang perlu diubah (POOL_JSON asli, N_MEASURED/RUN_DURATION final, ENABLE_PINNING,
SESSION_ID) -- skrip orchestrator lainnya tidak disentuh.

FAKTORIAL DESAIN (Path B):
- impl_mode_rest: "passthrough" | "typed" (kontrol via APE_IMPL_MODE_REST)
- impl_mode_graphql: "passthrough" | "typed" (kontrol via APE_IMPL_MODE_GRAPHQL)

Untuk replikasi hasil awal: rest=passthrough, graphql=typed
Untuk desain faktorial 2x2: jalankan 4 kombinasi berbeda.

Semua knob dibaca dari environment variable (prefix APE_) dengan default yang
masuk akal untuk mode PILOT lokal. Lintas-platform: ENABLE_PINNING hanya
berlaku di POSIX (taskset); di Windows selalu dilewati apa pun nilainya.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _env_list(name: str, default: List[str]) -> List[str]:
    val = os.environ.get(name)
    if val is None:
        return list(default)
    return [v.strip() for v in val.split(",") if v.strip()]


def _env_int_list(name: str, default: List[int]) -> List[int]:
    return [int(v) for v in _env_list(name, [str(d) for d in default])]


PROTOCOLS = ("rest", "graphql")  # KONSTAN -- bukan knob, jangan diubah per-VM


@dataclass
class Config:
    pool_json: str
    seed: int
    n_warmup: int
    n_measured: int
    run_duration: str
    concurrency_levels: List[int]
    densities: List[str]
    patterns: List[str]
    host: str
    port: int
    session_id: str
    results_dir: Path
    pilot: bool
    pilot_patterns: List[str]
    pilot_densities: List[str]
    pilot_concurrency: List[int]
    enable_pinning: bool
    server_cores: Optional[str]
    k6_cores: Optional[str]
    sampler_core: Optional[str]
    # Faktor implementasi untuk desain faktorial 2x2
    impl_mode_rest: str = "passthrough"
    impl_mode_graphql: str = "typed"

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def run_plan_csv(self) -> Path:
        return self.results_dir / "run_plan.csv"

    @property
    def results_csv(self) -> Path:
        return self.results_dir / "results.csv"

    @property
    def telemetry_dir(self) -> Path:
        return self.results_dir / "telemetry"

    @property
    def k6_summary_dir(self) -> Path:
        return self.results_dir / "k6_summaries"

    def active_patterns(self) -> List[str]:
        return self.pilot_patterns if self.pilot else self.patterns

    def active_densities(self) -> List[str]:
        return self.pilot_densities if self.pilot else self.densities

    def active_concurrency(self) -> List[int]:
        return self.pilot_concurrency if self.pilot else self.concurrency_levels

    def pinning_active(self) -> bool:
        """Pinning hanya valid di POSIX (taskset); Windows selalu dilewati."""
        return self.enable_pinning and os.name == "posix"


def get_config() -> Config:
    pilot = _env_bool("APE_PILOT", False)
    return Config(
        pool_json=os.environ.get("APE_POOL_JSON", str(PROJECT_ROOT / "scratch" / "synthetic.json")),
        seed=int(os.environ.get("APE_SEED", "42")),
        n_warmup=int(os.environ.get("APE_N_WARMUP", "1" if pilot else "3")),
        n_measured=int(os.environ.get("APE_N_MEASURED", "3" if pilot else "30")),
        run_duration=os.environ.get("APE_RUN_DURATION", "10s" if pilot else "30s"),
        concurrency_levels=_env_int_list("APE_CONCURRENCY_LEVELS", [1, 10, 50, 100]),
        densities=_env_list("APE_DENSITIES", ["low", "medium", "high"]),
        patterns=_env_list("APE_PATTERNS", ["baseline", "partial", "filtered", "aggregate"]),
        host=os.environ.get("APE_HOST", "127.0.0.1"),
        port=int(os.environ.get("APE_PORT", "8000")),
        session_id=os.environ.get("APE_SESSION_ID", "local-pilot"),
        results_dir=Path(os.environ.get("APE_RESULTS_DIR", str(PROJECT_ROOT / "results"))),
        pilot=pilot,
        pilot_patterns=_env_list("APE_PILOT_PATTERNS", ["baseline", "partial"]),
        pilot_densities=_env_list("APE_PILOT_DENSITIES", ["low", "high"]),
        pilot_concurrency=_env_int_list("APE_PILOT_CONCURRENCY", [1]),
        enable_pinning=_env_bool("APE_ENABLE_PINNING", False),
        server_cores=os.environ.get("APE_SERVER_CORES"),
        k6_cores=os.environ.get("APE_K6_CORES"),
        sampler_core=os.environ.get("APE_SAMPLER_CORE"),
        impl_mode_rest=os.environ.get("APE_IMPL_MODE_REST", "passthrough").lower(),
        impl_mode_graphql=os.environ.get("APE_IMPL_MODE_GRAPHQL", "typed").lower(),
    )
