#!/usr/bin/env python3
"""Accessors for the DWJ-scraped tune + champion data.

The scrapers (scrape_dwj.py, scrape_dwj_calc.py) write JSON under
data/dwj/parsed/. This module loads that JSON on demand and exposes typed
objects the rest of PyAutoRaid can consume — without re-scraping on import.

The raw JSON is the source of truth. This module adds:
- dataclass typing
- convenience lookups (by slug, by hash, by champion name)
- an adapter converting a DWJ variant to the legacy TuneDefinition/TuneSlot
  schema in tools/tune_library.py so existing sim code keeps working

Usage:
    from dwj_tunes import load_all, find_variant
    dwj = load_all()
    variant = find_variant(dwj, slug="myth-eater", variant_name="Ninja UNM")
    for slot in variant.slots:
        print(slot.name, slot.total_speed, slot.skill_configs)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PARSED_DIR = PROJECT_ROOT / "data" / "dwj" / "parsed"

TUNES_PATH = PARSED_DIR / "tunes.json"
CALC_TUNES_PATH = PARSED_DIR / "calc_tunes.json"
CALC_CHAMPIONS_PATH = PARSED_DIR / "calc_champions.json"
TIER_LIST_PATH = PARSED_DIR / "tier_list.json"


@dataclass
class DwjSkillConfig:
    alias: str           # "A1", "A2", ...
    id: str              # same as alias for most
    priority: int        # in-game priority slot; 1 = highest among castables
    delay: int           # DWJ delay value; fires on turn (delay+1) counting opener
    cooldown: int        # booked cooldown as used by this tune


@dataclass
class DwjChampionSlot:
    """One of 5 slots in a tune variant, after the calculator has resolved speeds."""
    index: int                         # 1-5
    name: str                          # hero name or "DPS" / "4:3 DPS" placeholder
    total_speed: int                   # in-fight SPD (user-input from tune)
    base_speed: int                    # intrinsic SPD (0 for placeholder slots)
    speed_bonus: int
    has_lore_of_steel: bool
    skill_configs: list[DwjSkillConfig]
    # meta derived from tunes.json for the same slot index (if we could match it)
    min_spd: Optional[int] = None
    max_spd: Optional[int] = None
    mastery: Optional[str] = None
    relentless: Optional[bool] = None
    cycle_of_magic: Optional[bool] = None
    lasting_gifts: Optional[bool] = None
    special_rules_html: Optional[str] = None
    portrait: Optional[str] = None


@dataclass
class DwjVariant:
    """One calculator variant (e.g. 'Ultra-Nightmare', 'Ninja UNM')."""
    hash: str
    name: str
    slug: str                          # parent tune's slug
    boss_speed: int
    boss_difficulty: str
    boss_affinity: str
    speed_aura: int
    slots: list[DwjChampionSlot]

    @property
    def url(self) -> str:
        return f"https://deadwoodjedi.info/cb/{self.hash}"


@dataclass
class DwjTune:
    """A tune as published by DWJ; has 1-4 calc variants."""
    id: int
    name: str
    slug: str
    url: str
    type: str                          # "Unkillable" / "Traditional"
    difficulty: str                    # "Easy"..."Extreme"
    key_capability: str                # "1 Key UNM"..."4 Key UNM"
    affinity: str                      # "All Affinities" / "Void Only"
    created_by: Optional[str]
    description: Optional[str]
    notes_html: Optional[str]
    youtube_id: Optional[str]
    community_videos: list[str]
    variants: list[DwjVariant] = field(default_factory=list)


@dataclass
class DwjSkillEffect:
    """One effect entry on a champion skill (from calc_champions.json)."""
    id: str                            # "add_buff", "add_debuff", "tm_up", etc.
    amount: Optional[int] = None
    turns: Optional[int] = None
    champions: Optional[str] = None    # "self" / "allies" / "single" / "all"
    enemy: Optional[str] = None        # "single" / "all"
    buff: Optional[str] = None         # buff kind, e.g. "tm_up", "unkillable"
    debuff: Optional[str] = None
    condition: Optional[dict] = None
    raw: Optional[dict] = None         # preserve anything we didn't model


@dataclass
class DwjSkill:
    alias: str                         # "A1", "A2", ...
    name: str
    cooldown: int
    booked_cooldown: int
    cooldown_blocked: int
    description: str
    passive: list                      # raw; structure varies
    effects: list[DwjSkillEffect]
    books: list[str]
    damage_based_on: list[str]


@dataclass
class DwjChampion:
    name: str
    faction: str
    rarity: str
    role: str
    affinity: str
    stats: dict                        # hp/atk/def/spd/crate/cmdg/resist/acc
    skills: list[DwjSkill]
    avatar_url: str


@dataclass
class DwjDataset:
    tunes: dict[str, DwjTune]                          # slug -> tune
    variants_by_hash: dict[str, DwjVariant]
    champions: dict[str, DwjChampion]                  # name -> champion
    tier_list: list[dict]

    def find_tune(self, *, slug: str | None = None, name: str | None = None) -> Optional[DwjTune]:
        if slug:
            return self.tunes.get(slug)
        if name:
            lower = name.lower()
            return next((t for t in self.tunes.values() if t.name.lower() == lower), None)
        return None

    def find_variant(self, *, slug: str, variant_name: str) -> Optional[DwjVariant]:
        tune = self.tunes.get(slug)
        if not tune:
            return None
        lower = variant_name.lower().strip()
        return next((v for v in tune.variants if (v.name or "").lower().strip() == lower), None)

    def champion(self, name: str) -> Optional[DwjChampion]:
        return self.champions.get(name)


def _parse_skill_effects(raw_list) -> list[DwjSkillEffect]:
    if not raw_list:
        return []
    out: list[DwjSkillEffect] = []
    for e in raw_list:
        # Some "Aura" skill entries have non-dict effects (e.g. plain strings).
        # Wrap them into a raw payload so callers don't choke.
        if not isinstance(e, dict):
            out.append(DwjSkillEffect(id="aura_meta", raw={"value": e}))
            continue
        out.append(DwjSkillEffect(
            id=e.get("id", "?"),
            amount=e.get("amount"),
            turns=e.get("turns"),
            champions=e.get("champions"),
            enemy=e.get("enemy"),
            buff=e.get("buff"),
            debuff=e.get("debuff"),
            condition=e.get("condition"),
            raw={k: v for k, v in e.items() if k not in {
                "id", "amount", "turns", "champions", "enemy", "buff",
                "debuff", "condition",
            }} or None,
        ))
    return out


def _parse_champion(raw: dict) -> DwjChampion:
    klass = raw.get("class") or {}
    skills = []
    for i, sk in enumerate(raw.get("skills") or []):
        alias = ["A1", "A2", "A3", "A4"][i] if i < 4 else f"A{i+1}"
        skills.append(DwjSkill(
            alias=alias,
            name=sk.get("name") or alias,
            cooldown=int(sk.get("cooldown") or 0),
            booked_cooldown=int(sk.get("booked_cooldown") or 0),
            cooldown_blocked=int(sk.get("cooldown_blocked") or 0),
            description=sk.get("description") or "",
            passive=sk.get("passive") or [],
            effects=_parse_skill_effects(sk.get("effect")),
            books=list(sk.get("books") or []),
            damage_based_on=list(sk.get("damage_based_on") or []),
        ))
    return DwjChampion(
        name=raw["name"],
        faction=klass.get("faction") or "",
        rarity=klass.get("rarity") or "",
        role=klass.get("role") or "",
        affinity=klass.get("affinity") or "",
        stats=raw.get("stats") or {},
        skills=skills,
        avatar_url=raw.get("avatarUrl") or "",
    )


def _parse_variant_champion_slot(raw_champ: dict, index: int, meta_slot: Optional[dict]) -> DwjChampionSlot:
    scfg = []
    for c in raw_champ.get("skillConfigs") or []:
        scfg.append(DwjSkillConfig(
            alias=c.get("alias") or c.get("id") or "?",
            id=c.get("id") or c.get("alias") or "?",
            priority=int(c.get("priority") or 0),
            delay=int(c.get("delay") or 0),
            cooldown=int(c.get("cooldown") or 0),
        ))
    return DwjChampionSlot(
        index=index,
        name=raw_champ.get("name") or "?",
        total_speed=int(raw_champ.get("total_speed") or 0),
        base_speed=int(raw_champ.get("base_speed") or 0),
        speed_bonus=int(raw_champ.get("speed_bonus") or 0),
        has_lore_of_steel=bool(raw_champ.get("has_lore_of_steel")),
        skill_configs=scfg,
        min_spd=(meta_slot or {}).get("min_spd"),
        max_spd=(meta_slot or {}).get("max_spd"),
        mastery=(meta_slot or {}).get("mastery"),
        relentless=(meta_slot or {}).get("relentless"),
        cycle_of_magic=(meta_slot or {}).get("cycle_of_magic"),
        lasting_gifts=(meta_slot or {}).get("lasting_gifts"),
        special_rules_html=(meta_slot or {}).get("special_rules_html"),
        portrait=(meta_slot or {}).get("portrait"),
    )


def _build_variants(tune_meta: dict, calc_tunes_by_hash: dict) -> list[DwjVariant]:
    out = []
    meta_slots = tune_meta.get("slots") or []
    for calc_link in tune_meta.get("calculator_links") or []:
        h = calc_link.get("hash")
        state = calc_tunes_by_hash.get(h)
        if not state:
            continue
        clanboss = state.get("clanboss") or {}
        slots = []
        for idx, c in enumerate(state.get("champions") or []):
            meta = meta_slots[idx] if idx < len(meta_slots) else None
            slots.append(_parse_variant_champion_slot(c, idx + 1, meta))
        out.append(DwjVariant(
            hash=h,
            name=calc_link.get("name") or "",
            slug=tune_meta.get("slug") or "",
            boss_speed=int(clanboss.get("speed") or 0),
            boss_difficulty=clanboss.get("difficulty") or "",
            boss_affinity=clanboss.get("affinity") or "",
            speed_aura=int(state.get("speed_aura") or 0),
            slots=slots,
        ))
    return out


@lru_cache(maxsize=1)
def load_all() -> DwjDataset:
    """Parse all DWJ JSON once and return typed accessors."""
    tunes_raw = json.loads(TUNES_PATH.read_text(encoding="utf-8"))
    calc_tunes_raw = json.loads(CALC_TUNES_PATH.read_text(encoding="utf-8"))
    calc_champs_raw = json.loads(CALC_CHAMPIONS_PATH.read_text(encoding="utf-8"))
    tier_raw = json.loads(TIER_LIST_PATH.read_text(encoding="utf-8"))

    tunes: dict[str, DwjTune] = {}
    variants_by_hash: dict[str, DwjVariant] = {}
    for t in tunes_raw:
        variants = _build_variants(t, calc_tunes_raw)
        tune = DwjTune(
            id=int(t.get("id") or 0),
            name=t.get("name") or "",
            slug=t.get("slug") or "",
            url=t.get("url") or "",
            type=t.get("type") or "",
            difficulty=t.get("difficulty") or "",
            key_capability=t.get("key_capability") or "",
            affinity=t.get("affinity") or "",
            created_by=t.get("created_by"),
            description=t.get("description"),
            notes_html=t.get("notes_html"),
            youtube_id=t.get("youtube_id"),
            community_videos=list(t.get("community_videos") or []),
            variants=variants,
        )
        if tune.slug:
            tunes[tune.slug] = tune
        for v in variants:
            variants_by_hash[v.hash] = v

    champions: dict[str, DwjChampion] = {}
    for c in calc_champs_raw:
        try:
            champ = _parse_champion(c)
            champions[champ.name] = champ
        except Exception:
            continue

    return DwjDataset(
        tunes=tunes,
        variants_by_hash=variants_by_hash,
        champions=champions,
        tier_list=tier_raw,
    )


# -------------------------- convenience lookups --------------------------


def get_tune(slug: str) -> Optional[DwjTune]:
    return load_all().tunes.get(slug)


def get_variant(hash_: str) -> Optional[DwjVariant]:
    return load_all().variants_by_hash.get(hash_)


def list_tunes() -> list[DwjTune]:
    return list(load_all().tunes.values())


def get_champion(name: str) -> Optional[DwjChampion]:
    return load_all().champions.get(name)


# ---------------------- adapter to legacy tune_library -----------------------


def to_tune_library_slot(slot: DwjChampionSlot):
    """Convert a DwjChampionSlot into a tune_library.TuneSlot.

    Imports tune_library lazily so this module remains usable in isolation.
    Single-speed slots collapse the range to (spd, spd); placeholder DPS slots
    fall back to the calc-reported total_speed.
    """
    from tune_library import TuneSlot  # type: ignore[import-not-found]
    priority_order = sorted(slot.skill_configs, key=lambda c: c.priority)
    # A1 opener unless first priority has nonzero delay (then that skill is held)
    opening = ["A1"] if slot.skill_configs else []
    skill_priority = [c.alias for c in priority_order if c.alias != "A4"]
    spd = slot.total_speed or (slot.min_spd or 0)
    spd_max = slot.max_spd or spd
    return TuneSlot(
        role=_infer_role(slot),
        speed_range=(spd, spd_max),
        opening=opening,
        skill_priority=skill_priority,
        required_hero=slot.name if slot.base_speed else None,
        notes=_render_slot_notes(slot),
    )


def _infer_role(slot: DwjChampionSlot) -> str:
    name = (slot.name or "").lower()
    if "unkillable" in name or "maneater" in name:
        return "fast_uk"
    if "demytha" in name or "block damage" in name or "block dmg" in name:
        return "block_damage"
    if "ninja" in name:
        return "ninja_tm_boost"
    if "4:3" in name or "4_3" in name:
        return "dps_4to3"
    if "stun" in name:
        return "stun"
    if "1:1" in name:
        return "dps_1to1"
    return "dps"


def _render_slot_notes(slot: DwjChampionSlot) -> str:
    parts = []
    for s in slot.skill_configs:
        if s.alias == "A4":
            continue
        parts.append(f"{s.alias} pri={s.priority} delay={s.delay} CD={s.cooldown}")
    if slot.has_lore_of_steel:
        parts.append("Lore of Steel")
    if slot.mastery and slot.mastery != "Warmaster":
        parts.append(f"Mastery {slot.mastery}")
    return "; ".join(parts)
