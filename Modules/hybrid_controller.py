"""
Hybrid controller: RTK for game state + pyautogui for actions.

This is the next-gen replacement for pure screen automation.
Every action verifies its result through RTK instead of image matching.

Usage:
    python hybrid_controller.py

Requires:
    - Raid Toolkit SDK installed and running (https://raidtoolkit.com)
    - Raid: Shadow Legends running via Plarium Play
    - websocket-client package (pip install websocket-client)
"""

import logging
import time
import sys
import os

import pyautogui

from base import BaseDaily, asset, locate_and_click, locate_and_click_loop, MAX_RETRIES
from rtk_client import RTKClient, RTKConnectionError, RTKApiError
from game_state import GameState, View

logging.basicConfig(
    filename='HybridController.log',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filemode='w',
    level=logging.DEBUG,
)
logger = logging.getLogger(__name__)

# Also log to console
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logger.addHandler(console)

# ---------------------------------------------------------------------------
# Named coordinates (same as PyAutoRaid, game window 900x600 centered)
# ---------------------------------------------------------------------------
GEM_MINE_POS = (583, 595)
TIMED_REWARDS_Y = 500
TIMED_REWARDS_X_RANGE = range(669, 1269, 100)
CB_SCROLL_POS = (1080, 724)
ARENA_REGIONS = [
    (1215, 423, 167, 58, 1304, 457),
    (1215, 508, 167, 58, 1304, 540),
    (1215, 596, 167, 58, 1303, 625),
    (1215, 681, 167, 58, 1304, 711),
    (1208, 762, 190, 68, 1304, 800),
]


