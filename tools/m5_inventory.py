"""Milestone 5 Phase 1 — Game-truth coverage inventory.

Reads every static-data file in `data/static/` and reports what we have
extracted from the live game vs. what's still missing for ALL heroes /
skills / masteries / blessings / sets / locations (NOT just the user's
owned roster).

Outputs:
    docs/m5_phase1_inventory.md   (overwritten)

The goal: a single snapshot of "what's the universe of game content we
can already simulate or recommend on, and where are the gaps."

Run after `tools/refresh_static_data.py` to ensure freshness:
    python3 tools/refresh_static_data.py --check
    python3 tools/m5_inventory.py
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "data" / "static"
OUT = ROOT / "docs" / "m5_phase1_inventory.md"


def _load(name: str) -> Any:
    p = STATIC / name
    if not p.exists():
        return None
    with p.open(encoding="utf-8") as fh:
        return json.load(fh)


def _unwrap_list(blob: Any) -> list:
    if isinstance(blob, list):
        return blob
    if isinstance(blob, dict):
        for k, v in blob.items():
            if k != "_meta" and isinstance(v, list):
                return v
    return []


def _file_mtime(name: str) -> str:
    p = STATIC / name
    if not p.exists():
        return "MISSING"
    import datetime
    return datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d")


def heroes_section() -> list[str]:
    ht = _load("hero_types.json")
    rows = _unwrap_list(ht)
    if not rows:
        return ["## Heroes\n\n_file missing or empty_\n"]
    playable = [r for r in rows if not r.get("is_boss") and r.get("ascend_level") == 0]
    by_el = Counter(r.get("element") for r in playable)
    by_rar = Counter(r.get("rarity") for r in playable)
    by_role = Counter(r.get("role") for r in playable)
    by_fac = Counter(r.get("fraction") for r in playable)

    lines = ["## Heroes (game-truth roster)", ""]
    lines.append(f"- **Total rows in `hero_types.json`**: {len(rows)} (form × ascend tier × base)")
    lines.append(f"- **Distinct hero base_ids**: {len({r['base_id'] for r in rows})}")
    lines.append(f"- **Distinct hero names**: {len({r['name'] for r in rows})}")
    lines.append(f"- **Playable champions (base ascend, non-boss)**: {len(playable)}")
    lines.append(f"- **Boss entries** (per-stage boss types): {sum(1 for r in rows if r.get('is_boss'))}")
    lines.append(f"- **File freshness**: {_file_mtime('hero_types.json')}")
    lines.append("")
    lines.append("### By element")
    for k, v in sorted(by_el.items(), key=lambda kv: -kv[1]):
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("### By rarity")
    for k, v in sorted(by_rar.items(), key=lambda kv: -kv[1]):
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("### By role")
    for k, v in sorted(by_role.items(), key=lambda kv: -kv[1]):
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("### By faction")
    for k, v in sorted(by_fac.items(), key=lambda kv: -kv[1]):
        lines.append(f"- {k}: {v}")
    lines.append("")
    return lines


def skills_section() -> list[str]:
    ht = _load("hero_types.json")
    rows = _unwrap_list(ht)
    sa = _load("skills_all.json")
    srows = _unwrap_list(sa)
    desc = _load("skill_descriptions_all.json") or {}
    sd_dict = desc.get("skill_descriptions", {}) if isinstance(desc, dict) else {}

    all_skill_ids = set()
    hero_to_skills: dict[str, set[int]] = {}
    for r in rows:
        sids = r.get("skill_ids") or []
        for s in sids:
            all_skill_ids.add(s)
        hero_to_skills.setdefault(r["name"], set()).update(sids)

    sid_in_all = {s.get("Id") or s.get("id") for s in srows}
    missing = all_skill_ids - sid_in_all
    affected = {n for n, sids in hero_to_skills.items() if sids & missing}

    lines = ["## Skills", ""]
    lines.append(f"- **Distinct skill IDs referenced by heroes**: {len(all_skill_ids)}")
    lines.append(f"- **`skills_all.json` entries**: {len(srows)} (depth=3 fetch)")
    lines.append(f"- **Coverage**: {len(all_skill_ids & sid_in_all)}/{len(all_skill_ids)} hero-referenced skills present")
    lines.append(f"- **Missing skill IDs**: {len(missing)}")
    lines.append(f"- **Heroes blocked by missing skills**: {len(affected)}")
    lines.append(f"- **Skill descriptions**: {len(sd_dict)} entries (mapped to skill IDs)")
    lines.append(f"- **File freshness**: `skills_all.json` {_file_mtime('skills_all.json')}, `skill_descriptions_all.json` {_file_mtime('skill_descriptions_all.json')}")
    lines.append("")
    if affected:
        lines.append("### Heroes with missing skill data (need fresh `skills_all` refresh)")
        for name in sorted(affected):
            miss = hero_to_skills[name] & missing
            lines.append(f"- {name} — missing {len(miss)} skill(s)")
        lines.append("")

    # Effect-kind distribution over ALL skills (not just owned)
    kind_counter: Counter = Counter()
    for s in srows:
        for e in (s.get("Effects") or []):
            k = e.get("KindId") or e.get("kind")
            kind_counter[k] += 1
    lines.append(f"### Effect kind distribution (across all {len(srows)} skill entries)")
    lines.append(f"- **Distinct effect kinds in use**: {len(kind_counter)}")
    lines.append("")
    lines.append("Top 30 by frequency:")
    for k, v in kind_counter.most_common(30):
        lines.append(f"- `{k}`: {v}")
    lines.append("")
    return lines


def masteries_section() -> list[str]:
    mm = _load("mastery_manifest.json")
    mn = _load("masteries_named.json")
    if not mm:
        return ["## Masteries\n\n_manifest missing_\n"]
    items = mm.get("masteries", []) if isinstance(mm, dict) else mm
    named = {x["id"]: x for x in (mn.get("masteries", []) if isinstance(mn, dict) else mn or [])}

    simple = [x for x in items if x.get("is_simple_stat_bonus")]
    hand = [x for x in items if x.get("is_hand_coded")]
    unmapped = [x for x in items if not x.get("is_simple_stat_bonus") and not x.get("is_hand_coded")]

    lines = ["## Masteries", ""]
    lines.append(f"- **Total masteries**: {len(items)} (3 trees × 22 each)")
    lines.append(f"- **Simple stat-bonus (auto-loaded from `/masteries-truth`)**: {len(simple)}")
    lines.append(f"- **Hand-coded conditional procs in `raid_data.py`**: {len(hand)}")
    lines.append(f"- **UNMAPPED** (no sim model yet): {len(unmapped)}")
    lines.append(f"- **File freshness**: {_file_mtime('mastery_manifest.json')}")
    lines.append("")
    lines.append("### Hand-coded masteries (modeled in sim)")
    for x in hand:
        n = named.get(x["id"], {})
        lines.append(f"- {x['id']} **{n.get('name', '?')}** — {n.get('description', '')[:80]}")
    lines.append("")
    lines.append("### Unmapped masteries (potential sim gaps)")
    for x in unmapped:
        n = named.get(x["id"], {})
        lines.append(f"- {x['id']} **{n.get('name', '?')}** [{n.get('tree', '?')}] — {n.get('description', '')[:90]}")
    lines.append("")
    return lines


def blessings_section() -> list[str]:
    bm = _load("blessing_manifest.json")
    if not bm:
        return ["## Blessings\n\n_manifest missing_\n"]
    items = bm.get("blessings", []) if isinstance(bm, dict) else bm
    hand = [x for x in items if x.get("is_hand_coded") or x.get("hand_coded")]
    hand_ids = {x["id"] for x in hand}
    leg = [x for x in items if x.get("rarity") == "Legendary"]
    leg_unmodeled = [x for x in leg if x["id"] not in hand_ids]

    lines = ["## Blessings", ""]
    lines.append(f"- **Total blessings**: {len(items)}")
    lines.append(f"- **Legendary blessings**: {len(leg)}")
    lines.append(f"- **Hand-coded proc logic (in sim)**: {len(hand)}")
    lines.append(f"- **Legendary blessings WITHOUT hand-coded sim logic**: {len(leg_unmodeled)}")
    lines.append(f"- **File freshness**: {_file_mtime('blessing_manifest.json')}")
    lines.append("")
    lines.append("### Hand-coded blessings")
    for b in hand:
        lines.append(f"- **{b['id']}** ({b.get('divinity')}, {b.get('rarity')})")
    lines.append("")
    lines.append("### Legendary blessings with NO sim proc model (potential gaps)")
    for b in leg_unmodeled:
        sg = b.get("static_grade_bonuses", [])
        top = sg[-1].get("stat_kinds", []) if sg else []
        lines.append(f"- **{b['id']}** ({b.get('divinity')}) — top-grade stats: {top}")
    lines.append("")
    return lines


def effects_section() -> list[str]:
    ef = _load("effects.json")
    rows = _unwrap_list(ef)
    if not rows:
        return ["## Effects (buff/debuff catalog)\n\n_file missing_\n"]
    lines = ["## Effects (buff/debuff catalog)", ""]
    lines.append(f"- **Total effect type entries**: {len(rows)}")
    lines.append(f"- **File freshness**: {_file_mtime('effects.json')}")
    # Distribution of LifetimeUpdateType (sim-relevant — Custom = special tick).
    # Field is nested under StatusParams in the live mod export.
    lifetime_counter: Counter = Counter()
    kind_counter: Counter = Counter()
    group_counter: Counter = Counter()
    stack_counter: Counter = Counter()
    can_stack = 0
    is_passive = 0
    for r in rows:
        sp = r.get("StatusParams") or {}
        lt = sp.get("LifetimeUpdateType") if isinstance(sp, dict) else None
        lifetime_counter[str(lt)] += 1
        kind_counter[r.get("KindId", "?")] += 1
        group_counter[r.get("Group", "?")] += 1
        stack_counter[r.get("StackCount", "?")] += 1
        if r.get("CanStack"): can_stack += 1
        if r.get("IsPassiveBonus"): is_passive += 1
    lines.append("")
    lines.append("### Lifetime update type distribution (Custom = special-cased in sim)")
    for k, v in lifetime_counter.most_common():
        lines.append(f"- `{k}`: {v}")
    lines.append("")
    lines.append("### Effect group distribution")
    for k, v in group_counter.most_common():
        lines.append(f"- `{k}`: {v}")
    lines.append("")
    lines.append(f"- **Stackable effects** (`CanStack=true`): {can_stack}")
    lines.append(f"- **Passive bonuses** (`IsPassiveBonus=true`): {is_passive}")
    lines.append("")
    lines.append("### Effect kind distribution (top 25)")
    for k, v in kind_counter.most_common(25):
        lines.append(f"- `{k}`: {v}")
    lines.append("")
    return lines


def sets_section() -> list[str]:
    af = _load("artifact_sets.json")
    rows = _unwrap_list(af)
    if not rows:
        return ["## Artifact Sets\n\n_file missing_\n"]
    proc_kw = {"Lifesteal", "Stoneskin", "Untouchable", "Reflex", "Counter", "Stun", "Block",
               "Resist", "Provoke", "Frenzy", "Wrath", "Bloodthirst", "Shield", "IgnoreDef",
               "Burn"}
    by_name = sorted({r["set"] for r in rows})
    proc_named = [n for n in by_name if any(k.lower() in n.lower() for k in proc_kw)]
    lines = ["## Artifact Sets", ""]
    lines.append(f"- **Distinct artifact set names**: {len(by_name)}")
    lines.append(f"- **Rows in `artifact_sets.json`** (per piece count): {len(rows)}")
    lines.append(f"- **Sets with proc-suggesting names**: {len(proc_named)} (validate proc modeling)")
    lines.append(f"- **File freshness**: {_file_mtime('artifact_sets.json')}")
    lines.append("")
    lines.append("### Proc-suggesting set names (need sim coverage check)")
    for n in proc_named:
        lines.append(f"- `{n}`")
    lines.append("")
    return lines


def location_section() -> list[str]:
    lines = ["## Per-location game data", ""]
    files = [
        ("alliance_bosses.json", "CB boss profiles (Easy→UNM, 6 difficulties)"),
        ("cb_bosses.json", "CB boss skill detail dump"),
        ("stage_bosses.json", "Dungeon + FoggyForest boss stats (228 entries)"),
        ("stages.json", "Master stage list (every battle the game knows about)"),
        ("hydra.json", "Hydra competition data"),
        ("chimera.json", "Chimera competition data"),
        ("siege.json", "Siege data"),
        ("cursed_city.json", "Cursed City stages"),
        ("foggy_forest.json", "Grim Forest stages"),
        ("stage_areas.json", "Area-type metadata (Story/Dungeon/Hydra/...)"),
        ("stage_regions.json", "Regions (campaign chapters, dungeon difficulty tiers)"),
        ("stage_rewards.json", "Per-area reward profiles"),
        ("drops.json", "Per-region/per-difficulty artifact drops"),
        ("battle_quests.json", "Battle quest types (35 entries)"),
        ("gameplay.json", "Global gameplay tunables"),
        ("primary_bonuses.json", "Artifact primary stats by slot/rank"),
        ("secondary_bonuses.json", "Artifact substats by rank/rarity"),
        ("ascend_bonuses.json", "Artifact ascension bonuses"),
        ("artifact_settings.json", "Artifact roll/upgrade settings"),
        ("factions.json", "Race/faction enum data"),
        ("forge_sets.json", "Forge craft recipes"),
    ]
    for fname, label in files:
        p = STATIC / fname
        if p.exists():
            size_kb = p.stat().st_size // 1024
            lines.append(f"- ✅ `{fname}` — {label} ({size_kb} KB, {_file_mtime(fname)})")
        else:
            lines.append(f"- ❌ `{fname}` — {label} **MISSING**")
    lines.append("")
    return lines


def build() -> str:
    import datetime
    parts = [
        f"# Milestone 5 Phase 1 — Game-truth coverage inventory",
        "",
        f"_Generated by `tools/m5_inventory.py` on {datetime.date.today().isoformat()}_",
        "",
        "This document maps what we've extracted from the live game (via the BepInEx mod's",
        "`StaticData` exports) against the full universe of Raid content — so the user can",
        "see at a glance where sim coverage is solid and where there are still hand-coded",
        "or missing pieces. Heroes are inventoried across the entire roster, not just the",
        "user's owned champions.",
        "",
        "Refresh data and regenerate:",
        "```bash",
        "python3 tools/refresh_static_data.py",
        "python3 tools/m5_inventory.py",
        "```",
        "",
    ]
    parts += heroes_section()
    parts += skills_section()
    parts += masteries_section()
    parts += blessings_section()
    parts += effects_section()
    parts += sets_section()
    parts += location_section()
    return "\n".join(parts)


def main() -> None:
    out = build()
    OUT.write_text(out, encoding="utf-8")
    print(f"Wrote {OUT}  ({len(out)} chars)")


if __name__ == "__main__":
    main()
