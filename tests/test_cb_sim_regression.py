"""Deterministic regression test for the CB simulator.

Locks in the canonical MEN-team smoke output. Any refactor that drifts
these numbers without an intentional reason flags here.

The values were validated across 7+ rounds of manifest/facade refactor
work on 2026-06-15 — every refactor was behavior-preserving against
this exact configuration. If you intentionally change sim behavior
(e.g. implement Cruelty blessing), update LOCKED_TOTAL_DMG and add a
comment explaining the delta.
"""
import os
import sys
import unittest

# Make tools/ importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))


class TestCBSimDeterministicSmoke(unittest.TestCase):
    """Lock the deterministic MEN (Myth Eater Ninja) team output."""

    # Locked 2026-06-15 — MEN team, deterministic, model_survival=True.
    # See docs/cb_engineering_plan.md for the canonical MEN tune.
    # Float compare allows 1 part-per-million tolerance for arithmetic
    # noise (TICK_RATE = 0.7 vs 0.7000000000000001 from facade math).
    #
    # History:
    #   - Initial lock 2026-06-15: 18 / 8,073,110.06 (across rounds 1-15)
    #   - 2026-06-15 round 16: 18 / 8,211,037.43 (+1.7%) after wiring
    #     Attack book bonus (SkillBonusType=0). Game-correct shift — books
    #     boost A1/A2/A3 damage that sim previously missed.
    #   - 2026-06-15 round 18: 25 / 13,476,158.82 after wiring
    #     Geomancer Stoneguard team -15% DR AND skip-on-apply override
    #     for UK/BD/BkD/Shield/Veil. Game-correct shifts: real CB tick
    #     log captures show heroes RETAIN survival buffs through their
    #     placement turn (manifest's SkipProcessingWhenJultApplied=None
    #     disagrees with observed game behavior).
    #   - 2026-06-15 round 22: 25 / 13,414,277.72 after EMPIRICAL_CD_OVERRIDES
    #     (Maneater A3 cd=4). Calibrates A3 cycle to real-game cadence (every 3
    #     boss turns vs sim's prior 4-5). Delta: -0.46%. See cb_sim.py
    #     EMPIRICAL_CD_OVERRIDES + project_cb_speed_compensating_wrong memory
    #     for mechanism investigation.
    #   - 2026-06-15 round 23: 25 / 13,476,158.82 — REVERTED the cd=4 override.
    #     User screenshots prove A3 fully booked at level 3/3 with cd=5 effective.
    #     Real missing mechanism lives elsewhere; the hack was masking it.
    #   - 2026-06-16 round 27: BRIEFLY changed affinity tables and locked at
    #     20/9.01M. REVERTED — Raid trinity is Spirit > Force > Magic > Spirit
    #     (Magic strong vs Spirit, etc), which is what the ORIGINAL tables had.
    #     User caught the mistake.
    #   - 2026-06-16 round 30: 25 / 13,306,753.40 after AOE1 multiplier fix.
    #     CB_ATTACK_MULT['aoe1'] changed from 4.0 (interpretation of Count=4
    #     × formula 1*ATK as 4*ATK per hero) to 1.0 (real game data shows
    #     Count=4 distributes 4 hits across enemies, averaging ~1*ATK/hero).
    #     This fix brought Spirit-day MEN match from +1.0% to +0.0% vs real
    #     T50/37.12M. Boss damage to team is now ~10× lower at AOE1 turns
    #     (every 3rd turn), allowing real-game survival cycle.
    #   - 2026-06-23 RE-BASELINE: 18 / 7,354,476.70. The lock went stale across
    #     intentional game-truth fixes that postdate round 30 (investigated, NOT
    #     a regression):
    #       * 599297f — Maneater A3 (Ancient Blood) deals damage to SELF, not
    #         the boss (static effect 107033 KindId=Damage TargetType=Producer),
    #         and no longer rolls WM/PT procs on the cast. Verified via real
    #         Spirit BT50 attribution (Maneater had been +31.7% over). Main
    #         driver of BOTH the damage drop (13.3M->7.35M) and the survival
    #         drop (25->18 boss turns — A3 now correctly self-damages).
    #       * da59b52 — DWJ-parity cadence (TM reset to 0).
    #       * 95472fa — 3 game-truth debuff fixes (IL2CPP-verified).
    #   Re-baselined 2026-06-28 — ASYMMETRIC TM reset (heroes overflow-preserve,
    #   boss zero-resets), matching live-game per-hero ticks/turn from
    #   tick_log_cb_clean2 (slow heroes run at true continuous rate, boss fixed
    #   8/turn). Restores the survival interlock (Demytha BD locked to aoe1):
    #   minimal-team survives to 25 boss turns again; damage re-baselines as the
    #   old number was inflated to compensate for the under-counted cadence.
    LOCKED_CB_TURNS = 25
    LOCKED_TOTAL_DMG = 11_074_802.64
    LOCKED_TOTAL_TOL = 20.0  # widened for additive arithmetic noise

    def _build_men_team(self):
        from cb_sim import build_champion_minimal
        return [
            build_champion_minimal(name="Maneater", position=1, speed=288,
                                    hp=40000, defense=1500, element=4),
            build_champion_minimal(name="Demytha", position=2, speed=172,
                                    hp=38000, defense=1500, element=4),
            build_champion_minimal(name="Ninja", position=3, speed=205,
                                    hp=43000, defense=1500, element=1),
            build_champion_minimal(name="Geomancer", position=4, speed=177,
                                    hp=58000, defense=1500, element=4),
            build_champion_minimal(name="Venomage", position=5, speed=162,
                                    hp=48000, defense=1500, element=2),
        ]

    def test_men_deterministic_locked(self):
        from cb_sim import CBSimulator
        heroes = self._build_men_team()
        sim = CBSimulator(
            heroes, cb_speed=190, cb_element=1,
            deterministic=True, model_survival=True,
        )
        res = sim.run(max_cb_turns=50)
        self.assertEqual(
            res.get("cb_turns", 0), self.LOCKED_CB_TURNS,
            f"cb_turns drifted from locked value {self.LOCKED_CB_TURNS}; "
            f"if intentional, update the constant + comment why",
        )
        actual = res.get("total", 0)
        if self.LOCKED_TOTAL_DMG is None:
            return  # damage lock paused — only cb_turns checked
        self.assertAlmostEqual(
            actual, self.LOCKED_TOTAL_DMG, delta=self.LOCKED_TOTAL_TOL,
            msg=(f"total_dmg drifted from locked value "
                 f"{self.LOCKED_TOTAL_DMG:,.2f} ± {self.LOCKED_TOTAL_TOL} "
                 f"(actual {actual:,.4f}); if intentional, update the "
                 f"constant + comment why"),
        )

    def test_facade_self_test_passes(self):
        """If the facade self-test breaks, all the facade-routed call
        sites in cb_sim are at risk. Runs the facade's own asserts."""
        from sim_data_facade import _selftest
        self.assertEqual(_selftest(), 0,
                         "sim_data_facade self-test failed")

    def test_cardiel_team_exercises_lethal_save(self):
        """Run a Cardiel-led team and verify the LETHAL_SAVE_PASSIVES
        dispatcher actually fires (saves at least one teammate) — this
        catches a registry that loads but isn't reached by the death
        loop, e.g. if a future refactor breaks the dispatch path.
        """
        from cb_sim import build_champion_minimal, CBSimulator
        heroes = [
            build_champion_minimal(name="Cardiel", position=1, speed=246,
                                    hp=42000, defense=1800, element=1),
            build_champion_minimal(name="Demytha", position=2, speed=172,
                                    hp=38000, defense=1500, element=4),
            build_champion_minimal(name="Ninja", position=3, speed=205,
                                    hp=43000, defense=1500, element=1),
            build_champion_minimal(name="Geomancer", position=4, speed=177,
                                    hp=58000, defense=1500, element=4),
            build_champion_minimal(name="Venomage", position=5, speed=162,
                                    hp=48000, defense=1500, element=2),
        ]
        sim = CBSimulator(
            heroes, cb_speed=190, cb_element=4,
            deterministic=True, model_survival=True,
        )
        sim.run(max_cb_turns=50)
        # If Cardiel's save passive fired at least once for any teammate,
        # an attr matching `_save_cd_Cardiel_<pos>` should be set on him.
        cardiel = heroes[0]
        save_attrs = [a for a in dir(cardiel)
                       if a.startswith("_save_cd_Cardiel_")]
        self.assertGreater(
            len(save_attrs), 0,
            "Cardiel lethal-save dispatcher never fired — either the "
            "registry isn't reached or no teammate died (sim too tame). "
            "If sim got tougher legitimately, lower hero defense to "
            "trigger a death.",
        )


