"""
orchestrator/run_experiment.py
================================
Executor: run_plan.csv -> results.csv for the Phase 2 cache-vs-paradigm
study. Replaces the retired Path-B executor (old block = protocol x pattern
x density x concurrency against the in-memory JSON pool; no cache layer, no
network emulation).

Per-block flow:
1. If this block's protocol differs from the live server (or none is up):
   stop old server, wait for the port to free, start new server under
   systemd-run with fixed CPU/memory caps (N6), wait for /health 200.
2. If this block's caching level differs from the live cache state: start or
   stop Varnish (cache/varnish.vcl) fronting the server on the cache port.
3. If this block's network profile differs from the currently applied
   tc/netem profile: reapply via tools/netem.sh (needs sudo).
4. Start the telemetry sampler (telemetry/sampler.py, unchanged from Phase 1/
   the retired study -- protocol-agnostic, samples by PID).
5. Run N_WARMUP k6 workload.js executions -> discarded (not written to
   results.csv).
6. Run measured executions not yet in results.csv -> append one row each.
7. Stop the sampler at the end of the block.

RESUME: identical contract to the retired executor -- a block whose measured
rows are all already in results.csv is skipped entirely; the first block
with missing measured rows gets its warmup re-run (server assumed cold after
a session restart); later blocks proceed normally.

Process-management primitives (kill_tree, wait_port_free, wait_health,
find_listening_pid, the PID-registry/lock-file pattern) are carried over
from the retired executor essentially unchanged -- that machinery is
protocol/factor-agnostic and was already correct.

Subcommands:
    python orchestrator/run_experiment.py                 # execute (default)
    python orchestrator/run_experiment.py --preflight      # readiness check
    python orchestrator/run_experiment.py --status         # progress report
"""
from __future__ import annotations

import argparse
import atexit
import csv
import json
import math
import os
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.config import Config, get_config  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent

RESULTS_FIELDNAMES = [
    "run_uid", "block_id",
    "protocol", "caching", "access_pattern", "entropy", "payload_weight",
    "network", "density", "concurrency", "page_size",
    "scenario", "tier", "rate_label", "backend",
    "run_index", "session_id", "ts_start", "ts_end",
    "lat_p50", "lat_p95", "lat_p99",
    "throughput_rps",
    "payload_bytes_med",
    "cache_hit_rate",
    "round_trip_count",
    "page_latency_med",
    "error_rate",
    "apq_registrations",
    "cpu_mean", "cpu_p95", "rss_mean_mb", "rss_p95_mb",
    "k6_iterations", "dropped_iterations", "notes",
]
# round_trip_count is a real per-row value, not always constant: for
# core/full grid blocks (page_size=0, "not in page mode") it's 1 -- every
# block there issues ONE logical request per k6 iteration on BOTH protocols.
# For the batch grid (APE_GRID=batch, page_size>0 -- the round-trip-vs-
# cacheability arm, k6/workload.js's PAGE_SIZE handling), it's the page size
# K for REST (K separate, independently-cacheable round trips) and 1 for
# GraphQL (one composite round trip via the images(ids) field). See
# page_latency_med for the actual page-render-time comparison that pairs
# with this -- req_latency/lat_p* still describe individual HTTP calls.

_FACTOR_KEYS = (
    "protocol", "caching", "access_pattern", "entropy",
    "payload_weight", "network", "density", "concurrency", "page_size",
    "scenario", "tier", "rate_label", "backend",
)


# --- Plan & results loading -----------------------------------------------------

