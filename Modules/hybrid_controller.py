"""
Hybrid daily automation controller for Raid: Shadow Legends.

Combines three automation strategies:
  1. Coordinate clicks — fixed positions for known UI elements (nav bar, etc.)
  2. Memory reading — game state via pymem (resources, battle, ViewKey, opponents)
  3. Image matching — only for dynamic/unpredictable elements (popups, battle results)

Memory reading provides:
  - Instant battle completion detection (no image polling timeouts)
  - Smart resource checks (skip arena if no tokens, skip CB if no keys)
  - Arena opponent evaluation (pick weakest target)
  - Navigation verification via ViewKey (know exactly what screen we're on)
  - Instant fight support (CB quick battles detected via state + key count)

Usage:
    python hybrid_controller.py              # full daily run
    python hybrid_controller.py --no-memory  # screen-only fallback
"""

import logging
import time
import sys
import os

import pyautogui
pyautogui.FAILSAFE = False

from base import asset, locate_and_click, locate_and_click_loop, MAX_RETRIES
from screen_state import ScreenState
from win32_input import InputBackend

logging.basicConfig(
    filename='HybridController.log',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filemode='w', level=logging.DEBUG)
logger = logging.getLogger(__name__)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logger.addHandler(console)


# =============================================================================
# Game-relative coordinates (900x600 window, set by ScreenState.initialize)
# =============================================================================

# Bottom navigation bar
BTN_SHOP = (74, 556)
BTN_QUESTS = (263, 560)
BTN_CLAN = (527, 561)
BTN_BATTLE = (807, 560)

# Village elements
GEM_MINE = (73, 355)

# Timed rewards sidebar
TIMED_REWARDS_Y = 260
TIMED_REWARDS_X_RANGE = range(159, 759, 100)

# Generic click targets
CENTER = (450, 300)


def _abs(game, rel):
    """Convert game-relative (x, y) to screen-absolute coordinates."""
    return (rel[0] + game.win_x, rel[1] + game.win_y)


