"""Milestone 5 — Cross-hero synergy graph.

Derives, for every playable champion, what they PROVIDE to a team and what
they BENEFIT FROM, purely from game-truth skill descriptions + the effect-kind
catalog. Then builds provider->beneficiary synergy edges so the (future)
recommender can assemble teams for ANY location, not just CB.

Sources of truth (no outside data):
    data/static/skill_descriptions_all.json — localized skill text naming every
        buff/debuff/DoT in [Brackets] (game-truth, full roster)
    data/static/hero_types.json — roster + which skill IDs belong to each hero
    data/m5_hero_catalog.jsonl — per-hero effect-kinds (from m5_hero_catalog.py)

Outputs:
    data/m5_synergy.jsonl       — per-hero {provides, needs, role} record
    docs/m5_synergy_graph.md    — summary + top providers per synergy axis

Synergy model
-------------
PROVIDES (what a hero brings to allies / does to enemies):
    team_buff:<name>   — buff placed on allies (Increase ATK/DEF/SPD/CR/CD,
                         Shield, Block Damage, Unkillable, Continuous Heal,
                         Counterattack, Reflect Damage, Strengthen, Veil, ...)
    enemy_debuff:<name>— debuff on enemies (Decrease DEF/ATK/SPD/ACC, Weaken,
                         Heal Reduction, Hex, Provoke, ...)
    dot:<name>         — Poison / HP Burn
    dot_detonate       — detonates/activates DoTs (multiplies DoT teams)
    tm_control         — TM boost / extra turn / TM drain
    cleanse            — removes debuffs from allies
    revive             — revive ally

NEEDS (what makes this hero stronger — matched against allies' PROVIDES):
    def_break          — DPS wants enemy Decrease DEF / Weaken
    poison_synergy     — poison dealer wants Poison Sensitivity + detonators
    burn_synergy       — burn dealer wants burn activators
    speed/tm           — wants TM control to cycle
    survival           — squishy DPS wants Shield/Block Damage/heal providers

ROLE (coarse archetype): attacker / support / debuffer / healer / tank / dot.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "data" / "static"
OUT_JSONL = ROOT / "data" / "m5_synergy.jsonl"
OUT_DOC = ROOT / "docs" / "m5_synergy_graph.md"

_BRACKET = re.compile(r"\[([^\]]+)\]")
_TAG = re.compile(r"<[^>]+>")

# Buffs are placed on allies/self; debuffs on enemies. Classify by the
# bracketed name (game's canonical effect names).
BUFF_NAMES = {
    "Increase ATK", "Increase DEF", "Increase SPD", "Increase C. RATE",
    "Increase C. DMG", "Increase ACC", "Increase RES",
    "Shield", "Continuous Heal", "Block Damage", "Block Debuffs",
    "Unkillable", "Counterattack", "Reflect Damage", "Strengthen",
    "Veil", "Perfect Veil", "Ally Protection", "Revive On Death",
    "Revive on Death", "Increase Crit Rate", "Taunt",
}
DEBUFF_NAMES = {
    "Decrease DEF", "Decrease ATK", "Decrease SPD", "Decrease ACC",
    "Decrease C. RATE", "Decrease C. DMG", "Decrease RES", "Decrease C.RATE",
    "Weaken", "Heal Reduction", "Hex", "Provoke", "Stun", "Freeze",
    "Sleep", "Fear", "True Fear", "Petrification", "Sheep",
    "Block Buffs", "Block Active Skills", "Block Revive", "Bomb",
    "Poison Sensitivity",
}
DOT_NAMES = {"Poison", "HP Burn", "Leech"}

# Control debuffs that the CB boss (and most raid bosses) are immune to —
# flag them so the recommender can downweight in boss content.
CONTROL_DEBUFFS = {"Stun", "Freeze", "Sleep", "Provoke", "Fear", "True Fear",
                   "Petrification", "Sheep"}


def _load_json(name):
    p = STATIC / name
    with p.open(encoding="utf-8") as fh:
        return json.load(fh)


def _unwrap(blob):
    if isinstance(blob, list):
        return blob
    if isinstance(blob, dict):
        for k, v in blob.items():
            if k != "_meta" and isinstance(v, list):
                return v
    return []


def _clean(txt: str) -> str:
    return _TAG.sub("", txt or "")


def main() -> None:
    desc_blob = _load_json("skill_descriptions_all.json")
    sd = desc_blob.get("skill_descriptions", {})
    ht = _unwrap(_load_json("hero_types.json"))

    # Load per-hero effect kinds from the Phase 2 catalog (for DoT-detonate /
    # TM-control / cleanse signals that come from effect kinds, not bracket names).
    kinds_by_hero: dict[str, set[str]] = {}
    cat_path = ROOT / "data" / "m5_hero_catalog.jsonl"
    if cat_path.exists():
        with cat_path.open(encoding="utf-8") as fh:
            for line in fh:
                row = json.loads(line)
                kinds = set()
                for sk in row.get("skills", []):
                    kinds.update(sk.get("kinds", []))
                kinds_by_hero[row["name"]] = kinds

    playable = [r for r in ht if not r.get("is_boss") and r.get("ascend_level") == 0]

    # `hero_types.json` skill_ids is incomplete for ~47% of heroes (omits one
    # skill — e.g. Demytha's A3 Block Damage / Maneater's A2 TM-drain). Skill
    # IDs follow `base*100 + N`; the full kit is recovered by expanding each
    # listed skill's base across N=1..6 and keeping those present in the
    # description set. Verified: this restores Demytha [Block Damage] etc.
    sd_ids = {int(k) for k in sd.keys()}

    def full_skill_family(listed_ids: list[int]) -> list[int]:
        bases = {s // 100 for s in listed_ids}
        out = set(listed_ids)
        for base in bases:
            for n in range(1, 7):
                cand = base * 100 + n
                if cand in sd_ids:
                    out.add(cand)
        return sorted(out)

    records = []
    provider_index: dict[str, list[str]] = defaultdict(list)  # provide-tag -> [hero]
    recovered_skills = 0

    for hero in playable:
        name = hero["name"]
        listed = hero.get("skill_ids") or []
        sids = full_skill_family(listed)
        recovered_skills += len(sids) - len(set(listed))
        provides: set[str] = set()
        dot_kinds: set[str] = set()
        control_only = True  # becomes False if any non-control debuff present

        for sid in sids:
            txt = _clean(sd.get(str(sid), ""))
            if not txt:
                continue
            for raw in _BRACKET.findall(txt):
                nm = raw.strip()
                if nm in BUFF_NAMES:
                    provides.add(f"team_buff:{nm}")
                elif nm in DEBUFF_NAMES:
                    if nm == "Poison Sensitivity":
                        provides.add("enables:poison")  # boosts poison dealers
                    else:
                        provides.add(f"enemy_debuff:{nm}")
                        if nm not in CONTROL_DEBUFFS:
                            control_only = False
                elif nm in DOT_NAMES:
                    provides.add(f"dot:{nm}")
                    dot_kinds.add(nm)

        # Effect-kind-derived signals (full-roster reliable).
        kinds = kinds_by_hero.get(name, set())
        if {"Detonate", "DetonateContinuousDamage", "ForceStatusEffectTick"} & kinds:
            provides.add("dot_detonate")
        if {"IncreaseStamina", "ExtraTurn"} & kinds:
            provides.add("tm_control")
        if "ReduceStamina" in kinds:
            provides.add("tm_drain")
        if "RemoveDebuff" in kinds:
            provides.add("cleanse")
        if {"Revive", "ReviveOnDeath"} & kinds:
            provides.add("revive")
        if "ReduceCooldown" in kinds:
            provides.add("cooldown_reduction")
        if "Heal" in kinds:
            provides.add("heal")
        # Buff-duration extension (Demytha-A2 "Increase buff duration" style).
        # This is the linchpin of BD/UK stall chains: a 2-turn defensive buff
        # only holds a 50-turn run if an ally re-extends it each cycle.
        if "IncreaseBuffLifetime" in kinds:
            provides.add("buff_extension")

        # NEEDS — what makes this hero better (matched vs allies' provides).
        needs: set[str] = set()
        is_attacker = (hero.get("role") == "Attack")
        if is_attacker:
            needs.add("def_break")        # wants Decrease DEF / Weaken
            needs.add("tm_control")       # wants to cycle faster
        if "dot:Poison" in provides:
            needs.add("poison_synergy")   # wants Poison Sensitivity + detonators
        if "dot:HP Burn" in provides:
            needs.add("burn_synergy")
        # squishy roles want survival support
        if hero.get("role") in ("Attack", "Support"):
            needs.add("survival_support")
        # A hero supplying a short-lived defensive buff (UK / BD / Shield /
        # Continuous Heal / Counterattack) needs an ally to re-extend it for a
        # 50-turn stall — matched against allies' provides:buff_extension.
        _DEF_BUFFS = ("team_buff:Unkillable", "team_buff:Block Damage",
                      "team_buff:Shield", "team_buff:Continuous Heal",
                      "team_buff:Counterattack")
        if any(p in provides for p in _DEF_BUFFS):
            needs.add("buff_extension")

        # ROLE (coarse)
        n_debuff = sum(1 for p in provides if p.startswith("enemy_debuff:"))
        n_buff = sum(1 for p in provides if p.startswith("team_buff:"))
        n_dot = len(dot_kinds)
        if "heal" in provides and n_buff >= 1:
            role = "healer/support"
        elif n_dot >= 1 and (is_attacker or "dot_detonate" in provides):
            role = "dot"
        elif n_debuff >= 2:
            role = "debuffer"
        elif n_buff >= 2:
            role = "support"
        elif is_attacker:
            role = "attacker"
        else:
            role = hero.get("role", "?").lower()

        rec = {
            "name": name,
            "base_id": hero.get("base_id"),
            "element": hero.get("element"),
            "rarity": hero.get("rarity"),
            "fraction": hero.get("fraction"),
            "game_role": hero.get("role"),
            "synergy_role": role,
            "provides": sorted(provides),
            "needs": sorted(needs),
            "debuffs_control_only": control_only and n_debuff > 0,
        }
        records.append(rec)
        for p in provides:
            provider_index[p].append(name)

    with OUT_JSONL.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Doc
    import datetime
    lines = [
        "# Cross-hero synergy graph",
        "",
        f"_Generated by `tools/m5_synergy_graph.py` on {datetime.date.today().isoformat()}_",
        "",
        f"Universe: **{len(records)} playable champions**. Provides/needs derived from",
        "game-truth skill descriptions (bracketed effect names) + effect-kind catalog.",
        "This is the recommender's matchmaking substrate — works for every location.",
        "",
        "## Synergy-role distribution",
        "",
    ]
    role_counts = Counter(r["synergy_role"] for r in records)
    for role, n in role_counts.most_common():
        lines.append(f"- **{role}**: {n}")
    lines.append("")

    # Top providers per axis — the recommender's "who do I add for X" lookup.
    lines.append("## Provider counts per synergy axis")
    lines.append("")
    lines.append("| Provide tag | # heroes |")
    lines.append("|---|---|")
    for tag in sorted(provider_index, key=lambda t: -len(provider_index[t])):
        lines.append(f"| `{tag}` | {len(provider_index[tag])} |")
    lines.append("")

    # Highlight the rarest, highest-value providers (CB-critical buffs)
    lines.append("## Key survival/enabler providers (recommender priorities)")
    lines.append("")
    for tag in ["team_buff:Block Damage", "team_buff:Unkillable",
                "team_buff:Shield", "enemy_debuff:Decrease DEF",
                "enemy_debuff:Weaken", "enables:poison", "dot_detonate",
                "tm_control", "cleanse", "revive"]:
        heroes = provider_index.get(tag, [])
        sample = ", ".join(sorted(heroes)[:12])
        more = f" … (+{len(heroes)-12} more)" if len(heroes) > 12 else ""
        lines.append(f"### `{tag}` — {len(heroes)} heroes")
        lines.append(f"{sample}{more}" if heroes else "_none_")
        lines.append("")

    lines.append("## Files")
    lines.append(f"- Per-hero detail: `data/m5_synergy.jsonl` ({len(records)} records)")
    lines.append("")
    lines.append("Regenerate after refreshing static data + `tools/m5_hero_catalog.py`:")
    lines.append("```bash")
    lines.append("python3 tools/m5_hero_catalog.py")
    lines.append("python3 tools/m5_synergy_graph.py")
    lines.append("```")

    OUT_DOC.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_JSONL}  ({len(records)} heroes)")
    print(f"  recovered {recovered_skills} skills omitted from hero_types.json skill_ids")
    print(f"Wrote {OUT_DOC}")
    print()
    print("Synergy roles:")
    for role, n in role_counts.most_common():
        print(f"  {role}: {n}")
    print()
    print("Sample key providers:")
    for tag in ["team_buff:Block Damage", "team_buff:Unkillable", "enables:poison", "dot_detonate"]:
        print(f"  {tag}: {len(provider_index.get(tag, []))} heroes")


if __name__ == "__main__":
    main()
