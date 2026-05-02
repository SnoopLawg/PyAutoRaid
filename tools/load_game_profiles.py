"""
Load game-accurate hero skill profiles from hero_profiles_game.json.

Replaces the manually-coded SKILL_DATA and SKILL_EFFECTS dicts in cb_sim.py
with data extracted directly from the live game via BepInEx mod API.

Source: hero_profiles_game.json (137 heroes, exact game data)
Secondary: skills_db.json (for book cooldown reductions)
"""

import json
import re
from pathlib import Path

import effect_engine as _ee  # local module — same dir as this file

# StatusEffectTypeId -> sim debuff/buff name
SE_TO_SIM = {
    80: "poison_5pct",
    81: "poison_2pct",
    470: "hp_burn",
    151: "def_down",
    152: "def_down_30",
    131: "dec_atk",
    132: "dec_atk_25",
    350: "weaken",
    351: "weaken_15",
    500: "poison_sensitivity",
    501: "poison_sensitivity_50",
    50: "counterattack",
    60: "block_damage",
    100: "block_debuffs",
    310: "ally_protect",
    311: "ally_protect_25",
    320: "unkillable",
    121: "atk_up",
    122: "atk_up_25",
    141: "inc_def",
    142: "inc_def_30",
    161: "inc_spd",
    171: "dec_spd",
    90: "cont_heal_75",
    91: "cont_heal_15",
    460: "leech",
    511: "strengthen",
    510: "strengthen_15",
    360: "block_revive",
    10: "stun",
    20: "freeze",
    241: "inc_cr_30",
    261: "inc_cd_30",
    280: "shield",
    300: "revive_on_death",
    160: "inc_spd_15",
    70: "heal_reduction",
    71: "heal_reduction_50",
    481: "perfect_veil",
}

# Which SE types are team buffs (applied to allies) vs debuffs (applied to enemies)
BUFF_SES = {
    "counterattack", "block_damage", "block_debuffs", "ally_protect",
    "ally_protect_25", "unkillable", "atk_up", "atk_up_25", "inc_def",
    "inc_def_30", "inc_spd", "inc_spd_15", "cont_heal_75", "cont_heal_15", "strengthen",
    "strengthen_15", "inc_cr_30", "inc_cd_30", "shield", "revive_on_death",
}

# SE types that go on the CB debuff bar
DEBUFF_SES = {
    "poison_5pct", "poison_2pct", "hp_burn", "def_down", "def_down_30",
    "dec_atk", "dec_atk_25", "weaken", "weaken_15", "poison_sensitivity",
    "poison_sensitivity_50", "leech", "dec_spd", "block_revive",
    "stun", "freeze", "heal_reduction", "heal_reduction_50",
}


def _eff(effect_type, **params):
    """Helper to build effect dicts matching cb_sim's expected format."""
    return {"effect_type": effect_type, "params": params}


def _classify_extend_debuff_for_skill(skill_id: int) -> dict | None:
    """Look up a skill's IncreaseDebuffLifetime classification.

    Returns the first (skill_id is one skill) IncreaseDebuffLifetime
    classification from `effect_engine`, or None if the skill has none.
    """
    if not skill_id:
        return None
    for ge in _ee.normalize_skill_effects(skill_id):
        c = _ee.classify_extend_debuff(ge)
        if c is not None:
            return c
    return None


def _classify_activate_dots_for_skill(skill_id: int, eff_index: int = 0) -> dict | None:
    """Look up a skill's ForceStatusEffectTick classification.

    Multi-hit skills (Ninja A2) have multiple kind=9002 effects — but
    they all have the same routing. This helper just returns one
    classification; the caller emits per occurrence.
    """
    if not skill_id:
        return None
    for ge in _ee.normalize_skill_effects(skill_id):
        c = _ee.classify_activate_dots(ge)
        if c is not None:
            return c
    return None


# Regex for extend-chance parsing from localized text. Matches both
# "Each hit has a 15% chance of increasing the duration of [HP Burn]"
# and "Has a 35% chance to extend the duration of any [HP Burn]".
_RE_EXTEND_CHANCE = re.compile(
    r'(\d+)% chance (?:to extend|of (?:increasing|extending)) the duration',
    re.IGNORECASE,
)

# "Each hit has a 35% chance of activating up to two [Poison] debuffs"
# "has a 50% chance of activating any [HP Burn]"
_RE_ACTIVATE_CHANCE = re.compile(
    r'(\d+)% chance of activating',
    re.IGNORECASE,
)

# "Has a 75% chance of placing a [HP Burn] debuff"
# "Has an 80% chance of placing a 25% [Weaken] debuff"
_RE_PLACE_CHANCE = re.compile(
    r'(\d+)% chance of placing',
    re.IGNORECASE,
)


def _parse_chance_from_desc(desc: str, regex: re.Pattern,
                            level_bonus_pct: float = 0.0) -> float:
    """Generic chance extractor: matches `regex`, returns base+book or 1.0."""
    if not desc:
        return 1.0
    m = regex.search(desc)
    if not m:
        return 1.0
    try:
        return min(1.0, int(m.group(1)) / 100.0 + level_bonus_pct)
    except ValueError:
        return 1.0


def _parse_extend_chance_from_desc(desc: str, level_bonus_pct: float = 0.0) -> float:
    """Return base extend chance + EffectChance book bonus, or 1.0 if not found."""
    return _parse_chance_from_desc(desc, _RE_EXTEND_CHANCE, level_bonus_pct)


_DESC_CACHE: dict[str, dict] | None = None


