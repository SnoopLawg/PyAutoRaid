"""Milestone 5 Phase 2 — Per-hero skill→sim-effect coverage catalog.

For every playable champion in the game (1113 entries from hero_types.json),
decode each skill (A1/A2/A3/Passive/Leader) and report:
    - skill effect kinds present
    - which are MODELED by the cb_sim translator (load_game_profiles.py)
    - which are NO-OP vs CB (intentionally not modeled — DestroyHp, Stun, etc.)
    - which are GAPS (could matter for CB but no sim path today)

Output formats:
    docs/m5_phase2_hero_catalog.md   (summary report)
    data/m5_hero_catalog.jsonl       (per-hero machine-readable detail)

This is the universe view — answers "if I pulled hero X tomorrow, would
PyAutoRaid know how to slot them into a sim comp?"

Source-of-truth files:
    data/static/hero_types.json        — roster + skill_ids
    data/static/skills_all.json        — every skill's effect list
    data/static/skill_descriptions_all.json — in-game tooltip text
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "data" / "static"
OUT_DOC = ROOT / "docs" / "m5_phase2_hero_catalog.md"
OUT_JSONL = ROOT / "data" / "m5_hero_catalog.jsonl"


# === sim coverage map ========================================================
# Sources of truth:
#   - data/static/effect_kind_id.json — full enum (232 kinds)
#   - tools/load_game_profiles.py kind=NUM handlers (legacy numeric path)
#   - tools/load_game_profiles.py ge.kind_id handlers (modern string path)
#   - tools/cb_sim.py SimSkill flags (grants_extra_turn, etc.)

# Kinds with an active sim translation path — either via the loaders above
# OR handled in cb_sim's per-turn loop / damage pipeline.
MODELED_KINDS = {
    "ApplyBuff", "ApplyOrProlongBuff",          # kind=4000 — team_buffs
    "ApplyDebuff", "ApplyOrProlongDebuff",      # kind=5000 — debuff placement
    "ReduceCooldown",                            # kind=4009 — A2/A3 CD reduce
    "Damage",                                    # kind=6000 — direct attack
    "IncreaseStamina",                           # kind=4001 — self/team TM fill
    "Heal",                                      # kind=1000 — self/team heal
    "IncreaseBuffLifetime",                      # kind=4011 — extend_buffs / Demy
    "IncreaseDebuffLifetime",                    # kind=5008 — extend_debuffs_*
    "ReduceDebuffLifetime",                      # kind=4010 — Demy A2 shrink (no-op vs boss)
    "ForceStatusEffectTick",                     # kind=9002 — activate DoTs
    "Detonate", "DetonateContinuousDamage",      # kind=5010/5018 — detonate_poisons
    "TeamAttack",                                # kind=4006 — ally_attack
    "ExtraTurn",                                 # kind=4007 — grants_extra_turn
    # Passive / damage-pipeline kinds (applied during damage calc, not direct effects)
    "PassiveChangeStats",                        # kind=4013 — leader/passive stats
    "PassiveBonus",                              # kind=4015 — generic
    "ChangeDamageMultiplier",                    # kind=7004 — set/blessing/aura
    "ChangeDefenceModifier",                    # kind=7001 — ignore_def
    "ChangeCalculatedDamage",                    # kind=7006 — damage modifier (set procs)
    "HitTypeModifier",                           # kind=7000 — crit/glance forcing
    "IgnoreDefenceModifier",                     # kind=7013
    # Effect-relationship kinds — handled via classify_* in effect_engine
    "StartOfStatusBuff", "EndOfStatusBuff",      # buff lifecycle markers
    "StartOfStatusDebuff", "EndOfStatusDebuff",
    "StartOfNeutralInstantEffects",
    "EndOfNeutralInstantEffects",
    "EndOfInstantBuff", "EndOfInstantDebuff",
    "EndOfCounters", "EndOfTechnical",
    "EndOfStatusNeutral",
}

# Intentionally NO-OP vs CB Demon Lord:
#   - Demon Lord is immune to: Stun, Sleep, Freeze, Provoke, all TM manipulation
#   - CB is single-round, single-target so challenge/quest/counter mechanics no-op
#   - No transformations, no banishment, no Hydra/Chimera/Doom-tower mechanics
# Memory: project_cb_boss_tm_immunity.md, project_cb_boss_turn_50_bypass.md
NO_OP_VS_CB_KINDS = {
    # TM manipulation against the boss (boss immune)
    "ReduceStamina",                             # kind=5001
    "ConvertStaminaReduceToIncrease",            # kind=4026
    "ChangeStaminaModifier",                     # kind=7010
    "EvenStamina",                               # kind=15001
    # Control debuffs (boss immune)
    "Stun", "Freeze", "Sleep", "Provoke", "Fear", "Petrification",
    "Polymorph", "Seal", "Ensnare", "Entangle", "Banish",
    "SheepTransformation", "CancelTransformation", "Transformation",
    "ChangeHeroForm", "ForceChangeHeroForm",
    "SkipNextTurn",                              # kind=5017
    # Damage caps / lethal-damage bypasses (handled in formula, not direct effect)
    "DestroyHp",                                 # kind=5009 — except turn-50 bypass
    "ChangeDestroyHpAmount",                    # kind=7008
    "DelayLetalDamage",                          # kind=15003
    "RestoreDestroyedHp",                        # kind=4023 — rare in CB
    # Counters / non-CB battle mechanics (Hydra, Chimera, Doom Tower, Sleep counter)
    "SetHeroCounter", "SetSpecificHeroCounter",  # kind=9009/9028
    "SetSoulCounter", "SoulCounter",
    "SetVoidAbyssCounter", "VoidAbyss",
    "ChangeSkyWrathCounter", "SkyWrath",
    "SetSleepCounter", "SleepCounter",
    "SetShieldHitCounter",
    "SetLightOrbsStackCount",
    "SetHydraHitCounter", "HydraHitCounter",
    "GrowHydraHead",                             # Hydra-specific
    "UpdateCombo",
    "HungerCounter", "SetHungerCounter",
    "PlaceHungerCounter", "Devour", "Devoured",
    "Digestion", "Chewing",
    # Challenge/quest tracking (non-battle effects)
    "StartChallenge", "SetChallengeProgress", "SetChallengeCounter",
    "AddQuestProgress", "SetQuestProgress", "FailQuest",
    # Pre-battle / setup
    "SetHeroTier",                               # kind=9060
    "GiveFirstTurn",                             # kind=9070
    "ShowSecretSkill",                           # kind=4005 — UI only
    "MarkAsEvader", "Evade",                     # arena-specific
    # Revive: CB heroes don't come back during the same key (one-shot run)
    "Revive",                                    # kind=0
    "ReviveOnDeath",                             # kind=2006
    "BlockRevive",                               # kind=3011
    # Visualization only
    "ActionForVisualization",                    # kind=11010
    # Boss is single-target so summons don't apply meaningfully against it
    "Summon", "CopyHero",                        # kind=8000/8001
    # Skill-target changers (CB has single boss target, manipulating skill targets is moot)
    "ChangeEffectTarget", "ChangeSkillTarget", "ChangeSkillTargets",
    "CancelEffect",
    # CB-irrelevant duel/grab mechanics
    "Grab", "Grabbed", "DuelTargetMark", "DuelProducerMark",
    # Misc
    "DelayedDamage",                             # kind=14003 — rare in CB
    "ApplyNeutral",                              # kind=14000
    "ApplyCounter",                              # kind=9027 — counter-mechanic
    "ThunderStunApplier",                        # rare
}

# Kinds that COULD affect CB sim but have no path today.
GAP_KINDS = {
    # Hero-side buff manipulation against boss buffs (the boss has minor buffs
    # from its own skills — sim tracks boss debuffs but not hero-stripping)
    "RemoveBuff",                                # kind=5003 — strip boss buff
    "StealBuff",                                 # kind=5002 — would steal Demy BD!
    "ConvertStatusBuffToDebuff",                 # kind=5016
    "TransferDebuff",                            # kind=4022
    # Hero-side debuff manipulation (cleanse / remove from teammates)
    "RemoveDebuff",                              # kind=4003 — cleanse ally
    "ReturnDebuffs",                             # kind=4021
    "ConvertStatusDebuffToBuff",                 # kind=4027
    # Cooldown manipulation against boss
    "IncreaseCooldown",                          # kind=5004 — would extend boss AOE2 CD
    "ChangeCooldownModifier",                    # kind=7021
    # Lifetime manipulation (hero side, on boss debuffs)
    "ReduceBuffLifetime",                        # kind=5005 — shrink boss buff
    "EffectDurationModifier",                    # kind=10000
    "ChangeEffectProtection",                    # kind=10001
    "ReplaceStatusEffectOnApplying",             # kind=10002
    # Passive procs not yet modeled (would help survival)
    "PassiveBlockDebuff",                        # kind=4014
    "PassiveBlockBuff",                          # kind=5013
    "PassiveBlockEffect",                        # kind=9030
    "PassiveCounterattack",                      # kind=4012
    "PassiveReflectDamage",                      # kind=4017
    "PassiveShareDamage",                        # kind=4018
    "PassiveUnkillable",                         # kind=4024
    "PassiveBonus",
    "ActivateCounterattack",                     # kind=4028
    # Effect-chance / accuracy modifiers
    "MultiplyEffectChance",                      # kind=7003
    "ChangeEffectAccuracy",                      # kind=7002
    "ChangeEffectResistance",                    # kind=7012
    "AddIgnoredEffects",                         # kind=7005
    "ChangeEffectRepeatCount",                   # kind=7007
    "ChangeEffectApplyMode",                     # kind=7015
    "AddChanceToActivateOnGlancingHit",          # kind=7016 — known glance-gate mechanic
    "ChangeCritChance",                          # kind=7018
    "ChangeRestoreHPMultiplier",                 # kind=7019
    "ChangeReviveHealValue",                     # kind=7020
    "ChangeHealMultiplier",                      # kind=7009
    "ChangeShieldMultiplier",                    # kind=7011
    "ChangeStatForEffect",                       # kind=7023
    "ExcludeHitType",                            # kind=7014
    "ChangeCounterattackParams",                 # kind=7017
    # Debuff multiplication / amplification
    "MultiplyDebuff",                            # kind=5011 — Karam, Cardiel
    "MultiplyBuff",                              # kind=4016
    "ActivateSkill",                             # kind=4004 — trigger another of this hero's skills (Sicia A3, etc.)
    "DestroyStats",                              # kind=5014 — Dragon-only mechanic
    "ReduceShield", "IncreaseShield",            # kind=5012/4020
    "ReduceStoneSkin",                           # kind=5019
    "SwapHealth",                                # kind=5007
    "LifeShare",                                 # kind=4008
    "ShareDamage",                               # kind=2007
    "ReflectDamage",                             # kind=2010
    "CopyStatusBuff",                            # kind=4029
    "EffectContainer",                           # kind=11001 — group/container
    "CheckTargetForCondition",                   # kind=11000
    "GiveTurn",                                  # kind=4025 — give ally a turn (BU-style)
}


def _load(name: str):
    p = STATIC / name
    if not p.exists():
        return None
    with p.open(encoding="utf-8") as fh:
        return json.load(fh)


def _unwrap_list(blob):
    if isinstance(blob, list):
        return blob
    if isinstance(blob, dict):
        for k, v in blob.items():
            if k != "_meta" and isinstance(v, list):
                return v
    return []


def classify(kind: str) -> str:
    if kind in MODELED_KINDS:
        return "modeled"
    if kind in NO_OP_VS_CB_KINDS:
        return "no_op_vs_cb"
    if kind in GAP_KINDS:
        return "gap"
    return "unknown"


def main() -> None:
    ht = _load("hero_types.json")
    sa = _load("skills_all.json")
    desc_blob = _load("skill_descriptions_all.json") or {}
    sd_dict = desc_blob.get("skill_descriptions", {}) if isinstance(desc_blob, dict) else {}

    hero_rows = _unwrap_list(ht)
    skill_rows = _unwrap_list(sa)
    skill_by_id = {s.get("Id") or s.get("id"): s for s in skill_rows}

    # Only base-ascend, non-boss playable champions.
    playable = [r for r in hero_rows if not r.get("is_boss") and r.get("ascend_level") == 0]

    per_hero: list[dict] = []
    coverage_counter: Counter = Counter()
    gap_kinds_by_hero: dict[str, set[str]] = defaultdict(set)

    for hero in playable:
        name = hero["name"]
        sids = hero.get("skill_ids") or []
        skills_info = []
        hero_kinds: Counter = Counter()
        hero_status_by_kind: dict[str, str] = {}

        for sid in sids:
            skill = skill_by_id.get(sid)
            if not skill:
                skills_info.append({"id": sid, "missing": True})
                continue
            effs = skill.get("Effects") or []
            kinds = [e.get("KindId") for e in effs if e.get("KindId")]
            for k in kinds:
                hero_kinds[k] += 1
                hero_status_by_kind[k] = classify(k)
            sname = ""
            n = skill.get("Name") or {}
            if isinstance(n, dict):
                sname = n.get("DefaultValue", "")
            skills_info.append({
                "id": sid,
                "name": sname,
                "group": skill.get("Group"),
                "cooldown": skill.get("Cooldown"),
                "effect_count": len(effs),
                "kinds": kinds,
                "desc_excerpt": (sd_dict.get(str(sid)) or "")[:120],
            })

        gaps = {k for k, st in hero_status_by_kind.items() if st == "gap"}
        unknowns = {k for k, st in hero_status_by_kind.items() if st == "unknown"}
        modeled = {k for k, st in hero_status_by_kind.items() if st == "modeled"}

        # Coverage label: GREEN if all kinds modeled-or-noop, YELLOW if gaps only,
        # RED if unknowns. Hero with no skill data → BLACK.
        if not skills_info or all(s.get("missing") for s in skills_info):
            tier = "no_skill_data"
        elif unknowns:
            tier = "unknown_kinds"
        elif gaps:
            tier = "has_gaps"
        else:
            tier = "fully_modeled"
        coverage_counter[tier] += 1
        for g in gaps:
            gap_kinds_by_hero[g].add(name)

        per_hero.append({
            "name": name,
            "base_id": hero.get("base_id"),
            "element": hero.get("element"),
            "rarity": hero.get("rarity"),
            "role": hero.get("role"),
            "fraction": hero.get("fraction"),
            "skill_ids": sids,
            "skills": skills_info,
            "coverage_tier": tier,
            "modeled_kinds": sorted(modeled),
            "gap_kinds": sorted(gaps),
            "unknown_kinds": sorted(unknowns),
        })

    # Write per-hero JSONL.
    with OUT_JSONL.open("w", encoding="utf-8") as fh:
        for row in per_hero:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    # Write the doc.
    lines = []
    lines.append("# Milestone 5 Phase 2 — Per-hero skill→sim-effect coverage")
    lines.append("")
    import datetime
    lines.append(f"_Generated by `tools/m5_hero_catalog.py` on {datetime.date.today().isoformat()}_")
    lines.append("")
    lines.append(f"Universe: **{len(playable)} playable champions** from `hero_types.json` (base ascend, non-boss).")
    lines.append("")
    lines.append("## Coverage tiers")
    lines.append("")
    lines.append("| Tier | Count | Meaning |")
    lines.append("|---|---|---|")
    lines.append(f"| **fully_modeled** | {coverage_counter['fully_modeled']} | Every effect kind on every skill is either modeled by the sim translator or intentionally no-op vs CB |")
    lines.append(f"| **has_gaps** | {coverage_counter['has_gaps']} | One or more effect kinds COULD matter for CB but have no sim path today (see gap-kind table below) |")
    lines.append(f"| **unknown_kinds** | {coverage_counter['unknown_kinds']} | Has effect kinds not in MODELED/NO_OP/GAP sets — need investigation |")
    lines.append(f"| **no_skill_data** | {coverage_counter['no_skill_data']} | Skill IDs reference missing entries in `skills_all.json` |")
    lines.append("")
    lines.append("## Gap-kind frequency (across the universe)")
    lines.append("")
    lines.append("How often each unmodeled-but-CB-relevant kind appears, and on how many heroes:")
    lines.append("")
    lines.append("| Kind | Heroes affected |")
    lines.append("|---|---|")
    for k in sorted(gap_kinds_by_hero, key=lambda x: -len(gap_kinds_by_hero[x])):
        lines.append(f"| `{k}` | {len(gap_kinds_by_hero[k])} |")
    lines.append("")

    # Heroes with unknown_kinds — top priority for investigation
    unk_heroes = [r for r in per_hero if r["coverage_tier"] == "unknown_kinds"]
    if unk_heroes:
        # Collect all unknown kinds with frequency
        unk_kind_counter: Counter = Counter()
        for r in unk_heroes:
            for k in r["unknown_kinds"]:
                unk_kind_counter[k] += 1
        lines.append("## Unknown effect kinds (need MODELED/NO_OP/GAP classification)")
        lines.append("")
        lines.append("| Kind | Heroes |")
        lines.append("|---|---|")
        for k, v in unk_kind_counter.most_common():
            lines.append(f"| `{k}` | {v} |")
        lines.append("")

    # Per-element coverage
    lines.append("## Coverage by element")
    lines.append("")
    by_el_tier: dict[str, Counter] = defaultdict(Counter)
    for r in per_hero:
        by_el_tier[r["element"]][r["coverage_tier"]] += 1
    lines.append("| Element | fully_modeled | has_gaps | unknown_kinds | no_skill_data |")
    lines.append("|---|---|---|---|---|")
    for el in sorted(by_el_tier):
        c = by_el_tier[el]
        lines.append(f"| {el} | {c['fully_modeled']} | {c['has_gaps']} | {c['unknown_kinds']} | {c['no_skill_data']} |")
    lines.append("")

    # Per-faction coverage (top 10)
    by_fac_tier: dict[str, Counter] = defaultdict(Counter)
    for r in per_hero:
        by_fac_tier[r["fraction"]][r["coverage_tier"]] += 1
    top_fac = sorted(by_fac_tier, key=lambda f: -sum(by_fac_tier[f].values()))[:12]
    lines.append("## Coverage by faction (top 12)")
    lines.append("")
    lines.append("| Faction | fully_modeled | has_gaps | unknown_kinds | no_skill_data |")
    lines.append("|---|---|---|---|---|")
    for f in top_fac:
        c = by_fac_tier[f]
        lines.append(f"| {f} | {c['fully_modeled']} | {c['has_gaps']} | {c['unknown_kinds']} | {c['no_skill_data']} |")
    lines.append("")

    # Sample heroes per tier
    lines.append("## Sample heroes per tier")
    lines.append("")
    for tier in ("fully_modeled", "has_gaps", "unknown_kinds", "no_skill_data"):
        sample = [r for r in per_hero if r["coverage_tier"] == tier][:15]
        if not sample:
            continue
        lines.append(f"### {tier} (first 15)")
        for r in sample:
            extras = []
            if r["gap_kinds"]:
                extras.append(f"gaps={r['gap_kinds']}")
            if r["unknown_kinds"]:
                extras.append(f"unknown={r['unknown_kinds']}")
            extras_s = (" " + " ".join(extras)) if extras else ""
            lines.append(f"- **{r['name']}** [{r['element']}/{r['rarity']}/{r['fraction']}]{extras_s}")
        lines.append("")

    lines.append("## Files")
    lines.append("")
    lines.append(f"- Summary: `{OUT_DOC.relative_to(ROOT).as_posix()}` (this file)")
    lines.append(f"- Per-hero detail: `{OUT_JSONL.relative_to(ROOT).as_posix()}` ({len(per_hero)} JSON lines)")
    lines.append("")
    lines.append("Re-generate after `tools/refresh_static_data.py`:")
    lines.append("```bash")
    lines.append("python3 tools/refresh_static_data.py --section hero_types skills_all skill_descriptions_all")
    lines.append("python3 tools/m5_hero_catalog.py")
    lines.append("```")

    OUT_DOC.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_DOC}  ({len(per_hero)} heroes catalogued)")
    print(f"Wrote {OUT_JSONL}")
    print()
    print("Coverage tiers:")
    for tier, n in coverage_counter.most_common():
        print(f"  {tier}: {n}")


if __name__ == "__main__":
    main()