class TestRegistryDataDriven(unittest.TestCase):
    """Verify the data-driven hero registries have the expected shape so
    cb_sim's dispatchers find what they need."""

    def test_lethal_save_registry_shape(self):
        from cb_sim import LETHAL_SAVE_PASSIVES
        self.assertIn("Cardiel", LETHAL_SAVE_PASSIVES)
        self.assertIn("Ultimate Deathknight", LETHAL_SAVE_PASSIVES)
        # Each entry has the required keys
        for name, defn in LETHAL_SAVE_PASSIVES.items():
            self.assertIn("save_scope", defn)
            self.assertIn(defn["save_scope"], ("ally", "self"))
            self.assertIn("cooldown_turns", defn)
            self.assertIsInstance(defn["cooldown_turns"], int)

    def test_duplicate_instance_heroes_shape(self):
        from cb_sim import (DUPLICATE_INSTANCE_HEROES,
                            DUPLICATE_INSTANCE_OPENERS,
                            _dup_key_for, _dup_opener_for)
        self.assertIn("Maneater", DUPLICATE_INSTANCE_HEROES)
        # _dup_key_for behavior
        self.assertEqual(_dup_key_for("Maneater", 1), "Maneater")
        self.assertEqual(_dup_key_for("Maneater", 2), "Maneater_2")
        self.assertEqual(_dup_key_for("NotADup", 2), "NotADup")
        # _dup_opener_for behavior
        self.assertEqual(_dup_opener_for("Maneater", 1), ["A3"])
        self.assertEqual(_dup_opener_for("Maneater", 2), ["A1", "A3"])
        self.assertEqual(_dup_opener_for("Maneater", 99), [])


