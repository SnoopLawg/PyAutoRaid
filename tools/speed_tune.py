"""
Clan Boss Speed Tune Calculator — DeadwoodJedi-style turn meter simulator.

Simulates the exact turn-by-turn fight mechanics:
- Tick-based turn meter (TM += speed per tick, threshold = 1000)
- TM overflow preserved across turns
- Buff/debuff durations tick at START of the buffed unit's turn
- CB 3-turn rotation: A2 (AoE) → A3 (AoE) → A1 (stun) [Void]
- Validates Unkillable/Block Damage coverage on every CB AoE
- Turn 50 hard enrage (Unkillable ignored)

Usage:
    python3 tools/speed_tune.py                    # validate current best team
    python3 tools/speed_tune.py --sweep            # find valid speed ranges
    python3 tools/speed_tune.py --speeds 219 218 178 172 171  # test specific speeds
"""
import argparse
import json
from pathlib import Path
from copy import deepcopy
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# =============================================================================
# Constants
# =============================================================================
TM_THRESHOLD = 1000
MAX_CB_TURNS = 50  # hard enrage at turn 50

# CB speeds by difficulty
CB_SPEEDS = {
    "easy": 130, "normal": 140, "hard": 150,
    "brutal": 160, "nightmare": 170, "unm": 190,
}

# CB attack pattern (Void): A2(AoE) → A3(AoE) → A1(stun), repeating
# Affinity CB swaps A2/A3: A3(AoE) → A2(AoE) → A1(stun)
CB_VOID_PATTERN = ["aoe1", "aoe2", "stun"]  # 3-turn cycle
CB_AFFINITY_PATTERN = ["aoe2", "aoe1", "stun"]


# =============================================================================
# Data Classes
# =============================================================================
@dataclass
class Skill:
    name: str
    base_cd: int = 0          # 0 = no cooldown (A1)
    current_cd: int = 0       # turns until available (0 = ready)
    buffs_on_team: list = field(default_factory=list)   # [(buff_name, duration)]
    buffs_on_self: list = field(default_factory=list)
    debuffs_on_enemy: list = field(default_factory=list)
    tm_boost_allies: float = 0.0   # % TM fill on allies (e.g. 0.20 = 20%)
    tm_boost_self: float = 0.0
    cd_reduce_allies: int = 0      # reduce ally cooldowns by N
    is_passive: bool = False


@dataclass
class Champion:
    name: str
    speed: float
    position: int              # 1-5 (1 = leader)
    tm: float = 0.0
    skills: List[Skill] = field(default_factory=list)
    buffs: Dict[str, int] = field(default_factory=dict)  # buff_name → remaining turns
    is_stunned: bool = False
    turns_taken: int = 0
    opening: List[str] = field(default_factory=list)  # forced skill order for first N turns

    def has_buff(self, buff_name):
        return self.buffs.get(buff_name, 0) > 0

    def tick_buffs(self):
        """Tick down buff durations at START of this champion's turn."""
        expired = []
        for buff, dur in self.buffs.items():
            self.buffs[buff] = dur - 1
            if self.buffs[buff] <= 0:
                expired.append(buff)
        for b in expired:
            del self.buffs[b]

    def add_buff(self, buff_name, duration):
        """Add or refresh a buff."""
        self.buffs[buff_name] = max(self.buffs.get(buff_name, 0), duration)


@dataclass
class ClanBoss:
    speed: float
    tm: float = 0.0
    turn_count: int = 0
    pattern: list = field(default_factory=lambda: list(CB_VOID_PATTERN))
    affinity: str = "void"

    def get_attack_type(self):
        """Return current attack type based on 3-turn cycle."""
        idx = self.turn_count % 3
        return self.pattern[idx]


# =============================================================================
# Skill Definitions for Key Champions
# =============================================================================
def _cd(displayed_cd: int) -> int:
    """Convert Raid's displayed cooldown to internal base_cd.

    Raid shows "Cooldown: N turns" meaning the skill is usable again on the Nth
    turn after use. In our tick system, we set CD on use and don't tick that turn,
    so base_cd = displayed - 1.

    Example: "Cooldown: 5 turns" → base_cd=4 → use on T1, ticks T2(3) T3(2) T4(1) T5(0=ready)
    """
    return max(0, displayed_cd - 1)


