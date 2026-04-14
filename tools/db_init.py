#!/usr/bin/env python3
"""
Comprehensive SQLite database for PyAutoRaid CB optimization.

Creates and populates pyautoraid.db from all JSON data files.
Run: python3 tools/db_init.py [--db path] [--data-dir path]
"""

import json
import os
import sqlite3
import sys
import argparse
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from gear_constants import (
    SLOT_NAMES, STAT_NAMES, SET_NAMES, SET_BONUSES, SPECIAL_SETS,
    ACCESSORY_SLOTS,
)
from status_effect_map import STATUS_EFFECT_MAP


# =============================================================================
# Schema
# =============================================================================

SCHEMA_SQL = """
-- Reference tables
CREATE TABLE IF NOT EXISTS ref_stat_kinds (
    stat_id     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ref_artifact_sets (
    set_id          INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    pieces_needed   INTEGER,
    bonus_stat_id   INTEGER REFERENCES ref_stat_kinds(stat_id),
    bonus_value     REAL,
    bonus_stat2_id  INTEGER REFERENCES ref_stat_kinds(stat_id),
    bonus_value2    REAL,
    special_effect  TEXT
);

CREATE TABLE IF NOT EXISTS ref_status_effects (
    type_id     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    is_debuff   INTEGER NOT NULL DEFAULT 0,
    is_buff     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ref_slot_kinds (
    slot_id     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    is_accessory INTEGER NOT NULL DEFAULT 0
);

-- Heroes
CREATE TABLE IF NOT EXISTS heroes (
    id              INTEGER PRIMARY KEY,
    type_id         INTEGER NOT NULL,
    name            TEXT NOT NULL,
    grade           INTEGER NOT NULL,
    level           INTEGER NOT NULL,
    empower         INTEGER NOT NULL DEFAULT 0,
    fraction        INTEGER NOT NULL,
    rarity          INTEGER NOT NULL,
    element         INTEGER NOT NULL,
    role            INTEGER NOT NULL,
    base_hp         REAL, base_atk    REAL, base_def    REAL, base_spd    REAL,
    base_res        REAL, base_acc    REAL, base_cr     REAL, base_cd     REAL,
    masteries       TEXT,
    mastery_count   INTEGER DEFAULT 0,
    fetched_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_heroes_type_id ON heroes(type_id);
CREATE INDEX IF NOT EXISTS idx_heroes_grade ON heroes(grade);
CREATE INDEX IF NOT EXISTS idx_heroes_name ON heroes(name);

-- Hero computed stats (from game API)
CREATE TABLE IF NOT EXISTS hero_computed_stats (
    hero_id     INTEGER PRIMARY KEY,
    base_hp     REAL, base_atk    REAL, base_def    REAL, base_spd    REAL,
    base_res    REAL, base_acc    REAL, base_cr     REAL, base_cd     REAL,
    bless_hp    REAL DEFAULT 0, bless_atk   REAL DEFAULT 0, bless_def   REAL DEFAULT 0,
    emp_hp      REAL DEFAULT 0, emp_atk     REAL DEFAULT 0, emp_def     REAL DEFAULT 0,
    arena_hp    REAL DEFAULT 0, arena_atk   REAL DEFAULT 0, arena_def   REAL DEFAULT 0,
    arena_spd   REAL DEFAULT 0,
    gh_hp       REAL DEFAULT 0, gh_atk      REAL DEFAULT 0, gh_def      REAL DEFAULT 0,
    gh_acc      REAL DEFAULT 0, gh_res      REAL DEFAULT 0, gh_cd       REAL DEFAULT 0,
    fetched_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
);

-- Artifacts
CREATE TABLE IF NOT EXISTS artifacts (
    id              INTEGER PRIMARY KEY,
    level           INTEGER NOT NULL,
    kind            INTEGER NOT NULL REFERENCES ref_slot_kinds(slot_id),
    rank            INTEGER NOT NULL,
    rarity          INTEGER NOT NULL,
    set_id          INTEGER NOT NULL,
    hero_id         INTEGER,
    primary_stat    INTEGER NOT NULL,
    primary_value   REAL NOT NULL,
    primary_flat    INTEGER NOT NULL,
    pct_hp  REAL DEFAULT 0, pct_atk REAL DEFAULT 0, pct_def REAL DEFAULT 0,
    pct_spd REAL DEFAULT 0, pct_res REAL DEFAULT 0, pct_acc REAL DEFAULT 0,
    pct_cr  REAL DEFAULT 0, pct_cd  REAL DEFAULT 0,
    flat_hp REAL DEFAULT 0, flat_atk REAL DEFAULT 0, flat_def REAL DEFAULT 0,
    flat_spd REAL DEFAULT 0,
    fetched_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_artifacts_hero ON artifacts(hero_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_set ON artifacts(set_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_kind ON artifacts(kind);
CREATE INDEX IF NOT EXISTS idx_artifacts_unequipped ON artifacts(hero_id) WHERE hero_id IS NULL;

-- Artifact substats
CREATE TABLE IF NOT EXISTS artifact_substats (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_id INTEGER NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    stat_id     INTEGER NOT NULL REFERENCES ref_stat_kinds(stat_id),
    value       REAL NOT NULL,
    is_flat     INTEGER NOT NULL,
    rolls       INTEGER NOT NULL DEFAULT 0,
    glyph       REAL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_substats_artifact ON artifact_substats(artifact_id);
CREATE INDEX IF NOT EXISTS idx_substats_stat_value ON artifact_substats(stat_id, value);

-- Skills
CREATE TABLE IF NOT EXISTS skills (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    hero_type_id    INTEGER NOT NULL,
    skill_type_id   INTEGER NOT NULL,
    level           INTEGER NOT NULL DEFAULT 1,
    is_a1           INTEGER NOT NULL DEFAULT 0,
    cooldown        INTEGER,
    skill_type      TEXT,
    multiplier      REAL,
    scaling_stat    TEXT,
    hits            INTEGER DEFAULT 1,
    name            TEXT,
    description     TEXT,
    UNIQUE(hero_type_id, skill_type_id)
);
CREATE INDEX IF NOT EXISTS idx_skills_hero_type ON skills(hero_type_id);

-- Skill effects
CREATE TABLE IF NOT EXISTS skill_effects (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id        INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    effect_kind     INTEGER NOT NULL,
    effect_count    INTEGER DEFAULT 1,
    formula         TEXT,
    tag             TEXT,
    sort_order      INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_skill_effects_skill ON skill_effects(skill_id);
CREATE INDEX IF NOT EXISTS idx_skill_effects_kind ON skill_effects(effect_kind);

-- Skill status effects (debuffs/buffs placed by skills)
CREATE TABLE IF NOT EXISTS skill_status_effects (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_effect_id INTEGER NOT NULL REFERENCES skill_effects(id) ON DELETE CASCADE,
    status_type_id  INTEGER NOT NULL,
    duration        INTEGER NOT NULL,
    chance          INTEGER DEFAULT 100,
    name            TEXT
);
CREATE INDEX IF NOT EXISTS idx_sse_effect ON skill_status_effects(skill_effect_id);
CREATE INDEX IF NOT EXISTS idx_sse_type ON skill_status_effects(status_type_id);

-- Skill level bonuses
CREATE TABLE IF NOT EXISTS skill_level_bonuses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id        INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    level           INTEGER NOT NULL,
    bonus_type      INTEGER NOT NULL,
    bonus_value     REAL NOT NULL
);

-- Account
CREATE TABLE IF NOT EXISTS account (
    id              INTEGER PRIMARY KEY DEFAULT 1,
    arena_league    INTEGER,
    arena_points    INTEGER,
    clan_level      INTEGER,
    account_level   INTEGER,
    fetched_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
);

CREATE TABLE IF NOT EXISTS great_hall (
    element     INTEGER NOT NULL,
    stat_id     INTEGER NOT NULL REFERENCES ref_stat_kinds(stat_id),
    level       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (element, stat_id)
);

-- Teams
CREATE TABLE IF NOT EXISTS teams (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    tune_name   TEXT,
    boss_difficulty TEXT DEFAULT 'UNM',
    is_unkillable INTEGER DEFAULT 0,
    notes       TEXT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
);

CREATE TABLE IF NOT EXISTS team_members (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id         INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    hero_id         INTEGER REFERENCES heroes(id),
    hero_type_id    INTEGER NOT NULL,
    hero_name       TEXT NOT NULL,
    slot            INTEGER NOT NULL,
    target_spd_min  INTEGER,
    target_spd_max  INTEGER,
    actual_spd      REAL,
    role_label      TEXT,
    UNIQUE(team_id, slot)
);
CREATE INDEX IF NOT EXISTS idx_team_members_team ON team_members(team_id);

-- Sim runs
CREATE TABLE IF NOT EXISTS sim_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id         INTEGER REFERENCES teams(id),
    boss_difficulty TEXT DEFAULT 'UNM',
    cb_element      TEXT DEFAULT 'void',
    force_affinity  INTEGER DEFAULT 1,
    max_turns       INTEGER DEFAULT 50,
    total_damage    INTEGER,
    turns_survived  INTEGER,
    damage_breakdown TEXT,
    hero_damages    TEXT,
    valid_tune      INTEGER,
    errors          TEXT,
    run_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_sim_runs_team ON sim_runs(team_id);

-- Battle sessions
CREATE TABLE IF NOT EXISTS battle_sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id         INTEGER REFERENCES teams(id),
    boss_difficulty TEXT,
    scene           TEXT,
    total_turns     INTEGER,
    total_polls     INTEGER,
    total_damage    INTEGER,
    source_file     TEXT,
    recorded_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
);

-- Battle turns
CREATE TABLE IF NOT EXISTS battle_turns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL REFERENCES battle_sessions(id) ON DELETE CASCADE,
    turn_number     INTEGER NOT NULL,
    poll_number     INTEGER,
    active_hero_slot INTEGER
);
CREATE INDEX IF NOT EXISTS idx_battle_turns_session ON battle_turns(session_id);

-- Battle hero states (per-turn per-hero snapshot)
CREATE TABLE IF NOT EXISTS battle_hero_states (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id         INTEGER NOT NULL REFERENCES battle_turns(id) ON DELETE CASCADE,
    side            TEXT NOT NULL,
    battle_slot     INTEGER NOT NULL,
    type_id         INTEGER NOT NULL,
    hp_max          INTEGER,
    hp_cur          INTEGER,
    hp_lost         INTEGER,
    hp_pct          INTEGER,
    tm              INTEGER,
    dmg_taken       INTEGER,
    turn_n          INTEGER,
    can_atk         INTEGER,
    active_flags    TEXT,
    stat_mods       TEXT,
    absorbed_dmg    TEXT,
    skills_json     TEXT
);
CREATE INDEX IF NOT EXISTS idx_bhs_turn ON battle_hero_states(turn_id);
CREATE INDEX IF NOT EXISTS idx_bhs_type ON battle_hero_states(type_id);
"""


