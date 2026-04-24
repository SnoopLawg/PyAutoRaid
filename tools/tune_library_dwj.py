#!/usr/bin/env python3
"""AUTO-GENERATED from data/dwj/parsed/calc_tunes.json.

Do not edit by hand. To refresh:
    python3 tools/scrape_dwj.py         # refresh tunes.json
    python3 tools/scrape_dwj_calc.py    # refresh calc_tunes.json + calc_champions.json
    python3 tools/gen_tune_library_dwj.py

Each entry registers one DWJ tune variant (difficulty-specific) with the same
TuneDefinition schema as tune_library.py. Import this module alongside
tune_library.py to make DWJ-sourced tunes discoverable.
"""

from tune_library import TuneDefinition, TuneSlot, _register


# Batman Forever — Ultra-Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/batman-forever/  |  calc: https://deadwoodjedi.info/cb/d3edeec70427190fdf16fd1a8f2a39e22a603cd5
_register(TuneDefinition(
    name="Batman Forever (Ultra-Nightmare)",
    tune_id="batman_forever__ultra_nightmare",
    tune_type="unkillable",
    difficulty="hard",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(265, 265), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(248, 248), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(247, 247), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(246, 246), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(220, 220), required_hero="Kreela Witch-Arm", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4")
    ],
    notes="Batman Forever · Ultra-Nightmare (boss SPD 190 Ultra-Nightmare) · by Napoleon Camembert · This is the unkillable version of the Batman 2:1 with Seeker. Can be made full auto and affinity friendly with a cleanser or block debuffs champion."
))


# Batman Forever — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/batman-forever/  |  calc: https://deadwoodjedi.info/cb/a13f12722f41ea60a25346fb3d7cec1dc0467a4f
_register(TuneDefinition(
    name="Batman Forever (Nightmare)",
    tune_id="batman_forever__nightmare",
    tune_type="unkillable",
    difficulty="hard",
    performance="1_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(265, 265), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(248, 248), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(247, 247), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(246, 246), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(220, 220), required_hero="Kreela Witch-Arm", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4")
    ],
    notes="Batman Forever · Nightmare (boss SPD 170 Nightmare) · by Napoleon Camembert · This is the unkillable version of the Batman 2:1 with Seeker. Can be made full auto and affinity friendly with a cleanser or block debuffs champion."
))


# Batman Forever — Brutal (Brutal)
# Source: https://deadwoodjedi.com/speed-tunes/batman-forever/  |  calc: https://deadwoodjedi.info/cb/5258c436ddd51c1f0432a42595307f6f2cb7de27
_register(TuneDefinition(
    name="Batman Forever (Brutal)",
    tune_id="batman_forever__brutal",
    tune_type="unkillable",
    difficulty="hard",
    performance="1_key_unm",
    affinities="all",
    cb_speed=160,
    slots=[
        TuneSlot(role="dps", speed_range=(265, 265), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(248, 248), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(247, 247), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(246, 246), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(220, 220), required_hero="Kreela Witch-Arm", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4")
    ],
    notes="Batman Forever · Brutal (boss SPD 160 Brutal) · by Napoleon Camembert · This is the unkillable version of the Batman 2:1 with Seeker. Can be made full auto and affinity friendly with a cleanser or block debuffs champion."
))


# Budget HeartKeeper Unkillable — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/budget-heartkeeper-unkillable/  |  calc: https://deadwoodjedi.info/cb/35619889f9592ac0c2344fa13c7e43b53392f439
_register(TuneDefinition(
    name="Budget HeartKeeper Unkillable (Ultra Nightmare)",
    tune_id="budget_heartkeeper_unkillable__ultra_nightmare",
    tune_type="unkillable",
    difficulty="extreme",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(175, 175), required_hero="Emic Trunkheart", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=1 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(121, 121), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(179, 179), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Budget HeartKeeper Unkillable · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Unkillable team requiring only Trunkheart and Painkeeper. Low Damage potential, but exceedingly low champ and speed requirements."
))


# Budget HeartKeeper Unkillable — Ultra Nightmare Spirit (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/budget-heartkeeper-unkillable/  |  calc: https://deadwoodjedi.info/cb/60c31cf57d58bc0810693bcc6b28c9d9e36f2f67
_register(TuneDefinition(
    name="Budget HeartKeeper Unkillable (Ultra Nightmare Spirit)",
    tune_id="budget_heartkeeper_unkillable__ultra_nightmare_spirit",
    tune_type="unkillable",
    difficulty="extreme",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(175, 175), required_hero="Emic Trunkheart", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=1 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(121, 121), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(179, 179), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Budget HeartKeeper Unkillable · Ultra Nightmare Spirit (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Unkillable team requiring only Trunkheart and Painkeeper. Low Damage potential, but exceedingly low champ and speed requirements."
))


# Budget HeartKeeper Unkillable — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/budget-heartkeeper-unkillable/  |  calc: https://deadwoodjedi.info/cb/43086f1d5ebb13e6e4d1022b1ffa44cad2f6f27b
_register(TuneDefinition(
    name="Budget HeartKeeper Unkillable (Nightmare)",
    tune_id="budget_heartkeeper_unkillable__nightmare",
    tune_type="unkillable",
    difficulty="extreme",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(175, 175), required_hero="Emic Trunkheart", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=1 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=4; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(121, 121), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(179, 179), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Budget HeartKeeper Unkillable · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi · Unkillable team requiring only Trunkheart and Painkeeper. Low Damage potential, but exceedingly low champ and speed requirements."
))


# Budget HeartKeeper Unkillable — Brutal (Brutal)
# Source: https://deadwoodjedi.com/speed-tunes/budget-heartkeeper-unkillable/  |  calc: https://deadwoodjedi.info/cb/a9ea87426644c3076aa194d2df30d68af1769eea
_register(TuneDefinition(
    name="Budget HeartKeeper Unkillable (Brutal)",
    tune_id="budget_heartkeeper_unkillable__brutal",
    tune_type="unkillable",
    difficulty="extreme",
    performance="2_key_unm",
    affinities="all",
    cb_speed=160,
    slots=[
        TuneSlot(role="dps", speed_range=(175, 175), required_hero="Emic Trunkheart", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=1 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=4; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(121, 121), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(179, 179), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Budget HeartKeeper Unkillable · Brutal (boss SPD 160 Brutal) · by DeadwoodJedi · Unkillable team requiring only Trunkheart and Painkeeper. Low Damage potential, but exceedingly low champ and speed requirements."
))


# Budget Maneater Unkillable — Ultra-Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/budget-maneater-unkillable/  |  calc: https://deadwoodjedi.info/cb/d7c74e2629b8eda47925b37b26389ee27a43105e
_register(TuneDefinition(
    name="Budget Maneater Unkillable (Ultra-Nightmare)",
    tune_id="budget_maneater_unkillable__ultra_nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(240, 240), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=5"),
TuneSlot(role="dps", speed_range=(220, 220), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(115, 115), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Budget Maneater Unkillable · Ultra-Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi and Rust · The Budget Maneater tune is perfect for those with a single Maneater and looking to put together a reliable Ultra-nightmare Clan Boss Team"
))


# Budget Maneater Unkillable — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/budget-maneater-unkillable/  |  calc: https://deadwoodjedi.info/cb/03d1c072e03ee9cf2713aea771528761a9374c18
_register(TuneDefinition(
    name="Budget Maneater Unkillable (Nightmare)",
    tune_id="budget_maneater_unkillable__nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(240, 240), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="dps", speed_range=(220, 220), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(121, 121), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Budget Maneater Unkillable · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi and Rust · The Budget Maneater tune is perfect for those with a single Maneater and looking to put together a reliable Ultra-nightmare Clan Boss Team"
))


# Budget Maneater Unkillable — Brutal (Brutal)
# Source: https://deadwoodjedi.com/speed-tunes/budget-maneater-unkillable/  |  calc: https://deadwoodjedi.info/cb/8a876815d3a8728550232879129e3212891de5de
_register(TuneDefinition(
    name="Budget Maneater Unkillable (Brutal)",
    tune_id="budget_maneater_unkillable__brutal",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=160,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(240, 240), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=5"),
TuneSlot(role="dps", speed_range=(220, 220), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=4; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(115, 115), required_hero="Rowan", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3")
    ],
    notes="Budget Maneater Unkillable · Brutal (boss SPD 160 Brutal) · by DeadwoodJedi and Rust · The Budget Maneater tune is perfect for those with a single Maneater and looking to put together a reliable Ultra-nightmare Clan Boss Team"
))


# Budget Maneater Unkillable - Extra Turn — Ultra-Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/budget-maneater-unkillable-extra-turn/  |  calc: https://deadwoodjedi.info/cb/9cd660fda73fdae82f34ec9ad93d0eec9903dbc0
_register(TuneDefinition(
    name="Budget Maneater Unkillable - Extra Turn (Ultra-Nightmare)",
    tune_id="budget_maneater_unkillable_extra_turn__ultra_nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(240, 240), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=5"),
TuneSlot(role="dps", speed_range=(220, 220), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=4; A3 pri=3 delay=2 CD=4"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Lord Shazar", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=2 delay=0 CD=5"),
TuneSlot(role="dps", speed_range=(115, 115), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Budget Maneater Unkillable - Extra Turn · Ultra-Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · A variation of the popular Budget Unkillable that uses a champion with an extra turn such as Lord Shazar or Cruetraxa. A great option to increase your Damage per Key."
))


# Budget Maneater Unkillable – Ninja — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/budget-maneater-unkillable-ninja/  |  calc: https://deadwoodjedi.info/cb/637aea3438628523b82fc7935f8db8a9d98f10bd
_register(TuneDefinition(
    name="Budget Maneater Unkillable – Ninja (Ultra Nightmare)",
    tune_id="budget_maneater_unkillable_ninja__ultra_nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(240, 240), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=5"),
TuneSlot(role="dps", speed_range=(220, 220), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="ninja_tm_boost", speed_range=(161, 161), required_hero="Ninja", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(115, 115), required_hero="Gravechill Killer", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3")
    ],
    notes="Budget Maneater Unkillable – Ninja · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · A variation of the popular Budget Unkillable that uses a very annoying champ to tune, Ninja! A great option to increase your Damage per Key."
))


# Budget Maneater Unkillable – Ninja — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/budget-maneater-unkillable-ninja/  |  calc: https://deadwoodjedi.info/cb/0edcb93efa4603c85ecf1afab034abb6d8adb766
_register(TuneDefinition(
    name="Budget Maneater Unkillable – Ninja (Nightmare)",
    tune_id="budget_maneater_unkillable_ninja__nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(240, 240), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="dps", speed_range=(220, 220), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="ninja_tm_boost", speed_range=(161, 161), required_hero="Ninja", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(121, 121), required_hero="Gravechill Killer", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3")
    ],
    notes="Budget Maneater Unkillable – Ninja · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi · A variation of the popular Budget Unkillable that uses a very annoying champ to tune, Ninja! A great option to increase your Damage per Key."
))


# Budget Maneater Unkillable – Ninja — Brutal (Brutal)
# Source: https://deadwoodjedi.com/speed-tunes/budget-maneater-unkillable-ninja/  |  calc: https://deadwoodjedi.info/cb/3eff31f3eb8eedc10e0c6ce48903e1cee505409b
_register(TuneDefinition(
    name="Budget Maneater Unkillable – Ninja (Brutal)",
    tune_id="budget_maneater_unkillable_ninja__brutal",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=160,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(240, 240), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=5"),
TuneSlot(role="dps", speed_range=(220, 220), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=2 CD=4"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="ninja_tm_boost", speed_range=(161, 161), required_hero="Ninja", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(116, 116), required_hero="Gravechill Killer", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3")
    ],
    notes="Budget Maneater Unkillable – Ninja · Brutal (boss SPD 160 Brutal) · by DeadwoodJedi · A variation of the popular Budget Unkillable that uses a very annoying champ to tune, Ninja! A great option to increase your Damage per Key."
))


# Budget Myth Heir — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/budget-myth-heir/  |  calc: https://deadwoodjedi.info/cb/728ccd8c0ba2a6fc5b1fd292fe4fda3d9b9d3152
_register(TuneDefinition(
    name="Budget Myth Heir (Ultra Nightmare)",
    tune_id="budget_myth_heir__ultra_nightmare",
    tune_type="unkillable",
    difficulty="easy",
    performance="3_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="ninja_tm_boost", speed_range=(234, 234), required_hero="Ninja", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(189, 189), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=1 CD=4; A3 pri=3 delay=2 CD=4"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="block_damage", speed_range=(249, 249), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(238, 238), required_hero="Heiress", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Budget Myth Heir · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by u/Steffenrd · Affinity friendly single demytha unkillable team!"
))


# Budget Myth Heir — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/budget-myth-heir/  |  calc: https://deadwoodjedi.info/cb/5bc9b35ff5f4c3ce26348482a95a5b7430ed41b9
_register(TuneDefinition(
    name="Budget Myth Heir (Nightmare)",
    tune_id="budget_myth_heir__nightmare",
    tune_type="unkillable",
    difficulty="easy",
    performance="3_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="ninja_tm_boost", speed_range=(234, 234), required_hero="Ninja", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=1 CD=4; A3 pri=3 delay=2 CD=4"),
TuneSlot(role="dps", speed_range=(189, 189), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="block_damage", speed_range=(249, 249), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(238, 238), required_hero="Heiress", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Budget Myth Heir · Nightmare (boss SPD 170 Nightmare) · by u/Steffenrd · Affinity friendly single demytha unkillable team!"
))


# CatEater — Ultra-Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/cateater/  |  calc: https://deadwoodjedi.info/cb/41257f31c4c8f18e321f264455c7ac512aa79e53
_register(TuneDefinition(
    name="CatEater (Ultra-Nightmare)",
    tune_id="cateater__ultra_nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(255, 255), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="dps", speed_range=(213, 213), required_hero="Kreela Witch-Arm", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(218, 218), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(179, 179), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(192, 192), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=4")
    ],
    notes="CatEater · Ultra-Nightmare (boss SPD 190 Ultra-Nightmare) · by Xaavik, Facemelter, Optilink · Unkillable Team utilizing Helicath and Maneater to stay unkillable and affinity friendly. 1 Key UNM is possible with very good gear and meta champions."
))


# CatEater — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/cateater/  |  calc: https://deadwoodjedi.info/cb/59461c92bca9774c90923b3c48e8d65495f13447
_register(TuneDefinition(
    name="CatEater (Nightmare)",
    tune_id="cateater__nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(255, 255), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="dps", speed_range=(213, 213), required_hero="Kreela Witch-Arm", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(218, 218), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=5 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(179, 179), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(192, 192), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=4")
    ],
    notes="CatEater · Nightmare (boss SPD 170 Nightmare) · by Xaavik, Facemelter, Optilink · Unkillable Team utilizing Helicath and Maneater to stay unkillable and affinity friendly. 1 Key UNM is possible with very good gear and meta champions."
))


# CatEater — Brutal (Brutal)
# Source: https://deadwoodjedi.com/speed-tunes/cateater/  |  calc: https://deadwoodjedi.info/cb/0d67724a7c9ceb63866ac51fc49f77c1276412d6
_register(TuneDefinition(
    name="CatEater (Brutal)",
    tune_id="cateater__brutal",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=160,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(255, 255), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=5"),
TuneSlot(role="dps", speed_range=(213, 213), required_hero="Kreela Witch-Arm", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(218, 218), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=4 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(179, 179), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(192, 192), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4")
    ],
    notes="CatEater · Brutal (boss SPD 160 Brutal) · by Xaavik, Facemelter, Optilink · Unkillable Team utilizing Helicath and Maneater to stay unkillable and affinity friendly. 1 Key UNM is possible with very good gear and meta champions."
))


# Deacon Forever — UNM / NM / Brutal (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/deacon-forever/  |  calc: https://deadwoodjedi.info/cb/cc8341c4d47d57a38ed2662da3dbbad833677e4b
_register(TuneDefinition(
    name="Deacon Forever (UNM / NM / Brutal)",
    tune_id="deacon_forever__unm_nm_brutal",
    tune_type="unkillable",
    difficulty="expert",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(226, 226), required_hero="Deacon Armstrong", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(285, 285), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(249, 249), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(253, 253), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(201, 201), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Deacon Forever · UNM / NM / Brutal (boss SPD 190 Ultra-Nightmare) · by Sipho879 · 2:1 Unkillable with Deacon Armstrong and two Block Damage or Unkillable champs."
))


