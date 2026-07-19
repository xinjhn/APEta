#!/usr/bin/env python3
"""Local control panel for the short APE Windows/WSL demonstration."""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import signal
import sqlite3
import statistics
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "tools" / "demo_ui_static"
DB_PATH = Path(os.environ.get("APE_DB_PATH", "/mnt/d/TA/APE VM/training/mot_detections.db"))
RESULTS_DIR = Path(os.environ.get("APE_RESULTS_DIR", ROOT / "results" / "wsl-analysis-m6cache"))
UI_LOG_DIR = RESULTS_DIR / "ui_logs"

app = FastAPI(title="APE Demo Control Room", docs_url=None, redoc_url=None)
_jobs: dict[str, subprocess.Popen] = {}
_job_logs: dict[str, Path] = {}
_job_handles: dict[str, Any] = {}
_lock = threading.Lock()


def _tail(path: Path, lines: int = 180) -> str:
    if not path.exists():
        return "No log output yet."
    try:
        return "".join(path.read_text(encoding="utf-8", errors="replace").splitlines(True)[-lines:])
    except OSError as exc:
        return f"Unable to read log: {exc}"


def _csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _progress() -> dict[str, Any]:
    plan = _csv_rows(RESULTS_DIR / "run_plan.csv")
    results = _csv_rows(RESULTS_DIR / "results.csv")
    expected = {r["run_uid"] for r in plan if r.get("is_warmup") == "0"}
    done = {r.get("run_uid") for r in results} & expected
    total = len(expected)
    return {
        "done": len(done),
        "total": total,
        "percent": round(100 * len(done) / total, 1) if total else 0,
        "results_rows": len(results),
    }


def _metric_summary() -> dict[str, dict[str, float | None]]:
    rows = _csv_rows(RESULTS_DIR / "results.csv")
    metrics = ("lat_p95", "throughput_rps", "payload_bytes_med", "cache_hit_rate", "cpu_mean")
    output: dict[str, dict[str, float | None]] = {}
    for protocol in ("rest", "graphql"):
        protocol_rows = [r for r in rows if r.get("protocol") == protocol]
        output[protocol] = {}
        for metric in metrics:
            values = []
            for row in protocol_rows:
                try:
                    if row.get(metric) not in (None, "", "None"):
                        values.append(float(row[metric]))
                except ValueError:
                    pass
            output[protocol][metric] = round(statistics.median(values), 3) if values else None
    return output


def _command_ready(command: str) -> dict[str, Any]:
    path = shutil.which(command)
    return {"ok": bool(path), "detail": path or "not found"}


def _sudo_ready() -> dict[str, Any]:
    try:
        result = subprocess.run(["sudo", "-n", "true"], capture_output=True, text=True, timeout=3)
        return {"ok": result.returncode == 0,
                "detail": "temporary APE sudo rule active" if result.returncode == 0
                else (result.stderr.strip() or "non-interactive sudo unavailable")}
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "detail": str(exc)}


def _job_state(name: str) -> dict[str, Any]:
    proc = _jobs.get(name)
    if proc is None:
        return {"state": "idle", "returncode": None}
    rc = proc.poll()
    return {"state": "running" if rc is None else ("passed" if rc == 0 else "failed"),
            "returncode": rc, "pid": proc.pid}


def _spawn(name: str, command: list[str], env: dict[str, str] | None = None) -> dict[str, Any]:
    with _lock:
        current = _jobs.get(name)
        if current is not None and current.poll() is None:
            raise HTTPException(409, f"{name} is already running")
        UI_LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = UI_LOG_DIR / f"{name}.log"
        handle = log_path.open("a", encoding="utf-8", buffering=1)
        handle.write(f"\n=== Starting {name}: {' '.join(command)} ===\n")
        proc = subprocess.Popen(
            command,
            cwd=ROOT,
            env=env or os.environ.copy(),
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        _jobs[name] = proc
        _job_logs[name] = log_path
        _job_handles[name] = handle
        return {"ok": True, "job": name, "pid": proc.pid, "log": str(log_path)}


def _demo_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "APE_DB_PATH": str(DB_PATH),
        "APE_ID_POOL_JSON": str(ROOT / "scratch" / "id_pool_mot.json"),
        "APE_GRID": "mot",
        "APE_MOT_ARM": os.environ.get("APE_MOT_ARM", "m6cache"),
        "APE_SESSION_ID": os.environ.get("APE_SESSION_ID", RESULTS_DIR.name),
        "APE_RESULTS_DIR": str(RESULTS_DIR),
        "APE_DISABLE_NETEM": "1",
    })
    return env


