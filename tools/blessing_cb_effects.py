"""Blessing -> Clan Boss effect classifier (M5 / task #7).

The blessing proc catalog (`data/static/blessing_procs.json`) stores, per
blessing and per grade, the game-truth `formula` + a machine-readable
`condition` string lifted from the IL2CPP effect relations (e.g.
`isOwnerProduceRelatedEffect&&!relationTargetIsAlly&&isPvPBattle&&...`).

Those conditions are the authoritative answer to "does this blessing do
anything on Clan Boss, and if so what?" — which the hand-maintained
`blessing_relevance.json` audit gets WRONG in several places (it marks
PvP-only blessings like Lethal Dose as "cb: relevant", and tags
already-modeled ones as unmodeled). Rather than hand-wire 25 blessings on
guessed behavior, this tool EVALUATES each condition against the fixed facts
of a CB fight and reports the real per-grade CB effect.

CB context facts (game-truth):
  - NOT a PvP battle            -> `isPvPBattle` is False
  - exactly one enemy (boss)    -> `aliveEnemiesCount` == 1, no minions
  - boss is immune to control   -> `targetHasControlDebuff` False on boss
  - boss is TM-immune           -> stamina change ON THE BOSS is a no-op
  - the boss is never an ally   -> `relationTargetIsAlly` / `...ProducerIsAlly` False

Output: a per-blessing CB classification (noop / offense / defense / survival
/ other) with the resolved per-grade formula for the CB-active offensive
amps, written to `data/static/blessing_cb_effects.json` and printed as a
table. This is the prerequisite worklist for wiring blessings into cb_sim —
and it fixes the misleading relevance flags on the way.

CLI:
    python3 tools/blessing_cb_effects.py                 # table for all blessings
    python3 tools/blessing_cb_effects.py --cb-active     # only CB-active ones
    python3 tools/blessing_cb_effects.py --audit-diff    # disagreements vs blessing_relevance.json
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROCS = ROOT / "data" / "static" / "blessing_procs.json"
RELEVANCE = ROOT / "data" / "static" / "blessing_relevance.json"
OUT = ROOT / "data" / "static" / "blessing_cb_effects.json"

# Effect kinds that change DAMAGE OUTPUT (what cb_sim must model). Everything
# else is survival/control/passive — classified separately.
DAMAGE_KINDS = {
    "ChangeDamageMultiplier", "ChangeCalculatedDamage", "Damage",
    "ChangeDefenceModifier", "DestroyStats",
}
SURVIVAL_KINDS = {
    "Heal", "RestoreDestroyedHp", "ChangeHealMultiplier", "ApplyBuff",
    "SetShieldHitCounter", "SetLightOrbsStackCount", "PassiveReflectDamage",
    "PassiveBlockDebuff", "RemoveDebuff",
}
# Boss-TM-immune: stamina changes targeting the boss do nothing on CB.
STAMINA_KINDS = {"IncreaseStamina", "ReduceStamina"}
CONTROL_KINDS = {"SheepTransformation"}  # CB immune to control
# Demon Lord is immune to DestroyHp (task #8) — a no-op vs CB.
DESTROYHP_KINDS = {"DestroyHp"}

# Fixed truth-values for CB-context atoms. Anything not listed is treated as
# runtime-variable and assumed satisfiable (True) for an "is it ever active"
# test — the load-bearing facts here are isPvPBattle=False (the no-op
# detector) and the ally/minion/control facts.
CB_FACTS = {
    "isPvPBattle": False,
    "relationTargetIsAlly": False,
    "relationProducerIsAlly": False,
    "relationTargetIsMinion": False,
    "relationTargetIsBoss": True,
    "targetHasControlDebuff": False,
    "relatedReviveBlocked": False,
    "relationDamageIgnores": False,
    "skillIsDefault": False,
}

# Owner-role atoms are complementary: a proc is evaluated as either the owner
# DEALING the effect (offense) or the owner BEING HIT (defense). A condition
# that holds in EITHER context is active on CB; the context that activates it
# tells us whether it amplifies output (offense) or reduces damage-taken
# (defense). Without this split, `!ownerIsRelatedEffectTarget` in every
# offensive proc would wrongly evaluate False.
OFFENSE_CTX = {
    "isOwnerProduceRelatedEffect": True,
    "ownerIsRelatedEffectTarget": False,
    "ownerIsSkillProducer": True,
    "ownerIsSkillProduc": True,  # truncation-safe
}
DEFENSE_CTX = {
    "isOwnerProduceRelatedEffect": False,
    "ownerIsRelatedEffectTarget": True,
    "ownerIsSkillProducer": False,
    "ownerIsSkillProduc": False,
}
# Kinds that increase damage DEALT when the owner produces them (sign is not a
# "reduction" signal here — a negative ChangeDefenceModifier on the boss is
# offensive because it strips the boss's DEF).
OFFENSE_DEALT_KINDS = {"Damage", "ChangeCalculatedDamage", "DestroyStats",
                       "ChangeDefenceModifier"}

# Function-call atoms (e.g. HeroCounterWithId(...)) -> collapse to satisfiable.
_FUNC_CALL = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\([^()]*\)")

_GRADE_EQ = re.compile(r"ownersDoubleAscendLevel\s*==\s*([1-6])")
_GRADE_GE = re.compile(r"ownersDoubleAscendLevel\s*>=\s*([1-6])")
# An identifier atom: letters/digits/underscore, optionally with a trailing
# comparison we leave for the variable-satisfiable default.
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _cond_active_for_grade(condition: str, grade: int, ctx: dict) -> bool:
    """Evaluate whether `condition` can hold in a CB fight at `grade` under the
    given owner-role context (OFFENSE_CTX or DEFENSE_CTX).

    Returns True if satisfiable under the CB facts (runtime-variable atoms
    assumed satisfiable); False if a fixed CB fact forces it False (most
    importantly `isPvPBattle`)."""
    if not condition:
        return True
    facts = {**CB_FACTS, **ctx}
    expr = condition
    # Grade gates first (fixed truth per grade), before literal processing.
    expr = _GRADE_EQ.sub(lambda m: "True" if int(m.group(1)) == grade else "False", expr)
    expr = _GRADE_GE.sub(lambda m: "True" if grade >= int(m.group(1)) else "False", expr)

    # Literal-level satisfiability: a literal is an optional `!` then an atom
    # (identifier, optional func-call, optional comparison). Only a FIXED CB
    # fact can force a literal False; every free runtime literal — even when
    # negated — is satisfiable (set True), since the underlying variable can
    # take whichever value makes the conjunction hold. This is what prevents
    # `!targetIsDying`, `DEBUFF_COUNT>0`, etc. from spuriously zeroing a
    # condition while keeping `isPvPBattle` (a fixed False) load-bearing.
    def repl(m: re.Match) -> str:
        neg = bool(m.group(1))
        body = m.group(2)
        if body in ("True", "False"):
            return ("not " + body) if neg else body
        # Bare identifier that is a fixed CB fact?
        if body in facts and "(" not in body and not re.search(r"[=<>]", body):
            val = bool(facts[body])
            val = (not val) if neg else val
            return "True" if val else "False"
        return "True"  # free literal -> satisfiable

    lit = re.compile(r"(!?)\s*([A-Za-z_][A-Za-z0-9_./]*(?:\([^()]*\))?"
                     r"(?:\s*(?:==|!=|>=|<=|>|<)\s*[A-Za-z0-9_.]+)?)")
    expr = lit.sub(repl, expr)
    expr = expr.replace("&&", " and ").replace("||", " or ")
    expr = expr.replace("!", " not ")  # any stray !( group-negation
    try:
        return bool(eval(expr, {"__builtins__": {}}, {}))
    except Exception:
        return True  # don't claim no-op on a parse miss


def _formula_is_damage_reduction(formula: str) -> bool:
    """A negative ChangeDamageMultiplier reduces damage (defensive)."""
    return formula.strip().startswith("-")


def classify_blessing(b: dict) -> dict:
    """Return the CB classification + per-grade active formulas for a blessing."""
    code = b.get("blessing_code_id")
    ui = b.get("ui_name")
    damage_grades: dict[int, str] = {}     # grade -> formula (CB-active dmg amp)
    defense_grades: dict[int, str] = {}
    has_pvp_only_dmg = False
    has_survival = False
    has_stamina_boss = False
    has_control = False
    has_destroyhp = False
    other_kinds: set[str] = set()

    for ps in b.get("proc_skills", []):
        for e in ps.get("effects", []):
            kind = e.get("kind")
            cond = e.get("condition") or ""
            formula = e.get("formula") or ""
            grades = e.get("grades") or [1, 2, 3, 4, 5, 6]
            if kind in DAMAGE_KINDS:
                active_off = active_def = False
                for g in grades:
                    off = _cond_active_for_grade(cond, g, OFFENSE_CTX)
                    deff = _cond_active_for_grade(cond, g, DEFENSE_CTX)
                    if off:
                        active_off = True
                    if deff:
                        active_def = True
                    # ChangeDamageMultiplier: a NEGATIVE multiplier reduces
                    # damage. When it activates in the defense context (owner
                    # is the one hit), that's damage TAKEN reduction -> survival.
                    # Every other damage kind (incl. negative DEF modifier on
                    # the boss) increases damage DEALT when active on offense.
                    if kind == "ChangeDamageMultiplier" and _formula_is_damage_reduction(formula):
                        if deff:
                            defense_grades[g] = formula
                        elif off:
                            # negative mult on own offense (rare) — still a reduction
                            defense_grades[g] = formula
                    else:
                        if off and (kind in OFFENSE_DEALT_KINDS or not _formula_is_damage_reduction(formula)):
                            damage_grades[g] = formula
                if not (active_off or active_def) and "isPvPBattle" in cond:
                    has_pvp_only_dmg = True
            elif kind in STAMINA_KINDS:
                has_stamina_boss = True       # vs boss -> no-op (TM immune)
            elif kind in CONTROL_KINDS:
                has_control = True            # CB immune to control
            elif kind in DESTROYHP_KINDS:
                has_destroyhp = True          # Demon Lord immune (task #8)
            elif kind in SURVIVAL_KINDS:
                has_survival = True
            else:
                other_kinds.add(kind)

    # Decide the dominant CB role.
    if damage_grades:
        role = "cb_offense"
    elif defense_grades:
        role = "cb_defense"
    elif has_survival:
        role = "cb_survival"
    elif has_pvp_only_dmg and not (has_survival or other_kinds):
        role = "cb_noop_pvp_only"
    elif has_control and not other_kinds:
        role = "cb_noop_control_immune"
    elif (has_stamina_boss or has_destroyhp) and not (
            damage_grades or defense_grades or has_survival or other_kinds):
        role = "cb_noop_tm_immune" if has_stamina_boss and not has_destroyhp else "cb_noop_immune"
    elif other_kinds:
        role = "cb_other"
    else:
        role = "cb_noop"

    return {
        "code": code, "ui_name": ui, "rarity": b.get("rarity"),
        "cb_role": role,
        "damage_amp_by_grade": {str(g): damage_grades[g] for g in sorted(damage_grades)},
        "damage_reduction_by_grade": {str(g): defense_grades[g] for g in sorted(defense_grades)},
        "other_effect_kinds": sorted(other_kinds),
        "notes": _role_note(role),
    }


def _role_note(role: str) -> str:
    return {
        "cb_offense": "Increases damage on CB; wire damage_amp_by_grade into cb_sim bless_mult.",
        "cb_defense": "Reduces damage TAKEN on CB (survival, not output).",
        "cb_survival": "Heal/shield/cleanse — affects survival, not damage output.",
        "cb_noop_pvp_only": "PvP-only (isPvPBattle) — NO EFFECT on Clan Boss.",
        "cb_noop_control_immune": "Control effect — CB is immune; no effect.",
        "cb_noop_tm_immune": "Stamina/TM change vs boss — CB is TM-immune; no effect.",
        "cb_noop_immune": "DestroyHp/stamina vs boss — CB is immune (task #8); no effect.",
        "cb_other": "Buff/passive of a kind not affecting CB damage directly.",
        "cb_noop": "No CB-relevant effect found.",
    }.get(role, "")


def load_relevance_audit() -> dict:
    if not RELEVANCE.exists():
        return {}
    rows = json.loads(RELEVANCE.read_text(encoding="utf-8")).get("blessings", [])
    out = {}
    for r in rows:
        out[r.get("id")] = r.get("relevance", {}).get("cb")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cb-active", action="store_true",
                    help="show only blessings that affect CB (offense/defense/survival)")
    ap.add_argument("--audit-diff", action="store_true",
                    help="show where this classification disagrees with blessing_relevance.json's cb flag")
    args = ap.parse_args(argv)

    procs = json.loads(PROCS.read_text(encoding="utf-8"))["blessings"]
    results = [classify_blessing(b) for b in procs]
    results.sort(key=lambda r: (r["cb_role"], r["code"]))

    audit = load_relevance_audit() if args.audit_diff else {}
    # CB-active roles for the audit cross-check.
    active_roles = {"cb_offense", "cb_defense", "cb_survival"}

    print(f"{'CODE':22} {'UI NAME':22} {'CB ROLE':24} AMP(grade6)")
    shown = 0
    for r in results:
        if args.cb_active and r["cb_role"] not in active_roles:
            continue
        amp6 = r["damage_amp_by_grade"].get("6") or r["damage_reduction_by_grade"].get("6") or ""
        line = f"{r['code']:22.22} {r['ui_name']:22.22} {r['cb_role']:24.24} {amp6}"
        if args.audit_diff:
            audit_cb = audit.get(r["code"])
            ours_active = r["cb_role"] in active_roles
            ours_noop = r["cb_role"].startswith("cb_noop")
            if audit_cb == "relevant" and ours_noop:
                line += "   [AUDIT SAYS relevant, WE SAY no-op]"
            elif audit_cb in ("no_op", None) and ours_active:
                line += "   [AUDIT SAYS no-op, WE SAY active]"
            # cb_other = indirect/uncertain (e.g. Smite debuff, leader aura) —
            # not asserted either way.
        print(line)
        shown += 1

    # Summary counts.
    from collections import Counter
    counts = Counter(r["cb_role"] for r in results)
    print("\nrole counts:", dict(counts))

    OUT.write_text(json.dumps({
        "_meta": {"source": "blessing_procs.json conditions evaluated against CB facts",
                  "tool": "tools/blessing_cb_effects.py"},
        "blessings": results,
    }, indent=1), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({shown} rows shown, {len(results)} total)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