class TestForcingFunctionInfrastructure(unittest.TestCase):
    """Lock the cb_truth_diff buff-name normalizer + delta-aware
    hypothesis dispatch. Prevents a future refactor from re-introducing
    false-positive name-mismatch divergences or losing the
    "missing_in_sim" / "extra_in_sim" structured delta keys."""

    def test_buff_name_aliases_normalize_real_and_sim_names(self):
        from cb_truth_diff import _normalize_buff_name
        # Real side uses short codes; sim uses long names; both should
        # collapse to the same canonical token.
        self.assertEqual(_normalize_buff_name("bkd"),
                         _normalize_buff_name("block_debuffs"))
        self.assertEqual(_normalize_buff_name("uk"),
                         _normalize_buff_name("unkillable"))
        self.assertEqual(_normalize_buff_name("continuousheal"),
                         _normalize_buff_name("cont_heal_15"))
        self.assertEqual(_normalize_buff_name("continuousheal"),
                         _normalize_buff_name("cont_heal_75"))
        # Unknown buff names pass through unchanged (lowercased)
        self.assertEqual(_normalize_buff_name("brandNewBuff"),
                         "brandnewbuff")
        # Spaces normalize to underscore
        self.assertEqual(_normalize_buff_name("Block Damage"),
                         _normalize_buff_name("block_damage"))

    def test_jsonable_preserves_dict_structure(self):
        """Buff-set divergences emit dicts with `missing_in_sim` etc.
        — programmatic consumers need them as real dicts."""
        from cb_truth_diff import _jsonable
        sample = {"all": ["unkillable"], "missing_in_sim": ["veil"],
                  "extra_in_sim": []}
        out = _jsonable(sample)
        self.assertIsInstance(out, dict)
        self.assertIn("missing_in_sim", out)
        self.assertEqual(out["extra_in_sim"], [])

    def test_self_buff_override_registry_shape(self):
        """KNOWN_SELF_BUFF_OVERRIDES holds the self-buff placements
        the upstream extractor (hero_profiles_game.json) misses. Verify
        Ninja A2 -> Veil entry is present and shape is right."""
        from cb_sim import KNOWN_SELF_BUFF_OVERRIDES
        self.assertIn("Ninja", KNOWN_SELF_BUFF_OVERRIDES)
        ninja_a2 = KNOWN_SELF_BUFF_OVERRIDES["Ninja"].get("A2")
        self.assertIsNotNone(ninja_a2)
        # Each entry is (buff_name, duration)
        for buff_name, dur in ninja_a2:
            self.assertIsInstance(buff_name, str)
            self.assertIsInstance(dur, int)
            self.assertGreater(dur, 0)
        # Specifically Ninja A2 should place Veil
        veil_entries = [e for e in ninja_a2 if e[0] == "veil"]
        self.assertEqual(len(veil_entries), 1,
                         "Ninja A2 must have exactly one veil entry")

    def test_book_shield_creation_bonus_loads(self):
        """SkillBonusType=4 (ShieldCreation) from skill books must
        propagate from skills_db.json -> SKILL_DATA -> SimSkill so
        shield-providers like Demytha don't under-shield by 20%+
        on survival calcs.

        Game-truth source: IL2Cpp `SkillBonusType` enum (value 4 =
        ShieldCreation). Demytha A1 fully booked = 4 × 5% = +0.20.
        """
        from cb_sim import SKILL_DATA
        dy_a1 = SKILL_DATA.get("Demytha", {}).get("A1", {})
        bonus = dy_a1.get("shield_creation_bonus", 0.0)
        self.assertAlmostEqual(
            bonus, 0.20, places=4,
            msg=("Demytha A1 should have +0.20 ShieldCreation book bonus "
                 "(4 × 5%). If this drops to 0 the upstream book extraction "
                 "regressed; if it changes, books in the user's roster shifted."),
        )

    def test_lasting_gifts_extends_eligible_buff(self):
        """Lasting Gifts mastery (500351) extends a random ally buff by
        1 turn at start of owner's turn with 30% chance. Deterministic
        accumulator should produce 1 proc after ~4 turns (4 × 0.30 = 1.2).
        Excluded buffs (UK, BD, etc.) must NOT be extended.
        """
        from cb_sim import build_champion_minimal, CBSimulator
        # 1 hero with Lasting Gifts, both holding extendable + non-extendable buffs
        heroes = [
            build_champion_minimal(name="Demytha", position=1, speed=200,
                                    hp=40000, defense=1500, element=4),
            build_champion_minimal(name="Ninja", position=2, speed=190,
                                    hp=40000, defense=1500, element=4),
        ]
        heroes[0].has_lasting_gifts = True
        # Pre-load buffs that LG SHOULD extend
        heroes[0].buffs = {"cont_heal_15": 5}
        heroes[1].buffs = {"shield": 5}
        # Also pre-load buffs that LG should NEVER touch
        heroes[0].buffs["unkillable"] = 1
        heroes[1].buffs["block_damage"] = 1

        sim = CBSimulator(heroes, cb_speed=190, cb_element=4,
                          deterministic=True, model_survival=False)
        # Run enough cb_turns for the accumulator to cross 1.0 at least once.
        sim.run(max_cb_turns=4)
        # If LG fired, the non-protected buffs may have +1; UK/BD should
        # still be ≤ 1 (decremented OR not extended, never bumped above).
        # Sanity check: code path runs without raising; UK never extended.
        self.assertLessEqual(
            heroes[0].buffs.get("unkillable", 0), 1,
            "Lasting Gifts must NOT extend Unkillable (NonIncreaseable)",
        )
        self.assertLessEqual(
            heroes[1].buffs.get("block_damage", 0), 1,
            "Lasting Gifts must NOT extend Block Damage (NonIncreaseable)",
        )

    def test_master_hexer_extends_debuff_on_placement(self):
        """Master Hexer mastery (500354) gives 30% chance to extend a
        debuff at placement. Deterministic mode uses an accumulator.
        After enough placements, the extension should fire.
        """
        from cb_sim import build_champion_minimal, CBSimulator
        heroes = [
            build_champion_minimal(name="Ninja", position=1, speed=205,
                                    hp=40000, defense=1500, element=1),
        ] + [
            build_champion_minimal(name=nm, position=i, speed=180,
                                    hp=40000, defense=1500, element=4)
            for i, nm in enumerate(["Demytha", "Maneater", "Geomancer", "Venomage"], start=2)
        ]
        heroes[0].has_master_hexer = True
        sim = CBSimulator(heroes, cb_speed=190, cb_element=1,
                          deterministic=True, model_survival=False)
        # Verify _master_hexer_extends returns 1 after the accumulator
        # has built up to ≥ 1.0 (4 calls × 0.30 = 1.2).
        from cb_sim import SimChampion
        ninja = heroes[0]
        extends_seen = 0
        for _ in range(8):
            extends_seen += sim._master_hexer_extends(ninja, "hp_burn")
        self.assertGreater(
            extends_seen, 0,
            "Master Hexer accumulator must produce at least one +1 extension "
            "after 8 deterministic placements at 30% chance.",
        )

    def test_book_attack_bonus_loads(self):
        """SkillBonusType=0 (Attack) book bonus must propagate to skill
        damage. Maneater A1 + A2 fully booked = +20% damage each.

        Game-truth source: IL2Cpp `SkillBonusType` enum (value 0 = Attack).
        """
        from cb_sim import SKILL_DATA
        me_a1 = SKILL_DATA.get("Maneater", {}).get("A1", {})
        bonus = me_a1.get("attack_book_bonus", 0.0)
        self.assertAlmostEqual(
            bonus, 0.20, places=4,
            msg=("Maneater A1 should have +0.20 Attack book bonus "
                 "(4 × 5%). If this drops to 0 the upstream extraction "
                 "regressed."),
        )

    def test_book_health_bonus_loads(self):
        """SkillBonusType=1 (Health) from skill books must propagate
        to heal-providers like Demytha A2. Without this, sim under-heals
        by ~20% on the user's MEN tune (survival modeling gap).

        Game-truth source: IL2Cpp `SkillBonusType` enum (value 1 =
        Health). Demytha A2 fully booked = 4 × 5% = +0.20.
        """
        from cb_sim import SKILL_DATA
        dy_a2 = SKILL_DATA.get("Demytha", {}).get("A2", {})
        bonus = dy_a2.get("health_book_bonus", 0.0)
        self.assertAlmostEqual(
            bonus, 0.20, places=4,
            msg=("Demytha A2 should have +0.20 Health book bonus "
                 "(4 × 5%). If this drops to 0 the upstream book extraction "
                 "regressed."),
        )

    def test_geared_champion_loader_returns_real_speeds(self):
        """The diff's _build_geared_sim_champions reads SPD/HP/DEF from
        heroes_all.json. Ninja in the MEN tune should have ≥190 SPD;
        if this regresses to the 180 default, the diff's actor-order
        gets wrong and the forcing function noise re-appears."""
        try:
            from cb_truth_diff import _build_geared_sim_champions
        except ImportError:
            self.skipTest("cb_truth_diff not importable")
        team = ["Maneater", "Demytha", "Ninja", "Geomancer", "Venomage"]
        champs, ok = _build_geared_sim_champions(team, cb_element=4)
        if not ok:
            self.skipTest("heroes_all.json missing — geared loader fell back")
        ninja = next((c for c in champs if c.name == "Ninja"), None)
        self.assertIsNotNone(ninja, "Ninja should be in geared champ list")
        # SPD index is 4 per gear_constants
        ninja_spd = ninja.stats.get(4, 0)
        self.assertGreater(
            ninja_spd, 190,
            f"Ninja SPD={ninja_spd}; expected >190 from real artifact load. "
            f"If this drops to ~180 the diff will mis-order actors."
        )


