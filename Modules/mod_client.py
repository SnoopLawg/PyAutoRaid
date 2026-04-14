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

    def sell_artifacts(self, ids_str):
        """Sell artifacts by ID via direct SellArtifactsCmd.

        Args:
            ids_str: Comma-separated artifact IDs (e.g. "28018,28110")

        Returns:
            dict with sold count, guard info, and exec status
        """
        return self._get(f"/sell?ids={ids_str}")

    def get_artifacts(self, max_rank=6, max_rarity=5):
        """Get all artifacts, optionally filtered by rank and rarity.

        Args:
            max_rank: Maximum rank to include (1-6)
            max_rarity: Maximum rarity to include (0=common, 1=uncommon, etc.)

        Returns:
            dict with lastId, count, and artifacts list
        """
        return self._get(f"/artifacts?maxrank={max_rank}&maxrarity={max_rarity}")

    # === Artifact Equipment API ===

    def equip_artifact(self, hero_id, artifact_id):
        """Equip an artifact to a hero via game command.

        Automatically handles swap if the slot is already occupied.

        Args:
            hero_id: Target hero ID
            artifact_id: Artifact ID to equip

        Returns:
            dict with ok/error status
        """
        return self._get(f"/equip?hero_id={hero_id}&artifact_id={artifact_id}")

    def unequip_artifact(self, hero_id, artifact_id):
        """Remove an artifact from a hero.

        Args:
            hero_id: Hero ID to remove from
            artifact_id: Artifact ID to remove

        Returns:
            dict with ok/error status
        """
        return self._get(f"/unequip?hero_id={hero_id}&artifact_id={artifact_id}")

    def swap_artifact(self, hero_id, from_id, to_id, owner_id=None):
        """Swap an equipped artifact with another.

        Args:
            hero_id: Target hero ID
            from_id: Currently equipped artifact ID to replace
            to_id: New artifact ID to equip
            owner_id: Hero who currently owns to_id (None = vault or same hero)

        Returns:
            dict with ok/error status
        """
        url = f"/swap?hero_id={hero_id}&from_id={from_id}&to_id={to_id}"
        if owner_id is not None:
            url += f"&owner_id={owner_id}"
        return self._get(url)

    def bulk_equip(self, hero_id, artifact_ids):
        """Equip multiple artifacts to a hero in one command.

        Handles swaps automatically for occupied slots.

        Args:
            hero_id: Target hero ID
            artifact_ids: List of artifact IDs to equip

        Returns:
            dict with bulk result and count
        """
        ids_json = urllib.parse.quote(str(artifact_ids), safe='')
        return self._get(f"/bulk-equip?hero_id={hero_id}&artifacts={ids_json}")

    def set_auto_dismiss(self, enabled):
        """Enable/disable automatic overlay dismissal."""
        val = "on" if enabled else "off"
        return self._get(f"/overlays?auto={val}")

    def get_shop_items(self):
        """Get Magic Market items from memory."""
        return self._get("/shopitems")

    def open_market(self):
        """Open the Market screen via building click binding.

        Must disable auto-dismiss first (popup is part of navigation flow).
        Tries multiple path variants for the Market building.
        """
        paths = [
            "VillageView/BuildingModels/OlympianScene_h/"
            "Sector_Olympian(Clone)/Buildings_group/"
            "Market_group/UI_Elements",
        ]
        # Also try finding the Market via search
        try:
            found = self.find_objects("Market_group")
            if found and found.get("results"):
                for r in found["results"]:
                    if "UI_Elements" not in r:
                        paths.append(r + "/UI_Elements")
                    else:
                        paths.append(r)
        except Exception:
            pass

        for path in paths:
            result = self.click_path(path)
            if result:
                return True
        return False

    def buy_market_item(self, item_id):
        """Buy a Market item by clicking its price button then the Buy button.

        Args:
            item_id: Item slot index (0-11)

        Returns:
            True if purchase succeeded, False otherwise
        """
        import time
        # Click the item's price button
        price_path = (f"UIManager/Canvas (Ui Root)/Dialogs/"
                      f"[DV] ShopAggregatorDialog/Workspace/Content/"
                      f"TabsContent/Market_h/InnerContext/"
                      f"Scroll View/Viewport/Items/{item_id}/Bottom/Price_h")
        if not self.click_path(price_path):
            return False

        time.sleep(3)

        # Find and click the Buy button on the overlay
        buy_path = ("UIManager/Canvas (Ui Root)/OverlayDialogs/"
                    "[OV] HeroTypeInfoOverlay/Workspace/Content/BuyButton_h")
        return self.click_path(buy_path)

    # === Context-based MVVM calls (bypasses broken button clicks) ===

    def get_view_contexts(self, path=None):
        """Get MVVM contexts on active dialogs or a specific path."""
        if path:
            encoded = urllib.parse.quote(path, safe='')
            return self._get(f"/view-context?path={encoded}")
        return self._get("/view-context")

    def context_call(self, path, method, arg=None):
        """Call a method on the MVVM context of a view/dialog.

        This bypasses the MVVM CommandBinding system entirely, calling
        methods directly on the context instance via IL2CPP.

        Args:
            path: GameObject path to search for BaseView with context
            method: Method name to invoke on the context
            arg: Optional string argument

        Returns:
            dict with invoked method info, or error
        """
        encoded_path = urllib.parse.quote(path, safe='')
        encoded_method = urllib.parse.quote(method, safe='')
        url = f"/context-call?path={encoded_path}&method={encoded_method}"
        if arg:
            url += f"&arg={urllib.parse.quote(str(arg), safe='')}"
        result = self._get(url)
        if "error" in result:
            logger.warning(f"Context call failed: {result['error']}")
            return None
        logger.info(f"Context call: {method} on {result.get('on_context', '?')}")
        return result

    def arena_start_fight(self, opponent_index):
        """Start arena fight against opponent by index (0-9).

        Uses context-call to invoke OnStartClick on the opponent's
        CurrentOpponentContext, bypassing broken MVVM button clicks.
        """
        path = (f"UIManager/Canvas (Ui Root)/Dialogs/[DV] ArenaDialog/"
                f"Workspace/Content/Tabs/Battle_h/ArenaBattleTab(Clone)/"
                f"Content/Opponents/Viewport/Content/{opponent_index}")
        return self.context_call(path, "OnStartClick")

    def close_dialog(self, dialog_path=None):
        """Close a dialog via its context's Close method.

        Args:
            dialog_path: Full path to dialog, or None to close first active dialog
        """
        if dialog_path is None:
            # Find first active dialog
            try:
                data = self.get_view_contexts()
                for d in data.get("dialogs", []):
                    if d.get("context_class"):
                        dialog_path = f"UIManager/Canvas (Ui Root)/Dialogs/{d['dialog']}"
                        break
            except Exception:
                return None
        if dialog_path:
            return self.context_call(dialog_path, "Close")
        return None

    def cb_start_battle(self):
        """Start CB battle via context-call on AllianceEnemiesBattlesContext.OnStartClick.

        Must be at the CB dialog with a difficulty selected first.
        """
        path = ("UIManager/Canvas (Ui Root)/Dialogs/"
                "[DV] AllianceEnemiesDialog/Workspace/Content/RightPanel")
        return self.context_call(path, "OnStartClick")

    def navigate(self, target):
        """Navigate to a game screen via IL2CPP direct invocation.

        Args:
            target: One of 'arena', 'cb', 'campaign', 'dungeon', etc.
        """
        try:
            result = self._get(f"/navigate?target={target}")
            if result and "navigated" in result:
                return True
        except Exception:
            pass
        return False

    def arena_start_battle(self):
        """Click Start Battle on the hero selection screen via context-call.

        Must be at ArenaHeroesSelectionDialog.
        Uses StartBattle on HeroesSelectionArenaDialogContext.
        """
        path = ("UIManager/Canvas (Ui Root)/Dialogs/"
                "[DV] ArenaHeroesSelectionDialog")
        return self.context_call(path, "StartBattle")

    def dismiss_battle_finish(self):
        """Dismiss the battle finish/results screen via context Close.

        Works for arena, CB, dungeon battle finish dialogs.
        Returns the dialog that was closed, or None.
        """
        try:
            data = self.get_view_contexts()
            for d in data.get("dialogs", []):
                if "BattleFinish" in d.get("dialog", ""):
                    path = f"UIManager/Canvas (Ui Root)/Dialogs/{d['dialog']}"
                    return self.context_call(path, "Close")
        except Exception:
            pass
        return None