# Deacon Forever — Brutal (Brutal)
# Source: https://deadwoodjedi.com/speed-tunes/deacon-forever/  |  calc: https://deadwoodjedi.info/cb/6785fbc66a0b57f4b914154cc6c45024dca400e2
_register(TuneDefinition(
    name="Deacon Forever (Brutal)",
    tune_id="deacon_forever__brutal",
    tune_type="unkillable",
    difficulty="expert",
    performance="1_key_unm",
    affinities="all",
    cb_speed=160,
    slots=[
        TuneSlot(role="dps", speed_range=(226, 226), required_hero="Deacon Armstrong", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(278, 278), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(253, 253), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(254, 254), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(201, 201), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Deacon Forever · Brutal (boss SPD 160 Brutal) · by Sipho879 · 2:1 Unkillable with Deacon Armstrong and two Block Damage or Unkillable champs."
))


# Deacon Forever — Hard (Hard)
# Source: https://deadwoodjedi.com/speed-tunes/deacon-forever/  |  calc: https://deadwoodjedi.info/cb/bbed71ea1b61d74266740df90e1e558316666901
_register(TuneDefinition(
    name="Deacon Forever (Hard)",
    tune_id="deacon_forever__hard",
    tune_type="unkillable",
    difficulty="expert",
    performance="1_key_unm",
    affinities="all",
    cb_speed=140,
    slots=[
        TuneSlot(role="dps", speed_range=(226, 226), required_hero="Deacon Armstrong", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(278, 278), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(253, 253), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(254, 254), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(201, 201), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Deacon Forever · Hard (boss SPD 140 Hard) · by Sipho879 · 2:1 Unkillable with Deacon Armstrong and two Block Damage or Unkillable champs."
))


# DeaconEater — UNM / NM / Brutal (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/deaconeater/  |  calc: https://deadwoodjedi.info/cb/4ed187c510d87a11500840b7b93dd9c2346ec531
_register(TuneDefinition(
    name="DeaconEater (UNM / NM / Brutal)",
    tune_id="deaconeater__unm_nm_brutal",
    tune_type="unkillable",
    difficulty="hard",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(226, 226), required_hero="Deacon Armstrong", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="fast_uk", speed_range=(286, 286), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=5"),
TuneSlot(role="fast_uk", speed_range=(250, 250), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="dps", speed_range=(249, 249), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(201, 201), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4")
    ],
    notes="DeaconEater · UNM / NM / Brutal (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · 2:1 Unkillable with Deacon Armstrong, Pain Keeper, and two Maneaters."
))


# DeaconEater — Full auto (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/deaconeater/  |  calc: https://deadwoodjedi.info/cb/39a28fa75794646859c366d91ee422f039cf01b4
_register(TuneDefinition(
    name="DeaconEater (Full auto)",
    tune_id="deaconeater__full_auto",
    tune_type="unkillable",
    difficulty="hard",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(226, 226), required_hero="Deacon Armstrong", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="fast_uk", speed_range=(278, 278), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=5"),
TuneSlot(role="fast_uk", speed_range=(253, 253), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="dps", speed_range=(252, 252), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(201, 201), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4")
    ],
    notes="DeaconEater · Full auto (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · 2:1 Unkillable with Deacon Armstrong, Pain Keeper, and two Maneaters."
))


# Double Demytha — UNM / NM (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/double-demytha/  |  calc: https://deadwoodjedi.info/cb/42d082ab9ed5f1e0ac230cb08b9ce7148847b9f6
_register(TuneDefinition(
    name="Double Demytha (UNM / NM)",
    tune_id="double_demytha__unm_nm",
    tune_type="unkillable",
    difficulty="easy",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="block_damage", speed_range=(285, 285), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="block_damage", speed_range=(254, 254), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(169, 169), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(169, 169), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(168, 168), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="Double Demytha · UNM / NM (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Double Demytha's Double the fun! Block damage or cleanse to stay affinity friendly."
))


# Double Warcaster v2 — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/double-warcaster-v2/  |  calc: https://deadwoodjedi.info/cb/cf28362d06c7ff110f9751e801ec344983edb6e1
_register(TuneDefinition(
    name="Double Warcaster v2 (Ultra Nightmare)",
    tune_id="double_warcaster_v2__ultra_nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(247, 247), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=2 CD=4"),
TuneSlot(role="dps", speed_range=(218, 218), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(219, 219), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(190, 190), required_hero="Tatura Rimehide", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(225, 225), required_hero="Fahrakin the Fat", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4")
    ],
    notes="Double Warcaster v2 · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by Cyborg · Double Warcaster blocks the AOEs and Skullcrusher or any champ that won't die easily takes the stun."
))


# Double Warcaster v2 — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/double-warcaster-v2/  |  calc: https://deadwoodjedi.info/cb/c2d54ba5ef8bcfe60f1969d1f4289ae45e62d505
_register(TuneDefinition(
    name="Double Warcaster v2 (Nightmare)",
    tune_id="double_warcaster_v2__nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(247, 247), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=2 CD=4"),
TuneSlot(role="dps", speed_range=(218, 218), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4; Lore of Steel"),
TuneSlot(role="dps", speed_range=(218, 218), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(190, 190), required_hero="Tatura Rimehide", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(225, 225), required_hero="Fahrakin the Fat", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4")
    ],
    notes="Double Warcaster v2 · Nightmare (boss SPD 170 Nightmare) · by Cyborg · Double Warcaster blocks the AOEs and Skullcrusher or any champ that won't die easily takes the stun."
))


# Easy Double Maneater — Ultra-Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/easy-double-maneater/  |  calc: https://deadwoodjedi.info/cb/e45fe7b976359f36d229b89f33cca06fc8f11473
_register(TuneDefinition(
    name="Easy Double Maneater (Ultra-Nightmare)",
    tune_id="easy_double_maneater__ultra_nightmare",
    tune_type="unkillable",
    difficulty="easy",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(220, 220), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=5"),
TuneSlot(role="fast_uk", speed_range=(215, 215), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=4 CD=5"),
TuneSlot(role="dps", speed_range=(175, 175), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(168, 168), required_hero="Bulwark", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Easy Double Maneater · Ultra-Nightmare (boss SPD 190 Ultra-Nightmare) · by Frugus · Easiest Maneater Unkillable that utilizes 2 Maneaters to make the tune fully unkillable. You have more flexibility with DPS slots compared to the Budget Unkillable allowing more damage per key."
))


# Easy Double Maneater — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/easy-double-maneater/  |  calc: https://deadwoodjedi.info/cb/aa6428723d8657aef0192993ee43487338f29257
_register(TuneDefinition(
    name="Easy Double Maneater (Nightmare)",
    tune_id="easy_double_maneater__nightmare",
    tune_type="unkillable",
    difficulty="easy",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(220, 220), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=5"),
TuneSlot(role="fast_uk", speed_range=(215, 215), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=4 CD=5"),
TuneSlot(role="dps", speed_range=(175, 175), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(168, 168), required_hero="Bulwark", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Easy Double Maneater · Nightmare (boss SPD 170 Nightmare) · by Frugus · Easiest Maneater Unkillable that utilizes 2 Maneaters to make the tune fully unkillable. You have more flexibility with DPS slots compared to the Budget Unkillable allowing more damage per key."
))


# Easy Double Maneater — Brutal (Brutal)
# Source: https://deadwoodjedi.com/speed-tunes/easy-double-maneater/  |  calc: https://deadwoodjedi.info/cb/879ab400b21ff8f94885b453df13a94da3fdf4d1
_register(TuneDefinition(
    name="Easy Double Maneater (Brutal)",
    tune_id="easy_double_maneater__brutal",
    tune_type="unkillable",
    difficulty="easy",
    performance="2_key_unm",
    affinities="all",
    cb_speed=160,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(220, 220), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="fast_uk", speed_range=(215, 215), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=5"),
TuneSlot(role="dps", speed_range=(175, 175), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(168, 168), required_hero="Bulwark", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Easy Double Maneater · Brutal (boss SPD 160 Brutal) · by Frugus · Easiest Maneater Unkillable that utilizes 2 Maneaters to make the tune fully unkillable. You have more flexibility with DPS slots compared to the Budget Unkillable allowing more damage per key."
))


# Fast Hellcat Unkillable — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/fast-hellcat-unkillable/  |  calc: https://deadwoodjedi.info/cb/9b98f20934c00a7299f1c7b85dd5058104454718
_register(TuneDefinition(
    name="Fast Hellcat Unkillable (Ultra Nightmare)",
    tune_id="fast_hellcat_unkillable__ultra_nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps_4to3", speed_range=(245, 245), required_hero="4:3 DPS", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4; Lore of Steel"),
TuneSlot(role="dps", speed_range=(241, 241), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4; Lore of Steel"),
TuneSlot(role="dps", speed_range=(195, 195), required_hero=None, opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(193, 193), required_hero=None, opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(191, 191), required_hero="BLOCK DEBUFFS", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=1 CD=3; A3 pri=3 delay=0 CD=4")
    ],
    notes="Fast Hellcat Unkillable · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Unkillable team using Helicath to block damage on the clan boss AOE hits and his Shield to prevent dying from the stun. This version has a 4:3 ratio champion to provide more damage. 1 Key UNM is possible with very good gear and meta champions."
))


# Fast Hellcat Unkillable — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/fast-hellcat-unkillable/  |  calc: https://deadwoodjedi.info/cb/2261777999bbf766e5a6ce3045d0e74854497b29
_register(TuneDefinition(
    name="Fast Hellcat Unkillable (Nightmare)",
    tune_id="fast_hellcat_unkillable__nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps_4to3", speed_range=(245, 245), required_hero="4:3 DPS", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4; Lore of Steel"),
TuneSlot(role="dps", speed_range=(241, 241), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4; Lore of Steel"),
TuneSlot(role="dps", speed_range=(195, 195), required_hero=None, opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(193, 193), required_hero=None, opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="cleanser", speed_range=(191, 191), required_hero="CLEANSER", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Fast Hellcat Unkillable · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi · Unkillable team using Helicath to block damage on the clan boss AOE hits and his Shield to prevent dying from the stun. This version has a 4:3 ratio champion to provide more damage. 1 Key UNM is possible with very good gear and meta champions."
))


# Fast Tower Skullcrusher Unkillable — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/fast-tower-skullcrusher-unkillable-copy/  |  calc: https://deadwoodjedi.info/cb/6af320c65b2fe28f8dfc963c60d85352241c0490
_register(TuneDefinition(
    name="Fast Tower Skullcrusher Unkillable (Ultra Nightmare)",
    tune_id="fast_tower_skullcrusher_unkillable_copy__ultra_nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="3_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(244, 244), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(241, 241), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(195, 195), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(193, 193), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(191, 191), required_hero="Bulwark", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Fast Tower Skullcrusher Unkillable · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Unkillable team using Roschard The Tower to block damage on the clan boss AOE hits and skullcrusher to tank the stun with his self unkillable. 2 Key UNM is possible with very good gear."
))


# Fast Tower Skullcrusher Unkillable — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/fast-tower-skullcrusher-unkillable-copy/  |  calc: https://deadwoodjedi.info/cb/1d0372c5ad89f6474446e04b022c6f5870143435
_register(TuneDefinition(
    name="Fast Tower Skullcrusher Unkillable (Nightmare)",
    tune_id="fast_tower_skullcrusher_unkillable_copy__nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="3_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(244, 244), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(241, 241), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(195, 195), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=1 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(193, 193), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(191, 191), required_hero="Bulwark", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Fast Tower Skullcrusher Unkillable · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi · Unkillable team using Roschard The Tower to block damage on the clan boss AOE hits and skullcrusher to tank the stun with his self unkillable. 2 Key UNM is possible with very good gear."
))


# Fast Tower Skullcrusher w/ 4:3 — Fast Ultra-Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/fast-tower-skullcrusher-w-43/  |  calc: https://deadwoodjedi.info/cb/44b25c8fe31c724984d6a48db922cb068cdbc059
_register(TuneDefinition(
    name="Fast Tower Skullcrusher w/ 4:3 (Fast Ultra-Nightmare)",
    tune_id="fast_tower_skullcrusher_w_43__fast_ultra_nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(241, 241), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(257, 257), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(240, 240), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=4"),
TuneSlot(role="dps", speed_range=(192, 192), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(191, 191), required_hero="Bulwark", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Fast Tower Skullcrusher w/ 4:3 · Fast Ultra-Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Fast Tower + Skullcrusher Unkillable with a 4:3 champ to increase damage or debuffs."
))


# Fast Tower Skullcrusher w/ 4:3 — Slow Ultra-Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/fast-tower-skullcrusher-w-43/  |  calc: https://deadwoodjedi.info/cb/d18dd04def03874b1db7c1e994173e23e54e432a
_register(TuneDefinition(
    name="Fast Tower Skullcrusher w/ 4:3 (Slow Ultra-Nightmare)",
    tune_id="fast_tower_skullcrusher_w_43__slow_ultra_nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(221, 221), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(240, 240), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(220, 220), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=4"),
TuneSlot(role="dps", speed_range=(192, 192), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(171, 171), required_hero="Bulwark", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Fast Tower Skullcrusher w/ 4:3 · Slow Ultra-Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Fast Tower + Skullcrusher Unkillable with a 4:3 champ to increase damage or debuffs."
))


# Heart Eater — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/heart-eater/  |  calc: https://deadwoodjedi.info/cb/079fca47e3415d6670f632041881c3eb33850ff0
_register(TuneDefinition(
    name="Heart Eater (Ultra Nightmare)",
    tune_id="heart_eater__ultra_nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(245, 245), required_hero="Emic Trunkheart", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="fast_uk", speed_range=(240, 240), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Kreela Witch-Arm", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Fahrakin the Fat", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Longbeard", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=2; A3 pri=3 delay=0 CD=4")
    ],
    notes="Heart Eater · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by SIpho879 · Easy Maneater and Emic Trunkheart 2 key UNM comp with the possibility of a 1 key with really crazy gear."
))


# Heart Eater — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/heart-eater/  |  calc: https://deadwoodjedi.info/cb/9374fb7b373e99a0d4c64addd421f788978a8059
_register(TuneDefinition(
    name="Heart Eater (Nightmare)",
    tune_id="heart_eater__nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(245, 245), required_hero="Emic Trunkheart", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="fast_uk", speed_range=(240, 240), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=5"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Kreela Witch-Arm", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Fahrakin the Fat", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Longbeard", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=2; A3 pri=3 delay=0 CD=4")
    ],
    notes="Heart Eater · Nightmare (boss SPD 170 Nightmare) · by SIpho879 · Easy Maneater and Emic Trunkheart 2 key UNM comp with the possibility of a 1 key with really crazy gear."
))


# Man Salad — Ultra Nightmare - BOBO (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/man-salad/  |  calc: https://deadwoodjedi.info/cb/56bfc386cd83c1ef03f6201edec45bac35b78213
_register(TuneDefinition(
    name="Man Salad (Ultra Nightmare - BOBO)",
    tune_id="man_salad__ultra_nightmare_bobo",
    tune_type="unkillable",
    difficulty="moderate",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(252, 252), required_hero="Ma'Shalled", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=1 CD=3; A3 pri=2 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(251, 251), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="fast_uk", speed_range=(225, 225), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="fast_uk", speed_range=(205, 205), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=5"),
TuneSlot(role="dps", speed_range=(186, 186), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4")
    ],
    notes="Man Salad · Ultra Nightmare - BOBO (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Using Double Maneater and Ma'Shalled to achieve an affinity friendly 2:1 unkillable team."
))


# Man Salad — Ultra-Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/man-salad/  |  calc: https://deadwoodjedi.info/cb/c7cc9bb8528953680d736712d3cab9f5cabbd5f4
_register(TuneDefinition(
    name="Man Salad (Ultra-Nightmare)",
    tune_id="man_salad__ultra_nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(252, 252), required_hero="Ma'Shalled", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=1 CD=3; A3 pri=2 delay=0 CD=3"),
TuneSlot(role="fast_uk", speed_range=(251, 251), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=4 CD=5"),
TuneSlot(role="fast_uk", speed_range=(225, 225), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=5 CD=5"),
TuneSlot(role="dps", speed_range=(205, 205), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(186, 186), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=4; A3 pri=3 delay=0 CD=4")
    ],
    notes="Man Salad · Ultra-Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Using Double Maneater and Ma'Shalled to achieve an affinity friendly 2:1 unkillable team."
))


# Man Salad — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/man-salad/  |  calc: https://deadwoodjedi.info/cb/6a3a537af806229336c2d50955bcb484eee06c63
_register(TuneDefinition(
    name="Man Salad (Nightmare)",
    tune_id="man_salad__nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="1_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(252, 252), required_hero="Ma'Shalled", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=1 CD=3; A3 pri=2 delay=0 CD=3"),
TuneSlot(role="fast_uk", speed_range=(251, 251), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=5"),
TuneSlot(role="fast_uk", speed_range=(225, 225), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=8 CD=5"),
TuneSlot(role="dps", speed_range=(205, 205), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(186, 186), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=3 CD=4")
    ],
    notes="Man Salad · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi · Using Double Maneater and Ma'Shalled to achieve an affinity friendly 2:1 unkillable team."
))


# Man Seeks God — Godseeker Aniri UNM and NM (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/man-seeks-god/  |  calc: https://deadwoodjedi.info/cb/15582482b4d7479547c5f0834643c88328fec894
_register(TuneDefinition(
    name="Man Seeks God (Godseeker Aniri UNM and NM)",
    tune_id="man_seeks_god__godseeker_aniri_unm_and_nm",
    tune_type="unkillable",
    difficulty="extreme",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(254, 254), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=5"),
TuneSlot(role="dps", speed_range=(218, 218), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=4 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(214, 214), required_hero="Godseeker Aniri", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(191, 191), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(191, 191), required_hero="Fahrakin the Fat", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4")
    ],
    notes="Man Seeks God · Godseeker Aniri UNM and NM (boss SPD 190 Ultra-Nightmare) · by Facemelter, Optilink, Robohobobobo · Using Revive on Death mechanic with Maneater to stay unkillable for 50 turns."
))


# Man Seeks God — Cardiel UNM and NM (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/man-seeks-god/  |  calc: https://deadwoodjedi.info/cb/f79d3d331b8f05030354f157aa6558d474e186db
_register(TuneDefinition(
    name="Man Seeks God (Cardiel UNM and NM)",
    tune_id="man_seeks_god__cardiel_unm_and_nm",
    tune_type="unkillable",
    difficulty="extreme",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(236, 236), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=5"),
TuneSlot(role="dps", speed_range=(198, 198), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=4 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(196, 196), required_hero="Cardiel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(173, 173), required_hero="Longbeard", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=2; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Fahrakin the Fat", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=4")
    ],
    notes="Man Seeks God · Cardiel UNM and NM (boss SPD 190 Ultra-Nightmare) · by Facemelter, Optilink, Robohobobobo · Using Revive on Death mechanic with Maneater to stay unkillable for 50 turns."
))


# Man Seeks God — Cardiel and Ninja UNM and NM (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/man-seeks-god/  |  calc: https://deadwoodjedi.info/cb/0e44a9876b288b3d26f8306d70658cf5df13ba92
_register(TuneDefinition(
    name="Man Seeks God (Cardiel and Ninja UNM and NM)",
    tune_id="man_seeks_god__cardiel_and_ninja_unm_and_nm",
    tune_type="unkillable",
    difficulty="extreme",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(236, 236), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=5"),
TuneSlot(role="dps", speed_range=(198, 198), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="ninja_tm_boost", speed_range=(169, 169), required_hero="Ninja", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4; Lore of Steel"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(171, 171), required_hero="Cardiel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=1 CD=4")
    ],
    notes="Man Seeks God · Cardiel and Ninja UNM and NM (boss SPD 190 Ultra-Nightmare) · by Facemelter, Optilink, Robohobobobo · Using Revive on Death mechanic with Maneater to stay unkillable for 50 turns."
))


# ManSeekNia — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/manseeknia/  |  calc: https://deadwoodjedi.info/cb/7bf0e5b0f0352a99a38758a62ad62e3d0468c21c
_register(TuneDefinition(
    name="ManSeekNia (Ultra Nightmare)",
    tune_id="manseeknia__ultra_nightmare",
    tune_type="unkillable",
    difficulty="easy",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(192, 192), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=5"),
TuneSlot(role="dps", speed_range=(183, 183), required_hero="Godseeker Aniri", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=0; A3 pri=1 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(182, 182), required_hero="White Dryad Nia", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(180, 180), required_hero="Chani", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(180, 180), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3")
    ],
    notes="ManSeekNia · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · \\\"The LOWEST Clan Boss Speeds Out There!\\\" - DeadwoodJedi"
))


# ManSeekNia — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/manseeknia/  |  calc: https://deadwoodjedi.info/cb/dd934c84f1d114e63d153686858c359deee3be20
_register(TuneDefinition(
    name="ManSeekNia (Nightmare)",
    tune_id="manseeknia__nightmare",
    tune_type="unkillable",
    difficulty="easy",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(192, 192), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="dps", speed_range=(181, 181), required_hero="Godseeker Aniri", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=0; A3 pri=1 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(181, 181), required_hero="White Dryad Nia", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Chani", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(178, 178), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3")
    ],
    notes="ManSeekNia · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi · \\\"The LOWEST Clan Boss Speeds Out There!\\\" - DeadwoodJedi"
))


# ManTower Fast — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/mantower-fast/  |  calc: https://deadwoodjedi.info/cb/9d9c3d32755672fc95ca8580c0dd0a27f651c2c5
_register(TuneDefinition(
    name="ManTower Fast (Ultra Nightmare)",
    tune_id="mantower_fast__ultra_nightmare",
    tune_type="unkillable",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(287, 287), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="dps", speed_range=(239, 239), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=4"),
TuneSlot(role="dps", speed_range=(181, 181), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(221, 221), required_hero="Kreela Witch-Arm", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=3; A3 pri=3 delay=3 CD=4"),
TuneSlot(role="dps", speed_range=(171, 171), required_hero="Septimus", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0")
    ],
    notes="ManTower Fast · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by iAanGGaming · Fast Tower and Maneater Stays Unkillable and Affinity Friendly."
))


# ManTower Fast — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/mantower-fast/  |  calc: https://deadwoodjedi.info/cb/6a67d0d8b6abf6e3a886d47adcaba3686dff297d
_register(TuneDefinition(
    name="ManTower Fast (Nightmare)",
    tune_id="mantower_fast__nightmare",
    tune_type="unkillable",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(287, 287), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=5"),
TuneSlot(role="dps", speed_range=(244, 244), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(169, 169), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(221, 221), required_hero="Kreela Witch-Arm", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(171, 171), required_hero="Septimus", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0")
    ],
    notes="ManTower Fast · Nightmare (boss SPD 170 Nightmare) · by iAanGGaming · Fast Tower and Maneater Stays Unkillable and Affinity Friendly."
))


# ManTower Fast — Brutal (Brutal)
# Source: https://deadwoodjedi.com/speed-tunes/mantower-fast/  |  calc: https://deadwoodjedi.info/cb/9b992c17c2804892d6493ccb69f2e33736eedca8
_register(TuneDefinition(
    name="ManTower Fast (Brutal)",
    tune_id="mantower_fast__brutal",
    tune_type="unkillable",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all",
    cb_speed=160,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(287, 287), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=5"),
TuneSlot(role="dps", speed_range=(239, 239), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(171, 171), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(178, 178), required_hero="Kreela Witch-Arm", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(171, 171), required_hero="Septimus", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0")
    ],
    notes="ManTower Fast · Brutal (boss SPD 160 Brutal) · by iAanGGaming · Fast Tower and Maneater Stays Unkillable and Affinity Friendly."
))


# ManTower Slow — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/mantower-slow/  |  calc: https://deadwoodjedi.info/cb/6d65a3abaf33b5cd3aa38683ef91d0cff6119b35
_register(TuneDefinition(
    name="ManTower Slow (Ultra Nightmare)",
    tune_id="mantower_slow__ultra_nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(249, 249), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=5"),
TuneSlot(role="dps", speed_range=(191, 191), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4; Lore of Steel"),
TuneSlot(role="dps", speed_range=(217, 217), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(216, 216), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(192, 192), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="ManTower Slow · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by Skratch AK47 · Uses a drifting 5:4 Maneater and a 1:1 UK champ to become unkillable."
))


# MummyMan — Ultra-Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/mummyman/  |  calc: https://deadwoodjedi.info/cb/a866933e937b43252a7b09748341faf05d608509
_register(TuneDefinition(
    name="MummyMan (Ultra-Nightmare)",
    tune_id="mummyman__ultra_nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(284, 284), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="dps", speed_range=(129, 129), required_hero="High Khatun", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=1 CD=3; A3 pri=2 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(164, 164), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Rathalos Blademaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(256, 256), required_hero="khafru", opening=['A1'], skill_priority=['A2', 'A1', 'unkillable'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; unkillable pri=3 delay=3 CD=5")
    ],
    notes="MummyMan · Ultra-Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Utilize Maneater and Khafru to create an affinity friendly unkillable team for UNM and NM Clan Boss."
))


# MummyMan — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/mummyman/  |  calc: https://deadwoodjedi.info/cb/216c5e9c807ba87d3bdc36addb8759cba69f6227
_register(TuneDefinition(
    name="MummyMan (Nightmare)",
    tune_id="mummyman__nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(284, 284), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="dps", speed_range=(129, 129), required_hero="High Khatun", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=1 CD=3; A3 pri=2 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(164, 164), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Rathalos Blademaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(256, 256), required_hero="khafru", opening=['A1'], skill_priority=['A2', 'A1', 'unkillable'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; unkillable pri=3 delay=3 CD=5")
    ],
    notes="MummyMan · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi · Utilize Maneater and Khafru to create an affinity friendly unkillable team for UNM and NM Clan Boss."
))


# Myth Buster — UNM, NM, Brutal (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-buster/  |  calc: https://deadwoodjedi.info/cb/ee5bb55af3243b9f73b33c2c413299a3ba86d27e
_register(TuneDefinition(
    name="Myth Buster (UNM, NM, Brutal)",
    tune_id="myth_buster__unm_nm_brutal",
    tune_type="unkillable",
    difficulty="expert",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="block_damage", speed_range=(297, 297), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(302, 302), required_hero="Lydia the Deathsiren", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=2 delay=0 CD=3; Lore of Steel"),
TuneSlot(role="dps", speed_range=(187, 187), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0; Lore of Steel"),
TuneSlot(role="dps", speed_range=(209, 209), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(265, 265), required_hero="Cardiel", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=0 CD=3; A3 pri=3 delay=0 CD=4; Lore of Steel")
    ],
    notes="Myth Buster · UNM, NM, Brutal (boss SPD 190 Ultra-Nightmare) · by Facemelter · Demytha Unkillable team utilizing Cardiel’s for his speed aura and to stay affinity friendly."
))


# Myth Buster — Ninja Variant (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-buster/  |  calc: https://deadwoodjedi.info/cb/30f83442aeafbb3be7e60e04041f078d2bc9bc47
_register(TuneDefinition(
    name="Myth Buster (Ninja Variant)",
    tune_id="myth_buster__ninja_variant",
    tune_type="unkillable",
    difficulty="expert",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="block_damage", speed_range=(297, 297), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(302, 302), required_hero="Lydia the Deathsiren", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=2 delay=0 CD=3; Lore of Steel"),
TuneSlot(role="dps", speed_range=(185, 185), required_hero="Cardiel", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=0 CD=3; A3 pri=3 delay=0 CD=4; Lore of Steel"),
TuneSlot(role="dps", speed_range=(209, 209), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="ninja_tm_boost", speed_range=(265, 265), required_hero="Ninja", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=0 CD=3; A3 pri=3 delay=0 CD=4; Lore of Steel")
    ],
    notes="Myth Buster · Ninja Variant (boss SPD 190 Ultra-Nightmare) · by Facemelter · Demytha Unkillable team utilizing Cardiel’s for his speed aura and to stay affinity friendly."
))


# Myth Deacon — UNM/NM (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-deacon/  |  calc: https://deadwoodjedi.info/cb/2e85cbf25febd4aba294f7527ccd78e72eff8523
_register(TuneDefinition(
    name="Myth Deacon (UNM/NM)",
    tune_id="myth_deacon__unm_nm",
    tune_type="unkillable",
    difficulty="hard",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="block_damage", speed_range=(310, 310), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(309, 309), required_hero="High Khatun", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=2 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(198, 198), required_hero="Deacon Armstrong", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(203, 203), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="Myth Deacon · UNM/NM (boss SPD 190 Ultra-Nightmare) · by TheDragonsBeard · This speed tune is ideal for anyone looking to utilise Demytha in a 2:1 Fully Unkillable Comp without Seeker. It uses Deacon Armstrong and High Khatun to fill Turn Meter and Increase Speed whilst giving 2 spots for damage. Speeds are quite high so will be challenging gear wise."
))


# Myth Deacon — Affinity Friendly (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-deacon/  |  calc: https://deadwoodjedi.info/cb/1c3a26dc7e595e1187bf038b581f909e541e43b0
_register(TuneDefinition(
    name="Myth Deacon (Affinity Friendly)",
    tune_id="myth_deacon__affinity_friendly",
    tune_type="unkillable",
    difficulty="hard",
    performance="1_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="block_damage", speed_range=(310, 310), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(309, 309), required_hero="High Khatun", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=2 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(198, 198), required_hero="Deacon Armstrong", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(203, 203), required_hero="Underpriest Brogni", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="Myth Deacon · Affinity Friendly (boss SPD 170 Nightmare) · by TheDragonsBeard · This speed tune is ideal for anyone looking to utilise Demytha in a 2:1 Fully Unkillable Comp without Seeker. It uses Deacon Armstrong and High Khatun to fill Turn Meter and Increase Speed whilst giving 2 spots for damage. Speeds are quite high so will be challenging gear wise."
))


# Myth Deacon — Brutal (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-deacon/  |  calc: https://deadwoodjedi.info/cb/1c3a26dc7e595e1187bf038b581f909e541e43b0
_register(TuneDefinition(
    name="Myth Deacon (Brutal)",
    tune_id="myth_deacon__brutal",
    tune_type="unkillable",
    difficulty="hard",
    performance="1_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="block_damage", speed_range=(310, 310), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(309, 309), required_hero="High Khatun", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=2 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(198, 198), required_hero="Deacon Armstrong", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(203, 203), required_hero="Underpriest Brogni", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="Myth Deacon · Brutal (boss SPD 170 Nightmare) · by TheDragonsBeard · This speed tune is ideal for anyone looking to utilise Demytha in a 2:1 Fully Unkillable Comp without Seeker. It uses Deacon Armstrong and High Khatun to fill Turn Meter and Increase Speed whilst giving 2 spots for damage. Speeds are quite high so will be challenging gear wise."
))


# Myth Deacon — Four infinity (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-deacon/  |  calc: https://deadwoodjedi.info/cb/1c3a26dc7e595e1187bf038b581f909e541e43b0
_register(TuneDefinition(
    name="Myth Deacon (Four infinity)",
    tune_id="myth_deacon__four_infinity",
    tune_type="unkillable",
    difficulty="hard",
    performance="1_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="block_damage", speed_range=(310, 310), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(309, 309), required_hero="High Khatun", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=2 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(198, 198), required_hero="Deacon Armstrong", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(203, 203), required_hero="Underpriest Brogni", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="Myth Deacon · Four infinity (boss SPD 170 Nightmare) · by TheDragonsBeard · This speed tune is ideal for anyone looking to utilise Demytha in a 2:1 Fully Unkillable Comp without Seeker. It uses Deacon Armstrong and High Khatun to fill Turn Meter and Increase Speed whilst giving 2 spots for damage. Speeds are quite high so will be challenging gear wise."
))


# Myth Eater — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-eater/  |  calc: https://deadwoodjedi.info/cb/9f59bf39a2dca1bd9fd46108b89cbf6b00f011de
_register(TuneDefinition(
    name="Myth Eater (Ultra Nightmare)",
    tune_id="myth_eater__ultra_nightmare",
    tune_type="unkillable",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(286, 286), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="block_damage", speed_range=(171, 171), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps_4to3", speed_range=(224, 224), required_hero=None, opening=[], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps_1to1", speed_range=(179, 179), required_hero=None, opening=[], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps_1to1", speed_range=(160, 160), required_hero=None, opening=[], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="Myth Eater · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by Facemelter · Maneater and Demytha and 3 dps with one at a 4:3 Ratio."
))


# Myth Eater — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-eater/  |  calc: https://deadwoodjedi.info/cb/ad8f54090a757cc97ba53799ac1bd551ff134b70
_register(TuneDefinition(
    name="Myth Eater (Nightmare)",
    tune_id="myth_eater__nightmare",
    tune_type="unkillable",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(286, 286), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=5"),
TuneSlot(role="block_damage", speed_range=(171, 171), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps_4to3", speed_range=(224, 224), required_hero=None, opening=[], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps_1to1", speed_range=(179, 179), required_hero=None, opening=[], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps_1to1", speed_range=(160, 160), required_hero=None, opening=[], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="Myth Eater · Nightmare (boss SPD 170 Nightmare) · by Facemelter · Maneater and Demytha and 3 dps with one at a 4:3 Ratio."
))


# Myth Eater — Ninja UNM (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-eater/  |  calc: https://deadwoodjedi.info/cb/6737fa4be0ec51c5065a433d3f23b7616d9ca430
_register(TuneDefinition(
    name="Myth Eater (Ninja UNM)",
    tune_id="myth_eater__ninja_unm",
    tune_type="unkillable",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(288, 288), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="block_damage", speed_range=(172, 172), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="ninja_tm_boost", speed_range=(205, 205), required_hero="Ninja", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps_1to1", speed_range=(178, 178), required_hero=None, opening=[], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps_1to1", speed_range=(160, 160), required_hero=None, opening=[], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="Myth Eater · Ninja UNM (boss SPD 190 Ultra-Nightmare) · by Facemelter · Maneater and Demytha and 3 dps with one at a 4:3 Ratio."
))


# Myth Eater — Ninja NM (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-eater/  |  calc: https://deadwoodjedi.info/cb/6d245eb01682779bdeee64eea8af933eaa434bfb
_register(TuneDefinition(
    name="Myth Eater (Ninja NM)",
    tune_id="myth_eater__ninja_nm",
    tune_type="unkillable",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(288, 288), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=5"),
TuneSlot(role="block_damage", speed_range=(172, 172), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="ninja_tm_boost", speed_range=(205, 205), required_hero="Ninja", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps_1to1", speed_range=(178, 178), required_hero=None, opening=[], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps_1to1", speed_range=(160, 160), required_hero=None, opening=[], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="Myth Eater · Ninja NM (boss SPD 170 Nightmare) · by Facemelter · Maneater and Demytha and 3 dps with one at a 4:3 Ratio."
))


# Myth Fu — Ultra-Nightmare, Nightmare, Brutal (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-fu/  |  calc: https://deadwoodjedi.info/cb/4e2a74291eb55911a8bc4e4281b1bccd002af0b2
_register(TuneDefinition(
    name="Myth Fu (Ultra-Nightmare, Nightmare, Brutal)",
    tune_id="myth_fu__ultra_nightmare_nightmare_brutal",
    tune_type="unkillable",
    difficulty="expert",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="block_damage", speed_range=(290, 290), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(261, 261), required_hero="Heiress", opening=['A1'], skill_priority=['A1', 'SPEED & REMOVE DEBUFF', 'A3'], notes="A1 pri=1 delay=0 CD=0; SPEED & REMOVE DEBUFF pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(185, 185), required_hero="Fu-Shan", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(184, 184), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(169, 169), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0; Lore of Steel")
    ],
    notes="Myth Fu · Ultra-Nightmare, Nightmare, Brutal (boss SPD 190 Ultra-Nightmare) · by Saphyrra · Myth-Fu is a highly recommended, full-auto speedtune with a high speed 3:1 Demytha while Heiress cleanses the debuffs to make it affinity friendly."
))


# Myth Fu — Jintoro Variation (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-fu/  |  calc: https://deadwoodjedi.info/cb/a9b29b1867165467e611647e2bf2c2180dcc298d
_register(TuneDefinition(
    name="Myth Fu (Jintoro Variation)",
    tune_id="myth_fu__jintoro_variation",
    tune_type="unkillable",
    difficulty="expert",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="block_damage", speed_range=(292, 292), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(261, 261), required_hero="Heiress", opening=['A1'], skill_priority=['A1', 'SPEED & REMOVE DEBUFF', 'A3'], notes="A1 pri=1 delay=0 CD=0; SPEED & REMOVE DEBUFF pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0; Lore of Steel"),
TuneSlot(role="dps", speed_range=(193, 193), required_hero="Fu-Shan", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3; Lore of Steel"),
TuneSlot(role="dps", speed_range=(185, 185), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(154, 154), required_hero="Jintoro", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3; Lore of Steel")
    ],
    notes="Myth Fu · Jintoro Variation (boss SPD 190 Ultra-Nightmare) · by Saphyrra · Myth-Fu is a highly recommended, full-auto speedtune with a high speed 3:1 Demytha while Heiress cleanses the debuffs to make it affinity friendly."
))


# Myth Fu — Ninja Variation (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-fu/  |  calc: https://deadwoodjedi.info/cb/5aeb4ccbef5636012859506b98cad7834b476dd3
_register(TuneDefinition(
    name="Myth Fu (Ninja Variation)",
    tune_id="myth_fu__ninja_variation",
    tune_type="unkillable",
    difficulty="expert",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="block_damage", speed_range=(296, 296), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'EXTEND', 'BLK DMG'], notes="A1 pri=1 delay=0 CD=0; EXTEND pri=2 delay=0 CD=3; BLK DMG pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(265, 265), required_hero="Heiress", opening=['A1'], skill_priority=['A1', 'SPEED & REMOVE DEBUFF', 'A3'], notes="A1 pri=1 delay=0 CD=0; SPEED & REMOVE DEBUFF pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0; Lore of Steel"),
TuneSlot(role="dps", speed_range=(192, 192), required_hero="Fu-Shan", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=3; Lore of Steel"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="ninja_tm_boost", speed_range=(141, 141), required_hero="Ninja", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=1 CD=3; A3 pri=3 delay=0 CD=4; Lore of Steel")
    ],
    notes="Myth Fu · Ninja Variation (boss SPD 190 Ultra-Nightmare) · by Saphyrra · Myth-Fu is a highly recommended, full-auto speedtune with a high speed 3:1 Demytha while Heiress cleanses the debuffs to make it affinity friendly."
))


# Myth Fu — 3:1 Ninja Hard to UNM (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-fu/  |  calc: https://deadwoodjedi.info/cb/c5edd9ee6aa5ce6b21ae9a6a8fbfc1fce2bf6be6
_register(TuneDefinition(
    name="Myth Fu (3:1 Ninja Hard to UNM)",
    tune_id="myth_fu__3_1_ninja_hard_to_unm",
    tune_type="unkillable",
    difficulty="expert",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="block_damage", speed_range=(294, 294), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'BLK DMG', 'EXTEND'], notes="A1 pri=1 delay=0 CD=0; EXTEND pri=4 delay=1 CD=3; BLK DMG pri=3 delay=2 CD=3; Lore of Steel"),
TuneSlot(role="dps", speed_range=(298, 298), required_hero="Heiress", opening=['A1'], skill_priority=['A1', 'SPEED & REMOVE DEBUFF', 'A3'], notes="A1 pri=1 delay=0 CD=0; SPEED & REMOVE DEBUFF pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0; Lore of Steel"),
TuneSlot(role="dps", speed_range=(187, 187), required_hero="Fu-Shan", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(200, 200), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="ninja_tm_boost", speed_range=(267, 267), required_hero="Ninja", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=0 CD=3; A3 pri=3 delay=0 CD=4; Lore of Steel")
    ],
    notes="Myth Fu · 3:1 Ninja Hard to UNM (boss SPD 190 Ultra-Nightmare) · by Saphyrra · Myth-Fu is a highly recommended, full-auto speedtune with a high speed 3:1 Demytha while Heiress cleanses the debuffs to make it affinity friendly."
))


# Myth Hare — Ultimate Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-hare/  |  calc: https://deadwoodjedi.info/cb/4657f8748b45e09b10ba2743bc9a6396a9c4e0a9
_register(TuneDefinition(
    name="Myth Hare (Ultimate Nightmare)",
    tune_id="myth_hare__ultimate_nightmare",
    tune_type="unkillable",
    difficulty="hard",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(212, 212), required_hero="Razelvarg", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="block_damage", speed_range=(315, 315), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(210, 210), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(211, 211), required_hero="Underpriest Brogni", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(195, 195), required_hero="Bully", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="Myth Hare · Ultimate Nightmare (boss SPD 190 Ultra-Nightmare) · by Sir Henry White · Unkillable Clan Boss team focused around the crazy speeds of Razelvarg and Demytha to go incredibly fast and do great damage!"
))


# Myth Hare — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-hare/  |  calc: https://deadwoodjedi.info/cb/62705c08084bac68cdaf3f706b56cf0f44ec2ec1
_register(TuneDefinition(
    name="Myth Hare (Nightmare)",
    tune_id="myth_hare__nightmare",
    tune_type="unkillable",
    difficulty="hard",
    performance="1_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(212, 212), required_hero="Razelvarg", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="block_damage", speed_range=(315, 315), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(210, 210), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(211, 211), required_hero="Underpriest Brogni", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(195, 195), required_hero="Bully", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="Myth Hare · Nightmare (boss SPD 170 Nightmare) · by Sir Henry White · Unkillable Clan Boss team focused around the crazy speeds of Razelvarg and Demytha to go incredibly fast and do great damage!"
))


# Myth Hare — Brutal (Brutal)
# Source: https://deadwoodjedi.com/speed-tunes/myth-hare/  |  calc: https://deadwoodjedi.info/cb/c1d123ab9456e5dd0c2b7c04535b3a5280c6803f
_register(TuneDefinition(
    name="Myth Hare (Brutal)",
    tune_id="myth_hare__brutal",
    tune_type="unkillable",
    difficulty="hard",
    performance="1_key_unm",
    affinities="all",
    cb_speed=160,
    slots=[
        TuneSlot(role="dps", speed_range=(212, 212), required_hero="Razelvarg", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="block_damage", speed_range=(315, 315), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(210, 210), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(211, 211), required_hero="Underpriest Brogni", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(195, 195), required_hero="Bully", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="Myth Hare · Brutal (boss SPD 160 Brutal) · by Sir Henry White · Unkillable Clan Boss team focused around the crazy speeds of Razelvarg and Demytha to go incredibly fast and do great damage!"
))


# Myth Hare — Ultimate Nightmare Spirit  (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-hare/  |  calc: https://deadwoodjedi.info/cb/f8d80f251edf984f75726fc4ebd5e679564e1abe
_register(TuneDefinition(
    name="Myth Hare (Ultimate Nightmare Spirit )",
    tune_id="myth_hare__ultimate_nightmare_spirit",
    tune_type="unkillable",
    difficulty="hard",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(212, 212), required_hero="Razelvarg", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="block_damage", speed_range=(315, 315), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=3 CD=3"),
TuneSlot(role="dps", speed_range=(210, 210), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(211, 211), required_hero="Underpriest Brogni", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(195, 195), required_hero="Bully", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="Myth Hare · Ultimate Nightmare Spirit (boss SPD 190 Ultra-Nightmare) · by Sir Henry White · Unkillable Clan Boss team focused around the crazy speeds of Razelvarg and Demytha to go incredibly fast and do great damage!"
))


# Myth Heir — UNM, NM, Brutal (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-heir/  |  calc: https://deadwoodjedi.info/cb/34f8a7766af615aebef2e06844daa753539a827a
_register(TuneDefinition(
    name="Myth Heir (UNM, NM, Brutal)",
    tune_id="myth_heir__unm_nm_brutal",
    tune_type="unkillable",
    difficulty="hard",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="block_damage", speed_range=(274, 274), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(245, 245), required_hero="Heiress", opening=['A1'], skill_priority=['A1', 'SPEED & REMOVE DEBUFF', 'A3'], notes="A1 pri=1 delay=0 CD=0; SPEED & REMOVE DEBUFF pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(185, 185), required_hero="Deacon Armstrong", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(169, 169), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(157, 157), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="Myth Heir · UNM, NM, Brutal (boss SPD 190 Ultra-Nightmare) · by Facemelter · A full-auto affinity friendly team that uses Demytha's block damage to stay unkillable. Deacon and Seeker push turn meter to keep speeds low, and Heiress cleanses debuffs while bringing a speed buff. Achieving 1 key UNM with this team requires high end gear."
))


# Myth Heir — Ninja UNM, NM, Brutal (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-heir/  |  calc: https://deadwoodjedi.info/cb/0077642b0d3939cf3686ee1251fabfe69cc86c28
_register(TuneDefinition(
    name="Myth Heir (Ninja UNM, NM, Brutal)",
    tune_id="myth_heir__ninja_unm_nm_brutal",
    tune_type="unkillable",
    difficulty="hard",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="block_damage", speed_range=(283, 283), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(266, 266), required_hero="Heiress", opening=['A1'], skill_priority=['A1', 'SPEED & REMOVE DEBUFF', 'A3'], notes="A1 pri=1 delay=0 CD=0; SPEED & REMOVE DEBUFF pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(195, 195), required_hero="Deacon Armstrong", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(181, 181), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="ninja_tm_boost", speed_range=(166, 166), required_hero="Ninja", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=0 CD=3; A3 pri=3 delay=0 CD=4")
    ],
    notes="Myth Heir · Ninja UNM, NM, Brutal (boss SPD 190 Ultra-Nightmare) · by Facemelter · A full-auto affinity friendly team that uses Demytha's block damage to stay unkillable. Deacon and Seeker push turn meter to keep speeds low, and Heiress cleanses debuffs while bringing a speed buff. Achieving 1 key UNM with this team requires high end gear."
))


# Myth Heir — Jintoro 2:1 UNM, NM, Brutal (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-heir/  |  calc: https://deadwoodjedi.info/cb/460bc5bf05f1119e2ebbe09a6d36119e22555fa1
_register(TuneDefinition(
    name="Myth Heir (Jintoro 2:1 UNM, NM, Brutal)",
    tune_id="myth_heir__jintoro_2_1_unm_nm_brutal",
    tune_type="unkillable",
    difficulty="hard",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="block_damage", speed_range=(274, 274), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(245, 245), required_hero="Heiress", opening=['A1'], skill_priority=['A1', 'SPEED & REMOVE DEBUFF', 'A3'], notes="A1 pri=1 delay=0 CD=0; SPEED & REMOVE DEBUFF pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(185, 185), required_hero="Deacon Armstrong", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(169, 169), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(130, 130), required_hero="Jintoro", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3")
    ],
    notes="Myth Heir · Jintoro 2:1 UNM, NM, Brutal (boss SPD 190 Ultra-Nightmare) · by Facemelter · A full-auto affinity friendly team that uses Demytha's block damage to stay unkillable. Deacon and Seeker push turn meter to keep speeds low, and Heiress cleanses debuffs while bringing a speed buff. Achieving 1 key UNM with this team requires high end gear."
))


# Myth Heir Alternate — No Seeker - UNM, NM, Brutal (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-heir-with-no-seeker/  |  calc: https://deadwoodjedi.info/cb/b24777bb67f98284b220ae5e04ab1dd0113ffba6
_register(TuneDefinition(
    name="Myth Heir Alternate (No Seeker - UNM, NM, Brutal)",
    tune_id="myth_heir_with_no_seeker__no_seeker_unm_nm_brutal",
    tune_type="unkillable",
    difficulty="hard",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="block_damage", speed_range=(329, 329), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(265, 265), required_hero="Heiress", opening=['A1'], skill_priority=['A1', 'SPEED & REMOVE DEBUFF', 'A3'], notes="A1 pri=1 delay=0 CD=0; SPEED & REMOVE DEBUFF pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(263, 263), required_hero="Doomscreech", opening=['A1'], skill_priority=['A1', 'TM BOOST', 'A3'], notes="A1 pri=1 delay=0 CD=0; TM BOOST pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(179, 179), required_hero="Deacon Armstrong", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(163, 163), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="Myth Heir Alternate · No Seeker - UNM, NM, Brutal (boss SPD 190 Ultra-Nightmare) · by Facemelter · Demytha Unkillable team utilizing Heiress, Deacon and a 30% Turn Meter Booster to stay affinity friendly without Seeker."
))


# Myth Heir Salad — UNM, NM, Brutal (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-heir-salad/  |  calc: https://deadwoodjedi.info/cb/177a6c04d04f2b1370b053251e0f7b9b768ae80e
_register(TuneDefinition(
    name="Myth Heir Salad (UNM, NM, Brutal)",
    tune_id="myth_heir_salad__unm_nm_brutal",
    tune_type="unkillable",
    difficulty="hard",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="block_damage", speed_range=(315, 315), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=1 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(293, 293), required_hero="Heiress", opening=['A1'], skill_priority=['A1', 'SPEED & REMOVE DEBUFF', 'A3'], notes="A1 pri=1 delay=0 CD=0; SPEED & REMOVE DEBUFF pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(216, 216), required_hero="Ma'Shalled", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=2 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(197, 197), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(214, 214), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="Myth Heir Salad · UNM, NM, Brutal (boss SPD 190 Ultra-Nightmare) · by Agrias · Demytha Unkillable team utilizing Heiress to stay affinity friendly with Ma'shalled."
))


# Myth Heir with Double Deacon — UNM / NM / Brutal (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-heir-with-double-deacon/  |  calc: https://deadwoodjedi.info/cb/b5f9fb612cd1b18a5765708781efea5893d95694
_register(TuneDefinition(
    name="Myth Heir with Double Deacon (UNM / NM / Brutal)",
    tune_id="myth_heir_with_double_deacon__unm_nm_brutal",
    tune_type="unkillable",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(212, 212), required_hero="Deacon Armstrong", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(180, 180), required_hero="Deacon Armstrong", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(196, 196), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(266, 266), required_hero="Heiress", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="block_damage", speed_range=(295, 295), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3")
    ],
    notes="Myth Heir with Double Deacon · UNM / NM / Brutal (boss SPD 190 Ultra-Nightmare) · by ShortOnSkillz · Unkillable Team using Two Deacons for Turn Meter boosting and Heiress to remain affinity friendly. 1 key capable with strong gear."
))


# Myth Rue-Elva — Ultra-Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-rue-elva/  |  calc: https://deadwoodjedi.info/cb/c6bd51f133d5a35b9d9159b39918dda133aaef30
_register(TuneDefinition(
    name="Myth Rue-Elva (Ultra-Nightmare)",
    tune_id="myth_rue_elva__ultra_nightmare",
    tune_type="unkillable",
    difficulty="hard",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="block_damage", speed_range=(295, 295), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(244, 244), required_hero="Elva Autumnborn", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(294, 294), required_hero="Ruella", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(155, 155), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="Myth Rue-Elva · Ultra-Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Unkillable team based on the Myth Heir team utilizing the unique abilities of Ruella and Elva Autumnborn combined with Demytha to create a extremely fast and effective team."
))


# Myth Rue-Elva — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-rue-elva/  |  calc: https://deadwoodjedi.info/cb/62f0430ea311f5cd232619a9c2499d43af046924
_register(TuneDefinition(
    name="Myth Rue-Elva (Nightmare)",
    tune_id="myth_rue_elva__nightmare",
    tune_type="unkillable",
    difficulty="hard",
    performance="1_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="block_damage", speed_range=(295, 295), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(244, 244), required_hero="Elva Autumnborn", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(294, 294), required_hero="Ruella", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(155, 155), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="Myth Rue-Elva · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi · Unkillable team based on the Myth Heir team utilizing the unique abilities of Ruella and Elva Autumnborn combined with Demytha to create a extremely fast and effective team."
))


# Myth Salad — UNM / NM / Brutal (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-salad/  |  calc: https://deadwoodjedi.info/cb/110d12db5f3a1e2da209b0ae032202e27797d310
_register(TuneDefinition(
    name="Myth Salad (UNM / NM / Brutal)",
    tune_id="myth_salad__unm_nm_brutal",
    tune_type="unkillable",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(183, 183), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(190, 190), required_hero="Ma'Shalled", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=2 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(202, 202), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(220, 220), required_hero="Tatura Rimehide", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=1 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="block_damage", speed_range=(292, 292), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=2 CD=3")
    ],
    notes="Myth Salad · UNM / NM / Brutal (boss SPD 190 Ultra-Nightmare) · by ShortOnSkillz · Unkillable Team using Ma'Shalled for a Speed buff and a 2 turn Block Debuff champ to remain Affinity Friendly. 1 key capable with strong gear."
))


# Myth Seeker — UNM / NM / Brutal (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-seeker/  |  calc: https://deadwoodjedi.info/cb/ba3a416c1f8b22bc28b23a6ec7a6833280699ca2
_register(TuneDefinition(
    name="Myth Seeker (UNM / NM / Brutal)",
    tune_id="myth_seeker__unm_nm_brutal",
    tune_type="unkillable",
    difficulty="expert",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="block_damage", speed_range=(292, 292), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(256, 256), required_hero="High Khatun", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=2 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(180, 180), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(169, 169), required_hero="Underpriest Brogni", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(145, 145), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="Myth Seeker · UNM / NM / Brutal (boss SPD 190 Ultra-Nightmare) · by Bluntguts · High Khatun (or similar) leads the team with Demytha, Seeker, a Block Debuff Champ and a DPS."
))


# Myth Seeker — UNM / NM / Brutal ( 1 Turn Block Debuff ) (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-seeker/  |  calc: https://deadwoodjedi.info/cb/6fd0f0010ee8f2203630cdae6917c5ada57bdcff
_register(TuneDefinition(
    name="Myth Seeker (UNM / NM / Brutal ( 1 Turn Block Debuff ))",
    tune_id="myth_seeker__unm_nm_brutal_1_turn_block_debuff",
    tune_type="unkillable",
    difficulty="expert",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="block_damage", speed_range=(295, 295), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(258, 258), required_hero="High Khatun", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=2 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(195, 195), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(170, 170), required_hero="Marked", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(149, 149), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="Myth Seeker · UNM / NM / Brutal ( 1 Turn Block Debuff ) (boss SPD 190 Ultra-Nightmare) · by Bluntguts · High Khatun (or similar) leads the team with Demytha, Seeker, a Block Debuff Champ and a DPS."
))


# Myth Tower — Ultra-Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-tower/  |  calc: https://deadwoodjedi.info/cb/077469e5a0ca95ce9d5e96b0918f2cac6d361f83
_register(TuneDefinition(
    name="Myth Tower (Ultra-Nightmare)",
    tune_id="myth_tower__ultra_nightmare",
    tune_type="unkillable",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="block_damage", speed_range=(174, 174), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(186, 186), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(248, 248), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(178, 178), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="Myth Tower · Ultra-Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Utilizing Demytha to block the damage from the stun with Tower or Santa"
))


# Myth Tower — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-tower/  |  calc: https://deadwoodjedi.info/cb/204fddb17a57c22b5a60ac5affaa4a7fda4dfb7f
_register(TuneDefinition(
    name="Myth Tower (Nightmare)",
    tune_id="myth_tower__nightmare",
    tune_type="unkillable",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="block_damage", speed_range=(174, 174), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(186, 186), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(248, 248), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(178, 178), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="Myth Tower · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi · Utilizing Demytha to block the damage from the stun with Tower or Santa"
))


# Myth Tower — Warcaster UNM (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-tower/  |  calc: https://deadwoodjedi.info/cb/ebfe3bb2e7cd31ec2a73eb231a896dd128e86af1
_register(TuneDefinition(
    name="Myth Tower (Warcaster UNM)",
    tune_id="myth_tower__warcaster_unm",
    tune_type="unkillable",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="block_damage", speed_range=(174, 174), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(186, 186), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(248, 248), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(178, 178), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=2 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Myth Tower · Warcaster UNM (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Utilizing Demytha to block the damage from the stun with Tower or Santa"
))


# Myth Tower — Warcaster NM (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/myth-tower/  |  calc: https://deadwoodjedi.info/cb/fd2303e5a6883465244d8d938b212cfad40a8954
_register(TuneDefinition(
    name="Myth Tower (Warcaster NM)",
    tune_id="myth_tower__warcaster_nm",
    tune_type="unkillable",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="block_damage", speed_range=(174, 174), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(186, 186), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(248, 248), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(178, 178), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=2 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Myth Tower · Warcaster NM (boss SPD 170 Nightmare) · by DeadwoodJedi · Utilizing Demytha to block the damage from the stun with Tower or Santa"
))


# Ninja CatEater — Ultra-Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/ninja-cateater/  |  calc: https://deadwoodjedi.info/cb/9dbbc2b22c9ffe8be78d47dae49e676038edb160
_register(TuneDefinition(
    name="Ninja CatEater (Ultra-Nightmare)",
    tune_id="ninja_cateater__ultra_nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(255, 255), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="ninja_tm_boost", speed_range=(192, 192), required_hero="Ninja", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(218, 218), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(179, 179), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(192, 192), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=4")
    ],
    notes="Ninja CatEater · Ultra-Nightmare (boss SPD 190 Ultra-Nightmare) · by Xaavik, Facemelter, Optilink · Unkillable Team utilizing Ninja, along with Helicath and Maneater to stay unkillable and affinity friendly. 1 Key UNM is possible with very good gear and meta champions."
))


# Ninja CatEater — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/ninja-cateater/  |  calc: https://deadwoodjedi.info/cb/deef19472a49947551ed709e070d4d555429739b
_register(TuneDefinition(
    name="Ninja CatEater (Nightmare)",
    tune_id="ninja_cateater__nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(255, 255), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="ninja_tm_boost", speed_range=(192, 192), required_hero="Ninja", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(218, 218), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=5 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(179, 179), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(192, 192), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=4")
    ],
    notes="Ninja CatEater · Nightmare (boss SPD 170 Nightmare) · by Xaavik, Facemelter, Optilink · Unkillable Team utilizing Ninja, along with Helicath and Maneater to stay unkillable and affinity friendly. 1 Key UNM is possible with very good gear and meta champions."
))


