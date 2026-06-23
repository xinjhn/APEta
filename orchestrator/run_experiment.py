"""
orchestrator/run_experiment.py
================================
Eksekutor run_plan.csv -> results.csv, dengan RESUME aman, reaping orphan
otomatis, dan manajemen proses lintas-platform (server uvicorn + sampler
telemetri). Diperkeras untuk eksekusi UNATTENDED, multi-sesi, di VM Linux
dengan CPU pinning.

Alur per blok:
1. Bila protokol blok ini != protokol server yang sedang hidup (atau server
   belum hidup): matikan server lama, tunggu port lepas, start server baru,
   tunggu /health 200.
2. Start sampler telemetri (subprocess) menyampel PID server -> CSV per-blok.
3. Jalankan N_WARMUP run (k6) -> dibuang, TIDAK ditulis ke results.csv.
4. Jalankan run terukur yang BELUM ada di results.csv -> append baris per run.
5. Hentikan sampler di akhir blok.

RESUME: blok yang seluruh run terukurnya sudah ada di results.csv dilewati
total. Blok pertama yang punya run terukur belum tercatat di-warmup ULANG
(server dianggap dingin setelah restart sesi), lalu hanya run terukur yang
belum tercatat dieksekusi. Blok-blok sesudahnya berjalan normal.

Hardening (lihat VM_SETUP.md):
- PID registry (results/.locks/*.pid) + reap orphan di startup -- penutup
  utama kasus hard-kill/SIGKILL/reboot yang tak bisa ditangkap sinyal apa pun.
- Self-cleanup via signal handler (SIGINT/SIGTERM) + try/finally + atexit
  untuk kasus Ctrl-C/exception/exit normal.
- Subcommand --preflight, --status, --selftest-pinning.
- Heartbeat ke results/logs/progress.log; session log versi k6 & paket Python.

Subcommand:
    python orchestrator/run_experiment.py                 # eksekusi (default)
    python orchestrator/run_experiment.py --preflight      # cek kesiapan, exit pass/fail
    python orchestrator/run_experiment.py --status         # progres sesi saat ini
    python orchestrator/run_experiment.py --selftest-pinning  # Linux-only, no-op di Windows
"""
from __future__ import annotations

import argparse
import atexit
import csv
import json
import os
import shutil
import signal
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
from core.pool import load_records, stratify  # noqa: E402
from core.config import DEFAULT_Q1, DEFAULT_Q3  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent

RESULTS_FIELDNAMES = [
    "run_uid", "block_id", "protocol", "pattern", "density", "concurrency",
    "run_index", "session_id", "ts_start", "ts_end",
    "lat_p50", "lat_p95", "lat_p99",
    "throughput_rps",
    "payload_bytes_med",
    "xproc_p95", "xproc_med",
    "error_rate",
    "cpu_mean", "cpu_p95", "rss_mean_mb", "rss_p95_mb",
    "k6_iterations", "notes",
    "impl_mode",  # Faktor implementasi: "passthrough" atau "typed"
]


# --- Plan & results loading -----------------------------------------------------

