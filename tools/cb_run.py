#!/usr/bin/env python3
"""
CB Battle Runner — one command to run a CB fight and capture results.

Navigates to CB, starts battle via mod API (no UI), polls until complete,
saves battle log, runs calibration, stores results.

Usage:
    python3 tools/cb_run.py                          # run with current team
    python3 tools/cb_run.py --cb-element force       # specify today's affinity
    python3 tools/cb_run.py --calibrate              # also run sim calibration
    python3 tools/cb_run.py --team "ME,Demytha,..."  # override team for calibration
"""

import json
import sys
import time
import argparse
import requests
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

MOD_BASE = "http://localhost:6790"
POLL_INTERVAL = 20  # seconds between battle state polls
MAX_POLLS = 50      # ~16 minutes max


def mod_get(endpoint, params=None, timeout=15):
    """GET request to mod API."""
    try:
        r = requests.get(f"{MOD_BASE}{endpoint}", params=params, timeout=timeout)
        return r.json()
    except Exception as ex:
        return {"error": str(ex)}


def check_ready():
    """Check if mod is up and game is logged in."""
    status = mod_get("/status")
    if "error" in status:
        print(f"Mod not reachable: {status['error']}")
        return False
    if not status.get("logged_in"):
        print(f"Not logged in: scene={status.get('scene')}")
        return False
    print(f"Mod ready: scene={status.get('scene')}")
    return True


def check_keys():
    """Check available CB keys."""
    res = mod_get("/resources")
    keys = res.get("cb_keys", 0)
    print(f"CB keys: {keys}")
    return keys