def _reset_results(confirm: str | None) -> dict[str, Any]:
    if confirm != "RESET":
        raise HTTPException(400, "Type RESET to confirm archiving the current run results")

    results_root = (ROOT / "results").resolve()
    source = RESULTS_DIR.resolve()
    try:
        relative = source.relative_to(results_root)
    except ValueError as exc:
        raise HTTPException(400, "The configured results directory is outside the workspace results folder") from exc
    if source == results_root or not relative.parts or relative.parts[0] == ".trash":
        raise HTTPException(400, "Refusing to reset this results directory")

    with _lock:
        running = [name for name, proc in _jobs.items() if proc.poll() is None]
        if running:
            raise HTTPException(409, f"Wait for or stop the running job(s): {', '.join(running)}")

        lock_path = RESULTS_DIR / ".locks" / "orchestrator.lock"
        if lock_path.exists():
            try:
                pid = int(json.loads(lock_path.read_text(encoding="utf-8"))["pid"])
                if psutil.pid_exists(pid):
                    raise HTTPException(409, f"Stop the running orchestrator (pid {pid}) before resetting")
            except HTTPException:
                raise
            except (KeyError, ValueError, OSError, json.JSONDecodeError):
                pass

        for handle in _job_handles.values():
            try:
                handle.close()
            except (OSError, ValueError):
                pass
        _jobs.clear()
        _job_logs.clear()
        _job_handles.clear()

        archive: Path | None = None
        if RESULTS_DIR.exists():
            archive_root = results_root / ".trash"
            archive_root.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            archive = archive_root / f"{RESULTS_DIR.name}-{timestamp}"
            suffix = 1
            while archive.exists():
                archive = archive_root / f"{RESULTS_DIR.name}-{timestamp}-{suffix}"
                suffix += 1
            shutil.move(str(RESULTS_DIR), str(archive))

        UI_LOG_DIR.mkdir(parents=True, exist_ok=True)
        return {
            "ok": True,
            "detail": "Current run results archived and the session was reset",
            "archive": str(archive) if archive else None,
            "results_dir": str(RESULTS_DIR),
        }


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/api/overview")
def overview() -> dict[str, Any]:
    plan_rows = _csv_rows(RESULTS_DIR / "run_plan.csv")
    arm = os.environ.get("APE_MOT_ARM", "m6cache").lower()
    planned_scenarios = sorted({r.get("scenario", "") for r in plan_rows if r.get("scenario")})
    if not planned_scenarios:
        planned_scenarios = list({
            "core": ("M1", "M2", "M3", "M4", "M5", "M6"),
            "demo6": ("M1", "M2", "M3", "M4", "M5", "M6"),
            "m6cache": ("M6",),
            "m5embed": ("M5E",),
            "m1mem": ("M1",),
        }.get(arm, ()))
    readiness = {
        "database": {"ok": DB_PATH.is_file(), "detail": str(DB_PATH)},
        "id_pool": {"ok": (ROOT / "scratch" / "id_pool_mot.json").is_file(),
                    "detail": str(ROOT / "scratch" / "id_pool_mot.json")},
        "k6": _command_ready("k6"),
        "varnish": _command_ready("varnishd"),
        "tmux": _command_ready("tmux"),
        "sudo": _sudo_ready(),
        "netem": {"ok": False, "detail": "disabled: WSL kernel has no sch_netem (demo-only)"},
    }
    artifacts: list[str] = []
    artifact_versions: dict[str, int] = {}
    for name in ("fig_mot_latency_by_scenario.png", "fig_mot_throughput_by_scenario.png",
                 "fig_mot_payload_by_scenario.png", "fig_mot_round_trips_by_scenario.png",
                 "fig_mot_client_flow_latency.png", "fig_mot_overload.png"):
        path = RESULTS_DIR / "analysis" / name
        try:
            artifact_versions[name] = path.stat().st_mtime_ns
            artifacts.append(name)
        except FileNotFoundError:
            pass
    return {
        "readiness": readiness,
        "progress": _progress(),
        "metrics": _metric_summary(),
        "jobs": {name: _job_state(name) for name in ("parity", "resume", "experiment", "validate", "analyze")},
        "artifacts": artifacts,
        "artifact_versions": artifact_versions,
        "results_dir": str(RESULTS_DIR),
        "experiment_config": {
            "arm": arm,
            "session_id": os.environ.get("APE_SESSION_ID", RESULTS_DIR.name),
            "scenarios": planned_scenarios,
            "run_duration": os.environ.get("APE_RUN_DURATION", "5s"),
            "n_warmup": int(os.environ.get("APE_N_WARMUP", "1")),
            "n_measured": int(os.environ.get("APE_N_MEASURED", "3")),
            "reduced_demo_grid": arm == "demo6",
        },
        "demo_only": True,
    }


