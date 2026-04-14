"""Tests for AccountIntel — smart decision layer over RTK data."""

import sys
import os
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Modules'))

from account_intel import AccountIntel


class TestResourceChecks(unittest.TestCase):
    """Test resource reading and task readiness."""

    def _make_intel(self, resources=None, heroes=None, arena=None):
        mock_rtk = MagicMock()
        mock_rtk.get_resources.return_value = resources or {}
        mock_rtk.get_heroes.return_value = heroes or []
        mock_rtk.get_arena.return_value = arena or {}
        mock_rtk.get_account_dump.return_value = {}
        intel = AccountIntel(mock_rtk, "test-123")
        intel.refresh()
        return intel

    def test_resources_dict_format(self):
        intel = self._make_intel(resources={
            "energy": 120,
            "silver": 5000000,
            "gems": 200,
            "arenaTokens": 8,
            "clanBossKeys": 2,
        })
        self.assertEqual(intel.energy, 120)
        self.assertEqual(intel.silver, 5000000)
        self.assertEqual(intel.gems, 200)
        self.assertEqual(intel.arena_tokens, 8)
        self.assertEqual(intel.cb_keys, 2)

    def test_resources_list_format(self):
        intel = self._make_intel(resources=[
            {"type": "energy", "amount": 80},
            {"type": "silver", "amount": 3000000},
            {"type": "arenaTokens", "amount": 5},
            {"type": "clanBossKeys", "amount": 1},
        ])
        self.assertEqual(intel.energy, 80)
        self.assertEqual(intel.arena_tokens, 5)
        self.assertEqual(intel.cb_keys, 1)

    def test_resources_empty(self):
        intel = self._make_intel(resources={})
        self.assertEqual(intel.energy, 0)
        self.assertEqual(intel.arena_tokens, 0)
        self.assertEqual(intel.cb_keys, 0)

    def test_has_arena_tokens_true(self):
        intel = self._make_intel(resources={"arenaTokens": 5})
        self.assertTrue(intel.has_arena_tokens())

    def test_has_arena_tokens_false(self):
        intel = self._make_intel(resources={"arenaTokens": 0})
        self.assertFalse(intel.has_arena_tokens())

    def test_has_cb_keys_true(self):
        intel = self._make_intel(resources={"clanBossKeys": 2})
        self.assertTrue(intel.has_cb_keys())

    def test_has_cb_keys_false(self):
        intel = self._make_intel(resources={"clanBossKeys": 0})
        self.assertFalse(intel.has_cb_keys())

    def test_has_energy_threshold(self):
        intel = self._make_intel(resources={"energy": 10})
        self.assertTrue(intel.has_energy(min_energy=10))
        self.assertFalse(intel.has_energy(min_energy=11))


class TestHeroAnalysis(unittest.TestCase):
    """Test hero roster intelligence."""

    def _make_intel(self, heroes):
        mock_rtk = MagicMock()
        mock_rtk.get_resources.return_value = {}
        mock_rtk.get_heroes.return_value = heroes
        mock_rtk.get_arena.return_value = {}
        mock_rtk.get_account_dump.return_value = {}
        intel = AccountIntel(mock_rtk, "test-123")
        intel.refresh()
        return intel

    def test_get_top_heroes(self):
        heroes = [
            {"name": "Kael", "totalPower": 50000},
            {"name": "Athel", "totalPower": 45000},
            {"name": "Elhain", "totalPower": 60000},
            {"name": "Galek", "totalPower": 30000},
        ]
        intel = self._make_intel(heroes)
        top = intel.get_top_heroes(2)
        self.assertEqual(len(top), 2)
        self.assertEqual(top[0]["name"], "Elhain")
        self.assertEqual(top[1]["name"], "Kael")

    def test_get_total_team_power(self):
        heroes = [
            {"name": "A", "totalPower": 10000},
            {"name": "B", "totalPower": 20000},
            {"name": "C", "totalPower": 30000},
        ]
        intel = self._make_intel(heroes)
        self.assertEqual(intel.get_total_team_power(), 60000)

    def test_find_hero_by_name(self):
        heroes = [
            {"name": "Kael", "totalPower": 50000},
            {"name": "Athel", "totalPower": 45000},
        ]
        intel = self._make_intel(heroes)
        self.assertIsNotNone(intel.find_hero_by_name("kael"))
        self.assertIsNone(intel.find_hero_by_name("Arbiter"))

    def test_empty_heroes(self):
        intel = self._make_intel([])
        self.assertEqual(intel.get_top_heroes(5), [])
        self.assertEqual(intel.get_total_team_power(), 0)
        self.assertIsNone(intel.find_hero_by_name("Kael"))


class TestArtifactScoring(unittest.TestCase):
    """Test artifact quality evaluation."""

    def _make_intel(self):
        mock_rtk = MagicMock()
        mock_rtk.get_resources.return_value = {}
        mock_rtk.get_heroes.return_value = []
        mock_rtk.get_arena.return_value = {}
        mock_rtk.get_account_dump.return_value = {}
        mock_rtk.get_artifacts.return_value = [
            {"rank": 6, "rarity": "Legendary", "level": 16},
            {"rank": 3, "rarity": "Common", "level": 0},
            {"rank": 5, "rarity": "Epic", "level": 8},
            {"rank": 1, "rarity": "Common", "level": 0},
        ]
        intel = AccountIntel(mock_rtk, "test-123")
        intel.refresh()
        return intel

    def test_score_high_quality(self):
        intel = self._make_intel()
        score = intel.score_artifact({"rank": 6, "rarity": "Legendary", "level": 16})
        self.assertGreater(score, 90)

    def test_score_low_quality(self):
        intel = self._make_intel()
        score = intel.score_artifact({"rank": 1, "rarity": "Common", "level": 0})
        self.assertLess(score, 15)

    def test_get_bad_artifacts(self):
        intel = self._make_intel()
        bad = intel.get_bad_artifacts(threshold=30)
        # Rank 1 Common lvl 0 and Rank 3 Common lvl 0 should be bad
        self.assertGreaterEqual(len(bad), 1)
        # Verify they're sorted by score ascending
        scores = [s for _, s in bad]
        self.assertEqual(scores, sorted(scores))