# Ninja CatEater — Brutal (Brutal)
# Source: https://deadwoodjedi.com/speed-tunes/ninja-cateater/  |  calc: https://deadwoodjedi.info/cb/8f2256aa43898895eec5c969c58e13dc9c1235bc
_register(TuneDefinition(
    name="Ninja CatEater (Brutal)",
    tune_id="ninja_cateater__brutal",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=160,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(255, 255), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=5"),
TuneSlot(role="ninja_tm_boost", speed_range=(192, 192), required_hero="Ninja", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(218, 218), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=4 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(179, 179), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(192, 192), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=4 CD=4")
    ],
    notes="Ninja CatEater · Brutal (boss SPD 160 Brutal) · by Xaavik, Facemelter, Optilink · Unkillable Team utilizing Ninja, along with Helicath and Maneater to stay unkillable and affinity friendly. 1 Key UNM is possible with very good gear and meta champions."
))


# Ninja Hellcat Unkillable — Ultra-Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/ninja-hellcat-unkillable/  |  calc: https://deadwoodjedi.info/cb/21390f8806705da0c3108351b287e2433d7a8b72
_register(TuneDefinition(
    name="Ninja Hellcat Unkillable (Ultra-Nightmare)",
    tune_id="ninja_hellcat_unkillable__ultra_nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(172, 172), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="ninja_tm_boost", speed_range=(174, 174), required_hero="Ninja", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=1 CD=3; A3 pri=3 delay=0 CD=4; Lore of Steel"),
TuneSlot(role="dps", speed_range=(254, 254), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=2 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(186, 186), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Ninja Hellcat Unkillable · Ultra-Nightmare (boss SPD 190 Ultra-Nightmare) · by Tiago Titan · Utilizing Helicath to block damage on the clan boss AOE hits and his Shield to prevent dying from the stun and Ninja for insane damage. Allows a cleanser or debuff blocker keep your team stun friendly against affinity CB."
))


# Ninja Hellcat Unkillable — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/ninja-hellcat-unkillable/  |  calc: https://deadwoodjedi.info/cb/a89aee551b5f70221ec4d5e53e5a332b90629d3c
_register(TuneDefinition(
    name="Ninja Hellcat Unkillable (Nightmare)",
    tune_id="ninja_hellcat_unkillable__nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(172, 172), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="ninja_tm_boost", speed_range=(174, 174), required_hero="Ninja", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=2 CD=3; A3 pri=3 delay=2 CD=4; Lore of Steel"),
TuneSlot(role="dps", speed_range=(254, 254), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=2 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(186, 186), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Ninja Hellcat Unkillable · Nightmare (boss SPD 170 Nightmare) · by Tiago Titan · Utilizing Helicath to block damage on the clan boss AOE hits and his Shield to prevent dying from the stun and Ninja for insane damage. Allows a cleanser or debuff blocker keep your team stun friendly against affinity CB."
))


# NinjaHelicath v2 — UNM - Ninja + CA  (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/ninjahelicath-v2/  |  calc: https://deadwoodjedi.info/cb/e86c246e6946fd5eda897fd02e173e2525464273
_register(TuneDefinition(
    name="NinjaHelicath v2 (UNM - Ninja + CA )",
    tune_id="ninjahelicath_v2__unm_ninja_ca",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(171, 171), required_hero="Tatura Rimehide", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="ninja_tm_boost", speed_range=(171, 171), required_hero="Ninja", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=1 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(253, 253), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(206, 206), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3")
    ],
    notes="NinjaHelicath v2 · UNM - Ninja + CA (boss SPD 190 Ultra-Nightmare) · by Lil · Utilizing Helicath to block damage on the clan boss AOE hits and his Shield to prevent dying from the stun and Ninja for insane damage. Allows a debuff blocker keep your team stun friendly against affinity CB"
))


# NinjaHelicath v2 — NM - Ninja + CA (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/ninjahelicath-v2/  |  calc: https://deadwoodjedi.info/cb/988b1194b604ec816ecfa69d67052a7e4ac1a921
_register(TuneDefinition(
    name="NinjaHelicath v2 (NM - Ninja + CA)",
    tune_id="ninjahelicath_v2__nm_ninja_ca",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(171, 171), required_hero="Tatura Rimehide", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=1 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(186, 186), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(253, 253), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(206, 206), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3")
    ],
    notes="NinjaHelicath v2 · NM - Ninja + CA (boss SPD 170 Nightmare) · by Lil · Utilizing Helicath to block damage on the clan boss AOE hits and his Shield to prevent dying from the stun and Ninja for insane damage. Allows a debuff blocker keep your team stun friendly against affinity CB"
))


# NinjaHelicath v2 — UNM - CA + Ally Attack (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/ninjahelicath-v2/  |  calc: https://deadwoodjedi.info/cb/d3cb87dbab59152ca8f725eacb68389079bc16a3
_register(TuneDefinition(
    name="NinjaHelicath v2 (UNM - CA + Ally Attack)",
    tune_id="ninjahelicath_v2__unm_ca_ally_attack",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(171, 171), required_hero="Tatura Rimehide", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="ninja_tm_boost", speed_range=(171, 171), required_hero="Ninja", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=3 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(253, 253), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(206, 206), required_hero="Fahrakin the Fat", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4")
    ],
    notes="NinjaHelicath v2 · UNM - CA + Ally Attack (boss SPD 190 Ultra-Nightmare) · by Lil · Utilizing Helicath to block damage on the clan boss AOE hits and his Shield to prevent dying from the stun and Ninja for insane damage. Allows a debuff blocker keep your team stun friendly against affinity CB"
))


