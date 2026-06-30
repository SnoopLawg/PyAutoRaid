"""CB adapter — wraps the calibrated Clan Boss simulator as a fitness source.

When `score()` is asked for a *simulated* fitness on the clan_boss location it
delegates here. Damage (total over the fight) is the fitness; the result is
clearly labelled kind="cb_sim" so callers never confuse it with the heuristic.

Two underlying sims exist (CLAUDE.md):
  • cb_potential.simulate_team   — builds 6★/booked/optimal gear for ANY hero;
    deterministic, fast (~0.1–0.8s), works without owned-gear data. DEFAULT.
  • cb_sim.evaluate_team_calibrated(use_current_gear=True) — uses each hero's
    real equipped artifacts; matches the +0.61% calibration but only works for
    owned/geared heroes. Used when context['use_current_gear'] is True.

NOTE: the sim under-survives vs the real game (see memory
project_cb_sim_calibration_state) — treat the number as an estimate / ranking
signal, exactly how cb_recommender labels it.
"""
from __future__ import annotations

import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))


def cb_sim_score(comp: list[str], context: dict) -> dict:
    """Run the CB sim on `comp` and return {fitness, kind:"cb_sim", breakdown}."""
    context = context or {}
    cb_element = int(context.get("cb_element", 4))  # default Void
    use_current_gear = bool(context.get("use_current_gear", False))

    try:
        if use_current_gear:
            import cb_sim
            r = cb_sim.evaluate_team_calibrated(
                list(comp), cb_element=cb_element, use_current_gear=True,
                deterministic=True)
            source = "cb_sim.evaluate_team_calibrated(use_current_gear=True)"
        else:
            import cb_potential
            r = cb_potential.simulate_team(list(comp), cb_element=cb_element)
            source = "cb_potential.simulate_team"
    except Exception as e:  # surfacing > swallowing: report, fall back to 0
        return {
            "fitness": 0.0, "kind": "cb_sim",
            "breakdown": {"error": f"{type(e).__name__}: {e}",
                          "source": "cb_adapter", "comp": list(comp)},
        }

    if r.get("error"):
        return {"fitness": 0.0, "kind": "cb_sim",
                "breakdown": {"error": r["error"], "source": source,
                              "comp": list(comp)}}

    total = float(r.get("total", 0.0) or 0.0)
    return {
        "fitness": total,
        "kind": "cb_sim",
        "breakdown": {
            "total": total,
            "cb_turns": r.get("cb_turns"),
            "valid": r.get("valid"),
            "cb_element": cb_element,
            "source": source,
            "comp": list(comp),
            "estimate_note": ("CB sim under-survives vs real game; treat as a "
                              "ranking estimate, not an absolute clear check."),
        },
    }
