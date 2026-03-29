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
    """Daily automation: mod API > memory > coordinates > image matching."""

    def __init__(self, use_memory=True):
        self.game = None       # ScreenState (window management, popups, image fallback)
        self.reader = None     # MemoryReader (game data, battle state, ViewKey)
        self.mod = None        # ModClient (direct UI button clicks via game API)
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

        # Initialize mod API client (MelonLoader HTTP API)
        try:
            from mod_client import ModClient
            self.mod = ModClient()
            if self.mod.available:
                logger.info("Mod API active — direct UI control enabled")
            else:
                self.mod = None
        except Exception:
            self.mod = None

        return True

    def disconnect(self):
        if self.reader:
            self.reader.detach()

    def _click(self, game_rel, sleep_after=1):
        """Click at game-relative coordinates."""
        x, y = _abs(self.game, game_rel)
        self.input.click(x, y, sleep_after=sleep_after)

    def _click_nav(self, name, game_rel_fallback, sleep_after=2):
        """Click a navigation button. Uses mod API if available, else coordinates."""
        if self.mod:
            if self.mod.click_button(name):
                time.sleep(sleep_after)
                return True
        self._click(game_rel_fallback, sleep_after=sleep_after)
        return True

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
        self._click_nav("shop", BTN_SHOP)
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
        self._click_nav("quests", BTN_QUESTS)
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
        self._click_nav("clan", BTN_CLAN)
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
        # Open inbox: mod API > keyboard shortcut
        if not (self.mod and self.mod.click_button("inbox")):
            self.input.press_char("i", sleep_after=1)
        time.sleep(1)
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

    # Arena opponent row layout (game-relative Y positions for 5 visible slots)
    ARENA_ROW_Y = [195, 275, 355, 435, 515]
    ARENA_BATTLE_X = 820  # Battle button on right side of each row

    def _nav_to_arena(self):
        """Navigate from village to classic arena opponent list."""
        self._click_nav("battle", BTN_BATTLE)
        # Arena tab: try mod API first, then image matching
        if self.mod:
            path = self.mod.find_button("ArenaHub") or self.mod.find_button("Arena")
            if path and self.mod.click_path(path):
                time.sleep(2)
                path2 = self.mod.find_button("ClassicArena") or self.mod.find_button("classic")
                if path2:
                    self.mod.click_path(path2)
                    time.sleep(2)
                    return True
        # Fallback to image matching
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

    def _pick_and_click_opponent(self):
        """Use memory to pick the weakest available opponent and click
        their Battle button by calculated position. Falls back to image
        matching if memory unavailable.
        Returns True if we navigated to team selection.
        """
        arena_battle = asset(self.asset_path, "arenaBattle.png")

        if not self.reader:
            # Fallback: click first visible battle button
            loc = pyautogui.locateOnScreen(arena_battle, confidence=0.6)
            if loc:
                pyautogui.click(*pyautogui.center(loc))
                time.sleep(3)
                return True
            return False

        opps = self.reader.get_arena_opponents()
        # Only consider the first 5 (visible without scrolling)
        available = [(i, o) for i, o in enumerate(opps[:5]) if o["available"]]
        if not available:
            # Try all 10 with image fallback
            logger.info("No available opponents in top 5, using image fallback.")
            loc = pyautogui.locateOnScreen(arena_battle, confidence=0.6)
            if loc:
                pyautogui.click(*pyautogui.center(loc))
                time.sleep(3)
                return True
            return False

        # Sort by power (weakest first = easiest win)
        available.sort(key=lambda x: x[1]["power"])
        target_idx, target = available[0]
        logger.info(f"Target: [{target_idx}] {target['name']} "
                     f"(power={target['power']:,})")

        # Click the Battle button for this visible slot
        btn_y = self.ARENA_ROW_Y[target_idx]
        self._click((self.ARENA_BATTLE_X, btn_y), sleep_after=3)

        # Verify we reached team selection via ViewKey
        if self.reader:
            vk = self.reader.get_current_view()
            if vk == 1011:  # HeroesSelectionDialogToArena
                return True
            # Click didn't work — fall back to image matching
            logger.info(f"Click didn't navigate (view={vk}), trying image fallback")
            loc = pyautogui.locateOnScreen(arena_battle, confidence=0.6)
            if loc:
                pyautogui.click(*pyautogui.center(loc))
                time.sleep(3)
                return True
            return False

        return True

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
            # Log full opponent analysis
            opps = self.reader.get_arena_opponents()
            available = sorted([o for o in opps if o["available"]], key=lambda o: o["power"])
            for o in available:
                logger.info(f"  {o['name']:20s} power={o['power']:>10,}")

        if not self.game.ensure_village():
            return False
        if not self._nav_to_arena():
            return False

        battles = 0
        arena_start = asset(self.asset_path, "arenaStart.png")
        arena_refill = asset(self.asset_path, "classicArenaRefill.png")

        while battles < num_battles:
            # Check tokens before each fight
            if self.reader and not self.reader.has_arena_tokens():
                logger.info("Out of arena tokens (memory).")
                break

            # Pick and click the weakest opponent
            if not self._pick_and_click_opponent():
                # Try refreshing the list
                refresh = asset(self.asset_path, "arenaRefresh.png")
                if locate_and_click(refresh, confidence=0.7, sleep_after=3):
                    if not self._pick_and_click_opponent():
                        break
                else:
                    break

            # Check for refill prompt (out of tokens)
            if pyautogui.locateOnScreen(arena_refill, confidence=0.8):
                logger.info("Out of tokens (refill prompt).")
                pyautogui.press('escape')
                time.sleep(1)
                break

            # Click Start on team selection
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
        self._click_nav("battle", BTN_BATTLE, sleep_after=3)
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

        # Scroll difficulty panel down to Ultra-Nightmare
        # The panel is on the right side (~x=490). Drag multiple times to ensure
        # we reach the bottom (UNM is the last difficulty).
        gx = self.game.win_x + 490
        for drag in range(3):
            pyautogui.moveTo(gx, self.game.win_y + 380)
            time.sleep(0.15)
            pyautogui.mouseDown()
            pyautogui.moveTo(gx, self.game.win_y + 100, duration=0.4)
            pyautogui.mouseUp()
            time.sleep(0.5)
        time.sleep(1)

        # Click Battle button (should now be for UNM after scrolling)
        cb_battle = asset(self.asset_path, "CBbattle.png")
        if not locate_and_click(cb_battle, confidence=0.6, sleep_after=3, max_attempts=3):
            logger.info("No CB battle button (already fought today).")
            self.game.ensure_village()
            return True

        # Verify we're at team selection via ViewKey
        if self.reader:
            vk = self.reader.get_current_view()
            logger.info(f"After Battle click: {self.reader.get_current_view_name()}")
            if vk != 1072:  # HeroesSelectionDialogToAllianceBoss
                # Might have clicked a dead boss's row — try clicking Battle again
                logger.warning(f"Not at team selection (view={vk}), retrying...")
                if not locate_and_click(cb_battle, confidence=0.6, sleep_after=3, max_attempts=3):
                    self.game.ensure_village()
                    return False
                vk = self.reader.get_current_view()
                if vk != 1072:
                    self.game.ensure_village()
                    return False

        # Click Start
        cb_start = asset(self.asset_path, "CBstart.png")
        if not locate_and_click(cb_start, confidence=0.8, sleep_after=3, max_attempts=5):
            logger.warning("CBstart not found")
            self.game.ensure_village()
            return False

        # Wait for battle — supports normal and instant/quick fights
        logger.info("CB battle started, waiting...")
        if self.reader:
            result = self._wait_battle_or_view(
                from_view=1072, keys_before=keys_before, timeout=600)
            logger.info(f"CB complete: {result}")
            self.results["clan_boss"] = f"{difficulty} fought"
        else:
            result = self._wait_battle(timeout=600)
            self.results["clan_boss"] = f"{difficulty}: {result['result']}"

        # Dismiss results
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
    # Dungeon Farming (Event-Aware)
    # =========================================================================

    # Dungeon button names in the Dungeons map (for mod API / image matching)
    DUNGEON_REGIONS = {
        "dragon": {"region": 206, "image": "dungeonDragon.png"},
        "ice_golem": {"region": 207, "image": "dungeonIceGolem.png"},
        "fire_knight": {"region": 208, "image": "dungeonFireKnight.png"},
        "spider": {"region": 209, "image": "dungeonSpider.png"},
        "minotaur": {"region": 210, "image": "dungeonMinotaur.png"},
    }

    def _detect_best_dungeon(self):
        """Check active events and pick the optimal dungeon to farm.
        Returns dungeon name (e.g. 'dragon', 'ice_golem') or None.
        """
        if not self.reader:
            return None
        running = self.reader.get_running_events()
        all_events = running["solo_events"] + running["tournaments"]

        # Check event names for dungeon hints
        for event in all_events:
            name = event.get("name", "").lower()
            if "dragon" in name:
                return "dragon"
            if "spider" in name:
                return "spider"
            if "fire knight" in name or "fire_knight" in name:
                return "fire_knight"
            if "ice golem" in name or "ice_golem" in name:
                return "ice_golem"
            if "minotaur" in name:
                return "minotaur"

        # Generic dungeon event — default to dragon (best gear drops)
        if self.reader.should_farm_dungeons():
            return "dragon"

        return None

    def _nav_to_dungeons(self):
        """Navigate from village to the dungeons map."""
        self._click_nav("battle", BTN_BATTLE, sleep_after=3)

        # Look for dungeons tab/button
        if self.mod:
            path = self.mod.find_button("Dungeons") or self.mod.find_button("dungeon")
            if path and self.mod.click_path(path):
                time.sleep(3)
                return True

        # Fallback: image matching
        dungeons_btn = asset(self.asset_path, "dungeonsTab.png")
        if locate_and_click(dungeons_btn, confidence=0.7, sleep_after=3, max_attempts=3):
            return True

        # Check if we're already at dungeons map
        if self.reader:
            vk = self.reader.get_current_view()
            if vk in (1027, 1028):  # DungeonsMap or DungeonsHUD
                return True

        return False

    def _select_dungeon(self, dungeon_name):
        """Click on a specific dungeon on the dungeons map."""
        info = self.DUNGEON_REGIONS.get(dungeon_name)
        if not info:
            return False

        # Try mod API first
        if self.mod:
            # Search for buttons matching dungeon name
            search_terms = {
                "dragon": "Dragon", "ice_golem": "IceGolem",
                "fire_knight": "FireKnight", "spider": "Spider",
                "minotaur": "Minotaur",
            }
            term = search_terms.get(dungeon_name, dungeon_name)
            path = self.mod.find_button(term)
            if path and self.mod.click_path(path):
                time.sleep(3)
                return True

        # Fallback: image matching
        img = asset(self.asset_path, info["image"])
        if img and locate_and_click(img, confidence=0.7, sleep_after=3, max_attempts=3):
            return True

        return False

    def _select_difficulty(self, target_level=20):
        """On the dungeon stage selection screen, scroll to and select
        the target difficulty level (default: highest available, 20 or 25).
        """
        # Scroll down to reach higher stages
        gx = self.game.win_x + 450
        for _ in range(5):
            pyautogui.moveTo(gx, self.game.win_y + 450)
            time.sleep(0.15)
            pyautogui.mouseDown()
            pyautogui.moveTo(gx, self.game.win_y + 100, duration=0.3)
            pyautogui.mouseUp()
            time.sleep(0.3)
        time.sleep(1)

        # Click the highest visible stage (should be at bottom after scrolling)
        # Look for a stage button with the right level
        stage_btn = asset(self.asset_path, "dungeonStage.png")
        if stage_btn and locate_and_click(stage_btn, confidence=0.6, sleep_after=3):
            return True

        # Fallback: click the last visible stage (bottom of scrolled list)
        self._click((450, 500), sleep_after=3)
        return True

    def run_dungeon_farming(self, dungeon_name=None, max_runs=20,
                             energy_floor=1000, target_level=20):
        """Farm a dungeon, spending energy for gear drops + event points.

        Args:
            dungeon_name: Which dungeon ('dragon', 'spider', etc).
                         Auto-detected from events if None.
            max_runs: Maximum runs before stopping.
            energy_floor: Stop when energy drops below this.
            target_level: Dungeon stage to farm (default 20).
        """
        # Auto-detect best dungeon from events
        if not dungeon_name:
            dungeon_name = self._detect_best_dungeon()
            if not dungeon_name:
                logger.info("No dungeon events active — skipping farming")
                self.results["dungeon_farming"] = "Skipped (no active events)"
                return True

        logger.info(f"=== Dungeon Farming: {dungeon_name} (max {max_runs} runs, "
                     f"energy floor {energy_floor}) ===")

        # Log active events
        if self.reader:
            running = self.reader.get_running_events()
            for e in running["solo_events"] + running["tournaments"]:
                if e.get("active"):
                    hours = e.get("hours_left", "?")
                    logger.info(f"  Active: {e['name']} ({hours:.1f}h left)")

        if not self.game.ensure_village():
            return False

        # Check energy
        if self.reader:
            energy = int(self.reader.get_resources().get("energy", 0))
            if energy < energy_floor:
                logger.info(f"Energy {energy:,} below floor {energy_floor} — skipping")
                self.results["dungeon_farming"] = f"Skipped (energy={energy:,})"
                return True
            logger.info(f"Energy: {energy:,} (floor: {energy_floor})")

        # Navigate to dungeons
        if not self._nav_to_dungeons():
            logger.error("Failed to navigate to dungeons")
            self.game.ensure_village()
            return False

        # Select the target dungeon
        if not self._select_dungeon(dungeon_name):
            logger.error(f"Failed to select {dungeon_name}")
            self.game.ensure_village()
            return False

        # Select difficulty
        self._select_difficulty(target_level)

        runs = 0
        start_btn = asset(self.asset_path, "dungeonStart.png")
        replay_btn = asset(self.asset_path, "dungeonReplay.png")

        while runs < max_runs:
            # Check energy before each run
            if self.reader:
                energy = int(self.reader.get_resources().get("energy", 0))
                if energy < energy_floor:
                    logger.info(f"Energy {energy:,} below floor — stopping")
                    break

            # Start the run
            if runs == 0:
                # First run: click Start on team selection
                if self.reader:
                    vk = self.reader.get_current_view()
                    logger.info(f"Pre-start view: {self.reader.get_current_view_name()}")

                if not locate_and_click(start_btn, confidence=0.7, sleep_after=3,
                                        max_attempts=5):
                    # Try clicking a generic "Battle" or "Start" button
                    cb_start = asset(self.asset_path, "CBstart.png")
                    arena_start = asset(self.asset_path, "arenaStart.png")
                    if not (locate_and_click(cb_start, confidence=0.6, sleep_after=3) or
                            locate_and_click(arena_start, confidence=0.6, sleep_after=3)):
                        logger.error("Could not find start button")
                        break
            else:
                # Subsequent runs: click Replay
                if not locate_and_click(replay_btn, confidence=0.7, sleep_after=3,
                                        max_attempts=5):
                    # Also try a generic replay/restart button
                    logger.info("No replay button found, trying to restart manually")
                    break

            # Wait for battle to end
            result = self._wait_battle(timeout=300)
            runs += 1
            logger.info(f"Run {runs}/{max_runs}: {result.get('result', 'unknown')}")

            # Dismiss battle results
            time.sleep(2)
            for _ in range(10):
                if self.reader:
                    vk = self.reader.get_current_view()
                    # If we see replay option or are back at dungeon dialog, we're good
                    if vk in (1029, 1063):  # DungeonDialog or BattleFinishDungeon
                        break
                tap = asset(self.asset_path, "tapToContinue.png")
                if locate_and_click(tap, confidence=0.7, sleep_after=2):
                    continue
                self._click(CENTER, sleep_after=2)

        self.game.ensure_village()

        # Log results
        if self.reader:
            energy_after = int(self.reader.get_resources().get("energy", 0))
            logger.info(f"Energy after: {energy_after:,}")
        self.results["dungeon_farming"] = f"{dungeon_name}: {runs} runs"
        return True

    # =========================================================================
    # Artifact Sell
    # =========================================================================

    # Artifact grid layout in the inventory panel (game-relative positions)
    # The inventory shows artifacts in rows of ~8, grouped by set
    # Each artifact tile is approximately 50x50 pixels
    ART_GRID_START_X = 195   # First artifact X in the storage panel
    ART_GRID_START_Y = 200   # First row Y (below "Set: Life" header)
    ART_TILE_SIZE = 50       # Approximate tile width/height
    ART_TILES_PER_ROW = 8    # Artifacts per row

    def _open_manage_screen(self):
        """Navigate to Champions → artifact slot → Manage screen.
        Returns True if on the artifact management screen.
        """
        if not self.game.ensure_village():
            return False

        # Open Champions screen via keyboard
        self.input.press_char("c", sleep_after=3)

        # Click equipped artifact slot to open inventory panel
        self._click((700, 155), sleep_after=3)

        # Click "Manage" button to open the full artifact management screen
        manage_btn = asset(self.asset_path, "manageBtn.png")
        if manage_btn:
            try:
                if locate_and_click(manage_btn, confidence=0.7, sleep_after=3):
                    logger.info("Clicked Manage button")
                    return True
            except Exception:
                pass

        # Fallback: try coordinate click for Manage
        # Manage button is at approximately (130, 380) game-relative
        self._click((130, 380), sleep_after=3)

        # Verify we're on the manage screen by checking for SellMode toggle
        if self.mod:
            tog = self.mod.find_toggle("SellMode")
            if tog:
                logger.info("Artifact manage screen opened")
                return True

        logger.warning("Could not open manage screen")
        return False

    def _close_manage_screen(self):
        """Close manage screen and return to village."""
        self.input.press_escape(sleep_after=2)
        self.input.press_escape(sleep_after=2)
        self.input.press_escape(sleep_after=2)
        self.game.ensure_village()

    def sell_bad_artifacts(self, score_threshold=40, max_sells=50):
        """Score all artifacts and sell the worst ones through the UI.

        Flow:
        1. Read artifacts from memory, score them, identify junk
        2. Navigate to Champions → artifact slot → Manage screen
        3. Switch to Artifacts tab, click "Sell" button at top to enter sell mode
        4. Click "Select All" (or individual artifacts) to select junk
        5. Click "Apply" (sell) on the sell panel
        6. Confirm in the modal dialog

        Args:
            score_threshold: Sell artifacts scoring below this (0-100)
            max_sells: Maximum artifacts to sell per run
        """
        logger.info(f"=== Auto-Sell Artifacts (threshold={score_threshold}, max={max_sells}) ===")

        if not self.reader:
            logger.warning("Memory reader required for artifact selling")
            self.results["artifact_sell"] = "Skipped (no memory)"
            return False

        # Step 1: Score artifacts from memory
        sellable = self.reader.get_sellable_artifacts(threshold=score_threshold)
        if not sellable:
            logger.info("No artifacts below threshold — nothing to sell")
            self.results["artifact_sell"] = "Nothing to sell"
            return True

        total_silver = sum(a["sell_price"] for a in sellable)
        logger.info(f"Found {len(sellable)} sellable artifacts (worth {total_silver:,} silver)")
        for a in sellable[:5]:
            logger.info(f"  Score={a['score']:3d} | {a['rank']}* {a['rarity_name']:9s} "
                        f"{a['kind_name']:7s} {a['set_name']:12s} Sell={a['sell_price']:,}")

        # Step 2: Open the manage screen
        if not self._open_manage_screen():
            self.results["artifact_sell"] = "Failed (couldn't open manage screen)"
            return False

        # Step 3: Switch to Artifacts tab (use pointer click, not toggle)
        if self.mod:
            art_tab = self.mod.find_toggle("Tab1.Artifacts")
            if art_tab and not art_tab["on"]:
                self.mod.click_path(art_tab["path"])
                time.sleep(2)
                logger.info("Switched to Artifacts tab")

        # Step 4: Activate sell mode by clicking the "Sell" button
        # The Sell button is the SellMode toggle at top-right of the panel
        # Use pyautogui physical click at the button position
        self._click((420, 75), sleep_after=2)
        logger.info("Clicked Sell button position")

        # Verify sell mode activated by checking for the sell panel buttons
        sell_panel_active = False
        for attempt in range(5):
            time.sleep(1)
            if self.mod:
                # Look for SelectAll or Apply buttons from SellArtifactsPanel
                btns = self.mod.get_buttons()
                for btn in btns.get("buttons", []):
                    if "SellArtifactsPanel" in btn["path"]:
                        sell_panel_active = True
                        logger.info(f"Sell panel active (found: {btn['path'].split('/')[-1]})")
                        break
            if sell_panel_active:
                break
            logger.info(f"Waiting for sell panel (attempt {attempt + 1})...")

        if not sell_panel_active:
            logger.warning("Could not activate sell mode")
            self._close_manage_screen()
            self.results["artifact_sell"] = "Failed (sell mode)"
            return False

        # Step 5: Select artifacts
        # Use "Select All" for bulk selling, or click individual tiles
        # For safety, let's click individual artifact tiles first
        selected = 0
        sell_count = min(len(sellable), max_sells)
        gx = self.game.win_x
        gy = self.game.win_y

        # Click artifact tiles in the visible grid
        for row in range(6):
            for col in range(8):
                if selected >= sell_count:
                    break
                tile_x = gx + self.ART_GRID_START_X + col * self.ART_TILE_SIZE
                tile_y = gy + self.ART_GRID_START_Y + row * 65
                if tile_y > gy + 480:
                    break
                pyautogui.click(tile_x, tile_y)
                time.sleep(0.3)
                selected += 1
            if selected >= sell_count:
                break

        logger.info(f"Clicked {selected} artifact tiles")

        if selected == 0:
            self._close_manage_screen()
            self.results["artifact_sell"] = "No artifacts selected"
            return True

        # Step 6: Click "Apply" (Sell) button on the sell panel
        time.sleep(1)
        if self.mod:
            apply_path = self.mod.find_button("Apply")
            if apply_path and "SellArtifactsPanel" in apply_path:
                logger.info("Clicking Apply (sell)")
                self.mod.click_path(apply_path)
                time.sleep(2)

        # Step 7: Confirm in the modal dialog
        # Modal has: Buttons_h/0 (Cancel) and Buttons_h/1 (Sell confirm)
        time.sleep(1)
        if self.mod:
            # The gold "Sell" confirm button is Buttons_h/1
            confirm_path = self.mod.find_button("Buttons_h/1")
            if confirm_path:
                logger.info("Confirming sell")
                self.mod.click_path(confirm_path)
                time.sleep(3)
            else:
                # Try BTN_Close or any button with index 1
                btns = self.mod.get_buttons()
                for btn in btns.get("buttons", []):
                    if "Buttons_h/1" in btn["path"]:
                        self.mod.click_path(btn["path"])
                        time.sleep(3)
                        break

        # Step 8: Verify silver increased
        if self.reader:
            res = self.reader.get_resources()
            silver = int(res.get("silver", 0))
            logger.info(f"Silver after sell: {silver:,}")

        self._close_manage_screen()
        self.results["artifact_sell"] = f"{selected} artifacts sold"
        return True

    # =========================================================================
    # Main daily run
    # =========================================================================

    def run_daily(self):
        parts = []
        if self.mod: parts.append("mod API")
        if self.reader: parts.append("memory")
        parts.append("screen")
        mode = " + ".join(parts)
        logger.info("=" * 50)
        logger.info(f"Daily automation ({mode})")
        logger.info("=" * 50)

        if self.reader:
            res = self.reader.get_resources()
            logger.info(f"Pre: E={int(res['energy']):,} S={int(res['silver']):,} "
                        f"G={int(res['gems'])} A={res['arena_tokens']:.1f} CB={int(res['cb_keys'])}")

        # Log active events
        if self.reader:
            events = self.reader.get_active_events()
            running_solo = [e for e in events["solo_events"] if e.get("active")]
            running_tourn = [e for e in events["tournaments"] if e.get("active")]
            if running_solo or running_tourn:
                logger.info("Active events:")
                for e in running_solo + running_tourn:
                    hours = e.get("hours_left", "?")
                    logger.info(f"  {e['name']} ({hours:.1f}h left)")

        for name, fn in [
            ("Gem Mine", self.collect_gem_mine),
            ("Shop Rewards", self.collect_shop_rewards),
            ("Timed Rewards", self.collect_timed_rewards),
            ("Clan", self.collect_clan),
            ("Quest Claims", self.collect_quests),
            ("Inbox", self.collect_inbox),
            ("Arena", lambda: self.run_arena_battles(10)),
            ("Clan Boss", lambda: self.run_clan_boss("ultra-nightmare")),
            ("Dungeon Farming", lambda: self.run_dungeon_farming(
                max_runs=10, energy_floor=1000)),
            ("Artifact Sell", lambda: self.sell_bad_artifacts(
                score_threshold=40, max_sells=50)),
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
        if "--farm" in sys.argv:
            # Dungeon farming mode: farm based on active events
            dungeon = None
            max_runs = 20
            energy_floor = 1000
            for arg in sys.argv:
                if arg.startswith("--dungeon="):
                    dungeon = arg.split("=")[1]
                if arg.startswith("--runs="):
                    max_runs = int(arg.split("=")[1])
                if arg.startswith("--energy-floor="):
                    energy_floor = int(arg.split("=")[1])
            ctrl.run_dungeon_farming(dungeon_name=dungeon,
                                      max_runs=max_runs,
                                      energy_floor=energy_floor)
        elif "--sell" in sys.argv:
            # Artifact sell mode
            threshold = 40
            max_sells = 50
            for arg in sys.argv:
                if arg.startswith("--threshold="):
                    threshold = int(arg.split("=")[1])
                if arg.startswith("--max="):
                    max_sells = int(arg.split("=")[1])
            ctrl.sell_bad_artifacts(score_threshold=threshold, max_sells=max_sells)
        elif "--events" in sys.argv:
            # Just show active events and farming recommendations
            if ctrl.reader:
                events = ctrl.reader.get_active_events()
                print("\n=== Active Events ===")
                for e in events["solo_events"]:
                    active = "ACTIVE" if e.get("active") else "inactive"
                    hours = f" ({e.get('hours_left', '?'):.1f}h left)" if e.get("hours_left") else ""
                    print(f"  SOLO: {e['name'][:50]:50s} {active}{hours}")
                for e in events["tournaments"]:
                    active = "ACTIVE" if e.get("active") else "inactive"
                    hours = f" ({e.get('hours_left', '?'):.1f}h left)" if e.get("hours_left") else ""
                    print(f"  TOUR: {e['name'][:50]:50s} {active}{hours}")
                print(f"\nRecommendations:")
                print(f"  Farm dungeons: {ctrl.reader.should_farm_dungeons()}")
                print(f"  Farm arena:    {ctrl.reader.should_farm_arena()}")
                print(f"  Upgrade gear:  {ctrl.reader.should_upgrade_artifacts()}")
                print(f"  Summon:        {ctrl.reader.should_summon_champions()}")
                print(f"  Train:         {ctrl.reader.should_level_champions()}")
                best = ctrl._detect_best_dungeon()
                if best:
                    print(f"  Best dungeon:  {best}")
        else:
            ctrl.run_daily()
    except KeyboardInterrupt:
        logger.info("Interrupted.")
    finally:
        ctrl.disconnect()


if __name__ == "__main__":
    main()
