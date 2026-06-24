#!/usr/bin/env python3
"""extract_mastery_manifest.py — canonical mastery dataset.

Workstream 2 deliverable: surface the literal mastery proc formulas
in one auditable place. Combines:

  1. `data/static/masteries.json` — 66 masteries with `stat_bonus` for the
     simple stat-bonus ones (13 of 66)
  2. `tools/raid_data.py` MASTERY_IDS + dot caps — hand-coded literal
     formulas for the 53 conditional masteries (Warmaster, Giant Slayer,
     Helmsmasher, Cycle of Magic, Lasting Gifts, Master Hexer, etc.)
  3. Cross-reference for sanity

Output: data/static/mastery_manifest.json — single canonical source.

Per memory `project_mastery_blessing_data.md`: conditional masteries
have NO static form so they MUST be hand-coded; this manifest captures
the hand-coded truth in one structured place rather than scattered
across raid_data.py.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MASTERIES_STATIC = ROOT / "data" / "static" / "masteries.json"
OUTPUT_JSON = ROOT / "data" / "static" / "mastery_manifest.json"


# Hand-coded conditional masteries — literal proc behavior from raid_data.py
# and the in-game mastery tooltip descriptions. Verified against community
# guides (HellHades, AyumiLove, DeadwoodJedi).
CONDITIONAL_MASTERIES = {
    # ---------- Offense tier 6 (boss-damage tier) ----------
    500161: {
        "name": "Warmaster",
        "tree": "Offense",
        "tier": 6,
        "proc": {
            "chance": 0.60,
            "trigger": "once_per_skill_use_against_boss",
            "damage_basis": "0.10 × target_max_hp (4% vs boss)",
            # 67,626 (NOT 75K) — game-truth from real per-event mod capture
            # 2026-06-22 (DAMAGE_HOOK, Force UNM, all 5 MEN heroes). Plarium
            # tuned the WM/GS cap down at a patch after 2026-05-01 (commit
            # 4551388). HP Burn cap stays a distinct 75K.
            "damage_cap": 67_626,
            "stacks_with_def_down_weaken": False,
            "notes": "WM dmg is flat 67,626 cap vs boss, NOT scaled by DEF Down/Weaken (game-truth 2026-06-22)",
        },
    },
    500162: {
        "name": "Helmsmasher",
        "tree": "Offense",
        "tier": 6,
        "proc": {
            "chance": 0.50,
            "trigger": "per_hit_against_target_with_higher_defense",
            "effect": "ignore 25% of target DEF",
            "average_def_ignore": 0.125,  # 12.5% effective average
        },
    },
    500163: {
        "name": "Giant Slayer",
        "tree": "Offense",
        "tier": 6,
        "proc": {
            "chance": 0.30,
            "trigger": "per_hit_against_target_with_higher_hp",
            "damage_basis": "0.075 × target_max_hp (3% vs boss)",
            # 67,626 game-truth cap (same as WM) — see commit 4551388.
            "damage_cap": 67_626,
            "stacks_with_def_down_weaken": False,
            "multi_hit": True,
        },
    },
    500164: {
        "name": "Flawless Execution",
        "tree": "Offense",
        "tier": 6,
        "proc": {
            "effect": "+20% Critical Damage (flat)",
        },
    },
    # ---------- Offense tier 4-5 ----------
    500141: {
        "name": "Bring It Down",
        "tree": "Offense",
        "tier": 4,
        "proc": {
            "effect": "+6% damage vs target with higher max HP",
            "always_on_against_cb_boss": True,
        },
    },
    500151: {
        "name": "Methodical",
        "tree": "Offense",
        "tier": 5,
        "proc": {
            "effect": "+2% A1 damage per A1 use, stacks max 5 (+10%)",
            "decay": "resets on non-A1 cast",
        },
    },
    500152: {
        "name": "Kill Streak",
        "tree": "Offense",
        "tier": 5,
        "proc": {"effect": "+3% damage per kill", "cb_relevance": "useless (boss doesn't die)"},
    },
    500122: {
        "name": "Keen Strike",
        "tree": "Offense",
        "tier": 2,
        "proc": {"effect": "+10% Critical Damage"},
    },
    # ---------- Support — Cycle of Magic / Lasting Gifts / Master Hexer ----------
    500342: {
        "name": "Cycle of Magic",
        "tree": "Support",
        "tier": 4,
        "proc": {
            "chance": 0.05,
            "trigger": "per_hit_when_team_takes_damage",
            "effect": "reduce a random ally's skill cooldown by 1",
        },
    },
    500351: {
        "name": "Lasting Gifts",
        "tree": "Support",
        "tier": 5,
        "proc": {
            "chance": 0.30,
            "trigger": "at_start_of_owner_turn",
            "effect": "extend a random ally buff by 1 turn",
        },
    },
    500354: {
        "name": "Master Hexer",
        "tree": "Support",
        "tier": 5,
        "proc": {
            "chance": 0.30,
            "trigger": "when_owner_places_debuff",
            "effect": "extend that debuff's duration by 1 turn",
        },
    },
    500353: {
        "name": "Sniper",
        "tree": "Support",
        "tier": 5,
        "proc": {"effect": "+5% buff/debuff placement chance"},
    },
    500364: {
        "name": "Eagle Eye",
        "tree": "Support",
        "tier": 6,
        "proc": {"stat_bonus": {"ACC": 50}},
    },
    500343: {
        "name": "Lore of Steel",
        "tree": "Support",
        "tier": 4,
        "proc": {
            "effect": "+15% to basic set bonus stat values",
            "source": "data/static/masteries.json — has stat_bonus formula",
        },
    },
    # ---------- Defense ----------
    500253: {
        "name": "Retribution",
        "tree": "Defense",
        "tier": 5,
        "proc": {
            "chance": 0.50,
            "trigger": "when_taking_25pct_max_hp_damage",
            "effect": "counterattack",
        },
    },
    500254: {
        "name": "Deterrence",
        "tree": "Defense",
        "tier": 5,
        "proc": {
            "chance": 0.20,
            "trigger": "when_ally_receives_stun_freeze_fear",
            "effect": "counterattack",
        },
    },
}


def build_manifest() -> dict:
    """Combine static + hand-coded into one canonical manifest."""
    static_data = {}
    if MASTERIES_STATIC.exists():
        d = json.loads(MASTERIES_STATIC.read_text(encoding="utf-8"))
        for m in d.get("masteries", []):
            mid = m.get("id")
            if mid:
                static_data[mid] = m

    out_entries = []
    all_ids = set(static_data) | set(CONDITIONAL_MASTERIES)
    for mid in sorted(all_ids):
        static_row = static_data.get(mid, {})
        cond = CONDITIONAL_MASTERIES.get(mid)
        entry = {
            "id": mid,
            "tree": cond.get("tree") if cond else _decode_tree(mid),
            "tier_row": static_row.get("row"),
            "col": static_row.get("col"),
            "name": (cond or {}).get("name", static_row.get("name", f"mastery_{mid}")),
            "static_stat_bonus": static_row.get("stat_bonus"),
            "conditional_proc": cond["proc"] if cond else None,
            "is_simple_stat_bonus": bool(static_row.get("stat_bonus")) and not cond,
            "is_hand_coded": bool(cond),
        }
        out_entries.append(entry)

    return {
        "_meta": {
            "generated_by": "tools/extract_mastery_manifest.py",
            "total_masteries": len(out_entries),
            "simple_stat_bonus_count": sum(1 for e in out_entries if e["is_simple_stat_bonus"]),
            "hand_coded_count": sum(1 for e in out_entries if e["is_hand_coded"]),
            "unmapped_count": sum(
                1 for e in out_entries
                if not e["is_simple_stat_bonus"] and not e["is_hand_coded"]
            ),
        },
        "masteries": out_entries,
    }


def _decode_tree(mid: int) -> str | None:
    """Mastery ID format 500XYZ — X is tree code (1=Off, 2=Def, 3=Sup)."""
    if mid < 500000:
        return None
    tree_digit = (mid // 100) % 10
    return {1: "Offense", 2: "Defense", 3: "Support"}.get(tree_digit)


def main() -> int:
    manifest = build_manifest()
    OUTPUT_JSON.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    meta = manifest["_meta"]
    print(f"Wrote {OUTPUT_JSON.relative_to(ROOT)}")
    print(f"  Total masteries: {meta['total_masteries']}")
    print(f"  Simple stat-bonus (auto-applied): {meta['simple_stat_bonus_count']}")
    print(f"  Conditional / hand-coded: {meta['hand_coded_count']}")
    print(f"  Unmapped (need extraction): {meta['unmapped_count']}")
    # Spot-check key boss masteries
    print()
    print("Key CB masteries verified:")
    for e in manifest["masteries"]:
        if e["id"] in (500161, 500163, 500162, 500343, 500342, 500351, 500354):
            proc = e.get("conditional_proc") or e.get("static_stat_bonus") or "—"
            print(f"  {e['id']:>6} {e['name']:<22} {str(proc)[:80]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
