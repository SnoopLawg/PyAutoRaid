"""Classify every mastery for game-wide sim relevance.

Reads `data/static/masteries_named.json` (game-truth names + descriptions
extracted from the live mod) and tags each mastery with:
    relevance_by_location: dict[location_code -> "relevant"|"no_op"|"stat_bonus"|"out_of_scope"]
    sim_handler:           SimChampion flag if modeled, else None
    triggers:              tags describing what conditions activate the proc
    notes:                 short justification

Outputs:
    data/static/mastery_relevance.json   (machine-readable, per-location)
    docs/m5_mastery_relevance.md         (human-readable, per-location table)

Location codes follow `data/static/stage_areas.json` + CLAUDE.md battle-location
list:
    cb       — Clan Boss / Demon Lord
    arena    — Classic + Live Arena (5v5 PVP)
    tt       — Tag Team Arena (3v3 PVP, swap mechanic)
    dungeon  — Dragon/Spider/FK/Ice Golem/Minotaur/4 Keeps
    fw       — Faction Wars
    dt       — Doom Tower (120 floors)
    cc       — Cursed City
    siege    — Siege battles
    hydra    — Hydra (5-head)
    chimera  — Chimera (3-head)
    forest   — Grim Forest (Foggy Forest)
    campaign — Story Campaign

Classification rules per location:
    stat_bonus    — pure flat/percent stat (always applies in any battle)
    relevant      — fires/applies in this location's typical encounter
    no_op         — depends on a mechanic this location doesn't have
                    (e.g. WoD needs kills; CB has no kills; Mighty Endurance
                     needs CC debuffs on this hero; CB boss can't apply CC)
    out_of_scope  — explicitly only triggers in a subset (Arena/Siege only
                    for Kill Streak); we mark non-matching modes as out_of_scope.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "data" / "static"
OUT_JSON = STATIC / "mastery_relevance.json"
OUT_DOC = ROOT / "docs" / "m5_mastery_relevance.md"

LOCATIONS = ["cb", "arena", "tt", "dungeon", "fw", "dt", "cc", "siege",
             "hydra", "chimera", "forest", "campaign"]

# Locations where mobs die during the battle (kill-gated masteries trigger).
KILL_LOCATIONS = {"arena", "tt", "dungeon", "fw", "dt", "cc", "siege",
                  "hydra", "chimera", "forest", "campaign"}
# All except CB and Hydra/Chimera bosses (but those have heads dying — count as kills)

# Locations where enemies apply Stun/Sleep/Freeze/Fear on heroes
# (CB boss is immune to applying these; most other content has CC enemies).
CC_INCOMING_LOCATIONS = {"arena", "tt", "dungeon", "fw", "dt", "cc", "siege",
                         "hydra", "chimera", "forest", "campaign"}

# Locations where enemies have Shield buffs (Shield Breaker targets)
# Sacred Order FW + Doom Tower + some Cursed City + Hydra/Chimera have Shield users.
SHIELD_USER_LOCATIONS = {"arena", "tt", "fw", "dt", "cc", "hydra", "chimera"}


def _everywhere(value: str = "relevant") -> dict[str, str]:
    return {loc: value for loc in LOCATIONS}


def _kills() -> dict[str, str]:
    """Kill-gated mastery — relevant where kills happen."""
    return {loc: ("relevant" if loc in KILL_LOCATIONS else "no_op")
            for loc in LOCATIONS}


def _cc_incoming() -> dict[str, str]:
    """Hero has CC debuff applied to them by enemies."""
    return {loc: ("relevant" if loc in CC_INCOMING_LOCATIONS else "no_op")
            for loc in LOCATIONS}


def _shield_targets() -> dict[str, str]:
    return {loc: ("relevant" if loc in SHIELD_USER_LOCATIONS else "no_op")
            for loc in LOCATIONS}


def _stat() -> dict[str, str]:
    return {loc: "stat_bonus" for loc in LOCATIONS}


def _arena_siege_only(other: str = "relevant") -> dict[str, str]:
    """Kill Streak — +6% Arena/Siege, lower +3% in every other location.
    `other` controls the non-Arena/Siege value (use 'relevant' for partial,
    'out_of_scope' if you want it to highlight as Arena/Siege exclusive)."""
    out = _everywhere(other)
    out["arena"] = "relevant"
    out["tt"] = "relevant"
    out["siege"] = "relevant"
    return out


# === per-mastery classification ==============================================
CLASSIFICATION: dict[int, dict] = {
    # ============== OFFENSE TREE ==============
    500112: {"sim_handler": "stat", "triggers": ["always"],
             "relevance": _stat(),
             "notes": "Blade Disciple — ATK +75 auto-loaded"},
    500113: {"sim_handler": "stat", "triggers": ["always"],
             "relevance": _stat(),
             "notes": "Deadly Precision — C.RATE +5% auto-loaded"},
    500121: {"sim_handler": "has_heart_of_glory", "triggers": ["self_full_hp"],
             "relevance": _everywhere(),
             "notes": "Heart of Glory — modeled. +5% dmg @ full HP."},
    500122: {"sim_handler": "has_keen_strike", "triggers": ["always"],
             "relevance": _everywhere(),
             "notes": "Keen Strike — +10% C.DMG flat"},
    500123: {"sim_handler": None, "triggers": ["target_has_shield"],
             "relevance": _shield_targets(),
             "notes": "Shield Breaker — +25% vs Shield buffs. Relevant where enemies wear Shield (SO FW, DT, Hydra/Chimera, PvP)."},
    500124: {"sim_handler": "has_grim_resolve", "triggers": ["self_low_hp"],
             "relevance": _everywhere(),
             "notes": "Grim Resolve — modeled. +5% dmg @≤50% HP"},
    500131: {"sim_handler": "has_single_out", "triggers": ["target_low_hp"],
             "relevance": _everywhere(),
             "notes": "Single Out — modeled. +8% dmg @ target <40% HP. Boss HP fraction approx via cumul_dmg/UNM_HP."},
    500132: {"sim_handler": None, "triggers": ["self_low_hp"],
             "relevance": _everywhere(),
             "notes": "Life Drinker — heal 5% of dmg @≤50% HP"},
    500133: {"sim_handler": None, "triggers": ["killed_enemy"],
             "relevance": _kills(),
             "notes": "Whirlwind of Death — +6 SPD per kill (cap not given). No kills in CB."},
    500134: {"sim_handler": "has_ruthless_ambush", "triggers": ["first_hit_per_enemy"],
             "relevance": _everywhere(),
             "notes": "Ruthless Ambush — modeled (CB-shape: +8% on this hero's first damaging cast). Multi-enemy modes need per-enemy tracking — future work."},
    500141: {"sim_handler": "has_bring_it_down", "triggers": ["target_higher_max_hp"],
             "relevance": _everywhere(),
             "notes": "Bring It Down — +6% vs higher-MAX-HP target. Boss = always higher; mostly true vs dungeon bosses too."},
    500142: {"sim_handler": "has_wrath_of_slain", "triggers": ["ally_dead"],
             "relevance": _everywhere(),
             "notes": "Wrath of the Slain — modeled. +5% dmg per dead ally (cap +10%)."},
    500143: {"sim_handler": None, "triggers": ["killed_enemy"],
             "relevance": _kills(),
             "notes": "Cycle of Violence — 30% chance CD reduce on kill. No kills in CB."},
    500144: {"sim_handler": None, "triggers": ["target_has_cc"],
             "relevance": _cc_incoming(),
             "notes": "Opportunist — bonus vs Stun/Sleep/Freeze targets. Triggers where target gets CC'd. CB boss immune."},
    500151: {"sim_handler": None, "triggers": ["always"],
             "relevance": _everywhere(),
             "notes": "Methodical — +2% A1 dmg per A1 use, cap +10%. Universal A1 ramp."},
    500152: {"sim_handler": "has_kill_streak", "triggers": ["arena_or_siege"],
             "relevance": _arena_siege_only(),
             "notes": "Kill Streak — Arena/Siege get +6%; all other modes get the smaller +3% blanket — relevant everywhere but stronger in PVP."},
    500153: {"sim_handler": None, "triggers": ["self_has_cc"],
             "relevance": _cc_incoming(),
             "notes": "Blood Shield — Shield buff when self hit by Stun/Sleep/Freeze. CB boss can't apply those."},
    500154: {"sim_handler": None, "triggers": ["self_has_debuff"],
             "relevance": {**_everywhere(), "cb": "relevant"},
             "notes": "Stoked To Fury — +4% per self-debuff (cap +12%). Triggers anywhere enemies apply debuffs."},
    500161: {"sim_handler": "has_wm", "triggers": ["per_skill_hit"],
             "relevance": _everywhere(),
             "notes": "Warmaster — modeled. 60% chance + cap per skill use."},
    500162: {"sim_handler": "has_helmsmasher", "triggers": ["target_above_50_hp"],
             "relevance": _everywhere(),
             "notes": "Helmsmasher — modeled. 50% ignore 25% DEF on >50% HP target."},
    500163: {"sim_handler": "has_gs", "triggers": ["per_hit"],
             "relevance": _everywhere(),
             "notes": "Giant Slayer — modeled. 30%/hit, 7.5% TRG_HP (capped vs bosses)."},
    500164: {"sim_handler": "has_flawless_exec", "triggers": ["always"],
             "relevance": _everywhere(),
             "notes": "Flawless Execution — modeled. +20% C.DMG flat."},

    # ============== DEFENSE TREE ==============
    500212: {"sim_handler": "stat", "triggers": ["always"], "relevance": _stat(),
             "notes": "Tough Skin — DEF +75 auto-loaded"},
    500213: {"sim_handler": "stat", "triggers": ["always"], "relevance": _stat(),
             "notes": "Defiant — RES +10 auto-loaded"},
    500221: {"sim_handler": "has_blastproof", "triggers": ["incoming_aoe"],
             "relevance": _everywhere(),
             "notes": "Blastproof — modeled. -5% from AoE attacks (all CB boss skills are AoE)."},
    500222: {"sim_handler": None, "triggers": ["heal_or_shield_received"],
             "relevance": _everywhere(),
             "notes": "Rejuvenation — +15% heal+shield value received."},
    500223: {"sim_handler": None, "triggers": ["self_has_cc"],
             "relevance": _cc_incoming(),
             "notes": "Mighty Endurance — -10% dmg when self has Stun/Sleep/Freeze. CB no-op (boss can't apply)."},
    500224: {"sim_handler": "has_improved_parry", "triggers": ["incoming_crit"],
             "relevance": _everywhere(),
             "notes": "Improved Parry — modeled. -8% dmg from crits, gated by boss crit share in deterministic mode."},
    500231: {"sim_handler": None, "triggers": ["enemy_healed"],
             "relevance": {**_everywhere("no_op"), "arena": "relevant", "tt": "relevant", "dungeon": "relevant", "dt": "relevant", "fw": "relevant"},
             "notes": "Shadow Heal — heal 6% MAX HP per enemy heal (1/turn). Triggers vs healer enemies (PVP, FW priests, DT)."},
    500232: {"sim_handler": None, "triggers": ["self_lost_25_hp"],
             "relevance": _everywhere(),
             "notes": "Resurgent — 50% chance remove 1 debuff from self on 25% HP loss."},
    500233: {"sim_handler": None, "triggers": ["killed_enemy"],
             "relevance": _kills(),
             "notes": "Bloodthirst — heal 10% MAX HP per kill (no boss minion). No kills in CB."},
    500234: {"sim_handler": None, "triggers": ["ally_took_crit"],
             "relevance": _everywhere(),
             "notes": "Wisdom of Battle — 30% chance BD buff on this hero when ally takes crit. Strong vs CB (constant boss crits)."},
    500241: {"sim_handler": None, "triggers": ["self_placed_buff"],
             "relevance": _everywhere(),
             "notes": "Solidarity — +5 ally RES per buff this hero placed. Stacks with buff-heavy supports."},
    500242: {"sim_handler": None, "triggers": ["hit_by_same_enemy"],
             "relevance": _everywhere(),
             "notes": "Delay Death — -0.75% dmg per hit from same enemy. Boss = always same enemy → stacks all fight."},
    500243: {"sim_handler": None, "triggers": ["placed_debuff"],
             "relevance": _everywhere(),
             "notes": "Harvest Despair — 60% Leech 1T when placing any debuff. Leech IS damage."},
    500244: {"sim_handler": None, "triggers": ["self_has_debuff"],
             "relevance": _everywhere(),
             "notes": "Stubbornness — +10 RES per debuff on self (cap +30). Defensive ramp anywhere enemies apply debuffs."},
    500251: {"sim_handler": None, "triggers": ["ally_first_hit_per_round"],
             "relevance": _everywhere(),
             "notes": "Selfless Defender — -20% dmg ally takes from first enemy hit per round. CB = 1 round; multi-round modes get more triggers."},
    500252: {"sim_handler": None, "triggers": ["ally_took_crit"],
             "relevance": _everywhere(),
             "notes": "Cycle of Revenge — 50% chance +15% TM when ally takes crit. Triggers from enemy crits anywhere."},
    500253: {"sim_handler": "has_retribution", "triggers": ["self_lost_25_hp"],
             "relevance": _everywhere(),
             "notes": "Retribution — modeled. 50% counter on 25%+ HP loss."},
    500254: {"sim_handler": None, "triggers": ["ally_got_cc"],
             "relevance": _cc_incoming(),
             "notes": "Deterrence — 20% counter when ally Stunned/Frozen/Feared. CB no-op."},
    500261: {"sim_handler": "stat", "triggers": ["always"], "relevance": _stat(),
             "notes": "Iron Skin — DEF +200 auto-loaded"},
    500262: {"sim_handler": "has_bulwark", "triggers": ["always_team"],
             "relevance": _everywhere(),
             "notes": "Bulwark — modeled. -5% team dmg (added to team_dmg_reduction pool; redirect-to-self not separately tracked)."},
    500263: {"sim_handler": None, "triggers": ["target_can_be_cc"],
             "relevance": _cc_incoming(),
             "notes": "Fearsome Presence — +Stun/Sleep/Freeze chance. CB boss immune."},
    500264: {"sim_handler": "stat", "triggers": ["always"], "relevance": _stat(),
             "notes": "Unshakeable — RES +50 auto-loaded"},

    # ============== SUPPORT TREE ==============
    500312: {"sim_handler": "stat", "triggers": ["always"], "relevance": _stat(),
             "notes": "Steadfast — HP +810 auto-loaded"},
    500313: {"sim_handler": "stat", "triggers": ["always"], "relevance": _stat(),
             "notes": "Pinpoint Accuracy — ACC +10 auto-loaded"},
    500321: {"sim_handler": None, "triggers": ["heal_cast"],
             "relevance": _everywhere(),
             "notes": "Lay On Hands — +5% heal value cast"},
    500322: {"sim_handler": None, "triggers": ["shield_cast"],
             "relevance": _everywhere(),
             "notes": "Shieldbearer — +5% Shield value cast"},
    500323: {"sim_handler": None, "triggers": ["killed_enemy"],
             "relevance": _kills(),
             "notes": "Exalt in Death — heal 10% MAX HP first kill per round. No kills in CB."},
    500324: {"sim_handler": None, "triggers": ["all_skills_off_cd"],
             "relevance": _everywhere(),
             "notes": "Charged Focus — +20 ACC when no skills on CD. Niche; applies to openers and post-rotation lulls."},
    500331: {"sim_handler": None, "triggers": ["heal_low_hp_ally"],
             "relevance": _everywhere(),
             "notes": "Healing Savior — +50% heal value on <50% HP allies"},
    500332: {"sim_handler": None, "triggers": ["self_buff_dispelled"],
             "relevance": {**_everywhere("no_op"), "arena": "relevant", "tt": "relevant", "siege": "relevant", "fw": "relevant", "dt": "relevant"},
             "notes": "Rapid Response — 30% TM when self buff dispelled. Triggers where enemies dispel (PVP, FW, DT)."},
    500333: {"sim_handler": None, "triggers": ["per_alive_enemy"],
             "relevance": {**_everywhere(), "cb": "no_op", "hydra": "relevant", "chimera": "relevant"},
             "notes": "Swarm Smiter — +4 ACC per alive enemy (cap +16). CB has 1 enemy = fixed +4 (auto-loaded if at all)."},
    500334: {"sim_handler": None, "triggers": ["debuff_placed_on_self"],
             "relevance": _everywhere(),
             "notes": "Arcane Celerity — 30% chance +10% TM when debuff placed on self. Triggers wherever enemies apply debuffs."},
    500341: {"sim_handler": None, "triggers": ["heal_debuffed_ally"],
             "relevance": _everywhere(),
             "notes": "Merciful Aid — +15% heal+shield on debuffed allies."},
    500342: {"sim_handler": "has_cycle_of_magic", "triggers": ["per_own_turn"],
             "relevance": _everywhere(),
             "notes": "Cycle of Magic — modeled. 5%/own-turn CD reduce."},
    500343: {"sim_handler": "set_bonus_mult", "triggers": ["always_stat"],
             "relevance": _stat(),
             "notes": "Lore of Steel — +15% base set bonuses. Applied in artifact stat calc."},
    500344: {"sim_handler": "has_evil_eye", "triggers": ["a1_hit"],
             "relevance": {**_everywhere("relevant"), "cb": "no_op"},
             "notes": "Evil Eye — A1 TM drain. CB boss TM-immune; useful in any other mode."},
    500351: {"sim_handler": "has_lasting_gifts", "triggers": ["per_buff_placed"],
             "relevance": _everywhere(),
             "notes": "Lasting Gifts — modeled. 30% extend buff +1T."},
    500352: {"sim_handler": "has_spirit_haste", "triggers": ["ally_dead"],
             "relevance": _everywhere(),
             "notes": "Spirit Haste — modeled. +8 SPD per dead ally (cap +24, flat additive in _eff_speed)."},
    500353: {"sim_handler": "has_sniper", "triggers": ["per_debuff_placement"],
             "relevance": _everywhere(),
             "notes": "Sniper — modeled. +5% debuff land chance."},
    500354: {"sim_handler": "has_master_hexer", "triggers": ["per_debuff_placement"],
             "relevance": _everywhere(),
             "notes": "Master Hexer — modeled. 30% extend debuff +1T."},
    500361: {"sim_handler": "stat", "triggers": ["always"], "relevance": _stat(),
             "notes": "Elixir of Life — HP +3000 auto-loaded"},
    500362: {"sim_handler": None, "triggers": ["ally_below_25_hp"],
             "relevance": _everywhere(),
             "notes": "Timely Intervention — +20% TM when ally drops below 25% HP. Survival-burst."},
    500363: {"sim_handler": "has_oppressor", "triggers": ["per_active_debuff_self_cast"],
             "relevance": _everywhere(),
             "notes": "Oppressor — modeled. +2.5% TM rate per active debuff cast by this hero (counted via debuff_bar source==champ.name)."},
    500364: {"sim_handler": "has_eagle_eye", "triggers": ["always"],
             "relevance": _stat(),
             "notes": "Eagle-Eye — ACC +50 flat (stat-bonus-equivalent)"},
}


def load_named() -> dict[int, dict]:
    raw = json.load(open(STATIC / "masteries_named.json", encoding="utf-8"))
    items = raw["masteries"] if isinstance(raw, dict) else raw
    return {x["id"]: x for x in items}


def main() -> None:
    named = load_named()
    rows = []
    for mid, info in CLASSIFICATION.items():
        n = named.get(mid, {})
        row = {
            "id": mid,
            "name": n.get("name", "?"),
            "tree": n.get("tree", "?"),
            "row": n.get("row"),
            "col": n.get("col"),
            "description": n.get("description", ""),
            **info,
        }
        rows.append(row)

    missing = sorted(named.keys() - CLASSIFICATION.keys())
    if missing:
        print(f"WARNING — {len(missing)} unclassified:")
        for mid in missing:
            n = named[mid]
            print(f"  {mid}  {n['name']:30s}  {n.get('description', '')[:60]}")

    # Stats
    by_loc_counts = {loc: {"relevant": 0, "no_op": 0, "stat_bonus": 0, "out_of_scope": 0}
                     for loc in LOCATIONS}
    for r in rows:
        for loc, val in r["relevance"].items():
            by_loc_counts[loc][val] = by_loc_counts[loc].get(val, 0) + 1

    payload = {
        "_meta": {
            "generated_by": "tools/m5_mastery_tagger.py",
            "total_classified": len(rows),
            "locations": LOCATIONS,
            "modeled_in_sim": sum(1 for r in rows if r["sim_handler"] and r["sim_handler"] not in ("stat", "set_bonus_mult")),
            "auto_loaded_stat": sum(1 for r in rows if r["sim_handler"] in ("stat", "set_bonus_mult")),
            "relevance_by_location": by_loc_counts,
        },
        "masteries": rows,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Doc — wide table with location columns
    import datetime
    lines = [
        "# Mastery relevance — game-wide (every location)",
        "",
        f"_Generated by `tools/m5_mastery_tagger.py` on {datetime.date.today().isoformat()}_",
        "",
        f"All **{len(rows)} masteries** classified per location. Location codes:",
        "",
    ]
    loc_names = {
        "cb": "Clan Boss (Demon Lord)", "arena": "Classic/Live Arena",
        "tt": "Tag Team Arena", "dungeon": "Dungeons (Dragon/Spider/FK/IG/Mino/4Keeps)",
        "fw": "Faction Wars", "dt": "Doom Tower (120 floors)",
        "cc": "Cursed City", "siege": "Siege",
        "hydra": "Hydra", "chimera": "Chimera",
        "forest": "Grim Forest (Foggy Forest)", "campaign": "Story Campaign",
    }
    for code, name in loc_names.items():
        lines.append(f"- `{code}` — {name}")
    lines.append("")

    lines.append("## Modeling status snapshot")
    lines.append("")
    lines.append(f"- **Modeled with active sim handler**: {payload['_meta']['modeled_in_sim']}")
    lines.append(f"- **Auto-loaded stat bonus** (no handler needed): {payload['_meta']['auto_loaded_stat']}")
    lines.append(f"- **Total**: {len(rows)}")
    lines.append("")
    lines.append("## Relevance by location (count of masteries that trigger)")
    lines.append("")
    lines.append("| Location | relevant | no_op | stat_bonus | out_of_scope |")
    lines.append("|---|---|---|---|---|")
    for loc in LOCATIONS:
        c = by_loc_counts[loc]
        lines.append(f"| **{loc}** | {c['relevant']} | {c['no_op']} | {c['stat_bonus']} | {c['out_of_scope']} |")
    lines.append("")

    # Per-mastery table
    lines.append("## Per-mastery relevance grid")
    lines.append("")
    header_cells = " | ".join(["ID", "Name", "Tree", "Sim flag"] + LOCATIONS + ["Notes"])
    lines.append("| " + header_cells + " |")
    lines.append("|" + "---|" * (len(LOCATIONS) + 5))
    for r in sorted(rows, key=lambda r: r["id"]):
        loc_cells = []
        for loc in LOCATIONS:
            val = r["relevance"].get(loc, "no_op")
            short = {"relevant": "✓", "no_op": "✗", "stat_bonus": "S", "out_of_scope": "-"}[val]
            loc_cells.append(short)
        handler = r["sim_handler"] or ""
        cells = [
            str(r["id"]),
            r["name"],
            r["tree"],
            f"`{handler}`" if handler else "",
        ] + loc_cells + [r["notes"][:90]]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("Legend: ✓ relevant — ✗ no_op — S stat-bonus auto-loaded — - out_of_scope")
    lines.append("")

    OUT_DOC.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_DOC}")
    print()
    print("Per-location 'relevant' mastery counts:")
    for loc in LOCATIONS:
        c = by_loc_counts[loc]
        print(f"  {loc:8s}  relevant={c['relevant']:2d}  no_op={c['no_op']:2d}  stat={c['stat_bonus']:2d}  oos={c['out_of_scope']}")


if __name__ == "__main__":
    main()
