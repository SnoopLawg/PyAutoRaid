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
import sys
from collections import Counter, defaultdict
from pathlib import Path

# cb_profiles lives alongside this script (tools/). It carries the hand-curated
# `breaks_speed_tune` signal that seeds the per-hero tune-compatibility field.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cb_profiles  # noqa: E402

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

# ---------------------------------------------------------------------------
# M1 — channel-split + role-classification semantics (game-truth derived).
#
# The team scorer needs to know which damage CHANNEL an amplifier helps and
# which channel a damage engine fires through, because the channels are
# physically separate in the game:
#   * Decrease DEF / Weaken amplify HITS (+ Warmaster/Giant-Slayer procs and
#     %-MAX-HP "Bring It Down" hits) — they DO NOT touch DoTs.
#   * Poison Sensitivity amplifies POISON ticks ONLY.
#   * HP Burn is amplified by NOTHING.
# Mismatching an amplifier to a DoT is the single most common modelling error
# this milestone exists to prevent.
# ---------------------------------------------------------------------------

# Debuffs that amplify the HIT channel (and only the hit channel).
HIT_AMP_DEBUFFS = {"Decrease DEF", "Weaken"}
# DoT effect names whose co-placement on a skill makes an amp a "rider"
# (part of the DoT package) rather than a dedicated hit-amplifier role.
DOT_AMP_BLOCKERS = {"Poison", "HP Burn"}

# survival_currency: the survival mechanic a hero PROVIDES to the team, in
# keystone-priority order (a hero that gives several keeps the strongest).
SURVIVAL_PRIORITY = [
    ("unkillable",      ("team_buff:Unkillable",)),
    ("block_damage",    ("team_buff:Block Damage",)),
    ("shield",          ("team_buff:Shield",)),
    ("revive_on_death", ("team_buff:Revive On Death", "team_buff:Revive on Death",
                         "revive")),
    ("ally_protect",    ("team_buff:Ally Protection",)),
    ("heal_lifesteal",  ("team_buff:Continuous Heal", "heal")),
]
# Bracketed buff name(s) to look up for each survival currency's keystone
# (used to read the keystone skill's buff DURATION for the CD-vs-duration test).
SURVIVAL_BUFF_NAMES = {
    "unkillable":      ["Unkillable"],
    "block_damage":    ["Block Damage"],
    "shield":          ["Shield"],
    "revive_on_death": ["Revive On Death", "Revive on Death"],
    "ally_protect":    ["Ally Protection"],
    "heal_lifesteal":  ["Continuous Heal"],
}

_FOR_TURNS = re.compile(r"for (\d+) turn")
_N_TIMES = re.compile(r"attacks[^.]*?(\d+)\s+times", re.IGNORECASE)
_MAXHP_DMG = re.compile(r"(?:proportional to|equal to|based on)\s+([^.]{0,40}?max hp)",
                        re.IGNORECASE)

# A skill is a DAMAGING HIT when its text opens with the game's canonical attack
# clause ("Attacks 1 enemy", "Attacks all enemies", "Attacks 1 enemy 3 times",
# "Attacks at random", ...). DoT/utility application casts (Geomancer's
# "Fully depletes the target's Turn Meter", Teodor's "Increases the duration of
# all [Poison] debuffs") have NO such clause — they place effects without
# dealing ATK-scaled damage. This is the discriminator the amplifier-channel
# rider rule needs: a Dec-DEF/Weaken on a damaging hit is a real hit-amplifier;
# the same debuff on a pure DoT-application cast is just a rider on the package.
_ATTACK_CLAUSE = re.compile(r"\bAttacks\s+(?:\d+|all|an?\b|the\b|at\s+random)",
                            re.IGNORECASE)

# A genuine TEAM-WIDE extra turn (granted to allies, not just the caster) shifts
# the whole team's action order and breaks any fixed shared speed-tune. The
# game's self extra turns read "Grants an Extra Turn" (to this Champion); only an
# ally-targeted grant qualifies here.
_TEAM_EXTRA_TURN = re.compile(
    r"[Gg]rants?\s+an?\s+[Ee]xtra\s+[Tt]urn\s+to\s+"
    r"(?:all\s+allies|a\s+random\s+ally|each\s+ally|all\s+other\s+allies)")