def load_plan(path: Path) -> List[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["block_order"] = int(r["block_order"])
        r["concurrency"] = int(r["concurrency"])
        r["run_index"] = int(r["run_index"])
        r["is_warmup"] = bool(int(r["is_warmup"]))
    return rows


def group_blocks(rows: List[dict]) -> List[dict]:
    blocks: Dict[int, dict] = {}
    order: List[int] = []
    for r in rows:
        bo = r["block_order"]
        if bo not in blocks:
            blocks[bo] = {
                "block_order": bo,
                "block_id": r["block_id"],
                "protocol": r["protocol"],
                "pattern": r["pattern"],
                "density": r["density"],
                "concurrency": r["concurrency"],
                "warmup_rows": [],
                "measured_rows": [],
            }
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


# --- Manajemen proses lintas-platform --------------------------------------------

def popen_kwargs_for_group() -> dict:
    """Telurkan anak dalam process group/session sendiri (POSIX) agar seluruh
    subtree -- termasuk yang dibungkus taskset -- bisa dimatikan andal. Tidak
    ada ekuivalen yang diperlukan di Windows: psutil.children(recursive=True)
    sudah menjangkau subtree tanpa perlu process group terpisah."""
    if os.name == "posix":
        return {"start_new_session": True}
    return {}


def wait_port_free(host: str, port: int, timeout: float = 15.0) -> None:
    import socket

    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            try:
                s.connect((host, port))
            except OSError:
                return  # connect gagal -> tidak ada yang listen -> port lepas
        time.sleep(0.3)
    raise TimeoutError(f"Port {host}:{port} tidak lepas dalam {timeout}s")


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
    raise TimeoutError(f"Server tidak healthy dalam {timeout}s ({base_url}/health): {last_err}")


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
    """SIGTERM (psutil.terminate) seluruh subtree, tunggu, lalu SIGKILL
    (psutil.kill) sisa yang masih hidup. Di Windows kedua panggilan psutil
    sama-sama berarti TerminateProcess (tidak ada SIGTERM bertahap), tapi
    pola tunggu-lalu-force tetap berlaku untuk proses yang lambat exit."""
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


def _cmdline_of(pid: int) -> Optional[str]:
    try:
        return " ".join(psutil.Process(pid).cmdline())
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
        return None


def classify_pid(pid: int) -> tuple:
    """Klasifikasikan SEBELUM mematikan apa pun -- supaya proses asing (bukan
    APE) tidak pernah ikut dibunuh oleh reaping. Mengembalikan (kind, cmdline)
    dengan kind salah satu dari: "gone", "orchestrator", "ape_server",
    "ape_sampler", "foreign"."""
    cmdline = _cmdline_of(pid)
    if cmdline is None:
        return "gone", None
    if "run_experiment.py" in cmdline:
        return "orchestrator", cmdline
    if "uvicorn" in cmdline and ("rest_server:app" in cmdline or "graphql_server:app" in cmdline):
        return "ape_server", cmdline
    if "sampler.py" in cmdline:
        return "ape_sampler", cmdline
    return "foreign", cmdline


class ForeignProcessOnPortError(Exception):
    pass


class OrchestratorLockError(Exception):
    def __init__(self, info: dict):
        self.info = info
        super().__init__(f"orchestrator lain pid={info.get('pid')}")


# --- PID registry (safety net untuk hard-kill / reboot) ---------------------------

def _registry_path(cfg: Config, name: str) -> Path:
    return cfg.results_dir / ".locks" / f"{name}.pid"


def write_registry(cfg: Config, name: str, pid: int, marker: str, **extra) -> None:
    path = _registry_path(cfg, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"pid": pid, "marker": marker, **extra}), encoding="utf-8")


def clear_registry(cfg: Config, name: str) -> None:
    _registry_path(cfg, name).unlink(missing_ok=True)


def read_registry(cfg: Config, name: str) -> Optional[dict]:
    path = _registry_path(cfg, name)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _lock_path(cfg: Config) -> Path:
    return cfg.results_dir / ".locks" / "orchestrator.lock"


def read_lock(cfg: Config) -> Optional[dict]:
    path = _lock_path(cfg)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def acquire_orchestrator_lock(cfg: Config) -> None:
    """Cegah dua instance eksekusi beradu pada results.csv/server/port yang
    sama. HANYA subcommand eksekusi memanggil ini -- --status/--preflight
    read-only dan tidak mengambil lock. Dipanggil SEBELUM reap_orphans()."""
    path = _lock_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    info = read_lock(cfg)
    if info is not None:
        kind, _ = classify_pid(info.get("pid", -1))
        if kind == "orchestrator":
            raise OrchestratorLockError(info)
        print(f"  [lock] stale lock dibersihkan (pid lama={info.get('pid')}, status={kind})")
    path.write_text(json.dumps({
        "pid": os.getpid(), "start_ts": time.time(),
        "session_id": cfg.session_id, "host": cfg.host,
    }), encoding="utf-8")


def release_orchestrator_lock(cfg: Config) -> None:
    _lock_path(cfg).unlink(missing_ok=True)


