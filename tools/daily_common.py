"""
Shared framework for tools/daily_*.py collection CLIs.

Every daily task follows the same pattern:
    snapshot resources -> navigate -> click reward/claim buttons -> snapshot -> diff

All game interaction goes through the mod HTTP API (BepInEx :6790).
No pyautogui. No screen automation. Memory reader is optional (not used here).

Canonical sequence inside a CLI:

    from daily_common import Session, main_wrapper

    def run(s: Session):
        s.navigate("village")
        s.click_village("shop")
        s.wait_scene_not("Village")
        s.click_any(["Claim", "Free"])   # first match of /buttons containing 'Claim' or 'Free'
        s.dismiss_popups()
        return True

    if __name__ == "__main__":
        main_wrapper("shop", run)
"""

import argparse
import json
import logging
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from Modules.mod_client import ModClient, VILLAGE_BUTTONS  # noqa: E402

logger = logging.getLogger(__name__)


# Human-readable resource labels. Raw keys like "resource_111" are unknown
# shard/token types; we surface them verbatim so deltas are still visible.
RESOURCE_LABELS = {
    "energy": "Energy",
    "silver": "Silver",
    "gems": "Gems",
    "arena_tokens": "Arena tokens",
    "arena_3x3_tokens": "Live Arena 3x3 tokens",
    "live_arena_tokens": "Live Arena tokens",
    "cb_keys": "CB keys",
    "resource_5": "Souls",
    "resource_101": "Mystery shards",
    "resource_102": "Ancient shards",
    "resource_103": "Void shards",
    "resource_111": "Energy refill",
    "resource_112": "XP boost",
    "resource_113": "Sacred shards",
    "resource_121": "Primal shards",
}


def _fmt(k, v):
    if v is None:
        return "-"
    if k == "silver" and abs(v) >= 1000:
        return f"{v/1000:,.1f}K" if abs(v) < 1e6 else f"{v/1e6:,.2f}M"
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return f"{v:,}" if isinstance(v, (int, float)) else str(v)