class TestArenaIntelligence(unittest.TestCase):
    """Test arena opponent evaluation and picking."""

    def _make_intel(self, my_power=100000):
        mock_rtk = MagicMock()
        heroes = [{"name": f"Hero{i}", "totalPower": my_power // 5} for i in range(5)]
        mock_rtk.get_resources.return_value = {"arenaTokens": 10}
        mock_rtk.get_heroes.return_value = heroes
        mock_rtk.get_arena.return_value = {"leagueName": "Gold IV"}
        mock_rtk.get_account_dump.return_value = {}
        intel = AccountIntel(mock_rtk, "test-123")
        intel.refresh()
        return intel

    def test_rank_opponents_sorted_by_power(self):
        intel = self._make_intel(my_power=100000)
        opponents = [
            {"teamPower": 120000},
            {"teamPower": 50000},
            {"teamPower": 90000},
        ]
        ranked = intel.rank_arena_opponents(opponents)
        powers = [r["power"] for r in ranked]
        self.assertEqual(powers, [50000, 90000, 120000])

    def test_pick_best_opponent_winnable(self):
        intel = self._make_intel(my_power=100000)
        opponents = [
            {"teamPower": 150000},  # too strong (1.5x)
            {"teamPower": 80000},   # easy win
            {"teamPower": 110000},  # within 1.2x, winnable
        ]
        pick = intel.pick_best_opponent(opponents)
        self.assertEqual(pick, 1)  # index of 80000 power opponent

    def test_pick_best_opponent_all_strong(self):
        intel = self._make_intel(my_power=50000)
        opponents = [
            {"teamPower": 200000},
            {"teamPower": 150000},
            {"teamPower": 180000},
        ]
        # Should pick weakest even if all too strong
        pick = intel.pick_best_opponent(opponents)
        self.assertEqual(pick, 1)  # index of 150000 (weakest)

    def test_pick_best_opponent_empty(self):
        intel = self._make_intel()
        self.assertIsNone(intel.pick_best_opponent([]))

    def test_winnable_threshold(self):
        intel = self._make_intel(my_power=100000)
        opponents = [{"teamPower": 119000}]  # 1.19x, within 1.2x threshold
        ranked = intel.rank_arena_opponents(opponents)
        self.assertTrue(ranked[0]["winnable"])

        opponents = [{"teamPower": 121000}]  # 1.21x, exceeds threshold
        ranked = intel.rank_arena_opponents(opponents)
        self.assertFalse(ranked[0]["winnable"])


class TestDungeonIntelligence(unittest.TestCase):
    """Test dungeon farming readiness checks."""

    def _make_intel(self, energy=100):
        mock_rtk = MagicMock()
        mock_rtk.get_resources.return_value = {"energy": energy}
        mock_rtk.get_heroes.return_value = []
        mock_rtk.get_arena.return_value = {}
        mock_rtk.get_account_dump.return_value = {}
        intel = AccountIntel(mock_rtk, "test-123")
        intel.refresh()
        return intel

    def test_can_farm_enough_energy(self):
        intel = self._make_intel(energy=160)
        can_run, runs = intel.can_farm_dungeon(energy_per_run=16, num_runs=10)
        self.assertTrue(can_run)
        self.assertEqual(runs, 10)

    def test_can_farm_partial_energy(self):
        intel = self._make_intel(energy=50)
        can_run, runs = intel.can_farm_dungeon(energy_per_run=16, num_runs=10)
        self.assertTrue(can_run)
        self.assertEqual(runs, 3)  # 50 // 16 = 3

    def test_cannot_farm_no_energy(self):
        intel = self._make_intel(energy=5)
        can_run, runs = intel.can_farm_dungeon(energy_per_run=16, num_runs=10)
        self.assertFalse(can_run)
        self.assertEqual(runs, 0)

    def test_can_farm_campaign_low_cost(self):
        intel = self._make_intel(energy=40)
        can_run, runs = intel.can_farm_dungeon(energy_per_run=8, num_runs=10)
        self.assertTrue(can_run)
        self.assertEqual(runs, 5)


class TestSnapshot(unittest.TestCase):
    """Test the account snapshot summary."""

    def test_snapshot_fields(self):
        mock_rtk = MagicMock()
        mock_rtk.get_resources.return_value = {
            "energy": 100, "silver": 5000000, "gems": 50,
            "arenaTokens": 10, "clanBossKeys": 2,
        }
        mock_rtk.get_heroes.return_value = [
            {"name": "Kael", "totalPower": 50000},
            {"name": "Athel", "totalPower": 40000},
        ]
        mock_rtk.get_arena.return_value = {"leagueName": "Gold IV"}
        mock_rtk.get_account_dump.return_value = {}
        intel = AccountIntel(mock_rtk, "test-123")
        intel.refresh()

        snap = intel.get_snapshot()
        self.assertEqual(snap["energy"], 100)
        self.assertEqual(snap["silver"], 5000000)
        self.assertEqual(snap["arena_tokens"], 10)
        self.assertEqual(snap["hero_count"], 2)
        self.assertEqual(snap["arena_league"], "Gold IV")
        self.assertEqual(snap["top_power"], 90000)


if __name__ == '__main__':
    unittest.main()
