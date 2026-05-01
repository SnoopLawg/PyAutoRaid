// Auto-extracted from RaidAutomationPlugin.cs (slice: battle state).
// All methods are partial-class members of RaidAutomationPlugin.
// Behavior identical; isolates battle-state polling, /battle-state
// IL2CPP read path, /battle-log, /tick-log, and the AppendBattleHero
// helpers from the rest of the plugin.
using System;
using System.Collections;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using BepInEx;
using BepInEx.Logging;
using BepInEx.Unity.IL2CPP;
using HarmonyLib;
using Il2CppInterop.Runtime.Injection;
using UnityEngine;

namespace RaidAutomation
{
    public partial class RaidAutomationPlugin : BasePlugin
    {
        /// Return the FULL battle log. If clear=true, log is cleared after reading.
        /// </summary>
        private static string GetBattleLogFull(bool clear)
        {
            var sb = new StringBuilder(8192);
            // If no battle is currently active but we have a snapshot from the
            // most recently completed battle, serve that. Otherwise serve the
            // current (active or empty) log.
            List<string> source;
            int turns, polls;
            lock (_battleLog)
            {
                if (!_battleActive && _completedBattleLog.Count > 0)
                {
                    source = _completedBattleLog;
                    turns = _completedTurnCount;
                    polls = _completedPollCount;
                }
                else
                {
                    source = _battleLog;
                    turns = _battleCommandCount;
                    polls = _pollCount;
                }
                sb.Append("{\"active\":" + (_battleActive ? "true" : "false"));
                sb.Append(",\"turns\":" + turns);
                sb.Append(",\"polls\":" + polls);
                sb.Append(",\"log\":[");
                for (int i = 0; i < source.Count; i++)
                {
                    if (i > 0) sb.Append(",");
                    sb.Append(source[i]);
                }
                sb.Append("],\"count\":" + source.Count + "}");
                if (clear) { _battleLog.Clear(); _completedBattleLog.Clear(); }
            }
            return sb.ToString();
        }

        private string GetTickLog(bool clear)
        {
            var sb = new StringBuilder(8192);
            sb.Append("{\"ticks\":[");
            lock (_tickLog)
            {
                for (int i = 0; i < _tickLog.Count; i++)
                {
                    if (i > 0) sb.Append(",");
                    sb.Append(_tickLog[i]);
                }
                sb.Append("],\"count\":" + _tickLog.Count + "}");
                if (clear) _tickLog.Clear();
            }
            return sb.ToString();
        }