def make_maneater_skills(booked=True):
    """Maneater skill rotation.
    A2: ATK Up 2T. Displayed CD: 4 (booked 3).
    A3: Unkillable 3T + Block Damage 1T. Displayed CD: 7 (booked 5).
    Books increase Unkillable from 2T to 3T.
    """
    return [
        Skill(name="A1", base_cd=0),
        Skill(name="A2", base_cd=_cd(3 if booked else 4),
              buffs_on_team=[("atk_up", 2)]),
        Skill(name="A3", base_cd=_cd(5 if booked else 7),
              buffs_on_team=[("unkillable", 3 if booked else 2), ("block_damage", 1)]),
    ]


def make_pain_keeper_skills(booked=True):
    """Pain Keeper: A3 reduces ally cooldowns by 1.
    A2: Heal. Displayed CD: 4 (booked 3).
    A3: CD reduce. Displayed CD: 5 (booked 3).
    """
    return [
        Skill(name="A1", base_cd=0),
        Skill(name="A2", base_cd=_cd(3 if booked else 4)),
        Skill(name="A3", base_cd=_cd(3 if booked else 5),
              cd_reduce_allies=1),
    ]


def make_demytha_skills(booked=True):
    """Demytha: A2 Block Damage 2T, A3 Cont Heal.
    A2: Displayed CD: 4 (booked 3). A3: Displayed CD: 4 (booked 3).
    """
    return [
        Skill(name="A1", base_cd=0),
        Skill(name="A2", base_cd=_cd(3 if booked else 4),
              buffs_on_team=[("block_damage", 2)]),
        Skill(name="A3", base_cd=_cd(3 if booked else 4),
              buffs_on_team=[("cont_heal", 2)]),
    ]


def make_generic_dps_skills():
    """Generic DPS: A1 only (no buffs/debuffs that affect the tune)."""
    return [
        Skill(name="A1", base_cd=0),
        Skill(name="A2", base_cd=_cd(4)),
        Skill(name="A3", base_cd=_cd(5)),
    ]


CHAMPION_SKILLS = {
    "Maneater": make_maneater_skills,
    "Pain Keeper": make_pain_keeper_skills,
    "Demytha": make_demytha_skills,
}