# =============================================================================
# Reference table seeding
# =============================================================================

def seed_reference_tables(conn):
    """Seed ref tables from gear_constants.py and status_effect_map.py."""
    c = conn.cursor()

    # Stat kinds
    for stat_id, name in STAT_NAMES.items():
        c.execute("INSERT OR REPLACE INTO ref_stat_kinds (stat_id, name) VALUES (?, ?)",
                  (stat_id, name))

    # Slot kinds
    for slot_id, name in SLOT_NAMES.items():
        is_acc = 1 if slot_id in ACCESSORY_SLOTS else 0
        c.execute("INSERT OR REPLACE INTO ref_slot_kinds (slot_id, name, is_accessory) VALUES (?, ?, ?)",
                  (slot_id, name, is_acc))

    # Artifact sets
    for set_id, name in SET_NAMES.items():
        pieces = None
        bonus_stat = None
        bonus_val = None
        bonus_stat2 = None
        bonus_val2 = None
        special = SPECIAL_SETS.get(set_id)

        if set_id in SET_BONUSES:
            pieces, bonuses = SET_BONUSES[set_id]
            stats = list(bonuses.items())
            if len(stats) >= 1:
                bonus_stat, bonus_val = stats[0]
            if len(stats) >= 2:
                bonus_stat2, bonus_val2 = stats[1]
        elif special:
            # Special sets: pieces_needed varies (most are 4-piece)
            pieces = 4 if set_id not in SET_BONUSES else 2

        c.execute("""INSERT OR REPLACE INTO ref_artifact_sets
                     (set_id, name, pieces_needed, bonus_stat_id, bonus_value,
                      bonus_stat2_id, bonus_value2, special_effect)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                  (set_id, name, pieces, bonus_stat, bonus_val,
                   bonus_stat2, bonus_val2, special))

    # Status effects
    for type_id, (name, is_debuff, is_buff) in STATUS_EFFECT_MAP.items():
        c.execute("""INSERT OR REPLACE INTO ref_status_effects
                     (type_id, name, is_debuff, is_buff) VALUES (?, ?, ?, ?)""",
                  (type_id, name, int(is_debuff), int(is_buff)))

    conn.commit()
    print(f"  ref_stat_kinds: {len(STAT_NAMES)} rows")
    print(f"  ref_slot_kinds: {len(SLOT_NAMES)} rows")
    print(f"  ref_artifact_sets: {len(SET_NAMES)} rows")
    print(f"  ref_status_effects: {len(STATUS_EFFECT_MAP)} rows")


# =============================================================================
# Heroes
# =============================================================================

def import_heroes(conn, data_dir):
    """Import heroes from heroes_all.json."""
    path = data_dir / "heroes_all.json"
    if not path.exists():
        print(f"  SKIP heroes: {path} not found")
        return 0

    data = json.loads(path.read_text())
    heroes = data.get("heroes", data) if isinstance(data, dict) else data
    c = conn.cursor()
    c.execute("DELETE FROM heroes")

    count = 0
    for h in heroes:
        bs = h.get("base_stats", {})
        masteries_list = h.get("masteries", [])
        mastery_count = h.get("mastery_count", len(masteries_list) if isinstance(masteries_list, list) else 0)

        c.execute("""INSERT OR REPLACE INTO heroes
                     (id, type_id, name, grade, level, empower, fraction, rarity, element, role,
                      base_hp, base_atk, base_def, base_spd, base_res, base_acc, base_cr, base_cd,
                      masteries, mastery_count)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (h["id"], h["type_id"], h.get("name", ""), h["grade"], h["level"],
                   h.get("empower", 0), h.get("fraction", 0), h.get("rarity", 0),
                   h.get("element", 0), h.get("role", 0),
                   bs.get("HP"), bs.get("ATK"), bs.get("DEF"), bs.get("SPD"),
                   bs.get("RES"), bs.get("ACC"), bs.get("CR"), bs.get("CD"),
                   json.dumps(masteries_list) if masteries_list else None,
                   mastery_count))
        count += 1

    conn.commit()
    print(f"  heroes: {count} rows")
    return count


