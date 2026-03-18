"""
Wrapper around Raid Toolkit SDK's WebSocket API.

Requires RTK to be installed and running on the same Windows machine as Raid.
Connects to ws://localhost:9090 and provides typed access to game state.

Install RTK: https://raidtoolkit.com/pages/installation/
"""

import asyncio
import json
import logging
import uuid
from threading import Thread, Event
from typing import Optional

import websocket

logger = logging.getLogger(__name__)


class RTKConnectionError(Exception):
    """Raised when unable to connect to Raid Toolkit."""
    pass


class RTKApiError(Exception):
    """Raised when an RTK API call fails."""
    pass


class RTKClient:
    """
    Client for the Raid Toolkit WebSocket API.

    Usage:
        client = RTKClient()
        client.connect()

        account_id = client.get_first_account_id()
        view = client.get_current_view(account_id)
        heroes = client.get_heroes(account_id)

        client.close()
    """

    def __init__(self, endpoint="ws://localhost:9090", timeout=10):
        self.endpoint = endpoint
        self.timeout = timeout
        self._ws = None
        self._worker = None
        self._connected = Event()
        self._promises = {}
        self._events = {}

    # --- Connection ---

    def connect(self):
        """Connect to RTK WebSocket. Blocks until connected or timeout."""
        self._connected.clear()
        self._ws = websocket.WebSocketApp(
            self.endpoint,
            on_message=self._on_message,
            on_error=self._on_error,
            on_open=self._on_open,
            on_close=self._on_close,
        )
        self._worker = Thread(target=self._ws.run_forever, daemon=True)
        self._worker.start()

        if not self._connected.wait(timeout=self.timeout):
            raise RTKConnectionError(
                f"Could not connect to RTK at {self.endpoint}. "
                "Is Raid Toolkit installed and running?"
            )
        logger.info(f"Connected to RTK at {self.endpoint}")

    def close(self):
        """Close the WebSocket connection."""
        if self._ws:
            self._ws.close()
        logger.info("RTK connection closed.")

    @property
    def is_connected(self):
        return self._connected.is_set()

    # --- Synchronous API calls ---

    def _call(self, api_name, method_name, args=None):
        """Make a synchronous API call to RTK. Returns the result."""
        if not self.is_connected:
            raise RTKConnectionError("Not connected to RTK.")

        promise_id = str(uuid.uuid4())
        result_event = Event()
        self._promises[promise_id] = {"event": result_event, "result": None, "error": None}

        payload = json.dumps([
            api_name, "call", {
                "promiseId": promise_id,
                "methodName": method_name,
                "args": args or [],
            }
        ])
        self._ws.send(payload)

        if not result_event.wait(timeout=self.timeout):
            del self._promises[promise_id]
            raise RTKApiError(f"Timeout calling {api_name}.{method_name}")

        promise = self._promises.pop(promise_id)
        if promise["error"]:
            raise RTKApiError(f"{api_name}.{method_name} failed: {promise['error']}")
        return promise["result"]

    # --- Account API ---

    def get_accounts(self):
        """Get all known account info."""
        return self._call("account-api", "getAccounts")

    def get_first_account_id(self):
        """Convenience: get the first account's ID."""
        accounts = self.get_accounts()
        if not accounts:
            raise RTKApiError("No accounts found. Is the game running?")
        return accounts[0]["id"]

    def get_account_dump(self, account_id):
        """Full account dump in RaidExtractor format."""
        return self._call("account-api", "getAccountDump", [account_id])

    def get_heroes(self, account_id, snapshot=False):
        """Get all heroes. snapshot=True includes computed stats."""
        return self._call("account-api", "getHeroes", [account_id, snapshot])

    def get_hero_by_id(self, account_id, hero_id, snapshot=False):
        """Get a specific hero by ID."""
        return self._call("account-api", "getHeroById", [account_id, hero_id, snapshot])

    def get_artifacts(self, account_id):
        """Get all artifacts."""
        return self._call("account-api", "getArtifacts", [account_id])

    def get_artifact_by_id(self, account_id, artifact_id):
        """Get a specific artifact by ID."""
        return self._call("account-api", "getArtifactById", [account_id, artifact_id])

    def get_resources(self, account_id):
        """Get all resources (shards, silver, gems, energy, etc.)."""
        return self._call("account-api", "getAllResources", [account_id])

    def get_arena(self, account_id):
        """Get arena data (league, points, win/loss, defense teams)."""
        return self._call("account-api", "getArena", [account_id])

    def get_academy(self, account_id):
        """Get academy/guardian data."""
        return self._call("account-api", "getAcademy", [account_id])

    # --- Realtime API ---

    def get_connected_accounts(self):
        """Get accounts from currently running game instances."""
        return self._call("realtime-api", "getConnectedAccounts")

    def get_current_view(self, account_id):
        """
        Get the current screen/view the game is showing.
        Returns dict with 'viewId' (int) and 'viewKey' (str).
        ViewKey examples: 'Village', 'ArenaDialog', 'BattleHUD', etc.
        """
        return self._call("realtime-api", "getCurrentViewInfo", [account_id])

    def get_last_battle_response(self, account_id):
        """Get the last battle result (XP, damage, tournament points, etc.)."""
        return self._call("realtime-api", "getLastBattleResponse", [account_id])

    # --- Static Data API ---

    def get_all_static_data(self):
        """Get all static game data (heroes, skills, artifacts, stages, etc.)."""
        return self._call("static-data", "getAllData")

    def get_hero_data(self):
        """Get all hero type definitions."""
        return self._call("static-data", "getHeroData")

    def get_skill_data(self):
        """Get all skill type definitions."""
        return self._call("static-data", "getSkillData")

    def get_artifact_data(self):
        """Get artifact set kinds and bonuses."""
        return self._call("static-data", "getArtifactData")

    def get_stage_data(self):
        """Get areas, regions, stages (campaign/dungeon maps)."""
        return self._call("static-data", "getStageData")

    def get_arena_data(self):
        """Get arena league definitions."""
        return self._call("static-data", "getArenaData")

    # --- WebSocket handlers ---

    def _on_open(self, ws):
        self._connected.set()

    def _on_message(self, ws, message):
        try:
            msg = json.loads(message)
            if msg[1] == "set-promise":
                data = msg[2]
                promise_id = data["promiseId"]
                if promise_id in self._promises:
                    if data.get("success"):
                        self._promises[promise_id]["result"] = data.get("value")
                    else:
                        self._promises[promise_id]["error"] = data.get("error", "Unknown error")
                    self._promises[promise_id]["event"].set()
        except Exception as e:
            logger.error(f"Error processing RTK message: {e}")

    def _on_error(self, ws, error):
        logger.error(f"RTK WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        self._connected.clear()
        logger.info(f"RTK WebSocket closed: {close_status_code} {close_msg}")