# =============================================================================
# Turn Meter Simulation Engine
# =============================================================================
class SpeedTuneSimulator:
    def __init__(self, champions: List[Champion], cb_speed: float = 190,
                 affinity: str = "void", verbose: bool = False):
        self.champions = champions
        self.cb = ClanBoss(
            speed=cb_speed,
            pattern=CB_VOID_PATTERN if affinity == "void" else CB_AFFINITY_PATTERN,
            affinity=affinity,
        )
        self.verbose = verbose
        self.log = []
        self.errors = []
        self.turn_order_log = []  # [(tick, actor_name, action, buffs_snapshot)]

    def run(self, max_cb_turns: int = MAX_CB_TURNS) -> dict:
        """Run the full fight simulation. Returns result dict."""
        tick = 0
        all_combatants = self.champions + [self.cb]

        while self.cb.turn_count < max_cb_turns:
            tick += 1
            if tick > 100000:  # safety valve
                self.errors.append(f"Simulation exceeded 100K ticks at CB turn {self.cb.turn_count}")
                break

            # Fill turn meters
            for champ in self.champions:
                champ.tm += champ.speed
            self.cb.tm += self.cb.speed

            # Process all combatants above threshold, highest TM first
            while True:
                # Gather everyone above threshold
                ready = []
                for champ in self.champions:
                    if champ.tm >= TM_THRESHOLD:
                        ready.append(("champ", champ))
                if self.cb.tm >= TM_THRESHOLD:
                    ready.append(("cb", self.cb))

                if not ready:
                    break

                # Sort: highest TM first, then by position (lower = first)
                def sort_key(entry):
                    kind, unit = entry
                    tm = unit.tm
                    pos = unit.position if kind == "champ" else 99
                    return (-tm, pos)

                ready.sort(key=sort_key)
                kind, actor = ready[0]

                if kind == "cb":
                    self._process_cb_turn(tick)
                else:
                    self._process_champion_turn(actor, tick)

        # Compile results
        return {
            "cb_turns": self.cb.turn_count,
            "errors": self.errors,
            "valid": len(self.errors) == 0,
            "log": self.turn_order_log,
            "champion_turns": {c.name + f"(p{c.position})": c.turns_taken for c in self.champions},
        }

    def _process_cb_turn(self, tick: int):
        """CB takes a turn."""
        self.cb.tm -= TM_THRESHOLD
        attack = self.cb.get_attack_type()
        self.cb.turn_count += 1

        entry = {
            "tick": tick,
            "cb_turn": self.cb.turn_count,
            "attack": attack,
            "actor": "CB",
        }

        if attack in ("aoe1", "aoe2"):
            # Check: is every champion protected?
            for champ in self.champions:
                protected = champ.has_buff("unkillable") or champ.has_buff("block_damage")
                if not protected and self.cb.turn_count <= MAX_CB_TURNS:
                    self.errors.append(
                        f"DEATH: {champ.name}(p{champ.position}) has NO Unkillable/BlockDmg "
                        f"on CB turn {self.cb.turn_count} ({attack}) [tick {tick}]"
                    )
            entry["protection"] = {
                c.name + f"(p{c.position})": {
                    "UK": c.buffs.get("unkillable", 0),
                    "BD": c.buffs.get("block_damage", 0),
                }
                for c in self.champions
            }

        elif attack == "stun":
            # Stun targets the champion without protective buffs, lowest HP%, or position
            # For simulation purposes, we just need to verify it doesn't break the tune
            # The stun is irresistible — target gets stunned for 1 turn
            # In UK comps, Block Damage or Unkillable prevents death but stun still lands
            # unless Block Debuffs is up
            target = self._pick_stun_target()
            if target:
                target.is_stunned = True
                entry["stun_target"] = target.name + f"(p{target.position})"

        self.turn_order_log.append(entry)

        if self.verbose:
            prot_str = ""
            if attack in ("aoe1", "aoe2"):
                parts = []
                for c in self.champions:
                    uk = c.buffs.get("unkillable", 0)
                    bd = c.buffs.get("block_damage", 0)
                    status = f"UK{uk}" if uk else ""
                    status += f"BD{bd}" if bd else ""
                    if not status:
                        status = "EXPOSED!"
                    parts.append(f"{c.name[:3]}={status}")
                prot_str = f"  [{', '.join(parts)}]"
            self.log.append(
                f"  T{self.cb.turn_count:>3} CB {attack}{prot_str}"
            )

    def _pick_stun_target(self) -> Optional[Champion]:
        """Simplified stun targeting: pick champion without Block Debuffs,
        preferring those without defensive buffs, then lowest position."""
        candidates = [c for c in self.champions if not c.has_buff("block_debuffs")]
        if not candidates:
            candidates = list(self.champions)

        # Prefer those without Counter Attack, Block Damage, Inc DEF
        def stun_priority(c):
            has_protection = (c.has_buff("block_damage") or
                              c.has_buff("counterattack") or
                              c.has_buff("inc_def"))
            return (has_protection, c.position)

        candidates.sort(key=stun_priority)
        return candidates[0] if candidates else None

    def _process_champion_turn(self, champ: Champion, tick: int):
        """Champion takes a turn."""
        champ.tm -= TM_THRESHOLD
        champ.turns_taken += 1

        # === START OF TURN: tick buffs and CDs ===
        champ.tick_buffs()
        for sk in champ.skills:
            if sk.current_cd > 0:
                sk.current_cd -= 1

        # Clear stun (costs the turn — no skill used, but CDs/buffs still ticked)
        if champ.is_stunned:
            champ.is_stunned = False
            entry = {
                "tick": tick, "actor": champ.name + f"(p{champ.position})",
                "action": "STUNNED (turn wasted)",
                "cb_turn": self.cb.turn_count,
            }
            self.turn_order_log.append(entry)
            if self.verbose:
                self.log.append(f"       {champ.name:>15} — STUNNED")
            return

        # === SKILL SELECTION (after CDs have ticked) ===
        chosen = champ.skills[0]  # A1 fallback
        if champ.opening:
            forced_name = champ.opening.pop(0)
            for sk in champ.skills:
                if sk.name == forced_name:
                    chosen = sk
                    break
        else:
            # Auto AI: use highest priority skill off cooldown
            for sk in reversed(champ.skills):  # check A3 first, then A2
                if sk.base_cd > 0 and sk.current_cd == 0:
                    chosen = sk
                    break

        # === APPLY SKILL EFFECTS ===
        action_str = chosen.name

        for buff_name, duration in chosen.buffs_on_team:
            for c in self.champions:
                c.add_buff(buff_name, duration)
            action_str += f" → {buff_name}({duration}T) on team"

        for buff_name, duration in chosen.buffs_on_self:
            champ.add_buff(buff_name, duration)

        if chosen.tm_boost_allies > 0:
            for c in self.champions:
                if c is not champ:
                    c.tm += TM_THRESHOLD * chosen.tm_boost_allies

        if chosen.tm_boost_self > 0:
            champ.tm += TM_THRESHOLD * chosen.tm_boost_self

        if chosen.cd_reduce_allies > 0:
            for c in self.champions:
                if c is not champ:
                    for sk in c.skills:
                        if sk.current_cd > 0:
                            sk.current_cd = max(0, sk.current_cd - chosen.cd_reduce_allies)
            action_str += f" → reduce ally CDs by {chosen.cd_reduce_allies}"

        # Put chosen skill on cooldown (AFTER using it)
        if chosen.base_cd > 0:
            chosen.current_cd = chosen.base_cd

        entry = {
            "tick": tick,
            "actor": champ.name + f"(p{champ.position})",
            "action": action_str,
            "cb_turn": self.cb.turn_count,
            "buffs": dict(champ.buffs),
        }
        self.turn_order_log.append(entry)

        if self.verbose:
            buffs_str = ",".join(f"{k}{v}" for k, v in champ.buffs.items()) or "none"
            self.log.append(
                f"       {champ.name:>15} {chosen.name:>3} [{buffs_str}]"
            )