# =============================================================================
# Computed stats
# =============================================================================

def import_computed_stats(conn, data_dir):
    """Import from hero_computed_stats.json."""
    path = data_dir / "hero_computed_stats.json"
    if not path.exists():
        print(f"  SKIP computed_stats: {path} not found")
        return 0

    data = json.loads(path.read_text())
    heroes = data.get("heroes", data) if isinstance(data, dict) else data
    if isinstance(heroes, dict):
        heroes = list(heroes.values())

    c = conn.cursor()
    c.execute("DELETE FROM hero_computed_stats")

    count = 0
    for h in heroes:
        hid = h.get("id")
        if not hid:
            continue
        bc = h.get("base_computed", {})
        bl = h.get("blessing_bonus", {})
        em = h.get("empower_bonus", {})
        ar = h.get("arena_bonus", {})
        gh = h.get("great_hall_bonus", {})

        c.execute("""INSERT OR REPLACE INTO hero_computed_stats
                     (hero_id,
                      base_hp, base_atk, base_def, base_spd, base_res, base_acc, base_cr, base_cd,
                      bless_hp, bless_atk, bless_def,
                      emp_hp, emp_atk, emp_def,
                      arena_hp, arena_atk, arena_def, arena_spd,
                      gh_hp, gh_atk, gh_def, gh_acc, gh_res, gh_cd)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (hid,
                   bc.get("HP"), bc.get("ATK"), bc.get("DEF"), bc.get("SPD"),
                   bc.get("RES"), bc.get("ACC"), bc.get("CR"), bc.get("CD"),
                   bl.get("HP", 0), bl.get("ATK", 0), bl.get("DEF", 0),
                   em.get("HP", 0), em.get("ATK", 0), em.get("DEF", 0),
                   ar.get("HP", 0), ar.get("ATK", 0), ar.get("DEF", 0), ar.get("SPD", 0),
                   gh.get("HP", 0), gh.get("ATK", 0), gh.get("DEF", 0),
                   gh.get("ACC", 0), gh.get("RES", 0), gh.get("CD", 0)))
        count += 1

    conn.commit()
    print(f"  hero_computed_stats: {count} rows")
    return count


# =============================================================================
# Artifacts
# =============================================================================

def import_artifacts(conn, data_dir):
    """Import from all_artifacts.json."""
    path = data_dir / "all_artifacts.json"
    if not path.exists():
        print(f"  SKIP artifacts: {path} not found")
        return 0

    data = json.loads(path.read_text())
    artifacts = data.get("artifacts", data) if isinstance(data, dict) else data

    c = conn.cursor()
    c.execute("DELETE FROM artifact_substats")
    c.execute("DELETE FROM artifacts")

    art_count = 0
    sub_count = 0
    for a in artifacts:
        pri = a.get("primary", {})
        pct = a.get("pct_bonus", {})
        flat = a.get("flat_bonus", {})
        hero_id = a.get("hero_id")
        if hero_id == 0:
            hero_id = None

        c.execute("""INSERT OR REPLACE INTO artifacts
                     (id, level, kind, rank, rarity, set_id, hero_id,
                      primary_stat, primary_value, primary_flat,
                      pct_hp, pct_atk, pct_def, pct_spd, pct_res, pct_acc, pct_cr, pct_cd,
                      flat_hp, flat_atk, flat_def, flat_spd)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (a["id"], a.get("level", 0), a["kind"], a.get("rank", 1),
                   a.get("rarity", 1), a.get("set", 0), hero_id,
                   pri.get("stat", 0), pri.get("value", 0), int(pri.get("flat", True)),
                   pct.get("HP", 0), pct.get("ATK", 0), pct.get("DEF", 0), pct.get("SPD", 0),
                   pct.get("RES", 0), pct.get("ACC", 0), pct.get("CR", 0), pct.get("CD", 0),
                   flat.get("HP", 0), flat.get("ATK", 0), flat.get("DEF", 0), flat.get("SPD", 0)))
        art_count += 1

        for sub in a.get("substats", []):
            c.execute("""INSERT INTO artifact_substats
                         (artifact_id, stat_id, value, is_flat, rolls, glyph)
                         VALUES (?, ?, ?, ?, ?, ?)""",
                      (a["id"], sub["stat"], sub["value"], int(sub.get("flat", False)),
                       sub.get("rolls", 0), sub.get("glyph", 0)))
            sub_count += 1

    conn.commit()
    print(f"  artifacts: {art_count} rows")
    print(f"  artifact_substats: {sub_count} rows")
    return art_count