# NinjaHelicath v2 — NM - CA + Ally Attack (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/ninjahelicath-v2/  |  calc: https://deadwoodjedi.info/cb/9b5a1446160f31ae2a63d6aea3fa3202b811318a
_register(TuneDefinition(
    name="NinjaHelicath v2 (NM - CA + Ally Attack)",
    tune_id="ninjahelicath_v2__nm_ca_ally_attack",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(171, 171), required_hero="Tatura Rimehide", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=1 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(186, 186), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(253, 253), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(206, 206), required_hero="Fahrakin the Fat", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4")
    ],
    notes="NinjaHelicath v2 · NM - CA + Ally Attack (boss SPD 170 Nightmare) · by Lil · Utilizing Helicath to block damage on the clan boss AOE hits and his Shield to prevent dying from the stun and Ninja for insane damage. Allows a debuff blocker keep your team stun friendly against affinity CB"
))


# Old Budget Maneater Unkillable — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/old-budget-maneater-unkillable/  |  calc: https://deadwoodjedi.info/cb/401f571c8e5ac270013f08f5bb922b291a143fc9
_register(TuneDefinition(
    name="Old Budget Maneater Unkillable (Ultra Nightmare)",
    tune_id="old_budget_maneater_unkillable__ultra_nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(254, 254), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=5"),
TuneSlot(role="dps", speed_range=(240, 240), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(187, 187), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(182, 182), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(124, 124), required_hero="Bulwark", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Old Budget Maneater Unkillable · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by ColdBrew Gaming · Maneater + Pain Keeper unkillable team, using a 2:3 turn ratio champion as the stun target This is a legacy tune. Recommend using the updated version titled: \\\"New Budget Maneater Unkillable\\\" or \\\"Ultimate Budget Unkillable\\\""
))


# Pain-Eater — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/pain-eater/  |  calc: https://deadwoodjedi.info/cb/50dcdb1d3f9d4ea6fe89499f42929ecd31ce6793
_register(TuneDefinition(
    name="Pain-Eater (Ultra Nightmare)",
    tune_id="pain_eater__ultra_nightmare",
    tune_type="unkillable",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(245, 245), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=4; Lore of Steel"),
TuneSlot(role="fast_uk", speed_range=(241, 241), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=1 CD=5; Lore of Steel"),
TuneSlot(role="dps", speed_range=(215, 215), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=4; A3 pri=3 delay=3 CD=4; Lore of Steel"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero=None, opening=[], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(171, 171), required_hero="Martyr", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=2 delay=0 CD=0")
    ],
    notes="Pain-Eater · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by Icy Floe · Maneater and Warcaster Unkillable team where you can use Counter-Attack and Ally Attack Freely."
))


# Pain-Eater — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/pain-eater/  |  calc: https://deadwoodjedi.info/cb/96dc4f547b2ed717d00fffa45e841b32b11fb670
_register(TuneDefinition(
    name="Pain-Eater (Nightmare)",
    tune_id="pain_eater__nightmare",
    tune_type="unkillable",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(245, 245), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=1 CD=4; Lore of Steel"),
TuneSlot(role="fast_uk", speed_range=(241, 241), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=2 CD=5; Lore of Steel"),
TuneSlot(role="dps", speed_range=(215, 215), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=4; A3 pri=3 delay=4 CD=4; Lore of Steel"),
TuneSlot(role="dps", speed_range=(178, 178), required_hero=None, opening=[], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Martyr", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=2 delay=0 CD=4")
    ],
    notes="Pain-Eater · Nightmare (boss SPD 170 Nightmare) · by Icy Floe · Maneater and Warcaster Unkillable team where you can use Counter-Attack and Ally Attack Freely."
))


# Pain-Eater — Brutal (Brutal)
# Source: https://deadwoodjedi.com/speed-tunes/pain-eater/  |  calc: https://deadwoodjedi.info/cb/09a9c132c54f9664fb62befac914cd7d3f8c855c
_register(TuneDefinition(
    name="Pain-Eater (Brutal)",
    tune_id="pain_eater__brutal",
    tune_type="unkillable",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all",
    cb_speed=160,
    slots=[
        TuneSlot(role="dps", speed_range=(245, 245), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=4; Lore of Steel"),
TuneSlot(role="fast_uk", speed_range=(241, 241), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=2 CD=5; Lore of Steel"),
TuneSlot(role="dps", speed_range=(215, 215), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=4 CD=4; A3 pri=3 delay=5 CD=4; Lore of Steel"),
TuneSlot(role="dps", speed_range=(178, 178), required_hero=None, opening=[], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="DPS 2", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=0; A3 pri=2 delay=0 CD=0")
    ],
    notes="Pain-Eater · Brutal (boss SPD 160 Brutal) · by Icy Floe · Maneater and Warcaster Unkillable team where you can use Counter-Attack and Ally Attack Freely."
))


# RabBatEater — Ultra-Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/rabbateater/  |  calc: https://deadwoodjedi.info/cb/884908faa6fb6b7f4336ecb9276466c5d10cb104
_register(TuneDefinition(
    name="RabBatEater (Ultra-Nightmare)",
    tune_id="rabbateater__ultra_nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(240, 240), required_hero="Razelvarg", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="fast_uk", speed_range=(272, 272), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=5"),
TuneSlot(role="fast_uk", speed_range=(271, 271), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=5"),
TuneSlot(role="dps", speed_range=(217, 217), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(170, 170), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="RabBatEater · Ultra-Nightmare (boss SPD 190 Ultra-Nightmare) · by ShortonSkillz · Unkillable Clan Boss team focused around the crazy speeds of Razelvarg and two Block Damage or Unkillable Champions."
))


# RabBatEater — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/rabbateater/  |  calc: https://deadwoodjedi.info/cb/54ce0886e194cb3a591a86932c56f596e0602851
_register(TuneDefinition(
    name="RabBatEater (Nightmare)",
    tune_id="rabbateater__nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="1_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(239, 239), required_hero="Razelvarg", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="fast_uk", speed_range=(272, 272), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=5"),
TuneSlot(role="fast_uk", speed_range=(271, 271), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=5"),
TuneSlot(role="dps", speed_range=(217, 217), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(170, 170), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="RabBatEater · Nightmare (boss SPD 170 Nightmare) · by ShortonSkillz · Unkillable Clan Boss team focused around the crazy speeds of Razelvarg and two Block Damage or Unkillable Champions."
))


# RabBatEater — Brutal (Brutal)
# Source: https://deadwoodjedi.com/speed-tunes/rabbateater/  |  calc: https://deadwoodjedi.info/cb/0a827e81607318bcb3a4c2eaefce669612710609
_register(TuneDefinition(
    name="RabBatEater (Brutal)",
    tune_id="rabbateater__brutal",
    tune_type="unkillable",
    difficulty="moderate",
    performance="1_key_unm",
    affinities="all",
    cb_speed=160,
    slots=[
        TuneSlot(role="dps", speed_range=(239, 239), required_hero="Razelvarg", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="fast_uk", speed_range=(272, 272), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="fast_uk", speed_range=(271, 271), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=5"),
TuneSlot(role="dps", speed_range=(217, 217), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(170, 170), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="RabBatEater · Brutal (boss SPD 160 Brutal) · by ShortonSkillz · Unkillable Clan Boss team focused around the crazy speeds of Razelvarg and two Block Damage or Unkillable Champions."
))


# Razzle Dazzle Unkillable — Ultimate Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/razzle-dazzle-unkillable/  |  calc: https://deadwoodjedi.info/cb/482e7d72486978ebef707f26369598ef972bf04b
_register(TuneDefinition(
    name="Razzle Dazzle Unkillable (Ultimate Nightmare)",
    tune_id="razzle_dazzle_unkillable__ultimate_nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(242, 242), required_hero="Razelvarg", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(232, 232), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=4"),
TuneSlot(role="dps", speed_range=(231, 231), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(214, 214), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(167, 167), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Razzle Dazzle Unkillable · Ultimate Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi and ShortonSkillz · Unkillable Clan Boss team focused around the crazy speeds of Razelvarg to incredibly fast and do great damage!"
))


# Razzle Dazzle Unkillable — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/razzle-dazzle-unkillable/  |  calc: https://deadwoodjedi.info/cb/f5c32c9f574490fdb3e8077c9796502a51b697bc
_register(TuneDefinition(
    name="Razzle Dazzle Unkillable (Nightmare)",
    tune_id="razzle_dazzle_unkillable__nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="1_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(242, 242), required_hero="Razelvarg", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(232, 232), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=4"),
TuneSlot(role="dps", speed_range=(231, 231), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(214, 214), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(167, 167), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Razzle Dazzle Unkillable · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi and ShortonSkillz · Unkillable Clan Boss team focused around the crazy speeds of Razelvarg to incredibly fast and do great damage!"
))


# Razzle Dazzle Unkillable — Brutal (Brutal)
# Source: https://deadwoodjedi.com/speed-tunes/razzle-dazzle-unkillable/  |  calc: https://deadwoodjedi.info/cb/a9151dd0a58b6102bcc5fc9f387f8d54f11c117b
_register(TuneDefinition(
    name="Razzle Dazzle Unkillable (Brutal)",
    tune_id="razzle_dazzle_unkillable__brutal",
    tune_type="unkillable",
    difficulty="moderate",
    performance="1_key_unm",
    affinities="all",
    cb_speed=160,
    slots=[
        TuneSlot(role="dps", speed_range=(242, 242), required_hero="Razelvarg", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(232, 232), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=4"),
TuneSlot(role="dps", speed_range=(231, 231), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(214, 214), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(167, 167), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Razzle Dazzle Unkillable · Brutal (boss SPD 160 Brutal) · by DeadwoodJedi and ShortonSkillz · Unkillable Clan Boss team focused around the crazy speeds of Razelvarg to incredibly fast and do great damage!"
))


# Razzle Dazzle Unkillable — Ultimate Nightmare Spirit  (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/razzle-dazzle-unkillable/  |  calc: https://deadwoodjedi.info/cb/3bb6dd081626474f82211d0a890741bc95ee15f1
_register(TuneDefinition(
    name="Razzle Dazzle Unkillable (Ultimate Nightmare Spirit )",
    tune_id="razzle_dazzle_unkillable__ultimate_nightmare_spirit",
    tune_type="unkillable",
    difficulty="moderate",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(242, 242), required_hero="Razelvarg", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(232, 232), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=4"),
TuneSlot(role="dps", speed_range=(231, 231), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(214, 214), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(167, 167), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Razzle Dazzle Unkillable · Ultimate Nightmare Spirit (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi and ShortonSkillz · Unkillable Clan Boss team focused around the crazy speeds of Razelvarg to incredibly fast and do great damage!"
))


# Santa Unkillable — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/santa-unkillable/  |  calc: https://deadwoodjedi.info/cb/f1d4437070f7fb2a71fa12992a386bca49a76d3c
_register(TuneDefinition(
    name="Santa Unkillable (Ultra Nightmare)",
    tune_id="santa_unkillable__ultra_nightmare",
    tune_type="unkillable",
    difficulty="expert",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(240, 240), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=4; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(209, 209), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(175, 175), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Sir Nicholas", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=3 CD=3; A3 pri=2 delay=2 CD=4")
    ],
    notes="Santa Unkillable · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Unkillable team centered around Sir Nicholas, Skullcrusher, and Pain Keeper."
))


# Santa Unkillable — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/santa-unkillable/  |  calc: https://deadwoodjedi.info/cb/7f823ca5b1672254185c3abb0d59a40fd32825da
_register(TuneDefinition(
    name="Santa Unkillable (Nightmare)",
    tune_id="santa_unkillable__nightmare",
    tune_type="unkillable",
    difficulty="expert",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(240, 240), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=4 CD=4; A3 pri=3 delay=2 CD=4"),
TuneSlot(role="dps", speed_range=(209, 209), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(175, 175), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Sir Nicholas", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=1 CD=3; A3 pri=2 delay=0 CD=4")
    ],
    notes="Santa Unkillable · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi · Unkillable team centered around Sir Nicholas, Skullcrusher, and Pain Keeper."
))


# Santa Unkillable - 4:3 Stun Target — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/santa-unkillable-43-stun-target/  |  calc: https://deadwoodjedi.info/cb/c116b53a82355abfc42d378b9e13de14a7862a89
_register(TuneDefinition(
    name="Santa Unkillable - 4:3 Stun Target (Ultra Nightmare)",
    tune_id="santa_unkillable_43_stun_target__ultra_nightmare",
    tune_type="unkillable",
    difficulty="expert",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(240, 240), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=4; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(229, 229), required_hero="Taurus", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=4"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(175, 175), required_hero="Sir Nicholas", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=3 CD=3; A3 pri=2 delay=2 CD=4")
    ],
    notes="Santa Unkillable - 4:3 Stun Target · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Santa Unkillable with a 4:3 turn ratio Stun Target like Taurus."
))


# Santa Unkillable - 4:3 Stun Target — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/santa-unkillable-43-stun-target/  |  calc: https://deadwoodjedi.info/cb/7eec74e20021f1e52810c9a47d2efc70b3acf455
_register(TuneDefinition(
    name="Santa Unkillable - 4:3 Stun Target (Nightmare)",
    tune_id="santa_unkillable_43_stun_target__nightmare",
    tune_type="unkillable",
    difficulty="expert",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(240, 240), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=4; A3 pri=3 delay=2 CD=4"),
TuneSlot(role="dps", speed_range=(229, 229), required_hero="Taurus", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=4"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(175, 175), required_hero="Sir Nicholas", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=1 CD=3; A3 pri=2 delay=0 CD=4")
    ],
    notes="Santa Unkillable - 4:3 Stun Target · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi · Santa Unkillable with a 4:3 turn ratio Stun Target like Taurus."
))


# Santa's Ho-Ho-Ho-mies — Ultra Nightmare / Nightmare / Brutal (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/santas-ho-ho-ho-mies/  |  calc: https://deadwoodjedi.info/cb/56915015b3b53798d1cb71fff65cccbc1fafcdff
_register(TuneDefinition(
    name="Santa's Ho-Ho-Ho-mies (Ultra Nightmare / Nightmare / Brutal)",
    tune_id="santas_ho_ho_ho_mies__ultra_nightmare_nightmare_brutal",
    tune_type="unkillable",
    difficulty="moderate",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(271, 271), required_hero="Godseeker Aniri", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=1 CD=3; A3 pri=1 delay=0 CD=4; Lore of Steel"),
TuneSlot(role="dps", speed_range=(269, 269), required_hero="Lady Noelle", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=3 delay=0 CD=0; Lore of Steel"),
TuneSlot(role="dps", speed_range=(245, 245), required_hero="Underpriest Brogni", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Sir Nicholas", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=2 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="Santa's Ho-Ho-Ho-mies · Ultra Nightmare / Nightmare / Brutal (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · 2:1 turn ratio using Lady Noelle and a buff extender. A 1-Key Unkillable team for all difficulties."
))


# Slow Beating Trunkheart — Ultra-Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/slow-beating-trunkheart/  |  calc: https://deadwoodjedi.info/cb/18cc0a1ea9cbb6f47edcec035b957f6c71a4b226
_register(TuneDefinition(
    name="Slow Beating Trunkheart (Ultra-Nightmare)",
    tune_id="slow_beating_trunkheart__ultra_nightmare",
    tune_type="unkillable",
    difficulty="easy",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(246, 246), required_hero="Emic Trunkheart", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(178, 178), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Sir Nicholas", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=4 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0")
    ],
    notes="Slow Beating Trunkheart · Ultra-Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · With the same speeds as the original Tower/Skullcrusher Unkillable and Slow Hellcat Unkillable, Emic Trunkheart creates an Unkillable team by utilizing his cooldown ability to enable another AOE Unkillable or Block Damage champ to work at insanely low speeds."
))


# Slow Beating Trunkheart — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/slow-beating-trunkheart/  |  calc: https://deadwoodjedi.info/cb/e44c5e6bdfbac3c921f29fbeb1a0b0bae94a76c1
_register(TuneDefinition(
    name="Slow Beating Trunkheart (Nightmare)",
    tune_id="slow_beating_trunkheart__nightmare",
    tune_type="unkillable",
    difficulty="easy",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(246, 246), required_hero="Emic Trunkheart", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(178, 178), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Sir Nicholas", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=4 delay=2 CD=4"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=4; A3 pri=3 delay=0 CD=0")
    ],
    notes="Slow Beating Trunkheart · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi · With the same speeds as the original Tower/Skullcrusher Unkillable and Slow Hellcat Unkillable, Emic Trunkheart creates an Unkillable team by utilizing his cooldown ability to enable another AOE Unkillable or Block Damage champ to work at insanely low speeds."
))


# Slow Beating Trunkheart — Nightmare Spirit w/Cleanser (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/slow-beating-trunkheart/  |  calc: https://deadwoodjedi.info/cb/f2269b824d31aaae7cd30b5cd3ba34e6081595d9
_register(TuneDefinition(
    name="Slow Beating Trunkheart (Nightmare Spirit w/Cleanser)",
    tune_id="slow_beating_trunkheart__nightmare_spirit_w_cleanser",
    tune_type="unkillable",
    difficulty="easy",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(246, 246), required_hero="Emic Trunkheart", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(178, 178), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Sir Nicholas", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=4 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Bully", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="Slow Beating Trunkheart · Nightmare Spirit w/Cleanser (boss SPD 170 Nightmare) · by DeadwoodJedi · With the same speeds as the original Tower/Skullcrusher Unkillable and Slow Hellcat Unkillable, Emic Trunkheart creates an Unkillable team by utilizing his cooldown ability to enable another AOE Unkillable or Block Damage champ to work at insanely low speeds."
))


# Slow Beating Trunkheart — Nightmare Spirit Special (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/slow-beating-trunkheart/  |  calc: https://deadwoodjedi.info/cb/419bde2d213089ea1fd0f046481e4c4533409c67
_register(TuneDefinition(
    name="Slow Beating Trunkheart (Nightmare Spirit Special)",
    tune_id="slow_beating_trunkheart__nightmare_spirit_special",
    tune_type="unkillable",
    difficulty="easy",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(246, 246), required_hero="Emic Trunkheart", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(179, 179), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Sir Nicholas", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=4 delay=2 CD=4"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Bully", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="Slow Beating Trunkheart · Nightmare Spirit Special (boss SPD 170 Nightmare) · by DeadwoodJedi · With the same speeds as the original Tower/Skullcrusher Unkillable and Slow Hellcat Unkillable, Emic Trunkheart creates an Unkillable team by utilizing his cooldown ability to enable another AOE Unkillable or Block Damage champ to work at insanely low speeds."
))


# Slow Hellcat Unkillable — Ultra-Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/slow-hellcat-unkillable/  |  calc: https://deadwoodjedi.info/cb/25d297df0d13217aa0b1c3617a1826bd6dda8901
_register(TuneDefinition(
    name="Slow Hellcat Unkillable (Ultra-Nightmare)",
    tune_id="slow_hellcat_unkillable__ultra_nightmare",
    tune_type="unkillable",
    difficulty="easy",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(246, 246), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(179, 179), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Bully", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Marked", opening=['A1'], skill_priority=['A1', 'A2', 'Block Debuffs'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; Block Debuffs pri=3 delay=0 CD=3")
    ],
    notes="Slow Hellcat Unkillable · Ultra-Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Using the original Tower/Skullcrusher Unkillable, but utilizing Helicath to block damage on the clan boss AOE hits and his Shield to prevent dying from the stun. Allows a cleanser or debuff blocker keep your team stun friendly against affinity CB."
))


# Slow Hellcat Unkillable — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/slow-hellcat-unkillable/  |  calc: https://deadwoodjedi.info/cb/3029e50c14eb2150f398fc750dcb8790263052ac
_register(TuneDefinition(
    name="Slow Hellcat Unkillable (Nightmare)",
    tune_id="slow_hellcat_unkillable__nightmare",
    tune_type="unkillable",
    difficulty="easy",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(246, 246), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(179, 179), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Bully", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Marked", opening=['A1'], skill_priority=['A1', 'A2', 'Block Debuffs'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; Block Debuffs pri=3 delay=1 CD=3")
    ],
    notes="Slow Hellcat Unkillable · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi · Using the original Tower/Skullcrusher Unkillable, but utilizing Helicath to block damage on the clan boss AOE hits and his Shield to prevent dying from the stun. Allows a cleanser or debuff blocker keep your team stun friendly against affinity CB."
))


# Slow Tower Skullcrusher Unkillable — Ultra-Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/slow-tower-skullcrusher-unkillable/  |  calc: https://deadwoodjedi.info/cb/a66f2f9dd30d2f6d864e049063b2ed53b2af6ce0
_register(TuneDefinition(
    name="Slow Tower Skullcrusher Unkillable (Ultra-Nightmare)",
    tune_id="slow_tower_skullcrusher_unkillable__ultra_nightmare",
    tune_type="unkillable",
    difficulty="easy",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(174, 174), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(186, 186), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(248, 248), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(178, 178), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=2 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=2 CD=3")
    ],
    notes="Slow Tower Skullcrusher Unkillable · Ultra-Nightmare (boss SPD 190 Ultra-Nightmare) · by abscity · Tower + Skullcrusher Unkillable that allows a cleanser or debuff blocker keep your team stun friendly against affinity CB"
))


# Slow Tower Skullcrusher Unkillable — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/slow-tower-skullcrusher-unkillable/  |  calc: https://deadwoodjedi.info/cb/bbe8308821d0c30dfdfb4d590be33e5978e4fdc3
_register(TuneDefinition(
    name="Slow Tower Skullcrusher Unkillable (Nightmare)",
    tune_id="slow_tower_skullcrusher_unkillable__nightmare",
    tune_type="unkillable",
    difficulty="easy",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(174, 174), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(186, 186), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(248, 248), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(178, 178), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3")
    ],
    notes="Slow Tower Skullcrusher Unkillable · Nightmare (boss SPD 170 Nightmare) · by abscity · Tower + Skullcrusher Unkillable that allows a cleanser or debuff blocker keep your team stun friendly against affinity CB"
))


# Slow Tuned Man Tower Unkillable — Ultra Nightmare (Ultimate Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/slow-tuned-man-tower-unkillable/  |  calc: https://deadwoodjedi.info/cb/fc7a77280f4da78383152b44a30041ce2c364447
_register(TuneDefinition(
    name="Slow Tuned Man Tower Unkillable (Ultra Nightmare)",
    tune_id="slow_tuned_man_tower_unkillable__ultra_nightmare",
    tune_type="unkillable",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(256, 256), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=5"),
TuneSlot(role="dps", speed_range=(215, 215), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(207, 207), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(158, 158), required_hero="Septimus", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(130, 130), required_hero="Apothecary", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=2; A3 pri=3 delay=0 CD=3")
    ],
    notes="Slow Tuned Man Tower Unkillable · Ultra Nightmare (boss SPD 190 Ultimate Nightmare) · by DeadwoodJedi · Use a Maneater and Tower/Warcaster/Santa with a speed booster to achieve Unkillable."
))


# Slow Tuned Man Tower Unkillable — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/slow-tuned-man-tower-unkillable/  |  calc: https://deadwoodjedi.info/cb/30661bd8facab4c7f54b25f22458b9c62a90b38f
_register(TuneDefinition(
    name="Slow Tuned Man Tower Unkillable (Nightmare)",
    tune_id="slow_tuned_man_tower_unkillable__nightmare",
    tune_type="unkillable",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(256, 256), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=5"),
TuneSlot(role="dps", speed_range=(215, 215), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(216, 216), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(158, 158), required_hero="Septimus", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(130, 130), required_hero="Apothecary", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=2; A3 pri=3 delay=0 CD=3")
    ],
    notes="Slow Tuned Man Tower Unkillable · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi · Use a Maneater and Tower/Warcaster/Santa with a speed booster to achieve Unkillable."
))


# Slow Tuned Man Tower Unkillable — Ultra Nightmare - Turvold (Ultimate Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/slow-tuned-man-tower-unkillable/  |  calc: https://deadwoodjedi.info/cb/4f61b7c8e75ee6b3b973a519d4cdedab4b4f1b40
_register(TuneDefinition(
    name="Slow Tuned Man Tower Unkillable (Ultra Nightmare - Turvold)",
    tune_id="slow_tuned_man_tower_unkillable__ultra_nightmare_turvold",
    tune_type="unkillable",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(256, 256), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=5"),
TuneSlot(role="dps", speed_range=(215, 215), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(206, 206), required_hero="Turvold", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=1 CD=3; A3 pri=2 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(158, 158), required_hero="Saito", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(130, 130), required_hero="Apothecary", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=2; A3 pri=3 delay=0 CD=3")
    ],
    notes="Slow Tuned Man Tower Unkillable · Ultra Nightmare - Turvold (boss SPD 190 Ultimate Nightmare) · by DeadwoodJedi · Use a Maneater and Tower/Warcaster/Santa with a speed booster to achieve Unkillable."
))


# Super Charged Hellcat — Fast Ultra-Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/super-charged-hellcat/  |  calc: https://deadwoodjedi.info/cb/ab1f7f2553d1fcbefc7865e10afac0702a91724e
_register(TuneDefinition(
    name="Super Charged Hellcat (Fast Ultra-Nightmare)",
    tune_id="super_charged_hellcat__fast_ultra_nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(241, 241), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(257, 257), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(240, 240), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(192, 192), required_hero="Dark Kael", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(191, 191), required_hero="Venomage", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3")
    ],
    notes="Super Charged Hellcat · Fast Ultra-Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Unkillable team using Helicath to block damage on the clan boss AOE hits and his Shield to prevent dying from the stun. This version has TWO 4:3 ratio champion to provide more damage. 1 Key UNM is possible with very good gear and meta champions."
))


# Super Charged Hellcat — Slow Ultra-Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/super-charged-hellcat/  |  calc: https://deadwoodjedi.info/cb/263af4850292c62750d6e184d1842cb5dd7512ac
_register(TuneDefinition(
    name="Super Charged Hellcat (Slow Ultra-Nightmare)",
    tune_id="super_charged_hellcat__slow_ultra_nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(221, 221), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(240, 240), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(220, 220), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=4"),
TuneSlot(role="dps", speed_range=(192, 192), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(171, 171), required_hero="Bulwark", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Super Charged Hellcat · Slow Ultra-Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Unkillable team using Helicath to block damage on the clan boss AOE hits and his Shield to prevent dying from the stun. This version has TWO 4:3 ratio champion to provide more damage. 1 Key UNM is possible with very good gear and meta champions."
))


# Super Charged Hellcat — Slow Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/super-charged-hellcat/  |  calc: https://deadwoodjedi.info/cb/23006bbd78e2aabcb0ba8c76b2f70d5dc022f239
_register(TuneDefinition(
    name="Super Charged Hellcat (Slow Nightmare)",
    tune_id="super_charged_hellcat__slow_nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(221, 221), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(240, 240), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(220, 220), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Venomage", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(171, 171), required_hero="Dark Kael", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3")
    ],
    notes="Super Charged Hellcat · Slow Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi · Unkillable team using Helicath to block damage on the clan boss AOE hits and his Shield to prevent dying from the stun. This version has TWO 4:3 ratio champion to provide more damage. 1 Key UNM is possible with very good gear and meta champions."
))


# The Dark Knight - aka, WarCrusher — UNM / NM / Brutal (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/the-dark-knight-aka-warcrusher/  |  calc: https://deadwoodjedi.info/cb/bbda83fa38dfdffb644cd40a34743654f924c0ee
_register(TuneDefinition(
    name="The Dark Knight - aka, WarCrusher (UNM / NM / Brutal)",
    tune_id="the_dark_knight_aka_warcrusher__unm_nm_brutal",
    tune_type="unkillable",
    difficulty="expert",
    performance="1_key_unm",
    affinities="void_only",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(265, 265), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(248, 248), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(247, 247), required_hero="Renegade", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(246, 246), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(220, 220), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4")
    ],
    notes="The Dark Knight - aka, WarCrusher · UNM / NM / Brutal (boss SPD 190 Ultra-Nightmare) · by Various · Using Renegade and a 4 Turn Cooldown Unkillable champ to stay unkillable. Affinity can be difficult to navigate, but there are solutions. An excellent option for those lacking other unkillable champions."
))


# The Dark Knight - aka, WarCrusher — Full Booked Renegade UNM / NM / Brutal (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/the-dark-knight-aka-warcrusher/  |  calc: https://deadwoodjedi.info/cb/44122f0c51070f3672124698dd4dbf03642790ae
_register(TuneDefinition(
    name="The Dark Knight - aka, WarCrusher (Full Booked Renegade UNM / NM / Brutal)",
    tune_id="the_dark_knight_aka_warcrusher__full_booked_renegade_unm_nm_brutal",
    tune_type="unkillable",
    difficulty="expert",
    performance="1_key_unm",
    affinities="void_only",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(265, 265), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(248, 248), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(247, 247), required_hero="Renegade", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=1 CD=3; A3 pri=3 delay=0 CD=5"),
TuneSlot(role="dps", speed_range=(246, 246), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(220, 220), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4")
    ],
    notes="The Dark Knight - aka, WarCrusher · Full Booked Renegade UNM / NM / Brutal (boss SPD 190 Ultra-Nightmare) · by Various · Using Renegade and a 4 Turn Cooldown Unkillable champ to stay unkillable. Affinity can be difficult to navigate, but there are solutions. An excellent option for those lacking other unkillable champions."
))


# The North Pole — v.1 Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/santa-and-warcaster/  |  calc: https://deadwoodjedi.info/cb/dab136e18875c8fda6b035c262f8e93f301e1088
_register(TuneDefinition(
    name="The North Pole (v.1 Ultra Nightmare)",
    tune_id="santa_and_warcaster__v_1_ultra_nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(255, 255), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=4"),
TuneSlot(role="dps", speed_range=(254, 254), required_hero="Sir Nicholas", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=1 CD=4; A3 pri=2 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(200, 200), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(187, 187), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6")
    ],
    notes="The North Pole · v.1 Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · Santa or Tower + Warcaster Unkillable with slot for cleanser for affinity friendliness."
))


# The North Pole — v.2 Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/santa-and-warcaster/  |  calc: https://deadwoodjedi.info/cb/76c40d1c06a32336ede474f464cea9b6680590ca
_register(TuneDefinition(
    name="The North Pole (v.2 Ultra Nightmare)",
    tune_id="santa_and_warcaster__v_2_ultra_nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(267, 267), required_hero="Sir Nicholas", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=4; A3 pri=2 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(264, 264), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=4"),
TuneSlot(role="dps", speed_range=(205, 205), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(193, 193), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(191, 191), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6")
    ],
    notes="The North Pole · v.2 Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · Santa or Tower + Warcaster Unkillable with slot for cleanser for affinity friendliness."
))


# The North Pole with 4:3 Champ — Ultra-Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/tower-and-warcaster-with-43-champ/  |  calc: https://deadwoodjedi.info/cb/eb97d9e3de7a99ecfe85e0ce069ea2f855fb098a
_register(TuneDefinition(
    name="The North Pole with 4:3 Champ (Ultra-Nightmare)",
    tune_id="tower_and_warcaster_with_43_champ__ultra_nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="void_only",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(242, 242), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(241, 241), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(221, 221), required_hero="Kreela Witch-Arm", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=4"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=2 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(171, 171), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=1 CD=3")
    ],
    notes="The North Pole with 4:3 Champ · Ultra-Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Taking the traditional Tower and Sir Nicholas (or Warcaster) composition and adding in a 4:3 champion to maximize damage potential."
))


# Tower and Valkyrie Unkillable with 43 Champ — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/tower-and-valkyrie-unkillable-with-43-champ/  |  calc: https://deadwoodjedi.info/cb/eafb0c01d9a5266eadac54167f3542a415cba8d3
_register(TuneDefinition(
    name="Tower and Valkyrie Unkillable with 43 Champ (Ultra Nightmare)",
    tune_id="tower_and_valkyrie_unkillable_with_43_champ__ultra_nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="void_only",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(240, 240), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=4 CD=4"),
TuneSlot(role="dps", speed_range=(226, 226), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(175, 175), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(173, 173), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(171, 171), required_hero="Valkyrie", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Tower and Valkyrie Unkillable with 43 Champ · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · Use Tower to block the AOEs and Valkyrie shield to tank the stun."
))


# Turvold Double Maneater Unkillable — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/turvold-double-maneater-unkillable/  |  calc: https://deadwoodjedi.info/cb/c7063bc84441ee3cf72cabe35b8733fd25b49c78
_register(TuneDefinition(
    name="Turvold Double Maneater Unkillable (Ultra Nightmare)",
    tune_id="turvold_double_maneater_unkillable__ultra_nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(218, 218), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=5"),
TuneSlot(role="fast_uk", speed_range=(218, 218), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=4 CD=5"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(155, 155), required_hero="Turvold", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=4 CD=3; A3 pri=2 delay=0 CD=3")
    ],
    notes="Turvold Double Maneater Unkillable · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Adds Turvold to the slow double Maneater unkillable team to increase your damage."
))


