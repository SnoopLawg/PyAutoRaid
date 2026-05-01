"""Single import surface for `data/static/*.json`.

Loads + caches each section. Adds typed accessors for the data shapes
consumers most frequently want (CB boss profile, hero base stats, leader
skills, artifact set bonuses). Use this instead of opening the JSON
files directly so we have one place to add invariants / migrations.

Usage:
    from tools.static_data import StaticData
    sd = StaticData()
    boss = sd.alliance_boss("UltraNightmare")
    print(boss.hp, boss.spd, boss.element)
    hero = sd.hero_type(936)            # Ma'Shalled (max ascended Spirit)
    print(hero.base_stats, hero.leader_skills)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "static"


@dataclass(frozen=True)
class BaseStats:
    hp: float = 0
    atk: float = 0
    def_: float = 0
    spd: float = 0
    res: float = 0
    acc: float = 0
    cr: float = 0
    cd: float = 0
    ch: float = 0
    ignore_def: float = 0
    weight: float = 0

    @classmethod
    def from_dict(cls, d: dict | None) -> "BaseStats":
        d = d or {}
        return cls(
            hp=d.get("hp", d.get("hp_base", 0)),
            atk=d.get("atk", 0),
            def_=d.get("def", 0),
            spd=d.get("spd", 0),
            res=d.get("res", 0),
            acc=d.get("acc", 0),
            cr=d.get("cr", 0),
            cd=d.get("cd", 0),
            ch=d.get("ch", 0),
            ignore_def=d.get("ignore_def", 0),
            weight=d.get("weight", 0),
        )


@dataclass(frozen=True)
class LeaderSkill:
    stat: str
    amount_int: int            # percentage as int (e.g. 19 = +19%)
    absolute: bool = False     # true = flat value, false = percentage

    @property
    def amount(self) -> float:
        return self.amount_int / 100 if not self.absolute else float(self.amount_int)


@dataclass(frozen=True)
class HeroType:
    id: int
    name: str
    fraction: str
    rarity: str
    element: str
    role: str
    ascend_level: int
    base_id: int
    is_boss: bool
    is_max_ascended: bool
    base_stats: BaseStats
    skill_ids: list[int] = field(default_factory=list)
    leader_skills: list[LeaderSkill] = field(default_factory=list)


@dataclass(frozen=True)
class AllianceBoss:
    difficulty: str          # Easy/Normal/Hard/Brutal/Nightmare/UltraNightmare
    hp: int                  # full effective HP (e.g. UNM = 1,171,204,485)
    hero_type_id: int
    level: int
    name: str
    element: str             # Magic/Force/Spirit/Void
    base_stats: BaseStats    # NOT the in-battle actual; static base values
    skill_ids: list[int]


def _load(name: str) -> dict:
    p = DATA_DIR / name
    if not p.exists():
        raise FileNotFoundError(f"static data missing: {p} — run tools/refresh_static_data.py")
    return json.loads(p.read_text())


class StaticData:
    """Lazy-loaded view over data/static/*.json."""

    @cached_property
    def _hero_types_raw(self) -> list[dict]:
        return _load("hero_types.json").get("hero_types", [])

    @cached_property
    def hero_types(self) -> dict[int, HeroType]:
        out: dict[int, HeroType] = {}
        for h in self._hero_types_raw:
            ls = [LeaderSkill(stat=l["stat"], amount_int=l.get("amount_int", 0),
                              absolute=l.get("absolute", False))
                  for l in h.get("leader_skills", [])]
            out[h["id"]] = HeroType(
                id=h["id"], name=h["name"], fraction=h["fraction"],
                rarity=h["rarity"], element=h["element"], role=h["role"],
                ascend_level=h["ascend_level"], base_id=h["base_id"],
                is_boss=h.get("is_boss", False),
                is_max_ascended=h.get("is_max_ascended", False),
                base_stats=BaseStats.from_dict(h.get("base_stats")),
                skill_ids=h.get("skill_ids", []), leader_skills=ls,
            )
        return out

    @cached_property
    def hero_types_by_base(self) -> dict[int, list[HeroType]]:
        """Group by base_id: e.g. base_id=5760 → all 7 ascend rows of Cardiel."""
        out: dict[int, list[HeroType]] = {}
        for h in self.hero_types.values():
            out.setdefault(h.base_id, []).append(h)
        for v in out.values():
            v.sort(key=lambda h: h.ascend_level)
        return out

    def hero_type(self, hid: int) -> HeroType:
        return self.hero_types[hid]

    def find_hero(self, name: str, *, max_ascended: bool = True,
                  element: str | None = None) -> HeroType | None:
        """First case-insensitive name match, optionally filtered by element/asc."""
        target = name.lower()
        for h in self.hero_types.values():
            if target not in h.name.lower():
                continue
            if max_ascended and not h.is_max_ascended:
                continue
            if element and h.element.lower() != element.lower():
                continue
            return h
        return None

    @cached_property
    def alliance_bosses(self) -> dict[str, AllianceBoss]:
        raw = _load("alliance_bosses.json").get("bosses", [])
        out: dict[str, AllianceBoss] = {}
        for b in raw:
            out[b["difficulty"]] = AllianceBoss(
                difficulty=b["difficulty"], hp=b["hp"],
                hero_type_id=b["hero_type_id"], level=b["level"],
                name=b.get("name", "?"), element=b.get("element", "?"),
                base_stats=BaseStats.from_dict(b.get("base_stats")),
                skill_ids=b.get("skill_ids", []),
            )
        return out

    def alliance_boss(self, difficulty: str) -> AllianceBoss:
        # Accept aliases: "unm" → "UltraNightmare", "nm" → "Nightmare"
        diff = difficulty.lower().replace("-", "").replace("_", "")
        aliases = {
            "unm": "UltraNightmare", "ultranightmare": "UltraNightmare",
            "nm": "Nightmare", "nightmare": "Nightmare",
            "brutal": "Brutal", "hard": "Hard",
            "normal": "Normal", "easy": "Easy",
        }
        key = aliases.get(diff, difficulty)
        return self.alliance_bosses[key]

    @cached_property
    def artifact_sets(self) -> list[dict]:
        return _load("artifact_sets.json").get("data", [])

    @cached_property
    def masteries(self) -> list[dict]:
        return _load("masteries.json").get("masteries", [])

    @cached_property
    def blessings(self) -> list[dict]:
        return _load("blessings.json").get("blessings", [])

    @cached_property
    def effects(self) -> list[dict]:
        return _load("effects.json").get("data", [])

    @cached_property
    def revision(self) -> dict[str, Any]:
        return _load("revision.json")


# Module-level singleton for callers who don't want to instantiate.
_default: StaticData | None = None


def default() -> StaticData:
    global _default
    if _default is None:
        _default = StaticData()
    return _default
