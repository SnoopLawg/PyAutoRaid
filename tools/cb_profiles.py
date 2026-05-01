"""CB hero profiles — extracted from cb_optimizer for separation of concerns.

`HeroProfile` is a static description of a hero's CB-relevant kit (A1
multiplier, debuff/buff types, special flags). `PROFILES` maps hero name
→ profile, used by the optimizer to score teams and validate UK tunes.

Adding a hero: append to PROFILES with the relevant flags. Notes field
should describe why the profile matters for CB scoring (skill IDs, key
debuffs, tune-breaking interactions).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HeroProfile:
    """CB-relevant snapshot of a hero's kit.

    a1_hits, a1_mult, a1_stat — A1 attack pattern (hits, multiplier, scaling stat).
    poisons_per_turn — average poisons placed per hero turn (active skill cycle).
    poison_on_counter — additional poisons from counter-attack A1s.
    hp_burn_uptime — fraction of CB turns HP Burn is active (0–1).
    passive_dmg — flat damage per CB turn (passives only, e.g. Geomancer reflect).
    unkillable / counterattack — buff types this hero applies to the team.
    ally_attack — number of ally-attack triggers per cast.
    def_down / weaken / dec_atk / inc_atk / inc_def / strengthen — debuff/buff
        types this hero places.
    poison_sensitivity — places PoisonSens (boosts poison damage taken).
    breaks_speed_tune — TM manipulation that breaks standard UK rotation.
    gs_preferred — multi-hit A1 benefits more from Giant Slayer than Warmaster.
    needs_acc — auto-set if the hero places any debuff (poison/burn/def-down/etc).
    """
    name: str
    a1_hits: int = 1
    a1_mult: float = 3.5
    a1_stat: str = "ATK"
    poisons_per_turn: float = 0
    poison_on_counter: float = 0
    hp_burn_uptime: float = 0
    passive_dmg: float = 0
    unkillable: bool = False
    counterattack: bool = False
    ally_attack: int = 0
    def_down: bool = False
    weaken: bool = False
    dec_atk: bool = False
    inc_atk: bool = False
    inc_def: bool = False
    strengthen: bool = False
    poison_sensitivity: bool = False
    breaks_speed_tune: bool = False
    gs_preferred: bool = False
    needs_acc: bool = False
    notes: str = ""

    def __post_init__(self) -> None:
        # Derived: any debuff placement implies the hero needs ACC.
        if not self.needs_acc:
            self.needs_acc = (
                self.poisons_per_turn > 0
                or self.def_down
                or self.weaken
                or self.hp_burn_uptime > 0
            )


def _hp(name: str, **kw) -> HeroProfile:
    return HeroProfile(name=name, **kw)


# Hero -> profile. Names match the in-game DefaultName (case-sensitive).
PROFILES: dict[str, HeroProfile] = {
    "Maneater": _hp("Maneater", a1_hits=2, a1_mult=3.4,
        unkillable=True, inc_atk=True,
        notes="Budget UK core. A3: Unkillable+BlockDmg. A2: ATK Up."),

    "Demytha": _hp("Demytha", a1_hits=1, a1_mult=4.0, a1_stat="DEF",
        unkillable=True, inc_def=True,
        notes="Myth comps. A2: Block Damage 2T. A3: Continuous Heal."),

    "Skullcrusher": _hp("Skullcrusher", a1_hits=1, a1_mult=3.8,
        counterattack=True,
        notes="A2: CA 2T on team. Ally Protect passive. CA = ~2x everyone's turns."),

    "Geomancer": _hp("Geomancer", a1_hits=1, a1_mult=3.5, a1_stat="DEF",
        hp_burn_uptime=0.6, passive_dmg=0, needs_acc=True,
        notes="Passive: reflects CB AoE -> GS procs (5 hits/AoE x 30% = ~1.5 GS/turn = ~112K/turn). HP Burn A3."),

    "Fayne": _hp("Fayne", a1_hits=3, a1_mult=3.0,
        poisons_per_turn=1.5, poison_on_counter=0.5,
        def_down=True, weaken=True, gs_preferred=True, needs_acc=True,
        notes="A3: DEF Down+Weaken+2 Poisons. A1: 3-hit poison chance. Top debuffer."),

    "Occult Brawler": _hp("Occult Brawler", a1_hits=1, a1_mult=3.5,
        poisons_per_turn=2.5, poison_on_counter=1.5, needs_acc=True,
        notes="A1: 2x 5% Poison. Passive: random poison. Best raw poisoner."),

    "Fahrakin the Fat": _hp("Fahrakin the Fat", a1_hits=2, a1_mult=3.2,
        poisons_per_turn=0.5, ally_attack=3, hp_burn_uptime=0.3,
        notes="A2: Ally Attack 3. A3: 2 Poisons. A1: HP Burn chance."),

    "Nethril": _hp("Nethril", a1_hits=3, a1_mult=3.0,
        poisons_per_turn=2.0, gs_preferred=True, needs_acc=True,
        notes="A2: 3x Poison. A1: 3-hit TM down."),

    "Venomage": _hp("Venomage", a1_hits=2, a1_mult=3.5,
        poisons_per_turn=1.5, poison_on_counter=0.5, needs_acc=True,
        poison_sensitivity=True,
        notes="A1: Poison. A2: Poison Sens 2T/3T CD + Poison. A3: 2 Poisons."),

    "Urogrim": _hp("Urogrim", a1_hits=1, a1_mult=3.2,
        poisons_per_turn=2.0, poison_on_counter=0.5, needs_acc=True,
        notes="A1: Poison. A2: Heal + 2 Poisons."),

    "Rhazin Scarhide": _hp("Rhazin Scarhide", a1_hits=1, a1_mult=4.0, a1_stat="DEF",
        def_down=True, weaken=True, needs_acc=True,
        notes="A2: DEF Down+Weaken (100%). A3: TM down. DEF-based."),

    "Sepulcher Sentinel": _hp("Sepulcher Sentinel", a1_hits=1, a1_mult=3.8, a1_stat="DEF",
        dec_atk=True, inc_def=True,
        notes="A1: Dec ATK 100%. A3: Block Debuffs + DEF Up. DEF-based."),

    "Doompriest": _hp("Doompriest", a1_hits=1, a1_mult=3.5,
        inc_atk=True,
        notes="Passive: Cleanse 1 debuff/turn + 5% heal. A2: ATK Up."),

    "Aox the Rememberer": _hp("Aox the Rememberer", a1_hits=1, a1_mult=3.5, a1_stat="DEF",
        dec_atk=True, poisons_per_turn=0.5,
        notes="A1: 50% Dec ATK. A3: CD reduction + Poison. DEF-based."),

    "Toragi the Frog": _hp("Toragi the Frog", a1_hits=2, a1_mult=3.0, a1_stat="DEF",
        poisons_per_turn=1.0, poison_on_counter=0.3,
        notes="A1: Poison. A2: Ally Protect. A3: 2 Poisons. DEF-based."),

    "Ninja": _hp("Ninja", a1_hits=3, a1_mult=4.2,
        hp_burn_uptime=0.6, gs_preferred=True, breaks_speed_tune=True,
        notes="A3: HP Burn. A2: high dmg. A1: 3-hit. PASSIVE: TM boost on HP Burn -- breaks UK tune!"),

    "Venus": _hp("Venus", a1_hits=1, a1_mult=3.5,
        def_down=True, weaken=True, hp_burn_uptime=0.5,
        poisons_per_turn=1.0, needs_acc=True,
        notes="A3: DEF Down+Weaken. A2: HP Burn+2 Poisons. Best all-in-one debuffer."),

    "Cardiel": _hp("Cardiel", a1_hits=1, a1_mult=3.5,
        inc_atk=True,
        notes="Passive: Block Damage on low HP. Revive + ATK Up."),

    "Iron Brago": _hp("Iron Brago", a1_hits=1, a1_mult=3.5, a1_stat="DEF",
        inc_def=True, strengthen=True,
        notes="A2: DEF Up + Strengthen (25% dmg). DEF-based."),

    "Drexthar Bloodtwin": _hp("Drexthar Bloodtwin", a1_hits=1, a1_mult=4.0, a1_stat="DEF",
        hp_burn_uptime=0.5,
        notes="Passive: HP Burn on hit. DEF-based."),

    "Coldheart": _hp("Coldheart", a1_hits=4, a1_mult=2.8,
        gs_preferred=True,
        notes="A1: 4-hit. A3: MaxHP dmg (bad for CB). GS value only."),

    "Apothecary": _hp("Apothecary", a1_hits=3, a1_mult=2.4,
        gs_preferred=True, breaks_speed_tune=True,
        notes="A2: SPD buff + TM boost. A1: 3-hit. TM boost breaks UK tune!"),

    "Arbiter": _hp("Arbiter", a1_hits=1, a1_mult=3.0,
        inc_atk=True,
        notes="A3: TM boost + ATK Up. Revive."),

    "Seeker": _hp("Seeker", a1_hits=1, a1_mult=4.0, a1_stat="DEF",
        inc_atk=True, breaks_speed_tune=True,
        notes="A2: TM boost + ATK Up. DEF-based. TM boost breaks UK tune!"),

    "Ultimate Deathknight": _hp("Ultimate Deathknight", a1_hits=1, a1_mult=3.5, a1_stat="DEF",
        inc_def=True,
        notes="Passive: 15% Ally Protect. Shield. DEF-based."),

    "Achak the Wendarin": _hp("Achak the Wendarin", a1_hits=1, a1_mult=3.5,
        hp_burn_uptime=0.3,
        notes="A3: HP Burn + Freeze."),

    "Teodor the Savant": _hp("Teodor the Savant", a1_hits=1, a1_mult=3.1, a1_stat="DEF",
        poisons_per_turn=1.5, poison_on_counter=0.5, needs_acc=True,
        breaks_speed_tune=True,
        notes="A1: 3.1*DEF + Poison. A2: 2 Poisons + INC SPD (BREAKS UK TUNE!). A3: Extend+Activate poisons."),

    "Artak": _hp("Artak", a1_hits=1, a1_mult=4.0,
        hp_burn_uptime=0.8, needs_acc=True,
        notes="A1: HP Burn 100%. A3: Strengthen+BlockDebuffs self. Passive: +dmg per debuff on enemy."),

    "Razelvarg": _hp("Razelvarg", a1_hits=2, a1_mult=3.2,
        poisons_per_turn=1.0, poison_on_counter=0.3,
        poison_sensitivity=True, needs_acc=True,
        notes="A1: Poison Sens. A2: multi-hit. A3: Poisons. PSens on A1 = high uptime."),

    "Steelskull": _hp("Steelskull", a1_hits=1, a1_mult=3.5, a1_stat="DEF",
        poisons_per_turn=1.0, poison_on_counter=0.3, inc_def=True, needs_acc=True,
        notes="A1: Poison. A2: Heal+Cleanse+DEF Up. DEF-based. Clean kit."),

    "Uugo": _hp("Uugo", a1_hits=1, a1_mult=3.5,
        def_down=True, needs_acc=True,
        notes="A2: DEF Down. A3: Heal+BlockDebuffs+Revive. HP-based support, wastes DPS slot."),

    # TM breakers — profiled but flagged
    "Ma'Shalled": _hp("Ma'Shalled", a1_hits=1, a1_mult=4.0,
        hp_burn_uptime=0.4, breaks_speed_tune=True,
        notes="A2: HP Burn. A3: TM boost 20% to allies -- BREAKS UK TUNE!"),

    "Scyl of the Drakes": _hp("Scyl of the Drakes", a1_hits=1, a1_mult=3.5, a1_stat="DEF",
        breaks_speed_tune=True,
        notes="Passive: random SPD Up on allies -- BREAKS UK TUNE!"),

    "Gnut": _hp("Gnut", a1_hits=1, a1_mult=4.0,
        breaks_speed_tune=True,
        notes="Passive: extra turns when allies hit. Extra turns burn Unkillable buff duration faster -> expires before Maneater can reapply."),

    "Galek": _hp("Galek", a1_hits=1, a1_mult=3.0,
        hp_burn_uptime=0.3, breaks_speed_tune=True,
        notes="A2: SPD Up on self -- BREAKS UK TUNE! Starter, too weak for UNM."),

    # --- S-tier CB heroes (may not be in roster but profiled for future pulls) ---
    "Dracomorph": _hp("Dracomorph", a1_hits=1, a1_mult=4.0,
        poisons_per_turn=2.0, poison_on_counter=0.5,
        def_down=True, weaken=True, gs_preferred=True, needs_acc=True,
        notes="A2: 4-hit + poisons. A3: DEF Down+Weaken. Best single-slot debuffer in game."),

    "Frozen Banshee": _hp("Frozen Banshee", a1_hits=2, a1_mult=3.0,
        poisons_per_turn=2.0, poison_on_counter=0.8,
        poison_sensitivity=True, needs_acc=True,
        notes="A1: 2-hit Poison IF PSens up. A3: Poison Sensitivity 2T. Best Rare poisoner."),

    "Bad-El-Kazar": _hp("Bad-El-Kazar", a1_hits=1, a1_mult=3.5,
        poisons_per_turn=2.0, needs_acc=True,
        notes="A2: 2 Poisons on all enemies + heal. A3: Cleanse+heal. Self-sufficient."),

    "Kalvalax": _hp("Kalvalax", a1_hits=1, a1_mult=4.0,
        poisons_per_turn=2.5, needs_acc=True,
        notes="A2: Detonate poisons (instant damage). A3+Passive: places poisons continuously."),

    "Vizier Ovelis": _hp("Vizier Ovelis", a1_hits=3, a1_mult=3.0,
        poisons_per_turn=0.5, gs_preferred=True, needs_acc=True,
        notes="A1: 3-hit + extends ALL debuffs by 1T per hit. Keeps poisons/DD/WK up forever."),

    "Corvis the Corruptor": _hp("Corvis the Corruptor", a1_hits=1, a1_mult=3.5,
        poisons_per_turn=2.0, dec_atk=True, needs_acc=True,
        notes="A2: extends enemy debuffs + ally buffs. A3: 2 Poison per hit. Built-in dmg reduction."),

    "Kreela Witch-Arm": _hp("Kreela Witch-Arm", a1_hits=2, a1_mult=3.5,
        ally_attack=3, inc_atk=True,
        notes="A2: Ally Attack 3. A3: ATK Up + CR Up on all. Like Fahrakin but better buffs."),

    "Helicath": _hp("Helicath", a1_hits=1, a1_mult=3.5, a1_stat="DEF",
        unkillable=True,  # Block Damage 3T = effectively unkillable solo
        inc_def=True,
        notes="A2: Block Damage 3T on all. Solo UK enabler -- frees 4 DPS slots!"),

    "Warcaster": _hp("Warcaster", a1_hits=2, a1_mult=3.0,
        unkillable=True,
        notes="A2: Block Damage 1T on all. Paired with Roshcard for UK loop."),

    "Roshcard the Tower": _hp("Roshcard the Tower", a1_hits=1, a1_mult=3.5, a1_stat="DEF",
        unkillable=True,
        notes="A2: Block Damage 2T on all. Paired with Warcaster for UK loop."),

    "Jintoro": _hp("Jintoro", a1_hits=1, a1_mult=4.0,
        def_down=True, weaken=True, needs_acc=True,
        notes="A3: DEF Down+Weaken (every 4th use = 5 hits). Ramps damage over fight."),

    "Narma the Returned": _hp("Narma the Returned", a1_hits=1, a1_mult=3.5,
        poisons_per_turn=2.5, needs_acc=True,
        notes="A1+A2: Poisons. Passive: places poisons + 25% dmg reduction when 5+ poisons."),

    "Heiress": _hp("Heiress", a1_hits=1, a1_mult=3.0,
        notes="Passive: extends all ally buffs by 1T each turn + cleanse. Myth-Heir core."),

    "Pain Keeper": _hp("Pain Keeper", a1_hits=1, a1_mult=3.0,
        notes="A3: Reduce all ally CDs by 1T. Budget UK core with Maneater. Rare."),

    # --- Tune breakers with profiles for reference ---
    "Sicia Flametongue": _hp("Sicia Flametongue", a1_hits=1, a1_mult=4.0,
        hp_burn_uptime=0.8, breaks_speed_tune=True,
        notes="A3: Extra Turn -- BREAKS UK TUNE! Dungeon speed farmer, not CB."),

    "Turvold": _hp("Turvold", a1_hits=1, a1_mult=6.0,
        breaks_speed_tune=True,
        notes="A3: Extra Turn + SPD Up self -- BREAKS standard UK. Needs Turvold-specific tune."),
}


def get(name: str) -> HeroProfile | None:
    """Lookup by name. Returns None if unknown."""
    return PROFILES.get(name)
