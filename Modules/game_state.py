"""
Game state machine and screen navigator.

Uses RTK to know which screen we're on, and pyautogui to navigate.
The key insight: we ALWAYS know our current state via RTK, so clicks
become state transitions rather than blind guesses.
"""

import logging
import time
from enum import Enum

import pyautogui

from base import asset, locate_and_click, wait_for_image
from rtk_client import RTKClient, RTKConnectionError, RTKApiError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Known ViewKey values from RTK (subset — add more as discovered)
# ---------------------------------------------------------------------------
class View(str, Enum):
    """Game screen identifiers returned by RTK's getCurrentViewInfo()."""
    VILLAGE = "Village"                  # Main bastion/village
    MAP = "Map"                          # Campaign map
    DUNGEONS_MAP = "DungeonsMap"         # Dungeon selection
    ARENA_DIALOG = "ArenaDialog"         # Arena main screen
    ARENA_3X3 = "Arena3x3Dialog"         # Tag Team Arena
    BATTLE_HUD = "BattleHUD"            # In battle
    BATTLE_FINISH = "BattleFinishStoryDialog"  # Battle results
    PORTAL_DIALOG = "PortalDialog"       # Summoning portal
    FORGE_DIALOG = "ForgeDialog"         # Forge
    HEROES_INFO = "HeroesInfoOverlay"    # Hero roster
    DOOM_TOWER = "DoomTowerMap"          # Doom Tower
    FACTION_WARS = "FractionWarsMap"     # Faction Wars
    SHOP = "ShopDialog"                  # Shop
    CLAN = "ClanDialog"                  # Clan
    QUESTS = "QuestsDialog"             # Quests/missions
    INBOX = "InboxDialog"                # Inbox
    TAVERN = "TavernDialog"             # Tavern (upgrades)
    MARKET = "MarketDialog"             # Market
    CLAN_BOSS = "ClanBossDialog"        # Clan Boss
    UNKNOWN = "Unknown"

    @classmethod
    def from_key(cls, key: str):
        """Convert a ViewKey string to a View enum, with fallback."""
        for member in cls:
            if member.value == key:
                return member
        logger.warning(f"Unknown ViewKey: {key}")
        return cls.UNKNOWN


class GameState:
    """
    Reads game state from RTK and provides high-level navigation.
    Combines RTK state reading with pyautogui for actions.
    """

    def __init__(self, rtk: RTKClient, asset_path: str):
        self.rtk = rtk
        self.asset_path = asset_path
        self.account_id = None

    def initialize(self):
        """Connect to RTK and find the active game account."""
        if not self.rtk.is_connected:
            self.rtk.connect()

        accounts = self.rtk.get_connected_accounts()
        if not accounts:
            raise RTKApiError("No running game instances found. Is Raid open?")
        self.account_id = accounts[0]["id"]
        logger.info(f"Connected to account: {accounts[0].get('name', self.account_id)}")

    # --- State reading ---

    def current_view(self) -> View:
        """Get the current screen as a View enum."""
        info = self.rtk.get_current_view(self.account_id)
        return View.from_key(info.get("viewKey", "Unknown"))

    def is_on(self, view: View) -> bool:
        """Check if we're on a specific screen."""
        return self.current_view() == view

    def wait_for_view(self, target: View, timeout=60, poll_interval=1) -> bool:
        """
        Wait for a specific screen to appear.
        Returns True if reached, False on timeout.
        """
        start = time.time()
        while time.time() - start < timeout:
            if self.is_on(target):
                return True
            time.sleep(poll_interval)
        logger.warning(f"Timed out waiting for {target.value} after {timeout}s")
        return False

    def wait_for_view_change(self, from_view: View = None, timeout=30, poll_interval=0.5) -> View:
        """
        Wait for the screen to change from the current one.
        Returns the new View.
        """
        if from_view is None:
            from_view = self.current_view()
        start = time.time()
        while time.time() - start < timeout:
            current = self.current_view()
            if current != from_view:
                return current
            time.sleep(poll_interval)
        logger.warning(f"View did not change from {from_view.value} after {timeout}s")
        return from_view

    def wait_for_battle_end(self, timeout=600, poll_interval=2) -> dict:
        """
        Wait for a battle to finish by monitoring the view.
        Returns the last battle response when done.
        """
        logger.info("Waiting for battle to end...")
        start = time.time()
        while time.time() - start < timeout:
            view = self.current_view()
            if view != View.BATTLE_HUD:
                logger.info(f"Battle ended, now on: {view.value}")
                time.sleep(1)
                try:
                    return self.rtk.get_last_battle_response(self.account_id)
                except Exception:
                    return {}
            time.sleep(poll_interval)
        logger.warning(f"Battle did not end within {timeout}s")
        return {}

    # --- Game data ---

    def get_resources(self) -> dict:
        return self.rtk.get_resources(self.account_id)

    def get_heroes(self, with_stats=False) -> list:
        return self.rtk.get_heroes(self.account_id, snapshot=with_stats)

    def get_artifacts(self) -> list:
        return self.rtk.get_artifacts(self.account_id)

    def get_arena(self) -> dict:
        return self.rtk.get_arena(self.account_id)

    # --- Navigation (state-aware clicks) ---

    def ensure_village(self, timeout=30):
        """Navigate back to village/bastion if not already there."""
        if self.is_on(View.VILLAGE):
            return True

        # Try ESC key first
        pyautogui.hotkey("esc")
        time.sleep(1)
        if self.is_on(View.VILLAGE):
            return True

        # Try the go-back button
        go_back = asset(self.asset_path, "goBack.png")
        attempts = 0
        while attempts < 10 and not self.is_on(View.VILLAGE):
            locate_and_click(go_back, confidence=0.7, sleep_after=2)
            attempts += 1

        return self.is_on(View.VILLAGE)

    def navigate_to(self, target: View, click_image: str, confidence=0.8, timeout=15) -> bool:
        """
        Click an image and verify we arrive at the expected screen.
        Returns True if we reached the target view.
        """
        current = self.current_view()
        image_path = asset(self.asset_path, click_image)

        if locate_and_click(image_path, confidence=confidence, sleep_after=2):
            if self.wait_for_view(target, timeout=timeout):
                logger.info(f"Navigated from {current.value} -> {target.value}")
                return True
            else:
                logger.warning(
                    f"Clicked {click_image} but did not reach {target.value}. "
                    f"Currently on: {self.current_view().value}"
                )
                return False
        else:
            logger.warning(f"Could not find {click_image} on screen.")
            return False

    def click_and_verify(self, x, y, expected_view: View = None, sleep_after=2) -> bool:
        """
        Click at coordinates and optionally verify the expected view.
        If expected_view is None, just clicks and returns True.
        """
        before = self.current_view()
        pyautogui.click(x, y)
        time.sleep(sleep_after)

        if expected_view:
            return self.is_on(expected_view)
        return True

    def smart_click(self, image: str, expected_view: View = None,
                    confidence=0.8, sleep_after=2, max_attempts=3) -> bool:
        """
        Locate and click an image, verify the result via RTK.
        Retries if the expected view isn't reached.
        """
        image_path = asset(self.asset_path, image)
        for attempt in range(max_attempts):
            if locate_and_click(image_path, confidence=confidence, sleep_after=sleep_after):
                if expected_view is None:
                    return True
                if self.is_on(expected_view):
                    return True
                logger.debug(
                    f"Attempt {attempt + 1}: clicked {image} but on "
                    f"{self.current_view().value}, expected {expected_view.value}"
                )
            time.sleep(1)
        return False
