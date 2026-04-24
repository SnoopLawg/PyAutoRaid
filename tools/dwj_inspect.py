#!/usr/bin/env python3
"""CLI inspector for scraped DeadwoodJedi data.

Prints a tune (all variants), a single variant, or a champion's skill detail.

Usage:
    python3 tools/dwj_inspect.py tune myth-eater
    python3 tools/dwj_inspect.py variant 6737fa4be0ec51c5065a433d3f23b7616d9ca430
    python3 tools/dwj_inspect.py champion Ninja
    python3 tools/dwj_inspect.py list                   # all tune slugs
    python3 tools/dwj_inspect.py search forever          # name substring
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dwj_tunes import load_all, DwjVariant, DwjTune, DwjChampion


def print_variant(v: DwjVariant) -> None:
    print(f"  [{v.name}] boss SPD {v.boss_speed} ({v.boss_difficulty}/{v.boss_affinity}) aura={v.speed_aura}")
    print(f"    {v.url}")
    for s in v.slots:
        cfg = ", ".join(
            f"{c.alias}(p{c.priority} d{c.delay} cd{c.cooldown})"
            for c in s.skill_configs
            if c.alias != "A4"
        )
        tag = "LoS" if s.has_lore_of_steel else ""
        print(f"    slot{s.index} {s.name:<16} SPD={s.total_speed:<4} {tag:<3} {cfg}")


def print_tune(t: DwjTune) -> None:
    print(f"=== {t.name} (slug={t.slug}) ===")
    print(f"  type={t.type}  difficulty={t.difficulty}  key={t.key_capability}  affinity={t.affinity}")
    if t.created_by:
        print(f"  author: {t.created_by}")
    print(f"  {t.url}")
    if t.description:
        print(f"  {t.description[:200]}")
    if not t.variants:
        print("  (no calculator variants parsed)")
        return
    print("  Variants:")
    for v in t.variants:
        print_variant(v)


def print_champion(c: DwjChampion) -> None:
    print(f"=== {c.name} ({c.rarity} {c.affinity} {c.role}, {c.faction}) ===")
    print(f"  stats: {c.stats}")
    for sk in c.skills:
        print(f"\n  {sk.alias} {sk.name}  CD {sk.cooldown} -> booked {sk.booked_cooldown}")
        if sk.description:
            desc = " ".join(sk.description.split())
            print(f"    {desc[:250]}")
        for e in sk.effects:
            fields = []
            for attr in ("amount", "turns", "champions", "enemy", "buff", "debuff"):
                v = getattr(e, attr)
                if v is not None:
                    fields.append(f"{attr}={v}")
            if e.condition:
                fields.append(f"condition={e.condition}")
            print(f"    * {e.id} {{{', '.join(fields)}}}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["tune", "variant", "champion", "list", "search"])
    ap.add_argument("arg", nargs="?")
    args = ap.parse_args()

    dwj = load_all()

    if args.cmd == "list":
        for slug in sorted(dwj.tunes):
            t = dwj.tunes[slug]
            print(f"{slug:<40}  {t.name}  [{t.key_capability} / {t.difficulty}]")
        return

    if args.cmd == "search":
        needle = (args.arg or "").lower()
        for slug, t in sorted(dwj.tunes.items()):
            if needle in t.name.lower() or needle in slug:
                print(f"{slug:<40}  {t.name}")
        return

    if not args.arg:
        ap.error(f"{args.cmd} requires an argument")

    if args.cmd == "tune":
        t = dwj.tunes.get(args.arg) or dwj.find_tune(name=args.arg)
        if not t:
            print(f"no tune with slug/name '{args.arg}'")
            sys.exit(1)
        print_tune(t)
        return

    if args.cmd == "variant":
        v = dwj.variants_by_hash.get(args.arg)
        if not v:
            print(f"no variant with hash '{args.arg}'")
            sys.exit(1)
        print(f"variant {v.hash} of tune {v.slug}:")
        print_variant(v)
        return

    if args.cmd == "champion":
        c = dwj.champions.get(args.arg)
        if not c:
            # case-insensitive fallback
            c = next((x for x in dwj.champions.values() if x.name.lower() == args.arg.lower()), None)
        if not c:
            print(f"no champion named '{args.arg}'")
            sys.exit(1)
        print_champion(c)
        return


if __name__ == "__main__":
    main()