def clean_results_tail(results_csv: Path) -> None:
    """Toleransi hard-kill tepat saat menulis baris terakhir results.csv: bila
    baris terakhir tidak diakhiri newline (terpotong) ATAU jumlah kolomnya
    tidak cocok dengan header (korup), buang baris itu. Baris yang dibuang
    berarti run yang belum tuntas tercatat -- akan otomatis dijalankan ulang
    oleh logika resume yang sudah ada, bukan hilang begitu saja."""
    if not results_csv.exists():
        return
    with open(results_csv, newline="", encoding="utf-8") as f:
        text = f.read()
    if not text:
        return
    lines = text.splitlines()
    if len(lines) <= 1:
        return  # cuma header (atau kosong) -- tidak ada baris data utk divalidasi
    ends_with_newline = text.endswith("\n")
    header_cols = len(next(csv.reader([lines[0]])))
    try:
        last_cols = len(next(csv.reader([lines[-1]])))
    except (csv.Error, StopIteration):
        last_cols = -1
    malformed = (not ends_with_newline) or (last_cols != header_cols)
    if not malformed:
        return
    print("  [resume] baris terakhir results.csv malformed -> dibuang (hard-kill saat menulis)")
    cleaned = lines[:-1]
    new_text = ("\n".join(cleaned) + "\n") if cleaned else ""
    with open(results_csv, "w", newline="", encoding="utf-8") as f:
        f.write(new_text)


def reap_orphans(cfg: Config) -> None:
    """Dipanggil di startup (SETELAH lock orchestrator didapat), SEBELUM
    server pertama distart. Menutup kasus `taskkill -F`/SIGKILL/crash yang tak
    bisa ditangkap signal handler -- TAPI hanya untuk proses yang TERVERIFIKASI
    milik APE (uvicorn rest_server/graphql_server, atau sampler.py). Proses
    asing yang menahan port target TIDAK dimatikan -- reaping di-abort dengan
    ForeignProcessOnPortError supaya operator memeriksa manual (mematikan
    proses tak dikenal berisiko menutupi kesalahan konfigurasi VM).
    1. Baca registry server/sampler sesi sebelumnya -- bila PID itu masih
       hidup DAN klasifikasinya cocok (bukan PID yang sudah dipakai ulang
       proses lain), matikan.
    2. Safety net: siapa pun yang masih bind host:port target diklasifikasi
       ulang (independen dari registry, karena registry bisa hilang/tidak
       konsisten dengan crash mendadak) -- hanya orphan APE dikenal yang
       dimatikan otomatis.
    3. Tunggu port benar-benar bebas sebelum lanjut.
    """
    expected_kind = {"server": "ape_server", "sampler": "ape_sampler"}
    for name in ("server", "sampler"):
        info = read_registry(cfg, name)
        if info:
            kind, _ = classify_pid(info.get("pid", -1))
            if kind == expected_kind[name]:
                print(f"  [reap] orphan APE dikenal ({name}) pid={info['pid']} -- dimatikan")
                kill_tree(info["pid"])
        clear_registry(cfg, name)

    pid_on_port = find_listening_pid(cfg.port, timeout=1.0)
    if pid_on_port:
        kind, cmdline = classify_pid(pid_on_port)
        if kind in ("ape_server", "ape_sampler"):
            print(f"  [reap] port {cfg.host}:{cfg.port} dipegang orphan APE dikenal pid={pid_on_port} -- dimatikan")
            kill_tree(pid_on_port)
        elif kind == "gone":
            pass  # proses sudah hilang antara deteksi & klasifikasi -- aman lanjut
        else:
            label = "orchestrator APE lain" if kind == "orchestrator" else "proses asing (bukan APE)"
            raise ForeignProcessOnPortError(
                f"Port {cfg.host}:{cfg.port} dipegang {label} pid={pid_on_port} (cmdline={cmdline!r}) -- "
                f"BUKAN orphan APE dikenal, TIDAK dimatikan otomatis. Periksa/bebaskan manual lalu coba lagi."
            )

    wait_port_free(cfg.host, cfg.port, timeout=15.0)