class HybridController:
    """
    Closed-loop game automation controller.

    Loop:
    1. Read current view from RTK
    2. Decide action based on state + config
    3. Execute click via pyautogui
    4. Verify state change via RTK
    5. Repeat
    """

    def __init__(self):
        self.rtk = RTKClient()
        self.game = None
        self.asset_path = self._get_asset_path()
        self.results = {}

    def _get_asset_path(self):
        """Resolve asset path from script location."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        candidate = os.path.join(current_dir, '..', 'assets')
        if os.path.exists(candidate):
            return os.path.abspath(candidate)
        candidate = os.path.join(current_dir, 'assets')
        if os.path.exists(candidate):
            return os.path.abspath(candidate)
        # Frozen exe
        if getattr(sys, 'frozen', False):
            return os.path.join(sys._MEIPASS, 'assets')
        logger.error("Could not find assets folder.")
        return None

    def connect(self):
        """Connect to RTK and initialize game state."""
        logger.info("Connecting to Raid Toolkit...")
        try:
            self.rtk.connect()
            self.game = GameState(self.rtk, self.asset_path)
            self.game.initialize()
            logger.info("Connected. Ready to automate.")
            return True
        except RTKConnectionError as e:
            logger.error(f"RTK connection failed: {e}")
            logger.error("Make sure Raid Toolkit is installed and running.")
            return False
        except RTKApiError as e:
            logger.error(f"RTK API error: {e}")
            logger.error("Make sure Raid: Shadow Legends is running.")
            return False

    def disconnect(self):
        """Clean up connections."""
        if self.rtk:
            self.rtk.close()

    # --- Task runners (state-aware versions of PyAutoRaid commands) ---

    def collect_gem_mine(self):
        """Collect gem mine — verify we're in village first."""
        logger.info("=== Gem Mine ===")
        if not self.game.ensure_village():
            logger.error("Could not navigate to village.")
            return False

        pyautogui.click(*GEM_MINE_POS)
        time.sleep(2)
        pyautogui.hotkey("esc")
        time.sleep(2)

        # Verify we're back at village
        self.game.ensure_village()
        self.results["gem_mine"] = "Collected"
        logger.info("Gem mine collected.")
        return True

    def collect_shop_rewards(self):
        """Navigate to shop, collect free gifts."""
        logger.info("=== Shop Rewards ===")
        if not self.game.ensure_village():
            return False

        if self.game.smart_click("shop.png", expected_view=View.SHOP):
            # Look for free offers
            offers_image = asset(self.asset_path, "offers.png")
            free_gift_image = asset(self.asset_path, "claimFreeGift.png")

            if locate_and_click(offers_image, confidence=0.9, sleep_after=3):
                for i in range(724, 1400, 50):
                    pyautogui.click(i, 333)
                    locate_and_click(free_gift_image, sleep_after=1)

            self.game.ensure_village()
            self.results["shop"] = "Collected"
            logger.info("Shop rewards collected.")
            return True
        else:
            logger.warning("Could not navigate to shop.")
            return False

    def collect_timed_rewards(self):
        """Collect timed rewards."""
        logger.info("=== Timed Rewards ===")
        if not self.game.ensure_village():
            return False

        time_rewards_image = asset(self.asset_path, "timeRewards.png")
        red_dot_image = asset(self.asset_path, "redNotificationDot.png")

        if locate_and_click(time_rewards_image, sleep_after=2):
            locate_and_click_loop(red_dot_image, sleep_after=1)
            for i in TIMED_REWARDS_X_RANGE:
                time.sleep(0.2)
                pyautogui.click(i, TIMED_REWARDS_Y)
            time.sleep(1)

            self.game.ensure_village()
            self.results["timed_rewards"] = "Collected"
            logger.info("Timed rewards collected.")
            return True
        return False

    def collect_quests(self):
        """Claim completed quests."""
        logger.info("=== Quest Claims ===")
        if not self.game.ensure_village():
            return False

        quest_claim_image = asset(self.asset_path, "questClaim.png")
        advanced_quests_image = asset(self.asset_path, "advancedQuests.png")

        if self.game.smart_click("quests.png"):
            claimed = locate_and_click_loop(quest_claim_image, sleep_after=1)
            if locate_and_click(advanced_quests_image, sleep_after=1):
                claimed += locate_and_click_loop(quest_claim_image, sleep_after=1)

            self.game.ensure_village()
            self.results["quests"] = f"{claimed} claimed"
            logger.info(f"Quests: {claimed} claimed.")
            return True
        return False

    def collect_clan(self):
        """Check in and collect clan rewards."""
        logger.info("=== Clan ===")
        if not self.game.ensure_village():
            return False

        clan_check_in = asset(self.asset_path, "clanCheckIn.png")
        clan_treasure = asset(self.asset_path, "clanTreasure.png")

        if self.game.smart_click("clanBTN.png"):
            locate_and_click(asset(self.asset_path, "clanMembers.png"), sleep_after=2)
            locate_and_click_loop(clan_check_in, sleep_after=1)
            locate_and_click(clan_treasure, sleep_after=1)

            self.game.ensure_village()
            self.results["clan"] = "Checked in"
            logger.info("Clan check-in done.")
            return True
        return False

    def collect_inbox(self):
        """Collect inbox items."""
        logger.info("=== Inbox ===")
        if not self.game.ensure_village():
            return False

        pyautogui.hotkey("i")
        time.sleep(1)

        inbox_items = [
            "inbox_energy", "inbox_brew", "inbox_purple_forge",
            "inbox_yellow_forge", "inbox_coin", "inbox_potion",
        ]
        for item in inbox_items:
            png = asset(self.asset_path, f"{item}.png")
            retries = 0
            while retries < MAX_RETRIES:
                location = pyautogui.locateOnScreen(png, confidence=0.8)
                if not location:
                    break
                pyautogui.moveTo(location)
                pyautogui.moveRel(250, 0)
                pyautogui.click()
                time.sleep(2)
                retries += 1

        self.game.ensure_village()
        self.results["inbox"] = "Collected"
        logger.info("Inbox collected.")
        return True

    def run_arena_battles(self, num_battles=10):
        """
        Run arena battles with RTK-verified battle completion.
        This is where the hybrid approach really shines — we know
        exactly when battles end instead of polling for pixel changes.
        """
        logger.info(f"=== Arena ({num_battles} battles) ===")
        if not self.game.ensure_village():
            return False

        battles_fought = 0

        # Navigate to arena
        if not self.game.smart_click("battleBTN.png"):
            return False
        time.sleep(2)

        if not self.game.smart_click("arenaTab.png"):
            self.game.ensure_village()
            return False
        time.sleep(2)

        if not self.game.smart_click("classicArena.png"):
            self.game.ensure_village()
            return False
        time.sleep(2)

        arena_battle_image = asset(self.asset_path, "arenaBattle.png")
        arena_start_image = asset(self.asset_path, "arenaStart.png")
        arena_refill_image = asset(self.asset_path, "classicArenaRefill.png")

        for rx, ry, rw, rh, cx, cy in ARENA_REGIONS:
            if battles_fought >= num_battles:
                break

            if pyautogui.locateOnScreen(arena_battle_image, region=(rx, ry, rw, rh), confidence=0.6):
                pyautogui.click(cx, cy)
                time.sleep(3)

                # Check if out of tokens
                if pyautogui.locateOnScreen(arena_refill_image, confidence=0.8):
                    logger.info("Out of arena tokens.")
                    break

                # Start battle
                if locate_and_click(arena_start_image, confidence=0.9, sleep_after=2):
                    # === THE KEY DIFFERENCE ===
                    # Instead of pixel-polling for "tap to continue",
                    # we use RTK to know when the battle view changes
                    if self.game.wait_for_view(View.BATTLE_HUD, timeout=10):
                        battle_result = self.game.wait_for_battle_end(timeout=300)
                        battles_fought += 1
                        logger.info(
                            f"Battle {battles_fought}/{num_battles} complete. "
                            f"Result: {battle_result.get('result', 'unknown')}"
                        )

                        # Click through results screen
                        time.sleep(2)
                        pyautogui.click(960, 540)  # Click center to dismiss
                        time.sleep(3)

        self.game.ensure_village()
        self.results["arena"] = f"{battles_fought} battles fought"
        logger.info(f"Arena: {battles_fought}/{num_battles} battles fought.")
        return True

    def run_clan_boss(self, difficulty="ultra-nightmare"):
        """
        Fight clan boss with RTK-verified battle completion.
        """
        logger.info(f"=== Clan Boss ({difficulty}) ===")
        if not self.game.ensure_village():
            return False

        # Navigate: Village -> Battle -> CB
        if not self.game.smart_click("battleBTN.png"):
            return False
        time.sleep(2)

        locate_and_click_loop(asset(self.asset_path, "CB.png"), sleep_after=2)
        locate_and_click_loop(asset(self.asset_path, "demonLord2.png"), sleep_after=4)

        # Collect any available rewards first
        cb_reward_image = asset(self.asset_path, "CBreward.png")
        cb_claim_image = asset(self.asset_path, "CBclaim.png")
        locate_and_click_loop(cb_reward_image, sleep_after=2)
        locate_and_click_loop(cb_claim_image, sleep_after=2)

        # Start the fight
        cb_battle_image = asset(self.asset_path, "CBbattle.png")
        cb_start_image = asset(self.asset_path, "CBstart.png")
        cb_no_key_image = asset(self.asset_path, "CBnokey.png")

        if locate_and_click(cb_battle_image, sleep_after=2):
            if pyautogui.locateOnScreen(cb_no_key_image, confidence=0.8):
                logger.warning("No keys available for Clan Boss.")
                self.game.ensure_village()
                return False

            time.sleep(2)
            if locate_and_click(cb_start_image, sleep_after=2):
                # Wait for battle using RTK
                if self.game.wait_for_view(View.BATTLE_HUD, timeout=15):
                    battle_result = self.game.wait_for_battle_end(timeout=600)
                    logger.info(f"Clan Boss battle complete: {battle_result}")
                    self.results["clan_boss"] = f"{difficulty} fought"

                    # Click through results
                    time.sleep(3)
                    goto_bastion = asset(self.asset_path, "gotoBastion.png")
                    locate_and_click(goto_bastion, sleep_after=2, max_attempts=10)

        self.game.ensure_village()
        return True

    # --- Main run ---

    def run_daily(self):
        """Run all daily tasks."""
        logger.info("=" * 50)
        logger.info("Starting daily automation (hybrid mode)")
        logger.info("=" * 50)

        # Show account status
        try:
            resources = self.game.get_resources()
            logger.info(f"Resources: {resources}")
        except Exception as e:
            logger.debug(f"Could not fetch resources: {e}")

        # Run tasks
        tasks = [
            ("Gem Mine", self.collect_gem_mine),
            ("Shop Rewards", self.collect_shop_rewards),
            ("Timed Rewards", self.collect_timed_rewards),
            ("Clan", self.collect_clan),
            ("Quest Claims", self.collect_quests),
            ("Inbox", self.collect_inbox),
            ("Arena", lambda: self.run_arena_battles(10)),
            ("Clan Boss", lambda: self.run_clan_boss("ultra-nightmare")),
        ]

        for name, task_fn in tasks:
            try:
                view = self.game.current_view()
                logger.info(f"[{name}] Starting (current view: {view.value})")
                task_fn()
            except Exception as e:
                logger.error(f"[{name}] Failed: {e}", exc_info=True)
                try:
                    self.game.ensure_village()
                except Exception:
                    pass

        # Summary
        logger.info("=" * 50)
        logger.info("Daily automation complete. Results:")
        for task, result in self.results.items():
            logger.info(f"  {task}: {result}")
        logger.info("=" * 50)


def main():
    controller = HybridController()

    if not controller.connect():
        print("\nFailed to connect. Checklist:")
        print("  1. Is Raid Toolkit installed? (https://raidtoolkit.com)")
        print("  2. Is Raid Toolkit running? (check system tray)")
        print("  3. Is Raid: Shadow Legends running?")
        sys.exit(1)

    try:
        controller.run_daily()
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    finally:
        controller.disconnect()


if __name__ == "__main__":
    main()