# =============================================================================
# Skills
# =============================================================================

def import_skills(conn, data_dir):
    """Import from skills_db.json + enrich from hero_profiles_game.json."""
    skills_path = data_dir / "skills_db.json"
    profiles_path = data_dir / "hero_profiles_game.json"

    if not skills_path.exists():
        print(f"  SKIP skills: {skills_path} not found")
        return 0

    skills_db = json.loads(skills_path.read_text())

    # Load profiles for enrichment
    profiles = {}
    if profiles_path.exists():
        profiles = json.loads(profiles_path.read_text())

    c = conn.cursor()
    c.execute("DELETE FROM skill_level_bonuses")
    c.execute("DELETE FROM skill_status_effects")
    c.execute("DELETE FROM skill_effects")
    c.execute("DELETE FROM skills")

    skill_count = 0
    effect_count = 0
    sse_count = 0

    # Build profile skill lookup: {(hero_type_id, skill_type_id): profile_skill}
    profile_skills = {}
    for hero_name, prof in profiles.items():
        type_id = prof.get("type_id")
        if not type_id:
            continue
        for sk in prof.get("skills", []):
            sid = sk.get("id")
            if sid:
                profile_skills[(type_id, sid)] = sk

    for hero_name, skill_list in skills_db.items():
        for sk in skill_list:
            hero_type_id = sk.get("hero_id", 0)
            skill_type_id = sk.get("skill_type_id", 0)
            is_a1 = int(sk.get("is_a1", False))

            # Get enrichment from game profiles
            prof_sk = profile_skills.get((hero_type_id, skill_type_id), {})
            multiplier = prof_sk.get("mult")
            scaling_stat = prof_sk.get("stat")
            hits = prof_sk.get("hits", 1)
            cooldown = prof_sk.get("cooldown") or sk.get("cooldown")
            skill_type = prof_sk.get("type")  # "A1", "active", "passive"

            skill_name = sk.get("name") or prof_sk.get("name")
            skill_desc = sk.get("desc")

            c.execute("""INSERT OR REPLACE INTO skills
                         (hero_type_id, skill_type_id, level, is_a1, cooldown,
                          skill_type, multiplier, scaling_stat, hits, name, description)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                      (hero_type_id, skill_type_id, sk.get("level", 1), is_a1,
                       cooldown, skill_type, multiplier, scaling_stat, hits,
                       skill_name, skill_desc))
            skill_id = c.lastrowid
            skill_count += 1

            # Effects (from skills_db)
            for idx, eff in enumerate(sk.get("effects", [])):
                # Get tag from profile if available
                prof_effects = prof_sk.get("effects", [])
                tag = prof_effects[idx].get("tag") if idx < len(prof_effects) else None

                c.execute("""INSERT INTO skill_effects
                             (skill_id, effect_kind, effect_count, formula, tag, sort_order)
                             VALUES (?, ?, ?, ?, ?, ?)""",
                          (skill_id, eff.get("kind", 0), eff.get("count", 1),
                           eff.get("formula"), tag, idx))
                eff_id = c.lastrowid
                effect_count += 1

                # Status effects within this effect
                for se in eff.get("status_effects", []):
                    se_type = se.get("type", 0)
                    se_name = se.get("name")
                    # Resolve name from status_effect_map if available
                    if not se_name or se_name.startswith("se_"):
                        mapped = STATUS_EFFECT_MAP.get(se_type)
                        if mapped:
                            se_name = mapped[0]

                    c.execute("""INSERT INTO skill_status_effects
                                 (skill_effect_id, status_type_id, duration, chance, name)
                                 VALUES (?, ?, ?, ?, ?)""",
                              (eff_id, se_type, se.get("duration", 1),
                               se.get("chance", 100), se_name))
                    sse_count += 1

            # Level bonuses
            for lvl_idx, lb in enumerate(sk.get("level_bonuses", [])):
                c.execute("""INSERT INTO skill_level_bonuses
                             (skill_id, level, bonus_type, bonus_value)
                             VALUES (?, ?, ?, ?)""",
                          (skill_id, lvl_idx + 2, lb.get("type", 0), lb.get("value", 0)))

    conn.commit()
    print(f"  skills: {skill_count} rows")
    print(f"  skill_effects: {effect_count} rows")
    print(f"  skill_status_effects: {sse_count} rows")
    return skill_count


# =============================================================================
# Account
# =============================================================================

def import_account(conn, data_dir):
    """Import from account_data.json."""
    path = data_dir / "account_data.json"
    if not path.exists():
        print(f"  SKIP account: {path} not found")
        return

    data = json.loads(path.read_text())
    c = conn.cursor()

    arena = data.get("arena", {})
    clan = data.get("clan", {})
    c.execute("""INSERT OR REPLACE INTO account
                 (id, arena_league, arena_points, clan_level, account_level)
                 VALUES (1, ?, ?, ?, ?)""",
              (arena.get("league"), arena.get("points"),
               clan.get("level"), data.get("account_level")))

    c.execute("DELETE FROM great_hall")
    gh = data.get("great_hall", {})
    gh_count = 0
    for element_str, stats in gh.items():
        element = int(element_str)
        for stat_str, level in stats.items():
            stat_id = int(stat_str)
            c.execute("""INSERT OR REPLACE INTO great_hall (element, stat_id, level)
                         VALUES (?, ?, ?)""", (element, stat_id, level))
            gh_count += 1

    conn.commit()
    print(f"  account: 1 row")
    print(f"  great_hall: {gh_count} rows")


# =============================================================================
# Battle logs
# =============================================================================

def import_battle_log(conn, log_path):
    """Import a single battle log file into battle_sessions/turns/hero_states."""
    path = Path(log_path)
    if not path.exists():
        print(f"  SKIP battle log: {path} not found")
        return 0

    data = json.loads(path.read_text())

    # Handle both formats: {log: [...]} or bare list
    if isinstance(data, dict):
        log_entries = data.get("log", [])
        total_turns = data.get("turns", 0)
        total_polls = data.get("polls", 0)
    else:
        log_entries = data
        total_turns = 0
        total_polls = 0

    c = conn.cursor()

    # Find total damage from last poll with boss data
    total_damage = 0
    scene = None
    for entry in reversed(log_entries):
        if "heroes" in entry:
            if not scene:
                scene = entry.get("scene")
            for h in entry["heroes"]:
                if h.get("side") == "enemy":
                    total_damage = max(total_damage, h.get("dmg_taken", 0))
                    break
            if total_damage > 0:
                break

    c.execute("""INSERT INTO battle_sessions
                 (boss_difficulty, scene, total_turns, total_polls, total_damage, source_file)
                 VALUES (?, ?, ?, ?, ?, ?)""",
              ("UNM", scene, total_turns, total_polls, total_damage, path.name))
    session_id = c.lastrowid

    turn_count = 0
    state_count = 0
    current_turn_id = None
    last_turn_num = -1

    for entry in log_entries:
        # Skip diagnostic entries
        if "diag" in entry:
            continue

        poll = entry.get("poll")
        turn_num = entry.get("turn", 0)
        heroes = entry.get("heroes")

        if heroes is None:
            continue

        # Create a new battle_turn row when turn number changes
        if turn_num != last_turn_num:
            c.execute("""INSERT INTO battle_turns
                         (session_id, turn_number, poll_number)
                         VALUES (?, ?, ?)""",
                      (session_id, turn_num, poll))
            current_turn_id = c.lastrowid
            last_turn_num = turn_num
            turn_count += 1

        # Insert hero states
        for h in heroes:
            # Extract flags
            flags = h.get("st", [])
            if not flags:
                flags = []
                # Build from boolean properties
                for flag in ["dead", "dying", "stun", "freeze", "sleep"]:
                    if h.get(flag):
                        flags.append(flag)

            # Skills as JSON
            skills_data = h.get("sk", [])

            c.execute("""INSERT INTO battle_hero_states
                         (turn_id, side, battle_slot, type_id,
                          hp_max, hp_cur, hp_lost, hp_pct, tm, dmg_taken, turn_n,
                          can_atk, active_flags, stat_mods, absorbed_dmg, skills_json)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                      (current_turn_id, h.get("side", "player"), h.get("id", 0),
                       h.get("type_id", 0),
                       h.get("hp_max"), h.get("hp_cur"), h.get("hp_lost"),
                       h.get("hp_pct"), h.get("tm"), h.get("dmg_taken"),
                       h.get("turn_n"),
                       int(h.get("can_atk", True)),
                       json.dumps(flags) if flags else None,
                       json.dumps(h.get("mods")) if h.get("mods") else None,
                       json.dumps(h.get("abs")) if h.get("abs") else None,
                       json.dumps(skills_data) if skills_data else None))
            state_count += 1

    conn.commit()
    print(f"  battle_session: {path.name} ({turn_count} turns, {state_count} hero states, {total_damage:,} total dmg)")
    return turn_count


