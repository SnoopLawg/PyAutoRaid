"""
Account intelligence layer.

Consumes RTK account data and provides smart decision-making:
- Resource checks (energy, keys, tokens, shards)
- Arena opponent evaluation
- Hero roster analysis
- Artifact quality scoring
- Task readiness checks (should we even attempt this task?)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AccountIntel:
    """
    Processes raw RTK account data into actionable automation decisions.

    Usage:
        intel = AccountIntel(rtk_client, account_id)
        intel.refresh()  # pulls fresh data from RTK

        if intel.has_arena_tokens():
            opponents = intel.get_arena_opponents()
            weak = intel.pick_weakest_opponent(opponents)

        if intel.has_cb_keys():
            ...
    """

    def __init__(self, rtk, account_id):
        self.rtk = rtk
        self.account_id = account_id
        self._dump = None
        self._resources = None
        self._heroes = None
        self._artifacts = None
        self._arena = None

    def refresh(self):
        """Pull fresh data from RTK. Call before making decisions."""
        logger.info("Refreshing account data from RTK...")
        try:
            self._dump = self.rtk.get_account_dump(self.account_id)
            logger.info("Account dump loaded.")
        except Exception as e:
            logger.warning(f"Account dump failed, falling back to individual calls: {e}")
            self._dump = None

        try:
            self._resources = self.rtk.get_resources(self.account_id)
        except Exception as e:
            logger.warning(f"Resources fetch failed: {e}")
            self._resources = {}

        try:
            self._heroes = self.rtk.get_heroes(self.account_id, snapshot=True)
        except Exception as e:
            logger.warning(f"Heroes fetch failed: {e}")
            self._heroes = []

        try:
            self._arena = self.rtk.get_arena(self.account_id)
        except Exception as e:
            logger.warning(f"Arena fetch failed: {e}")
            self._arena = {}

        self._log_summary()

    def _log_summary(self):
        """Log a human-readable account status."""
        r = self._resources or {}
        logger.info(f"Energy: {self.energy} | Silver: {self.silver:,} | Gems: {self.gems}")
        logger.info(f"Arena tokens: {self.arena_tokens} | CB keys: {self.cb_keys}")
        logger.info(f"Heroes: {len(self._heroes or [])}")
        if self._arena:
            logger.info(f"Arena tier: {self._arena.get('leagueName', 'unknown')}")

    # ── Resource helpers ──────────────────────────────────────────

    def _res(self, key, default=0):
        """Safely get a resource value from the resources dict."""
        if not self._resources:
            return default
        # RTK resources can be a dict or list of {type, amount} pairs
        if isinstance(self._resources, dict):
            return self._resources.get(key, default)
        if isinstance(self._resources, list):
            for r in self._resources:
                if r.get("type") == key or r.get("kind") == key:
                    return r.get("amount", r.get("count", default))
        return default

    @property
    def energy(self):
        return self._res("energy", 0) or self._res("Energy", 0)

    @property
    def silver(self):
        return self._res("silver", 0) or self._res("Silver", 0)

    @property
    def gems(self):
        return self._res("gems", 0) or self._res("Gems", 0)

    @property
    def arena_tokens(self):
        return self._res("arenaTokens", 0) or self._res("ArenaToken", 0) or self._res("arena_tokens", 0)

    @property
    def cb_keys(self):
        return self._res("clanBossKeys", 0) or self._res("ClanBossKey", 0) or self._res("clan_boss_keys", 0)

    @property
    def arena_refills(self):
        return self._res("arenaTokenRefill", 0) or self._res("ArenaTokenRefill", 0)

    # ── Task readiness checks ─────────────────────────────────────

    def has_arena_tokens(self, min_tokens=1):
        tokens = self.arena_tokens
        ready = tokens >= min_tokens
        if not ready:
            logger.info(f"Arena: {tokens} tokens (need {min_tokens}), skipping.")
        return ready

    def has_cb_keys(self, min_keys=1):
        keys = self.cb_keys
        ready = keys >= min_keys
        if not ready:
            logger.info(f"Clan Boss: {keys} keys (need {min_keys}), skipping.")
        return ready

    def has_energy(self, min_energy=1):
        e = self.energy
        ready = e >= min_energy
        if not ready:
            logger.info(f"Energy: {e} (need {min_energy}), skipping.")
        return ready

    # ── Hero analysis ─────────────────────────────────────────────

    def get_hero_power(self, hero) -> int:
        """Extract total power from a hero dict."""
        # RTK hero format varies — try common fields
        return (hero.get("totalPower", 0) or
                hero.get("power", 0) or
                hero.get("totalStats", {}).get("power", 0))

    def get_top_heroes(self, count=5) -> list:
        """Get top N heroes by power."""
        if not self._heroes:
            return []
        sorted_heroes = sorted(self._heroes, key=lambda h: self.get_hero_power(h), reverse=True)
        return sorted_heroes[:count]

    def get_total_team_power(self, heroes=None) -> int:
        """Sum power of a list of heroes (defaults to top 5)."""
        heroes = heroes or self.get_top_heroes(5)
        return sum(self.get_hero_power(h) for h in heroes)

    def find_hero_by_name(self, name: str) -> Optional[dict]:
        """Find a hero by name (case-insensitive)."""
        if not self._heroes:
            return None
        name_lower = name.lower()
        for h in self._heroes:
            hero_name = h.get("name", "") or h.get("typeName", "") or ""
            if hero_name.lower() == name_lower:
                return h
        return None

    # ── Arena intelligence ────────────────────────────────────────

    def get_arena_league(self) -> str:
        if not self._arena:
            return "unknown"
        return self._arena.get("leagueName", self._arena.get("league", "unknown"))

    def get_arena_defense(self) -> list:
        """Get current arena defense team."""
        if not self._arena:
            return []
        return self._arena.get("defensiveHeroes", self._arena.get("defense", []))

    def evaluate_opponent_power(self, opponent) -> int:
        """
        Estimate opponent power from arena data.
        RTK arena data format varies — this handles common structures.
        """
        if isinstance(opponent, dict):
            # Direct power field
            if "teamPower" in opponent:
                return opponent["teamPower"]
            if "power" in opponent:
                return opponent["power"]
            # Sum hero powers
            heroes = opponent.get("heroes", opponent.get("team", []))
            if heroes:
                return sum(
                    h.get("power", 0) or h.get("totalPower", 0)
                    for h in heroes
                )
        return 0

    # ── Artifact analysis ─────────────────────────────────────────

    def get_artifacts(self) -> list:
        """Get all artifacts."""
        if self._artifacts is None:
            try:
                self._artifacts = self.rtk.get_artifacts(self.account_id)
            except Exception as e:
                logger.warning(f"Artifacts fetch failed: {e}")
                self._artifacts = []
        return self._artifacts

    def score_artifact(self, artifact) -> float:
        """
        Score an artifact 0-100 based on quality.
        Higher = better, considers rank, rarity, and substat rolls.
        """
        score = 0.0

        # Rank contribution (1-6 stars, 6 is best)
        rank = artifact.get("rank", artifact.get("stars", 1))
        score += rank * 8  # max 48

        # Rarity contribution
        rarity_scores = {"Common": 0, "Uncommon": 4, "Rare": 8, "Epic": 14, "Legendary": 20}
        rarity = artifact.get("rarity", artifact.get("rarityId", "Common"))
        if isinstance(rarity, str):
            score += rarity_scores.get(rarity, 0)
        elif isinstance(rarity, int):
            score += min(rarity * 5, 20)

        # Level contribution (0-16)
        level = artifact.get("level", 0)
        score += level * 2  # max 32

        return min(score, 100.0)

    def get_bad_artifacts(self, threshold=30.0) -> list:
        """Get artifacts scoring below threshold (candidates for selling)."""
        artifacts = self.get_artifacts()
        bad = []
        for a in artifacts:
            s = self.score_artifact(a)
            if s < threshold:
                bad.append((a, s))
        bad.sort(key=lambda x: x[1])
        logger.info(f"Found {len(bad)} artifacts below score {threshold} (out of {len(artifacts)} total)")
        return bad

    # ── Full account snapshot ─────────────────────────────────────

    # ── Arena opponent evaluation ───────────────────────────────

    def rank_arena_opponents(self, opponents: list) -> list:
        """
        Rank arena opponents by estimated difficulty (easiest first).
        Each opponent gets a dict with 'index', 'power', and 'winnable' flag.
        """
        my_power = self.get_total_team_power()
        ranked = []
        for i, opp in enumerate(opponents):
            opp_power = self.evaluate_opponent_power(opp)
            ranked.append({
                "index": i,
                "opponent": opp,
                "power": opp_power,
                "power_ratio": opp_power / my_power if my_power > 0 else 999,
                "winnable": opp_power < my_power * 1.2,  # fight up to 20% stronger
            })
        ranked.sort(key=lambda x: x["power"])
        return ranked

    def pick_best_opponent(self, opponents: list) -> Optional[int]:
        """
        Pick the best opponent index to fight (weakest winnable).
        Returns the index (0-based position in the list) or None if all too strong.
        """
        ranked = self.rank_arena_opponents(opponents)
        for entry in ranked:
            if entry["winnable"]:
                logger.info(
                    f"Arena pick: opponent #{entry['index']} "
                    f"(power {entry['power']:,} vs our {self.get_total_team_power():,}, "
                    f"ratio {entry['power_ratio']:.2f})"
                )
                return entry["index"]
        # No easy wins — pick the weakest anyway
        if ranked:
            logger.warning("No winnable opponents found, picking weakest.")
            return ranked[0]["index"]
        return None

    # ── Dungeon intelligence ──────────────────────────────────────

    def can_farm_dungeon(self, energy_per_run=16, num_runs=10) -> tuple:
        """
        Check if we have enough energy for dungeon farming.
        Returns (can_run, affordable_runs).
        """
        total_needed = energy_per_run * num_runs
        available = self.energy
        affordable = available // energy_per_run if energy_per_run > 0 else 0
        can_run = affordable > 0
        if not can_run:
            logger.info(f"Dungeon: {available} energy, need {energy_per_run}/run, can't farm.")
        else:
            logger.info(f"Dungeon: {available} energy, can run {affordable}/{num_runs} requested.")
        return can_run, min(affordable, num_runs)

    def get_snapshot(self) -> dict:
        """Return a summary dict of current account state."""
        return {
            "energy": self.energy,
            "silver": self.silver,
            "gems": self.gems,
            "arena_tokens": self.arena_tokens,
            "cb_keys": self.cb_keys,
            "hero_count": len(self._heroes or []),
            "top_power": self.get_total_team_power(),
            "arena_league": self.get_arena_league(),
        }