def start_server(cfg: Config, protocol: str, log_path: Path) -> subprocess.Popen:
    module = "rest_server:app" if protocol == "rest" else "graphql_server:app"
    cmd = [sys.executable, "-m", "uvicorn", module, "--workers", "1", "--host", cfg.host, "--port", str(cfg.port)]
    if cfg.pinning_active() and cfg.server_cores:
        cmd = ["taskset", "-c", cfg.server_cores] + cmd
    env = os.environ.copy()
    env["APE_POOL_JSON"] = cfg.pool_json
    # Faktor implementasi untuk desain faktorial 2x2 (Path B)
    if protocol == "rest":
        env["APE_REST_MODE"] = cfg.impl_mode_rest
    else:
        env["APE_GRAPHQL_MODE"] = cfg.impl_mode_graphql
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_f = open(log_path, "a", encoding="utf-8")
    proc = subprocess.Popen(cmd, cwd=PROJECT_ROOT, env=env, stdout=log_f, stderr=log_f, **popen_kwargs_for_group())
    write_registry(cfg, "server", proc.pid, "uvicorn", host=cfg.host, port=cfg.port, protocol=protocol)
    return proc


def start_sampler(cfg: Config, server_pid: int, block_id: str) -> subprocess.Popen:
    out_path = cfg.telemetry_dir / f"{block_id}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(PROJECT_ROOT / "telemetry" / "sampler.py"),
           "--pid", str(server_pid), "--out", str(out_path), "--interval", "1.0"]
    if cfg.pinning_active() and cfg.sampler_core:
        cmd = ["taskset", "-c", cfg.sampler_core] + cmd
    proc = subprocess.Popen(cmd, cwd=PROJECT_ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             **popen_kwargs_for_group())
    write_registry(cfg, "sampler", proc.pid, "sampler.py", block_id=block_id)
    return proc


# --- k6 + parsing ringkasan --------------------------------------------------------

def run_k6(cfg: Config, row: dict, summary_path: Path) -> tuple:
    env = os.environ.copy()
    env.update({
        "PROTOCOL": row["protocol"],
        "PATTERN": row["pattern"],
        "DENSITY": row["density"],
        "VUS": str(row["concurrency"]),
        "DURATION": cfg.run_duration,
        "BASE_URL": cfg.base_url,
        "SUMMARY_FILE": str(summary_path),
    })
    cmd = ["k6", "run", str(PROJECT_ROOT / "k6" / "load.js")]
    if cfg.pinning_active() and cfg.k6_cores:
        cmd = ["taskset", "-c", cfg.k6_cores] + cmd
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    ts_start = time.time()
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ts_end = time.time()
    return ts_start, ts_end, result.returncode


def metric(data: dict, name: str, key: str):
    try:
        return data["metrics"][name]["values"][key]
    except KeyError:
        return None


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
    with open(results_csv, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULTS_FIELDNAMES)
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


def write_session_log(cfg: Config) -> None:
    """Catat versi k6 & paket Python di awal sesi -- reprodusibilitas dan
    deteksi bila lingkungan ter-update tak sengaja antar sesi."""
    log_path = cfg.results_dir / "logs" / f"session_{cfg.session_id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        k6v = subprocess.run(["k6", "version"], capture_output=True, text=True, timeout=5).stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        k6v = f"(gagal: {exc})"
    try:
        pkgs = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True,
                               timeout=15).stdout
    except subprocess.TimeoutExpired:
        pkgs = "(timeout)"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"=== session start {time.strftime('%Y-%m-%dT%H:%M:%S')} ===\n")
        f.write(f"k6: {k6v}\npython: {sys.version}\nplatform: {os.name}\n")
        f.write(pkgs)
        f.write("\n")


# --- Orkestrasi utama --------------------------------------------------------------