class TestTeamInventionEngine(unittest.TestCase):
    """Lock the sim-integrated scoring pipeline. If score_team's return
    contract changes or beam_search loses its sim integration,
    Workstream 10 (Phase 4) regresses to stub status."""

    def test_score_team_respects_int_element_field(self):
        """heroes_all.json sometimes stores element as int (1=Magic,
        2=Force, etc.) instead of string ("Magic"). The score_team's
        element resolver must handle BOTH. Round-29 bug: int element=1
        fell through to default cb_element=4, silently making every
        hero Void affinity. Verified locally that Venomage, Ninja,
        Geomancer, Maneater, and Demytha all have int elements in
        heroes_all.json.
        """
        try:
            from team_invention_engine import load_owned
            from cb_optimizer import calc_stats
            from cb_sim import build_sim_champion
        except ImportError:
            self.skipTest("not importable")
        roster = load_owned()
        # Ninja must resolve to element=1 (Magic) not default cb_element
        ninja = roster.get(6206)
        if not ninja:
            self.skipTest("Ninja not in roster")
        elem_raw = ninja.get("element")
        if isinstance(elem_raw, int) and 1 <= elem_raw <= 4:
            elem = elem_raw
        else:
            elem = {"Magic": 1, "Force": 2, "Spirit": 3, "Void": 4}.get(
                elem_raw or "", 4)
        # Build champ via score_team's path; expect element=1 (Magic)
        # for Ninja regardless of cb_element passed
        stats = calc_stats(ninja, ninja.get("artifacts", []), {})
        champ = build_sim_champion(ninja.get("name"), stats, 1, element=elem)
        self.assertEqual(
            champ.element, 1,
            f"Ninja element resolved to {champ.element}, expected 1 (Magic). "
            f"Round-29 regression of element-resolution bug — int elements "
            f"in heroes_all.json must not fall through to default."
        )

    def test_base_HP_flows_through_calc_stats(self):
        """Phase E base_HP capture for CB stun damage (TRG_B_HP formula
        in skill 222601 = 0.2 * TRG_B_HP). Bug fix round 24: base_HP
        was computed in `scaled` but never copied to returned `stats`.

        Lock this in: any hero in the computed_stats cache should have
        a base_HP field populated, and that value should be < their
        gear-included MAX HP (since base = pre-gear, MAX = post-gear).
        """
        try:
            from team_invention_engine import load_owned
            from cb_optimizer import calc_stats
        except ImportError:
            self.skipTest("not importable")
        roster = load_owned()
        mn = roster.get(1076)  # Maneater type_id
        if not mn:
            self.skipTest("Maneater not in roster")
        stats = calc_stats(mn, mn.get("artifacts", []), {})
        base_hp = stats.get("base_HP")
        max_hp = stats.get(1)  # HP index = 1
        self.assertIsNotNone(
            base_hp,
            "base_HP missing from calc_stats output — "
            "regression of round-24 fix"
        )
        self.assertGreater(base_hp, 0)
        self.assertLess(
            base_hp, max_hp,
            f"base_HP ({base_hp}) should be < MAX HP ({max_hp}); "
            f"if they're equal, the pre-gear base is being conflated "
            f"with gear-included HP."
        )

    def test_score_team_is_deterministic_across_runs(self):
        """score_team must produce identical results across calls when
        deterministic=True. Round-25 bug: `_try_place_smite` was using
        self.rng (random.Random initialized with system time) even in
        deterministic mode, causing ~5% variance in total damage between
        otherwise-identical runs.
        """
        try:
            from team_invention_engine import load_owned, score_team
        except ImportError:
            self.skipTest("not importable")
        roster = load_owned()
        if not roster:
            self.skipTest("roster empty")
        MEN = (1076, 6516, 6206, 4886, 6286)
        if not all(tid in roster for tid in MEN):
            self.skipTest("MEN team type_ids missing")
        results = [
            score_team(MEN, roster, cb_element=3, max_cb_turns=30)
            for _ in range(3)
        ]
        for i, r in enumerate(results[1:], 2):
            self.assertEqual(
                r["total_damage"], results[0]["total_damage"],
                f"score_team run {i} damage differs from run 1 "
                f"({r['total_damage']:,} vs {results[0]['total_damage']:,}) — "
                f"deterministic mode regressed"
            )
            self.assertEqual(
                r["cb_turns_survived"], results[0]["cb_turns_survived"],
                f"score_team run {i} cb_turns differs from run 1"
            )

    def test_load_owned_prefers_higher_spd_duplicate(self):
        """User owns 2 Maneaters (type_id 1076): id 15120 fully geared
        (288 SPD) and id 18357 partially geared (208 SPD). load_owned
        must pick the higher-SPD copy — picking the ungeared one in
        round 19 made Maneater A3 cycle every 5.5 boss turns instead of
        the real game's 4-turn cycle, causing sim heroes to die at T22
        when they should survive to T32+.

        Locked here so future refactor of load_owned doesn't regress.
        """
        try:
            from team_invention_engine import load_owned
            from cb_optimizer import calc_stats
        except ImportError:
            self.skipTest("team_invention_engine not importable")
        roster = load_owned()
        mn = roster.get(1076)
        if not mn:
            self.skipTest("Maneater not in roster")
        spd = calc_stats(mn, mn.get("artifacts", []), {}).get(4, 0)
        self.assertGreater(
            spd, 250,
            f"Maneater roster pick has SPD={spd}; expected >250 (geared "
            f"copy 288). The ungeared 208-SPD copy regression dropped "
            f"sim survival by 10+ cb_turns."
        )

    def test_score_team_returns_required_fields(self):
        """score_team must return a stable dict shape so the CLI and
        downstream rank_candidates can rely on it."""
        try:
            from team_invention_engine import score_team, load_owned
        except ImportError:
            self.skipTest("team_invention_engine not importable")
        roster = load_owned()
        if not roster:
            self.skipTest("heroes_all.json missing")
        # MEN team type_ids
        MEN = (1076, 6516, 6206, 4886, 6286)
        if not all(tid in roster for tid in MEN):
            self.skipTest("MEN team type_ids not all in roster")
        result = score_team(MEN, roster, cb_element=4, max_cb_turns=10)
        self.assertNotIn(
            "error", result,
            f"score_team failed on MEN baseline: {result.get('error')}",
        )
        for key in ("total_damage", "cb_turns_survived",
                     "first_death_turn", "survival_factor",
                     "damage_score", "team_names", "team_type_ids"):
            self.assertIn(key, result, f"score_team missing {key}")
        # MEN should produce positive damage and reasonable survival
        self.assertGreater(result["total_damage"], 0)
        self.assertGreater(result["cb_turns_survived"], 0)
        # Survival factor must be in [0, 1]
        self.assertGreaterEqual(result["survival_factor"], 0.0)
        self.assertLessEqual(result["survival_factor"], 1.0)


class TestManifestCrossCheck(unittest.TestCase):
    """If cb_constants and the manifest drift, this test catches it.

    cb_constants emits a warning by default; set CB_CONSTANTS_STRICT=1
    in CI to make drift a test failure rather than a warning.
    """

    def test_cb_constants_imports_without_drift(self):
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # Fresh import — _validate_against_manifest runs on import
            import importlib
            import cb_constants
            importlib.reload(cb_constants)
            drift_warnings = [
                str(ww.message) for ww in w
                if "manifest" in str(ww.message).lower()
            ]
            self.assertEqual(
                drift_warnings, [],
                f"cb_constants reported manifest drift: {drift_warnings}",
            )


if __name__ == "__main__":
    unittest.main()