# Turvold Double Maneater Unkillable — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/turvold-double-maneater-unkillable/  |  calc: https://deadwoodjedi.info/cb/2c9ac1f7469b935626fa1f7365c0c68633e28aa5
_register(TuneDefinition(
    name="Turvold Double Maneater Unkillable (Nightmare)",
    tune_id="turvold_double_maneater_unkillable__nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(218, 218), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=5"),
TuneSlot(role="fast_uk", speed_range=(218, 218), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=5 CD=5"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(155, 155), required_hero="Turvold", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=3 CD=3; A3 pri=2 delay=0 CD=3")
    ],
    notes="Turvold Double Maneater Unkillable · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi · Adds Turvold to the slow double Maneater unkillable team to increase your damage."
))


# Ultimate Myth Heir - 2 Seekers — Ultra-Nightmare, Nightmare, Brutal (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/ultimate-myth-heir-2-seekers/  |  calc: https://deadwoodjedi.info/cb/adedb4b2d5e6cf65dcf480be597f218795ab0f27
_register(TuneDefinition(
    name="Ultimate Myth Heir - 2 Seekers (Ultra-Nightmare, Nightmare, Brutal)",
    tune_id="ultimate_myth_heir_2_seekers__ultra_nightmare_nightmare_brutal",
    tune_type="unkillable",
    difficulty="expert",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="block_damage", speed_range=(287, 287), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(264, 264), required_hero="Heiress", opening=['A1'], skill_priority=['A1', 'SPEED & REMOVE DEBUFF', 'A3'], notes="A1 pri=1 delay=0 CD=0; SPEED & REMOVE DEBUFF pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(205, 205), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(204, 204), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(263, 263), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="Ultimate Myth Heir - 2 Seekers · Ultra-Nightmare, Nightmare, Brutal (boss SPD 190 Ultra-Nightmare) · by TheDragonsBeard · Full-auto tune with high speed with 2x Seeker, 3:1 DPS and Demytha while Heiress cleanses the debuffs to make it affinity friendly. Ninja viable."
))


# Ultimate Myth Heir - 2 Seekers — Ninja Variation (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/ultimate-myth-heir-2-seekers/  |  calc: https://deadwoodjedi.info/cb/e591c24f542e80935f5c7a702f90cccfcaa06818
_register(TuneDefinition(
    name="Ultimate Myth Heir - 2 Seekers (Ninja Variation)",
    tune_id="ultimate_myth_heir_2_seekers__ninja_variation",
    tune_type="unkillable",
    difficulty="expert",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="block_damage", speed_range=(295, 295), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(283, 283), required_hero="Heiress", opening=['A1'], skill_priority=['A1', 'SPEED & REMOVE DEBUFF', 'A3'], notes="A1 pri=1 delay=0 CD=0; SPEED & REMOVE DEBUFF pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(214, 214), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(195, 195), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="ninja_tm_boost", speed_range=(263, 263), required_hero="Ninja", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=0 CD=3; A3 pri=3 delay=0 CD=4")
    ],
    notes="Ultimate Myth Heir - 2 Seekers · Ninja Variation (boss SPD 190 Ultra-Nightmare) · by TheDragonsBeard · Full-auto tune with high speed with 2x Seeker, 3:1 DPS and Demytha while Heiress cleanses the debuffs to make it affinity friendly. Ninja viable."
))


# Ultimate Myth Heir - 2 Seekers — 2:1 DPS (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/ultimate-myth-heir-2-seekers/  |  calc: https://deadwoodjedi.info/cb/af9786de88f64dd590c0880b1c403e5a6eb5591c
_register(TuneDefinition(
    name="Ultimate Myth Heir - 2 Seekers (2:1 DPS)",
    tune_id="ultimate_myth_heir_2_seekers__2_1_dps",
    tune_type="unkillable",
    difficulty="expert",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="block_damage", speed_range=(293, 293), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(257, 257), required_hero="Heiress", opening=['A1'], skill_priority=['A1', 'SPEED & REMOVE DEBUFF', 'A3'], notes="A1 pri=1 delay=0 CD=0; SPEED & REMOVE DEBUFF pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(204, 204), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(191, 191), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="ninja_tm_boost", speed_range=(161, 161), required_hero="Ninja", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=0 CD=3; A3 pri=3 delay=0 CD=4")
    ],
    notes="Ultimate Myth Heir - 2 Seekers · 2:1 DPS (boss SPD 190 Ultra-Nightmare) · by TheDragonsBeard · Full-auto tune with high speed with 2x Seeker, 3:1 DPS and Demytha while Heiress cleanses the debuffs to make it affinity friendly. Ninja viable."
))


# Ultimate Myth Heir with 3:1 DPS — UNM, NM, Brutal (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/ultimate-myth-heir-with-31-dps-ninja-works/  |  calc: https://deadwoodjedi.info/cb/bd95b5fa121fe9ee6c5721b028c5c1ecdddbe0b7
_register(TuneDefinition(
    name="Ultimate Myth Heir with 3:1 DPS (UNM, NM, Brutal)",
    tune_id="ultimate_myth_heir_with_31_dps_ninja_works__unm_nm_brutal",
    tune_type="unkillable",
    difficulty="expert",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="block_damage", speed_range=(288, 288), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'EXTEND', 'BLK DMG'], notes="A1 pri=1 delay=0 CD=0; EXTEND pri=2 delay=0 CD=3; BLK DMG pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(266, 266), required_hero="Heiress", opening=['A1'], skill_priority=['A1', 'SPEED & REMOVE DEBUFF', 'A3'], notes="A1 pri=1 delay=0 CD=0; SPEED & REMOVE DEBUFF pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(195, 195), required_hero="Deacon Armstrong", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(185, 185), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(258, 258), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6")
    ],
    notes="Ultimate Myth Heir with 3:1 DPS · UNM, NM, Brutal (boss SPD 190 Ultra-Nightmare) · by TheDragonsBeard · Demytha Unkillable team utilizing Heiress to stay affinity friendly adding in a 3:1 Ratio DPS. Ninja Viable."
))


# Ultimate Myth Heir with 3:1 DPS — Ninja (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/ultimate-myth-heir-with-31-dps-ninja-works/  |  calc: https://deadwoodjedi.info/cb/f55a62bcb879a5f4b0db383c7f72391995d3b6d4
_register(TuneDefinition(
    name="Ultimate Myth Heir with 3:1 DPS (Ninja)",
    tune_id="ultimate_myth_heir_with_31_dps_ninja_works__ninja",
    tune_type="unkillable",
    difficulty="expert",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="block_damage", speed_range=(288, 288), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'EXTEND', 'BLK DMG'], notes="A1 pri=1 delay=0 CD=0; EXTEND pri=2 delay=0 CD=3; BLK DMG pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(266, 266), required_hero="Heiress", opening=['A1'], skill_priority=['A1', 'SPEED & REMOVE DEBUFF', 'A3'], notes="A1 pri=1 delay=0 CD=0; SPEED & REMOVE DEBUFF pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(195, 195), required_hero="Deacon Armstrong", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(185, 185), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="ninja_tm_boost", speed_range=(258, 258), required_hero="Ninja", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=0 CD=3; A3 pri=3 delay=0 CD=4")
    ],
    notes="Ultimate Myth Heir with 3:1 DPS · Ninja (boss SPD 190 Ultra-Nightmare) · by TheDragonsBeard · Demytha Unkillable team utilizing Heiress to stay affinity friendly adding in a 3:1 Ratio DPS. Ninja Viable."
))


# Ultimate Myth Heir with 3:1 DPS — Jintoro (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/ultimate-myth-heir-with-31-dps-ninja-works/  |  calc: https://deadwoodjedi.info/cb/4f6703e42f032be14c5fad57f636e0a6fc5dfce2
_register(TuneDefinition(
    name="Ultimate Myth Heir with 3:1 DPS (Jintoro)",
    tune_id="ultimate_myth_heir_with_31_dps_ninja_works__jintoro",
    tune_type="unkillable",
    difficulty="expert",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="block_damage", speed_range=(292, 292), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(266, 266), required_hero="Heiress", opening=['A1'], skill_priority=['A1', 'SPEED & REMOVE DEBUFF', 'A3'], notes="A1 pri=1 delay=0 CD=0; SPEED & REMOVE DEBUFF pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(243, 243), required_hero="Jintoro", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(191, 191), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(195, 195), required_hero="Deacon Armstrong", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=3")
    ],
    notes="Ultimate Myth Heir with 3:1 DPS · Jintoro (boss SPD 190 Ultra-Nightmare) · by TheDragonsBeard · Demytha Unkillable team utilizing Heiress to stay affinity friendly adding in a 3:1 Ratio DPS. Ninja Viable."
))


# Un-Kreelable — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/un-kreelable/  |  calc: https://deadwoodjedi.info/cb/595b05942cf8f23a4b26e3cf4f63430d74be73b6
_register(TuneDefinition(
    name="Un-Kreelable (Ultra Nightmare)",
    tune_id="un_kreelable__ultra_nightmare",
    tune_type="unkillable",
    difficulty="expert",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(248, 248), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=5"),
TuneSlot(role="dps", speed_range=(223, 223), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=4; A3 pri=3 delay=3 CD=4"),
TuneSlot(role="dps", speed_range=(232, 232), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Kreela Witch-Arm", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(123, 123), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=1 CD=3")
    ],
    notes="Un-Kreelable · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by Bobo & Wystix · Adds a 4:3 champion and Ally Attack to the Budget Maneater Unkillable"
))


# Un-Kreelable — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/un-kreelable/  |  calc: https://deadwoodjedi.info/cb/6a89c1db693eff826ed3d5caa0ece2d2bc2cfce0
_register(TuneDefinition(
    name="Un-Kreelable (Nightmare)",
    tune_id="un_kreelable__nightmare",
    tune_type="unkillable",
    difficulty="expert",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(248, 248), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="dps", speed_range=(223, 223), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(232, 232), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(181, 181), required_hero="Kreela Witch-Arm", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=3; A3 pri=3 delay=2 CD=4"),
TuneSlot(role="dps", speed_range=(123, 123), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=1 CD=3")
    ],
    notes="Un-Kreelable · Nightmare (boss SPD 170 Nightmare) · by Bobo & Wystix · Adds a 4:3 champion and Ally Attack to the Budget Maneater Unkillable"
))


# Un-Kreelable — Brutal (Brutal)
# Source: https://deadwoodjedi.com/speed-tunes/un-kreelable/  |  calc: https://deadwoodjedi.info/cb/8bfd57406c4f7d054b422e6b612a3061053eaa11
_register(TuneDefinition(
    name="Un-Kreelable (Brutal)",
    tune_id="un_kreelable__brutal",
    tune_type="unkillable",
    difficulty="expert",
    performance="2_key_unm",
    affinities="all",
    cb_speed=160,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(248, 248), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=5"),
TuneSlot(role="dps", speed_range=(223, 223), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=4; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(232, 232), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Kreela Witch-Arm", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=3; A3 pri=3 delay=2 CD=4"),
TuneSlot(role="dps", speed_range=(123, 123), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3")
    ],
    notes="Un-Kreelable · Brutal (boss SPD 160 Brutal) · by Bobo & Wystix · Adds a 4:3 champion and Ally Attack to the Budget Maneater Unkillable"
))


# WarMBat — Ultra-Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/warmbat/  |  calc: https://deadwoodjedi.info/cb/41257f31c4c8f18e321f264455c7ac512aa79e53
_register(TuneDefinition(
    name="WarMBat (Ultra-Nightmare)",
    tune_id="warmbat__ultra_nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(255, 255), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="dps", speed_range=(213, 213), required_hero="Kreela Witch-Arm", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(218, 218), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(179, 179), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(192, 192), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=4")
    ],
    notes="WarMBat · Ultra-Nightmare (boss SPD 190 Ultra-Nightmare) · by Xaavik, Facemelter, Optilink · Unkillable Team utilizing a 4 Turn Cooldown Unkillable Champ and Maneater to stay unkillable and affinity friendly 1 Key UNM is possible with very good gear and meta champions."
))


# WarMBat — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/warmbat/  |  calc: https://deadwoodjedi.info/cb/59461c92bca9774c90923b3c48e8d65495f13447
_register(TuneDefinition(
    name="WarMBat (Nightmare)",
    tune_id="warmbat__nightmare",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(255, 255), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="dps", speed_range=(213, 213), required_hero="Kreela Witch-Arm", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(218, 218), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=5 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(179, 179), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(192, 192), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=4")
    ],
    notes="WarMBat · Nightmare (boss SPD 170 Nightmare) · by Xaavik, Facemelter, Optilink · Unkillable Team utilizing a 4 Turn Cooldown Unkillable Champ and Maneater to stay unkillable and affinity friendly 1 Key UNM is possible with very good gear and meta champions."
))


# WarMBat — Brutal (Brutal)
# Source: https://deadwoodjedi.com/speed-tunes/warmbat/  |  calc: https://deadwoodjedi.info/cb/0d67724a7c9ceb63866ac51fc49f77c1276412d6
_register(TuneDefinition(
    name="WarMBat (Brutal)",
    tune_id="warmbat__brutal",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=160,
    slots=[
        TuneSlot(role="fast_uk", speed_range=(255, 255), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=5"),
TuneSlot(role="dps", speed_range=(213, 213), required_hero="Kreela Witch-Arm", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(218, 218), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=4 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(179, 179), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(192, 192), required_hero="Helicath", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4")
    ],
    notes="WarMBat · Brutal (boss SPD 160 Brutal) · by Xaavik, Facemelter, Optilink · Unkillable Team utilizing a 4 Turn Cooldown Unkillable Champ and Maneater to stay unkillable and affinity friendly 1 Key UNM is possible with very good gear and meta champions."
))


# WarTower — Ultra Nightmare (Ultimate Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/wartower/  |  calc: https://deadwoodjedi.info/cb/e57042e0f0842133342b7261540aff1cd32bd14f
_register(TuneDefinition(
    name="WarTower (Ultra Nightmare)",
    tune_id="wartower__ultra_nightmare",
    tune_type="unkillable",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(247, 247), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(240, 240), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(175, 175), required_hero="Septimus", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4")
    ],
    notes="WarTower · Ultra Nightmare (boss SPD 190 Ultimate Nightmare) · by Litooth · WarTower comp uses Warcaster and Roschard (Sir Nic is an alternative) to stay unkillable for 50 turns and use Doompriest to stay affinity friendly. Warcaster cannot be the stun target"
))


# WarTower — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/wartower/  |  calc: https://deadwoodjedi.info/cb/1ff251bcbfa5b0b44e170a2bc4dc744923bf72d3
_register(TuneDefinition(
    name="WarTower (Nightmare)",
    tune_id="wartower__nightmare",
    tune_type="unkillable",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(247, 247), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(240, 240), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=4"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(175, 175), required_hero="Septimus", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4")
    ],
    notes="WarTower · Nightmare (boss SPD 170 Nightmare) · by Litooth · WarTower comp uses Warcaster and Roschard (Sir Nic is an alternative) to stay unkillable for 50 turns and use Doompriest to stay affinity friendly. Warcaster cannot be the stun target"
))


# WarTower — Brutal (Ultimate Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/wartower/  |  calc: https://deadwoodjedi.info/cb/e57042e0f0842133342b7261540aff1cd32bd14f
_register(TuneDefinition(
    name="WarTower (Brutal)",
    tune_id="wartower__brutal",
    tune_type="unkillable",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(247, 247), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(240, 240), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(175, 175), required_hero="Septimus", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4")
    ],
    notes="WarTower · Brutal (boss SPD 190 Ultimate Nightmare) · by Litooth · WarTower comp uses Warcaster and Roschard (Sir Nic is an alternative) to stay unkillable for 50 turns and use Doompriest to stay affinity friendly. Warcaster cannot be the stun target"
))


# What in the Hellmut — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/what-in-the-hellmut/  |  calc: https://deadwoodjedi.info/cb/c0c91f3760f37c014a337065af556dce6a3e9e23
_register(TuneDefinition(
    name="What in the Hellmut (Ultra Nightmare)",
    tune_id="what_in_the_hellmut__ultra_nightmare",
    tune_type="unkillable",
    difficulty="expert",
    performance="1_key_unm",
    affinities="void_only",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(186, 186), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(301, 301), required_hero="Archmage Hellmut", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=3; Lore of Steel"),
TuneSlot(role="dps", speed_range=(243, 243), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(225, 225), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(200, 200), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=4")
    ],
    notes="What in the Hellmut · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by Ilbey · Runs Archmage Hellmut at 3:1 Ratio with Seeker to provide permanent suite of buffs for your DPS champion."
))


# What in the Hellmut — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/what-in-the-hellmut/  |  calc: https://deadwoodjedi.info/cb/6579c6f69c5847a247ded6f06fd42c59d360e4b7
_register(TuneDefinition(
    name="What in the Hellmut (Nightmare)",
    tune_id="what_in_the_hellmut__nightmare",
    tune_type="unkillable",
    difficulty="expert",
    performance="1_key_unm",
    affinities="void_only",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(186, 186), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(301, 301), required_hero="Archmage Hellmut", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=2 CD=3; Lore of Steel"),
TuneSlot(role="dps", speed_range=(243, 243), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(225, 225), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(200, 200), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=4")
    ],
    notes="What in the Hellmut · Nightmare (boss SPD 170 Nightmare) · by Ilbey · Runs Archmage Hellmut at 3:1 Ratio with Seeker to provide permanent suite of buffs for your DPS champion."
))


# What in the Hellmut — Brutal (Brutal)
# Source: https://deadwoodjedi.com/speed-tunes/what-in-the-hellmut/  |  calc: https://deadwoodjedi.info/cb/8636f29eebee09aa608a41a8075acd635816974c
_register(TuneDefinition(
    name="What in the Hellmut (Brutal)",
    tune_id="what_in_the_hellmut__brutal",
    tune_type="unkillable",
    difficulty="expert",
    performance="1_key_unm",
    affinities="void_only",
    cb_speed=160,
    slots=[
        TuneSlot(role="dps", speed_range=(186, 186), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(301, 301), required_hero="Archmage Hellmut", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=3; Lore of Steel"),
TuneSlot(role="dps", speed_range=(243, 243), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(225, 225), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(200, 200), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=4")
    ],
    notes="What in the Hellmut · Brutal (boss SPD 160 Brutal) · by Ilbey · Runs Archmage Hellmut at 3:1 Ratio with Seeker to provide permanent suite of buffs for your DPS champion."
))


# White-Myth-Caster — Ninja  (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/white-myth-caster/  |  calc: https://deadwoodjedi.info/cb/af832892d9603b71e7258f87b39875bf0fed2fc5
_register(TuneDefinition(
    name="White-Myth-Caster (Ninja )",
    tune_id="white_myth_caster__ninja",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="block_damage", speed_range=(254, 254), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="White Dryad Nia", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=2 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(256, 256), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=2 CD=4"),
TuneSlot(role="ninja_tm_boost", speed_range=(195, 195), required_hero="Ninja", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(205, 205), required_hero="Martyr", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=2 CD=3; A3 pri=2 delay=0 CD=4")
    ],
    notes="White-Myth-Caster · Ninja (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Unkillable comp abusing Demytha's 3 turn cooldown block damage to stay unkillable!"
))


# White-Myth-Caster — UNM (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/white-myth-caster/  |  calc: https://deadwoodjedi.info/cb/23934ade338ccc2546c0341e868c0a575d4d998f
_register(TuneDefinition(
    name="White-Myth-Caster (UNM)",
    tune_id="white_myth_caster__unm",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="block_damage", speed_range=(254, 254), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="White Dryad Nia", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=2 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(256, 256), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=2 CD=4"),
TuneSlot(role="dps", speed_range=(195, 195), required_hero="Grizzled Jarl", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=1 CD=3; A3 pri=2 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(205, 205), required_hero="Jintoro", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3")
    ],
    notes="White-Myth-Caster · UNM (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Unkillable comp abusing Demytha's 3 turn cooldown block damage to stay unkillable!"
))


# 32 Team with Speed Booster — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/32-team-with-speed-booster/  |  calc: https://deadwoodjedi.info/cb/2b4b678fbc28651f0d562d2118d65a0901a9f08e
_register(TuneDefinition(
    name="32 Team with Speed Booster (Ultra Nightmare)",
    tune_id="32_team_with_speed_booster__ultra_nightmare",
    tune_type="traditional",
    difficulty="moderate",
    performance="3_key_unm",
    affinities="void_only",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(251, 251), required_hero="Tayrel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(238, 238), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(232, 232), required_hero="Kreela Witch-Arm", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(216, 216), required_hero="Iron Brago", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(171, 171), required_hero="Apothecary", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=2; A3 pri=3 delay=0 CD=3")
    ],
    notes="32 Team with Speed Booster · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by Cyborg · Speed booster makes the whole team go at a 3:2 turn ratio."
))