class Executor:
    def __init__(self, cfg: Config, results_path: Path, total_measured: int = 0, done_count: int = 0):
        self.cfg = cfg
        self.results_path = results_path
        self.server_proc: Optional[subprocess.Popen] = None
        self.server_pid: Optional[int] = None
        self.current_protocol: Optional[str] = None
        self.sampler_proc: Optional[subprocess.Popen] = None
        self.total_measured = total_measured
        self.done_count = done_count
        self.run_durations: List[float] = []

    def ensure_server(self, protocol: str) -> None:
        if self.current_protocol == protocol and self.server_proc and self.server_proc.poll() is None:
            return
        self.stop_server()
        wait_port_free(self.cfg.host, self.cfg.port)
        print(f"  [server] start {protocol}")
        log_path = self.cfg.results_dir / "logs" / f"server_{protocol}.log"
        self.server_proc = start_server(self.cfg, protocol, log_path)
        wait_health(self.cfg.base_url)
        self.server_pid = find_listening_pid(self.cfg.port) or self.server_proc.pid
        self.current_protocol = protocol

    def stop_server(self) -> None:
        if self.server_proc is not None:
            print(f"  [server] stop {self.current_protocol}")
            kill_tree(self.server_proc.pid)
            self.server_proc = None
            self.current_protocol = None
        clear_registry(self.cfg, "server")

    def start_block_sampler(self, block_id: str) -> None:
        self.sampler_proc = start_sampler(self.cfg, self.server_pid, block_id)

    def stop_block_sampler(self) -> None:
        if self.sampler_proc is not None:
            kill_tree(self.sampler_proc.pid)
            self.sampler_proc = None
        clear_registry(self.cfg, "sampler")

    def shutdown(self) -> None:
        self.stop_block_sampler()
        self.stop_server()

    def run_block(self, block: dict, done_uids: set) -> None:
        self.ensure_server(block["protocol"])
        self.start_block_sampler(block["block_id"])

        print(f"  [block {block['block_id']}] {block['protocol']}/{block['pattern']}/"
              f"{block['density']}/vus={block['concurrency']} -- warmup x{len(block['warmup_rows'])}")
        for row in block["warmup_rows"]:
            summary_path = self.cfg.k6_summary_dir / f"warmup_{row['run_uid']}.json"
            run_k6(self.cfg, row, summary_path)
            summary_path.unlink(missing_ok=True)

        pending = [r for r in block["measured_rows"] if r["run_uid"] not in done_uids]
        print(f"  [block {block['block_id']}] run terukur tersisa: {len(pending)}/{len(block['measured_rows'])}")
        for row in pending:
            self.run_measured(block, row)
            done_uids.add(row["run_uid"])

        self.stop_block_sampler()

    def run_measured(self, block: dict, row: dict) -> None:
        summary_path = self.cfg.k6_summary_dir / f"{row['run_uid']}.json"
        ts_start, ts_end, rc = run_k6(self.cfg, row, summary_path)

        notes = "" if rc == 0 else f"k6_rc={rc}"
        data = {}
        if summary_path.exists():
            with open(summary_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            notes = (notes + ";no_summary_file").lstrip(";")

        telemetry_csv = self.cfg.telemetry_dir / f"{block['block_id']}.csv"
        cpu_mean, cpu_p95, rss_mean, rss_p95, tnote = telemetry_stats(telemetry_csv, ts_start, ts_end)
        if tnote:
            notes = ";".join(n for n in (notes, tnote) if n)

        result_row = {
            "run_uid": row["run_uid"],
            "block_id": block["block_id"],
            "protocol": block["protocol"],
            "pattern": block["pattern"],
            "density": block["density"],
            "concurrency": block["concurrency"],
            "run_index": row["run_index"],
            "session_id": self.cfg.session_id,
            "ts_start": f"{ts_start:.3f}",
            "ts_end": f"{ts_end:.3f}",
            "lat_p50": metric(data, "http_req_duration", "p(50)"),
            "lat_p95": metric(data, "http_req_duration", "p(95)"),
            "lat_p99": metric(data, "http_req_duration", "p(99)"),
            "throughput_rps": metric(data, "http_reqs", "rate"),
            "payload_bytes_med": metric(data, "payload_bytes", "med"),
            "xproc_p95": metric(data, "xproc_time", "p(95)"),
            "xproc_med": metric(data, "xproc_time", "med"),
            "error_rate": metric(data, "http_req_failed", "rate"),
            "cpu_mean": cpu_mean,
            "cpu_p95": cpu_p95,
            "rss_mean_mb": rss_mean,
            "rss_p95_mb": rss_p95,
            "k6_iterations": metric(data, "iterations", "count"),
            "notes": notes,
            "impl_mode": self.cfg.impl_mode_rest if block["protocol"] == "rest" else self.cfg.impl_mode_graphql,
        }
        append_result(self.results_path, result_row)
        self.run_durations.append(ts_end - ts_start)
        self.done_count += 1
        append_progress(self.cfg, self.done_count, self.total_measured, self.run_durations, block["block_id"])
        print(f"    run {row['run_index']} uid={row['run_uid']} lat_p95={result_row['lat_p95']} "
              f"error_rate={result_row['error_rate']} ({self.done_count}/{self.total_measured})")


# --- Subcommand: eksekusi utama -----------------------------------------------------

def run_experiment(cfg: Config, plan_path: Path, results_path: Path) -> int:
    cfg.results_dir.mkdir(parents=True, exist_ok=True)

    try:
        acquire_orchestrator_lock(cfg)
    except OrchestratorLockError as exc:
        info = exc.info
        started = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(info.get("start_ts", 0)))
        print(f"FAIL: Orchestrator lain PID {info.get('pid')} aktif sejak {started} "
              f"sesi {info.get('session_id')!r} di {info.get('host')}; hentikan dulu sebelum "
              f"menjalankan instance baru.")
        return 1
    atexit.register(release_orchestrator_lock, cfg)

    write_session_log(cfg)

    print("Reaping orphan (jika ada) sebelum start...")
    try:
        reap_orphans(cfg)
    except ForeignProcessOnPortError as exc:
        print(f"FAIL: {exc}")
        release_orchestrator_lock(cfg)
        return 1

    clean_results_tail(results_path)
    rows = load_plan(plan_path)
    blocks = group_blocks(rows)
    done_uids = load_done_uids(results_path)

    resume_idx = find_resume_index(blocks, done_uids)
    total_measured = sum(len(b["measured_rows"]) for b in blocks)
    if resume_idx >= len(blocks):
        print("Semua blok sudah selesai -- tidak ada yang dijalankan.")
        release_orchestrator_lock(cfg)
        return 0

    print(f"Total blok: {len(blocks)}. Resume mulai dari blok index {resume_idx} "
          f"({blocks[resume_idx]['block_id']}). Run terukur sudah tercatat: {len(done_uids)}/{total_measured}")

    executor = Executor(cfg, results_path, total_measured=total_measured, done_count=len(done_uids))

    def _raise_kbi(signum, frame):  # noqa: ANN001
        raise KeyboardInterrupt()

    signal.signal(signal.SIGINT, _raise_kbi)
    if hasattr(signal, "SIGTERM"):
        try:
            signal.signal(signal.SIGTERM, _raise_kbi)
        except (ValueError, OSError):
            pass  # tidak semua platform/konteks mengizinkan ini (mis. thread non-main)
    atexit.register(executor.shutdown)

    try:
        for block in blocks[resume_idx:]:
            executor.run_block(block, done_uids)
    except KeyboardInterrupt:
        print("\nDiinterupsi -- menghentikan server/sampler...")
        return 130
    finally:
        executor.shutdown()
        release_orchestrator_lock(cfg)
    return 0


