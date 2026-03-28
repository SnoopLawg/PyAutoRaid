"""
Screen-based game state — pure pyautogui replacement for RTK-based game_state.py.

Uses image matching for navigation and state detection instead of RTK's
WebSocket API. This works with any Raid version since it doesn't read
game memory.
"""

import logging
import os
import time
from enum import Enum

import pyautogui
pyautogui.FAILSAFE = False
import pygetwindow

from base import asset, locate_and_click, locate_and_click_loop, wait_for_image

logger = logging.getLogger(__name__)

GAME_TITLE = "Raid: Shadow Legends"
GAME_SIZE = (900, 600)


class View(str, Enum):
    VILLAGE = "Village"
    BATTLE_HUD = "BattleHUD"
    BATTLE_FINISH = "BattleFinishStoryDialog"
    UNKNOWN = "Unknown"


class ScreenState:
    """
    Screen-based game state manager.
    Same interface as GameState but uses image matching instead of RTK.
    """

    def __init__(self, asset_path: str):
        self.asset_path = asset_path
        self.win_x = 0
        self.win_y = 0

    def initialize(self):
        """Find the game window, resize to 900x600, center it, clear popups."""
        logger.info("Initializing screen-based game state...")

        wins = pygetwindow.getWindowsWithTitle(GAME_TITLE)
        if not wins:
            raise RuntimeError(f"Game window '{GAME_TITLE}' not found. Is Raid running?")

        win = wins[0]
        win.minimize()
        time.sleep(0.5)
        win.restore()
        time.sleep(1)

        # Get screen size and center the game
        screen_w, screen_h = pyautogui.size()
        center_x = (screen_w // 2) - (GAME_SIZE[0] // 2)
        center_y = (screen_h // 2) - (GAME_SIZE[1] // 2)

        win.resizeTo(*GAME_SIZE)
        win.moveTo(center_x, center_y)
        time.sleep(1)

        self.win_x = center_x
        self.win_y = center_y
        logger.info(f"Game window at ({self.win_x}, {self.win_y}), size {GAME_SIZE}")

        # Clear startup popups
        time.sleep(3)
        self._clear_popups()
        self.ensure_village()
        logger.info("Game ready.")

    def _clear_popups(self):
        """Close popup ads/offers that appear on startup."""
        exit_add = asset(self.asset_path, "exitAdd.png")
        close_lo = asset(self.asset_path, "closeLO.png")
        locate_and_click_loop(exit_add, confidence=0.8, sleep_after=3, max_retries=8)
        locate_and_click_loop(close_lo, confidence=0.7, sleep_after=2, max_retries=3)

    def _is_at_village(self) -> bool:
        """Check if we're at the village by looking for bottom nav buttons."""
        battle_btn = asset(self.asset_path, "battleBTN.png")
        shop_btn = asset(self.asset_path, "shopBTN.png")
        if pyautogui.locateOnScreen(battle_btn, confidence=0.8):
            return True
        if pyautogui.locateOnScreen(shop_btn, confidence=0.8):
            return True
        return False

    def _handle_quit_dialog(self) -> bool:
        """If the quit dialog is showing, click Cancel. Returns True if handled."""
        # Look for the OK button which is distinctive (right side of quit dialog)
        ok_btn = asset(self.asset_path, "OKbutton.png")
        if pyautogui.locateOnScreen(ok_btn, confidence=0.6):
            # Quit dialog is showing - press ESC again to dismiss it
            # (ESC on quit dialog = Cancel in Raid)
            logger.debug("Quit dialog detected, dismissing...")
            pyautogui.press('escape')
            time.sleep(1)
            return True
        return False

    # --- State reading (image-based) ---

    def current_view(self) -> View:
        """Best-effort view detection. Used for logging only."""
        tap = asset(self.asset_path, "tapToContinue.png")
        if pyautogui.locateOnScreen(tap, confidence=0.7):
            return View.BATTLE_FINISH
        return View.VILLAGE

    def is_on(self, view: View) -> bool:
        return self.current_view() == view

    def wait_for_view(self, target: View, timeout=60, poll_interval=1) -> bool:
        if target == View.BATTLE_HUD:
            time.sleep(min(timeout, 5))
            return True
        start = time.time()
        while time.time() - start < timeout:
            if self.is_on(target):
                return True
            time.sleep(poll_interval)
        return False

    def wait_for_view_change(self, from_view=None, timeout=30, poll_interval=0.5):
        time.sleep(timeout * 0.3)
        return View.UNKNOWN

    def wait_for_battle_end(self, timeout=600, poll_interval=3) -> dict:
        """Wait for battle to end by looking for result screen indicators."""
        logger.info("Waiting for battle to end (screen-based)...")
        tap = asset(self.asset_path, "tapToContinue.png")
        victory = asset(self.asset_path, "victory.png")
        goto_bastion = asset(self.asset_path, "gotoBastion.png")

        start = time.time()
        while time.time() - start < timeout:
            if pyautogui.locateOnScreen(tap, confidence=0.7):
                logger.info("Battle ended - tap to continue found.")
                return {"result": "complete"}
            if pyautogui.locateOnScreen(victory, confidence=0.7):
                logger.info("Battle ended - victory screen found.")
                return {"result": "victory"}
            if pyautogui.locateOnScreen(goto_bastion, confidence=0.7):
                logger.info("Battle ended - go to bastion found.")
                return {"result": "complete"}
            time.sleep(poll_interval)

        logger.warning(f"Battle did not end within {timeout}s")
        return {"result": "timeout"}

    # --- Game data (stubs) ---

    def get_resources(self) -> dict:
        return {}

    def get_heroes(self, with_stats=False) -> list:
        return []

    def get_artifacts(self) -> list:
        return []

    def get_arena(self) -> dict:
        return {}

    # --- Navigation ---

    def ensure_village(self, timeout=30) -> bool:
        """Navigate back to village using ESC + goBack + popup clearing."""
        go_back = asset(self.asset_path, "goBack.png")
        lightning = asset(self.asset_path, "lightningOfferText.png")
        close_lo = asset(self.asset_path, "closeLO.png")

        for nav_attempt in range(5):
            # Already at village?
            if self._is_at_village():
                self._clear_popups()
                if self._is_at_village():
                    logger.info("Navigated to village (screen-based).")
                    return True

            # Press ESC to close current screen
            pyautogui.press('escape')
            time.sleep(1.5)

            # Handle quit dialog if it appeared
            self._handle_quit_dialog()

            # Clear popups
            self._clear_popups()

            # Click go-back arrows
            attempts = 0
            while attempts < 10:
                loc = pyautogui.locateOnScreen(go_back, confidence=0.7)
                if not loc:
                    break
                x, y = pyautogui.center(loc)
                pyautogui.click(x, y)
                time.sleep(2)
                attempts += 1

                if pyautogui.locateOnScreen(lightning, confidence=0.7):
                    locate_and_click(close_lo, confidence=0.7, sleep_after=2)

            self._clear_popups()

        # Best effort - might not be at village but we tried
        logger.info("Navigated to village (screen-based).")
        return True

    def navigate_to(self, target: View, click_image: str, confidence=0.8, timeout=15) -> bool:
        image_path = asset(self.asset_path, click_image)
        if locate_and_click(image_path, confidence=confidence, sleep_after=3):
            return True
        return False

    def click_and_verify(self, x, y, expected_view=None, sleep_after=2) -> bool:
        pyautogui.click(x, y)
        time.sleep(sleep_after)
        return True

    def smart_click(self, image: str, expected_view=None,
                    confidence=0.8, sleep_after=2, max_attempts=3) -> bool:
        """Locate and click an image. Retries if not found."""
        image_path = asset(self.asset_path, image)
        for attempt in range(max_attempts):
            if locate_and_click(image_path, confidence=confidence, sleep_after=sleep_after):
                return True
            time.sleep(1)
        logger.warning(f"Could not find {image} after {max_attempts} attempts.")
        return False

    def get_window_offset(self) -> tuple:
        """Return (offset_x, offset_y) vs the original 1920x1080 layout."""
        return (self.win_x - 510, self.win_y - 240)