@app.get("/api/profile")
def profile() -> dict[str, Any]:
    if not DB_PATH.is_file():
        raise HTTPException(404, f"Database not found: {DB_PATH}")
    connection = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        counts = {table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                  for table in ("sequence", "image", "track", "detection", "class")}
        density = dict(connection.execute(
            "SELECT density_tier, COUNT(*) FROM image GROUP BY density_tier"
        ).fetchall())
        classes = [{"class_id": row[0], "count": row[1]}
                   for row in connection.execute(
                       "SELECT class_id, COUNT(*) FROM detection GROUP BY class_id ORDER BY COUNT(*) DESC"
                   ).fetchall()]
    finally:
        connection.close()
    stored_profile = json.loads((ROOT / "design" / "mot_profile.json").read_text(encoding="utf-8"))
    return {"counts": counts, "density": density, "classes": classes,
            "density_tiers": stored_profile.get("image_density_tiers", {}),
            "distribution": stored_profile.get("detections_per_image", {})}


@app.post("/api/actions/{action}")
def run_action(action: str, confirm: str | None = None) -> dict[str, Any]:
    if action == "reset":
        return _reset_results(confirm)
    env = _demo_env()
    plan = RESULTS_DIR / "run_plan.csv"
    results = RESULTS_DIR / "results.csv"
    if action == "parity":
        return _spawn("parity", [sys.executable, "-m", "pytest", "tests/test_parity_mot.py", "-q", "-rs"], env)
    if action == "resume":
        if not plan.exists():
            raise HTTPException(409, "No run_plan.csv exists yet")
        return _spawn("resume", [sys.executable, "orchestrator/run_experiment.py",
                                  "--simulate-resume", "--run-plan", str(plan),
                                  "--results", str(results)], env)
    if action == "experiment":
        return _spawn("experiment", ["bash", "tools/run_wsl_demo.sh"], env)
    if action == "validate":
        if not results.exists():
            raise HTTPException(409, "No results.csv exists yet")
        return _spawn("validate", [sys.executable, "tools/validate_results.py",
                                    "--run-plan", str(plan), "--results", str(results)], env)
    if action == "analyze":
        if not results.exists():
            raise HTTPException(409, "No results.csv exists yet")
        return _spawn("analyze", [sys.executable, "tools/analyze_mot_scenarios.py",
                                   "--input", str(results),
                                   "--output-dir", str(RESULTS_DIR / "analysis")], env)
    raise HTTPException(404, f"Unknown action: {action}")


@app.post("/api/actions/experiment/stop")
def stop_experiment() -> dict[str, Any]:
    proc = _jobs.get("experiment")
    if proc is not None and proc.poll() is None:
        os.killpg(proc.pid, signal.SIGINT)
        return {"ok": True, "detail": "Interrupt sent to experiment process group"}
    lock_path = RESULTS_DIR / ".locks" / "orchestrator.lock"
    if lock_path.exists():
        try:
            pid = int(json.loads(lock_path.read_text(encoding="utf-8"))["pid"])
            if psutil.pid_exists(pid):
                os.kill(pid, signal.SIGINT)
                return {"ok": True, "detail": f"Interrupt sent to orchestrator pid {pid}"}
        except (KeyError, ValueError, OSError, json.JSONDecodeError):
            pass
    return {"ok": False, "detail": "No running experiment found"}


@app.get("/api/logs/{name}")
def logs(name: str) -> dict[str, Any]:
    if name == "experiment":
        path = RESULTS_DIR / "orchestrator_console.log"
        if not path.exists():
            path = _job_logs.get(name, path)
    else:
        path = _job_logs.get(name, UI_LOG_DIR / f"{name}.log")
    return {"name": name, "path": str(path), "content": _tail(path), "job": _job_state(name)}


@app.get("/api/artifacts/{name}")
def artifact(name: str) -> FileResponse:
    allowed = {"fig_mot_latency_by_scenario.png", "fig_mot_throughput_by_scenario.png",
               "fig_mot_payload_by_scenario.png", "fig_mot_round_trips_by_scenario.png",
               "fig_mot_client_flow_latency.png", "fig_mot_overload.png"}
    if name not in allowed:
        raise HTTPException(404, "Unknown artifact")
    path = RESULTS_DIR / "analysis" / name
    if not path.is_file():
        raise HTTPException(404, "Artifact has not been generated")
    return FileResponse(path, media_type="image/png")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
