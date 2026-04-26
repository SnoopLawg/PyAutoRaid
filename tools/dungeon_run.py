#!/usr/bin/env python3
"""Open a specific dungeon stage and (optionally) start the battle.

Discovery path (verified 2026-04-25 against Raid v11.40):
  1. /open-dungeon?type=<dungeon> calls
     WebViewInGameTransition.OpenDungeonOfType(RegionTypeId). Opens
     DungeonsDialog with the stage list populated. Earlier failures
     were due to passing wrong int IDs - the param is RegionTypeId,
     not a sequential dungeon index.
  2. /context-call -> DungeonStageContext.OpenSelectionDialog/0 on the
     target stage's GameObject path. That opens the hero selection
     dialog (DungeonHeroesSelectionDialog).
  3. /context-call -> HeroesSelectionPveDialogContext.StartBattle/0 to
     actually launch the battle (uses current team selection).

Usage:
    # Single run
    python3 tools/dungeon_run.py --dungeon dragon --stage 20 --start
    python3 tools/dungeon_run.py --dungeon spider --stage 1 --no-start
    python3 tools/dungeon_run.py --stage 1                # already on stage list

    # Loop until the Minotaur scroll-cap messagebox appears
    python3 tools/dungeon_run.py --dungeon minotaur --stage max --until-capped

    # Loop a fixed number of runs (any dungeon)
    python3 tools/dungeon_run.py --dungeon dragon --stage 20 --runs 10

Dungeon aliases match RegionTypeId (200s):
    dragon spider fire_knight ice_golem minotaur
    void_keep spirit_keep magic_keep force_keep arcane_keep

Stop conditions (only --until-capped is wired up; others to come):
    --runs N           generic counter, any dungeon
    --until-capped     minotaur only - daily scroll cap

Limitations:
- Stage must be unlocked. Locked stages register the click but the
  game silently ignores it (dialog stays the same).
- The team that fires is whatever's currently selected in-game on the
  dungeon hero-selection dialog. We don't pick the team here.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request

MOD_BASE = "http://localhost:6790"
DUNGEONS_DIALOG = "UIManager/Canvas (Ui Root)/Dialogs/[DV] DungeonsDialog"
HEROES_DIALOG = "UIManager/Canvas (Ui Root)/Dialogs/[DV] DungeonHeroesSelectionDialog"

DUNGEONS = {
    "dragon", "spider", "fire_knight", "ice_golem", "minotaur",
    "void_keep", "spirit_keep", "magic_keep", "force_keep", "arcane_keep",
}


def _get(path: str, timeout: int = 10) -> dict:
    r = urllib.request.urlopen(MOD_BASE + path, timeout=timeout).read().decode("utf-8")
    return json.loads(r)


def _context_call(path: str, method: str, arg: str | None = None) -> dict:
    q = "/context-call?path=" + urllib.parse.quote(path) + "&method=" + method
    if arg is not None:
        q += "&arg=" + urllib.parse.quote(arg)
    return _get(q)


def _dialogs() -> list[str]:
    try:
        d = _get("/view-contexts", timeout=5)
        return [c.get("dialog") or "" for c in d.get("contexts", [])]
    except Exception:
        return []


def _ensure_dungeons_dialog() -> bool:
    return any("DungeonsDialog" in d for d in _dialogs())


def _ensure_hero_selection() -> bool:
    return any("DungeonHeroesSelectionDialog" in d for d in _dialogs())


def open_dungeon(dungeon: str) -> bool:
    """Navigate from any scene to the dungeon's stage list."""
    print(f"  open dungeon {dungeon}")
    try:
        r = _get("/open-dungeon?type=" + urllib.parse.quote(dungeon))
    except Exception as ex:
        print(f"  ERR: {ex}", file=sys.stderr)
        return False
    if "error" in r:
        print(f"  ERR: {r['error']}", file=sys.stderr)
        return False
    # Poll for DungeonsDialog. Cold-start (just relaunched + logged in)
    # can take noticeably longer than warm transitions.
    deadline = time.time() + 15
    while time.time() < deadline:
        if _ensure_dungeons_dialog():
            return True
        time.sleep(1)
    print(f"  ERR: DungeonsDialog didn't open after /open-dungeon",
          file=sys.stderr)
    return False