# 32 Team with Speed Booster — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/32-team-with-speed-booster/  |  calc: https://deadwoodjedi.info/cb/c1da452b3d87b6e51f5ad0804c72311f8037891b
_register(TuneDefinition(
    name="32 Team with Speed Booster (Nightmare)",
    tune_id="32_team_with_speed_booster__nightmare",
    tune_type="traditional",
    difficulty="moderate",
    performance="3_key_unm",
    affinities="void_only",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(251, 251), required_hero="Tayrel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(238, 238), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(232, 232), required_hero="Kreela Witch-Arm", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(216, 216), required_hero="Iron Brago", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(171, 171), required_hero="Apothecary", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=2; A3 pri=3 delay=0 CD=3")
    ],
    notes="32 Team with Speed Booster · Nightmare (boss SPD 170 Nightmare) · by Cyborg · Speed booster makes the whole team go at a 3:2 turn ratio."
))


# A Girl and Her Turtle — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/pavos-krisk-and-lydia/  |  calc: https://deadwoodjedi.info/cb/242361d7075fa0896077aca3e502018f7144c1f6
_register(TuneDefinition(
    name="A Girl and Her Turtle (Ultra Nightmare)",
    tune_id="pavos_krisk_and_lydia__ultra_nightmare",
    tune_type="traditional",
    difficulty="expert",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(199, 199), required_hero="Iron Brago", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(238, 238), required_hero="Krisk the Ageless", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(269, 269), required_hero="Underpriest Brogni", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(268, 268), required_hero="Lydia the Deathsiren", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=1 CD=3; A3 pri=2 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(200, 200), required_hero="Valkyrie", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="A Girl and Her Turtle · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by Pavo · Super Tanky World Record team utilizing Lydia (or another 30% speed buff on 3 turn CD with no TM boost) and Krisk."
))


# A Girl and Her Turtle — Alternate UNM (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/pavos-krisk-and-lydia/  |  calc: https://deadwoodjedi.info/cb/87daf5d8451981954d4817cc01755dc2533c8eed
_register(TuneDefinition(
    name="A Girl and Her Turtle (Alternate UNM)",
    tune_id="pavos_krisk_and_lydia__alternate_unm",
    tune_type="traditional",
    difficulty="expert",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(268, 268), required_hero="Lydia the Deathsiren", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=1 CD=3; A3 pri=2 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(244, 244), required_hero="Krisk the Ageless", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=3 CD=3"),
TuneSlot(role="dps", speed_range=(244, 244), required_hero="Altan", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(218, 218), required_hero="Valkyrie", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(199, 199), required_hero="Bad-el-Kazar", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="A Girl and Her Turtle · Alternate UNM (boss SPD 190 Ultra-Nightmare) · by Pavo · Super Tanky World Record team utilizing Lydia (or another 30% speed buff on 3 turn CD with no TM boost) and Krisk."
))


# Affinity Friendly Valkyrie — Ultra-Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/affinity-friendly-valkyrie/  |  calc: https://deadwoodjedi.info/cb/818476b217fdeb8534c8da68b62a508361c1ee39
_register(TuneDefinition(
    name="Affinity Friendly Valkyrie (Ultra-Nightmare)",
    tune_id="affinity_friendly_valkyrie__ultra_nightmare",
    tune_type="traditional",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(187, 187), required_hero="Tayrel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(171, 171), required_hero="Valkyrie", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(187, 187), required_hero="Marked", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(189, 189), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=2 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=2 CD=3")
    ],
    notes="Affinity Friendly Valkyrie · Ultra-Nightmare (boss SPD 190 Ultra-Nightmare) · by Beefeaterz · Speed ranges to maintain turn order with Valkyrie's Passive against affinity or void Clan Boss. Results will vary depending on your champions you use but speeds are quite low and should be a good entry point for people to challenge the Clan Boss."
))


# Affinity Friendly Valkyrie — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/affinity-friendly-valkyrie/  |  calc: https://deadwoodjedi.info/cb/4ca67f87025a9f5e93aacc88161c76a6d6aa9003
_register(TuneDefinition(
    name="Affinity Friendly Valkyrie (Nightmare)",
    tune_id="affinity_friendly_valkyrie__nightmare",
    tune_type="traditional",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(187, 187), required_hero="Tayrel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(171, 171), required_hero="Valkyrie", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(187, 187), required_hero="Marked", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(189, 189), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3")
    ],
    notes="Affinity Friendly Valkyrie · Nightmare (boss SPD 170 Nightmare) · by Beefeaterz · Speed ranges to maintain turn order with Valkyrie's Passive against affinity or void Clan Boss. Results will vary depending on your champions you use but speeds are quite low and should be a good entry point for people to challenge the Clan Boss."
))


# Affinity Friendly Valkyrie with two 4:3 Champs — Ultra-Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/affinity-friendly-valkyrie-with-two-43-champs/  |  calc: https://deadwoodjedi.info/cb/6b5a2e213096042ed8edb80b552f1363085a005a
_register(TuneDefinition(
    name="Affinity Friendly Valkyrie with two 4:3 Champs (Ultra-Nightmare)",
    tune_id="affinity_friendly_valkyrie_with_two_43_champs__ultra_nightmare",
    tune_type="traditional",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(172, 172), required_hero="Valkyrie", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(185, 185), required_hero="Vizier Ovelis", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(240, 240), required_hero="Steelskull", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=4"),
TuneSlot(role="dps", speed_range=(245, 245), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=4; A3 pri=3 delay=0 CD=0")
    ],
    notes="Affinity Friendly Valkyrie with two 4:3 Champs · Ultra-Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Speed ranges to maintain turn order with Valkyrie's Passive against affinity or void Clan Boss with multiple 4:3 Champions"
))


# Affinity Friendly Valkyrie with two 4:3 Champs — UNM Affinity (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/affinity-friendly-valkyrie-with-two-43-champs/  |  calc: https://deadwoodjedi.info/cb/01c8dd4a79c8c872f8abf7043bcf37c30c886295
_register(TuneDefinition(
    name="Affinity Friendly Valkyrie with two 4:3 Champs (UNM Affinity)",
    tune_id="affinity_friendly_valkyrie_with_two_43_champs__unm_affinity",
    tune_type="traditional",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(172, 172), required_hero="Valkyrie", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(185, 185), required_hero="Vizier Ovelis", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(240, 240), required_hero="Steelskull", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=4"),
TuneSlot(role="dps", speed_range=(245, 245), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=4; A3 pri=3 delay=0 CD=0")
    ],
    notes="Affinity Friendly Valkyrie with two 4:3 Champs · UNM Affinity (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Speed ranges to maintain turn order with Valkyrie's Passive against affinity or void Clan Boss with multiple 4:3 Champions"
))


# Affinity Friendly Valkyrie with two 4:3 Champs — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/affinity-friendly-valkyrie-with-two-43-champs/  |  calc: https://deadwoodjedi.info/cb/5be7eb69ef462c836a744cca0954b352d939f237
_register(TuneDefinition(
    name="Affinity Friendly Valkyrie with two 4:3 Champs (Nightmare)",
    tune_id="affinity_friendly_valkyrie_with_two_43_champs__nightmare",
    tune_type="traditional",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(172, 172), required_hero="Valkyrie", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(185, 185), required_hero="Vizier Ovelis", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(240, 240), required_hero="Steelskull", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=4"),
TuneSlot(role="dps", speed_range=(245, 245), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=4; A3 pri=3 delay=0 CD=0")
    ],
    notes="Affinity Friendly Valkyrie with two 4:3 Champs · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi · Speed ranges to maintain turn order with Valkyrie's Passive against affinity or void Clan Boss with multiple 4:3 Champions"
))


# Affinity Friendly Valkyrie with two 4:3 Champs — Nightmare Affinity (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/affinity-friendly-valkyrie-with-two-43-champs/  |  calc: https://deadwoodjedi.info/cb/f40413bdbf12799bb22e6181521c5ed12a35d886
_register(TuneDefinition(
    name="Affinity Friendly Valkyrie with two 4:3 Champs (Nightmare Affinity)",
    tune_id="affinity_friendly_valkyrie_with_two_43_champs__nightmare_affinity",
    tune_type="traditional",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(172, 172), required_hero="Valkyrie", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(185, 185), required_hero="Vizier Ovelis", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(240, 240), required_hero="Steelskull", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=4"),
TuneSlot(role="dps", speed_range=(245, 245), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=4; A3 pri=3 delay=0 CD=0")
    ],
    notes="Affinity Friendly Valkyrie with two 4:3 Champs · Nightmare Affinity (boss SPD 170 Nightmare) · by DeadwoodJedi · Speed ranges to maintain turn order with Valkyrie's Passive against affinity or void Clan Boss with multiple 4:3 Champions"
))


# Basic — Ultra-Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/basic/  |  calc: https://deadwoodjedi.info/cb/0042dac2ec21fa00d0c5ff70f490c50b799aecaa
_register(TuneDefinition(
    name="Basic (Ultra-Nightmare)",
    tune_id="basic__ultra_nightmare",
    tune_type="traditional",
    difficulty="easy",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(185, 185), required_hero="Bulwark", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(205, 205), required_hero="Nazana", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(194, 194), required_hero="Tayrel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Basic · Ultra-Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Simple 1:1 ratio speed tune which is the foundation for every other speed tune we've created."
))


# Basic — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/basic/  |  calc: https://deadwoodjedi.info/cb/316d86d42910e12b5d3cd094657970e4e6003818
_register(TuneDefinition(
    name="Basic (Nightmare)",
    tune_id="basic__nightmare",
    tune_type="traditional",
    difficulty="easy",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(185, 185), required_hero="Bulwark", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(205, 205), required_hero="Nazana", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(194, 194), required_hero="Tayrel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Basic · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi · Simple 1:1 ratio speed tune which is the foundation for every other speed tune we've created."
))


# Batman — UNM / NM / Brutal (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/batman/  |  calc: https://deadwoodjedi.info/cb/d6ddb1c511dcb86d17d1395a7ea65685b36a543c
_register(TuneDefinition(
    name="Batman (UNM / NM / Brutal)",
    tune_id="batman__unm_nm_brutal",
    tune_type="traditional",
    difficulty="hard",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(265, 265), required_hero="Valkyrie", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(248, 248), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(247, 247), required_hero="Iron Brago", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(246, 246), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(220, 220), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6")
    ],
    notes="Batman · UNM / NM / Brutal (boss SPD 190 Ultra-Nightmare) · by Napoleon Camembert · This is the general 2:1 speed tune with Seeker. It utilizes Seeker's TM boost to give everyone a second turn before CB goes. This can be made affinity friendly by either introducing a cleanser or a [Block Debuffs] buffer."
))


# Batman — Brutal (Brutal)
# Source: https://deadwoodjedi.com/speed-tunes/batman/  |  calc: https://deadwoodjedi.info/cb/05269bee89aaf48e149c26b1d326768404852e3e
_register(TuneDefinition(
    name="Batman (Brutal)",
    tune_id="batman__brutal",
    tune_type="traditional",
    difficulty="hard",
    performance="1_key_unm",
    affinities="all",
    cb_speed=160,
    slots=[
        TuneSlot(role="dps", speed_range=(265, 265), required_hero="Valkyrie", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(248, 248), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(247, 247), required_hero="Iron Brago", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(246, 246), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(220, 220), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6")
    ],
    notes="Batman · Brutal (boss SPD 160 Brutal) · by Napoleon Camembert · This is the general 2:1 speed tune with Seeker. It utilizes Seeker's TM boost to give everyone a second turn before CB goes. This can be made affinity friendly by either introducing a cleanser or a [Block Debuffs] buffer."
))


# BatManSaladEater — UNM / NM / Brutal (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/batmansaladeater/  |  calc: https://deadwoodjedi.info/cb/a4b559b61648ecb047c589d856c3999fe43adc24
_register(TuneDefinition(
    name="BatManSaladEater (UNM / NM / Brutal)",
    tune_id="batmansaladeater__unm_nm_brutal",
    tune_type="traditional",
    difficulty="expert",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(288, 288), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=4 CD=5"),
TuneSlot(role="dps", speed_range=(287, 287), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="dps", speed_range=(239, 239), required_hero="Ma'Shalled", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=2 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(221, 221), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(187, 187), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4")
    ],
    notes="BatManSaladEater · UNM / NM / Brutal (boss SPD 190 Ultra-Nightmare) · by TheDragonsBeard, Optilink, and Bobo · BatEater w/ Ma'Shalled instead of Pain Keeper; Maneaters going at a 5:2"
))


# Double Counter-Attack — Ultra-Nightmare (Ultimate Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/double-counter-attack/  |  calc: https://deadwoodjedi.info/cb/44e5e748161ef8ac917676f622f1fb62e90b0260
_register(TuneDefinition(
    name="Double Counter-Attack (Ultra-Nightmare)",
    tune_id="double_counter_attack__ultra_nightmare",
    tune_type="traditional",
    difficulty="easy",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(173, 173), required_hero="Bulwark", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Martyr", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=2 CD=3; A3 pri=2 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(182, 182), required_hero="Tayrel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Double Counter-Attack · Ultra-Nightmare (boss SPD 190 Ultimate Nightmare) · Using 2 Counter-Attack Champions to stay survive longer and maximize damage."
))


# Double Counter-Attack — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/double-counter-attack/  |  calc: https://deadwoodjedi.info/cb/9f877ac4013f566270c2184d8fb0412eaabb51e9
_register(TuneDefinition(
    name="Double Counter-Attack (Nightmare)",
    tune_id="double_counter_attack__nightmare",
    tune_type="traditional",
    difficulty="easy",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(173, 173), required_hero="Bulwark", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Martyr", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=2 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(182, 182), required_hero="Tayrel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Double Counter-Attack · Nightmare (boss SPD 170 Nightmare) · Using 2 Counter-Attack Champions to stay survive longer and maximize damage."
))


# Double Warcaster — Ultra Nightmare - Skullcrusher (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/double-warcaster/  |  calc: https://deadwoodjedi.info/cb/6ab012951c83794fec2c68bb4966191cd291aa54
_register(TuneDefinition(
    name="Double Warcaster (Ultra Nightmare - Skullcrusher)",
    tune_id="double_warcaster__ultra_nightmare_skullcrusher",
    tune_type="traditional",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(256, 256), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(255, 255), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=4; Lore of Steel"),
TuneSlot(role="dps", speed_range=(211, 211), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(210, 210), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(209, 209), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Double Warcaster · Ultra Nightmare - Skullcrusher (boss SPD 190 Ultra-Nightmare) · by Skratch AK47 · Double Warcaster blocks the AOEs and Bushi or Skullcrusher takes the stun."
))


# Double Warcaster — Bushi-Turn-2-or-3-Death (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/double-warcaster/  |  calc: https://deadwoodjedi.info/cb/0a78700d959fe911aa258d4d502b5984a4339c13
_register(TuneDefinition(
    name="Double Warcaster (Bushi-Turn-2-or-3-Death)",
    tune_id="double_warcaster__bushi_turn_2_or_3_death",
    tune_type="traditional",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(256, 256), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(255, 255), required_hero="Warcaster", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=4; Lore of Steel"),
TuneSlot(role="dps", speed_range=(211, 211), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(210, 210), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(209, 209), required_hero="Bushi", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Double Warcaster · Bushi-Turn-2-or-3-Death (boss SPD 190 Ultra-Nightmare) · by Skratch AK47 · Double Warcaster blocks the AOEs and Bushi or Skullcrusher takes the stun."
))


# Drokgul Unkillable — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/drokgul-unkillable/  |  calc: https://deadwoodjedi.info/cb/13dc320a523c65953af4e58698a8ead13ea64a0a
_register(TuneDefinition(
    name="Drokgul Unkillable (Ultra Nightmare)",
    tune_id="drokgul_unkillable__ultra_nightmare",
    tune_type="traditional",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(287, 287), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="dps", speed_range=(207, 207), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=2 CD=3; Lore of Steel"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=2 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Bulwark", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Drokgul the Gaunt", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=2 CD=3; A3 pri=2 delay=0 CD=4")
    ],
    notes="Drokgul Unkillable · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Unkillable team using Drokgul and Maneater."
))


# Drokgul Unkillable — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/drokgul-unkillable/  |  calc: https://deadwoodjedi.info/cb/bd7be56a2558e205cf09716a604bc00181d7fea1
_register(TuneDefinition(
    name="Drokgul Unkillable (Nightmare)",
    tune_id="drokgul_unkillable__nightmare",
    tune_type="traditional",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(287, 287), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=5; Lore of Steel"),
TuneSlot(role="dps", speed_range=(182, 182), required_hero="Suwai Firstborn", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4; Lore of Steel"),
TuneSlot(role="dps", speed_range=(159, 159), required_hero="Vizier Ovelis", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(168, 168), required_hero="Aothar", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Drokgul the Gaunt", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=3 CD=3; A3 pri=2 delay=0 CD=4")
    ],
    notes="Drokgul Unkillable · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi · Unkillable team using Drokgul and Maneater."
))


# Endless Speed — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/endless-speed/  |  calc: https://deadwoodjedi.info/cb/afcf42b22ea88a1550099ff8d44e63ab28d04ba5
_register(TuneDefinition(
    name="Endless Speed (Ultra Nightmare)",
    tune_id="endless_speed__ultra_nightmare",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(240, 240), required_hero="Tayrel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(229, 229), required_hero="Iron Brago", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(226, 226), required_hero="Apothecary", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=2; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(197, 197), required_hero="Sandlashed Survivor", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(178, 178), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=1 CD=3; A3 pri=1 delay=0 CD=6")
    ],
    notes="Endless Speed · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Fully auto 3:2 turn ratio for the whole team with a speed booster and buff extender"
))


# Endless Speed — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/endless-speed/  |  calc: https://deadwoodjedi.info/cb/b8d1b23a4fa72bbd313959ce06821b4a7e379322
_register(TuneDefinition(
    name="Endless Speed (Nightmare)",
    tune_id="endless_speed__nightmare",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(240, 240), required_hero="Tayrel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(229, 229), required_hero="Iron Brago", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(226, 226), required_hero="Apothecary", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=2; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(197, 197), required_hero="Sandlashed Survivor", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(178, 178), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=1 CD=3; A3 pri=1 delay=0 CD=6")
    ],
    notes="Endless Speed · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi · Fully auto 3:2 turn ratio for the whole team with a speed booster and buff extender"
))


# Fanatic White Whale — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/fanatic-white-whale/  |  calc: https://deadwoodjedi.info/cb/19e930cdfeb448aa8745eab71dfa777819ba7fb2
_register(TuneDefinition(
    name="Fanatic White Whale (Nightmare)",
    tune_id="fanatic_white_whale__nightmare",
    tune_type="traditional",
    difficulty="easy",
    performance="4_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(221, 221), required_hero="High Khatun", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=1 CD=3; A3 pri=2 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(206, 206), required_hero="Apothecary", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=2; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(209, 209), required_hero="Coffin Smasher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(200, 200), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(116, 116), required_hero="Fanatic", opening=['A1'], skill_priority=['A1', 'Cleanse', 'A3'], notes="A1 pri=1 delay=0 CD=0; Cleanse pri=2 delay=3 CD=4; A3 pri=3 delay=0 CD=0")
    ],
    notes="Fanatic White Whale · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi · 2:1 turn ratio for NM using two speed boosters and fanatic to cleanse the stun."
))


# Fanatic White Whale — Brutal (Brutal)
# Source: https://deadwoodjedi.com/speed-tunes/fanatic-white-whale/  |  calc: https://deadwoodjedi.info/cb/1eb015250b468ac01d5b3fd8daba9db0188287ff
_register(TuneDefinition(
    name="Fanatic White Whale (Brutal)",
    tune_id="fanatic_white_whale__brutal",
    tune_type="traditional",
    difficulty="easy",
    performance="4_key_unm",
    affinities="all",
    cb_speed=160,
    slots=[
        TuneSlot(role="dps", speed_range=(221, 221), required_hero="High Khatun", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=1 CD=3; A3 pri=2 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(206, 206), required_hero="Apothecary", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=2; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(209, 209), required_hero="Coffin Smasher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(200, 200), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(116, 116), required_hero="Fanatic", opening=['A1'], skill_priority=['A1', 'Cleanse', 'A3'], notes="A1 pri=1 delay=0 CD=0; Cleanse pri=2 delay=3 CD=4; A3 pri=3 delay=0 CD=0")
    ],
    notes="Fanatic White Whale · Brutal (boss SPD 160 Brutal) · by DeadwoodJedi · 2:1 turn ratio for NM using two speed boosters and fanatic to cleanse the stun."
))


# Fast Double Maneater — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/fast-double-maneater/  |  calc: https://deadwoodjedi.info/cb/a94676f8b2f53346fc64b87b9f0a74ca4828f4f8
_register(TuneDefinition(
    name="Fast Double Maneater (Ultra Nightmare)",
    tune_id="fast_double_maneater__ultra_nightmare",
    tune_type="traditional",
    difficulty="easy",
    performance="4_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(248, 248), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="dps", speed_range=(245, 245), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=5"),
TuneSlot(role="dps", speed_range=(211, 211), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(207, 207), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(205, 205), required_hero="Bulwark", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Fast Double Maneater · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · Fast Double Maneater Unkillable team that is fully affinity friendly. UNM or NM only. Recommend using the Easy Double Maneater Unkillable team instead."
))


# Fast Double Maneater — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/fast-double-maneater/  |  calc: https://deadwoodjedi.info/cb/466d53e6f01935379f55da212ec91f5884e76089
_register(TuneDefinition(
    name="Fast Double Maneater (Nightmare)",
    tune_id="fast_double_maneater__nightmare",
    tune_type="traditional",
    difficulty="easy",
    performance="4_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(226, 226), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="dps", speed_range=(223, 223), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=5"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(175, 175), required_hero="Bulwark", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Fast Double Maneater · Nightmare (boss SPD 170 Nightmare) · Fast Double Maneater Unkillable team that is fully affinity friendly. UNM or NM only. Recommend using the Easy Double Maneater Unkillable team instead."
))


# Fast Double Maneater — Easy Double ME - NM (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/fast-double-maneater/  |  calc: https://deadwoodjedi.info/cb/aa6428723d8657aef0192993ee43487338f29257
_register(TuneDefinition(
    name="Fast Double Maneater (Easy Double ME - NM)",
    tune_id="fast_double_maneater__easy_double_me_nm",
    tune_type="traditional",
    difficulty="easy",
    performance="4_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(220, 220), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=5"),
TuneSlot(role="dps", speed_range=(215, 215), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=4 CD=5"),
TuneSlot(role="dps", speed_range=(175, 175), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(168, 168), required_hero="Bulwark", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Fast Double Maneater · Easy Double ME - NM (boss SPD 170 Nightmare) · Fast Double Maneater Unkillable team that is fully affinity friendly. UNM or NM only. Recommend using the Easy Double Maneater Unkillable team instead."
))


# Fast Single 4:3 Champion — Ultra-Nightmare, 4:3 after Stun v1 (Ultimate Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/fast-single-43-champ/  |  calc: https://deadwoodjedi.info/cb/4626587fbeeee97bc80bbf357e98ed20aedd409e
_register(TuneDefinition(
    name="Fast Single 4:3 Champion (Ultra-Nightmare, 4:3 after Stun v1)",
    tune_id="fast_single_43_champ__ultra_nightmare_4_3_after_stun_v1",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(256, 256), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(191, 191), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(196, 196), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(192, 192), required_hero="Tayrel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(193, 193), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=6")
    ],
    notes="Fast Single 4:3 Champion · Ultra-Nightmare, 4:3 after Stun v1 (boss SPD 190 Ultimate Nightmare) · 1 Champ moves at a 4:3 ratio, taking a double turn on Ultra-Nightmare and Nightmare. Perfect for champions with 4 turn cooldowns!"
))


# Fast Single 4:3 Champion — Ultra-Nightmare, 4:3 between AOE's v1 (Ultimate Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/fast-single-43-champ/  |  calc: https://deadwoodjedi.info/cb/5349717266c622f0bcdf232109ad59990f897cfa
_register(TuneDefinition(
    name="Fast Single 4:3 Champion (Ultra-Nightmare, 4:3 between AOE's v1)",
    tune_id="fast_single_43_champ__ultra_nightmare_4_3_between_aoe_s_v1",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(256, 256), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(191, 191), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(207, 207), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(192, 192), required_hero="Tayrel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(193, 193), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=6")
    ],
    notes="Fast Single 4:3 Champion · Ultra-Nightmare, 4:3 between AOE's v1 (boss SPD 190 Ultimate Nightmare) · 1 Champ moves at a 4:3 ratio, taking a double turn on Ultra-Nightmare and Nightmare. Perfect for champions with 4 turn cooldowns!"
))


# Fast Single 4:3 Champion — Ultra-Nightmare, 4:3 after AOE's v2 (Ultimate Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/fast-single-43-champ/  |  calc: https://deadwoodjedi.info/cb/bb094379c54691bf36a742ef9767e4d43ab11740
_register(TuneDefinition(
    name="Fast Single 4:3 Champion (Ultra-Nightmare, 4:3 after AOE's v2)",
    tune_id="fast_single_43_champ__ultra_nightmare_4_3_after_aoe_s_v2",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(260, 260), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(191, 191), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(196, 196), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(192, 192), required_hero="Tayrel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(193, 193), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=6")
    ],
    notes="Fast Single 4:3 Champion · Ultra-Nightmare, 4:3 after AOE's v2 (boss SPD 190 Ultimate Nightmare) · 1 Champ moves at a 4:3 ratio, taking a double turn on Ultra-Nightmare and Nightmare. Perfect for champions with 4 turn cooldowns!"
))


# Fast Single 4:3 Champion — Ultra-Nightmare, 4:3 after Stun v2 (Ultimate Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/fast-single-43-champ/  |  calc: https://deadwoodjedi.info/cb/712d62033410c1d407eb41dab283a56f17beda60
_register(TuneDefinition(
    name="Fast Single 4:3 Champion (Ultra-Nightmare, 4:3 after Stun v2)",
    tune_id="fast_single_43_champ__ultra_nightmare_4_3_after_stun_v2",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(260, 260), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(191, 191), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(207, 207), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(192, 192), required_hero="Tayrel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(193, 193), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=6")
    ],
    notes="Fast Single 4:3 Champion · Ultra-Nightmare, 4:3 after Stun v2 (boss SPD 190 Ultimate Nightmare) · 1 Champ moves at a 4:3 ratio, taking a double turn on Ultra-Nightmare and Nightmare. Perfect for champions with 4 turn cooldowns!"
))