# --- Subcommand: --preflight ---------------------------------------------------------

def _parse_core_spec(spec: str) -> List[int]:
    cores = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-")
            cores.update(range(int(a), int(b) + 1))
        else:
            cores.add(int(part))
    return sorted(cores)


def _read_cpu_governor() -> Optional[str]:
    path = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def preflight(cfg: Config) -> int:
    checks: List[tuple] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, ok, detail))

    try:
        records = load_records(cfg.pool_json)
        tiers = stratify(records, DEFAULT_Q1, DEFAULT_Q3)
        summary = {t: len(v) for t, v in tiers.items()}
        check("APE_POOL_JSON", True, f"{len(records)} record, tier={summary}")
    except Exception as exc:  # noqa: BLE001
        check("APE_POOL_JSON", False, str(exc))

    log_dir = cfg.results_dir / "logs"
    try:
        out = subprocess.run(["k6", "version"], capture_output=True, text=True, timeout=5)
        version_str = (out.stdout or out.stderr).strip()
        check("k6", out.returncode == 0, version_str)
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "k6_version_preflight.log").write_text(version_str, encoding="utf-8")
    except FileNotFoundError:
        check("k6", False, "k6 tidak ditemukan di PATH")
    except Exception as exc:  # noqa: BLE001
        check("k6", False, str(exc))

    lock_info = read_lock(cfg)
    if lock_info is None:
        check("lock", True, "tidak ada lock aktif")
    else:
        lock_kind, _ = classify_pid(lock_info.get("pid", -1))
        if lock_kind == "orchestrator":
            started = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(lock_info.get("start_ts", 0)))
            check("lock", False, f"orchestrator lain PID {lock_info.get('pid')} aktif sejak {started} "
                                  f"sesi {lock_info.get('session_id')!r} -- hentikan dulu")
        else:
            check("lock", True, f"lock lama stale (pid={lock_info.get('pid')}, status={lock_kind}) "
                                 f"-- akan direclaim otomatis saat run")

    pid_on_port = find_listening_pid(cfg.port, timeout=1.0)
    if pid_on_port is None:
        check("port", True, f"{cfg.host}:{cfg.port} bebas")
    else:
        kind, cmdline = classify_pid(pid_on_port)
        if kind in ("ape_server", "ape_sampler"):
            check("port", True, f"{cfg.host}:{cfg.port} dipegang orphan APE dikenal pid={pid_on_port} "
                                 f"({kind}) -- aman di-reap otomatis saat run")
        elif kind == "orchestrator":
            check("port", False, f"{cfg.host}:{cfg.port} dipegang ORCHESTRATOR APE LAIN pid={pid_on_port} "
                                  f"-- hentikan dulu, TIDAK akan di-reap")
        else:
            check("port", False, f"{cfg.host}:{cfg.port} dipegang PROSES ASING pid={pid_on_port} "
                                  f"cmdline={cmdline!r} -- PERIKSA manual, TIDAK akan di-reap otomatis")

    try:
        cfg.results_dir.mkdir(parents=True, exist_ok=True)
        probe = cfg.results_dir / ".preflight_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        check("results_dir_writable", True, str(cfg.results_dir))
    except OSError as exc:
        check("results_dir_writable", False, str(exc))

    try:
        usage = shutil.disk_usage(cfg.results_dir)
        free_mb = usage.free / (1024 * 1024)
        ok = free_mb > 500
        check("disk_space", ok, f"{free_mb:.0f} MB bebas" + ("" if ok else " -- MENIPIS, pertimbangkan bersihkan/relokasi"))
    except OSError as exc:
        check("disk_space", False, str(exc))

    if cfg.enable_pinning:
        if os.name != "posix":
            check("pinning", False, "APE_ENABLE_PINNING=1 tapi OS bukan POSIX -- taskset tidak tersedia di Windows")
        else:
            taskset_path = shutil.which("taskset")
            check("taskset", bool(taskset_path), taskset_path or "tidak ditemukan di PATH")

            n_cpu = os.cpu_count() or 0
            core_specs = {"server": cfg.server_cores, "k6": cfg.k6_cores, "sampler": cfg.sampler_core}
            parsed: Dict[str, List[int]] = {}
            for label, spec in core_specs.items():
                if not spec:
                    check(f"cores_{label}", False, f"APE_{label.upper()}_CORES kosong")
                    continue
                try:
                    cores = _parse_core_spec(spec)
                except ValueError as exc:
                    check(f"cores_{label}", False, f"spec tidak valid {spec!r}: {exc}")
                    continue
                parsed[label] = cores
                invalid = [c for c in cores if c < 0 or c >= n_cpu]
                if invalid:
                    check(f"cores_{label}", False, f"core {invalid} di luar rentang 0..{n_cpu - 1}")
                else:
                    check(f"cores_{label}", True, str(cores))

            names = list(parsed)
            overlap_found = False
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    inter = set(parsed[names[i]]) & set(parsed[names[j]])
                    if inter:
                        overlap_found = True
                        check("cores_overlap", False, f"{names[i]} & {names[j]} tumpang tindih di {sorted(inter)}")
            if not overlap_found and len(parsed) == len(core_specs):
                check("cores_overlap", True, "tidak ada tumpang tindih")

            governor = _read_cpu_governor()
            if governor is None:
                sysfs_absent_ok = os.environ.get("APE_GOVERNOR_SYSFS_ABSENT_OK") == "1"
                if sysfs_absent_ok:
                    check(
                        "cpu_governor", True,
                        "sysfs tidak ada -- dilewati via APE_GOVERNOR_SYSFS_ABSENT_OK=1 "
                        "(operator sudah konfirmasi manual clock CPU tetap, lihat VM_SETUP.md)",
                    )
                else:
                    check("cpu_governor", False, "tidak bisa membaca scaling_governor (sysfs tidak ada)")
            elif governor != "performance":
                check("cpu_governor", False, f"governor={governor} (disarankan 'performance', lihat VM_SETUP.md)")
            else:
                check("cpu_governor", True, governor)
    else:
        check("pinning", True, "APE_ENABLE_PINNING=0 -- dilewati (OK untuk lokal)")

    print(f"=== PREFLIGHT ({'PILOT' if cfg.pilot else 'FULL'}) ===")
    all_ok = True
    for name, ok, detail in checks:
        status = "PASS" if ok else "FAIL"
        all_ok = all_ok and ok
        print(f"[{status}] {name}: {detail}")
    print("\n" + ("PREFLIGHT PASS" if all_ok else "PREFLIGHT FAIL"))
    return 0 if all_ok else 1


