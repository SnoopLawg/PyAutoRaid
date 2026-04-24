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


def compare_slot(idx: int, tl_slot, dwj_slot) -> list[str]:
    """Compare only the fields where a disagreement is meaningful.

    DWJ's calc doesn't encode in-game priority rank or opener — priority in the
    calc_tunes JSON is just a slot label (A1=1, A2=2, A3=3) and delay is an
    observed/simulated schedule offset. So we don't compare those. We DO compare
    speed ranges, required hero, and the per-skill delay pattern to surface
    drift that would actually cause the tune to break.
    """
    issues = []
    # Speed range: DWJ's total_speed must fall inside tune_library's range
    if tl_slot.speed_range and dwj_slot.total_speed:
        tl_min, tl_max = tl_slot.speed_range
        dwj_spd = dwj_slot.total_speed
        if not (tl_min <= dwj_spd <= tl_max):
            issues.append(
                f"    slot{idx} SPD: tune_library {tl_min}-{tl_max}, DWJ {dwj_spd}"
            )
    # required_hero
    tl_hero = (tl_slot.required_hero or "").lower()
    dwj_hero = (dwj_slot.name or "").lower()
    if tl_hero and dwj_hero and tl_hero not in dwj_hero and dwj_hero not in tl_hero:
        issues.append(
            f"    slot{idx} hero: tune_library '{tl_slot.required_hero}', DWJ '{dwj_slot.name}'"
        )
    # Per-skill delay pattern: the A3 delay in particular matters for UK/BD sync
    dwj_delays = {c.alias: c.delay for c in dwj_slot.skill_configs}
    for alias in ("A2", "A3"):
        delay = dwj_delays.get(alias, 0)
        if delay:
            # Not a diff per se — informational so the human sees DWJ's delay at a glance
            issues.append(f"    slot{idx} {alias} DWJ delay={delay}")
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
    # Per slot
    for i, tl_slot in enumerate(tl_def.slots):
        if i >= len(variant.slots):
            issues.append(f"    slot{i+1}: no DWJ slot (tune has fewer heroes)")
            continue
        issues.extend(compare_slot(i + 1, tl_slot, variant.slots[i]))
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
    anything = False
    for tune_id, tl_def in sorted(hand.items()):
        issues = compare_tune(tl_def, dwj)
        # Only print if there's a real issue beyond the "matched" header
        has_issue = any(not line.startswith("  matched") for line in issues)
        if not has_issue:
            # still print the match header so user sees it was checked
            print(f"OK: {tune_id} ({tl_def.name})")
            continue
        anything = True
        print(f"\n--- {tune_id} ({tl_def.name}) ---")
        for line in issues:
            print(line)
    if not anything:
        print("\nNo drift detected.")


if __name__ == "__main__":
    main()