# =============================================================================
# Team Builder
# =============================================================================
def build_champion(name: str, speed: float, position: int,
                   booked: bool = True, opening: List[str] = None) -> Champion:
    """Build a champion with their skill rotation."""
    skill_fn = CHAMPION_SKILLS.get(name)
    if skill_fn:
        skills = skill_fn(booked=booked)
    else:
        skills = make_generic_dps_skills()

    return Champion(
        name=name,
        speed=speed,
        position=position,
        skills=skills,
        opening=list(opening) if opening else [],
    )


def build_team(specs: List[Tuple[str, float]], booked: bool = True,
               openings: Dict[int, List[str]] = None) -> List[Champion]:
    """Build a team from (name, speed) tuples. Position assigned by order.

    Args:
        openings: {position: [skill_names]} for forced opening rotations
    """
    openings = openings or {}
    return [
        build_champion(name, speed, i + 1, booked, opening=openings.get(i + 1))
        for i, (name, speed) in enumerate(specs)
    ]


# =============================================================================
# Speed Range Finder
# =============================================================================
def find_valid_speeds(team_names: List[str], cb_speed: float = 190,
                      affinity: str = "void",
                      speed_ranges: Dict[str, Tuple[int, int]] = None,
                      openings: Dict[int, List[str]] = None,
                      step: int = 1) -> List[dict]:
    """Sweep speed combinations to find valid tunes.

    Args:
        team_names: List of 5 champion names
        cb_speed: CB speed (190 for UNM)
        speed_ranges: {name: (min_speed, max_speed)} overrides
        step: speed increment for sweep

    Returns:
        List of valid speed combinations
    """
    # Default ranges based on role
    default_ranges = {}
    me_count = 0
    for name in team_names:
        if name == "Maneater":
            me_count += 1
            if me_count == 1:
                default_ranges[f"Maneater_1"] = (217, 225)
            else:
                default_ranges[f"Maneater_2"] = (217, 225)
        elif name == "Pain Keeper":
            default_ranges[name] = (174, 179)
        elif name == "Demytha":
            default_ranges[name] = (174, 179)
        else:
            default_ranges[name] = (171, 189)

    if speed_ranges:
        default_ranges.update(speed_ranges)

    # Build key list for sweeping
    keys = []
    ranges_list = []
    me_idx = 0
    for name in team_names:
        if name == "Maneater":
            me_idx += 1
            key = f"Maneater_{me_idx}"
        else:
            key = name
        keys.append(key)
        lo, hi = default_ranges.get(key, (171, 225))
        ranges_list.append(range(lo, hi + 1, step))

    valid = []
    # For 5 champions with small ranges, this is tractable
    # But we need to be smart about it — don't iterate all combos blindly
    # Instead, fix Maneater speeds and sweep DPS speeds
    from itertools import product

    total_combos = 1
    for r in ranges_list:
        total_combos *= len(r)

    if total_combos > 500000:
        print(f"  Warning: {total_combos:,} combinations — using step={max(step, 2)}")
        step = max(step, 2)
        ranges_list = []
        me_idx = 0
        for name in team_names:
            if name == "Maneater":
                me_idx += 1
                key = f"Maneater_{me_idx}"
            else:
                key = name
            lo, hi = default_ranges.get(key, (171, 225))
            ranges_list.append(range(lo, hi + 1, step))

    total_combos = 1
    for r in ranges_list:
        total_combos *= len(r)
    print(f"  Sweeping {total_combos:,} speed combinations...")

    tested = 0
    for combo in product(*ranges_list):
        tested += 1
        specs = list(zip(team_names, combo))
        team = build_team(specs, openings=openings or {})
        sim = SpeedTuneSimulator(team, cb_speed=cb_speed, affinity=affinity)
        result = sim.run()

        if result["valid"]:
            valid.append({
                "speeds": dict(zip(keys, combo)),
                "champion_turns": result["champion_turns"],
            })

    print(f"  Tested {tested:,} → {len(valid)} valid tunes found")
    return valid


