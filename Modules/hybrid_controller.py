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

    def _ensure_village(self):
        """Fast village check via memory ViewKey, falling back to screen-based."""
        # Memory reader is the fastest and most reliable check
        if self.reader:
            for attempt in range(10):
                try:
                    vk = self.reader.get_current_view()
                    if vk == 1033:  # VillageHUD ViewKey
                        return True
                except Exception:
                    pass
                # Not at village — press escape to navigate back
                self.input.press_escape(sleep_after=1.5)
            # If we got here, 10 escapes didn't work — use slow fallback
            return self.game.ensure_village()

        # No memory reader — use slow screen-based fallback
        return self.game.ensure_village()

    # =========================================================================
    # Daily tasks
    # =========================================================================

    def collect_gem_mine(self):
        logger.info("=== Gem Mine ===")
        if not self._ensure_village():
            return False
        self._click(GEM_MINE, sleep_after=2)
        self.input.press_escape(sleep_after=2)
        self._ensure_village()
        self.results["gem_mine"] = "Collected"
        return True

    def collect_shop_rewards(self):
        logger.info("=== Shop Rewards ===")
        if not self._ensure_village():
            return False
        self._click_nav("shop", BTN_SHOP)
        offers = asset(self.asset_path, "offers.png")
        free = asset(self.asset_path, "claimFreeGift.png")
        if locate_and_click(offers, confidence=0.9, sleep_after=3):
            for rx in range(214, 890, 50):
                self._click((rx, 93), sleep_after=0.1)
                locate_and_click(free, sleep_after=1)
        self._ensure_village()
        self.results["shop"] = "Collected"
        return True

    def collect_timed_rewards(self):
        logger.info("=== Timed Rewards ===")
        if not self._ensure_village():
            return False
        tr = asset(self.asset_path, "timeRewards.png")
        rd = asset(self.asset_path, "redNotificationDot.png")
        if locate_and_click(tr, sleep_after=2):
            locate_and_click_loop(rd, sleep_after=1)
            for rx in TIMED_REWARDS_X_RANGE:
                self._click((rx, TIMED_REWARDS_Y), sleep_after=0.2)
            time.sleep(1)
            self._ensure_village()
            self.results["timed_rewards"] = "Collected"
            return True
        return False

    def collect_quests(self):
        logger.info("=== Quest Claims ===")
        if not self._ensure_village():
            return False
        self._click_nav("quests", BTN_QUESTS)
        qc = asset(self.asset_path, "questClaim.png")
        aq = asset(self.asset_path, "advancedQuests.png")
        claimed = locate_and_click_loop(qc, sleep_after=1)
        if locate_and_click(aq, sleep_after=1):
            claimed += locate_and_click_loop(qc, sleep_after=1)
        self._ensure_village()
        self.results["quests"] = f"{claimed} claimed"
        return True

    def collect_clan(self):
        logger.info("=== Clan ===")
        if not self._ensure_village():
            return False
        self._click_nav("clan", BTN_CLAN)
        locate_and_click(asset(self.asset_path, "clanMembers.png"), sleep_after=2)
        locate_and_click_loop(asset(self.asset_path, "clanCheckIn.png"), sleep_after=1)
        locate_and_click(asset(self.asset_path, "clanTreasure.png"), sleep_after=1)
        self._ensure_village()
        self.results["clan"] = "Checked in"
        return True

    def collect_inbox(self):
        logger.info("=== Inbox ===")
        if not self._ensure_village():
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
        self._ensure_village()
        self.results["inbox"] = "Collected"
        return True

    # =========================================================================
    # Arena
    # =========================================================================

    # Arena opponent row layout (game-relative Y positions for 5 visible slots)
    ARENA_ROW_Y = [195, 275, 355, 435, 515]
    ARENA_BATTLE_X = 820  # Battle button on right side of each row

    # Mod API paths for arena navigation
    _ARENA_PANEL = ("UIManager/Canvas (Ui Root)/Dialogs/"
                    "[DV] BattleModeSelectionDialog/Workspace/Content/"
                    "Scroll Items/Viewport/Content/Arena/Panel")
    _ARENA_CLASSIC = "SceneView/Canvas/1x1"
    _ARENA_FIGHT = ("UIManager/Canvas (Ui Root)/Dialogs/[DV] ArenaDialog/"
                    "Workspace/Content/Tabs/Battle_h/ArenaBattleTab(Clone)/"
                    "Content/Opponents/Viewport/Content/{idx}/StartBattle_h")
    _ARENA_START = ("UIManager/Canvas (Ui Root)/Dialogs/"
                    "[DV] ArenaHeroesSelectionDialog/Workspace/Content/"
                    "LowerPanel/Content/StartBattleButton/Default_h")

    def _nav_to_arena(self):
        """Navigate from village to classic arena opponent list."""
        # Direct IL2CPP navigation (fastest, most reliable)
        if self.mod:
            try:
                result = self.mod._get("/navigate?target=arena")
                if result and "navigated" in result:
                    time.sleep(3)
                    return True
            except Exception:
                pass

        # Fallback: UI button navigation
        self._click_nav("battle", BTN_BATTLE, sleep_after=3)
        if self.mod:
            if self.mod.click_path(self._ARENA_PANEL):
                time.sleep(3)
                if self.mod.click_path(self._ARENA_CLASSIC):
                    time.sleep(3)
                    return True

        # Fallback to image matching
        if self.game.smart_click("arenaTab.png", max_attempts=3):
            time.sleep(2)
            self.game.smart_click("classicArena.png", max_attempts=2)
            time.sleep(2)
            return True

        self._ensure_village()
        return False

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
        """Pick the weakest opponent and invoke OnStartClick via context-call.
        Uses memory for opponent analysis, context-call for MVVM bypass.
        Returns True if we navigated to team selection.
        """
        # Context-call: invoke OnStartClick on opponent's CurrentOpponentContext
        if self.mod and self.reader:
            opps = self.reader.get_arena_opponents()
            available = [(i, o) for i, o in enumerate(opps[:10]) if o["available"]]
            if available:
                available.sort(key=lambda x: x[1]["power"])
                target_idx, target = available[0]
                logger.info(f"Target: [{target_idx}] {target['name']} "
                             f"(power={target['power']:,})")
                result = self.mod.arena_start_fight(target_idx)
                if result:
                    time.sleep(3)
                    return True

        # Context-call fallback: try first opponent
        if self.mod:
            for idx in range(10):
                result = self.mod.arena_start_fight(idx)
                if result:
                    time.sleep(3)
                    return True

        # Image fallback
        arena_battle = asset(self.asset_path, "arenaBattle.png")
        if arena_battle:
            loc = pyautogui.locateOnScreen(arena_battle, confidence=0.6)
            if loc:
                pyautogui.click(*pyautogui.center(loc))
                time.sleep(3)
                return True
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
            # Log full opponent analysis
            opps = self.reader.get_arena_opponents()
            available = sorted([o for o in opps if o["available"]], key=lambda o: o["power"])
            for o in available:
                logger.info(f"  {o['name']:20s} power={o['power']:>10,}")

        if not self._ensure_village():
            return False
        if not self._nav_to_arena():
            return False

        battles = 0
        arena_start = asset(self.asset_path, "arenaStart.png")

        while battles < num_battles:
            # Check tokens before each fight
            if self.reader and not self.reader.has_arena_tokens():
                logger.info("Out of arena tokens (memory).")
                break

            # Pick and click the weakest opponent
            if not self._pick_and_click_opponent():
                # Try refreshing via mod API
                if self.mod:
                    refresh = self.mod.find_button("FreeResfreshAvailable")
                    if refresh and self.mod.click_path(refresh):
                        time.sleep(3)
                        if not self._pick_and_click_opponent():
                            break
                        # continue to fight
                    else:
                        break
                else:
                    break

            # Click Start on team selection — use context-call (MVVM bypass)
            started = False
            if self.mod:
                result = self.mod.arena_start_battle()
                if result:
                    started = True
                    time.sleep(3)
            if not started:
                if not locate_and_click(arena_start, confidence=0.9, sleep_after=3):
                    self.input.press_escape(sleep_after=2)
                    continue

            # Memory-based battle detection (instant) or image polling (fallback)
            result = self._wait_battle(timeout=180)
            battles += 1
            logger.info(f"Battle {battles}/{num_battles}: {result['result']}")

            # Dismiss battle results via context-call
            time.sleep(3)
            for _ in range(10):
                if self.mod:
                    result = self.mod.dismiss_battle_finish()
                    if result:
                        time.sleep(2)
                        continue
                    # Check if back at arena opponent list
                    try:
                        ctx = self.mod.get_view_contexts()
                        active = [d["dialog"] for d in ctx.get("dialogs", []) if d.get("context_class")]
                        if "[DV] ArenaDialog" in active and "[DV] BattleFinish" not in " ".join(active):
                            break
                    except Exception:
                        pass
                # Fallback image matching
                if self.reader:
                    vk = self.reader.get_current_view()
                    if vk == 1009:  # ArenaDialog
                        break
                tap = asset(self.asset_path, "tapToContinue.png")
                ret = asset(self.asset_path, "returnToArena.png")
                if tap and locate_and_click(tap, confidence=0.7, sleep_after=2):
                    continue
                if ret and locate_and_click(ret, confidence=0.7, sleep_after=3):
                    continue
                self._click(CENTER, sleep_after=2)

        self._ensure_village()
        self.results["arena"] = f"{battles} battles fought"
        return True

    # =========================================================================
    # Clan Boss
    # =========================================================================

    # Mod API paths for Clan Boss
    _CB_PANEL = ("UIManager/Canvas (Ui Root)/Dialogs/"
                 "[DV] BattleModeSelectionDialog/Workspace/Content/"
                 "Scroll Items/Viewport/Content/AllianceActivity/Panel")
    _CB_DEMON_LORD = "SceneView/Canvas/DemonLord"

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

        if not self._ensure_village():
            return False

        # Navigate: Direct IL2CPP or fallback to UI buttons
        navigated = False
        if self.mod:
            try:
                result = self.mod._get("/navigate?target=cb")
                if result and "navigated" in result:
                    time.sleep(4)
                    navigated = True
            except Exception:
                pass

        if not navigated and self.mod:
            self._click_nav("battle", BTN_BATTLE, sleep_after=3)
            if self.mod.click_path(self._CB_PANEL):
                time.sleep(3)
                if self.mod.click_path(self._CB_DEMON_LORD):
                    time.sleep(4)
                    navigated = True

        if not navigated:
            # Fallback to image matching
            cb = asset(self.asset_path, "CB.png")
            if not locate_and_click(cb, confidence=0.8, sleep_after=3, max_attempts=5):
                self._ensure_village()
                return False
            dl = asset(self.asset_path, "demonLord2.png")
            if not locate_and_click(dl, confidence=0.7, sleep_after=4, max_attempts=5):
                self._ensure_village()
                return False

        if self.reader:
            logger.info(f"CB screen: {self.reader.get_current_view_name()}")

        # Claim rewards via mod API
        if self.mod:
            chest_btn = self.mod.find_button("CollectChest")
            if chest_btn:
                self.mod.click_path(chest_btn)
                time.sleep(2)
                logger.info("Claimed CB chest")

        # Click Battle — use context-call (bypasses MVVM), fallback to UI
        battle_clicked = False
        if self.mod:
            # Try context-call on AllianceEnemiesBattlesContext.OnStartClick
            result = self.mod.cb_start_battle()
            if result:
                time.sleep(3)
                battle_clicked = True
            else:
                # Fallback: scroll to UNM difficulty and click BTN_2_StartBattle
                buttons = self.mod.get_buttons()
                # Scroll right panel to show UNM difficulty
                gx = self.game.win_x + 750
                for drag in range(4):
                    pyautogui.moveTo(gx, self.game.win_y + 380)
                    time.sleep(0.15)
                    pyautogui.mouseDown()
                    pyautogui.moveTo(gx, self.game.win_y + 100, duration=0.4)
                    pyautogui.mouseUp()
                    time.sleep(0.5)
                time.sleep(1)

                # Select UNM difficulty
                battle_btns = [b["path"] for b in buttons.get("buttons", [])
                              if "PanelAndIcon/Panel/BTN_1" in b["path"]]
                if battle_btns:
                    logger.info("Selecting UNM difficulty")
                    self.mod.click_path(battle_btns[0])
                    time.sleep(1)

                # Click Start Battle
                start_btn = self.mod.find_button("BTN_2_StartBattle")
                if start_btn:
                    logger.info("Clicking Battle button")
                    if self.mod.click_path(start_btn):
                        time.sleep(3)
                        battle_clicked = True

        if not battle_clicked:
            # Fallback: scroll and use image matching
            gx = self.game.win_x + 490
            for drag in range(3):
                pyautogui.moveTo(gx, self.game.win_y + 380)
                time.sleep(0.15)
                pyautogui.mouseDown()
                pyautogui.moveTo(gx, self.game.win_y + 100, duration=0.4)
                pyautogui.mouseUp()
                time.sleep(0.5)
            time.sleep(1)
            cb_battle = asset(self.asset_path, "CBbattle.png")
            if not locate_and_click(cb_battle, confidence=0.6, sleep_after=3, max_attempts=3):
                logger.info("No CB battle button (already fought today).")
                self._ensure_village()
                self.results["clan_boss"] = "Already fought"
                return True

        # Check if at team selection (ViewKey 1072 or any HeroesSelection)
        if self.reader:
            vk = self.reader.get_current_view()
            logger.info(f"After Battle click: view={vk} ({self.reader.get_current_view_name()})")
            if vk == 1071:  # Still on ClanBoss screen — battle didn't open
                logger.warning("Battle button didn't open team selection")
                self._ensure_village()
                self.results["clan_boss"] = "Failed (no team select)"
                return False

        # Click Start on team selection — try mod API then image
        started = False
        if self.mod:
            # CB team selection uses same StartBattleButton path pattern
            cb_start_path = ("UIManager/Canvas (Ui Root)/Dialogs/"
                            "[DV] AllianceBossHeroesSelectionDialog/Workspace/"
                            "Content/LowerPanel/Content/StartBattleButton/Default_h")
            if self.mod.click_path(cb_start_path) or self.mod.click_path(self._ARENA_START):
                started = True
                time.sleep(3)
        if not started:
            cb_start = asset(self.asset_path, "CBstart.png")
            if not locate_and_click(cb_start, confidence=0.8, sleep_after=3, max_attempts=5):
                logger.warning("CBstart not found")
                self._ensure_village()
                return False

        # Wait for battle
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

        self._ensure_village()
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

        if not self._ensure_village():
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
            self._ensure_village()
            return False

        # Select the target dungeon
        if not self._select_dungeon(dungeon_name):
            logger.error(f"Failed to select {dungeon_name}")
            self._ensure_village()
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

        self._ensure_village()

        # Log results
        if self.reader:
            energy_after = int(self.reader.get_resources().get("energy", 0))
            logger.info(f"Energy after: {energy_after:,}")
        self.results["dungeon_farming"] = f"{dungeon_name}: {runs} runs"
        return True

    # =========================================================================
    # Artifact Sell (UI-based, server-persistent)
    # =========================================================================

    # Inventory UI path constants
    _INV_BASE = ("UIManager/Canvas (Ui Root)/OverlayDialogs/[OV] HeroesInfoOverlay/"
                 "Workspace/InventoryViewLoader_h/InventoryView(Clone)")
    _SELL_MODE = _INV_BASE + "/InventoryWindowHolder/InventoryWindow/ViewMode/SellMode"
    _SELL_APPLY = _INV_BASE + "/SellArtifactsPanel_h/Buttons/Apply"
    _SELL_CANCEL = _INV_BASE + "/SellArtifactsPanel_h/Buttons/Cancel"
    _SELL_ALL = _INV_BASE + "/SellArtifactsPanel_h/Buttons/SelectAll_h"
    _ART_GROUPS = (_INV_BASE + "/InventoryWindowHolder/InventoryWindow/Content/"
                   "Artifacts_h/Tab1.Content/GroupsViewport/Groups/Groups")

    def _open_inventory(self):
        """Navigate to Heroes → click artifact slot → open inventory.
        Returns True if inventory is visible.
        """
        if not self._ensure_village():
            return False
        if not self.mod:
            return False

        self.mod.click_button("heroes")
        time.sleep(4)

        # Click artifact slot 1 to open inventory panel
        slot = ("UIManager/Canvas (Ui Root)/OverlayDialogs/[OV] HeroesInfoOverlay/"
                "Workspace/Content/DetailsBlockLoader_h/DetailsBlock(Clone)/Swipe/1/"
                "PanelHolder/UpperPanel/Artifacts/EquipmentArtifactSlot (1)/"
                "BASE_ArtifactAvatar_h")
        result = self.mod.click_path(slot)
        if not result:
            logger.warning("Could not click artifact slot")
            return False
        time.sleep(3)

        # Verify inventory opened by checking for SellMode toggle
        tog = self.mod.find_toggle("SellMode")
        if not tog:
            logger.warning("Inventory did not open (no SellMode toggle)")
            return False
        logger.info("Inventory opened successfully")
        return True

    def _close_inventory(self):
        """Close inventory and return to village."""
        close = ("UIManager/Canvas (Ui Root)/OverlayDialogs/[OV] HeroesInfoOverlay/"
                 "Workspace/Content/HeroesHeader/CloseButton")
        self.mod.click_path(close)
        time.sleep(2)
        self._ensure_village()

    def sell_bad_artifacts(self, max_rank=3, max_rarity=1):
        """Sell low-rank/rarity artifacts through the game UI (server-persistent).

        Flow: Heroes → artifact slot → SellMode → select items → Apply → Confirm.
        Uses /click on SellMode to activate MVVM binding properly.

        Args:
            max_rank: Sell artifacts with rank <= this (1-6, default 3)
            max_rarity: Sell artifacts with rarity <= this (0=common, 1=uncommon)
        """
        logger.info(f"=== Artifact Sell (rank<={max_rank}, rarity<={max_rarity}) ===")

        if not self.mod:
            self.results["artifact_sell"] = "Skipped (no mod API)"
            return False

        # Check how many trash artifacts exist
        try:
            data = self.mod.get_artifacts(max_rank=max_rank, max_rarity=max_rarity)
            if not data or "error" in data:
                logger.error(f"Artifact API error: {data}")
                self.results["artifact_sell"] = "Failed (API)"
                return False
            artifacts = data.get("artifacts", [])
            sellable = [a for a in artifacts
                        if not a.get("equipped") and a.get("level", 0) == 0]
            if not sellable:
                logger.info("No trash artifacts to sell")
                self.results["artifact_sell"] = "Nothing to sell"
                return True
            total_value = sum(a.get("sellPrice", 0) for a in sellable)
            logger.info(f"Found {len(sellable)} sellable artifacts (~{total_value:,} silver)")
        except Exception as e:
            logger.warning(f"Could not pre-check artifacts: {e}")
            sellable = None

        # Use direct /sell command with specific IDs
        # Safe: only sells artifacts matching our strict filter criteria
        sell_ids = [a["id"] for a in sellable]
        sold_total = 0

        # Sell in batches of 20
        for i in range(0, len(sell_ids), 20):
            batch = sell_ids[i:i+20]
            ids_str = ",".join(str(aid) for aid in batch)
            try:
                result = self.mod.sell_artifacts(ids_str)
                sold = result.get("sold", 0) if isinstance(result, dict) else 0
                sold_total += sold
                logger.info(f"Batch {i//20+1}: sold {sold} (ids: {ids_str[:50]}...)")
            except Exception as e:
                logger.warning(f"Sell batch failed: {e}")
            time.sleep(1)

        self.results["artifact_sell"] = f"{sold_total} artifacts sold"
        return True

    # =========================================================================
    # Market Shard Buying
    # =========================================================================

    def buy_market_shards(self):
        """Buy mystery shards from the Magic Market via mod API.

        Flow:
        1. Disable auto-dismiss (Market popup is part of navigation)
        2. Open Market building via InvokeCommand
        3. Wait for Market to load (ShopAggregatorDialog)
        4. Read shop items, find type=3 (shards)
        5. Click Price button → BuyButton_h for each shard
        6. Handle showcase animation after purchase
        7. Re-enable auto-dismiss
        """
        logger.info("=== Market Shards ===")

        if not self.mod:
            self.results["market_shards"] = "Skipped (no mod API)"
            return False

        if not self._ensure_village():
            return False

        # Disable auto-dismiss (Market navigation uses a popup)
        try:
            self.mod.set_auto_dismiss(False)
        except Exception:
            pass

        try:
            # Open Market building
            logger.info("Opening Market...")
            if not self.mod.open_market():
                logger.warning("Failed to open Market")
                self.mod.set_auto_dismiss(True)
                self.results["market_shards"] = "Failed (Market open)"
                return False

            time.sleep(5)

            # Read shop inventory
            shop = self.mod.get_shop_items()
            if not shop or "error" in shop:
                logger.warning(f"Failed to read shop: {shop}")
                self.mod.set_auto_dismiss(True)
                self._ensure_village()
                self.results["market_shards"] = "Failed (shop read)"
                return False

            items = shop.get("items", [])
            # type=3 = mystery shards, price should be cheap (~5k-10k silver)
            shards = [item for item in items if item.get("type") == 3]
            logger.info(f"Market: {len(items)} items total")
            for item in items:
                logger.info(f"  id={item.get('id')} type={item.get('type')} "
                            f"rare={item.get('rare')} price={item.get('price')}")
            logger.info(f"Shards found: {len(shards)}")

            if not shards:
                logger.info("No shards available")
                # Close Market
                self.mod.click_found("CloseButton")
                time.sleep(2)
                self.mod.set_auto_dismiss(True)
                self._ensure_village()
                self.results["market_shards"] = "No shards available"
                return True

            # Buy each shard (with price safety check)
            bought = 0
            for shard in shards:
                sid = shard["id"]
                price_str = shard.get("price", "")
                logger.info(f"Buying shard id={sid} price={price_str}")

                # Safety: mystery shards cost ~5k-10k silver. Skip if > 15k
                try:
                    price_val = int(''.join(c for c in price_str if c.isdigit()))
                    if price_val > 15000:
                        logger.warning(f"Skipping id={sid} — price {price_val} too high for shard")
                        continue
                except (ValueError, TypeError):
                    logger.warning(f"Skipping id={sid} — can't parse price: {price_str}")
                    continue

                if not self.mod.buy_market_item(sid):
                    logger.warning(f"Failed to buy shard {sid}")
                    continue

                bought += 1
                time.sleep(3)

                # Dismiss showcase if it appears
                for _ in range(5):
                    try:
                        status = self.mod.get_status()
                        if "Showcase" in status.get("scene", ""):
                            self.mod.click_found("CloseButton")
                            time.sleep(2)
                        else:
                            break
                    except Exception:
                        time.sleep(2)

            logger.info(f"Bought {bought}/{len(shards)} shards")

            # Close Market
            self.mod.click_found("CloseButton")
            time.sleep(2)

        finally:
            # Re-enable auto-dismiss
            try:
                self.mod.set_auto_dismiss(True)
            except Exception:
                pass

        self._ensure_village()
        self.results["market_shards"] = f"{bought} shards bought"
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
            ("Market Shards", self.buy_market_shards),
            ("Artifact Sell", lambda: self.sell_bad_artifacts(
                max_rank=3, max_rarity=1)),
            ("Dungeon Farming", lambda: self.run_dungeon_farming(
                max_runs=10, energy_floor=1000)),
        ]:
            try:
                logger.info(f"[{name}] Starting...")
                fn()
            except Exception as e:
                logger.error(f"[{name}] Failed: {e}", exc_info=True)
                try:
                    self._ensure_village()
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
            max_rank = 3
            max_rarity = 1
            for arg in sys.argv:
                if arg.startswith("--max-rank="):
                    max_rank = int(arg.split("=")[1])
                if arg.startswith("--max-rarity="):
                    max_rarity = int(arg.split("=")[1])
            ctrl.sell_bad_artifacts(max_rank=max_rank, max_rarity=max_rarity)
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
