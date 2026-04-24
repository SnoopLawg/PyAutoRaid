#!/usr/bin/env python3
"""Diff hand-maintained tune_library.py entries against canonical DWJ data.

For each TuneDefinition registered in tune_library.py, find the matching DWJ
tune (by slug or name) and compare:
- per-slot speed ranges
- required_hero
- opening
- skill_priority

Prints a report highlighting drift — values in tune_library.py that no longer
match deadwoodjedi.info. Run this after a DWJ scrape to surface which hand-
maintained entries need updating.

Usage:
    python3 tools/dwj_vs_tune_library.py
    python3 tools/dwj_vs_tune_library.py --only myth_eater
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tune_library import TUNES, TuneDefinition  # type: ignore[import-not-found]
from dwj_tunes import load_all, DwjTune, DwjVariant


def slug_from_tune_id(tune_id: str) -> str:
    """tune_library uses snake_case; DWJ uses kebab-case slugs. Convert."""
    return tune_id.replace("_", "-")


def find_dwj_match(tl_def: TuneDefinition, dwj) -> DwjTune | None:
    # First try slug-style match
    slug = slug_from_tune_id(tl_def.tune_id)
    if slug in dwj.tunes:
        return dwj.tunes[slug]
    # Try name match (case-insensitive, normalized)
    name_lower = (tl_def.name or "").lower().strip()
    for t in dwj.tunes.values():
        if t.name.lower().strip() == name_lower:
            return t
    # Try removing parenthetical from tune_library name: "Myth Eater (Ninja variant)" → "myth eater"
    base_name = re.sub(r"\s*\(.*?\)\s*", "", name_lower).strip()
    if base_name and base_name != name_lower:
        for t in dwj.tunes.values():
            if t.name.lower().strip() == base_name:
                return t
    return None


def pick_canonical_variant(tune: DwjTune, tl_def: TuneDefinition | None = None) -> DwjVariant | None:
    """Pick the variant that best matches the tune_library entry.

    - If tune_library name contains "Ninja", prefer Ninja-flavored variants
    - Otherwise score each variant by how many of its slot speeds fall inside
      the corresponding tune_library slot ranges; return the best-scoring one
    """
    if not tune.variants:
        return None
    tl_name = (tl_def.name or "").lower() if tl_def else ""
    is_ninja = "ninja" in tl_name

    def score(v: DwjVariant) -> tuple[int, int]:
        """Higher is better. (name_bonus, spd_matches)."""
        name_bonus = 1 if is_ninja and "ninja" in (v.name or "").lower() else 0
        matches = 0
        if tl_def:
            for i, tl_slot in enumerate(tl_def.slots):
                if i >= len(v.slots):
                    break
                if tl_slot.speed_range and v.slots[i].total_speed:
                    lo, hi = tl_slot.speed_range
                    if lo <= v.slots[i].total_speed <= hi:
                        matches += 1
        return (name_bonus, matches)

    best = max(tune.variants, key=score)
    return best


def _name_key(s: str) -> str:
    """Normalize hero names for matching — lowercase, strip punctuation/whitespace."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _match_hand_slot_to_dwj(tl_slot, dwj_variant) -> tuple[int, object] | tuple[None, None]:
    """Find the DWJ slot whose hero name matches tl_slot.required_hero.

    Returns (dwj_index_1based, dwj_slot) or (None, None) if no match.
    Falls back to SPD-range overlap if hero name is unspecified/generic.
    """
    if tl_slot.required_hero:
        tl_key = _name_key(tl_slot.required_hero)
        for i, ds in enumerate(dwj_variant.slots):
            if _name_key(ds.name) == tl_key:
                return i + 1, ds
            # Partial match (e.g. tune_library 'Demytha' vs DWJ 'Demytha (UNM)')
            if tl_key and (tl_key in _name_key(ds.name) or _name_key(ds.name) in tl_key):
                return i + 1, ds
    # Generic DPS / no required hero: match by SPD range
    if tl_slot.speed_range:
        lo, hi = tl_slot.speed_range
        for i, ds in enumerate(dwj_variant.slots):
            if ds.total_speed and lo <= ds.total_speed <= hi:
                return i + 1, ds
    return None, None