# =============================================================================
# Orchestrator
# =============================================================================

def create_schema(conn):
    """Create all tables and indexes."""
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def import_all(db_path=None, data_dir=None):
    """Full import of all data files into the database."""
    if data_dir is None:
        data_dir = PROJECT_ROOT
    else:
        data_dir = Path(data_dir)

    if db_path is None:
        db_path = data_dir / "pyautoraid.db"
    else:
        db_path = Path(db_path)

    print(f"Database: {db_path}")
    print(f"Data dir: {data_dir}")
    print()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    print("Creating schema...")
    create_schema(conn)

    print("\nSeeding reference tables...")
    seed_reference_tables(conn)

    print("\nImporting heroes...")
    import_heroes(conn, data_dir)

    print("\nImporting computed stats...")
    import_computed_stats(conn, data_dir)

    print("\nImporting artifacts...")
    import_artifacts(conn, data_dir)

    print("\nImporting skills...")
    import_skills(conn, data_dir)

    print("\nImporting account...")
    import_account(conn, data_dir)

    # Import all battle logs
    print("\nImporting battle logs...")
    log_files = sorted(data_dir.glob("battle_logs_cb_*.json"))
    if log_files:
        # Clear existing battle data
        c = conn.cursor()
        c.execute("DELETE FROM battle_hero_states")
        c.execute("DELETE FROM battle_turns")
        c.execute("DELETE FROM battle_sessions")
        conn.commit()

        for lf in log_files:
            import_battle_log(conn, lf)
    else:
        print("  No battle log files found")

    # Summary
    print("\n" + "=" * 50)
    print("IMPORT COMPLETE — Summary:")
    c = conn.cursor()
    tables = [
        "heroes", "hero_computed_stats", "artifacts", "artifact_substats",
        "skills", "skill_effects", "skill_status_effects",
        "great_hall", "battle_sessions", "battle_turns", "battle_hero_states",
    ]
    for t in tables:
        c.execute(f"SELECT COUNT(*) FROM {t}")
        print(f"  {t}: {c.fetchone()[0]:,}")

    conn.close()
    print(f"\nDatabase saved to: {db_path}")
    return db_path


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Initialize PyAutoRaid database")
    parser.add_argument("--db", default=None, help="Database path (default: <data-dir>/pyautoraid.db)")
    parser.add_argument("--data-dir", default=None, help="Data directory (default: project root)")
    args = parser.parse_args()

    import_all(db_path=args.db, data_dir=args.data_dir)


if __name__ == "__main__":
    main()
