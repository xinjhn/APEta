"""
orchestrator/config.py
=======================
Central knobs for the Phase 2 cache-vs-paradigm study. Replaces the retired
Path-B config (old factors: pattern/density/impl_mode against the in-memory
JSON pool) with the BUILD SPEC's factor grid against the relational corpus
(~/training/mot_detections.db) and the cache layer from Phase 2a.

Factors (BUILD SPEC Section 3):
    protocol        rest | graphql                          (constant tuple)
    caching         on | off
    access_pattern  unique | zipfian | uniform
    entropy         low | medium | high   (query-shape entropy)
    payload_weight  light | heavy
    network         lan | constrained
    density         low | medium | high   (only matters when payload_weight=light)
    concurrency     VUS levels

CORE GRID (spec Section 3: "core grid first... find the crossover, then
drill in"): protocol x caching x access_pattern x payload_weight, with
entropy/density/concurrency/network held at fixed "core" values. That's
2x2x3x2 = 24 cells -- the default `make_run_plan.py` output. Full-grid
drill-in (varying entropy/network/concurrency too) is available via
APE_GRID=full but is NOT the default (combinatorial cost) -- see
make_run_plan.py's build_full_grid_blocks().
"""
from __future__ import annotations

import os
from dataclasses import dataclass
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


PROTOCOLS = ("rest", "graphql")          # constant -- not a knob
CACHING_LEVELS = ("on", "off")           # constant -- not a knob
ACCESS_PATTERNS = ("unique", "zipfian", "uniform")
ENTROPY_LEVELS = ("low", "medium", "high")
PAYLOAD_WEIGHTS = ("light", "heavy")
NETWORK_PROFILES = ("lan", "constrained")
DENSITY_TIERS = ("low", "medium", "high")


@dataclass
class Config:
    db_path: str
    id_pool_json: str
    seed: int
    n_warmup: int
    n_measured: int
    run_duration: str
    grid: str  # "core" | "full"
    # Core-grid fixed values (used for the factors NOT varied in "core" mode)
    core_entropy: str
    core_density: str
    core_concurrency: int
    core_network: str
    # Full-grid drill-in axes (only consulted when grid == "full")
    entropy_levels: List[str]
    densities: List[str]
    concurrency_levels: List[int]
    network_profiles: List[str]
    # Round-trip-vs-cacheability arm (only consulted when grid == "batch") --
    # page/batch size K: REST issues K separate cacheable round trips,
    # GraphQL issues 1 composite round trip for the same K-id page. See
    # make_run_plan.py's build_batch_grid_blocks() and k6/workload.js's
    # PAGE_SIZE handling.
    page_sizes: List[int]
    host: str
    port: int
    varnish_port: int
    session_id: str
    results_dir: Path
    enable_pinning: bool
    server_cores: Optional[str]
    k6_cores: Optional[str]
    sampler_core: Optional[str]
    cpu_quota_pct: int     # systemd-run CPUQuota for the server, e.g. 400 = 4 cores (N6)
    memory_max_mb: int     # systemd-run MemoryMax for the server (N6)
    # Network-namespace topology (tools/netns_topology.sh) -- fixes the
    # netem-on-loopback double-delay threat (see tools/netem.sh's THREAT TO
    # VALIDITY note): server+varnish run INSIDE netns_name, reachable from
    # the root namespace (where k6 runs) via this one veth hop only. The
    # backend<->varnish hop stays on the namespace's own loopback, never
    # touching the delayed veth, so a cache MISS no longer pays the network
    # delay twice. This is now the only supported topology for real runs --
    # tools/netem.sh's whole-loopback approach is kept solely as a documented
    # historical artifact of the bug it had.
    netns_name: str
    netns_host_ip: str
    netns_ns_ip: str
    netns_veth_host: str
    netns_veth_ns: str
    run_as_user: str

    @property
    def base_url_direct(self) -> str:
        return f"http://{self.netns_ns_ip}:{self.port}"

    @property
    def base_url_cached(self) -> str:
        return f"http://{self.netns_ns_ip}:{self.varnish_port}"

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

    def pinning_active(self) -> bool:
        return self.enable_pinning and os.name == "posix"


def get_config() -> Config:
    grid = os.environ.get("APE_GRID", "core").lower()
    return Config(
        db_path=os.environ.get("APE_DB_PATH", "/home/ubuntu/training/mot_detections.db"),
        id_pool_json=os.environ.get("APE_ID_POOL_JSON", str(PROJECT_ROOT / "scratch" / "id_pool.json")),
        seed=int(os.environ.get("APE_SEED", "42")),
        n_warmup=int(os.environ.get("APE_N_WARMUP", "1")),
        n_measured=int(os.environ.get("APE_N_MEASURED", "30")),
        run_duration=os.environ.get("APE_RUN_DURATION", "20s"),
        grid=grid,
        core_entropy=os.environ.get("APE_CORE_ENTROPY", "medium"),
        core_density=os.environ.get("APE_CORE_DENSITY", "medium"),
        core_concurrency=int(os.environ.get("APE_CORE_CONCURRENCY", "10")),
        core_network=os.environ.get("APE_CORE_NETWORK", "constrained"),
        entropy_levels=_env_list("APE_ENTROPY_LEVELS", list(ENTROPY_LEVELS)),
        densities=_env_list("APE_DENSITIES", list(DENSITY_TIERS)),
        concurrency_levels=_env_int_list("APE_CONCURRENCY_LEVELS", [1, 10, 50]),
        network_profiles=_env_list("APE_NETWORK_PROFILES", list(NETWORK_PROFILES)),
        page_sizes=_env_int_list("APE_PAGE_SIZES", [1, 5, 10]),
        host=os.environ.get("APE_HOST", "127.0.0.1"),
        port=int(os.environ.get("APE_PORT", "8000")),
        varnish_port=int(os.environ.get("APE_VARNISH_PORT", "8080")),
        session_id=os.environ.get("APE_SESSION_ID", "local-pilot"),
        results_dir=Path(os.environ.get("APE_RESULTS_DIR", str(PROJECT_ROOT / "results" / "phase2"))),
        enable_pinning=_env_bool("APE_ENABLE_PINNING", False),
        server_cores=os.environ.get("APE_SERVER_CORES"),
        k6_cores=os.environ.get("APE_K6_CORES"),
        sampler_core=os.environ.get("APE_SAMPLER_CORE"),
        cpu_quota_pct=int(os.environ.get("APE_CPU_QUOTA_PCT", "400")),
        memory_max_mb=int(os.environ.get("APE_MEMORY_MAX_MB", "2048")),
        netns_name=os.environ.get("APE_NETNS_NAME", "ape-origin"),
        netns_host_ip=os.environ.get("APE_NETNS_HOST_IP", "10.200.0.1"),
        netns_ns_ip=os.environ.get("APE_NETNS_NS_IP", "10.200.0.2"),
        netns_veth_host=os.environ.get("APE_NETNS_VETH_HOST", "veth-ape-h"),
        netns_veth_ns=os.environ.get("APE_NETNS_VETH_NS", "veth-ape-n"),
        run_as_user=os.environ.get("APE_RUN_AS_USER", os.environ.get("USER", "ubuntu")),
    )
