# DWJ Notation ↔ In-Game Preset Translation

Researched 2026-05-02 against DWJ's Myth Eater Ninja UNM tune
(https://deadwoodjedi.info/cb/6737fa4be0ec51c5065a433d3f23b7616d9ca430)
and the user's verified-working preset 1 ("Cb"). User-confirmed
clarifications on the UI ↔ DWJ inversion.

## DWJ Calculator Notation

Each skill in a DWJ tune is annotated `pN dN cdN`:

| Field | Meaning |
|---|---|
| `pN` | Priority. **DWJ: HIGHER NUMBER = HIGHER PRIORITY.** Sorted DESC; first skill where `cd=0 AND delay=0` is cast. |
| `dN` | Delay. Skill is not castable until N hero-turns have elapsed (counted at battle start, decrements each hero turn after each cast). |
| `cdN` | Cooldown. Number of hero-turns the skill is on CD after casting. |

Source: `docs/dwj/calc_algorithm.md` line 33-41 + `tools/cb_scheduler.py::pick_skill`:
```python
sorted_cfg = sorted(actor.skill_configs, key=lambda c: -c.priority)
return next((c for c in sorted_cfg if c.current_cooldown == 0 and c.delay == 0), None)
```

## In-Game Preset (Plarium UI Convention)

The in-game preset editor (Team Setup → preset slot → per-hero "Skill Instructions"):

| UI Element | Storage Field | Encoding |
|---|---|---|
| Starter button (round 1 forced cast) | `rounds[i].starter_ids: int[]` | List of skill_type_ids — first one is the forced opener |
| Priority numbers (1, 2, 3...) | `rounds[i].priorities: {sid_str: int}` | **OPPOSITE of DWJ — UI LOWER NUMBER = HIGHER PRIORITY.** `0` = unranked / default fallback. |

**The opener trumps everything but only for the first move.** Subsequent
turns use the priority order.

The DWJ Myth Eater page reads "Set A3 as 1st priority, Set A2 as 2nd choice".
"1st priority" maps to the UI's lowest non-zero number (e.g. `priorities[A3]=1`),
"2nd choice" to the next (`priorities[A2]=2`).

**Verified empirically 2026-05-02** by checking the user's preset (Ninja
priorities {A1:0, A3:1, A2:2}) against DWJ's stated intent for Ninja
(A3 1st priority, A2 2nd choice): user's `A3=1, A2=2` matches.

## Translating DWJ "delay" to In-Game

**The Plarium UI does NOT have a delay field.** The user CANNOT directly
set DWJ's `dN` value. To achieve DWJ's "A3 d2" (A3 delayed to 3rd cast)
in-game, you use a **workaround via opener + priority**:

| DWJ Tune | In-Game Workaround |
|---|---|
| `A3(p3 d0 cd5)` (A3 first) | Set opener=A3 OR set A3 as priority 1 |
| `A3(p3 d1 cd5)` (A3 fires 2nd) | Opener=A1 + priority A3=1 → A1 first, then A3 |
| `A3(p3 d2 cd3)` (A3 fires 3rd) | Opener=A1 + priority A2=1, A3=2 → A1 first, A2 second, A3 third |

The "delay" is achieved by **forcing other skills to fire first via
the priority queue**.

Per user (2026-05-02): "you cannot actually delay using the game presets,
but you can be smart about it and use an opener which forces a start
ability and then the normal AI would pick the A3 etc. or opener on A1
and then prioritize A2 and now A3 is successfully delayed twice because
we did a workaround way to force A1, A2, then finally the A3."

## Translation Table (CONFIRMED)

DWJ Myth Eater Ninja UNM tune → user's preset 1:

| DWJ tune entry | What user clicks in UI | Preset stored |
|---|---|---|
| Maneater A1(p1 d0 cd0) — base | (no priority click) | `priorities[A1]=0` |
| Maneater A2(p2 d0 cd3) | "2nd priority" | `priorities[A2]=2` |
| Maneater A3(p3 d1 cd5) — "delayed 1" | (no priority click — relies on natural AI) | `priorities[A3]=0`. The d1 effect comes from gear SPD. |
| Maneater opener "A1, A1, A3" | Click "Starter" on A1 (or A2 in user's variant) | `starter_ids=[A2_id]` (user customization) |
| Demytha A3(p3 d2 cd3) — "delayed 2" | "2nd priority" on A3 | `priorities[A3]=2` (UI's "2nd") |
| Demytha A2(p2 d0 cd3) | "1st priority" on A2 | `priorities[A2]=1` (UI's "1st") |
| Demytha opener "A3" | Click "Starter" on A1 (user variant) | `starter_ids=[A1]` |
| Ninja A3 1st choice | "1st priority" on A3 | `priorities[A3]=1` |
| Ninja A2 2nd choice | "2nd priority" on A2 | `priorities[A2]=2` |

## Sim Implementation

`tools/preset_loader.py::load_preset_for_team`:
- Reads `/presets` from the live mod
- Maps `starter_ids` → `SimChampion.opening` (consumed turn 1)
- Maps `priorities` → `SimChampion.skill_priority`:
  - Sorts by priority value ASC (lower number first = highest priority)
  - Priority 0 (unranked) sorts to the END as fallback
- Returns `{hero_name: {opening, priority}}`

Sort key:
```python
BIG = 999  # priority 0 → "infinity" so unranked sorts after ranked
prio_pairs.sort(key=lambda x: (x[1] if x[1] > 0 else BIG, x[2]))
```
