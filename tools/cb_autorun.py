"""Background CB autorun: fire tools/cb_run.py whenever a key is available.

The dashboard exposes this as an /api/autorun toggle; the CLI here can
do the same headless. Single shared state so multiple consumers see
the same view of "is autorun enabled, when did it last fire".

CLI usage:
    python3 tools/cb_autorun.py status
    python3 tools/cb_autorun.py start             # blocks; prints fires
    python3 tools/cb_autorun.py start --once      # fire one CB run, exit
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import os as _os
sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from cli_util import project_root  # noqa: E402

logger = logging.getLogger(__name__)

DEFAULT_MOD_URL = "http://localhost:6790"
POLL_INTERVAL_S = 60.0          # how often we check key count
MIN_GAP_BETWEEN_FIRES_S = 60.0  # never fire more than once per minute
CB_RUN_TIMEOUT_S = 420          # cb_run.py is slow (5-50 turn battle)


# ============================================================================
# Shared state — one process owns one autorun thread
# ============================================================================

_state: dict = {
    "enabled": False,
    "last_fired": None,
    "last_result": None,
    "thread_started": False,
}
_lock = threading.Lock()


def state() -> dict:
    """Snapshot of autorun state. JSON-safe (no thread/lock objects)."""
    with _lock:
        return {k: v for k, v in _state.items() if k != "thread_started"}


def enable() -> None:
    with _lock:
        _state["enabled"] = True


def disable() -> None:
    with _lock:
        _state["enabled"] = False


def ensure_thread(mod_url: str = DEFAULT_MOD_URL,
                  root: Path | None = None) -> None:
    """Idempotent: start the background poller thread if not already running."""
    with _lock:
        if _state["thread_started"]:
            return
        _state["thread_started"] = True
    threading.Thread(
        target=_worker, args=(mod_url, root or project_root()),
        daemon=True, name="cb-autorun",
    ).start()


# ============================================================================
# Worker
# ============================================================================

def _check_key_count(mod_url: str) -> int | None:
    """Pull current CB key count from the mod. None on any failure."""
    try:
        with urllib.request.urlopen(f"{mod_url}/all-resources", timeout=10) as r:
            data = json.loads(r.read().decode())
        if isinstance(data, dict):
            return int(data.get("cb_keys") or 0)
    except Exception:
        pass
    return None


def _fire_once(root: Path) -> dict:
    """Synchronously run tools/cb_run.py once. Returns a result dict
    suitable for setting on `_state['last_result']`."""
    try:
        result = subprocess.run(
            [sys.executable, str(root / "tools" / "cb_run.py")],
            cwd=str(root), timeout=CB_RUN_TIMEOUT_S,
            capture_output=True, text=True,
        )
        return {
            "ok": result.returncode == 0,
            "stdout_tail": (result.stdout or "")[-500:],
            "stderr_tail": (result.stderr or "")[-500:],
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timed out (>{CB_RUN_TIMEOUT_S//60}min)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _worker(mod_url: str, root: Path) -> None:
    """Poll loop: every POLL_INTERVAL_S, if enabled and a key is available
    and we haven't fired recently, run cb_run.py."""
    while True:
        time.sleep(POLL_INTERVAL_S)
        with _lock:
            enabled = _state["enabled"]
        if not enabled:
            continue
        keys = _check_key_count(mod_url)
        if keys is None or keys <= 0:
            continue
        with _lock:
            last = _state.get("last_fired") or 0
            if time.time() - last < MIN_GAP_BETWEEN_FIRES_S:
                continue
            _state["last_fired"] = time.time()
        result = _fire_once(root)
        with _lock:
            _state["last_result"] = result


# ============================================================================
# CLI
# ============================================================================

def _main() -> int:
    import argparse

    ap = argparse.ArgumentParser(
        description="CB autorun — fire tools/cb_run.py when a key is available.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="print current state")

    st = sub.add_parser("start",
                        help="enable autorun + block, printing fires to stdout")
    st.add_argument("--once", action="store_true",
                    help="fire one CB run synchronously and exit")
    st.add_argument("--mod-url", default=DEFAULT_MOD_URL)

    args = ap.parse_args()

    if args.cmd == "status":
        print(json.dumps(state(), indent=2, default=str))
        return 0

    if args.cmd == "start":
        if args.once:
            keys = _check_key_count(args.mod_url)
            if keys is None:
                print("ERR: mod not reachable", file=sys.stderr)
                return 2
            if keys <= 0:
                print("No CB keys available.")
                return 1
            print(f"Firing cb_run.py (keys available: {keys})...")
            result = _fire_once(project_root())
            print(json.dumps(result, indent=2))
            return 0 if result.get("ok") else 3
        # Long-running mode: enable + watch
        enable()
        ensure_thread(args.mod_url)
        print(f"autorun enabled (poll every {POLL_INTERVAL_S}s); Ctrl+C to stop")
        last_fired = None
        try:
            while True:
                time.sleep(5)
                snap = state()
                if snap.get("last_fired") and snap["last_fired"] != last_fired:
                    last_fired = snap["last_fired"]
                    res = snap.get("last_result") or {}
                    print(f"  fired at {time.ctime(last_fired)}: ok={res.get('ok')}")
        except KeyboardInterrupt:
            disable()
            print("\nautorun disabled")
            return 0


if __name__ == "__main__":
    raise SystemExit(_main())
