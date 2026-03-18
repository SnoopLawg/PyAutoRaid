"""
Win32 background input module.

Sends mouse clicks and key presses directly to the Raid window handle
via PostMessage/SendMessage. Does NOT steal focus or move the real mouse.

This replaces pyautogui for action execution, enabling:
- Background operation (game doesn't need to be focused)
- No mouse hijacking
- Works with minimized or obscured windows (if the game accepts it)

Note: Some games/apps ignore PostMessage clicks (they check for hardware input).
Raid: Shadow Legends is a Unity game and may or may not accept synthetic messages.
If PostMessage doesn't work, fall back to SendInput (still better than pyautogui)
or use the pyautogui fallback.
"""

import ctypes
import ctypes.wintypes
import logging
import time
from typing import Optional, Tuple

try:
    import win32api
    import win32con
    import win32gui
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

logger = logging.getLogger(__name__)

# Window message constants
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_CHAR = 0x0102
MK_LBUTTON = 0x0001

# Virtual key codes
VK_ESCAPE = 0x1B
VK_RETURN = 0x0D

# Game window title
RAID_WINDOW_TITLE = "Raid: Shadow Legends"


def _make_lparam(x: int, y: int) -> int:
    """Pack x, y coordinates into an lParam value for window messages."""
    return (y << 16) | (x & 0xFFFF)


class Win32Input:
    """
    Send input to the Raid window without stealing focus.

    Usage:
        inp = Win32Input()
        if inp.find_window():
            inp.click(583, 595)
            inp.press_key(VK_ESCAPE)
    """

    def __init__(self):
        self.hwnd = None
        self._use_post = True  # PostMessage (async) vs SendMessage (sync)

    def find_window(self) -> bool:
        """Find the Raid: Shadow Legends window handle."""
        if not HAS_WIN32:
            logger.error("pywin32 not installed. Run: pip install pywin32")
            return False

        self.hwnd = win32gui.FindWindow(None, RAID_WINDOW_TITLE)
        if not self.hwnd:
            logger.error(f"Window '{RAID_WINDOW_TITLE}' not found.")
            return False

        logger.info(f"Found Raid window: hwnd={self.hwnd}")
        return True

    def is_valid(self) -> bool:
        """Check if the stored window handle is still valid."""
        if not self.hwnd or not HAS_WIN32:
            return False
        return win32gui.IsWindow(self.hwnd)

    def _send(self, msg, wparam, lparam):
        """Send a message to the game window."""
        if not self.is_valid():
            if not self.find_window():
                return False
        try:
            if self._use_post:
                win32api.PostMessage(self.hwnd, msg, wparam, lparam)
            else:
                win32api.SendMessage(self.hwnd, msg, wparam, lparam)
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    # --- Mouse ---

    def click(self, x: int, y: int, sleep_after: float = 0.1):
        """
        Send a left click at (x, y) relative to the game window's client area.
        Does NOT move the real mouse or steal focus.
        """
        lparam = _make_lparam(x, y)
        self._send(WM_LBUTTONDOWN, MK_LBUTTON, lparam)
        time.sleep(0.05)
        self._send(WM_LBUTTONUP, 0, lparam)
        if sleep_after:
            time.sleep(sleep_after)
        logger.debug(f"Click at ({x}, {y})")

    def double_click(self, x: int, y: int, interval: float = 0.1, sleep_after: float = 0.1):
        """Send a double left click."""
        self.click(x, y, sleep_after=interval)
        self.click(x, y, sleep_after=sleep_after)

    def right_click(self, x: int, y: int, sleep_after: float = 0.1):
        """Send a right click."""
        lparam = _make_lparam(x, y)
        self._send(WM_RBUTTONDOWN, MK_LBUTTON, lparam)
        time.sleep(0.05)
        self._send(WM_RBUTTONUP, 0, lparam)
        if sleep_after:
            time.sleep(sleep_after)

    # --- Keyboard ---

    def press_key(self, vk_code: int, sleep_after: float = 0.1):
        """
        Send a key press (down + up) to the game window.
        Uses virtual key codes (e.g., VK_ESCAPE = 0x1B).
        """
        self._send(WM_KEYDOWN, vk_code, 0)
        time.sleep(0.05)
        self._send(WM_KEYUP, vk_code, 0)
        if sleep_after:
            time.sleep(sleep_after)
        logger.debug(f"Key press: 0x{vk_code:02X}")

    def press_escape(self, sleep_after: float = 0.5):
        """Send ESC key."""
        self.press_key(VK_ESCAPE, sleep_after)

    def press_char(self, char: str, sleep_after: float = 0.1):
        """Send a character key (e.g., 'i' for inbox, 'c' for champions)."""
        self._send(WM_CHAR, ord(char), 0)
        if sleep_after:
            time.sleep(sleep_after)
        logger.debug(f"Char press: '{char}'")

    # --- Window info ---

    def get_window_rect(self) -> Optional[Tuple[int, int, int, int]]:
        """Get the game window's screen rectangle (left, top, right, bottom)."""
        if not self.is_valid():
            return None
        try:
            return win32gui.GetWindowRect(self.hwnd)
        except Exception:
            return None

    def get_client_rect(self) -> Optional[Tuple[int, int, int, int]]:
        """Get the game window's client area rectangle."""
        if not self.is_valid():
            return None
        try:
            return win32gui.GetClientRect(self.hwnd)
        except Exception:
            return None

    def bring_to_front(self):
        """Bring the game window to the foreground (if you want to)."""
        if self.is_valid():
            try:
                win32gui.SetForegroundWindow(self.hwnd)
            except Exception as e:
                logger.error(f"Could not bring window to front: {e}")


