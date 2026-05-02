"""Boss profile registry — describes every battle the sim can run.

A BossProfile abstracts away "what fight is this" from the sim engine,
so `cb_sim.py` (and future Hydra/Doom Tower engines) read parameters
from a profile instead of hardcoded constants.

Design goals:
- One profile per (location, difficulty[, element/affinity]).
- Minimal fields — only what an existing or upcoming sim consumes.
  No speculative knobs.
- Backward-compatible: cb_sim.py keeps working with `cb_difficulty=` /
  `cb_element=` parameters; profiles are an additive convenience.

Usage (from sim.py dispatcher):

    from boss_profiles import lookup, list_locations
    profile = lookup("cb-unm-void")
    # → BossProfile(name=..., engine="cb", hp=1_171_204_485, speed=190, ...)

To extend:
- New CB difficulty? Already covered by the cb_profile() factory below.
- Hydra: implement HydraProfile subclass with `head_count` / `decap_rule`.
- Doom Tower: per-floor profiles read from data/static/stages.json.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from cb_constants import CB_HP_BY_DIFFICULTY, CB_SPEED_BY_DIFFICULTY, CB_ATK


# =============================================================================
# Element ID conventions (game-internal): 1=Magic, 2=Force, 3=Spirit, 4=Void.
# Some engines also accept a string. Map both ways.
# =============================================================================
ELEMENT_ID_BY_NAME = {"magic": 1, "force": 2, "spirit": 3, "void": 4}
ELEMENT_NAME_BY_ID = {v: k for k, v in ELEMENT_ID_BY_NAME.items()}


@dataclass
class BossProfile:
    """Canonical description of a battle the sim can run.

    Fields are populated based on what the target engine needs. CB
    profiles use the upper block; future Hydra/Doom Tower profiles
    populate the corresponding fields. The `engine` string picks the
    backend.
    """
    # Identity --------------------------------------------------------
    slug: str           # e.g. "cb-unm-void", "hydra-unm", "dragon-25"
    name: str           # human-readable: "Demon Lord UNM (Void)"
    engine: str         # which sim backend handles this: "cb" / "hydra" / "doom_tower" / "dungeon"
    location: str       # CLAUDE.md "Battle Locations" canonical name: "AllianceBoss" / "Hydra" / etc.
    difficulty: Optional[str] = None   # "easy" / "normal" / "hard" / "brutal" / "nm" / "unm"

    # Boss stats ------------------------------------------------------
    hp: int = 0
    atk: int = 0
    def_: int = 0       # Python: def is reserved
    speed: float = 0.0
    res: int = 0
    acc: int = 0
    cr: float = 0.0     # 0..1
    cd: float = 0.0     # 0..1
    element: int = 0    # 1=Magic, 2=Force, 3=Spirit, 4=Void; 0=untyped

    # Mechanic toggles (CB-specific today, expandable) ----------------
    skill_pattern: list[str] = field(default_factory=list)
    # ↑ Order of skills the boss cycles through each turn. CB Void uses
    # ["aoe1", "aoe2", "stun"]. Other patterns: ["aoe1", "aoe2", "single"].

    # CB has hard immunities to TM-manipulation and most CC. Engines
    # that respect this read from the immunities list. Empty list = no
    # immunities (e.g. dungeon mobs eat all debuffs).
    immunities: list[str] = field(default_factory=list)

    # CB caps DoT ticks at flat amounts (~75K each). Other bosses don't.
    dot_caps: bool = False
    # Force Affinity mode — applies the per-skill damage caps that
    # CB's "endless mode" uses post-defeat. Default off.
    force_affinity_caps: bool = False

    # Damage/turn schedule
    enrage_turn: int = 0           # 0 = no enrage. CB UNM: 50.
    gathering_fury_start: int = 0  # 0 = no GF. CB UNM: 10.

    # Multi-target placeholders (Hydra, Chimera) — fill in when the
    # engine for that location ships.
    head_count: int = 1
    head_specific_skills: dict[int, list[str]] = field(default_factory=dict)


# =============================================================================
# CB profiles — Easy through UNM × Magic / Force / Spirit / Void.
#
# CB boss stats come from cb_constants (HP / speed are calibrated +
# verified against live battle logs). The day-of-fight element is what
# changes; HP/SPD/etc. are difficulty-only.
# =============================================================================

_CB_DIFFICULTIES = ("easy", "normal", "hard", "brutal", "nm", "unm")
_CB_ELEMENTS = ("magic", "force", "spirit", "void")


def _cb_skill_pattern(element: str) -> list[str]:
    """CB boss skill rotation by element. All elements rotate AoE1 →
    AoE2 → Stun. The element only affects which affinity-skill is used
    when the boss drops below 50% HP (handled inside the sim, not the
    pattern)."""
    return ["aoe1", "aoe2", "stun"]


def cb_profile(difficulty: str, element: str) -> BossProfile:
    """Construct a Demon Lord profile for the given difficulty + element.

    `difficulty`: easy / normal / hard / brutal / nm / unm
    `element`:    magic / force / spirit / void  (the day's affinity)
    """
    diff = difficulty.lower().replace("-", "").replace(" ", "")
    elem = element.lower()
    if diff not in _CB_DIFFICULTIES:
        raise ValueError(f"unknown CB difficulty {difficulty!r} (want one of {_CB_DIFFICULTIES})")
    if elem not in _CB_ELEMENTS:
        raise ValueError(f"unknown CB element {element!r} (want one of {_CB_ELEMENTS})")

    return BossProfile(
        slug=f"cb-{diff}-{elem}",
        name=f"Demon Lord {diff.upper()} ({elem.title()})",
        engine="cb",
        location="AllianceBoss",
        difficulty=diff,
        hp=CB_HP_BY_DIFFICULTY[diff],
        atk=CB_ATK,
        # Boss DEF / RES / ACC / CR / CD — game-truth from
        # /alliance-bosses (verified UNM 2026-05-02: DEF 1520, RES 250,
        # ACC 330, CR 15%, CD 50%). Per-difficulty CR/CD/ACC don't vary
        # in static data — only HP/SPD scale.
        def_=1520 if diff == "unm" else 0,
        res=250 if diff == "unm" else 30,
        acc=330 if diff == "unm" else 0,
        cr=0.15,
        cd=0.50,
        speed=CB_SPEED_BY_DIFFICULTY[diff],
        element=ELEMENT_ID_BY_NAME[elem],
        skill_pattern=_cb_skill_pattern(elem),
        immunities=[
            "stun", "sleep", "freeze", "provoke",
            "tm_drain", "tm_steal", "decrease_tm",
        ],
        dot_caps=True,
        enrage_turn=50,
        gathering_fury_start=10,
    )


# =============================================================================
# Stub profiles for locations whose sim engine isn't implemented yet.
# The dispatcher (tools/sim.py) reports them as "not yet implemented"
# but listing them here keeps the registry honest about scope.
# =============================================================================

_HYDRA_DIFFICULTIES = ("easy", "normal", "hard", "brutal", "nm", "unm")
_CHIMERA_DIFFICULTIES = ("easy", "normal", "hard", "brutal", "nm", "unm")


def hydra_profile(difficulty: str) -> BossProfile:
    """Hydra profile — sim engine NOT IMPLEMENTED yet (5 heads with
    decapitation rules). Fields will land when the engine ships."""
    diff = difficulty.lower()
    if diff not in _HYDRA_DIFFICULTIES:
        raise ValueError(f"unknown Hydra difficulty {difficulty!r}")
    return BossProfile(
        slug=f"hydra-{diff}",
        name=f"Hydra {diff.upper()}",
        engine="hydra",
        location="Hydra",
        difficulty=diff,
        head_count=5,
    )


def chimera_profile(difficulty: str) -> BossProfile:
    """Chimera profile — sim engine NOT IMPLEMENTED yet."""
    diff = difficulty.lower()
    if diff not in _CHIMERA_DIFFICULTIES:
        raise ValueError(f"unknown Chimera difficulty {difficulty!r}")
    return BossProfile(
        slug=f"chimera-{diff}",
        name=f"Chimera {diff.upper()}",
        engine="chimera",
        location="Chimera",
        difficulty=diff,
        head_count=3,
    )


_DT_STAGES_CACHE: dict | None = None


def _load_dt_stages() -> dict:
    """Lazy-load DoomTower stages from data/static/stages.json keyed by
    (difficulty, floor_number) → list of stage records (DT has 3 region
    variants per floor: DoomTower1/2/3)."""
    global _DT_STAGES_CACHE
    if _DT_STAGES_CACHE is not None:
        return _DT_STAGES_CACHE
    import json
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent / "data" / "static" / "stages.json"
    if not p.exists():
        _DT_STAGES_CACHE = {}
        return _DT_STAGES_CACHE
    raw = json.loads(p.read_text(encoding="utf-8"))
    stages = raw.get("data") or []
    out: dict = {}
    for s in stages:
        area = s.get("Area")
        if not isinstance(area, dict) or area.get("Id") != "DoomTower":
            continue
        diff = (s.get("Difficulty") or "").lower()
        num = s.get("Number")
        if not diff or not num:
            continue
        out.setdefault((diff, num), []).append(s)
    _DT_STAGES_CACHE = out
    return _DT_STAGES_CACHE


def doom_tower_profile(floor: int, difficulty: str = "normal") -> BossProfile:
    """Doom Tower per-floor profile.

    Pulls per-floor metadata from data/static/stages.json (792 DT stages
    landed in Phase 2). Each floor has 3 region variants (DoomTower1/2/3
    visual scenes); we surface modifiers from the first one and tag the
    profile with the stage id so consumers can fetch deeper details on
    demand.

    The sim engine itself is NOT yet implemented — this populates the
    BossProfile with floor metadata + per-round Modifiers (ACC/RES
    floors etc.) for `--list-locations` to surface and downstream
    callers to consume when the engine ships.
    """
    diff = difficulty.lower()
    if not 1 <= floor <= 120:
        raise ValueError(f"Doom Tower floor must be 1..120, got {floor}")
    if diff not in ("normal", "hard"):
        raise ValueError(f"Doom Tower difficulty must be normal/hard, got {difficulty!r}")

    stages_by_floor = _load_dt_stages()
    matches = stages_by_floor.get((diff, floor)) or []
    profile = BossProfile(
        slug=f"dt-{diff}-f{floor:03d}",
        name=f"Doom Tower {diff.title()} Floor {floor}",
        engine="doom_tower",
        location="DoomTower",
        difficulty=diff,
    )

    if matches:
        # Use the first region variant; all three share modifiers.
        s = matches[0]
        # Stash stage metadata in the profile via a side dict so the
        # dispatcher / engine can load deeper details on demand without
        # bloating BossProfile fields.
        profile.head_specific_skills = {  # repurpose existing field for now
            "stage_id": s.get("Id"),
            "scene": s.get("SceneName"),
            "has_boss": bool(s.get("HasBoss")),
            "has_double_boss": bool(s.get("HasDoubleBoss")),
            "is_secret_chamber": bool(s.get("IsSecretChamber")),
            "modifiers": s.get("Modifiers") or [],
            "region_variants": [m.get("Region", {}).get("Id") for m in matches],
        }
    return profile


# =============================================================================
# Registry / lookup
# =============================================================================

def all_profiles() -> dict[str, BossProfile]:
    """Build the full slug -> BossProfile map.

    Computed on demand so changes to cb_constants (e.g. after a
    refresh_static_data run) are picked up next call.
    """
    out: dict[str, BossProfile] = {}
    for diff in _CB_DIFFICULTIES:
        for elem in _CB_ELEMENTS:
            p = cb_profile(diff, elem)
            out[p.slug] = p
    for diff in _HYDRA_DIFFICULTIES:
        p = hydra_profile(diff)
        out[p.slug] = p
    for diff in _CHIMERA_DIFFICULTIES:
        p = chimera_profile(diff)
        out[p.slug] = p
    return out


def lookup(slug: str) -> BossProfile:
    """Resolve a profile slug. Raises KeyError on unknown slugs.

    Doom Tower profiles aren't pre-enumerated (120 floors × 2 diffs);
    they parse on demand via the slug pattern dt-{normal|hard}-fNNN.
    """
    s = slug.lower().strip()
    profiles = all_profiles()
    if s in profiles:
        return profiles[s]
    # Doom Tower on-demand parse: dt-normal-f042 etc.
    if s.startswith("dt-"):
        try:
            _, diff, fnum = s.split("-")
            assert fnum.startswith("f")
            return doom_tower_profile(int(fnum[1:]), diff)
        except (ValueError, AssertionError):
            pass
    raise KeyError(f"unknown profile {slug!r} (try `tools/sim.py --list-locations`)")


def list_locations() -> list[BossProfile]:
    """Return all enumerable profiles, ordered by engine then slug."""
    profiles = list(all_profiles().values())
    profiles.sort(key=lambda p: (p.engine, p.slug))
    return profiles