def _load_descriptions() -> dict[str, dict]:
    """Lazy-load skill_descriptions.json, return {hero_name: {A1/A2/.../skill_dict}}."""
    global _DESC_CACHE
    if _DESC_CACHE is not None:
        return _DESC_CACHE
    p = Path(__file__).parent.parent / "skill_descriptions.json"
    if not p.exists():
        _DESC_CACHE = {}
        return _DESC_CACHE
    _DESC_CACHE = json.loads(p.read_text(encoding="utf-8"))
    return _DESC_CACHE


def _sum_effect_chance_book_bonus(skill_dict: dict) -> float:
    """Sum 'EffectChance' SkillLevelBonuses (the books that boost chance).

    Reads from the static `skills_d4` / `skills_all` cache via effect_engine.
    Returns 0.0 if the skill is not in the static export.
    """
    sid = skill_dict.get('id', 0) or 0
    s = _ee.skills_by_id().get(sid)
    if not isinstance(s, dict):
        return 0.0
    bonuses = s.get('SkillLevelBonuses') or []
    total = 0.0
    for b in bonuses:
        if not isinstance(b, dict):
            continue
        if b.get('SkillBonusType') == 'EffectChance':
            try:
                total += float(b.get('Value', 0) or 0)
            except (TypeError, ValueError):
                pass
    return total


def _hero_skill_desc(hero_name: str, label: str) -> str:
    """Return the localized description text for a hero/label, or ''."""
    descs = _load_descriptions()
    hero = descs.get(hero_name)
    if not isinstance(hero, dict):
        return ""
    sk_desc = hero.get(label)
    if not isinstance(sk_desc, dict):
        return ""
    return sk_desc.get('desc', '') or ""


def _resolve_extend_chance(hero_name: str, label: str, skill_dict: dict) -> float:
    """Get extend-debuffs chance from description text + book bonuses."""
    desc_text = _hero_skill_desc(hero_name, label)
    book_bonus = _sum_effect_chance_book_bonus(skill_dict)
    return _parse_extend_chance_from_desc(desc_text, level_bonus_pct=book_bonus)


def _resolve_activate_chance(hero_name: str, label: str, skill_dict: dict) -> float:
    """Get activate-DoT chance from description text + book bonuses.

    For "Each hit has a 35% chance of activating up to two [Poison]"
    plus EffectChance books summing to 0.12 → 0.47. Returns 1.0 when
    the description has no per-hit chance phrase (unconditional).
    """
    desc_text = _hero_skill_desc(hero_name, label)
    book_bonus = _sum_effect_chance_book_bonus(skill_dict)
    return _parse_chance_from_desc(desc_text, _RE_ACTIVATE_CHANCE,
                                   level_bonus_pct=book_bonus)


def _resolve_apply_chance(hero_name: str, label: str, skill_dict: dict) -> float:
    """Get apply-debuff/apply-buff chance from description.

    Returns 1.0 (always applies) when no "X% chance of placing" phrase
    matches — covers guaranteed effects. Note: this catches the FIRST
    chance in the description; multi-effect skills that use different
    chances per effect (e.g. "75% chance of A, 80% chance of B") will
    use the first match for all subsequent debuffs. That's a known
    limitation — caught by the regression suite if it bites the sim.
    """
    if not hero_name:
        return 1.0
    desc_text = _hero_skill_desc(hero_name, label)
    book_bonus = _sum_effect_chance_book_bonus(skill_dict)
    return _parse_chance_from_desc(desc_text, _RE_PLACE_CHANCE,
                                   level_bonus_pct=book_bonus)


def _condition_fires_vs_cb_boss(condition: str) -> bool:
    """Return False when the effect's gating condition can't trigger in CB.

    CB-immutable conditions:
      - kill-only ("killedEnemiesCount", "deathOf*"): boss has 1.17B HP,
        never killed by any single hero — these effects are no-ops.
      - "!targetIsBoss": explicitly NOT vs boss.
    Everything else is treated as eligible; the per-tick state of
    debuffs / HP / etc. is the sim's concern, not ours here.
    """
    cond = (condition or "").strip()
    if not cond:
        return True
    low = cond.lower()
    if "killed" in low or "deathof" in low or "death_of" in low:
        return False
    if "!targetisboss" in low.replace(" ", ""):
        return False
    return True


def _condition_modifies_chance(condition: str, hero_cr: float) -> float:
    """Return a chance multiplier for conditional effects that gate on
    hit-roll outcomes (e.g. `isCritical` only fires when the attack
    crits). Returns 1.0 when no such condition is detected.

    Maneater A1 places DEC ATK 50% only on crit hits. With his CR ~32%,
    the effective debuff land rate is 0.32 × 1.0 = 0.32 (not 1.0).
    """
    cond = (condition or "").strip().lower()
    if not cond:
        return 1.0
    if "iscritical" in cond:
        # Skill places its debuff only when the attack crits.
        return max(0.0, min(1.0, hero_cr))
    return 1.0