class InputBackend:
    """
    Abstraction layer that tries Win32 first, falls back to pyautogui.

    This lets the hybrid controller work on any setup:
    - If the game accepts PostMessage → background mode, no mouse hijack
    - If not → falls back to pyautogui (original behavior)
    """

    def __init__(self, prefer_background=True):
        self._win32 = None
        self._use_win32 = False

        if prefer_background and HAS_WIN32:
            self._win32 = Win32Input()
            if self._win32.find_window():
                self._use_win32 = True
                logger.info("Using Win32 background input.")
            else:
                logger.warning("Win32 window not found, falling back to pyautogui.")
        else:
            logger.info("Using pyautogui for input.")

    @property
    def is_background(self) -> bool:
        """True if we're using background input (no mouse hijack)."""
        return self._use_win32

    def click(self, x: int, y: int, sleep_after: float = 0.1):
        """Click at coordinates."""
        if self._use_win32:
            self._win32.click(x, y, sleep_after)
        else:
            import pyautogui
            pyautogui.click(x, y)
            if sleep_after:
                time.sleep(sleep_after)

    def double_click(self, x: int, y: int, interval: float = 0.1, sleep_after: float = 0.1):
        """Double click at coordinates."""
        if self._use_win32:
            self._win32.double_click(x, y, interval, sleep_after)
        else:
            import pyautogui
            pyautogui.doubleClick(x, y, interval=interval)
            if sleep_after:
                time.sleep(sleep_after)

    def press_escape(self, sleep_after: float = 0.5):
        """Press ESC."""
        if self._use_win32:
            self._win32.press_escape(sleep_after)
        else:
            import pyautogui
            pyautogui.hotkey("esc")
            if sleep_after:
                time.sleep(sleep_after)

    def press_char(self, char: str, sleep_after: float = 0.1):
        """Press a character key."""
        if self._use_win32:
            self._win32.press_char(char, sleep_after)
        else:
            import pyautogui
            pyautogui.hotkey(char)
            if sleep_after:
                time.sleep(sleep_after)

    def drag(self, x: int, y: int, dx: int, dy: int, duration: float = 1.0):
        """
        Drag from (x, y) by (dx, dy).
        Note: Win32 PostMessage drag is unreliable for most games.
        Falls back to pyautogui for drags.
        """
        import pyautogui
        pyautogui.click(x, y)
        pyautogui.drag(dx, dy, duration=duration)
