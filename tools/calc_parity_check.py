#!/usr/bin/env python3
"""Validate our calc_parity_sim output against DWJ's live rendered turn list.

Input: the raw text DWJ's calc shows on screen (captured via Chrome MCP
get_page_text), plus a variant hash. Compares our sim's cast order to DWJ's
turn-by-turn output action-for-action.

Usage:
    python3 tools/calc_parity_check.py --hash <hash> --text-file dwj_turns.txt
    python3 tools/calc_parity_check.py --hash <hash> --text "Maneater A2Ninja A2Clanboss..."
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from calc_parity_sim import simulate
from dwj_tunes import load_all


# Hero / skill pattern: either a recognized champion name or "Clanboss", followed
# by skill alias (A1-A4 / STUN / AOE1 / AOE2) or the Turn label.
# DWJ's raw text concatenates everything with no separators, so we parse
# greedily by searching for known skill aliases as anchors.
SKILL_ALIASES = ("A1", "A2", "A3", "A4", "STUN", "AOE1", "AOE2")


def parse_dwj_text(text: str, hero_names: list[str]) -> list[tuple[str, str]]:
    """Scan DWJ raw text for (hero)(skill_alias) pairs.

    Strategy:
    - Strip whitespace from text + hero names.
    - Turn labels like "Turn0" / "Turn11" appear between blocks — we DON'T
      split on them (greedy regex over "Turn01" would eat the leading "1"
      of "1:1 DPS 1"). Instead we scan position-by-position for either
      a hero token OR skip "TurnN" tokens in place.
    """
    text = re.sub(r"\s+", "", text)
    hero_stripped = {re.sub(r"\s+", "", h): h for h in hero_names + ["Clanboss"]}
    out = []
    pos = 0
    while pos < len(text):
        # Skip "TurnN" labels that appear AFTER Clanboss skill (2 digits max, max CB turn ~50)
        m = re.match(r"Turn\d{1,2}(?=[A-Z]|$)", text[pos:])
        if m:
            pos += m.end()
            continue
        matched = False
        for hero_norm in sorted(hero_stripped.keys(), key=len, reverse=True):
            if text[pos:pos + len(hero_norm)] == hero_norm:
                after = pos + len(hero_norm)
                for alias in sorted(SKILL_ALIASES, key=len, reverse=True):
                    if text[after:after + len(alias)] == alias:
                        out.append((hero_stripped[hero_norm], alias))
                        pos = after + len(alias)
                        matched = True
                        break
                if matched:
                    break
        if not matched:
            pos += 1
    return out


def simulate_actions(hash_: str) -> tuple[list[tuple[str, str]], list[str]]:
    """Run our sim, return list of (actor_name, skill_alias) plus hero_names for parsing."""
    dwj = load_all()
    variant = dwj.variants_by_hash.get(hash_)
    if not variant:
        raise SystemExit(f"no variant with hash {hash_}")
    turns = simulate(variant, max_boss_turns=25)
    actions = [(t.actor_name, t.skill_alias) for t in turns]
    hero_names = [s.name for s in variant.slots]
    return actions, hero_names


def diff(ours: list[tuple[str, str]], dwj: list[tuple[str, str]]):
    """Show action-by-action diff. Returns match %."""
    n = min(len(ours), len(dwj))
    matches = 0
    print(f"{'idx':>4} {'ours':>40}  {'dwj':>40}  {'status'}")
    for i in range(n):
        o = f"{ours[i][0]} {ours[i][1]}"
        d = f"{dwj[i][0]} {dwj[i][1]}"
        status = "✓" if ours[i] == dwj[i] else "✗"
        if ours[i] == dwj[i]:
            matches += 1
        print(f"{i+1:>4} {o:>40}  {d:>40}  {status}")
    if len(ours) != len(dwj):
        print(f"\nLENGTH MISMATCH — ours={len(ours)} dwj={len(dwj)}")
    pct = 100 * matches / n if n else 0
    print(f"\nMatch: {matches}/{n} = {pct:.1f}%")
    return pct


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hash", required=True)
    ap.add_argument("--text", help="raw DWJ text (use quotes)")
    ap.add_argument("--text-file", help="file containing DWJ text")
    args = ap.parse_args()

    if args.text:
        text = args.text
    elif args.text_file:
        text = Path(args.text_file).read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()

    ours, hero_names = simulate_actions(args.hash)
    dwj = parse_dwj_text(text, hero_names)
    print(f"hero names in variant: {hero_names}")
    print(f"ours: {len(ours)} actions  |  dwj: {len(dwj)} actions\n")
    diff(ours, dwj)


if __name__ == "__main__":
    main()