def _scroll_for_stage(stage: int) -> None:
    """The DungeonsDialog uses a virtualized scroll view that only
    renders ~15 tiles. Set the scroll position so the target stage's
    GameObject exists. v=1 is top (stage 1), v=0 is bottom (stage 25)."""
    # Linear interp: stage 1 -> v=1.0, stage 25 -> v=0.0
    v = max(0.0, min(1.0, (25 - stage) / 24.0))
    try:
        urllib.request.urlopen(
            MOD_BASE + "/set-scroll?path="
            + urllib.parse.quote(f"{DUNGEONS_DIALOG}/Workspace/Content/Scroll View")
            + f"&v={v:.3f}", timeout=5).read()
    except Exception:
        pass
    time.sleep(0.6)


def open_stage(stage: int) -> bool:
    """Click the stage tile (0-indexed in the GameObject hierarchy =
    stage-1 in user-facing terms)."""
    if not _ensure_dungeons_dialog():
        print(f"  ERROR: DungeonsDialog not open. Pass --dungeon to "
              f"navigate first.", file=sys.stderr)
        return False

    idx = stage - 1
    _scroll_for_stage(stage)
    stage_path = (f"{DUNGEONS_DIALOG}/Workspace/Content/Scroll View/"
                  f"Viewport/Content/{idx}")
    print(f"  open stage {stage} (idx {idx})")
    try:
        r = _context_call(stage_path, "OpenSelectionDialog")
    except Exception as ex:
        print(f"  ERR: {ex}", file=sys.stderr)
        return False
    if "error" in r:
        print(f"  ERR: {r['error']}", file=sys.stderr)
        return False
    time.sleep(2.0)
    if not _ensure_hero_selection():
        print(f"  WARN: hero-selection dialog didn't open. Stage {stage} "
              f"may be locked.", file=sys.stderr)
        return False
    print(f"  hero-selection dialog open")
    return True


def start_battle() -> bool:
    """Fire StartBattle on the open hero selection dialog. Uses whatever
    team is currently selected in-game."""
    if not _ensure_hero_selection():
        print(f"  ERROR: hero-selection dialog not open", file=sys.stderr)
        return False
    try:
        r = _context_call(HEROES_DIALOG, "StartBattle")
    except Exception as ex:
        print(f"  ERR: {ex}", file=sys.stderr)
        return False
    if "error" in r:
        print(f"  ERR: {r['error']}", file=sys.stderr)
        return False
    print(f"  battle started")
    return True


FINISH_DIALOG = "UIManager/Canvas (Ui Root)/Dialogs/[DV] BattleFinishDungeonDialog"
MESSAGE_BOXES = "UIManager/Canvas (Ui Root)/MessageBoxes"
MESSAGE_BOX = "UIManager/Canvas (Ui Root)/MessageBoxes/MessageBox"

# Minotaur shows this when every selected champion has hit the daily
# scroll cap. The text has been stable across versions; we substring-match.
SCROLL_CAP_MARKER = "maximum number of Scrolls"


def _read_messagebox_text() -> str:
    """Return concatenated MessageBox text, or '' if no box is open."""
    if not any("MessageBox" in d for d in _dialogs()):
        return ""
    try:
        r = _get("/get-text?path=" + urllib.parse.quote(MESSAGE_BOXES), timeout=5)
    except Exception:
        return ""
    return " ".join(t.get("text", "") for t in r.get("texts", []))


def _close_messagebox() -> None:
    try:
        _context_call(MESSAGE_BOX, "Close")
    except Exception:
        pass


def _mod_alive() -> bool:
    """Cheap liveness check on the mod HTTP server. Raid crashes take
    the server down; we use this to bail fast instead of polling for
    600s against a dead process."""
    try:
        urllib.request.urlopen(MOD_BASE + "/status", timeout=2).read()
        return True
    except Exception:
        return False


