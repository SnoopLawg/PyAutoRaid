"""
Shared base module for PyAutoRaid and DailyQuests.
Provides common utilities for screen automation, game window management,
config handling, and asset path resolution.
"""

import pyautogui
import platform
import tkinter
import logging
import os
import sys
import subprocess
import time
import configparser
import pygetwindow
from screeninfo import get_monitors
from tkinter import messagebox

logger = logging.getLogger(__name__)

# Max retries for while loops to prevent infinite spinning
MAX_RETRIES = 30


def locate_and_click(image_path, confidence=0.8, click=True, sleep_after=2, max_attempts=1):
    """
    Locate an image on screen and optionally click its center.
    Returns the location if found, None otherwise.
    Combines locate + click into a single scan to avoid race conditions.
    """
    for attempt in range(max_attempts):
        location = pyautogui.locateOnScreen(image_path, confidence=confidence)
        if location:
            if click:
                x, y = pyautogui.center(location)
                pyautogui.click(x, y)
                if sleep_after:
                    time.sleep(sleep_after)
            return location
        if max_attempts > 1:
            time.sleep(1)
    return None


def locate_and_click_loop(image_path, confidence=0.8, sleep_after=2, max_retries=MAX_RETRIES):
    """
    Repeatedly locate and click an image until it disappears.
    Returns the number of clicks performed.
    """
    clicks = 0
    retries = 0
    while retries < max_retries:
        location = pyautogui.locateOnScreen(image_path, confidence=confidence)
        if not location:
            break
        x, y = pyautogui.center(location)
        pyautogui.click(x, y)
        clicks += 1
        retries += 1
        if sleep_after:
            time.sleep(sleep_after)
    if retries >= max_retries:
        logger.warning(f"Hit max retries ({max_retries}) clicking {os.path.basename(image_path)}")
    return clicks


def wait_for_image(image_path, confidence=0.8, timeout=120, poll_interval=1):
    """
    Wait for an image to appear on screen.
    Returns the location if found within timeout, None otherwise.
    """
    start = time.time()
    while time.time() - start < timeout:
        location = pyautogui.locateOnScreen(image_path, confidence=confidence)
        if location:
            return location
        time.sleep(poll_interval)
    logger.warning(f"Timed out waiting for {os.path.basename(image_path)} after {timeout}s")
    return None


def asset(base_path, filename):
    """Build a cross-platform asset path."""
    return os.path.join(base_path, filename)


