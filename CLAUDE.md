# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PyAutoRaid is a Windows-only automation tool for Raid: Shadow Legends. It combines three control strategies — a BepInEx mod HTTP API, direct IL2CPP memory reading, and screen automation — to fully automate daily in-game tasks. Runs headless on a Windows 10 VM (1024x768 resolution), triggered by scheduled tasks. Also distributed as a Windows installer (PyInstaller + Inno Setup) for standalone use.

## Build & Run

```bash
# Install dependencies
pip install -r requirements.txt

# Run from source
python Modules/PyAutoRaid.py     # Main app
python Modules/DailyQuests.py    # Daily quests only

# Run tests
python -m pytest tests/ -v

# Compile to exe (requires pyinstaller)
python -m PyInstaller --onefile -w \
  --icon=assets/Icons/image1.ico \
  --hidden-import=pyautogui --hidden-import=pyscreeze \
  --hidden-import=Pillow --hidden-import=pywin32 \
  --hidden-import=psutil --hidden-import=PyGetWindow \
  --hidden-import=requests --hidden-import=screeninfo \
  --hidden-import=ttkthemes --hidden-import=cv2 \
  --add-data "assets;assets" \
  Modules/PyAutoRaid.py
```

## Architecture

### Shared Base Module (`Modules/base.py`)

All screen automation modules inherit from `BaseDaily` which provides:
- **`locate_and_click()`** — single-scan locate + click (avoids the old double-lookup race condition)
- **`locate_and_click_loop()`** — repeatedly click an image until it disappears, with `max_retries` to prevent infinite loops
- **`wait_for_image()`** — poll for an image with timeout
- **`asset()`** — cross-platform asset path builder
- OS detection, Raid path finding, asset path resolution, game window management
- Common navigation: `back_to_bastion()`, `delete_popup()`, `kill_processes()`

All while-loops use `MAX_RETRIES` (default 30) to prevent runaway execution.

### Command Pattern (`Modules/PyAutoRaid.py`)

Each in-game task is a Command class with an `execute()` method. `RewardsCommand` is a composite that runs all reward sub-commands. The `Daily` class extends `BaseDaily`, manages config, and registers commands.

### DailyQuests Module (`Modules/DailyQuests.py`)

Extends `BaseDaily`. Uses `getattr()` to dynamically call methods based on `DQconfig.ini` settings. Simpler than PyAutoRaid — methods are called directly instead of through Command objects.

### Threading Model

- **Main thread**: Tkinter event loop
- **daily_thread**: Runs `Daily.run()` automation loop
- **timer_thread**: 30-minute daemon timeout to prevent runaway execution

### Configuration

- **PARconfig.ini** — PyAutoRaid: task toggles, clan boss difficulty/fight counts, coordinate overrides
- **DQconfig.ini** — DailyQuests: quest method toggles, automated mode
- Both are re-read every loop iteration; changes take effect without restart

### CI/CD

`.github/workflows/compile-and-release.yml`: PyInstaller compile, embed admin manifests via Resource Hacker, Inno Setup installer, auto-increment version tag, upload to GitHub Releases.

### Hybrid Controller (`Modules/hybrid_controller.py`) — Primary Entry Point

The main automation controller (1248 lines). Uses a three-tier control strategy, preferring the fastest available method:

1. **Mod API (fastest)** — BepInEx HTTP endpoint on port 6790 for direct Unity UI button clicks, navigation, artifact equip/sell, mastery management
2. **Memory reading (instant)** — game state via pymem (resources, battle state, ViewKey, arena opponents, artifacts)
3. **Coordinate/image matching (fallback)** — fixed positions for nav bar, image matching for dynamic elements (popups, battle results)

**Known limitation — MainWindowHandle=0:** Raid.exe under Unity 6000 does not create a standard Win32 window handle. `pygetwindow.getWindowsWithTitle()` and `win32gui.FindWindow()` may fail to find it. The game renders via DirectX without a traditional HWND, so pyautogui screenshot-based matching and win32 input may not work reliably. The BepInEx mod API bypasses this issue entirely.

Entry point: `python Modules/hybrid_controller.py` (or `--no-memory` for screen-only fallback)

**Automated tasks (11 total):**
1. Gem Mine — coordinate click
2. Shop Rewards — mod API or coordinate
3. Timed Rewards — image-based collection
4. Quests — claim detection + advanced quests
5. Clan — check-in + treasure
6. Inbox — individual item detection + claiming
7. Arena (10 battles) — memory-based weakest opponent selection, instant fight detection
8. Clan Boss — difficulty selection + instant fight support
9. Market Shards — mod API with price safety checks
10. Artifact Sell — mod API with strict filter (rank ≤3, rarity ≤1, level 0)
11. Dungeon Farming — 20 runs with event auto-detection + energy floor checks

**Key modules:**
- `memory_reader.py` — pymem wrapper that reads IL2CPP game objects from Raid.exe process memory (828 lines)
- `screen_state.py` — pyautogui/pygetwindow for window management, popup clearing, image-based navigation fallback (241 lines)
- `mod_client.py` — HTTP client for the RaidAutomation BepInEx mod API (420 lines)
- `win32_input.py` — Win32 PostMessage/SendMessage input backend; replaces pyautogui so the game doesn't need focus (266 lines)
- `base.py` — shared helpers (`locate_and_click`, `asset()`, etc.)

### BepInEx Mod (`mod/bepinex/RaidAutomationPlugin.cs`) — Active

BepInEx IL2CPP plugin injected into the game process. Replaced MelonLoader which is incompatible with Unity 6000.0.60f1. Provides an HTTP API on port 6790 for game data access and UI control.