def load_plan(path: Path) -> List[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["block_order"] = int(r["block_order"])
        r["concurrency"] = int(r["concurrency"])
        r["run_index"] = int(r["run_index"])
        r["is_warmup"] = bool(int(r["is_warmup"]))
        # Backward compatibility: run_plan.csv files written before the
        # batch grid (page_size factor) was added don't have this column --
        # e.g. the entropy/density drill-in sessions already running when
        # this was added. Treat a missing column as "not in page mode",
        # consistent with build_core_grid_blocks()/build_full_grid_blocks()'s
        # explicit page_size=0 for the same case.
        if "page_size" not in r or r["page_size"] in (None, ""):
            r["page_size"] = "0"
        # Same backward compatibility for the MOT scenario columns: plans
        # written before grid=mot existed (core/full/batch sessions) don't
        # have them -- default to "not a mot row" values.
        for key, default in (("scenario", ""), ("tier", ""),
                              ("rate_label", ""), ("backend", "sqlite")):
            if r.get(key) in (None, ""):
                r[key] = default
    return rows


def group_blocks(rows: List[dict]) -> List[dict]:
    blocks: Dict[int, dict] = {}
    order: List[int] = []
    for r in rows:
        bo = r["block_order"]
        if bo not in blocks:
            blocks[bo] = {"block_order": bo, "block_id": r["block_id"],
                           "warmup_rows": [], "measured_rows": []}
            blocks[bo].update({k: r[k] for k in _FACTOR_KEYS})
            order.append(bo)
        (blocks[bo]["warmup_rows"] if r["is_warmup"] else blocks[bo]["measured_rows"]).append(r)
    return [blocks[bo] for bo in order]


def load_done_uids(results_csv: Path) -> set:
    if not results_csv.exists():
        return set()
    with open(results_csv, newline="", encoding="utf-8") as f:
        return {r["run_uid"] for r in csv.DictReader(f)}


def find_resume_index(blocks: List[dict], done_uids: set) -> int:
    for i, block in enumerate(blocks):
        uids = {r["run_uid"] for r in block["measured_rows"]}
        if not uids.issubset(done_uids):
            return i
    return len(blocks)


# --- Cross-platform process management (carried over from Phase 1 design) -------

def popen_kwargs_for_group() -> dict:
    if os.name == "posix":
        return {"start_new_session": True}
    return {}


def wait_port_free(host: str, port: int, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            try:
                s.connect((host, port))
            except OSError:
                return
        time.sleep(0.3)
    raise TimeoutError(f"Port {host}:{port} did not free up within {timeout}s")


def wait_health(base_url: str, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=1) as resp:
                if resp.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001
            last_err = exc
        time.sleep(0.3)
    raise TimeoutError(f"Server did not become healthy within {timeout}s ({base_url}/health): {last_err}")


def find_listening_pid(port: int, timeout: float = 5.0) -> Optional[int]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            for conn in psutil.net_connections(kind="tcp"):
                if conn.status == "LISTEN" and conn.laddr and conn.laddr.port == port:
                    return conn.pid
        except (psutil.AccessDenied, PermissionError):
            break
        time.sleep(0.2)
    return None


def kill_tree(pid: int) -> None:
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return
    children = proc.children(recursive=True)
    for c in children:
        try:
            c.terminate()
        except psutil.NoSuchProcess:
            pass
    try:
        proc.terminate()
    except psutil.NoSuchProcess:
        pass
    gone, alive = psutil.wait_procs(children + [proc], timeout=5)
    for p in alive:
        try:
            p.kill()
        except psutil.NoSuchProcess:
            pass


def kill_tree_privileged(pid: int) -> None:
    """Like kill_tree, but signals via `sudo kill` instead of psutil's
    direct terminate()/kill(). Needed for process trees spawned through
    netns_exec_prefix()'s `sudo ip netns exec ... runuser -u <user> -- ...`
    wrapper: the outer layers (sudo itself, ip netns exec, runuser before it
    drops privilege) are root-owned, and this orchestrator runs as an
    unprivileged user -- psutil's terminate()/kill() on those PIDs raises
    PermissionError (caught live: it killed the orchestrator itself with an
    unhandled exception mid-run). Reading the tree (children(), enumeration)
    doesn't need privilege, only sending the signal does, so enumeration
    still goes through psutil and only the signal goes through sudo."""
    try:
        proc = psutil.Process(pid)
        pids = [pid] + [c.pid for c in proc.children(recursive=True)]
    except psutil.NoSuchProcess:
        return
    if not pids:
        return
    subprocess.run(["sudo", "kill", "-TERM"] + [str(p) for p in pids],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 5
    while time.time() < deadline:
        if not any(psutil.pid_exists(p) for p in pids):
            return
        time.sleep(0.2)
    alive = [p for p in pids if psutil.pid_exists(p)]
    if alive:
        subprocess.run(["sudo", "kill", "-KILL"] + [str(p) for p in alive],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _lock_path(cfg: Config) -> Path:
    return cfg.results_dir / ".locks" / "orchestrator.lock"


def acquire_orchestrator_lock(cfg: Config) -> None:
    path = _lock_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            info = json.loads(path.read_text(encoding="utf-8"))
            if psutil.pid_exists(info.get("pid", -1)):
                raise RuntimeError(f"Another orchestrator (pid={info.get('pid')}) appears to be running. "
                                    f"Stop it first or remove {path} if stale.")
        except (json.JSONDecodeError, OSError):
            pass
    path.write_text(json.dumps({"pid": os.getpid(), "start_ts": time.time(),
                                 "session_id": cfg.session_id}), encoding="utf-8")


def release_orchestrator_lock(cfg: Config) -> None:
    _lock_path(cfg).unlink(missing_ok=True)


def clean_results_tail(results_csv: Path) -> None:
    """Tolerate a hard-kill mid-write of the last results.csv row: if the
    last line lacks a trailing newline OR has the wrong column count, drop
    it -- the resume logic will simply re-run that uid, nothing is lost."""
    if not results_csv.exists():
        return
    with open(results_csv, newline="", encoding="utf-8") as f:
        text = f.read()
    if not text:
        return
    lines = text.splitlines()
    if len(lines) <= 1:
        return
    ends_with_newline = text.endswith("\n")
    header_cols = len(next(csv.reader([lines[0]])))
    try:
        last_cols = len(next(csv.reader([lines[-1]])))
    except (csv.Error, StopIteration):
        last_cols = -1
    if ends_with_newline and last_cols == header_cols:
        return
    print("  [resume] last results.csv row malformed -> dropped (hard-kill mid-write)")
    cleaned = lines[:-1]
    new_text = ("\n".join(cleaned) + "\n") if cleaned else ""
    with open(results_csv, "w", newline="", encoding="utf-8") as f:
        f.write(new_text)


# --- Server / cache / network lifecycle -----------------------------------------
#
# Server and Varnish run INSIDE cfg.netns_name (tools/netns_topology.sh),
# reachable from the root namespace (where k6/this orchestrator run) via one
# veth hop. This is what fixes the netem-on-loopback double-delay threat
# (tools/netem.sh's old THREAT TO VALIDITY note): the veth is the only thing
# tc/netem touches, and the backend<->varnish hop stays on the namespace's
# OWN loopback, never crossing it. Measured before/after the fix: a cache
# MISS through Varnish under `constrained` went from ~2x direct latency to
# ~1x (see tools/netns_topology.sh's header comment for the numbers).
#
# `ip netns exec` only isolates the NETWORK namespace, not PID -- the whole
# process tree (sudo -> ip netns exec -> runuser -> systemd-run -> uvicorn)
# stays visible to psutil from the root namespace. What's NOT visible from
# root is the namespaced process's SOCKETS (psutil.net_connections() only
# sees the calling process's own netns) -- that's why find_listening_pid()
# can't locate the server here; find_server_pid_in_tree() below walks the
# process tree by cmdline match instead.

NETNS_TOPOLOGY_SH = PROJECT_ROOT / "tools" / "netns_topology.sh"


def netns_exec_prefix(cfg: Config, with_systemd_user_env: bool = False) -> List[str]:
    prefix = ["sudo", "ip", "netns", "exec", cfg.netns_name, "runuser", "-u", cfg.run_as_user, "--"]
    if with_systemd_user_env:
        # `runuser` doesn't replicate a full login session, so systemd-run
        # --user can't find the user's DBus session bus unless these are
        # passed explicitly (confirmed by reproducing "Failed to connect to
        # bus: No medium found" without them during topology verification).
        uid = subprocess.run(["id", "-u", cfg.run_as_user], capture_output=True, text=True).stdout.strip()
        prefix += ["env", f"XDG_RUNTIME_DIR=/run/user/{uid}",
                   f"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus"]
    return prefix


# Wrapper binaries in the netns_exec_prefix()/start_server() chain (sudo,
# ip netns exec, runuser, env, systemd-run) -- their OWN cmdline contains the
# full nested command they're about to launch, INCLUDING module_marker, since
# it's literally the argv they were invoked with. A naive substring match
# against the whole tree finds the outermost wrapper (sudo, since it's
# `root` itself and checked first) instead of the actual Python/uvicorn
# worker several exec/fork layers deeper -- confirmed live: sudo sat at 0%
# CPU/~7MB RSS for an entire block while the real worker (a separate PID)
# was actively serving requests. Telemetry sampled the wrapper, not the
# server, for as long as this bug was in place.
_PID_TREE_WRAPPER_NAMES = {"sudo", "ip", "runuser", "env", "systemd-run"}


def find_server_pid_in_tree(root_pid: int, module_marker: str) -> Optional[int]:
    try:
        root = psutil.Process(root_pid)
    except psutil.NoSuchProcess:
        return None
    candidates = [root] + root.children(recursive=True)
    for p in candidates:
        try:
            if p.name() in _PID_TREE_WRAPPER_NAMES:
                continue
            if module_marker in " ".join(p.cmdline()):
                return p.pid
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def _netns_script_cmd(cfg: Config, *args: str) -> List[str]:
    """Prefixes the script invocation with `sudo env NAME=value ...` so each
    orchestrator session can target its OWN namespace/veth/IP set (see
    tools/netns_topology.sh's parallel-runs note) -- using `env` rather than
    `sudo NAME=value script` is deliberate: sudo only honors inline env
    assignments if the running sudoers policy has env_reset off or the var
    explicitly in env_keep, which varies by host config, whereas `sudo env
    ...` always works since `env` is the privileged command being run, and
    it sets the vars for ITS OWN child (the actual script) regardless of
    sudoers env policy."""
    env_args = [
        f"NETNS={cfg.netns_name}",
        f"VETH_HOST={cfg.netns_veth_host}",
        f"VETH_NS={cfg.netns_veth_ns}",
        f"IP_HOST={cfg.netns_host_ip}",
        f"IP_NS={cfg.netns_ns_ip}",
    ]
    return ["sudo", "env"] + env_args + [str(NETNS_TOPOLOGY_SH)] + list(args)


def ensure_netns_topology(cfg: Config) -> None:
    subprocess.run(_netns_script_cmd(cfg, "up"), check=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def teardown_netns_topology(cfg: Config) -> None:
    subprocess.run(_netns_script_cmd(cfg, "down"),
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def start_server(cfg: Config, protocol: str, log_path: Path, backend: str = "sqlite") -> subprocess.Popen:
    """Runs inside cfg.netns_name, bound to 0.0.0.0 so it's reachable both
    directly (caching=off) and via Varnish's loopback-internal proxy
    (caching=on) -- see module-level comment above. Wrapped in systemd-run
    --user --scope for fixed CPU/memory caps (N6), IDENTICAL regardless of
    protocol so the resource ceiling is a constant control, not a confound.

    backend: APE_DATA_BACKEND for core/dal.py's dispatch -- "sqlite"
    (default, unchanged behavior) or "memory" (m1mem probe arm).
    """
    module = "rest_server:app" if protocol == "rest" else "graphql_server:app"
    inner_cmd = [sys.executable, "-m", "uvicorn", module, "--workers", "1",
                 "--host", "0.0.0.0", "--port", str(cfg.port)]
    if cfg.pinning_active() and cfg.server_cores:
        inner_cmd = ["taskset", "-c", cfg.server_cores] + inner_cmd
    unit_name = f"ape-server-{os.getpid()}"
    systemd_cmd = [
        "systemd-run", "--user", "--scope", f"--unit={unit_name}",
        "-p", f"CPUQuota={cfg.cpu_quota_pct}%",
        "-p", f"MemoryMax={cfg.memory_max_mb}M",
        "--setenv", f"APE_DB_PATH={cfg.db_path}",
        "--setenv", f"APE_DATA_BACKEND={backend}",
        "--",
    ] + inner_cmd
    cmd = netns_exec_prefix(cfg, with_systemd_user_env=True) + systemd_cmd
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_f = open(log_path, "a", encoding="utf-8")
    proc = subprocess.Popen(cmd, cwd=PROJECT_ROOT, stdout=log_f, stderr=log_f,
                             **popen_kwargs_for_group())
    return proc


def start_varnish(cfg: Config, log_path: Path) -> subprocess.Popen:
    """Runs inside cfg.netns_name, client-facing on the namespace's veth IP
    (reachable from root), backend on its OWN 127.0.0.1 (cache/varnish.vcl's
    default) -- that backend hop never crosses the veth, so it's never
    subject to whatever netem profile is applied there."""
    workdir = PROJECT_ROOT / "scratch" / f"varnish-{os.getpid()}"
    shutil.rmtree(workdir, ignore_errors=True)
    inner_cmd = ["varnishd", "-n", str(workdir), "-f", str(PROJECT_ROOT / "cache" / "varnish.vcl"),
                 "-a", f"{cfg.netns_ns_ip}:{cfg.varnish_port}", "-s", "malloc,64m", "-F"]
    cmd = netns_exec_prefix(cfg) + inner_cmd
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_f = open(log_path, "a", encoding="utf-8")
    proc = subprocess.Popen(cmd, cwd=PROJECT_ROOT, stdout=log_f, stderr=log_f,
                             **popen_kwargs_for_group())
    return proc


def apply_netem(cfg: Config, profile: str) -> None:
    subprocess.run(_netns_script_cmd(cfg, "apply-netem", profile), check=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def clear_netem(cfg: Config) -> None:
    subprocess.run(_netns_script_cmd(cfg, "apply-netem", "clear"),
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def start_sampler(cfg: Config, server_pid: int, block_id: str) -> subprocess.Popen:
    out_path = cfg.telemetry_dir / f"{block_id}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(PROJECT_ROOT / "telemetry" / "sampler.py"),
           "--pid", str(server_pid), "--out", str(out_path), "--interval", "1.0"]
    if cfg.pinning_active() and cfg.sampler_core:
        cmd = ["taskset", "-c", cfg.sampler_core] + cmd
    return subprocess.Popen(cmd, cwd=PROJECT_ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             **popen_kwargs_for_group())


# --- k6 + summary parsing --------------------------------------------------------

def run_k6(cfg: Config, row: dict, base_url: str, summary_path: Path, entity_offset: int = 0) -> tuple:
    is_mot = bool(row.get("scenario"))
    env = os.environ.copy()
    env.update({
        "PROTOCOL": row["protocol"],
        "BASE_URL": base_url,
        "ACCESS_PATTERN": row["access_pattern"],
        "ENTROPY": row["entropy"],
        "PAYLOAD_WEIGHT": row["payload_weight"],
        "DENSITY": row["density"],
        "ID_POOL_JSON": cfg.id_pool_json,
        "VUS": str(row["concurrency"]),
        "DURATION": cfg.run_duration,
        "SUMMARY_FILE": str(summary_path),
        "ENTITY_OFFSET": str(entity_offset),
        "PAGE_SIZE": str(row.get("page_size", 0)),
    })
    if is_mot:
        env.update({"SCENARIO": row["scenario"], "TIER": row["tier"]})
    script = "workload_mot.js" if is_mot else "workload.js"
    cmd = ["k6", "run", str(PROJECT_ROOT / "k6" / script)]
    if cfg.pinning_active() and cfg.k6_cores:
        cmd = ["taskset", "-c", cfg.k6_cores] + cmd
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    ts_start = time.time()
    # Hard timeout: a hung k6/backend pairing (observed once during manual
    # Phase 2b testing, not reproduced since, root cause unconfirmed) must
    # not stall the whole session -- better to record one failed run and move
    # on than block indefinitely.
    timeout_s = _duration_seconds(cfg.run_duration) + 60
    try:
        result = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, timeout=timeout_s)
        rc = result.returncode
    except subprocess.TimeoutExpired:
        rc = -1
    ts_end = time.time()
    return ts_start, ts_end, rc


def expected_iterations(row: dict, cfg: Config) -> int:
    """k6's constant-arrival-rate executor issues ceil(rate*duration)
    iterations deterministically when it isn't dropping (VUS env is the
    target rate, not concurrent VUs -- see k6/workload.js's LOAD MODEL
    note). Used to advance the per-block ENTITY_OFFSET by exactly as much
    as the run actually consumed from the entity pool, so the next run in
    the block continues the 'unique' cursor instead of overlapping it."""
    return math.ceil(int(row["concurrency"]) * _duration_seconds(cfg.run_duration))


def _duration_seconds(duration: str) -> float:
    if duration.endswith("ms"):
        return float(duration[:-2]) / 1000
    if duration.endswith("s"):
        return float(duration[:-1])
    if duration.endswith("m"):
        return float(duration[:-1]) * 60
    return float(duration)


def metric(data: dict, name: str, key: str):
    try:
        return data["metrics"][name]["values"][key]
    except KeyError:
        return None


def _round_trip_count(block: dict, data: dict):
    """page_size=0/"0" (not in page mode, core/full grid): always 1 logical
    request per k6 iteration on both protocols. page_size>0 (batch grid):
    real value reported by k6/workload.js's round_trip_count Trend -- K for
    REST's page mode (K separate calls), 1 for GraphQL's (one composite
    call). Reads the Trend's mean rather than hardcoding, since it's the
    actual per-iteration value k6 recorded, not assumed. MOT scenario rows
    (workload_mot.js) always emit the Trend -- 2 for REST M5, K for REST M6,
    1 everywhere else -- so they read it unconditionally too."""
    if block.get("scenario"):
        return metric(data, "round_trip_count", "avg")
    if str(block.get("page_size", 0)) in ("0", ""):
        return 1
    return metric(data, "round_trip_count", "avg")


def percentile(data: List[float], pct: float) -> float:
    s = sorted(data)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * pct / 100
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] * (c - k) + s[c] * (k - f)


def telemetry_stats(telemetry_csv: Path, ts_start: float, ts_end: float):
    if not telemetry_csv.exists():
        return None, None, None, None, "no_telemetry_file"
    cpu, rss = [], []
    with open(telemetry_csv, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ts = float(r["unix_ts"])
            if ts_start <= ts <= ts_end:
                cpu.append(float(r["cpu_percent"]))
                rss.append(float(r["rss_mb"]))
    if not cpu:
        return None, None, None, None, "no_samples_in_window"
    return mean(cpu), percentile(cpu, 95), mean(rss), percentile(rss, 95), ""


def append_result(results_csv: Path, row: dict) -> None:
    new_file = not results_csv.exists() or results_csv.stat().st_size == 0
    results_csv.parent.mkdir(parents=True, exist_ok=True)
    # If results_csv already has rows (e.g. a session started before a
    # schema change like the batch grid's page_size/page_latency_med
    # columns, then later paused/resumed with newer code), keep writing
    # ITS existing header, not the current RESULTS_FIELDNAMES -- otherwise
    # a longer/reordered fieldname list would misalign every column against
    # the header row already on disk. Extra keys in `row` not in the
    # existing header are silently dropped (DictWriter's default), which is
    # correct here: those columns genuinely don't exist for this session.
    fieldnames = RESULTS_FIELDNAMES
    if not new_file:
        with open(results_csv, newline="", encoding="utf-8") as f:
            existing_header = next(csv.reader(f), None)
        if existing_header:
            fieldnames = existing_header
    with open(results_csv, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if new_file:
            writer.writeheader()
        writer.writerow(row)
        f.flush()


def append_progress(cfg: Config, done: int, total: int, durations: List[float], block_id: str) -> None:
    avg = mean(durations) if durations else 0.0
    remaining = total - done
    eta_min = remaining * avg / 60 if avg else 0.0
    line = (f"{time.strftime('%Y-%m-%dT%H:%M:%S')} session={cfg.session_id} block={block_id} "
            f"done={done}/{total} eta_min={eta_min:.1f}\n")
    path = cfg.results_dir / "logs" / "progress.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)


# --- Main orchestration -----------------------------------------------------------

class Executor:
    def __init__(self, cfg: Config, results_path: Path, total_measured: int = 0, done_count: int = 0):
        self.cfg = cfg
        self.results_path = results_path
        self.server_proc: Optional[subprocess.Popen] = None
        self.server_pid: Optional[int] = None
        self.current_protocol: Optional[str] = None
        self.current_backend: Optional[str] = None
        self.varnish_proc: Optional[subprocess.Popen] = None
        self.current_caching: Optional[str] = None
        self.current_network: Optional[str] = None
        self.sampler_proc: Optional[subprocess.Popen] = None
        self.total_measured = total_measured
        self.done_count = done_count
        self.run_durations: List[float] = []
        # Per-block cursor continuation for ACCESS_PATTERN=unique -- see
        # k6/workload.js's ENTITY_OFFSET comment. Reset at the start of each
        # block (run_block) since a block is the unit at which the entity
        # pool (density/payload_weight) and access_pattern are fixed.
        self.entity_offset = 0

    def ensure_server(self, protocol: str, backend: str = "sqlite") -> None:
        # Backend is part of the server identity: an m1mem block after a
        # sqlite block (or vice versa) must get a RESTART, not a reuse --
        # the DAL backend is chosen once at process startup.
        if (self.current_protocol == protocol and self.current_backend == backend
                and self.server_proc and self.server_proc.poll() is None):
            return
        self.stop_server()
        wait_port_free(self.cfg.netns_ns_ip, self.cfg.port)
        print(f"  [server] start {protocol} (backend={backend})")
        log_path = self.cfg.results_dir / "logs" / f"server_{protocol}.log"
        self.server_proc = start_server(self.cfg, protocol, log_path, backend=backend)
        wait_health(self.cfg.base_url_direct)
        module_marker = "rest_server:app" if protocol == "rest" else "graphql_server:app"
        self.server_pid = find_server_pid_in_tree(self.server_proc.pid, module_marker) or self.server_proc.pid
        self.current_protocol = protocol
        self.current_backend = backend

    def stop_server(self) -> None:
        if self.server_proc is not None:
            print(f"  [server] stop {self.current_protocol}")
            kill_tree_privileged(self.server_proc.pid)
            self.server_proc = None
            self.current_protocol = None
            self.current_backend = None

    def ensure_caching(self, caching: str) -> None:
        if self.current_caching == caching and (caching == "off" or (self.varnish_proc and self.varnish_proc.poll() is None)):
            return
        self.stop_varnish()
        if caching == "on":
            print("  [cache] start varnish")
            wait_port_free(self.cfg.netns_ns_ip, self.cfg.varnish_port)
            log_path = self.cfg.results_dir / "logs" / "varnish.log"
            self.varnish_proc = start_varnish(self.cfg, log_path)
            self._wait_varnish_up()
        self.current_caching = caching

    def _wait_varnish_up(self, timeout: float = 10.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with socket.socket() as s:
                    s.settimeout(0.5)
                    s.connect((self.cfg.netns_ns_ip, self.cfg.varnish_port))
                    return
            except OSError:
                time.sleep(0.2)
        raise TimeoutError("varnishd did not come up in time")

    def stop_varnish(self) -> None:
        if self.varnish_proc is not None:
            print("  [cache] stop varnish")
            kill_tree_privileged(self.varnish_proc.pid)
            self.varnish_proc = None
        self.current_caching = None

    def ensure_network(self, network: str) -> None:
        if self.current_network == network:
            return
        print(f"  [network] apply {network}")
        apply_netem(self.cfg, network)
        self.current_network = network

    def start_block_sampler(self, block_id: str) -> None:
        self.sampler_proc = start_sampler(self.cfg, self.server_pid, block_id)

    def stop_block_sampler(self) -> None:
        if self.sampler_proc is not None:
            kill_tree(self.sampler_proc.pid)
            self.sampler_proc = None

    def shutdown(self) -> None:
        self.stop_block_sampler()
        self.stop_varnish()
        self.stop_server()
        clear_netem(self.cfg)
        teardown_netns_topology(self.cfg)

    def base_url_for(self, block: dict) -> str:
        return self.cfg.base_url_cached if block["caching"] == "on" else self.cfg.base_url_direct

    def run_block(self, block: dict, done_uids: set) -> None:
        self.ensure_server(block["protocol"], block.get("backend") or "sqlite")
        self.ensure_caching(block["caching"])
        self.ensure_network(block["network"])
        self.start_block_sampler(block["block_id"])
        self.entity_offset = 0

        if block.get("scenario"):
            print(f"  [block {block['block_id']}] {block['protocol']}/scenario={block['scenario']}/"
                  f"tier={block['tier']}/rate={block['concurrency']}rps({block['rate_label']})/"
                  f"caching={block['caching']}/{block['access_pattern']}/backend={block['backend']}/"
                  f"{block['network']} -- warmup x{len(block['warmup_rows'])}")
        else:
            print(f"  [block {block['block_id']}] {block['protocol']}/caching={block['caching']}/"
                  f"{block['access_pattern']}/entropy={block['entropy']}/{block['payload_weight']}/"
                  f"{block['network']}/density={block['density']}/vus={block['concurrency']}/"
                  f"page_size={block['page_size']} -- "
                  f"warmup x{len(block['warmup_rows'])}")
        base_url = self.base_url_for(block)
        for row in block["warmup_rows"]:
            summary_path = self.cfg.k6_summary_dir / f"warmup_{row['run_uid']}.json"
            run_k6(self.cfg, row, base_url, summary_path, entity_offset=self.entity_offset)
            self.entity_offset += expected_iterations(row, self.cfg)
            summary_path.unlink(missing_ok=True)

        pending = [r for r in block["measured_rows"] if r["run_uid"] not in done_uids]
        print(f"  [block {block['block_id']}] measured runs remaining: {len(pending)}/{len(block['measured_rows'])}")
        for row in pending:
            self.run_measured(block, row, base_url)
            done_uids.add(row["run_uid"])

        self.stop_block_sampler()

    def run_measured(self, block: dict, row: dict, base_url: str) -> None:
        summary_path = self.cfg.k6_summary_dir / f"{row['run_uid']}.json"
        ts_start, ts_end, rc = run_k6(self.cfg, row, base_url, summary_path, entity_offset=self.entity_offset)
        self.entity_offset += expected_iterations(row, self.cfg)

        notes = "" if rc == 0 else f"k6_rc={rc}"
        data = {}
        if summary_path.exists():
            with open(summary_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            notes = (notes + ";no_summary_file").lstrip(";")

        dropped = metric(data, "dropped_iterations", "count") or 0
        if dropped:
            # constant-arrival-rate hit maxVUs and couldn't sustain the
            # target rate -- the open-loop guarantee silently degraded back
            # toward closed-loop behavior for the dropped fraction. Surface
            # it instead of letting it pass as a clean run.
            notes = ";".join(n for n in (notes, f"dropped_iterations={int(dropped)}") if n)

        telemetry_csv = self.cfg.telemetry_dir / f"{block['block_id']}.csv"
        cpu_mean, cpu_p95, rss_mean, rss_p95, tnote = telemetry_stats(telemetry_csv, ts_start, ts_end)
        if tnote:
            notes = ";".join(n for n in (notes, tnote) if n)

        result_row = {
            "run_uid": row["run_uid"],
            "block_id": block["block_id"],
            "run_index": row["run_index"],
            "session_id": self.cfg.session_id,
            "ts_start": f"{ts_start:.3f}",
            "ts_end": f"{ts_end:.3f}",
            "lat_p50": metric(data, "req_latency", "p(50)"),
            "lat_p95": metric(data, "req_latency", "p(95)"),
            "lat_p99": metric(data, "req_latency", "p(99)"),
            "throughput_rps": metric(data, "http_reqs", "rate"),
            "payload_bytes_med": metric(data, "payload_bytes", "med"),
            "cache_hit_rate": metric(data, "cache_hit", "rate") if block["caching"] == "on" else None,
            "round_trip_count": _round_trip_count(block, data),
            "page_latency_med": metric(data, "page_latency", "med"),
            "error_rate": metric(data, "http_req_failed", "rate"),
            "apq_registrations": metric(data, "apq_registrations", "count") or 0,
            "cpu_mean": cpu_mean,
            "cpu_p95": cpu_p95,
            "rss_mean_mb": rss_mean,
            "rss_p95_mb": rss_p95,
            "k6_iterations": metric(data, "iterations", "count"),
            "dropped_iterations": dropped,
            "notes": notes,
        }
        result_row.update({k: block[k] for k in _FACTOR_KEYS})
        append_result(self.results_path, result_row)
        self.run_durations.append(ts_end - ts_start)
        self.done_count += 1
        append_progress(self.cfg, self.done_count, self.total_measured, self.run_durations, block["block_id"])
        print(f"    run {row['run_index']} uid={row['run_uid']} lat_p95={result_row['lat_p95']} "
              f"cache_hit_rate={result_row['cache_hit_rate']} error_rate={result_row['error_rate']} "
              f"({self.done_count}/{self.total_measured})")


def run_experiment(cfg: Config, plan_path: Path, results_path: Path) -> int:
    cfg.results_dir.mkdir(parents=True, exist_ok=True)
    try:
        acquire_orchestrator_lock(cfg)
    except RuntimeError as exc:
        print(f"FAIL: {exc}")
        return 1
    atexit.register(release_orchestrator_lock, cfg)

    clean_results_tail(results_path)
    rows = load_plan(plan_path)
    blocks = group_blocks(rows)
    done_uids = load_done_uids(results_path)

    resume_idx = find_resume_index(blocks, done_uids)
    total_measured = sum(len(b["measured_rows"]) for b in blocks)
    if resume_idx >= len(blocks):
        print("All blocks already complete -- nothing to run.")
        release_orchestrator_lock(cfg)
        return 0

    print(f"Total blocks: {len(blocks)}. Resuming from block index {resume_idx} "
          f"({blocks[resume_idx]['block_id']}). Measured runs already recorded: {len(done_uids)}/{total_measured}")

    print(f"  [netns] bringing up {cfg.netns_name} ({cfg.netns_host_ip} <-> {cfg.netns_ns_ip})")
    ensure_netns_topology(cfg)

    executor = Executor(cfg, results_path, total_measured=total_measured, done_count=len(done_uids))

    def _raise_kbi(signum, frame):  # noqa: ANN001
        raise KeyboardInterrupt()

    signal.signal(signal.SIGINT, _raise_kbi)
    if hasattr(signal, "SIGTERM"):
        try:
            signal.signal(signal.SIGTERM, _raise_kbi)
        except (ValueError, OSError):
            pass
    atexit.register(executor.shutdown)

    try:
        for block in blocks[resume_idx:]:
            executor.run_block(block, done_uids)
    except KeyboardInterrupt:
        print("\nInterrupted -- stopping server/cache/sampler...")
        return 130
    finally:
        executor.shutdown()
        release_orchestrator_lock(cfg)
    return 0


# --- --preflight -------------------------------------------------------------------

def preflight(cfg: Config) -> int:
    checks: List[tuple] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, ok, detail))

    try:
        conn = sqlite3.connect(cfg.db_path)
        n_img = conn.execute("SELECT COUNT(*) FROM image").fetchone()[0]
        n_det = conn.execute("SELECT COUNT(*) FROM detection").fetchone()[0]
        check("db", True, f"images={n_img} detections={n_det} ({cfg.db_path})")
    except Exception as exc:  # noqa: BLE001
        check("db", False, str(exc))

    check("id_pool_json", Path(cfg.id_pool_json).exists(), cfg.id_pool_json)

    try:
        out = subprocess.run(["k6", "version"], capture_output=True, text=True, timeout=5)
        check("k6", out.returncode == 0, (out.stdout or out.stderr).strip())
    except FileNotFoundError:
        check("k6", False, "k6 not found on PATH")

    varnishd_path = shutil.which("varnishd")
    check("varnishd", bool(varnishd_path), varnishd_path or "not found on PATH")

    try:
        r = subprocess.run(["sudo", "-n", "ip", "netns", "add", "ape-preflight-probe"],
                            capture_output=True, text=True, timeout=5)
        check("sudo_netns", r.returncode == 0, "passwordless sudo for ip netns confirmed" if r.returncode == 0
              else (r.stderr or "failed").strip())
        subprocess.run(["sudo", "ip", "netns", "del", "ape-preflight-probe"],
                        capture_output=True, timeout=5)
    except FileNotFoundError:
        check("sudo_netns", False, "sudo or ip not found")

    # Full nested combo: netns + veth + runuser + systemd-run --user --scope
    # with the DBus env vars netns_exec_prefix() injects -- this is exactly
    # what start_server() does, so a pass here means the real thing will
    # work, not just its pieces in isolation.
    try:
        subprocess.run(_netns_script_cmd(cfg, "up"), check=True,
                        capture_output=True, timeout=15)
        cmd = netns_exec_prefix(cfg, with_systemd_user_env=True) + \
            ["systemd-run", "--user", "--scope", "-p", "CPUQuota=50%", "--", "true"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        check("netns_systemd_run_user_scope", r.returncode == 0,
              "confirmed working (netns + runuser + systemd-run --user --scope)" if r.returncode == 0
              else (r.stderr or "failed").strip())
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        check("netns_systemd_run_user_scope", False, str(exc))
    finally:
        subprocess.run(_netns_script_cmd(cfg, "down"), capture_output=True, timeout=15)

    pid_on_port = find_listening_pid(cfg.port, timeout=1.0)
    check("root_port_free", pid_on_port is None,
          "free" if pid_on_port is None else f"pid {pid_on_port} is listening on {cfg.port} "
          f"in the ROOT namespace (unexpected -- the server should only ever bind inside "
          f"{cfg.netns_name})")

    print(f"=== PREFLIGHT (grid={cfg.grid}) ===")
    all_ok = True
    for name, ok, detail in checks:
        status = "PASS" if ok else "FAIL"
        all_ok = all_ok and ok
        print(f"[{status}] {name}: {detail}")
    print("\n" + ("PREFLIGHT PASS" if all_ok else "PREFLIGHT FAIL"))
    return 0 if all_ok else 1


# --- --status ------------------------------------------------------------------

def status_cmd(cfg: Config, plan_path: Path, results_path: Path) -> int:
    if not plan_path.exists():
        print(f"run_plan.csv not found: {plan_path}")
        return 1

    rows = load_plan(plan_path)
    blocks = group_blocks(rows)
    done_uids = load_done_uids(results_path)
    all_measured_uids = {r["run_uid"] for b in blocks for r in b["measured_rows"]}
    done_count = len(done_uids & all_measured_uids)
    total = len(all_measured_uids)
    pct = 100 * done_count / total if total else 0.0

    print(f"Session: {cfg.session_id}")
    print(f"Progress: {done_count}/{total} measured runs ({pct:.1f}%)")

    for factor in _FACTOR_KEYS:
        agg: Dict = defaultdict(lambda: [0, 0])
        for b in blocks:
            for r in b["measured_rows"]:
                key = b[factor]
                agg[key][1] += 1
                if r["run_uid"] in done_uids:
                    agg[key][0] += 1
        print(f"  per {factor}:")
        for k, (d, t) in sorted(agg.items(), key=lambda kv: str(kv[0])):
            print(f"    {k}: {d}/{t}")

    return 0


# --- CLI -----------------------------------------------------------------------------

def main() -> int:
    cfg = get_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-plan", default=str(cfg.run_plan_csv))
    ap.add_argument("--results", default=str(cfg.results_csv))
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()

    plan_path = Path(args.run_plan)
    results_path = Path(args.results)

    if args.preflight:
        return preflight(cfg)
    if args.status:
        return status_cmd(cfg, plan_path, results_path)
    return run_experiment(cfg, plan_path, results_path)


if __name__ == "__main__":
    sys.exit(main())