class BaseDaily:
    """
    Shared base class for PyAutoRaid's Daily and DailyQuests' Daily.
    Handles OS check, Raid path detection, asset path resolution,
    game window management, and common navigation methods.
    """

    def __init__(self, master=None):
        self.running = True
        self.master = master
        self.steps = {}
        self.manual_run_triggered = False
        self.width = 0
        self.height = 0

        self.OS = self._check_os()
        self.raidLoc = self._find_raid_path()
        self.asset_path = self._get_asset_path()
        self._folders_for_exe()

        if len(pygetwindow.getWindowsWithTitle("Raid: Shadow Legends")) < 1:
            self.open_raid()
        else:
            self.initiate_raid(False)

        subprocess.run(["taskkill", "/f", "/im", "PlariumPlay.exe"],
                       capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)

    def trigger_manual_run(self, value):
        self.manual_run_triggered = value
        logger.info(f"Manual run triggered: {value}")

    def close_gui(self):
        try:
            if self.master:
                self.master.after(0, self.master.destroy)
                logger.info("GUI closed.")
        except Exception as e:
            logger.error(f"Error in close_gui: {e}")

    # --- OS / path detection ---

    def _check_os(self):
        operating_system = platform.system()
        if operating_system == "Windows":
            self.steps["OS"] = "True"
            return operating_system
        else:
            tkinter.messagebox.showerror(
                "Error",
                "Unrecognized operating system (WINDOWS ONLY)",
            )
            logger.error("This program only works with Windows.")
            sys.exit(1)

    def _find_raid_path(self):
        try:
            appdata_local = os.environ['LOCALAPPDATA']
            for root_dir, dirs, files in os.walk(appdata_local):
                if "Raid.exe" in dirs or "Raid.exe" in files:
                    raidloc = os.path.join(root_dir, "Raid.exe")
                    logger.debug(f"Found Raid.exe at {raidloc}")
                    self.steps["Raid_path"] = "True"
                    return raidloc
            self.steps["Raid_path"] = "False"
            logger.error("Raid.exe was not found.")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error in _find_raid_path: {e}")
            sys.exit(1)

    def _get_asset_path(self):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            while True:
                candidate = os.path.join(current_dir, 'assets')
                if os.path.exists(candidate):
                    self.steps["Asset_path"] = "True"
                    logger.info(f"Assets folder found at {candidate}")
                    return candidate

                parent = os.path.dirname(current_dir)
                if parent == current_dir:
                    self.steps["Asset_path"] = "False"
                    if not self._folders_for_exe():
                        logger.error("Could not find the assets folder.")
                        sys.exit(1)
                    return None
                current_dir = parent
        except Exception as e:
            logger.error(f"Error in _get_asset_path: {e}")
            sys.exit(1)

    def _folders_for_exe(self):
        if getattr(sys, 'frozen', False):
            self.asset_path = os.path.join(sys._MEIPASS, 'assets')
            self.steps["Exe_path"] = "True"
            return True
        self.steps["Exe_path"] = "False"
        return False

    # --- Game window management ---

    def open_raid(self):
        try:
            logger.info("Attempting to open Raid: Shadow Legends.")
            subprocess.Popen([
                os.path.join(os.environ["LOCALAPPDATA"], "PlariumPlay", "PlariumPlay.exe"),
                "--args", "-gameid=101", "-tray-start",
            ])
            self._wait_for_game_window("Raid: Shadow Legends", timeout=100)
        except Exception as e:
            logger.error(f"Error in open_raid: {e}")

    def _wait_for_game_window(self, title, timeout):
        logger.info("Waiting for game window to appear.")
        start_time = time.time()
        while time.time() - start_time < timeout:
            if pyautogui.getWindowsWithTitle(title):
                logger.debug("Game window found.")
                self.steps["Open_raid"] = "True"
                self.initiate_raid(True)
                return
            time.sleep(5)
        self.steps["Open_raid"] = "False"
        logger.error("Raid took too long to open.")
        sys.exit(1)

    def get_screen_info(self):
        try:
            for m in get_monitors():
                self.width = m.width
                self.height = m.height
                if self.width != 1920 or self.height != 1080:
                    tkinter.messagebox.showerror(
                        "Warning",
                        "Your screen resolution is not 1920x1080. This may cause issues.",
                    )
                    logger.warning("Screen resolution is not 1920x1080.")
                if m.is_primary:
                    center_width = int((self.width / 2) - 450)
                    center_height = int((self.height / 2) - 300)
                    logger.info(f"Screen info: {self.width}x{self.height}")
                    return (center_width, center_height)
        except Exception as e:
            logger.error(f"Error in get_screen_info: {e}")

    def window_sizing_centering(self):
        try:
            center = self.get_screen_info()
            win_list = pygetwindow.getWindowsWithTitle("Raid: Shadow Legends")
            if win_list:
                win = win_list[0]
                win.minimize()
                win.restore()
                win.size = (900, 600)
                win.moveTo(center[0], center[1])
                logger.info("Game window resized and centered.")
            else:
                logger.warning("No Raid window found.")
        except Exception as e:
            logger.error(f"Error in window_sizing_centering: {e}")

    def initiate_raid(self, not_open):
        try:
            self.window_sizing_centering()
            exit_add_image = asset(self.asset_path, "exitAdd.png")
            if not_open:
                wait_for_image(exit_add_image, confidence=0.7)
            self.back_to_bastion()
            self.delete_popup()
            self.steps["Initiate_raid"] = "True"
            logger.info("Raid game initiated.")
        except Exception as e:
            logger.error(f"Error in initiate_raid: {e}")

    # --- Common navigation ---

    def delete_popup(self):
        """Close popup ads. Has max attempt limit to prevent infinite loops."""
        logger.info("Attempting to close any pop-up ads.")
        exit_add_image = asset(self.asset_path, "exitAdd.png")
        clicks = locate_and_click_loop(exit_add_image, confidence=0.8, sleep_after=4, max_retries=5)
        if clicks:
            logger.debug(f"Closed {clicks} pop-up ad(s).")
        else:
            logger.info("No pop-up ads found.")

    def back_to_bastion(self):
        """Navigate back to bastion with retry limit and lightning offer handling."""
        try:
            logger.info("Navigating back to Bastion.")
            go_back_image = asset(self.asset_path, "goBack.png")
            lightning_offer_image = asset(self.asset_path, "lightningOfferText.png")
            close_lo_image = asset(self.asset_path, "closeLO.png")

            max_attempts = 10
            attempts = 0
            while attempts < max_attempts:
                location = pyautogui.locateOnScreen(go_back_image, confidence=0.7)
                if not location:
                    break
                x, y = pyautogui.center(location)
                pyautogui.click(x, y)
                time.sleep(2)
                attempts += 1

                # Handle lightning offer popup
                if pyautogui.locateOnScreen(lightning_offer_image, confidence=0.7):
                    locate_and_click(close_lo_image, confidence=0.7, sleep_after=2)

            if attempts >= max_attempts:
                logger.warning("Hit max attempts navigating back to Bastion.")
            else:
                logger.info("Successfully navigated back to Bastion.")
        except Exception as e:
            logger.error(f"Error in back_to_bastion: {e}")

    @staticmethod
    def kill_processes(*process_names):
        """Kill processes by name using taskkill, safely without shell=True."""
        for name in process_names:
            subprocess.run(
                ["taskkill", "/f", "/im", name],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
