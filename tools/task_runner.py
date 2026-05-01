"""Generic task runner with a status registry.

A "task" is just a callable that takes a string id and returns truthy
on success. The runner manages a state dict (currently running task,
per-task log/status) so multiple consumers can poll it.

The dashboard uses this to chain CLI tool runs ("connect", "cb",
"shop", etc.). The CLI here exposes the same registry.

CLI usage:
    python3 tools/task_runner.py list              # show registered tasks
    python3 tools/task_runner.py run cb            # run one task
    python3 tools/task_runner.py run connect cb    # chain multiple
"""
from __future__ import annotations

import logging
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


# ============================================================================
# Generic state machine
# ============================================================================
# Module-level state. Single shared registry — a process is either running a
# chain or not; there's no need for multiple parallel chains in this app.

_run_state: dict = {
    "running": False,
    "started_at": None,
    "current_task_id": None,
    "tasks": {},  # task_id -> {status, log:[], started_at, finished_at}
}
_run_lock = threading.Lock()


def state() -> dict:
    """Return a *snapshot copy* of the current run state. The dashboard's
    /api/state polls this; CLI consumers can poll it too."""
    with _run_lock:
        return {
            "running": _run_state["running"],
            "started_at": _run_state["started_at"],
            "current_task_id": _run_state["current_task_id"],
            "tasks": {
                tid: {
                    "status": v.get("status"),
                    "log": list(v.get("log") or []),
                    "started_at": v.get("started_at"),
                    "finished_at": v.get("finished_at"),
                }
                for tid, v in _run_state["tasks"].items()
            },
        }


def rlog(tid: str, msg) -> None:
    """Append a log line for the given task id. Trimmed to 80 entries."""
    with _run_lock:
        t = _run_state["tasks"].setdefault(tid, {"log": []})
        t.setdefault("log", []).append({"ts": time.time(), "msg": str(msg)[:400]})
        if len(t["log"]) > 80:
            t["log"] = t["log"][-80:]
    logger.info("[run:%s] %s", tid, msg)


def task_subprocess(tid: str, args: list[str], cwd: Path | None = None,
                    timeout: int = 600) -> bool:
    """Run a Python tool, streaming stdout into the task log."""
    rlog(tid, f"exec: {' '.join(args)}")
    try:
        p = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=str(cwd) if cwd else None, text=True, bufsize=1,
        )
        if p.stdout:
            for line in iter(p.stdout.readline, ''):
                line = line.rstrip()
                if line:
                    rlog(tid, line)
        p.wait(timeout=timeout)
        rlog(tid, f"exit code {p.returncode}")
        return p.returncode == 0
    except Exception as e:
        rlog(tid, f"subprocess err: {e}")
        return False


def runner_thread(task_ids: list[str], registry: dict[str, Callable[[str], bool]]) -> None:
    """Drive a chain of tasks, updating module state. Call via start_run."""
    with _run_lock:
        _run_state["running"] = True
        _run_state["started_at"] = time.time()
        _run_state["tasks"] = {
            tid: {"status": "pending", "log": [], "started_at": None, "finished_at": None}
            for tid in task_ids
        }
    for tid in task_ids:
        if not _run_state["running"]:
            break  # stop requested
        with _run_lock:
            _run_state["current_task_id"] = tid
            _run_state["tasks"][tid]["status"] = "running"
            _run_state["tasks"][tid]["started_at"] = time.time()
        impl = registry.get(tid)
        if impl is None:
            rlog(tid, "not implemented for this task id")
            status = "skipped"
        else:
            try:
                status = "done" if impl(tid) else "error"
            except Exception as e:
                rlog(tid, f"unhandled exception: {e}")
                status = "error"
        with _run_lock:
            _run_state["tasks"][tid]["status"] = status
            _run_state["tasks"][tid]["finished_at"] = time.time()
    with _run_lock:
        _run_state["current_task_id"] = None
        _run_state["running"] = False


def start_run(task_ids: list[str], registry: dict[str, Callable[[str], bool]]) -> tuple[bool, str]:
    if _run_state["running"]:
        return False, "a run is already in progress"
    ids = [str(x) for x in task_ids]
    if not ids:
        return False, "no task_ids"
    threading.Thread(target=runner_thread, args=(ids, registry), daemon=True).start()
    return True, f"started {len(ids)} task(s)"


def stop_run() -> tuple[bool, str]:
    with _run_lock:
        if not _run_state["running"]:
            return False, "not running"
        _run_state["running"] = False  # current task finishes, loop exits
    return True, "stop requested (current task will finish)"


# ============================================================================
# Default task registry — CLI-tool wrappers per CLAUDE.md ("mod API only").
# Dashboard merges its own connect-task on top.
# ============================================================================

def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _task_cb(tid: str) -> bool:
    """Run tools/cb_daily.py --wait. Streams stdout into the task log."""
    return task_subprocess(tid, [sys.executable, str(_project_root() / "tools" / "cb_daily.py"), "--wait"], cwd=_project_root())


# Tasks with a pure mod-API CLI tool. Add more as tools/<x>_daily.py modules
# become available.
DEFAULT_REGISTRY: dict[str, Callable[[str], bool]] = {
    "cb": _task_cb,
}


# ============================================================================
# CLI — same registry the dashboard uses, runnable headless.
# ============================================================================

def _main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="show registered task ids")

    rn = sub.add_parser("run", help="run one or more tasks in sequence")
    rn.add_argument("task_ids", nargs="+", help="e.g. cb")

    args = ap.parse_args()

    if args.cmd == "list":
        for tid in DEFAULT_REGISTRY:
            print(tid)
        return 0

    if args.cmd == "run":
        unknown = [t for t in args.task_ids if t not in DEFAULT_REGISTRY]
        if unknown:
            print(f"ERR: unknown task id(s): {','.join(unknown)}", file=sys.stderr)
            print(f"Known: {','.join(DEFAULT_REGISTRY)}", file=sys.stderr)
            return 2
        ok, msg = start_run(args.task_ids, DEFAULT_REGISTRY)
        if not ok:
            print(f"ERR: {msg}", file=sys.stderr)
            return 3
        # Block until the chain finishes; flush log lines to stdout.
        last_seen: dict[str, int] = {tid: 0 for tid in args.task_ids}
        while True:
            snap = state()
            for tid in args.task_ids:
                tinfo = snap["tasks"].get(tid) or {}
                log = tinfo.get("log") or []
                for entry in log[last_seen.get(tid, 0):]:
                    print(f"[{tid}] {entry.get('msg','')}")
                last_seen[tid] = len(log)
            if not snap["running"]:
                # Final pass to grab any tail entries
                for tid in args.task_ids:
                    tinfo = snap["tasks"].get(tid) or {}
                    print(f"[{tid}] status={tinfo.get('status','?')}")
                return 0
            time.sleep(0.5)


if __name__ == "__main__":
    raise SystemExit(_main())