def _supplement_skill_from_static(skill_id: int, label: str, hero_eff: dict,
                                   hero_sd: dict, hero_name: str = "") -> None:
    """Merge effects the legacy parser missed, using static data via effect_engine.

    `hero_profiles_game.json` (the legacy effect source) sometimes drops
    `status_effects[]` entries — costing the sim the relevant
    debuff/buff. Static `ApplyStatusEffectParams.StatusEffectInfos`
    (depth=5) has the truth: TypeId + Duration.

    This function adds missing entries idempotently — won't duplicate
    what the legacy pass already produced. Routing is by SE TypeId
    via `SE_TO_SIM` + buff/debuff bucket, so adding new heroes is
    a no-op (their data flows through this same path).
    """
    if not skill_id or label not in hero_sd:
        return
    effs = hero_eff.setdefault(label, [])
    sd_entry = hero_sd[label]
    team_buffs = list(sd_entry.get("team_buffs") or [])
    team_buff_names = {b[0] for b in team_buffs if isinstance(b, tuple)}
    existing_debuff_names = {
        e.get("params", {}).get("debuff")
        for e in effs
        if e.get("effect_type") == "debuff"
    }
    # Collect DefenceModifier from Damage effects that fire vs the CB
    # boss. Conditions encode "targetIsBoss" for boss-gated damage and
    # "!targetIsBoss" for the inverse — we take the MIN (most negative)
    # def_modifier across boss-applicable effects to set ignore_def.
    boss_def_modifier = 0.0
    # Per-skill chance lookup from description text. Already includes
    # EffectChance book bonus — don't add it again at the use site.
    desc_chance = _resolve_apply_chance(hero_name, label, {"id": skill_id})
    for ge in _ee.normalize_skill_effects(skill_id):
        if not _condition_fires_vs_cb_boss(ge.condition):
            continue
        if ge.kind_id in ("ApplyBuff", "ApplyOrProlongBuff"):
            for tid, dur in ge.applied_status_effects:
                sim_name = SE_TO_SIM.get(tid)
                if not sim_name or sim_name not in BUFF_SES or dur <= 0:
                    continue
                if sim_name in team_buff_names:
                    continue
                team_buffs.append((sim_name, dur))
                team_buff_names.add(sim_name)
        elif ge.kind_id in ("ApplyDebuff", "ApplyOrProlongDebuff"):
            for tid, dur in ge.applied_status_effects:
                sim_name = SE_TO_SIM.get(tid)
                if not sim_name or sim_name not in DEBUFF_SES or dur <= 0:
                    continue
                if sim_name in existing_debuff_names:
                    continue
                # Chance: `desc_chance` already includes book bonus.
                # Self-targeted debuffs (rare — e.g. Sicia A3 self-burn)
                # are unconditional regardless of the description's
                # "X% chance" clause (which gates only the enemy effect).
                self_targeted = ge.target_type in (
                    "Producer", "RelationProducer", "Owner",
                )
                effs.append(_eff("debuff", debuff=sim_name, duration=dur,
                                 chance=1.0 if self_targeted else desc_chance))
                existing_debuff_names.add(sim_name)
        elif ge.kind_id == "ReduceCooldown":
            # ReduceCooldown affects the producer's *next* skill (A3 etc.)
            # by 1 turn per Count. The classic case is Geomancer A2 ->
            # A3 cooldown drop, but Geomancer's is kill-gated and
            # thus already filtered above by _condition_fires_vs_cb_boss.
            target = "A3" if label == "A2" else "A2"
            if not any(e.get("effect_type") == "cd_reduce_skill"
                       for e in effs):
                effs.append(_eff("cd_reduce_skill",
                                  target_skill=target, turns=ge.count or 1))
        elif ge.kind_id == "Damage":
            if ge.damage_def_modifier < boss_def_modifier:
                boss_def_modifier = ge.damage_def_modifier
    if boss_def_modifier < 0:
        # ignore_def is stored as positive fraction (0.5 = "ignore 50%")
        existing = sd_entry.get("ignore_def", 0.0)
        sd_entry["ignore_def"] = max(existing, -boss_def_modifier)
    sd_entry["team_buffs"] = team_buffs


def _detect_compound_extend_buff(skill_id: int) -> dict | None:
    """Detect the extend-buffs+shrink-debuffs+heal compound pattern.

    Returns kwargs for _eff("extend_buffs", **kwargs) when the skill has
    ALL of: IncreaseBuffLifetime, ReduceDebuffLifetime, and a Heal whose
    formula references totalIncreased/totalDecreased counts. Otherwise
    None (caller emits a plain extend_buffs).

    Demytha A2 is the canonical case but the detection is structural,
    not name-based — any future hero with this kit shape Just Works.
    """
    if not skill_id:
        return None
    effects = _ee.normalize_skill_effects(skill_id)
    has_extend = any(e.kind_id == _ee.KIND_INCREASE_BUFF_LIFETIME for e in effects)
    has_shrink = any(e.kind_id == _ee.KIND_REDUCE_DEBUFF_LIFETIME for e in effects)
    if not (has_extend and has_shrink):
        return None
    heal_effect = next(
        (e for e in effects if e.kind_id == "Heal"
         and "totalIncreasedTurnsCount" in (e.multiplier_formula or "")),
        None,
    )
    if heal_effect is None:
        return None
    # Parse "(0.025*TRG_HP)+((0.025*TRG_HP)*(totalIncreased+totalDecreased))"
    f = heal_effect.multiplier_formula
    base = re.search(r'\(([\d.]+)\*TRG_HP\)\s*\+\s*\(\(([\d.]+)\*TRG_HP\)', f)
    if not base:
        return None
    try:
        return {
            "turns": 1,
            "shrink_debuffs": 1,
            "heal_pct": float(base.group(1)),
            "heal_per_change_pct": float(base.group(2)),
        }
    except ValueError:
        return None