def unwind_post_battle_state():
    """Dismiss any lingering BattleFinish / MessageBox / reward-cascade
    dialogs left over from a previous CB key. Called at the start of each
    start_battle() so the second/third key starts from a clean
    AllianceEnemiesDialog state.

    Bug history:
      - 2026-05-16: BattleFinishAllianceEnemyDialog stuck → key 2 silent fail
      - 2026-05-22/23: only 1 of 2 keys per day; same pattern. Added more
        dialog types since post-key-1 the cascade now includes things like
        AllianceCheckInOverlay, PrizeInfoOverlay, etc.
      - 2026-05-24: ROOT CAUSE confirmed. The mod's context-call
        CreateAllianceBossBattleCmd dispatch works correctly; the failure
        mode is STUCK error MessageBox from prior attempts (e.g.
        Arena_OpponentAlreadyDefeated cascading) that block new cmds
        from reaching the server. Aggressive MessageBox dismissal + dialog
        close gets us back to a clean state. Verified: with clean state,
        2 keys → 16.89M on leaderboard."""
    import urllib.parse
    # 0a. PRIORITY: check OverlayManager bookkeeping. If a CoroutineTask
    #     exception orphaned an overlay counter, every UI write silently
    #     no-ops. /overlay-close-all resets the count dictionary without
    #     a Raid restart. See project_overlay_manager_wedge.md.
    try:
        s = requests.get(f"{MOD_BASE}/overlay-state", timeout=5).json()
        opened = s.get("opened") or []
        blocked = bool(s.get("block_ui_state"))
        if opened or blocked:
            print(f"  overlay wedge detected: opened={[o.get('key') for o in opened]} blocked={blocked}")
            requests.get(f"{MOD_BASE}/overlay-close-all", timeout=8)
            time.sleep(1.0)
    except Exception:
        pass
    # 0b. PRIORITY: dismiss any MessageBox / ErrorBox. These are modal
    #     and block all subsequent dialog operations. Click the OK button
    #     repeatedly (server errors can stack).
    for _ in range(5):
        try:
            r = requests.get(f"{MOD_BASE}/messagebox-click?index=0",
                             timeout=8).json()
            if not r.get("ok"):
                break
            time.sleep(0.5)
        except Exception:
            break
    # 1. Close known post-battle dialogs (Dialogs container).
    #    Also close dungeon dialogs because a parallel dungeon farm
    #    (dungeon_run.py super-raid loop) can leave Raid stuck on
    #    DungeonHeroesSelectionDialog at the 04:15 MDT CB wake-up.
    #    Without this, /navigate?target=cb bounces silently and the
    #    scheduled CB run exits 0 with no keys spent (verified pattern
    #    on 2026-06-03 and 2026-06-04).
    for dialog_name in ("[DV] BattleFinishAllianceEnemyDialog",
                        "[DV] BattleFinishStoryDialog",
                        "[DV] BattleFinishDialog",
                        "[DV] DungeonHeroesSelectionDialog",
                        "[DV] DungeonsDialog",
                        "[DV] PortalDialog",
                        "[DV] QuestsDialog",
                        "[DV] CompleteQuestsDialog",
                        "[DV] ArenaDialog",
                        "[DV] ArenaHeroesSelectionDialog",
                        "[DV] ShopAggregatorDialog"):
        path = f"UIManager/Canvas (Ui Root)/Dialogs/{dialog_name}"
        encoded = urllib.parse.quote(path, safe='')
        try:
            r = requests.get(f"{MOD_BASE}/context-call?path={encoded}&method=Close",
                             timeout=10).json()
            if r.get("invoked") == "Close":
                print(f"  unwound {dialog_name}")
                time.sleep(2.0)
        except Exception:
            pass
    # 2. Close overlay-cascade dialogs (OverlayDialogs container). After CB
    #    win, the game can pop a PrizeInfo / LevelUp / Daily-quest-complete
    #    overlay sequence that blocks /navigate. Sweep all common ones.
    for overlay_name in ("[OV] PrizeInfoOverlay",
                         "[OV] LevelUpOverlay",
                         "[OV] CompletedDailyQuestOverlay",
                         "[OV] AggressiveOfferOverlay",
                         "[OV] GiftOfferOverlay",
                         "[OV] ComboOfferOverlay"):
        path = f"UIManager/Canvas (Ui Root)/OverlayDialogs/{overlay_name}"
        encoded = urllib.parse.quote(path, safe='')
        try:
            r = requests.get(f"{MOD_BASE}/context-call?path={encoded}&method=Close",
                             timeout=10).json()
            if r.get("invoked") == "Close":
                print(f"  unwound {overlay_name}")
                time.sleep(1.0)
        except Exception:
            pass
    # 3. Close any MessageBox stuck on screen (rare — usually from
    #    error popups e.g. CB chest-claim "no chest" errors).
    path = "UIManager/Canvas (Ui Root)/MessageBoxes/MessageBox"
    encoded = urllib.parse.quote(path, safe='')
    for _ in range(3):
        try:
            r = requests.get(f"{MOD_BASE}/context-call?path={encoded}&method=Close",
                             timeout=10).json()
            if r.get("invoked") != "Close":
                break
            print(f"  unwound MessageBox")
            time.sleep(1.0)
        except Exception:
            break