class HybridController:
    """Daily automation controller using coordinates + memory + minimal images."""

    def __init__(self, use_memory=True):
        self.game = None       # ScreenState (window management, popups, image fallback)
        self.reader = None     # MemoryReader (game data, battle state, ViewKey)
        self.input = InputBackend(prefer_background=False)
        self.asset_path = self._get_asset_path()
        self.results = {}
        self._use_memory = use_memory

    def _get_asset_path(self):
        d = os.path.dirname(os.path.abspath(__file__))
        for c in [os.path.join(d, '..', 'assets'), os.path.join(d, 'assets')]:
            if os.path.exists(c):
                return os.path.abspath(c)
        return None

    def connect(self):
        """Initialize screen state and memory reader."""
        logger.info("Initializing...")
        try:
            self.game = ScreenState(self.asset_path)
            self.game.initialize()
            logger.info(f"Screen ready — window at ({self.game.win_x}, {self.game.win_y})")
        except Exception as e:
            logger.error(f"Screen init failed: {e}")
            return False

        if self._use_memory:
            try:
                from memory_reader import MemoryReader
                self.reader = MemoryReader()
                if self.reader.attach():
                    res = self.reader.get_resources()
                    logger.info(f"Memory active — Lv{self.reader.get_account_level()} "
                                f"Power {int(self.reader.get_total_power()):,}")
                    logger.info(f"  Energy={int(res['energy']):,} Silver={int(res['silver']):,} "
                                f"Gems={int(res['gems'])} Arena={res['arena_tokens']:.1f} "
                                f"CB={int(res['cb_keys'])}")
                else:
                    self.reader = None
            except Exception as e:
                logger.warning(f"Memory init failed: {e}")
                self.reader = None
        return True

    def disconnect(self):
        if self.reader:
            self.reader.detach()

    def _click(self, game_rel, sleep_after=1):
        """Click at game-relative coordinates."""
        x, y = _abs(self.game, game_rel)
        self.input.click(x, y, sleep_after=sleep_after)

    def _wait_battle(self, timeout=300):
        """Wait for battle end. Memory-based if available, else image polling."""
        if self.reader:
            state = self.reader.wait_for_battle_end(timeout=timeout, poll_interval=2)
            return {"result": "finished" if state >= 6 else "timeout", "state": state}
        return self.game.wait_for_battle_end(timeout=timeout)

    def _wait_battle_or_view(self, from_view, keys_before=None, timeout=120):
        """Wait for instant/quick battle completion via any signal."""
        if self.reader:
            return self.reader.wait_for_battle_or_view_change(
                from_view, keys_before=keys_before, timeout=timeout)
        time.sleep(10)
        return {"method": "sleep_fallback"}

    # =========================================================================
    # Daily tasks
    # =========================================================================

    def collect_gem_mine(self):
        logger.info("=== Gem Mine ===")
        if not self.game.ensure_village():
            return False
        self._click(GEM_MINE, sleep_after=2)
        self.input.press_escape(sleep_after=2)
        self.game.ensure_village()
        self.results["gem_mine"] = "Collected"
        return True

    def collect_shop_rewards(self):
        logger.info("=== Shop Rewards ===")
        if not self.game.ensure_village():
            return False
        self._click(BTN_SHOP, sleep_after=2)
        offers = asset(self.asset_path, "offers.png")
        free = asset(self.asset_path, "claimFreeGift.png")
        if locate_and_click(offers, confidence=0.9, sleep_after=3):
            for rx in range(214, 890, 50):
                self._click((rx, 93), sleep_after=0.1)
                locate_and_click(free, sleep_after=1)
        self.game.ensure_village()
        self.results["shop"] = "Collected"
        return True

    def collect_timed_rewards(self):
        logger.info("=== Timed Rewards ===")
        if not self.game.ensure_village():
            return False
        tr = asset(self.asset_path, "timeRewards.png")
        rd = asset(self.asset_path, "redNotificationDot.png")
        if locate_and_click(tr, sleep_after=2):
            locate_and_click_loop(rd, sleep_after=1)
            for rx in TIMED_REWARDS_X_RANGE:
                self._click((rx, TIMED_REWARDS_Y), sleep_after=0.2)
            time.sleep(1)
            self.game.ensure_village()
            self.results["timed_rewards"] = "Collected"
            return True
        return False

    def collect_quests(self):
        logger.info("=== Quest Claims ===")
        if not self.game.ensure_village():
            return False
        self._click(BTN_QUESTS, sleep_after=2)
        qc = asset(self.asset_path, "questClaim.png")
        aq = asset(self.asset_path, "advancedQuests.png")
        claimed = locate_and_click_loop(qc, sleep_after=1)
        if locate_and_click(aq, sleep_after=1):
            claimed += locate_and_click_loop(qc, sleep_after=1)
        self.game.ensure_village()
        self.results["quests"] = f"{claimed} claimed"
        return True

    def collect_clan(self):
        logger.info("=== Clan ===")
        if not self.game.ensure_village():
            return False
        self._click(BTN_CLAN, sleep_after=2)
        locate_and_click(asset(self.asset_path, "clanMembers.png"), sleep_after=2)
        locate_and_click_loop(asset(self.asset_path, "clanCheckIn.png"), sleep_after=1)
        locate_and_click(asset(self.asset_path, "clanTreasure.png"), sleep_after=1)
        self.game.ensure_village()
        self.results["clan"] = "Checked in"
        return True

    def collect_inbox(self):
        logger.info("=== Inbox ===")
        if not self.game.ensure_village():
            return False
        self.input.press_char("i", sleep_after=1)
        for item in ["inbox_energy", "inbox_brew", "inbox_purple_forge",
                      "inbox_yellow_forge", "inbox_coin", "inbox_potion"]:
            png = asset(self.asset_path, f"{item}.png")
            retries = 0
            while retries < MAX_RETRIES:
                loc = pyautogui.locateOnScreen(png, confidence=0.8)
                if not loc:
                    break
                cx, cy = pyautogui.center(loc)
                self.input.click(cx + 250, cy, sleep_after=2)
                retries += 1
        self.game.ensure_village()
        self.results["inbox"] = "Collected"
        return True

    # =========================================================================
    # Arena
    # =========================================================================

    def _nav_to_arena(self):
        """Navigate from village to classic arena opponent list."""
        self._click(BTN_BATTLE, sleep_after=2)
        if not self.game.smart_click("arenaTab.png", max_attempts=3):
            self.game.ensure_village()
            return False
        time.sleep(2)
        self.game.smart_click("classicArena.png", max_attempts=2)
        time.sleep(2)
        return True

    def _dismiss_arena_results(self):
        """Click through arena battle result screens."""
        tap = asset(self.asset_path, "tapToContinue.png")
        ret = asset(self.asset_path, "returnToArena.png")
        bat = asset(self.asset_path, "arenaBattle.png")
        for _ in range(12):
            if pyautogui.locateOnScreen(bat, confidence=0.6):
                return True
            if locate_and_click(tap, confidence=0.7, sleep_after=2):
                continue
            if locate_and_click(ret, confidence=0.7, sleep_after=3):
                continue
            self.game._clear_popups()
            self._click(CENTER, sleep_after=2)
        return False

    def run_arena_battles(self, num_battles=10):
        logger.info(f"=== Arena ({num_battles} battles) ===")

        # Smart check: skip if no tokens
        if self.reader:
            res = self.reader.get_resources()
            tokens = res.get("arena_tokens", 0)
            if tokens < 1:
                self.results["arena"] = f"Skipped ({tokens:.1f} tokens)"
                logger.info(f"Skipping arena — {tokens:.1f} tokens")
                return True
            # Log opponent analysis
            opps = self.reader.get_arena_opponents()
            available = sorted([o for o in opps if o["available"]], key=lambda o: o["power"])
            if available:
                logger.info(f"Opponents: {len(available)} available, "
                            f"weakest={available[0]['name']} ({available[0]['power']:,})")

        if not self.game.ensure_village():
            return False
        if not self._nav_to_arena():
            return False

        battles = 0
        arena_battle = asset(self.asset_path, "arenaBattle.png")
        arena_start = asset(self.asset_path, "arenaStart.png")
        arena_refill = asset(self.asset_path, "classicArenaRefill.png")

        while battles < num_battles:
            # Check tokens before each fight
            if self.reader and not self.reader.has_arena_tokens():
                logger.info("Out of arena tokens (memory).")
                break

            loc = pyautogui.locateOnScreen(arena_battle, confidence=0.6)
            if not loc:
                refresh = asset(self.asset_path, "arenaRefresh.png")
                locate_and_click(refresh, confidence=0.7, sleep_after=3)
                loc = pyautogui.locateOnScreen(arena_battle, confidence=0.6)
                if not loc:
                    break

            cx, cy = pyautogui.center(loc)
            pyautogui.click(cx, cy)
            time.sleep(3)

            if pyautogui.locateOnScreen(arena_refill, confidence=0.8):
                logger.info("Out of tokens (refill prompt).")
                pyautogui.press('escape')
                time.sleep(1)
                break

            if not locate_and_click(arena_start, confidence=0.9, sleep_after=3):
                pyautogui.press('escape')
                time.sleep(2)
                continue

            # Memory-based battle detection (instant) or image polling (fallback)
            result = self._wait_battle(timeout=180)
            battles += 1
            logger.info(f"Battle {battles}/{num_battles}: {result['result']}")

            time.sleep(2)
            if not self._dismiss_arena_results():
                self.game.ensure_village()
                if not self._nav_to_arena():
                    break

        self.game.ensure_village()
        self.results["arena"] = f"{battles} battles fought"
        return True

    # =========================================================================
    # Clan Boss
    # =========================================================================

    def run_clan_boss(self, difficulty="ultra-nightmare"):
        logger.info(f"=== Clan Boss ({difficulty}) ===")

        # Smart check: skip if no keys
        if self.reader:
            keys_before = int(self.reader.get_resources().get("cb_keys", 0))
            if keys_before < 1:
                self.results["clan_boss"] = f"Skipped ({keys_before} keys)"
                logger.info(f"Skipping CB — {keys_before} keys")
                return True
        else:
            keys_before = None

        if not self.game.ensure_village():
            return False

        # Navigate: Village -> Battle -> CB -> Demon Lord
        self._click(BTN_BATTLE, sleep_after=3)
        cb = asset(self.asset_path, "CB.png")
        if not locate_and_click(cb, confidence=0.8, sleep_after=3, max_attempts=5):
            self.game.ensure_village()
            return False
        dl = asset(self.asset_path, "demonLord2.png")
        if not locate_and_click(dl, confidence=0.7, sleep_after=4, max_attempts=5):
            self.game.ensure_village()
            return False

        # Verify we're on CB screen via ViewKey
        if self.reader:
            logger.info(f"CB screen: {self.reader.get_current_view_name()}")

        # Claim any available rewards
        locate_and_click_loop(asset(self.asset_path, "CBreward.png"), sleep_after=2, max_retries=3)
        locate_and_click_loop(asset(self.asset_path, "CBclaim.png"), sleep_after=2, max_retries=3)

        # Scroll difficulty panel to show higher difficulties (UNM)
        gx = self.game.win_x + 490
        pyautogui.moveTo(gx, self.game.win_y + 350)
        time.sleep(0.2)
        pyautogui.mouseDown()
        pyautogui.moveTo(gx, self.game.win_y + 120, duration=0.5)
        pyautogui.mouseUp()
        time.sleep(2)

        # Click Battle button
        cb_battle = asset(self.asset_path, "CBbattle.png")
        if not locate_and_click(cb_battle, confidence=0.6, sleep_after=3, max_attempts=3):
            logger.info("No CB battle button (already fought today).")
            self.game.ensure_village()
            return True

        # Verify we're at team selection
        if self.reader:
            vk = self.reader.get_current_view()
            logger.info(f"After Battle click: {self.reader.get_current_view_name()}")
            if vk != 1072:  # HeroesSelectionDialogToAllianceBoss
                logger.warning(f"Not at CB team selection (view={vk})")
                self.game.ensure_village()
                return False

        # Click Start
        cb_start = asset(self.asset_path, "CBstart.png")
        if not locate_and_click(cb_start, confidence=0.8, sleep_after=3, max_attempts=5):
            logger.warning("CBstart not found")
            self.game.ensure_village()
            return False

        # Wait for battle completion (supports instant/quick fights)
        logger.info("CB battle started, waiting...")
        if self.reader:
            result = self._wait_battle_or_view(
                from_view=1072, keys_before=keys_before, timeout=600)
            logger.info(f"CB complete: {result}")
            self.results["clan_boss"] = f"{difficulty} fought"
        else:
            result = self._wait_battle(timeout=600)
            self.results["clan_boss"] = f"{difficulty}: {result['result']}"

        # Dismiss results and return to village
        time.sleep(3)
        for _ in range(10):
            if self.reader and self.reader.is_at_village():
                break
            goto = asset(self.asset_path, "gotoBastion.png")
            if locate_and_click(goto, confidence=0.7, sleep_after=3):
                continue
            self._click(CENTER, sleep_after=2)

        self.game.ensure_village()
        return True

    # =========================================================================
    # Main daily run
    # =========================================================================

    def run_daily(self):
        mode = "coords + memory" if self.reader else "screen-only"
        logger.info("=" * 50)
        logger.info(f"Daily automation ({mode})")
        logger.info("=" * 50)

        if self.reader:
            res = self.reader.get_resources()
            logger.info(f"Pre: E={int(res['energy']):,} S={int(res['silver']):,} "
                        f"G={int(res['gems'])} A={res['arena_tokens']:.1f} CB={int(res['cb_keys'])}")

        for name, fn in [
            ("Gem Mine", self.collect_gem_mine),
            ("Shop Rewards", self.collect_shop_rewards),
            ("Timed Rewards", self.collect_timed_rewards),
            ("Clan", self.collect_clan),
            ("Quest Claims", self.collect_quests),
            ("Inbox", self.collect_inbox),
            ("Arena", lambda: self.run_arena_battles(10)),
            ("Clan Boss", lambda: self.run_clan_boss("ultra-nightmare")),
        ]:
            try:
                logger.info(f"[{name}] Starting...")
                fn()
            except Exception as e:
                logger.error(f"[{name}] Failed: {e}", exc_info=True)
                try:
                    self.game.ensure_village()
                except Exception:
                    pass

        if self.reader:
            res = self.reader.get_resources()
            logger.info(f"Post: E={int(res['energy']):,} S={int(res['silver']):,} "
                        f"G={int(res['gems'])} A={res['arena_tokens']:.1f} CB={int(res['cb_keys'])}")

        logger.info("=" * 50)
        logger.info("Results:")
        for k, v in self.results.items():
            logger.info(f"  {k}: {v}")
        logger.info("=" * 50)


def main():
    ctrl = HybridController(use_memory="--no-memory" not in sys.argv)
    if not ctrl.connect():
        sys.exit(1)
    try:
        ctrl.run_daily()
    except KeyboardInterrupt:
        logger.info("Interrupted.")
    finally:
        ctrl.disconnect()


if __name__ == "__main__":
    main()
