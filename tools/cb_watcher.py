#!/usr/bin/env python3
"""
CB Death Watcher — polls /battle-state and kills Raid.exe at the first
player-hero death so the CB key is preserved for re-attempt.

CB keys are only debited on successful battle completion. Killing Raid
mid-fight discards the run without consuming the key. This tool turns
that protocol into automation: max data per key on tunes that don't yet
survive (Magic/Spirit MEN, new comp validation, sim regression captures).

Pre-conditions:
  - A CB battle is in progress (or about to start). Run this BEFORE
    pressing Start, or shortly after.
  - Mod is up at localhost:6790.

What it does:
  1. Waits for battle-active.
  2. Polls /battle-state every POLL_INTERVAL seconds.
  3. Snapshots /battle-log to disk every N polls (crash-resilience).
  4. On first player-hero death (or threshold), snapshots one last
     time and runs `taskkill /F /IM Raid.exe`.
  5. Exits 0 (killed cleanly), 1 (battle ended naturally first),
     2 (error / never reached battle).

Usage:
  python3 tools/cb_watcher.py                            # default: kill on 1st death
  python3 tools/cb_watcher.py --threshold 2              # wait for 2nd death
  python3 tools/cb_watcher.py --threshold all-but-one    # wait for team-near-wipe
  python3 tools/cb_watcher.py --grace-turns 5            # don't kill before boss turn 5
  python3 tools/cb_watcher.py --dry-run                  # log only, do not kill
  python3 tools/cb_watcher.py --tag magic-attempt-3      # add tag to snapshot filename
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MOD_BASE = "http://localhost:6790"

POLL_INTERVAL = 1.0           # seconds between battle-state polls
WAIT_POLL_INTERVAL = 2.0      # seconds while waiting for battle to start
WAIT_MAX_SECONDS = 600        # 10min cap on "waiting for battle"
SNAPSHOT_EVERY_N_POLLS = 30   # crash-resilience snapshot cadence


def mod_get(endpoint, params=None, timeout=10):
    try:
        r = requests.get(f"{MOD_BASE}{endpoint}", params=params, timeout=timeout)
        return r.json()
    except Exception as ex:
        return {"error": str(ex)}


def battle_active(bs):
    """True if /battle-state shows a live battle (player heroes present)."""
    if not bs or "error" in bs:
        return False
    heroes = bs.get("heroes") or []
    return any(h.get("side") == "player" for h in heroes)


def _is_dead(h):
    """A player hero is dead iff hp_cur <= 0. /battle-state has no
    `st` field for deaths — dead heroes either show hp_cur=0 or
    disappear from the list entirely. Verified 2026-06-21 from
    poll_log_cb_20260621_154630.json (Force-day capture)."""
    hp = h.get("hp_cur")
    if hp is None:
        hp = h.get("hp_pct")  # fallback if hp_cur missing
    if hp is None:
        return False  # can't tell — don't claim dead
    return hp <= 0


def player_dead_count(bs, expected_total=None):
    """Count dead player heroes. Counts vanished heroes too: if
    `expected_total` (the team size from the first live poll) is
    provided and the current player count is lower, the missing
    heroes are treated as dead."""
    if not bs or "error" in bs:
        return 0
    players = [h for h in (bs.get("heroes") or []) if h.get("side") == "player"]
    dead_visible = sum(1 for h in players if _is_dead(h))
    vanished = max(0, (expected_total or len(players)) - len(players))
    return dead_visible + vanished


def player_total(bs):
    if not bs or "error" in bs:
        return 0
    return sum(1 for h in (bs.get("heroes") or []) if h.get("side") == "player")


def boss_turn(bs):
    if not bs or "error" in bs:
        return 0
    heroes = bs.get("heroes") or []
    boss = next((h for h in heroes if h.get("side") == "enemy"), None)
    return (boss or {}).get("turn_n", 0) or 0


def snapshot_battle_log(snapshot_dir, tag):
    """Append the current /battle-log payload to a JSON snapshot file.

    Keeps full-fidelity tick data even if Raid dies mid-write."""
    try:
        log = requests.get(f"{MOD_BASE}/battle-log", timeout=15).json()
    except Exception as ex:
        return None, str(ex)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"cb_watcher_{tag}_{ts}.json" if tag else f"cb_watcher_{ts}.json"
    path = snapshot_dir / name
    try:
        path.write_text(json.dumps(log, indent=2), encoding="utf-8")
        return path, None
    except Exception as ex:
        return None, str(ex)


def _hero_trace_row(h):
    """Compact per-hero state for the poll trace. Captures the fields
    that matter for death-sequence analysis (hp_cur, hp_pct, dmg_taken,
    turn_n, can_atk) without dragging in mods/sk/eff."""
    return {
        "id": h.get("id"),
        "type_id": h.get("type_id"),
        "hp_cur": h.get("hp_cur"),
        "hp_pct": h.get("hp_pct"),
        "hp_max": h.get("hp_max"),
        "dmg_taken": h.get("dmg_taken"),
        "turn_n": h.get("turn_n"),
        "can_atk": h.get("can_atk"),
        "tm": h.get("tm"),
    }


def append_poll_trace(trace_path, poll_n, ts, bs):
    """Append one JSONL row capturing per-hero state at this poll.

    Lets us reconstruct the death sequence after the fact even if
    snapshot files are cleaned up. Tiny on disk (one line per poll).
    Errors fall through silently — the trace is best-effort, never
    blocks the kill decision."""
    if not trace_path:
        return
    try:
        if "error" in (bs or {}):
            row = {"poll": poll_n, "ts": ts, "error": bs.get("error", "")[:120]}
        else:
            heroes = bs.get("heroes") or []
            row = {
                "poll": poll_n,
                "ts": ts,
                "active": bs.get("active"),
                "players": [_hero_trace_row(h) for h in heroes if h.get("side") == "player"],
                "boss": next(
                    (_hero_trace_row(h) for h in heroes if h.get("side") == "enemy"),
                    None,
                ),
            }
        with open(trace_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:
        pass


def kill_raid():
    """taskkill /F /IM Raid.exe — leaves PlariumPlay running.

    Returns (rc, stdout, stderr)."""
    res = subprocess.run(
        ["taskkill", "/F", "/IM", "Raid.exe"],
        capture_output=True, text=True,
    )
    return res.returncode, res.stdout.strip(), res.stderr.strip()


def parse_threshold(raw, total_heroes_when_known):
    """Resolve --threshold N or 'all-but-one' against current team size."""
    if raw == "all-but-one":
        return max(1, total_heroes_when_known - 1)
    try:
        n = int(raw)
    except ValueError:
        raise SystemExit(f"--threshold must be an int or 'all-but-one', got {raw!r}")
    return max(1, n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", default="1",
                    help="Number of dead player heroes that triggers kill. "
                         "Int or 'all-but-one'. Default: 1 (first death).")
    ap.add_argument("--grace-turns", type=int, default=0,
                    help="Do not kill before boss turn N, even if deaths occur. "
                         "Useful for capturing early-game data when team is fragile.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Log the death + snapshot, but do NOT taskkill Raid.")
    ap.add_argument("--tag", default="",
                    help="Tag appended to snapshot filename (e.g. 'magic-attempt-3').")
    ap.add_argument("--snapshot-dir", default=str(PROJECT_ROOT),
                    help="Where to write the battle-log snapshot. Default: repo root.")
    ap.add_argument("--no-wait", action="store_true",
                    help="Skip the wait-for-battle phase; assume battle already active.")
    args = ap.parse_args()

    snapshot_dir = Path(args.snapshot_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    # Always-on per-poll JSONL trace — cheap, and the only way to
    # reconstruct the death sequence after the fact.
    ts_start = datetime.now().strftime("%Y%m%d_%H%M%S")
    trace_name = (
        f"cb_watcher_{args.tag}_{ts_start}.poll.jsonl"
        if args.tag else f"cb_watcher_{ts_start}.poll.jsonl"
    )
    trace_path = snapshot_dir / trace_name
    trace_path.write_text("", encoding="utf-8")  # truncate any stale file
    print(f"Poll trace: {trace_path}")

    # Pre-flight: mod up?
    status = mod_get("/status")
    if "error" in status:
        print(f"ERROR: mod not reachable at {MOD_BASE} — {status['error']}")
        return 2
    print(f"Mod up: scene={status.get('scene')}")

    # Phase 1: wait for battle
    if not args.no_wait:
        print("Waiting for CB battle to become active...")
        waited = 0.0
        while waited < WAIT_MAX_SECONDS:
            bs = mod_get("/battle-state")
            if battle_active(bs):
                print(f"  battle active: {player_total(bs)} heroes detected")
                break
            time.sleep(WAIT_POLL_INTERVAL)
            waited += WAIT_POLL_INTERVAL
        else:
            print(f"ERROR: no battle within {WAIT_MAX_SECONDS}s")
            return 2

    # Phase 2: poll loop
    poll_n = 0
    prev_dead = 0
    prev_boss_turn = 0
    threshold = None         # resolved on first state with a known team size
    starting_team_size = None  # locked at first live poll; used for vanish detection
    inactive_streak = 0
    INACTIVE_CONFIRM = 5     # consecutive inactive polls before scene-checking

    while True:
        bs = mod_get("/battle-state")
        poll_n += 1
        now_ts = time.time()

        # Per-poll trace (always-on, best-effort)
        append_poll_trace(trace_path, poll_n, now_ts, bs)

        # Crash-resilience snapshot every N polls
        if poll_n % SNAPSHOT_EVERY_N_POLLS == 0:
            snapshot_battle_log(snapshot_dir, args.tag)

        # Transient errors: skip but keep polling
        if "error" in bs:
            time.sleep(POLL_INTERVAL)
            continue

        # Battle-ended detection — be CONSERVATIVE. /battle-state can
        # briefly show no player heroes during scene transitions
        # (e.g. between waves, dialog overlays). Require N consecutive
        # inactive polls AND scene confirmation, mirroring cb_run.py.
        if not battle_active(bs):
            inactive_streak += 1
            if inactive_streak >= INACTIVE_CONFIRM:
                st = mod_get("/status")
                scene = (st or {}).get("scene", "")
                ctxs = (mod_get("/view-contexts") or {}).get("contexts", [])
                finish_up = any(
                    "BattleFinish" in (c.get("dialog") or "")
                    for c in ctxs
                )
                if scene != "Dungeon_Clan" or finish_up:
                    print(f"Battle ended naturally (scene={scene}, "
                          f"finish_dialog={finish_up}, inactive={inactive_streak} polls).")
                    snapshot_battle_log(snapshot_dir, args.tag)
                    return 1
                # Still in CB scene — likely a transient glitch. Keep polling.
            time.sleep(POLL_INTERVAL)
            continue
        inactive_streak = 0

        # Resolve threshold + lock team size once we know it
        if threshold is None:
            total = player_total(bs)
            starting_team_size = total
            threshold = parse_threshold(args.threshold, total)
            print(f"Threshold resolved: kill at {threshold}/{total} dead "
                  f"(grace-turns={args.grace_turns})")

        # Progress reporting (deaths counted against starting team size)
        cur_dead = player_dead_count(bs, expected_total=starting_team_size)
        cur_turn = boss_turn(bs)
        if cur_dead != prev_dead or cur_turn != prev_boss_turn:
            print(f"  poll {poll_n}: boss turn {cur_turn}, dead {cur_dead}/{player_total(bs)}")
            prev_dead = cur_dead
            prev_boss_turn = cur_turn

        # Trigger condition
        if cur_dead >= threshold:
            if cur_turn < args.grace_turns:
                # Death below grace floor — log but keep polling
                # (we'd rather burn the key than discard sub-grace data)
                time.sleep(POLL_INTERVAL)
                continue

            print(f"\n*** TRIGGER: {cur_dead}/{player_total(bs)} dead at boss turn {cur_turn} ***")
            snap_path, snap_err = snapshot_battle_log(snapshot_dir, args.tag)
            if snap_path:
                print(f"  snapshot: {snap_path}")
            else:
                print(f"  snapshot FAILED: {snap_err}")

            if args.dry_run:
                print("  --dry-run: NOT killing Raid")
                return 0

            print("  taskkill /F /IM Raid.exe ...")
            rc, out, err = kill_raid()
            if rc == 0:
                print(f"  raid killed (key preserved). {out}")
            else:
                print(f"  taskkill rc={rc} — {err or out}")
            return 0

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    sys.exit(main())
