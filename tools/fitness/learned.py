"""M5 PHASE 5b — learned (comp, location) -> outcome model SCAFFOLD.

5a is a transparent heuristic. 5b's end-state is a *learned* model that
predicts a real outcome (cleared? / damage) from a comp + location, trained on
labelled runs. The labels don't exist yet at scale, so this module is the
scaffold the future data plugs into:

    featurize(comp, location, context) -> [float, ...]   # fixed-length vector
    train(samples) -> model                              # sklearn or fallback
    predict(model, comp, location, context) -> {p_clear, ...}
    save_model / load_model  (data/fitness_model.json)

It runs TODAY with zero training data: `train([])` returns a *prior* model
whose `predict` squashes the public `fitness.score()` heuristic into a
probability. As labels accumulate, the same `train()` fits a real classifier
and `predict` switches to it transparently — callers don't change.

Features are built ONLY from the public 5a surface: M1 tags via
`fitness.synergy_data` helpers + boss constraints + the caller's ACC context.
No reach into heuristic.py / cb_adapter.py internals.

----------------------------------------------------------------------------
LABEL SCHEMA (a "sample")
----------------------------------------------------------------------------
    {
      "comp":     ["Maneater", "Demytha", ...],   # hero names
      "location": "clan_boss",                     # fitness/boss key
      "cleared":  True,                            # bool outcome (clear/kill)
      "damage":   36_200_000.0,                    # optional float (CB total)
      "context":  {"cb_element": 1},               # optional score() context
      "source":   "cb_sim" | "real_run" | "recommender" | "rediscovery"
    }

`make_sample(...)` builds one with validation.

----------------------------------------------------------------------------
HOW LABELS GET GENERATED
----------------------------------------------------------------------------
NOW (clan_boss only): the cb_sim adapter is a real outcome simulator. Run a
comp through it and emit a sample — `labels_from_cb_sim(comps, context)` does
exactly this (cleared = survived to T50 / total>0; damage = sim total). This is
the only mode with a trustworthy automatic label today.

LATER (per-mode): each location needs its own outcome signal —
  • real runs        : battle_logs_* / cb_history -> cleared + damage/time
  • rediscovery harness: comp_finder / recommender solve -> "runnable + holds"
  • per-mode sims    : dragon/spider/etc. simulators (do not exist yet)
Until those land, non-CB samples must come from real runs or be hand-labelled;
`source` records provenance so the trainer can weight/filter by trust later.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from . import synergy_data as sd  # public helper layer (allowed)

MODEL_PATH = ROOT / "data" / "fitness_model.json"

# --------------------------------------------------------------------------- #
# Feature vector (fixed length, deterministic order).
# --------------------------------------------------------------------------- #
FEATURE_NAMES = [
    "n_hit_engines",
    "n_poison_engines",
    "n_hp_burn_engines",
    "amp_def_down",
    "amp_weaken",
    "amp_inc_atk",
    "amp_inc_crit",
    "hit_amp_multiplier",
    "hit_channel_strength",        # n_hit_engines * hit_amp_multiplier
    "poison_stacks_capped",
    "poison_sensitivity",
    "poison_channel_strength",     # stacks * sensitivity_multiplier
    "dot_detonate",
    "survival_value",
    "n_survival_currencies",
    "n_enablers",
    "n_keystones_needing_enabler",
    "keystone_satisfied",
    "n_debuffers",
    "team_acc",
    "acc_floor",
    "acc_gap",                     # max(0, acc_floor - team_acc), 0 if acc unknown
    "boss_poison_immune",
    "boss_hp_burn_bonus_pct",
    "lethality",
    "n_useful_control",
    "comp_size",
]
N_FEATURES = len(FEATURE_NAMES)


def _records(comp, context: dict):
    override = context.get("records_override")
    recs = []
    for name in comp:
        rec = sd.get_record(name, override=override)
        if rec is None and "_" in name:
            head = name.rpartition("_")[0]
            rec = sd.get_record(head, override=override) if head else None
        if rec is not None:
            recs.append(rec)
    return recs


def _boss_features(location: str, recs: list[dict]) -> dict:
    """ACC floor / poison-immune / hp-burn-bonus / lethality / useful-control
    from boss_constraints + the 5a lethality table. All wrapped so an unknown
    location degrades to neutral defaults."""
    out = {"acc_floor": 0.0, "poison_immune": 0.0, "hp_burn_bonus_pct": 0.0,
           "lethality": 0.6, "n_useful_control": 0.0}
    try:
        import boss_constraints as bc
        try:
            af = bc.acc_floor(location)
            out["acc_floor"] = float(af or 0.0)
        except Exception:
            pass
        try:
            rx = bc.dot_reactions(location) or {}
            out["poison_immune"] = 1.0 if (rx.get("poison_immune") or
                "immun" in str(rx.get("poison", "")).lower()) else 0.0
            out["hp_burn_bonus_pct"] = float(rx.get("hp_burn_bonus_pct") or 0.0)
        except Exception:
            pass
        # useful control effects vs this boss
        effects: set[str] = set()
        for r in recs:
            effects |= sd.control_tags(r)
        useful = 0
        for eff in effects:
            try:
                if bc.is_effect_useful(location, eff):
                    useful += 1
            except Exception:
                useful += 1
        out["n_useful_control"] = float(useful)
    except Exception:
        pass
    # lethality from the 5a table (public via heuristic module constant).
    try:
        from .heuristic import LETHALITY, DEFAULT_LETHALITY
        key = str(location).strip().lower().replace("-", "_").replace(" ", "_")
        out["lethality"] = float(LETHALITY.get(key, DEFAULT_LETHALITY))
    except Exception:
        pass
    return out


def featurize(comp, location: str, context: dict | None = None) -> list[float]:
    """Build the fixed-length feature vector for (comp, location).

    Reuses `fitness.synergy_data` classifiers + boss constraints. Heroes with
    no M1 record are dropped (so an all-unknown comp yields the zero vector,
    a valid prior input). Length is always `N_FEATURES`.
    """
    context = dict(context or {})
    recs = _records(comp, context)

    n_hit = sum(1 for r in recs if sd.has_hit_engine(r))
    n_poison = sum(1 for r in recs if sd.has_poison_engine(r))
    n_burn = sum(1 for r in recs if sd.has_hp_burn_engine(r))

    amp_types: set[str] = set()
    for r in recs:
        amp_types |= sd.hit_amplifier_types(r)
    hit_mult = 1.0
    for t in amp_types:
        hit_mult *= (1.0 + sd.HIT_AMPLIFIER_WEIGHTS[t])

    stacks = min(sum(sd.poison_stack_contribution(r) for r in recs), 10)
    sens = any(sd.is_poison_sensitivity(r) for r in recs)
    sens_mult = 1.5 if sens else 1.0
    detonate = any(sd.has_dot_detonate(r) for r in recs)

    survival_value = sum(sd.survival_weight(r) for r in recs)
    n_surv = sum(1 for r in recs if r.get("survival_currency"))
    enablers = {r["enabler"] for r in recs if r.get("enabler")}
    n_enablers = len(enablers)
    keystones = [r for r in recs if r.get("keystone_needs_enabler")
                 and r.get("survival_currency")]
    keystone_ok = 0.0
    for r in keystones:
        compat = sd.KEYSTONE_ENABLER_COMPAT.get(r["survival_currency"], set())
        if enablers & compat:
            keystone_ok = 1.0
            break

    n_debuffers = sum(1 for r in recs
                      if any(p.startswith("enemy_debuff:")
                             for p in r.get("provides", [])))
    team_acc = float(context.get("team_acc") or 0.0)

    bf = _boss_features(location, recs)
    acc_floor = bf["acc_floor"]
    acc_gap = max(0.0, acc_floor - team_acc) if team_acc > 0 and acc_floor else 0.0

    feats = {
        "n_hit_engines": float(n_hit),
        "n_poison_engines": float(n_poison),
        "n_hp_burn_engines": float(n_burn),
        "amp_def_down": 1.0 if "def_down" in amp_types else 0.0,
        "amp_weaken": 1.0 if "weaken" in amp_types else 0.0,
        "amp_inc_atk": 1.0 if "inc_atk" in amp_types else 0.0,
        "amp_inc_crit": 1.0 if "inc_crit" in amp_types else 0.0,
        "hit_amp_multiplier": hit_mult,
        "hit_channel_strength": n_hit * hit_mult,
        "poison_stacks_capped": float(stacks),
        "poison_sensitivity": 1.0 if sens else 0.0,
        "poison_channel_strength": stacks * sens_mult,
        "dot_detonate": 1.0 if detonate else 0.0,
        "survival_value": float(survival_value),
        "n_survival_currencies": float(n_surv),
        "n_enablers": float(n_enablers),
        "n_keystones_needing_enabler": float(len(keystones)),
        "keystone_satisfied": keystone_ok,
        "n_debuffers": float(n_debuffers),
        "team_acc": team_acc,
        "acc_floor": float(acc_floor),
        "acc_gap": float(acc_gap),
        "boss_poison_immune": bf["poison_immune"],
        "boss_hp_burn_bonus_pct": bf["hp_burn_bonus_pct"],
        "lethality": bf["lethality"],
        "n_useful_control": bf["n_useful_control"],
        "comp_size": float(len(comp)),
    }
    return [float(feats[name]) for name in FEATURE_NAMES]


# --------------------------------------------------------------------------- #
# Label schema helpers
# --------------------------------------------------------------------------- #
VALID_SOURCES = {"cb_sim", "real_run", "recommender", "rediscovery", "manual"}


def make_sample(comp, location: str, cleared: bool, damage: float | None = None,
                context: dict | None = None, source: str = "manual") -> dict:
    """Build a validated label sample (see module docstring for the schema)."""
    if source not in VALID_SOURCES:
        raise ValueError(f"source must be one of {sorted(VALID_SOURCES)}")
    return {
        "comp": list(comp),
        "location": str(location),
        "cleared": bool(cleared),
        "damage": None if damage is None else float(damage),
        "context": dict(context or {}),
        "source": source,
    }


# --------------------------------------------------------------------------- #
# Model: prior (no data) + trained (logistic). JSON-serializable throughout.
# --------------------------------------------------------------------------- #
# Soft prior used when there is no training data: squash the heuristic fitness
# into a probability. center/scale are deliberate placeholders — they make
# higher heuristic fitness -> higher p_clear, and get replaced the moment real
# labels train a classifier.
_PRIOR_CENTER = 2.0
_PRIOR_SCALE = 0.6


def _sigmoid(z: float) -> float:
    if z < -60:
        return 0.0
    if z > 60:
        return 1.0
    return 1.0 / (1.0 + math.exp(-z))


def _prior_model(reason: str) -> dict:
    return {
        "kind": "prior",
        "feature_names": FEATURE_NAMES,
        "weights": None,
        "bias": 0.0,
        "mean": None,
        "std": None,
        "trained_on": 0,
        "label": "cleared",
        "notes": reason,
    }


def _standardize(X: list[list[float]]):
    n, m = len(X), len(X[0])
    mean = [sum(row[j] for row in X) / n for j in range(m)]
    std = []
    for j in range(m):
        var = sum((row[j] - mean[j]) ** 2 for row in X) / n
        std.append(math.sqrt(var) if var > 1e-12 else 1.0)
    Z = [[(row[j] - mean[j]) / std[j] for j in range(m)] for row in X]
    return Z, mean, std


def _train_logreg_gd(Z, y, l2=1.0, lr=0.3, iters=800):
    """Pure-python logistic regression (gradient descent) — the documented
    fallback when scikit-learn is unavailable. Operates on standardized Z."""
    n, m = len(Z), len(Z[0])
    w = [0.0] * m
    b = 0.0
    for _ in range(iters):
        gw = [0.0] * m
        gb = 0.0
        for i in range(n):
            z = b + sum(w[j] * Z[i][j] for j in range(m))
            err = _sigmoid(z) - y[i]
            gb += err
            for j in range(m):
                gw[j] += err * Z[i][j]
        b -= lr * gb / n
        for j in range(m):
            w[j] -= lr * (gw[j] / n + l2 * w[j] / n)
    return w, b


def train(samples: list[dict]) -> dict:
    """Train a (comp, location) -> cleared classifier.

    With <2 samples or a single outcome class, returns a *prior* model (usable
    immediately). Otherwise fits scikit-learn LogisticRegression if available,
    else the pure-python gradient-descent fallback. Returns a JSON-serializable
    model dict (weights live in standardized space; predict re-standardizes).
    """
    if not samples:
        return _prior_model("no training data — using heuristic-squash prior")
    X = [featurize(s["comp"], s["location"], s.get("context")) for s in samples]
    y = [1 if s.get("cleared") else 0 for s in samples]
    if len(samples) < 2 or len(set(y)) < 2:
        return _prior_model(
            f"insufficient/degenerate labels (n={len(samples)}, "
            f"classes={sorted(set(y))}) — using prior")

    Z, mean, std = _standardize(X)
    kind = "logreg_fallback"
    try:
        from sklearn.linear_model import LogisticRegression
        clf = LogisticRegression(max_iter=1000)
        clf.fit(Z, y)
        w = [float(c) for c in clf.coef_[0]]
        b = float(clf.intercept_[0])
        kind = "logreg_sklearn"
    except Exception:
        w, b = _train_logreg_gd(Z, y)

    return {
        "kind": kind,
        "feature_names": FEATURE_NAMES,
        "weights": w,
        "bias": b,
        "mean": mean,
        "std": std,
        "trained_on": len(samples),
        "label": "cleared",
        "notes": f"trained on {len(samples)} samples via {kind}",
    }


def predict(model: dict, comp, location: str,
            context: dict | None = None) -> dict:
    """Predict the clear probability for (comp, location).

    Returns {p_clear, kind, features?, fitness?}. For a prior model this is the
    squashed heuristic fitness; for a trained model it's the logistic output.
    """
    context = dict(context or {})
    if not model or model.get("kind") == "prior" or model.get("weights") is None:
        from . import score  # public API
        try:
            fit = score(comp, location, context)["fitness"]
        except Exception:
            fit = 0.0
        p = _sigmoid((fit - _PRIOR_CENTER) * _PRIOR_SCALE)
        return {"p_clear": p, "kind": "prior", "fitness": fit}

    x = featurize(comp, location, context)
    mean = model.get("mean") or [0.0] * len(x)
    std = model.get("std") or [1.0] * len(x)
    w = model["weights"]
    b = model.get("bias", 0.0)
    z = b + sum(w[j] * ((x[j] - mean[j]) / (std[j] or 1.0))
                for j in range(len(x)))
    return {"p_clear": _sigmoid(z), "kind": model["kind"], "features": x}


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
def save_model(model: dict, path: Path | str = MODEL_PATH) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(model, indent=2), encoding="utf-8")
    return path


def load_model(path: Path | str = MODEL_PATH) -> dict:
    path = Path(path)
    if not path.exists():
        return _prior_model("no saved model on disk — using prior")
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Label generation (CB sim is the only trustworthy auto-label today)
# --------------------------------------------------------------------------- #
def labels_from_cb_sim(comps, context: dict | None = None) -> list[dict]:
    """Generate clan_boss labels by running comps through the cb_sim adapter.

    cleared := survived to T50 / total>0; damage := sim total. Requires the CB
    simulator stack (cb_potential / cb_sim); returns [] if unavailable. This is
    the wired example of automatic label generation — per-mode label sources
    (real runs, future per-mode sims) follow the same `make_sample` schema.
    """
    from . import score  # public API
    ctx = dict(context or {})
    ctx["sim"] = True
    samples: list[dict] = []
    for comp in comps:
        try:
            res = score(list(comp), "clan_boss", ctx)
        except Exception:
            continue
        if res.get("kind") != "cb_sim":
            continue  # sim stack unavailable -> heuristic fallback, skip
        bd = res.get("breakdown", {})
        total = bd.get("total", res.get("fitness", 0.0))
        cleared = bool(bd.get("survived_t50", total and total > 0))
        samples.append(make_sample(comp, "clan_boss", cleared,
                                   damage=float(total or 0.0),
                                   context=context, source="cb_sim"))
    return samples


if __name__ == "__main__":  # pragma: no cover - manual smoke
    a = ["Maneater", "Demytha", "Ninja", "Geomancer", "Venomage"]
    b = ["Warmaiden", "Hyria", "High Khatun", "Apothecary", "Ninja"]
    m = train([])
    print("prior model:", m["kind"], m["notes"])
    print("featurize A:", dict(zip(FEATURE_NAMES, featurize(a, "clan_boss"))))
    print("predict A:", predict(m, a, "clan_boss"))
    print("predict B:", predict(m, b, "clan_boss"))
