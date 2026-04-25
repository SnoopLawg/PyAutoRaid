#!/usr/bin/env python3
"""Open a specific dungeon stage and (optionally) start the battle.

Discovery path (verified 2026-04-25 against Raid v11.40):
  1. Caller must already be on the dungeon's stage list (DungeonsDialog
     open). The /open-dungeon endpoint can sometimes leave the UI in a
     half-rendered state; manual navigation is more reliable for now.
  2. /context-call → DungeonStageContext.OpenSelectionDialog/0 on the
     target stage's GameObject path. That opens the hero selection
     dialog (DungeonHeroesSelectionDialog).
  3. /context-call → HeroesSelectionPveDialogContext.StartBattle/0 to
     actually launch the battle (uses current team selection).

Usage:
    python3 tools/dungeon_run.py --stage 20 --start
    python3 tools/dungeon_run.py --stage 1 --no-start  # just open hero pick

Limitations:
- Stage must be unlocked. Locked stages register the click but the
  game silently ignores it (dialog stays the same).
- The team that fires is whatever's currently selected in-game on the
  dungeon hero-selection dialog. We don't pick the team here.
- /open-dungeon does NOT reliably enter a dungeon's stage list — the
  user must navigate manually to the target dungeon first. That's a
  bug to chase later in mod/RaidAutomationPlugin.cs.
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


def open_stage(stage: int) -> bool:
    """Click the stage tile (0-indexed in the GameObject hierarchy =
    stage-1 in user-facing terms)."""
    if not _ensure_dungeons_dialog():
        print(f"  ERROR: DungeonsDialog not open. Manually navigate to the "
              f"target dungeon first.", file=sys.stderr)
        return False

    idx = stage - 1
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


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", type=int, required=True,
                    help="Stage number 1-25")
    ap.add_argument("--start", dest="start", action="store_true",
                    default=True, help="(default) Auto-start battle after stage opens")
    ap.add_argument("--no-start", dest="start", action="store_false",
                    help="Just open hero selection, don't auto-start")
    args = ap.parse_args()

    if not (1 <= args.stage <= 25):
        ap.error("--stage must be 1..25")

    if not open_stage(args.stage):
        return 1
    if args.start:
        time.sleep(1.0)
        if not start_battle():
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