class Session:
    """Thin convenience wrapper around ModClient for daily-collection flows."""

    def __init__(self, client=None, verbose=True):
        self.mod = client or ModClient()
        self.verbose = verbose
        if not self.mod.available:
            raise RuntimeError("Mod API unreachable at http://localhost:6790 - launch Raid with BepInEx plugin")

    # ------- logging -------
    def log(self, msg):
        if self.verbose:
            print(f"  {msg}")
        logger.info(msg)

    # ------- resource snapshots -------
    def resources(self):
        try:
            return self.mod._get("/resources") or {}
        except Exception as e:
            logger.warning("resources fetch failed: %s", e)
            return {}

    @staticmethod
    def diff(before, after):
        keys = sorted(set(before) | set(after))
        out = {}
        for k in keys:
            b = before.get(k, 0) or 0
            a = after.get(k, 0) or 0
            d = a - b
            if d != 0:
                out[k] = (b, a, d)
        return out

    @staticmethod
    def print_diff(delta):
        if not delta:
            print("  (no resource changes detected)")
            return
        for k, (b, a, d) in delta.items():
            label = RESOURCE_LABELS.get(k, k)
            sign = "+" if d > 0 else ""
            print(f"  {label:<22} {_fmt(k, b):>12} -> {_fmt(k, a):<12}  {sign}{_fmt(k, d)}")

    # ------- view / status -------
    def scene(self):
        try:
            return (self.mod.get_status() or {}).get("scene")
        except Exception:
            return None

    def wait_scene(self, name, timeout=10, poll=0.4):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.scene() == name:
                return True
            time.sleep(poll)
        return False

    def wait_scene_not(self, name, timeout=10, poll=0.4):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.scene() != name:
                return True
            time.sleep(poll)
        return False

    # ------- navigation -------
    def navigate(self, target, wait=2.0):
        """Use /navigate?target=X then sleep."""
        self.log(f"navigate -> {target}")
        try:
            self.mod._get(f"/navigate?target={urllib.parse.quote(target)}")
        except Exception as e:
            self.log(f"navigate err: {e}")
            return False
        time.sleep(wait)
        return True

    def click_village(self, button_key, wait=1.5):
        """Click a known Village HUD button (see mod_client.VILLAGE_BUTTONS)."""
        path = VILLAGE_BUTTONS.get(button_key)
        if not path:
            self.log(f"unknown village button: {button_key}")
            return False
        self.log(f"click village.{button_key}")
        try:
            self.mod.click_path(path)
        except Exception as e:
            self.log(f"click err: {e}")
            return False
        time.sleep(wait)
        return True

    # ------- discovery -------
    def buttons(self):
        """List all currently interactable buttons."""
        try:
            d = self.mod.get_buttons() or {}
            return [b.get("path", "") for b in (d.get("buttons") or [])]
        except Exception as e:
            logger.warning("buttons fetch failed: %s", e)
            return []

    # Buttons to always skip when matching — they exist globally but are never
    # the target of a daily-collection task. Village HUD is always visible and
    # CollectionButton's name collides with "Collect" etc.
    _DEFAULT_EXCLUDE = ("VillageHUD",)

    def find_paths(self, *substrings, case_insensitive=True, whole_path=False,
                   exclude=None):
        """Return all button paths whose final segment contains any of the
        substrings. Pass whole_path=True to match anywhere in the path.
        `exclude` is a list of substrings; any path containing one is skipped.
        Defaults always exclude VillageHUD paths."""
        needles = [s.lower() if case_insensitive else s for s in substrings]
        skips = list(self._DEFAULT_EXCLUDE) + list(exclude or [])
        skips = [s.lower() if case_insensitive else s for s in skips]
        out = []
        for p in self.buttons():
            pl = p.lower() if case_insensitive else p
            if any(s in pl for s in skips):
                continue
            hay = p if whole_path else p.rsplit("/", 1)[-1]
            if case_insensitive:
                hay = hay.lower()
            if any(n in hay for n in needles):
                out.append(p)
        return out

    def click_any(self, substrings, wait=1.2, max_clicks=1, exclude=None):
        """Find buttons matching any substring, click up to max_clicks of them.
        Returns number of successful clicks.
        """
        paths = self.find_paths(*substrings, exclude=exclude)
        if not paths:
            self.log(f"no buttons matching {substrings}")
            return 0
        clicks = 0
        for p in paths[:max_clicks]:
            self.log(f"click {p.rsplit('/', 1)[-1]}")
            try:
                self.mod.click_path(p)
                clicks += 1
                time.sleep(wait)
            except Exception as e:
                self.log(f"click err: {e}")
        return clicks

    def click_until_gone(self, substrings, wait=1.0, max_iter=20, exclude=None):
        """Click a matching button, re-discover, click again, until no match or max_iter."""
        total = 0
        for _ in range(max_iter):
            paths = self.find_paths(*substrings, exclude=exclude)
            if not paths:
                break
            p = paths[0]
            self.log(f"click {p.rsplit('/', 1)[-1]}")
            try:
                self.mod.click_path(p)
                total += 1
                time.sleep(wait)
            except Exception as e:
                self.log(f"click err: {e}")
                break
        return total

    def debug_buttons(self, filter_substr=None):
        """Print all currently-interactable button paths (for discovery)."""
        paths = self.buttons()
        if filter_substr:
            paths = [p for p in paths if filter_substr.lower() in p.lower()]
        print(f"[debug] {len(paths)} button(s){' matching ' + filter_substr if filter_substr else ''}:")
        for p in paths:
            print(f"  {p}")

    # ------- popups -------
    def dismiss(self):
        """Close any currently-open dismissable dialogs via the mod."""
        try:
            r = self.mod._get("/dismiss") or {}
            n = r.get("dismissed", 0)
            if n:
                self.log(f"dismissed {n} dialog(s)")
            return n
        except Exception as e:
            self.log(f"dismiss err: {e}")
            return 0


def main_wrapper(task_name, run_fn, extra_args=None):
    """Standard CLI wrapper: parse args, snapshot, run, snapshot, diff.

    `run_fn(session)` must return truthy on success. Returns the process exit
    code so it can be used as `sys.exit(main_wrapper(...))`.
    """
    parser = argparse.ArgumentParser(description=f"Daily {task_name} collection")
    parser.add_argument("--quiet", action="store_true", help="suppress per-step logs")
    parser.add_argument("--debug-buttons", action="store_true",
                        help="after running, dump all currently-interactable button paths")
    parser.add_argument("--debug-filter", default=None,
                        help="with --debug-buttons, only print paths containing this substring")
    if extra_args:
        extra_args(parser)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    print(f"=== daily_{task_name} ===")
    try:
        s = Session(verbose=not args.quiet)
    except Exception as e:
        print(f"ERROR: {e}")
        return 2

    before = s.resources()
    start = time.time()
    try:
        ok = run_fn(s, args)
    except Exception as e:
        print(f"ERROR during run: {type(e).__name__}: {e}")
        ok = False
    elapsed = time.time() - start

    # Give the game a moment to commit resource updates
    time.sleep(1.0)
    after = s.resources()

    print(f"--- resource delta ({elapsed:.1f}s) ---")
    Session.print_diff(Session.diff(before, after))
    if args.debug_buttons:
        print("--- /buttons snapshot ---")
        s.debug_buttons(filter_substr=args.debug_filter)
    print(f"status: {'OK' if ok else 'FAIL'}")
    return 0 if ok else 1
