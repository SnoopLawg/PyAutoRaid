"""Classify every blessing for game-wide sim relevance.

Same pattern as `tools/m5_mastery_tagger.py`. Reads the canonical
`data/static/blessing_manifest.json` and tags each blessing's proc with
per-location relevance.

The procs themselves come from two places:
    - `blessing_manifest.json` `conditional_proc` field — for the 5
      Legendaries already hand-coded with verified game-truth formulas
      (Brimstone, Cruelty, PhantomTouch, LightOrbs, PerfectHeal).
    - Public game tooltip text for the remaining 9 Legendaries — these
      are tagged "needs_verification" until pulled from the live mod
      via `/blessings-truth` proc-formula extraction.

Outputs:
    data/static/blessing_relevance.json
    docs/m5_blessing_relevance.md

Run after `tools/refresh_static_data.py --section blessings` and
`tools/extract_blessing_manifest.py`.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "data" / "static"
OUT_JSON = STATIC / "blessing_relevance.json"
OUT_DOC = ROOT / "docs" / "m5_blessing_relevance.md"

LOCATIONS = ["cb", "arena", "tt", "dungeon", "fw", "dt", "cc", "siege",
             "hydra", "chimera", "forest", "campaign"]

# Locations where Stun/Sleep/Freeze/Fear procs on enemies do something useful
# (i.e. enemies can be controlled). CB boss is immune; rest of the game is fair game.
CC_TARGET_LOCATIONS = {"arena", "tt", "dungeon", "fw", "dt", "cc", "siege",
                       "hydra", "chimera", "forest", "campaign"}

# Locations where kill-procs trigger
KILL_LOCATIONS = {"arena", "tt", "dungeon", "fw", "dt", "cc", "siege",
                  "hydra", "chimera", "forest", "campaign"}

# Locations where TM drain on enemies works (CB boss immune)
TM_DRAIN_LOCATIONS = {"arena", "tt", "dungeon", "fw", "dt", "cc", "siege",
                      "hydra", "chimera", "forest", "campaign"}


def _stat_everywhere() -> dict[str, str]:
    return {loc: "stat_bonus" for loc in LOCATIONS}


def _everywhere(value: str = "relevant") -> dict[str, str]:
    return {loc: value for loc in LOCATIONS}


def _cc_only(default: str = "no_op") -> dict[str, str]:
    return {loc: ("relevant" if loc in CC_TARGET_LOCATIONS else default)
            for loc in LOCATIONS}


def _kills() -> dict[str, str]:
    return {loc: ("relevant" if loc in KILL_LOCATIONS else "no_op")
            for loc in LOCATIONS}


def _tm_drain() -> dict[str, str]:
    return {loc: ("relevant" if loc in TM_DRAIN_LOCATIONS else "no_op")
            for loc in LOCATIONS}


# === per-blessing classification =============================================
# Each entry: relevance per location + sim handler status.
# proc_source = "verified_game_truth" | "tooltip_public" | "needs_verification"
CLASSIFICATION: dict[str, dict] = {
    # ============== Legendary — hand-coded in sim ==============
    "Brimstone": {
        "sim_handler": "has_brimstone",
        "proc_source": "verified_game_truth",
        "mechanic": "Per-hit chance to place [Smite] debuff. Holder's allies do bonus dmg to smited target.",
        "relevance": _everywhere(),  # Boss can receive Smite; multiplier applies to all allies' hits
        "notes": "Modeled. Damage amp across the team; applies in every encounter where boss can be hit.",
    },
    "Cruelty": {
        "sim_handler": None,
        "proc_source": "verified_game_truth",
        "mechanic": "Ignore X% of target's DEF on each attack",
        "relevance": _everywhere(),
        "notes": "Formula verified in blessing_manifest (5/8/11/14/18% per grade) but NOT yet wired into cb_sim.",
    },
    "PhantomTouch": {
        "sim_handler": "phantom_touch_mult",
        "proc_source": "verified_game_truth",
        "mechanic": "AfterDamageDealt → bonus Damage = 3.5×ATK to producer (skill 600050)",
        "relevance": _everywhere(),
        "notes": "Modeled via phantom_touch_mult/_repeat fields on SimChampion (bid=1301 / 600050).",
    },
    "PerfectHeal": {
        "sim_handler": None,
        "proc_source": "verified_game_truth",
        "mechanic": "+X% to heals cast (10/15/20/25/30% per grade)",
        "relevance": _everywhere(),
        "notes": "Formula in blessing_manifest but NOT wired into cb_sim heal multiplier.",
    },
    "LightOrbs": {
        "sim_handler": None,
        "proc_source": "verified_game_truth",
        "mechanic": "Place Shield buff when HP < 50% (10/12/15/18/20% per grade)",
        "relevance": _everywhere(),
        "notes": "Formula in blessing_manifest but NOT wired into cb_sim shield-on-low-hp pipeline.",
    },

    # ============== Legendary — NOT yet hand-coded in sim ==============
    "Necromancy": {
        "sim_handler": None,
        "proc_source": "tooltip_public",
        "mechanic": "Place [Necrosis] debuff on attack — Necrosis is a stackable damage-over-time",
        "relevance": _everywhere(),
        "notes": "DoT proc; applies anywhere holder attacks an enemy.",
    },
    "Execute": {
        "sim_handler": None,
        "proc_source": "tooltip_public",
        "mechanic": "Bonus damage to enemies below X% HP",
        "relevance": _everywhere(),
        "notes": "Damage amp on low-HP targets; applies vs any boss/mob with HP bar.",
    },
    "LeadershipDomination": {
        "sim_handler": None,
        "proc_source": "tooltip_public",
        "mechanic": "Aura effect — boosts ally stats based on holder's stats",
        "relevance": _everywhere(),
        "notes": "Always-on team buff.",
    },
    "Meteor": {
        "sim_handler": None,
        "proc_source": "tooltip_public",
        "mechanic": "Per-hit chance to call a Meteor for AoE damage to all enemies",
        "relevance": _everywhere(),
        "notes": "AoE damage proc — strong in multi-enemy modes; works vs CB single boss too.",
    },
    "Polymorph": {
        "sim_handler": None,
        "proc_source": "tooltip_public",
        "mechanic": "Place Polymorph debuff (sheep transformation) on enemy",
        "relevance": _cc_only(),
        "notes": "CC debuff; CB boss is immune. Strong PVP/Faction Wars/DT.",
    },
    "TimeSlowdown": {
        "sim_handler": None,
        "proc_source": "tooltip_public",
        "mechanic": "Reduce target Turn Meter on attack",
        "relevance": _tm_drain(),
        "notes": "CB boss is TM-immune; relevant in any other mode.",
    },
    "SoulDrinker": {
        "sim_handler": None,
        "proc_source": "tooltip_public",
        "mechanic": "Heal a portion of damage dealt (Lifesteal-style)",
        "relevance": _everywhere(),
        "notes": "Self-heal on damage; useful anywhere holder attacks.",
    },
    "CreepingRoots": {
        "sim_handler": None,
        "proc_source": "tooltip_public",
        "mechanic": "Place [Ensnare] debuff on enemy on attack",
        "relevance": _cc_only(),
        "notes": "Ensnare reduces TM and prevents attack; CB boss immune.",
    },
    "WildImpulses": {
        "sim_handler": None,
        "proc_source": "tooltip_public",
        "mechanic": "Per-hit chance for instant additional attack",
        "relevance": _everywhere(),
        "notes": "Damage proc — applies anywhere holder attacks.",
    },

    # ============== Epic blessings (10) ==============
    "Exterminator": {
        "sim_handler": None, "proc_source": "tooltip_public",
        "mechanic": "Bonus damage vs enemies of opposite affinity",
        "relevance": _everywhere(),
        "notes": "Affinity-condition damage amp.",
    },
    "ToxicBlade": {
        "sim_handler": None, "proc_source": "tooltip_public",
        "mechanic": "Chance to place [Poison] debuff on attack",
        "relevance": _everywhere(),
        "notes": "Poison proc — universal.",
    },
    "NatureBalance": {
        "sim_handler": None, "proc_source": "tooltip_public",
        "mechanic": "Convert random debuff on ally to random buff on cast",
        "relevance": _everywhere(),
        "notes": "Cleanse-converter; triggers wherever enemies debuff.",
    },
    "NatureReach": {
        "sim_handler": None, "proc_source": "tooltip_public",
        "mechanic": "Extend duration of buffs cast",
        "relevance": _everywhere(),
        "notes": "Buff extension — universal.",
    },
    "EnhancedWeapon": {
        "sim_handler": None, "proc_source": "tooltip_public",
        "mechanic": "Bonus damage in early turns of a battle",
        "relevance": _everywhere(),
        "notes": "Front-loaded damage amp.",
    },
    "Vanguard": {
        "sim_handler": None, "proc_source": "tooltip_public",
        "mechanic": "First turn bonus (TM start / damage / etc.)",
        "relevance": _everywhere(),
        "notes": "Opener buff.",
    },
    "AdvancedLeadership": {
        "sim_handler": None, "proc_source": "tooltip_public",
        "mechanic": "Boosted leader aura (stat increase to allies of same affinity/faction)",
        "relevance": _everywhere(),
        "notes": "Leader-aura amp; universal.",
    },
    "ChainBreaker": {
        "sim_handler": None, "proc_source": "tooltip_public",
        "mechanic": "Cleanse self of debuffs when struck",
        "relevance": _everywhere(),
        "notes": "Defensive cleanse; triggers wherever enemies debuff.",
    },
    "MagicFlame": {
        "sim_handler": None, "proc_source": "tooltip_public",
        "mechanic": "Chance to place [HP Burn] debuff on attack",
        "relevance": _everywhere(),
        "notes": "HP Burn proc — universal.",
    },
    "Penetrator": {
        "sim_handler": None, "proc_source": "tooltip_public",
        "mechanic": "Ignore portion of target DEF",
        "relevance": _everywhere(),
        "notes": "DEF ignore on attack.",
    },

    # ============== Rare blessings (10) ==============
    "Fearless": {
        "sim_handler": None, "proc_source": "tooltip_public",
        "mechanic": "Resist Fear-related debuffs / immunity to Fear",
        "relevance": _cc_only(),
        "notes": "Niche Fear resist; CB boss can't apply Fear.",
    },
    "MagicOrb": {
        "sim_handler": "phantom_touch_mult",
        "proc_source": "verified_game_truth",
        "mechanic": "3.5×ATK direct damage on attack — same proc shape as PhantomTouch (skill 600050)",
        "relevance": _everywhere(),
        "notes": "Modeled via SimChampion.phantom_touch_mult (bid=1301 dispatches to the same Phantom Touch handler).",
    },
    "Tranquility": {
        "sim_handler": None, "proc_source": "tooltip_public",
        "mechanic": "Reduce duration of debuffs received",
        "relevance": _everywhere(),
        "notes": "Defensive debuff shortener.",
    },
    "WildGrowth": {
        "sim_handler": None, "proc_source": "tooltip_public",
        "mechanic": "Heal allies per turn",
        "relevance": _everywhere(),
        "notes": "Sustained heal.",
    },
    "AdvancedHeal": {
        "sim_handler": None, "proc_source": "tooltip_public",
        "mechanic": "Boost healing effects",
        "relevance": _everywhere(),
        "notes": "Heal-amp (smaller PerfectHeal).",
    },
    "Courage": {
        "sim_handler": None, "proc_source": "tooltip_public",
        "mechanic": "Bonus stats when below HP threshold",
        "relevance": _everywhere(),
        "notes": "Low-HP stat ramp.",
    },
    "Adaptation": {
        "sim_handler": None, "proc_source": "tooltip_public",
        "mechanic": "Stat resistance to opposing affinity hits",
        "relevance": _everywhere(),
        "notes": "Affinity defense.",
    },
    "Amplification": {
        "sim_handler": None, "proc_source": "tooltip_public",
        "mechanic": "Boost damage output by small percent",
        "relevance": _everywhere(),
        "notes": "Flat damage amp.",
    },
    "Agility": {
        "sim_handler": None, "proc_source": "tooltip_public",
        "mechanic": "Boost SPD when hit",
        "relevance": _everywhere(),
        "notes": "Defensive SPD ramp.",
    },
    "Carapace": {
        "sim_handler": None, "proc_source": "tooltip_public",
        "mechanic": "Reduce damage taken from first hit per round",
        "relevance": _everywhere(),
        "notes": "First-hit shield (more uses in multi-round modes).",
    },
}

def load_manifest() -> dict[str, dict]:
    raw = json.load(open(STATIC / "blessing_manifest.json", encoding="utf-8"))
    items = raw["blessings"] if isinstance(raw, dict) else raw
    return {b["id"]: b for b in items}


def main() -> None:
    bm = load_manifest()
    rows = []
    for bid, info in CLASSIFICATION.items():
        m = bm.get(bid, {})
        row = {
            "id": bid,
            "divinity": m.get("divinity"),
            "rarity": m.get("rarity"),
            "is_hand_coded": m.get("is_hand_coded", False),
            "role": m.get("role"),
            **info,
        }
        rows.append(row)

    missing = sorted(bm.keys() - CLASSIFICATION.keys())
    if missing:
        print(f"WARNING — {len(missing)} blessings in manifest have no classification:")
        for bid in missing:
            print(f"  {bid}")

    by_loc = {loc: {"relevant": 0, "no_op": 0, "stat_bonus": 0, "out_of_scope": 0}
              for loc in LOCATIONS}
    for r in rows:
        for loc, val in r["relevance"].items():
            by_loc[loc][val] = by_loc[loc].get(val, 0) + 1

    payload = {
        "_meta": {
            "generated_by": "tools/m5_blessing_tagger.py",
            "total_classified": len(rows),
            "locations": LOCATIONS,
            "modeled_in_sim": sum(1 for r in rows if r["sim_handler"]),
            "needs_verification": sum(1 for r in rows if r["proc_source"] == "tooltip_public"),
            "verified_game_truth": sum(1 for r in rows if r["proc_source"] == "verified_game_truth"),
            "relevance_by_location": by_loc,
        },
        "blessings": rows,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Doc
    import datetime
    lines = [
        "# Blessing relevance — game-wide (every location)",
        "",
        f"_Generated by `tools/m5_blessing_tagger.py` on {datetime.date.today().isoformat()}_",
        "",
        f"All **{len(rows)} blessings** classified per location.",
        "",
        "## Modeling status snapshot",
        "",
        f"- **Modeled with sim handler**: {payload['_meta']['modeled_in_sim']}",
        f"- **Proc source = verified_game_truth**: {payload['_meta']['verified_game_truth']}",
        f"- **Proc source = tooltip_public** (needs IL2CPP/`/blessings-truth` proc-formula verification): {payload['_meta']['needs_verification']}",
        "",
        "## Relevance by location (count of blessings that proc usefully)",
        "",
        "| Location | relevant | no_op | stat_bonus |",
        "|---|---|---|---|",
    ]
    for loc in LOCATIONS:
        c = by_loc[loc]
        lines.append(f"| **{loc}** | {c['relevant']} | {c['no_op']} | {c['stat_bonus']} |")
    lines.append("")
    lines.append("## Per-blessing grid")
    lines.append("")
    header = " | ".join(["ID", "Rarity", "Divinity", "Sim flag", "Proc source"] + LOCATIONS + ["Mechanic"])
    lines.append("| " + header + " |")
    lines.append("|" + "---|" * (len(LOCATIONS) + 6))
    for r in sorted(rows, key=lambda r: (r["rarity"], r["divinity"], r["id"])):
        loc_cells = []
        for loc in LOCATIONS:
            val = r["relevance"].get(loc, "no_op")
            short = {"relevant": "✓", "no_op": "✗", "stat_bonus": "S", "out_of_scope": "-"}.get(val, "?")
            loc_cells.append(short)
        handler = r["sim_handler"] or ""
        cells = [
            r["id"], r["rarity"] or "?", r["divinity"] or "?",
            f"`{handler}`" if handler else "",
            r["proc_source"],
        ] + loc_cells + [r["mechanic"][:90]]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("Legend: ✓ relevant — ✗ no_op — S stat-bonus auto-loaded")
    lines.append("")

    OUT_DOC.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_DOC}")
    print()
    print("Per-location 'relevant' blessing counts:")
    for loc in LOCATIONS:
        c = by_loc[loc]
        print(f"  {loc:8s}  relevant={c['relevant']:2d}  no_op={c['no_op']:2d}")


if __name__ == "__main__":
    main()