**Setup (BepInEx BE #755):**
- BepInEx 6.0.0-be.755 supports Unity 6000.0.60f1 (MelonLoader v0.7.2 does NOT)
- Proxy DLL: game's `version.dll` — rename doorstop's `winhttp.dll` to `version.dll` (game imports version.dll, not winhttp)
- Use **verbose doorstop** build from UnityDoorstop v4.5.0 for debugging (37KB DLL)
- `doorstop_config.ini`: `target_assembly = BepInEx\core\BepInEx.Unity.IL2CPP.dll`, `coreclr_path = dotnet\coreclr.dll`
- First run generates 135 interop DLLs in `BepInEx/interop/` (takes 10-15 min)
- URL reservation needed: `netsh http add urlacl url=http://+:6790/ user=Everyone` (run as admin)
- Plugin goes in `BepInEx/plugins/RaidAutomationPlugin.dll`

**Game install path:** `C:\Users\snoop\AppData\Local\PlariumPlay\StandAloneApps\raid-shadow-legends\build\` (NOT `C:\Games\Raid\`)

**Build & deploy (on VM):**
```powershell
# Serve source from host: python3 -m http.server 8877 --directory ~/projects/pyautoraid
$build = 'C:\Users\snoop\AppData\Local\PlariumPlay\StandAloneApps\raid-shadow-legends\build'
$modDir = 'C:\PyAutoRaid\mod\bepinex'
Invoke-WebRequest -Uri 'http://10.0.2.2:8877/mod/bepinex/RaidAutomationPlugin.cs' -OutFile "$modDir\RaidAutomationPlugin.cs"
C:\dotnet\dotnet.exe build $modDir\RaidAutomationPlugin.csproj -c Release
Copy-Item "$modDir\bin\Release\net6.0\RaidAutomationPlugin.dll" "$build\BepInEx\plugins\" -Force
Start-ScheduledTask -TaskName 'LaunchRaid'  # launches Raid.exe in user session
```

**API endpoints (port 6790) — actual BepInEx mod routes:**

| Endpoint | Description | Data |
|----------|-------------|------|
| `/status` | Mod status | scene, logged_in, unity version |
| `/all-heroes?min_grade=6&offset=0&limit=5` | Heroes with full data | name, stats, skills, masteries (IDs), blessings, leader skills, equipped artifacts |
| `/all-artifacts?offset=0&limit=200` | ALL artifacts (equipped + vault) | Scans artifact IDs 1..LastArtifactId via `One(id)` method |
| `/account` | Account-wide bonuses | Great Hall (4 elements × 6 stats), Arena league, Clan level, Account level |
| `/skill-data?hero_id=X&min_grade=6` | Skill data for heroes | Skill effects, cooldowns, StatusEffectTypeIds |
| `/hero-computed-stats?min_grade=6` | Game-computed stats | Base + blessing + arena + GH + empower stats via game calculator |
| `/buttons` | Active UI buttons | Unity hierarchy paths |
| `/click?path=X` | Click button | Pointer + onClick events |
| `/dismiss` | One-shot dismiss overlays | Destroys `[OV]` prefixed objects |
| `/types?q=X` | Search loaded types | Debugging — finds IL2CPP interop class names |
| `/props?type=X` | Inspect type | Properties and methods of any loaded type |
| `/server-info` | Server/account info | Server region, account details |
| `/equip?hero_id=X&artifact_id=Y` | Equip artifact | Auto-handles swap if slot occupied |
| `/unequip?hero_id=X&artifact_id=Y` | Unequip artifact | Removes from hero |
| `/swap?hero_id=X&from_id=A&to_id=B` | Swap artifacts | Replace equipped with another |
| `/bulk-equip?hero_id=X&artifacts=[ids]` | Bulk equip | Multiple artifacts at once |
| `/presets` | Get saved presets | Team presets |
| `/remove-preset?id=X` | Delete preset | |
| `/save-preset?name=X&heroes=Y&type=Z` | Create preset | |
| `/update-preset?id=X&priorities=Y` | Update preset | |
| `/mastery-data?hero_id=X` | Mastery info | Opened masteries, points, resets |
| `/open-mastery?hero_id=X&mastery_id=Y` | Open a mastery | Uses OpenHeroMasteryCmd |
| `/reset-masteries?hero_id=X` | Reset all masteries | Uses ResetHeroMasteriesCmd |
| `/battle-state` | Current battle state | Started/Finished/Stopped |
| `/battle-log?clear=1` | Full battle log buffer (up to 2000 entries) | active, turns, polls, log[{event|turn|poll|diag|heroes}] |
| `/navigate?target=X` | Navigate to screen | arena, cb, campaign, dungeon, etc. |
| `/context-call?path=X&method=Y&arg=Z` | Call MVVM context method | Bypasses button clicks via IL2CPP reflection |

**Endpoints that do NOT exist (mod_client.py calls these but they are not in the BepInEx mod):**
- `/find` — object search (not implemented)
- `/toggles`, `/toggle` — toggle components (not implemented)
- `/sell` — artifact selling via command (not implemented)
- `/artifacts` — filtered artifact list (not implemented; use `/all-artifacts` instead)
- `/overlays` — auto-dismiss toggle (not implemented; use `/dismiss` for one-shot)
- `/shopitems` — market item reading (not implemented)
- `/view-context` — MVVM context discovery (not implemented; use `/context-call` directly)

**How it accesses game data (reflection-based):**
1. `AppModel` singleton via `SingleInstance<AppModel>.Instance` (found by scanning properties for `UserWrapper` type)
2. `UserWrapper` from AppModel — has `Heroes` (HeroesWrapper), `Artifacts` (EquipmentWrapper), `Capitol`, `Arena`, `Alliance`
3. Hero data: `HeroesWrapper.HeroData.HeroById` (Dictionary<int, Hero>)
4. Hero type resolution: `hero.Type` property, falls back to `hero._type`, then `StaticData.HeroData.HeroTypeById[typeId]`
5. Artifact data: `EquipmentWrapper.One(artId)` — resolves through `ArtifactStorageResolver` → `ExternalArtifactsStorage` → `CachedArtifacts._artifacts` dict
6. All artifacts: scan IDs 1..`ArtifactData.LastArtifactId`, calling `One(id)` for each; `null` = deleted/non-existent
7. Hero→artifact mapping: `ArtifactData.ArtifactDataByHeroId` dict → `HeroArtifactData.ArtifactIdByKind` dict
8. `Fixed` type (game's fixed-point numbers): `ToString()` returns the double value; for % values multiply by 100

**Key IL2CPP interop type names:**
- `Client.Model.AppModel` — singleton, holds all game state
- `Client.Model.Guard.UserWrapper` — per-user data access (not at a fixed offset — scan AppModel properties)
- `Client.Model.Gameplay.Heroes.HeroesWrapper` — hero roster
- `Client.Model.Gameplay.Artifacts.EquipmentWrapper` — artifact access
- `SharedModel.Meta.Heroes.Hero` — individual hero (Id, TypeId, Grade, Level, Skills, MasteryData, DoubleAscendData)
- `SharedModel.Meta.Heroes.HeroType` — static hero data (Name, Fraction, Rarity, Forms→Element/Role/BaseStats, LeaderSkills)
- `SharedModel.Meta.Artifacts.Artifact` — artifact (Id, Level, KindId, RankId, RarityId, SetKindId, PrimaryBonus, SecondaryBonuses)
- `SharedModel.Meta.Artifacts.Bonuses.ArtifactBonus` — stat bonus (KindId=stat, Value=BonusValue, Level=rolls)
- `SharedModel.Meta.Artifacts.BonusValue` — (IsAbsolute=flat vs %, Value=Fixed)
- `SharedModel.Meta.Heroes.BattleStats` — HP/ATK/DEF/SPD/RES/ACC/CR/CD (all Fixed type)
- `SharedModel.Meta.Artifacts.ArtifactStorage.ArtifactStorageResolver` — static class, `_implementation` holds `ExternalArtifactsStorage`

**Important gotchas:**
- WinRM requires **Private** network profile: `Set-NetConnectionProfile -InterfaceAlias "Ethernet" -NetworkCategory Private` (admin PS)
- Plarium Play login sessions expire — if `Stop-Process -Name explorer` is run, PP credentials may be lost and require manual re-login via RDP. **NEVER `Stop-Process -Name PlariumPlay` to release a DLL lock during redeploy** — same effect; Raid.exe will relaunch then self-exit within ~60s (Player.log shows clean shutdown after Wwise init, not a crash). Only stop `Raid.exe` for redeploys.
- After a Raid-only restart, the HTTP listener log line "HTTP listener started on port 6790" can appear before http.sys has actually bound — give the mod 2–3 minutes before concluding the listener is broken.
- BepInEx doorstop sets `DOORSTOP_DISABLE=TRUE` env var after hooking — prevents child processes from double-hooking
- JSON responses > ~50KB get truncated by WinRM `Invoke-WebRequest` — use `curl` on VM + base64 file transfer instead
- `hero.Type` throws `TargetInvocationException` for some heroes — always wrap in try/catch, fall back to `_type` then `StaticData` lookup
- Base stats from `HeroType.Forms[0].BaseStats` are **level-1 unscaled** values — multiply by ~15 (HP) or ~7.5 (ATK/DEF) for 6★ L60

### Battle Logging Pipeline (in `RaidAutomationPlugin.cs`)

Turn-by-turn telemetry for arena/CB/dungeon fights. State lives in static fields on `RaidAutomationPlugin`:

- `_battleActive` — toggled by Harmony `BattleHook_ProcessStartBattle` / `BattleHook_ProcessEndBattle`. `PollBattleState` ALSO confirms activation via scene-name + BattleHUD GameObject presence (scene name alone is insufficient — e.g. `GoldArena` stays set on the opponent-select screen).
- `_battleCommandCount` — increments ONLY on `ProcessStartTurn` hook. True turn count.
- `_pollCount` — increments per Update() poll (every 0.5s) while `_battleActive`. Distinct from turns; do not confuse.
- `_battleLog` — `List<string>` of JSON entry strings, capped at 2000. Cleared on each `battle_start`. Entry shapes: `{"event":"battle_start|battle_end",...}`, `{"turn":N,"active_hero":id,"ptr":1}`, `{"poll":N,"turn":T,"scene":...,"heroes":[...]}`, `{"poll":N,"turn":T,"scene":...,"game_ctx":true|false}`, `{"diag":"ctx_props",...}`.

**BattleProcessor schema (captured from live diag 2026-04-13):**
- `BattleProcessor` get_* = `[Settings, Context, Setup, State, Statistics]`
- `BattleSetup` = `[IsAutoBattle, IsBackgroundBattle, Stage, MaxTurnsInBattle]` — NO heroes here
- `BattleState` = `[PlayerTeam, EnemyTeam, SkipViewData]` — **heroes live under the teams**
- `BattleContext` = `[DecisionMaker, MaxRecursionDepth, CurrentRegionTypeId, CurrentAreaTypeId, ActiveHeroId, ActiveUserId, StageId]` — metadata only
- Prior code navigated `Processor.Context.Setup.Heroes` which never returned — Setup/State hang off the Processor directly, not Context.

**ReadBattleHeroesIL2CPP path (verified 2026-04-13 in a live CB fight):**
- `BattleProcessor → State → {PlayerTeam, EnemyTeam} → HeroesWithGuardian[i]` yields each `BattleHero`. The team-heroes accessor is `get_HeroesWithGuardian` (NOT `Heroes`/`Members`/`Units` — my initial probes missed it; the probe order in `ReadBattleHeroesIL2CPP` and the PlayerTeam-drill diag has `HeroesWithGuardian` first now).
- The `BattleHero` class is the same across arena/CB/dungeon and exposes ~80 properties; the ones we extract per turn:
  - Identity: `Id` (battle slot index), `BaseTypeId` (matches `HeroType.Id` in `skills_db.json`)
  - HP: `MaxHealth`, `DestroyedHealth` (current HP = max - destroyed). `HealthPerc` also exists but doesn't always match; prefer computing from max/destroyed.
  - TM: `Stamina` (0–100 scale after conversion)
  - Bool flags: `IsUnkillable`, `IsBoss`, `CanAttack`, `MustSkipTurn`
  - Active status summary as `st:[...]` — 27 boolean flag getters mapped to short labels (`stun`, `freeze`, `sleep`, `provoke`, `invincible`, `block_debuff`, `taunt`, `invis`, `dying`, `dead`, `block_heal`, `nullifier`, `petrify`, `ss`, `ss_simple`, `ss_reflect`, `banish`, `grab`, `devour`, `entangle`, `absent`, `enfeeble`, `no_tm_tick`, `rages`, `xform`, `act_blk`, `pass_blk`). Only flags currently TRUE are emitted.
  - Skills: `HeroSkills` collection (3–6 entries), each as `{t:<skill_type_id>, rdy:<bool>, start?:true, same:<count>, blk?:true}`. A skill flipping from `rdy:true` to `rdy:false` between turns means the hero used it this turn. Matches IDs in `skills_db.json`.

**Fixed-point encoding (critical):** Raid's `Fixed` type is **32.32** (raw value = display × 2³²), NOT 16.16. Correct decode is `value = raw >> 32`. Reading the boxed Fixed at `+0x10` as Int64 and shifting 32 bits right yields the integer value (e.g., raw `173,351,751,876,938 >> 32 = 40,363 HP`). Using 16.16 gives huge nonsense numbers like 2.6 billion.

**Per-turn snapshot cadence:** The log emits a full `{poll,turn,scene,heroes:[...]}` entry once per turn change (via `_lastStatsLogTurn` bookkeeping) and every ~5s during long turns (safety against dropped turn hooks). `BattleHook_ProcessEndTurn` also nudges `_lastStatsLogTurn = -1` so the next poll force-emits a complete snapshot.

**Harmony patching reality:** `ProcessStartTurn` / `ProcessEndTurn` / `ProcessStartBattle` / `ProcessEndBattle` fire reliably and give us the authoritative turn counter. `ProcessStartRound` / `ProcessEndRound` / `ApplySkillCommand` report patched in the BepInEx log but the postfixes don't actually fire in IL2CPP builds (known BepInEx 6.0.0-be limitation with some internal Raid methods). Do NOT rely on them — infer rounds from turn counts and skill-use from per-turn `rdy` cooldown deltas instead.

**MessageBox dismissal (blocks arena StartBattle):** When `/view-contexts` shows `{"dialog":"MessageBox"}`, the confirmation dialog must be dismissed. It is NOT findable at `.../Dialogs/MessageBox`; the buttons live on a separate canvas at `UIManager/Canvas (Ui Root)/MessageBoxes/MessageBox/BoxContainer/Box/Content/Buttons_h/{0|1}`. Dismiss via `/context-call?path=<button_path>&method=OnClick` (NOT `/click` — the onClick handler does not fire that route, and `/dismiss` only handles `[OV]` prefixed objects).

**Known limitations:**
- `get_Game` on the BattleHUD MonoBehaviour currently returns null (`game_ctx:false` in poll entries) — alternate path not needed since Harmony-captured processor is authoritative.
- Programmatically starting arena/CB fights is fragile: `context-call StartBattle` reports success but the game may not launch (heroes unselected, message boxes pending, confirm dialogs). Cron-driven runs at 7am/1pm/7pm exercise the full UI flow correctly.

**Where active buffs/debuffs really live on BattleHero (verified 2026-04-13 via field-scan diag):**
- `AppliedEffectsByHeroes` @0x108 — ALWAYS null in practice (despite appearing in field list). Misnamed for our purposes; tracks effects applied BY this hero, not effects ON this hero.
- `_appliedStatModifications` @0xB0 — also null in practice.
- **`PhaseEffects._effectsByPhaseIndex: List<EffectType>[]` @0xF0 → 0x10** is the real storage for per-hero active effects (UK, Block Damage, Poison, HP Burn, shields, etc.). It's an array of lists, indexed by skill phase. Needs one more schema-drill to map `EffectType`'s fields (TypeId, Turns, SourceHeroId, Value). Until wired, duration-tracking is inferred from boolean-flag transitions on `BattleHero` and from `rdy` flips on the corresponding hero's skills.
- **`StatImpactByEffects._statsImpactByEffect: Dictionary<int, ValueTuple<Fixed, StatKindId, EffectContext>>` @0xA0 → 0x18** — dedicated storage for stat-modifying effects (DEF Down, ATK Down, Weaken, etc.). Sibling of PhaseEffects, narrower scope.
- **`Bonuses:BattleBonuses` @0xC8** — pre-aggregated stat-bonus stacks (Leader, Arena, Arts, Empower, Relic, Blessing, etc.). NOT dynamic buffs — the stat pre-calc layer.
- **`_heroState:HeroState` @0xC0** — the same 30 boolean flags accessible via `Is*` getters (IsStunned, IsFrozen, IsBlockDebuff, …). Getters just delegate here.
- .NET `Dictionary<K,V>` internal layout confirmed stable in IL2CPP: `_entries:Entry[]@0x18`, `_count:int@0x20`. Iterate via internal-array walking (faster and simpler than invoking GetEnumerator).

**Turn-counter semantics — confirmed:**
- `_battleCommandCount` (mod-side) fires on every `ProcessStartTurn` hook (player turns + boss turns + some passive ticks). Not what the in-game UI shows.
- In-game "Turn X" counter displayed in CB = `sum(player_hero.TurnCount)`. Each `BattleHero.TurnCount` @0xE8 increments only when that hero takes an actual turn. Sum over the 5 player heroes = the number the UI shows. Boss.TurnCount separately counts boss rounds.
- To answer speed-tune / turn-order questions (e.g., "did Demytha go before the boss and waste her buffs?"), use the `active_hero` field on each turn hook — the mod log already captures this without needing effect-duration tracking.

**Raid's Fixed-point encoding:** Raid uses **32.32 fixed-point** for HP/MaxHealth/DamageTaken/Stamina/etc. Raw int64 at field offset, display value = `raw >> 32`. Using 16.16 (common assumption) yields numbers ~65000× inflated. Confirmed empirically: Maneater HP raw=173,351,751,876,938 → 40,363 HP. This affects ALL Fixed reads (HP, Stamina aka TM, damage numbers, etc.) across the mod and analyzer tools.

**Gear-optimizer / SPD-calc calibration notes (learned the hard way):**
These are all empirical findings from matching calculated vs in-game speeds on a live team:

- **Lore of Steel mastery ID = `500343`** (Support T4 col 3). `raid_data.MASTERY_IDS["lore_of_steel"]`. Amplifies all basic set bonuses by +15% (so Speed set 12% becomes 13.8%). Earlier `cb_optimizer.calc_stats` checked the wrong IDs (500333/500334) and never applied the boost.
- **Raid rarity codes: 1=Common, 2=Uncommon, 3=Rare, 4=Epic, 5=Legendary.** `EMPOWERMENT_BONUSES["legendary"]` vs `["epic"]` should be selected by `rarity >= 5`, not `>= 4`. Epic empowerment caps at +10 SPD (emp4), Legendary at +15.
- **The game's `CalcEmpowerBonus` (via `/hero-computed-stats`) only returns HP/ATK/DEF** — it does NOT include the SPD/ACC/RES/CR/CD bonuses that empowerment also provides. Those must be added separately from the `EMPOWERMENT_BONUSES` table. Epic emp3 → +5 SPD (matters for Myth-Eater tune slots).
- **Artifact `flat_bonus` only aggregates HP/ATK/DEF/SPD — NOT ACC/RES/CR/CD.** Use `flat_bonus` for the 4 scaling stats (it includes Divine-rank enhancement bonuses: 6★ rank-6 artifacts get an extra ~6 flat on some stat axis that's NOT exposed as a substat). For ACC/RES/CR/CD, still iterate `primary` + `substats` manually. Calc_stats now does this hybrid.
- **Divine enhancement example:** Demytha's weapon (id 29809) has substat SPD=11+glyph 5=16, but `flat_bonus.SPD=22`. The extra 6 is Divine enhancement with no corresponding substat row.
- **Calibration vs live speeds (post-fix):** Maneater calc 288.6 / game 288-289 ✓, Demytha 172.1 / 173 ✓, Geomancer 179.0 / 179 ✓, Ninja 205.8 / 206 ✓, Venomage 162.0 / 162 ✓. Residual ±1 is game rounding.

**DWJ Myth-Eater tune presets** (embedded in `gear_optimizer.py` MYTH_EATER_SPEEDS) — these are the target in-game speeds, use as the spd_range when asking the optimizer for Myth-Eater builds:
```
Maneater   287-290   (tight)
Demytha    171-174
Ninja      204-207   (1:1 DPS variant, NOT 4:3)
DPS_1to1   177-180   (Geomancer slot)
DPS_slow   159-162   (Venomage slot)
```
UNM tune syncs on boss turn 6 when all five speeds are correct; missing even one slot prevents sync and causes buff/boss-AoE desync.

**Verified performance of this tune (2026-04-13, live run vs Force Affinity UNM):**
Actual in-game speeds after gear swaps: Maneater 288-289, Demytha 173, Ninja 206, Geomancer 179, Venomage 162. Result: **50/50 CB turns completed, 30.78M total damage, zero deaths.** Previous wipe run at misaligned speeds (Demytha at 229, Maneater at 227 — Demytha was faster than Maneater, breaking the tune) did 13M with full team wipe at boss turn 26. Gear-swap-fix was a ~2.4× damage improvement with same heroes, just correcting speeds to tune targets.

**Force-Affinity mode observations (when the clan has already beaten the CB):**
- Boss has effectively infinite HP (`hp_cur` on boss stays near 0 or stays untouched). `DamageTaken` on boss still accumulates normally — that's the headline "total damage" number (30.78M over 50 turns in our run).
- Boss-side flags show `dying:100%` permanently (FA-state) and `block_heal:~90%+` when Ninja-style kit is landing the Block Heal debuff.
- Per-skill damage caps appear as suspiciously round numbers in the per-turn damage deltas: `+75,000` / `+175,000` / `+250,000` on boss — these are hard caps the game applies to skill-damage in FA mode. `cb_sim.py`'s damage predictions over-estimate in FA mode because they don't model these caps.
- Player-side `hp_cur` still tracks normal damage and heals (e.g. Maneater 38,959 → 30,693 → back up to 38,959 over a round — healing is real), so survival analysis still works. `DestroyedHealth` (aka `hp_lost` in the log) is unreliable in FA mode; use `dmg_taken` + `hp_cur` instead.

**`block_heal` is NOT HP Burn.** `block_heal` = the Block Heal DEBUFF on the target (prevents them from receiving healing). HP Burn is a DIFFERENT, damage-over-time debuff that ticks each time the target takes a turn (like Poison). HP Burn has no HeroState boolean — it lives in the active-effects list along with Poison, DEF Down, Weaken, Unkillable-buff, Block-Damage-buff, etc. We detect HP Burn landing indirectly via the large per-boss-turn damage spikes.

**Unkillable-buff tracking is STILL INDIRECT.** `IsUnkillable` on BattleHero (what we serialize as `uk_saved`) only returns true when a hero is *currently at 0 HP being prevented from dying* — NOT when the UK buff is applied but not yet triggered. Same for Block Damage: `IsInvincible` (what we serialize as `block_damage`) doesn't always register during hits where BD is absorbing. Proof that UK buff IS held: heroes in the verified 50-turn run took 80-120K single-hit damage vs 40-50K HP caps and survived — UK clamped HP to 1, then healing restored. The coverage-gap detector in the analyzer will over-report WIPE RISK for this reason — trust the outcome (`dead` flag transitions + `hp_cur` trace) over the moment-of-hit flag state.

**CB sim (`tools/cb_sim.py`) refinements (calibrated vs live Myth-Eater run):**

- **Force-Affinity per-skill damage caps** added as a generalizable boss-state flag, not team-specific. Default `force_affinity=True` in `CBSimulator.__init__`. Disable with `--no-force-affinity` (pre-defeat CB).
  - `FA_CAP_BIG = 250,000` — A3 / big AoE per-hit cap
  - `FA_CAP_MEDIUM = 175,000` — A2/A4 / large single-target
  - `FA_CAP_SMALL = 75,000` — A1 / basic / WM/GS procs / Geomancer passive tick
  - `FA_CAP_DOT = 75,000` — per-tick HP Burn / Poison cap
  - Caps applied in `_cap_fa()` at all damage-accumulation sites: direct-hit, WM/GS procs, DoT ticks, passive damage.
- **Removed Budget-UK-specific speed overrides.** `main()` previously forced Maneater=228/215 and DPS to 171-189 range. That broke any non-Budget-UK tune (Myth-Eater, Clan Shield, 4:3, etc.). Now uses the actual calculated speeds from the assigned gear, so the sim respects whatever tune is present.
- **`--no-force-affinity` CLI flag** added to both `cb_sim.py` and `gear_optimizer.py` for pre-defeat CB simulation.
- **Calibration against live run (Myth-Eater, UNM, FA mode, 50 turns):** sim predicted 36.5M with caps ON vs 30.78M actual (18% over). Caps-OFF prediction is 46.9M (52% over). Remaining 18% gap is from rotation-timing / debuff-uptime modeling gaps, not cap-related.

**Direct active-effect tracking — landed 2026-04-13:** Two new per-snapshot fields now emit in every `heroes[i]` entry:

- **`mods: [{id, k, v}, ...]`** — read from `StatImpactByEffects._statsImpactByEffect` dict. Each entry is a currently-active stat-modifying effect: `id` is the source effect_id (look up in `skills_db.json` / masteries), `k` is `StatKindId` (1=HP, 2=ATK, 3=DEF, 4=SPD, 5=RES, 6=ACC, 7=CR, 8=CD; other ints = special), `v` is the signed value (Fixed >> 32; negative = debuff). Dict-entry stride is **0x28** (hash:4, next:4, key:4, pad:4, value tuple:24). Value tuple layout: `Fixed:8 @0x10`, `StatKindId:4 @0x18`, `EffectContext:8 @0x20`.
  - Example captured: `id:151 k:3 v:-912` on the boss = Venomage DEF Down (912 flat DEF reduction). `id:131 k:2 v:-3497` = Decrease ATK. `id:231 k:6 v:-113` = Decrease ACC. `id:620042 k:2 v:+2530` on Ninja = his A2 self-ATK buff. Mastery-passive effects (ids starting with `5001XXX`, `5003XXX`) also appear — filter them with a T0 baseline to see only dynamic in-battle effects.
- **`abs: {"<effect_kind>": <damage>, ...}`** — read from `AbsorbedDamageByEffectKindId:Dictionary<int, Fixed> @0x68`. Cumulative damage absorbed per effect-kind. Dict-entry stride is **0x18** (hash:4, next:4, key:4, pad:4, value:8 = Fixed raw long). Captured example: `Maneater abs={"2004": 21645}` = effect kind 2004 (continuous-heal / shield family) absorbed 21,645 damage over the fight.

**What this does NOT give us (still):** `AppliedEffectsByHeroes @0x108` stayed null in every probe. `Challenges:Dictionary @0xE0` reported `count > 0` but standard entry strides (0x10, 0x18) didn't find non-null Challenge objects. `Counters:Dict<int, Fixed> @0x138` has a valid-looking key=0 entry on Geomancer (probably a mastery stack counter, NOT UK state). Pure-non-stat buffs like the Unkillable and Block Damage buffs (when applied but not triggered) don't appear in `StatImpactByEffects` either — they're only observable via their `AbsorbedDamageByEffectKindId` entries when they actually absorb damage, or via the `uk_saved`/`block_damage` HeroState bools when they fire.

**UK/BD inference was rejected — don't guess.** An earlier iteration tried to infer UK/BD buff windows from skill-fire timing + skills_db lookups with manual overrides for gaps. This was removed because (a) guessing at skill effects that aren't in skills_db leads to errors (example mistake: Demytha A2 places Block Damage, **NOT Unkillable** — don't assume UK placement without verified data) and (b) the user wants direct observation, not inference. Future work must use verified-only sources: `skills_db.json` entries that actually exist, `AbsorbedDamageByEffectKindId` for retrospective absorption, `uk_saved` / `block_damage` HeroState flags for triggered state, and survival signatures (`hp_cur` reaching exactly 1) for UK-clamp detection. If skills_db is missing a known skill (like Demytha A2 type=65102), fix skills_db itself from the game's data — don't patch with assumed values.

**Schema diags retained in the mod** (auto-fire once per battle until populated):
- `hero_schema` — BattleHero class dump
- `effect_schema` — EffectType schema (from PhaseEffects — static skill phase data)
- `stat_impact_schema` — StatImpactByEffects tuple layout + EffectContext fields (confirmed stride 0x28)
- `challenge_schema` — Challenges dict (current status: entries probe returns "no populated" in practice)

**Analyzer update:** `tools/battle_log_analyze.py` added two new sections — `STAT-MOD EFFECTS` (per-turn dynamic debuff/buff ledger with source-effect IDs) and `ABSORBED DAMAGE BY EFFECT KIND` (cumulative absorb totals per hero). Use these to validate sim predictions for debuff uptime and healing/shield absorb.

### Data-refresh pipeline

- **`tools/refresh_data.py`** — fetches fresh roster + artifacts from the live mod in ~30s. Hits `/all-heroes` and `/all-artifacts` with pagination, writes `heroes_all.json`, `heroes_6star.json`, `all_artifacts.json`, `equipped_art_ids.json`. Run whenever gear changes to keep the optimizer accurate.
- **`tools/gear_optimizer.py`** auto-invokes `refresh_data.py` if any data file is older than 30 min. Skip with `PYAUTORAID_NO_REFRESH=1`. Old `tools/fetch_heroes.py` (WinRM-based) is slower and deprecated — prefer `refresh_data.py`.
- **`tools/cb_potential.build_potential_hero`** no longer wipes the hero's real masteries + empowerment when building the sim subject. Preserving them is essential for the SPD calc to match reality (Lore of Steel presence changes set bonus by ~15%, Epic emp3 adds +5 SPD, etc.).

### Battle-log analyzer (`tools/battle_log_analyze.py`)

Joins a saved `/battle-log` JSON with `skills_db.json` + `heroes_all.json` to produce:
- Team roster (type_id → name)
- Turn counters: mod `_battleCommandCount` vs in-game counter (sum of player `turn_n`) vs boss `turn_n`
- Per-turn damage events with BD absorption distinguished from real HP loss
- Per-hero damage totals (dmg_taken, hp_lost, BD_absorbed)
- **Coverage gaps per boss turn** — identifies heroes with no `block_damage` and no `invis`, flags WIPE RISK when ≥2 uncovered. This directly answers "at boss turn N, who was exposed?" from any captured log.
- Buff/debuff lifecycle with turn-by-turn flag transitions + attribution (who acted when the buff was consumed)
- Flag uptime percentages per hero
- Effect transitions per turn (excluding baseline passives) — shows buffs/debuffs placed/expired
- AoE applications (same effect kind placed on 2+ heroes in one turn — indicates AoE skill firing)
- Skills-used-per-turn inferred from `rdy:true→false` transitions on the active hero

Usage: `python3 tools/battle_log_analyze.py [path/to/battle_log.json]` (auto-loads most recent `battle_logs_cb_*.json` if no path given).

### MelonLoader Mod (`mod/RaidAutomationMod.cs`) — DEAD

Legacy MelonLoader plugin. **Incompatible with Unity 6000.0.60f1** ("No Support Module Loaded!" error). MelonLoader v0.7.2 does not support Unity 6000. The IL2CPP assembly cache was wiped during a debugging session and MelonLoader cannot regenerate it for this Unity version. Backup at `version.dll.melonloader` in the game build directory. Do not attempt to use or fix — use BepInEx instead.

### Mod Client (`Modules/mod_client.py`)

Python HTTP client wrapping the BepInEx mod API. Maps village HUD buttons to their Unity hierarchy paths (e.g., `"shop"` → `"UIManager/Canvas (Ui Root)/Dialogs/[DV] VillageHUD/.../ShopButton"`). Falls back gracefully if the mod isn't loaded.

**Working methods (endpoints exist in BepInEx mod):**
- `get_status()` → `/status`
- `get_buttons()` → `/buttons`
- `click_path()` / `click_button()` / `click_found()` → `/click`
- `get_artifacts()` → calls `/artifacts` — **BROKEN: endpoint does not exist in BepInEx mod** (use `/all-artifacts` instead)
- `sell_artifacts()` → calls `/sell` — **BROKEN: endpoint does not exist in BepInEx mod**
- `equip_artifact()` → `/equip` ✓
- `unequip_artifact()` → `/unequip` ✓
- `swap_artifact()` → `/swap` ✓
- `bulk_equip()` → `/bulk-equip` ✓
- `navigate()` → `/navigate` ✓
- `context_call()` / `arena_start_fight()` / `arena_start_battle()` / `cb_start_battle()` / `dismiss_battle_finish()` / `close_dialog()` → `/context-call` ✓ (endpoint exists, but may return "no MVVM context found" for some dialogs)

**Broken methods (endpoints do NOT exist in BepInEx mod):**
- `find_objects()` → `/find` — NOT IMPLEMENTED
- `get_toggles()` / `find_toggle()` / `set_sell_mode()` → `/toggles`, `/toggle` — NOT IMPLEMENTED
- `set_auto_dismiss()` → `/overlays` — NOT IMPLEMENTED (BepInEx has `/dismiss` for one-shot overlay removal)
- `get_shop_items()` → `/shopitems` — NOT IMPLEMENTED
- `get_view_contexts()` → `/view-context` — NOT IMPLEMENTED (use `/context-call` directly)

### Memory Reader (`Modules/memory_reader.py`)

Direct IL2CPP memory reading via pymem (828 lines). Replaces the dead RTK dependency with process memory access.

**How it works:**
- Attaches to `Raid.exe` process via `pymem.Pymem()`
- Finds `GameAssembly.dll` base address
- Resolves `AppModel` and `AppViewModel` singletons via IL2CPP TypeInfo pointer chains
- Reads game data by following field offsets from the Il2CppDumper output

**Singleton access chain:**
```
GA_BASE + TypeInfo_RVA -> klass
  -> +0xC8 (generic class info)
  -> +0x08 (specialized klass)
  -> +0xB8 (static_fields)
  -> +0x08 (_instance)
```

**What it reads:**
| Data | Method | Used For |
|------|--------|----------|
| Resources (energy, silver, gems, arena tokens, CB keys) | `get_resources()` | Skip tasks when empty |
| Account level & power | `get_account_level()`, `get_total_power()` | Logging |
| Hero roster (name, faction, rarity, grade, level, empower) | `get_heroes(with_names=True)` | Logging, future team building |
| Arena opponents (name, power, points, status) | `get_arena_opponents()` | Pick weakest target |
| Artifacts (set, rank, rarity, level, sell price) | `get_artifacts()` | Auto-sell bad gear |
| Battle state (Started/Finished/Stopped) | `get_battle_state()` | Instant battle detection |
| Current screen (497 ViewKeys) | `get_current_view()` | Navigation verification |
| Full account snapshot | `get_snapshot()` | Before/after comparison |

**Stubbed (offsets not yet mapped):**
- `get_active_events()` / `get_running_events()` — returns empty; event data offsets need mapping

**Offsets source:** Il2CppDumper v6.7.46 output for Raid v11.30.0 (metadata v31, Unity 6000.0.60).
Dump files at `C:\Tools\Il2CppDumper\output\` on the VM. Full ViewKey map at `C:\PyAutoRaid\offsets\viewkeys.json`.

**Key TypeInfo RVAs (in GameAssembly.dll):**
- AppModel: `0x4DC1558`
- AppViewModel: `0x4DC2A28`

**Offset update tooling:** `tools/update_offsets.py` — parses Il2CppDumper output after game patches, supports full dump+diff, dump-only, and verification modes.

**RTK status:** Dead. Raid Toolkit SDK v2.8.22 cannot parse IL2CPP metadata v31. `rtk_client.py` and `game_state.py` are legacy dead code. Port 9090 (RTK WebSocket) is still forwarded in QEMU but unused.

### Screen State (`Modules/screen_state.py`)

Handles game window management and image-based fallback navigation:
- Window resize/center to 900x600 (within 1024x768 VM desktop)
- Popup clearing (`exitAdd.png`, `closeLO.png`)
- `ensure_village()` — ESC + goBack + quit dialog handling + village verification
- `smart_click()` — locate image and click with retries

**Known issue:** May fail to find game window due to MainWindowHandle=0 (see hybrid controller notes above).

## VM Deployment (mothership2)

PyAutoRaid runs headless on a Windows 10 LTSC VM on the homelab server (Dell Optiplex i5-9600T, 16GB RAM).

### VM Details

| Property | Value |
|----------|-------|
| Host | mothership2 (`192.168.0.244`) |
| Hypervisor | QEMU/KVM (SeaBIOS, not UEFI) |
| VM specs | 4 vCPUs, 4GB RAM, 60GB AHCI/SATA disk, e1000 NIC |
| OS | Windows 10 Enterprise LTSC 2021 |
| VM user | `snoop` / `raid` |
| VM files | `/home/snoop/vms/win10-raid/` |
| Code | `C:\PyAutoRaid` (zip download from GitHub) |
| Game | `C:\Users\snoop\AppData\Local\PlariumPlay\StandAloneApps\raid-shadow-legends\build\` |
| Python | 3.12.4 (system-wide, on PATH) |

### Port Forwarding (QEMU user-mode networking)

| Host Port | Service |
|-----------|---------|
| 3389 | RDP (Windows Remote Desktop) — guest-forwarded |
| 5900 | VNC (QEMU native `-vnc :0`, NOT guest-forwarded) |
| 5985 | WinRM (PowerShell remoting) — guest-forwarded |
| 6790 | RaidAutomation BepInEx mod HTTP API — guest-forwarded |
| 9090 | RTK WebSocket API (legacy, unused) — guest-forwarded |

**VM screen resolution:** 1024x768 (game window resized to 900x600 by ScreenState)

### Scripts (`/home/snoop/vms/win10-raid/`)

- `start-vm.sh` — Boot the VM. Pass ISO path as arg for reinstall: `./start-vm.sh Win10.iso`
- `stop-vm.sh` — ACPI shutdown via QEMU monitor (Python, no socat needed)
- `type-cmd.py <text>` — Type a command into the VM via QEMU monitor sendkey
- `run-pyautoraid.sh` — Trigger automation (WinRM or manual VNC/RDP)

### Automation Schedule

**Linux cron (host):**
```
50 6 * * *  start-vm.sh   # Boot VM 10 min before first run
0 22 * * *  stop-vm.sh    # Shut down to free RAM for Minecraft
```

**Windows Scheduled Task "PyAutoRaid":**
- Runs `python C:\PyAutoRaid\Modules\hybrid_controller.py` at **7am, 1pm, 7pm**
- Plarium Play auto-starts with Windows and launches Raid via startup shortcut

### Daily Flow

1. **6:50am** — Linux cron starts the VM
2. **Boot** — Windows auto-logs in → Plarium Play launches Raid → BepInEx injects mod
3. **7am, 1pm, 7pm** — Scheduled Task runs `hybrid_controller.py`
4. **10pm** — Linux cron shuts down the VM

### Connecting to the VM

- **RDP (interactive):** `192.168.0.244:3389` — use "Windows App" on Mac (user `snoop`, pass `raid`)
- **VNC (view only):** `vncviewer 192.168.0.244:5900` (no password, no input — use for screenshots)
- **PowerShell via monitor:** `python3 type-cmd.py 'your-command-here'` from the server

### Windows Optimizations Applied

- Services disabled: SysMain, DiagTrack, WSearch, MapsBroker, Windows Update
- UAC disabled for admin user
- High performance power plan
- Notifications disabled

## Status & Future Work

### Completed
- **Phase 1**: Screen automation via PyAutoGUI (coordinate clicks + image matching)
- **Phase 2**: Direct IL2CPP memory reading via pymem — resources, heroes, artifacts, arena opponents, battle state, ViewKey navigation
- **Phase 3**: MelonLoader mod injection — now replaced by BepInEx (Phase 3b)
- **Phase 3b**: BepInEx mod — full game data access via HTTP API. Reads all heroes (536), all artifacts (2,680 including vault), account data (Great Hall, Arena, Clan level). Uses C# reflection over Il2CppInterop bindings — no hardcoded offsets, survives game updates.
- **Phase 4**: UNM Clan Boss team optimizer — game-accurate turn-by-turn simulation, 343-hero auto-profiled skills with exact StatusEffectTypeIds, game stat calculator integration

### Data Pipeline (fetch_heroes.py)
```bash
# Fetch all game data from the mod API (requires VM running with game logged in)
cd ~/projects/pyautoraid
python3 tools/fetch_heroes.py  # heroes_6star.json, heroes_all.json, all_artifacts.json, account_data.json, skills_db.json, hero_computed_stats.json

# CB tools
python3 tools/cb_potential.py                              # rank ALL 3654 team combos via turn-by-turn sim
python3 tools/cb_potential.py --team "ME,ME,Geomancer,Venus,Corvis the Corruptor"
python3 tools/gear_optimizer.py --team "..."                # constraint-based gear + sim
python3 tools/cb_sim.py --team "..." -v                     # verbose turn-by-turn simulation
python3 tools/cb_sim.py --monte-carlo 100                   # RNG variance test
python3 tools/speed_tune.py --preset budget_maneater        # validate speed tune
python3 tools/auto_skills.py                                # verify auto-generated skill profiles
```

### CB Reference Docs
- `docs/deadwoodjedi_speed_tunes.md` — All 40 DWJ speed tune compositions with speeds, requirements, auto status
- `docs/cb_team_analysis.md` — Full roster analysis, buildable team rankings, gear priorities, future goals

### CB Team Optimizer — Current State (v6, 2026-04-10)

**Architecture:**
1. `cb_sim.py` — game-accurate turn-by-turn simulator (tick-based TM, 10-slot debuff bar, exact poison/burn ticks, WM/GS, CA, ally attack, Geo passive, debuff extension, HP/survival/Gathering Fury, Leech healing, Ally Protect, Cardiel/UDK passives)
2. `auto_skills.py` — auto-generates SKILL_DATA + SKILL_EFFECTS for ALL 343 heroes from `skills_db.json` using **exact StatusEffectTypeId** (Poison=80, DEF Down=151, Weaken=350, Unkillable=320, Leech=460, etc.)
3. `status_effect_map.py` — complete StatusEffectTypeId → sim debuff/buff name mapping (from IL2CPP dump)
4. `cb_potential.py` — evaluates 3,654+ team combinations at full potential (6★ booked mastered, optimal gear)
5. `gear_optimizer.py` — constraint-based artifact assignment (SPD/ACC/HP hard constraints for UK and non-UK)

**Sim-verified best teams (with game-accurate stats + exact skill effects):**
- **#1 UK:** 2×Maneater + Geomancer + Venus + Corvis the Corruptor = **50.1M/key** (VALID tune, 0 gaps)
- **#2 UK:** 2×ME + Skullcrusher + Geomancer + Fayne = **49.1M** (0 gaps)
- **#3 UK:** 2×ME + Geomancer + Fayne + Fahrakin = **49.1M** (0 gaps)
- **Non-UK (user's team):** Cardiel + Ma'Shalled + Skullcrusher + Geomancer + Gnut = **23.1M** over 27 turns

**Game Stat Calculator Integration (from HeroExtensions static methods):**
The mod calls the game's OWN stat calculator for exact values:
- `GetBaseStats(hero)` → level-scaled base stats (HP multiplier=165, ATK/DEF=11.0 at 6★ L60) ✓
- `CalcBlessingBonus(hero)` → exact blessing bonuses (e.g., Cardiel +7,500 HP, +750 ATK) ✓
- `CalcArenaBonus(hero, ArenaLeagueId)` → exact arena bonuses (GoldII: Cardiel +3,144 HP) ✓
- `CalcBuildingsBonus(hero, BuildingSetup)` → exact Great Hall bonuses (Cardiel +1,965 HP) ✓
- `CalcEmpowerBonus(hero)` → empowerment bonuses ✓
- `CalcRelicsBonus(hero, relicSetups)` → relic bonuses (pending — 900 HP gap)
- Artifact bonuses computed in Python from raw artifact data ✓
- Saved to `hero_computed_stats.json` (511 heroes) — used as source of truth in `calc_stats()`

**StatusEffectTypeId Breakthrough:**
The mod reads `EffectType.ApplyStatusEffectParams.StatusEffectInfos[i].TypeId` to get EXACT buff/debuff types. This replaces guessing from generic KindId (5000=Poison family → now 80=Poison5%, 500=PoisonSensitivity, 470=HPBurn, etc.).

Key corrections from exact IDs:
- Maneater A1 places **Dec ATK 50%** (not Poison!)
- Maneater A3 places **Unkillable + Block Debuffs** (not Block Damage)
- Geomancer A3 places **HP Burn + Weaken 25%** (not Poison!)
- Corvis A1 places **Dec ATK**, A3 places **Poison + Poison Sensitivity**
- Skullcrusher A2 gives **Ally Protect + Counterattack + Unkillable**
- Venus A2 (CD3) has **DEF Down 60% + Weaken 25%**, A3 (CD5) has HP Burn

**Files:**
- `tools/cb_sim.py` — turn-by-turn simulator with auto-loaded skills from game data
- `tools/auto_skills.py` — auto-generates SKILL_DATA + SKILL_EFFECTS using exact StatusEffectTypeId
- `tools/status_effect_map.py` — StatusEffectTypeId enum → sim name mapping
- `tools/cb_potential.py` — full potential team ranker
- `tools/gear_optimizer.py` — constraint-based gear assignment (UK + non-UK modes)
- `tools/cb_optimizer.py` — stat calculator (uses game-computed stats when available)
- `tools/speed_tune.py` — Budget UK speed tune calculator (ME speeds 212-229 validated)
- `tools/raid_data.py` — game constants, mastery IDs, debuff uptimes
- `skills_db.json` — **343 heroes × 1,452 skills × 1,288 exact status effects** from game
- `hero_computed_stats.json` — **511 heroes** with game-computed base+blessing+arena+GH stats
- `heroes_all.json` — 536 heroes, `heroes_6star.json` — 46 with artifacts
- `all_artifacts.json` — 2,680 artifacts, `account_data.json` — Great Hall, Arena L22, Clan L18

**Non-UK Survival Model:**
Fully modeled: HP tracking, CB AoE damage (DEF formula), Gathering Fury (+2%/turn after T10), Lifesteal (30%), Leech (10%), Ally Protect (permanent passive on SC, or from A2 buffs), Cardiel passive (20% dmg reduction + Block Damage on dying ally), UDK passive (Unkillable at 1HP), Ma'Shalled A3 (50% dmg reduction), Gnut extra turns, Counter-attack healing chain, Block Debuffs prevents stun, Stalwart/Regen/Immortal sets. All passives auto-detected from skills_db.json.

**Remaining gaps:**
- Relic bonus (CalcRelicsBonus returns 0 — need hero-specific relic lookup, ~900 HP missing)
- Leader skill auras not applied
- Affinity weak/strong hit modifier
- Some passives need deeper modeling (Gnut extra turns = full extra turn with skill rotation, not just A1)
- `calc_stats()` does not add empowerment SPD/ACC/RES/CR/CD bonuses from computed stats — in-game speed is the only truth for speed tuning
- Evil Eye mastery: once per target per battle, NOT every A1

### Other Remaining Work
- **mod_client.py endpoint mismatch** — Many methods call endpoints that don't exist in BepInEx (`/find`, `/toggles`, `/toggle`, `/sell`, `/artifacts`, `/overlays`, `/shopitems`, `/view-context`). These need to be either removed or implemented in the mod.
- **Event data** — `get_active_events()` stubbed; need event data for dungeon farming decisions
- **Port 6790 from host** — mod binds to `+:6790` but QEMU user-mode networking forwards host:6790→VM:6790 successfully; also accessible via WinRM relay (`curl` on VM + base64 transfer for large responses)

## Artifact Data Pipeline — Critical Knowledge

All slot/stat/set mappings live in `tools/gear_constants.py` — single source of truth. Import from there.

### Slot IDs (ArtifactKindId enum)
```
1=Helmet, 2=Chest, 3=Gloves, 4=Boots, 5=Weapon, 6=Shield, 7=Ring, 8=Amulet(Cloak), 9=Banner
```
**WARNING**: NOT 1=Weapon. This was wrong for months and caused all artifact assignments to go to wrong slots.

### Stat IDs (StatKindId + IsAbsolute)
```
stat=1 flat=true → HP flat     stat=1 flat=false → HP%
stat=2 flat=true → ATK flat    stat=2 flat=false → ATK%
stat=3 flat=true → DEF flat    stat=3 flat=false → DEF%
stat=4 → SPD (always flat/additive)
stat=5 → RES    stat=6 → ACC    stat=7 → CR%    stat=8 → CD%
```
Verified against Teodor the Savant's in-game artifacts (2026-04-11). All values correct.

### Glyph Values
Stored in `ArtifactBonus.PowerUpValue` (Fixed type), separate from base `Value`. The mod exports as `"glyph"` field. Must add base + glyph for total stat contribution.

### Accessories are Faction-Locked
Ring/Amulet/Banner can only be equipped on heroes of the matching faction. The artifact data does NOT contain faction info — infer from which hero currently has it equipped. Gear optimizer must filter accessories to same-faction heroes only.

### CR/CD Detection
`ArtifactExtensions.ToStatKindId(bonus)` returns correct `ArtifactStatKindId` (10=CR, 11=CD) via reflection. Works for most equipped artifacts. The IL2CPP enum property getter can mismap CR/CD for some artifact types (gloves specifically). Use `ToStatKey()` as authoritative source.

## Equip System — Known Behaviors

### What Works
- **SwapArtifactCmd** (hero→hero): Persists across restart. Reliable.
- **DeactivateArtifactCmd** (unequip): Persists.
- Commands must run on Unity main thread via `RunOnMainThread`. Auto-initialize HTTP infrastructure from main thread.

### What Fails
- **ActivateArtifactCmd from vault**: Returns ok but often doesn't persist. Server rejects silently, game rolls back via async OnError.
- **Any equip on locked heroes**: Heroes in Arena Defense, 3v3, Siege, Hydra, or active multi-battle. Returns ok but server rejects.
- **Cross-faction accessories**: Server rejects.

### Hero Lock Causes (HeroLockCause enum)
Equipment-blocking: ArenaDefence(1), Arena3x3Defence(5), HydraLock(9), SiegeBuildingDefense(13), BackgroundBattleLocked(17), HeroInPreset(12).

### Best Practices
1. Always `fetch_heroes.py` before optimizer to get fresh artifact ownership
2. Protect already-assigned artifacts when gearing multiple heroes
3. Filter accessories by hero faction
4. Ensure heroes NOT in multi-battle/arena defense before equipping
5. CR ≥ 100% as hard constraint for DPS heroes
6. After failed equip session, restart Raid for clean state

## CB Simulator (`tools/cb_sim.py`)

Turn-by-turn Clan Boss damage simulator, DWJ-accurate mechanics.

### DWJ Speed Tune Mechanics
- **TM fill**: speed per tick, threshold 1000 (equivalent to DWJ's speed×0.07, threshold 100)
- **Tie-breaking**: highest TM → highest speed → position
- **Buff timing**: `isAddedThisTurn` — buffs don't tick on application turn. Critical for Unkillable.
- **Stun target**: Highest TM with skill on cooldown (`fromTargetsWithSkillOnCDSelectWithMaxStamina`)
- **Gathering Fury**: Round-based (+2% per round after round 4), NOT per-turn

### Skills from Game Data
`tools/load_game_profiles.py` reads `hero_profiles_game.json` (137 heroes). Key corrections found:
- **Maneater A3**: Unkillable 2T + Block Debuffs 2T (NOT 3T UK + 1T Block Damage)
- **Sicia A3**: Extra Turn (NOT Counterattack)
- **Ninja A1**: DEF Down 60% + 15% self TM (NOT just damage)
- **Ninja passive**: +20% ATK + 10% CD per combo on bosses
- **OB A2**: 12.4×ATK + Extra Turn + 30% ignore DEF

### Current Best CB Team
ME + Demytha + SC + Venomage + Sicia = ~63M (full auto, VALID tune)

## Gear Optimizer (`tools/gear_optimizer.py`)

### Stat Calculation
`calc_stats()` in `cb_optimizer.py` includes: base stats (L60 scaled), artifact primary+substats, Great Hall, Arena, empowerment (HP/ATK/DEF only), 2-piece set bonuses.

### Known Gaps
- **Empowerment SPD bonus not applied** — `calc_stats()` adds empowerment HP/ATK/DEF from computed stats but does NOT add empowerment SPD/ACC/RES/CR/CD. The fallback path (no computed stats) does add `emp_spd`. **In-game speed is the only source of truth for speed-tuned teams.**
- Lore of Steel mastery (+15% to set bonuses) — not applied
- 4-piece set bonuses — not recognized
- Leader skill auras — not modeled

## Mastery Tree IDs

Mastery IDs use format `500XYZ` where X=tree, Y=tier, Z=column:
- **X=1**: Offense (MasteryTreeId.Attack = 1 in game enum)
- **X=2**: Defense (MasteryTreeId.Defence = 2)
- **X=3**: Support (MasteryTreeId.Support = 3)

Example: `500161` = Offense tree (1), tier 6 (6), column 1 (1) = Warmaster

Note: EffectKindIds 5001/5002/5003 are UNRELATED (5001=TM manipulation, 5002=HP Burn, 5003=Debuff placement).

## Game Mechanics — Important Notes

- **Evil Eye mastery**: Places Dec TM (Turn Meter reduction) on A1 hits, but only **once per target per battle** (NOT every A1 hit). Does not stack or reapply.
- **Rings/Amulets cannot roll SPD substats** — this is a game rule, not a data error.
- **Accessories are faction-locked** — Ring/Amulet/Banner only equip on matching-faction heroes.

## Key Constraints

- **Windows-only**: Uses pywin32, PyGetWindow, Windows Task Scheduler
- **Resolution-dependent**: VM runs at 1024x768 desktop, game window resized to 900x600. Coordinate constants in `hybrid_controller.py` are game-relative (900x600). Legacy modules (`PyAutoRaid.py`, `DailyQuests.py`) assume 1920x1080 and are outdated.
- **Asset path handling**: Resolves `assets/` differently from source vs frozen PyInstaller exe (`sys._MEIPASS`)