def compare_tune_by_hero(tl_def: TuneDefinition, dwj_variant) -> list[str]:
    """Compare tune_library slots to DWJ slots matching by hero identity.

    Surfaces only meaningful drift: missing hero in DWJ, SPD out of range,
    or tune_library heroes that no longer appear in DWJ's canonical set.
    Advisory delay info is emitted alongside matched slots.
    """
    issues = []
    used_dwj = set()
    for i, tl_slot in enumerate(tl_def.slots):
        idx, ds = _match_hand_slot_to_dwj(tl_slot, dwj_variant)
        if ds is None:
            hero = tl_slot.required_hero or f"slot{i+1} (any)"
            issues.append(
                f"    tune_library slot{i+1} '{hero}' SPD "
                f"{tl_slot.speed_range[0]}-{tl_slot.speed_range[1]}: no DWJ slot"
            )
            continue
        used_dwj.add(idx)
        dwj_spd = ds.total_speed or 0
        lo, hi = tl_slot.speed_range or (0, 0)
        in_range = lo <= dwj_spd <= hi if lo else True
        matched_hero = f"{tl_slot.required_hero} -> {ds.name}" if tl_slot.required_hero else f"SPD-match {ds.name}"
        status = "OK" if in_range else "SPD OFF"
        delay_a2 = next((c.delay for c in ds.skill_configs if c.alias == "A2"), 0)
        delay_a3 = next((c.delay for c in ds.skill_configs if c.alias == "A3"), 0)
        delays = []
        if delay_a2:
            delays.append(f"A2 d{delay_a2}")
        if delay_a3:
            delays.append(f"A3 d{delay_a3}")
        suffix = f"  [{', '.join(delays)}]" if delays else ""
        issues.append(
            f"    slot{i+1} tl[{lo}-{hi}] = DWJ slot{idx}[{dwj_spd}] {matched_hero} — {status}{suffix}"
        )
    # DWJ heroes tune_library didn't claim
    missing = [
        (i + 1, ds.name, ds.total_speed)
        for i, ds in enumerate(dwj_variant.slots)
        if i + 1 not in used_dwj
    ]
    for i, name, spd in missing:
        issues.append(f"    DWJ slot{i} '{name}' SPD {spd}: not present in tune_library")
    return issues


def compare_tune(tl_def: TuneDefinition, dwj) -> list[str]:
    match = find_dwj_match(tl_def, dwj)
    if not match:
        return [f"  NO DWJ MATCH for tune_library entry '{tl_def.tune_id}' ({tl_def.name})"]
    variant = pick_canonical_variant(match, tl_def)
    if not variant:
        return [f"  DWJ '{match.slug}' has no calc variants to compare against"]

    issues = [f"  matched {tl_def.tune_id} -> {match.slug} [{variant.name}]"]
    # cb_speed
    if tl_def.cb_speed and variant.boss_speed and tl_def.cb_speed != variant.boss_speed:
        issues.append(
            f"    cb_speed: tune_library {tl_def.cb_speed}, DWJ {variant.boss_speed}"
        )
    issues.extend(compare_tune_by_hero(tl_def, variant))
    return issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="compare only this tune_library tune_id")
    args = ap.parse_args()

    dwj = load_all()
    # Only compare HAND-MAINTAINED entries (no __ suffix)
    hand = {k: v for k, v in TUNES.items() if "__" not in k}
    if args.only:
        hand = {k: v for k, v in hand.items() if k == args.only}

    print(f"=== Comparing {len(hand)} hand-maintained tunes vs DWJ scrape ===\n")
    for tune_id, tl_def in sorted(hand.items()):
        issues = compare_tune(tl_def, dwj)
        real_drift = [
            line for line in issues
            if "SPD OFF" in line or "no DWJ slot" in line or "NO DWJ MATCH" in line
            or "not present in tune_library" in line or "cb_speed:" in line
        ]
        print(f"\n--- {tune_id} ({tl_def.name}) ---")
        if not real_drift:
            print("  [clean]")
        for line in issues:
            print(line)


if __name__ == "__main__":
    main()