def _get_book_cd_reductions(skills_db_path):
    """Get cooldown reductions from skill books (level_bonuses type=3).

    The mod's /skill-data endpoint returns the skill's BASE (unbooked) CD
    along with a list of `level_bonuses`. Each type=3 bonus represents one
    skill-book upgrade that subtracts 1 turn from the cooldown. For
    Maneater's Ancient Blood:
        cooldown: 7 (base)  + level_bonuses: [type3, type3]  → booked CD = 5
    That 5 matches the in-game display with "Lvl.2 -1, Lvl.3 -1".
    """
    reductions = {}  # {skill_type_id: total_cd_reduction}
    try:
        with open(skills_db_path) as f:
            db = json.load(f)
        for name, skills in db.items():
            if isinstance(skills, list):
                for sk in skills:
                    sid = sk.get('skill_type_id', 0)
                    cd_red = sum(1 for b in sk.get('level_bonuses', []) if b.get('type') == 3)
                    if cd_red > 0:
                        reductions[sid] = cd_red
    except Exception:
        pass
    return reductions


def load_profiles():
    """
    Load hero_profiles_game.json and produce SKILL_DATA, SKILL_EFFECTS, and
    PASSIVE_DATA dicts compatible with cb_sim.py.

    Returns: (skill_data, skill_effects, passive_data)
    """
    base = Path(__file__).parent.parent
    profiles_path = base / "hero_profiles_game.json"
    skills_db_path = base / "skills_db.json"

    with open(profiles_path) as f:
        profiles = json.load(f)

    # Get book CD reductions
    cd_reductions = _get_book_cd_reductions(skills_db_path)

    skill_data = {}    # {hero_name: {"A1": {...}, "A2": {...}, "A3": {...}}}
    skill_effects = {} # {hero_name: {"A1": [...], "A2": [...], "A3": [...]}}
    passive_data = {}  # {hero_name: {flag: value, ...}}

    for name, hero in profiles.items():
        skills = hero.get('skills', [])

        # Separate skills by type
        a1_skills = [s for s in skills if s.get('type') == 'A1']
        active_skills = sorted(
            [s for s in skills if s.get('type') == 'active'],
            key=lambda s: s.get('cooldown', 99)
        )
        # If more than 2 actives, prefer ones with damage effects over utility-only
        if len(active_skills) > 2:
            def has_damage(sk):
                return any(e.get('kind') == 6000 or e.get('tag') == 'damage' for e in sk.get('effects', []))
            dmg_skills = [s for s in active_skills if has_damage(s)]
            nodmg_skills = [s for s in active_skills if not has_damage(s)]
            # Take up to 2 damage skills (sorted by CD), then fill with non-damage
            active_skills = (dmg_skills[:2] + nodmg_skills)[:3]
        passive_skills = [s for s in skills if s.get('type') == 'passive']

        # Assign labels: A1, A2, A3
        labeled = {}
        if a1_skills:
            labeled['A1'] = a1_skills[0]
        if len(active_skills) >= 1:
            labeled['A2'] = active_skills[0]
        if len(active_skills) >= 2:
            labeled['A3'] = active_skills[1]
        # Some heroes have 3+ active skills — take the 3rd as A4 (rare, usually ignore)

        hero_sd = {}
        hero_eff = {}

        for label, sk in labeled.items():
            sid = sk.get('id', 0)
            base_cd = sk.get('cooldown', 0)
            booked_cd = base_cd - cd_reductions.get(sid, 0)
            if booked_cd < 0:
                booked_cd = 0

            # Extract damage info
            mult = sk.get('mult', 0) or 0
            stat = sk.get('stat', 'ATK') or 'ATK'
            hits = sk.get('hits', 1) or 1

            # If mult is 0/None, try to parse from damage effect formulas
            if mult == 0:
                for eff in sk.get('effects', []):
                    if eff.get('kind') == 6000 or eff.get('tag') == 'damage':
                        f = eff.get('formula', '')
                        if not f:
                            continue
                        # Parse various formula patterns:
                        #   "3.9*ATK" -> mult=3.9, stat=ATK
                        #   "DEF*1.5" -> mult=1.5, stat=DEF
                        #   "ATK" -> mult=1.0, stat=ATK
                        #   "0.2*HP" -> mult=0.2, stat=HP
                        #   "DEF*6" -> mult=6, stat=DEF
                        m = re.match(r'^([\d.]+)\*(ATK|DEF|HP)', f)
                        if m:
                            mult = float(m.group(1))
                            stat = m.group(2)
                            break
                        m = re.match(r'^(ATK|DEF|HP)\*([\d.]+)', f)
                        if m:
                            stat = m.group(1)
                            mult = float(m.group(2))
                            break
                        m = re.match(r'^(ATK|DEF|HP)$', f)
                        if m:
                            mult = 1.0
                            stat = m.group(1)
                            break
                        # HP-scaling: "0.2*HP" or "HP*0.2"
                        m = re.match(r'^([\d.]+)\*HP', f)
                        if m:
                            mult = float(m.group(1))
                            stat = 'HP'
                            break
                        # Speed-scaling: "ATK*(0.45*SPD/100)" or "ATK*(1.5+SPD/100)"
                        # Approximate as ATK-based with estimated multiplier
                        m = re.match(r'^ATK\*\(([\d.]+)\*SPD/100\)', f)
                        if m:
                            # At ~200 SPD: mult = coeff * 200/100 = coeff * 2
                            mult = float(m.group(1)) * 2.0
                            stat = 'ATK'
                            break
                        m = re.match(r'^ATK\*\(([\d.]+)\+SPD/100\)', f)
                        if m:
                            # At ~200 SPD: mult = base + 200/100 = base + 2
                            mult = float(m.group(1)) + 2.0
                            stat = 'ATK'
                            break

            # For multi-damage skills, sum multipliers. Damage effects
            # appear with EITHER tag='damage' OR kind=6000 in the game data;
            # earlier this filter only matched tag, so multi-hit skills like
            # Ninja A2 (3 separate kind=6000 entries each "2*ATK") were
            # collapsed to hits=1 — costing ~5M of his real damage.
            dmg_effects = [e for e in sk.get('effects', [])
                           if e.get('tag') == 'damage' or e.get('kind') == 6000]
            extra_dmg = [e for e in sk.get('effects', []) if e.get('tag') == 'extra_damage']

            # Fix hit count: use max of count field on damage or number of damage effects
            actual_hits = max(
                sk.get('hits', 1),
                max((e.get('count', 1) for e in dmg_effects), default=1),
                len(dmg_effects)
            )
            hits = actual_hits

            if len(dmg_effects) > 1 and mult > 0:
                # Multiple damage effects = multi-hit (e.g., Ninja A2: 3x 2*ATK)
                total_mult = 0
                for d in dmg_effects:
                    f = d.get('formula', '')
                    if '*ATK' in f:
                        try: total_mult += float(f.split('*ATK')[0])
                        except: pass
                    elif '*DEF' in f:
                        try: total_mult += float(f.split('*DEF')[0])
                        except: pass
                    elif '*HP' in f:
                        try: total_mult += float(f.split('*HP')[0])
                        except: pass
                if total_mult > 0:
                    mult = total_mult
            # Add extra damage
            for ed in extra_dmg:
                f = ed.get('formula', '')
                if '*ATK' in f:
                    try: mult += float(f.split('*ATK')[0])
                    except: pass
                elif '*DEF' in f:
                    try: mult += float(f.split('*DEF')[0])
                    except: pass

            # Extract team buffs and self TM fill
            team_buffs = []
            team_tm_fill = 0.0
            self_tm_fill = 0.0
            grants_extra_turn = False
            ignore_def_pct = 0.0
            cb_tm_drain_pct = 0.0

            effects_list = []

            for eff in sk.get('effects', []):
                kind = eff.get('kind', 0)
                count = eff.get('count', 1)
                formula = eff.get('formula', '')
                ses = eff.get('status_effects', [])

                # Buff placement (kind=4000) — team buffs
                if kind == 4000:
                    for se in ses:
                        se_type = se.get('type', 0)
                        se_name = SE_TO_SIM.get(se_type)
                        dur = se.get('duration', 0)
                        if se_name and se_name in BUFF_SES and dur > 0:
                            team_buffs.append((se_name, dur))

                # Debuff placement (kind=5000)
                elif kind == 5000:
                    for se in ses:
                        se_type = se.get('type', 0)
                        se_name = SE_TO_SIM.get(se_type)
                        dur = se.get('duration', 0)
                        chance = se.get('chance', 100) / 100.0
                        if se_name and se_name in DEBUFF_SES and dur > 0:
                            for _ in range(count):
                                effects_list.append(_eff("debuff",
                                    debuff=se_name, duration=dur, chance=chance))

                # TM boost (kind=4001) — fixed-fraction self/team fill,
                # e.g. "0.15*MAX_STAMINA" (Ninja A1: +15% TM on cast).
                # CHANGED_STAMINA-style formulas pair with kind=5001 drain;
                # against the CB boss those drains are no-ops AND the caster
                # does not receive a fill (verified 2026-04-29 via per-tick
                # TM telemetry). So CHANGED_STAMINA is intentionally ignored
                # here.
                elif kind == 4001 and formula:
                    if "MAX_STAMINA" in formula:
                        m = re.match(r'([\d.]+)\*MAX_STAMINA', formula)
                        if m:
                            val = float(m.group(1))
                            if label == 'A1':
                                self_tm_fill = val
                            else:
                                team_tm_fill = val

                # Extra turn (kind=4007)
                elif kind == 4007:
                    grants_extra_turn = True

                # HP Burn spread/activation (kind=5002) — exact mechanic unclear.
                # Used by 44 heroes. NOT necessarily "place HP Burn" — may be
                # "spread existing burn" or "activate burn damage". Needs real
                # game testing per hero before enabling. Skipped for now.
                # elif kind == 5002:
                #     effects_list.append(_eff("debuff", debuff="hp_burn", duration=2, chance=1.0))

                # Extend debuffs (kind=5008 = IncreaseDebuffLifetime).
                # Family routing comes from `effect_engine` reading
                # `ChangeEffectLifetimeParams.EffectTypeIds` — no skill_id
                # branching. Per-hit vs per-target distinction stays here:
                # multi-hit damage skills extend per-hit (verified for
                # Sicia A1 / Artak A1). Chance comes from description
                # text + book bonuses (static Effect.Chance unreliable).
                elif kind == 5008:
                    per_hit = (actual_hits > 1)
                    classified = _classify_extend_debuff_for_skill(sk.get('id', 0))
                    chance = _resolve_extend_chance(name, label, sk)
                    sim_type = (classified["sim_type"] if classified
                                else "extend_debuffs")
                    turns = classified["turns"] if classified else 1
                    effects_list.append(_eff(
                        sim_type, turns=turns, per_hit=per_hit, chance=chance,
                    ))

                # Extend buffs (kind=4011 = IncreaseBuffLifetime).
                # When the same skill ALSO has ReduceDebuffLifetime AND a
                # Heal effect with the totalIncreased+totalDecreased
                # formula, it's a compound extend+shrink+heal — Demytha
                # A2's Light of the Deep is the canonical case but the
                # mechanic is data-driven, not hero-specific.
                elif kind == 4011:
                    compound = _detect_compound_extend_buff(sk.get('id', 0))
                    if compound is not None:
                        effects_list.append(_eff("extend_buffs", **compound))
                    else:
                        effects_list.append(_eff("extend_buffs", turns=1))

                # Activate DoTs (kind=9002 = ForceStatusEffectTick).
                # Family routing comes from `effect_engine` reading
                # `ForceTickParams.EffectTypeIds`:
                #   ['Burn']            → activate_hp_burns
                #   ['ContinuousDamage*'] → activate_poisons (cap from EffectCount)
                #   ['Burn','Continuous*'] → activate_dots (all)
                # Game data emits one kind=9002 per hit on multi-hit
                # damage skills (Ninja A2 has 3) — emit one effect each
                # so the sim activates per hit (verified 2026-04 against
                # real Ninja burn-attributed damage).
                elif kind == 9002:
                    classified = _classify_activate_dots_for_skill(sk.get('id', 0))
                    if classified is not None:
                        params: dict = {}
                        if classified.get("max_count"):
                            params["max_count"] = classified["max_count"]
                            params["chance"] = _resolve_activate_chance(name, label, sk)
                        effects_list.append(_eff(classified["sim_type"], **params))
                    # Effects we couldn't classify: skip (unknown mechanic)

                # Detonate poisons (kind=5018)
                elif kind == 5018:
                    effects_list.append(_eff("detonate_poisons"))

                # Ally attack (kind=4006)
                elif kind == 4006:
                    effects_list.append(_eff("ally_attack", count=count or 3))

                # Ignore DEF modifier (kind=7001)
                elif kind == 7001 and formula:
                    m = re.match(r'-([\d.]+)', formula)
                    if m:
                        ignore_def_pct = float(m.group(1))

                # TM reduce (kind=5001) — Syphon-style drain target stamina.
                # CB boss is immune (TM doesn't drop) AND caster does NOT
                # gain "what would have been drained" (verified 2026-04-29
                # via per-tick TM log: Maneater post-A2 TM matches pure
                # natural accumulation, no drain bonus). Recorded for
                # non-CB use only.
                elif kind == 5001 and formula:
                    if "MAX_STAMINA" in formula or "TRG_STAMINA" in formula:
                        cb_tm_drain_pct = 1.0
                    else:
                        m = re.match(r'([\d.]+)', formula)
                        if m:
                            try:
                                cb_tm_drain_pct = max(cb_tm_drain_pct, float(m.group(1)))
                            except Exception:
                                pass
                # Cleanse (kind=4010) — relevant for passive only
                # Strip buff (kind=5003) — not relevant for CB
                # Reduce CD (kind=4009) — handle per hero if needed
                # Heal (kind=1000) — handled in passive detection

            sd_entry = {
                "mult": mult,
                "stat": stat,
                "hits": hits,
                "cd": booked_cd,
                "team_buffs": team_buffs,
                "team_tm_fill": team_tm_fill,
                "self_tm_fill": self_tm_fill,
                "grants_extra_turn": grants_extra_turn,
            }
            if ignore_def_pct > 0:
                sd_entry["ignore_def"] = ignore_def_pct
            if cb_tm_drain_pct > 0:
                sd_entry["cb_tm_drain_pct"] = cb_tm_drain_pct

            hero_sd[label] = sd_entry
            hero_eff[label] = effects_list

        # =====================================================================
        # Static-data supplementation pass: for every labeled skill, fill
        # in any ApplyBuff/ApplyDebuff/ReduceCooldown/Damage-DefMod that
        # the legacy effect array missed. This pass is data-driven via
        # `effect_engine` (depth=5 SEI) — no per-hero conditionals.
        # Adding a new hero is a no-op (their skills flow through here).
        # =====================================================================
        for label_, sk_ in labeled.items():
            _supplement_skill_from_static(sk_.get('id', 0), label_,
                                           hero_eff, hero_sd,
                                           hero_name=name)

        if hero_sd:
            skill_data[name] = hero_sd
        if hero_eff:
            skill_effects[name] = hero_eff

        # Process passives
        p_data = {}
        for sk in passive_skills:
            for eff in sk.get('effects', []):
                kind = eff.get('kind', 0)
                formula = eff.get('formula', '')
                ses = eff.get('status_effects', [])

                # Passive ally protect (kind=4018 or kind=4010 passive)
                if kind == 4018 or kind == 4010:
                    p_data['ally_protect'] = True

                # Passive damage reduction (kind=7004 with -X*DMG_MUL).
                # Two flavors:
                #   - "relationTargetIsAlly" cond: TEAM-wide reduction
                #     (Geomancer Stoneguard -15% on all allies)
                #   - "ownerIsRelatedEffectTarget" cond: SELF-only (only
                #     the owner gets it, e.g. Geomancer -30% on self when
                #     he himself is the damage target)
                #   - no cond: SELF-only (e.g. Cardiel -20%)
                # `dmg_reduction` (per-hero) gets the higher of self+team
                # values for that hero; `team_dmg_reduction` propagates
                # the team-wide value to all teammates at sim init.
                if kind == 7004 and formula:
                    m = re.match(r'^-([\d.]+)\*DMG_MUL', formula)
                    if m:
                        val = float(m.group(1))
                        cond = (eff.get('condition') or '').lower()
                        if 'relationtargetisally' in cond:
                            p_data['team_dmg_reduction'] = max(
                                p_data.get('team_dmg_reduction', 0), val)
                            p_data['dmg_reduction'] = max(
                                p_data.get('dmg_reduction', 0), val)
                        else:
                            # Self-only (no cond, or ownerIsRelatedEffectTarget)
                            p_data['dmg_reduction'] = max(
                                p_data.get('dmg_reduction', 0), val)
                    # Sicia burn scaling: DMG_MUL*(0.03*burn_count)
                    m2 = re.search(r'DMG_MUL\*\(([\d.]+)\*.*AoEContinuousDamage', formula)
                    if m2:
                        p_data['burn_dmg_reduction'] = float(m2.group(1))
                    # Corvis poison scaling
                    m3 = re.search(r'-([\d.]+)\*DMG_MUL\).*ContinuousDamage', formula)
                    if m3:
                        p_data['poison_dmg_reduction_per'] = float(m3.group(1))

                # Extra turns passive (kind=7017)
                if kind == 7017:
                    p_data['extra_turns'] = True

                # Passive buff extension (kind=4012)
                if kind == 4012:
                    p_data['buff_extension'] = True

                # Passive stat scaling (kind=4013)
                if kind == 4013 and formula:
                    # Ninja: B_ATK*0.2*producerComboCounterOnBosses
                    m_atk = re.search(r'B_ATK\*([\d.]+)\*producerComboCounterOnBosses', formula)
                    if m_atk:
                        p_data['combo_atk_pct'] = float(m_atk.group(1))
                    m_crd = re.search(r'B_CRD\*([\d.]+)\*producerComboCounterOnBosses', formula)
                    if m_crd:
                        p_data['combo_cd_pct'] = float(m_crd.group(1))
                    # Sicia: 3*(burn_count)
                    if 'AoEContinuousDamage' in formula and not formula.startswith('-') and not formula.startswith('DMG_MUL'):
                        m6 = re.match(r'([\d.]+)\*', formula)
                        if m6:
                            p_data['burn_stat_pct'] = float(m6.group(1)) / 100

                # Passive counterattack (kind=4012)
                if kind == 4012:
                    p_data['passive_counterattack'] = True

                # Cleanse passive (kind=4010 on passive)
                if kind == 4010:
                    p_data['cleanse'] = True

                # Passive trigger (kind=9006) — Ninja's TM passive
                if kind == 9006:
                    p_data['passive_trigger'] = True

                # Geomancer-style reflect damage (kind=4017)
                if kind == 4017:
                    p_data['reflect_damage'] = True
                    if formula:
                        m_reflect = re.search(r'([\d.]+)\*TRG_HP', formula)
                        if m_reflect:
                            p_data['reflect_pct'] = float(m_reflect.group(1))

                # Passive debuff placement (OB passive places poisons)
                if kind == 5000:
                    for se in ses:
                        se_type = se.get('type', 0)
                        se_name = SE_TO_SIM.get(se_type)
                        dur = se.get('duration', 0)
                        if se_name in DEBUFF_SES:
                            p_data.setdefault('passive_debuffs', []).append(
                                {'debuff': se_name, 'duration': dur})

            # A1 heal detection
            for eff in sk.get('effects', []):
                kind = eff.get('kind', 0)
                formula = eff.get('formula', '')
                # Passive heal on dealt damage
                if kind == 1000 and 'DEALT_DMG' in formula:
                    m = re.match(r'([\d.]+)\*DEALT_DMG', formula)
                    if m:
                        p_data['self_heal_pct'] = float(m.group(1))
                if kind == 1000 and 'TRG_HP' in formula:
                    m = re.match(r'([\d.]+)\*TRG_HP', formula)
                    if m:
                        p_data['target_heal_pct'] = float(m.group(1))

        # Also check A1 for self-heal
        if 'A1' in labeled:
            for eff in labeled['A1'].get('effects', []):
                kind = eff.get('kind', 0)
                formula = eff.get('formula', '')
                if kind == 1000 and 'DEALT_DMG' in formula:
                    m = re.match(r'([\d.]+)\*DEALT_DMG', formula)
                    if m:
                        p_data['a1_self_heal_pct'] = float(m.group(1))
                if kind == 1000 and 'TRG_HP' in formula:
                    m = re.match(r'([\d.]+)\*TRG_HP', formula)
                    if m:
                        p_data['a1_target_heal_pct'] = float(m.group(1))

        if p_data:
            passive_data[name] = p_data

    # =====================================================================
    # Auto-correction pass: use parsed skill descriptions to fix chances,
    # missing debuffs/buffs, ignore_def, and other effects that the generic
    # effect-kind parser can't extract from game data alone.
    # =====================================================================
    try:
        from desc_profiler import parse_all_descriptions
        desc_parsed = parse_all_descriptions()

        # Load book bonuses: type=2 entries sum to debuff chance bonus per skill
        skills_db_path = base / "skills_db.json"
        book_bonuses = {}  # (hero_name, skill_type_id) -> debuff_chance_bonus
        if skills_db_path.exists():
            sdb = json.loads(skills_db_path.read_text())
            for hname, sklist in sdb.items():
                for sk in sklist:
                    stid = sk.get("skill_type_id", 0)
                    bonus = sum(lb.get("value", 0) for lb in sk.get("level_bonuses", [])
                                if lb.get("type") == 2)
                    if bonus > 0:
                        book_bonuses[(hname, stid)] = bonus / 100.0  # convert to fraction

        for hero_name in skill_data:
            dp = desc_parsed.get(hero_name, {})
            if not dp:
                continue

            for label in ["A1", "A2", "A3"]:
                p = dp.get(label)
                sd_entry = skill_data[hero_name].get(label)
                eff_list = skill_effects.get(hero_name, {}).get(label, [])
                if not p or not sd_entry:
                    continue

                # Fix debuff chances: use description base chance + book bonuses
                stid = p.get("skill_type_id", 0)
                book_bonus = book_bonuses.get((hero_name, stid), 0)
                for desc_db in p.get("debuffs", []):
                    if desc_db.get("on_self"):
                        continue
                    booked_chance = min(1.0, desc_db["chance"] + book_bonus)
                    for eff in eff_list:
                        if (eff.get("effect_type") == "debuff" and
                            eff["params"].get("debuff", "").startswith(desc_db["type"].split("_")[0])):
                            eff["params"]["chance"] = booked_chance

                # Fix ignore_def from descriptions
                if p.get("ignore_def_pct", 0) > 0 and sd_entry.get("ignore_def", 0) == 0:
                    sd_entry["ignore_def"] = p["ignore_def_pct"]

                # Add missing buffs from descriptions
                for desc_buf in p.get("buffs", []):
                    if desc_buf.get("target") == "self":
                        continue
                    existing_buffs = sd_entry.get("team_buffs", [])
                    has = any(b[0].startswith(desc_buf["type"].split("_")[0])
                              for b in existing_buffs if isinstance(b, tuple))
                    if not has:
                        existing_buffs.append((desc_buf["type"], desc_buf["duration"]))
                        sd_entry["team_buffs"] = existing_buffs

                # Fix extra_turn from descriptions
                if p.get("extra_turn") and not sd_entry.get("grants_extra_turn"):
                    sd_entry["grants_extra_turn"] = True
                if not p.get("extra_turn") and sd_entry.get("grants_extra_turn"):
                    sd_entry["grants_extra_turn"] = False

                # Add missing activate effects from descriptions.
                # activate_dots is a superset of activate_hp_burns + poisons,
                # so don't double-add — Teodor A3 has both flags but only
                # activate_dots should fire (real game = single tick of
                # all DoTs, not double).
                has_dots = any("activate_dots" in e.get("effect_type", "")
                               for e in eff_list)
                if p.get("activate_burns") and not has_dots:
                    has = any("activate_hp_burns" in e.get("effect_type", "") for e in eff_list)
                    if not has:
                        eff_list.append(_eff("activate_hp_burns"))
                if p.get("activate_poisons") and not has_dots:
                    has = any("activate_poisons" in e.get("effect_type", "") for e in eff_list)
                    if not has:
                        eff_list.append(_eff("activate_poisons", max_count=2))
                if p.get("activate_dots") and not has_dots:
                    eff_list.append(_eff("activate_dots"))

                # Add ally attack from descriptions
                if p.get("ally_attack"):
                    has = any("ally_attack" in e.get("effect_type", "") for e in eff_list)
                    if not has:
                        eff_list.append(_eff("ally_attack", count=4))

                # Add extend debuffs from descriptions
                if p.get("extend_debuffs") and not any("extend" in e.get("effect_type", "") for e in eff_list):
                    ext_type = p["extend_debuffs"]
                    if ext_type == "hp_burn":
                        eff_list.append(_eff("extend_debuffs_hp_burn", turns=1, per_hit=(p["hits"] > 1)))
                    elif ext_type == "poison_burn":
                        eff_list.append(_eff("extend_debuffs_poison_burn", turns=1))
                    else:
                        eff_list.append(_eff("extend_debuffs", turns=1, per_hit=(p["hits"] > 1)))

                # Add missing debuffs from descriptions (that game data didn't capture)
                for desc_db in p.get("debuffs", []):
                    if desc_db.get("on_self"):
                        continue
                    has = any(e.get("params", {}).get("debuff", "").startswith(desc_db["type"].split("_")[0])
                              for e in eff_list if e.get("effect_type") == "debuff")
                    if not has and desc_db["type"] in (
                        "def_down", "weaken", "dec_atk", "hp_burn", "poison_5pct",
                        "leech", "poison_sensitivity", "heal_reduction"
                    ):
                        eff_list.append(_eff("debuff",
                            debuff=desc_db["type"],
                            duration=desc_db["duration"],
                            chance=desc_db["chance"]))

    except Exception as ex:
        pass  # desc_profiler not available or failed — use game-data-only profiles

    # Phase 4 — fill in heroes not present in hero_profiles_game.json
    # (i.e. unowned ones) via the static-text desc parser. Owned heroes
    # already in skill_data are NOT overwritten — their book-aware
    # structured profiles always win. The augment is best-effort: if
    # profile_resolver or its inputs are missing, skill_data is
    # unchanged.
    try:
        from profile_resolver import augment_with_unowned
        augment_with_unowned(skill_data, skill_effects, passive_data=passive_data)
    except Exception:
        pass

    return skill_data, skill_effects, passive_data


if __name__ == "__main__":
    sd, se, pd = load_profiles()
    print(f"Loaded {len(sd)} heroes with skills")
    print(f"Loaded {len(se)} heroes with effects")
    print(f"Loaded {len(pd)} heroes with passives")

    # Print a few examples
    for name in ["Sicia Flametongue", "Maneater", "Ninja", "Occult Brawler", "Skullcrusher"]:
        if name in sd:
            print(f"\n=== {name} ===")
            for label, s in sd[name].items():
                print(f"  {label}: mult={s['mult']:.1f}x{s['stat']} hits={s['hits']} "
                      f"CD={s['cd']} buffs={s['team_buffs']} "
                      f"extra_turn={s.get('grants_extra_turn',False)}")
            if name in se:
                for label, effs in se[name].items():
                    for e in effs:
                        print(f"  {label} effect: {e['effect_type']} {e['params']}")
            if name in pd:
                print(f"  Passive: {pd[name]}")