def _is_attack(text: str) -> bool:
    return bool(_ATTACK_CLAUSE.search(text or ""))


def _buff_duration(text: str, names: list[str]):
    """Shortest 'for N turns' attached to any of the named buffs (or None)."""
    best = None
    for nm in names:
        idx = text.find("[" + nm + "]")
        if idx < 0:
            continue
        m = _FOR_TURNS.search(text, idx)
        if m:
            d = int(m.group(1))
            best = d if best is None else min(best, d)
    return best


def _is_multi_hit(text: str) -> bool:
    m = _N_TIMES.search(text or "")
    return bool(m and int(m.group(1)) >= 2)


def _hits_enemy_maxhp(text: str) -> bool:
    """True if the skill deals damage scaling off the ENEMY's MAX HP
    (the 'Bring It Down' channel) — excludes self-MAX-HP nukers."""
    tl = (text or "").lower()
    if "max hp" not in tl:
        return False
    for m in _MAXHP_DMG.finditer(tl):
        seg = m.group(1)
        if "champion" in seg or "their max hp" in seg:
            continue  # this Champion's own MAX HP — different engine
        if "enemy" in seg or "target" in seg:
            return True
    return False


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

    # Authoritative per-skill cooldowns (for keystone_needs_enabler: a survival
    # buff whose skill CD exceeds the buff's own duration can't self-sustain).
    cd_by_id: dict[int, int] = {}
    for sk in _unwrap(_load_json("skills_all.json")):
        if isinstance(sk, dict) and "Id" in sk:
            cd_by_id[int(sk["Id"])] = int(sk.get("Cooldown", 0) or 0)

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

        # M1 per-skill bookkeeping (channel-split + keystone CD/duration test).
        nonrider_hit_amp = False   # places Dec DEF / Weaken on a non-DoT skill
        multi_hit = False          # any "Attacks ... N times" (>=2) → WM/GS density
        enemy_maxhp_dmg = False    # damage scales off enemy MAX HP → bring_it_down
        skill_texts: dict[int, str] = {}

        for sid in sids:
            txt = _clean(sd.get(str(sid), ""))
            if not txt:
                continue
            skill_texts[sid] = txt
            sk_hit_amp = False
            sk_has_dot = False
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
                        if nm in HIT_AMP_DEBUFFS:
                            sk_hit_amp = True
                elif nm in DOT_NAMES:
                    provides.add(f"dot:{nm}")
                    dot_kinds.add(nm)
                    if nm in DOT_AMP_BLOCKERS:
                        sk_has_dot = True
            # A Dec-DEF/Weaken is a real HIT-CHANNEL amplifier when it lands on a
            # DAMAGING HIT (e.g. Venomage A2 "Attacks 1 enemy" + Dec DEF, Fayne
            # A3, Ninja A1). It is only a "rider" — part of a DoT package, not a
            # dedicated amplifier role — when it co-places a DoT on a cast that is
            # PRIMARILY a DoT/utility application with no direct damage (e.g.
            # Geomancer's "Fully depletes Turn Meter" + HP Burn + Weaken, Teodor's
            # duration-extension cast + Weaken). The old rule keyed only on
            # DoT co-placement and so wrongly suppressed amplifiers on damaging
            # hits whose text merely *references* [Poison] as a condition.
            sk_is_attack = _is_attack(txt)
            if sk_hit_amp and (sk_is_attack or not sk_has_dot):
                nonrider_hit_amp = True
            if _is_multi_hit(txt):
                multi_hit = True
            if _hits_enemy_maxhp(txt):
                enemy_maxhp_dmg = True

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

        # ------------------------------------------------------------------
        # M1 derived semantics (channel-split + survival/enabler taxonomy).
        # ------------------------------------------------------------------

        # amplifier_channel — which damage channel this hero amplifies for the
        # team. Dec-DEF/Weaken (non-rider) -> hit; Poison Sensitivity -> poison;
        # otherwise none (incl. HP-burn dealers whose only "amp" is a DoT rider).
        if nonrider_hit_amp:
            amplifier_channel = "hit"
        elif "enables:poison" in provides:
            amplifier_channel = "poison"
        else:
            amplifier_channel = "none"

        # tune_compat — how compatible the kit is with a FIXED shared speed-tune
        # (the basis of every CB Unkillable/Block-Damage stall). Base signal is
        # cb_profiles' hand-curated `breaks_speed_tune`; refined by provide tags:
        #   * hard_breaker — provides a FLAT TEAM [Increase SPD] buff (shifts
        #     everyone's SPD mid-fight, so NO fixed tune holds) or a team-wide
        #     extra-turn (re-orders the whole team's cadence). e.g. Teodor.
        #   * manageable — breaks_speed_tune is True but only via a CONDITIONAL /
        #     self TM effect a tune can be built AROUND (e.g. Ninja's TM-on-burn
        #     passive — the MEN tune is built around it).
        #   * ok — no tune-breaking behaviour.
        breaks_tune = cb_profiles.resolve(name).breaks_speed_tune
        team_inc_spd = "team_buff:Increase SPD" in provides
        team_extra_turn = any(_TEAM_EXTRA_TURN.search(t)
                              for t in skill_texts.values())
        if team_inc_spd or team_extra_turn:
            tune_compat = "hard_breaker"
        elif breaks_tune:
            tune_compat = "manageable"
        else:
            tune_compat = "ok"

        # engine_channel — which damage channel(s) this hero's own damage flows
        # through (multi allowed). DoT channels come straight from the DoTs the
        # kit places; hit / wm_gs apply to direct-damage attackers.
        engine_channel: list[str] = []
        if "dot:Poison" in provides:
            engine_channel.append("poison")
        if "dot:HP Burn" in provides:
            engine_channel.append("hp_burn")
        if enemy_maxhp_dmg:
            engine_channel.append("bring_it_down")
        if is_attacker:
            engine_channel.append("hit")
            if multi_hit:  # many small hits => Warmaster/Giant-Slayer density
                engine_channel.append("wm_gs")

        # survival_currency — the strongest survival mechanic this hero PROVIDES
        # to the team (keystone priority); absent if it provides none.
        survival_currency = None
        for currency, tags in SURVIVAL_PRIORITY:
            if any(t in provides for t in tags):
                survival_currency = currency
                break

        # enabler — does the kit SUSTAIN a survival keystone (reduce ally
        # cooldowns or extend ally buff lifetimes)? absent if neither.
        if "cooldown_reduction" in provides:
            enabler = "cooldown_reduction"
        elif "buff_extension" in provides:
            enabler = "buff_extension"
        else:
            enabler = None

        # keystone_needs_enabler — a survival provider whose keystone buff's
        # COOLDOWN exceeds its DURATION can't self-sustain (e.g. Maneater
        # Unkillable 2-turn buff on a 7-turn cooldown) and needs an enabler.
        keystone_needs_enabler = False
        if survival_currency:
            buff_names = SURVIVAL_BUFF_NAMES.get(survival_currency, [])
            best_cd = None  # the dedicated keystone = highest-CD placement skill
            best_dur = None
            for sid, txt in skill_texts.items():
                if not any(("[" + bn + "]") in txt for bn in buff_names):
                    continue
                cd = cd_by_id.get(sid, 0)
                if best_cd is None or cd > best_cd:
                    best_cd = cd
                    best_dur = _buff_duration(txt, buff_names)
            if best_cd and best_dur is not None and best_cd > best_dur:
                keystone_needs_enabler = True

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
            "amplifier_channel": amplifier_channel,
            "tune_compat": tune_compat,
            "engine_channel": engine_channel,
            "survival_currency": survival_currency,
            "enabler": enabler,
            "keystone_needs_enabler": keystone_needs_enabler,
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