# --- Subcommand: --status ----------------------------------------------------------

def status_cmd(cfg: Config, plan_path: Path, results_path: Path) -> int:
    if not plan_path.exists():
        print(f"run_plan.csv tidak ditemukan: {plan_path}")
        return 1

    rows = load_plan(plan_path)
    blocks = group_blocks(rows)
    done_uids = load_done_uids(results_path)
    all_measured_uids = {r["run_uid"] for b in blocks for r in b["measured_rows"]}
    done_count = len(done_uids & all_measured_uids)
    total = len(all_measured_uids)
    pct = 100 * done_count / total if total else 0.0

    print(f"Sesi: {cfg.session_id}")
    print(f"Progres: {done_count}/{total} run terukur ({pct:.1f}%)")

    for factor in ("protocol", "pattern", "density", "concurrency"):
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

    if results_path.exists():
        with open(results_path, newline="", encoding="utf-8") as f:
            results_rows = list(csv.DictReader(f))
        durations = []
        for r in results_rows:
            try:
                durations.append(float(r["ts_end"]) - float(r["ts_start"]))
            except (ValueError, KeyError):
                continue
        if durations:
            avg = mean(durations)
            remaining = total - done_count
            print(f"  durasi rata-rata/run: {avg:.1f}s | ETA kasar sisa: {remaining * avg / 60:.1f} menit "
                  f"({remaining} run tersisa)")

    return 0


