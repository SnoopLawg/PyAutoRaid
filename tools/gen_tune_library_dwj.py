#!/usr/bin/env python3
"""Generate tools/tune_library_dwj.py from data/dwj/parsed/calc_tunes.json.

Produces a static Python module matching tools/tune_library.py's
TuneDefinition / TuneSlot dataclass schema so existing sim tooling can
import DWJ-sourced tunes without refactor.

Each DWJ tune becomes up to four entries — one per difficulty variant — with
tune_ids like:
    myth_eater__ultra_nightmare
    myth_eater__nightmare
    myth_eater__ninja_unm
    myth_eater__ninja_nm

Run after scraping:
    python3 tools/gen_tune_library_dwj.py

Re-run whenever calc_tunes.json changes; git diff the output.
"""

from __future__ import annotations

import re
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dwj_tunes import load_all, DwjTune, DwjVariant, DwjChampionSlot

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = PROJECT_ROOT / "tools" / "tune_library_dwj.py"


# --- mappings -------------------------------------------------------------

TYPE_MAP = {
    "Unkillable": "unkillable",
    "Traditional": "traditional",
    "Block Damage": "block_damage",
}

DIFF_MAP = {
    "Easy": "easy",
    "Moderate": "moderate",
    "Hard": "hard",
    "Expert": "expert",
    "Extreme": "extreme",
}

AFFINITY_MAP = {
    "All Affinities": "all",
    "Void Only": "void_only",
    "Not Force": "not_force",
}

KEY_MAP = {
    "1 Key UNM": "1_key_unm",
    "2 Key UNM": "2_key_unm",
    "3 Key UNM": "3_key_unm",
    "4 Key UNM": "4_key_unm",
    "5 Key UNM": "5_key_unm",
}

VARIANT_SUFFIX_MAP = {
    # Raw variant name -> short suffix for tune_id
    "ultra-nightmare": "ultra_nightmare",
    "ultra nightmare": "ultra_nightmare",
    "nightmare": "nightmare",
    "ninja unm": "ninja_unm",
    "ninja nm": "ninja_nm",
    "brutal": "brutal",
    "hard": "hard",
}


def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or "unnamed"


def _one_line(s: str) -> str:
    """Collapse whitespace + escape quotes so a string can go in a Python literal."""
    s = re.sub(r"\s+", " ", (s or "")).strip()
    return s.replace('\\', '\\\\').replace('"', '\\"')


def variant_suffix(name: str) -> str:
    key = name.lower().strip()
    if key in VARIANT_SUFFIX_MAP:
        return VARIANT_SUFFIX_MAP[key]
    return slugify(key)


def infer_role(slot: DwjChampionSlot, tune_type: str) -> str:
    name = (slot.name or "").lower()
    if "maneater" in name and tune_type == "unkillable":
        return "fast_uk"
    if "demytha" in name:
        return "block_damage"
    if "ninja" in name:
        return "ninja_tm_boost"
    if "stun" in name:
        return "stun"
    if "4:3" in name or "4_3" in name or "43" in name:
        return "dps_4to3"
    if "1:1" in name:
        return "dps_1to1"
    if "cleanser" in name:
        return "cleanser"
    if "speed booster" in name or "booster" in name:
        return "speed_booster"
    return "dps"


def slot_notes(slot: DwjChampionSlot) -> str:
    parts = []
    for c in slot.skill_configs:
        if c.alias == "A4":
            continue
        parts.append(f"{c.alias} pri={c.priority} delay={c.delay} CD={c.cooldown}")
    if slot.has_lore_of_steel:
        parts.append("Lore of Steel")
    return "; ".join(parts)


def render_tune_entry(tune: DwjTune, variant: DwjVariant) -> str:
    tune_type = TYPE_MAP.get(tune.type, tune.type.lower().replace(" ", "_") or "traditional")
    difficulty = DIFF_MAP.get(tune.difficulty, tune.difficulty.lower() or "moderate")
    performance = KEY_MAP.get(tune.key_capability, slugify(tune.key_capability or "unknown"))
    affinities = AFFINITY_MAP.get(tune.affinity, slugify(tune.affinity or "all"))
    base_id = slugify(tune.slug)
    suffix = variant_suffix(variant.name or "")
    tune_id = f"{base_id}__{suffix}" if suffix else base_id

    slot_blocks = []
    for slot in variant.slots:
        role = infer_role(slot, tune_type)
        spd = slot.total_speed
        # Get skill_priority ordered by priority number (1..N), excluding A4
        priority_order = sorted(slot.skill_configs, key=lambda c: c.priority)
        skill_priority = [c.alias for c in priority_order if c.alias != "A4"]
        # Opener inference: if slot has a named hero and delay>0 on some skill,
        # we just default to ["A1"] since DWJ's calc encodes "delay" rather than
        # an explicit opener. Users translate delays to in-game presets via
        # priority ranks (see feedback_dwj_preset_debugging.md).
        opening = ["A1"] if slot.base_speed else []
        required_hero = (
            f'"{slot.name}"'
            if slot.base_speed and slot.name and slot.name.lower() not in ("dps", "?")
            else "None"
        )
        notes = slot_notes(slot).replace('"', '\\"')
        slot_blocks.append(
            f'TuneSlot(role="{role}", speed_range=({spd}, {spd}), '
            f"required_hero={required_hero}, "
            f"opening={opening!r}, "
            f"skill_priority={skill_priority!r}, "
            f'notes="{notes}")'
        )

    slots_src = ",\n        ".join(slot_blocks)
    desc = _one_line(tune.description or "")
    note_hdr = f"{tune.name} · {variant.name} (boss SPD {variant.boss_speed} {variant.boss_difficulty})"
    author = f" · by {tune.created_by}" if tune.created_by else ""
    tune_notes = _one_line(note_hdr + author + (" · " + desc if desc else ""))

    return textwrap.dedent(f'''\
        # {tune.name} — {variant.name} ({variant.boss_difficulty})
        # Source: {tune.url}  |  calc: {variant.url}
        _register(TuneDefinition(
            name="{tune.name} ({variant.name})",
            tune_id="{tune_id}",
            tune_type="{tune_type}",
            difficulty="{difficulty}",
            performance="{performance}",
            affinities="{affinities}",
            cb_speed={variant.boss_speed},
            slots=[
                {slots_src}
            ],
            notes="{tune_notes}"
        ))
        ''')


HEADER = '''\
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
'''


def main():
    dwj = load_all()
    entries = []
    skipped_empty = 0
    for tune in dwj.tunes.values():
        if not tune.variants:
            continue
        for v in tune.variants:
            # Skip variants with no hash, no boss config, or no champion slots
            if not v.hash or v.hash == "None" or not v.slots or not v.boss_speed:
                skipped_empty += 1
                continue
            entries.append(render_tune_entry(tune, v))
    if skipped_empty:
        print(f"skipped {skipped_empty} empty variants")

    body = "\n\n".join(entries)
    OUT_PATH.write_text(HEADER + "\n\n" + body, encoding="utf-8")
    print(f"wrote {OUT_PATH} ({len(entries)} variant entries across {len(dwj.tunes)} tunes)")


if __name__ == "__main__":
    main()
