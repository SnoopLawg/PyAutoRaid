"""Shared turn-meter scheduling core — the single source of CB turn order.

The three CB sims (cb_sim damage/survival, calc_parity_sim DWJ-parity,
speed_tune) historically each rolled their own turn-meter loop. They agree on
the *structure* — a do-while tick loop, max-TM selection with index tie-break,
and a post-cast reset policy — but differ in the exact per-tick arithmetic and
the TM threshold. This engine owns the shared STRUCTURE; each caller supplies
its own bit-exact increment via `increment_fn`, so consolidating the loop
cannot alter a caller's floating-point result (which could otherwise flip a tie
and change the cast order).

Decoupled from any concrete actor class: it only needs a turn-meter attribute
(name configurable) and the caller's increment function. No imports of cb_sim /
cb_scheduler / speed_tune — those depend on this, not the reverse (low coupling,
dependency-inversion).

Design notes:
  - `increment_fn(actor) -> float`: TM gained by `actor` this tick. The caller
    bakes in effective-speed (incl. aura + speed buffs) and the threshold-scaled
    rate. Engine never computes speed itself.
  - do-while: ALWAYS tick at least once, even if an actor already sits above
    threshold from a prior cast's TM overflow. Skipping that tick was a real
    DWJ-parity miss (9% vs 91%).
  - reset policy: `"zero"` resets TM to 0 after a turn (DWJ / cb_sim's da59b52
    cadence); `"overflow"` subtracts the threshold (preserves carry-over).

`facade_tick_rate(threshold)` exposes the game-truth per-tick rate from
sim_data_facade (stamina_per_tick × threshold / stamina_to_turn) so callers can
derive their rate consistently instead of hardcoding 0.07 / 0.7.
"""
from __future__ import annotations

from typing import Callable


def facade_tick_rate(threshold: float) -> float:
    """Game-truth per-tick TM gain factor for a given threshold, from the
    facade's StaminaByTick / StaminaToTurn. Falls back to the documented
    0.07 × threshold / 100 if manifests are unavailable."""
    try:
        from sim_data_facade import try_facade
        f = try_facade()
        if f is not None:
            return f.tm.tick_rate_for_threshold(threshold)
    except Exception:
        pass
    return 0.07 * threshold / 100.0


class TurnMeterEngine:
    """Owns the turn-meter loop structure. Arithmetic stays with the caller."""

    def __init__(self, *, threshold: float, increment_fn: Callable[[object], float],
                 tm_attr: str = "turn_meter", round_ndigits: int | None = None,
                 max_safety_ticks: int = 10000):
        self.threshold = threshold
        self.increment_fn = increment_fn
        self.tm_attr = tm_attr
        self.round_ndigits = round_ndigits
        self.max_safety_ticks = max_safety_ticks

    # --- TM accessors (configurable attribute keeps the engine class-agnostic) ---
    def get_tm(self, actor) -> float:
        return getattr(actor, self.tm_attr)

    def set_tm(self, actor, value: float) -> None:
        setattr(actor, self.tm_attr, value)

    # --- loop primitives ---
    def tick_once(self, actors) -> None:
        """Add one tick of TM to every actor, using the caller's increment_fn."""
        for a in actors:
            v = self.get_tm(a) + self.increment_fn(a)
            if self.round_ndigits is not None:
                v = round(v, self.round_ndigits)
            self.set_tm(a, v)

    def tick_until_ready(self, actors) -> int:
        """do-while: tick at least once, then until an actor crosses threshold.
        Returns the number of ticks elapsed (callers that track a monotonic
        tick counter use this)."""
        safety = 0
        while True:
            self.tick_once(actors)
            safety += 1
            if any(self.get_tm(a) >= self.threshold for a in actors):
                return safety
            if safety > self.max_safety_ticks:
                raise RuntimeError("TM tick loop failed to terminate")

    def highest_tm_actor(self, actors):
        """The actor with the highest TM; ties resolved by list order (first
        wins), matching DWJ's reduce(max)."""
        m = max(self.get_tm(a) for a in actors)
        return next(a for a in actors if self.get_tm(a) == m)

    def reset_after_turn(self, actor, *, mode: str = "zero") -> None:
        """Post-cast TM policy. 'zero' (default) matches DWJ + cb_sim's
        da59b52 cadence; 'overflow' preserves carry-over above threshold."""
        if mode == "zero":
            self.set_tm(actor, 0.0)
        elif mode == "overflow":
            self.set_tm(actor, self.get_tm(actor) - self.threshold)
        else:
            raise ValueError(f"unknown reset mode: {mode!r}")
