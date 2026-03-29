"""
HTTP client for the RaidAutomation MelonLoader mod.

Provides Python access to the in-game mod API for direct UI control.
Falls back gracefully if the mod isn't loaded.

Usage:
    client = ModClient()
    if client.available:
        client.click_button("ShopButton")
        buttons = client.get_buttons()
"""

import logging
import json
import urllib.request
import urllib.parse
import urllib.error

logger = logging.getLogger(__name__)

MOD_API_URL = "http://localhost:6790"
TIMEOUT = 5

# Village HUD button paths (discovered via /buttons endpoint)
VILLAGE_BUTTONS = {
    "shop":       "UIManager/Canvas (Ui Root)/Dialogs/[DV] VillageHUD/Workspace/Bottom/LeftButtonLayout 1/ShopButton",
    "quests":     "UIManager/Canvas (Ui Root)/Dialogs/[DV] VillageHUD/Workspace/Bottom/LeftButtonLayout 1/QuestButton",
    "battle":     "UIManager/Canvas (Ui Root)/Dialogs/[DV] VillageHUD/Workspace/Bottom/RightButtonLayout 2/WorldMapButton",
    "clan":       "UIManager/Canvas (Ui Root)/Dialogs/[DV] VillageHUD/Workspace/Bottom/RightButtonLayout 2/AllianceButton",
    "heroes":     "UIManager/Canvas (Ui Root)/Dialogs/[DV] VillageHUD/Workspace/Bottom/RightButtonLayout 2/HeroesButton",
    "inbox":      "UIManager/Canvas (Ui Root)/Dialogs/[DV] VillageHUD/Workspace/Top/TopButtonLayout/InboxButton",
    "challenges": "UIManager/Canvas (Ui Root)/Dialogs/[DV] VillageHUD/Workspace/Bottom/LeftButtonLayout 1/ChallengesButton_h",
    "collection": "UIManager/Canvas (Ui Root)/Dialogs/[DV] VillageHUD/Workspace/Bottom/RightButtonLayout 2/CollectionButton",
}


class ModClient:
    """HTTP client for the in-game RaidAutomation mod API."""

    def __init__(self, base_url=MOD_API_URL, timeout=TIMEOUT):
        self.base_url = base_url
        self.timeout = timeout
        self._available = None

    @property
    def available(self):
        """Check if the mod API is reachable."""
        if self._available is None:
            try:
                self._get("/status")
                self._available = True
                logger.info("Mod API available on port 6790")
            except Exception:
                self._available = False
                logger.info("Mod API not available — using fallback")
        return self._available

    def _get(self, endpoint):
        """HTTP GET and return parsed JSON."""
        url = self.base_url + endpoint
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode())

    def _post(self, endpoint):
        """HTTP POST (same as GET for our simple API)."""
        return self._get(endpoint)

    # === Public API ===

    def get_status(self):
        """Get mod status and current scene."""
        return self._get("/status")

    def get_buttons(self):
        """Get all active interactable buttons with paths."""
        return self._get("/buttons")

    def click_path(self, game_object_path):
        """Click a button by its full GameObject path."""
        encoded = urllib.parse.quote(game_object_path, safe='')
        result = self._get(f"/click?path={encoded}")
        if "error" in result:
            logger.warning(f"Click failed: {result['error']}")
            return False
        logger.info(f"Mod click: {game_object_path.split('/')[-1]}")
        return True

    def click_button(self, name):
        """Click a named village button (shop, battle, clan, quests, inbox, etc.)."""
        path = VILLAGE_BUTTONS.get(name.lower())
        if not path:
            logger.warning(f"Unknown button name: {name}")
            return False
        return self.click_path(path)

    def find_button(self, search):
        """Find a button by partial name match from active buttons."""
        try:
            data = self.get_buttons()
            search_lower = search.lower()
            for btn in data.get("buttons", []):
                if search_lower in btn["path"].lower():
                    return btn["path"]
        except Exception:
            pass
        return None

    def click_found(self, search):
        """Find a button by search term and click it."""
        path = self.find_button(search)
        if path:
            return self.click_path(path)
        logger.warning(f"Button not found: {search}")
        return False

    def find_objects(self, name):
        """Search for GameObjects by name."""
        encoded = urllib.parse.quote(name, safe='')
        return self._get(f"/find?name={encoded}")

    # === Toggle API ===

    def get_toggles(self):
        """Get all active Toggle components with on/off state."""
        return self._get("/toggles")

    def toggle_path(self, game_object_path):
        """Toggle a Toggle component on/off by its full GameObject path."""
        encoded = urllib.parse.quote(game_object_path, safe='')
        result = self._get(f"/toggle?path={encoded}")
        if "error" in result:
            logger.warning(f"Toggle failed: {result['error']}")
            return False
        logger.info(f"Toggled: {game_object_path.split('/')[-1]} -> {result.get('now')}")
        return True

    def find_toggle(self, search):
        """Find a toggle by partial name match."""
        try:
            data = self.get_toggles()
            search_lower = search.lower()
            for tog in data.get("toggles", []):
                if search_lower in tog["path"].lower():
                    return tog
        except Exception:
            pass
        return None

    def set_sell_mode(self, on=True):
        """Enable or disable artifact sell mode in the inventory panel."""
        tog = self.find_toggle("SellMode")
        if not tog:
            return False
        if tog["on"] == on:
            return True
        return self.toggle_path(tog["path"])
