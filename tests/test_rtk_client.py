"""Tests for RTK client and game state logic (mocked, no real RTK needed)."""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock, PropertyMock
from threading import Event

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Modules'))


class TestRTKClient(unittest.TestCase):
    """Test RTKClient with mocked WebSocket."""

    @patch('rtk_client.websocket')
    def test_connect_success(self, mock_ws_module):
        from rtk_client import RTKClient

        client = RTKClient(timeout=1)
        # Simulate on_open being called immediately
        mock_app = MagicMock()
        mock_ws_module.WebSocketApp.return_value = mock_app

        def fake_run_forever():
            # Simulate connection opening
            on_open = mock_ws_module.WebSocketApp.call_args[1]['on_open']
            on_open(mock_app)

        mock_app.run_forever.side_effect = fake_run_forever
        client.connect()
        self.assertTrue(client.is_connected)
        client.close()

    @patch('rtk_client.websocket')
    def test_connect_timeout(self, mock_ws_module):
        from rtk_client import RTKClient, RTKConnectionError

        mock_app = MagicMock()
        mock_ws_module.WebSocketApp.return_value = mock_app
        mock_app.run_forever.return_value = None  # Never calls on_open

        client = RTKClient(timeout=0.1)
        with self.assertRaises(RTKConnectionError):
            client.connect()

    def test_is_connected_default_false(self):
        from rtk_client import RTKClient
        client = RTKClient()
        self.assertFalse(client.is_connected)

    @patch('rtk_client.websocket')
    def test_call_not_connected(self, mock_ws_module):
        from rtk_client import RTKClient, RTKConnectionError
        client = RTKClient()
        with self.assertRaises(RTKConnectionError):
            client._call("account-api", "getAccounts")


class TestGameStateViews(unittest.TestCase):
    """Test the View enum and game state logic."""

    def test_view_from_key_known(self):
        from game_state import View
        self.assertEqual(View.from_key("Village"), View.VILLAGE)
        self.assertEqual(View.from_key("BattleHUD"), View.BATTLE_HUD)
        self.assertEqual(View.from_key("ArenaDialog"), View.ARENA_DIALOG)

    def test_view_from_key_unknown(self):
        from game_state import View
        self.assertEqual(View.from_key("SomeNewScreen"), View.UNKNOWN)

    def test_view_from_key_all_members(self):
        from game_state import View
        # Every defined view should round-trip
        for member in View:
            if member != View.UNKNOWN:
                self.assertEqual(View.from_key(member.value), member)


class TestGameState(unittest.TestCase):
    """Test GameState methods with mocked RTK."""

    def _make_game_state(self):
        from game_state import GameState
        mock_rtk = MagicMock()
        mock_rtk.is_connected = True
        gs = GameState(mock_rtk, "/fake/assets")
        gs.account_id = "test-account-123"
        return gs, mock_rtk

    def test_current_view(self):
        from game_state import View
        gs, mock_rtk = self._make_game_state()
        mock_rtk.get_current_view.return_value = {"viewId": 1, "viewKey": "Village"}
        self.assertEqual(gs.current_view(), View.VILLAGE)

    def test_is_on(self):
        from game_state import View
        gs, mock_rtk = self._make_game_state()
        mock_rtk.get_current_view.return_value = {"viewId": 1, "viewKey": "Village"}
        self.assertTrue(gs.is_on(View.VILLAGE))
        self.assertFalse(gs.is_on(View.ARENA_DIALOG))

    def test_wait_for_view_immediate(self):
        from game_state import View
        gs, mock_rtk = self._make_game_state()
        mock_rtk.get_current_view.return_value = {"viewId": 1, "viewKey": "Village"}
        self.assertTrue(gs.wait_for_view(View.VILLAGE, timeout=1))

    def test_wait_for_view_timeout(self):
        from game_state import View
        gs, mock_rtk = self._make_game_state()
        mock_rtk.get_current_view.return_value = {"viewId": 99, "viewKey": "BattleHUD"}
        self.assertFalse(gs.wait_for_view(View.VILLAGE, timeout=0.5, poll_interval=0.1))

    def test_wait_for_view_change(self):
        from game_state import View
        gs, mock_rtk = self._make_game_state()
        mock_rtk.get_current_view.side_effect = [
            {"viewId": 1, "viewKey": "Village"},  # initial
            {"viewId": 1, "viewKey": "Village"},  # still same
            {"viewId": 2, "viewKey": "ArenaDialog"},  # changed!
        ]
        result = gs.wait_for_view_change(View.VILLAGE, timeout=5, poll_interval=0.1)
        self.assertEqual(result, View.ARENA_DIALOG)

    def test_get_resources(self):
        gs, mock_rtk = self._make_game_state()
        mock_rtk.get_resources.return_value = {"silver": 1000000, "gems": 50}
        resources = gs.get_resources()
        self.assertEqual(resources["gems"], 50)
        mock_rtk.get_resources.assert_called_once_with("test-account-123")

    def test_get_heroes(self):
        gs, mock_rtk = self._make_game_state()
        mock_rtk.get_heroes.return_value = [{"id": 1, "name": "Kael"}]
        heroes = gs.get_heroes()
        self.assertEqual(len(heroes), 1)
        mock_rtk.get_heroes.assert_called_once_with("test-account-123", snapshot=False)


class TestHybridControllerLogic(unittest.TestCase):
    """Test controller task logic without real game/RTK."""

    @patch('hybrid_controller.RTKClient')
    def test_connect_failure(self, mock_rtk_cls):
        from hybrid_controller import HybridController
        from rtk_client import RTKConnectionError

        mock_rtk = mock_rtk_cls.return_value
        mock_rtk.connect.side_effect = RTKConnectionError("No RTK")

        controller = HybridController()
        controller.rtk = mock_rtk
        result = controller.connect()
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