def start_battle():
    """Navigate to CB and start battle via context-calls. Returns True if battle started."""
    # Clean up any leftover dialogs from a previous key before navigating.
    unwind_post_battle_state()

    print("Navigating to CB...")
    r = mod_get("/navigate", {"target": "cb"})
    if "error" in r:
        print(f"  Navigate failed: {r['error']}")
        return False

    # Poll for the AllianceEnemiesDialog to actually appear before clicking it.
    # The post-navigate transition can take 5-10s on the first open of the day.
    for _ in range(15):
        time.sleep(1)
        ctxs = mod_get("/view-contexts").get("contexts") or []
        if any("AllianceEnemiesDialog" in (c.get("dialog") or "") for c in ctxs):
            break
    else:
        print("  AllianceEnemiesDialog did not appear after 15s")
        return False

    print("Opening team selection (OnStartClick)...")
    # Use curl-style URL (spaces as %20, brackets as %5B%5D)
    try:
        r = requests.get(
            f"{MOD_BASE}/context-call?"
            "path=UIManager/Canvas%20(Ui%20Root)/Dialogs/"
            "%5BDV%5D%20AllianceEnemiesDialog/Workspace/Content/RightPanel"
            "&method=OnStartClick",
            timeout=15
        )
        d = r.json()
        if "error" in d:
            print(f"  OnStartClick failed: {d['error']}")
            return False
        print(f"  OK: {d.get('invoked')}")
    except Exception as ex:
        print(f"  OnStartClick error: {ex}")
        return False

    # Poll for the AllianceBossHeroesSelectionDialog to be loaded.
    for _ in range(15):
        time.sleep(1)
        ctxs = mod_get("/view-contexts").get("contexts") or []
        if any("AllianceBossHeroesSelectionDialog" in (c.get("dialog") or "") for c in ctxs):
            break
    else:
        print("  AllianceBossHeroesSelectionDialog did not appear after 15s")
        return False

    # Force Quick Battle OFF before StartBattle. Quick Battle skips the
    # BattleScene transition, so the polling loop misses the per-poll
    # heroes[]/dmg_taken snapshots cb_calibrate.py needs. Wasted a UNM
    # key 2026-06-13 finding this out. Abort if we can't confirm OFF.
    qb = mod_get("/cb-quick-battle", {"value": "false"})
    if "error" in qb:
        print(f"  /cb-quick-battle failed: {qb['error']}")
        return False
    if qb.get("enabled") is not False:
        print(f"  Quick Battle still ON after toggle attempt: {qb}")
        return False
    print(f"  Quick Battle: OFF (changed={qb.get('changed')})")

    print("Starting battle (StartBattle)...")
    try:
        r = requests.get(
            f"{MOD_BASE}/context-call?"
            "path=UIManager/Canvas%20(Ui%20Root)/Dialogs/"
            "%5BDV%5D%20AllianceBossHeroesSelectionDialog"
            "&method=StartBattle",
            timeout=15
        )
        d = r.json()
        if "error" in d:
            print(f"  StartBattle failed: {d['error']}")
            return False
        print(f"  OK: {d.get('invoked')}")
    except Exception as ex:
        print(f"  StartBattle error: {ex}")
        return False

    # Wait for battle to actually start
    time.sleep(10)
    status = mod_get("/status")
    scene = status.get("scene", "")
    if "Dungeon_Clan" in scene or "Battle" in scene:
        print(f"Battle started! Scene: {scene}")
        return True

    # Check battle state as fallback
    bs = mod_get("/battle-state")
    if "error" not in bs:
        print("Battle started! (detected via battle-state)")
        return True

    print(f"Battle did not start. Scene: {scene}")
    return False


def _snapshot_battle_log(snapshot_path):
    """Best-effort fetch of /battle-log + /tick-log to disk. Used by
    poll_battle for crash-resilient incremental snapshots.
    Game crashes on scene transitions (Raid.exe APPCRASH in coreclr.dll
    has been a recurring pattern; see WER ReportArchive). Saving the
    log incrementally during polling means we always have data within
    one snapshot interval of the crash.
    """
    try:
        r = mod_get("/battle-log", timeout=10)
        if "error" not in r and r.get("log"):
            with open(snapshot_path, "w") as f:
                json.dump(r, f)
        # Also tick log if available
        tl = mod_get("/tick-log", timeout=10)
        if "error" not in tl and tl.get("ticks"):
            tick_path = str(snapshot_path).replace("battle_logs_cb_", "tick_log_cb_")
            with open(tick_path, "w") as f:
                json.dump(tl, f)
    except Exception:
        pass  # Crash-resilience: snapshot failure shouldn't break polling


def _poll_log_path(snapshot_path):
    """Derive poll_log_*.json companion path from a battle_logs_*.json
    snapshot path. The poll log captures per-poll /battle-state
    responses (heroes with buffs/debuffs/HP) which the saved
    battle_log + tick_log do NOT preserve. Required for cb_truth_diff
    per docs/cb_workstream_0_audit.md.
    """
    if not snapshot_path:
        return None
    return str(snapshot_path).replace("battle_logs_cb_", "poll_log_cb_")


def _append_poll_record(poll_log_path, record):
    """Append one poll record to the poll log as JSONL. Crash-resilient
    — if the process dies mid-battle, every poll up to the crash is
    durable on disk.
    """
    if not poll_log_path:
        return
    try:
        with open(poll_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, separators=(",", ":")) + "\n")
    except Exception:
        pass