# =============================================================================
# Pretty Printer
# =============================================================================
def print_turn_log(result: dict, sim: 'SpeedTuneSimulator', max_lines: int = 100):
    """Print a DeadwoodJedi-style turn-by-turn log."""
    print(f"\n{'='*90}")
    print(f"SPEED TUNE VALIDATION — {'VALID ✓' if result['valid'] else 'INVALID ✗'}")
    print(f"{'='*90}")

    print(f"\nChampion turns taken (across {result['cb_turns']} CB turns):")
    for name, turns in result["champion_turns"].items():
        print(f"  {name}: {turns} turns")

    if result["errors"]:
        print(f"\n{'!'*60}")
        print(f"ERRORS ({len(result['errors'])}):")
        for err in result["errors"][:20]:
            print(f"  ✗ {err}")
        if len(result["errors"]) > 20:
            print(f"  ... and {len(result['errors']) - 20} more")
        print(f"{'!'*60}")

    if sim.log:
        print(f"\nTurn-by-turn log (first {max_lines} entries):")
        print(f"{'─'*90}")
        for line in sim.log[:max_lines]:
            print(line)
        if len(sim.log) > max_lines:
            print(f"  ... ({len(sim.log) - max_lines} more lines)")


# =============================================================================
# Presets: Known Speed Tunes
# =============================================================================
PRESETS = {
    # Position order matters! Position 1 = stun target (CB prefers pos 1).
    # Maneaters must NEVER be in pos 1.
    "easy_double_maneater": {
        "description": "Easy Double Maneater (no Pain Keeper)",
        "team": [
            ("DPS1", 177),        # Pos 1: stun target (lowest position = CB prefers)
            ("Maneater", 248),    # Pos 2: Fast ME — opens with A3
            ("Maneater", 219),    # Pos 3: Slow ME — opens with A2, then A3
            ("DPS2", 176),        # Pos 4
            ("DPS3", 175),        # Pos 5
        ],
        "openings": {
            2: ["A3", "A2"],        # Fast ME: A3 first
            3: ["A2", "A3"],        # Slow ME: delay A3
        },
        "notes": "Both ME fully booked. DPS pos 1 = stun target. Fast ME needs 241+ for 4:3 ratio.",
    },
    "budget_maneater": {
        "description": "Budget Maneater with Pain Keeper",
        "team": [
            ("Stun Target", 118), # Pos 1: slow stun target (111-118 SPD)
            ("Maneater", 228),    # Pos 2: Fast ME — opens with A3 (212-229)
            ("Maneater", 215),    # Pos 3: Slow ME — delays A3 (210-229)
            ("Pain Keeper", 176), # Pos 4: CD reducer
            ("DPS", 176),         # Pos 5: DPS (171-189)
        ],
        "openings": {
            2: ["A3"],            # Fast ME opens with A3
            3: ["A1", "A3"],      # Slow ME delays A3 by 1 turn
        },
        "notes": "ME range: 212-229 (153 valid pairs). PK 176. Stun target 111-118. All fully booked.",
    },
}