# Get Nekh-REKT — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/get-nekh-rekt/  |  calc: https://deadwoodjedi.info/cb/540b957cf4d06628f3e31e15b37ad45b0aea3900
_register(TuneDefinition(
    name="Get Nekh-REKT (Ultra Nightmare)",
    tune_id="get_nekh_rekt__ultra_nightmare",
    tune_type="traditional",
    difficulty="extreme",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(234, 234), required_hero="Martyr", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=1 CD=3; A3 pri=2 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(221, 221), required_hero="Ma'Shalled", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=1 CD=3; A3 pri=2 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(259, 259), required_hero="Krisk the Ageless", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(184, 184), required_hero="Nekhret the Great", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=2; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(190, 190), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3")
    ],
    notes="Get Nekh-REKT · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Using Nekhret, Krisk, and Ma'Shalled to create a monstrosity."
))


# Get Nekh-REKT — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/get-nekh-rekt/  |  calc: https://deadwoodjedi.info/cb/4a64fe8bed59c4d1fe3d8f47426da5be8d7ade1a
_register(TuneDefinition(
    name="Get Nekh-REKT (Nightmare)",
    tune_id="get_nekh_rekt__nightmare",
    tune_type="traditional",
    difficulty="extreme",
    performance="1_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(234, 234), required_hero="Martyr", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=2 CD=3; A3 pri=2 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(221, 221), required_hero="Ma'Shalled", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=2 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(259, 259), required_hero="Krisk the Ageless", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(184, 184), required_hero="Nekhret the Great", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=2; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(190, 190), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3")
    ],
    notes="Get Nekh-REKT · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi · Using Nekhret, Krisk, and Ma'Shalled to create a monstrosity."
))


# Heaven and Hell — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/heaven-and-hell/  |  calc: https://deadwoodjedi.info/cb/f8002f7095e8565e2305acef640756960d8c9842
_register(TuneDefinition(
    name="Heaven and Hell (Ultra Nightmare)",
    tune_id="heaven_and_hell__ultra_nightmare",
    tune_type="traditional",
    difficulty="expert",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(252, 252), required_hero="Ma'Shalled", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=1 CD=3; A3 pri=2 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(251, 251), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="dps", speed_range=(225, 225), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(204, 204), required_hero="Belanor", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=4 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(187, 187), required_hero="Prince Kymar", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=6")
    ],
    notes="Heaven and Hell · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Ma'Shalled 2:1 team using Kymar, Maneater, and Skullcrusher to be unkillable, while Belanor rains holy wrath."
))


# Heaven and Hell — Nightmare / Brutal (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/heaven-and-hell/  |  calc: https://deadwoodjedi.info/cb/7dca1b040f5b6bf47c5efb386f9f47e5f3d2c66e
_register(TuneDefinition(
    name="Heaven and Hell (Nightmare / Brutal)",
    tune_id="heaven_and_hell__nightmare_brutal",
    tune_type="traditional",
    difficulty="expert",
    performance="1_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(252, 252), required_hero="Ma'Shalled", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=2 CD=3; A3 pri=2 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(251, 251), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="dps", speed_range=(225, 225), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(204, 204), required_hero="Belanor", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=4 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(187, 187), required_hero="Prince Kymar", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=6")
    ],
    notes="Heaven and Hell · Nightmare / Brutal (boss SPD 170 Nightmare) · by DeadwoodJedi · Ma'Shalled 2:1 team using Kymar, Maneater, and Skullcrusher to be unkillable, while Belanor rains holy wrath."
))


# Heiress 3x 43 Champs — UNM - Cleanse Stun (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/heiress-3x-43-champs/  |  calc: https://deadwoodjedi.info/cb/2f6f248c3066f2584e92f74e57b3807019b730c1
_register(TuneDefinition(
    name="Heiress 3x 43 Champs (UNM - Cleanse Stun)",
    tune_id="heiress_3x_43_champs__unm_cleanse_stun",
    tune_type="traditional",
    difficulty="moderate",
    performance="3_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(166, 166), required_hero="Heiress", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=2 CD=0"),
TuneSlot(role="dps", speed_range=(165, 165), required_hero="165", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=0; A3 pri=1 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(209, 209), required_hero="209", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(221, 221), required_hero="221", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(245, 245), required_hero="245", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0")
    ],
    notes="Heiress 3x 43 Champs · UNM - Cleanse Stun (boss SPD 190 Ultra-Nightmare) · by Shadok, optilink · Use Heiress to get three champions going at a 4:3 turn ratio."
))


# Heiress 3x 43 Champs — UNM - Cleanse Affinity (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/heiress-3x-43-champs/  |  calc: https://deadwoodjedi.info/cb/28a93dc12bcb7003d6852998504fb2a9e5968187
_register(TuneDefinition(
    name="Heiress 3x 43 Champs (UNM - Cleanse Affinity)",
    tune_id="heiress_3x_43_champs__unm_cleanse_affinity",
    tune_type="traditional",
    difficulty="moderate",
    performance="3_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(166, 166), required_hero="Heiress", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=2 CD=0"),
TuneSlot(role="dps", speed_range=(165, 165), required_hero="165", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=0; A3 pri=1 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(209, 209), required_hero="209", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(221, 221), required_hero="221", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(245, 245), required_hero="245", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0")
    ],
    notes="Heiress 3x 43 Champs · UNM - Cleanse Affinity (boss SPD 190 Ultra-Nightmare) · by Shadok, optilink · Use Heiress to get three champions going at a 4:3 turn ratio."
))


# Heiress 3x 43 Champs — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/heiress-3x-43-champs/  |  calc: https://deadwoodjedi.info/cb/ca08a1b2d4bb8baa5bfb2d6606887f3af72743b4
_register(TuneDefinition(
    name="Heiress 3x 43 Champs (Nightmare)",
    tune_id="heiress_3x_43_champs__nightmare",
    tune_type="traditional",
    difficulty="moderate",
    performance="3_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(214, 214), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(165, 165), required_hero="165", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=0; A3 pri=1 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(209, 209), required_hero="209", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(221, 221), required_hero="221", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(245, 245), required_hero="245", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0")
    ],
    notes="Heiress 3x 43 Champs · Nightmare (boss SPD 170 Nightmare) · by Shadok, optilink · Use Heiress to get three champions going at a 4:3 turn ratio."
))


# HellBatEater — UNM / NM / Brutal (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/hellbateater/  |  calc: https://deadwoodjedi.info/cb/7c3e6c5c98de2d7ef29804556ed3d8bc46d3989a
_register(TuneDefinition(
    name="HellBatEater (UNM / NM / Brutal)",
    tune_id="hellbateater__unm_nm_brutal",
    tune_type="traditional",
    difficulty="hard",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(306, 306), required_hero="Archmage Hellmut", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=3; Lore of Steel"),
TuneSlot(role="dps", speed_range=(287, 287), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3', '1 Turn Delay A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=4 CD=5; 1 Turn Delay A3 pri=4 delay=9 CD=999"),
TuneSlot(role="dps", speed_range=(286, 286), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=5"),
TuneSlot(role="dps", speed_range=(222, 222), required_hero="Seeker", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(220, 220), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4")
    ],
    notes="HellBatEater · UNM / NM / Brutal (boss SPD 190 Ultra-Nightmare) · by Toshy, Bobo · Hellmut-Seeker-Double ME Unkillable team that doesn't work on Force."
))


# High Myth Man — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/high-myth-man/  |  calc: https://deadwoodjedi.info/cb/99b21955d885b6d81c7c9bde85ec3a31a64bf4d2
_register(TuneDefinition(
    name="High Myth Man (Ultra Nightmare)",
    tune_id="high_myth_man__ultra_nightmare",
    tune_type="traditional",
    difficulty="easy",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(119, 119), required_hero="High Khatun", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=2 delay=0 CD=4"),
TuneSlot(role="block_damage", speed_range=(112, 112), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(245, 245), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=5"),
TuneSlot(role="dps", speed_range=(125, 125), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(122, 122), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3")
    ],
    notes="High Myth Man · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by ShortOnSkillz · Budget Version of Demytha and Maneater by utilizing High Khatun and slow speeds."
))


# High Myth Man — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/high-myth-man/  |  calc: https://deadwoodjedi.info/cb/10c82b61cd1c2b5467a8839cf166985297e1721b
_register(TuneDefinition(
    name="High Myth Man (Nightmare)",
    tune_id="high_myth_man__nightmare",
    tune_type="traditional",
    difficulty="easy",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(111, 111), required_hero="High Khatun", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=2 CD=3; A3 pri=2 delay=0 CD=4"),
TuneSlot(role="block_damage", speed_range=(112, 112), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(245, 245), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=5"),
TuneSlot(role="dps", speed_range=(125, 125), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(122, 122), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3")
    ],
    notes="High Myth Man · Nightmare (boss SPD 170 Nightmare) · by ShortOnSkillz · Budget Version of Demytha and Maneater by utilizing High Khatun and slow speeds."
))


# High Myth Man — Spirit Affinity (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/high-myth-man/  |  calc: https://deadwoodjedi.info/cb/f087e582c82d09abc1ecf750a8c303068587f516
_register(TuneDefinition(
    name="High Myth Man (Spirit Affinity)",
    tune_id="high_myth_man__spirit_affinity",
    tune_type="traditional",
    difficulty="easy",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(119, 119), required_hero="High Khatun", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=2 delay=0 CD=4"),
TuneSlot(role="block_damage", speed_range=(112, 112), required_hero="Demytha", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(245, 245), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3', 'MANUAL DELAY'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5; MANUAL DELAY pri=4 delay=6 CD=999"),
TuneSlot(role="dps", speed_range=(125, 125), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(122, 122), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3")
    ],
    notes="High Myth Man · Spirit Affinity (boss SPD 190 Ultra-Nightmare) · by ShortOnSkillz · Budget Version of Demytha and Maneater by utilizing High Khatun and slow speeds."
))


# Krisk 4:3 Slow Tune — Ultra-Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/krisk-43-slow-tune/  |  calc: https://deadwoodjedi.info/cb/8e4b183b6a4991f09456096eb2268b9d36c068be
_register(TuneDefinition(
    name="Krisk 4:3 Slow Tune (Ultra-Nightmare)",
    tune_id="krisk_43_slow_tune__ultra_nightmare",
    tune_type="traditional",
    difficulty="moderate",
    performance="3_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(206, 206), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(137, 137), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(145, 145), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(155, 155), required_hero="Tayrel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(191, 191), required_hero="Krisk the Ageless", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=1 CD=3")
    ],
    notes="Krisk 4:3 Slow Tune · Ultra-Nightmare (boss SPD 190 Ultra-Nightmare) · Uses Krisks ally speed buff and extend buff ability to let everyone have less speed to move faster, with one champ moving at 4:3. Perfect for early level accounts!"
))


# Krisk 4:3 Slow Tune — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/krisk-43-slow-tune/  |  calc: https://deadwoodjedi.info/cb/9375138946e17b4d91145f6ae3e305047d6d9ba4
_register(TuneDefinition(
    name="Krisk 4:3 Slow Tune (Nightmare)",
    tune_id="krisk_43_slow_tune__nightmare",
    tune_type="traditional",
    difficulty="moderate",
    performance="3_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(206, 206), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(137, 137), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(145, 145), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(155, 155), required_hero="Tayrel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(191, 191), required_hero="Krisk the Ageless", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=1 CD=3")
    ],
    notes="Krisk 4:3 Slow Tune · Nightmare (boss SPD 170 Nightmare) · Uses Krisks ally speed buff and extend buff ability to let everyone have less speed to move faster, with one champ moving at 4:3. Perfect for early level accounts!"
))


# Krisk Slow Tune — Ultra-Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/krisk-slow-tune/  |  calc: https://deadwoodjedi.info/cb/25ad6569b894c1b1f5969514be168291e1655d0d
_register(TuneDefinition(
    name="Krisk Slow Tune (Ultra-Nightmare)",
    tune_id="krisk_slow_tune__ultra_nightmare",
    tune_type="traditional",
    difficulty="easy",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(155, 155), required_hero="Bulwark", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(142, 142), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(145, 145), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(137, 137), required_hero="Grizzled Jarl", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=2 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(191, 191), required_hero="Krisk the Ageless", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3")
    ],
    notes="Krisk Slow Tune · Ultra-Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Uses Krisks ally speed buff and extend buff ability to let everyone have less speed to move faster. Perfect for early level accounts!"
))


# Krisk Slow Tune — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/krisk-slow-tune/  |  calc: https://deadwoodjedi.info/cb/43cd9dd141e732d62db54d875f46d9495b50611e
_register(TuneDefinition(
    name="Krisk Slow Tune (Nightmare)",
    tune_id="krisk_slow_tune__nightmare",
    tune_type="traditional",
    difficulty="easy",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(147, 147), required_hero="Bulwark", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(142, 142), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(145, 145), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(137, 137), required_hero="Grizzled Jarl", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=2 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(191, 191), required_hero="Krisk the Ageless", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3")
    ],
    notes="Krisk Slow Tune · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi · Uses Krisks ally speed buff and extend buff ability to let everyone have less speed to move faster. Perfect for early level accounts!"
))


# Ma'shalled White Whale — v.1 Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/mashalled-white-whale/  |  calc: https://deadwoodjedi.info/cb/072a385d7b9996f0414b558ad5f0357ac16f70ba
_register(TuneDefinition(
    name="Ma'shalled White Whale (v.1 Ultra Nightmare)",
    tune_id="mashalled_white_whale__v_1_ultra_nightmare",
    tune_type="traditional",
    difficulty="moderate",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(252, 252), required_hero="Valkyrie", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(251, 251), required_hero="Blind Seer", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=2 CD=3; A3 pri=1 delay=0 CD=5"),
TuneSlot(role="dps", speed_range=(214, 214), required_hero="Iron Brago", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=2 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(191, 191), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(238, 238), required_hero="Ma'Shalled", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=1 CD=3; A3 pri=2 delay=0 CD=3")
    ],
    notes="Ma'shalled White Whale · v.1 Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi, Optilink · Multiple versions of a 2:1 Ratio Team with Ma'Shalled. Excellent entry build into faster clan boss teams"
))


# Ma'shalled White Whale — v.1 UNM - Slower Speeds (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/mashalled-white-whale/  |  calc: https://deadwoodjedi.info/cb/cedcbfac8f3fa949111d3b06843b788c7dbeab59
_register(TuneDefinition(
    name="Ma'shalled White Whale (v.1 UNM - Slower Speeds)",
    tune_id="mashalled_white_whale__v_1_unm_slower_speeds",
    tune_type="traditional",
    difficulty="moderate",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(251, 251), required_hero="Valkyrie", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(230, 230), required_hero="Underpriest Brogni", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(212, 212), required_hero="Iron Brago", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=2 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(191, 191), required_hero="Dracomorph", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(238, 238), required_hero="Ma'Shalled", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=1 CD=3; A3 pri=2 delay=0 CD=3")
    ],
    notes="Ma'shalled White Whale · v.1 UNM - Slower Speeds (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi, Optilink · Multiple versions of a 2:1 Ratio Team with Ma'Shalled. Excellent entry build into faster clan boss teams"
))


# Ma'shalled White Whale — v.2 Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/mashalled-white-whale/  |  calc: https://deadwoodjedi.info/cb/07ae9b667056cc05487f385974e1a741f051d15d
_register(TuneDefinition(
    name="Ma'shalled White Whale (v.2 Ultra Nightmare)",
    tune_id="mashalled_white_whale__v_2_ultra_nightmare",
    tune_type="traditional",
    difficulty="moderate",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(252, 252), required_hero="Ma'Shalled", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=1 CD=3; A3 pri=2 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(251, 251), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(225, 225), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(205, 205), required_hero="Iron Brago", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(187, 187), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Ma'shalled White Whale · v.2 Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi, Optilink · Multiple versions of a 2:1 Ratio Team with Ma'Shalled. Excellent entry build into faster clan boss teams"
))


# One Hellmut of a Team — UNM / NM / Brutal (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/one-hellmut-of-a-team/  |  calc: https://deadwoodjedi.info/cb/42c04ad9d81bc08a0554ff2bba4bb33d395ae73d
_register(TuneDefinition(
    name="One Hellmut of a Team (UNM / NM / Brutal)",
    tune_id="one_hellmut_of_a_team__unm_nm_brutal",
    tune_type="traditional",
    difficulty="hard",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(238, 238), required_hero="Godseeker Aniri", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(268, 268), required_hero="Archmage Hellmut", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(238, 238), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(218, 218), required_hero="Iron Brago", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(262, 262), required_hero="Valkyrie", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="One Hellmut of a Team · UNM / NM / Brutal (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Use Archmage Hellmut and an Extender to achieve a 2:1 ratio."
))


# Razzle Dazzle Counter-Attack — UNM & NM (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/razzle-dazzle-counter-attack/  |  calc: https://deadwoodjedi.info/cb/b467e0c12a04fdf8e2f9b3f5f04559e3bf700df6
_register(TuneDefinition(
    name="Razzle Dazzle Counter-Attack (UNM & NM)",
    tune_id="razzle_dazzle_counter_attack__unm_nm",
    tune_type="traditional",
    difficulty="moderate",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(236, 236), required_hero="Razelvarg", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(244, 244), required_hero="Corvis the Corruptor", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=1 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(210, 210), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(182, 182), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(230, 230), required_hero="Pythion", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Razzle Dazzle Counter-Attack · UNM & NM (boss SPD 190 Ultra-Nightmare) · by ShortonSkillz · Clan Boss team focused around the crazy speeds of Razelvarg and a Counter-Attacker to go incredibly fast and do great damage!"
))


# Razzle Dazzle Counter-Attack — Brutal (Brutal)
# Source: https://deadwoodjedi.com/speed-tunes/razzle-dazzle-counter-attack/  |  calc: https://deadwoodjedi.info/cb/33fc6049fc93ad446530116fb552c64fbb7bd1a4
_register(TuneDefinition(
    name="Razzle Dazzle Counter-Attack (Brutal)",
    tune_id="razzle_dazzle_counter_attack__brutal",
    tune_type="traditional",
    difficulty="moderate",
    performance="1_key_unm",
    affinities="all",
    cb_speed=160,
    slots=[
        TuneSlot(role="dps", speed_range=(236, 236), required_hero="Razelvarg", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(244, 244), required_hero="Corvis the Corruptor", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=1 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(210, 210), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(182, 182), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(230, 230), required_hero="Pythion", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Razzle Dazzle Counter-Attack · Brutal (boss SPD 160 Brutal) · by ShortonSkillz · Clan Boss team focused around the crazy speeds of Razelvarg and a Counter-Attacker to go incredibly fast and do great damage!"
))


# Razzle Dazzle Survival — Ultimate Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/razzle-dazzle-survival/  |  calc: https://deadwoodjedi.info/cb/80d3c21744b7f4c5b67ce1dca10b321101f429c9
_register(TuneDefinition(
    name="Razzle Dazzle Survival (Ultimate Nightmare)",
    tune_id="razzle_dazzle_survival__ultimate_nightmare",
    tune_type="traditional",
    difficulty="moderate",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(242, 242), required_hero="Razelvarg", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(232, 232), required_hero="Toragi the Frog", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(231, 231), required_hero="Altan", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(214, 214), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(167, 167), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Razzle Dazzle Survival · Ultimate Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi and ShortonSkillz · Unkillable Clan Boss team focused around the crazy speeds of Razelvarg to incredibly fast and do great damage!"
))


# Razzle Dazzle Survival — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/razzle-dazzle-survival/  |  calc: https://deadwoodjedi.info/cb/f56d65920ee9abe03d5c66e69716c682852e19bb
_register(TuneDefinition(
    name="Razzle Dazzle Survival (Nightmare)",
    tune_id="razzle_dazzle_survival__nightmare",
    tune_type="traditional",
    difficulty="moderate",
    performance="1_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(242, 242), required_hero="Razelvarg", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(232, 232), required_hero="Toragi the Frog", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(231, 231), required_hero="Altan", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(214, 214), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(167, 167), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Razzle Dazzle Survival · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi and ShortonSkillz · Unkillable Clan Boss team focused around the crazy speeds of Razelvarg to incredibly fast and do great damage!"
))


# Razzle Dazzle Survival — Brutal (Brutal)
# Source: https://deadwoodjedi.com/speed-tunes/razzle-dazzle-survival/  |  calc: https://deadwoodjedi.info/cb/cb0e028ef1dfdefc2e344dbd969e012b277993b1
_register(TuneDefinition(
    name="Razzle Dazzle Survival (Brutal)",
    tune_id="razzle_dazzle_survival__brutal",
    tune_type="traditional",
    difficulty="moderate",
    performance="1_key_unm",
    affinities="all",
    cb_speed=160,
    slots=[
        TuneSlot(role="dps", speed_range=(242, 242), required_hero="Razelvarg", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(232, 232), required_hero="Toragi the Frog", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(231, 231), required_hero="Altan", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(214, 214), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(167, 167), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Razzle Dazzle Survival · Brutal (boss SPD 160 Brutal) · by DeadwoodJedi and ShortonSkillz · Unkillable Clan Boss team focused around the crazy speeds of Razelvarg to incredibly fast and do great damage!"
))


# Razzle Dazzle Survival — Ultimate Nightmare Spirit  (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/razzle-dazzle-survival/  |  calc: https://deadwoodjedi.info/cb/2d6246da1734a47c033e0c553ae0c7dd3cdac8e5
_register(TuneDefinition(
    name="Razzle Dazzle Survival (Ultimate Nightmare Spirit )",
    tune_id="razzle_dazzle_survival__ultimate_nightmare_spirit",
    tune_type="traditional",
    difficulty="moderate",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(242, 242), required_hero="Razelvarg", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(232, 232), required_hero="Toragi the Frog", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(231, 231), required_hero="Altan", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(214, 214), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(167, 167), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Razzle Dazzle Survival · Ultimate Nightmare Spirit (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi and ShortonSkillz · Unkillable Clan Boss team focused around the crazy speeds of Razelvarg to incredibly fast and do great damage!"
))


# Single 4:3 Advanced — Ultra-Nightmare, 4:3 between AOE's (Ultimate Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/single-43-advanced/  |  calc: https://deadwoodjedi.info/cb/55f338ec8f3b8d14a59e838a4cb319faf2481e4c
_register(TuneDefinition(
    name="Single 4:3 Advanced (Ultra-Nightmare, 4:3 between AOE's)",
    tune_id="single_43_advanced__ultra_nightmare_4_3_between_aoe_s",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(239, 239), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(192, 192), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(175, 175), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Bulwark", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(182, 182), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=6")
    ],
    notes="Single 4:3 Advanced · Ultra-Nightmare, 4:3 between AOE's (boss SPD 190 Ultimate Nightmare) · 1 Champ moves at a 4:3 ratio, taking a double turn on Ultra-Nightmare and Nightmare. Perfect for champions with 4 turn cooldowns!"
))


# Single 4:3 Advanced — Ultra-Nightmare, 4:3 after Stun (Ultimate Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/single-43-advanced/  |  calc: https://deadwoodjedi.info/cb/60afff2cef8f61be441169ec420af7775968f80d
_register(TuneDefinition(
    name="Single 4:3 Advanced (Ultra-Nightmare, 4:3 after Stun)",
    tune_id="single_43_advanced__ultra_nightmare_4_3_after_stun",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(239, 239), required_hero="Jareg", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(191, 191), required_hero="Marked", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(173, 173), required_hero="Nazana", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(175, 175), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=6")
    ],
    notes="Single 4:3 Advanced · Ultra-Nightmare, 4:3 after Stun (boss SPD 190 Ultimate Nightmare) · 1 Champ moves at a 4:3 ratio, taking a double turn on Ultra-Nightmare and Nightmare. Perfect for champions with 4 turn cooldowns!"
))


# Single 4:3 Advanced — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/single-43-advanced/  |  calc: https://deadwoodjedi.info/cb/fff95080d53fd0adba35c3b67b8cdd02b2b8e1ea
_register(TuneDefinition(
    name="Single 4:3 Advanced (Nightmare)",
    tune_id="single_43_advanced__nightmare",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(239, 239), required_hero="Jareg", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(191, 191), required_hero="Marked", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(173, 173), required_hero="Nazana", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(175, 175), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=6")
    ],
    notes="Single 4:3 Advanced · Nightmare (boss SPD 170 Nightmare) · 1 Champ moves at a 4:3 ratio, taking a double turn on Ultra-Nightmare and Nightmare. Perfect for champions with 4 turn cooldowns!"
))


# Single 4:3 Champion — Ultra-Nightmare, 230-237 (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/single-43-champ/  |  calc: https://deadwoodjedi.info/cb/e4143c2c32d87ede848b04b7fe74fe6e457bbf03
_register(TuneDefinition(
    name="Single 4:3 Champion (Ultra-Nightmare, 230-237)",
    tune_id="single_43_champ__ultra_nightmare_230_237",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(231, 231), required_hero="Kreela Witch-Arm", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=4"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(173, 173), required_hero="Iron Brago", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(175, 175), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=2 CD=3; A3 pri=1 delay=0 CD=6")
    ],
    notes="Single 4:3 Champion · Ultra-Nightmare, 230-237 (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · One Champion going at a 4:3 ratio allowing for a double turn once per CB Cycle. Timing depends on speeds used."
))


# Single 4:3 Champion — Nightmare, 230-237 (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/single-43-champ/  |  calc: https://deadwoodjedi.info/cb/e81abc33bfe641b2ef5348a6925710c1ee1081b9
_register(TuneDefinition(
    name="Single 4:3 Champion (Nightmare, 230-237)",
    tune_id="single_43_champ__nightmare_230_237",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(231, 231), required_hero="Kreela Witch-Arm", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=4"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(173, 173), required_hero="Iron Brago", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(175, 175), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=2 CD=3; A3 pri=1 delay=0 CD=6")
    ],
    notes="Single 4:3 Champion · Nightmare, 230-237 (boss SPD 170 Nightmare) · by DeadwoodJedi · One Champion going at a 4:3 ratio allowing for a double turn once per CB Cycle. Timing depends on speeds used."
))