        private string GetBattleState()
        {
            var sb = new StringBuilder(4096);
            sb.Append("{");

            // Use Harmony-captured BattleProcessor instance
            if (_activeBattleProcessor != null && _battleActive)
            {
                try
                {
                    var ptrProp = _activeBattleProcessor.GetType().GetProperty("Pointer");
                    if (ptrProp != null)
                    {
                        IntPtr procPtr = (IntPtr)ptrProp.GetValue(_activeBattleProcessor);
                        if (procPtr != IntPtr.Zero)
                        {
                            sb.Append("\"found_via\":\"harmony\"");
                            sb.Append(",\"turns\":" + _battleCommandCount);

                            var heroData = ReadBattleHeroesIL2CPP(procPtr);
                            if (heroData != null)
                                sb.Append(",\"heroes\":" + heroData);

                            // Return recent log
                            lock (_battleLog)
                            {
                                sb.Append(",\"log_count\":" + _battleLog.Count);
                                sb.Append(",\"recent\":[");
                                int start = Math.Max(0, _battleLog.Count - 10);
                                for (int li = start; li < _battleLog.Count; li++)
                                {
                                    if (li > start) sb.Append(",");
                                    sb.Append(_battleLog[li]);
                                }
                                sb.Append("]");
                            }

                            sb.Append("}");
                            return sb.ToString();
                        }
                    }
                }
                catch (Exception ex)
                {
                    return "{\"error\":\"harmony read failed: " + Esc(ex.Message) + "\",\"turns\":" + _battleCommandCount + "}";
                }
            }

            // No active battle or no captured processor
            if (!_battleActive && _battleCommandCount > 0)
            {
                // Battle finished — return final log
                sb.Append("\"battle_finished\":true,\"total_turns\":" + _battleCommandCount);
                lock (_battleLog)
                {
                    sb.Append(",\"log_count\":" + _battleLog.Count);
                    sb.Append(",\"log\":[");
                    for (int li = 0; li < _battleLog.Count && li < 100; li++)
                    {
                        if (li > 0) sb.Append(",");
                        sb.Append(_battleLog[li]);
                    }
                    sb.Append("]");
                }
                sb.Append("}");
                return sb.ToString();
            }

            var appModel = GetAppModel();
            if (appModel == null)
                return "{\"error\":\"no active battle\",\"harmony_captured\":" + (_activeBattleProcessor != null) + "}";

            object battleAccess = null;
            string foundVia = null;

            // Path 1: Skip — AppModel Battle properties are managers, not live processors
            // (e.g., LiveArenaBattleRequestResponseManager is always present but not a battle)
            // Go directly to Path 4 (IL2CPP scan) for live battle detection

            // Path 2: Try well-known static types
            if (battleAccess == null)
            {
                string[] staticBattleTypes = {
                    "Client.ViewModel.Contextes.Battle.BattleContext",
                    "Client.Model.Gameplay.Battle.BattleFacade",
                    "Client.Model.Gameplay.Battle.BattleAccess",
                    "SharedModel.Battle.Core.BattleProcessor",
                    "Client.ViewModel.Battle.BattleViewModel"
                };

                foreach (var typeName in staticBattleTypes)
                {
                    try
                    {
                        var type = FindType(typeName);
                        if (type == null) continue;

                        // Try Instance/Current singleton
                        foreach (var pName in new[] { "Instance", "Current", "_instance" })
                        {
                            var p = type.GetProperty(pName, BindingFlags.Public | BindingFlags.Static | BindingFlags.NonPublic);
                            if (p != null)
                            {
                                try
                                {
                                    var val = p.GetValue(null);
                                    if (val != null)
                                    {
                                        battleAccess = val;
                                        foundVia = typeName + "." + pName;
                                        break;
                                    }
                                }
                                catch { }
                            }
                        }
                        if (battleAccess != null) break;

                        // Try static fields
                        foreach (var f in type.GetFields(BindingFlags.Public | BindingFlags.Static | BindingFlags.NonPublic))
                        {
                            try
                            {
                                if (f.FieldType.Name.Contains("Battle") || f.FieldType.Name.Contains("Processor"))
                                {
                                    var val = f.GetValue(null);
                                    if (val != null)
                                    {
                                        battleAccess = val;
                                        foundVia = typeName + "." + f.Name;
                                        break;
                                    }
                                }
                            }
                            catch { }
                        }
                        if (battleAccess != null) break;
                    }
                    catch { }
                }
            }

            // Path 3: Skip — UserWrapper.Battle is BattleWrapper (state tracker), not live processor
            // Path 4 (IL2CPP scan) handles live battle detection
            if (false && battleAccess == null)
            {
                try
                {
                    var uw = GetUserWrapper();
                    if (uw != null)
                    {
                        foreach (var prop in uw.GetType().GetProperties(
                            BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic))
                        {
                            try
                            {
                                string typeName = prop.PropertyType.Name;
                                if (typeName.Contains("Battle") || typeName.Contains("Combat"))
                                {
                                    var val = prop.GetValue(uw);
                                    if (val != null)
                                    {
                                        battleAccess = val;
                                        foundVia = "UserWrapper." + prop.Name + " (" + typeName + ")";
                                        break;
                                    }
                                }
                            }
                            catch { }
                        }
                    }
                }
                catch { }
            }

            // Path 4: Use raw IL2CPP to find BattleProcessor via MonoBehaviours
            // During battle, ClientBattleMode has a Processor property
            if (battleAccess == null)
            {
                try
                {
                    // Scan ALL MonoBehaviours in the ENTIRE scene for ANY that has
                    // get_Processor method (ClientBattleMode, PlayBattleMode, etc.)
                    // or get_Context returning a battle-related context
                    // Include inactive objects since battle views may be under non-standard parents
                    var allMBs = Resources.FindObjectsOfTypeAll<MonoBehaviour>();
                    foreach (var mb in allMBs)
                    {
                        if (mb == null) continue;
                        try
                        {
                            IntPtr monoPtr = mb.Pointer;
                            if (monoPtr == IntPtr.Zero) continue;
                            IntPtr monoClass = il2cpp_object_get_class(monoPtr);
                            if (monoClass == IntPtr.Zero) continue;

                            string className = Marshal.PtrToStringAnsi(il2cpp_class_get_name(monoClass));
                            if (className == null) continue;

                            // Skip obvious non-battle types for performance
                            if (className.StartsWith("UI") || className.StartsWith("TMP") ||
                                className.StartsWith("Canvas") || className.StartsWith("Layout") ||
                                className.StartsWith("Image") || className.StartsWith("Text") ||
                                className.StartsWith("Scroll") || className.StartsWith("Mask")) continue;

                            // Check if this MB has get_Processor via IL2CPP method scan
                            IntPtr getProcMethod = FindIL2CPPMethod(monoClass, "get_Processor", 0);

                            if (getProcMethod != IntPtr.Zero)
                            {
                                IntPtr exc = IntPtr.Zero;
                                IntPtr procObj = il2cpp_runtime_invoke(getProcMethod, monoPtr, IntPtr.Zero, ref exc);
                                if (procObj != IntPtr.Zero && exc == IntPtr.Zero)
                                {
                                    // Wrap the raw pointer into a managed object via Il2CppObjectBase
                                    var procType = FindType("SharedModel.Battle.Core.BattleProcessor");
                                    if (procType != null)
                                    {
                                        try
                                        {
                                            // Create managed wrapper: new Il2CppObjectBase(ptr)
                                            battleAccess = Activator.CreateInstance(procType, procObj);
                                            foundVia = "IL2CPP." + className + ".Processor";
                                        }
                                        catch
                                        {
                                            // Can't wrap — use raw pointer approach instead
                                            // Read heroes directly from the processor via IL2CPP
                                            IntPtr procClass = il2cpp_object_get_class(procObj);
                                            string procClassName = Marshal.PtrToStringAnsi(il2cpp_class_get_name(procClass));
                                            foundVia = "IL2CPP." + className + ".Processor (raw " + procClassName + ")";

                                            // Read Context.Setup.Heroes from the processor
                                            sb.Append("\"found_via\":\"" + Esc(foundVia) + "\"");
                                            sb.Append(",\"battle_mode\":\"" + Esc(className) + "\"");

                                            // Get Statistics.StatisticsByHero for per-hero data
                                            var heroData = ReadBattleHeroesIL2CPP(procObj);
                                            if (heroData != null)
                                            {
                                                sb.Append(",\"heroes\":" + heroData);
                                                sb.Append("}");
                                                return sb.ToString();
                                            }
                                            else
                                            {
                                                sb.Append(",\"error\":\"found processor but could not read heroes\"}");
                                                return sb.ToString();
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        catch { }
                        if (battleAccess != null) break;
                    }
                }
                catch { }
            }

            if (battleAccess == null)
            {
                // Return discovery info: list all AppModel properties for debugging
                sb.Append("\"error\":\"No active battle found\",\"discovery\":{");
                sb.Append("\"appmodel_props\":[");
                int pi = 0;
                try
                {
                    foreach (var prop in _appModelType.GetProperties(
                        BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic))
                    {
                        if (pi > 0) sb.Append(",");
                        sb.Append("\"" + Esc(prop.Name + ":" + prop.PropertyType.Name) + "\"");
                        pi++;
                    }
                }
                catch { }
                sb.Append("]}}");
                return sb.ToString();
            }

            sb.Append("\"found_via\":\"" + Esc(foundVia) + "\"");

            // Navigate from battleAccess down to BattleProcessor
            var battleProcessor = FindBattleProcessor(battleAccess);
            if (battleProcessor == null)
            {
                // Dump what we found for debugging
                sb.Append(",\"access_type\":\"" + Esc(battleAccess.GetType().FullName ?? "unknown") + "\"");
                sb.Append(",\"access_props\":[");
                int pi2 = 0;
                try
                {
                    foreach (var prop in battleAccess.GetType().GetProperties(
                        BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic))
                    {
                        if (pi2 > 0) sb.Append(",");
                        sb.Append("\"" + Esc(prop.Name + ":" + prop.PropertyType.Name) + "\"");
                        pi2++;
                    }
                }
                catch { }
                sb.Append("],\"error\":\"Found battle access but could not locate BattleProcessor\"}");
                return sb.ToString();
            }

            sb.Append(",\"processor_type\":\"" + Esc(battleProcessor.GetType().FullName ?? "unknown") + "\"");

            // Read battle context/state
            try
            {
                var context = Prop(battleProcessor, "Context");
                if (context != null)
                {
                    var stateEnum = Prop(context, "State");
                    if (stateEnum != null)
                        sb.Append(",\"battle_state\":\"" + Esc(stateEnum.ToString()) + "\"");
                    var activeHero = Prop(context, "ActiveHeroId");
                    if (activeHero != null)
                        sb.Append(",\"active_hero_id\":" + Convert.ToInt32(activeHero));
                }
            }
            catch { }

            // Find heroes in the battle via multiple possible paths
            object heroList = null;
            string heroesPath = null;
            string[] heroPaths = {
                "Context.Setup.Heroes",
                "Heroes",
                "Context.Heroes",
                "State.Heroes",
                "Context.State.Heroes"
            };

            foreach (var hpath in heroPaths)
            {
                try
                {
                    object cur = battleProcessor;
                    bool valid = true;
                    foreach (var part in hpath.Split('.'))
                    {
                        cur = Prop(cur, part);
                        if (cur == null) { valid = false; break; }
                    }
                    if (valid && cur != null)
                    {
                        heroList = cur;
                        heroesPath = hpath;
                        break;
                    }
                }
                catch { }
            }

            if (heroList == null)
            {
                // Dump processor properties for discovery
                sb.Append(",\"processor_props\":[");
                int pi3 = 0;
                try
                {
                    foreach (var prop in battleProcessor.GetType().GetProperties(
                        BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic))
                    {
                        if (pi3 > 0) sb.Append(",");
                        sb.Append("\"" + Esc(prop.Name + ":" + prop.PropertyType.Name) + "\"");
                        pi3++;
                    }
                }
                catch { }
                sb.Append("],\"error\":\"Could not find hero list in BattleProcessor\"}");
                return sb.ToString();
            }

            sb.Append(",\"heroes_path\":\"" + Esc(heroesPath) + "\"");

            // Iterate heroes — try as Dictionary first, then as List
            sb.Append(",\"heroes\":[");
            int heroIdx = 0;
            try
            {
                IEnumerable<object> heroItems;
                try
                {
                    var valProp = heroList.GetType().GetProperty("Values");
                    if (valProp != null && heroList.GetType().Name.Contains("Dict"))
                        heroItems = DictValues(heroList);
                    else
                        heroItems = ListItems(heroList);
                }
                catch
                {
                    heroItems = ListItems(heroList);
                }

                foreach (var hero in heroItems)
                {
                    if (hero == null) continue;
                    if (heroIdx > 0) sb.Append(",");
                    sb.Append("{");
                    try
                    {
                        AppendBattleHero(sb, hero);
                    }
                    catch (Exception ex)
                    {
                        sb.Append("\"error\":\"" + Esc(ex.Message) + "\"");
                    }
                    sb.Append("}");
                    heroIdx++;
                }
            }
            catch (Exception ex)
            {
                sb.Append("{\"error\":\"" + Esc("Hero iteration failed: " + ex.Message) + "\"}");
            }
            sb.Append("]");

            // Statistics (round count, etc.)
            try
            {
                var stats = Prop(battleProcessor, "Statistics");
                if (stats != null)
                {
                    sb.Append(",\"has_statistics\":true");
                    var round = Prop(stats, "Round");
                    if (round != null) sb.Append(",\"round\":" + Convert.ToInt32(round));
                }
            }
            catch { }

            sb.Append("}");
            return sb.ToString();
        }

        /// <summary>
        /// Read hero data from a BattleProcessor via raw IL2CPP pointers.
        /// Returns a JSON array string of hero data, or null on failure.
        /// </summary>
        private string ReadBattleHeroesIL2CPP(IntPtr processorPtr)
        {
            try
            {
                // BattleProcessor.State has PlayerTeam and EnemyTeam (NOT a flat Heroes list).
                // Diagnostic: BattleState get_* = [PlayerTeam, EnemyTeam, SkipViewData]
                IntPtr stateObj = IL2CPPCallGetter(processorPtr, "get_State");
                if (stateObj == IntPtr.Zero) return null;

                IntPtr playerTeam = IL2CPPCallGetter(stateObj, "get_PlayerTeam");
                IntPtr enemyTeam = IL2CPPCallGetter(stateObj, "get_EnemyTeam");

                var allHeroes = new StringBuilder();
                allHeroes.Append("[");
                int idx = 0;
                foreach (var teamInfo in new[] { ("player", playerTeam), ("enemy", enemyTeam) })
                {
                    string side = teamInfo.Item1;
                    IntPtr team = teamInfo.Item2;
                    if (team == IntPtr.Zero) continue;

                    // BattleTeam exposes get_HeroesWithGuardian (confirmed via diag 2026-04-13)
                    IntPtr teamHeroes = IL2CPPCallGetter(team, "get_HeroesWithGuardian");
                    if (teamHeroes == IntPtr.Zero) teamHeroes = IL2CPPCallGetter(team, "get_Heroes");
                    if (teamHeroes == IntPtr.Zero) teamHeroes = IL2CPPCallGetter(team, "get_Members");
                    if (teamHeroes == IntPtr.Zero) teamHeroes = IL2CPPCallGetter(team, "get_Units");
                    if (teamHeroes == IntPtr.Zero)
                    {
                        // As last resort, try "get_All" or team IS the collection
                        teamHeroes = team;
                    }
                    if (teamHeroes == IntPtr.Zero) continue;

                    // Append team members to output
                    int added = AppendTeamHeroes(allHeroes, teamHeroes, side, ref idx);
                    // If team was actually not a collection (added==-1), emit diag hint and skip
                    if (added < 0)
                    {
                        // Could not iterate — skip silently; diag path in PollBattleState will log
                    }
                }
                allHeroes.Append("]");
                string result = allHeroes.ToString();
                // If no heroes were appended, treat as failure so diag fires
                if (result == "[]") return null;
                return result;
            }
            catch
            {
                return null;
            }
        }

        /// <summary>
        /// Append heroes from a Team's collection to sb. Returns count added, or -1 on failure.
        /// </summary>
        private int AppendTeamHeroes(StringBuilder sb, IntPtr heroesObj, string side, ref int globalIdx)
        {
            try
            {
                IntPtr heroesClass = il2cpp_object_get_class(heroesObj);
                IntPtr getCount = FindIL2CPPMethod(heroesClass, "get_Count", 0);
                IntPtr getItem = FindIL2CPPMethod(heroesClass, "get_Item", 1);
                if (getCount == IntPtr.Zero || getItem == IntPtr.Zero) return -1;
                // DEFER to the existing per-hero reader below by jumping into the original
                // iterate logic via a shared helper. Reuse the main path below.
                return IterateHeroList(sb, heroesObj, getCount, getItem, side, ref globalIdx);
            }
            catch { return -1; }
        }

        private int IterateHeroList(StringBuilder sb, IntPtr heroesObj, IntPtr getCount, IntPtr getItem, string side, ref int globalIdx)
        {
            IntPtr exc = IntPtr.Zero;
            IntPtr countResult = il2cpp_runtime_invoke(getCount, heroesObj, IntPtr.Zero, ref exc);
            if (countResult == IntPtr.Zero) return -1;
            int count = Marshal.ReadInt32(countResult + 0x10);
            int added = 0;
            for (int i = 0; i < count && i < 20; i++)
            {
                if (globalIdx > 0) sb.Append(",");
                sb.Append("{\"side\":\"" + side + "\"");
                try
                {
                    IntPtr intBuf = Marshal.AllocHGlobal(4);
                    Marshal.WriteInt32(intBuf, i);
                    IntPtr argsArr = Marshal.AllocHGlobal(IntPtr.Size);
                    Marshal.WriteIntPtr(argsArr, intBuf);
                    IntPtr exc2 = IntPtr.Zero;
                    IntPtr heroObj = il2cpp_runtime_invoke(getItem, heroesObj, argsArr, ref exc2);
                    Marshal.FreeHGlobal(intBuf);
                    Marshal.FreeHGlobal(argsArr);
                    if (heroObj != IntPtr.Zero) AppendHeroFields(sb, heroObj);
                }
                catch { }
                sb.Append("}");
                globalIdx++;
                added++;
            }
            return added;
        }

        // BaseTypeId -> Element (1=Magic, 2=Force, 3=Spirit, 4=Void). Populated
        // lazily on first battle poll per type id; zero cost thereafter.
        private static readonly Dictionary<int, int> _typeIdToElement = new();

        private int GetElementForTypeId(int typeId)
        {
            if (typeId <= 0) return 0;
            lock (_typeIdToElement)
            {
                if (_typeIdToElement.TryGetValue(typeId, out int cached)) return cached;
            }
            int element = 0;
            try
            {
                var appModel = GetAppModel();
                var staticData = Prop(appModel, "StaticData");
                var heroData = Prop(staticData, "HeroData");
                var htDict = Prop(heroData, "HeroTypeById");
                if (htDict != null)
                {
                    var containsKey = htDict.GetType().GetMethod("ContainsKey");
                    if (containsKey != null && (bool)containsKey.Invoke(htDict, new object[] { typeId }))
                    {
                        var itemProp = htDict.GetType().GetProperty("Item");
                        var heroType = itemProp?.GetValue(htDict, new object[] { typeId });
                        var forms = Prop(heroType, "Forms");
                        if (forms != null)
                        {
                            foreach (var form in ListItems(forms))
                            {
                                element = IntProp(form, "Element");
                                if (element > 0) break;
                            }
                        }
                    }
                }
            }
            catch { }
            lock (_typeIdToElement) { _typeIdToElement[typeId] = element; }
            return element;
        }

        // Status flags on BattleHero that we serialize as a string-array "st":[...]
        // Ordered roughly by frequency; only emit flags that are TRUE.
        // NOTE on naming:
        //   - `block_damage` is IsInvincible (Raid's internal name for the Block Damage buff;
        //     "Invincible" as a status effect and "Block Damage" as a buff share this flag).
        //   - `uk_saved` is IsUnkillable which ONLY flips true when the hero is actively being
        //     saved from death by the UK buff (i.e. at 0 HP). It does NOT reflect "has UK buff
        //     applied" -- that state lives in the active-effects list, not HeroState.
        private static readonly (string getter, string key)[] HeroStatusFlags = new[] {
            ("get_IsDead", "dead"),
            ("get_IsDying", "dying"),
            ("get_IsStunned", "stun"),
            ("get_IsFrozen", "freeze"),
            ("get_IsSleep", "sleep"),
            ("get_IsProvoked", "provoke"),
            ("get_IsBanished", "banish"),
            ("get_IsGrabbed", "grab"),
            ("get_IsEntangled", "entangle"),
            ("get_IsDevoured", "devour"),
            ("get_IsAbsent", "absent"),
            ("get_IsEnfeeble", "enfeeble"),
            ("get_IsStaminaTickBlocked", "no_tm_tick"),
            ("get_IsBlockHeal", "block_heal"),
            ("get_IsUnderNullifier", "nullifier"),
            ("get_UnderPetrification", "petrify"),
            ("get_UnderSimpleStoneSkin", "ss_simple"),
            ("get_UnderReflectiveStoneSkin", "ss_reflect"),
            ("get_UnderStoneSkin", "ss"),
            ("get_IsInvincible", "block_damage"),        // was "invincible" — renamed for clarity
            ("get_IsBlockDebuff", "block_debuff"),
            ("get_IsTaunt", "taunt"),
            ("get_IsRages", "rages"),
            ("get_IsInvisible", "invis"),
            ("get_IsTransformed", "xform"),
            ("get_HeroPassiveSkillsBlocked", "pass_blk"),
            ("get_ActiveSkillsBlocked", "act_blk"),
        };

        private void AppendHeroFields(StringBuilder sb, IntPtr heroObj)
        {
            IntPtr heroClass = il2cpp_object_get_class(heroObj);

            // Identity: Id (battle hero id), BaseTypeId (matches static HeroType.Id)
            AppendIntGetter(sb, heroClass, heroObj, "get_Id", "id");
            AppendIntGetter(sb, heroClass, heroObj, "get_BaseTypeId", "type_id");

            // Element (1=Magic, 2=Force, 3=Spirit, 4=Void). Cached by BaseTypeId
            // for zero-cost lookup on subsequent polls; first hit goes through
            // StaticData.HeroData.HeroTypeById -> Forms[0].Element.
            try
            {
                int btid = 0;
                IntPtr gbt = FindIL2CPPMethod(heroClass, "get_BaseTypeId", 0);
                if (gbt != IntPtr.Zero)
                {
                    IntPtr exc = IntPtr.Zero;
                    IntPtr res = il2cpp_runtime_invoke(gbt, heroObj, IntPtr.Zero, ref exc);
                    if (res != IntPtr.Zero) btid = Marshal.ReadInt32(res + 0x10);
                }
                if (btid > 0)
                {
                    int element = GetElementForTypeId(btid);
                    if (element > 0) sb.Append(",\"element\":" + element);
                }
            }
            catch { }

            // HP: MaxHealth - DestroyedHealth = current; HealthPerc is %*100 (Fixed)
            AppendFixedGetter(sb, heroClass, heroObj, "get_MaxHealth", "hp_max");
            AppendFixedGetter(sb, heroClass, heroObj, "get_DestroyedHealth", "hp_lost");
            AppendFixedGetter(sb, heroClass, heroObj, "get_HealthPerc", "hp_pct", percent: true);

            // TM
            AppendFixedGetter(sb, heroClass, heroObj, "get_Stamina", "tm");

            // Direct field reads (offsets from diag 2026-04-13):
            // DamageTaken @0x60 (Fixed) — REAL damage; 'hp_lost' can stay 0 in boss shield / force-affinity phase
            // TurnCount   @0xE8 (int32) — in-game turn counter the UI shows (vs _battleCommandCount which counts every ProcessStartTurn)
            // Health      @0x58 (Fixed) — current live HP (same as hp_max - destroyed typically; useful for sanity check)
            AppendFixedFieldAtOffset(sb, heroObj, 0x60, "dmg_taken");
            AppendInt32FieldAtOffset(sb, heroObj, 0xE8, "turn_n");
            AppendFixedFieldAtOffset(sb, heroObj, 0x58, "hp_cur");
            // AbsorbedDamageByEffectKindId @0x68 (Dict<int, Fixed>) — total damage absorbed
            // by each effect kind on this hero. If UK/BD absorbed damage, entries live here
            // keyed by EffectKindId. Use this as the authoritative "is UK/BD really present"
            // signal (at least retrospectively).
            AppendAbsorbedDamage(sb, heroObj);
            // StatImpactByEffects @0xA0 → _statsImpactByEffect dict @0x18 — per-effect active
            // stat modifications. Schema confirmed via diag: stride=0x28 entries with
            // (Fixed_value, StatKindId, EffectContext) tuple. We emit (effect_id, kind, value)
            // tuples; consumers can look up effect_id in skills_db / status_effect_map for label.
            AppendStatModEffects(sb, heroObj);
            // Counters @0x138 — Dict<int, Fixed>. Hypothesis: keys are StatusEffectTypeId
            // (320=Unkillable, 40=BlockDamage, …) and values = turns-remaining. Emit as
            // "ctr":{key:val} so the analyzer can detect the Unkillable BUFF directly.
            AppendCountersDict(sb, heroObj, 0x138, "ctr");
            // CountersByUnique @0x140 — Dict<int, HashSet<int>>. Emit per-key set size.
            AppendCountersByUniqueDict(sb, heroObj, 0x140, "ctr_uniq");

            // Core flags emitted individually (cheap and useful)
            // NOTE: `uk_saved` = IsUnkillable which ONLY returns true when hero is at 0 HP and
            // being saved from death by the UK buff. For "UK buff is applied but not yet triggered"
            // state, use the "uk_buff" derived field below (from Challenges dict or skill-cast inference).
            AppendBoolGetter(sb, heroClass, heroObj, "get_IsUnkillable", "uk_saved");
            AppendBoolGetter(sb, heroClass, heroObj, "get_IsBoss", "boss");
            AppendBoolGetter(sb, heroClass, heroObj, "get_CanAttack", "can_atk");
            AppendBoolGetter(sb, heroClass, heroObj, "get_MustSkipTurn", "skip");
            // Attempt to count active challenges (Raid's internal active-effect container)
            AppendChallengeCount(sb, heroObj);

            // Status flag summary — only include flags that are currently TRUE
            var active = new List<string>();
            foreach (var (g, k) in HeroStatusFlags)
            {
                IntPtr m = FindIL2CPPMethod(heroClass, g, 0);
                if (m == IntPtr.Zero) continue;
                IntPtr e = IntPtr.Zero;
                IntPtr r = il2cpp_runtime_invoke(m, heroObj, IntPtr.Zero, ref e);
                if (r != IntPtr.Zero && Marshal.ReadByte(r + 0x10) != 0) active.Add(k);
            }
            if (active.Count > 0)
            {
                sb.Append(",\"st\":[");
                for (int i = 0; i < active.Count; i++) { if (i>0) sb.Append(","); sb.Append("\""+active[i]+"\""); }
                sb.Append("]");
            }

            // Skills: HeroSkills collection, per-skill {type, ready, blocked}
            AppendHeroSkills(sb, heroObj, heroClass);

            // Applied buffs/debuffs from HeroState — class-name only (no data reads yet)
            AppendAppliedBuffsDebuffs(sb, heroObj);

            // Active effects with durations — from PhaseEffects._effectsByPhaseIndex.
            // Array index = turns until expiry (0 = expiring this turn, 1 = next turn, ...).
            // Each entry: EffectType with {Id@0x10, KindId@0x14, Count@0x68, StackCount@0x6C}.
            AppendActiveEffects(sb, heroObj);
        }

        /// <summary>
        /// Read Challenges dict (at 0xE0) count. If populated, this is where effect-based
        /// constraints like Unkillable-buff tracking may live.
        /// </summary>
        private void AppendChallengeCount(StringBuilder sb, IntPtr heroObj)
        {
            try
            {
                IntPtr dict = Marshal.ReadIntPtr(heroObj + 0xE0);
                if (dict == IntPtr.Zero) return;
                // Dict<K,V>._count is at offset 0x20 (confirmed from prior diag)
                int count = Marshal.ReadInt32(dict + 0x20);
                if (count > 0) sb.Append(",\"chl\":" + count);
            }
            catch { }
        }

        /// <summary>
        /// Read AbsorbedDamageByEffectKindId dict @0x68 — Dictionary&lt;int (EffectKindId), Fixed (cumulative)&gt;.
        /// Walks the dict's _entries array and emits per-kind absorbed totals.
        /// EffectKindId values seen so far in our schema diags include 4013, 4014, 6000, 7003, 7004, 9028, 9030, etc.
        /// We don't yet have a clean kind→name mapping; emit raw {kind: total} pairs.
        /// </summary>
        private void AppendAbsorbedDamage(StringBuilder sb, IntPtr heroObj)
        {
            try
            {
                IntPtr dict = Marshal.ReadIntPtr(heroObj + 0x68);
                if (dict == IntPtr.Zero) return;
                int count = Marshal.ReadInt32(dict + 0x20);
                if (count <= 0) return;
                IntPtr entries = Marshal.ReadIntPtr(dict + 0x18);
                if (entries == IntPtr.Zero) return;
                long arrLen = Marshal.ReadInt64(entries + 0x18);
                // Entry<int, Fixed>: hashCode(4) + next(4) + key(4) + pad(4) + value(8 = Fixed raw long), stride = 0x18
                sb.Append(",\"abs\":{");
                bool first = true;
                int emitted = 0;
                for (int e = 0; e < arrLen && emitted < 32; e++)
                {
                    IntPtr entryAddr = entries + 0x20 + e * 0x18;
                    int hashCode = Marshal.ReadInt32(entryAddr + 0x00);
                    if (hashCode == 0) continue;
                    int kind = Marshal.ReadInt32(entryAddr + 0x08);
                    long fixedRaw = Marshal.ReadInt64(entryAddr + 0x10);
                    long val = fixedRaw >> 32;  // Fixed 32.32 → display
                    if (val <= 0) continue;
                    if (!first) sb.Append(",");
                    first = false;
                    sb.Append("\"" + kind + "\":" + val);
                    emitted++;
                }
                sb.Append("}");
            }
            catch { }
        }

        /// <summary>
        /// Read StatImpactByEffects._statsImpactByEffect dict — active stat-modifying effects
        /// (DEF Down, ATK Down, Weaken, mastery passives, etc.). Each entry holds
        /// (Fixed value, StatKindId, EffectContext).
        ///
        /// Output shape per hero: "mods":[{id,k,v}, ...] where:
        ///   id = effect_id (key) — looks up in skills_db / mastery tables
        ///   k  = StatKindId (1=HP, 2=ATK, 3=DEF, 4=SPD, 5=RES, 6=ACC, 7=CR, 8=CD, others = special)
        ///   v  = signed value (% if k in {1..8 and >|10|}, otherwise flat). Display = raw >> 32.
        /// </summary>
        /// <summary>
        /// Read a Dict&lt;int, Fixed&gt; at the given field offset and emit as "key":{int:long, ...}.
        /// Used for Counters @0x138 which holds StatusEffectTypeId-like keys → turns-remaining.
        ///
        /// IL2CPP .NET layout for Dict&lt;int, Fixed&gt;.Entry is 0x18 bytes but ordering can be:
        ///   (a) hashCode@0, next@4, key@8, pad@C, value@0x10  (classic .NET)
        ///   (b) next@0, hashCode@4, key@8, pad@C, value@0x10  (seen in some IL2CPP builds)
        /// Empirically (2026-04-13) on this game, reading key@0x08 returned -1 which is the
        /// "freelist next marker", so the real key lives elsewhere. Try key@0x04 instead.
        /// </summary>
        private void AppendCountersDict(StringBuilder sb, IntPtr heroObj, int fieldOffset, string label)
        {
            try
            {
                IntPtr dict = Marshal.ReadIntPtr(heroObj + fieldOffset);
                if (dict == IntPtr.Zero) return;
                int count = Marshal.ReadInt32(dict + 0x20);
                if (count <= 0) return;
                IntPtr entries = Marshal.ReadIntPtr(dict + 0x18);
                if (entries == IntPtr.Zero) return;
                long arrLen = Marshal.ReadInt64(entries + 0x18);
                sb.Append(",\"" + label + "\":{");
                bool first = true;
                int emitted = 0;
                for (int e = 0; e < arrLen && emitted < 48; e++)
                {
                    IntPtr entryAddr = entries + 0x20 + e * 0x18;
                    int w0 = Marshal.ReadInt32(entryAddr + 0x00);
                    int w1 = Marshal.ReadInt32(entryAddr + 0x04);
                    int w2 = Marshal.ReadInt32(entryAddr + 0x08);
                    long v64 = Marshal.ReadInt64(entryAddr + 0x10);
                    // Skip freelist / empty slots: in .NET, deleted entries have hashCode=-1
                    // and next points to freelist head. Occupied entries have hashCode >= 0
                    // OR in newer impls, (next >= -1 treated as occupied if key is set).
                    // Heuristic: any int key in [0, 10_000_000] is a valid StatusEffectTypeId / mastery.
                    int key = -1;
                    if (w1 >= 0 && w1 < 10_000_000) key = w1;
                    else if (w2 >= 0 && w2 < 10_000_000) key = w2;
                    else if (w0 >= 0 && w0 < 10_000_000) key = w0;
                    if (key < 0) continue;
                    long val = v64 >> 32;
                    if (!first) sb.Append(",");
                    first = false;
                    sb.Append("\"" + key + "\":" + val);
                    emitted++;
                }
                sb.Append("}");
            }
            catch { }
        }

        /// <summary>One-shot diag: dump the raw first 4 entries of Counters dict for a hero,
        /// showing all 4-byte words at each entry offset so we can determine the real layout.</summary>
        /// <summary>One-shot diag: dump ALL BattleHero methods (not just 0-arg getters),
        /// all HeroState fields (no cap), and search for any HasBuff/HasEffect/GetEffect APIs
        /// that might return Unkillable-buff state directly.</summary>
        internal bool TryEmitBuffApiDiag(IntPtr procPtr)
        {
            var sb = new StringBuilder();
            sb.Append("{\"diag\":\"buff_api\"");
            try
            {
                IntPtr stateObj = IL2CPPCallGetter(procPtr, "get_State");
                if (stateObj == IntPtr.Zero) { sb.Append(",\"err\":\"no state\"}"); LogDiag(sb); return false; }
                IntPtr team = IL2CPPCallGetter(stateObj, "get_PlayerTeam");
                if (team == IntPtr.Zero) { sb.Append(",\"err\":\"no team\"}"); LogDiag(sb); return false; }
                IntPtr heroesColl = IL2CPPCallGetter(team, "get_HeroesWithGuardian");
                IntPtr hc = il2cpp_object_get_class(heroesColl);
                IntPtr getI = FindIL2CPPMethod(hc, "get_Item", 1);
                IntPtr ib = Marshal.AllocHGlobal(4); Marshal.WriteInt32(ib, 0);
                IntPtr ab = Marshal.AllocHGlobal(IntPtr.Size); Marshal.WriteIntPtr(ab, ib);
                IntPtr eIt = IntPtr.Zero;
                IntPtr heroObj = il2cpp_runtime_invoke(getI, heroesColl, ab, ref eIt);
                Marshal.FreeHGlobal(ib); Marshal.FreeHGlobal(ab);
                if (heroObj == IntPtr.Zero) { sb.Append(",\"err\":\"no hero\"}"); LogDiag(sb); return false; }

                IntPtr heroClass = il2cpp_object_get_class(heroObj);

                // Dump ALL BattleHero methods (not just get_*/0-arg)
                var allMethods = new List<string>();
                IntPtr kH = heroClass;
                while (kH != IntPtr.Zero && allMethods.Count < 400)
                {
                    IntPtr mIter = IntPtr.Zero; IntPtr m;
                    while ((m = il2cpp_class_get_methods(kH, ref mIter)) != IntPtr.Zero)
                    {
                        string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                        if (mn == null) continue;
                        uint pc = il2cpp_method_get_param_count(m);
                        allMethods.Add(mn + "/" + pc);
                    }
                    kH = il2cpp_class_get_parent(kH);
                    string pn = kH != IntPtr.Zero ? Marshal.PtrToStringAnsi(il2cpp_class_get_name(kH)) : "";
                    if (pn == "Object" || pn == "Il2CppObjectBase" || string.IsNullOrEmpty(pn)) break;
                }
                // Filter to buff/effect/has/get-related
                var interesting = allMethods.Where(mn => {
                    var ln = mn.ToLowerInvariant();
                    return ln.Contains("buff") || ln.Contains("effect") || ln.Contains("has")
                        || ln.Contains("status") || ln.Contains("unkillable") || ln.Contains("blockdam")
                        || ln.Contains("getall") || ln.Contains("active");
                }).ToList();
                sb.Append(",\"hero_methods_all_count\":" + allMethods.Count);
                sb.Append(",\"hero_methods_interesting\":[");
                for (int i = 0; i < interesting.Count && i < 100; i++)
                {
                    if (i > 0) sb.Append(",");
                    sb.Append("\"" + Esc(interesting[i]) + "\"");
                }
                sb.Append("]");

                // Dump HeroState fields (full, cap 80)
                IntPtr heroState = Marshal.ReadIntPtr(heroObj + 0xC0);
                if (heroState != IntPtr.Zero)
                {
                    IntPtr hsCls = il2cpp_object_get_class(heroState);
                    var hsFields = new List<string>();
                    IntPtr kHs = hsCls;
                    while (kHs != IntPtr.Zero && hsFields.Count < 80)
                    {
                        IntPtr iter = IntPtr.Zero; IntPtr f;
                        while ((f = il2cpp_class_get_fields(kHs, ref iter)) != IntPtr.Zero)
                        {
                            string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(f));
                            IntPtr ft = il2cpp_field_get_type(f);
                            string tn = ft != IntPtr.Zero ? Marshal.PtrToStringAnsi(il2cpp_type_get_name(ft)) : "?";
                            uint off = il2cpp_field_get_offset(f);
                            hsFields.Add(fn + ":" + tn + "@" + off.ToString("X"));
                            if (hsFields.Count >= 80) break;
                        }
                        kHs = il2cpp_class_get_parent(kHs);
                        string pn = kHs != IntPtr.Zero ? Marshal.PtrToStringAnsi(il2cpp_class_get_name(kHs)) : "";
                        if (pn == "Object" || pn == "Il2CppObjectBase" || string.IsNullOrEmpty(pn)) break;
                    }
                    sb.Append(",\"hero_state_fields_count\":" + hsFields.Count);
                    sb.Append(",\"hero_state_fields\":[");
                    for (int i = 0; i < hsFields.Count; i++)
                    {
                        if (i > 0) sb.Append(",");
                        sb.Append("\"" + Esc(hsFields[i]) + "\"");
                    }
                    sb.Append("]");
                }

                // Try calling any found HasBuff-like method that takes one int param.
                // If BattleHero has HasBuff(StatusEffectTypeId) we can test for UK (type 320).
                var probed = new List<string>();
                foreach (var mstr in interesting)
                {
                    int slash = mstr.IndexOf('/');
                    if (slash <= 0) continue;
                    string mname = mstr.Substring(0, slash);
                    string pcStr = mstr.Substring(slash + 1);
                    if (pcStr != "1") continue;
                    // Find method
                    IntPtr method = FindIL2CPPMethodStatic(heroClass, mname, 1);
                    if (method == IntPtr.Zero) continue;
                    // Try calling with int=320 (Unkillable StatusEffectTypeId)
                    try
                    {
                        IntPtr argBuf = Marshal.AllocHGlobal(4); Marshal.WriteInt32(argBuf, 320);
                        IntPtr argArr = Marshal.AllocHGlobal(IntPtr.Size); Marshal.WriteIntPtr(argArr, argBuf);
                        IntPtr ex = IntPtr.Zero;
                        IntPtr result = il2cpp_runtime_invoke(method, heroObj, argArr, ref ex);
                        Marshal.FreeHGlobal(argBuf); Marshal.FreeHGlobal(argArr);
                        if (result != IntPtr.Zero && ex == IntPtr.Zero)
                        {
                            // Read first byte of result for bool, or int for other
                            byte b = Marshal.ReadByte(result + 0x10);
                            probed.Add(mname + "(320)=" + b);
                        }
                        else if (ex != IntPtr.Zero)
                        {
                            probed.Add(mname + "(320)=EXC");
                        }
                    }
                    catch { probed.Add(mname + "=THROW"); }
                }
                sb.Append(",\"uk_probe\":[");
                for (int i = 0; i < probed.Count && i < 40; i++)
                {
                    if (i > 0) sb.Append(",");
                    sb.Append("\"" + Esc(probed[i]) + "\"");
                }
                sb.Append("]}");
                LogDiag(sb);
                return true;
            }
            catch (Exception ex)
            {
                sb.Append(",\"err\":\"" + Esc(ex.Message) + "\"}");
                LogDiag(sb);
                return false;
            }
        }

        internal bool TryEmitCountersDiag(IntPtr procPtr)
        {
            var sb = new StringBuilder();
            sb.Append("{\"diag\":\"counters_schema\"");
            try
            {
                IntPtr stateObj = IL2CPPCallGetter(procPtr, "get_State");
                if (stateObj == IntPtr.Zero) { sb.Append(",\"err\":\"no state\"}"); LogDiag(sb); return false; }
                IntPtr team = IL2CPPCallGetter(stateObj, "get_PlayerTeam");
                if (team == IntPtr.Zero) { sb.Append(",\"err\":\"no team\"}"); LogDiag(sb); return false; }
                IntPtr heroesColl = IL2CPPCallGetter(team, "get_HeroesWithGuardian");
                if (heroesColl == IntPtr.Zero) { sb.Append(",\"err\":\"no heroes\"}"); LogDiag(sb); return false; }
                IntPtr hc = il2cpp_object_get_class(heroesColl);
                IntPtr getC = FindIL2CPPMethod(hc, "get_Count", 0);
                IntPtr getI = FindIL2CPPMethod(hc, "get_Item", 1);
                if (getC == IntPtr.Zero || getI == IntPtr.Zero) { sb.Append(",\"err\":\"no list iter\"}"); LogDiag(sb); return false; }
                IntPtr eN = IntPtr.Zero;
                IntPtr nR = il2cpp_runtime_invoke(getC, heroesColl, IntPtr.Zero, ref eN);
                int n = nR != IntPtr.Zero ? Marshal.ReadInt32(nR + 0x10) : 0;
                for (int i = 0; i < n; i++)
                {
                    IntPtr ib = Marshal.AllocHGlobal(4); Marshal.WriteInt32(ib, i);
                    IntPtr ab = Marshal.AllocHGlobal(IntPtr.Size); Marshal.WriteIntPtr(ab, ib);
                    IntPtr eIt = IntPtr.Zero;
                    IntPtr heroObj = il2cpp_runtime_invoke(getI, heroesColl, ab, ref eIt);
                    Marshal.FreeHGlobal(ib); Marshal.FreeHGlobal(ab);
                    if (heroObj == IntPtr.Zero) continue;
                    IntPtr dict = Marshal.ReadIntPtr(heroObj + 0x138);
                    if (dict == IntPtr.Zero) continue;
                    int count = Marshal.ReadInt32(dict + 0x20);
                    if (count <= 0) continue;
                    IntPtr entries = Marshal.ReadIntPtr(dict + 0x18);
                    if (entries == IntPtr.Zero) continue;
                    long arrLen = Marshal.ReadInt64(entries + 0x18);
                    sb.Append(",\"hero_idx\":" + i + ",\"count\":" + count + ",\"arr_len\":" + arrLen);
                    // Dump first 6 entries raw — 6 ints each to see layout
                    sb.Append(",\"raw\":[");
                    bool first = true;
                    for (int e = 0; e < arrLen && e < 6; e++)
                    {
                        IntPtr entryAddr = entries + 0x20 + e * 0x18;
                        int w0 = Marshal.ReadInt32(entryAddr + 0x00);
                        int w1 = Marshal.ReadInt32(entryAddr + 0x04);
                        int w2 = Marshal.ReadInt32(entryAddr + 0x08);
                        int w3 = Marshal.ReadInt32(entryAddr + 0x0C);
                        long v64 = Marshal.ReadInt64(entryAddr + 0x10);
                        if (!first) sb.Append(",");
                        first = false;
                        sb.Append("{\"w0\":" + w0 + ",\"w1\":" + w1 + ",\"w2\":" + w2 + ",\"w3\":" + w3 +
                                  ",\"v64\":" + v64 + ",\"v_shifted\":" + (v64 >> 32) + "}");
                    }
                    sb.Append("]}");
                    LogDiag(sb);
                    return true;
                }
                sb.Append(",\"err\":\"no populated Counters dict\"}");
                LogDiag(sb);
                return false;
            }
            catch (Exception ex)
            {
                sb.Append(",\"err\":\"" + Esc(ex.Message) + "\"}");
                LogDiag(sb);
                return false;
            }
        }

        /// <summary>
        /// Read a Dict&lt;int, HashSet&lt;int&gt;&gt; — emit as "key":{int: set_count, ...}. HashSet count
        /// lives at its `_count` field (standard .NET layout @0x28). For now we just emit the
        /// key as "present" (= 1) to confirm population; full enumeration can be added later.
        /// Entry stride for Dict&lt;int, ref&gt; is 0x18 (hash:4, next:4, key:4, pad:4, ref:8).
        /// </summary>
        private void AppendCountersByUniqueDict(StringBuilder sb, IntPtr heroObj, int fieldOffset, string label)
        {
            try
            {
                IntPtr dict = Marshal.ReadIntPtr(heroObj + fieldOffset);
                if (dict == IntPtr.Zero) return;
                int count = Marshal.ReadInt32(dict + 0x20);
                if (count <= 0) return;
                IntPtr entries = Marshal.ReadIntPtr(dict + 0x18);
                if (entries == IntPtr.Zero) return;
                long arrLen = Marshal.ReadInt64(entries + 0x18);
                sb.Append(",\"" + label + "\":{");
                bool first = true;
                int emitted = 0;
                for (int e = 0; e < arrLen && emitted < 48; e++)
                {
                    IntPtr entryAddr = entries + 0x20 + e * 0x18;
                    int hashCode = Marshal.ReadInt32(entryAddr + 0x00);
                    if (hashCode == 0) continue;
                    int key = Marshal.ReadInt32(entryAddr + 0x08);
                    IntPtr hashSet = Marshal.ReadIntPtr(entryAddr + 0x10);
                    int setCount = 0;
                    if (hashSet != IntPtr.Zero)
                    {
                        // HashSet<int>._count is at offset 0x28 in standard .NET layout
                        try { setCount = Marshal.ReadInt32(hashSet + 0x28); } catch { }
                    }
                    if (!first) sb.Append(",");
                    first = false;
                    sb.Append("\"" + key + "\":" + setCount);
                    emitted++;
                }
                sb.Append("}");
            }
            catch { }
        }

        private void AppendStatModEffects(StringBuilder sb, IntPtr heroObj)
        {
            try
            {
                IntPtr siObj = Marshal.ReadIntPtr(heroObj + 0xA0);
                if (siObj == IntPtr.Zero) return;
                IntPtr siDict = Marshal.ReadIntPtr(siObj + 0x18);
                if (siDict == IntPtr.Zero) return;
                int count = Marshal.ReadInt32(siDict + 0x20);
                if (count <= 0) return;
                IntPtr entries = Marshal.ReadIntPtr(siDict + 0x18);
                if (entries == IntPtr.Zero) return;
                long arrLen = Marshal.ReadInt64(entries + 0x18);
                // Entry stride = 0x28 (Hash:4, Next:4, Key:4, Pad:4, Value tuple:24)
                // Tuple layout: Fixed:8 @0x10, StatKindId:4 @0x18, EffectContext:8 @0x20
                sb.Append(",\"mods\":[");
                bool first = true;
                int emitted = 0;
                for (int e = 0; e < arrLen && emitted < 32; e++)
                {
                    IntPtr entryAddr = entries + 0x20 + e * 0x28;
                    int hashCode = Marshal.ReadInt32(entryAddr + 0x00);
                    if (hashCode == 0) continue;
                    int effectId = Marshal.ReadInt32(entryAddr + 0x08);
                    long fixedRaw = Marshal.ReadInt64(entryAddr + 0x10);
                    long val = fixedRaw >> 32;
                    int kind = Marshal.ReadInt32(entryAddr + 0x18);
                    if (!first) sb.Append(",");
                    first = false;
                    sb.Append("{\"id\":" + effectId + ",\"k\":" + kind + ",\"v\":" + val + "}");
                    emitted++;
                }
                sb.Append("]");
            }
            catch { }
        }

        private void AppendActiveEffects(StringBuilder sb, IntPtr heroObj)
        {
            try
            {
                IntPtr phaseEffects = Marshal.ReadIntPtr(heroObj + 0xF0);
                if (phaseEffects == IntPtr.Zero) return;
                IntPtr effArr = Marshal.ReadIntPtr(phaseEffects + 0x10);
                if (effArr == IntPtr.Zero) return;
                long arrLen = Marshal.ReadInt64(effArr + 0x18);
                if (arrLen <= 0) return;

                sb.Append(",\"eff\":[");
                bool first = true;
                for (int z = 0; z < arrLen && z < 32; z++)
                {
                    IntPtr list = Marshal.ReadIntPtr(effArr + 0x20 + z * IntPtr.Size);
                    if (list == IntPtr.Zero) continue;
                    IntPtr lCls = il2cpp_object_get_class(list);
                    IntPtr lCnt = FindIL2CPPMethod(lCls, "get_Count", 0);
                    IntPtr lItem = FindIL2CPPMethod(lCls, "get_Item", 1);
                    if (lCnt == IntPtr.Zero || lItem == IntPtr.Zero) continue;
                    IntPtr xE = IntPtr.Zero;
                    IntPtr xR = il2cpp_runtime_invoke(lCnt, list, IntPtr.Zero, ref xE);
                    int xC = xR != IntPtr.Zero ? Marshal.ReadInt32(xR + 0x10) : 0;
                    if (xC <= 0) continue;

                    if (!first) sb.Append(",");
                    first = false;
                    sb.Append("{\"ph\":" + z + ",\"e\":[");
                    for (int q = 0; q < xC && q < 10; q++)
                    {
                        if (q > 0) sb.Append(",");
                        try
                        {
                            IntPtr qBuf = Marshal.AllocHGlobal(4); Marshal.WriteInt32(qBuf, q);
                            IntPtr qArr = Marshal.AllocHGlobal(IntPtr.Size); Marshal.WriteIntPtr(qArr, qBuf);
                            IntPtr qE = IntPtr.Zero;
                            IntPtr eff = il2cpp_runtime_invoke(lItem, list, qArr, ref qE);
                            Marshal.FreeHGlobal(qBuf); Marshal.FreeHGlobal(qArr);
                            if (eff == IntPtr.Zero) { sb.Append("null"); continue; }
                            int effId = Marshal.ReadInt32(eff + 0x10);
                            int kindId = Marshal.ReadInt32(eff + 0x14);
                            int count = Marshal.ReadInt32(eff + 0x68);
                            int stack = Marshal.ReadInt32(eff + 0x6C);
                            sb.Append("{\"id\":" + effId + ",\"k\":" + kindId);
                            if (count > 0) sb.Append(",\"c\":" + count);
                            if (stack > 1) sb.Append(",\"s\":" + stack);
                            sb.Append("}");
                        }
                        catch { sb.Append("null"); }
                    }
                    sb.Append("]}");
                }
                sb.Append("]");
            }
            catch { }
        }

        /// <summary>
        /// Read HeroState.AppliedBuffs and .AppliedDebuffs to emit active status effects.
        /// Each list element is a status-effect object; we extract TypeId (StatusEffectTypeId)
        /// and Duration (turns remaining) using IL2CPP reflection.
        /// Emits: ,"buffs":[{t:320,d:2},{t:40,d:1}],"debuffs":[{t:151,d:2}]
        /// </summary>
        private void AppendAppliedBuffsDebuffs(StringBuilder sb, IntPtr heroObj)
        {
            try
            {
                IntPtr heroState = Marshal.ReadIntPtr(heroObj + 0xC0);
                if (heroState == IntPtr.Zero) return;

                // Resolve HeroState field offsets once
                if (!_hsBuffFieldsResolved)
                {
                    _hsBuffFieldsResolved = true;
                    IntPtr hsCls = il2cpp_object_get_class(heroState);
                    IntPtr klass = hsCls;
                    while (klass != IntPtr.Zero)
                    {
                        IntPtr fIter = IntPtr.Zero; IntPtr f;
                        while ((f = il2cpp_class_get_fields(klass, ref fIter)) != IntPtr.Zero)
                        {
                            string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(f));
                            uint off = il2cpp_field_get_offset(f);
                            if (fn == "AppliedBuffs") _hsAppliedBuffsOff = (int)off;
                            else if (fn == "AppliedDebuffs") _hsAppliedDebuffsOff = (int)off;
                        }
                        if (_hsAppliedBuffsOff >= 0 && _hsAppliedDebuffsOff >= 0) break;
                        klass = il2cpp_class_get_parent(klass);
                        string pn = klass != IntPtr.Zero ? Marshal.PtrToStringAnsi(il2cpp_class_get_name(klass)) : "";
                        if (pn == "Object" || pn == "Il2CppObjectBase" || string.IsNullOrEmpty(pn)) break;
                    }
                    // Log resolved offsets (minimal, safe)
                    var diagSb = new StringBuilder();
                    diagSb.Append("{\"diag\":\"hs_buff_offsets\"");
                    diagSb.Append(",\"buffs_off\":\"0x" + _hsAppliedBuffsOff.ToString("X") + "\"");
                    diagSb.Append(",\"debuffs_off\":\"0x" + _hsAppliedDebuffsOff.ToString("X") + "\"}");
                    LogDiag(diagSb);
                }

                // Emit buffs and debuffs
                AppendEffectList(sb, heroState, _hsAppliedBuffsOff, "buffs");
                AppendEffectList(sb, heroState, _hsAppliedDebuffsOff, "debuffs");
            }
            catch { }
        }

        /// <summary>Iterate List of AppliedEffect via get_Count/get_Item.
        /// Minimal: only try get_Id (proven safe pattern from TypeId probe).
        /// get_TypeId → not found on AppliedEffect. get_Id → exists per /props.</summary>
        private void AppendEffectList(StringBuilder sb, IntPtr heroState, int fieldOff, string key)
        {
            if (fieldOff < 0) return;
            try
            {
                IntPtr lst = Marshal.ReadIntPtr(heroState + fieldOff);
                if (lst == IntPtr.Zero) return;
                IntPtr lCls = il2cpp_object_get_class(lst);
                IntPtr gCnt = FindIL2CPPMethod(lCls, "get_Count", 0);
                IntPtr gItm = FindIL2CPPMethod(lCls, "get_Item", 1);
                if (gCnt == IntPtr.Zero || gItm == IntPtr.Zero) return;
                IntPtr xE = IntPtr.Zero;
                IntPtr xR = il2cpp_runtime_invoke(gCnt, lst, IntPtr.Zero, ref xE);
                int count = xR != IntPtr.Zero ? Marshal.ReadInt32(xR + 0x10) : 0;
                if (count <= 0) return;

                sb.Append(",\"" + key + "\":[");
                for (int i = 0; i < count && i < 20; i++)
                {
                    if (i > 0) sb.Append(",");
                    try
                    {
                        IntPtr ib = Marshal.AllocHGlobal(4); Marshal.WriteInt32(ib, i);
                        IntPtr ab = Marshal.AllocHGlobal(IntPtr.Size); Marshal.WriteIntPtr(ab, ib);
                        IntPtr ie = IntPtr.Zero;
                        IntPtr elem = il2cpp_runtime_invoke(gItm, lst, ab, ref ie);
                        Marshal.FreeHGlobal(ib); Marshal.FreeHGlobal(ab);
                        if (elem == IntPtr.Zero || ie != IntPtr.Zero) { sb.Append("null"); continue; }

                        IntPtr eCls = il2cpp_object_get_class(elem);
                        // Cache field handles ONCE via il2cpp_class_get_fields
                        if (eCls != IntPtr.Zero && !_aeFieldsResolved)
                        {
                            _aeFieldsResolved = true;
                            IntPtr fIter = IntPtr.Zero; IntPtr f;
                            while ((f = il2cpp_class_get_fields(eCls, ref fIter)) != IntPtr.Zero)
                            {
                                string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(f));
                                if (fn == "EffectTypeId") _aeEffectTypeIdField = f;
                                else if (fn == "TurnLeft") _aeTurnLeftField = f;
                                else if (fn == "ProducerId") _aeProducerIdField = f;
                            }
                        }
                        // Read via il2cpp_field_get_value (safe IL2CPP API)
                        int eti = -1, tl = -1, pid = -1;
                        IntPtr vBuf = Marshal.AllocHGlobal(8);
                        if (_aeEffectTypeIdField != IntPtr.Zero)
                        {
                            il2cpp_field_get_value(elem, _aeEffectTypeIdField, vBuf);
                            eti = Marshal.ReadInt32(vBuf);
                        }
                        if (_aeTurnLeftField != IntPtr.Zero)
                        {
                            il2cpp_field_get_value(elem, _aeTurnLeftField, vBuf);
                            tl = Marshal.ReadInt32(vBuf);
                        }
                        if (_aeProducerIdField != IntPtr.Zero)
                        {
                            il2cpp_field_get_value(elem, _aeProducerIdField, vBuf);
                            pid = Marshal.ReadInt32(vBuf);
                        }
                        Marshal.FreeHGlobal(vBuf);
                        sb.Append("{\"t\":" + eti + ",\"d\":" + tl + ",\"src\":" + pid + "}");
                    }
                    catch { sb.Append("null"); }
                }
                sb.Append("]");
            }
            catch { }
        }

        private void AppendIntGetter(StringBuilder sb, IntPtr cls, IntPtr obj, string getter, string key)
        {
            IntPtr m = FindIL2CPPMethod(cls, getter, 0);
            if (m == IntPtr.Zero) return;
            IntPtr e = IntPtr.Zero;
            IntPtr r = il2cpp_runtime_invoke(m, obj, IntPtr.Zero, ref e);
            if (r == IntPtr.Zero) return;
            sb.Append(",\"" + key + "\":" + Marshal.ReadInt32(r + 0x10));
        }

        private void AppendBoolGetter(StringBuilder sb, IntPtr cls, IntPtr obj, string getter, string key)
        {
            IntPtr m = FindIL2CPPMethod(cls, getter, 0);
            if (m == IntPtr.Zero) return;
            IntPtr e = IntPtr.Zero;
            IntPtr r = il2cpp_runtime_invoke(m, obj, IntPtr.Zero, ref e);
            if (r == IntPtr.Zero) return;
            bool b = Marshal.ReadByte(r + 0x10) != 0;
            if (b) sb.Append(",\"" + key + "\":true");
        }

        /// <summary>
        /// Read a Fixed (16.16) getter. Raid stores Fixed as a 64-bit int (48.16 layout) so
        /// HP values (which can be >32K) don't overflow. We read Int64 at +0x10.
        /// 'percent' multiplies by 100 for display.
        /// </summary>
        /// <summary>Read a Fixed (32.32) directly at a known offset from the object pointer.</summary>
        private void AppendFixedFieldAtOffset(StringBuilder sb, IntPtr obj, int offset, string key)
        {
            try
            {
                long raw = Marshal.ReadInt64(obj + offset);
                long v = raw >> 32;
                sb.Append(",\"" + key + "\":");
                sb.Append(v.ToString(System.Globalization.CultureInfo.InvariantCulture));
            }
            catch { }
        }

        private void AppendInt32FieldAtOffset(StringBuilder sb, IntPtr obj, int offset, string key)
        {
            try
            {
                int v = Marshal.ReadInt32(obj + offset);
                sb.Append(",\"" + key + "\":" + v);
            }
            catch { }
        }

        /// <summary>Read an IntPtr (reference) directly at a known offset.</summary>
        private IntPtr ReadIntPtrAtOffset(IntPtr obj, int offset)
        {
            try { return Marshal.ReadIntPtr(obj + offset); } catch { return IntPtr.Zero; }
        }

        /// <summary>
        /// Find a field by name on klass (walks parent chain) and return its offset as uint.
        /// Returns uint.MaxValue if not found.
        /// </summary>
        private uint FindFieldOffset(IntPtr klass, string fieldName)
        {
            IntPtr k = klass;
            while (k != IntPtr.Zero)
            {
                IntPtr iter = IntPtr.Zero; IntPtr f;
                while ((f = il2cpp_class_get_fields(k, ref iter)) != IntPtr.Zero)
                {
                    string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(f));
                    if (fn == fieldName) return il2cpp_field_get_offset(f);
                }
                k = il2cpp_class_get_parent(k);
                string pn = k != IntPtr.Zero ? Marshal.PtrToStringAnsi(il2cpp_class_get_name(k)) : "";
                if (pn == "Object" || pn == "Il2CppObjectBase" || string.IsNullOrEmpty(pn)) break;
            }
            return uint.MaxValue;
        }

        private void AppendFixedGetter(StringBuilder sb, IntPtr cls, IntPtr obj, string getter, string key, bool percent = false)
        {
            IntPtr m = FindIL2CPPMethod(cls, getter, 0);
            if (m == IntPtr.Zero) return;
            IntPtr e = IntPtr.Zero;
            IntPtr r = il2cpp_runtime_invoke(m, obj, IntPtr.Zero, ref e);
            if (r == IntPtr.Zero) return;
            // Raid stores Fixed as 32.32 fixed-point (raw = value << 32).
            // Confirmed empirically: hp_max_raw = 173_351_751_876_938 => /2^32 = 40363 HP.
            long raw = Marshal.ReadInt64(r + 0x10);
            long divided = raw >> 32;
            if (percent) divided *= 100;
            sb.Append(",\"" + key + "\":");
            sb.Append(divided.ToString(System.Globalization.CultureInfo.InvariantCulture));
        }

        private void AppendHeroSkills(StringBuilder sb, IntPtr heroObj, IntPtr heroClass)
        {
            IntPtr m = FindIL2CPPMethod(heroClass, "get_HeroSkills", 0);
            if (m == IntPtr.Zero) return;
            IntPtr e = IntPtr.Zero;
            IntPtr coll = il2cpp_runtime_invoke(m, heroObj, IntPtr.Zero, ref e);
            if (coll == IntPtr.Zero) return;
            IntPtr cCls = il2cpp_object_get_class(coll);
            IntPtr gC = FindIL2CPPMethod(cCls, "get_Count", 0);
            IntPtr gI = FindIL2CPPMethod(cCls, "get_Item", 1);
            if (gC == IntPtr.Zero || gI == IntPtr.Zero) return;
            IntPtr eN = IntPtr.Zero;
            IntPtr nR = il2cpp_runtime_invoke(gC, coll, IntPtr.Zero, ref eN);
            int n = nR != IntPtr.Zero ? Marshal.ReadInt32(nR + 0x10) : 0;
            sb.Append(",\"sk\":[");
            for (int i = 0; i < n && i < 6; i++)
            {
                if (i > 0) sb.Append(",");
                try
                {
                    IntPtr ib = Marshal.AllocHGlobal(4); Marshal.WriteInt32(ib, i);
                    IntPtr ab = Marshal.AllocHGlobal(IntPtr.Size); Marshal.WriteIntPtr(ab, ib);
                    IntPtr eIt = IntPtr.Zero;
                    IntPtr sk = il2cpp_runtime_invoke(gI, coll, ab, ref eIt);
                    Marshal.FreeHGlobal(ib); Marshal.FreeHGlobal(ab);
                    if (sk == IntPtr.Zero) { sb.Append("null"); continue; }
                    sb.Append("{");
                    IntPtr skCls = il2cpp_object_get_class(sk);
                    bool first = true;
                    // Type (skill type id), IsReady, Blocked, IsStarter, SameSkillCount
                    foreach (var (getter, key, kind) in new[] {
                        ("get_Type","t","int"),
                        ("get_IsReady","rdy","bool"),
                        ("get_Blocked","blk","bool"),
                        ("get_IsStarter","start","bool"),
                        ("get_SameSkillCount","same","int"),
                    })
                    {
                        IntPtr fm = FindIL2CPPMethod(skCls, getter, 0);
                        if (fm == IntPtr.Zero) continue;
                        IntPtr fe = IntPtr.Zero;
                        IntPtr fr = il2cpp_runtime_invoke(fm, sk, IntPtr.Zero, ref fe);
                        if (fr == IntPtr.Zero) continue;
                        if (kind == "bool")
                        {
                            bool bv = Marshal.ReadByte(fr + 0x10) != 0;
                            if (!bv && (key == "blk" || key == "start")) continue;  // omit false
                            if (!first) sb.Append(","); first = false;
                            sb.Append("\"" + key + "\":" + (bv ? "true" : "false"));
                        }
                        else
                        {
                            if (!first) sb.Append(","); first = false;
                            sb.Append("\"" + key + "\":" + Marshal.ReadInt32(fr + 0x10));
                        }
                    }
                    sb.Append("}");
                }
                catch { sb.Append("null"); }
            }
            sb.Append("]");
        }

        /// <summary>
        /// Iterate a status-effect collection on hero (Buffs/Debuffs), emitting [{t,turns,value,src}].
        /// </summary>
        private void AppendStatusCollection(StringBuilder sb, IntPtr heroObj, IntPtr heroClass, string label, string[] getters)
        {
            foreach (var g in getters)
            {
                IntPtr m = FindIL2CPPMethod(heroClass, g, 0);
                if (m == IntPtr.Zero) continue;
                IntPtr e = IntPtr.Zero;
                IntPtr coll = il2cpp_runtime_invoke(m, heroObj, IntPtr.Zero, ref e);
                if (coll == IntPtr.Zero) return;
                IntPtr cCls = il2cpp_object_get_class(coll);
                IntPtr getC = FindIL2CPPMethod(cCls, "get_Count", 0);
                IntPtr getI = FindIL2CPPMethod(cCls, "get_Item", 1);
                if (getC == IntPtr.Zero || getI == IntPtr.Zero) return;
                IntPtr exCnt = IntPtr.Zero;
                IntPtr cR = il2cpp_runtime_invoke(getC, coll, IntPtr.Zero, ref exCnt);
                int cnt = cR != IntPtr.Zero ? Marshal.ReadInt32(cR + 0x10) : 0;
                sb.Append(",\"" + label + "\":[");
                for (int i = 0; i < cnt && i < 20; i++)
                {
                    if (i > 0) sb.Append(",");
                    try
                    {
                        IntPtr ib = Marshal.AllocHGlobal(4); Marshal.WriteInt32(ib, i);
                        IntPtr ab = Marshal.AllocHGlobal(IntPtr.Size); Marshal.WriteIntPtr(ab, ib);
                        IntPtr exIt = IntPtr.Zero;
                        IntPtr elObj = il2cpp_runtime_invoke(getI, coll, ab, ref exIt);
                        Marshal.FreeHGlobal(ib); Marshal.FreeHGlobal(ab);
                        if (elObj == IntPtr.Zero) { sb.Append("null"); continue; }
                        sb.Append("{");
                        IntPtr elCls = il2cpp_object_get_class(elObj);
                        bool first = true;
                        foreach (var (getter, key) in new[] { ("get_TypeId","t"), ("get_StatusEffectTypeId","t"), ("get_KindId","t"), ("get_Turns","turns"), ("get_TurnsRemaining","turns"), ("get_Value","v"), ("get_SourceHeroId","src"), ("get_IsExpired","exp") })
                        {
                            IntPtr fm = FindIL2CPPMethod(elCls, getter, 0);
                            if (fm == IntPtr.Zero) continue;
                            IntPtr fe = IntPtr.Zero;
                            IntPtr fr = il2cpp_runtime_invoke(fm, elObj, IntPtr.Zero, ref fe);
                            if (fr == IntPtr.Zero) continue;
                            if (!first) sb.Append(",");
                            first = false;
                            IntPtr frCls = il2cpp_object_get_class(fr);
                            string frTy = Marshal.PtrToStringAnsi(il2cpp_class_get_name(frCls));
                            if (frTy == "Boolean")
                                sb.Append("\"" + key + "\":" + (Marshal.ReadByte(fr + 0x10) != 0 ? "true" : "false"));
                            else if (frTy == "Int64" || frTy == "UInt64")
                                sb.Append("\"" + key + "\":" + Marshal.ReadInt64(fr + 0x10));
                            else
                                sb.Append("\"" + key + "\":" + Marshal.ReadInt32(fr + 0x10));
                        }
                        sb.Append("}");
                    }
                    catch { sb.Append("null"); }
                }
                sb.Append("]");
                return; // only first matching accessor
            }
        }

        /// <summary>
        /// Emit skills array with cooldowns: [{id, cd}].
        /// </summary>
        private void AppendSkillCooldowns(StringBuilder sb, IntPtr heroObj, IntPtr heroClass)
        {
            IntPtr m = FindIL2CPPMethod(heroClass, "get_Skills", 0);
            if (m == IntPtr.Zero) return;
            IntPtr e = IntPtr.Zero;
            IntPtr coll = il2cpp_runtime_invoke(m, heroObj, IntPtr.Zero, ref e);
            if (coll == IntPtr.Zero) return;
            IntPtr cCls = il2cpp_object_get_class(coll);
            IntPtr getC = FindIL2CPPMethod(cCls, "get_Count", 0);
            IntPtr getI = FindIL2CPPMethod(cCls, "get_Item", 1);
            if (getC == IntPtr.Zero || getI == IntPtr.Zero) return;
            IntPtr exCnt = IntPtr.Zero;
            IntPtr cR = il2cpp_runtime_invoke(getC, coll, IntPtr.Zero, ref exCnt);
            int cnt = cR != IntPtr.Zero ? Marshal.ReadInt32(cR + 0x10) : 0;
            sb.Append(",\"skills\":[");
            for (int i = 0; i < cnt && i < 8; i++)
            {
                if (i > 0) sb.Append(",");
                try
                {
                    IntPtr ib = Marshal.AllocHGlobal(4); Marshal.WriteInt32(ib, i);
                    IntPtr ab = Marshal.AllocHGlobal(IntPtr.Size); Marshal.WriteIntPtr(ab, ib);
                    IntPtr exIt = IntPtr.Zero;
                    IntPtr sk = il2cpp_runtime_invoke(getI, coll, ab, ref exIt);
                    Marshal.FreeHGlobal(ib); Marshal.FreeHGlobal(ab);
                    if (sk == IntPtr.Zero) { sb.Append("null"); continue; }
                    sb.Append("{");
                    IntPtr skCls = il2cpp_object_get_class(sk);
                    bool first = true;
                    foreach (var (getter, key) in new[] { ("get_TypeId","id"), ("get_SkillTypeId","id"), ("get_Cooldown","cd"), ("get_CurrentCooldown","cd"), ("get_TurnsToCooldown","cd") })
                    {
                        IntPtr fm = FindIL2CPPMethod(skCls, getter, 0);
                        if (fm == IntPtr.Zero) continue;
                        IntPtr fe = IntPtr.Zero;
                        IntPtr fr = il2cpp_runtime_invoke(fm, sk, IntPtr.Zero, ref fe);
                        if (fr == IntPtr.Zero) continue;
                        if (!first) sb.Append(",");
                        first = false;
                        sb.Append("\"" + key + "\":" + Marshal.ReadInt32(fr + 0x10));
                    }
                    sb.Append("}");
                }
                catch { sb.Append("null"); }
            }
            sb.Append("]");
        }

        /// <summary>
        /// Emit a schema diag entry to _battleLog showing the real property/getter names of
        /// BattleHero (via Processor → State → PlayerTeam → HeroesWithGuardian[0]) and its
        /// Buffs/Debuffs/Skills collection elements. Called once per battle on first successful
        /// hero read so the logs capture the actual schema for the current battle type
        /// (CB vs Arena vs Dungeon may use different hero subclasses).
        /// </summary>
        internal void EmitBattleSchemaDiag(IntPtr procPtr)
        {
            try
            {
                var sb = new StringBuilder();
                sb.Append("{\"diag\":\"hero_schema\"");

                IntPtr stateObj = IL2CPPCallGetter(procPtr, "get_State");
                if (stateObj == IntPtr.Zero) { sb.Append(",\"err\":\"no_state\"}"); LogDiag(sb); return; }
                IntPtr team = IL2CPPCallGetter(stateObj, "get_PlayerTeam");
                if (team == IntPtr.Zero) { sb.Append(",\"err\":\"no_playerteam\"}"); LogDiag(sb); return; }
                IntPtr heroesColl = IL2CPPCallGetter(team, "get_HeroesWithGuardian");
                if (heroesColl == IntPtr.Zero) { sb.Append(",\"err\":\"no_heroes_coll\"}"); LogDiag(sb); return; }

                IntPtr hc = il2cpp_object_get_class(heroesColl);
                IntPtr getC = FindIL2CPPMethod(hc, "get_Count", 0);
                IntPtr getI = FindIL2CPPMethod(hc, "get_Item", 1);
                if (getC == IntPtr.Zero || getI == IntPtr.Zero) { sb.Append(",\"err\":\"not_list\"}"); LogDiag(sb); return; }
                IntPtr eC = IntPtr.Zero;
                IntPtr cR = il2cpp_runtime_invoke(getC, heroesColl, IntPtr.Zero, ref eC);
                int cnt = cR != IntPtr.Zero ? Marshal.ReadInt32(cR + 0x10) : 0;
                if (cnt <= 0) { sb.Append(",\"err\":\"empty_coll\"}"); LogDiag(sb); return; }

                IntPtr ib = Marshal.AllocHGlobal(4); Marshal.WriteInt32(ib, 0);
                IntPtr ab = Marshal.AllocHGlobal(IntPtr.Size); Marshal.WriteIntPtr(ab, ib);
                IntPtr eIt = IntPtr.Zero;
                IntPtr heroObj = il2cpp_runtime_invoke(getI, heroesColl, ab, ref eIt);
                Marshal.FreeHGlobal(ib); Marshal.FreeHGlobal(ab);
                if (heroObj == IntPtr.Zero) { sb.Append(",\"err\":\"null_hero\"}"); LogDiag(sb); return; }

                IntPtr heroClass = il2cpp_object_get_class(heroObj);
                string hTy = Marshal.PtrToStringAnsi(il2cpp_class_get_name(heroClass));
                sb.Append(",\"hero_type\":\"" + Esc(hTy ?? "?") + "\"");
                AppendClassProps(sb, heroClass, "hero_props", 120);
                AppendClassFields(sb, heroClass, "hero_fields", 120);

                // Drill into AppliedEffectsByHeroes (Dictionary<int, List<AppliedEffect>>) at field offset 0x108.
                // Walk down to one AppliedEffect and dump its class + fields so we can read individual effects.
                try
                {
                    IntPtr dict = ReadIntPtrAtOffset(heroObj, 0x108);
                    if (dict != IntPtr.Zero)
                    {
                        IntPtr dictClass = il2cpp_object_get_class(dict);
                        string dictTy = Marshal.PtrToStringAnsi(il2cpp_class_get_name(dictClass));
                        sb.Append(",\"dict_type\":\"" + Esc(dictTy ?? "?") + "\"");
                        // Call get_Count and if >0, get_Values, then iterate first list's [0].
                        IntPtr getCountM = FindIL2CPPMethodStatic(dictClass, "get_Count", 0);
                        if (getCountM != IntPtr.Zero)
                        {
                            IntPtr exC = IntPtr.Zero;
                            IntPtr cntR = il2cpp_runtime_invoke(getCountM, dict, IntPtr.Zero, ref exC);
                            int dictCnt = cntR != IntPtr.Zero ? Marshal.ReadInt32(cntR + 0x10) : 0;
                            sb.Append(",\"dict_count\":" + dictCnt);
                        }
                        AppendClassFields(sb, dictClass, "dict_fields", 30);
                    }
                }
                catch { }

                // Find the first collection-shaped getter (returns something with get_Count)
                // and dump its element's props. Do this for each collection accessor we find.
                AppendFirstElementProps(sb, heroClass, heroObj, "buffs");
                AppendFirstElementProps(sb, heroClass, heroObj, "debuffs");
                AppendFirstElementProps(sb, heroClass, heroObj, "effects");
                AppendFirstElementProps(sb, heroClass, heroObj, "skills");

                sb.Append("}");
                LogDiag(sb);
            }
            catch (Exception ex)
            {
                try { lock (_battleLog) { if (_battleLog.Count < 2000) _battleLog.Add("{\"diag\":\"hero_schema_fail\",\"err\":\"" + Esc(ex.Message) + "\"}"); } } catch { }
            }
        }

        private void LogDiag(StringBuilder sb)
        {
            lock (_battleLog) { if (_battleLog.Count < 2000) _battleLog.Add(sb.ToString()); }
        }

        /// <summary>
        /// Attempt to walk one hero's AppliedEffectsByHeroes (a Dictionary<int, List<AppliedEffect>>)
        /// down to the first AppliedEffect and dump its class + field schema. Returns true only if
        /// we successfully emit a full schema (so callers can retry on subsequent polls when empty).
        ///
        /// Strategy: iterate heroes until we find one whose dict has >0 entries, then invoke
        /// Dictionary.get_Values → invoke GetEnumerator → MoveNext → Current. Each Current is a
        /// List<AppliedEffect>; take [0] off it, dump class/fields.
        /// </summary>
        /// <summary>
        /// Probe BattleHero.Challenges (Dict<int, Challenge> @0xE0) on the first hero with a
        /// populated dict. Walks one Challenge entry to dump its class + fields so we can map
        /// where active UK/BD buff durations actually live.
        /// </summary>
        internal bool TryEmitChallengeDiag(IntPtr procPtr)
        {
            var trace = new StringBuilder();
            trace.Append("{\"diag\":\"chl_probe\"");
            try
            {
                IntPtr stateObj = IL2CPPCallGetter(procPtr, "get_State");
                if (stateObj == IntPtr.Zero) { trace.Append(",\"err\":\"no state\"}"); LogDiag(trace); return false; }
                foreach (var sideGetter in new[] { "get_PlayerTeam", "get_EnemyTeam" })
                {
                    IntPtr team = IL2CPPCallGetter(stateObj, sideGetter);
                    if (team == IntPtr.Zero) continue;
                    IntPtr heroesColl = IL2CPPCallGetter(team, "get_HeroesWithGuardian");
                    if (heroesColl == IntPtr.Zero) continue;
                    IntPtr hc = il2cpp_object_get_class(heroesColl);
                    IntPtr getC = FindIL2CPPMethod(hc, "get_Count", 0);
                    IntPtr getI = FindIL2CPPMethod(hc, "get_Item", 1);
                    if (getC == IntPtr.Zero || getI == IntPtr.Zero) continue;
                    IntPtr eN = IntPtr.Zero;
                    IntPtr nR = il2cpp_runtime_invoke(getC, heroesColl, IntPtr.Zero, ref eN);
                    int n = nR != IntPtr.Zero ? Marshal.ReadInt32(nR + 0x10) : 0;
                    for (int i = 0; i < n; i++)
                    {
                        IntPtr ib = Marshal.AllocHGlobal(4); Marshal.WriteInt32(ib, i);
                        IntPtr ab = Marshal.AllocHGlobal(IntPtr.Size); Marshal.WriteIntPtr(ab, ib);
                        IntPtr eIt = IntPtr.Zero;
                        IntPtr heroObj = il2cpp_runtime_invoke(getI, heroesColl, ab, ref eIt);
                        Marshal.FreeHGlobal(ib); Marshal.FreeHGlobal(ab);
                        if (heroObj == IntPtr.Zero) continue;

                        // Challenges dict @ 0xE0 (verified field offset)
                        IntPtr dict = Marshal.ReadIntPtr(heroObj + 0xE0);
                        if (dict == IntPtr.Zero) continue;
                        // Dict<K,V>._count @ 0x20 (verified .NET internal layout)
                        int dc = Marshal.ReadInt32(dict + 0x20);
                        if (dc <= 0) continue;
                        // Dict<K,V>._entries (Entry[]) @ 0x18
                        IntPtr entries = Marshal.ReadIntPtr(dict + 0x18);
                        if (entries == IntPtr.Zero) continue;
                        // IL2CPP array: header 0x10 + bounds 0x8 + max_length 0x8, elements @ 0x20
                        long arrLen = Marshal.ReadInt64(entries + 0x18);
                        if (arrLen <= 0) continue;

                        // Each Entry<int,Challenge> in .NET internal layout:
                        // [hashCode:int @0][next:int @4][key:int @8][value:IntPtr @0x10]  (16-byte stride for int+ref)
                        // Actually the standard layout is:
                        //   hashCode:int, next:int, key:K, value:V (pointer or value type)
                        // For Dict<int, ref-type>: stride = 0x18 typically, value at +0x10
                        // We'll dump first 3 entries and try +0x10 and +0x18 for value
                        var sb = new StringBuilder();
                        sb.Append("{\"diag\":\"challenge_schema\"");
                        sb.Append(",\"hero_idx\":" + i);
                        sb.Append(",\"side\":\"" + sideGetter.Substring(4) + "\"");
                        sb.Append(",\"chl_count\":" + dc);
                        sb.Append(",\"arr_len\":" + arrLen);

                        // Read first non-zero entry
                        IntPtr challenge = IntPtr.Zero;
                        int entryStride = 0x18;  // typical .NET Dict<int, ref> entry stride
                        int valueOffset = 0x10;  // value field within entry
                        int keyValRead = 0;
                        for (int e = 0; e < arrLen && e < 16; e++)
                        {
                            IntPtr entryAddr = entries + 0x20 + e * entryStride;
                            int hashCode = Marshal.ReadInt32(entryAddr + 0x00);
                            int keyVal = Marshal.ReadInt32(entryAddr + 0x08);
                            IntPtr val = Marshal.ReadIntPtr(entryAddr + valueOffset);
                            if (val != IntPtr.Zero && hashCode != 0)
                            {
                                challenge = val;
                                keyValRead = keyVal;
                                sb.Append(",\"first_key\":" + keyVal + ",\"hash\":" + hashCode);
                                break;
                            }
                        }
                        if (challenge == IntPtr.Zero)
                        {
                            sb.Append(",\"err\":\"no entry found via 0x10/0x18 stride\"}");
                            LogDiag(sb);
                            continue;
                        }

                        IntPtr chCls = il2cpp_object_get_class(challenge);
                        string chTy = Marshal.PtrToStringAnsi(il2cpp_class_get_name(chCls));
                        sb.Append(",\"challenge_type\":\"" + Esc(chTy ?? "?") + "\"");
                        AppendClassProps(sb, chCls, "challenge_props", 60);
                        AppendClassFields(sb, chCls, "challenge_fields", 60);
                        sb.Append("}");
                        LogDiag(sb);
                        return true;
                    }
                }
                trace.Append(",\"err\":\"no populated Challenges dict\"}");
                LogDiag(trace);
                return false;
            }
            catch (Exception ex)
            {
                trace.Append(",\"err\":\"" + Esc(ex.Message) + "\"}");
                LogDiag(trace);
                return false;
            }
        }

        /// <summary>
        /// Probe BattleHero.StatImpactByEffects._statsImpactByEffect — the dict that holds active
        /// stat-modifying effects. Each value is a ValueTuple<Fixed, StatKindId, EffectContext>.
        /// EffectContext should carry the duration + source we need for direct buff tracking.
        /// </summary>
        internal bool TryEmitStatImpactDiag(IntPtr procPtr)
        {
            var trace = new StringBuilder();
            trace.Append("{\"diag\":\"si_probe\"");
            try
            {
                IntPtr stateObj = IL2CPPCallGetter(procPtr, "get_State");
                if (stateObj == IntPtr.Zero) { trace.Append(",\"err\":\"no state\"}"); LogDiag(trace); return false; }
                foreach (var sideGetter in new[] { "get_PlayerTeam", "get_EnemyTeam" })
                {
                    IntPtr team = IL2CPPCallGetter(stateObj, sideGetter);
                    if (team == IntPtr.Zero) continue;
                    IntPtr heroesColl = IL2CPPCallGetter(team, "get_HeroesWithGuardian");
                    if (heroesColl == IntPtr.Zero) continue;
                    IntPtr hc = il2cpp_object_get_class(heroesColl);
                    IntPtr getC = FindIL2CPPMethod(hc, "get_Count", 0);
                    IntPtr getI = FindIL2CPPMethod(hc, "get_Item", 1);
                    if (getC == IntPtr.Zero || getI == IntPtr.Zero) continue;
                    IntPtr eN = IntPtr.Zero;
                    IntPtr nR = il2cpp_runtime_invoke(getC, heroesColl, IntPtr.Zero, ref eN);
                    int n = nR != IntPtr.Zero ? Marshal.ReadInt32(nR + 0x10) : 0;
                    for (int i = 0; i < n; i++)
                    {
                        IntPtr ib = Marshal.AllocHGlobal(4); Marshal.WriteInt32(ib, i);
                        IntPtr ab = Marshal.AllocHGlobal(IntPtr.Size); Marshal.WriteIntPtr(ab, ib);
                        IntPtr eIt = IntPtr.Zero;
                        IntPtr heroObj = il2cpp_runtime_invoke(getI, heroesColl, ab, ref eIt);
                        Marshal.FreeHGlobal(ib); Marshal.FreeHGlobal(ab);
                        if (heroObj == IntPtr.Zero) continue;

                        // StatImpactByEffects @ 0xA0 → _statsImpactByEffect dict @ 0x18 inside it
                        IntPtr siObj = Marshal.ReadIntPtr(heroObj + 0xA0);
                        if (siObj == IntPtr.Zero) continue;
                        IntPtr siDict = Marshal.ReadIntPtr(siObj + 0x18);
                        if (siDict == IntPtr.Zero) continue;
                        int siCount = Marshal.ReadInt32(siDict + 0x20);
                        if (siCount <= 0) continue;
                        IntPtr siEntries = Marshal.ReadIntPtr(siDict + 0x18);
                        if (siEntries == IntPtr.Zero) continue;
                        long arrLen = Marshal.ReadInt64(siEntries + 0x18);

                        var sb = new StringBuilder();
                        sb.Append("{\"diag\":\"stat_impact_schema\"");
                        sb.Append(",\"hero_idx\":" + i);
                        sb.Append(",\"side\":\"" + sideGetter.Substring(4) + "\"");
                        sb.Append(",\"si_count\":" + siCount);
                        sb.Append(",\"arr_len\":" + arrLen);

                        // ValueTuple<Fixed, StatKindId, EffectContext> as the value.
                        // ValueTuple<long,int,IntPtr> has layout: long(8) + int(4) + pad(4) + IntPtr(8) = 24 bytes
                        // Entry<K,V>: hashCode(4) + next(4) + key(int=4) + pad(4) + value(24) = 40 bytes typically
                        // But we need to dump the actual class to confirm
                        IntPtr siDictClass = il2cpp_object_get_class(siDict);
                        AppendClassFields(sb, siDictClass, "dict_fields", 15);

                        // Try walking entries — value contains EffectContext as third tuple element
                        // Tuple layout assumed: +0(Fixed:8) +8(StatKindId int:4) +0x10(EffectContext IntPtr:8)
                        // Entry stride: 0x28 estimated (hash:4, next:4, key:4, pad:4, value:24)
                        foreach (int stride in new[] { 0x28, 0x20, 0x18, 0x30 })
                        {
                            // Try to find a non-null EffectContext at each candidate entry
                            for (int e = 0; e < arrLen && e < 8; e++)
                            {
                                IntPtr entryAddr = siEntries + 0x20 + e * stride;
                                int hashCode = Marshal.ReadInt32(entryAddr + 0x00);
                                if (hashCode == 0) continue;
                                int keyVal = Marshal.ReadInt32(entryAddr + 0x08);
                                long fixedVal = Marshal.ReadInt64(entryAddr + 0x10);
                                int statKindId = Marshal.ReadInt32(entryAddr + 0x18);
                                IntPtr effCtx = Marshal.ReadIntPtr(entryAddr + 0x20);
                                if (effCtx != IntPtr.Zero)
                                {
                                    IntPtr ecCls = il2cpp_object_get_class(effCtx);
                                    string ecTy = Marshal.PtrToStringAnsi(il2cpp_class_get_name(ecCls));
                                    sb.Append(",\"stride\":\"0x" + stride.ToString("X") + "\"");
                                    sb.Append(",\"sample_key\":" + keyVal);
                                    sb.Append(",\"fixed_raw\":" + fixedVal);
                                    sb.Append(",\"stat_kind\":" + statKindId);
                                    sb.Append(",\"effect_ctx_type\":\"" + Esc(ecTy ?? "?") + "\"");
                                    AppendClassProps(sb, ecCls, "effect_ctx_props", 40);
                                    AppendClassFields(sb, ecCls, "effect_ctx_fields", 40);
                                    sb.Append("}");
                                    LogDiag(sb);
                                    return true;
                                }
                            }
                        }
                        sb.Append(",\"err\":\"no EffectContext found via known strides\"}");
                        LogDiag(sb);
                        continue;
                    }
                }
                trace.Append(",\"err\":\"no populated StatImpact dict\"}");
                LogDiag(trace);
                return false;
            }
            catch (Exception ex)
            {
                trace.Append(",\"err\":\"" + Esc(ex.Message) + "\"}");
                LogDiag(trace);
                return false;
            }
        }

        internal bool TryEmitAppliedEffectDiag(IntPtr procPtr)
        {
            var trace = new StringBuilder();
            trace.Append("{\"diag\":\"effect_probe\"");
            try
            {
                IntPtr stateObj = IL2CPPCallGetter(procPtr, "get_State");
                if (stateObj == IntPtr.Zero) { trace.Append(",\"err\":\"no state\"}"); LogDiag(trace); return false; }
                foreach (var sideGetter in new[] { "get_PlayerTeam", "get_EnemyTeam" })
                {
                    IntPtr team = IL2CPPCallGetter(stateObj, sideGetter);
                    if (team == IntPtr.Zero) continue;
                    IntPtr heroesColl = IL2CPPCallGetter(team, "get_HeroesWithGuardian");
                    if (heroesColl == IntPtr.Zero) continue;
                    IntPtr hc = il2cpp_object_get_class(heroesColl);
                    IntPtr getC = FindIL2CPPMethod(hc, "get_Count", 0);
                    IntPtr getI = FindIL2CPPMethod(hc, "get_Item", 1);
                    if (getC == IntPtr.Zero || getI == IntPtr.Zero) continue;
                    IntPtr eN = IntPtr.Zero;
                    IntPtr nR = il2cpp_runtime_invoke(getC, heroesColl, IntPtr.Zero, ref eN);
                    int n = nR != IntPtr.Zero ? Marshal.ReadInt32(nR + 0x10) : 0;
                    trace.Append(",\"" + sideGetter.Substring(4) + "_n\":" + n);
                    for (int i = 0; i < n; i++)
                    {
                        IntPtr ib = Marshal.AllocHGlobal(4); Marshal.WriteInt32(ib, i);
                        IntPtr ab = Marshal.AllocHGlobal(IntPtr.Size); Marshal.WriteIntPtr(ab, ib);
                        IntPtr eIt = IntPtr.Zero;
                        IntPtr heroObj = il2cpp_runtime_invoke(getI, heroesColl, ab, ref eIt);
                        Marshal.FreeHGlobal(ib); Marshal.FreeHGlobal(ab);
                        if (heroObj == IntPtr.Zero) continue;

                        // Walk heroObj → PhaseEffects → _effectsByPhaseIndex (array of List<EffectType>)
                        // For the first non-empty list, dump its element's class + fields.
                        IntPtr phaseEffects = Marshal.ReadIntPtr(heroObj + 0xF0);
                        if (phaseEffects == IntPtr.Zero) { trace.Append(",\"h" + i + "\":\"PhaseEffects=null\""); continue; }
                        IntPtr effArr = Marshal.ReadIntPtr(phaseEffects + 0x10);
                        if (effArr == IntPtr.Zero) { trace.Append(",\"h" + i + "\":\"effArr=null\""); continue; }
                        // IL2CPP array layout: header(16) + bounds(8 @0x10) + max_length(8 @0x18) + elements(@0x20)
                        long arrLen = Marshal.ReadInt64(effArr + 0x18);
                        trace.Append(",\"h" + i + "_arrLen\":" + arrLen);
                        if (arrLen <= 0) { continue; }
                        // Walk array slots looking for a non-empty list
                        IntPtr listObj = IntPtr.Zero;
                        int listIdx = -1;
                        int listCount = 0;
                        for (int z = 0; z < arrLen && z < 64; z++)
                        {
                            IntPtr slot = Marshal.ReadIntPtr(effArr + 0x20 + z * IntPtr.Size);
                            if (slot == IntPtr.Zero) continue;
                            IntPtr slotCls = il2cpp_object_get_class(slot);
                            IntPtr slotCnt = FindIL2CPPMethod(slotCls, "get_Count", 0);
                            if (slotCnt == IntPtr.Zero) continue;
                            IntPtr sE = IntPtr.Zero;
                            IntPtr cR = il2cpp_runtime_invoke(slotCnt, slot, IntPtr.Zero, ref sE);
                            int c = cR != IntPtr.Zero ? Marshal.ReadInt32(cR + 0x10) : 0;
                            if (c > 0) { listObj = slot; listIdx = z; listCount = c; break; }
                        }
                        if (listObj == IntPtr.Zero) { trace.Append(",\"h" + i + "\":\"all phase lists empty\""); continue; }
                        trace.Append(",\"h" + i + "_phaseIdx\":" + listIdx);
                        trace.Append(",\"h" + i + "_listCount\":" + listCount);
                        // Grab first EffectType from the list
                        IntPtr listCls2 = il2cpp_object_get_class(listObj);
                        IntPtr getItem2 = FindIL2CPPMethod(listCls2, "get_Item", 1);
                        if (getItem2 == IntPtr.Zero) continue;
                        IntPtr ibE = Marshal.AllocHGlobal(4); Marshal.WriteInt32(ibE, 0);
                        IntPtr abE = Marshal.AllocHGlobal(IntPtr.Size); Marshal.WriteIntPtr(abE, ibE);
                        IntPtr eiE = IntPtr.Zero;
                        IntPtr effObj = il2cpp_runtime_invoke(getItem2, listObj, abE, ref eiE);
                        Marshal.FreeHGlobal(ibE); Marshal.FreeHGlobal(abE);
                        if (effObj == IntPtr.Zero) continue;

                        // Dump EffectType class + props + fields
                        IntPtr effCls = il2cpp_object_get_class(effObj);
                        string effTy = Marshal.PtrToStringAnsi(il2cpp_class_get_name(effCls));
                        var schema = new StringBuilder();
                        schema.Append("{\"diag\":\"effect_schema\"");
                        schema.Append(",\"hero_idx\":" + i);
                        schema.Append(",\"side\":\"" + sideGetter.Substring(4) + "\"");
                        schema.Append(",\"phase_idx\":" + listIdx);
                        schema.Append(",\"list_count\":" + listCount);
                        schema.Append(",\"effect_type\":\"" + Esc(effTy ?? "?") + "\"");
                        AppendClassProps(schema, effCls, "effect_props", 40);
                        AppendClassFields(schema, effCls, "effect_fields", 40);
                        schema.Append("}");
                        LogDiag(schema);
                        return true;
                    }
                }
                trace.Append(",\"err\":\"no populated PhaseEffects list found\"}");
                LogDiag(trace);
                return false;
            }
            catch (Exception ex)
            {
                trace.Append(",\"err\":\"" + Esc(ex.Message) + "\"}");
                LogDiag(trace);
                return false;
            }
        }

        private void AppendClassFields(StringBuilder sb, IntPtr klass, string key, int cap)
        {
            var list = new List<string>();
            IntPtr k = klass;
            while (k != IntPtr.Zero && list.Count < cap)
            {
                IntPtr iter = IntPtr.Zero; IntPtr f;
                while ((f = il2cpp_class_get_fields(k, ref iter)) != IntPtr.Zero)
                {
                    string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(f));
                    if (fn == null) continue;
                    IntPtr ft = il2cpp_field_get_type(f);
                    string tn = ft != IntPtr.Zero ? Marshal.PtrToStringAnsi(il2cpp_type_get_name(ft)) : "?";
                    uint off = il2cpp_field_get_offset(f);
                    list.Add(fn + ":" + (tn ?? "?") + "@" + off.ToString("X"));
                }
                k = il2cpp_class_get_parent(k);
                string pn = k != IntPtr.Zero ? Marshal.PtrToStringAnsi(il2cpp_class_get_name(k)) : "";
                if (pn == "Object" || pn == "Il2CppObjectBase" || string.IsNullOrEmpty(pn)) break;
            }
            sb.Append(",\"" + key + "\":[");
            for (int i = 0; i < list.Count; i++) { if (i>0) sb.Append(","); sb.Append("\""+Esc(list[i])+"\""); }
            sb.Append("]");
        }

        private void AppendClassProps(StringBuilder sb, IntPtr klass, string key, int cap)
        {
            var list = new List<string>();
            IntPtr k = klass;
            while (k != IntPtr.Zero && list.Count < cap)
            {
                IntPtr mIter = IntPtr.Zero; IntPtr m;
                while ((m = il2cpp_class_get_methods(k, ref mIter)) != IntPtr.Zero)
                {
                    string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                    if (mn != null && mn.StartsWith("get_") && il2cpp_method_get_param_count(m) == 0)
                        list.Add(mn.Substring(4));
                }
                k = il2cpp_class_get_parent(k);
                string pn = k != IntPtr.Zero ? Marshal.PtrToStringAnsi(il2cpp_class_get_name(k)) : "";
                if (pn == "Object" || pn == "Il2CppObjectBase" || string.IsNullOrEmpty(pn)) break;
            }
            sb.Append(",\"" + key + "\":[");
            for (int i = 0; i < list.Count; i++) { if (i>0) sb.Append(","); sb.Append("\""+Esc(list[i])+"\""); }
            sb.Append("]");
        }

        /// <summary>
        /// For a label like "buffs" look at all getters whose name contains the label (case-insensitive),
        /// pick the first that returns a collection, and dump its element's class + props.
        /// </summary>
        private void AppendFirstElementProps(StringBuilder sb, IntPtr heroClass, IntPtr heroObj, string label)
        {
            try
            {
                // Scan getters whose name contains the label (case-insensitive)
                IntPtr k = heroClass;
                while (k != IntPtr.Zero)
                {
                    IntPtr mIter = IntPtr.Zero; IntPtr m;
                    while ((m = il2cpp_class_get_methods(k, ref mIter)) != IntPtr.Zero)
                    {
                        string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                        if (mn == null || !mn.StartsWith("get_") || il2cpp_method_get_param_count(m) != 0) continue;
                        if (mn.IndexOf(label, StringComparison.OrdinalIgnoreCase) < 0) continue;

                        IntPtr e = IntPtr.Zero;
                        IntPtr coll = il2cpp_runtime_invoke(m, heroObj, IntPtr.Zero, ref e);
                        if (coll == IntPtr.Zero) continue;
                        IntPtr cCls = il2cpp_object_get_class(coll);
                        IntPtr gC = FindIL2CPPMethod(cCls, "get_Count", 0);
                        IntPtr gI = FindIL2CPPMethod(cCls, "get_Item", 1);
                        if (gC == IntPtr.Zero || gI == IntPtr.Zero) continue;
                        IntPtr eN = IntPtr.Zero;
                        IntPtr nR = il2cpp_runtime_invoke(gC, coll, IntPtr.Zero, ref eN);
                        int n = nR != IntPtr.Zero ? Marshal.ReadInt32(nR + 0x10) : 0;

                        sb.Append(",\"" + label + "_getter\":\"" + Esc(mn.Substring(4)) + "\"");
                        sb.Append(",\"" + label + "_count\":" + n);
                        if (n <= 0) return;

                        IntPtr ib = Marshal.AllocHGlobal(4); Marshal.WriteInt32(ib, 0);
                        IntPtr ab = Marshal.AllocHGlobal(IntPtr.Size); Marshal.WriteIntPtr(ab, ib);
                        IntPtr eIt = IntPtr.Zero;
                        IntPtr elObj = il2cpp_runtime_invoke(gI, coll, ab, ref eIt);
                        Marshal.FreeHGlobal(ib); Marshal.FreeHGlobal(ab);
                        if (elObj == IntPtr.Zero) return;
                        IntPtr elCls = il2cpp_object_get_class(elObj);
                        string elTy = Marshal.PtrToStringAnsi(il2cpp_class_get_name(elCls));
                        sb.Append(",\"" + label + "_el_type\":\"" + Esc(elTy ?? "?") + "\"");
                        AppendClassProps(sb, elCls, label + "_el_props", 40);
                        return;
                    }
                    k = il2cpp_class_get_parent(k);
                    string pn = k != IntPtr.Zero ? Marshal.PtrToStringAnsi(il2cpp_class_get_name(k)) : "";
                    if (pn == "Object" || pn == "Il2CppObjectBase" || string.IsNullOrEmpty(pn)) break;
                }
            }
            catch { }
        }

        /// <summary>
        /// Call a 0-param getter method via IL2CPP and return the result pointer.
        /// </summary>
        private IntPtr IL2CPPCallGetter(IntPtr obj, string methodName)
        {
            IntPtr klass = il2cpp_object_get_class(obj);
            IntPtr method = FindIL2CPPMethod(klass, methodName, 0);
            if (method == IntPtr.Zero) return IntPtr.Zero;
            IntPtr exc = IntPtr.Zero;
            return il2cpp_runtime_invoke(method, obj, IntPtr.Zero, ref exc);
        }

        /// <summary>
        /// Find a method by name and param count on an IL2CPP class (walks parent chain).
        /// </summary>
        private IntPtr FindIL2CPPMethod(IntPtr klass, string methodName, int paramCount)
        {
            IntPtr k = klass;
            while (k != IntPtr.Zero)
            {
                IntPtr mIter = IntPtr.Zero;
                IntPtr m;
                while ((m = il2cpp_class_get_methods(k, ref mIter)) != IntPtr.Zero)
                {
                    string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                    if (mn == methodName && il2cpp_method_get_param_count(m) == paramCount)
                        return m;
                }
                k = il2cpp_class_get_parent(k);
                string pn = k != IntPtr.Zero ? Marshal.PtrToStringAnsi(il2cpp_class_get_name(k)) : "";
                if (pn == "Object" || pn == "Il2CppObjectBase" || string.IsNullOrEmpty(pn)) break;
            }
            return IntPtr.Zero;
        }

        /// Navigate from a battle access object down to the BattleProcessor.
        /// Tries multiple property paths up to 2 levels deep.
        /// </summary>
        private object FindBattleProcessor(object obj)
        {
            if (obj == null) return null;
            string typeName = obj.GetType().FullName ?? "";

            // If it's already a BattleProcessor, return it
            if (typeName.Contains("BattleProcessor")) return obj;

            // Try common navigation paths
            string[] navProps = { "Processor", "BattleProcessor", "Context", "Battle",
                                  "CurrentBattle", "ActiveBattle", "Model", "Core" };
            foreach (var pName in navProps)
            {
                try
                {
                    var val = Prop(obj, pName);
                    if (val == null) continue;
                    string valType = val.GetType().FullName ?? "";
                    if (valType.Contains("BattleProcessor")) return val;

                    // One more level deep
                    foreach (var pName2 in navProps)
                    {
                        try
                        {
                            var val2 = Prop(val, pName2);
                            if (val2 != null && (val2.GetType().FullName ?? "").Contains("BattleProcessor"))
                                return val2;
                        }
                        catch { }
                    }
                }
                catch { }
            }

            // If we can't find BattleProcessor specifically, return the object itself
            // — we'll still attempt to read heroes from it
            return obj;
        }

        /// <summary>
        /// Append a single BattleHero's data to the JSON StringBuilder.
        /// </summary>
        private void AppendBattleHero(StringBuilder sb, object hero)
        {
            // Basic identification
            int id = IntProp(hero, "Id");
            if (id == 0) id = IntProp(hero, "HeroId");
            sb.Append("\"id\":" + id);

            int typeId = IntProp(hero, "TypeId");
            if (typeId == 0) typeId = IntProp(hero, "HeroTypeId");
            if (typeId > 0) sb.Append(",\"type_id\":" + typeId);

            // Name
            try
            {
                var nameObj = Prop(hero, "Name");
                if (nameObj != null)
                {
                    string name = nameObj.ToString();
                    if (!string.IsNullOrEmpty(name))
                        sb.Append(",\"name\":\"" + Esc(name) + "\"");
                }
            }
            catch { }

            // Team indicator (0=player, 1=enemy typically)
            try
            {
                var team = Prop(hero, "Team");
                if (team != null) sb.Append(",\"team\":" + Convert.ToInt32(team));
            }
            catch { }

            // Stamina (Turn Meter) — Fixed type, range 0-1000
            try
            {
                var stamina = Prop(hero, "Stamina");
                if (stamina != null)
                {
                    double tm = ReadFixed(stamina);
                    sb.Append(",\"stamina\":" + FixedToJson(tm));
                }
            }
            catch { }

            // Health — current HP
            try
            {
                var health = Prop(hero, "Health");
                if (health != null)
                {
                    double hp = ReadFixed(health);
                    sb.Append(",\"health\":" + FixedToJson(hp));
                }
            }
            catch { }

            // Max Health
            try
            {
                var maxHp = Prop(hero, "MaxHealth");
                if (maxHp != null)
                {
                    double mhp = ReadFixed(maxHp);
                    sb.Append(",\"max_health\":" + FixedToJson(mhp));
                }
            }
            catch { }

            // DamageTaken — cumulative
            try
            {
                var dmg = Prop(hero, "DamageTaken");
                if (dmg != null)
                {
                    double d = ReadFixed(dmg);
                    sb.Append(",\"damage_taken\":" + FixedToJson(d));
                }
            }
            catch { }

            // TurnCount
            try
            {
                int turns = IntProp(hero, "TurnCount");
                sb.Append(",\"turn_count\":" + turns);
            }
            catch { }

            // IsUnkillable
            try
            {
                var unk = Prop(hero, "IsUnkillable");
                if (unk is bool b) sb.Append(",\"is_unkillable\":" + (b ? "true" : "false"));
            }
            catch { }

            // HeroState — IsDead, IsStunned, etc.
            try
            {
                var heroState = Prop(hero, "_heroState");
                if (heroState == null) heroState = Prop(hero, "HeroState");
                if (heroState == null) heroState = Prop(hero, "State");
                if (heroState != null)
                {
                    sb.Append(",\"state\":{");
                    bool first = true;
                    string[] boolProps = { "IsDead", "IsStunned", "IsBlockDebuff", "IsSleep",
                                           "IsFrozen", "IsProvoked", "IsFeared", "IsBombed",
                                           "IsBlockActiveSkills", "IsBlockPassiveSkills" };
                    foreach (var pName in boolProps)
                    {
                        try
                        {
                            var val = Prop(heroState, pName);
                            if (val is bool bv)
                            {
                                if (!first) sb.Append(",");
                                sb.Append("\"" + pName + "\":" + (bv ? "true" : "false"));
                                first = false;
                            }
                        }
                        catch { }
                    }
                    sb.Append("}");
                }
            }
            catch { }

            // Skills with cooldowns
            try
            {
                var skills = Prop(hero, "Skills");
                if (skills != null)
                {
                    sb.Append(",\"skills\":[");
                    int si = 0;
                    foreach (var skill in ListItems(skills))
                    {
                        if (skill == null) continue;
                        if (si > 0) sb.Append(",");
                        sb.Append("{");
                        int skillTypeId = IntProp(skill, "TypeId");
                        if (skillTypeId == 0) skillTypeId = IntProp(skill, "Id");
                        sb.Append("\"type_id\":" + skillTypeId);

                        int cd = IntProp(skill, "Cooldown");
                        sb.Append(",\"cooldown\":" + cd);

                        // Current cooldown remaining
                        try
                        {
                            int cdRemain = IntProp(skill, "CooldownRemaining");
                            if (cdRemain == 0) cdRemain = IntProp(skill, "CurrentCooldown");
                            sb.Append(",\"cooldown_remaining\":" + cdRemain);
                        }
                        catch { }

                        sb.Append("}");
                        si++;
                    }
                    sb.Append("]");
                }
            }
            catch { }

            // Buffs and Debuffs — from StatusEffects or Bonuses
            try
            {
                object effects = Prop(hero, "StatusEffects");
                if (effects == null) effects = Prop(hero, "Effects");
                if (effects == null) effects = Prop(hero, "AppliedEffects");
                if (effects == null)
                {
                    // Try through Bonuses sub-object
                    var bonuses = Prop(hero, "Bonuses");
                    if (bonuses != null)
                    {
                        effects = Prop(bonuses, "StatusEffects");
                        if (effects == null) effects = Prop(bonuses, "Effects");
                        if (effects == null) effects = Prop(bonuses, "AppliedEffects");
                    }
                }

                if (effects != null)
                {
                    sb.Append(",\"effects\":[");
                    int ei = 0;
                    foreach (var effect in ListItems(effects))
                    {
                        if (effect == null) continue;
                        if (ei > 0) sb.Append(",");
                        sb.Append("{");

                        int effectTypeId = IntProp(effect, "TypeId");
                        if (effectTypeId == 0) effectTypeId = IntProp(effect, "StatusEffectTypeId");
                        sb.Append("\"type_id\":" + effectTypeId);

                        int dur = IntProp(effect, "Duration");
                        sb.Append(",\"duration\":" + dur);

                        try
                        {
                            var isDebuff = Prop(effect, "IsDebuff");
                            if (isDebuff is bool db)
                                sb.Append(",\"is_debuff\":" + (db ? "true" : "false"));
                        }
                        catch { }

                        // Value (for damage effects like Poison)
                        try
                        {
                            var val = Prop(effect, "Value");
                            if (val != null)
                            {
                                double v = ReadFixed(val);
                                if (v != 0) sb.Append(",\"value\":" + FixedToJson(v));
                            }
                        }
                        catch { }

                        sb.Append("}");
                        ei++;
                    }
                    sb.Append("]");
                }
            }
            catch { }

            // EmpowerLevel
            try
            {
                int emp = IntProp(hero, "EmpowerLevel");
                if (emp > 0) sb.Append(",\"empower\":" + emp);
            }
            catch { }
        }

        // =====================================================
        // API: /mastery-data, /open-mastery, /reset-masteries
        // =====================================================
    }
}