# =============================================================================
# Main
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="CB Speed Tune Calculator")
    parser.add_argument("--preset", choices=list(PRESETS.keys()),
                        help="Use a known speed tune preset")
    parser.add_argument("--speeds", nargs="+", type=float,
                        help="Manual speeds: ME1 ME2 DPS1 DPS2 DPS3")
    parser.add_argument("--names", nargs="+",
                        help="Champion names (default: Maneater Maneater DPS DPS DPS)")
    parser.add_argument("--sweep", action="store_true",
                        help="Sweep speed ranges to find valid tunes")
    parser.add_argument("--difficulty", default="unm", choices=list(CB_SPEEDS.keys()),
                        help="CB difficulty (default: unm)")
    parser.add_argument("--affinity", default="void",
                        choices=["void", "force", "magic", "spirit"],
                        help="CB affinity (default: void)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show turn-by-turn log")
    parser.add_argument("--turns", type=int, default=MAX_CB_TURNS,
                        help="Number of CB turns to simulate")
    args = parser.parse_args()

    cb_speed = CB_SPEEDS[args.difficulty]
    print(f"=== CB Speed Tune Calculator ===")
    print(f"Difficulty: {args.difficulty.upper()} (CB speed: {cb_speed})")
    print(f"Affinity: {args.affinity}")
    print()

    openings = {}
    if args.preset:
        preset = PRESETS[args.preset]
        print(f"Preset: {preset['description']}")
        print(f"Notes: {preset['notes']}")
        specs = preset["team"]
        openings = preset.get("openings", {})
    elif args.speeds:
        names = args.names or ["Maneater", "Maneater", "DPS1", "DPS2", "DPS3"]
        if len(names) != len(args.speeds):
            print(f"Error: {len(names)} names but {len(args.speeds)} speeds")
            return
        specs = list(zip(names, args.speeds))
    else:
        # Default: Easy Double Maneater
        print("Using Easy Double Maneater preset (use --preset or --speeds to customize)")
        specs = PRESETS["easy_double_maneater"]["team"]

    if args.sweep:
        team_names = [name for name, _ in specs]
        valid = find_valid_speeds(team_names, cb_speed=cb_speed, affinity=args.affinity,
                                  openings=openings)
        if valid:
            print(f"\nSample valid tunes:")
            for v in valid[:10]:
                speeds_str = ", ".join(f"{k}={v}" for k, v in v["speeds"].items())
                print(f"  {speeds_str}")
                print(f"    Turns: {v['champion_turns']}")
        else:
            print("\nNo valid tunes found in the given speed ranges!")
        return

    # Single simulation
    print(f"Team: {', '.join(f'{n}({s})' for n, s in specs)}")

    team = build_team(specs, openings=openings)
    sim = SpeedTuneSimulator(team, cb_speed=cb_speed, affinity=args.affinity,
                             verbose=args.verbose or True)
    result = sim.run(max_cb_turns=args.turns)
    print_turn_log(result, sim, max_lines=200 if args.verbose else 60)


if __name__ == "__main__":
    main()