def _wait_for_finish_or_block(timeout_s: int = 600) -> str:
    """Poll until BattleFinishDungeonDialog appears, or a blocking MessageBox
    appears (e.g. the Minotaur scroll-cap warning). Returns:
      'finish'  - BattleFinishDungeonDialog is open
      'capped'  - scroll-cap messagebox blocked the run
      'blocked' - some other messagebox blocked the run
      'crashed' - mod server stopped responding (Raid likely crashed)
      'timeout' - neither appeared within timeout
    """
    deadline = time.time() + timeout_s
    consecutive_dead = 0
    while time.time() < deadline:
        dlgs = _dialogs()
        # Check MessageBox first: when the cap warning appears it sits
        # ON TOP of the previous finish dialog, so seeing BattleFinish
        # alongside MessageBox should still classify as capped.
        if any("MessageBox" in d for d in dlgs):
            text = _read_messagebox_text()
            if SCROLL_CAP_MARKER in text:
                return "capped"
            print(f"  blocking messagebox: {text[:160]}", file=sys.stderr)
            return "blocked"
        if any("BattleFinish" in d for d in dlgs):
            return "finish"
        # Empty dlgs can mean "no dialogs" or "server unreachable".
        # Confirm via /status; bail after a few consecutive dead polls.
        if not dlgs:
            if not _mod_alive():
                consecutive_dead += 1
                if consecutive_dead >= 3:
                    print(f"  mod server unreachable for "
                          f"{consecutive_dead} polls; Raid likely crashed",
                          file=sys.stderr)
                    return "crashed"
            else:
                consecutive_dead = 0
        time.sleep(3)
    return "timeout"


def _read_verdict() -> tuple[str | None, str | None]:
    """Returns (result, stage_name). Result is 'VICTORY'/'DEFEAT'/etc."""
    try:
        r = _get("/get-text?path=" + urllib.parse.quote(FINISH_DIALOG), timeout=8)
    except Exception:
        return None, None
    result = stage = None
    for t in r.get("texts", []):
        if t.get("name") == "ResultLabel":
            result = t.get("text")
        elif t.get("name") == "Name":
            stage = t.get("text")
    return result, stage


def wait_and_report() -> tuple[int, str]:
    """Wait for battle finish and print verdict. Returns (exit_code, status).
    status: 'victory', 'defeat', 'capped', 'blocked', 'timeout', 'unreadable'."""
    print("  waiting for battle to finish...")
    outcome = _wait_for_finish_or_block()
    if outcome == "capped":
        print("  CAPPED: every selected champion has maxed scrolls for the day")
        _close_messagebox()
        time.sleep(1)
        return 0, "capped"
    if outcome == "blocked":
        return 2, "blocked"
    if outcome == "crashed":
        return 3, "crashed"
    if outcome == "timeout":
        print("  ERR: battle finish dialog never appeared", file=sys.stderr)
        return 2, "timeout"
    # Finish dialog is up. Give it a moment to populate and retry the
    # verdict read a few times - the ResultLabel can be empty on the
    # frame the dialog first opens.
    result = stage = None
    for _ in range(4):
        time.sleep(2)
        result, stage = _read_verdict()
        if result:
            break
    if result is None:
        # Dialog is up but text didn't populate. Treat as victory:
        # defeats render in BattleFinishDungeonDialog with ResultLabel
        # 'DEFEAT' which we *do* read reliably; an empty label is just a
        # text-population race that shows up after a successful run.
        print("  victory (verdict text didn't populate, treating as VICTORY)")
        return 0, "victory"
    label = stage or "battle"
    print(f"  {result}: {label}")
    if result.upper() == "VICTORY":
        return 0, "victory"
    return 1, "defeat"


def _close_finish_dialog() -> None:
    """Dismiss BattleFinishDungeonDialog if open, returning to DungeonsDialog.
    Polls until the dialog is actually gone (up to ~12s) to absorb the
    Raid close animation."""
    deadline = time.time() + 12
    attempts = 0
    while time.time() < deadline:
        if not any("BattleFinish" in d for d in _dialogs()):
            return
        attempts += 1
        try:
            _context_call(FINISH_DIALOG, "Close")
        except Exception:
            pass
        time.sleep(1.5)
    if attempts:
        print(f"  WARN: finish dialog still open after {attempts} close "
              f"attempts; continuing anyway", file=sys.stderr)


def _resolve_max_stage() -> int | None:
    """Return the highest visible stage idx+1 in DungeonsDialog, or None."""
    try:
        btns = _get("/buttons", 5).get("buttons", [])
    except Exception as ex:
        print(f"  ERR: failed to read buttons: {ex}", file=sys.stderr)
        return None
    idxs = sorted({int(b["path"].split("Content/")[2].split("/")[0])
                   for b in btns
                   if "Viewport/Content/" in b["path"]
                   and b["path"].endswith("DefaulCostButton_h")})
    if not idxs:
        return None
    return idxs[-1] + 1