def poll_battle(snapshot_path=None, snapshot_every_polls=20):
    """Poll until the battle is truly over.

    Previous version bailed as soon as /battle-state returned an error, which
    trips during scene transitions (post-battle result screen) while the real
    battle is still running. We now hold the loop open until we see any of:
      - `/status` reports a scene OTHER than Dungeon_Clan (result screen gone)
      - battle-log contains a `battle_end` event
      - `/battle-state` returns active=False AND heroes list is empty

    Transient `/battle-state` errors are tolerated (logged, not fatal).

    `snapshot_path`: when provided, /battle-log + /tick-log are saved
    to disk every `snapshot_every_polls` polls (default 20 = ~60s). This
    is crash-resilience: Raid.exe periodically crashes on scene
    transitions (APPCRASH in coreclr.dll) and the post-battle
    /battle-log fetch can return ConnectionRefused. Incremental
    snapshots ensure we have data within ~60s of the crash.

    Additionally writes a `poll_log_cb_*.json` JSONL companion with
    every /battle-state response per poll — this is the source of
    truth for cb_truth_diff per-CB-turn buff/debuff/HP state. The
    pure /battle-log endpoint emits only an event stream (skill_cmd /
    round events) and never includes hero state.
    """
    print("\nPolling battle progress...")
    prev_turn = 0
    final_dmg = 0
    final_turn = 0
    transient_err_streak = 0
    no_progress_polls = 0
    MAX_TRANSIENT = 10
    poll_log_path = _poll_log_path(snapshot_path)
    # Truncate any stale poll log at start (one battle = one poll log)
    if poll_log_path:
        try:
            Path(poll_log_path).write_text("", encoding="utf-8")
        except Exception:
            pass

    for i in range(MAX_POLLS):
        # Crash-resilience snapshot. Fire on every Nth poll AND once
        # immediately when we first see transient errors (early hint
        # of scene transition, before the crash window).
        if snapshot_path and (i > 0 and i % snapshot_every_polls == 0):
            _snapshot_battle_log(snapshot_path)
        bs = mod_get("/battle-state")
        # Persist this poll (success or error) to poll_log for
        # post-hoc state diffs. JSONL = one entry per line.
        _append_poll_record(poll_log_path, {
            "poll": i,
            "ts": time.time(),
            "state": bs,
        })
        if "error" in bs:
            transient_err_streak += 1
            # FIRST transient error often precedes a scene-transition crash:
            # snapshot now while the mod is still up.
            if transient_err_streak == 1 and snapshot_path:
                _snapshot_battle_log(snapshot_path)
            if transient_err_streak >= MAX_TRANSIENT:
                # Likely real end — confirm by checking scene
                st = mod_get("/status")
                scene = (st or {}).get("scene", "")
                if scene != "Dungeon_Clan":
                    print(f"  Scene changed to {scene!r} — battle ended at poll {i}")
                    # One more snapshot before exiting (in case mod is still up)
                    if snapshot_path: _snapshot_battle_log(snapshot_path)
                    break
                # Scene still CB: just a glitch, keep polling
                transient_err_streak = 0
            time.sleep(POLL_INTERVAL)
            continue
        transient_err_streak = 0

        active = bs.get("active")
        heroes = bs.get("heroes", [])
        boss = next((h for h in heroes if h.get("side") == "enemy"), None)
        if boss is not None:
            turn = boss.get("turn_n", 0) or 0
            dmg = boss.get("dmg_taken", 0) or 0
            if turn > prev_turn:
                print(f"  Turn {turn:>2d}: {dmg:>12,}")
                prev_turn = turn
                no_progress_polls = 0
            else:
                no_progress_polls += 1
            final_dmg = max(final_dmg, dmg)
            final_turn = max(final_turn, turn)

        # Real end detection
        if active is False and (not heroes or all(h.get("side") == "player" and "dead" in (h.get("st") or []) for h in heroes)):
            # Confirm via scene OR BattleFinishAllianceEnemyDialog —
            # CB battles end with the finish dialog overlaid on the
            # Dungeon_Clan scene, so the scene-only check misses it
            # and polls for the full MAX_POLLS×POLL_INTERVAL=~17min
            # before giving up (saves an empty 64B log + loses key 1
            # damage data). Adding the dialog probe ends polling within
            # ~20s of the actual battle finish. Verified 2026-05-16 via
            # the 4 prior days' 64B+4.1MB log pattern.
            st = mod_get("/status")
            scene = (st or {}).get("scene", "")
            ctxs = (mod_get("/view-contexts") or {}).get("contexts", [])
            finish_up = any("BattleFinish" in (c.get("dialog") or "") for c in ctxs)
            if scene != "Dungeon_Clan" or finish_up:
                print(f"  Battle ended at poll {i} "
                      f"(scene={scene}, finish_dialog={finish_up})")
                break

        # Stall watchdog — 120 polls with no turn progress AND scene has left CB
        if no_progress_polls >= 120:
            st = mod_get("/status")
            scene = (st or {}).get("scene", "")
            if scene != "Dungeon_Clan":
                print(f"  Stall + scene exit ({scene}) — assuming battle ended at poll {i}")
                break
            # Keep polling otherwise

        time.sleep(POLL_INTERVAL)
    else:
        print("  WARNING: Max polls reached, battle may still be running")

    return final_dmg, final_turn


