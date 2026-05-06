// Auto-extracted from RaidAutomationPlugin.cs (slice: presets / team AI).
// All methods are partial-class members of RaidAutomationPlugin.
// Behavior identical; isolates preset CRUD endpoints (/presets,
// /save-preset, /update-preset, /preset-schema, /remove-preset) plus
// the IL2CPP plumbing they need (MakeIl2CppList / MakeIl2CppDict).
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
        // =====================================================

        /// <summary>
        /// Find and invoke Execute() on a game command. Must be called from main thread.
        /// </summary>
        // =====================================================
        // API: /presets — read team AI presets
        // =====================================================
        private string GetPresets()
        {
            var uw = GetUserWrapper();
            if (uw == null) return "{\"error\":\"Not logged in\"}";

            var sb = new StringBuilder(8192);
            sb.Append("{\"presets\":[");

            try
            {
                var heroes = Prop(uw, "Heroes");
                var heroData = Prop(heroes, "HeroData");

                // HeroesAiPresets is on UserHeroData
                // But it might be on a different path — try HeroesWrapper first
                object presetList = null;

                // Try UserHeroData.HeroesAiPresets
                if (heroData != null)
                    presetList = Prop(heroData, "HeroesAiPresets");

                // Also try via HeroesWrapper
                if (presetList == null)
                    presetList = Prop(heroes, "HeroesAiPresets");

                if (presetList != null)
                {
                    int pi = 0;
                    foreach (var preset in ListItems(presetList))
                    {
                        if (pi > 0) sb.Append(",");
                        sb.Append("{");

                        int presetId = IntProp(preset, "Id");
                        string presetName = StrProp(preset, "Name");
                        bool isEmpty = false;
                        try { isEmpty = (bool)Prop(preset, "IsEmpty"); } catch { }

                        sb.Append("\"id\":" + presetId);
                        sb.Append(",\"name\":\"" + Esc(presetName) + "\"");
                        sb.Append(",\"empty\":" + (isEmpty ? "true" : "false"));

                        // Type
                        try
                        {
                            var typeVal = Prop(preset, "Type");
                            if (typeVal != null)
                                sb.Append(",\"type\":" + Convert.ToInt32(typeVal));
                        }
                        catch { }

                        // SkillPrioritiesSetups — the hero slots
                        var setups = Prop(preset, "SkillPrioritiesSetups");
                        if (setups != null)
                        {
                            sb.Append(",\"heroes\":[");
                            int si = 0;
                            foreach (var setup in ListItems(setups))
                            {
                                int heroId = IntProp(setup, "HeroId");
                                if (heroId <= 0) continue;

                                if (si > 0) sb.Append(",");
                                sb.Append("{\"hero_id\":" + heroId);

                                // StarterSkillId
                                try
                                {
                                    var starter = Prop(setup, "StarterSkillId");
                                    if (starter != null)
                                    {
                                        var hasVal = Prop(starter, "HasValue");
                                        if (hasVal != null && (bool)hasVal)
                                        {
                                            var val = Prop(starter, "Value");
                                            if (val != null)
                                                sb.Append(",\"starter_skill\":" + Convert.ToInt32(val));
                                        }
                                    }
                                }
                                catch { }

                                // PriorityBySkillId — base priorities
                                var priorities = Prop(setup, "PriorityBySkillId");
                                if (priorities != null)
                                {
                                    sb.Append(",\"priorities\":{");
                                    int pri = 0;
                                    foreach (var (skillId, prioObj) in DictEntries(priorities))
                                    {
                                        int prio = 0;
                                        try { prio = Convert.ToInt32(prioObj); } catch { }
                                        if (pri > 0) sb.Append(",");
                                        sb.Append("\"" + skillId + "\":" + prio);
                                        pri++;
                                    }
                                    sb.Append("}");
                                }

                                // Sequences — per-round setups
                                var sequences = Prop(setup, "Sequences");
                                if (sequences != null)
                                {
                                    sb.Append(",\"rounds\":[");
                                    int ri = 0;
                                    foreach (var seq in ListItems(sequences))
                                    {
                                        if (ri > 0) sb.Append(",");
                                        sb.Append("{");
                                        // Track whether any field has been written so the
                                        // next field's leading comma is conditional.
                                        // Prevents `{,"priorities":...}` malformed JSON
                                        // when StarterSkillId is null.
                                        bool roundHasField = false;

                                        // StarterSkillId for this round (Nullable<SkillTypeId>).
                                        // The .Value property returns marshaled garbage on
                                        // IL2Cpp wrappers — use NullableEnumInt (reads native
                                        // Pointer+16 directly).
                                        int starter = NullableEnumInt(Prop(seq, "StarterSkillId"));
                                        if (starter > 0)
                                        {
                                            sb.Append("\"starter\":" + starter);
                                            roundHasField = true;
                                        }

                                        // StarterSkillIds list
                                        var rStarterIds = Prop(seq, "StarterSkillIds");
                                        if (rStarterIds != null)
                                        {
                                            if (roundHasField) sb.Append(",");
                                            sb.Append("\"starter_ids\":[");
                                            int sti = 0;
                                            foreach (var sid in ListItems(rStarterIds))
                                            {
                                                if (sti > 0) sb.Append(",");
                                                try { sb.Append(Convert.ToInt32(sid)); } catch { }
                                                sti++;
                                            }
                                            sb.Append("]");
                                            roundHasField = true;
                                        }

                                        // PriorityBySkillId for this round
                                        var rPrios = Prop(seq, "PriorityBySkillId");
                                        if (rPrios != null)
                                        {
                                            if (roundHasField) sb.Append(",");
                                            sb.Append("\"priorities\":{");
                                            int rpi = 0;
                                            foreach (var (skillId, prioObj) in DictEntries(rPrios))
                                            {
                                                int prio = 0;
                                                try { prio = Convert.ToInt32(prioObj); } catch { }
                                                if (rpi > 0) sb.Append(",");
                                                sb.Append("\"" + skillId + "\":" + prio);
                                                rpi++;
                                            }
                                            sb.Append("}");
                                            roundHasField = true;
                                        }

                                        sb.Append("}");
                                        ri++;
                                    }
                                    sb.Append("]");
                                }

                                sb.Append("}");
                                si++;
                            }
                            sb.Append("]");
                        }

                        sb.Append("}");
                        pi++;
                    }
                }
            }
            catch (Exception ex)
            {
                sb.Append("{\"error\":\"" + Esc(ex.Message) + "\"}");
            }

            sb.Append("]}");
            return sb.ToString();
        }

        private string RemovePreset(string idStr)
        {
            if (string.IsNullOrEmpty(idStr))
                return "{\"error\":\"id required\"}";
            int presetId;
            if (!int.TryParse(idStr, out presetId))
                return "{\"error\":\"invalid id\"}";

            var cmdType = FindType("Client.Model.Gameplay.Heroes.Commands.RemoveAiPresetCmd");
            if (cmdType == null) return "{\"error\":\"RemoveAiPresetCmd not found\"}";

            try
            {
                var ctor = cmdType.GetConstructor(new[] { typeof(int) });
                if (ctor == null) return "{\"error\":\"ctor not found\"}";
                var cmd = ctor.Invoke(new object[] { presetId });
                InvokeExecute(cmd);
                return "{\"ok\":true,\"removed\":" + presetId + "}";
            }
            catch (TargetInvocationException tex)
            {
                return "{\"error\":\"" + Esc((tex.InnerException ?? tex).Message) + "\"}";
            }
        }

        // save-preset: Build a new HeroesAiPreset using the game's
        // own factories (BattlePresetsOverlayContext.CreateNewPreset
        // for the empty shell, HeroesAiPresetExtensions.
        // DefaultSkillPriorities for each hero's priority dict, then
        // the 3-arg SkillPrioritiesSetup ctor). Send via SaveAiPresetCmd.
        //
        // Earlier strategies (clone-then-mutate) failed local PreEdit
        // validation with HeroesAiPreset_InvalidPrioritiesTypes because
        // our manually-built priority dicts didn't have the proper
        // IL2Cpp-side enum value boxing the validator checks for. The
        // game's factory `DefaultSkillPriorities(HeroType)` produces
        // dicts the validator accepts.
        //
        // Params: name, heroes (comma-sep instance IDs), type (1=PvE)
        //   priorities: heroId:skillId=pri,skillId=pri;heroId:... (optional)
        //   pri: 0=Default, 1=First, 2=Second, 3=Third, 4=NotUsed
        private string SavePreset(string nameStr, string heroIdsStr, string typeStr, string emptyStr = null)
        {
            bool emptyOnly = (emptyStr == "1" || emptyStr == "true");
            if (!emptyOnly && string.IsNullOrEmpty(heroIdsStr))
                return "{\"error\":\"heroes required (comma-separated hero IDs), or pass empty=1 for an empty shell\"}";

            string presetName = string.IsNullOrEmpty(nameStr) ? "New Team" : nameStr;
            int presetType = 1; // GeneralPve
            if (!string.IsNullOrEmpty(typeStr))
                int.TryParse(typeStr, out presetType);

            var heroIds = new List<int>();
            if (!string.IsNullOrEmpty(heroIdsStr))
            {
                foreach (var s in heroIdsStr.Split(','))
                {
                    if (int.TryParse(s.Trim(), out int hid) && hid > 0)
                        heroIds.Add(hid);
                }
            }
            if (!emptyOnly && heroIds.Count == 0)
                return "{\"error\":\"no valid hero IDs\"}";

            var presetT = FindType("SharedModel.Meta.Heroes.HeroesAiPreset");
            var setupT = FindType("SharedModel.Meta.Heroes.SkillPrioritiesSetup");
            var sptEnum = FindType("SharedModel.Meta.Heroes.SkillPriorityType");
            var presetTypeEnum = FindType("SharedModel.Meta.Heroes.HeroesAiPresetType");

            if (presetT == null) return "{\"error\":\"HeroesAiPreset type not found\"}";
            if (setupT == null) return "{\"error\":\"SkillPrioritiesSetup type not found\"}";
            if (sptEnum == null) return "{\"error\":\"SkillPriorityType enum not found\"}";

            try
            {
                var uw = GetUserWrapper();
                var heroDict = Prop(Prop(Prop(uw, "Heroes"), "HeroData"), "HeroById");

                var sb = new StringBuilder();
                sb.Append("{\"ok\":true,\"debug\":{");

                // === Factory-based strategy (using game's own helpers) ===
                // 1. Find unused Id in 1-99 range so get_Type returns 1 (GeneralPvE)
                var usedIds = new HashSet<int>();
                try {
                    var heroes2 = Prop(uw, "Heroes");
                    var hd2 = Prop(heroes2, "HeroData");
                    object pl2 = Prop(hd2, "HeroesAiPresets") ?? Prop(heroes2, "HeroesAiPresets");
                    if (pl2 != null) {
                        foreach (var pp in ListItems(pl2))
                            usedIds.Add(IntProp(pp, "Id"));
                    }
                } catch {}
                int newId = 0;
                for (int candidate = 1; candidate < 100; candidate++) {
                    if (!usedIds.Contains(candidate)) { newId = candidate; break; }
                }
                if (newId == 0) return "{\"error\":\"no free preset Id in 1-99 range\"}";
                sb.Append("\"newId\":").Append(newId);

                // 2. Use BattlePresetsOverlayContext.CreateNewPreset(int id)
                //    to build the empty preset shell (proper IL2Cpp identity).
                var bpoT = FindType("Client.ViewModel.Contextes.BattlePresets.BattlePresetsOverlayContext");
                if (bpoT == null) return "{\"error\":\"BattlePresetsOverlayContext type not found\"}";
                var createM = bpoT.GetMethod("CreateNewPreset",
                    BindingFlags.NonPublic | BindingFlags.Static);
                if (createM == null)
                    createM = bpoT.GetMethod("CreateNewPreset",
                        BindingFlags.Public | BindingFlags.Static);
                if (createM == null) return "{\"error\":\"CreateNewPreset method not found\"}";
                object preset;
                try { preset = createM.Invoke(null, new object[] { newId }); }
                catch (TargetInvocationException tex) {
                    return "{\"error\":\"CreateNewPreset failed: " + Esc((tex.InnerException ?? tex).Message) + "\"}";
                }
                if (preset == null) return "{\"error\":\"CreateNewPreset returned null\"}";
                sb.Append(",\"strategy\":\"factory\"");

                // 3. Override Name (CreateNewPreset gave it "New Team N").
                SetFieldOrProp(presetT, preset, "Name", presetName);
                SetFieldOrProp(presetT, preset, "NameIsNotDefault", true);

                // 4. Build setups via game factories: for each hero,
                //    call DefaultSkillPriorities(hero.Type) to make the
                //    priority dict, then SkillPrioritiesSetup(heroId,
                //    dict, presetType) to build the setup with proper
                //    sequences. Add to preset.SkillPrioritiesSetups.
                var presetTypeEnumVal = presetTypeEnum != null
                    ? Enum.ToObject(presetTypeEnum, presetType)
                    : null;
                var hpExtT = FindType("SharedModel.Meta.Heroes.HeroesAiPresetExtensions");
                if (hpExtT == null) return "{\"error\":\"HeroesAiPresetExtensions not found\"}";
                var heroTypeT = FindType("SharedModel.Meta.Heroes.HeroType");
                if (heroTypeT == null) return "{\"error\":\"HeroType not found\"}";
                var defaultPrioritiesM = hpExtT.GetMethod("DefaultSkillPriorities",
                    BindingFlags.Public | BindingFlags.Static, null, new[] { heroTypeT }, null);
                if (defaultPrioritiesM == null)
                    return "{\"error\":\"DefaultSkillPriorities not found\"}";

                var setupCtor3 = setupT.GetConstructor(new[] { typeof(int), defaultPrioritiesM.ReturnType, presetTypeEnum });
                if (setupCtor3 == null)
                    return "{\"error\":\"3-arg SkillPrioritiesSetup ctor not found\"}";

                // Get the preset's setup list to add into
                var spsField = presetT.GetField("SkillPrioritiesSetups",
                    BindingFlags.Public | BindingFlags.Instance);
                object setupList = spsField != null ? spsField.GetValue(preset) : null;
                if (setupList == null) {
                    var getSetups = presetT.GetMethod("get_SkillPrioritiesSetups");
                    if (getSetups != null) setupList = getSetups.Invoke(preset, null);
                }
                if (setupList == null) return "{\"error\":\"preset.SkillPrioritiesSetups null\"}";
                var addSetupM = setupList.GetType().GetMethod("Add");
                if (addSetupM == null) return "{\"error\":\"setupList.Add not found\"}";

                sb.Append("},\"heroes\":[");
                bool first = true;
                // When emptyOnly=true, skip adding setups so the saved
                // preset has SkillPrioritiesSetups=[]. The validator's
                // per-setup loop is then a no-op.
                IEnumerable<int> setupHeroes = emptyOnly ? new int[0] : (IEnumerable<int>)heroIds;
                foreach (int heroId in setupHeroes)
                {
                    object hero = null;
                    try {
                        var ck = heroDict.GetType().GetMethod("ContainsKey");
                        if (ck != null && (bool)ck.Invoke(heroDict, new object[] { heroId }))
                            hero = heroDict.GetType().GetProperty("Item")?.GetValue(heroDict, new object[] { heroId });
                    } catch {}
                    if (hero == null) {
                        sb.Append(first ? "" : ",");
                        first = false;
                        sb.Append("{\"id\":").Append(heroId).Append(",\"err\":\"hero not found\"}");
                        continue;
                    }
                    object hType = Prop(hero, "Type");
                    if (hType == null) {
                        sb.Append(first ? "" : ",");
                        first = false;
                        sb.Append("{\"id\":").Append(heroId).Append(",\"err\":\"hero.Type null\"}");
                        continue;
                    }
                    // Build dict via game factory
                    object priDict;
                    try { priDict = defaultPrioritiesM.Invoke(null, new object[] { hType }); }
                    catch (TargetInvocationException tex) {
                        sb.Append(first ? "" : ",");
                        first = false;
                        sb.Append("{\"id\":").Append(heroId)
                          .Append(",\"err\":\"DefaultSkillPriorities: ")
                          .Append(Esc((tex.InnerException ?? tex).Message))
                          .Append("\"}");
                        continue;
                    }
                    // Build setup via 3-arg ctor
                    object setup;
                    try { setup = setupCtor3.Invoke(new object[] { heroId, priDict, presetTypeEnumVal }); }
                    catch (TargetInvocationException tex) {
                        sb.Append(first ? "" : ",");
                        first = false;
                        sb.Append("{\"id\":").Append(heroId)
                          .Append(",\"err\":\"setup ctor: ")
                          .Append(Esc((tex.InnerException ?? tex).Message))
                          .Append("\"}");
                        continue;
                    }
                    addSetupM.Invoke(setupList, new object[] { setup });
                    sb.Append(first ? "" : ",");
                    first = false;
                    sb.Append("{\"id\":").Append(heroId).Append(",\"ok\":true}");
                }
                sb.Append("]");

                // 5. Save via SaveAiPresetCmd (same path as
                //    BattlePresetsOverlayContext.SavePreset uses).
                var cmdT = FindType("Client.Model.Gameplay.Heroes.Commands.SaveAiPresetCmd");
                if (cmdT == null) return "{\"error\":\"SaveAiPresetCmd not found\"}";
                var cmdCtor = cmdT.GetConstructor(new[] { presetT });
                if (cmdCtor == null) return "{\"error\":\"SaveAiPresetCmd ctor not found\"}";
                var cmd = cmdCtor.Invoke(new object[] { preset });
                try { InvokeExecute(cmd); }
                catch (TargetInvocationException tex) {
                    return sb.ToString() + ",\"saveError\":\""
                         + Esc((tex.InnerException ?? tex).Message) + "\"}";
                }
                sb.Append(",\"name\":\"").Append(Esc(presetName)).Append("\"}");
                return sb.ToString();
            }
            catch (TargetInvocationException tex)
            {
                return "{\"error\":\"" + Esc((tex.InnerException ?? tex).Message) + "\"}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // The clone-and-mutate strategy is REMOVED. See git history
        // commit c450ef0 for the prior implementation. The factory
        // strategy above (CreateNewPreset + DefaultSkillPriorities +
        // 3-arg SkillPrioritiesSetup ctor) is the correct path.
#if false
        private string SavePreset_LegacyCloneStrategy(string nameStr, string heroIdsStr, string typeStr)
        {
            try
            {
                var uw = GetUserWrapper();
                var heroDict = Prop(Prop(Prop(uw, "Heroes"), "HeroData"), "HeroById");

                var sb = new StringBuilder();
                sb.Append("{\"ok\":true,\"debug\":{");

                // === Strategy A: Clone an existing preset and modify it ===
                // Pick the source preset deterministically: prefer one with the
                // SAME hero count we're creating (so the cloned setup list is
                // already the right size for in-place mutation) and matching
                // type. Fall back to "first preset" only when nothing better.
                object existingPreset = null;
                try
                {
                    var heroes = Prop(uw, "Heroes");
                    var heroData = Prop(heroes, "HeroData");
                    object presetList = Prop(heroData, "HeroesAiPresets");
                    if (presetList == null) presetList = Prop(heroes, "HeroesAiPresets");
                    if (presetList != null)
                    {
                        // Source-picker tiers (lower = more preferred):
                        //   0: same type, same heroes set, has starters
                        //   1: same type, same heroes set
                        //   2: same type, same hero count, has starters
                        //   3: same type, same hero count
                        //   4: same type
                        //   5: anything
                        // "has starters" = at least one Sequence has a non-empty
                        //   StarterSkillIds list. This matters because the
                        //   validator's first check on each setup is an Any()
                        //   over starters; cloning a source with that flag
                        //   already set means we don't trigger the empty-
                        //   starters fallback path that throws 80003.
                        var heroIdSet = new HashSet<int>(heroIds);
                        object[] tier = new object[6];
                        foreach (var p in ListItems(presetList))
                        {
                            int pType = 0;
                            try { pType = Convert.ToInt32(Prop(p, "Type")); } catch { }
                            var sps = Prop(p, "SkillPrioritiesSetups");
                            int spsCount = 0;
                            var spsHeroes = new HashSet<int>();
                            bool hasStarters = false;
                            if (sps != null)
                            {
                                var cntP = sps.GetType().GetProperty("Count");
                                var itemP = sps.GetType().GetProperty("Item");
                                if (cntP != null) spsCount = Convert.ToInt32(cntP.GetValue(sps));
                                if (itemP != null)
                                {
                                    for (int i = 0; i < spsCount; i++)
                                    {
                                        var setup = itemP.GetValue(sps, new object[] { i });
                                        spsHeroes.Add(IntProp(setup, "HeroId"));
                                        if (!hasStarters)
                                        {
                                            var seqs = Prop(setup, "Sequences");
                                            if (seqs != null)
                                            {
                                                var sCntP = seqs.GetType().GetProperty("Count");
                                                var sItemP = seqs.GetType().GetProperty("Item");
                                                int sCnt = sCntP != null ? Convert.ToInt32(sCntP.GetValue(seqs)) : 0;
                                                for (int j = 0; j < sCnt && !hasStarters; j++)
                                                {
                                                    var seq = sItemP.GetValue(seqs, new object[] { j });
                                                    if (seq == null) continue;
                                                    var ss = Prop(seq, "StarterSkillIds");
                                                    if (ss != null)
                                                    {
                                                        var sLen = ss.GetType().GetProperty("Count");
                                                        if (sLen != null && Convert.ToInt32(sLen.GetValue(ss)) > 0)
                                                            hasStarters = true;
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            bool sameType = pType == presetType;
                            bool sameHeroes = sameType && spsHeroes.SetEquals(heroIdSet);
                            bool sameCount = sameType && spsCount == heroIds.Count;
                            int t = sameHeroes && hasStarters ? 0
                                  : sameHeroes ? 1
                                  : sameCount && hasStarters ? 2
                                  : sameCount ? 3
                                  : sameType ? 4 : 5;
                            if (tier[t] == null) tier[t] = p;
                        }
                        for (int t = 0; t < 6; t++)
                        {
                            if (tier[t] != null) { existingPreset = tier[t]; break; }
                        }
                    }
                }
                catch { }

                object preset = null;
                string strategy = "unknown";

                if (existingPreset != null)
                {
                    // Clone existing preset — this creates a proper IL2CPP object
                    var cloneMethod = presetT.GetMethod("Clone", BindingFlags.Public | BindingFlags.Instance);
                    if (cloneMethod != null)
                    {
                        preset = cloneMethod.Invoke(existingPreset, null);
                        strategy = "clone";
                    }
                }

                if (preset == null)
                {
                    // Fallback: create new via Activator (may not persist)
                    preset = Activator.CreateInstance(presetT);
                    strategy = "activator";
                }

                sb.Append("\"strategy\":\"" + strategy + "\"");

                // Set fields — try both field and property setter, also try IL2CPP
                // raw field write for the Id (which must be 0 for "create new").
                SetFieldOrProp(presetT, preset, "Name", presetName);
                SetFieldOrProp(presetT, preset, "NameIsNotDefault", true);

                // Note: HeroesAiPreset.Type is a READ-ONLY computed
                // property (no setter, no backing field). It's derived
                // from the preset's SkillPrioritiesSetups — specifically
                // the number of Sequences each setup carries. The 3-arg
                // SkillPrioritiesSetup ctor below takes presetType and
                // builds Sequences accordingly, so we drive the type
                // through THAT path. Callers' `type` param flows in via
                // `presetTypeEnumVal` used in the ctor invocation.

                // CRITICAL: Pick an unused Id in the range 1-100 so the
                // game's HeroesAiPreset.get_Type() returns 1 (GeneralPvE).
                //
                // Earlier attempts forced Id to 0 thinking that meant
                // "new preset for server to assign". WRONG — game's
                // IsArenaDefencePreset(0) returns true, which makes
                // get_Type() return 2 (Pvp). The local Validate then
                // runs `AssertIsValidPrioritiesSetup(setup, Pvp, hero)`
                // and rejects because our setup structure is the
                // GeneralPvE shape (3 sequences), not Pvp-shape.
                //
                // Id range -> Type mapping (from get_Type disassembly):
                //    Id == 0, 301, 601-603 -> 2 (ArenaDefence/Pvp)
                //    Id < 100              -> 1 (GeneralPvE)
                //    100 <= Id < 200       -> 2 (Pvp)
                //    200 <= Id < 400       -> 4 (Fractions)
                //    400 <= Id < 700       -> 5 (DoomTower)
                //    700 <= Id < 800       -> 3 (Hydra)
                //    800 <= Id < 900       -> {6,7}
                //    Id >= 900             -> 7 (CooperationEventWorldBoss)
                //
                // For now we only support type=1 (GeneralPvE) reliably,
                // so pick any unused 1-100 Id. The server reassigns its
                // own Id on save anyway.
                int targetIdForType = 0;
                if (presetType == 1) // GeneralPvE
                {
                    var usedIds = new HashSet<int>();
                    try {
                        var heroes2 = Prop(uw, "Heroes");
                        var hd2 = Prop(heroes2, "HeroData");
                        object pl2 = Prop(hd2, "HeroesAiPresets") ?? Prop(heroes2, "HeroesAiPresets");
                        if (pl2 != null) {
                            foreach (var pp in ListItems(pl2))
                                usedIds.Add(IntProp(pp, "Id"));
                        }
                    } catch {}
                    for (int candidate = 1; candidate < 100; candidate++) {
                        if (!usedIds.Contains(candidate)) { targetIdForType = candidate; break; }
                    }
                }
                bool idSet = false;
                if (targetIdForType > 0) {
                    try {
                        var setId = presetT.GetMethod("set_Id");
                        if (setId != null) {
                            setId.Invoke(preset, new object[] { targetIdForType });
                            idSet = true;
                        }
                    } catch {}
                    if (!idSet) {
                        try {
                            var idField = presetT.GetField("Id", BindingFlags.Public | BindingFlags.Instance);
                            if (idField != null) { idField.SetValue(preset, targetIdForType); idSet = true; }
                        } catch {}
                    }
                    if (!idSet) {
                        // IL2CPP raw write
                        try {
                            var ptrProp = presetT.GetProperty("Pointer");
                            if (ptrProp != null) {
                                IntPtr ptr = (IntPtr)ptrProp.GetValue(preset);
                                if (ptr != IntPtr.Zero) {
                                    Marshal.WriteInt32(ptr + 0x10, targetIdForType);
                                    idSet = true;
                                }
                            }
                        } catch {}
                    }
                }
                sb.Append(",\"targetId\":").Append(targetIdForType);
                sb.Append(",\"idSet\":" + (idSet ? "true" : "false"));

                // Build the SkillPrioritiesSetups list using the game's own constructors.
                // SkillPrioritiesSetup has a ctor(int heroId, Dict<int,SPT> skills, PresetType)
                // that internally calls CreateSequences() to properly build sequences.

                // First, get the Dictionary<int, SkillPriorityType> type from an existing
                // setup's PriorityBySkillId field, OR construct it.
                var dictT = GetIl2CppDictType(typeof(int), sptEnum);
                sb.Append(",\"dictType\":\"" + (dictT != null ? dictT.FullName : "null") + "\"");

                // Get IL2CPP List<SkillPrioritiesSetup> from the CLONED preset
                // (don't create new — Activator gives managed list, not IL2CPP list)
                var spsField = presetT.GetField("SkillPrioritiesSetups",
                    BindingFlags.Public | BindingFlags.Instance);
                object setupList = null;
                if (spsField != null)
                    setupList = spsField.GetValue(preset);
                if (setupList == null)
                {
                    var getSetups = presetT.GetMethod("get_SkillPrioritiesSetups");
                    if (getSetups != null) setupList = getSetups.Invoke(preset, null);
                }
                if (setupList == null) return "{\"error\":\"cloned preset has null SkillPrioritiesSetups\"}";

                Type setupListT = setupList.GetType();
                sb.Append(",\"listType\":\"" + setupListT.FullName + "\"");

                // === Mutate-in-place strategy ===
                // Earlier strategy was clear-list + rebuild via the 3-arg
                // SkillPrioritiesSetup ctor. That triggered server-side
                // HeroesAiPreset_InvalidPrioritiesTypes (80003) — likely
                // because the dict we built in managed code didn't marshal
                // through SaveAiPresetCmd's serializer the way the validator
                // expects (Il2Cpp's enum value boxing, etc.).
                //
                // The clone source's setups are ALREADY validator-acceptable
                // by definition (the user saved them in-game). We mutate
                // those setups in place: keep the existing dict objects
                // and Sequences, just rewrite HeroId and translate skill
                // IDs to match the new hero. Everything else (priority
                // VALUES, Sequences count, type tags) stays untouched.
                var listCount = setupListT.GetProperty("Count");
                var listItem  = setupListT.GetProperty("Item");
                int existingCount = listCount != null ? Convert.ToInt32(listCount.GetValue(setupList)) : 0;
                sb.Append(",\"existingSetups\":" + existingCount);

                // Get/Add helpers; we may need to grow or shrink the list
                var addSetupM = setupListT.GetMethod("Add");
                var removeAtM = setupListT.GetMethod("RemoveAt", new[] { typeof(int) });
                var dictAdd = dictT.GetMethod("Add");
                if (dictAdd == null) dictAdd = dictT.GetMethod("Add", new[] { typeof(int), sptEnum });

                // If the cloned list has FEWER setups than we need, clone
                // the last one to fill. If MORE, drop extras from the end.
                while (existingCount < heroIds.Count)
                {
                    if (existingCount == 0)
                    {
                        sb.Append(",\"err\":\"clone source has 0 setups, cannot grow\"");
                        return sb.ToString() + "}";
                    }
                    object srcSetup = listItem.GetValue(setupList, new object[] { existingCount - 1 });
                    var setupCloneM = setupT.GetMethod("Clone", BindingFlags.Public | BindingFlags.Instance);
                    object newSetup = setupCloneM != null
                        ? setupCloneM.Invoke(srcSetup, null)
                        : null;
                    if (newSetup == null) { sb.Append(",\"err\":\"setup Clone failed\""); break; }
                    addSetupM.Invoke(setupList, new object[] { newSetup });
                    existingCount++;
                }
                while (existingCount > heroIds.Count)
                {
                    if (removeAtM == null) break;
                    removeAtM.Invoke(setupList, new object[] { existingCount - 1 });
                    existingCount--;
                }

                // Detect if the cloned source already has the EXACT
                // heroes we want — in that order. When true, skip the
                // per-setup remap entirely (zero-touch clone). The
                // source's skill_ids may even be STALE for the current
                // game version, but the validator was happy with them
                // when the user originally saved the preset, so leaving
                // them alone is safer than retranslating.
                bool sourceMatchesExactly = true;
                if (existingCount == heroIds.Count)
                {
                    for (int idx = 0; idx < heroIds.Count; idx++)
                    {
                        var sup = listItem.GetValue(setupList, new object[] { idx });
                        if (sup == null || IntProp(sup, "HeroId") != heroIds[idx])
                        {
                            sourceMatchesExactly = false;
                            break;
                        }
                    }
                }
                else
                {
                    sourceMatchesExactly = false;
                }
                sb.Append(",\"sourceMatchesExactly\":" + (sourceMatchesExactly ? "true" : "false"));

                sb.Append("},\"heroes\":[");
                bool first = true;

                for (int idx = 0; idx < heroIds.Count; idx++)
                {
                    int heroId = heroIds[idx];
                    object setup = listItem.GetValue(setupList, new object[] { idx });
                    if (setup == null) continue;

                    // Get hero's skills (only for the response payload)
                    object hero = null;
                    try {
                        var ck = heroDict.GetType().GetMethod("ContainsKey");
                        if (ck != null && (bool)ck.Invoke(heroDict, new object[] { heroId }))
                            hero = heroDict.GetType().GetProperty("Item")?.GetValue(heroDict, new object[] { heroId });
                    } catch {}

                    var newSkillIds = new List<int>();
                    if (hero != null)
                    {
                        try {
                            var skills = Prop(hero, "Skills");
                            if (skills != null)
                            {
                                var getCount = skills.GetType().GetProperty("Count");
                                int cnt = getCount != null ? Convert.ToInt32(getCount.GetValue(skills)) : 0;
                                var getItem = skills.GetType().GetProperty("Item");
                                for (int si = 0; si < cnt; si++)
                                {
                                    var skill = getItem?.GetValue(skills, new object[] { si });
                                    if (skill != null)
                                    {
                                        var typeId = Prop(skill, "TypeId");
                                        if (typeId != null) newSkillIds.Add(Convert.ToInt32(typeId));
                                    }
                                }
                            }
                        } catch {}
                    }

                    if (!sourceMatchesExactly)
                    {
                        // Mutate the cloned setup: set HeroId, translate every
                        // dict's skill IDs to match the new hero's skills.
                        SetFieldOrProp(setupT, setup, "HeroId", heroId);
                        RemapSetupSkillIds(setup, sptEnum, dictT, dictAdd, newSkillIds);
                    }
                    // else: leave the cloned setup completely untouched

                    if (!first) sb.Append(",");
                    first = false;
                    sb.Append("{\"id\":" + heroId + ",\"skills\":[" + string.Join(",", newSkillIds) + "]}");
                }

                sb.Append("]");

                // Add the new preset to the local HeroesAiPresets list in memory
                // (the game normally does this when the server responds)
                bool addedToList = false;
                try
                {
                    var uw2 = GetUserWrapper();
                    object presetListObj = Prop(Prop(Prop(uw2, "Heroes"), "HeroData"), "HeroesAiPresets");
                    if (presetListObj == null) presetListObj = Prop(Prop(uw2, "Heroes"), "HeroesAiPresets");
                    if (presetListObj != null)
                    {
                        var addM = presetListObj.GetType().GetMethod("Add");
                        if (addM != null)
                        {
                            addM.Invoke(presetListObj, new object[] { preset });
                            addedToList = true;
                        }
                    }
                }
                catch (Exception addEx)
                {
                    sb.Append(",\"addError\":\"" + Esc(addEx.Message) + "\"");
                }
                sb.Append(",\"addedToList\":" + (addedToList ? "true" : "false"));

                // Execute SaveAiPresetCmd to persist to server
                var cmdType = FindType("Client.Model.Gameplay.Heroes.Commands.SaveAiPresetCmd");
                if (cmdType == null) return "{\"error\":\"SaveAiPresetCmd not found\"}";

                var ctor = cmdType.GetConstructor(new[] { presetT });
                if (ctor == null) return "{\"error\":\"SaveAiPresetCmd ctor not found\"}";

                var cmd = ctor.Invoke(new object[] { preset });
                InvokeExecute(cmd);

                sb.Append(",\"name\":\"" + Esc(presetName) + "\"}");
                return sb.ToString();
            }
            catch (TargetInvocationException tex)
            {
                return "{\"error\":\"" + Esc((tex.InnerException ?? tex).Message) + "\"}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\",\"stack\":\"" + Esc(ex.StackTrace) + "\"}";
            }
        }
#endif

        /// <summary>
        /// Mutate a SkillPrioritiesSetup in place so its skill-id keys
        /// match the new hero's skill list. Preserves the priority
        /// VALUES (Default/First/Second/Third) by index — i.e., the
        /// first skill in the new hero's kit gets whatever priority the
        /// first skill in the old hero's kit had, etc. This keeps the
        /// validator-acceptable structure of the source preset while
        /// retargeting the heroes.
        /// </summary>
        private static void RemapSetupSkillIds(object setup, Type sptEnum, Type dictT, MethodInfo dictAdd, List<int> newSkillIds)
        {
            // Collect the OLD ordered skill ids from the setup-level
            // PriorityBySkillId dict (or the first sequence's dict, since
            // the setup-level dict is empty in valid presets).
            List<int> oldSkillIds = new List<int>();
            object templateDict = Prop(setup, "PriorityBySkillId");
            if (templateDict == null || GetDictCount(templateDict) == 0)
            {
                // Fall back to first sequence's dict for ordering
                var seqs = Prop(setup, "Sequences");
                if (seqs != null)
                {
                    var sCntP = seqs.GetType().GetProperty("Count");
                    var sItemP = seqs.GetType().GetProperty("Item");
                    int sCnt = sCntP != null ? Convert.ToInt32(sCntP.GetValue(seqs)) : 0;
                    if (sCnt > 0 && sItemP != null)
                    {
                        var firstSeq = sItemP.GetValue(seqs, new object[] { 0 });
                        if (firstSeq != null) templateDict = Prop(firstSeq, "PriorityBySkillId");
                    }
                }
            }
            if (templateDict != null)
            {
                CollectIl2CppDictKeys(templateDict, oldSkillIds);
            }

            // Translate the setup-level dict (usually empty, but mutate
            // in place anyway in case the source preset stamped values).
            object setupDict = Prop(setup, "PriorityBySkillId");
            if (setupDict != null)
            {
                RemapDictKeysPreservingValues(setupDict, oldSkillIds, newSkillIds, sptEnum, dictT, dictAdd);
            }

            // Translate each Sequence's PriorityBySkillId AND StarterSkillIds.
            var sequences = Prop(setup, "Sequences");
            if (sequences != null)
            {
                var cntP = sequences.GetType().GetProperty("Count");
                var itemP = sequences.GetType().GetProperty("Item");
                int cnt = cntP != null ? Convert.ToInt32(cntP.GetValue(sequences)) : 0;
                for (int i = 0; i < cnt; i++)
                {
                    object seq = itemP.GetValue(sequences, new object[] { i });
                    if (seq == null) continue;
                    var seqDict = Prop(seq, "PriorityBySkillId");
                    if (seqDict != null)
                        RemapDictKeysPreservingValues(seqDict, oldSkillIds, newSkillIds, sptEnum, dictT, dictAdd);

                    // Translate StarterSkillIds list (List<int>).
                    var starterList = Prop(seq, "StarterSkillIds");
                    if (starterList != null)
                    {
                        var sCntP = starterList.GetType().GetProperty("Count");
                        var sItemP = starterList.GetType().GetProperty("Item");
                        int sCnt = sCntP != null ? Convert.ToInt32(sCntP.GetValue(starterList)) : 0;
                        // Capture old starters → translate to new
                        var newStarters = new List<int>();
                        for (int s = 0; s < sCnt; s++)
                        {
                            int oldSid = Convert.ToInt32(sItemP.GetValue(starterList, new object[] { s }));
                            int idx = oldSkillIds.IndexOf(oldSid);
                            if (idx >= 0 && idx < newSkillIds.Count)
                                newStarters.Add(newSkillIds[idx]);
                        }
                        var clearM = starterList.GetType().GetMethod("Clear");
                        var addM   = starterList.GetType().GetMethod("Add");
                        if (clearM != null) clearM.Invoke(starterList, null);
                        if (addM != null)
                            foreach (int sid in newStarters)
                                addM.Invoke(starterList, new object[] { sid });
                    }
                }
            }
        }

        private static int GetDictCount(object dict)
        {
            try
            {
                var p = dict.GetType().GetProperty("Count");
                if (p != null) return Convert.ToInt32(p.GetValue(dict));
            }
            catch { }
            return 0;
        }

        private static void CollectIl2CppDictKeys(object dict, List<int> outKeys)
        {
            var t = dict.GetType();
            var getEnum = t.GetMethod("GetEnumerator");
            if (getEnum == null) return;
            var enumerator = getEnum.Invoke(dict, null);
            if (enumerator == null) return;
            var et = enumerator.GetType();
            var moveNext = et.GetMethod("MoveNext");
            var current = et.GetProperty("Current");
            if (moveNext == null || current == null) return;
            while ((bool)moveNext.Invoke(enumerator, null))
            {
                var pair = current.GetValue(enumerator);
                if (pair == null) continue;
                var keyP = pair.GetType().GetProperty("Key");
                if (keyP == null) continue;
                outKeys.Add(Convert.ToInt32(keyP.GetValue(pair)));
            }
        }

        private static void RemapDictKeysPreservingValues(object dict, List<int> oldKeys, List<int> newKeys, Type sptEnum, Type dictT, MethodInfo dictAdd)
        {
            // Capture (oldKey, value) pairs ordered by oldKeys so we can
            // map index-aligned to newKeys.
            var oldValues = new Dictionary<int, object>();
            var t = dict.GetType();
            var getEnum = t.GetMethod("GetEnumerator");
            if (getEnum != null)
            {
                var enumerator = getEnum.Invoke(dict, null);
                if (enumerator != null)
                {
                    var et = enumerator.GetType();
                    var moveNext = et.GetMethod("MoveNext");
                    var current = et.GetProperty("Current");
                    if (moveNext != null && current != null)
                    {
                        while ((bool)moveNext.Invoke(enumerator, null))
                        {
                            var pair = current.GetValue(enumerator);
                            if (pair == null) continue;
                            var keyP = pair.GetType().GetProperty("Key");
                            var valP = pair.GetType().GetProperty("Value");
                            if (keyP == null || valP == null) continue;
                            int k = Convert.ToInt32(keyP.GetValue(pair));
                            oldValues[k] = valP.GetValue(pair);
                        }
                    }
                }
            }
            // Pick a "Default" value from an existing entry to reuse
            // when we need to add a NEW key beyond what oldKeys had.
            // Reusing an existing IL2Cpp-boxed enum value avoids the
            // managed-vs-Il2Cpp type mismatch that managed Enum.ToObject
            // produces (the validator's check on enum values seems to
            // require values that came from Il2Cpp's own boxing).
            object reusableDefault = null;
            foreach (var ov in oldValues.Values)
            {
                if (ov != null && Convert.ToInt32(ov) == 0) { reusableDefault = ov; break; }
            }
            if (reusableDefault == null)
            {
                // No 0-valued entry to reuse — fall back to managed
                // Enum.ToObject. Caller may still see InvalidPrioritiesTypes
                // if validator rejects this boxing.
                reusableDefault = Enum.ToObject(sptEnum, 0);
            }

            // Clear and re-populate with new keys, value index-aligned
            var clearM = dict.GetType().GetMethod("Clear");
            if (clearM != null) clearM.Invoke(dict, null);
            for (int i = 0; i < newKeys.Count; i++)
            {
                int newKey = newKeys[i];
                object val = null;
                if (i < oldKeys.Count && oldValues.TryGetValue(oldKeys[i], out var ov))
                    val = ov;
                else
                    val = reusableDefault;
                try { dictAdd.Invoke(dict, new object[] { newKey, val }); } catch { }
            }
        }

        /// <summary>
        /// Walk an IL2CPP Dictionary<int, T> via GetEnumerator/MoveNext
        /// and emit `"key":int_value,...` JSON pairs. Il2Cpp's
        /// KeyCollection / ValueCollection don't implement managed
        /// System.Collections.IEnumerable, so the standard `foreach`
        /// throws an InvalidCastException.
        /// </summary>
        private static void DumpIl2CppIntDict(StringBuilder sb, object dict)
        {
            var t = dict.GetType();
            var getEnum = t.GetMethod("GetEnumerator");
            if (getEnum == null) return;
            var enumerator = getEnum.Invoke(dict, null);
            if (enumerator == null) return;
            var et = enumerator.GetType();
            var moveNext = et.GetMethod("MoveNext");
            var current = et.GetProperty("Current");
            if (moveNext == null || current == null) return;
            bool first = true;
            while ((bool)moveNext.Invoke(enumerator, null))
            {
                var pair = current.GetValue(enumerator);
                if (pair == null) continue;
                var pt = pair.GetType();
                var keyP = pt.GetProperty("Key");
                var valP = pt.GetProperty("Value");
                if (keyP == null || valP == null) continue;
                int kv = Convert.ToInt32(keyP.GetValue(pair));
                int vv = Convert.ToInt32(valP.GetValue(pair));
                if (!first) sb.Append(","); first = false;
                sb.Append("\"").Append(kv).Append("\":").Append(vv);
            }
        }

        /// <summary>
        /// Deep dump of a preset's priorities — for every setup, every
        /// sequence, every (skill_id, priority_type) pair. Used to
        /// discover what the server's SaveAiPresetCmd validator
        /// accepts. Mirroring this structure in /save-preset prevents
        /// the HeroesAiPreset_InvalidPrioritiesTypes rejection.
        /// </summary>
        private string PresetDeepDump(string idStr)
        {
            if (!int.TryParse(idStr ?? "", out int targetId))
                return "{\"error\":\"bad id\"}";
            try
            {
                var uw = GetUserWrapper();
                var heroes = Prop(uw, "Heroes");
                var heroData = Prop(heroes, "HeroData");
                object presetList = Prop(heroData, "HeroesAiPresets") ?? Prop(heroes, "HeroesAiPresets");
                if (presetList == null) return "{\"error\":\"no presets\"}";
                object target = null;
                foreach (var p in ListItems(presetList))
                    if (IntProp(p, "Id") == targetId) { target = p; break; }
                if (target == null) return "{\"error\":\"preset not found\"}";

                var sb = new StringBuilder();
                sb.Append("{\"id\":").Append(targetId);
                sb.Append(",\"name\":\"").Append(Esc(StrProp(target, "Name") ?? "")).Append("\"");
                int typeIv = 0;
                try { typeIv = Convert.ToInt32(Prop(target, "Type")); } catch { }
                sb.Append(",\"type\":").Append(typeIv);
                sb.Append(",\"setups\":[");
                bool firstSetup = true;
                var setups = Prop(target, "SkillPrioritiesSetups");
                if (setups != null)
                {
                    foreach (var setup in ListItems(setups))
                    {
                        if (!firstSetup) sb.Append(","); firstSetup = false;
                        int heroId = IntProp(setup, "HeroId");
                        sb.Append("{\"hero_id\":").Append(heroId);
                        // StarterSkillId (Nullable<int>)
                        try
                        {
                            var ss = Prop(setup, "StarterSkillId");
                            if (ss != null)
                            {
                                bool hv = false; int v = 0;
                                try { hv = (bool)ss.GetType().GetProperty("HasValue").GetValue(ss); } catch { }
                                if (hv)
                                {
                                    try { v = (int)ss.GetType().GetProperty("Value").GetValue(ss); } catch { }
                                    sb.Append(",\"starter\":").Append(v);
                                }
                                else { sb.Append(",\"starter\":null"); }
                            }
                        }
                        catch { }
                        // PriorityBySkillId (IL2CPP Dictionary<int, SkillPriorityType>).
                        // Il2Cpp KeyCollection doesn't implement managed
                        // IEnumerable — use the GetEnumerator() / MoveNext pair.
                        sb.Append(",\"pri\":{");
                        try
                        {
                            var dict = Prop(setup, "PriorityBySkillId");
                            if (dict != null)
                            {
                                DumpIl2CppIntDict(sb, dict);
                            }
                        }
                        catch (Exception ex) { sb.Append("\"_err\":\"").Append(Esc(ex.Message)).Append("\""); }
                        sb.Append("}");
                        // Sequences (each round's priorities)
                        sb.Append(",\"seqs\":[");
                        try
                        {
                            var seqs = Prop(setup, "Sequences");
                            if (seqs != null)
                            {
                                bool firstSeq = true;
                                foreach (var seq in ListItems(seqs))
                                {
                                    if (!firstSeq) sb.Append(","); firstSeq = false;
                                    sb.Append("{\"starters\":[");
                                    try
                                    {
                                        var ss = Prop(seq, "StarterSkillIds");
                                        if (ss != null)
                                        {
                                            // Iterate via Count + Item[index]
                                            var cntP = ss.GetType().GetProperty("Count");
                                            var itemP = ss.GetType().GetProperty("Item");
                                            int cnt = cntP != null ? Convert.ToInt32(cntP.GetValue(ss)) : 0;
                                            for (int i = 0; i < cnt; i++)
                                            {
                                                if (i > 0) sb.Append(",");
                                                var sv = itemP.GetValue(ss, new object[] { i });
                                                sb.Append(Convert.ToInt32(sv));
                                            }
                                        }
                                    }
                                    catch { }
                                    sb.Append("],\"pri\":{");
                                    try
                                    {
                                        var sd = Prop(seq, "PriorityBySkillId");
                                        if (sd != null) DumpIl2CppIntDict(sb, sd);
                                    }
                                    catch (Exception ex) { sb.Append("\"_err\":\"").Append(Esc(ex.Message)).Append("\""); }
                                    sb.Append("}}");
                                }
                            }
                        }
                        catch (Exception ex) { sb.Append("{\"_err\":\"").Append(Esc(ex.Message)).Append("\"}"); }
                        sb.Append("]}");
                    }
                }
                sb.Append("]}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        /// <summary>
        /// One-shot schema dump — lists every field + property on the first
        /// SkillPrioritiesSetup and Sequence inside the given preset, plus
        /// the current value for each (numeric/bool/string). Used to discover
        /// "Delay" or other unpublished fields Raid's in-game UI might expose.
        /// </summary>
        private string PresetSchema(string idStr)
        {
            if (!int.TryParse(idStr ?? "", out int targetId)) return "{\"error\":\"bad id\"}";
            try
            {
                var uw = GetUserWrapper();
                var heroes = Prop(uw, "Heroes");
                var heroData = Prop(heroes, "HeroData");
                object presetList = Prop(heroData, "HeroesAiPresets") ?? Prop(heroes, "HeroesAiPresets");
                if (presetList == null) return "{\"error\":\"no presets\"}";
                object target = null;
                foreach (var p in ListItems(presetList))
                {
                    if (IntProp(p, "Id") == targetId) { target = p; break; }
                }
                if (target == null) return "{\"error\":\"preset not found\"}";

                var sb = new StringBuilder();
                sb.Append("{\"preset_fields\":[");
                var pt = target.GetType();
                bool first = true;
                foreach (var f in pt.GetFields(BindingFlags.Public | BindingFlags.Instance))
                {
                    if (!first) sb.Append(","); first = false;
                    sb.Append("{\"name\":\"" + Esc(f.Name) + "\",\"type\":\"" + Esc(f.FieldType.Name) + "\"}");
                }
                foreach (var p in pt.GetProperties(BindingFlags.Public | BindingFlags.Instance))
                {
                    if (!first) sb.Append(","); first = false;
                    sb.Append("{\"name\":\"" + Esc(p.Name) + "\",\"type\":\"" + Esc(p.PropertyType.Name) + "\",\"is_prop\":true}");
                }
                sb.Append("]");

                // Dig into first setup + first sequence
                var setups = Prop(target, "SkillPrioritiesSetups");
                object firstSetup = null;
                if (setups != null)
                {
                    foreach (var s in ListItems(setups)) { firstSetup = s; break; }
                }
                if (firstSetup != null)
                {
                    sb.Append(",\"setup_fields\":[");
                    first = true;
                    var st = firstSetup.GetType();
                    foreach (var f in st.GetFields(BindingFlags.Public | BindingFlags.Instance))
                    {
                        if (!first) sb.Append(","); first = false;
                        sb.Append("{\"name\":\"" + Esc(f.Name) + "\",\"type\":\"" + Esc(f.FieldType.Name) + "\"}");
                    }
                    foreach (var p in st.GetProperties(BindingFlags.Public | BindingFlags.Instance))
                    {
                        if (!first) sb.Append(","); first = false;
                        sb.Append("{\"name\":\"" + Esc(p.Name) + "\",\"type\":\"" + Esc(p.PropertyType.Name) + "\",\"is_prop\":true}");
                    }
                    sb.Append("]");

                    var seqs = Prop(firstSetup, "Sequences");
                    object firstSeq = null;
                    if (seqs != null)
                    {
                        foreach (var s in ListItems(seqs)) { firstSeq = s; break; }
                    }
                    if (firstSeq != null)
                    {
                        sb.Append(",\"sequence_fields\":[");
                        first = true;
                        var qt = firstSeq.GetType();
                        foreach (var f in qt.GetFields(BindingFlags.Public | BindingFlags.Instance))
                        {
                            if (!first) sb.Append(","); first = false;
                            sb.Append("{\"name\":\"" + Esc(f.Name) + "\",\"type\":\"" + Esc(f.FieldType.Name) + "\"}");
                        }
                        foreach (var p in qt.GetProperties(BindingFlags.Public | BindingFlags.Instance))
                        {
                            if (!first) sb.Append(","); first = false;
                            sb.Append("{\"name\":\"" + Esc(p.Name) + "\",\"type\":\"" + Esc(p.PropertyType.Name) + "\",\"is_prop\":true}");
                        }
                        sb.Append("]");
                    }
                }
                sb.Append("}");
                return sb.ToString();
            }
            catch (Exception ex) { return "{\"error\":\"" + Esc(ex.Message) + "\"}"; }
        }

        /// Update an existing preset's skill priorities by cloning, modifying, and saving.
        /// This avoids IL2CPP type mismatch by reusing the game's own objects.
        /// priorities format: heroId:skillId=pri,skillId=pri;heroId:skillId=pri,...
        /// pri: 0=Default, 1=First, 2=Second, 3=Third, 4=NotUsed
        /// Example: /update-preset?id=1&priorities=15120:10703=3;18607:65102=2,65103=3;2643:62003=3
        /// </summary>
        private string UpdatePreset(string idStr, string prioritiesStr, string startersStr = null, string nameStr = null)
        {
            if (string.IsNullOrEmpty(idStr))
                return "{\"error\":\"id required\"}";
            int targetId;
            if (!int.TryParse(idStr, out targetId))
                return "{\"error\":\"invalid id\"}";

            // Reject names with characters the game's AssertIsValidName rejects.
            // (Same set client-side validates in tools/preset_manage.py.)
            if (!string.IsNullOrEmpty(nameStr) &&
                (nameStr.IndexOf('+') >= 0 || nameStr.IndexOf('&') >= 0 ||
                 nameStr.IndexOf('<') >= 0 || nameStr.IndexOf('>') >= 0))
                return "{\"error\":\"name contains rejected characters (+, &, <, >)\"}";

            // Sync length pre-check against live HeroSettings — avoids queueing
            // a SaveAiPresetCmd that fails AssertIsValidName async (which produces
            // an in-game popup we can't intercept).
            if (!string.IsNullOrEmpty(nameStr))
            {
                int minV, maxV;
                if (TryReadPresetNameLimits(out minV, out maxV) &&
                    (nameStr.Length < minV || nameStr.Length > maxV))
                {
                    return "{\"error\":\"name length " + nameStr.Length +
                           " outside [" + minV + "," + maxV + "]\"}";
                }
            }

            // starters format: heroId:skillId,skillId,skillId;heroId:skillId;...
            // Each hero's list becomes Sequence[0].StarterSkillIds (Round 1).
            // Pass an empty list (heroId:) to clear the opener.
            var starters = new Dictionary<int, List<int>>();
            if (!string.IsNullOrEmpty(startersStr))
            {
                foreach (var heroBlock in startersStr.Split(';'))
                {
                    var parts = heroBlock.Split(':');
                    if (parts.Length != 2) continue;
                    if (!int.TryParse(parts[0].Trim(), out int heroId)) continue;
                    var list = new List<int>();
                    foreach (var sk in parts[1].Split(','))
                    {
                        if (int.TryParse(sk.Trim(), out int sid)) list.Add(sid);
                    }
                    starters[heroId] = list;
                }
            }

            var presetT = FindType("SharedModel.Meta.Heroes.HeroesAiPreset");
            var sptEnum = FindType("SharedModel.Meta.Heroes.SkillPriorityType");
            if (presetT == null || sptEnum == null)
                return "{\"error\":\"types not found\"}";

            try
            {
                // Find the existing preset
                var uw = GetUserWrapper();
                var heroes = Prop(uw, "Heroes");
                var heroData = Prop(heroes, "HeroData");
                object presetList = Prop(heroData, "HeroesAiPresets");
                if (presetList == null) presetList = Prop(heroes, "HeroesAiPresets");
                if (presetList == null) return "{\"error\":\"no presets found\"}";

                object targetPreset = null;
                foreach (var p in ListItems(presetList))
                {
                    int pid = IntProp(p, "Id");
                    if (pid == targetId)
                    {
                        targetPreset = p;
                        break;
                    }
                }
                if (targetPreset == null)
                    return "{\"error\":\"preset " + targetId + " not found\"}";

                // Clone the preset — this preserves all IL2CPP native memory
                var cloneMethod = presetT.GetMethod("Clone", BindingFlags.Public | BindingFlags.Instance);
                object cloned;
                if (cloneMethod != null)
                    cloned = cloneMethod.Invoke(targetPreset, null);
                else
                    return "{\"error\":\"Clone method not found\"}";

                // Parse and apply priority changes
                // Format: heroId:skillId=pri,skillId=pri;heroId:skillId=pri,...
                var changes = new Dictionary<int, Dictionary<int, int>>();
                if (!string.IsNullOrEmpty(prioritiesStr))
                {
                    foreach (var heroBlock in prioritiesStr.Split(';'))
                    {
                        var parts = heroBlock.Split(':');
                        if (parts.Length != 2) continue;
                        int heroId;
                        if (!int.TryParse(parts[0].Trim(), out heroId)) continue;
                        var skillChanges = new Dictionary<int, int>();
                        foreach (var pair in parts[1].Split(','))
                        {
                            var kv = pair.Split('=');
                            if (kv.Length != 2) continue;
                            int skillId, pri;
                            if (int.TryParse(kv[0].Trim(), out skillId) && int.TryParse(kv[1].Trim(), out pri))
                                skillChanges[skillId] = pri;
                        }
                        changes[heroId] = skillChanges;
                    }
                }

                // Get the SkillPrioritiesSetups from cloned preset
                var setupsField = presetT.GetField("SkillPrioritiesSetups", BindingFlags.Public | BindingFlags.Instance);
                object clonedSetups = null;
                if (setupsField != null)
                    clonedSetups = setupsField.GetValue(cloned);
                if (clonedSetups == null)
                {
                    var getSetups = presetT.GetMethod("get_SkillPrioritiesSetups");
                    if (getSetups != null) clonedSetups = getSetups.Invoke(cloned, null);
                }
                if (clonedSetups == null)
                    return "{\"error\":\"cloned SkillPrioritiesSetups is null\"}";

                var sb = new StringBuilder();
                sb.Append("{\"ok\":true,\"changes\":[");
                bool first = true;

                foreach (var setup in ListItems(clonedSetups))
                {
                    int heroId = IntProp(setup, "HeroId");
                    if (!changes.ContainsKey(heroId)) continue;
                    var heroChanges = changes[heroId];

                    // Update PriorityBySkillId on the setup itself
                    var priField = setup.GetType().GetField("PriorityBySkillId", BindingFlags.Public | BindingFlags.Instance);
                    object priDict = priField != null ? priField.GetValue(setup) : null;
                    if (priDict == null)
                    {
                        var getPri = setup.GetType().GetMethod("get_PriorityBySkillId");
                        if (getPri != null) priDict = getPri.Invoke(setup, null);
                    }

                    if (priDict != null)
                    {
                        // Use indexer to set values: dict[key] = value
                        var indexer = priDict.GetType().GetProperty("Item");
                        foreach (var kv in heroChanges)
                        {
                            try
                            {
                                indexer?.SetValue(priDict, Enum.ToObject(sptEnum, kv.Value), new object[] { kv.Key });
                            }
                            catch (Exception ex)
                            {
                                Logger.LogWarning("PRESET: Failed to set priority " + kv.Key + "=" + kv.Value + " on hero " + heroId + ": " + ex.Message);
                            }
                        }
                    }

                    // Also update priorities in each Sequence (round-specific)
                    var seqField = setup.GetType().GetField("Sequences", BindingFlags.Public | BindingFlags.Instance);
                    object seqs = seqField != null ? seqField.GetValue(setup) : null;
                    if (seqs == null)
                    {
                        var getSeqs = setup.GetType().GetMethod("get_Sequences");
                        if (getSeqs != null) seqs = getSeqs.Invoke(setup, null);
                    }
                    if (seqs != null)
                    {
                        foreach (var seq in ListItems(seqs))
                        {
                            var seqPriField = seq.GetType().GetField("PriorityBySkillId", BindingFlags.Public | BindingFlags.Instance);
                            object seqDict = seqPriField != null ? seqPriField.GetValue(seq) : null;
                            if (seqDict == null)
                            {
                                var getSeqPri = seq.GetType().GetMethod("get_PriorityBySkillId");
                                if (getSeqPri != null) seqDict = getSeqPri.Invoke(seq, null);
                            }
                            if (seqDict != null)
                            {
                                var seqIdx = seqDict.GetType().GetProperty("Item");
                                foreach (var kv in heroChanges)
                                {
                                    try { seqIdx?.SetValue(seqDict, Enum.ToObject(sptEnum, kv.Value), new object[] { kv.Key }); }
                                    catch { }
                                }
                            }
                        }
                    }

                    if (!first) sb.Append(",");
                    first = false;
                    sb.Append("{\"hero\":" + heroId + ",\"skills\":" + heroChanges.Count + "}");
                }

                // Instead of SaveAiPresetCmd (which doesn't persist), modify the
                // ORIGINAL preset's dictionaries directly in memory.
                // This works because we're changing values in existing IL2CPP dicts,
                // not creating new objects.
                var origSetups = Prop(targetPreset, "SkillPrioritiesSetups");
                if (origSetups == null)
                {
                    var origField = presetT.GetField("SkillPrioritiesSetups", BindingFlags.Public | BindingFlags.Instance);
                    if (origField != null) origSetups = origField.GetValue(targetPreset);
                }
                if (origSetups == null) return "{\"error\":\"original SkillPrioritiesSetups is null\"}";

                // Apply changes to the ORIGINAL preset in memory
                var dbg = new StringBuilder();
                dbg.Append(",\"debug_setups\":[");
                bool dbgFirst = true;
                int applied = 0;
                int startersApplied = 0;
                foreach (var setup in ListItems(origSetups))
                {
                    int heroId = IntProp(setup, "HeroId");
                    bool needsPri = changes.ContainsKey(heroId);
                    bool needsStarter = starters.ContainsKey(heroId);
                    if (!dbgFirst) dbg.Append(",");
                    dbgFirst = false;
                    dbg.Append("{\"hid\":" + heroId + ",\"pri\":" + (needsPri ? "true" : "false") + ",\"starters\":" + (needsStarter ? "true" : "false") + "}");

                    // Apply StarterSkillIds to each Sequence (Round 1 is [0]).
                    // We only touch Round 1's opener by convention; other rounds
                    // keep their existing starters unless explicitly addressed.
                    if (needsStarter)
                    {
                        try
                        {
                            var seqsForStarter = Prop(setup, "Sequences");
                            if (seqsForStarter == null)
                            {
                                var sf = setup.GetType().GetField("Sequences", BindingFlags.Public | BindingFlags.Instance);
                                if (sf != null) seqsForStarter = sf.GetValue(setup);
                            }
                            if (seqsForStarter != null)
                            {
                                int rIdx = 0;
                                foreach (var seq in ListItems(seqsForStarter))
                                {
                                    if (rIdx != 0) { rIdx++; continue; }  // Round 1 only
                                    rIdx++;
                                    var listField = seq.GetType().GetField("StarterSkillIds", BindingFlags.Public | BindingFlags.Instance);
                                    object listObj = null;
                                    if (listField != null) listObj = listField.GetValue(seq);
                                    if (listObj == null)
                                    {
                                        var getList = seq.GetType().GetMethod("get_StarterSkillIds");
                                        if (getList != null) listObj = getList.Invoke(seq, null);
                                    }
                                    if (listObj != null)
                                    {
                                        // Clear + add each new starter via List.Clear() and List.Add(int).
                                        var t = listObj.GetType();
                                        t.GetMethod("Clear")?.Invoke(listObj, null);
                                        var add = t.GetMethod("Add");
                                        foreach (var sid in starters[heroId])
                                            add?.Invoke(listObj, new object[] { sid });
                                        startersApplied++;
                                    }
                                }
                            }
                        }
                        catch (Exception ex) { Logger.LogWarning("PRESET starters: " + ex.Message); }
                    }

                    if (!needsPri) continue;
                    applied++;
                    var heroChanges = changes[heroId];

                    // Update top-level PriorityBySkillId
                    object priDict = null;
                    var priField = setup.GetType().GetField("PriorityBySkillId", BindingFlags.Public | BindingFlags.Instance);
                    if (priField != null) priDict = priField.GetValue(setup);
                    if (priDict == null) { var g = setup.GetType().GetMethod("get_PriorityBySkillId"); if (g != null) priDict = g.Invoke(setup, null); }

                    if (priDict != null)
                    {
                        var indexer = priDict.GetType().GetProperty("Item");
                        foreach (var kv in heroChanges)
                        {
                            try { indexer?.SetValue(priDict, Enum.ToObject(sptEnum, kv.Value), new object[] { kv.Key }); }
                            catch (Exception ex) { Logger.LogWarning("PRESET set pri: " + ex.Message); }
                        }
                    }

                    // Update each Sequence's PriorityBySkillId
                    object seqs = null;
                    var seqField = setup.GetType().GetField("Sequences", BindingFlags.Public | BindingFlags.Instance);
                    if (seqField != null) seqs = seqField.GetValue(setup);
                    if (seqs == null) { var g = setup.GetType().GetMethod("get_Sequences"); if (g != null) seqs = g.Invoke(setup, null); }
                    if (seqs != null)
                    {
                        foreach (var seq in ListItems(seqs))
                        {
                            object seqDict = null;
                            var sf = seq.GetType().GetField("PriorityBySkillId", BindingFlags.Public | BindingFlags.Instance);
                            if (sf != null) seqDict = sf.GetValue(seq);
                            if (seqDict == null) { var g = seq.GetType().GetMethod("get_PriorityBySkillId"); if (g != null) seqDict = g.Invoke(seq, null); }
                            if (seqDict != null)
                            {
                                var idx = seqDict.GetType().GetProperty("Item");
                                foreach (var kv in heroChanges)
                                {
                                    try { idx?.SetValue(seqDict, Enum.ToObject(sptEnum, kv.Value), new object[] { kv.Key }); }
                                    catch { }
                                }
                            }
                        }
                    }
                }

                dbg.Append("]");

                // Optional rename: set Name on the original preset before saving.
                bool nameApplied = false;
                if (!string.IsNullOrEmpty(nameStr))
                {
                    try { SetFieldOrProp(presetT, targetPreset, "Name", nameStr); nameApplied = true; }
                    catch (Exception ex) { Logger.LogWarning("PRESET set name: " + ex.Message); }
                }

                // Now save the ORIGINAL (modified) preset via SaveAiPresetCmd
                var cmdType = FindType("Client.Model.Gameplay.Heroes.Commands.SaveAiPresetCmd");
                if (cmdType == null) return "{\"error\":\"SaveAiPresetCmd not found\"}";
                var ctor = cmdType.GetConstructor(new[] { presetT });
                if (ctor == null) return "{\"error\":\"SaveAiPresetCmd ctor not found\"}";

                var cmd = ctor.Invoke(new object[] { targetPreset });
                InvokeExecute(cmd);

                sb.Append("]");
                sb.Append(",\"applied\":" + applied);
                sb.Append(",\"starters_applied\":" + startersApplied);
                sb.Append(",\"name_applied\":" + (nameApplied ? "true" : "false"));
                sb.Append(dbg.ToString());
                sb.Append("}");
                return sb.ToString();
            }
            catch (TargetInvocationException tex)
            {
                return "{\"error\":\"" + Esc((tex.InnerException ?? tex).Message) + "\"}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\",\"stack\":\"" + Esc(ex.StackTrace) + "\"}";
            }
        }

        /// <summary>
        /// Set a public field or property on an IL2CPP object.
        /// IL2CPP interop types have PUBLIC FIELDS (from the original C# class),
        /// not C# properties. The old code called set_X() which doesn't exist.
        /// </summary>
        private static void SetFieldOrProp(Type type, object obj, string name, object value)
        {
            // Try field first (IL2CPP types use public fields)
            var field = type.GetField(name, BindingFlags.Public | BindingFlags.Instance);
            if (field != null)
            {
                field.SetValue(obj, value);
                return;
            }
            // Try property setter
            var setter = type.GetMethod("set_" + name, BindingFlags.Public | BindingFlags.Instance);
            if (setter != null)
            {
                setter.Invoke(obj, new[] { value });
                return;
            }
            // Try property directly
            var prop = type.GetProperty(name, BindingFlags.Public | BindingFlags.Instance);
            if (prop != null && prop.CanWrite)
            {
                prop.SetValue(obj, value);
            }
        }

        /// <summary>
        /// Resolve HeroSettings.HeroesAiPresetNameMin/MaxCharsCount via the same
        /// reflection chain GetPresetNameLimits() uses (field → property → getter).
        /// Returns true on success.
        /// </summary>
        private bool TryReadPresetNameLimits(out int minV, out int maxV)
        {
            minV = -1; maxV = -1;
            try
            {
                var smT = FindType("SharedModel.SharedModelManager");
                if (smT == null) return false;
                var allFlags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static;
                object gp = null;
                var gpField = smT.GetField("GameParameters", allFlags);
                if (gpField != null) gp = gpField.GetValue(null);
                if (gp == null) { var p = smT.GetProperty("GameParameters", allFlags); if (p != null) gp = p.GetValue(null); }
                if (gp == null) { var m = smT.GetMethod("get_GameParameters", allFlags); if (m != null) gp = m.Invoke(null, null); }
                if (gp == null) return false;

                object hs = null;
                var hsF = gp.GetType().GetField("HeroSettings", BindingFlags.Public | BindingFlags.Instance);
                if (hsF != null) hs = hsF.GetValue(gp);
                if (hs == null) { var p = gp.GetType().GetProperty("HeroSettings", BindingFlags.Public | BindingFlags.Instance); if (p != null) hs = p.GetValue(gp); }
                if (hs == null) return false;

                int Read(string n)
                {
                    var f = hs.GetType().GetField(n, BindingFlags.Public | BindingFlags.Instance);
                    if (f != null) return (int)f.GetValue(hs);
                    var p = hs.GetType().GetProperty(n, BindingFlags.Public | BindingFlags.Instance);
                    if (p != null) return (int)p.GetValue(hs);
                    return -1;
                }
                minV = Read("HeroesAiPresetNameMinCharsCount");
                maxV = Read("HeroesAiPresetNameMaxCharsCount");
                return minV >= 0 && maxV >= 0;
            }
            catch { return false; }
        }

        /// <summary>
        /// Read SharedModelManager.GameParameters.HeroSettings.HeroesAiPresetNameMin/MaxCharsCount.
        /// Surfaces the actual length bounds the game's AssertIsValidName checks against,
        /// so we can pre-validate before queueing a SaveAiPresetCmd that would popup-error.
        /// </summary>
        private string GetPresetNameLimits()
        {
            try
            {
                var smT = FindType("SharedModel.SharedModelManager");
                if (smT == null) return "{\"error\":\"SharedModelManager type not found\"}";

                // IL2CPP often wraps static fields as property getters. Try field, then property.
                object gp = null;
                var allFlags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static;
                var gpField = smT.GetField("GameParameters", allFlags);
                if (gpField != null) gp = gpField.GetValue(null);
                if (gp == null)
                {
                    var gpProp = smT.GetProperty("GameParameters", allFlags);
                    if (gpProp != null) gp = gpProp.GetValue(null);
                }
                if (gp == null)
                {
                    var gpGet = smT.GetMethod("get_GameParameters", allFlags);
                    if (gpGet != null) gp = gpGet.Invoke(null, null);
                }
                if (gp == null)
                {
                    // Diagnostic dump of available members so we can see the actual API shape.
                    var diag = new StringBuilder();
                    diag.Append("{\"error\":\"GameParameters not accessible\",\"members\":[");
                    bool first = true;
                    foreach (var f in smT.GetFields(allFlags))
                    {
                        if (!first) diag.Append(",");
                        first = false;
                        diag.Append("\"f:" + f.Name + "\"");
                    }
                    foreach (var p in smT.GetProperties(allFlags))
                    {
                        if (!first) diag.Append(",");
                        first = false;
                        diag.Append("\"p:" + p.Name + "\"");
                    }
                    foreach (var m in smT.GetMethods(allFlags))
                    {
                        if (m.Name.StartsWith("get_"))
                        {
                            if (!first) diag.Append(",");
                            first = false;
                            diag.Append("\"m:" + m.Name + "\"");
                        }
                    }
                    diag.Append("]}");
                    return diag.ToString();
                }

                var hsField = gp.GetType().GetField("HeroSettings", BindingFlags.Public | BindingFlags.Instance);
                var hs = hsField != null ? hsField.GetValue(gp) : null;
                if (hs == null)
                {
                    var hsProp = gp.GetType().GetProperty("HeroSettings", BindingFlags.Public | BindingFlags.Instance);
                    if (hsProp != null) hs = hsProp.GetValue(gp);
                }
                if (hs == null) return "{\"error\":\"HeroSettings not found on GameParameters\"}";
                var hsT = hs.GetType();
                int minV = -1, maxV = -1;
                var minF = hsT.GetField("HeroesAiPresetNameMinCharsCount", BindingFlags.Public | BindingFlags.Instance);
                if (minF != null) minV = (int)minF.GetValue(hs);
                else
                {
                    var p = hsT.GetProperty("HeroesAiPresetNameMinCharsCount", BindingFlags.Public | BindingFlags.Instance);
                    if (p != null) minV = (int)p.GetValue(hs);
                }
                var maxF = hsT.GetField("HeroesAiPresetNameMaxCharsCount", BindingFlags.Public | BindingFlags.Instance);
                if (maxF != null) maxV = (int)maxF.GetValue(hs);
                else
                {
                    var p = hsT.GetProperty("HeroesAiPresetNameMaxCharsCount", BindingFlags.Public | BindingFlags.Instance);
                    if (p != null) maxV = (int)p.GetValue(hs);
                }
                if (minV >= 0 && maxV >= 0)
                    return "{\"min\":" + minV + ",\"max\":" + maxV + "}";

                // Diagnostic: enumerate HeroSettings members so we can see real API shape.
                var diag2 = new StringBuilder();
                diag2.Append("{\"min\":" + minV + ",\"max\":" + maxV + ",\"hs_type\":\"" + Esc(hsT.FullName) + "\",\"members\":[");
                bool df = true;
                foreach (var f in hsT.GetFields(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance))
                {
                    if (!df) diag2.Append(","); df = false;
                    diag2.Append("\"f:" + f.Name + ":" + f.FieldType.Name + "\"");
                }
                foreach (var p in hsT.GetProperties(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance))
                {
                    if (!df) diag2.Append(","); df = false;
                    diag2.Append("\"p:" + p.Name + ":" + p.PropertyType.Name + "\"");
                }
                diag2.Append("]}");
                return diag2.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        /// <summary>
        /// Get the IL2CPP Dictionary type for the given key/value types.
        /// Tries Il2CppSystem first (proper IL2CPP collections), falls back to System.
        /// </summary>
        private Type GetIl2CppDictType(Type keyT, Type valT)
        {
            // Try Il2CppSystem.Collections.Generic.Dictionary`2
            var il2DictT = FindType("Il2CppSystem.Collections.Generic.Dictionary`2");
            if (il2DictT != null)
            {
                try { return il2DictT.MakeGenericType(keyT, valT); } catch {}
            }
            // Try System.Collections.Generic.Dictionary`2 (in IL2CPP interop, these may be remapped)
            try { return typeof(Dictionary<,>).MakeGenericType(keyT, valT); } catch {}
            return null;
        }

        // =====================================================
        // API: /apply-preset?id=N — activate preset N on the current
        // hero-selection dialog.
        //
        // Replicates the in-game checkbox-click flow: the overlay's
        // checkbox handler (BattlePresetItemContext.ChangePresetActivity)
        // ultimately calls back into the parent dialog via
        // HeroesSelectionDialogContext.SelectPresetsForBattle(int[]),
        // which writes SelectedPresets[] and calls the dialog's
        // (overridden) UpdateAiPreset() + UpdateSlots() to auto-populate
        // the squad. Hitting SelectPresetsForBattle directly skips the
        // overlay UI but uses the same downstream preset machinery —
        // so the squad fill goes through the game's preset path, not
        // a direct HeroesSquadContext.AddHero / SetHero.
        //
        // Implementation note: standard managed reflection cannot see
        // IL2CPP-defined Context properties / methods on proxy types, so
        // we use raw il2cpp_* APIs (same pattern as SearchContextAndInvoke
        // in RaidAutomationPlugin.Navigate.cs).
        // =====================================================
        private string ApplyPreset(string idStr)
        {
            if (string.IsNullOrEmpty(idStr) || !int.TryParse(idStr, out int presetId))
                return "{\"error\":\"id (int) required\"}";

            try
            {
                // 1. Verify the preset id exists & isn't empty (early bail).
                var uw = GetUserWrapper();
                if (uw == null) return "{\"error\":\"Not logged in\"}";
                object presetList = Prop(Prop(Prop(uw, "Heroes"), "HeroData"), "HeroesAiPresets")
                                    ?? Prop(Prop(uw, "Heroes"), "HeroesAiPresets");
                bool found = false; bool isEmpty = true; string presetName = "";
                if (presetList != null)
                {
                    foreach (var p in ListItems(presetList))
                    {
                        if (IntProp(p, "Id") != presetId) continue;
                        found = true;
                        presetName = StrProp(p, "Name");
                        try { isEmpty = (bool)Prop(p, "IsEmpty"); } catch { }
                        break;
                    }
                }
                if (!found) return "{\"error\":\"preset id " + presetId + " not found\"}";
                if (isEmpty) return "{\"error\":\"preset id " + presetId + " is empty (no heroes)\"}";

                // 2. Find the active hero-selection dialog by walking the dialog
                //    GameObject tree via raw IL2Cpp pointers. We're looking for a
                //    MonoBehaviour whose get_Context() returns an instance whose
                //    type-hierarchy includes "HeroesSelectionDialogContext`1".
                var dialogsRoot = GameObject.Find("UIManager/Canvas (Ui Root)/Dialogs");
                if (dialogsRoot == null) return "{\"error\":\"no Dialogs root in scene\"}";

                IntPtr ctxObj = IntPtr.Zero;
                IntPtr ctxClass = IntPtr.Zero;
                string dialogName = null;
                string ctxClassName = null;
                string ctxNs = null;

                for (int di = 0; di < dialogsRoot.transform.childCount && ctxObj == IntPtr.Zero; di++)
                {
                    var dialog = dialogsRoot.transform.GetChild(di);
                    if (!dialog.gameObject.activeSelf) continue;
                    if (TryFindHeroesSelectionContext(dialog, out ctxObj, out ctxClass, out ctxClassName, out ctxNs))
                        dialogName = dialog.gameObject.name;
                }

                if (ctxObj == IntPtr.Zero)
                    return "{\"error\":\"no active HeroesSelectionDialog (open Battle Setup first)\"}";

                // 3. Locate SelectPresetsForBattle(int[]) on the context class
                //    (walk the IL2Cpp parent chain — defined on generic base).
                IntPtr spfbMethod = IntPtr.Zero;
                IntPtr ck = ctxClass;
                while (ck != IntPtr.Zero && spfbMethod == IntPtr.Zero)
                {
                    IntPtr mIter = IntPtr.Zero;
                    IntPtr m;
                    while ((m = il2cpp_class_get_methods(ck, ref mIter)) != IntPtr.Zero)
                    {
                        string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                        if (mn == "SelectPresetsForBattle" && il2cpp_method_get_param_count(m) == 1)
                        {
                            spfbMethod = m;
                            break;
                        }
                    }
                    ck = il2cpp_class_get_parent(ck);
                    string pn = ck != IntPtr.Zero ? Marshal.PtrToStringAnsi(il2cpp_class_get_name(ck)) : "";
                    if (pn == "Object" || pn == "Il2CppObjectBase") break;
                }
                if (spfbMethod == IntPtr.Zero)
                    return "{\"error\":\"SelectPresetsForBattle not found on " + Esc(ctxClassName) + "\"}";

                // 4. Allocate Il2Cpp int[1] = { presetId } and invoke.
                //    Il2CppInterop's Il2CppStructArray<int>(int[]) builds a
                //    GC-rooted IL2CPP array from a managed source.
                var presetIdArr = new Il2CppInterop.Runtime.InteropTypes.Arrays.Il2CppStructArray<int>(
                    new int[] { presetId });
                IntPtr arrPtr = presetIdArr.Pointer;

                // Reference-type arg: il2cpp_runtime_invoke wants params to be
                // an array of pointers; for object args, each element holds the
                // object pointer directly.
                IntPtr[] argv = new IntPtr[] { arrPtr };
                System.Runtime.InteropServices.GCHandle h =
                    System.Runtime.InteropServices.GCHandle.Alloc(argv,
                        System.Runtime.InteropServices.GCHandleType.Pinned);
                IntPtr exc = IntPtr.Zero;
                try
                {
                    IntPtr argsAddr = System.Runtime.InteropServices.Marshal.UnsafeAddrOfPinnedArrayElement(argv, 0);
                    il2cpp_runtime_invoke(spfbMethod, ctxObj, argsAddr, ref exc);
                }
                finally { h.Free(); }

                if (exc != IntPtr.Zero)
                    return "{\"error\":\"SelectPresetsForBattle threw\",\"context\":\"" + Esc(ctxClassName) + "\"}";

                return "{\"ok\":true,\"preset_id\":" + presetId +
                       ",\"preset_name\":\"" + Esc(presetName) + "\"" +
                       ",\"dialog\":\"" + Esc(dialogName) + "\"" +
                       ",\"context\":\"" + Esc((ctxNs ?? "") + "." + (ctxClassName ?? "")) + "\"}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // =====================================================
        // API: /set-dungeon-difficulty?hard=N — switch the open
        // DungeonsDialog between Normal (0) and Hard (1).
        //
        // Mechanism: locate the difficulty Dropdown UI component
        // (UnityEngine.UI.Dropdown subclass), call set_value(N) via
        // raw IL2Cpp. Unity fires onValueChanged, which the dialog's
        // viewmodel binding routes into OnDifficultyChanged() — same
        // path as a UI dropdown click.
        // =====================================================
        private string SetDungeonDifficulty(string hardStr)
        {
            int hard = (hardStr == "1" || hardStr.ToLowerInvariant() == "true") ? 1 : 0;
            string dropPath = "UIManager/Canvas (Ui Root)/Dialogs/[DV] DungeonsDialog/Workspace/Content/RegionInfoView/DropdownPlace_h/Dropdown";
            try
            {
                var go = GameObject.Find(dropPath);
                if (go == null) return "{\"error\":\"DungeonsDialog dropdown not found (open Dragon/Spider/etc dungeon first)\"}";

                // Find the UnityEngine.UI.Dropdown component. Il2CppInterop's
                // managed wrapper Type names don't always carry the IL2Cpp
                // class name, so match via raw IL2Cpp class name instead.
                IntPtr dropPtr = IntPtr.Zero;
                IntPtr dropClass = IntPtr.Zero;
                foreach (var comp in go.GetComponents<MonoBehaviour>())
                {
                    if (comp == null) continue;
                    IntPtr ptr = comp.Pointer;
                    if (ptr == IntPtr.Zero) continue;
                    IntPtr cls = il2cpp_object_get_class(ptr);
                    // Walk the class chain and check each ancestor for "Dropdown"
                    IntPtr scan = cls;
                    bool isDropdown = false;
                    while (scan != IntPtr.Zero)
                    {
                        string sn = Marshal.PtrToStringAnsi(il2cpp_class_get_name(scan));
                        if (sn != null && sn.Contains("Dropdown")) { isDropdown = true; break; }
                        if (sn == "Object" || sn == "MonoBehaviour" || sn == "Behaviour") break;
                        scan = il2cpp_class_get_parent(scan);
                    }
                    if (isDropdown)
                    {
                        dropPtr = ptr;
                        dropClass = cls;
                        break;
                    }
                }
                if (dropPtr == IntPtr.Zero) return "{\"error\":\"no Dropdown component on " + Esc(dropPath) + "\"}";

                // Walk the class chain looking for set_value(int).
                IntPtr setValueMethod = IntPtr.Zero;
                IntPtr klass = dropClass;
                while (klass != IntPtr.Zero && setValueMethod == IntPtr.Zero)
                {
                    IntPtr mIter = IntPtr.Zero;
                    IntPtr m;
                    while ((m = il2cpp_class_get_methods(klass, ref mIter)) != IntPtr.Zero)
                    {
                        string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                        if (mn == "set_value" && il2cpp_method_get_param_count(m) == 1)
                        {
                            setValueMethod = m;
                            break;
                        }
                    }
                    klass = il2cpp_class_get_parent(klass);
                }
                if (setValueMethod == IntPtr.Zero) return "{\"error\":\"set_value not found on Dropdown class chain\"}";

                // Value-type arg: each argv element points to the value buffer.
                int v = hard;
                System.Runtime.InteropServices.GCHandle h =
                    System.Runtime.InteropServices.GCHandle.Alloc(new int[] { v },
                        System.Runtime.InteropServices.GCHandleType.Pinned);
                IntPtr exc = IntPtr.Zero;
                try
                {
                    IntPtr valAddr = System.Runtime.InteropServices.Marshal.UnsafeAddrOfPinnedArrayElement((int[])h.Target, 0);
                    IntPtr[] argv = new IntPtr[] { valAddr };
                    System.Runtime.InteropServices.GCHandle h2 =
                        System.Runtime.InteropServices.GCHandle.Alloc(argv,
                            System.Runtime.InteropServices.GCHandleType.Pinned);
                    try
                    {
                        IntPtr argsAddr = System.Runtime.InteropServices.Marshal.UnsafeAddrOfPinnedArrayElement(argv, 0);
                        il2cpp_runtime_invoke(setValueMethod, dropPtr, argsAddr, ref exc);
                    }
                    finally { h2.Free(); }
                }
                finally { h.Free(); }

                if (exc != IntPtr.Zero)
                    return "{\"error\":\"set_value threw\"}";

                return "{\"ok\":true,\"hard\":" + (hard == 1 ? "true" : "false") + "}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // =====================================================
        // API: /rank-up?hero_id=X&food=A,B,C[,...] — rank up a champion
        // by sacrificing food champions.
        //
        // Mechanic: MultiRankUpHeroesCmd (NOT the single RankUpHeroCmd —
        // that one is a UserPreEditCmdNoOut, a deprecated client-side
        // pre-edit validator that returns ok but never reaches the
        // server. Same pattern as SellArtifactsCmd vs
        // SellArtifactsWithEquippedCmd — see memory).
        //
        // MultiRankUpHeroesCmd : UserPostEditCmdNoOut<MultiRankUpHeroRequestDto>
        //   RankUpItems: List<RankUpHeroRequestDto> (at least 1 item)
        //   DeactivateMaterialsHeroArtifacts: bool (strip gear off fodder)
        //   VaultFilterUsed: Nullable<bool>
        // RankUpHeroRequestDto:
        //   HeroId             target
        //   MaterialHeroIds[]  food hero instance ids
        //   BmiTypeIds[]       black-market substitutes (chickens etc.)
        // =====================================================
        private string RankUpHero(string heroIdStr, string foodCsv)
        {
            if (string.IsNullOrEmpty(heroIdStr) || !int.TryParse(heroIdStr, out int heroId))
                return "{\"error\":\"hero_id (int) required\"}";
            if (string.IsNullOrEmpty(foodCsv))
                return "{\"error\":\"food (comma-separated hero ids) required\"}";

            var foodIds = new List<int>();
            foreach (var part in foodCsv.Split(','))
            {
                var p = part.Trim();
                if (string.IsNullOrEmpty(p)) continue;
                if (!int.TryParse(p, out int fid))
                    return "{\"error\":\"food list must be int csv, got: " + Esc(p) + "\"}";
                foodIds.Add(fid);
            }
            if (foodIds.Count == 0)
                return "{\"error\":\"at least 1 food hero required\"}";

            var itemDtoType = FindType("SharedModel.Meta.Heroes.Dtos.RankUpHeroRequestDto");
            var multiDtoType = FindType("SharedModel.Meta.Heroes.Dtos.MultiRankUpHeroRequestDto");
            var cmdType = FindType("Client.Model.Gameplay.Heroes.Commands.MultiRankUpHeroesCmd");
            if (itemDtoType == null) return "{\"error\":\"RankUpHeroRequestDto type not found\"}";
            if (multiDtoType == null) return "{\"error\":\"MultiRankUpHeroRequestDto type not found\"}";
            if (cmdType == null) return "{\"error\":\"MultiRankUpHeroesCmd type not found\"}";

            try
            {
                // NOTE: IL2Cpp interop exposes public fields as PROPERTIES on the
                // C# side (the interop layer wraps them so memory access goes
                // through the proper IL2Cpp marshaller). GetField() succeeds via
                // reflection but SetValue silently no-ops on IL2Cpp objects —
                // verified empirically (multiDto.RankUpItems stayed NULL after
                // SetValue). Use GetProperty + SetValue instead, same pattern as
                // SellArtifactsWithEquippedCmd in Mutations.cs.

                // 1) Build the per-item RankUpHeroRequestDto
                var itemDto = Activator.CreateInstance(itemDtoType);
                var heroIdP = itemDtoType.GetProperty("HeroId");
                if (heroIdP != null) heroIdP.SetValue(itemDto, heroId);

                var matP = itemDtoType.GetProperty("MaterialHeroIds");
                if (matP != null)
                {
                    var arr = new Il2CppInterop.Runtime.InteropTypes.Arrays.Il2CppStructArray<int>(foodIds.ToArray());
                    matP.SetValue(itemDto, arr);
                }

                var bmiP = itemDtoType.GetProperty("BmiTypeIds");
                if (bmiP != null)
                {
                    var arrType = bmiP.PropertyType;
                    var emptyArr = Activator.CreateInstance(arrType, new object[] { 0 });
                    bmiP.SetValue(itemDto, emptyArr);
                }

                // 2) Build the MultiRankUpHeroRequestDto wrapping a List of one
                var multiDto = Activator.CreateInstance(multiDtoType);
                var itemsP = multiDtoType.GetProperty("RankUpItems");
                if (itemsP == null)
                    return "{\"error\":\"RankUpItems property not found on MultiRankUpHeroRequestDto\"}";
                {
                    var listType = itemsP.PropertyType;
                    var list = Activator.CreateInstance(listType);
                    MethodInfo addM = null;
                    foreach (var m in listType.GetMethods(BindingFlags.Public | BindingFlags.Instance))
                    {
                        if (m.Name == "Add" && m.GetParameters().Length == 1) { addM = m; break; }
                    }
                    if (addM == null) return "{\"error\":\"List.Add not found on RankUpItems type\"}";
                    addM.Invoke(list, new object[] { itemDto });
                    itemsP.SetValue(multiDto, list);
                }
                var deactP = multiDtoType.GetProperty("DeactivateMaterialsHeroArtifacts");
                if (deactP != null) deactP.SetValue(multiDto, true);  // strip gear off fodder before sacrifice

                // VaultFilterUsed is Nullable<bool>; leaving null is fine

                // 3) Construct + execute MultiRankUpHeroesCmd
                var ctor = cmdType.GetConstructor(new[] { multiDtoType });
                if (ctor == null) return "{\"error\":\"MultiRankUpHeroesCmd(MultiRankUpHeroRequestDto) ctor not found\"}";
                var cmd = ctor.Invoke(new object[] { multiDto });

                // Hook IfError(Action) — fires if server rejects the cmd post-queue.
                // Uses Action overload (slot 9 on INotifyingCmd interface).
                try
                {
                    var ifErrorM = cmd.GetType().GetMethod("IfError",
                        BindingFlags.Instance | BindingFlags.Public | BindingFlags.FlattenHierarchy,
                        null, new[] { typeof(Action) }, null);
                    if (ifErrorM != null)
                    {
                        Action errCb = () => Logger.LogWarning(
                            "[RankUp] SERVER REJECTED hero=" + heroId
                            + " food=[" + string.Join(",", foodIds) + "]");
                        ifErrorM.Invoke(cmd, new object[] { errCb });
                    }
                }
                catch { /* non-fatal; cmd still executes */ }

                Logger.LogInfo("[RankUp] enqueue hero=" + heroId
                    + " food=[" + string.Join(",", foodIds) + "]");
                try
                {
                    InvokeExecute(cmd);
                }
                catch (Exception eExec)
                {
                    Logger.LogError("[RankUp] InvokeExecute threw: "
                        + eExec.GetType().Name + ": " + eExec.Message);
                    return "{\"error\":\"InvokeExecute: " + Esc(eExec.Message) + "\"}";
                }

                return "{\"ok\":true,\"hero_id\":" + heroId + ",\"food_count\":" + foodIds.Count + "}";
            }
            catch (TargetInvocationException tex)
            {
                return "{\"error\":\"" + Esc((tex.InnerException ?? tex).Message) + "\"}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // =====================================================
        // API: /move-heroes?dest=X&ids=A,B,C — relocate champions
        // between Champion list / Master Vault / Reserve Vault.
        //   dest=inventory  -> Champion list (MoveHeroesToInventoryCmd)
        //   dest=storage    -> Master Vault (AddHeroesToStorageCmd)
        //   dest=bathhouse  -> Reserve Vault (AddHeroesToBathhouseCmd)
        //
        // Note: "Bathhouse" is Plarium's IL2CPP field name — the in-game
        // UI calls this location "Reserve Vault". Same thing.
        //
        // All three cmds take a List<int> of hero instance IDs;
        // Bathhouse also takes `needDeactivateArtifacts` (true = strip gear).
        // Storage and Inventory don't strip gear.
        // =====================================================
        private string MoveHeroes(string dest, string idsCsv)
        {
            if (string.IsNullOrEmpty(dest))
                return "{\"error\":\"dest required: inventory|storage|bathhouse\"}";
            dest = dest.ToLowerInvariant().Trim();
            if (dest != "inventory" && dest != "storage" && dest != "bathhouse")
                return "{\"error\":\"dest must be inventory|storage|bathhouse, got: " + Esc(dest) + "\"}";
            if (string.IsNullOrEmpty(idsCsv))
                return "{\"error\":\"ids (comma-separated hero ids) required\"}";

            var heroIds = new List<int>();
            foreach (var part in idsCsv.Split(','))
            {
                var p = part.Trim();
                if (string.IsNullOrEmpty(p)) continue;
                if (!int.TryParse(p, out int hid))
                    return "{\"error\":\"ids must be int csv, got: " + Esc(p) + "\"}";
                heroIds.Add(hid);
            }
            if (heroIds.Count == 0)
                return "{\"error\":\"at least 1 id required\"}";

            string cmdTypeName;
            if (dest == "inventory")
                cmdTypeName = "Client.Model.Gameplay.Heroes.Commands.MoveHeroesToInventoryCmd";
            else if (dest == "storage")
                cmdTypeName = "Client.Model.Gameplay.Heroes.Commands.AddHeroesToStorageCmd";
            else // bathhouse
                cmdTypeName = "Client.Model.Gameplay.Heroes.Commands.AddHeroesToBathhouseCmd";

            var cmdType = FindType(cmdTypeName);
            if (cmdType == null) return "{\"error\":\"" + cmdTypeName + " not found\"}";

            try
            {
                // Build Il2Cpp List<int> of hero ids. The cmds expect
                // SharedModel.* generic List<int>; using Il2CppSystem.Collections
                // .Generic.List<int> is the IL2CPP marshalled form.
                var listType = typeof(Il2CppSystem.Collections.Generic.List<int>);
                var list = Activator.CreateInstance(listType);
                MethodInfo addM = null;
                foreach (var m in listType.GetMethods(BindingFlags.Public | BindingFlags.Instance))
                {
                    if (m.Name == "Add" && m.GetParameters().Length == 1) { addM = m; break; }
                }
                if (addM == null) return "{\"error\":\"List<int>.Add not found\"}";
                foreach (int hid in heroIds) addM.Invoke(list, new object[] { hid });

                object cmd;
                if (dest == "bathhouse")
                {
                    // AddHeroesToBathhouseCmd(List<int> heroIds, bool needDeactivateArtifacts)
                    var ctor = cmdType.GetConstructor(new[] { listType, typeof(bool) });
                    if (ctor == null) return "{\"error\":\"AddHeroesToBathhouseCmd(List<int>,bool) ctor not found\"}";
                    cmd = ctor.Invoke(new object[] { list, true });  // strip gear by default
                }
                else
                {
                    // MoveHeroesToInventoryCmd(List<int>) and AddHeroesToStorageCmd(List<int>)
                    var ctor = cmdType.GetConstructor(new[] { listType });
                    if (ctor == null) return "{\"error\":\"" + cmdType.Name + "(List<int>) ctor not found\"}";
                    cmd = ctor.Invoke(new object[] { list });
                }

                Logger.LogInfo("[Move] " + cmdType.Name + " ids=[" + string.Join(",", heroIds) + "] -> " + dest);
                try
                {
                    InvokeExecute(cmd);
                }
                catch (Exception eExec)
                {
                    Logger.LogError("[Move] InvokeExecute threw: " + eExec.GetType().Name + ": " + eExec.Message);
                    return "{\"error\":\"InvokeExecute: " + Esc(eExec.Message) + "\"}";
                }

                return "{\"ok\":true,\"dest\":\"" + dest + "\",\"count\":" + heroIds.Count + "}";
            }
            catch (TargetInvocationException tex)
            {
                return "{\"error\":\"" + Esc((tex.InnerException ?? tex).Message) + "\"}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // =====================================================
        // API: /skill-up?hero_id=X&food=A,B[,...] — feed duplicate
        // copies of the hero (heroInventoryIds) to upgrade their skills.
        // For tome-based skill-up, additionally pass &books=tier:count
        // (e.g., books=4:5 means 5x Legendary tomes; tier maps to
        // BlackMarketItemId).
        //
        // Mechanic: LevelUpSkillCmd takes a LevelUpSkillRequestDto with:
        //   HeroId           target hero
        //   HeroFormId       form id (0 for default)
        //   HeroInventoryIds duplicates of same hero used as fodder
        //   BmiCountByTypeIds  Dictionary<BlackMarketItemId, int> of tomes
        //
        // Server validates the food champs are duplicates of the target
        // (same baseTypeId) and that you have the tome counts claimed.
        // =====================================================
        private string SkillUpHero(string heroIdStr, string foodCsv, string booksCsv)
        {
            if (string.IsNullOrEmpty(heroIdStr) || !int.TryParse(heroIdStr, out int heroId))
                return "{\"error\":\"hero_id (int) required\"}";

            var foodIds = new List<int>();
            if (!string.IsNullOrEmpty(foodCsv))
            {
                foreach (var part in foodCsv.Split(','))
                {
                    var p = part.Trim();
                    if (string.IsNullOrEmpty(p)) continue;
                    if (!int.TryParse(p, out int fid))
                        return "{\"error\":\"food list must be int csv\"}";
                    foodIds.Add(fid);
                }
            }

            // Parse books: "tier:count,tier:count" — each pair becomes
            // a BmiCountByTypeIds entry. Tier ids correspond to skill
            // tome BMIs (Mystery=1, Rare=2, Epic=3, Legendary=4 — verify
            // against actual BlackMarketItemId enum values when in use).
            var bookPairs = new List<(int tier, int count)>();
            if (!string.IsNullOrEmpty(booksCsv))
            {
                foreach (var part in booksCsv.Split(','))
                {
                    var p = part.Trim();
                    if (string.IsNullOrEmpty(p)) continue;
                    var kv = p.Split(':');
                    if (kv.Length != 2)
                        return "{\"error\":\"books must be tier:count pairs\"}";
                    if (!int.TryParse(kv[0], out int t) || !int.TryParse(kv[1], out int c))
                        return "{\"error\":\"books pair must be int:int\"}";
                    bookPairs.Add((t, c));
                }
            }

            if (foodIds.Count == 0 && bookPairs.Count == 0)
                return "{\"error\":\"need either food (duplicate hero ids) or books (tier:count pairs)\"}";

            var dtoType = FindType("SharedModel.Meta.Heroes.Dtos.LevelUpSkillRequestDto");
            var cmdType = FindType("Client.Model.Gameplay.Heroes.Commands.LevelUpSkillCmd");
            if (dtoType == null) return "{\"error\":\"LevelUpSkillRequestDto type not found\"}";
            if (cmdType == null) return "{\"error\":\"LevelUpSkillCmd type not found\"}";

            try
            {
                // Resolve heroFormId from /all-heroes (default to 0)
                int heroFormId = 0;
                try
                {
                    var uw = GetUserWrapper();
                    var heroes = Prop(Prop(uw, "Heroes"), "HeroData");
                    var heroList = Prop(heroes, "Heroes");
                    if (heroList != null)
                    {
                        foreach (var h in ListItems(heroList))
                        {
                            if (IntProp(h, "Id") == heroId)
                            {
                                heroFormId = IntProp(h, "FormId");
                                if (heroFormId == 0)
                                    heroFormId = IntProp(h, "HeroFormId");
                                break;
                            }
                        }
                    }
                }
                catch { /* form 0 is the typical default */ }

                // IL2Cpp DTO fields must be accessed via PROPERTY reflection
                // (interop layer wraps them) — see RankUp comment above.
                var dto = Activator.CreateInstance(dtoType);
                dtoType.GetProperty("HeroId")?.SetValue(dto, heroId);
                dtoType.GetProperty("HeroFormId")?.SetValue(dto, heroFormId);

                if (foodIds.Count > 0)
                {
                    var arr = new Il2CppInterop.Runtime.InteropTypes.Arrays.Il2CppStructArray<int>(
                        foodIds.ToArray());
                    dtoType.GetProperty("HeroInventoryIds")?.SetValue(dto, arr);
                }

                // BmiCountByTypeIds is Dictionary<BlackMarketItemId, int>.
                // For now we only set it if books were provided AND we can
                // resolve the BlackMarketItemId enum type. Skipping if not
                // resolvable (food-only skill-up still works).
                if (bookPairs.Count > 0)
                {
                    var bmiEnum = FindType("SharedModel.Meta.BlackMarket.BlackMarketItemId");
                    if (bmiEnum != null)
                    {
                        var dictType = typeof(Il2CppSystem.Collections.Generic.Dictionary<,>)
                            .MakeGenericType(bmiEnum, typeof(int));
                        var dict = Activator.CreateInstance(dictType);
                        var addM = dictType.GetMethod("Add");
                        foreach (var (tier, count) in bookPairs)
                        {
                            var enumVal = Enum.ToObject(bmiEnum, tier);
                            addM.Invoke(dict, new object[] { enumVal, count });
                        }
                        dtoType.GetProperty("BmiCountByTypeIds")?.SetValue(dto, dict);
                    }
                }

                var ctor = cmdType.GetConstructor(new[] { dtoType });
                if (ctor == null) return "{\"error\":\"LevelUpSkillCmd(dto) ctor not found\"}";
                var cmd = ctor.Invoke(new object[] { dto });
                InvokeExecute(cmd);

                return "{\"ok\":true,\"hero_id\":" + heroId +
                       ",\"food_count\":" + foodIds.Count +
                       ",\"book_pairs\":" + bookPairs.Count + "}";
            }
            catch (TargetInvocationException tex)
            {
                return "{\"error\":\"" + Esc((tex.InnerException ?? tex).Message) + "\"}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // =====================================================
        // API: /apply-blessing?hero_id=X&blessing_id=Y -- assign a
        // Blessing to a hero. Mirrors the in-game blessing-picker UI.
        //
        // Mechanic: SetBlessingCmd(int heroId, BlessingTypeId typeId)
        // is a UserPostEditCmdNoOut. Server validates the hero owns
        // the right Blessing tier (Mythical / Divine / Sacred / etc.)
        // and that the player has the resource cost (Mythical/Divine
        // Mystery dust depending on tier). On success the assignment
        // is permanent until /remove-blessing is called.
        //
        // BlessingTypeId is an int enum — pass the raw id from
        // HH details JSON (`blessingId` field).
        // =====================================================
        private string ApplyBlessing(string heroIdStr, string blessingIdStr)
        {
            if (string.IsNullOrEmpty(heroIdStr) || !int.TryParse(heroIdStr, out int heroId))
                return "{\"error\":\"hero_id (int) required\"}";
            if (string.IsNullOrEmpty(blessingIdStr) || !int.TryParse(blessingIdStr, out int blessingId))
                return "{\"error\":\"blessing_id (int) required\"}";

            var cmdType = FindType("Client.Model.Gameplay.DoubleAscend.Commands.SetBlessingCmd");
            if (cmdType == null) return "{\"error\":\"SetBlessingCmd type not found\"}";

            var blessingEnum = FindType("SharedModel.Meta.DoubleAscend.BlessingTypeId");
            if (blessingEnum == null)
            {
                // Try alternate namespace paths
                foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
                {
                    try
                    {
                        foreach (var t in asm.GetTypes())
                        {
                            if (t.Name == "BlessingTypeId" && t.IsEnum) { blessingEnum = t; break; }
                        }
                    } catch { }
                    if (blessingEnum != null) break;
                }
            }
            if (blessingEnum == null) return "{\"error\":\"BlessingTypeId enum not found\"}";

            try
            {
                // Find the (int, BlessingTypeId) constructor
                var ctor = cmdType.GetConstructor(new[] { typeof(int), blessingEnum });
                if (ctor == null)
                {
                    // Try with a base int type for the enum (Il2Cpp interop sometimes
                    // surfaces enums as int parameters directly).
                    ctor = cmdType.GetConstructor(new[] { typeof(int), typeof(int) });
                }
                if (ctor == null) return "{\"error\":\"SetBlessingCmd ctor (int, BlessingTypeId) not found\"}";

                // Build the enum value from raw int
                object enumVal;
                try { enumVal = Enum.ToObject(blessingEnum, blessingId); }
                catch { enumVal = blessingId; }

                var cmd = ctor.Invoke(new object[] { heroId, enumVal });
                InvokeExecute(cmd);

                return "{\"ok\":true,\"hero_id\":" + heroId + ",\"blessing_id\":" + blessingId + "}";
            }
            catch (TargetInvocationException tex)
            {
                return "{\"error\":\"" + Esc((tex.InnerException ?? tex).Message) + "\"}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // =====================================================
        // API: /event-progress — live per-event score + placement.
        //
        // The game splits event data:
        //   - DataJson (served by /events) holds the static catalog:
        //     prototype ids, mission rules, tier reward tables, dates.
        //     This is sent down once per refresh and rarely re-syncs.
        //   - TournamentPointsByStateId, SoloEventPointsByStateId,
        //     PositionByStateId hold the LIVE state — your earned
        //     points and current leaderboard position. These are
        //     [JsonSkip]/[IgnoreMember] in the DTO so they never
        //     appear in DataJson; only direct memory access works.
        //
        // Cross-reference with /events output via the shared stateId.
        // =====================================================
        private string GetEventProgress()
        {
            try
            {
                var uw = GetUserWrapper();
                if (uw == null) return "{\"error\":\"Not logged in\"}";
                var tournaments = Prop(uw, "Tournaments");
                if (tournaments == null) return "{\"error\":\"Tournaments wrapper not found\"}";

                var sb = new StringBuilder(2048);
                sb.Append("{");

                // PositionByStateId: int -> int (stateId -> rank).
                var positions = Prop(tournaments, "PositionByStateId");
                sb.Append("\"positions\":");
                AppendIntDict(sb, positions);

                // Per-quest score lives in QuestState.TotalPoints (a
                // Nullable<int> at offset 0xF4 on each QuestState row of
                // QuestData.OpenedStates). Walk the list, emit
                // {prototype_id, quest_id, points} rows. Consumers
                // aggregate by prototype_id (= GlobalEvent's stateId
                // domain) to get per-event totals.
                var qd = Prop(tournaments, "QuestData");
                var openedStates = Prop(qd, "OpenedStates");
                sb.Append(",\"quest_points\":");
                AppendQuestStatePoints(sb, openedStates);

                sb.Append("}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        /// <summary>
        /// Walk a List&lt;QuestState&gt; and emit per-quest score rows.
        /// Each QuestState may track score in two places:
        ///   - TotalPoints (Nullable&lt;int&gt; @0xF4): aggregated total,
        ///     populated for some quest types (notably Solo events
        ///     after their final tally — not always live during play).
        ///   - Completions[i].ByTournament.ByPoints.CountCollected:
        ///     live per-quest tournament score that updates as you
        ///     play. For TA Dragon this is the field that mirrors
        ///     the in-game tournament UI's "your points" number.
        ///   - Completions[i].BySoloEvent.ByPoints.ByPoints.CountCollected:
        ///     same idea for solo events.
        ///
        /// Field offsets (all from the IL2CPP dump):
        ///   QuestState.QuestId      @0x10 (int)
        ///   QuestState.PrototypeId  @0x14 (int)
        ///   QuestState.Completions  @0x88 (List&lt;QuestCompletion&gt;)
        ///   QuestState.TotalPoints  @0xF4 (Nullable&lt;int&gt;)
        ///   QuestCompletion.BySoloEvent  @0x88 (QuestCompletionBySoloEvent)
        ///   QuestCompletion.ByTournament @0x90 (QuestCompletionByTournament)
        ///   QuestCompletionBySoloEvent.ByPoints   @0x20 (QuestCompletionByEventPoints)
        ///   QuestCompletionByTournament.ByPoints  @0x20 (QuestCompletionByTournamentPoints)
        ///   QuestCompletionBy*Points.CountCollected @0x14 (int)
        /// </summary>
        private void AppendQuestStatePoints(StringBuilder sb, object listObj)
        {
            sb.Append("[");
            if (listObj == null) { sb.Append("]"); return; }
            try
            {
                IntPtr listPtr = GetIl2CppPointer(listObj);
                if (listPtr == IntPtr.Zero) { sb.Append("]"); return; }
                IntPtr listCls = il2cpp_object_get_class(listPtr);
                IntPtr itemsField = IntPtr.Zero, sizeField = IntPtr.Zero;
                IntPtr fi = IntPtr.Zero;
                IntPtr f;
                while ((f = il2cpp_class_get_fields(listCls, ref fi)) != IntPtr.Zero)
                {
                    string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(f));
                    if (fn == "_items") itemsField = f;
                    else if (fn == "_size") sizeField = f;
                }
                if (itemsField == IntPtr.Zero || sizeField == IntPtr.Zero) { sb.Append("]"); return; }
                int size = Marshal.ReadInt32(listPtr, (int)il2cpp_field_get_offset(sizeField));
                IntPtr itemsArrPtr = Marshal.ReadIntPtr(listPtr, (int)il2cpp_field_get_offset(itemsField));
                if (itemsArrPtr == IntPtr.Zero || size == 0) { sb.Append("]"); return; }

                IntPtr itemsBase = IntPtr.Add(itemsArrPtr, 0x20);
                bool first = true;
                int kept = 0;
                for (int i = 0; i < size && kept < 800; i++)
                {
                    IntPtr qsPtr = Marshal.ReadIntPtr(itemsBase, i * 8);
                    if (qsPtr == IntPtr.Zero) continue;
                    int questId = Marshal.ReadInt32(qsPtr, 0x10);
                    int protoId = Marshal.ReadInt32(qsPtr, 0x14);

                    // 1) TotalPoints (Nullable<int>) at 0xF4. Layout
                    // varies — read both halves and keep the non-zero.
                    int totalPts = Marshal.ReadInt32(qsPtr, 0xF4);

                    // 2) Walk Completions and pull tournament/solo CountCollected
                    int tournamentCol = 0;
                    int soloCol = 0;
                    IntPtr completionsList = Marshal.ReadIntPtr(qsPtr, 0x88);
                    if (completionsList != IntPtr.Zero)
                    {
                        // Repeat the List walker on completionsList
                        IntPtr cCls = il2cpp_object_get_class(completionsList);
                        IntPtr cItemsF = IntPtr.Zero, cSizeF = IntPtr.Zero;
                        IntPtr cFi = IntPtr.Zero;
                        IntPtr cF;
                        while ((cF = il2cpp_class_get_fields(cCls, ref cFi)) != IntPtr.Zero)
                        {
                            string cn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(cF));
                            if (cn == "_items") cItemsF = cF;
                            else if (cn == "_size") cSizeF = cF;
                        }
                        if (cItemsF != IntPtr.Zero && cSizeF != IntPtr.Zero)
                        {
                            int cSize = Marshal.ReadInt32(completionsList, (int)il2cpp_field_get_offset(cSizeF));
                            IntPtr cArr = Marshal.ReadIntPtr(completionsList, (int)il2cpp_field_get_offset(cItemsF));
                            if (cArr != IntPtr.Zero)
                            {
                                IntPtr cBase = IntPtr.Add(cArr, 0x20);
                                for (int ci = 0; ci < cSize; ci++)
                                {
                                    IntPtr qcPtr = Marshal.ReadIntPtr(cBase, ci * 8);
                                    if (qcPtr == IntPtr.Zero) continue;

                                    // ByTournament @ 0x90 -> ByPoints @ 0x20 -> CountCollected @ 0x14
                                    IntPtr byTour = Marshal.ReadIntPtr(qcPtr, 0x90);
                                    if (byTour != IntPtr.Zero)
                                    {
                                        IntPtr byPts = Marshal.ReadIntPtr(byTour, 0x20);
                                        if (byPts != IntPtr.Zero)
                                            tournamentCol += Marshal.ReadInt32(byPts, 0x14);
                                    }
                                    // BySoloEvent @ 0x88 -> ByPoints @ 0x20 ->
                                    //   QuestCompletionByEventPoints.ByPoints (nested) -> CountCollected
                                    IntPtr bySolo = Marshal.ReadIntPtr(qcPtr, 0x88);
                                    if (bySolo != IntPtr.Zero)
                                    {
                                        IntPtr eventByPts = Marshal.ReadIntPtr(bySolo, 0x20);
                                        if (eventByPts != IntPtr.Zero)
                                            soloCol += Marshal.ReadInt32(eventByPts, 0x14);
                                    }
                                }
                            }
                        }
                    }

                    if (totalPts == 0 && tournamentCol == 0 && soloCol == 0) continue;
                    if (!first) sb.Append(",");
                    first = false;
                    sb.Append("{\"q\":").Append(questId)
                      .Append(",\"p\":").Append(protoId)
                      .Append(",\"tp\":").Append(totalPts)
                      .Append(",\"tour\":").Append(tournamentCol)
                      .Append(",\"solo\":").Append(soloCol)
                      .Append("}");
                    kept++;
                }
            }
            catch (Exception ex) { sb.Append("\"_err\":\"").Append(Esc(ex.Message)).Append("\""); }
            sb.Append("]");
        }

        /// <summary>
        /// Get the raw IL2Cpp pointer of a wrapping CLR object. Walks the
        /// type chain looking for a Pointer property/field — Il2CppInterop
        /// places it on Il2CppObjectBase but type wrappers obscure it.
        /// </summary>
        private static IntPtr GetIl2CppPointer(object obj)
        {
            if (obj == null) return IntPtr.Zero;
            var t = obj.GetType();
            while (t != null && t != typeof(object))
            {
                var p = t.GetProperty("Pointer",
                    BindingFlags.Public | BindingFlags.Instance | BindingFlags.DeclaredOnly);
                if (p != null)
                {
                    try { return (IntPtr)p.GetValue(obj); } catch { }
                }
                var f = t.GetField("Pointer",
                    BindingFlags.Public | BindingFlags.Instance | BindingFlags.DeclaredOnly);
                if (f != null)
                {
                    try { return (IntPtr)f.GetValue(obj); } catch { }
                }
                t = t.BaseType;
            }
            return IntPtr.Zero;
        }

        /// <summary>
        /// Walk an IL2Cpp object's class fields by name; return the
        /// pointer stored at the matching field's offset. Used for fields
        /// the managed reflection can't see (e.g. [IgnoreMember] dicts of
        /// unresolved generic types).
        /// </summary>
        private IntPtr ResolveDictByFieldName(object holder, string fieldName)
        {
            if (holder == null) return IntPtr.Zero;
            IntPtr holderPtr = GetIl2CppPointer(holder);
            if (holderPtr == IntPtr.Zero) return IntPtr.Zero;
            IntPtr klass = il2cpp_object_get_class(holderPtr);
            if (klass == IntPtr.Zero) return IntPtr.Zero;
            IntPtr fIter = IntPtr.Zero;
            IntPtr fld;
            while ((fld = il2cpp_class_get_fields(klass, ref fIter)) != IntPtr.Zero)
            {
                string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(fld));
                if (fn == fieldName)
                {
                    uint off = il2cpp_field_get_offset(fld);
                    return Marshal.ReadIntPtr(holderPtr, (int)off);
                }
            }
            return IntPtr.Zero;
        }

        /// <summary>
        /// Walk a Dictionary&lt;int,int&gt; by raw _entries[] memory layout and
        /// emit it as JSON. Same entry layout as the wrapper-aware path
        /// in AppendIntDict but starting from a raw IntPtr.
        /// </summary>
        private void AppendIntDictRaw(StringBuilder sb, IntPtr dictPtr)
        {
            if (dictPtr == IntPtr.Zero) { sb.Append("{}"); return; }
            sb.Append("{");
            try
            {
                IntPtr klass = il2cpp_object_get_class(dictPtr);
                IntPtr entriesField = IntPtr.Zero;
                IntPtr countField = IntPtr.Zero;
                IntPtr fIter = IntPtr.Zero;
                IntPtr f;
                while ((f = il2cpp_class_get_fields(klass, ref fIter)) != IntPtr.Zero)
                {
                    string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(f));
                    if (fn == "_entries") entriesField = f;
                    else if (fn == "_count") countField = f;
                }
                if (entriesField == IntPtr.Zero || countField == IntPtr.Zero) { sb.Append("}"); return; }
                uint entriesOff = il2cpp_field_get_offset(entriesField);
                uint countOff = il2cpp_field_get_offset(countField);
                int count = Marshal.ReadInt32(dictPtr, (int)countOff);
                IntPtr entriesPtr = Marshal.ReadIntPtr(dictPtr, (int)entriesOff);
                if (entriesPtr == IntPtr.Zero || count == 0) { sb.Append("}"); return; }
                bool first = true;
                int entrySize = 16;  // hashCode(4) + next(4) + key(4) + value(4)
                IntPtr dataBase = IntPtr.Add(entriesPtr, 0x20);
                for (int i = 0; i < count; i++)
                {
                    int hashCode = Marshal.ReadInt32(dataBase, i * entrySize);
                    if (hashCode < 0) continue;
                    int key = Marshal.ReadInt32(dataBase, i * entrySize + 8);
                    int val = Marshal.ReadInt32(dataBase, i * entrySize + 12);
                    if (!first) sb.Append(",");
                    first = false;
                    sb.Append("\"").Append(key).Append("\":").Append(val);
                }
            }
            catch (Exception ex) { sb.Append("\"_err\":\"").Append(Esc(ex.Message)).Append("\""); }
            sb.Append("}");
        }

        /// <summary>
        /// Serialize an Il2Cpp Dictionary&lt;int,int&gt; as JSON {"k":v,...}.
        /// Uses raw IL2Cpp via il2cpp_runtime_invoke on get_Keys / get_Item:
        /// managed reflection on Il2CppInterop dict wrappers tends to
        /// return "?"-typed enumerators that can't be walked.
        /// </summary>
        private void AppendIntDict(StringBuilder sb, object dict)
        {
            if (dict == null) { sb.Append("{}"); return; }
            sb.Append("{");
            try
            {
                // Need an Il2CppObjectBase (or anything exposing .Pointer).
                // The dict object may be wrapped — cast to Il2CppSystem.Object
                // first if its declared type doesn't expose Pointer directly.
                IntPtr dictPtr = IntPtr.Zero;
                var ptrProp = dict.GetType().GetProperty("Pointer",
                    BindingFlags.Public | BindingFlags.Instance);
                if (ptrProp != null)
                {
                    try { dictPtr = (IntPtr)ptrProp.GetValue(dict); } catch { }
                }
                if (dictPtr == IntPtr.Zero)
                {
                    // Walk type chain — some wrapped types expose Pointer
                    // only on a base class.
                    var bt = dict.GetType().BaseType;
                    while (bt != null && dictPtr == IntPtr.Zero && bt != typeof(object))
                    {
                        var bp = bt.GetProperty("Pointer",
                            BindingFlags.Public | BindingFlags.Instance | BindingFlags.DeclaredOnly);
                        if (bp != null)
                        {
                            try { dictPtr = (IntPtr)bp.GetValue(dict); } catch { }
                        }
                        bt = bt.BaseType;
                    }
                }
                if (dictPtr == IntPtr.Zero)
                {
                    // Last resort — Il2CppObjectBase exposes a `Pointer` field too.
                    var pointerField = dict.GetType().GetField("Pointer",
                        BindingFlags.Public | BindingFlags.Instance | BindingFlags.NonPublic);
                    if (pointerField != null)
                    {
                        try { dictPtr = (IntPtr)pointerField.GetValue(dict); } catch { }
                    }
                }
                if (dictPtr == IntPtr.Zero)
                {
                    sb.Append("\"_err\":\"no Pointer on ").Append(Esc(dict.GetType().FullName ?? "?")).Append("\"}");
                    return;
                }

                IntPtr klass = il2cpp_object_get_class(dictPtr);
                // Find get_Keys + get_Count + indexer (get_Item) on the
                // Dictionary class. Walk the parent chain in case the
                // method is inherited.
                IntPtr getKeys = IntPtr.Zero, getCount = IntPtr.Zero, getItem = IntPtr.Zero;
                IntPtr scan = klass;
                while (scan != IntPtr.Zero && (getKeys == IntPtr.Zero || getCount == IntPtr.Zero || getItem == IntPtr.Zero))
                {
                    IntPtr mIter = IntPtr.Zero;
                    IntPtr m;
                    while ((m = il2cpp_class_get_methods(scan, ref mIter)) != IntPtr.Zero)
                    {
                        string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                        uint pc = il2cpp_method_get_param_count(m);
                        if (mn == "get_Keys" && pc == 0 && getKeys == IntPtr.Zero) getKeys = m;
                        else if (mn == "get_Count" && pc == 0 && getCount == IntPtr.Zero) getCount = m;
                        else if (mn == "get_Item" && pc == 1 && getItem == IntPtr.Zero) getItem = m;
                    }
                    scan = il2cpp_class_get_parent(scan);
                }
                if (getKeys == IntPtr.Zero || getItem == IntPtr.Zero) { sb.Append("}"); return; }

                IntPtr exc = IntPtr.Zero;
                IntPtr keysObj = il2cpp_runtime_invoke(getKeys, dictPtr, IntPtr.Zero, ref exc);
                if (exc != IntPtr.Zero || keysObj == IntPtr.Zero) { sb.Append("}"); return; }

                // Keys is a KeyCollection — use its Count + index-based iteration
                // via its own enumerator. Easier: use System.Linq via reflection
                // OR just fall back to walking _entries directly.
                // Cleanest: walk _entries[] directly. The dict layout in the
                // System.Collections.Generic.Dictionary IL2Cpp port has:
                //   _entries (ref-array of Entry structs) somewhere at offset.
                // Find via field iteration + name match.
                IntPtr fIter = IntPtr.Zero;
                IntPtr fld;
                IntPtr entriesField = IntPtr.Zero;
                IntPtr countField = IntPtr.Zero;
                while ((fld = il2cpp_class_get_fields(klass, ref fIter)) != IntPtr.Zero)
                {
                    string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(fld));
                    if (fn == "_entries") entriesField = fld;
                    else if (fn == "_count") countField = fld;
                }
                if (entriesField == IntPtr.Zero || countField == IntPtr.Zero) { sb.Append("}"); return; }

                uint entriesOff = il2cpp_field_get_offset(entriesField);
                uint countOff = il2cpp_field_get_offset(countField);
                int count = Marshal.ReadInt32(dictPtr, (int)countOff);
                IntPtr entriesPtr = Marshal.ReadIntPtr(dictPtr, (int)entriesOff);
                if (entriesPtr == IntPtr.Zero || count == 0) { sb.Append("}"); return; }

                // Il2Cpp arrays: header is 0x20 bytes, then Length at 0x18,
                // then data at 0x20. Each Entry<int,int> in IL2Cpp layout is
                // 16 bytes: { int hashCode, int next, int key, int value }.
                // Walk count entries, skipping deleted (hashCode < 0).
                bool first = true;
                int entrySize = 16;
                IntPtr dataBase = IntPtr.Add(entriesPtr, 0x20);
                for (int i = 0; i < count; i++)
                {
                    int hashCode = Marshal.ReadInt32(dataBase, i * entrySize);
                    if (hashCode < 0) continue; // deleted slot
                    int key = Marshal.ReadInt32(dataBase, i * entrySize + 8);
                    int val = Marshal.ReadInt32(dataBase, i * entrySize + 12);
                    if (!first) sb.Append(",");
                    first = false;
                    sb.Append("\"").Append(key).Append("\":").Append(val);
                }
            }
            catch (Exception ex)
            {
                sb.Append("\"_err\":\"").Append(Esc(ex.Message)).Append("\"");
            }
            sb.Append("}");
        }

        // =====================================================
        // API: /events — dump active GlobalEvents (tournaments,
        // solo events, cvc, etc.) as the game's own JSON.
        //
        // Source: UserWrapper.Tournaments._globalEvents.DataJson —
        // a 200KB+ string the server sends down with the full event
        // catalog: prototype ids, titles, mission types, score tables,
        // reward tiers, start/end timestamps. Surfacing it raw lets
        // tooling decide which events are worth farming.
        // =====================================================
        private string GetEvents()
        {
            try
            {
                var uw = GetUserWrapper();
                if (uw == null) return "{\"error\":\"Not logged in\"}";
                var tournaments = Prop(uw, "Tournaments");
                if (tournaments == null) return "{\"error\":\"Tournaments wrapper not found\"}";
                var globalEvents = Prop(tournaments, "_globalEvents");
                if (globalEvents == null) return "{\"error\":\"_globalEvents not found on TournamentsWrapper\"}";

                // The DataJson public property and its backing field both work.
                // Read the property first; fall back to the backing field if
                // the property accessor is missing (Il2CppInterop sometimes
                // wraps these inconsistently).
                string json = null;
                try
                {
                    var v = Prop(globalEvents, "DataJson");
                    if (v != null) json = v.ToString();
                }
                catch { }
                if (string.IsNullOrEmpty(json))
                {
                    try
                    {
                        var v = Prop(globalEvents, "_DataJson_k__BackingField");
                        if (v != null) json = v.ToString();
                    }
                    catch { }
                }
                if (string.IsNullOrEmpty(json))
                    return "{\"error\":\"DataJson empty (no events down from server yet?)\"}";

                // The DataJson is already valid JSON — wrap it so consumers
                // can also see the byte size + when it was last refreshed.
                long updatedTicks = 0;
                try
                {
                    var ut = Prop(globalEvents, "_knownUpdateTime");
                    if (ut != null)
                    {
                        var ticksProp = ut.GetType().GetProperty("Ticks",
                            BindingFlags.Public | BindingFlags.Instance);
                        if (ticksProp != null)
                            updatedTicks = (long)ticksProp.GetValue(ut);
                    }
                }
                catch { }

                var sb = new StringBuilder(json.Length + 256);
                sb.Append("{\"size\":").Append(json.Length);
                sb.Append(",\"updated_ticks\":").Append(updatedTicks);
                sb.Append(",\"data\":").Append(json);
                sb.Append("}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        /// <summary>
        /// BFS through a dialog's transform hierarchy looking for a MonoBehaviour
        /// whose get_Context() returns a HeroesSelectionDialogContext subclass.
        /// Uses raw IL2Cpp APIs (managed reflection misses IL2Cpp-defined props).
        /// </summary>
        private bool TryFindHeroesSelectionContext(Transform root,
                                                   out IntPtr ctxObj,
                                                   out IntPtr ctxClass,
                                                   out string ctxClassName,
                                                   out string ctxNs)
        {
            ctxObj = IntPtr.Zero;
            ctxClass = IntPtr.Zero;
            ctxClassName = null;
            ctxNs = null;

            var queue = new Queue<KeyValuePair<Transform, int>>();
            queue.Enqueue(new KeyValuePair<Transform, int>(root, 0));
            int searched = 0;
            while (queue.Count > 0 && searched < 400)
            {
                var pair = queue.Dequeue();
                var t = pair.Key;
                int depth = pair.Value;
                searched++;

                foreach (var mono in t.gameObject.GetComponents<MonoBehaviour>())
                {
                    if (mono == null) continue;
                    try
                    {
                        IntPtr monoPtr = mono.Pointer;
                        if (monoPtr == IntPtr.Zero) continue;
                        IntPtr monoClass = il2cpp_object_get_class(monoPtr);
                        if (monoClass == IntPtr.Zero) continue;

                        // Walk the class hierarchy looking for get_Context.
                        IntPtr klass = monoClass;
                        IntPtr getCtx = IntPtr.Zero;
                        while (klass != IntPtr.Zero && getCtx == IntPtr.Zero)
                        {
                            IntPtr mIter = IntPtr.Zero;
                            IntPtr mm;
                            while ((mm = il2cpp_class_get_methods(klass, ref mIter)) != IntPtr.Zero)
                            {
                                string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(mm));
                                if (mn == "get_Context" && il2cpp_method_get_param_count(mm) == 0)
                                {
                                    getCtx = mm;
                                    break;
                                }
                            }
                            if (getCtx == IntPtr.Zero)
                                klass = il2cpp_class_get_parent(klass);
                        }
                        if (getCtx == IntPtr.Zero) continue;

                        IntPtr exc = IntPtr.Zero;
                        IntPtr cobj = il2cpp_runtime_invoke(getCtx, monoPtr, IntPtr.Zero, ref exc);
                        if (exc != IntPtr.Zero || cobj == IntPtr.Zero) continue;

                        IntPtr cclass = il2cpp_object_get_class(cobj);
                        if (cclass == IntPtr.Zero) continue;

                        // Walk parent chain to see if any ancestor is the
                        // HeroesSelectionDialogContext`1 generic base.
                        IntPtr scan = cclass;
                        bool isMatch = false;
                        while (scan != IntPtr.Zero)
                        {
                            string sn = Marshal.PtrToStringAnsi(il2cpp_class_get_name(scan));
                            if (sn == "HeroesSelectionDialogContext`1")
                            {
                                isMatch = true;
                                break;
                            }
                            if (sn == "Object" || sn == "Il2CppObjectBase") break;
                            scan = il2cpp_class_get_parent(scan);
                        }
                        if (!isMatch) continue;

                        ctxObj = cobj;
                        ctxClass = cclass;
                        ctxClassName = Marshal.PtrToStringAnsi(il2cpp_class_get_name(cclass));
                        ctxNs = Marshal.PtrToStringAnsi(il2cpp_class_get_namespace(cclass));
                        return true;
                    }
                    catch { }
                }

                if (depth < 10)
                {
                    for (int ci = 0; ci < t.childCount && ci < 30; ci++)
                        queue.Enqueue(new KeyValuePair<Transform, int>(t.GetChild(ci), depth + 1));
                }
            }
            return false;
        }

        // =====================================================
        // SQUAD MANIPULATION (no presets)
        //
        // The user-facing battle setup screen (StoryHeroesSelectionDialog,
        // and the dungeon equivalents) embeds a HeroesSquadContext<T> that
        // exposes AddHero / RemoveHero / Reset on the active squad. These
        // endpoints let us drive the slots directly — no preset save needed,
        // suitable for tight rotation loops where the team changes every
        // few battles.
        //
        // Endpoints:
        //   /squad-set?ids=A,B,C,D,E — replace the whole squad
        //   /squad-add?hero_id=X     — add one hero to the next free slot
        //   /squad-remove?hero_id=X  — remove a specific hero
        //   /squad-clear             — empty all slots
        //   /squad-current           — read current HeroIds (diagnostic)
        // =====================================================

        /// <summary>
        /// BFS the active dialog tree looking for a MonoBehaviour whose
        /// get_Context() returns an instance whose class hierarchy contains
        /// HeroesSquadContext`1. Mirrors TryFindHeroesSelectionContext but
        /// matches the squad context instead of the dialog context.
        /// </summary>
        private bool TryFindHeroesSquadContext(Transform root,
                                               out IntPtr ctxObj,
                                               out IntPtr ctxClass)
        {
            ctxObj = IntPtr.Zero;
            ctxClass = IntPtr.Zero;

            var queue = new Queue<KeyValuePair<Transform, int>>();
            queue.Enqueue(new KeyValuePair<Transform, int>(root, 0));
            int searched = 0;
            while (queue.Count > 0 && searched < 600)
            {
                var pair = queue.Dequeue();
                var t = pair.Key;
                int depth = pair.Value;
                searched++;

                foreach (var mono in t.gameObject.GetComponents<MonoBehaviour>())
                {
                    if (mono == null) continue;
                    try
                    {
                        IntPtr monoPtr = mono.Pointer;
                        if (monoPtr == IntPtr.Zero) continue;
                        IntPtr monoClass = il2cpp_object_get_class(monoPtr);
                        if (monoClass == IntPtr.Zero) continue;

                        IntPtr klass = monoClass;
                        IntPtr getCtx = IntPtr.Zero;
                        while (klass != IntPtr.Zero && getCtx == IntPtr.Zero)
                        {
                            IntPtr mIter = IntPtr.Zero;
                            IntPtr mm;
                            while ((mm = il2cpp_class_get_methods(klass, ref mIter)) != IntPtr.Zero)
                            {
                                string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(mm));
                                if (mn == "get_Context" && il2cpp_method_get_param_count(mm) == 0)
                                {
                                    getCtx = mm;
                                    break;
                                }
                            }
                            if (getCtx == IntPtr.Zero)
                                klass = il2cpp_class_get_parent(klass);
                        }
                        if (getCtx == IntPtr.Zero) continue;

                        IntPtr exc = IntPtr.Zero;
                        IntPtr cobj = il2cpp_runtime_invoke(getCtx, monoPtr, IntPtr.Zero, ref exc);
                        if (exc != IntPtr.Zero || cobj == IntPtr.Zero) continue;

                        IntPtr cclass = il2cpp_object_get_class(cobj);
                        if (cclass == IntPtr.Zero) continue;

                        IntPtr scan = cclass;
                        bool isMatch = false;
                        while (scan != IntPtr.Zero)
                        {
                            string sn = Marshal.PtrToStringAnsi(il2cpp_class_get_name(scan));
                            if (sn == "HeroesSquadContext`1") { isMatch = true; break; }
                            if (sn == "Object" || sn == "Il2CppObjectBase") break;
                            scan = il2cpp_class_get_parent(scan);
                        }
                        if (!isMatch) continue;

                        ctxObj = cobj;
                        ctxClass = cclass;
                        return true;
                    }
                    catch { }
                }

                if (depth < 12)
                {
                    for (int ci = 0; ci < t.childCount && ci < 40; ci++)
                        queue.Enqueue(new KeyValuePair<Transform, int>(t.GetChild(ci), depth + 1));
                }
            }
            return false;
        }

        /// <summary>
        /// Resolve the active HeroesSquadContext. The squad is NOT a separate
        /// MonoBehaviour-context — it's a protected field `MySquad` on the
        /// dialog's HeroesSquadSelectionDialogContext. Walks the active
        /// dialogs root, finds the dialog context, then reads the MySquad
        /// field from its IL2Cpp class hierarchy.
        /// Returns (IntPtr.Zero, IntPtr.Zero) if no battle-setup dialog with a
        /// squad is currently visible.
        /// </summary>
        private (IntPtr ctxObj, IntPtr ctxClass) FindActiveSquadContext()
        {
            var dialogsRoot = GameObject.Find("UIManager/Canvas (Ui Root)/Dialogs");
            if (dialogsRoot == null) return (IntPtr.Zero, IntPtr.Zero);

            // Step 1: find the HeroesSelectionDialogContext via BFS. Don't
            // skip activeSelf=false because the underlying battle-setup dialog
            // gets deactivated when a finish dialog overlays it. The squad
            // context still lives on the inactive dialog and we can still
            // call AddHero/RemoveHero on it (verified live).
            IntPtr dlgCtx = IntPtr.Zero;
            IntPtr dlgClass = IntPtr.Zero;
            string ignoreClassName = null, ignoreNs = null;
            for (int di = 0; di < dialogsRoot.transform.childCount; di++)
            {
                var dialog = dialogsRoot.transform.GetChild(di);
                // Try ACTIVE first (preferred), fall back to inactive after.
                if (!dialog.gameObject.activeSelf) continue;
                if (TryFindHeroesSelectionContext(dialog, out dlgCtx, out dlgClass,
                                                   out ignoreClassName, out ignoreNs))
                    break;
            }
            if (dlgCtx == IntPtr.Zero)
            {
                for (int di = 0; di < dialogsRoot.transform.childCount; di++)
                {
                    var dialog = dialogsRoot.transform.GetChild(di);
                    if (dialog.gameObject.activeSelf) continue;
                    if (TryFindHeroesSelectionContext(dialog, out dlgCtx, out dlgClass,
                                                       out ignoreClassName, out ignoreNs))
                        break;
                }
            }
            if (dlgCtx == IntPtr.Zero) return (IntPtr.Zero, IntPtr.Zero);

            // Step 2: locate the `MySquad` instance field on the class
            // hierarchy. The field is declared `protected readonly
            // HeroesSquadContext<HeroSlotContext>` on
            // HeroesSquadSelectionDialogContext (the parent of every
            // story/dungeon/arena dialog context). Walk up the chain.
            IntPtr fieldPtr = IntPtr.Zero;
            uint fieldOffset = 0;
            bool foundField = false;
            IntPtr scan = dlgClass;
            while (scan != IntPtr.Zero)
            {
                IntPtr fIter = IntPtr.Zero;
                IntPtr ff;
                while ((ff = il2cpp_class_get_fields(scan, ref fIter)) != IntPtr.Zero)
                {
                    string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(ff));
                    if (fn == "MySquad")
                    {
                        fieldPtr = ff;
                        fieldOffset = il2cpp_field_get_offset(ff);
                        foundField = true;
                        break;
                    }
                }
                if (foundField) break;
                scan = il2cpp_class_get_parent(scan);
            }
            if (!foundField)
            {
                Logger.LogWarning("[Squad] MySquad field not found on dialog class chain");
                return (IntPtr.Zero, IntPtr.Zero);
            }

            // Step 3: read the field from the dialog context object. IL2Cpp
            // stores reference fields as IntPtr at the field's offset within
            // the object's instance data. Object header = 16 bytes (klass +
            // monitor) on 64-bit; field offsets are relative to start of
            // object including header.
            IntPtr squadPtr;
            try
            {
                squadPtr = Marshal.ReadIntPtr(dlgCtx, (int)fieldOffset);
            }
            catch (Exception ex)
            {
                Logger.LogWarning("[Squad] read MySquad field failed: " + ex.Message);
                return (IntPtr.Zero, IntPtr.Zero);
            }
            if (squadPtr == IntPtr.Zero)
            {
                Logger.LogWarning("[Squad] MySquad field is null at offset " + fieldOffset);
                return (IntPtr.Zero, IntPtr.Zero);
            }
            IntPtr squadClass = il2cpp_object_get_class(squadPtr);
            Logger.LogInfo("[Squad] resolved MySquad ptr=0x" + squadPtr.ToString("X")
                + " offset=" + fieldOffset);
            return (squadPtr, squadClass);
        }

        /// <summary>
        /// Find a method by name + parameter count on the IL2CPP class
        /// hierarchy, walking parents until found or exhausted.
        /// </summary>
        private IntPtr FindClassMethodByName(IntPtr cclass, string name, int paramCount)
        {
            IntPtr scan = cclass;
            while (scan != IntPtr.Zero)
            {
                IntPtr mIter = IntPtr.Zero;
                IntPtr m;
                while ((m = il2cpp_class_get_methods(scan, ref mIter)) != IntPtr.Zero)
                {
                    string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                    if (mn == name && il2cpp_method_get_param_count(m) == paramCount)
                        return m;
                }
                scan = il2cpp_class_get_parent(scan);
            }
            return IntPtr.Zero;
        }

        /// <summary>
        /// Read current squad hero IDs by invoking get_HeroIds() on the squad
        /// context. Returns IEnumerable<int> as a managed list (best-effort).
        /// </summary>
        private List<int> ReadCurrentSquadHeroIds(IntPtr ctxObj, IntPtr ctxClass)
        {
            var result = new List<int>();
            try
            {
                IntPtr getMethod = FindClassMethodByName(ctxClass, "get_HeroIds", 0);
                if (getMethod == IntPtr.Zero) return result;
                IntPtr exc = IntPtr.Zero;
                IntPtr enumObj = il2cpp_runtime_invoke(getMethod, ctxObj, IntPtr.Zero, ref exc);
                if (exc != IntPtr.Zero || enumObj == IntPtr.Zero) return result;

                // Wrap as Il2CppSystem object and iterate.
                var enumerable = new Il2CppSystem.Object(enumObj);
                // Try cast to IEnumerable<int> via Il2CppSystem.Collections.IEnumerable.
                // Easiest path: GetEnumerator() + MoveNext + Current using reflection.
                IntPtr enumClass = il2cpp_object_get_class(enumObj);
                IntPtr getEnum = FindClassMethodByName(enumClass, "GetEnumerator", 0);
                if (getEnum == IntPtr.Zero) return result;
                IntPtr exc2 = IntPtr.Zero;
                IntPtr it = il2cpp_runtime_invoke(getEnum, enumObj, IntPtr.Zero, ref exc2);
                if (exc2 != IntPtr.Zero || it == IntPtr.Zero) return result;
                IntPtr itClass = il2cpp_object_get_class(it);
                IntPtr moveNext = FindClassMethodByName(itClass, "MoveNext", 0);
                IntPtr getCur = FindClassMethodByName(itClass, "get_Current", 0);
                if (moveNext == IntPtr.Zero || getCur == IntPtr.Zero) return result;
                while (true)
                {
                    IntPtr e3 = IntPtr.Zero;
                    IntPtr okPtr = il2cpp_runtime_invoke(moveNext, it, IntPtr.Zero, ref e3);
                    if (e3 != IntPtr.Zero || okPtr == IntPtr.Zero) break;
                    // il2cpp_object_unbox returns pointer to the value buffer
                    // (skips the IL2Cpp object header) — works for any value type.
                    IntPtr okVal = il2cpp_object_unbox(okPtr);
                    bool ok = okVal != IntPtr.Zero && Marshal.ReadByte(okVal) != 0;
                    if (!ok) break;
                    IntPtr e4 = IntPtr.Zero;
                    IntPtr curPtr = il2cpp_runtime_invoke(getCur, it, IntPtr.Zero, ref e4);
                    if (e4 != IntPtr.Zero || curPtr == IntPtr.Zero) continue;
                    IntPtr curVal = il2cpp_object_unbox(curPtr);
                    if (curVal == IntPtr.Zero) continue;
                    int v = Marshal.ReadInt32(curVal);
                    result.Add(v);
                    // Safety: bound the loop in case something pathological happens.
                    if (result.Count > 50) break;
                }
            }
            catch { }
            return result;
        }

        /// <summary>
        /// Invoke a method with int and optional bool args. Uses unmanaged
        /// HGlobal buffers (the working pattern from Battle.cs's getItem(int)
        /// invocation) — pinned managed arrays don't survive correctly across
        /// the IL2CPP runtime_invoke boundary on this binding.
        /// </summary>
        private string InvokeIntArgMethod(IntPtr ctxObj, IntPtr ctxClass,
                                          string methodName, int paramCount, int heroId,
                                          bool secondBoolArg = false, bool secondVal = false)
        {
            IntPtr method = FindClassMethodByName(ctxClass, methodName, paramCount);
            if (method == IntPtr.Zero)
                return "{\"error\":\"" + Esc(methodName) + "(" + paramCount
                    + " params) not found on squad context\"}";

            // Try TWO layouts in sequence:
            //   POINTER LAYOUT:  argsArr[i] = pointer to value buffer
            //                    (Battle.cs getItem(int) uses this)
            //   INLINE LAYOUT:   argsArr[i] = the value, 8 bytes (zero/sign-extended)
            // Both are documented for different IL2CPP wrappers; we try the
            // first, and if it throws "no value (HeroType) for given key" with
            // a likely-pointer key (huge negative or > 1M), fall back to inline.
            string callOnceWithLayout(bool inlineLayout)
            {
                IntPtr intBuf = IntPtr.Zero, boolBuf = IntPtr.Zero, argsArr = IntPtr.Zero;
                try
                {
                    if (inlineLayout)
                    {
                        argsArr = System.Runtime.InteropServices.Marshal.AllocHGlobal(IntPtr.Size * paramCount);
                        // Each slot is 8 bytes; write the int value into the
                        // low 4 bytes (zero-extended), bool into next slot.
                        System.Runtime.InteropServices.Marshal.WriteInt64(argsArr, (long)heroId);
                        if (secondBoolArg)
                            System.Runtime.InteropServices.Marshal.WriteInt64(argsArr, IntPtr.Size, secondVal ? 1L : 0L);
                    }
                    else
                    {
                        intBuf = System.Runtime.InteropServices.Marshal.AllocHGlobal(4);
                        boolBuf = secondBoolArg
                            ? System.Runtime.InteropServices.Marshal.AllocHGlobal(4) : IntPtr.Zero;
                        argsArr = System.Runtime.InteropServices.Marshal.AllocHGlobal(IntPtr.Size * paramCount);
                        System.Runtime.InteropServices.Marshal.WriteInt32(intBuf, heroId);
                        if (secondBoolArg)
                            System.Runtime.InteropServices.Marshal.WriteInt32(boolBuf, secondVal ? 1 : 0);
                        System.Runtime.InteropServices.Marshal.WriteIntPtr(argsArr, intBuf);
                        if (secondBoolArg)
                            System.Runtime.InteropServices.Marshal.WriteIntPtr(argsArr, IntPtr.Size, boolBuf);
                    }

                    IntPtr exc = IntPtr.Zero;
                    il2cpp_runtime_invoke(method, ctxObj, argsArr, ref exc);
                    if (exc != IntPtr.Zero)
                    {
                        string excMsg = "(no detail)";
                        try
                        {
                            IntPtr excClass = il2cpp_object_get_class(exc);
                            IntPtr getMsg = FindClassMethodByName(excClass, "get_Message", 0);
                            if (getMsg != IntPtr.Zero)
                            {
                                IntPtr exc2 = IntPtr.Zero;
                                IntPtr msgPtr = il2cpp_runtime_invoke(getMsg, exc, IntPtr.Zero, ref exc2);
                                if (msgPtr != IntPtr.Zero)
                                {
                                    string mg = Il2CppInterop.Runtime.IL2CPP.Il2CppStringToManaged(msgPtr);
                                    if (!string.IsNullOrEmpty(mg)) excMsg = mg;
                                }
                            }
                        }
                        catch { }
                        return excMsg;
                    }
                    return null;
                }
                finally
                {
                    if (intBuf != IntPtr.Zero) System.Runtime.InteropServices.Marshal.FreeHGlobal(intBuf);
                    if (boolBuf != IntPtr.Zero) System.Runtime.InteropServices.Marshal.FreeHGlobal(boolBuf);
                    if (argsArr != IntPtr.Zero) System.Runtime.InteropServices.Marshal.FreeHGlobal(argsArr);
                }
            }

            // Pointer layout first (matches Battle.cs).
            string err = callOnceWithLayout(false);
            if (err == null) return null;
            // If the failure mentions the magic "no value (HeroType) for given
            // key" pattern with a value that's clearly a heap pointer (millions
            // or negative), retry with inline.
            bool looksLikePointerLeak = err.Contains("no value")
                && err.Contains("for given key");
            if (!looksLikePointerLeak)
            {
                Logger.LogWarning("[Squad] " + methodName + " threw: " + err);
                return "{\"error\":\"" + Esc(methodName) + " threw: " + Esc(err) + "\"}";
            }
            Logger.LogInfo("[Squad] " + methodName + " pointer-layout failed (" + err
                + "); retrying inline layout");
            string err2 = callOnceWithLayout(true);
            if (err2 == null) return null;
            Logger.LogWarning("[Squad] " + methodName + " inline layout also failed: " + err2);
            return "{\"error\":\"" + Esc(methodName) + " threw (both layouts): "
                + Esc(err) + " | " + Esc(err2) + "\"}";
        }

        // =====================================================
        // DIAGNOSTICS: stage history
        //
        // Returns the user's BattleResultsByStageId map (stageId -> hit count).
        // Lets us reverse-engineer the StageId encoding for a chapter+stage+
        // difficulty triple by inspecting which IDs the user has battled.
        // Use case: identify the StageId for "Campaign 12-3 Nightmare" so we
        // can call OpenStageCmd(stageId) and skip the manual click-thru.
        // =====================================================
        private string StageHistory()
        {
            try
            {
                var uw = GetUserWrapper();
                if (uw == null) return "{\"error\":\"Not logged in\"}";
                // user.Stages.StageData (UpdatableUserStageData) wraps UserStageData.
                var stages = Prop(uw, "Stages");
                if (stages == null) return "{\"error\":\"Stages wrapper null\"}";
                // Walk the parent for StageData (protected field on StageWrapperReadOnly).
                object stageData = null;
                try { stageData = Prop(stages, "StageData"); } catch { }
                if (stageData == null)
                {
                    // The protected field needs reflection on the type hierarchy.
                    var t = stages.GetType();
                    while (t != null)
                    {
                        var f = t.GetField("StageData", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
                        if (f != null) { stageData = f.GetValue(stages); break; }
                        var p = t.GetProperty("StageData", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
                        if (p != null) { stageData = p.GetValue(stages); break; }
                        t = t.BaseType;
                    }
                }
                if (stageData == null) return "{\"error\":\"StageData not accessible\"}";
                // BattleResultsByStageId is also exposed as a property on the readonly wrapper.
                object battleResults = null;
                try { battleResults = Prop(stages, "BattleResultsByStageId"); } catch { }
                if (battleResults == null)
                {
                    try { battleResults = Prop(stageData, "BattleResultsByStageId"); } catch { }
                }
                if (battleResults == null) return "{\"error\":\"BattleResultsByStageId not accessible\"}";

                var sb = new StringBuilder("{\"ok\":true,\"results\":[");
                bool first = true;
                int count = 0;
                // IL2Cpp dicts don't expose a managed-reflection-friendly
                // GetEnumerator over KeyValuePair. Zip Keys + Values instead.
                var keysProp = battleResults.GetType().GetProperty("Keys");
                var valsProp = battleResults.GetType().GetProperty("Values");
                if (keysProp == null || valsProp == null)
                    return "{\"error\":\"Keys/Values not on results dict\"}";
                var keysObj = keysProp.GetValue(battleResults);
                var valsObj = valsProp.GetValue(battleResults);
                var kIter = keysObj?.GetType().GetMethod("GetEnumerator");
                var vIter = valsObj?.GetType().GetMethod("GetEnumerator");
                if (kIter == null || vIter == null)
                    return "{\"error\":\"key/value enumerators not available\"}";
                var kEn = kIter.Invoke(keysObj, null);
                var vEn = vIter.Invoke(valsObj, null);
                var kMove = kEn.GetType().GetMethod("MoveNext");
                var vMove = vEn.GetType().GetMethod("MoveNext");
                var kCur = kEn.GetType().GetProperty("Current");
                var vCur = vEn.GetType().GetProperty("Current");
                while (kMove != null && vMove != null
                       && (bool)kMove.Invoke(kEn, null)
                       && (bool)vMove.Invoke(vEn, null))
                {
                    int stageId = 0;
                    int passes = 0;
                    try { stageId = (int)kCur.GetValue(kEn); } catch { }
                    var stats = vCur.GetValue(vEn);
                    if (stats != null)
                    {
                        try { passes = IntProp(stats, "PassedCount"); } catch { }
                        if (passes == 0)
                        {
                            try { var p = (bool)stats.GetType().GetProperty("Passed").GetValue(stats); passes = p ? 1 : 0; } catch { }
                        }
                    }
                    if (!first) sb.Append(",");
                    sb.Append("{\"id\":" + stageId + ",\"passed\":" + passes + "}");
                    first = false;
                    count++;
                    if (count >= 5000) break;
                }
                sb.Append("],\"count\":" + count + "}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // =====================================================
        // /finish-edit-team — From the BattleFinishStoryDialog (or other
        // finish-dialog variants), invokes OpenSelectionDialog which closes
        // the finish dialog and re-opens StoryHeroesSelectionDialog with
        // the same squad. Equivalent to clicking the in-game "Edit Team"
        // button. After this lands, /squad-set works again because the
        // battle-setup dialog is back in the scene tree.
        // =====================================================
        private string FinishEditTeam()
        {
            try
            {
                var dialogsRoot = GameObject.Find("UIManager/Canvas (Ui Root)/Dialogs");
                if (dialogsRoot == null) return "{\"error\":\"no Dialogs root\"}";
                // Find the active BattleFinish dialog (Story / Campaign / etc.).
                Transform finishDlg = null;
                for (int di = 0; di < dialogsRoot.transform.childCount; di++)
                {
                    var d = dialogsRoot.transform.GetChild(di);
                    if (!d.gameObject.activeSelf) continue;
                    if (d.gameObject.name.Contains("BattleFinish"))
                    {
                        finishDlg = d;
                        break;
                    }
                }
                if (finishDlg == null) return "{\"error\":\"no active BattleFinish dialog\"}";

                // BFS the dialog tree for any MonoBehaviour whose Context is
                // a BattleFinishStorylineDialogContext (or similar). Then
                // call OpenSelectionDialog on it (any arity).
                var queue = new Queue<Transform>();
                queue.Enqueue(finishDlg);
                int searched = 0;
                while (queue.Count > 0 && searched < 600)
                {
                    var t = queue.Dequeue();
                    searched++;
                    foreach (var mono in t.gameObject.GetComponents<MonoBehaviour>())
                    {
                        if (mono == null) continue;
                        try
                        {
                            IntPtr monoPtr = mono.Pointer;
                            if (monoPtr == IntPtr.Zero) continue;
                            IntPtr monoClass = il2cpp_object_get_class(monoPtr);
                            // Find get_Context.
                            IntPtr getCtx = IntPtr.Zero;
                            IntPtr ck = monoClass;
                            while (ck != IntPtr.Zero && getCtx == IntPtr.Zero)
                            {
                                IntPtr mIter = IntPtr.Zero;
                                IntPtr m;
                                while ((m = il2cpp_class_get_methods(ck, ref mIter)) != IntPtr.Zero)
                                {
                                    string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                                    if (mn == "get_Context" && il2cpp_method_get_param_count(m) == 0)
                                    {
                                        getCtx = m;
                                        break;
                                    }
                                }
                                if (getCtx == IntPtr.Zero) ck = il2cpp_class_get_parent(ck);
                            }
                            if (getCtx == IntPtr.Zero) continue;

                            IntPtr exc = IntPtr.Zero;
                            IntPtr ctxObj = il2cpp_runtime_invoke(getCtx, monoPtr, IntPtr.Zero, ref exc);
                            if (exc != IntPtr.Zero || ctxObj == IntPtr.Zero) continue;
                            IntPtr ctxClass = il2cpp_object_get_class(ctxObj);
                            if (ctxClass == IntPtr.Zero) continue;

                            // Filter to BattleFinish*DialogContext.
                            string ctxName = Marshal.PtrToStringAnsi(il2cpp_class_get_name(ctxClass)) ?? "";
                            if (!ctxName.Contains("BattleFinish")) continue;

                            // Find OpenSelectionDialog (any arity, walk parents).
                            IntPtr openMethod = IntPtr.Zero;
                            int openArity = -1;
                            IntPtr scan = ctxClass;
                            while (scan != IntPtr.Zero && openMethod == IntPtr.Zero)
                            {
                                IntPtr mIter = IntPtr.Zero;
                                IntPtr m;
                                while ((m = il2cpp_class_get_methods(scan, ref mIter)) != IntPtr.Zero)
                                {
                                    string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                                    if (mn == "OpenSelectionDialog")
                                    {
                                        openMethod = m;
                                        openArity = (int)il2cpp_method_get_param_count(m);
                                        break;
                                    }
                                }
                                if (openMethod == IntPtr.Zero) scan = il2cpp_class_get_parent(scan);
                            }
                            if (openMethod == IntPtr.Zero) continue;

                            // CRASH GUARD: only invoke 0-arg overloads. The 1-arg
                            // OpenSelectionDialog needs a State object — passing null
                            // crashes the game (verified). For the non-zero-arity
                            // case we'd need a real state value.
                            if (openArity != 0)
                            {
                                Logger.LogWarning("[Finish] OpenSelectionDialog has "
                                    + openArity + " args — skipping (need state object)");
                                return "{\"error\":\"OpenSelectionDialog requires arity-"
                                    + openArity + " args; only 0-arg supported\"}";
                            }
                            IntPtr argsArr = IntPtr.Zero;
                            IntPtr exc2 = IntPtr.Zero;
                            try
                            {
                                il2cpp_runtime_invoke(openMethod, ctxObj, argsArr, ref exc2);
                            }
                            finally
                            {
                                if (argsArr != IntPtr.Zero) Marshal.FreeHGlobal(argsArr);
                            }
                            if (exc2 != IntPtr.Zero)
                            {
                                string excMsg = "(no detail)";
                                try
                                {
                                    IntPtr excClass = il2cpp_object_get_class(exc2);
                                    IntPtr getMsg = FindClassMethodByName(excClass, "get_Message", 0);
                                    if (getMsg != IntPtr.Zero)
                                    {
                                        IntPtr exc3 = IntPtr.Zero;
                                        IntPtr msgPtr = il2cpp_runtime_invoke(getMsg, exc2, IntPtr.Zero, ref exc3);
                                        if (msgPtr != IntPtr.Zero)
                                        {
                                            string mg = Il2CppInterop.Runtime.IL2CPP.Il2CppStringToManaged(msgPtr);
                                            if (!string.IsNullOrEmpty(mg)) excMsg = mg;
                                        }
                                    }
                                }
                                catch { }
                                return "{\"error\":\"OpenSelectionDialog threw: " + Esc(excMsg) + "\"}";
                            }
                            Logger.LogInfo("[Finish] OpenSelectionDialog invoked on " + ctxName
                                + " (arity " + openArity + ")");
                            return "{\"ok\":true,\"context\":\"" + Esc(ctxName)
                                + "\",\"arity\":" + openArity + "}";
                        }
                        catch { }
                    }
                    for (int ci = 0; ci < t.childCount && ci < 40; ci++)
                        queue.Enqueue(t.GetChild(ci));
                }
                return "{\"error\":\"no BattleFinish*DialogContext.OpenSelectionDialog found\"}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        private string SquadCurrent()
        {
            try
            {
                var (ctxObj, ctxClass) = FindActiveSquadContext();
                if (ctxObj == IntPtr.Zero)
                    return "{\"error\":\"no active battle-setup squad\"}";
                var ids = ReadCurrentSquadHeroIds(ctxObj, ctxClass);
                return "{\"ok\":true,\"hero_ids\":[" + string.Join(",", ids) + "]}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        /// <summary>
        /// Find a Hero IL2CPP object by hero instance id, by walking the
        /// user's Heroes.HeroData.HeroById dictionary. Returns IntPtr.Zero
        /// if not found. We use raw IL2CPP because managed reflection
        /// fights us on IL2Cpp generic Dictionary.
        /// </summary>
        private IntPtr FindHeroObjectById(int heroId)
        {
            try
            {
                var uw = GetUserWrapper();
                if (uw == null) return IntPtr.Zero;
                var heroes = Prop(uw, "Heroes");
                var heroData = Prop(heroes, "HeroData");
                var heroDict = Prop(heroData, "HeroById");
                if (heroDict == null) return IntPtr.Zero;
                foreach (var h in DictValues(heroDict))
                {
                    if (h == null) continue;
                    if (IntProp(h, "Id") == heroId)
                    {
                        if (h is Il2CppSystem.Object il2obj) return il2obj.Pointer;
                        return IntPtr.Zero;
                    }
                }
            }
            catch { }
            return IntPtr.Zero;
        }

        /// <summary>
        /// Invoke AddHero(Hero hero, bool showHeroFuse) on the squad context.
        /// HeroesSquadContext`1.AddHero(int,bool) does NOT exist — that
        /// overload is on IterativeHeroSquadContext, a totally different class.
        /// HeroesSquadContext only has AddHero(Hero,bool) and AddHero(HeroType).
        /// </summary>
        private string SquadInvokeAddHero(IntPtr ctxObj, IntPtr ctxClass, int heroId)
        {
            IntPtr heroObj = FindHeroObjectById(heroId);
            if (heroObj == IntPtr.Zero)
                return "{\"error\":\"hero id " + heroId + " not in user roster\"}";

            // Find AddHero(Hero, bool) — 2 params, first param is reference
            // type (Hero). We look it up by name + count + parameter-type-name
            // matching for safety.
            IntPtr method = IntPtr.Zero;
            IntPtr scan = ctxClass;
            while (scan != IntPtr.Zero && method == IntPtr.Zero)
            {
                IntPtr mIter = IntPtr.Zero;
                IntPtr m;
                while ((m = il2cpp_class_get_methods(scan, ref mIter)) != IntPtr.Zero)
                {
                    string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                    if (mn != "AddHero" || il2cpp_method_get_param_count(m) != 2)
                        continue;
                    // First param should be Hero (reference type). Without a
                    // direct il2cpp_method_get_param_type C# wrapper, we trust
                    // the count + class lookup since HeroesSquadContext only
                    // has one 2-param AddHero.
                    method = m;
                    break;
                }
                scan = il2cpp_class_get_parent(scan);
            }
            if (method == IntPtr.Zero)
                return "{\"error\":\"AddHero(Hero,bool) not found on squad class\"}";

            // Args: [pointer-to-Hero-pointer, pointer-to-bool-buffer]. Reference
            // type args are POINTERS TO POINTERS in the IL2CPP runtime_invoke
            // convention; value type args are pointers to value buffers.
            IntPtr heroPtrSlot = System.Runtime.InteropServices.Marshal.AllocHGlobal(IntPtr.Size);
            IntPtr boolBuf = System.Runtime.InteropServices.Marshal.AllocHGlobal(4);
            IntPtr argsArr = System.Runtime.InteropServices.Marshal.AllocHGlobal(IntPtr.Size * 2);
            try
            {
                System.Runtime.InteropServices.Marshal.WriteIntPtr(heroPtrSlot, heroObj);
                System.Runtime.InteropServices.Marshal.WriteInt32(boolBuf, 0);
                System.Runtime.InteropServices.Marshal.WriteIntPtr(argsArr, heroObj);  // direct hero pointer
                System.Runtime.InteropServices.Marshal.WriteIntPtr(argsArr, IntPtr.Size, boolBuf);

                IntPtr exc = IntPtr.Zero;
                il2cpp_runtime_invoke(method, ctxObj, argsArr, ref exc);
                if (exc != IntPtr.Zero)
                {
                    string excMsg = "(no detail)";
                    try
                    {
                        IntPtr excClass = il2cpp_object_get_class(exc);
                        IntPtr getMsg = FindClassMethodByName(excClass, "get_Message", 0);
                        if (getMsg != IntPtr.Zero)
                        {
                            IntPtr exc2 = IntPtr.Zero;
                            IntPtr msgPtr = il2cpp_runtime_invoke(getMsg, exc, IntPtr.Zero, ref exc2);
                            if (msgPtr != IntPtr.Zero)
                            {
                                string mg = Il2CppInterop.Runtime.IL2CPP.Il2CppStringToManaged(msgPtr);
                                if (!string.IsNullOrEmpty(mg)) excMsg = mg;
                            }
                        }
                    }
                    catch { }
                    Logger.LogWarning("[Squad] AddHero(Hero,bool) threw: " + excMsg);
                    return "{\"error\":\"AddHero threw: " + Esc(excMsg) + "\"}";
                }
                return null;
            }
            finally
            {
                System.Runtime.InteropServices.Marshal.FreeHGlobal(heroPtrSlot);
                System.Runtime.InteropServices.Marshal.FreeHGlobal(boolBuf);
                System.Runtime.InteropServices.Marshal.FreeHGlobal(argsArr);
            }
        }

        private string SquadAdd(string heroIdStr)
        {
            if (!int.TryParse(heroIdStr, out int heroId))
                return "{\"error\":\"hero_id (int) required\"}";
            var (ctxObj, ctxClass) = FindActiveSquadContext();
            if (ctxObj == IntPtr.Zero)
                return "{\"error\":\"no active battle-setup squad\"}";
            var err = SquadInvokeAddHero(ctxObj, ctxClass, heroId);
            if (err != null) return err;
            return "{\"ok\":true,\"added\":" + heroId + "}";
        }

        private string SquadRemove(string heroIdStr)
        {
            if (!int.TryParse(heroIdStr, out int heroId))
                return "{\"error\":\"hero_id (int) required\"}";
            var (ctxObj, ctxClass) = FindActiveSquadContext();
            if (ctxObj == IntPtr.Zero)
                return "{\"error\":\"no active battle-setup squad\"}";
            // RemoveHero(int) IS on the generic HeroesSquadContext as a 1-arg
            // method. Different from AddHero — both squads have RemoveHero(int).
            var err = InvokeIntArgMethod(ctxObj, ctxClass, "RemoveHero", 1, heroId);
            if (err != null) return err;
            return "{\"ok\":true,\"removed\":" + heroId + "}";
        }

        private string SquadClear()
        {
            try
            {
                var (ctxObj, ctxClass) = FindActiveSquadContext();
                if (ctxObj == IntPtr.Zero)
                    return "{\"error\":\"no active battle-setup squad\"}";
                var current = ReadCurrentSquadHeroIds(ctxObj, ctxClass);
                int removed = 0;
                foreach (int hid in current)
                {
                    var err = InvokeIntArgMethod(ctxObj, ctxClass, "RemoveHero", 1, hid);
                    if (err == null) removed++;
                }
                return "{\"ok\":true,\"removed\":" + removed + "}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        private string SquadSet(string idsCsv)
        {
            if (string.IsNullOrEmpty(idsCsv))
                return "{\"error\":\"ids (csv of hero ids) required\"}";
            var heroIds = new List<int>();
            foreach (var p in idsCsv.Split(','))
            {
                var s = p.Trim();
                if (string.IsNullOrEmpty(s)) continue;
                if (!int.TryParse(s, out int id))
                    return "{\"error\":\"ids must be int csv: " + Esc(s) + "\"}";
                heroIds.Add(id);
            }
            try
            {
                var (ctxObj, ctxClass) = FindActiveSquadContext();
                if (ctxObj == IntPtr.Zero)
                    return "{\"error\":\"no active battle-setup squad\"}";

                // Diff-based set: remove only heroes that aren't in the
                // target list, add only target heroes that aren't already
                // in the squad. This avoids unnecessary churn AND avoids
                // re-adding heroes whose AddHero is rejected by game logic
                // (e.g. Faction Guardians) — if a guardian is already in
                // the squad as the carry, she stays untouched.
                var current = ReadCurrentSquadHeroIds(ctxObj, ctxClass);
                var targetSet = new HashSet<int>(heroIds);
                var currentSet = new HashSet<int>(current);

                int removed = 0;
                foreach (int hid in current)
                {
                    if (targetSet.Contains(hid)) continue;
                    var err = InvokeIntArgMethod(ctxObj, ctxClass, "RemoveHero", 1, hid);
                    if (err == null) removed++;
                }

                var added = new List<int>();
                var seen = new HashSet<int>();
                foreach (int hid in heroIds)
                {
                    if (!seen.Add(hid)) continue;
                    if (currentSet.Contains(hid)) continue;
                    var err = SquadInvokeAddHero(ctxObj, ctxClass, hid);
                    if (err == null) added.Add(hid);
                }
                return "{\"ok\":true,\"removed\":" + removed
                       + ",\"added\":[" + string.Join(",", added)
                       + "],\"already_present\":[" + string.Join(",",
                            current.FindAll(h => targetSet.Contains(h))) + "]}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }
    }
}