# --- Subcommand: --selftest-pinning (Linux-only) -------------------------------------

def selftest_pinning(cfg: Config) -> int:
    if os.name != "posix":
        print("SKIP -- --selftest-pinning no-op di Windows (taskset hanya POSIX). Jalankan ini di VM Linux.")
        return 0
    if not cfg.enable_pinning or not cfg.server_cores:
        print("FAIL: set APE_ENABLE_PINNING=1 dan APE_SERVER_CORES untuk menjalankan selftest ini.")
        return 1

    target_cores = _parse_core_spec(cfg.server_cores)
    print(f"Target cpu_affinity server: {target_cores}")

    try:
        reap_orphans(cfg)
    except ForeignProcessOnPortError as exc:
        print(f"FAIL: {exc}")
        return 1
    log_path = cfg.results_dir / "logs" / "selftest_pinning.log"
    proc = start_server(cfg, "rest", log_path)
    try:
        wait_health(cfg.base_url)
        pid = find_listening_pid(cfg.port) or proc.pid
        actual = sorted(psutil.Process(pid).cpu_affinity())
        ok = actual == target_cores
        print(f"Actual cpu_affinity(pid={pid}): {actual}")
        print("PASS" if ok else "FAIL: cpu_affinity tidak sama dengan target")
        return 0 if ok else 1
    finally:
        kill_tree(proc.pid)
        clear_registry(cfg, "server")


# --- CLI -----------------------------------------------------------------------------

def main() -> int:
    cfg = get_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-plan", default=str(cfg.run_plan_csv))
    ap.add_argument("--results", default=str(cfg.results_csv))
    ap.add_argument("--preflight", action="store_true", help="cek kesiapan, exit pass/fail, tanpa menjalankan k6")
    ap.add_argument("--status", action="store_true", help="cetak progres sesi (run_plan vs results)")
    ap.add_argument("--selftest-pinning", action="store_true", help="Linux-only, no-op di Windows")
    args = ap.parse_args()

    plan_path = Path(args.run_plan)
    results_path = Path(args.results)

    if args.preflight:
        return preflight(cfg)
    if args.status:
        return status_cmd(cfg, plan_path, results_path)
    if args.selftest_pinning:
        return selftest_pinning(cfg)
    return run_experiment(cfg, plan_path, results_path)


if __name__ == "__main__":
    sys.exit(main())