# Single 4:3 Champion — Ultra-Nightmare, 239-243 (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/single-43-champ/  |  calc: https://deadwoodjedi.info/cb/7f7c754cb88dbfa83a9fead7557e84e9dbdd4093
_register(TuneDefinition(
    name="Single 4:3 Champion (Ultra-Nightmare, 239-243)",
    tune_id="single_43_champ__ultra_nightmare_239_243",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(173, 173), required_hero="Sandlashed Survivor", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(239, 239), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(175, 175), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=2 CD=3; A3 pri=1 delay=0 CD=6")
    ],
    notes="Single 4:3 Champion · Ultra-Nightmare, 239-243 (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · One Champion going at a 4:3 ratio allowing for a double turn once per CB Cycle. Timing depends on speeds used."
))


# Single 4:3 Champion — Nightmare,  239-243 (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/single-43-champ/  |  calc: https://deadwoodjedi.info/cb/4dcd692011df1f0c53578537dae4221446c7fd37
_register(TuneDefinition(
    name="Single 4:3 Champion (Nightmare,  239-243)",
    tune_id="single_43_champ__nightmare_239_243",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(173, 173), required_hero="Sandlashed Survivor", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(239, 239), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(175, 175), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=2 CD=3; A3 pri=1 delay=0 CD=6")
    ],
    notes="Single 4:3 Champion · Nightmare, 239-243 (boss SPD 170 Nightmare) · by DeadwoodJedi · One Champion going at a 4:3 ratio allowing for a double turn once per CB Cycle. Timing depends on speeds used."
))


# The Two Towers — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/the-two-towers/  |  calc: https://deadwoodjedi.info/cb/4c1c2de9b691b7696366c12f81be5bfdd36614a1
_register(TuneDefinition(
    name="The Two Towers (Ultra Nightmare)",
    tune_id="the_two_towers__ultra_nightmare",
    tune_type="traditional",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(218, 218), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=5"),
TuneSlot(role="dps", speed_range=(215, 215), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=5 CD=5"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Septimus", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0")
    ],
    notes="The Two Towers · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Two Roschard the Tower on a 5:4 turn ratio, alternating block damage to stay unkillable. Has some difficulty with spirit affinity - beware!"
))


# The Two Towers — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/the-two-towers/  |  calc: https://deadwoodjedi.info/cb/a628290e7f3045303e4a41e6ce00de715133d9a8
_register(TuneDefinition(
    name="The Two Towers (Nightmare)",
    tune_id="the_two_towers__nightmare",
    tune_type="traditional",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(218, 218), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=5"),
TuneSlot(role="dps", speed_range=(214, 214), required_hero="Roshcard the Tower", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=5 CD=5"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Septimus", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0")
    ],
    notes="The Two Towers · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi · Two Roschard the Tower on a 5:4 turn ratio, alternating block damage to stay unkillable. Has some difficulty with spirit affinity - beware!"
))


# Three 4:3 Champs — Ultra-Nightmare, 172 speed (Ultimate Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/three-43-champs/  |  calc: https://deadwoodjedi.info/cb/68cffdddb76cb5def422ac39763ab261f1426c7b
_register(TuneDefinition(
    name="Three 4:3 Champs (Ultra-Nightmare, 172 speed)",
    tune_id="three_43_champs__ultra_nightmare_172_speed",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(239, 239), required_hero="Jareg", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(171, 171), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(223, 223), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(222, 222), required_hero="Steelskull", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=4 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=6")
    ],
    notes="Three 4:3 Champs · Ultra-Nightmare, 172 speed (boss SPD 190 Ultimate Nightmare) · Various speed ranges for three champions running at a 4:3 ratio"
))


# Three 4:3 Champs — Nightmare, 172 speed (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/three-43-champs/  |  calc: https://deadwoodjedi.info/cb/f0b549018970a698ee49b9e531140fd6fd3bb2cf
_register(TuneDefinition(
    name="Three 4:3 Champs (Nightmare, 172 speed)",
    tune_id="three_43_champs__nightmare_172_speed",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(239, 239), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(171, 171), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(223, 223), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(222, 222), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=4"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Bulwark", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Three 4:3 Champs · Nightmare, 172 speed (boss SPD 170 Nightmare) · Various speed ranges for three champions running at a 4:3 ratio"
))


# Three 4:3 Champs — Ultra-Nightmare, 180-189 speed (Ultimate Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/three-43-champs/  |  calc: https://deadwoodjedi.info/cb/7bed76326b532072ec8e3fa5c3681c4bc8770eed
_register(TuneDefinition(
    name="Three 4:3 Champs (Ultra-Nightmare, 180-189 speed)",
    tune_id="three_43_champs__ultra_nightmare_180_189_speed",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(239, 239), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(223, 223), required_hero="Occult Brawler", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(222, 222), required_hero="Steelskull", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=4"),
TuneSlot(role="dps", speed_range=(180, 180), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=2 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Three 4:3 Champs · Ultra-Nightmare, 180-189 speed (boss SPD 190 Ultimate Nightmare) · Various speed ranges for three champions running at a 4:3 ratio"
))


# Three 4:3 Champs — Nightmare, 180-189 speed (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/three-43-champs/  |  calc: https://deadwoodjedi.info/cb/8c5f5f8172c765eba96b0869d0358958b322f31e
_register(TuneDefinition(
    name="Three 4:3 Champs (Nightmare, 180-189 speed)",
    tune_id="three_43_champs__nightmare_180_189_speed",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(239, 239), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(223, 223), required_hero="Occult Brawler", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(222, 222), required_hero="Steelskull", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=4"),
TuneSlot(role="dps", speed_range=(180, 180), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=4 delay=0 CD=3; A3 pri=3 delay=1 CD=0")
    ],
    notes="Three 4:3 Champs · Nightmare, 180-189 speed (boss SPD 170 Nightmare) · Various speed ranges for three champions running at a 4:3 ratio"
))


# Three 4:3 Champs Alternate — Ultra-Nightmare (Ultimate Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/three-43-champs-alternate/  |  calc: https://deadwoodjedi.info/cb/ddd572a7b01343a8839a06bdde41da9dc9bd084d
_register(TuneDefinition(
    name="Three 4:3 Champs Alternate (Ultra-Nightmare)",
    tune_id="three_43_champs_alternate__ultra_nightmare",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="void_only",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(228, 228), required_hero="Jareg", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Iron Brago", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(225, 225), required_hero="Steelskull", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(225, 225), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=4"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Three 4:3 Champs Alternate · Ultra-Nightmare (boss SPD 190 Ultimate Nightmare) · Various speed ranges for three champions running at a 4:3 ratio."
))


# Three 4:3 Champs Alternate — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/three-43-champs-alternate/  |  calc: https://deadwoodjedi.info/cb/cef1c57c23979cd019c3326145d0730f7c6ac347
_register(TuneDefinition(
    name="Three 4:3 Champs Alternate (Nightmare)",
    tune_id="three_43_champs_alternate__nightmare",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="void_only",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(228, 228), required_hero="Jareg", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Iron Brago", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(225, 225), required_hero="Steelskull", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(225, 225), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=4"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Three 4:3 Champs Alternate · Nightmare (boss SPD 170 Nightmare) · Various speed ranges for three champions running at a 4:3 ratio."
))


# Three 4:3 Champs Alternate — Nightmare Cleanser (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/three-43-champs-alternate/  |  calc: https://deadwoodjedi.info/cb/c277124ccf77aec43a503e3c2c92a67205fa709f
_register(TuneDefinition(
    name="Three 4:3 Champs Alternate (Nightmare Cleanser)",
    tune_id="three_43_champs_alternate__nightmare_cleanser",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="void_only",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(226, 226), required_hero="Kreela Witch-Arm", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(182, 182), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(225, 225), required_hero="Occult Brawler", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(225, 225), required_hero="Jareg", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Grizzled Jarl", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=1 CD=3; A3 pri=2 delay=0 CD=4")
    ],
    notes="Three 4:3 Champs Alternate · Nightmare Cleanser (boss SPD 170 Nightmare) · Various speed ranges for three champions running at a 4:3 ratio."
))


# Tuhanarak and Lydia — UNM / NM / Brutal (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/tuhanarak-and-lydia/  |  calc: https://deadwoodjedi.info/cb/81b380c556719cec96dcda3a20d3ddd249b3e049
_register(TuneDefinition(
    name="Tuhanarak and Lydia (UNM / NM / Brutal)",
    tune_id="tuhanarak_and_lydia__unm_nm_brutal",
    tune_type="traditional",
    difficulty="expert",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(268, 268), required_hero="Lydia the Deathsiren", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=2 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(204, 204), required_hero="Tuhanarak", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(239, 239), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(240, 240), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(269, 269), required_hero="Warboy", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0")
    ],
    notes="Tuhanarak and Lydia · UNM / NM / Brutal (boss SPD 170 Nightmare) · by DeadwoodJedi · 2:1 ratio using Lydia and Tuhanarak, while letting Tuhanarak go first to cleanse debuffs."
))


# Two 4:3 Champs — Ultra-Nightmare (Ultimate Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/two-43-champs/  |  calc: https://deadwoodjedi.info/cb/deb47acbaba9109d3f50bb8279f3dcffba631a35
_register(TuneDefinition(
    name="Two 4:3 Champs (Ultra-Nightmare)",
    tune_id="two_43_champs__ultra_nightmare",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="void_only",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(230, 230), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(229, 229), required_hero="Occult Brawler", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Sandlashed Survivor", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(180, 180), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=6")
    ],
    notes="Two 4:3 Champs · Ultra-Nightmare (boss SPD 190 Ultimate Nightmare) · Various speed ranges for two champions running at a 4:3"
))


# Two 4:3 Champs — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/two-43-champs/  |  calc: https://deadwoodjedi.info/cb/79d0820a9850dd722a9accead3e4a2943936c855
_register(TuneDefinition(
    name="Two 4:3 Champs (Nightmare)",
    tune_id="two_43_champs__nightmare",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="void_only",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(230, 230), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(229, 229), required_hero="Occult Brawler", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=0; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(177, 177), required_hero="Sandlashed Survivor", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(180, 180), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=6")
    ],
    notes="Two 4:3 Champs · Nightmare (boss SPD 170 Nightmare) · Various speed ranges for two champions running at a 4:3"
))


# Two 4:3 Champs Alternate — Ultra-Nightmare, 0-1 over 186 (Ultimate Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/two-43-champs-alternate/  |  calc: https://deadwoodjedi.info/cb/7f7b5f5f31323cc8f0988be373aa67a0656bbb8d
_register(TuneDefinition(
    name="Two 4:3 Champs Alternate (Ultra-Nightmare, 0-1 over 186)",
    tune_id="two_43_champs_alternate__ultra_nightmare_0_1_over_186",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="void_only",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(239, 239), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(180, 180), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(246, 246), required_hero="Steelskull", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(184, 184), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=2 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(182, 182), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=2 CD=3")
    ],
    notes="Two 4:3 Champs Alternate · Ultra-Nightmare, 0-1 over 186 (boss SPD 190 Ultimate Nightmare) · Various speed ranges for two champions running at a 4:3 ratio"
))


# Two 4:3 Champs Alternate — Ultra-Nightmare, 2 over 186 (Ultimate Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/two-43-champs-alternate/  |  calc: https://deadwoodjedi.info/cb/848284479222d6109769da0a362ec014d22f2a82
_register(TuneDefinition(
    name="Two 4:3 Champs Alternate (Ultra-Nightmare, 2 over 186)",
    tune_id="two_43_champs_alternate__ultra_nightmare_2_over_186",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="void_only",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(239, 239), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(180, 180), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(246, 246), required_hero="Steelskull", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(187, 187), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=2 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(186, 186), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=2 CD=3")
    ],
    notes="Two 4:3 Champs Alternate · Ultra-Nightmare, 2 over 186 (boss SPD 190 Ultimate Nightmare) · Various speed ranges for two champions running at a 4:3 ratio"
))


# Two 4:3 Champs Alternate — Ultra-Nightmare, 3 over 186 (Ultimate Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/two-43-champs-alternate/  |  calc: https://deadwoodjedi.info/cb/bd5b7c8195ff0b6345ebf4bed0d801d721724812
_register(TuneDefinition(
    name="Two 4:3 Champs Alternate (Ultra-Nightmare, 3 over 186)",
    tune_id="two_43_champs_alternate__ultra_nightmare_3_over_186",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="void_only",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(239, 239), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(186, 186), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(246, 246), required_hero="Steelskull", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(189, 189), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=2 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=2 CD=3")
    ],
    notes="Two 4:3 Champs Alternate · Ultra-Nightmare, 3 over 186 (boss SPD 190 Ultimate Nightmare) · Various speed ranges for two champions running at a 4:3 ratio"
))


# Two 4:3 Champs with Cleanser — Ultra-Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/two-43-champs-with-cleanser/  |  calc: https://deadwoodjedi.info/cb/04fed3aecc759bf00c14507d0555f069a533141b
_register(TuneDefinition(
    name="Two 4:3 Champs with Cleanser (Ultra-Nightmare)",
    tune_id="two_43_champs_with_cleanser__ultra_nightmare",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="void_only",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(240, 240), required_hero="Jareg", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(179, 179), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(239, 239), required_hero="Steelskull", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(180, 180), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(186, 186), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Two 4:3 Champs with Cleanser · Ultra-Nightmare (boss SPD 190 Ultra-Nightmare) · Various speed ranges for two champions running at a 4:3 with a Debuff Cleanser."
))


# Two 4:3 Champs with Cleanser — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/two-43-champs-with-cleanser/  |  calc: https://deadwoodjedi.info/cb/0c366ec2117f07f5126ab82310dfe3fbbf3d4dae
_register(TuneDefinition(
    name="Two 4:3 Champs with Cleanser (Nightmare)",
    tune_id="two_43_champs_with_cleanser__nightmare",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="void_only",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(240, 240), required_hero="Jareg", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(179, 179), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(239, 239), required_hero="Steelskull", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=4"),
TuneSlot(role="dps", speed_range=(180, 180), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(186, 186), required_hero="Doompriest", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Two 4:3 Champs with Cleanser · Nightmare (boss SPD 170 Nightmare) · Various speed ranges for two champions running at a 4:3 with a Debuff Cleanser."
))


# Ultimate Budget Unkillable — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/ultimate-budget-unkillable/  |  calc: https://deadwoodjedi.info/cb/657c590d00dafc8cb52d0aceeefbdbdd8f2d490e
_register(TuneDefinition(
    name="Ultimate Budget Unkillable (Ultra Nightmare)",
    tune_id="ultimate_budget_unkillable__ultra_nightmare",
    tune_type="traditional",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(256, 256), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=5"),
TuneSlot(role="dps", speed_range=(223, 223), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=4; A3 pri=3 delay=3 CD=4"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(180, 180), required_hero="Vizier Ovelis", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(129, 129), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3")
    ],
    notes="Ultimate Budget Unkillable · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by KebaanDK, Bobo · Budget Maneater team that works on UNM and NM with NO gear swaps!"
))


# Ultimate Budget Unkillable — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/ultimate-budget-unkillable/  |  calc: https://deadwoodjedi.info/cb/b197553ac2940e7e8584d532372304c53a3346a4
_register(TuneDefinition(
    name="Ultimate Budget Unkillable (Nightmare)",
    tune_id="ultimate_budget_unkillable__nightmare",
    tune_type="traditional",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(256, 256), required_hero="Maneater", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=5"),
TuneSlot(role="dps", speed_range=(223, 223), required_hero="Pain Keeper", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=4; A3 pri=3 delay=2 CD=4"),
TuneSlot(role="dps", speed_range=(188, 188), required_hero="Fayne", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(180, 180), required_hero="Vizier Ovelis", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(129, 129), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3")
    ],
    notes="Ultimate Budget Unkillable · Nightmare (boss SPD 170 Nightmare) · by KebaanDK, Bobo · Budget Maneater team that works on UNM and NM with NO gear swaps!"
))


# Ultimate Kyoku Team — UNM & NM (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/ultimate-kyoku-team/  |  calc: https://deadwoodjedi.info/cb/a30f7401e09f4d7eee773aa5f1bd65194377cbc5
_register(TuneDefinition(
    name="Ultimate Kyoku Team (UNM & NM)",
    tune_id="ultimate_kyoku_team__unm_nm",
    tune_type="traditional",
    difficulty="hard",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(257, 257), required_hero="Krisk the Ageless", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(244, 244), required_hero="Godseeker Aniri", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(269, 269), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(192, 192), required_hero="Kyoku", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=4; A3 pri=3 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(220, 220), required_hero="Martyr", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=1 CD=3; A3 pri=2 delay=0 CD=4")
    ],
    notes="Ultimate Kyoku Team · UNM & NM (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · Affinity Friendly 2:1 team using Kyoku with Krisk and a Buff Extender to dominate the Clan Boss."
))


# Vergis Magic — Ultra-Nightmare (Ultimate Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/vergis-magic/  |  calc: https://deadwoodjedi.info/cb/fc569ad20a199fe90123119a49ab2a7ce10989b1
_register(TuneDefinition(
    name="Vergis Magic (Ultra-Nightmare)",
    tune_id="vergis_magic__ultra_nightmare",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(205, 205), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(175, 175), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Vergis", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(182, 182), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=2 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(191, 191), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Vergis Magic · Ultra-Nightmare (boss SPD 190 Ultimate Nightmare) · by DeadwoodJedi · Vergis speeds up one champ to a 4:3 turn ratio, going First/Last between AOEs. Perfect Beginner Speed Tune for Clan Boss! Works on UNM and NM!"
))


# Vergis Magic — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/vergis-magic/  |  calc: https://deadwoodjedi.info/cb/ede3d57fdba2d44b13e4205f5554b6be2588176b
_register(TuneDefinition(
    name="Vergis Magic (Nightmare)",
    tune_id="vergis_magic__nightmare",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(205, 205), required_hero="Sepulcher Sentinel", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=4; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(175, 175), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Vergis", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(182, 182), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=2 CD=3; A3 pri=1 delay=0 CD=6"),
TuneSlot(role="dps", speed_range=(191, 191), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=3; A3 pri=3 delay=0 CD=0")
    ],
    notes="Vergis Magic · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi · Vergis speeds up one champ to a 4:3 turn ratio, going First/Last between AOEs. Perfect Beginner Speed Tune for Clan Boss! Works on UNM and NM!"
))


# Vergis Magic — Nightmare, 4:3 between AOE's (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/vergis-magic/  |  calc: https://deadwoodjedi.info/cb/2b2f2e4286d93a438e6fcd769e04917401436adc
_register(TuneDefinition(
    name="Vergis Magic (Nightmare, 4:3 between AOE's)",
    tune_id="vergis_magic__nightmare_4_3_between_aoe_s",
    tune_type="traditional",
    difficulty="easy",
    performance="3_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(231, 231), required_hero="Kreela Witch-Arm", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=3 CD=4"),
TuneSlot(role="dps", speed_range=(172, 172), required_hero="Skullcrusher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=2 CD=3; A3 pri=3 delay=0 CD=0"),
TuneSlot(role="dps", speed_range=(173, 173), required_hero="Iron Brago", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(174, 174), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(175, 175), required_hero="Rhazin Scarhide", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=2 CD=3; A3 pri=1 delay=0 CD=6")
    ],
    notes="Vergis Magic · Nightmare, 4:3 between AOE's (boss SPD 170 Nightmare) · by DeadwoodJedi · Vergis speeds up one champ to a 4:3 turn ratio, going First/Last between AOEs. Perfect Beginner Speed Tune for Clan Boss! Works on UNM and NM!"
))


# White Whale — Buff Extender - Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/white-whale/  |  calc: https://deadwoodjedi.info/cb/4c80e5054b1cc7837725aa30017e1315bf6433f0
_register(TuneDefinition(
    name="White Whale (Buff Extender - Ultra Nightmare)",
    tune_id="white_whale__buff_extender_ultra_nightmare",
    tune_type="traditional",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(248, 248), required_hero="High Khatun", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=2 delay=0 CD=4; Lore of Steel"),
TuneSlot(role="dps", speed_range=(227, 227), required_hero="Sandlashed Survivor", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=0 CD=0; Lore of Steel"),
TuneSlot(role="dps", speed_range=(225, 225), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(193, 193), required_hero="Marked", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(178, 178), required_hero="Coffin Smasher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0")
    ],
    notes="White Whale · Buff Extender - Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · 2:1 turn ratio using 2 speed boosters or a speed booster and a buff extender."
))


# White Whale — Buff Extender - Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/white-whale/  |  calc: https://deadwoodjedi.info/cb/3d18fa083a9377a58607a3e7d22790354bd9d3da
_register(TuneDefinition(
    name="White Whale (Buff Extender - Nightmare)",
    tune_id="white_whale__buff_extender_nightmare",
    tune_type="traditional",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(248, 248), required_hero="High Khatun", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=3 CD=3; A3 pri=2 delay=0 CD=4; Lore of Steel"),
TuneSlot(role="dps", speed_range=(227, 227), required_hero="Sandlashed Survivor", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=3 CD=3; A3 pri=3 delay=0 CD=0; Lore of Steel"),
TuneSlot(role="dps", speed_range=(225, 225), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(193, 193), required_hero="Marked", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(178, 178), required_hero="Coffin Smasher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0")
    ],
    notes="White Whale · Buff Extender - Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi · 2:1 turn ratio using 2 speed boosters or a speed booster and a buff extender."
))


# White Whale — Double Booster - UNM, NM, Brutal (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/white-whale/  |  calc: https://deadwoodjedi.info/cb/04f2c63b4388aac74de2bebeed1a1ae40a61c21e
_register(TuneDefinition(
    name="White Whale (Double Booster - UNM, NM, Brutal)",
    tune_id="white_whale__double_booster_unm_nm_brutal",
    tune_type="traditional",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(248, 248), required_hero="High Khatun", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=2 delay=0 CD=4; Lore of Steel"),
TuneSlot(role="dps", speed_range=(225, 225), required_hero="Apothecary", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=2; A3 pri=3 delay=1 CD=3; Lore of Steel"),
TuneSlot(role="dps", speed_range=(206, 206), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(205, 205), required_hero="Marked", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(176, 176), required_hero="Coffin Smasher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0")
    ],
    notes="White Whale · Double Booster - UNM, NM, Brutal (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · 2:1 turn ratio using 2 speed boosters or a speed booster and a buff extender."
))


# White Whale - NM Only — Nightmare (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/white-whale-nm-only/  |  calc: https://deadwoodjedi.info/cb/c983fbe8d0be46af46b189a3bf9c11b01ae6396d
_register(TuneDefinition(
    name="White Whale - NM Only (Nightmare)",
    tune_id="white_whale_nm_only__nightmare",
    tune_type="traditional",
    difficulty="moderate",
    performance="4_key_unm",
    affinities="void_only",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(205, 205), required_hero="High Khatun", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=6 CD=3; A3 pri=2 delay=0 CD=4; Lore of Steel"),
TuneSlot(role="dps", speed_range=(205, 205), required_hero="Apothecary", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=2; A3 pri=3 delay=1 CD=3; Lore of Steel"),
TuneSlot(role="dps", speed_range=(205, 205), required_hero="Frozen Banshee", opening=['A1'], skill_priority=['A2', 'A1', 'A3'], notes="A1 pri=2 delay=0 CD=0; A2 pri=1 delay=0 CD=3; A3 pri=3 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(221, 221), required_hero="Marked", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(178, 178), required_hero="Coffin Smasher", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=4; A3 pri=3 delay=0 CD=0")
    ],
    notes="White Whale - NM Only · Nightmare (boss SPD 170 Nightmare) · by DeadwoodJedi · 2:1 turn ratio for NM using two speed boosters."
))


# White Whale Lydia — Ultra Nightmare (Ultra-Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/white-whale-lydia/  |  calc: https://deadwoodjedi.info/cb/03408360584312518396d45756be5c21b9ac788a
_register(TuneDefinition(
    name="White Whale Lydia (Ultra Nightmare)",
    tune_id="white_whale_lydia__ultra_nightmare",
    tune_type="traditional",
    difficulty="moderate",
    performance="1_key_unm",
    affinities="all",
    cb_speed=190,
    slots=[
        TuneSlot(role="dps", speed_range=(269, 269), required_hero="Lydia the Deathsiren", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=2 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(256, 256), required_hero="Godseeker Aniri", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=0 CD=3; A3 pri=1 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(255, 255), required_hero="Underpriest Brogni", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=3; Lore of Steel"),
TuneSlot(role="dps", speed_range=(225, 225), required_hero="Toragi the Frog", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=2 CD=3"),
TuneSlot(role="dps", speed_range=(217, 217), required_hero="Iron Brago", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=2 CD=3")
    ],
    notes="White Whale Lydia · Ultra Nightmare (boss SPD 190 Ultra-Nightmare) · by DeadwoodJedi · 2:1 turn ratio using Lydia and a buff extender. The foundation for many high end damage teams."
))


# White Whale Lydia — Nightmare / Brutal (Nightmare)
# Source: https://deadwoodjedi.com/speed-tunes/white-whale-lydia/  |  calc: https://deadwoodjedi.info/cb/2f23b2e2f2a2d6db95c3abf3c84ef7366c30a4b1
_register(TuneDefinition(
    name="White Whale Lydia (Nightmare / Brutal)",
    tune_id="white_whale_lydia__nightmare_brutal",
    tune_type="traditional",
    difficulty="moderate",
    performance="1_key_unm",
    affinities="all",
    cb_speed=170,
    slots=[
        TuneSlot(role="dps", speed_range=(269, 269), required_hero="Lydia the Deathsiren", opening=['A1'], skill_priority=['A1', 'A3', 'A2'], notes="A1 pri=1 delay=0 CD=0; A2 pri=3 delay=2 CD=3; A3 pri=2 delay=0 CD=3"),
TuneSlot(role="dps", speed_range=(256, 256), required_hero="Godseeker Aniri", opening=['A1'], skill_priority=['A3', 'A1', 'A2'], notes="A1 pri=2 delay=0 CD=0; A2 pri=3 delay=2 CD=3; A3 pri=1 delay=0 CD=4"),
TuneSlot(role="dps", speed_range=(255, 255), required_hero="Underpriest Brogni", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=1 CD=3; A3 pri=3 delay=1 CD=3; Lore of Steel"),
TuneSlot(role="dps", speed_range=(225, 225), required_hero="Toragi the Frog", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3"),
TuneSlot(role="dps", speed_range=(217, 217), required_hero="Iron Brago", opening=['A1'], skill_priority=['A1', 'A2', 'A3'], notes="A1 pri=1 delay=0 CD=0; A2 pri=2 delay=0 CD=3; A3 pri=3 delay=1 CD=3")
    ],
    notes="White Whale Lydia · Nightmare / Brutal (boss SPD 170 Nightmare) · by DeadwoodJedi · 2:1 turn ratio using Lydia and a buff extender. The foundation for many high end damage teams."
))