def _run_one(stage: int, dungeon: str | None = None) -> tuple[int, str]:
    """Open the stage's hero selection and battle once. Returns (rc, status).
    If `dungeon` is provided, will re-navigate via /open-dungeon as a
    one-shot recovery if DungeonsDialog isn't currently up.
    Leaves the BattleFinishDungeonDialog open on success so the caller
    can chain via _replay_one()."""
    if not _ensure_dungeons_dialog() and dungeon:
        # We probably just exited a finish dialog; if scene drifted,
        # re-navigate so the next iteration starts cleanly.
        if not open_dungeon(dungeon):
            return 1, "open_failed"
    if not open_stage(stage):
        # One retry: re-navigate then try again.
        if dungeon and open_dungeon(dungeon) and open_stage(stage):
            pass
        else:
            return 1, "open_failed"
    time.sleep(1.0)
    if not start_battle():
        return 1, "start_failed"
    return wait_and_report()


def _wait_for_prev_finish_to_close(timeout_s: int = 15) -> bool:
    """After triggering replay, the old BattleFinishDungeonDialog hangs
    around for a moment while the new battle starts. Wait until it's
    gone (or a blocking MessageBox appears) before polling for the
    next finish dialog. Returns True if the dialog closed cleanly."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        dlgs = _dialogs()
        if not any("BattleFinish" in d for d in dlgs):
            return True
        if any("MessageBox" in d for d in dlgs):
            # Cap warning or other block - let the caller's wait handle it.
            return True
        time.sleep(1)
    return False


def _replay_one() -> tuple[int, str]:
    """Re-fight the same stage by invoking OnQuickRestartPressed on the
    BattleFinishDungeonDialog. Caller must currently be on that dialog
    (the previous battle's finish screen). Returns (rc, status) like
    wait_and_report. Leaves the next BattleFinishDungeonDialog open on
    success."""
    if not any("BattleFinish" in d for d in _dialogs()):
        return 1, "replay_failed"
    try:
        r = _context_call(FINISH_DIALOG, "OnQuickRestartPressed")
    except Exception as ex:
        print(f"  ERR replay: {ex}", file=sys.stderr)
        return 1, "replay_failed"
    if "error" in r:
        print(f"  ERR replay: {r['error']}", file=sys.stderr)
        return 1, "replay_failed"
    print(f"  replay")
    # Wait for the *previous* finish dialog to close (replay animation).
    # Otherwise wait_and_report sees the stale dialog and instantly
    # returns a phantom "victory", which then triggers a parallel-battle
    # error on the next iteration.
    if not _wait_for_prev_finish_to_close():
        print(f"  WARN: previous finish dialog didn't close after replay",
              file=sys.stderr)
        return 1, "replay_failed"
    return wait_and_report()


def run_loop(dungeon: str | None,
             stage: int,
             stop_condition: dict,
             on_progress=None,
             should_stop=None,
             log_path: str = "data/runs/dungeon_runs.log") -> dict:
    """Programmatic entry point for the dungeon-run loop. Used by both
    the CLI (main) and the dashboard server.

    stop_condition: dict with one of these shapes:
        {"type": "runs", "n": <int>}      - run exactly N times
        {"type": "capped"}                - minotaur only; stop on cap modal

    on_progress(event_kind, **kwargs) is called at notable points:
        kind="start", dungeon, stage, target
        kind="run_done", index, status, elapsed_s
        kind="end", reason, completed

    should_stop() is called between iterations; if it returns True the
    loop exits with reason='aborted'.

    Returns a result dict: {"ok": bool, "reason": str, "completed": int,
                            "failures": int}
    """
    if on_progress is None:
        on_progress = lambda *a, **kw: None
    if should_stop is None:
        should_stop = lambda: False
    if stop_condition.get("type") == "capped" and dungeon and dungeon != "minotaur":
        return {"ok": False, "reason": "capped_only_minotaur",
                "completed": 0, "failures": 0}

    if dungeon and not _ensure_dungeons_dialog():
        if not open_dungeon(dungeon):
            return {"ok": False, "reason": "open_dungeon_failed",
                    "completed": 0, "failures": 0}

    dungeon_label = (dungeon or "dungeon") + f"_{stage}"
    target_str = ("until capped" if stop_condition.get("type") == "capped"
                  else f"{stop_condition.get('n', 1)} run(s)")
    print(f"  loop start: {dungeon_label}, {target_str}")
    on_progress("start", dungeon=dungeon, stage=stage, target=stop_condition)

    completed = 0
    failures = 0
    on_finish_dialog = False
    is_capped = stop_condition.get("type") == "capped"
    max_iters = 10_000 if is_capped else int(stop_condition.get("n", 1))

    for i in range(1, max_iters + 1):
        if should_stop():
            on_progress("end", reason="aborted", completed=completed)
            return {"ok": True, "reason": "aborted",
                    "completed": completed, "failures": failures}
        t0 = time.time()
        if on_finish_dialog:
            rc, status = _replay_one()
            if status == "replay_failed":
                _close_finish_dialog()
                rc, status = _run_one(stage, dungeon=dungeon)
        else:
            rc, status = _run_one(stage, dungeon=dungeon)
        elapsed = int(time.time() - t0)
        line = (f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {dungeon_label} "
                f"{status.upper()} {elapsed}s")
        if log_path:
            try:
                import os
                os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
                with open(log_path, "a") as f:
                    f.write(line + "\n")
            except Exception as ex:
                print(f"  log write failed: {ex}", file=sys.stderr)
        print(f"  [{i}] {status} ({elapsed}s)")
        on_progress("run_done", index=i, status=status, elapsed_s=elapsed)

        if status == "capped":
            print(f"  loop end: capped after {completed} successful run(s)")
            on_progress("end", reason="capped", completed=completed)
            return {"ok": True, "reason": "capped",
                    "completed": completed, "failures": failures}
        if status == "victory":
            completed += 1
            on_finish_dialog = True
            continue
        failures += 1
        on_finish_dialog = False
        print(f"  loop end: aborting after status={status} "
              f"({completed} success, {failures} fail)", file=sys.stderr)
        on_progress("end", reason=status, completed=completed)
        return {"ok": False, "reason": status,
                "completed": completed, "failures": failures}

    if on_finish_dialog:
        _close_finish_dialog()
    print(f"  loop end: completed {completed} run(s)")
    on_progress("end", reason="done", completed=completed)
    return {"ok": True, "reason": "done",
            "completed": completed, "failures": failures}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dungeon", choices=sorted(DUNGEONS),
                    help="Dungeon to open (skips if already on stage list)")
    ap.add_argument("--stage",
                    help="Stage number (1-25) or 'max' for highest visible")
    ap.add_argument("--start", dest="start", action="store_true",
                    default=True, help="(default) Auto-start battle after stage opens")
    ap.add_argument("--no-start", dest="start", action="store_false",
                    help="Just open hero selection, don't auto-start")
    ap.add_argument("--wait", action="store_true",
                    help="After --start, wait for finish and print VICTORY/DEFEAT")
    ap.add_argument("--runs", type=int, default=1,
                    help="Run the battle N times (implies --start --wait). Default 1.")
    ap.add_argument("--until-capped", action="store_true",
                    help="Minotaur only. Loop until the 'all champions have "
                         "max scrolls' messagebox appears, then stop.")
    ap.add_argument("--log", default="data/runs/dungeon_runs.log",
                    help="Append per-run results to this log (default: "
                         "data/runs/dungeon_runs.log; pass empty to disable)")
    args = ap.parse_args()

    if args.until_capped and args.dungeon and args.dungeon != "minotaur":
        ap.error("--until-capped is minotaur-specific (other dungeons don't "
                 "have a daily scroll cap)")
    looping = args.runs > 1 or args.until_capped
    if looping:
        args.start = True
        args.wait = True

    if args.dungeon and not open_dungeon(args.dungeon):
        return 1

    if args.stage is None:
        ap.error("--stage required (1-25 or 'max')")
    if str(args.stage).lower() == "max":
        stage = _resolve_max_stage()
        if stage is None:
            print("  ERR: no stage tiles visible", file=sys.stderr)
            return 1
        print(f"  max visible stage: {stage}")
    else:
        try:
            stage = int(args.stage)
        except ValueError:
            ap.error(f"--stage must be int or 'max', got {args.stage!r}")
        if not (1 <= stage <= 25):
            ap.error("--stage int must be 1..25")

    # Single run, no --wait → preserve previous behaviour.
    if not looping:
        if not open_stage(stage):
            return 1
        if args.start:
            time.sleep(1.0)
            if not start_battle():
                return 1
            if args.wait:
                rc, status = wait_and_report()
                if status == "victory":
                    _close_finish_dialog()
                return rc
        return 0

    # Loop via the shared run_loop function.
    stop_condition = ({"type": "capped"} if args.until_capped
                      else {"type": "runs", "n": args.runs})
    result = run_loop(dungeon=args.dungeon, stage=stage,
                      stop_condition=stop_condition,
                      log_path=args.log or None)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