def _snapshot_run_build(log_filename, entries, boss_turns):
    """Save a per-run BUILD snapshot next to the battle log: each team hero's
    game-computed stats (CB-effective totals + full column breakdown), equipped
    gear, sets, masteries, blessing, AND the effective speed derived from turn
    counts. This lets us later answer 'what build/speed produced this run'
    directly instead of guessing — the per-unit s_spd field read 0 before
    2026-06-16, so older runs lost their build entirely. Best-effort; never
    breaks the run.
    """
    try:
        from collections import Counter
        # team type_ids + per-hero turn counts from the battle log
        team_types, hero_turns = [], {}
        for e in entries:
            for h in e.get("heroes", []) or []:
                if h.get("side") == "player" and h.get("type_id"):
                    tid = h["type_id"]
                    if tid not in team_types:
                        team_types.append(tid)
                    hero_turns[tid] = max(hero_turns.get(tid, 0), h.get("turn_n", 0) or 0)
        if not team_types:
            return
        cs = mod_get("/hero-computed-stats?hero_id=0", timeout=20)
        cs_by_id = {h.get("id"): h for h in (cs.get("heroes", []) if isinstance(cs, dict) else [])}
        ah = mod_get("/all-heroes?limit=20000", timeout=20)
        ah_heroes = ah.get("heroes", []) if isinstance(ah, dict) else []
        # type_id -> hero record; prefer the geared copy (most artifacts) for duplicates.
        # The battle log truncates the type_id's last digit (form/ascension), so a
        # /all-heroes type_id 6206 logs as 6200 — match on (tid // 10) * 10.
        tid_to_hero = {}
        for h in ah_heroes:
            tid = h.get("type_id")
            if tid is None:
                continue
            base_tid = (tid // 10) * 10
            if base_tid in team_types:
                cur = tid_to_hero.get(base_tid)
                if cur is None or len(h.get("artifacts") or []) > len(cur.get("artifacts") or []):
                    tid_to_hero[base_tid] = h
        BOSS_SPD = 190.0  # UNM CB boss SPD (cb_constants CB_SPEED_BY_DIFFICULTY) — for the
                          # effective-speed estimate only; the `stats` below are exact.
        COLS = ["blessing_bonus", "empower_bonus", "affinity_bonus", "artifact_bonus",
                "relic_bonus", "mastery_bonus", "faction_guardians_bonus"]
        SLOT = {1: "Helmet", 2: "Chest", 3: "Gloves", 4: "Boots", 5: "Weapon",
                6: "Shield", 7: "Ring", 8: "Amulet", 9: "Banner"}
        team_out = []
        for tid in team_types:
            hero = tid_to_hero.get(tid)
            hid = hero.get("id") if hero else None
            comp = cs_by_id.get(hid)
            rec = {"type_id": tid, "id": hid, "name": hero.get("name") if hero else None}
            if comp:
                base = comp.get("base_computed", {})
                rec["stats"] = {s: round(base.get(s, 0) + sum(comp.get(c, {}).get(s, 0) for c in COLS), 1)
                                for s in ("HP", "ATK", "DEF", "SPD", "RES", "ACC", "CR", "CD")}
                rec["stat_columns"] = {c: comp.get(c) for c in (["base_computed"] + COLS + ["classic_arena_bonus"]) if c in comp}
            tn = hero_turns.get(tid, 0)
            rec["turns_taken"] = tn
            rec["effective_spd"] = round(tn / boss_turns * BOSS_SPD, 1) if boss_turns else None
            if hero:
                rec["gear"] = {SLOT.get(a.get("kind"), a.get("kind")): a.get("id") for a in (hero.get("artifacts") or [])}
                rec["sets"] = dict(Counter(a.get("set") for a in (hero.get("artifacts") or []) if a.get("set")))
                rec["masteries"] = hero.get("masteries")
                rec["blessing"] = hero.get("blessing")
            team_out.append(rec)
        out = {"run": log_filename, "captured_at": datetime.now().isoformat(timespec="seconds"),
               "boss_turns": boss_turns, "boss_spd_assumed": BOSS_SPD, "team": team_out}
        build_filename = log_filename.replace("battle_logs_cb_", "build_cb_")
        if build_filename != log_filename:
            path = PROJECT_ROOT / build_filename
            with open(path, "w") as f:
                json.dump(out, f, indent=2)
            print(f"  Build snapshot: {len(team_out)} heroes (stats+gear+eff.spd), saved: {path.name}")
    except Exception as ex:
        print(f"  [warn] build snapshot skipped: {ex}")


def save_battle_log(filename=None):
    """Fetch and save the battle log from the mod.

    Retries up to 5 times with 2s delay, keeping the largest log seen.
    The mod's in-memory log gets wiped when ProcessStartBattle fires for
    the post-battle result screen; we try to catch the moment before
    that wipe. Early-exit bug mitigation: never save a truncated log.
    """
    best = None
    for attempt in range(5):
        time.sleep(2)
        r = mod_get("/battle-log", timeout=30)
        if "error" in r:
            print(f"  [attempt {attempt+1}] battle-log fetch error: {r['error']}")
            continue
        entries = r.get("log", [])
        if best is None or len(entries) > len(best.get("log", [])):
            best = r
        # Accept if we see `battle_end` event OR final snapshot + plenty of entries
        has_end = any(e.get("event") == "battle_end" for e in entries if isinstance(e, dict))
        has_final = any(e.get("scene") == "final" for e in entries if isinstance(e, dict))
        if has_end and has_final and len(entries) > 50:
            break
    r = best or {}
    entries = r.get("log", [])
    print(f"\nBattle log: {len(entries)} entries")

    # Find final damage
    max_dmg = 0
    max_turn = 0
    has_final = False
    has_end = False
    team_types = []

    for entry in entries:
        if entry.get("scene") == "final":
            has_final = True
        if entry.get("event") == "battle_end":
            has_end = True
        if "heroes" in entry:
            if not team_types:
                team_types = [h.get("type_id") for h in entry["heroes"] if h.get("side") == "player"]
            for h in entry["heroes"]:
                if h.get("side") == "enemy":
                    max_dmg = max(max_dmg, h.get("dmg_taken", 0))
                    max_turn = max(max_turn, h.get("turn_n", 0))

    print(f"  Final snapshot captured: {has_final}")
    print(f"  Battle end event: {has_end}")
    print(f"  Boss turns: {max_turn}")
    print(f"  Total damage: {max_dmg:,}")

    # Save
    if filename is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"battle_logs_cb_{ts}.json"

    filepath = PROJECT_ROOT / filename
    # Don't clobber a poll_battle crash-resilience snapshot with an
    # empty post-crash fetch. If the file already exists with more
    # entries than we just fetched, keep the existing one.
    existing_entries = 0
    if filepath.exists():
        try:
            with open(filepath) as f:
                existing_entries = len(json.load(f).get("log", []) or [])
        except Exception:
            pass
    new_entries = len(entries)
    if new_entries >= existing_entries:
        with open(filepath, "w") as f:
            json.dump(r, f)
        print(f"  Saved: {filepath.name}")
    else:
        print(f"  Keeping prior snapshot ({existing_entries} entries) — final fetch returned only {new_entries}")

    # Phase 5 (mechanics research) — also save the per-event tick log.
    # The mod's BattleHook_DamageChange path captures attacker ATK / target
    # DEF / pre-mitigation calc_raw / post-mitigation calc per damage event.
    # Saving alongside lets us back-solve the game's DEF mitigation formula
    # empirically (no more "community estimate"). Best-effort: skip if
    # /tick-log isn't available or empty.
    try:
        tl = mod_get("/tick-log", timeout=15)
        ticks = tl.get("ticks") or []
        if ticks:
            tick_filename = filename.replace("battle_logs_cb_", "tick_log_cb_")
            if tick_filename == filename:
                tick_filename = filename.replace(".json", "_tick.json")
            tick_path = PROJECT_ROOT / tick_filename
            with open(tick_path, "w") as f:
                json.dump(tl, f)
            damage_events = sum(1 for t in ticks if isinstance(t, dict) and t.get("kind") == "damage")
            print(f"  Tick log: {len(ticks)} entries ({damage_events} damage), saved: {tick_path.name}")
    except Exception as ex:
        print(f"  [warn] tick-log save skipped: {ex}")

    # Snapshot the live presets at fixture capture time. The user can
    # edit presets between battles; sim_replay needs the preset that
    # was actually in force during this run, not whatever is live when
    # we replay. Skipping this caused 2026-06-21 Force fixtures to
    # diff against today's preset and overstate sim drift.
    try:
        ps = mod_get("/presets", timeout=10)
        preset_filename = filename.replace("battle_logs_cb_", "presets_cb_")
        if preset_filename != filename:
            preset_path = PROJECT_ROOT / preset_filename
            with open(preset_path, "w") as f:
                json.dump(ps, f)
            n = len((ps or {}).get("presets") or [])
            print(f"  Presets snapshot: {n} entries, saved: {preset_path.name}")
    except Exception as ex:
        print(f"  [warn] preset snapshot skipped: {ex}")

    # Per-run BUILD snapshot — heroes + game-computed stats + gear + effective
    # speed, paired to this run so we always know what build produced the result.
    _snapshot_run_build(filepath.name, entries, max_turn)

    return {
        "filepath": str(filepath),
        "filename": filepath.name,
        "entries": len(entries),
        "boss_turns": max_turn,
        "total_damage": max_dmg,
        "has_final": has_final,
        "team_type_ids": team_types,
    }


def run_calibration(log_filename, cb_element="void", team=None):
    """Run sim calibration against the battle log."""
    print(f"\n{'='*60}")
    print(f"CALIBRATION")
    print(f"{'='*60}")

    from cb_calibrate import extract_real_data, run_sim_for_team, calibrate

    log_path = PROJECT_ROOT / log_filename
    real_data = extract_real_data(log_path)

    ELEMENT_MAP = {"magic": 1, "force": 2, "spirit": 3, "void": 4}
    element = ELEMENT_MAP.get(cb_element, 4)

    if team is None:
        team = ["Maneater", "Demytha", "Ninja", "Geomancer", "Venomage"]

    sim_result = run_sim_for_team(team, element, False, max_cb_turns=50, use_current_gear=True)
    calibrate(real_data, sim_result)

    delta = {
        "real_total": real_data["total_damage"],
        "sim_total": sim_result["total"],
        "error_pct": (sim_result["total"] - real_data["total_damage"]) / max(real_data["total_damage"], 1) * 100,
    }
    _record_calibration_delta(log_path.name, team, cb_element, real_data, sim_result)
    return delta


def _record_calibration_delta(log_filename, team, cb_element, real_data, sim_result):
    """Append one calibration row to data/sim_calibration_history.jsonl so
    drift over time is visible. Each row: when, team, cb_element, real,
    sim, error_pct, real_turns, sim_turns, tune_slug (best-effort match
    against DWJ tunes). Append-only — never rewrites.
    """
    from datetime import datetime
    out_path = PROJECT_ROOT / "data" / "sim_calibration_history.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    real = real_data.get("total_damage") or 0
    sim = sim_result.get("total") or 0
    row = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "log_file": log_filename,
        "team": team,
        "cb_element": cb_element,
        "real_total": int(real),
        "sim_total": int(sim),
        "real_turns": real_data.get("boss_turns") or 0,
        "sim_turns": sim_result.get("cb_turns") or 0,
        "error_pct": round((sim - real) / max(real, 1) * 100, 2),
        "tune_slug": _detect_tune_slug(team),
    }
    try:
        with open(out_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except Exception as ex:
        print(f"  [warn] failed to record calibration delta: {ex}")


def _detect_tune_slug(team: list[str] | None) -> str | None:
    """Match the team against DWJ tunes; return the slug of the highest-
    matching tune (>=0.6 score). Lets per-tune accuracy aggregation work
    without the user having to pass --tune explicitly.
    """
    if not team:
        return None
    try:
        import json as _json
        tunes_path = PROJECT_ROOT / "data" / "dwj" / "parsed" / "tunes.json"
        if not tunes_path.exists():
            return None
        tunes = _json.loads(tunes_path.read_text(encoding="utf-8"))
        team_lc = [n.lower() for n in team]
        best = (0.0, None)
        for t in tunes:
            slots = t.get("slots") or []
            named = [s.get("hero", "") for s in slots
                     if s.get("hero") and (s.get("hero") or "").lower() not in
                        ("dps", "1:1 dps", "1:1 dps 1", "1:1 dps 2", "4:3 dps",
                         "block debuff", "cleanser", "stun target")]
            if not named:
                continue
            # Each team member can only fill one slot (duplicates in `named`
            # = needs that many copies). Track consumption to avoid scoring
            # Double Demytha as a 2/2 match when the user has 1 Demytha.
            available = list(team_lc)
            matched = 0
            for n in named:
                nl = n.lower()
                if nl in available:
                    available.remove(nl)
                    matched += 1
            score = matched / len(named)
            # Tiebreaker: prefer the tune with more distinct named heroes
            # so Myth Eater (Maneater + Demytha) beats Double Demytha
            # (Demytha × 2) when both happen to score the same.
            tiebreak = len(set(n.lower() for n in named))
            key = (score, tiebreak)
            if score >= 0.6 and key > (best[0], best[2] if len(best) > 2 else 0):
                best = (score, t.get("slug"), tiebreak)
        return best[1] if best[1] is not None else None
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="CB Battle Runner")
    parser.add_argument("--cb-element", default="void",
                        choices=["magic", "force", "spirit", "void"],
                        help="Today's CB affinity (default: void)")
    parser.add_argument("--calibrate", action="store_true",
                        help="Run sim calibration after battle")
    parser.add_argument("--team", default=None,
                        help="Team for calibration (comma-separated)")
    parser.add_argument("--log-name", default=None,
                        help="Custom filename for battle log")
    parser.add_argument("--skip-battle", default=None,
                        help="Skip battle, calibrate existing log file")
    args = parser.parse_args()

    if args.skip_battle:
        # Just calibrate an existing log
        team = [n.strip() for n in args.team.split(",")] if args.team else None
        run_calibration(args.skip_battle, args.cb_element, team)
        return

    # Pre-checks
    if not check_ready():
        return 1

    keys = check_keys()
    if keys < 1:
        print("No CB keys available!")
        return 1

    # Start battle
    if not start_battle():
        return 1

    # Pre-allocate the snapshot filename so poll_battle can write
    # incremental crash-resilient snapshots to it. Same name used by
    # save_battle_log at the end (overwrites with the final fetch).
    snapshot_filename = (args.log_name
                          if args.log_name
                          else f"battle_logs_cb_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    snapshot_path = PROJECT_ROOT / snapshot_filename

    # Poll until complete (with periodic battle-log snapshots)
    final_dmg, final_turn = poll_battle(snapshot_path=snapshot_path)
    print(f"\nBattle complete: {final_dmg:,} damage over {final_turn} boss turns")

    # Save log — final attempt; if mod is reachable this overwrites
    # the snapshot with the complete log. If Raid has crashed, we
    # fall back to whatever the last snapshot captured.
    log_info = save_battle_log(snapshot_filename)
    if not log_info:
        return 1

    # Calibrate
    if args.calibrate and log_info:
        team = [n.strip() for n in args.team.split(",")] if args.team else None
        cal = run_calibration(log_info["filename"], args.cb_element, team)
        print(f"\nSim accuracy: {cal['error_pct']:+.1f}%")

    print(f"\n{'='*60}")
    print(f"DONE — {final_dmg:,} damage, log saved to {log_info['filename']}")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
