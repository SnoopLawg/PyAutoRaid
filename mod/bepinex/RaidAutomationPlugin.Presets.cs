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

                // 2. Use BattlePresetSettings.DefaultPreset(int[] heroes, int presetId)
                //    to build a FULLY-INITIALIZED preset (heroes + default skill
                //    priorities + correct sequences-per-round). This is the same
                //    public factory the in-game Save Current Team button reaches
                //    through QuickCreatePresetImpl. Avoids the silent-Validate-
                //    fail trap where our manually-built SkillPrioritiesSetup
                //    objects were missing IL2Cpp-side identity bits.
                var bpsT = FindType("Client.ViewModel.Contextes.BattlePresetSettingsOverlay.BattlePresetSettings");
                if (bpsT == null) return "{\"error\":\"BattlePresetSettings type not found\"}";
                var defaultPresetM = bpsT.GetMethod("DefaultPreset",
                    BindingFlags.Public | BindingFlags.Static);
                if (defaultPresetM == null)
                    return "{\"error\":\"BattlePresetSettings.DefaultPreset method not found\"}";

                // DefaultPreset's first parameter is an IL2Cpp int[] —
                // managed int[] doesn't auto-marshal, must wrap in
                // Il2CppStructArray<int> so Il2CppInterop can pass the
                // pointer to the IL2Cpp side correctly.
                int[] managedArr = emptyOnly ? new int[0] : heroIds.ToArray();
                var heroIdsArr = new Il2CppInterop.Runtime.InteropTypes.Arrays.Il2CppStructArray<int>(managedArr);
                object preset;
                try { preset = defaultPresetM.Invoke(null, new object[] { heroIdsArr, newId }); }
                catch (TargetInvocationException tex) {
                    return "{\"error\":\"DefaultPreset failed: " + Esc((tex.InnerException ?? tex).Message) + "\"}";
                }
                if (preset == null) return "{\"error\":\"DefaultPreset returned null\"}";
                sb.Append(",\"strategy\":\"defaultPreset\"");

                // 3. Override Name (DefaultPreset gives "New Team N").
                SetFieldOrProp(presetT, preset, "Name", presetName);
                SetFieldOrProp(presetT, preset, "NameIsNotDefault", true);

                // 4. (No manual setup-building needed — DefaultPreset already
                //    populated SkillPrioritiesSetups with valid entries.)
                sb.Append("},\"heroes\":[");
                bool first = true;
                foreach (int heroId in (emptyOnly ? new int[0] : (IEnumerable<int>)heroIds))
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
                    sb.Append(first ? "" : ",");
                    first = false;
                    sb.Append("{\"id\":").Append(heroId).Append(",\"ok\":true}");
                }
                sb.Append("]");

                // 5. Add the new preset to the local HeroesAiPresets
                //    list BEFORE dispatching SaveAiPresetCmd. The game
                //    normally does both on success; the local list is
                //    what the in-game Saved Team Presets dialog reads.
                //    Without this step the preset shows in /presets
                //    (mod reads HeroesAiPresets too) but NOT in the UI,
                //    AND the SaveAiPresetCmd has no anchor and silently
                //    fails server-side persistence.
                bool addedToList = false;
                try {
                    object presetListObj = Prop(Prop(Prop(uw, "Heroes"), "HeroData"), "HeroesAiPresets")
                                       ?? Prop(Prop(uw, "Heroes"), "HeroesAiPresets");
                    if (presetListObj != null) {
                        var addM = presetListObj.GetType().GetMethod("Add");
                        if (addM != null) {
                            addM.Invoke(presetListObj, new object[] { preset });
                            addedToList = true;
                        }
                    }
                } catch (Exception addEx) {
                    sb.Append(",\"addError\":\"").Append(Esc(addEx.Message)).Append("\"");
                }
                sb.Append(",\"addedToList\":").Append(addedToList ? "true" : "false");

                // 6. Save via SaveAiPresetCmd (same path as
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

            // starters format: heroId:r1_sid,r2_sid,r3_sid;heroId:...
            // Each comma-separated value is the starter for that round
            // (1-indexed by position). Empty token OR 0 = leave that
            // round's starter unchanged. The downstream applier reads
            // this list positionally per Sequence (R1=[0], R2=[1], ...).
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
                        // Empty token preserves position with sentinel 0.
                        if (int.TryParse(sk.Trim(), out int sid)) list.Add(sid);
                        else list.Add(0);
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

                    // Apply StarterSkillIds per round.
                    // starters[heroId] is the parsed comma-separated list from the
                    // CLI. Interpretation: each token = the starter for that round
                    // (token <= 0 means "leave unchanged"). E.g. "67402,0,67403"
                    // sets R1=A2, R2 unchanged, R3=A3. This is the per-round
                    // schedule HH's data captures and Dragon-style multi-round
                    // dungeons need to survive (e.g. save Mithrala A3 for R3).
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
                                var startersForHero = starters[heroId];
                                int rIdx = 0;
                                foreach (var seq in ListItems(seqsForStarter))
                                {
                                    if (rIdx >= startersForHero.Count) break;
                                    int sidForRound = startersForHero[rIdx];
                                    rIdx++;
                                    if (sidForRound <= 0) continue; // leave unchanged
                                    var listField = seq.GetType().GetField("StarterSkillIds", BindingFlags.Public | BindingFlags.Instance);
                                    var listProp = seq.GetType().GetProperty("StarterSkillIds");
                                    object listObj = null;
                                    if (listField != null) listObj = listField.GetValue(seq);
                                    if (listObj == null && listProp != null) listObj = listProp.GetValue(seq);
                                    if (listObj == null)
                                    {
                                        // Fresh preset Sequences have null StarterSkillIds.
                                        // Create the matching List<int> type via the property's
                                        // declared type (Il2Cpp List<int> wrapper).
                                        Type listT = listField?.FieldType ?? listProp?.PropertyType;
                                        if (listT != null)
                                        {
                                            try
                                            {
                                                listObj = Activator.CreateInstance(listT);
                                                listField?.SetValue(seq, listObj);
                                                listProp?.SetValue(seq, listObj);
                                            }
                                            catch (Exception ex) { Logger.LogWarning("PRESET starter list-create: " + ex.Message); }
                                        }
                                    }
                                    if (listObj != null)
                                    {
                                        var t = listObj.GetType();
                                        t.GetMethod("Clear")?.Invoke(listObj, null);
                                        var add = t.GetMethod("Add");
                                        add?.Invoke(listObj, new object[] { sidForRound });
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
        // API: /hero-fragments[?type=N] — owned hero fragments.
        // Without type: returns full dict { typeId: {amount, required} }.
        // With type=N: returns just that hero's record.
        //
        // Walks UserWrapper.Heroes.HeroParts.HeroPartsByTypeIds
        // (Dictionary<int, HeroPartsData>) where each entry has
        // Amount + RequiredAmount on the HeroPartsData record.
        // =====================================================
        private string GetHeroFragments(string typeStr)
        {
            try
            {
                int filterType = 0;
                if (!string.IsNullOrEmpty(typeStr)) int.TryParse(typeStr, out filterType);

                var uw = GetUserWrapper();
                if (uw == null) return "{\"error\":\"Not logged in\"}";

                var heroes = Prop(uw, "Heroes");
                // The actual fragment counts live on UserHeroData.HeroParts
                // (raw Dictionary<int,int>: typeId -> amount). The
                // HeroPartsWrapper exposes a view but its HeroPartsByTypeIds
                // reads Amount/Required from HeroPartsData records which
                // were all zeroed (lazy-init or stale).
                var heroData = Prop(heroes, "HeroData");
                if (heroData == null) return "{\"error\":\"Heroes.HeroData not found\"}";
                var byType = Prop(heroData, "HeroParts");
                if (byType == null) return "{\"error\":\"HeroData.HeroParts dict not found\"}";

                // Also surface fuse requirement for target hero (if any).
                int requiredForFuse = 0;
                if (filterType > 0)
                {
                    try
                    {
                        var fuseInfos = Prop(heroData, "FuseInfosByOutputHeroId");
                        if (fuseInfos != null)
                        {
                            var fdt = fuseInfos.GetType();
                            var contains = fdt.GetMethod("ContainsKey");
                            if (contains != null && (bool)contains.Invoke(fuseInfos, new object[] { filterType }))
                            {
                                var info = fdt.GetProperty("Item")?.GetValue(fuseInfos, new object[] { filterType });
                                if (info != null)
                                {
                                    try { requiredForFuse = Convert.ToInt32(Prop(info, "RequiredHeroPartsCount")); } catch { }
                                    if (requiredForFuse == 0)
                                    {
                                        try { requiredForFuse = Convert.ToInt32(Prop(info, "RequiredAmount")); } catch { }
                                    }
                                }
                            }
                        }
                    }
                    catch { }
                }

                var sb = new StringBuilder();
                sb.Append("{\"ok\":true,\"fragments\":{");
                bool first = true;
                int matchedAmount = -1;

                var dt = byType.GetType();
                var getEnum = dt.GetMethod("GetEnumerator");
                var en = getEnum?.Invoke(byType, null);
                if (en != null)
                {
                    var moveNext = en.GetType().GetMethod("MoveNext");
                    var current = en.GetType().GetProperty("Current");
                    while ((bool)moveNext.Invoke(en, null))
                    {
                        var kvp = current.GetValue(en);
                        int tid = 0;
                        try { tid = Convert.ToInt32(Prop(kvp, "Key")); } catch { }
                        int amount = 0;
                        try { amount = Convert.ToInt32(Prop(kvp, "Value")); } catch { }
                        if (filterType > 0 && tid != filterType) continue;
                        if (filterType > 0) matchedAmount = amount;
                        if (!first) sb.Append(",");
                        sb.Append("\"" + tid + "\":" + amount);
                        first = false;
                    }
                }
                sb.Append("}");
                if (filterType > 0)
                {
                    sb.Append(",\"type\":" + filterType);
                    sb.Append(",\"amount\":" + (matchedAmount < 0 ? 0 : matchedAmount));
                    sb.Append(",\"required_for_fuse\":" + requiredForFuse);
                }
                sb.Append("}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // =====================================================
        // API: /cb-quick-battle           — read current state
        //      /cb-quick-battle?value=false — set state
        //
        // Reads / writes _isQuickBattleEnabled on the active
        // HeroesSelectionAllianceBossDialogContext (dump.cs L127614).
        // The dialog's StartBattle override branches on this flag —
        // when ON, the in-game flow dispatches PlayQuickBattleCmd
        // which finishes the battle server-side instantly, skipping
        // the BattleScene transition that cb_run.py's polling loop
        // requires. cb_run MUST disable this before StartBattle.
        //
        // To stay reactive-binding-safe, also flip the checkbox
        // context's _active BoolProperty (the upstream source).
        // Direct _value byte write — fires no notification, but
        // StartBattle reads Value off the same byte so it's
        // sufficient for our purpose. UI checkbox visual may not
        // reflect the change until the next reactive cycle.
        // =====================================================
        private string CbQuickBattle(string valueStr)
        {
            try
            {
                var dialogsRoot = GameObject.Find("UIManager/Canvas (Ui Root)/Dialogs");
                if (dialogsRoot == null) return "{\"error\":\"no Dialogs root in scene\"}";

                IntPtr ctxObj = IntPtr.Zero;
                IntPtr ctxClass = IntPtr.Zero;
                string ctxClassName = null, ctxNs = null;
                string dialogName = null;

                for (int di = 0; di < dialogsRoot.transform.childCount && ctxObj == IntPtr.Zero; di++)
                {
                    var dialog = dialogsRoot.transform.GetChild(di);
                    if (!dialog.gameObject.activeSelf) continue;
                    if (TryFindHeroesSelectionContext(dialog, out ctxObj, out ctxClass, out ctxClassName, out ctxNs))
                        dialogName = dialog.gameObject.name;
                }

                if (ctxObj == IntPtr.Zero)
                    return "{\"error\":\"no active HeroesSelectionDialog (open the CB battle setup first)\"}";

                // Sanity: only the AllianceBoss subclass has _isQuickBattleEnabled.
                // Other selection dialogs (Story, Dungeon, ...) inherit different fields.
                if (ctxClassName == null
                    || ctxClassName.IndexOf("AllianceBoss", StringComparison.OrdinalIgnoreCase) < 0)
                    return "{\"error\":\"open dialog is not AllianceBoss variant: " + Esc(ctxClassName) + "\"}";

                uint propOff = FindFieldOffset(ctxClass, "_isQuickBattleEnabled");
                if (propOff == uint.MaxValue)
                    return "{\"error\":\"_isQuickBattleEnabled field not found on " + Esc(ctxClassName) + "\"}";

                IntPtr boolPropPtr = Marshal.ReadIntPtr(ctxObj, (int)propOff);
                if (boolPropPtr == IntPtr.Zero)
                    return "{\"error\":\"_isQuickBattleEnabled BoolProperty is null\"}";

                IntPtr boolPropClass = il2cpp_object_get_class(boolPropPtr);
                uint valueOff = FindFieldOffset(boolPropClass, "_value");
                if (valueOff == uint.MaxValue)
                    return "{\"error\":\"_value field not found on BoolProperty\"}";

                bool currentValue = Marshal.ReadByte(boolPropPtr, (int)valueOff) != 0;

                bool? desired = null;
                if (!string.IsNullOrEmpty(valueStr))
                {
                    string vs = valueStr.ToLowerInvariant();
                    if (vs == "true" || vs == "1" || vs == "on") desired = true;
                    else if (vs == "false" || vs == "0" || vs == "off") desired = false;
                    else return "{\"error\":\"value must be true/false (or 1/0, on/off)\"}";
                }

                bool changed = false;
                if (desired.HasValue && desired.Value != currentValue)
                {
                    // Write the dialog's _isQuickBattleEnabled._value directly.
                    Marshal.WriteByte(boolPropPtr, (int)valueOff, (byte)(desired.Value ? 1 : 0));

                    // Also flip the upstream checkbox's _active BoolProperty so
                    // reactive bindings stay consistent if anything fires before
                    // StartBattle.
                    uint cbOff = FindFieldOffset(ctxClass, "_quickBattleCheckbox");
                    if (cbOff != uint.MaxValue)
                    {
                        IntPtr cbPtr = Marshal.ReadIntPtr(ctxObj, (int)cbOff);
                        if (cbPtr != IntPtr.Zero)
                        {
                            IntPtr cbClass = il2cpp_object_get_class(cbPtr);
                            uint activeOff = FindFieldOffset(cbClass, "_active");
                            if (activeOff != uint.MaxValue)
                            {
                                IntPtr activePropPtr = Marshal.ReadIntPtr(cbPtr, (int)activeOff);
                                if (activePropPtr != IntPtr.Zero)
                                {
                                    IntPtr activeClass = il2cpp_object_get_class(activePropPtr);
                                    uint activeValOff = FindFieldOffset(activeClass, "_value");
                                    if (activeValOff != uint.MaxValue)
                                        Marshal.WriteByte(activePropPtr, (int)activeValOff,
                                                          (byte)(desired.Value ? 1 : 0));
                                }
                            }
                        }
                    }

                    currentValue = Marshal.ReadByte(boolPropPtr, (int)valueOff) != 0;
                    changed = true;
                }

                return "{\"ok\":true,\"enabled\":" + (currentValue ? "true" : "false") +
                       ",\"changed\":" + (changed ? "true" : "false") +
                       ",\"context\":\"" + Esc(ctxClassName) + "\"" +
                       ",\"dialog\":\"" + Esc(dialogName) + "\"}";
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
        // API: /claim-clan-checkin, /claim-gem-mine
        //
        // Generic single-cmd dispatcher: construct a zero-arg cmd
        // by FQN and enqueue via CmdQueue. Used for daily collection
        // tasks that take no parameters server-side.
        //
        // The cmd queue handles validation; if the action isn't
        // available (e.g. mine on cooldown), the server rejects and
        // IfError fires.
        // =====================================================
        private string ClaimByZeroArgCmd(string fqn)
        {
            var cmdType = FindType(fqn);
            if (cmdType == null) return "{\"error\":\"type not found: " + Esc(fqn) + "\"}";
            try
            {
                // Only zero-arg ctors. Cmds that require parameters
                // (TakeAllSessionChestRewardsCmd takes last-claim minutes;
                // CollectAllAvailableRewards14DaysProgramsCmd takes programId)
                // crashed the game when constructed without arguments — never
                // probe-and-pray on that class. Specialized endpoints handle
                // those when we have the right fields.
                var defaultCtor = cmdType.GetConstructor(System.Type.EmptyTypes);
                if (defaultCtor == null)
                    return "{\"error\":\"no zero-arg ctor on " + Esc(fqn) + " (cmd needs parameters)\"}";
                object cmd = defaultCtor.Invoke(null);

                // Wire IfError so server rejection is visible in logs.
                bool[] errored = { false };
                string[] errMsg = { null };
                try
                {
                    var ifErrorM = cmd.GetType().GetMethod("IfError",
                        BindingFlags.Instance | BindingFlags.Public | BindingFlags.FlattenHierarchy,
                        null, new[] { typeof(System.Action) }, null);
                    if (ifErrorM != null)
                    {
                        System.Action errCb = () => {
                            errored[0] = true;
                            errMsg[0] = "server rejected";
                            Logger.LogWarning("[ClaimDaily] " + fqn + " rejected by server");
                        };
                        ifErrorM.Invoke(cmd, new object[] { errCb });
                    }
                }
                catch { }

                Logger.LogInfo("[ClaimDaily] enqueue " + fqn);
                InvokeExecute(cmd);
                return "{\"ok\":true,\"cmd\":\"" + Esc(fqn.Substring(fqn.LastIndexOf('.') + 1)) + "\"}";
            }
            catch (System.Reflection.TargetInvocationException tex)
            {
                return "{\"error\":\"" + Esc((tex.InnerException ?? tex).Message) + "\"}";
            }
            catch (System.Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // =====================================================
        // API: /claim-daily-collect — fire all zero-arg daily cmds
        // in one round-trip. Skips ones whose types aren't loaded.
        // Returns per-cmd success/error so the orchestrator can
        // record per-phase status.
        // =====================================================
        private string ClaimDailyCollect()
        {
            var sb = new StringBuilder();
            sb.Append("{\"results\":[");

            // Only verified-safe zero-arg cmds. The session-chest /
            // daily-program cmds need parameterized fields (last-claim
            // minutes, programId etc.) — firing them with default values
            // crashed the game in testing. They're available as discrete
            // endpoints for hand-driven invocation; skip from the batch.
            string[] zeroArgCmds = new[] {
                "Client.Model.Gameplay.Alliance.Commands.AllianceCheckInCmd",
                "Client.Model.Gameplay.Village.Commands.CollectGemsFromMineCmd",
            };
            int idx = 0;
            for (int i = 0; i < zeroArgCmds.Length; i++, idx++)
            {
                if (idx > 0) sb.Append(",");
                string fqn = zeroArgCmds[i];
                string label = fqn.Substring(fqn.LastIndexOf('.') + 1);
                try
                {
                    string r = ClaimByZeroArgCmd(fqn);
                    sb.Append("{\"cmd\":\"" + Esc(label) + "\",\"result\":" + r + "}");
                }
                catch (System.Exception ex)
                {
                    sb.Append("{\"cmd\":\"" + Esc(label) + "\",\"error\":\"" + Esc(ex.Message) + "\"}");
                }
            }

            // Stateful walks (offers, inbox, quests).
            string[] stateful = new[] { "free_shop_offers", "inbox", "quests" };
            System.Func<string>[] handlers = new System.Func<string>[] {
                () => ClaimFreeShopOffers(),
                () => ClaimInbox(),
                () => ClaimQuests(),
            };
            for (int i = 0; i < stateful.Length; i++, idx++)
            {
                if (idx > 0) sb.Append(",");
                try
                {
                    string r = handlers[i]();
                    sb.Append("{\"cmd\":\"" + Esc(stateful[i]) + "\",\"result\":" + r + "}");
                }
                catch (System.Exception ex)
                {
                    sb.Append("{\"cmd\":\"" + Esc(stateful[i]) + "\",\"error\":\"" + Esc(ex.Message) + "\"}");
                }
            }
            sb.Append("]}");
            return sb.ToString();
        }

        // =====================================================
        // API: /claim-daily-program (Daily 14-Days reward program)
        //
        // CollectAllAvailableRewards14DaysProgramsCmd has fields:
        //   _programId:Int32  — required; pull from
        //                       userWrapper.DailyPrograms.Daily14Days.LastProgramId
        //   _collectedRewardsCallback:Action<...> — optional, leave null
        //   _collectedPointsCallback:Action<...>  — optional, leave null
        // =====================================================
        private string Claim14DaysProgram()
        {
            try
            {
                object uw = GetUserWrapper();
                if (uw == null) return "{\"error\":\"UserWrapper null\"}";
                object dailyPrograms = Prop(uw, "DailyPrograms");
                if (dailyPrograms == null) return "{\"error\":\"DailyPrograms null\"}";

                // DailyProgramsWrapper exposes Daily14Days via TWO properties
                // (Daily14DaysWrapper and Daily14DaysWrapperReadOnly) which
                // makes a bare GetProperty("Daily14Days") ambiguous. Pick
                // the writable wrapper specifically by walking properties.
                object daily14 = null;
                foreach (var p in dailyPrograms.GetType().GetProperties(
                    BindingFlags.Public | BindingFlags.NonPublic |
                    BindingFlags.Instance | BindingFlags.FlattenHierarchy))
                {
                    if (p.Name != "Daily14Days") continue;
                    if (p.PropertyType.Name.Contains("ReadOnly")) continue;
                    try { daily14 = p.GetValue(dailyPrograms); } catch { }
                    if (daily14 != null) break;
                }
                if (daily14 == null) return "{\"error\":\"Daily14Days writable wrapper not found\"}";

                // Walk Daily14Days.Programs to find an active program ID.
                // LastProgramId can be null if the user has never started one,
                // even when a program is currently active (Programs has it).
                int programId = 0;
                int programsSeen = 0;
                object programs = Prop(daily14, "Programs");
                if (programs != null)
                {
                    foreach (var p in ListItems(programs))
                    {
                        if (p == null) continue;
                        programsSeen++;
                        // Each program has an Id or ProgramId field.
                        int pid = TryInt(Prop(p, "Id"));
                        if (pid == 0) pid = TryInt(Prop(p, "ProgramId"));
                        if (pid != 0) { programId = pid; break; }
                    }
                }
                // Fall back to LastProgramId Nullable<int>.
                if (programId == 0)
                {
                    object lastProgIdObj = Prop(daily14, "LastProgramId");
                    if (lastProgIdObj != null)
                    {
                        try { programId = Convert.ToInt32(lastProgIdObj); }
                        catch
                        {
                            object hv = Prop(lastProgIdObj, "HasValue");
                            if (hv is bool h && h)
                            {
                                object v = Prop(lastProgIdObj, "Value");
                                if (v != null)
                                {
                                    try { programId = Convert.ToInt32(v); } catch { }
                                }
                            }
                        }
                    }
                }
                if (programId == 0)
                    return "{\"claimed\":false,\"note\":\"no active 14Days program\",\"programs_seen\":"
                           + programsSeen + "}";

                bool hasPrograms = false;
                try { hasPrograms = (bool)Prop(daily14, "HasPrograms"); } catch { }

                var cmdType = FindType(
                    "Client.Model.Gameplay.DailyRewards.Commands.DailyProgram14Days.CollectAllAvailableRewards14DaysProgramsCmd");
                if (cmdType == null) return "{\"error\":\"cmd type not found\"}";

                var ctor = cmdType.GetConstructor(System.Type.EmptyTypes);
                if (ctor == null) return "{\"error\":\"no zero-arg ctor\"}";
                object cmd = ctor.Invoke(null);

                // _programId is declared on the cmd subclass, but reflection
                // may also find shadowed inherited properties — disambiguate
                // with DeclaredOnly walking up the hierarchy.
                System.Reflection.PropertyInfo pidProp = null;
                var walkT = cmdType;
                while (walkT != null && pidProp == null)
                {
                    try
                    {
                        pidProp = walkT.GetProperty("_programId",
                            BindingFlags.Public | BindingFlags.NonPublic |
                            BindingFlags.Instance | BindingFlags.DeclaredOnly);
                    }
                    catch { }
                    walkT = walkT.BaseType;
                }
                if (pidProp == null) return "{\"error\":\"_programId property not found\"}";
                pidProp.SetValue(cmd, programId);

                try
                {
                    var ifErrorM = cmd.GetType().GetMethod("IfError",
                        BindingFlags.Instance | BindingFlags.Public | BindingFlags.FlattenHierarchy,
                        null, new[] { typeof(System.Action) }, null);
                    if (ifErrorM != null)
                    {
                        int captured = programId;
                        System.Action errCb = () =>
                            Logger.LogWarning("[Claim14Days] server rejected program=" + captured);
                        ifErrorM.Invoke(cmd, new object[] { errCb });
                    }
                }
                catch { }

                Logger.LogInfo("[Claim14Days] enqueue program_id=" + programId);
                InvokeExecute(cmd);
                return "{\"claimed\":true,\"program_id\":" + programId
                       + ",\"has_programs\":" + (hasPrograms ? "true" : "false") + "}";
            }
            catch (System.Reflection.TargetInvocationException tex)
            {
                var inner = tex.InnerException ?? tex;
                Logger.LogWarning("[Claim14Days] " + inner.GetType().Name + ": " + inner.Message
                                  + "\n" + inner.StackTrace);
                return "{\"error\":\"" + Esc(inner.GetType().Name + ": " + inner.Message) + "\"}";
            }
            catch (Exception ex)
            {
                Logger.LogWarning("[Claim14Days] " + ex.GetType().Name + ": " + ex.Message
                                  + "\n" + ex.StackTrace);
                return "{\"error\":\"" + Esc(ex.GetType().Name + ": " + ex.Message) + "\"}";
            }
        }

        // =====================================================
        // API: /list-playtime-state, /claim-playtime-rewards, /claim-pp-rewards
        //
        // Session-chest rewards (in-game and PlariumPlay tracks).
        // The TakeAllSessionChestRewardsCmd has three required fields:
        //   _lastRegularAwardToTakeMinutes  (last in-game milestone minute)
        //   _lastPlariumAwardToTakeMinutes  (last PP milestone minute)
        //   _isPlariumPlay                  (selects which side to claim)
        //
        // Walk HourlyGiftsWrapper.PrizesByMinutes (or PlariumProgramPrizesByMinutes),
        // intersect with TotalMsInGameToday/60000, exclude PrizeReceivedMinutes,
        // find max-eligible-minute; that becomes the cmd's "last" field.
        // =====================================================
        private object FindHourlyGiftsWrapper()
        {
            object uw = GetUserWrapper();
            if (uw == null) return null;
            // userWrapper.HourlyGiftsWrapper (per UserWrapper props inspection).
            return Prop(uw, "HourlyGiftsWrapper") ?? Prop(uw, "SessionChests");
        }

        // Iterate the keys of a Dictionary<TKey, TValue> via reflection.
        private static IEnumerable<object> DictKeys(object dict)
        {
            if (dict == null) yield break;
            var keys = Prop(dict, "Keys");
            if (keys == null) yield break;
            var getEnum = keys.GetType().GetMethod("GetEnumerator");
            if (getEnum == null) yield break;
            var enumerator = getEnum.Invoke(keys, null);
            var enumType = enumerator.GetType();
            var moveNext = enumType.GetMethod("MoveNext");
            var current = enumType.GetProperty("Current");
            while ((bool)moveNext.Invoke(enumerator, null))
            {
                yield return current.GetValue(enumerator);
            }
        }

        private (int currentMin, int maxEligibleMin, int eligibleCount, int totalMinutes) GetSessionChestSummary(bool isPp)
        {
            object hgw = FindHourlyGiftsWrapper();
            if (hgw == null) return (0, 0, 0, 0);
            int totalMs = isPp ? IntProp(hgw, "TotalMsInPlariumPlayToday")
                               : IntProp(hgw, "TotalMsInGameToday");
            int currentMin = totalMs / 60000;
            object prizes = isPp ? Prop(hgw, "PlariumProgramPrizesByMinutes")
                                 : Prop(hgw, "PrizesByMinutes");
            object claimedList = isPp ? Prop(hgw, "PlariumPlayPrizeReceivedMinutes")
                                      : Prop(hgw, "PrizeReceivedMinutes");
            var claimed = new HashSet<int>();
            foreach (var m in ListItems(claimedList))
            {
                if (m != null)
                {
                    try { claimed.Add(Convert.ToInt32(m)); } catch { }
                }
            }
            int totalMilestones = 0;
            int eligibleCount = 0;
            int maxEligible = 0;
            foreach (var k in DictKeys(prizes))
            {
                int minute;
                try { minute = Convert.ToInt32(k); } catch { continue; }
                totalMilestones++;
                if (minute <= currentMin && !claimed.Contains(minute))
                {
                    eligibleCount++;
                    if (minute > maxEligible) maxEligible = minute;
                }
            }
            return (currentMin, maxEligible, eligibleCount, totalMilestones);
        }

        private string ListPlaytimeState()
        {
            try
            {
                var ig = GetSessionChestSummary(false);
                var pp = GetSessionChestSummary(true);
                var sb = new StringBuilder();
                sb.Append("{");
                sb.Append("\"in_game\":{")
                  .Append("\"current_min\":").Append(ig.currentMin)
                  .Append(",\"max_eligible_min\":").Append(ig.maxEligibleMin)
                  .Append(",\"eligible_count\":").Append(ig.eligibleCount)
                  .Append(",\"total_milestones\":").Append(ig.totalMinutes)
                  .Append("}");
                sb.Append(",\"plarium_play\":{")
                  .Append("\"current_min\":").Append(pp.currentMin)
                  .Append(",\"max_eligible_min\":").Append(pp.maxEligibleMin)
                  .Append(",\"eligible_count\":").Append(pp.eligibleCount)
                  .Append(",\"total_milestones\":").Append(pp.totalMinutes)
                  .Append("}");
                sb.Append("}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        private string ClaimSessionChestRewards(bool isPlariumProgram)
        {
            try
            {
                var (currentMin, maxEligible, eligibleCount, _) = GetSessionChestSummary(isPlariumProgram);
                if (eligibleCount == 0)
                    return "{\"claimed_count\":0,\"note\":\"nothing eligible\",\"current_min\":" + currentMin + "}";

                var cmdType = FindType("Client.Model.Gameplay.SessionChests.Commands.TakeAllSessionChestRewardsCmd");
                if (cmdType == null) return "{\"error\":\"TakeAllSessionChestRewardsCmd not found\"}";
                // 3-arg ctor (verified via dump.cs):
                //   .ctor(int lastRegularAwardToTakeMinutes,
                //         int lastPlariumAwardToTakeMinutes,
                //         bool isPlariumPlay)
                // Fields are readonly — must be set via ctor, NOT post-construction.
                var ctor = cmdType.GetConstructor(new[] {
                    typeof(int), typeof(int), typeof(bool)
                });
                if (ctor == null)
                    return "{\"error\":\"3-arg ctor not found on TakeAllSessionChestRewardsCmd\"}";

                int regMin = isPlariumProgram ? 0 : maxEligible;
                int ppMin = isPlariumProgram ? maxEligible : 0;
                object cmd = ctor.Invoke(new object[] { regMin, ppMin, isPlariumProgram });

                // Diagnostic on rejection
                try
                {
                    var ifErrorM = cmd.GetType().GetMethod("IfError",
                        BindingFlags.Instance | BindingFlags.Public | BindingFlags.FlattenHierarchy,
                        null, new[] { typeof(System.Action) }, null);
                    if (ifErrorM != null)
                    {
                        System.Action errCb = () =>
                            Logger.LogWarning("[SessionChest] server rejected: isPp=" + isPlariumProgram
                                              + " lastMin=" + maxEligible);
                        ifErrorM.Invoke(cmd, new object[] { errCb });
                    }
                }
                catch { }

                Logger.LogInfo("[SessionChest] enqueue isPp=" + isPlariumProgram
                               + " lastMin=" + maxEligible + " current=" + currentMin
                               + " eligible=" + eligibleCount);
                InvokeExecute(cmd);

                return "{\"claimed_count\":" + eligibleCount
                       + ",\"last_minute\":" + maxEligible
                       + ",\"current_min\":" + currentMin
                       + ",\"is_plarium_play\":" + (isPlariumProgram ? "true" : "false")
                       + "}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // =====================================================
        // API: /list-inbox, /claim-inbox
        //
        // InboxWrapper holds InboxData.Items: List<InboxItem>. Each
        // item has Id + IsRead + Prize. Unread items can be claimed
        // via CollectMultipleItemsCmd(_items: List<int>) — server
        // marks them read+collected and grants the prize.
        // =====================================================
        private object FindInboxData()
        {
            object uw = GetUserWrapper();
            if (uw == null) return null;
            object inbox = Prop(uw, "Inbox");
            if (inbox == null) return null;
            return Prop(inbox, "InboxData");
        }

        private string ListInbox()
        {
            try
            {
                object inboxData = FindInboxData();
                if (inboxData == null) return "{\"error\":\"InboxData not reachable\"}";
                object items = Prop(inboxData, "Items");
                if (items == null) return "{\"items\":[],\"count\":0}";

                var sb = new StringBuilder();
                sb.Append("{\"items\":[");
                int n = 0, unreadN = 0;
                foreach (var it in ListItems(items))
                {
                    if (it == null) continue;
                    int id = TryInt(Prop(it, "Id"));
                    bool isRead;
                    try { isRead = (bool)Prop(it, "IsRead"); } catch { isRead = false; }
                    string typeId = SafeStr(Prop(it, "TypeId"));
                    if (n > 0) sb.Append(",");
                    sb.Append("{\"id\":").Append(id);
                    sb.Append(",\"type_id\":\"").Append(Esc(typeId)).Append("\"");
                    sb.Append(",\"is_read\":").Append(isRead ? "true" : "false");
                    sb.Append("}");
                    n++;
                    if (!isRead) unreadN++;
                }
                sb.Append("],\"count\":").Append(n);
                sb.Append(",\"unread_count\":").Append(unreadN).Append("}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // Two-stage inbox flow:
        //   1. MarkInboxItemsReadCmd(_itemIds: int[])   — server flips IsRead
        //   2. CollectMultipleItemsCmd(_items: List<int>) — server grants prizes
        // Items without a prize (ClientUpdate / similar notices) only get
        // step 1. Items with a real prize get both. Server requires items
        // be marked read before they can be collected.
        //
        // CRITICAL: passing the wrong item ID (e.g. a ClientUpdate-type
        // notification that lacks a real Prize) to CollectMultipleItemsCmd
        // causes the server to reject the whole batch with
        // "ClientLogicException Inbox_InvalidInboxItem" and surface a
        // user-facing error popup. Filter strictly by InboxTypeId AND by
        // checking the Prize struct has actual contents.
        private static readonly HashSet<string> _NON_COLLECTIBLE_INBOX_TYPES =
            new HashSet<string>
        {
            "ClientUpdate",      // patch / version notes (no prize)
            "PersonalMessage",   // plain text from staff
            "GuideForBeginners", // tutorial nudges
            // SessionChest receipt — actual prize claimed via
            // TakeAllSessionChestRewardsCmd; inbox copy is informational.
            "SessionChest",
            // Note: BankPackages / DynamicPriceBankPackages / GiftOffer ARE
            // collectible (Shop Purchase deliveries, Limited Special Offer
            // gifts). They land here with the actual prize attached and need
            // explicit collect.
        };

        // Arena-token reward types: per user preference, only claim when
        // arena tokens are actually needed (otherwise they cap silently
        // and the reward is wasted). Keep these in the inbox until the
        // user manually claims via the UI.
        private static readonly HashSet<string> _ARENA_TOKEN_INBOX_TYPES =
            new HashSet<string>
        {
            "ArenaWeeklyReward",   // 8  — Classic Arena weekly reward
            "ArenaReward",         // 18 — Daily Classic Arena reward
            "Arena3X3Shop",        // 45 — 3v3 arena shop currency
            "LiveArena",           // 98 — Live Arena rewards (tokens)
        };
        private bool InboxItemHasPrize(object item)
        {
            object prize = Prop(item, "Prize");
            if (prize == null) return false;
            // Walk obvious "has-something" fields. UserPrize has Resources,
            // Heroes, Artifacts, etc. — if any non-empty, count it.
            object resources = Prop(prize, "Resources");
            if (resources != null)
            {
                object isEmpty = Prop(resources, "IsEmpty");
                if (isEmpty is bool be && !be) return true;
                object total = Prop(resources, "Total");
                if (total != null)
                {
                    try { if (Convert.ToInt64(total) != 0) return true; } catch { }
                }
            }
            foreach (var listProp in new[] {
                "Heroes", "Artifacts", "HeroSouls", "HeroSkins", "Avatars",
                "Badges", "Frames", "ArtifactDropSettings", "Effects",
                "SelectableHeroes",
            })
            {
                object lst = Prop(prize, listProp);
                int cnt = IntProp(lst, "Count");
                if (cnt > 0) return true;
            }
            // Dictionary fields
            foreach (var dictProp in new[] {
                "HeroParts", "HeroPartsChest", "BlackMarketItems", "PointsByPass",
            })
            {
                object dct = Prop(prize, dictProp);
                int cnt = IntProp(dct, "Count");
                if (cnt > 0) return true;
            }
            // Scalar non-null fields
            int xp = IntProp(prize, "Experience");
            if (xp > 0) return true;
            long arenaPts = LongProp(prize, "ArenaPoints");
            if (arenaPts > 0) return true;
            return false;
        }

        // Build an IL2Cpp Il2CppStructArray<int> — the cmd's field type.
        // Falls back to typed array via Activator if the struct-array type
        // isn't directly resolvable (e.g. shape varies between cmds).
        private object BuildIntArray(System.Type fieldType, IList<int> ids)
        {
            // Path 1: Il2CppStructArray<int> from Il2CppInterop.
            try
            {
                if (fieldType.Name.StartsWith("Il2CppStructArray"))
                {
                    var arr = new Il2CppInterop.Runtime.InteropTypes.Arrays.Il2CppStructArray<int>(
                        new int[ids.Count]);
                    for (int i = 0; i < ids.Count; i++) arr[i] = ids[i];
                    return arr;
                }
            }
            catch { }
            // Path 2: List<int>.
            try
            {
                var list = System.Activator.CreateInstance(fieldType);
                var addM = fieldType.GetMethod("Add", new[] { typeof(int) });
                if (addM != null)
                {
                    foreach (var id in ids) addM.Invoke(list, new object[] { id });
                    return list;
                }
            }
            catch { }
            // Path 3: int[].
            try
            {
                var arr = new int[ids.Count];
                for (int i = 0; i < ids.Count; i++) arr[i] = ids[i];
                return arr;
            }
            catch { }
            return null;
        }

        private bool FireCmdWithIntCollection(string cmdFqn, string fieldName, IList<int> ids,
                                              out string err)
        {
            err = null;
            var cmdType = FindType(cmdFqn);
            if (cmdType == null) { err = cmdFqn + " not found"; return false; }

            // Strategy 1: zero-arg ctor + property-set on the field.
            // Strategy 2: 1-arg ctor accepting the collection directly.
            var fieldP = cmdType.GetProperty(fieldName);
            object cmd = null;
            var defaultCtor = cmdType.GetConstructor(System.Type.EmptyTypes);
            if (defaultCtor != null && fieldP != null)
            {
                try
                {
                    cmd = defaultCtor.Invoke(null);
                    object collection0 = BuildIntArray(fieldP.PropertyType, ids);
                    if (collection0 != null) fieldP.SetValue(cmd, collection0);
                }
                catch { cmd = null; }
            }
            if (cmd == null)
            {
                foreach (var c in cmdType.GetConstructors(
                    BindingFlags.Public | BindingFlags.Instance))
                {
                    var ps = c.GetParameters();
                    if (ps.Length != 1) continue;
                    var ptype = ps[0].ParameterType;
                    object collection = BuildIntArray(ptype, ids);
                    if (collection == null) continue;
                    try { cmd = c.Invoke(new object[] { collection }); break; }
                    catch (System.Exception cex) { err = "ctor1: " + cex.Message; }
                }
            }
            if (cmd == null)
            {
                if (err == null) err = cmdFqn + " no usable ctor";
                return false;
            }

            try
            {
                var ifErrorM = cmd.GetType().GetMethod("IfError",
                    BindingFlags.Instance | BindingFlags.Public | BindingFlags.FlattenHierarchy,
                    null, new[] { typeof(System.Action) }, null);
                if (ifErrorM != null)
                {
                    string lbl = cmdFqn.Substring(cmdFqn.LastIndexOf('.') + 1);
                    System.Action errCb = () =>
                        Logger.LogWarning("[Inbox] " + lbl + " server rejected (n=" + ids.Count + ")");
                    ifErrorM.Invoke(cmd, new object[] { errCb });
                }
            }
            catch { }

            try
            {
                Logger.LogInfo("[Inbox] enqueue " + cmdFqn + " ids=" + ids.Count);
                InvokeExecute(cmd);
            }
            catch (System.Exception ex)
            {
                err = "exec: " + ex.Message;
                return false;
            }
            return true;
        }

        // =====================================================
        // Helper: get the IL2Cpp class pointer for a managed wrapper type.
        // Required because Activator.CreateInstance returns a wrapper with
        // pooledPtr=0 (no IL2Cpp instance) for some cmd classes — calling
        // Execute on that no-ops silently. il2cpp_object_new is the only
        // path that actually allocates the IL2Cpp side.
        private IntPtr GetIL2CppClassPtr(System.Type managedType)
        {
            try
            {
                var ptrStoreT = typeof(Il2CppInterop.Runtime.Il2CppClassPointerStore<>)
                    .MakeGenericType(managedType);
                var ncpField = ptrStoreT.GetField("NativeClassPtr",
                    BindingFlags.Public | BindingFlags.Static);
                if (ncpField == null) return IntPtr.Zero;
                return (IntPtr)ncpField.GetValue(null);
            }
            catch { return IntPtr.Zero; }
        }

        private IntPtr FindIL2CppMethodOnHierarchy(IntPtr cls, string name, int paramCount)
        {
            if (cls == IntPtr.Zero) return IntPtr.Zero;
            IntPtr scan = cls;
            int hops = 0;
            while (scan != IntPtr.Zero && hops < 10)
            {
                IntPtr m = FindIL2CPPMethod(scan, name, paramCount);
                if (m != IntPtr.Zero) return m;
                scan = il2cpp_class_get_parent(scan);
                hops++;
            }
            return IntPtr.Zero;
        }

        // =====================================================
        // API: /diag-inbox-cmd?id=N — diagnostic for cmd construction.
        // Builds CollectRewardItemCmd(N), inspects post-ctor field state,
        // returns key fields. Helps identify whether ctor body actually
        // ran or just allocated the object.
        // =====================================================
        private string DiagInboxCmd(string idStr)
        {
            int id;
            if (!int.TryParse(idStr, out id) || id <= 0)
                return "{\"error\":\"id required\"}";
            var cmdType = FindType("Client.Model.Gameplay.Inbox.Commands.CollectRewardItemCmd");
            if (cmdType == null) return "{\"error\":\"type not found\"}";
            var ctor = cmdType.GetConstructor(new[] { typeof(int) });
            if (ctor == null) return "{\"error\":\"no (int) ctor\"}";
            object cmd;
            try { cmd = ctor.Invoke(new object[] { id }); }
            catch (System.Reflection.TargetInvocationException tex)
            {
                var inner = tex.InnerException ?? tex;
                return "{\"error\":\"ctor inner: " + Esc(inner.GetType().Name + ": " + inner.Message)
                       + "\",\"stack\":\"" + Esc(inner.StackTrace ?? "") + "\"}";
            }
            catch (Exception ex) { return "{\"error\":\"ctor: " + Esc(ex.Message) + "\"}"; }

            var sb = new StringBuilder();
            sb.Append("{\"id\":").Append(id);
            sb.Append(",\"cmd_type\":\"").Append(Esc(cmd.GetType().FullName)).Append("\"");

            // Walk all instance fields/props and dump their values
            var t = cmd.GetType();
            sb.Append(",\"fields\":{");
            int fn = 0;
            foreach (var f in t.GetFields(BindingFlags.Public | BindingFlags.NonPublic |
                                           BindingFlags.Instance | BindingFlags.FlattenHierarchy))
            {
                if (f.Name.Contains("BackingField") && fn > 30) continue;
                if (fn > 0) sb.Append(",");
                object v;
                try { v = f.GetValue(cmd); } catch { v = null; }
                string vStr = v == null ? "null" : v.ToString();
                if (vStr.Length > 80) vStr = vStr.Substring(0, 80);
                sb.Append("\"").Append(Esc(f.Name)).Append("\":\"")
                  .Append(Esc(vStr)).Append("\"");
                fn++;
                if (fn >= 60) break;
            }
            sb.Append("},\"field_count\":").Append(fn).Append("}");
            return sb.ToString();
        }

        // =====================================================
        // API: /claim-inbox-il2cpp?id=N — claim ONE inbox item via raw
        // IL2CPP construction. Bypasses Activator/managed-wrapper bind
        // by using il2cpp_object_new + il2cpp_runtime_invoke for both
        // ctor and Execute. The `Activator.CreateInstance` path leaves
        // the wrapper's pooledPtr=0 (no actual IL2Cpp instance), which
        // is why our cmds enqueue without ever firing IfStarting.
        // =====================================================
        [DllImport("GameAssembly", CharSet = CharSet.Ansi, ExactSpelling = true,
                   CallingConvention = CallingConvention.Cdecl)]
        private static extern IntPtr il2cpp_object_new(IntPtr klass);

        private string ClaimInboxIL2Cpp(string idStr)
        {
            int id;
            if (!int.TryParse(idStr, out id) || id <= 0)
                return "{\"error\":\"id required\"}";
            try
            {
                var cmdManagedT = FindType(
                    "Client.Model.Gameplay.Inbox.Commands.CollectRewardItemCmd");
                if (cmdManagedT == null) return "{\"error\":\"managed type not found\"}";

                // Get the IL2Cpp class pointer via Il2CppClassPointerStore<T>.
                // Each Il2CppInterop wrapper has a static field NativeClassPtr.
                var ptrStoreT = typeof(Il2CppInterop.Runtime.Il2CppClassPointerStore<>)
                    .MakeGenericType(cmdManagedT);
                var nativeClsField = ptrStoreT.GetField("NativeClassPtr",
                    BindingFlags.Public | BindingFlags.Static);
                if (nativeClsField == null)
                    return "{\"error\":\"NativeClassPtr field not found\"}";
                IntPtr cmdCls = (IntPtr)nativeClsField.GetValue(null);
                if (cmdCls == IntPtr.Zero)
                    return "{\"error\":\"cmd IL2Cpp class ptr is zero\"}";

                // Allocate IL2Cpp instance + invoke .ctor(int)
                IntPtr cmdPtr = il2cpp_object_new(cmdCls);
                if (cmdPtr == IntPtr.Zero)
                    return "{\"error\":\"il2cpp_object_new returned null\"}";

                IntPtr ctorM = FindIL2CPPMethod(cmdCls, ".ctor", 1);
                if (ctorM == IntPtr.Zero)
                    return "{\"error\":\".ctor(int) not found via IL2CPP\"}";

                // Box the int. Easier path: pass via a stack-allocated buffer.
                // il2cpp_runtime_invoke takes IntPtr* as args (each entry is a
                // pointer to the value for value types, or the object for refs).
                int[] argBuf = new[] { id };
                IntPtr exc = IntPtr.Zero;
                System.Runtime.InteropServices.GCHandle pin =
                    System.Runtime.InteropServices.GCHandle.Alloc(
                        argBuf, System.Runtime.InteropServices.GCHandleType.Pinned);
                try
                {
                    IntPtr argPtr = pin.AddrOfPinnedObject();
                    IntPtr[] args = { argPtr };
                    System.Runtime.InteropServices.GCHandle pinArgs =
                        System.Runtime.InteropServices.GCHandle.Alloc(
                            args, System.Runtime.InteropServices.GCHandleType.Pinned);
                    try
                    {
                        il2cpp_runtime_invoke(ctorM, cmdPtr, pinArgs.AddrOfPinnedObject(), ref exc);
                    }
                    finally { pinArgs.Free(); }
                }
                finally { pin.Free(); }

                if (exc != IntPtr.Zero)
                {
                    Logger.LogWarning("[InboxIL2Cpp] ctor exc id=" + id);
                    return "{\"error\":\"ctor threw IL2Cpp exception\"}";
                }

                // Wrap into managed for Logger and Execute lookup.
                object cmd = Activator.CreateInstance(cmdManagedT, cmdPtr);
                Logger.LogInfo("[InboxIL2Cpp] constructed via il2cpp_object_new id=" + id
                               + " cmd_ptr=0x" + cmdPtr.ToString("X"));

                // Find Execute() via IL2CPP and invoke.
                IntPtr execM = FindIL2CPPMethod(cmdCls, "Execute", 0);
                if (execM == IntPtr.Zero)
                {
                    // Walk parent classes
                    IntPtr scan = cmdCls;
                    int hops = 0;
                    while (scan != IntPtr.Zero && execM == IntPtr.Zero && hops < 8)
                    {
                        scan = il2cpp_class_get_parent(scan);
                        if (scan != IntPtr.Zero)
                            execM = FindIL2CPPMethod(scan, "Execute", 0);
                        hops++;
                    }
                }
                if (execM == IntPtr.Zero)
                    return "{\"error\":\"Execute() not found via IL2CPP\"}";

                IntPtr execExc = IntPtr.Zero;
                il2cpp_runtime_invoke(execM, cmdPtr, IntPtr.Zero, ref execExc);
                if (execExc != IntPtr.Zero)
                {
                    Logger.LogWarning("[InboxIL2Cpp] Execute threw IL2Cpp exception");
                    return "{\"error\":\"Execute threw IL2Cpp exception\"}";
                }

                Logger.LogInfo("[InboxIL2Cpp] Execute returned cleanly id=" + id);
                return "{\"ok\":true,\"id\":" + id + "}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.GetType().Name + ": " + ex.Message) + "\"}";
            }
        }

        // =====================================================
        // API: /claim-inbox-onclick
        //
        // The in-game inbox "Collect" button calls
        // InboxRewardItemContext.OnButtonClick() per item, which runs the
        // proper Collect() → ValidateCollect → CollectRewardItemCmd flow
        // including the OnCollectReward callback that's required for the
        // local state to actually update.
        //
        // The plain CollectRewardItemCmd cmd path enqueues fine but server-
        // side processing leaves the items in inbox (no IfError fires
        // either) — likely because the cmd's edit-side state mutation
        // depends on the OnButtonClick orchestration we were skipping.
        //
        // Strategy: walk Resources.FindObjectsOfTypeAll<MonoBehaviour>() for
        // any whose IL2CPP class is InboxRewardItemContext, then invoke
        // OnButtonClick on each via raw IL2CPP runtime invoke. Same path the
        // user's tap fires.
        // =====================================================
        private string ClaimInboxByOnClick()
        {
            try
            {
                var allMbs = Resources.FindObjectsOfTypeAll<MonoBehaviour>();
                int sawCtx = 0, invoked = 0, errors = 0;
                var seen = new HashSet<string>();

                foreach (var mb in allMbs)
                {
                    if (mb == null) continue;
                    IntPtr monoPtr; IntPtr monoCls; string mbCn;
                    try
                    {
                        monoPtr = mb.Pointer;
                        if (monoPtr == IntPtr.Zero) continue;
                        monoCls = il2cpp_object_get_class(monoPtr);
                        if (monoCls == IntPtr.Zero) continue;
                        mbCn = Marshal.PtrToStringAnsi(il2cpp_class_get_name(monoCls));
                    }
                    catch { continue; }
                    if (string.IsNullOrEmpty(mbCn)) continue;

                    // We're after the views' Context, not the MB itself —
                    // get_Context returns the InboxRewardItemContext instance
                    // (or other context classes).
                    IntPtr getCtx = FindIL2CPPMethod(monoCls, "get_Context", 0);
                    if (getCtx == IntPtr.Zero) continue;
                    IntPtr exc = IntPtr.Zero;
                    IntPtr ctxPtr = il2cpp_runtime_invoke(getCtx, monoPtr, IntPtr.Zero, ref exc);
                    if (ctxPtr == IntPtr.Zero || exc != IntPtr.Zero) continue;
                    IntPtr ctxCls = il2cpp_object_get_class(ctxPtr);
                    string ctxCn = Marshal.PtrToStringAnsi(il2cpp_class_get_name(ctxCls));
                    if (string.IsNullOrEmpty(ctxCn)) continue;
                    if (seen.Count < 5) seen.Add(ctxCn);

                    if (ctxCn != "InboxRewardItemContext") continue;
                    sawCtx++;

                    // Invoke OnButtonClick() — the same handler the in-game
                    // Collect button calls.
                    IntPtr onClickM = FindIL2CPPMethod(ctxCls, "OnButtonClick", 0);
                    if (onClickM == IntPtr.Zero)
                    {
                        Logger.LogWarning("[InboxOnClick] no OnButtonClick on context");
                        errors++; continue;
                    }
                    IntPtr ex2 = IntPtr.Zero;
                    try
                    {
                        il2cpp_runtime_invoke(onClickM, ctxPtr, IntPtr.Zero, ref ex2);
                        if (ex2 != IntPtr.Zero)
                        {
                            Logger.LogWarning("[InboxOnClick] OnButtonClick threw IL2CPP ex");
                            errors++;
                        }
                        else
                        {
                            invoked++;
                            Logger.LogInfo("[InboxOnClick] invoked OnButtonClick");
                        }
                    }
                    catch (Exception iex)
                    {
                        Logger.LogWarning("[InboxOnClick] managed throw: "
                                          + iex.GetType().Name + ": " + iex.Message);
                        errors++;
                    }
                }

                var sb = new StringBuilder();
                sb.Append("{\"saw_context_instances\":").Append(sawCtx);
                sb.Append(",\"invoked\":").Append(invoked);
                sb.Append(",\"errors\":").Append(errors);
                if (sawCtx == 0)
                {
                    sb.Append(",\"note\":\"InboxRewardItemContext not active — open inbox dialog first\"");
                    sb.Append(",\"sample_context_types\":[");
                    int n = 0;
                    foreach (var s in seen)
                    {
                        if (n > 0) sb.Append(",");
                        sb.Append("\"").Append(Esc(s)).Append("\"");
                        n++;
                    }
                    sb.Append("]");
                }
                sb.Append("}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        private string ClaimInbox()
        {
            try
            {
                object inboxData = FindInboxData();
                if (inboxData == null) return "{\"error\":\"InboxData not reachable\"}";
                object items = Prop(inboxData, "Items");
                if (items == null) return "{\"claimed_count\":0}";

                var idsToCollect = new List<int>();   // items to collect (have or might have prize)
                var idsToMarkRead = new List<int>();  // unread items WITHOUT prize
                var skippedArena = new List<int>();   // arena tokens — skip per user pref
                foreach (var it in ListItems(items))
                {
                    if (it == null) continue;
                    bool isRead;
                    try { isRead = (bool)Prop(it, "IsRead"); } catch { continue; }
                    int id = TryInt(Prop(it, "Id"));
                    if (id <= 0) continue;
                    string typeId = SafeStr(Prop(it, "TypeId"));
                    // ClientUpdate / PersonalMessage / GuideForBeginners /
                    // SessionChest are notices with no prize.
                    if (_NON_COLLECTIBLE_INBOX_TYPES.Contains(typeId))
                    {
                        if (!isRead) idsToMarkRead.Add(id);
                        continue;
                    }
                    // Arena token types: skip per user preference (capped
                    // silently; user claims manually via UI when needed).
                    if (_ARENA_TOKEN_INBOX_TYPES.Contains(typeId))
                    {
                        skippedArena.Add(id);
                        continue;
                    }
                    // Everything else: attempt to collect. The earlier
                    // InboxItemHasPrize() gate was too conservative — it
                    // returned false for GiftOffer / BankPackages items
                    // even though they DO have prizes (the heuristic
                    // walked wrong sub-fields). Server will reject items
                    // without a real prize via Inbox_InvalidInboxItem
                    // (typed error); per-item cmd dispatch means each
                    // rejection is isolated, doesn't kill the batch.
                    idsToCollect.Add(id);
                }

                if (idsToCollect.Count == 0 && idsToMarkRead.Count == 0)
                    return "{\"claimed_count\":0,\"note\":\"nothing to do\"}";

                // Step 1: batch-mark unread (notice) items as read.
                int markedN = 0;
                if (idsToMarkRead.Count > 0)
                {
                    string mErr;
                    if (FireCmdWithIntCollection(
                        "Client.Model.Gameplay.Inbox.Commands.MarkInboxItemsReadCmd",
                        "_itemIds", idsToMarkRead, out mErr))
                    {
                        markedN = idsToMarkRead.Count;
                    }
                }

                // Step 2: per-item CollectRewardItemCmd(itemId). One per item
                // so a single resource-cap rejection (e.g. arena tokens at
                // max) doesn't kill the whole batch — server returns a
                // typed error per cmd, others continue.
                int collectedN = 0, rejectedN = 0;
                var rejectedIds = new List<int>();
                var collectCmdType = FindType(
                    "Client.Model.Gameplay.Inbox.Commands.CollectRewardItemCmd");
                var collectCtor = collectCmdType?.GetConstructor(new[] { typeof(int) });

                // Use IL2Cpp-direct construction to avoid the empty-pooledPtr
                // issue that the standard Activator/Reflection path produces.
                // See ClaimInboxIL2Cpp for the smoking-gun diagnostic.
                IntPtr cmdCls = IntPtr.Zero;
                IntPtr ctorIL2Cpp = IntPtr.Zero;
                IntPtr execIL2Cpp = IntPtr.Zero;
                {
                    var ptrStoreT = typeof(Il2CppInterop.Runtime.Il2CppClassPointerStore<>)
                        .MakeGenericType(collectCmdType);
                    var ncpField = ptrStoreT.GetField("NativeClassPtr",
                        BindingFlags.Public | BindingFlags.Static);
                    if (ncpField != null) cmdCls = (IntPtr)ncpField.GetValue(null);
                    if (cmdCls != IntPtr.Zero)
                    {
                        ctorIL2Cpp = FindIL2CPPMethod(cmdCls, ".ctor", 1);
                        execIL2Cpp = FindIL2CPPMethod(cmdCls, "Execute", 0);
                        IntPtr scan = cmdCls; int hops = 0;
                        while (scan != IntPtr.Zero && execIL2Cpp == IntPtr.Zero && hops < 8)
                        {
                            scan = il2cpp_class_get_parent(scan);
                            if (scan != IntPtr.Zero)
                                execIL2Cpp = FindIL2CPPMethod(scan, "Execute", 0);
                            hops++;
                        }
                    }
                }

                if (cmdCls == IntPtr.Zero || ctorIL2Cpp == IntPtr.Zero || execIL2Cpp == IntPtr.Zero)
                {
                    // Last-resort: managed Activator path (won't work but keeps
                    // shape).
                    string cErr;
                    if (FireCmdWithIntCollection(
                        "Client.Model.Gameplay.Inbox.Commands.CollectMultipleItemsCmd",
                        "_items", idsToCollect, out cErr))
                    {
                        collectedN = idsToCollect.Count;
                    }
                }
                else
                {
                    foreach (var id in idsToCollect)
                    {
                        // 1. Allocate via il2cpp_object_new
                        IntPtr cmdPtr = il2cpp_object_new(cmdCls);
                        if (cmdPtr == IntPtr.Zero) { rejectedN++; rejectedIds.Add(id); continue; }
                        // 2. Invoke .ctor(int)
                        int[] argBuf = { id };
                        var pinArg = System.Runtime.InteropServices.GCHandle.Alloc(
                            argBuf, System.Runtime.InteropServices.GCHandleType.Pinned);
                        IntPtr[] argList = { pinArg.AddrOfPinnedObject() };
                        var pinList = System.Runtime.InteropServices.GCHandle.Alloc(
                            argList, System.Runtime.InteropServices.GCHandleType.Pinned);
                        IntPtr exc = IntPtr.Zero;
                        try
                        {
                            il2cpp_runtime_invoke(ctorIL2Cpp, cmdPtr, pinList.AddrOfPinnedObject(), ref exc);
                        }
                        finally
                        {
                            pinList.Free();
                            pinArg.Free();
                        }
                        if (exc != IntPtr.Zero)
                        {
                            Logger.LogWarning("[Inbox] IL2Cpp ctor exc id=" + id);
                            rejectedN++; rejectedIds.Add(id); continue;
                        }
                        // 2.5. Wrap into managed — keeps the IL2Cpp object
                        // alive through Il2CppInterop's bookkeeping during
                        // the async server roundtrip.
                        object cmdMgd = null;
                        try { cmdMgd = Activator.CreateInstance(collectCmdType, cmdPtr); }
                        catch { /* still proceed; managed wrap is best-effort */ }
                        // 3. Invoke Execute()
                        IntPtr exc2 = IntPtr.Zero;
                        try
                        {
                            il2cpp_runtime_invoke(execIL2Cpp, cmdPtr, IntPtr.Zero, ref exc2);
                        }
                        catch (Exception ex)
                        {
                            Logger.LogWarning("[Inbox] Execute managed throw id=" + id + ": " + ex.Message);
                            rejectedN++; rejectedIds.Add(id); continue;
                        }
                        if (exc2 != IntPtr.Zero)
                        {
                            Logger.LogWarning("[Inbox] Execute IL2Cpp exc id=" + id);
                            rejectedN++; rejectedIds.Add(id); continue;
                        }
                        Logger.LogInfo("[Inbox] claimed id=" + id);
                        collectedN++;
                        // Stagger cmds: server processes serially and rapid
                        // back-to-back fires can race the InboxData mutation
                        // (multiple cmds reading the SAME pre-claim list).
                        // 250ms is enough to let Edit complete locally.
                        System.Threading.Thread.Sleep(250);
                        continue;

                        // Legacy path (kept for reference / fallback) ↓
                        #pragma warning disable CS0162
                        object cmd;
                        try { cmd = collectCtor.Invoke(new object[] { id }); }
                        catch (Exception cex)
                        {
                            Logger.LogWarning("[Inbox] CollectRewardItemCmd ctor err id="
                                              + id + ": " + cex.Message);
                            rejectedN++;
                            rejectedIds.Add(id);
                            continue;
                        }
                        int captured = id;
                        try
                        {
                            var t = cmd.GetType();
                            // Wire all 4 callbacks for full state visibility.
                            foreach (var (mname, label) in new[] {
                                ("IfStarting", "starting"),
                                ("IfOk",       "ok"),
                                ("IfError",    "ERROR"),
                                ("IfFinished", "finished"),
                            })
                            {
                                var m = t.GetMethod(mname,
                                    BindingFlags.Instance | BindingFlags.Public | BindingFlags.FlattenHierarchy,
                                    null, new[] { typeof(System.Action) }, null);
                                if (m == null) continue;
                                int cap = captured;
                                string lbl = label;
                                System.Action cb = () =>
                                    Logger.LogInfo("[Inbox] item " + cap + " " + lbl);
                                try { m.Invoke(cmd, new object[] { cb }); } catch { }
                            }
                        }
                        catch (Exception cb)
                        {
                            Logger.LogWarning("[Inbox] handler-wire err id=" + id + ": " + cb.Message);
                        }
                        try
                        {
                            Logger.LogInfo("[Inbox] enqueue CollectRewardItemCmd id=" + id);
                            InvokeExecute(cmd);
                            collectedN++;
                        }
                        catch (Exception ex)
                        {
                            Logger.LogWarning("[Inbox] item " + id + " exec err: " + ex.Message);
                            rejectedN++;
                            rejectedIds.Add(id);
                        }
                    }
                }

                var sb = new StringBuilder();
                sb.Append("{\"claimed_count\":").Append(collectedN);
                sb.Append(",\"rejected_count\":").Append(rejectedN);
                sb.Append(",\"marked_read\":").Append(markedN);
                sb.Append(",\"items_attempted\":").Append(idsToCollect.Count);
                sb.Append(",\"items_marked_read\":").Append(idsToMarkRead.Count);
                sb.Append(",\"skipped_arena\":").Append(skippedArena.Count);
                if (rejectedIds.Count > 0)
                {
                    sb.Append(",\"rejected_ids\":[");
                    for (int i = 0; i < rejectedIds.Count; i++)
                    {
                        if (i > 0) sb.Append(",");
                        sb.Append(rejectedIds[i]);
                    }
                    sb.Append("]");
                }
                sb.Append("}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // =====================================================
        // API: /list-quests, /claim-quests
        //
        // QuestWrapper.Quests is a Dictionary<QuestId, QuestState>.
        // Claimable: StateId == Completed && PrizeGiven == false.
        // ClaimQuestRewardCmd.InitCloseQuest(QuestState) wires the
        // cmd to the quest; we then enqueue per-quest.
        // =====================================================
        private System.Collections.Generic.IEnumerable<object> WalkQuests()
        {
            object uw = GetUserWrapper();
            if (uw == null) yield break;
            // userWrapper.Quests is QuestWrapper, not the dict directly.
            object questWrapper = Prop(uw, "Quests");
            if (questWrapper == null) yield break;

            // PRIMARY source: UserQuestData.OpenedStates is the LIVE list of
            // QuestState records with actual progress (StateId=Completed/InProgress
            // and PrizeGiven flag). The QuestWrapper.Quests Dict is full of
            // template stubs (all StateId=Undefined) — useless for claim walks.
            object questData = Prop(questWrapper, "QuestData");
            if (questData != null)
            {
                object opened = Prop(questData, "OpenedStates");
                if (opened != null)
                {
                    foreach (var q in ListItems(opened))
                    {
                        if (q != null) yield return q;
                    }
                }
            }
            // Fallback: also walk the Dict in case some live entries land there.
            object questDict = Prop(questWrapper, "Quests");
            if (questDict != null)
            {
                foreach (var q in DictValues(questDict))
                {
                    if (q != null) yield return q;
                }
            }
        }

        // True when a quest is completed but the user hasn't taken the reward.
        private bool IsQuestClaimable(object questState)
        {
            if (questState == null) return false;
            // PrizeGiven == false is required.
            object prizeGiven = Prop(questState, "PrizeGiven");
            if (prizeGiven is bool pg && pg) return false;
            // StateId is QuestStateId enum: Completed=30 (the state where a prize
            // is pending). Il2CppInterop renders the enum's .ToString() as "30",
            // not "Completed", so compare numerically — string compare always
            // missed and showed claimable=0 even with completed quests waiting.
            int sid = -1;
            try { sid = Convert.ToInt32(Prop(questState, "StateId")); } catch { }
            return sid == 30;
        }

        // Returns one of: "Daily" / "Weekly" / "Monthly" / "Advanced:<sub>" /
        // "BattlePass" / "GlobalEvent" / "Other" — based on which Nullable
        // category-id field on the QuestState is populated.
        private string ClassifyQuest(object questState)
        {
            int periodic = NullableEnumInt(Prop(questState, "PeriodicQuestGroupId"));
            if (periodic == 1) return "Daily";
            if (periodic == 2) return "Weekly";
            if (periodic == 3) return "Monthly";

            int adv = NullableEnumInt(Prop(questState, "AdvancedDailyTypeId"));
            if (adv > 0)
            {
                string sub;
                switch (adv)
                {
                    case 1: sub = "Milestone"; break;
                    case 2: sub = "Static"; break;
                    case 3: sub = "ClanBoss"; break;
                    case 4: sub = "FactionWars"; break;
                    case 5: sub = "Arena"; break;
                    case 6: sub = "Development"; break;
                    case 7: sub = "Forge"; break;
                    case 8: sub = "Custom"; break;
                    case 9: sub = "Refreshable"; break;
                    default: sub = "T" + adv; break;
                }
                return "Advanced:" + sub;
            }

            int bp = NullableEnumInt(Prop(questState, "BattlePassId"));
            if (bp > 0) return "BattlePass";
            int ge = NullableEnumInt(Prop(questState, "GlobalEventSoloTypeId"));
            if (ge > 0) return "GlobalEvent";
            return "Other";
        }

        // Walk the QuestState.Completions[] list and pick the first Periodic
        // sub-entry that has progress info. Returns (current, needed) — both
        // 0 when no Periodic entry exists.
        private (int current, int needed) ReadQuestProgress(object questState)
        {
            try
            {
                object completions = Prop(questState, "Completions");
                if (completions == null) return (0, 0);
                foreach (var comp in ListItems(completions))
                {
                    if (comp == null) continue;
                    object periodic = Prop(comp, "Periodic");
                    if (periodic == null) continue;
                    long cur = 0;
                    try { cur = Convert.ToInt64(Prop(periodic, "CurrentPoints")); } catch { }
                    object qd = Prop(periodic, "QuestData");
                    int need = 0;
                    if (qd != null)
                    {
                        try { need = Convert.ToInt32(Prop(qd, "NeedCollectPoints")); } catch { }
                    }
                    return ((int)cur, need);
                }
            }
            catch { }
            return (0, 0);
        }

        // =====================================================
        // API: /quests — full per-quest dump categorized by Daily / Weekly /
        // Advanced (CB / FW / Arena / Forge / etc.) / BattlePass / GlobalEvent.
        //
        // Each entry: quest_id, prototype_id, category, state (string), progress
        // (current/needed), prize_given, claimable. Optional ?category=Daily
        // filter narrows to one bucket. Use this to answer "are my dailies
        // done", "do I have anything to claim", etc. without opening the UI.
        // =====================================================
        private string ListQuestsRich(string category)
        {
            try
            {
                bool filter = !string.IsNullOrEmpty(category);
                var sb = new StringBuilder();
                sb.Append("{\"quests\":[");
                int n = 0;

                // Per-category counters: total / completed / claimable
                var byCat = new Dictionary<string, int[]>();

                foreach (var q in WalkQuests())
                {
                    string cat = ClassifyQuest(q);
                    if (!byCat.ContainsKey(cat)) byCat[cat] = new int[3];

                    int sid = -1;
                    try { sid = Convert.ToInt32(Prop(q, "StateId")); } catch { }
                    string stateName;
                    switch (sid)
                    {
                        case 0:  stateName = "Undefined"; break;
                        case 10: stateName = "New"; break;
                        case 20: stateName = "InProgress"; break;
                        case 30: stateName = "Completed"; break;
                        default: stateName = "S" + sid; break;
                    }

                    bool prizeGiven = Prop(q, "PrizeGiven") is bool pgb && pgb;
                    bool claimable = IsQuestClaimable(q);

                    byCat[cat][0] += 1;
                    if (sid == 30) byCat[cat][1] += 1;
                    if (claimable) byCat[cat][2] += 1;

                    if (filter && !cat.StartsWith(category, StringComparison.OrdinalIgnoreCase))
                        continue;
                    // Skip Undefined-state quests (templates that never opened
                    // for this user) when no filter is applied — they bloat
                    // the response 5x without adding signal.
                    if (!filter && sid == 0) continue;

                    int qid = TryInt(Prop(q, "QuestId"));
                    int proto = TryInt(Prop(q, "PrototypeId"));
                    var (cur, need) = ReadQuestProgress(q);

                    if (n > 0) sb.Append(",");
                    sb.Append("{\"quest_id\":").Append(qid);
                    sb.Append(",\"prototype_id\":").Append(proto);
                    sb.Append(",\"category\":\"").Append(Esc(cat)).Append("\"");
                    sb.Append(",\"state\":\"").Append(stateName).Append("\"");
                    if (need > 0)
                    {
                        sb.Append(",\"progress\":{\"current\":").Append(cur)
                          .Append(",\"needed\":").Append(need).Append("}");
                    }
                    sb.Append(",\"prize_given\":").Append(prizeGiven ? "true" : "false");
                    sb.Append(",\"claimable\":").Append(claimable ? "true" : "false");
                    sb.Append("}");
                    n++;
                }

                sb.Append("],\"summary\":{");
                int sn = 0;
                // Stable order: Daily, Weekly, Monthly, Advanced:*, BattlePass,
                // GlobalEvent, Other. Anything else falls into alphabetical.
                var ordered = new List<string>();
                foreach (var k in new[] { "Daily", "Weekly", "Monthly" })
                    if (byCat.ContainsKey(k)) ordered.Add(k);
                foreach (var k in new List<string>(byCat.Keys))
                {
                    if (k.StartsWith("Advanced:") && !ordered.Contains(k))
                        ordered.Add(k);
                }
                foreach (var k in new[] { "BattlePass", "GlobalEvent", "Other" })
                    if (byCat.ContainsKey(k) && !ordered.Contains(k)) ordered.Add(k);
                foreach (var k in byCat.Keys)
                    if (!ordered.Contains(k)) ordered.Add(k);

                foreach (var k in ordered)
                {
                    var c = byCat[k];
                    if (sn > 0) sb.Append(",");
                    sb.Append("\"").Append(Esc(k)).Append("\":{\"total\":").Append(c[0])
                      .Append(",\"completed\":").Append(c[1])
                      .Append(",\"claimable\":").Append(c[2]).Append("}");
                    sn++;
                }
                sb.Append("}}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.GetType().Name + ": " + ex.Message) + "\"}";
            }
        }

        private string ListClaimableQuests()
        {
            try
            {
                var sb = new StringBuilder();
                sb.Append("{\"quests\":[");
                int n = 0, totalN = 0, claimableN = 0;
                int byState_0 = 0, byState_10 = 0, byState_20 = 0, byState_30 = 0;
                int prizeGivenT = 0, prizeGivenF = 0;
                foreach (var q in WalkQuests())
                {
                    totalN++;
                    int stateInt = -1;
                    try { stateInt = Convert.ToInt32(Prop(q, "StateId")); } catch { }
                    if (stateInt == 0) byState_0++;
                    else if (stateInt == 10) byState_10++;
                    else if (stateInt == 20) byState_20++;
                    else if (stateInt == 30) byState_30++;
                    object pg = Prop(q, "PrizeGiven");
                    if (pg is bool pgb) { if (pgb) prizeGivenT++; else prizeGivenF++; }
                    if (!IsQuestClaimable(q)) continue;
                    int id = TryInt(Prop(q, "QuestId"));
                    int proto = TryInt(Prop(q, "PrototypeId"));
                    string state = SafeStr(Prop(q, "StateId"));
                    if (n > 0) sb.Append(",");
                    sb.Append("{\"quest_id\":").Append(id);
                    sb.Append(",\"prototype_id\":").Append(proto);
                    sb.Append(",\"state\":\"").Append(Esc(state)).Append("\"");
                    sb.Append("}");
                    n++; claimableN++;
                }
                sb.Append("],\"total_quests\":").Append(totalN);
                sb.Append(",\"claimable\":").Append(claimableN);
                sb.Append(",\"by_state\":{\"undefined\":").Append(byState_0)
                  .Append(",\"new\":").Append(byState_10)
                  .Append(",\"in_progress\":").Append(byState_20)
                  .Append(",\"completed\":").Append(byState_30).Append("}");
                sb.Append(",\"prize_given\":{\"true\":").Append(prizeGivenT)
                  .Append(",\"false\":").Append(prizeGivenF).Append("}");
                sb.Append("}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        private string ClaimQuests()
        {
            try
            {
                // Regular quests use ClaimQuestRewardCmd.
                var regCmdType = FindType("Client.Model.Gameplay.Quests.Commands.ClaimQuestRewardCmd");
                // Daily/Weekly/Monthly (periodic) quests use a DIFFERENT cmd:
                // ClaimPeriodicQuestRewardCmd. Bug fix 2026-05-24: previously
                // every quest fired ClaimQuestRewardCmd, server silently
                // rejected periodic claims → UseEnergy/DefeatStoryBoss
                // dailies stayed claimable forever even though we said "claimed".
                var perCmdType = FindType("Client.Model.Gameplay.Quests.Commands.ClaimPeriodicQuestRewardCmd");
                if (regCmdType == null && perCmdType == null)
                    return "{\"error\":\"neither ClaimQuestRewardCmd nor ClaimPeriodicQuestRewardCmd type found\"}";

                int claimedN = 0, errorsN = 0;
                var sb = new StringBuilder();
                sb.Append("{\"claimed\":[");

                var regCtor1 = regCmdType?.GetConstructor(new[] { typeof(int) });
                var regCtor2 = regCmdType?.GetConstructor(new[] { typeof(int), typeof(int) });
                var perCtor1 = perCmdType?.GetConstructor(new[] { typeof(int) });

                foreach (var q in WalkQuests())
                {
                    if (!IsQuestClaimable(q)) continue;
                    int qid = TryInt(Prop(q, "QuestId"));
                    int proto = TryInt(Prop(q, "PrototypeId"));
                    if (qid <= 0) { errorsN++; continue; }

                    // Periodic-quest detection. Two signals:
                    //   1. PeriodicQuestGroupId Nullable<enum> populated.
                    //   2. PrototypeId in the periodic range 110000-110999
                    //      (PeriodicQuestPrototypeId enum from dump.cs).
                    // Signal #1 alone misses some Daily quests where the
                    // Nullable<enum> read returns 0 — fall back on proto id.
                    bool isPeriodic = NullableEnumInt(Prop(q, "PeriodicQuestGroupId")) > 0
                                      || (proto >= 110000 && proto < 111000);

                    object cmd = null;
                    try
                    {
                        if (isPeriodic && perCtor1 != null)
                            cmd = perCtor1.Invoke(new object[] { qid });
                        else if (proto != 0 && regCtor2 != null)
                            cmd = regCtor2.Invoke(new object[] { qid, proto });
                        else if (regCtor1 != null)
                            cmd = regCtor1.Invoke(new object[] { qid });
                    }
                    catch (System.Reflection.TargetInvocationException tex)
                    {
                        var inner = tex.InnerException ?? tex;
                        Logger.LogWarning("[ClaimQuest] ctor err qid=" + qid + " proto=" + proto
                                          + " periodic=" + isPeriodic + ": "
                                          + inner.GetType().Name + ": " + inner.Message);
                    }
                    catch (Exception cex)
                    {
                        Logger.LogWarning("[ClaimQuest] ctor err qid=" + qid + ": "
                                          + cex.GetType().Name + ": " + cex.Message);
                    }
                    if (cmd == null) { errorsN++; continue; }

                    try
                    {
                        Logger.LogInfo("[ClaimQuest] enqueue quest_id=" + qid
                                       + (isPeriodic ? " (periodic)" : ""));
                        InvokeExecute(cmd);
                        if (claimedN > 0) sb.Append(",");
                        sb.Append(qid);
                        claimedN++;
                    }
                    catch (Exception ex)
                    {
                        Logger.LogWarning("[ClaimQuest] failed quest_id=" + qid + ": " + ex.Message);
                        errorsN++;
                    }
                }

                sb.Append("],\"claimed_count\":").Append(claimedN);
                sb.Append(",\"errors\":").Append(errorsN).Append("}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // =====================================================
        // API: /list-static-offers — dump UserStaticOffer list (raw)
        //
        // Walks AppModel._userWrapper.Offers.OffersData.StaticOffers.
        // For each offer, returns Id/TypeId/StateId plus a few hints
        // about the matching ClientStaticOffer (price-free flag).
        // Used by /claim-free-shop-offers below.
        // =====================================================
        // Returns OffersWrapper or null. On failure, sets diagnostic
        // string so callers can surface the actual breakage step.
        private string _offersWrapperDiag = "";
        private object FindOffersWrapper()
        {
            _offersWrapperDiag = "";
            // Use the cached singleton accessor (FlattenHierarchy makes the
            // static Instance prop on AppModel reachable across builds).
            object appModel = GetAppModel();
            if (appModel == null) { _offersWrapperDiag = "GetAppModel returned null"; return null; }

            // GetUserWrapper walks all AppModel properties looking for a
            // UserWrapper-typed slot — independent of the property's name.
            object userWrapper = GetUserWrapper();
            if (userWrapper == null) { _offersWrapperDiag = "GetUserWrapper returned null"; return null; }

            object offers = Prop(userWrapper, "Offers");
            if (offers == null) { _offersWrapperDiag = "Offers prop not on UserWrapper"; return null; }
            return offers;
        }

        private string ListStaticOffers()
        {
            try
            {
                object offersWrapper = FindOffersWrapper();
                if (offersWrapper == null) return "{\"error\":\"OffersWrapper not reachable: " + Esc(_offersWrapperDiag) + "\"}";
                object offersData = Prop(offersWrapper, "OffersData");
                if (offersData == null) return "{\"error\":\"OffersData null\"}";
                object staticOffers = Prop(offersData, "StaticOffers");
                if (staticOffers == null) return "{\"error\":\"StaticOffers null\"}";

                var sb = new StringBuilder();
                sb.Append("{\"offers\":[");
                int n = 0;
                foreach (var offer in ListItems(staticOffers))
                {
                    if (offer == null) continue;
                    if (n > 0) sb.Append(",");
                    int id = TryInt(Prop(offer, "Id"));
                    int promoOfferId = TryInt(Prop(offer, "PromoOfferId"));
                    string state = SafeStr(Prop(offer, "StateId"));
                    int stateInt;
                    try { stateInt = Convert.ToInt32(Prop(offer, "StateId")); } catch { stateInt = -1; }
                    string typeId = SafeStr(Prop(offer, "TypeId"));
                    int purchaseDatesCount = IntProp(Prop(offer, "PurchaseDates"), "Count");
                    sb.Append("{");
                    sb.Append("\"id\":").Append(id);
                    sb.Append(",\"promo_offer_id\":").Append(promoOfferId);
                    sb.Append(",\"type_id\":\"").Append(Esc(typeId)).Append("\"");
                    sb.Append(",\"state_id\":\"").Append(Esc(state)).Append("\"");
                    sb.Append(",\"state_int\":").Append(stateInt);
                    sb.Append(",\"purchase_dates_count\":").Append(purchaseDatesCount);
                    object hasDynamic = Prop(offer, "HasDynamicPrice");
                    if (hasDynamic != null) sb.Append(",\"has_dynamic_price\":").Append((bool)hasDynamic ? "true" : "false");
                    sb.Append("}");
                    n++;
                }
                sb.Append("],\"count\":").Append(n).Append("}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // =====================================================
        // API: /list-give-offers, /claim-free-give-offers
        //
        // GiveOffers are the "Packs" tab Mystery Shard / Silver Ticket
        // FREE-refresh entries (and similar promotional offers). They
        // sit in OffersData.GiveOffers and pair with ClientGiveOffer
        // definitions. Free ones have FreeOfferData != null on the
        // matching ClientGiveOffer (or on the user offer itself).
        // PurchaseGiveOfferCmd takes a BuyGiveOfferRequestDto{Id=N}.
        // =====================================================
        private string ListGiveOffers()
        {
            try
            {
                object offersWrapper = FindOffersWrapper();
                if (offersWrapper == null) return "{\"error\":\"OffersWrapper not reachable: " + Esc(_offersWrapperDiag) + "\"}";
                object offersData = Prop(offersWrapper, "OffersData");
                if (offersData == null) return "{\"error\":\"OffersData null\"}";
                object giveOffers = Prop(offersData, "GiveOffers");
                if (giveOffers == null) return "{\"error\":\"GiveOffers null\"}";

                var sb = new StringBuilder();
                sb.Append("{\"offers\":[");
                int n = 0;
                foreach (var offer in ListItems(giveOffers))
                {
                    if (offer == null) continue;
                    if (n > 0) sb.Append(",");
                    sb.Append("{");
                    // Walk the user-side GiveOfferDto fields.
                    int id = TryInt(Prop(offer, "Id"));
                    int promoId = TryInt(Prop(offer, "PromoOfferId"));
                    string typeId = SafeStr(Prop(offer, "TypeId"));
                    string state = SafeStr(Prop(offer, "StateId"));
                    int stateInt;
                    try { stateInt = Convert.ToInt32(Prop(offer, "StateId")); } catch { stateInt = -1; }
                    object freeData = Prop(offer, "FreeOfferData");
                    object price = Prop(offer, "Price");
                    bool hasFreeData = freeData != null;

                    // Try to detect zero-price (no resources required).
                    bool priceIsEmpty = false;
                    if (price != null)
                    {
                        object isE = Prop(price, "IsEmpty");
                        if (isE is bool be) priceIsEmpty = be;
                    }
                    int purchaseDatesCount = IntProp(Prop(offer, "PurchaseDates"), "Count");

                    sb.Append("\"id\":").Append(id);
                    sb.Append(",\"promo_offer_id\":").Append(promoId);
                    sb.Append(",\"type_id\":\"").Append(Esc(typeId)).Append("\"");
                    sb.Append(",\"state_id\":\"").Append(Esc(state)).Append("\"");
                    sb.Append(",\"state_int\":").Append(stateInt);
                    sb.Append(",\"has_free_data\":").Append(hasFreeData ? "true" : "false");
                    sb.Append(",\"price_is_empty\":").Append(priceIsEmpty ? "true" : "false");
                    sb.Append(",\"purchase_dates_count\":").Append(purchaseDatesCount);
                    sb.Append("}");
                    n++;
                }
                sb.Append("],\"count\":").Append(n).Append("}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // OffersWrapper.Static is the FULL catalog of ClientStaticOffer
        // (63+ items including Mystery Shard, Silver Ticket, Ancient
        // Shard, etc.). UserOfferData.StaticOffers is the sparse user
        // history (only offers the user has interacted with).
        // To find claimable FREE offers we walk the catalog.
        private string ListStaticCatalog()
        {
            try
            {
                object offersWrapper = FindOffersWrapper();
                if (offersWrapper == null) return "{\"error\":\"OffersWrapper not reachable\"}";
                object catalog = Prop(offersWrapper, "Static");
                if (catalog == null) return "{\"error\":\"Static catalog null\"}";

                var sb = new StringBuilder();
                sb.Append("{\"offers\":[");
                int n = 0;
                int freeN = 0;
                foreach (var co in ListItems(catalog))
                {
                    if (co == null) continue;
                    int offerId = TryInt(Prop(co, "OfferId"));
                    int promoId = TryInt(Prop(co, "PromotionId"));
                    string typeId = SafeStr(Prop(co, "TypeId"));
                    string title = SafeStr(Prop(co, "Title"));

                    // FREE = no in-game-resource price AND no real-money PriceId.
                    // Many "free-looking" entries are actually USD packs whose
                    // Price.IsEmpty is true but PriceId is set (e.g. USD499).
                    object price = Prop(co, "Price");
                    bool priceEmpty = false;
                    if (price != null)
                    {
                        object isE = Prop(price, "IsEmpty");
                        if (isE is bool be) priceEmpty = be;
                        if (!priceEmpty)
                        {
                            object total = Prop(price, "Total");
                            if (total != null)
                            {
                                try { priceEmpty = (Convert.ToInt64(total) == 0); } catch { }
                            }
                        }
                    }
                    else priceEmpty = true;

                    object priceId = Prop(co, "PriceId");
                    bool hasMoneyPrice = false;
                    if (priceId != null)
                    {
                        // Nullable<X> reports HasValue here (and IL2Cpp wraps
                        // these with an interop pointer; if non-null, they
                        // have a real currency code).
                        object hv = Prop(priceId, "HasValue");
                        if (hv is bool h && h) hasMoneyPrice = true;
                        else
                        {
                            // some builds return raw ref; non-null means value
                            string s = SafeStr(priceId);
                            if (!string.IsNullOrEmpty(s) && s != "null") hasMoneyPrice = true;
                        }
                    }
                    if (hasMoneyPrice) continue;
                    if (!priceEmpty) continue;
                    freeN++;
                    if (n > 0) sb.Append(",");
                    sb.Append("{");
                    sb.Append("\"offer_id\":").Append(offerId);
                    sb.Append(",\"promotion_id\":").Append(promoId);
                    sb.Append(",\"type_id\":\"").Append(Esc(typeId)).Append("\"");
                    sb.Append(",\"title\":\"").Append(Esc(title)).Append("\"");
                    // PurchaseLimit info
                    object limit = Prop(co, "PurchaseLimit");
                    if (limit != null)
                    {
                        int max = IntProp(limit, "MaxCount");
                        string refresh = SafeStr(Prop(limit, "RefreshType"))
                                      ?? SafeStr(Prop(limit, "PurchaseRefreshTypeId"));
                        sb.Append(",\"max_per_cycle\":").Append(max);
                        sb.Append(",\"refresh_type\":\"").Append(Esc(refresh)).Append("\"");
                    }
                    sb.Append("}");
                    n++;
                }
                sb.Append("],\"free_count\":").Append(freeN);
                sb.Append(",\"catalog_total\":");
                int catalogTotal = 0;
                foreach (var _x in ListItems(catalog)) catalogTotal++;
                sb.Append(catalogTotal).Append("}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // =====================================================
        // API: /claim-free-shop-by-onclick
        //
        // Bypass the broken PurchaseStaticOfferCmd ctor by walking the
        // open BankOverlay dialog's StaticCommonOfferContext list and
        // invoking _onClick directly — same path as the user tapping
        // the in-game "Claim" button.
        //
        // Requires the shop dialog to be already open. The Python tool
        // (daily_shop.py) clicks ShopButton, waits, then calls this
        // endpoint, then dismisses.
        // =====================================================
        private string ClaimFreeShopByOnClick()
        {
            try
            {
                // Strategy: walk ALL MonoBehaviours in the scene, look for
                // any whose IL2CPP class name is BaseView (or a subclass)
                // AND whose .Context returns a StaticCommonOfferContext.
                // For each such context: check _isFree.Value, invoke _onClick.
                //
                // This avoids the BankOverlayContext lookup (which fails
                // because BaseView.Context returns IContext interface that
                // reflects oddly through IL2CPP interop). Going straight to
                // the offer-tile views is more direct anyway.
                var allMbs = Resources.FindObjectsOfTypeAll<MonoBehaviour>();
                int invoked = 0, freeAvail = 0, sawTiles = 0;
                var titles = new List<string>();
                var seen = new HashSet<string>();

                // Hybrid approach: use managed Activator wrapper for property
                // reads (BoolProperty.Value works fine through .NET reflection),
                // but use raw IL2CPP method invoke for the Action delegate
                // (managed wrappers don't expose Action targets cleanly).
                var managedT = FindType(
                    "Client.ViewModel.Contextes.Bank.Offers.StaticCommon.StaticCommonOfferContext");
                foreach (var mb in allMbs)
                {
                    if (mb == null) continue;
                    IntPtr ctxPtr = IntPtr.Zero;
                    string ctxCn = null;
                    try
                    {
                        IntPtr monoPtr = mb.Pointer;
                        if (monoPtr == IntPtr.Zero) continue;
                        IntPtr monoCls = il2cpp_object_get_class(monoPtr);
                        IntPtr getCtx = FindIL2CPPMethod(monoCls, "get_Context", 0);
                        if (getCtx == IntPtr.Zero) continue;
                        IntPtr exc = IntPtr.Zero;
                        ctxPtr = il2cpp_runtime_invoke(getCtx, monoPtr, IntPtr.Zero, ref exc);
                        if (ctxPtr == IntPtr.Zero || exc != IntPtr.Zero) continue;
                        IntPtr ctxCls = il2cpp_object_get_class(ctxPtr);
                        ctxCn = Marshal.PtrToStringAnsi(il2cpp_class_get_name(ctxCls));
                        if (string.IsNullOrEmpty(ctxCn)) continue;
                        seen.Add(ctxCn);
                    }
                    catch { continue; }

                    if (ctxCn != "StaticCommonOfferContext") continue;
                    sawTiles++;

                    // Get the managed wrapper to read properties.
                    object ctx = null;
                    if (managedT != null)
                    {
                        try { ctx = Activator.CreateInstance(managedT, ctxPtr); } catch { }
                    }
                    if (ctx == null) continue;

                    // Read _isFree.Value via managed reflection
                    object isFreeProp = Prop(ctx, "_isFree");
                    bool isFree = false;
                    if (isFreeProp != null)
                    {
                        object v = Prop(isFreeProp, "Value");
                        if (v is bool b) isFree = b;
                    }
                    if (!isFree) continue;
                    freeAvail++;

                    // Title
                    object offer0 = Prop(ctx, "_offer");
                    string title0 = SafeStr(Prop(offer0, "Title"));
                    if (string.IsNullOrEmpty(title0)) title0 = "offer#" + sawTiles;

                    // Read _offerState
                    int stateVal = -1;
                    {
                        object stateProp = Prop(ctx, "_offerState");
                        if (stateProp != null)
                        {
                            object v = Prop(stateProp, "Value");
                            if (v != null)
                            {
                                try { stateVal = Convert.ToInt32(v); } catch { }
                            }
                        }
                    }

                    // _onClick is a PRIVATE FIELD (Action _onClick at offset 0xB0
                    // per dump.cs). It has no getter method — read the field
                    // directly via il2cpp_class_get_fields iteration to find
                    // the offset (offsets shift between game versions, so
                    // don't hardcode 0xB0).
                    IntPtr ctxClsPtr = il2cpp_object_get_class(ctxPtr);
                    uint onClickOff = 0;
                    {
                        IntPtr fIter = IntPtr.Zero; IntPtr fld;
                        IntPtr scanCls = ctxClsPtr;
                        while (scanCls != IntPtr.Zero && onClickOff == 0)
                        {
                            fIter = IntPtr.Zero;
                            while ((fld = il2cpp_class_get_fields(scanCls, ref fIter)) != IntPtr.Zero)
                            {
                                string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(fld));
                                if (fn == "_onClick")
                                {
                                    onClickOff = il2cpp_field_get_offset(fld);
                                    break;
                                }
                            }
                            scanCls = il2cpp_class_get_parent(scanCls);
                        }
                    }
                    if (onClickOff == 0)
                    {
                        Logger.LogWarning("[ClaimFreeOnClick] '" + title0 + "' no _onClick field on IL2CPP class");
                        continue;
                    }
                    IntPtr onClickPtr = Marshal.ReadIntPtr(ctxPtr, (int)onClickOff);
                    if (onClickPtr == IntPtr.Zero)
                    {
                        Logger.LogWarning("[ClaimFreeOnClick] '" + title0 + "' _onClick null (state=" + stateVal + ")");
                        continue;
                    }
                    IntPtr actionCls = il2cpp_object_get_class(onClickPtr);
                    IntPtr invokeMPtr = FindIL2CPPMethod(actionCls, "Invoke", 0);
                    if (invokeMPtr == IntPtr.Zero)
                    {
                        Logger.LogWarning("[ClaimFreeOnClick] '" + title0 + "' no Invoke on Action");
                        continue;
                    }
                    IntPtr ex6 = IntPtr.Zero;
                    try
                    {
                        il2cpp_runtime_invoke(invokeMPtr, onClickPtr, IntPtr.Zero, ref ex6);
                        if (ex6 != IntPtr.Zero)
                        {
                            Logger.LogWarning("[ClaimFreeOnClick] '" + title0 + "' IL2CPP exception fired");
                            continue;
                        }
                        invoked++;
                        titles.Add(title0);
                        Logger.LogInfo("[ClaimFreeOnClick] invoked '" + title0 + "' (state=" + stateVal + ")");
                    }
                    catch (Exception iex)
                    {
                        Logger.LogWarning("[ClaimFreeOnClick] '" + title0 + "' Invoke threw: "
                                          + iex.GetType().Name + ": " + iex.Message);
                    }
                }

                if (sawTiles == 0)
                {
                    Logger.LogWarning("[ClaimFreeOnClick] no StaticCommonOfferContext active. Top context types seen: "
                                      + string.Join(",", seen));
                    return "{\"error\":\"BankOverlayContext not found — open shop first (no offer tiles)\"}";
                }

                var sbResult = new StringBuilder();
                sbResult.Append("{\"invoked\":").Append(invoked);
                sbResult.Append(",\"free_available\":").Append(freeAvail);
                sbResult.Append(",\"saw_tiles\":").Append(sawTiles);
                sbResult.Append(",\"titles\":[");
                for (int i = 0; i < titles.Count; i++)
                {
                    if (i > 0) sbResult.Append(",");
                    sbResult.Append("\"").Append(Esc(titles[i])).Append("\"");
                }
                sbResult.Append("]}");
                return sbResult.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // Legacy BankOverlay-tree walker — kept commented as reference. The
        // IL2CPP-direct approach above is more reliable.
        private string ClaimFreeShopByOnClick_Legacy()
        {
            try
            {
                object bankCtx = null;
                string[] roots = new[] {
                    "UIManager/Canvas (Ui Root)/OverlayDialogs",
                    "UIManager/Canvas (Ui Root)/Dialogs",
                };
                string foundUnder = null;
                foreach (var rootPath in roots)
                {
                    var root = GameObject.Find(rootPath);
                    if (root == null) continue;
                    for (int i = 0; i < root.transform.childCount && bankCtx == null; i++)
                    {
                        var child = root.transform.GetChild(i).gameObject;
                        if (!child.activeSelf) continue;
                        bankCtx = FindContextOfClass(child.transform, "BankOverlayContext", 6);
                        if (bankCtx != null) foundUnder = rootPath + "/" + child.name;
                    }
                    if (bankCtx != null) break;
                }
                if (bankCtx == null)
                {
                    // Diagnostic with IL2CPP class names — managed
                    // GetType().Name returns "MonoBehaviour" for IL2CPP-wrapped
                    // views; we need il2cpp_class_get_name to see real names.
                    var seen = new HashSet<string>();
                    foreach (var rootPath in roots)
                    {
                        var root = GameObject.Find(rootPath);
                        if (root == null) continue;
                        for (int i = 0; i < root.transform.childCount; i++)
                        {
                            var child = root.transform.GetChild(i).gameObject;
                            if (!child.activeSelf) continue;
                            var mbs = child.GetComponentsInChildren<MonoBehaviour>(true);
                            foreach (var mb in mbs)
                            {
                                if (mb == null) continue;
                                try
                                {
                                    IntPtr monoPtr = mb.Pointer;
                                    if (monoPtr == IntPtr.Zero) continue;
                                    IntPtr monoCls = il2cpp_object_get_class(monoPtr);
                                    if (monoCls == IntPtr.Zero) continue;
                                    string cn = Marshal.PtrToStringAnsi(il2cpp_class_get_name(monoCls));
                                    if (string.IsNullOrEmpty(cn)) continue;
                                    if (cn.StartsWith("UI") || cn.StartsWith("TMP") ||
                                        cn.StartsWith("Canvas") || cn.StartsWith("Layout") ||
                                        cn.StartsWith("Image") || cn.StartsWith("Text") ||
                                        cn.StartsWith("Scroll") || cn.StartsWith("Mask") ||
                                        cn == "MonoBehaviour" || cn.StartsWith("RectTransform") ||
                                        cn.StartsWith("Toggle") || cn.StartsWith("Button") ||
                                        cn.StartsWith("Animator") || cn.StartsWith("Selectable")) continue;
                                    seen.Add(cn);
                                }
                                catch { }
                            }
                        }
                    }
                    Logger.LogWarning("[ClaimFreeOnClick] no BankOverlayContext. IL2CPP MB types: "
                                      + string.Join(",", seen));
                    return "{\"error\":\"BankOverlayContext not found — open shop first\"}";
                }
                Logger.LogInfo("[ClaimFreeOnClick] found BankOverlayContext under " + foundUnder);

                // 2. Walk _tabs (TabsContext`1) -> .Tabs (or _tabs._items?) -> per-tab _offers.
                object tabsCtx = Prop(bankCtx, "_tabs");
                if (tabsCtx == null)
                    return "{\"error\":\"BankOverlayContext._tabs null\"}";

                // TabsContext`1 typically exposes its tab list via Tabs/Items/_tabs.
                object tabList = null;
                foreach (var n in new[] { "Tabs", "Items", "_tabs", "_items" })
                {
                    tabList = Prop(tabsCtx, n);
                    if (tabList != null) break;
                }
                if (tabList == null)
                    return "{\"error\":\"could not locate tab list on TabsContext\"}";

                int sawTabs = 0;
                int sawOffers = 0;
                int freeAvailable = 0;
                int invoked = 0;
                int skipped = 0;
                var titles = new List<string>();

                foreach (var tab in ListItems(tabList))
                {
                    if (tab == null) continue;
                    sawTabs++;
                    object offers = Prop(tab, "_offers");
                    if (offers == null) continue;
                    foreach (var off in ListItems(offers))
                    {
                        if (off == null) continue;
                        sawOffers++;
                        // _isFree:BoolProperty → .Value:bool
                        object isFreeProp = Prop(off, "_isFree");
                        bool isFree = false;
                        if (isFreeProp != null)
                        {
                            object val = Prop(isFreeProp, "Value");
                            if (val is bool b) isFree = b;
                        }
                        if (!isFree) { skipped++; continue; }

                        // _offerState:IntProperty → .Value:int
                        object stateProp = Prop(off, "_offerState");
                        int stateVal = -1;
                        if (stateProp != null)
                        {
                            object val = Prop(stateProp, "Value");
                            if (val != null)
                            {
                                try { stateVal = Convert.ToInt32(val); } catch { }
                            }
                        }
                        // StaticOfferState enum: Available is typically 1.
                        // Be permissive — anything not "Locked" / "Bought"
                        // could be claimable. Empirically we'll see what works.
                        if (stateVal != 1 && stateVal != 0) { skipped++; continue; }
                        freeAvailable++;

                        // _onClick:Action → .Invoke()
                        object onClick = Prop(off, "_onClick");
                        if (onClick == null) { skipped++; continue; }
                        var invokeM = onClick.GetType().GetMethod("Invoke",
                            BindingFlags.Public | BindingFlags.Instance);
                        if (invokeM == null) { skipped++; continue; }
                        try
                        {
                            invokeM.Invoke(onClick, null);
                            invoked++;
                            // Title for diagnostics
                            object offer = Prop(off, "_offer");
                            string title = SafeStr(Prop(offer, "Title"));
                            if (string.IsNullOrEmpty(title)) title = "offer#" + invoked;
                            titles.Add(title);
                            Logger.LogInfo("[ClaimFreeOnClick] invoked _onClick on '" + title
                                           + "' (state=" + stateVal + ")");
                        }
                        catch (System.Exception iex)
                        {
                            Logger.LogWarning("[ClaimFreeOnClick] _onClick threw: "
                                              + iex.GetType().Name + ": " + iex.Message);
                            skipped++;
                        }
                    }
                }

                var sb = new StringBuilder();
                sb.Append("{\"invoked\":").Append(invoked);
                sb.Append(",\"free_available\":").Append(freeAvailable);
                sb.Append(",\"saw_offers\":").Append(sawOffers);
                sb.Append(",\"saw_tabs\":").Append(sawTabs);
                sb.Append(",\"skipped\":").Append(skipped);
                sb.Append(",\"titles\":[");
                for (int i = 0; i < titles.Count; i++)
                {
                    if (i > 0) sb.Append(",");
                    sb.Append("\"").Append(Esc(titles[i])).Append("\"");
                }
                sb.Append("]}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // BFS the GameObject tree under `root` for a MonoBehaviour
        // exposing a target context. Tries the standard "Context" property
        // (DialogContext views) first, then walks all properties +
        // accessible fields on each MB looking for one whose runtime
        // type name contains `className`. Falls back to scanning fields
        // because OverlayContext-bound views use a different field name.
        private object FindContextOfClass(Transform root, string className, int depthLimit)
        {
            if (root == null || depthLimit < 0) return null;
            var mbs = root.GetComponentsInChildren<MonoBehaviour>(true);

            // Pass 1: standard Context-property scan (covers DialogContexts).
            foreach (var mb in mbs)
            {
                if (mb == null) continue;
                try
                {
                    var ctxProp = mb.GetType().GetProperty("Context",
                        BindingFlags.Public | BindingFlags.NonPublic |
                        BindingFlags.Instance | BindingFlags.FlattenHierarchy);
                    if (ctxProp == null) continue;
                    object ctx = ctxProp.GetValue(mb);
                    if (ctx == null) continue;
                    string cn = ctx.GetType().Name;
                    if (cn.Contains(className)) return ctx;
                }
                catch { }
            }

            // Pass 2: scan all properties + accessible fields on each MB
            // for any of OverlayContext-shape (matches className).
            foreach (var mb in mbs)
            {
                if (mb == null) continue;
                var t = mb.GetType();
                try
                {
                    foreach (var p in t.GetProperties(
                        BindingFlags.Public | BindingFlags.NonPublic |
                        BindingFlags.Instance | BindingFlags.FlattenHierarchy))
                    {
                        if (p.PropertyType == null) continue;
                        var ptn = p.PropertyType.Name;
                        if (ptn == null) continue;
                        // skip primitives
                        if (p.PropertyType.IsPrimitive) continue;
                        // quick skip if name doesn't even look like a context
                        if (!ptn.Contains(className) && !ptn.EndsWith("Context")) continue;
                        try
                        {
                            object v = p.GetValue(mb);
                            if (v == null) continue;
                            string cn = v.GetType().Name;
                            if (cn.Contains(className)) return v;
                        }
                        catch { }
                    }
                }
                catch { }
                try
                {
                    foreach (var f in t.GetFields(
                        BindingFlags.Public | BindingFlags.NonPublic |
                        BindingFlags.Instance | BindingFlags.FlattenHierarchy))
                    {
                        if (f.FieldType == null) continue;
                        var ftn = f.FieldType.Name;
                        if (!ftn.Contains(className) && !ftn.EndsWith("Context")) continue;
                        try
                        {
                            object v = f.GetValue(mb);
                            if (v == null) continue;
                            string cn = v.GetType().Name;
                            if (cn.Contains(className)) return v;
                        }
                        catch { }
                    }
                }
                catch { }
            }
            return null;
        }

        private string ListOpenOffers()
        {
            try
            {
                object offersWrapper = FindOffersWrapper();
                if (offersWrapper == null) return "{\"error\":\"OffersWrapper not reachable\"}";
                object offersData = Prop(offersWrapper, "OffersData");
                if (offersData == null) return "{\"error\":\"OffersData null\"}";
                object openOffers = Prop(offersData, "OpenOffers");
                if (openOffers == null) return "{\"error\":\"OpenOffers null\"}";

                var sb = new StringBuilder();
                sb.Append("{\"offers\":[");
                int n = 0;
                foreach (var offer in ListItems(openOffers))
                {
                    if (offer == null) continue;
                    if (n > 0) sb.Append(",");
                    int id = TryInt(Prop(offer, "Id"));
                    string typeId = SafeStr(Prop(offer, "TypeId"));
                    string typeName = offer.GetType().Name;
                    sb.Append("{");
                    sb.Append("\"id\":").Append(id);
                    sb.Append(",\"type_id\":\"").Append(Esc(typeId)).Append("\"");
                    sb.Append(",\"clr_type\":\"").Append(Esc(typeName)).Append("\"");
                    sb.Append("}");
                    n++;
                }
                sb.Append("],\"count\":").Append(n).Append("}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // Walk EVERY offer-typed collection on OffersWrapper + OffersData
        // to map where various offer kinds live. Used to track down which
        // collection holds the "Packs FREE refresh" Mystery Shard / Silver
        // Ticket entries.
        private string ListAllOfferCollections()
        {
            try
            {
                object offersWrapper = FindOffersWrapper();
                if (offersWrapper == null) return "{\"error\":\"OffersWrapper not reachable\"}";

                var sb = new StringBuilder();
                sb.Append("{\"collections\":[");
                int colN = 0;

                foreach (var src in new[] { offersWrapper, Prop(offersWrapper, "OffersData") })
                {
                    if (src == null) continue;
                    string srcName = src.GetType().Name;
                    foreach (var prop in src.GetType().GetProperties(
                        BindingFlags.Public | BindingFlags.Instance))
                    {
                        if (!prop.PropertyType.Name.StartsWith("List")
                            && !prop.PropertyType.Name.StartsWith("IEnumerable"))
                            continue;
                        // skip obvious non-offer fields
                        string pname = prop.Name;
                        if (pname.StartsWith("Local") || pname.StartsWith("Closed")) continue;

                        object collection;
                        try { collection = prop.GetValue(src); } catch { continue; }
                        if (collection == null) continue;

                        // Count items + sample first 2
                        int count = 0;
                        var samples = new List<string>();
                        foreach (var item in ListItems(collection))
                        {
                            if (item == null) continue;
                            count++;
                            if (samples.Count < 2)
                            {
                                int id = TryInt(Prop(item, "Id"));
                                string tid = SafeStr(Prop(item, "TypeId"));
                                string state = SafeStr(Prop(item, "StateId"));
                                bool freeData = Prop(item, "FreeOfferData") != null;
                                string ctn = item.GetType().Name;
                                samples.Add("{\"id\":" + id
                                    + ",\"type_id\":\"" + Esc(tid) + "\""
                                    + ",\"state\":\"" + Esc(state) + "\""
                                    + ",\"clr\":\"" + Esc(ctn) + "\""
                                    + ",\"free\":" + (freeData ? "true" : "false") + "}");
                            }
                        }
                        if (colN > 0) sb.Append(",");
                        sb.Append("{\"src\":\"" + Esc(srcName)
                            + "\",\"prop\":\"" + Esc(pname)
                            + "\",\"item_type\":\"" + Esc(prop.PropertyType.Name)
                            + "\",\"count\":" + count
                            + ",\"samples\":[" + string.Join(",", samples) + "]}");
                        colN++;
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

        private string ClaimFreeGiveOffers()
        {
            try
            {
                object offersWrapper = FindOffersWrapper();
                if (offersWrapper == null) return "{\"error\":\"OffersWrapper not reachable: " + Esc(_offersWrapperDiag) + "\"}";
                object offersData = Prop(offersWrapper, "OffersData");
                if (offersData == null) return "{\"error\":\"OffersData null\"}";
                object giveOffers = Prop(offersData, "GiveOffers");
                if (giveOffers == null) return "{\"error\":\"GiveOffers null\"}";

                var cmdType = FindType(
                    "Client.Model.Gameplay.Bank.Payments.Commands.PurchaseGiveOfferCmd");
                if (cmdType == null) return "{\"error\":\"PurchaseGiveOfferCmd type not found\"}";
                var dtoType = FindType(
                    "SharedModel.Meta.Offers.Dto.BuyGiveOfferRequestDto");
                if (dtoType == null) return "{\"error\":\"BuyGiveOfferRequestDto type not found\"}";

                var sb = new StringBuilder();
                sb.Append("{\"claimed\":[");
                int claimed = 0, skippedNotFree = 0, skippedAlreadyBought = 0, errors = 0;

                foreach (var offer in ListItems(giveOffers))
                {
                    if (offer == null) continue;

                    // FREE marker: FreeOfferData!=null OR Price.IsEmpty.
                    object freeData = Prop(offer, "FreeOfferData");
                    object price = Prop(offer, "Price");
                    bool isFree = freeData != null;
                    if (!isFree && price != null)
                    {
                        object isE = Prop(price, "IsEmpty");
                        if (isE is bool be && be) isFree = true;
                    }
                    if (!isFree) { skippedNotFree++; continue; }

                    // Skip if already-bought-this-cycle hint (purchase dates >0
                    // AND state suggests bought). Server validates anyway.
                    int stateInt;
                    try { stateInt = Convert.ToInt32(Prop(offer, "StateId")); }
                    catch { stateInt = -1; }
                    int pdCount = IntProp(Prop(offer, "PurchaseDates"), "Count");
                    // Heuristic: state 5 = Bought in observed enum order.
                    // Don't gate strictly — server is authoritative — but log.
                    int offerId = TryInt(Prop(offer, "Id"));
                    if (offerId <= 0) { errors++; continue; }

                    // PurchaseGiveOfferCmd ctor (from dump.cs):
                    //   .ctor(int id, string name = "", bool activate = false,
                    //         Nullable<bool> isAutoBattle)
                    // Same Nullable-wrap pattern as PurchaseStaticOfferCmd:
                    // managed null causes NRE inside Edit; build the IL2Cpp
                    // Nullable<bool> with HasValue=false instead.
                    object cmd = null;
                    foreach (var c in cmdType.GetConstructors(
                        BindingFlags.Public | BindingFlags.Instance))
                    {
                        var ps = c.GetParameters();
                        if (ps.Length != 4) continue;
                        try
                        {
                            var nullableBoolT = ps[3].ParameterType;
                            object nullableBool = null;
                            try
                            {
                                var c0 = nullableBoolT.GetConstructor(System.Type.EmptyTypes);
                                if (c0 != null) nullableBool = c0.Invoke(null);
                                else nullableBool = System.Activator.CreateInstance(nullableBoolT);
                            }
                            catch { }
                            cmd = c.Invoke(new object[] {
                                offerId,        // id (catalog/promo offer id)
                                "",             // name
                                false,          // activate
                                nullableBool,   // isAutoBattle (Nullable<bool> empty)
                            });
                            break;
                        }
                        catch (System.Reflection.TargetInvocationException tex)
                        {
                            var inner = tex.InnerException ?? tex;
                            Logger.LogWarning("[ClaimFreeGive] ctor err id=" + offerId
                                              + ": " + inner.GetType().Name + ": " + inner.Message);
                        }
                        catch (System.Exception cex)
                        {
                            Logger.LogWarning("[ClaimFreeGive] ctor err id=" + offerId
                                              + ": " + cex.GetType().Name + ": " + cex.Message);
                        }
                    }
                    if (cmd == null) { errors++; continue; }

                    // IfError diag
                    try
                    {
                        var ifErrorM = cmd.GetType().GetMethod("IfError",
                            BindingFlags.Instance | BindingFlags.Public | BindingFlags.FlattenHierarchy,
                            null, new[] { typeof(System.Action) }, null);
                        if (ifErrorM != null)
                        {
                            int captured = offerId;
                            System.Action errCb = () =>
                                Logger.LogWarning("[ClaimFreeGive] server rejected id=" + captured);
                            ifErrorM.Invoke(cmd, new object[] { errCb });
                        }
                    }
                    catch { }

                    Logger.LogInfo("[ClaimFreeGive] enqueue id=" + offerId
                                   + " state=" + stateInt + " pd_count=" + pdCount);
                    try
                    {
                        InvokeExecute(cmd);
                        if (claimed > 0) sb.Append(",");
                        sb.Append("{\"id\":").Append(offerId)
                          .Append(",\"state\":").Append(stateInt).Append("}");
                        claimed++;
                    }
                    catch (System.Exception ex)
                    {
                        Logger.LogWarning("[ClaimFreeGive] exec err id=" + offerId + ": " + ex.Message);
                        errors++;
                    }
                }

                sb.Append("],\"claimed_count\":").Append(claimed);
                sb.Append(",\"skipped_not_free\":").Append(skippedNotFree);
                sb.Append(",\"errors\":").Append(errors).Append("}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // =====================================================
        // API: /claim-free-shop-offers
        //
        // Walks UserStaticOffer list, finds offers where the matching
        // ClientStaticOffer has an empty/zero Price AND state is
        // Available, fires PurchaseStaticOfferCmd per offer.
        //
        // Mystery Shard / Silver Ticket / similar daily FREE packs
        // come through here.
        // =====================================================
        private static int TryInt(object v)
        {
            if (v == null) return 0;
            try { return Convert.ToInt32(v); } catch { return 0; }
        }
        private static string SafeStr(object v)
        {
            if (v == null) return "";
            try { return v.ToString() ?? ""; } catch { return ""; }
        }

        // Resolve a ClientStaticOffer by Id from the static-data manager.
        // Returns null if not found (e.g. expired/removed offer).
        private object FindClientStaticOffer(int offerId)
        {
            try
            {
                var appModelType = FindType("Client.Model.AppModel");
                var instProp = appModelType?.GetProperty("Instance",
                    BindingFlags.Public | BindingFlags.Static);
                object appModel = instProp?.GetValue(null);
                if (appModel == null) return null;

                object sdm = Prop(appModel, "_StaticDataManager_k__BackingField")
                          ?? Prop(appModel, "StaticDataManager");
                if (sdm == null) return null;

                // Static data has a ClientOffersManager / similar walker.
                // Try common shapes — first look for a property whose name
                // contains "StaticOffer" returning a list/dict.
                foreach (var p in sdm.GetType().GetProperties(
                    BindingFlags.Public | BindingFlags.Instance))
                {
                    if (p.PropertyType == null) continue;
                    string pname = p.Name;
                    if (pname.IndexOf("StaticOffer", StringComparison.OrdinalIgnoreCase) < 0
                        && pname.IndexOf("Offers", StringComparison.OrdinalIgnoreCase) < 0)
                        continue;
                    object container;
                    try { container = p.GetValue(sdm); } catch { continue; }
                    if (container == null) continue;
                    // dict by id?
                    var indexer = container.GetType().GetMethod("get_Item",
                        BindingFlags.Public | BindingFlags.Instance,
                        null, new[] { typeof(int) }, null);
                    if (indexer != null)
                    {
                        try
                        {
                            object hit = indexer.Invoke(container, new object[] { offerId });
                            if (hit != null) return hit;
                        }
                        catch { }
                    }
                    // List<ClientStaticOffer>?
                    foreach (var item in ListItems(container))
                    {
                        if (item == null) continue;
                        int itemId = TryInt(Prop(item, "OfferId"));
                        if (itemId == offerId) return item;
                    }
                }
            }
            catch { }
            return null;
        }

        // Determine if a ClientStaticOffer is FREE (price total = 0).
        // Resources class has either a Total/IsEmpty property or a
        // dictionary of resource-id->amount.
        private bool ClientOfferIsFree(object clientOffer)
        {
            if (clientOffer == null) return false;
            try
            {
                object price = Prop(clientOffer, "Price");
                if (price == null) return true;  // no price field == free
                // Try IsEmpty
                object isEmpty = Prop(price, "IsEmpty");
                if (isEmpty is bool b && b) return true;
                // Try Total (Int64 or similar)
                object total = Prop(price, "Total");
                if (total != null)
                {
                    try { return Convert.ToInt64(total) == 0; } catch { }
                }
                // Fall through: walk any IEnumerable on Price for non-zero amounts
                bool sawNonZero = false;
                foreach (var entry in ListItems(price))
                {
                    if (entry == null) continue;
                    object amt = Prop(entry, "Amount") ?? Prop(entry, "Value");
                    if (amt != null)
                    {
                        try { if (Convert.ToInt64(amt) != 0) { sawNonZero = true; break; } }
                        catch { }
                    }
                }
                return !sawNonZero;
            }
            catch { return false; }
        }

        // Returns true if a ClientStaticOffer is FREE (no in-game cost, no
        // real-money PriceId). Mirrors the filter in ListStaticCatalog.
        private bool ClientStaticOfferIsFree(object co)
        {
            if (co == null) return false;
            object price = Prop(co, "Price");
            bool priceEmpty = false;
            if (price != null)
            {
                object isE = Prop(price, "IsEmpty");
                if (isE is bool be) priceEmpty = be;
                if (!priceEmpty)
                {
                    object total = Prop(price, "Total");
                    if (total != null)
                    {
                        try { priceEmpty = (Convert.ToInt64(total) == 0); } catch { }
                    }
                }
            }
            else priceEmpty = true;
            if (!priceEmpty) return false;

            object priceId = Prop(co, "PriceId");
            if (priceId != null)
            {
                object hv = Prop(priceId, "HasValue");
                if (hv is bool h && h) return false;
                string s = SafeStr(priceId);
                if (!string.IsNullOrEmpty(s) && s != "null") return false;
            }
            return true;
        }

        // Walks the user's StaticOffers history to find the most recent
        // purchase date for a given catalog offer_id (matched via
        // UserStaticOffer.PromoOfferId == ClientStaticOffer.OfferId).
        // Returns DateTime.MinValue when never purchased.
        private DateTime LastPurchaseDateFor(object userStaticOffers, int catalogOfferId)
        {
            DateTime latest = DateTime.MinValue;
            if (userStaticOffers == null) return latest;
            foreach (var uo in ListItems(userStaticOffers))
            {
                if (uo == null) continue;
                int promoId = TryInt(Prop(uo, "PromoOfferId"));
                if (promoId != catalogOfferId) continue;
                object dates = Prop(uo, "PurchaseDates");
                foreach (var d in ListItems(dates))
                {
                    if (d == null) continue;
                    try
                    {
                        DateTime dt = (DateTime)d;
                        if (dt > latest) latest = dt;
                    }
                    catch { }
                }
            }
            return latest;
        }

        private string ClaimFreeShopOffers()
        {
            try
            {
                object offersWrapper = FindOffersWrapper();
                if (offersWrapper == null) return "{\"error\":\"OffersWrapper not reachable: " + Esc(_offersWrapperDiag) + "\"}";
                // The CATALOG (OffersWrapper.Static) holds all 63 ClientStaticOffer
                // definitions. The user's purchase history (OffersData.StaticOffers)
                // only carries offers they've ever interacted with — so a brand-
                // new daily-refresh free offer the user has never claimed will
                // NOT appear in the user-side list. Walk the catalog instead.
                object catalog = Prop(offersWrapper, "Static");
                if (catalog == null) return "{\"error\":\"Static catalog null\"}";
                object offersData = Prop(offersWrapper, "OffersData");
                object userHistory = offersData != null ? Prop(offersData, "StaticOffers") : null;

                var cmdType = FindType(
                    "Client.Model.Gameplay.Bank.Payments.Commands.PurchaseStaticOfferCmd");
                if (cmdType == null)
                    return "{\"error\":\"PurchaseStaticOfferCmd type not found\"}";

                var ctors = cmdType.GetConstructors(
                    BindingFlags.Public | BindingFlags.Instance);

                var sb = new StringBuilder();
                sb.Append("{\"claimed\":[");
                int claimedN = 0;
                int skippedNotFree = 0;
                int skippedRecentlyClaimed = 0;
                int errorsN = 0;
                DateTime now = DateTime.UtcNow;

                foreach (var clientOffer in ListItems(catalog))
                {
                    if (clientOffer == null) continue;
                    if (!ClientStaticOfferIsFree(clientOffer)) { skippedNotFree++; continue; }

                    int catalogOfferId = TryInt(Prop(clientOffer, "OfferId"));
                    string title = SafeStr(Prop(clientOffer, "Title"));
                    if (string.IsNullOrEmpty(title)) title = "offer#" + catalogOfferId;

                    // Whitelist Packs-tab FREE refresh offers only. Other
                    // "Price.IsEmpty" entries (Live Arena Refill, Tag Arena
                    // Refill, etc.) actually consume gems via a separate
                    // pricing path and are NOT what the user wants daily-
                    // claimed. Title-based gate is the most reliable filter
                    // since the in-shop tag flag ("FreeOffer") isn't on
                    // ClientStaticOffer directly.
                    string titleLower = title.ToLowerInvariant();
                    bool isPacksFree =
                        titleLower.Contains("mystery shard") ||
                        titleLower.Contains("silver ticket") ||
                        titleLower.Contains("ancient shard");
                    if (!isPacksFree) { skippedNotFree++; continue; }

                    // Refresh-window check: if user purchased within the last
                    // 22h, skip (server will reject anyway, this avoids spam).
                    DateTime last = LastPurchaseDateFor(userHistory, catalogOfferId);
                    if (last != DateTime.MinValue)
                    {
                        TimeSpan since = now - last;
                        if (since.TotalHours < 22)
                        {
                            skippedRecentlyClaimed++;
                            continue;
                        }
                    }

                    // Find or build a UserStaticOffer to pass to the cmd.
                    // First check user history; if not present, server may
                    // accept a freshly-built UserStaticOffer with PromoOfferId
                    // set to the catalog OfferId.
                    object userOffer = null;
                    if (userHistory != null)
                    {
                        foreach (var uo in ListItems(userHistory))
                        {
                            if (uo == null) continue;
                            int promo = TryInt(Prop(uo, "PromoOfferId"));
                            if (promo == catalogOfferId) { userOffer = uo; break; }
                        }
                    }

                    // PurchaseStaticOfferCmd ctor (from il2cppdumper dump.cs):
                    //   (int promoOfferId, string name = "", bool activate = false,
                    //    Nullable<bool> isAutoBattle, Nullable<int> count)
                    //
                    // promoOfferId is the catalog ClientStaticOffer.OfferId.
                    // name is an analytics tag, "" is the default. activate is
                    // critical: passing true previously crashed the game.
                    // Both Nullable args wrapped as Il2CppSystem.Nullable<X>
                    // with HasValue=false (default) — passing managed null
                    // can NRE in cmd internals.
                    object cmd = null;
                    foreach (var c in ctors)
                    {
                        var ps = c.GetParameters();
                        if (ps.Length != 5) continue;
                        try
                        {
                            // Build Il2CppSystem.Nullable<X> with HasValue=false
                            // (zero-arg ctor) for both nullable params.
                            var nullableBoolT = ps[3].ParameterType;
                            var nullableIntT = ps[4].ParameterType;
                            object nullableBool = null;
                            object nullableInt = null;
                            try
                            {
                                var c0 = nullableBoolT.GetConstructor(System.Type.EmptyTypes);
                                if (c0 != null) nullableBool = c0.Invoke(null);
                                else nullableBool = System.Activator.CreateInstance(nullableBoolT);
                            }
                            catch { }
                            try
                            {
                                var c0 = nullableIntT.GetConstructor(System.Type.EmptyTypes);
                                if (c0 != null) nullableInt = c0.Invoke(null);
                                else nullableInt = System.Activator.CreateInstance(nullableIntT);
                            }
                            catch { }

                            cmd = c.Invoke(new object[] {
                                catalogOfferId,   // promoOfferId
                                "",               // name (analytics)
                                false,            // activate (must be false)
                                nullableBool,     // isAutoBattle (Nullable<bool> empty)
                                nullableInt,      // count (Nullable<int> empty — defaults to 1 server-side)
                            });
                            break;
                        }
                        catch (System.Reflection.TargetInvocationException tex)
                        {
                            var inner = tex.InnerException ?? tex;
                            Logger.LogWarning("[ClaimFreeOffer] ctor err id=" + catalogOfferId
                                              + ": " + inner.GetType().Name + ": " + inner.Message);
                        }
                        catch (System.Exception cex)
                        {
                            Logger.LogWarning("[ClaimFreeOffer] ctor err id=" + catalogOfferId
                                              + ": " + cex.GetType().Name + ": " + cex.Message);
                        }
                    }
                    if (cmd == null) { errorsN++; continue; }

                    try
                    {
                        var ifErrorM = cmd.GetType().GetMethod("IfError",
                            BindingFlags.Instance | BindingFlags.Public | BindingFlags.FlattenHierarchy,
                            null, new[] { typeof(System.Action) }, null);
                        if (ifErrorM != null)
                        {
                            var capturedTitle = title;
                            System.Action errCb = () =>
                                Logger.LogWarning("[ClaimFreeOffer] server rejected: " + capturedTitle);
                            ifErrorM.Invoke(cmd, new object[] { errCb });
                        }
                    }
                    catch { }

                    try
                    {
                        Logger.LogInfo("[ClaimFreeOffer] enqueue " + title + " (id=" + catalogOfferId + ")");
                        InvokeExecute(cmd);
                        if (claimedN > 0) sb.Append(",");
                        sb.Append("{\"id\":").Append(catalogOfferId);
                        sb.Append(",\"title\":\"").Append(Esc(title)).Append("\"}");
                        claimedN++;
                    }
                    catch (Exception ex)
                    {
                        Logger.LogWarning("[ClaimFreeOffer] failed " + title + ": " + ex.Message);
                        errorsN++;
                    }
                }

                sb.Append("],\"claimed_count\":").Append(claimedN);
                sb.Append(",\"skipped_not_free\":").Append(skippedNotFree);
                sb.Append(",\"skipped_recently_claimed\":").Append(skippedRecentlyClaimed);
                sb.Append(",\"errors\":").Append(errorsN);
                sb.Append("}");
                return sb.ToString();
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
        // /cvc-multipliers — read the user's active Clan vs Clan tournament
        // and extract per-activity-group multipliers so callers can answer
        // "what locations have 2x CvC right now?". Returns:
        //   {ok, active: bool, ends_at: ms, multipliers: [{group: "Dragon",
        //    multiplier: 2.0, activity_ids: [...], group_id: 5}, ...]}
        // If no CvC tournament is currently active, returns active=false and
        // an empty multipliers list (no fields raised as errors).
        // /event-rewards — for each active tournament/event the user is
        // participating in, return: name, total points, end time, reward
        // milestone tiers with points thresholds, and which tiers are
        // taken/unlocked/skipped. Bridges QuestState -> Quest via the
        // UserQuestData.Quests dict (PrototypeId -> Quest).
        private string GetEventRewards()
        {
            try
            {
                var uw = GetUserWrapper();
                if (uw == null) return "{\"error\":\"Not logged in\"}";
                var tournaments = Prop(uw, "Tournaments");
                if (tournaments == null) return "{\"error\":\"Tournaments wrapper missing\"}";
                // Quests dict lives on UserWrapper.Quests (QuestWrapperReadOnly)
                var questWrapper = Prop(uw, "Quests");
                if (questWrapper == null) return "{\"error\":\"Quests wrapper missing\"}";
                var questsDict = Prop(questWrapper, "Quests");
                if (questsDict == null) return "{\"error\":\"Quests dict missing\"}";

                // Iterate the user's quest states directly. The All() method
                // wraps IEnumerable but won't iterate cleanly via reflection;
                // OpenedStates is a List<QuestState> we can walk normally.
                var qd = Prop(tournaments, "QuestData");
                if (qd == null) return "{\"error\":\"QuestData missing on Tournaments\"}";
                var states = Prop(qd, "OpenedStates");
                if (states == null) return "{\"error\":\"OpenedStates list missing\"}";

                var sb = new StringBuilder(4096);
                sb.Append("{\"ok\":true,\"events\":[");
                int n = 0;
                long nowMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();

                {
                    foreach (var qs in ListItems(states))
                    {
                        if (qs == null) continue;
                        try
                        {
                            int questId = 0, prototypeId = 0;
                            int totalPoints = 0;
                            long deadlineMs = 0;
                            try { questId = Convert.ToInt32(Prop(qs, "QuestId")); } catch { }
                            try { prototypeId = Convert.ToInt32(Prop(qs, "PrototypeId")); } catch { }
                            // TotalPoints (Nullable<int>)
                            try
                            {
                                var v = Prop(qs, "TotalPoints");
                                if (v != null)
                                {
                                    var hv = v.GetType().GetProperty("HasValue");
                                    if (hv != null && (bool)hv.GetValue(v))
                                        totalPoints = (int)v.GetType().GetProperty("Value").GetValue(v);
                                }
                            }
                            catch { }
                            // Walk Completions for live tournament/solo points (more accurate)
                            try
                            {
                                var comps = Prop(qs, "Completions");
                                foreach (var c in ListItems(comps))
                                {
                                    try
                                    {
                                        var bt = Prop(c, "ByTournament");
                                        if (bt != null)
                                        {
                                            var bp = Prop(bt, "ByPoints");
                                            if (bp != null)
                                            {
                                                var cc = Prop(bp, "CountCollected");
                                                if (cc != null) totalPoints = Math.Max(totalPoints, Convert.ToInt32(cc));
                                            }
                                        }
                                        var bs = Prop(c, "BySoloEvent");
                                        if (bs != null)
                                        {
                                            var bp = Prop(bs, "ByPoints");
                                            if (bp != null)
                                            {
                                                var bp2 = Prop(bp, "ByPoints");
                                                if (bp2 != null)
                                                {
                                                    var cc = Prop(bp2, "CountCollected");
                                                    if (cc != null) totalPoints = Math.Max(totalPoints, Convert.ToInt32(cc));
                                                }
                                            }
                                        }
                                    }
                                    catch { }
                                }
                            }
                            catch { }
                            // TimeDeadline (Nullable<DateTime>)
                            try
                            {
                                var v = Prop(qs, "TimeDeadline");
                                if (v != null)
                                {
                                    var hv = v.GetType().GetProperty("HasValue");
                                    if (hv != null && (bool)hv.GetValue(v))
                                    {
                                        var d = v.GetType().GetProperty("Value").GetValue(v);
                                        var ticksProp = d.GetType().GetProperty("Ticks");
                                        if (ticksProp != null)
                                        {
                                            long ticks = (long)ticksProp.GetValue(d);
                                            deadlineMs = (ticks - 621_355_968_000_000_000L) / 10_000L;
                                        }
                                    }
                                }
                            }
                            catch { }

                            // Reward arrays
                            var taken = new System.Collections.Generic.List<int>();
                            var unlocked = new System.Collections.Generic.List<int>();
                            var skipped = new System.Collections.Generic.List<int>();
                            foreach (var (fname, list) in new[] {
                                ("GlobalEventTakenRewardIds", taken),
                                ("GlobalEventUnlockedRewardIds", unlocked),
                                ("GlobalEventSkippedRewardIds", skipped),
                            })
                            {
                                try
                                {
                                    var lst = Prop(qs, fname);
                                    foreach (var x in ListItems(lst))
                                    {
                                        try { list.Add(Convert.ToInt32(x)); } catch { }
                                    }
                                }
                                catch { }
                            }

                            // Look up the Quest in the user's quest dict to get name + tiers
                            string questName = null;
                            string questDescription = null;
                            // Reward tier arrays — emit raw point thresholds + ids
                            var tierLines = new System.Collections.Generic.List<string>();
                            try
                            {
                                // Quests is Il2CppSystem Dictionary<int, Quest> — managed
                                // indexer/TryGetValue paths often fail. Walk the
                                // dict explicitly via the (key,value) enumerator.
                                object quest = null;
                                try
                                {
                                    var dictType = questsDict.GetType();
                                    var getEnum = dictType.GetMethod("GetEnumerator");
                                    var enumerator = getEnum?.Invoke(questsDict, null);
                                    if (enumerator != null)
                                    {
                                        var enumType = enumerator.GetType();
                                        var moveNext = enumType.GetMethod("MoveNext");
                                        var current = enumType.GetProperty("Current");
                                        while ((bool)moveNext.Invoke(enumerator, null))
                                        {
                                            var kvp = current.GetValue(enumerator);
                                            var k = Prop(kvp, "Key");
                                            if (k != null && Convert.ToInt32(k) == prototypeId)
                                            {
                                                quest = Prop(kvp, "Value");
                                                break;
                                            }
                                        }
                                    }
                                }
                                catch { }
                                if (quest != null)
                                {
                                    try { questName = Prop(quest, "Name")?.ToString(); } catch { }
                                    try { questDescription = Prop(quest, "Description")?.ToString(); } catch { }
                                    // Walk Quest.GlobalEventInfo.Rewards or .RewardItemsByGroup
                                    try
                                    {
                                        var info = Prop(quest, "GlobalEventInfo");
                                        if (info != null)
                                        {
                                            // Try different reward field names
                                            object items = null;
                                            foreach (var fn in new[] { "RewardItems", "RewardItemsByGroup", "Rewards", "GlobalEventRewardItems" })
                                            {
                                                try { items = Prop(info, fn); if (items != null) break; }
                                                catch { }
                                            }
                                            if (items != null)
                                            {
                                                // If dict, iterate values; if list, iterate directly
                                                System.Collections.IEnumerable iterRewards = null;
                                                if (items is System.Collections.IDictionary dict)
                                                    iterRewards = dict.Values;
                                                else
                                                    iterRewards = items as System.Collections.IEnumerable;
                                                if (iterRewards != null)
                                                {
                                                    foreach (var rg in iterRewards)
                                                    {
                                                        // rg may be a single GlobalEventRewardItem or a list of them
                                                        var rgList = rg as System.Collections.IEnumerable;
                                                        var toScan = new System.Collections.Generic.List<object>();
                                                        if (rgList != null && !(rg is string))
                                                        {
                                                            foreach (var x in rgList) toScan.Add(x);
                                                        }
                                                        else { toScan.Add(rg); }
                                                        foreach (var ri in toScan)
                                                        {
                                                            if (ri == null) continue;
                                                            int rid = 0;
                                                            int pts = 0;
                                                            try { rid = Convert.ToInt32(Prop(ri, "Id")); } catch { }
                                                            try { pts = Convert.ToInt32(Prop(ri, "Points") ?? Prop(ri, "p")); } catch { }
                                                            if (pts == 0) continue;
                                                            tierLines.Add("{\"id\":" + rid + ",\"points\":" + pts + "}");
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                    catch { }
                                }
                            }
                            catch { }

                            // (filter removed for debugging — show all)

                            if (n > 0) sb.Append(",");
                            sb.Append("{\"quest_id\":").Append(questId);
                            sb.Append(",\"prototype_id\":").Append(prototypeId);
                            sb.Append(",\"name\":\"").Append(Esc(questName ?? "?")).Append("\"");
                            sb.Append(",\"total_points\":").Append(totalPoints);
                            sb.Append(",\"deadline_ms\":").Append(deadlineMs);
                            sb.Append(",\"deadline_in_ms\":").Append(deadlineMs > 0 ? deadlineMs - nowMs : 0);
                            sb.Append(",\"taken_reward_ids\":[").Append(string.Join(",", taken)).Append("]");
                            sb.Append(",\"unlocked_reward_ids\":[").Append(string.Join(",", unlocked)).Append("]");
                            sb.Append(",\"skipped_reward_ids\":[").Append(string.Join(",", skipped)).Append("]");
                            sb.Append(",\"reward_tiers\":[").Append(string.Join(",", tierLines)).Append("]");
                            sb.Append("}");
                            n++;
                        }
                        catch { }
                    }
                }
                sb.Append("],\"count\":").Append(n).Append("}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // Summarize a UserPrize into a short reward label.
        // Inspects the most common fields (Resources, Heroes, Artifacts,
        // Badges) and returns "silver+200000, gem+50, hero r5/g4, badge#X x2".
        private static string SummarizeUserPrize(object up)
        {
            var parts = new System.Collections.Generic.List<string>();
            try
            {
                // Resources (silver/gems/keys/tokens) — Resources.Energy/Silver/Gems/etc.
                var res = Prop(up, "Resources");
                if (res != null)
                {
                    foreach (var fname in new[] { "Energy", "Silver", "Gems", "Tokens",
                        "Arena3X3Tokens", "AutoBattleTickets", "MythicalDust", "PlariumPoints",
                        "AllianceCoin", "AllianceBossKey", "AllianceHydraKeys", "AllianceChimeraKeys",
                        "DoomTowerGoldKeys", "DoomTowerSilverKeys", "FortressKeys" })
                    {
                        try
                        {
                            var v = Prop(res, fname);
                            if (v == null) continue;
                            double n = 0;
                            try { n = Convert.ToDouble(v); } catch { continue; }
                            if (n != 0) parts.Add(fname.ToLower() + "+" + (n >= 1 ? ((long)n).ToString() : n.ToString("F1")));
                        }
                        catch { }
                    }
                }
                // Heroes (List<HeroPrize>) - HeroPrize has TypeId, Rarity, Grade
                try
                {
                    var heroes = Prop(up, "Heroes");
                    foreach (var h in ListItems(heroes))
                    {
                        int rarity = 0, grade = 0, typeId = 0;
                        try { rarity = Convert.ToInt32(Prop(h, "Rarity")); } catch { }
                        try { grade = Convert.ToInt32(Prop(h, "Grade")); } catch { }
                        try { typeId = Convert.ToInt32(Prop(h, "TypeId")); } catch { }
                        parts.Add($"hero r{rarity}/g{grade}/type{typeId}");
                    }
                }
                catch { }
                // Artifacts
                try
                {
                    var arts = Prop(up, "Artifacts");
                    int count = 0;
                    foreach (var __ in ListItems(arts)) count++;
                    if (count > 0) parts.Add($"artifacts×{count}");
                }
                catch { }
                // HeroParts (shards)
                try
                {
                    var hp = Prop(up, "HeroParts");
                    if (hp != null)
                    {
                        int total = 0;
                        var dictType = hp.GetType();
                        var getEnum = dictType.GetMethod("GetEnumerator");
                        var enumerator = getEnum?.Invoke(hp, null);
                        if (enumerator != null)
                        {
                            var moveNext = enumerator.GetType().GetMethod("MoveNext");
                            var current = enumerator.GetType().GetProperty("Current");
                            while ((bool)moveNext.Invoke(enumerator, null))
                            {
                                var kvp = current.GetValue(enumerator);
                                try { total += Convert.ToInt32(Prop(kvp, "Value")); } catch { }
                            }
                        }
                        if (total > 0) parts.Add($"hero_parts×{total}");
                    }
                }
                catch { }
                // Badges (List<UserBadge>)
                try
                {
                    var bg = Prop(up, "Badges");
                    int count = 0;
                    foreach (var __ in ListItems(bg)) count++;
                    if (count > 0) parts.Add($"badges×{count}");
                }
                catch { }
            }
            catch { }
            return parts.Count == 0 ? "rank-only" : string.Join(", ", parts);
        }

        // /super-raid?action=status|toggle|on|off
        // Read or set the Super Raid (BattleMultiplier) toggle on the open
        // Heroes*SelectionDialog. Super Raid doubles per-run rewards AND
        // energy/key cost (or triples at x3). Game model:
        //   MultiRunContext._active     (bool) - currently on
        //   MultiRunContext._enabled    (bool) - can be toggled
        //   MultiRunContext._locked     (bool) - blocked (mid-multi-battle)
        //   MultiRunContext._multiplier (int)  - 1/2/3 (none/double/triple)
        //   MultiRunContext.OnToggle()         - cycles x1 -> x2 (-> x3 if avail)
        // Stage rules:
        //   * Available on: Campaign, Dungeons, Doom Tower, Faction Wars
        //   * Not on: Hydra/CB/Chimera/Arena (multi-battle works differently)
        //   * Stage must be passed at least once before toggle is enabled
        private string SuperRaid(string action)
        {
            try
            {
                var dialogsRoot = GameObject.Find("UIManager/Canvas (Ui Root)/Dialogs");
                if (dialogsRoot == null) return "{\"error\":\"no Dialogs root\"}";

                IntPtr ctxObj = IntPtr.Zero, ctxClass = IntPtr.Zero;
                string ctxName = null, ctxNs = null;
                for (int di = 0; di < dialogsRoot.transform.childCount; di++)
                {
                    var dialog = dialogsRoot.transform.GetChild(di);
                    if (!dialog.gameObject.activeSelf) continue;
                    if (TryFindHeroesSelectionContext(dialog, out ctxObj, out ctxClass, out ctxName, out ctxNs))
                        break;
                }
                if (ctxObj == IntPtr.Zero)
                    return "{\"error\":\"no active heroes-selection dialog (Super Raid only togglable from battle setup)\"}";

                // Walk class hierarchy to find MultiRun field on this context.
                IntPtr mrField = IntPtr.Zero;
                uint mrOff = 0;
                IntPtr scan = ctxClass;
                while (scan != IntPtr.Zero)
                {
                    IntPtr fIter = IntPtr.Zero;
                    IntPtr ff;
                    while ((ff = il2cpp_class_get_fields(scan, ref fIter)) != IntPtr.Zero)
                    {
                        string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(ff));
                        if (fn == "MultiRun")
                        { mrField = ff; mrOff = il2cpp_field_get_offset(ff); break; }
                    }
                    if (mrField != IntPtr.Zero) break;
                    scan = il2cpp_class_get_parent(scan);
                }
                if (mrField == IntPtr.Zero)
                    return "{\"ok\":true,\"available\":false,\"note\":\"this stage type doesn't support Super Raid (e.g. CB/Hydra/Arena)\"}";

                IntPtr mrCtx = Marshal.ReadIntPtr(ctxObj, (int)mrOff);
                if (mrCtx == IntPtr.Zero)
                    return "{\"ok\":true,\"available\":false,\"note\":\"MultiRunContext is null\"}";

                // Wrap raw IL2CPP pointer back into a managed object via the
                // standard Il2Cpp interop (TypeName)..ctor(IntPtr) pattern —
                // same approach as RaidAutomationPlugin.Battle.cs line 304.
                object mrManaged = null;
                string wrapErr = null;
                foreach (var typeName in new[] {
                    "Client.ViewModel.Contextes.MultiRun.MultiRunContext",
                    "Client.ViewModel.Contextes.MultiRunContext",
                })
                {
                    var t = FindType(typeName);
                    if (t == null) continue;
                    try
                    {
                        mrManaged = Activator.CreateInstance(t, mrCtx);
                        if (mrManaged != null) break;
                    }
                    catch (Exception ce) { wrapErr = $"{typeName}: {ce.Message}"; }
                }
                if (mrManaged == null)
                    return "{\"error\":\"could not wrap MultiRunContext as managed object\",\"detail\":\"" + Esc(wrapErr ?? "type not found") + "\"}";

                bool active = false, enabled = false, locked = false;
                int multiplier = 1;
                try { var p = Prop(mrManaged, "_active"); if (p != null) active = (bool)Prop(p, "Value"); } catch { }
                try { var p = Prop(mrManaged, "_enabled"); if (p != null) enabled = (bool)Prop(p, "Value"); } catch { }
                try { var p = Prop(mrManaged, "_locked"); if (p != null) locked = (bool)Prop(p, "Value"); } catch { }
                try { var p = Prop(mrManaged, "_multiplier"); if (p != null) multiplier = Convert.ToInt32(Prop(p, "Value")); } catch { }

                action = (action ?? "status").ToLower();
                string actionResult = "noop";
                if (action == "toggle" || (action == "on" && !active) || (action == "off" && active))
                {
                    if (locked || !enabled)
                    {
                        return "{\"ok\":true,\"active\":" + (active?"true":"false")
                            + ",\"enabled\":" + (enabled?"true":"false")
                            + ",\"locked\":" + (locked?"true":"false")
                            + ",\"multiplier\":" + multiplier
                            + ",\"action_skipped\":\"locked or not-enabled\"}";
                    }
                    var onToggle = mrManaged.GetType().GetMethod("OnToggle",
                        BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                    if (onToggle == null)
                        return "{\"error\":\"OnToggle method not found on MultiRunContext\"}";
                    onToggle.Invoke(mrManaged, null);
                    actionResult = "toggled";
                    try { var p = Prop(mrManaged, "_active"); if (p != null) active = (bool)Prop(p, "Value"); } catch { }
                    try { var p = Prop(mrManaged, "_multiplier"); if (p != null) multiplier = Convert.ToInt32(Prop(p, "Value")); } catch { }
                }

                return "{\"ok\":true,\"available\":true"
                     + ",\"active\":" + (active?"true":"false")
                     + ",\"enabled\":" + (enabled?"true":"false")
                     + ",\"locked\":" + (locked?"true":"false")
                     + ",\"multiplier\":" + multiplier
                     + ",\"action\":\"" + Esc(action) + "\""
                     + ",\"action_result\":\"" + Esc(actionResult) + "\"}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // /cvc-multipliers — read the user's active Clan vs Clan tournament
        // and extract per-activity-group point multipliers so callers can
        // answer "what locations have 2x CvC right now?". Reads
        // Quest.CvcTournamentInfo.PointsMultipliers[] which is the source
        // of truth used by the in-game multiplier badges.
        private string GetCvcMultipliers()
        {
            try
            {
                var uw = GetUserWrapper();
                if (uw == null) return "{\"error\":\"Not logged in\"}";
                var cvc = Prop(uw, "CvcTournament");
                if (cvc == null)
                    return "{\"ok\":true,\"active\":false,\"multipliers\":[],\"note\":\"CvcTournament missing\"}";

                bool hasActive = false, isParticipate = false, isEnabled = false;
                long endsMs = 0;
                long myUserId = 0;
                int myPoints = 0, allianceMatchPoints = 0;
                long opponentAllianceId = 0;
                int opponentMatchPoints = 0;
                var perActivity = new System.Collections.Generic.List<string>();
                try { hasActive = (bool)(Prop(cvc, "HasActive") ?? false); } catch { }
                try { isParticipate = (bool)(Prop(cvc, "IsParticipate") ?? false); } catch { }
                try { isEnabled = (bool)(Prop(cvc, "IsEnabled") ?? false); } catch { }
                try
                {
                    // UserWrapper.User.Id is the player's user id (long).
                    var uw2 = GetUserWrapper();
                    var u = Prop(uw2, "User");
                    var v = Prop(u, "Id");
                    if (v != null) myUserId = Convert.ToInt64(v);
                } catch { }
                try
                {
                    var stats = Prop(cvc, "AllianceStats");
                    if (stats != null)
                    {
                        try { var p = Prop(stats, "MatchMakingPoints"); if (p != null) allianceMatchPoints = Convert.ToInt32(p); } catch { }
                        // UserPoints[] — find my entry
                        try
                        {
                            var ups = Prop(stats, "UserPoints");
                            foreach (var up in ListItems(ups))
                            {
                                try
                                {
                                    long uid = Convert.ToInt64(Prop(up, "UserId"));
                                    if (uid == myUserId)
                                    {
                                        myPoints = Convert.ToInt32(Prop(up, "Points"));
                                        break;
                                    }
                                } catch { }
                            }
                        } catch { }
                        // Per-activity breakdown for the alliance
                        try
                        {
                            var aps = Prop(stats, "ActivityPoints");
                            foreach (var ap in ListItems(aps))
                            {
                                try
                                {
                                    int tid = Convert.ToInt32(Prop(ap, "ActivityTypeId"));
                                    int pts = Convert.ToInt32(Prop(ap, "Points"));
                                    perActivity.Add("{\"activity_type_id\":" + tid + ",\"points\":" + pts + "}");
                                } catch { }
                            }
                        } catch { }
                    }
                } catch { }
                try
                {
                    var oppStats = Prop(cvc, "OpponentStats");
                    if (oppStats != null)
                    {
                        try { var p = Prop(oppStats, "AllianceId"); if (p != null) opponentAllianceId = Convert.ToInt64(p); } catch { }
                        try { var p = Prop(oppStats, "MatchMakingPoints"); if (p != null) opponentMatchPoints = Convert.ToInt32(p); } catch { }
                    }
                } catch { }
                try
                {
                    var et = Prop(cvc, "EndTime");
                    if (et != null)
                    {
                        var hv = et.GetType().GetProperty("HasValue");
                        if (hv != null && (bool)hv.GetValue(et))
                        {
                            var v = et.GetType().GetProperty("Value").GetValue(et);
                            var ticksProp = v.GetType().GetProperty("Ticks");
                            if (ticksProp != null)
                            {
                                long ticks = (long)ticksProp.GetValue(v);
                                endsMs = (ticks - 621_355_968_000_000_000L) / 10_000L;
                            }
                        }
                    }
                }
                catch { }

                // Pull per-activity-group multipliers from
                // Quest.CvcTournamentInfo.PointsMultipliers[]. Also pull
                // MilestoneRewardsByLeague (alliance tiers) +
                // PersonalRewardsByLeague (per-user tiers) so callers can
                // show next-reward + reward-ladder info.
                var mults = new System.Collections.Generic.List<string>();
                var allianceMilestones = new System.Collections.Generic.List<string>();
                var personalMilestones = new System.Collections.Generic.List<string>();
                string err = null;
                string diag = "";
                try
                {
                    var quest = Prop(cvc, "Quest");
                    diag = "quest=" + (quest == null ? "null" : quest.GetType().Name);
                    object info = null;
                    if (quest != null)
                    {
                        info = Prop(quest, "CvcTournamentInfo");
                        diag += "; info=" + (info == null ? "null" : info.GetType().Name);
                    }
                    object pms = null;
                    if (info != null)
                    {
                        pms = Prop(info, "PointsMultipliers");
                        diag += "; pms=" + (pms == null ? "null" : pms.GetType().Name);
                    }
                    if (pms != null)
                    {
                        // Use ListItems (count+indexer) — IL2CPP Lists don't
                        // implement System.Collections.IEnumerable cleanly.
                        int dbgCount = 0;
                        foreach (var pm in ListItems(pms))
                        {
                            dbgCount++;
                            if (pm == null) continue;
                            int gid = 0;
                            double mult = 0.0;
                            int upper = 0;
                            try { gid = Convert.ToInt32(Prop(pm, "ActivityGroup")); } catch { }
                            try { mult = Convert.ToDouble(Prop(pm, "Multiplier")); } catch { }
                            try { upper = Convert.ToInt32(Prop(pm, "UpperLimit")); } catch { }
                            string lbl = gid switch
                            {
                                1 => "Hero", 2 => "Story (Campaign)",
                                3 => "AllKeep", 4 => "Minotaur",
                                5 => "Dragon", 6 => "IceGolem",
                                7 => "FireKnight", 8 => "Spider",
                                9 => "FactionWars", 10 => "Arena",
                                11 => "AllianceBoss (CB/Demon Lord)",
                                12 => "ArtifactAndJewelry (Gear)",
                                13 => "Craft", 14 => "Other",
                                15 => "ArtifactAscendDungeon",
                                16 => "JewelryAscendDungeon",
                                17 => "DoubleAscendDungeon",
                                18 => "EventDungeon",
                                _ => "Group" + gid,
                            };
                            mults.Add("{\"group_id\":" + gid
                                + ",\"group\":\"" + Esc(lbl) + "\""
                                + ",\"multiplier\":" + mult.ToString("F2")
                                + ",\"upper_limit\":" + upper + "}");
                        }
                        diag += "; iter_count=" + dbgCount;
                    }
                }
                catch (Exception qx) { err = qx.Message; }

                // Walk MilestoneRewardsByLeague (alliance) +
                // PersonalRewardsByLeague (per-user). Each is a
                // List<CvcLeagueMilestoneRewards>; each has Milestones
                // = List<CvcMilestoneReward {Points, Reward: UserPrize}>.
                System.Action<string, System.Collections.Generic.List<string>> readLeagueMilestones = (fname, into) =>
                {
                    try
                    {
                        var quest = Prop(cvc, "Quest");
                        var info = Prop(quest, "CvcTournamentInfo");
                        var leagues = Prop(info, fname);
                        int leagueIdx = 0;
                        foreach (var lg in ListItems(leagues))
                        {
                            var ms = Prop(lg, "Milestones");
                            int tierIdx = 0;
                            foreach (var mile in ListItems(ms))
                            {
                                int pts = 0;
                                try { pts = Convert.ToInt32(Prop(mile, "Points")); } catch { }
                                // UserPrize is a complex blob; serialize a brief label
                                string rewardLabel = "?";
                                try
                                {
                                    var reward = Prop(mile, "Reward");
                                    if (reward != null) rewardLabel = SummarizeUserPrize(reward);
                                }
                                catch (Exception ex) { rewardLabel = "err:" + ex.Message; }
                                into.Add("{\"league\":" + leagueIdx
                                       + ",\"tier\":" + tierIdx
                                       + ",\"points\":" + pts
                                       + ",\"reward\":\"" + Esc(rewardLabel) + "\"}");
                                tierIdx++;
                            }
                            leagueIdx++;
                        }
                    }
                    catch { }
                };
                readLeagueMilestones("MilestoneRewardsByLeague", allianceMilestones);
                readLeagueMilestones("PersonalRewardsByLeague", personalMilestones);

                var sb = new StringBuilder(2048);
                sb.Append("{\"ok\":true");
                sb.Append(",\"active\":").Append(hasActive ? "true" : "false");
                sb.Append(",\"is_participate\":").Append(isParticipate ? "true" : "false");
                sb.Append(",\"is_enabled\":").Append(isEnabled ? "true" : "false");
                sb.Append(",\"ends_at\":").Append(endsMs);
                sb.Append(",\"my_user_id\":").Append(myUserId);
                sb.Append(",\"my_points\":").Append(myPoints);
                sb.Append(",\"alliance_match_points\":").Append(allianceMatchPoints);
                sb.Append(",\"opponent_alliance_id\":").Append(opponentAllianceId);
                sb.Append(",\"opponent_match_points\":").Append(opponentMatchPoints);
                sb.Append(",\"per_activity_alliance\":[");
                for (int i = 0; i < perActivity.Count; i++)
                {
                    if (i > 0) sb.Append(",");
                    sb.Append(perActivity[i]);
                }
                sb.Append("]");
                sb.Append(",\"count\":").Append(mults.Count);
                sb.Append(",\"multipliers\":[");
                for (int i = 0; i < mults.Count; i++)
                {
                    if (i > 0) sb.Append(",");
                    sb.Append(mults[i]);
                }
                sb.Append("]");
                sb.Append(",\"alliance_milestones\":[")
                  .Append(string.Join(",", allianceMilestones)).Append("]");
                sb.Append(",\"personal_milestones\":[")
                  .Append(string.Join(",", personalMilestones)).Append("]");
                if (err != null)
                    sb.Append(",\"error\":\"").Append(Esc(err)).Append("\"");
                sb.Append(",\"diag\":\"").Append(Esc(diag)).Append("\"");
                sb.Append("}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

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
        // /tournament-points — dump UserQuestDataGlobalEvent.TournamentPointsByStateId
        // (Dictionary<int,int> at offset 0x50). This is the field the in-game UI
        // reads to render "your points" in each tournament. It's [JsonSkip] so
        // /events doesn't expose it; the existing /event-progress walker reads
        // a different (often empty for Champion Develop) QuestState completion
        // path. Returns {state_id: points}.
        private string GetTournamentPointsByStateId()
        {
            try
            {
                var uw = GetUserWrapper();
                if (uw == null) return "{\"error\":\"Not logged in\"}";
                var tournaments = Prop(uw, "Tournaments");
                if (tournaments == null) return "{\"error\":\"Tournaments null\"}";
                var qd = Prop(tournaments, "QuestData");
                if (qd == null) return "{\"error\":\"QuestData null\"}";
                var ged = Prop(qd, "GlobalEventsData");
                if (ged == null) return "{\"error\":\"GlobalEventsData null\"}";

                // NEW (2026-06-05): walk OpenedStates and call
                // QuestState.get_GlobalEventTotalPoints() on each — that
                // property returns the cumulative tournament score for the
                // quest. The score for an event is the sum across all of
                // its QuestStates (one per scoring category).
                //
                // Returns: {state_id_or_proto: {qs_id: int, total: int}, ...}
                // Plus a per-event aggregate.
                var openedStates = Prop(qd, "OpenedStates");
                if (openedStates == null)
                    return "{\"error\":\"OpenedStates null\"}";

                IntPtr listPtr = GetIl2CppPointer(openedStates);
                if (listPtr == IntPtr.Zero)
                    return "{\"error\":\"OpenedStates il2cpp ptr null\"}";
                IntPtr listCls = il2cpp_object_get_class(listPtr);
                IntPtr itemsField = IntPtr.Zero, sizeField = IntPtr.Zero;
                IntPtr fIter0 = IntPtr.Zero;
                IntPtr fp0;
                while ((fp0 = il2cpp_class_get_fields(listCls, ref fIter0)) != IntPtr.Zero)
                {
                    string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(fp0));
                    if (fn == "_items") itemsField = fp0;
                    else if (fn == "_size") sizeField = fp0;
                }
                if (itemsField == IntPtr.Zero || sizeField == IntPtr.Zero)
                    return "{\"error\":\"List<QuestState> _items/_size not found\"}";

                int size = Marshal.ReadInt32(listPtr, (int)il2cpp_field_get_offset(sizeField));
                IntPtr itemsArrPtr = Marshal.ReadIntPtr(listPtr, (int)il2cpp_field_get_offset(itemsField));
                if (itemsArrPtr == IntPtr.Zero)
                    return "{\"states\":[],\"_note\":\"empty array\"}";

                // Find the QuestState class's get_GlobalEventTotalPoints method.
                // We discover the method via the first non-null QuestState's class.
                var sb = new StringBuilder();
                sb.Append("{\"states\":[");
                int emitted = 0;
                IntPtr getMethod = IntPtr.Zero;
                IntPtr itemsBase = IntPtr.Add(itemsArrPtr, 0x20);
                for (int i = 0; i < size && i < 400; i++)
                {
                    IntPtr qsPtr = Marshal.ReadIntPtr(itemsBase, i * 8);
                    if (qsPtr == IntPtr.Zero) continue;

                    int questId = Marshal.ReadInt32(qsPtr, 0x10);
                    int protoId = Marshal.ReadInt32(qsPtr, 0x14);
                    int totalPointsField = Marshal.ReadInt32(qsPtr, 0xF4);  // Nullable<int> raw

                    // Resolve get_GlobalEventTotalPoints once.
                    if (getMethod == IntPtr.Zero)
                    {
                        IntPtr qsClass = il2cpp_object_get_class(qsPtr);
                        getMethod = FindClassMethodByName(qsClass, "get_GlobalEventTotalPoints", 0);
                    }

                    int computed = -1;
                    if (getMethod != IntPtr.Zero)
                    {
                        IntPtr exc = IntPtr.Zero;
                        IntPtr resPtr = il2cpp_runtime_invoke(getMethod, qsPtr, IntPtr.Zero, ref exc);
                        if (exc == IntPtr.Zero && resPtr != IntPtr.Zero)
                        {
                            // Boxed int — value is at offset 0x10 of the box.
                            computed = Marshal.ReadInt32(resPtr, 0x10);
                        }
                    }

                    if (emitted++ > 0) sb.Append(",");
                    sb.Append("{\"qs\":").Append(questId)
                      .Append(",\"proto\":").Append(protoId)
                      .Append(",\"tp_field\":").Append(totalPointsField)
                      .Append(",\"computed\":").Append(computed)
                      .Append("}");
                }
                sb.Append("]}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // /pull-stats — dumps shard-summon history from two locations:
        //   1. UserStatsData.SummonResultByShardId — cumulative Dictionary<ShardTypeId,
        //      Dictionary<HeroRarity, int>>. "I've opened N Sacreds and got K Lgnds across
        //      all time." Survives server-side, syncs from phone pulls.
        //   2. UserShardData.SummonResults — List<ShardSummonResult> with per-(shard,rarity)
        //      Count + LastHeroId. Same data as (1) but flat + remembers last hero pulled.
        // Combined: we can snapshot these on PC sessions and diff to detect phone-side
        // pulls between sessions.
        private string GetShardPullStats()
        {
            try
            {
                var uw = GetUserWrapper();
                if (uw == null) return "{\"error\":\"not logged in\"}";
                var sb = new StringBuilder();
                sb.Append("{");

                // 1. UserStatsData.SummonResultByShardId — Dictionary<ShardTypeId, Dictionary<HeroRarity, int>>
                try
                {
                    var statsWrapper = Prop(uw, "StatsDataWrapper");
                    var usd = Prop(statsWrapper, "UserStatsData");
                    sb.Append("\"by_shard\":{");
                    if (usd != null)
                    {
                        var outerDict = Prop(usd, "SummonResultByShardId");
                        if (outerDict != null)
                        {
                            int n = 0;
                            var enumMeth = outerDict.GetType().GetMethod("GetEnumerator");
                            if (enumMeth != null)
                            {
                                var en = enumMeth.Invoke(outerDict, null);
                                var moveNext = en.GetType().GetMethod("MoveNext");
                                var current = en.GetType().GetProperty("Current");
                                while ((bool)moveNext.Invoke(en, null))
                                {
                                    var kv = current.GetValue(en);
                                    var keyProp = kv.GetType().GetProperty("Key");
                                    var valProp = kv.GetType().GetProperty("Value");
                                    int shardId = (int)keyProp.GetValue(kv);
                                    var innerDict = valProp.GetValue(kv);
                                    if (n++ > 0) sb.Append(",");
                                    sb.Append("\"").Append(shardId).Append("\":{");
                                    if (innerDict != null)
                                    {
                                        int m = 0;
                                        var enm = innerDict.GetType().GetMethod("GetEnumerator");
                                        var en2 = enm.Invoke(innerDict, null);
                                        var mn2 = en2.GetType().GetMethod("MoveNext");
                                        var cur2 = en2.GetType().GetProperty("Current");
                                        while ((bool)mn2.Invoke(en2, null))
                                        {
                                            var kv2 = cur2.GetValue(en2);
                                            int rarity = (int)kv2.GetType().GetProperty("Key").GetValue(kv2);
                                            int count = (int)kv2.GetType().GetProperty("Value").GetValue(kv2);
                                            if (m++ > 0) sb.Append(",");
                                            sb.Append("\"").Append(rarity).Append("\":").Append(count);
                                        }
                                    }
                                    sb.Append("}");
                                }
                            }
                        }
                    }
                    sb.Append("}");
                }
                catch (Exception ex)
                {
                    sb.Append("\"by_shard\":{},\"_stats_err\":\"")
                      .Append(Esc(ex.Message)).Append("\"");
                }

                // 2. UserShardData.SummonResults (List<ShardSummonResult>)
                try
                {
                    var shards = Prop(uw, "Shards");
                    var shardData = Prop(shards, "ShardData");
                    if (shardData != null)
                    {
                        var summonResults = Prop(shardData, "SummonResults");
                        sb.Append(",\"results\":[");
                        if (summonResults != null)
                        {
                            int n = 0;
                            foreach (var sr in ListItems(summonResults))
                            {
                                int shard = IntProp(sr, "ShardTypeId");
                                int rarity = IntProp(sr, "Rarity");
                                int count = IntProp(sr, "Count");
                                int lastHero = IntProp(sr, "LastHeroId");
                                if (n++ > 0) sb.Append(",");
                                sb.Append("{\"shard\":").Append(shard)
                                  .Append(",\"rarity\":").Append(rarity)
                                  .Append(",\"count\":").Append(count)
                                  .Append(",\"last_hero_type\":").Append(lastHero).Append("}");
                            }
                        }
                        sb.Append("]");
                    }
                }
                catch (Exception ex)
                {
                    sb.Append(",\"_results_err\":\"").Append(Esc(ex.Message)).Append("\"");
                }

                // 3. Current shard inventory (UserShardData.Shards: List<Shard>)
                try
                {
                    var shards = Prop(uw, "Shards");
                    var shardData = Prop(shards, "ShardData");
                    if (shardData != null)
                    {
                        var shardsList = Prop(shardData, "Shards");
                        sb.Append(",\"inventory\":[");
                        if (shardsList != null)
                        {
                            int n = 0;
                            foreach (var s in ListItems(shardsList))
                            {
                                int t = IntProp(s, "TypeId");
                                int c = IntProp(s, "Count");
                                if (n++ > 0) sb.Append(",");
                                sb.Append("{\"shard\":").Append(t).Append(",\"count\":").Append(c).Append("}");
                            }
                        }
                        sb.Append("]");
                    }
                }
                catch (Exception ex)
                {
                    sb.Append(",\"_inv_err\":\"").Append(Esc(ex.Message)).Append("\"");
                }

                sb.Append("}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // Walk a Dictionary<int, Dictionary<int,int>> via raw _entries — outer keys are
        // ShardTypeIds, inner keys are HeroRarity values, inner values are pull counts.
        private void AppendDictOfDictRaw(StringBuilder sb, IntPtr outerDict)
        {
            try
            {
                IntPtr klass = il2cpp_object_get_class(outerDict);
                IntPtr entriesField = IntPtr.Zero, countField = IntPtr.Zero;
                IntPtr fIter = IntPtr.Zero;
                IntPtr f;
                while ((f = il2cpp_class_get_fields(klass, ref fIter)) != IntPtr.Zero)
                {
                    string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(f));
                    if (fn == "_entries") entriesField = f;
                    else if (fn == "_count") countField = f;
                }
                if (entriesField == IntPtr.Zero || countField == IntPtr.Zero) return;
                int count = Marshal.ReadInt32(outerDict, (int)il2cpp_field_get_offset(countField));
                IntPtr entriesArr = Marshal.ReadIntPtr(outerDict, (int)il2cpp_field_get_offset(entriesField));
                if (entriesArr == IntPtr.Zero) return;

                // Outer Entry layout: hashCode(4), next(4), key:int(4), value:IntPtr(8) — but
                // .NET Dictionary aligns to 24 bytes per entry for {int key, ref value}.
                // Verify via _entries class's element size if needed; safest is 24.
                IntPtr entriesCls = il2cpp_object_get_class(entriesArr);
                // Heuristic: try stride = 24 first (int key + ref value w/ padding).
                int stride = 24;
                int n = 0;
                for (int i = 0; i < count; i++)
                {
                    int entryOff = 0x20 + i * stride;
                    int hash = Marshal.ReadInt32(entriesArr, entryOff);
                    if (hash < 0) continue;
                    int shardId = Marshal.ReadInt32(entriesArr, entryOff + 8);
                    IntPtr innerDict = Marshal.ReadIntPtr(entriesArr, entryOff + 16);
                    if (n++ > 0) sb.Append(",");
                    sb.Append("\"").Append(shardId).Append("\":{");
                    AppendIntIntDictBody(sb, innerDict);
                    sb.Append("}");
                }
            }
            catch { }
        }

        // Body-only version of AppendIntDictRaw — no surrounding braces.
        private void AppendIntIntDictBody(StringBuilder sb, IntPtr dictPtr)
        {
            if (dictPtr == IntPtr.Zero) return;
            try
            {
                IntPtr klass = il2cpp_object_get_class(dictPtr);
                IntPtr entriesField = IntPtr.Zero, countField = IntPtr.Zero;
                IntPtr fIter = IntPtr.Zero;
                IntPtr f;
                while ((f = il2cpp_class_get_fields(klass, ref fIter)) != IntPtr.Zero)
                {
                    string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(f));
                    if (fn == "_entries") entriesField = f;
                    else if (fn == "_count") countField = f;
                }
                if (entriesField == IntPtr.Zero || countField == IntPtr.Zero) return;
                int count = Marshal.ReadInt32(dictPtr, (int)il2cpp_field_get_offset(countField));
                IntPtr entriesArr = Marshal.ReadIntPtr(dictPtr, (int)il2cpp_field_get_offset(entriesField));
                if (entriesArr == IntPtr.Zero) return;
                int n = 0;
                for (int i = 0; i < count; i++)
                {
                    int entryOff = 0x20 + i * 16;
                    int hash = Marshal.ReadInt32(entriesArr, entryOff);
                    if (hash < 0) continue;
                    int k = Marshal.ReadInt32(entriesArr, entryOff + 8);
                    int v = Marshal.ReadInt32(entriesArr, entryOff + 12);
                    if (n++ > 0) sb.Append(",");
                    sb.Append("\"").Append(k).Append("\":").Append(v);
                }
            }
            catch { }
        }

        // Walk List<ShardSummonResult>. ShardSummonResult has:
        //   ShardTypeId (int 4) @ 0x10, Rarity (int 4) @ 0x14,
        //   Count (int 4) @ 0x18, LastHeroId (int 4) @ 0x1C.
        private void AppendShardSummonResultsRaw(StringBuilder sb, IntPtr listPtr)
        {
            if (listPtr == IntPtr.Zero) return;
            try
            {
                IntPtr klass = il2cpp_object_get_class(listPtr);
                IntPtr itemsField = IntPtr.Zero, sizeField = IntPtr.Zero;
                IntPtr fIter = IntPtr.Zero;
                IntPtr f;
                while ((f = il2cpp_class_get_fields(klass, ref fIter)) != IntPtr.Zero)
                {
                    string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(f));
                    if (fn == "_items") itemsField = f;
                    else if (fn == "_size") sizeField = f;
                }
                if (itemsField == IntPtr.Zero || sizeField == IntPtr.Zero) return;
                int size = Marshal.ReadInt32(listPtr, (int)il2cpp_field_get_offset(sizeField));
                IntPtr itemsArr = Marshal.ReadIntPtr(listPtr, (int)il2cpp_field_get_offset(itemsField));
                if (itemsArr == IntPtr.Zero) return;
                IntPtr itemsBase = IntPtr.Add(itemsArr, 0x20);
                int n = 0;
                for (int i = 0; i < size; i++)
                {
                    IntPtr e = Marshal.ReadIntPtr(itemsBase, i * 8);
                    if (e == IntPtr.Zero) continue;
                    int shard = Marshal.ReadInt32(e, 0x10);
                    int rarity = Marshal.ReadInt32(e, 0x14);
                    int count = Marshal.ReadInt32(e, 0x18);
                    int lastHero = Marshal.ReadInt32(e, 0x1C);
                    if (n++ > 0) sb.Append(",");
                    sb.Append("{\"shard\":").Append(shard)
                      .Append(",\"rarity\":").Append(rarity)
                      .Append(",\"count\":").Append(count)
                      .Append(",\"last_hero_type\":").Append(lastHero).Append("}");
                }
            }
            catch { }
        }

        // Walk List<Shard>. Shard.TypeId @ 0x10, Shard.Count @ 0x14.
        private void AppendShardInventoryRaw(StringBuilder sb, IntPtr listPtr)
        {
            if (listPtr == IntPtr.Zero) return;
            try
            {
                IntPtr klass = il2cpp_object_get_class(listPtr);
                IntPtr itemsField = IntPtr.Zero, sizeField = IntPtr.Zero;
                IntPtr fIter = IntPtr.Zero;
                IntPtr f;
                while ((f = il2cpp_class_get_fields(klass, ref fIter)) != IntPtr.Zero)
                {
                    string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(f));
                    if (fn == "_items") itemsField = f;
                    else if (fn == "_size") sizeField = f;
                }
                if (itemsField == IntPtr.Zero || sizeField == IntPtr.Zero) return;
                int size = Marshal.ReadInt32(listPtr, (int)il2cpp_field_get_offset(sizeField));
                IntPtr itemsArr = Marshal.ReadIntPtr(listPtr, (int)il2cpp_field_get_offset(itemsField));
                if (itemsArr == IntPtr.Zero) return;
                IntPtr itemsBase = IntPtr.Add(itemsArr, 0x20);
                int n = 0;
                for (int i = 0; i < size; i++)
                {
                    IntPtr e = Marshal.ReadIntPtr(itemsBase, i * 8);
                    if (e == IntPtr.Zero) continue;
                    int shard = Marshal.ReadInt32(e, 0x10);
                    int count = Marshal.ReadInt32(e, 0x14);
                    if (n++ > 0) sb.Append(",");
                    sb.Append("{\"shard\":").Append(shard).Append(",\"count\":").Append(count).Append("}");
                }
            }
            catch { }
        }

        private string FinishEditTeam(string stageIdStr)
        {
            int requestedStageId = 0;
            int.TryParse(stageIdStr, out requestedStageId);
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

                            // 2026-06-04 FIX: the 1-arg OpenSelectionDialog takes
                            // `int stageId` (campaign Story override), NOT a "State
                            // object" — the previous null-pass crashed because it
                            // was the wrong type. Pass the requested stage_id query
                            // arg (e.g. 1113007 for campaign-11-7-brutal) and the
                            // call lands correctly.
                            if (openArity != 0 && openArity != 1)
                            {
                                Logger.LogWarning("[Finish] OpenSelectionDialog has "
                                    + openArity + " args — unsupported");
                                return "{\"error\":\"OpenSelectionDialog requires arity-"
                                    + openArity + " args; only 0-arg or 1-arg(int stageId) supported\"}";
                            }
                            if (openArity == 1 && requestedStageId == 0)
                            {
                                Logger.LogWarning("[Finish] OpenSelectionDialog needs stage_id "
                                    + "but none provided — pass ?stage_id=N");
                                return "{\"error\":\"OpenSelectionDialog(int stageId) requires ?stage_id=N query arg\"}";
                            }
                            IntPtr argsArr = IntPtr.Zero;
                            IntPtr exc2 = IntPtr.Zero;
                            try
                            {
                                if (openArity == 1)
                                {
                                    // Build [ &int ] args array for il2cpp_runtime_invoke.
                                    argsArr = Marshal.AllocHGlobal(IntPtr.Size);
                                    IntPtr stagePtr = Marshal.AllocHGlobal(sizeof(int));
                                    Marshal.WriteInt32(stagePtr, requestedStageId);
                                    Marshal.WriteIntPtr(argsArr, stagePtr);
                                    try
                                    {
                                        il2cpp_runtime_invoke(openMethod, ctxObj, argsArr, ref exc2);
                                    }
                                    finally
                                    {
                                        Marshal.FreeHGlobal(stagePtr);
                                    }
                                }
                                else
                                {
                                    il2cpp_runtime_invoke(openMethod, ctxObj, argsArr, ref exc2);
                                }
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

        // =====================================================
        // /open-chapter?n=N — from world map (MapHUD), open chapter N's
        // region map. MapContext (not MapHUDContext — different type)
        // owns _region1.._region12 fields, each a MapRegionItemContext
        // with `_regionType : RegionTypeId`. We:
        //   1. find MapContext in active dialogs
        //   2. read `_regionN._regionType` (the int)
        //   3. invoke MapContext.OnRegionClick(regionType)
        // Same downstream path as a user tapping chapter N on the world
        // map. Difficulty is whatever the dropdown is currently set to —
        // separate /set-map-difficulty endpoint covers that case.
        // =====================================================
        private string OpenChapter(string nStr)
        {
            if (string.IsNullOrEmpty(nStr) || !int.TryParse(nStr, out int chapterN))
                return "{\"error\":\"n (1..12) required\"}";
            if (chapterN < 1 || chapterN > 12)
                return "{\"error\":\"n must be 1..12\"}";
            try
            {
                var allMBs = UnityEngine.Object.FindObjectsOfType<MonoBehaviour>();
                IntPtr mapCtx = IntPtr.Zero, mapClass = IntPtr.Zero;
                foreach (var mono in allMBs)
                {
                    if (mono == null) continue;
                    try
                    {
                        IntPtr monoPtr = mono.Pointer;
                        if (monoPtr == IntPtr.Zero) continue;
                        IntPtr monoClass = il2cpp_object_get_class(monoPtr);
                        if (monoClass == IntPtr.Zero) continue;
                        IntPtr getCtx = IntPtr.Zero;
                        IntPtr klass = monoClass;
                        while (klass != IntPtr.Zero && getCtx == IntPtr.Zero)
                        {
                            IntPtr mIter = IntPtr.Zero;
                            IntPtr m;
                            while ((m = il2cpp_class_get_methods(klass, ref mIter)) != IntPtr.Zero)
                            {
                                string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                                if (mn == "get_Context" && il2cpp_method_get_param_count(m) == 0)
                                { getCtx = m; break; }
                            }
                            if (getCtx == IntPtr.Zero) klass = il2cpp_class_get_parent(klass);
                        }
                        if (getCtx == IntPtr.Zero) continue;
                        IntPtr exc = IntPtr.Zero;
                        IntPtr cobj = il2cpp_runtime_invoke(getCtx, monoPtr, IntPtr.Zero, ref exc);
                        if (exc != IntPtr.Zero || cobj == IntPtr.Zero) continue;
                        IntPtr cclass = il2cpp_object_get_class(cobj);
                        if (cclass == IntPtr.Zero) continue;
                        string sn = Marshal.PtrToStringAnsi(il2cpp_class_get_name(cclass));
                        if (sn != "MapContext") continue;
                        mapCtx = cobj; mapClass = cclass;
                        break;
                    }
                    catch { }
                }
                if (mapCtx == IntPtr.Zero)
                    return "{\"error\":\"MapContext not found in scene\"}";

                // Find _regionN field
                string fname = "_region" + chapterN;
                IntPtr fRegion = IntPtr.Zero;
                uint regOff = 0;
                IntPtr scan = mapClass;
                while (scan != IntPtr.Zero)
                {
                    IntPtr fIter = IntPtr.Zero;
                    IntPtr ff;
                    while ((ff = il2cpp_class_get_fields(scan, ref fIter)) != IntPtr.Zero)
                    {
                        string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(ff));
                        if (fn == fname)
                        { fRegion = ff; regOff = il2cpp_field_get_offset(ff); break; }
                    }
                    if (fRegion != IntPtr.Zero) break;
                    scan = il2cpp_class_get_parent(scan);
                }
                if (fRegion == IntPtr.Zero)
                    return "{\"error\":\"" + fname + " field not on MapContext\"}";
                IntPtr regionItemPtr = Marshal.ReadIntPtr(mapCtx, (int)regOff);
                if (regionItemPtr == IntPtr.Zero)
                    return "{\"error\":\"" + fname + " is null (chapter likely not yet unlocked)\"}";

                // Read _regionType from MapRegionItemContext
                IntPtr riClass = il2cpp_object_get_class(regionItemPtr);
                IntPtr fRegType = IntPtr.Zero;
                uint rtOff = 0;
                IntPtr riScan = riClass;
                while (riScan != IntPtr.Zero)
                {
                    IntPtr fIter = IntPtr.Zero;
                    IntPtr ff;
                    while ((ff = il2cpp_class_get_fields(riScan, ref fIter)) != IntPtr.Zero)
                    {
                        string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(ff));
                        if (fn == "_regionType")
                        { fRegType = ff; rtOff = il2cpp_field_get_offset(ff); break; }
                    }
                    if (fRegType != IntPtr.Zero) break;
                    riScan = il2cpp_class_get_parent(riScan);
                }
                if (fRegType == IntPtr.Zero)
                    return "{\"error\":\"_regionType not on MapRegionItemContext\"}";
                int regionType = Marshal.ReadInt32(regionItemPtr, (int)rtOff);

                // Find OnRegionClick(int) on MapContext
                IntPtr method = IntPtr.Zero;
                IntPtr mscan = mapClass;
                while (mscan != IntPtr.Zero && method == IntPtr.Zero)
                {
                    IntPtr mIter = IntPtr.Zero;
                    IntPtr m;
                    while ((m = il2cpp_class_get_methods(mscan, ref mIter)) != IntPtr.Zero)
                    {
                        string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                        if (mn == "OnRegionClick" && il2cpp_method_get_param_count(m) == 1)
                        { method = m; break; }
                    }
                    if (method == IntPtr.Zero) mscan = il2cpp_class_get_parent(mscan);
                }
                if (method == IntPtr.Zero)
                    return "{\"error\":\"OnRegionClick(int) not on MapContext\"}";

                // Invoke OnRegionClick(regionType)
                IntPtr boxed = Marshal.AllocHGlobal(sizeof(int));
                Marshal.WriteInt32(boxed, regionType);
                IntPtr[] args = new IntPtr[] { boxed };
                IntPtr argsHandle = Marshal.AllocHGlobal(IntPtr.Size);
                Marshal.WriteIntPtr(argsHandle, boxed);
                IntPtr exc2 = IntPtr.Zero;
                try
                {
                    il2cpp_runtime_invoke(method, mapCtx, argsHandle, ref exc2);
                }
                finally
                {
                    Marshal.FreeHGlobal(boxed);
                    Marshal.FreeHGlobal(argsHandle);
                }
                if (exc2 != IntPtr.Zero)
                    return "{\"error\":\"OnRegionClick threw\",\"region_type\":" + regionType + "}";
                return "{\"ok\":true,\"chapter\":" + chapterN + ",\"region_type\":" + regionType + "}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // =====================================================
        // /open-campaign-map — chain Village -> BattleModeSelectionDialog
        // -> AdventureModeContext.OpenMap() -> world map (MapHUD).
        // Invokes the private OpenMap on the dialog's `_adventure` child
        // context, replicating the user's tap on the Adventure mode button.
        // =====================================================
        private string OpenCampaignMap()
        {
            try
            {
                // Step 1: ensure BattleModeSelectionDialog is open. If not,
                // call BattleMapButtonContext.OpenWorldMap to open it.
                var dialogsRoot = GameObject.Find("UIManager/Canvas (Ui Root)/Dialogs");
                if (dialogsRoot == null) return "{\"error\":\"no Dialogs root\"}";

                Transform bmsdGO = null;
                for (int i = 0; i < dialogsRoot.transform.childCount; i++)
                {
                    var c = dialogsRoot.transform.GetChild(i);
                    if (c.name.Contains("BattleModeSelectionDialog"))
                    { bmsdGO = c; break; }
                }
                if (bmsdGO == null || !bmsdGO.gameObject.activeSelf)
                {
                    // Fire OpenWorldMap and return — dialog opens async on
                    // the cmd queue, and BLOCKING the main thread here
                    // would prevent Unity from processing it. Caller polls
                    // /view-contexts and re-invokes /open-campaign-map.
                    Type bm = FindType("Client.ViewModel.Contextes.Village.HUD.BattleMapButtonContext");
                    if (bm != null)
                    {
                        var owm = bm.GetMethod("OpenWorldMap",
                            BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static);
                        if (owm != null) owm.Invoke(null, null);
                    }
                    return "{\"ok\":true,\"step\":1,\"queued\":\"OpenWorldMap\",\"next\":\"poll for [DV] BattleModeSelectionDialog then re-invoke /open-campaign-map\"}";
                }

                // Step 2: walk the dialog GO for its BaseView -> Context.
                IntPtr dlgCtx = IntPtr.Zero, dlgClass = IntPtr.Zero;
                var queue = new Queue<Transform>();
                queue.Enqueue(bmsdGO);
                int searched = 0;
                while (queue.Count > 0 && searched < 200 && dlgCtx == IntPtr.Zero)
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
                            if (monoClass == IntPtr.Zero) continue;
                            IntPtr getCtx = IntPtr.Zero;
                            IntPtr klass = monoClass;
                            while (klass != IntPtr.Zero && getCtx == IntPtr.Zero)
                            {
                                IntPtr mIter = IntPtr.Zero;
                                IntPtr m;
                                while ((m = il2cpp_class_get_methods(klass, ref mIter)) != IntPtr.Zero)
                                {
                                    string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                                    if (mn == "get_Context" && il2cpp_method_get_param_count(m) == 0)
                                    { getCtx = m; break; }
                                }
                                if (getCtx == IntPtr.Zero) klass = il2cpp_class_get_parent(klass);
                            }
                            if (getCtx == IntPtr.Zero) continue;
                            IntPtr exc = IntPtr.Zero;
                            IntPtr cobj = il2cpp_runtime_invoke(getCtx, monoPtr, IntPtr.Zero, ref exc);
                            if (exc != IntPtr.Zero || cobj == IntPtr.Zero) continue;
                            IntPtr cclass = il2cpp_object_get_class(cobj);
                            if (cclass == IntPtr.Zero) continue;
                            string cn = Marshal.PtrToStringAnsi(il2cpp_class_get_name(cclass));
                            if (cn != null && cn.Contains("BattleModeSelectionDialogContext"))
                            { dlgCtx = cobj; dlgClass = cclass; break; }
                        }
                        catch { }
                    }
                    if (dlgCtx != IntPtr.Zero) break;
                    for (int ci = 0; ci < t.childCount && ci < 30; ci++)
                        queue.Enqueue(t.GetChild(ci));
                }
                if (dlgCtx == IntPtr.Zero)
                    return "{\"error\":\"BattleModeSelectionDialogContext not found in dialog tree\"}";

                // Step 3: read _adventure field
                IntPtr fAdv = IntPtr.Zero; uint advOff = 0;
                IntPtr scan = dlgClass;
                while (scan != IntPtr.Zero)
                {
                    IntPtr fIter = IntPtr.Zero;
                    IntPtr ff;
                    while ((ff = il2cpp_class_get_fields(scan, ref fIter)) != IntPtr.Zero)
                    {
                        string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(ff));
                        if (fn == "_adventure")
                        { fAdv = ff; advOff = il2cpp_field_get_offset(ff); break; }
                    }
                    if (fAdv != IntPtr.Zero) break;
                    scan = il2cpp_class_get_parent(scan);
                }
                if (fAdv == IntPtr.Zero) return "{\"error\":\"_adventure field not on BattleModeSelectionDialogContext\"}";
                IntPtr advCtx = Marshal.ReadIntPtr(dlgCtx, (int)advOff);
                if (advCtx == IntPtr.Zero) return "{\"error\":\"_adventure ctx is null\"}";
                IntPtr advClass = il2cpp_object_get_class(advCtx);

                // Step 4: invoke OpenMap (private instance method)
                IntPtr openMap = IntPtr.Zero;
                IntPtr ascan = advClass;
                while (ascan != IntPtr.Zero && openMap == IntPtr.Zero)
                {
                    IntPtr mIter = IntPtr.Zero;
                    IntPtr m;
                    while ((m = il2cpp_class_get_methods(ascan, ref mIter)) != IntPtr.Zero)
                    {
                        string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                        if (mn == "OpenMap" && il2cpp_method_get_param_count(m) == 0)
                        { openMap = m; break; }
                    }
                    if (openMap == IntPtr.Zero) ascan = il2cpp_class_get_parent(ascan);
                }
                if (openMap == IntPtr.Zero) return "{\"error\":\"OpenMap/0 not on AdventureModeContext\"}";

                IntPtr exc2 = IntPtr.Zero;
                il2cpp_runtime_invoke(openMap, advCtx, IntPtr.Zero, ref exc2);
                if (exc2 != IntPtr.Zero) return "{\"error\":\"OpenMap threw\"}";
                return "{\"ok\":true}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // =====================================================
        // /open-region-tile?id=N — from MapHUD (world map) drill into
        // a specific chapter region. Walks for MapRegionItemContext
        // whose `_regionType : RegionTypeId == N` and invokes its
        // OnClick() — replicating the user's tap on a chapter tile.
        // Captures region ids by walking active MapHUD; pass the int
        // RegionTypeId (no name registry yet — discover via inspection).
        // =====================================================
        private string OpenRegionTile(string idStr)
        {
            if (string.IsNullOrEmpty(idStr) || !int.TryParse(idStr, out int targetId))
                return "{\"error\":\"id (int RegionTypeId) required\"}";
            try
            {
                IntPtr hitObj = IntPtr.Zero, hitClass = IntPtr.Zero;
                int candidates = 0;
                string hitClassName = null;
                // Region tiles render in 3D scene, not under /Dialogs.
                var allMBs = UnityEngine.Object.FindObjectsOfType<MonoBehaviour>();
                foreach (var mono in allMBs)
                {
                    if (mono == null) continue;
                    try
                    {
                        IntPtr monoPtr = mono.Pointer;
                        if (monoPtr == IntPtr.Zero) continue;
                        IntPtr monoClass = il2cpp_object_get_class(monoPtr);
                        if (monoClass == IntPtr.Zero) continue;
                        IntPtr getCtx = IntPtr.Zero;
                        IntPtr klass = monoClass;
                        while (klass != IntPtr.Zero && getCtx == IntPtr.Zero)
                        {
                            IntPtr mIter = IntPtr.Zero;
                            IntPtr m;
                            while ((m = il2cpp_class_get_methods(klass, ref mIter)) != IntPtr.Zero)
                            {
                                string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                                if (mn == "get_Context" && il2cpp_method_get_param_count(m) == 0)
                                { getCtx = m; break; }
                            }
                            if (getCtx == IntPtr.Zero) klass = il2cpp_class_get_parent(klass);
                        }
                        if (getCtx == IntPtr.Zero) continue;
                        IntPtr exc = IntPtr.Zero;
                        IntPtr cobj = il2cpp_runtime_invoke(getCtx, monoPtr, IntPtr.Zero, ref exc);
                        if (exc != IntPtr.Zero || cobj == IntPtr.Zero) continue;
                        IntPtr cclass = il2cpp_object_get_class(cobj);
                        if (cclass == IntPtr.Zero) continue;
                        string sn = Marshal.PtrToStringAnsi(il2cpp_class_get_name(cclass));
                        if (sn != "MapRegionItemContext") continue;
                        IntPtr fRegion = IntPtr.Zero;
                        uint rOff = 0;
                        IntPtr scan = cclass;
                        while (scan != IntPtr.Zero)
                        {
                            IntPtr fIter = IntPtr.Zero;
                            IntPtr ff;
                            while ((ff = il2cpp_class_get_fields(scan, ref fIter)) != IntPtr.Zero)
                            {
                                string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(ff));
                                if (fn == "_regionType")
                                { fRegion = ff; rOff = il2cpp_field_get_offset(ff); break; }
                            }
                            if (fRegion != IntPtr.Zero) break;
                            scan = il2cpp_class_get_parent(scan);
                        }
                        if (fRegion == IntPtr.Zero) continue;
                        candidates++;
                        int rid = Marshal.ReadInt32(cobj, (int)rOff);
                        if (rid != targetId) continue;
                        hitObj = cobj;
                        hitClass = cclass;
                        hitClassName = sn;
                        break;
                    }
                    catch { }
                }
                if (hitObj == IntPtr.Zero)
                    return "{\"error\":\"no MapRegionItemContext with _regionType=" + targetId
                           + "\",\"candidates_scanned\":" + candidates + "}";

                IntPtr method = IntPtr.Zero;
                IntPtr cscan = hitClass;
                while (cscan != IntPtr.Zero && method == IntPtr.Zero)
                {
                    IntPtr mIter = IntPtr.Zero;
                    IntPtr m;
                    while ((m = il2cpp_class_get_methods(cscan, ref mIter)) != IntPtr.Zero)
                    {
                        string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                        if (mn == "OnClick" && il2cpp_method_get_param_count(m) == 0)
                        { method = m; break; }
                    }
                    if (method == IntPtr.Zero) cscan = il2cpp_class_get_parent(cscan);
                }
                if (method == IntPtr.Zero)
                    return "{\"error\":\"OnClick/0 not on " + Esc(hitClassName ?? "?") + "\"}";

                IntPtr excClick = IntPtr.Zero;
                il2cpp_runtime_invoke(method, hitObj, IntPtr.Zero, ref excClick);
                if (excClick != IntPtr.Zero)
                    return "{\"error\":\"OnClick threw\"}";
                return "{\"ok\":true,\"region_type\":" + targetId + ",\"ctx\":\"" + Esc(hitClassName ?? "?") + "\"}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // =====================================================
        // /list-region-tiles — diagnostic: dump all visible
        // MapRegionItemContext + their _regionType values. Use this to
        // discover the int for the chapter you want to open.
        // =====================================================
        private string ListRegionTiles()
        {
            try
            {
                // World-map region tiles render in the 3D scene, not under
                // /Dialogs. Scan ALL MonoBehaviours in the scene for
                // MapRegionItemContext.
                var allMBs = UnityEngine.Object.FindObjectsOfType<MonoBehaviour>();
                var sb = new StringBuilder();
                sb.Append("{\"tiles\":[");
                int n = 0;
                foreach (var mono in allMBs)
                {
                    if (mono == null) continue;
                    try
                    {
                        IntPtr monoPtr = mono.Pointer;
                        if (monoPtr == IntPtr.Zero) continue;
                        IntPtr monoClass = il2cpp_object_get_class(monoPtr);
                        if (monoClass == IntPtr.Zero) continue;
                        IntPtr getCtx = IntPtr.Zero;
                        IntPtr klass = monoClass;
                        while (klass != IntPtr.Zero && getCtx == IntPtr.Zero)
                        {
                            IntPtr mIter = IntPtr.Zero;
                            IntPtr m;
                            while ((m = il2cpp_class_get_methods(klass, ref mIter)) != IntPtr.Zero)
                            {
                                string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                                if (mn == "get_Context" && il2cpp_method_get_param_count(m) == 0)
                                { getCtx = m; break; }
                            }
                            if (getCtx == IntPtr.Zero) klass = il2cpp_class_get_parent(klass);
                        }
                        if (getCtx == IntPtr.Zero) continue;
                        IntPtr exc = IntPtr.Zero;
                        IntPtr cobj = il2cpp_runtime_invoke(getCtx, monoPtr, IntPtr.Zero, ref exc);
                        if (exc != IntPtr.Zero || cobj == IntPtr.Zero) continue;
                        IntPtr cclass = il2cpp_object_get_class(cobj);
                        if (cclass == IntPtr.Zero) continue;
                        string ctxName = Marshal.PtrToStringAnsi(il2cpp_class_get_name(cclass));
                        if (ctxName != "MapRegionItemContext") continue;
                        IntPtr fRegion = IntPtr.Zero;
                        uint rOff = 0;
                        IntPtr scan = cclass;
                        while (scan != IntPtr.Zero)
                        {
                            IntPtr fIter = IntPtr.Zero;
                            IntPtr ff;
                            while ((ff = il2cpp_class_get_fields(scan, ref fIter)) != IntPtr.Zero)
                            {
                                string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(ff));
                                if (fn == "_regionType")
                                { fRegion = ff; rOff = il2cpp_field_get_offset(ff); break; }
                            }
                            if (fRegion != IntPtr.Zero) break;
                            scan = il2cpp_class_get_parent(scan);
                        }
                        if (fRegion == IntPtr.Zero) continue;
                        int rid = Marshal.ReadInt32(cobj, (int)rOff);
                        if (n > 0) sb.Append(",");
                        sb.Append(rid);
                        n++;
                    }
                    catch { }
                }
                sb.Append("],\"count\":").Append(n).Append("}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        private string ListRegionTilesOLD()
        {
            try
            {
                var dialogsRoot = GameObject.Find("UIManager/Canvas (Ui Root)/Dialogs");
                if (dialogsRoot == null) return "{\"error\":\"no Dialogs root\"}";
                var sb = new StringBuilder();
                sb.Append("{\"tiles\":[");
                int n = 0;
                for (int di = 0; di < dialogsRoot.transform.childCount; di++)
                {
                    var dialog = dialogsRoot.transform.GetChild(di);
                    if (!dialog.gameObject.activeSelf) continue;
                    var queue = new Queue<KeyValuePair<Transform, int>>();
                    queue.Enqueue(new KeyValuePair<Transform, int>(dialog, 0));
                    int searched = 0;
                    while (queue.Count > 0 && searched < 800)
                    {
                        var pair = queue.Dequeue();
                        var t = pair.Key;
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
                                IntPtr getCtx = IntPtr.Zero;
                                IntPtr klass = monoClass;
                                while (klass != IntPtr.Zero && getCtx == IntPtr.Zero)
                                {
                                    IntPtr mIter = IntPtr.Zero;
                                    IntPtr m;
                                    while ((m = il2cpp_class_get_methods(klass, ref mIter)) != IntPtr.Zero)
                                    {
                                        string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                                        if (mn == "get_Context" && il2cpp_method_get_param_count(m) == 0)
                                        { getCtx = m; break; }
                                    }
                                    if (getCtx == IntPtr.Zero) klass = il2cpp_class_get_parent(klass);
                                }
                                if (getCtx == IntPtr.Zero) continue;
                                IntPtr exc = IntPtr.Zero;
                                IntPtr cobj = il2cpp_runtime_invoke(getCtx, monoPtr, IntPtr.Zero, ref exc);
                                if (exc != IntPtr.Zero || cobj == IntPtr.Zero) continue;
                                IntPtr cclass = il2cpp_object_get_class(cobj);
                                if (cclass == IntPtr.Zero) continue;
                                string ctxName = Marshal.PtrToStringAnsi(il2cpp_class_get_name(cclass));
                                if (ctxName != "MapRegionItemContext") continue;
                                IntPtr fRegion = IntPtr.Zero;
                                uint rOff = 0;
                                IntPtr scan = cclass;
                                while (scan != IntPtr.Zero)
                                {
                                    IntPtr fIter = IntPtr.Zero;
                                    IntPtr ff;
                                    while ((ff = il2cpp_class_get_fields(scan, ref fIter)) != IntPtr.Zero)
                                    {
                                        string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(ff));
                                        if (fn == "_regionType")
                                        { fRegion = ff; rOff = il2cpp_field_get_offset(ff); break; }
                                    }
                                    if (fRegion != IntPtr.Zero) break;
                                    scan = il2cpp_class_get_parent(scan);
                                }
                                if (fRegion == IntPtr.Zero) continue;
                                int rid = Marshal.ReadInt32(cobj, (int)rOff);
                                if (n > 0) sb.Append(",");
                                sb.Append(rid);
                                n++;
                            }
                            catch { }
                        }
                        if (pair.Value < 12)
                        {
                            for (int ci = 0; ci < t.childCount && ci < 60; ci++)
                                queue.Enqueue(new KeyValuePair<Transform, int>(t.GetChild(ci), pair.Value + 1));
                        }
                    }
                }
                sb.Append("],\"count\":").Append(n).Append("}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        private bool FindRegionItemByRegionType(Transform root, int targetId,
            out IntPtr ctxObj, out IntPtr ctxClass,
            out string ctxClassName, ref int candidates)
        {
            ctxObj = IntPtr.Zero; ctxClass = IntPtr.Zero; ctxClassName = null;
            var queue = new Queue<KeyValuePair<Transform, int>>();
            queue.Enqueue(new KeyValuePair<Transform, int>(root, 0));
            int searched = 0;
            while (queue.Count > 0 && searched < 1500)
            {
                var pair = queue.Dequeue();
                var t = pair.Key;
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
                        IntPtr getCtx = IntPtr.Zero;
                        IntPtr klass = monoClass;
                        while (klass != IntPtr.Zero && getCtx == IntPtr.Zero)
                        {
                            IntPtr mIter = IntPtr.Zero;
                            IntPtr m;
                            while ((m = il2cpp_class_get_methods(klass, ref mIter)) != IntPtr.Zero)
                            {
                                string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                                if (mn == "get_Context" && il2cpp_method_get_param_count(m) == 0)
                                { getCtx = m; break; }
                            }
                            if (getCtx == IntPtr.Zero) klass = il2cpp_class_get_parent(klass);
                        }
                        if (getCtx == IntPtr.Zero) continue;
                        IntPtr exc = IntPtr.Zero;
                        IntPtr cobj = il2cpp_runtime_invoke(getCtx, monoPtr, IntPtr.Zero, ref exc);
                        if (exc != IntPtr.Zero || cobj == IntPtr.Zero) continue;
                        IntPtr cclass = il2cpp_object_get_class(cobj);
                        if (cclass == IntPtr.Zero) continue;
                        string sn = Marshal.PtrToStringAnsi(il2cpp_class_get_name(cclass));
                        if (sn != "MapRegionItemContext") continue;
                        IntPtr fRegion = IntPtr.Zero;
                        uint rOff = 0;
                        IntPtr scan = cclass;
                        while (scan != IntPtr.Zero)
                        {
                            IntPtr fIter = IntPtr.Zero;
                            IntPtr ff;
                            while ((ff = il2cpp_class_get_fields(scan, ref fIter)) != IntPtr.Zero)
                            {
                                string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(ff));
                                if (fn == "_regionType")
                                { fRegion = ff; rOff = il2cpp_field_get_offset(ff); break; }
                            }
                            if (fRegion != IntPtr.Zero) break;
                            scan = il2cpp_class_get_parent(scan);
                        }
                        if (fRegion == IntPtr.Zero) continue;
                        candidates++;
                        int rid = Marshal.ReadInt32(cobj, (int)rOff);
                        if (rid != targetId) continue;
                        ctxObj = cobj;
                        ctxClass = cclass;
                        ctxClassName = sn;
                        return true;
                    }
                    catch { }
                }
                if (pair.Value < 12)
                {
                    for (int ci = 0; ci < t.childCount && ci < 60; ci++)
                        queue.Enqueue(new KeyValuePair<Transform, int>(t.GetChild(ci), pair.Value + 1));
                }
            }
            return false;
        }

        // =====================================================
        // /open-stage-tile?id=N — replicates "user taps stage tile in
        // chapter map" by walking the active scene for any StageContext
        // (StorylineStageContext / DungeonStageContext / etc.) whose
        // `_stage.Id == N`, then invoking its `OpenSelectionDialog()`.
        // Replaces the dead /open-stage cmd path (server returns 404 on
        // OpenStageCmd — Plarium retired it).
        // Requires the chapter map / region dialog to already be open
        // (the StageContext only exists while the chapter is rendered).
        // =====================================================
        private string OpenStageTile(string idStr)
        {
            if (string.IsNullOrEmpty(idStr) || !int.TryParse(idStr, out int targetId))
                return "{\"error\":\"id (int) required\"}";
            try
            {
                var dialogsRoot = GameObject.Find("UIManager/Canvas (Ui Root)/Dialogs");
                if (dialogsRoot == null)
                    return "{\"error\":\"no Dialogs root\"}";

                int candidates = 0;
                IntPtr hitObj = IntPtr.Zero, hitClass = IntPtr.Zero;
                IntPtr stageFieldPtr = IntPtr.Zero, idFieldPtr = IntPtr.Zero;
                uint stageOff = 0, idOff = 0;
                string hitClassName = null;

                // Pass 1: active dialogs (chapter map likely renders an active
                // RegionDialog with StageContext children)
                for (int di = 0; di < dialogsRoot.transform.childCount; di++)
                {
                    var dialog = dialogsRoot.transform.GetChild(di);
                    if (!dialog.gameObject.activeSelf) continue;
                    if (FindStageContextByStageId(dialog, targetId,
                            out hitObj, out hitClass, out stageOff, out idOff,
                            out stageFieldPtr, out idFieldPtr, out hitClassName,
                            ref candidates))
                        break;
                }
                // Pass 2: inactive dialogs (chapter map gets deactivated when
                // heroes-selection dialog overlays it; the StageContexts still
                // live inside but the parent GO is activeSelf=false)
                if (hitObj == IntPtr.Zero)
                {
                    for (int di = 0; di < dialogsRoot.transform.childCount; di++)
                    {
                        var dialog = dialogsRoot.transform.GetChild(di);
                        if (dialog.gameObject.activeSelf) continue;
                        if (FindStageContextByStageId(dialog, targetId,
                                out hitObj, out hitClass, out stageOff, out idOff,
                                out stageFieldPtr, out idFieldPtr, out hitClassName,
                                ref candidates))
                            break;
                    }
                }
                if (hitObj == IntPtr.Zero)
                    return "{\"error\":\"no StageContext with _stage.Id=" + targetId
                           + " in active dialogs\",\"candidates_scanned\":" + candidates + "}";

                // Walk class hierarchy to find OpenSelectionDialog method (0-arg)
                IntPtr method = IntPtr.Zero;
                IntPtr cscan = hitClass;
                while (cscan != IntPtr.Zero && method == IntPtr.Zero)
                {
                    IntPtr mIter = IntPtr.Zero;
                    IntPtr m;
                    while ((m = il2cpp_class_get_methods(cscan, ref mIter)) != IntPtr.Zero)
                    {
                        string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                        if (mn == "OpenSelectionDialog" && il2cpp_method_get_param_count(m) == 0)
                        {
                            method = m;
                            break;
                        }
                    }
                    if (method == IntPtr.Zero)
                        cscan = il2cpp_class_get_parent(cscan);
                }
                if (method == IntPtr.Zero)
                    return "{\"error\":\"OpenSelectionDialog/0 not found on " + Esc(hitClassName ?? "?") + " hierarchy\"}";

                IntPtr exc = IntPtr.Zero;
                il2cpp_runtime_invoke(method, hitObj, IntPtr.Zero, ref exc);
                if (exc != IntPtr.Zero)
                    return "{\"error\":\"OpenSelectionDialog threw\",\"ctx\":\"" + Esc(hitClassName ?? "?") + "\"}";

                return "{\"ok\":true,\"stage_id\":" + targetId + ",\"ctx\":\"" + Esc(hitClassName ?? "?") + "\"}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        /// <summary>
        /// BFS the scene tree under `root` for any MonoBehaviour whose
        /// IL2CPP context has a `_stage` field of type Stage with `_stage.Id == targetId`.
        /// Returns the matched object pointer + class.
        /// </summary>
        private bool FindStageContextByStageId(Transform root, int targetId,
            out IntPtr ctxObj, out IntPtr ctxClass,
            out uint stageOff, out uint idOff,
            out IntPtr stageFieldPtr, out IntPtr idFieldPtr,
            out string ctxClassName, ref int candidates)
        {
            ctxObj = IntPtr.Zero; ctxClass = IntPtr.Zero;
            stageOff = 0; idOff = 0;
            stageFieldPtr = IntPtr.Zero; idFieldPtr = IntPtr.Zero;
            ctxClassName = null;

            var queue = new Queue<KeyValuePair<Transform, int>>();
            queue.Enqueue(new KeyValuePair<Transform, int>(root, 0));
            int searched = 0;
            while (queue.Count > 0 && searched < 1500)
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

                        // Find get_Context on class hierarchy (UIElement <T>)
                        IntPtr getCtx = IntPtr.Zero;
                        IntPtr klass = monoClass;
                        while (klass != IntPtr.Zero && getCtx == IntPtr.Zero)
                        {
                            IntPtr mIter = IntPtr.Zero;
                            IntPtr mm;
                            while ((mm = il2cpp_class_get_methods(klass, ref mIter)) != IntPtr.Zero)
                            {
                                string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(mm));
                                if (mn == "get_Context" && il2cpp_method_get_param_count(mm) == 0)
                                { getCtx = mm; break; }
                            }
                            if (getCtx == IntPtr.Zero) klass = il2cpp_class_get_parent(klass);
                        }
                        if (getCtx == IntPtr.Zero) continue;

                        IntPtr exc = IntPtr.Zero;
                        IntPtr cobj = il2cpp_runtime_invoke(getCtx, monoPtr, IntPtr.Zero, ref exc);
                        if (exc != IntPtr.Zero || cobj == IntPtr.Zero) continue;

                        IntPtr cclass = il2cpp_object_get_class(cobj);
                        if (cclass == IntPtr.Zero) continue;

                        // Walk class hierarchy: must descend from StageContext
                        // (i.e. a tile in a chapter map), NOT from a dialog
                        // context. HeroesSelection*DialogContext also has _stage
                        // but it doesn't have OpenSelectionDialog/0.
                        IntPtr scanForBase = cclass;
                        bool isStageCtxSubclass = false;
                        while (scanForBase != IntPtr.Zero)
                        {
                            string sn = Marshal.PtrToStringAnsi(il2cpp_class_get_name(scanForBase));
                            if (sn == "StageContext") { isStageCtxSubclass = true; break; }
                            if (sn == "Object" || sn == "Il2CppObjectBase") break;
                            scanForBase = il2cpp_class_get_parent(scanForBase);
                        }
                        if (!isStageCtxSubclass) continue;

                        // Walk class hierarchy for _stage field
                        IntPtr fStage = IntPtr.Zero;
                        uint sOff = 0;
                        IntPtr scan = cclass;
                        while (scan != IntPtr.Zero)
                        {
                            IntPtr fIter = IntPtr.Zero;
                            IntPtr ff;
                            while ((ff = il2cpp_class_get_fields(scan, ref fIter)) != IntPtr.Zero)
                            {
                                string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(ff));
                                if (fn == "_stage")
                                { fStage = ff; sOff = il2cpp_field_get_offset(ff); break; }
                            }
                            if (fStage != IntPtr.Zero) break;
                            scan = il2cpp_class_get_parent(scan);
                        }
                        if (fStage == IntPtr.Zero) continue;
                        candidates++;

                        IntPtr stagePtr = Marshal.ReadIntPtr(cobj, (int)sOff);
                        if (stagePtr == IntPtr.Zero) continue;
                        IntPtr stageClass = il2cpp_object_get_class(stagePtr);

                        IntPtr fId = IntPtr.Zero;
                        uint iOff = 0;
                        IntPtr ssc = stageClass;
                        while (ssc != IntPtr.Zero)
                        {
                            IntPtr fIter = IntPtr.Zero;
                            IntPtr ff;
                            while ((ff = il2cpp_class_get_fields(ssc, ref fIter)) != IntPtr.Zero)
                            {
                                string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(ff));
                                if (fn == "Id")
                                { fId = ff; iOff = il2cpp_field_get_offset(ff); break; }
                            }
                            if (fId != IntPtr.Zero) break;
                            ssc = il2cpp_class_get_parent(ssc);
                        }
                        if (fId == IntPtr.Zero) continue;

                        int sid = Marshal.ReadInt32(stagePtr, (int)iOff);
                        if (sid != targetId) continue;

                        ctxObj = cobj;
                        ctxClass = cclass;
                        stageOff = sOff;
                        idOff = iOff;
                        stageFieldPtr = fStage;
                        idFieldPtr = fId;
                        ctxClassName = Marshal.PtrToStringAnsi(il2cpp_class_get_name(cclass));
                        return true;
                    }
                    catch { }
                }
                if (depth < 12)
                {
                    for (int ci = 0; ci < t.childCount && ci < 60; ci++)
                        queue.Enqueue(new KeyValuePair<Transform, int>(t.GetChild(ci), depth + 1));
                }
            }
            return false;
        }

        // =====================================================
        // /current-stage — reads Stage.Id from the open Heroes*Selection
        // dialog context (campaign Pve / dungeon / arena / etc.). The
        // dialog has a `_stage : Stage` field on its dialog ctx; Stage.Id
        // is the integer the game's CreatePveBattleCmd / OpenStageCmd
        // would carry. Use this instead of the OpenStageCmd Harmony
        // hook — taps don't always fire that cmd, but the dialog ALWAYS
        // holds the stage ref while it's open.
        // =====================================================
        private string CurrentStage()
        {
            try
            {
                var dialogsRoot = GameObject.Find("UIManager/Canvas (Ui Root)/Dialogs");
                if (dialogsRoot == null)
                    return "{\"error\":\"no Dialogs root\"}";

                IntPtr ctxObj = IntPtr.Zero, ctxClass = IntPtr.Zero;
                string ctxName = null, ctxNs = null;
                for (int di = 0; di < dialogsRoot.transform.childCount; di++)
                {
                    var dialog = dialogsRoot.transform.GetChild(di);
                    if (!dialog.gameObject.activeSelf) continue;
                    if (TryFindHeroesSelectionContext(dialog, out ctxObj, out ctxClass, out ctxName, out ctxNs))
                        break;
                }
                if (ctxObj == IntPtr.Zero)
                {
                    for (int di = 0; di < dialogsRoot.transform.childCount; di++)
                    {
                        var dialog = dialogsRoot.transform.GetChild(di);
                        if (dialog.gameObject.activeSelf) continue;
                        if (TryFindHeroesSelectionContext(dialog, out ctxObj, out ctxClass, out ctxName, out ctxNs))
                            break;
                    }
                }
                if (ctxObj == IntPtr.Zero)
                    return "{\"error\":\"no active heroes-selection dialog\"}";

                // Walk class hierarchy looking for _stage field.
                IntPtr stageFieldPtr = IntPtr.Zero;
                uint stageOff = 0;
                IntPtr scan = ctxClass;
                while (scan != IntPtr.Zero)
                {
                    IntPtr fIter = IntPtr.Zero;
                    IntPtr ff;
                    while ((ff = il2cpp_class_get_fields(scan, ref fIter)) != IntPtr.Zero)
                    {
                        string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(ff));
                        if (fn == "_stage")
                        {
                            stageFieldPtr = ff;
                            stageOff = il2cpp_field_get_offset(ff);
                            break;
                        }
                    }
                    if (stageFieldPtr != IntPtr.Zero) break;
                    scan = il2cpp_class_get_parent(scan);
                }
                if (stageFieldPtr == IntPtr.Zero)
                    return "{\"error\":\"_stage field not on dialog class chain\",\"ctx\":\"" + Esc(ctxName ?? "?") + "\"}";

                IntPtr stagePtr = Marshal.ReadIntPtr(ctxObj, (int)stageOff);
                if (stagePtr == IntPtr.Zero)
                    return "{\"error\":\"_stage is null (dialog open but stage not bound yet)\"}";

                IntPtr stageClass = il2cpp_object_get_class(stagePtr);
                IntPtr idFieldPtr = IntPtr.Zero;
                uint idOff = 0;
                IntPtr ssc = stageClass;
                while (ssc != IntPtr.Zero)
                {
                    IntPtr fIter = IntPtr.Zero;
                    IntPtr ff;
                    while ((ff = il2cpp_class_get_fields(ssc, ref fIter)) != IntPtr.Zero)
                    {
                        string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(ff));
                        if (fn == "Id")
                        {
                            idFieldPtr = ff;
                            idOff = il2cpp_field_get_offset(ff);
                            break;
                        }
                    }
                    if (idFieldPtr != IntPtr.Zero) break;
                    ssc = il2cpp_class_get_parent(ssc);
                }
                if (idFieldPtr == IntPtr.Zero)
                    return "{\"error\":\"Stage.Id field not found\"}";

                int stageId = Marshal.ReadInt32(stagePtr, (int)idOff);
                return "{\"ok\":true,\"stage_id\":" + stageId
                       + ",\"dialog_ctx\":\"" + Esc(ctxName ?? "?") + "\"}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // =====================================================
        // /last-stage-id — returns the most recent stage id observed by
        // the OpenStageCmd..ctor(int) Harmony hook, plus a short history.
        // Workflow: user taps the desired stage tile in-game once -> we
        // capture the real stageId -> farm_loop calls /open-stage?id=N
        // forever after.
        // =====================================================
        private string LastStageId()
        {
            try
            {
                int last = _lastOpenedStageId;
                string hist;
                lock (_stageIdHistory)
                {
                    hist = string.Join(",", _stageIdHistory);
                }
                return "{\"ok\":true,\"last\":" + last + ",\"history\":[" + hist + "]}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // =====================================================
        // /open-stage?id=N — invokes OpenStageCmd(stageId).
        // For campaign Nightmare 12-3 try 12034 (chapter*1000 + stage*10 + diff)
        // =====================================================
        private string OpenStage(string idStr)
        {
            if (string.IsNullOrEmpty(idStr) || !int.TryParse(idStr, out int stageId))
                return "{\"error\":\"id (int) required\"}";
            var cmdType = FindType("Client.Model.Gameplay.Stages.Commands.OpenStageCmd");
            if (cmdType == null) return "{\"error\":\"OpenStageCmd not found\"}";
            try
            {
                var ctor = cmdType.GetConstructor(new[] { typeof(int) });
                if (ctor == null) return "{\"error\":\"OpenStageCmd(int) ctor not found\"}";
                var cmd = ctor.Invoke(new object[] { stageId });
                Logger.LogInfo("[OpenStage] enqueue stageId=" + stageId);
                InvokeExecute(cmd);
                return "{\"ok\":true,\"stage_id\":" + stageId + "}";
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

        // =====================================================
        // API: /claim-cb-chests
        //
        // Claim every pending Clan Boss reward chest (UNM/NM/Brutal/Hard/
        // Normal/Easy stars) without opening the CB UI. Each chest the
        // game shows on the right-hand side of the AllianceEnemiesDialog
        // is one TakeAllianceBossRewardCmd(AllianceBossTypeId) cycle —
        // we fire one per difficulty (0..5) with a stagger.
        //
        // Constructed via raw IL2CPP (il2cpp_object_new + ctor invoke)
        // because Activator.CreateInstance leaves pooledPtr=0 on certain
        // cmd classes, making Execute a silent no-op (same root cause as
        // /claim-inbox-il2cpp).
        //
        // Server validates per-chest: difficulties without an unclaimed
        // chest get rejected (we ignore IfError, count those as skipped).
        // =====================================================
        private string ClaimCbChests()
        {
            try
            {
                var cmdT = FindType(
                    "Client.Model.Gameplay.Alliance.Commands.ClanBossRewards.TakeAllianceBossRewardCmd");
                if (cmdT == null)
                    return "{\"error\":\"TakeAllianceBossRewardCmd not found\"}";

                IntPtr cmdCls = GetIL2CppClassPtr(cmdT);
                if (cmdCls == IntPtr.Zero)
                    return "{\"error\":\"cmd IL2Cpp class ptr is zero\"}";

                IntPtr ctorM = FindIL2CPPMethod(cmdCls, ".ctor", 1);
                if (ctorM == IntPtr.Zero)
                    return "{\"error\":\".ctor(AllianceBossTypeId) not found\"}";

                IntPtr execM = FindIL2CppMethodOnHierarchy(cmdCls, "Execute", 0);
                if (execM == IntPtr.Zero)
                    return "{\"error\":\"Execute() not found\"}";

                var sb = new StringBuilder();
                sb.Append("{\"results\":[");
                int firedOk = 0, errors = 0;

                // AllianceBossTypeId: 0=Easy 1=Normal 2=Hard 3=Brutal 4=Nightmare 5=UltraNightmare
                // Only fire for NM + UNM. Users almost never have pending
                // chests in Easy-Brutal, and each rejected cmd produces a
                // "Demon Lord Chest not found" MessageBox that stacks on the
                // server queue, blocking subsequent UI flows (e.g. arena
                // /messagebox-click confuses these stale CB error MBs for
                // arena warnings). Verified 2026-05-10: cb_daily ran 12 cmds
                // (6×2 calls), generated ~10 error MBs that took minutes to
                // drain via the cmd queue.
                string[] diffNames = { "Easy", "Normal", "Hard", "Brutal", "Nightmare", "UltraNightmare" };
                for (int diff = 4; diff < 6; diff++)
                {
                    if (diff > 0) sb.Append(",");
                    sb.Append("{\"diff\":\"").Append(diffNames[diff]).Append("\",\"id\":").Append(diff);

                    IntPtr cmdPtr = il2cpp_object_new(cmdCls);
                    if (cmdPtr == IntPtr.Zero)
                    {
                        sb.Append(",\"error\":\"il2cpp_object_new null\"}");
                        errors++; continue;
                    }

                    int[] argBuf = { diff };
                    var pinArg = System.Runtime.InteropServices.GCHandle.Alloc(
                        argBuf, System.Runtime.InteropServices.GCHandleType.Pinned);
                    IntPtr[] argList = { pinArg.AddrOfPinnedObject() };
                    var pinList = System.Runtime.InteropServices.GCHandle.Alloc(
                        argList, System.Runtime.InteropServices.GCHandleType.Pinned);
                    IntPtr exc = IntPtr.Zero;
                    try
                    {
                        il2cpp_runtime_invoke(ctorM, cmdPtr, pinList.AddrOfPinnedObject(), ref exc);
                    }
                    finally { pinList.Free(); pinArg.Free(); }

                    if (exc != IntPtr.Zero)
                    {
                        sb.Append(",\"error\":\"ctor threw\"}");
                        errors++; continue;
                    }

                    // Keep-alive managed wrapper
                    object cmdMgd = null;
                    try { cmdMgd = Activator.CreateInstance(cmdT, cmdPtr); }
                    catch { /* wrapper is for keep-alive only; safe to ignore */ }

                    IntPtr exc2 = IntPtr.Zero;
                    il2cpp_runtime_invoke(execM, cmdPtr, IntPtr.Zero, ref exc2);
                    if (exc2 != IntPtr.Zero)
                    {
                        sb.Append(",\"error\":\"Execute threw\"}");
                        errors++;
                    }
                    else
                    {
                        sb.Append(",\"ok\":true}");
                        firedOk++;
                        Logger.LogInfo("[CbChests] dispatched TakeAllianceBossRewardCmd for diff="
                                       + diffNames[diff]);
                    }

                    // Stagger so the cmd queue / server can serialize requests.
                    System.Threading.Thread.Sleep(300);
                    GC.KeepAlive(cmdMgd);
                }

                sb.Append("],\"fired\":").Append(firedOk);
                sb.Append(",\"errors\":").Append(errors).Append("}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.GetType().Name + ": " + ex.Message) + "\"}";
            }
        }

        // =====================================================
        // Helper: invoke an IL2Cpp ctor with a single int argument and run
        // Execute. Used by SummonHeroes / BuyMagicShopItem / etc. — same
        // shape as ClaimCbChests but factored out so each endpoint stays
        // tight. Returns null on success, error string on failure.
        // =====================================================
        private string FireIntCmd(string cmdFqn, int arg, out object cmdMgd)
        {
            cmdMgd = null;
            var cmdT = FindType(cmdFqn);
            if (cmdT == null) return "type not found: " + cmdFqn;
            IntPtr cmdCls = GetIL2CppClassPtr(cmdT);
            if (cmdCls == IntPtr.Zero) return "IL2Cpp class ptr is zero";
            IntPtr ctorM = FindIL2CPPMethod(cmdCls, ".ctor", 1);
            if (ctorM == IntPtr.Zero) return ".ctor(int) not found";
            IntPtr execM = FindIL2CppMethodOnHierarchy(cmdCls, "Execute", 0);
            if (execM == IntPtr.Zero) return "Execute() not found";

            IntPtr cmdPtr = il2cpp_object_new(cmdCls);
            if (cmdPtr == IntPtr.Zero) return "il2cpp_object_new returned null";

            int[] argBuf = { arg };
            var pinArg = System.Runtime.InteropServices.GCHandle.Alloc(
                argBuf, System.Runtime.InteropServices.GCHandleType.Pinned);
            IntPtr[] argList = { pinArg.AddrOfPinnedObject() };
            var pinList = System.Runtime.InteropServices.GCHandle.Alloc(
                argList, System.Runtime.InteropServices.GCHandleType.Pinned);
            IntPtr exc = IntPtr.Zero;
            try
            {
                il2cpp_runtime_invoke(ctorM, cmdPtr, pinList.AddrOfPinnedObject(), ref exc);
            }
            finally { pinList.Free(); pinArg.Free(); }
            if (exc != IntPtr.Zero) return "ctor threw IL2Cpp exception";

            try { cmdMgd = Activator.CreateInstance(cmdT, cmdPtr); } catch { }

            IntPtr exc2 = IntPtr.Zero;
            il2cpp_runtime_invoke(execM, cmdPtr, IntPtr.Zero, ref exc2);
            if (exc2 != IntPtr.Zero) return "Execute threw IL2Cpp exception";
            return null;
        }

        // Invoke a 2-arg ctor (int, int). Used for SummonHeroesCmd which
        // takes (ShardTypeId, count). Other 2-arg cmds slot in here too.
        private string FireIntIntCmd(string cmdFqn, int arg1, int arg2, out object cmdMgd)
        {
            cmdMgd = null;
            var cmdT = FindType(cmdFqn);
            if (cmdT == null) return "type not found: " + cmdFqn;
            IntPtr cmdCls = GetIL2CppClassPtr(cmdT);
            if (cmdCls == IntPtr.Zero) return "IL2Cpp class ptr is zero";
            IntPtr ctorM = FindIL2CPPMethod(cmdCls, ".ctor", 2);
            if (ctorM == IntPtr.Zero) return ".ctor(int,int) not found";
            IntPtr execM = FindIL2CppMethodOnHierarchy(cmdCls, "Execute", 0);
            if (execM == IntPtr.Zero) return "Execute() not found";

            IntPtr cmdPtr = il2cpp_object_new(cmdCls);
            if (cmdPtr == IntPtr.Zero) return "il2cpp_object_new returned null";

            int[] argBuf1 = { arg1 };
            int[] argBuf2 = { arg2 };
            var pin1 = System.Runtime.InteropServices.GCHandle.Alloc(
                argBuf1, System.Runtime.InteropServices.GCHandleType.Pinned);
            var pin2 = System.Runtime.InteropServices.GCHandle.Alloc(
                argBuf2, System.Runtime.InteropServices.GCHandleType.Pinned);
            IntPtr[] argList = { pin1.AddrOfPinnedObject(), pin2.AddrOfPinnedObject() };
            var pinList = System.Runtime.InteropServices.GCHandle.Alloc(
                argList, System.Runtime.InteropServices.GCHandleType.Pinned);
            IntPtr exc = IntPtr.Zero;
            try
            {
                il2cpp_runtime_invoke(ctorM, cmdPtr, pinList.AddrOfPinnedObject(), ref exc);
            }
            finally { pinList.Free(); pin2.Free(); pin1.Free(); }
            if (exc != IntPtr.Zero) return "ctor threw IL2Cpp exception";

            try { cmdMgd = Activator.CreateInstance(cmdT, cmdPtr); } catch { }

            IntPtr exc2 = IntPtr.Zero;
            il2cpp_runtime_invoke(execM, cmdPtr, IntPtr.Zero, ref exc2);
            if (exc2 != IntPtr.Zero) return "Execute threw IL2Cpp exception";
            return null;
        }

        // =====================================================
        // API: /summon-heroes?type=mystery&count=3
        //
        // Fires SummonHeroesCmd(ShardTypeId, count). Validation can reject
        // counts other than 1 / 10 (game's IsValidSummonCount); we issue
        // count separate single-summon cmds so the daily-quest counter
        // ticks per shard and odd values like 3 don't get rejected.
        //
        // Default portal = mystery (cheapest, user has 3392 in stock).
        // Stops early if shard balance is exhausted mid-loop.
        // =====================================================
        private string SummonHeroes(string typeStr, string countStr)
        {
            int shardId = 1; // Mystery default
            if (!string.IsNullOrEmpty(typeStr))
            {
                switch (typeStr.ToLowerInvariant())
                {
                    case "mystery": shardId = 1; break;
                    case "ancient": shardId = 3; break;
                    case "void": shardId = 6; break;
                    case "sacred": shardId = 5; break;  // Legendary
                    case "legendary": shardId = 5; break;
                    case "primal":
                    case "mythical": shardId = 7; break;
                    default:
                        if (!int.TryParse(typeStr, out shardId))
                            return "{\"error\":\"unknown shard type: " + Esc(typeStr) + "\"}";
                        break;
                }
            }
            int count = 1;
            if (!string.IsNullOrEmpty(countStr) && !int.TryParse(countStr, out count))
                return "{\"error\":\"count must be int\"}";
            if (count < 1 || count > 100) return "{\"error\":\"count out of range\"}";

            int fired = 0, errors = 0;
            var sb = new StringBuilder();
            sb.Append("{\"results\":[");
            for (int i = 0; i < count; i++)
            {
                if (i > 0) sb.Append(",");
                string err = FireIntIntCmd(
                    "Client.Model.Gameplay.Heroes.Commands.SummonHeroesCmd",
                    shardId, 1, out object cmdMgd);
                if (err != null)
                {
                    sb.Append("{\"i\":").Append(i).Append(",\"error\":\"").Append(Esc(err)).Append("\"}");
                    errors++;
                    if (err.Contains("threw")) break;  // shard ran out / invalid
                }
                else
                {
                    sb.Append("{\"i\":").Append(i).Append(",\"ok\":true}");
                    fired++;
                    Logger.LogInfo("[Summon] dispatched SummonHeroesCmd type=" + shardId + " #" + (i + 1));
                }
                System.Threading.Thread.Sleep(400);
                GC.KeepAlive(cmdMgd);
            }
            sb.Append("],\"fired\":").Append(fired);
            sb.Append(",\"errors\":").Append(errors);
            sb.Append(",\"shard_type\":").Append(shardId).Append("}");
            return sb.ToString();
        }

        // =====================================================
        // API: /upgrade-junk-artifacts?count=4
        //
        // Picks `count` cheapest unequipped low-rank artifacts from the
        // vault and fires UpgradeArtifactCmd against each — one +1 level
        // per cmd. Each cmd ticks the daily "Upgrade Artifacts" quest.
        //
        // Selection: unequipped + level<16 + lowest rank/rarity first.
        // Skips equipped artifacts and rank-6 (legendary) gear.
        // =====================================================
        private string UpgradeJunkArtifacts(string countStr)
        {
            int count = 4;
            if (!string.IsNullOrEmpty(countStr) && !int.TryParse(countStr, out count))
                return "{\"error\":\"count must be int\"}";
            if (count < 1 || count > 20) return "{\"error\":\"count out of range\"}";

            // Build set of equipped artifact ids so we skip those.
            var equippedIds = new HashSet<int>();
            object uw = GetUserWrapper();
            if (uw == null) return "{\"error\":\"not logged in\"}";
            object equipment = Prop(uw, "Artifacts");
            if (equipment == null) return "{\"error\":\"no equipment wrapper\"}";
            object artData = Prop(equipment, "ArtifactData");
            if (artData != null)
            {
                object byHero = Prop(artData, "ArtifactDataByHeroId");
                if (byHero != null)
                {
                    foreach (var heroEntry in DictEntries(byHero))
                    {
                        var heroArtData = heroEntry.Value;
                        if (heroArtData == null) continue;
                        object idByKind = Prop(heroArtData, "ArtifactIdByKind");
                        if (idByKind == null) continue;
                        foreach (var slotEntry in DictEntries(idByKind))
                        {
                            int aid = 0;
                            try { aid = Convert.ToInt32(slotEntry.Value); } catch { }
                            if (aid > 0) equippedIds.Add(aid);
                        }
                    }
                }
            }

            // Walk ALL artifacts and pick the cheapest junk.
            // (rank, rarity, level) ascending — start with the cheapest +1.
            // Use One(id) scan from 1..LastArtifactId — same fallback path
            // /all-artifacts uses (the "All" IEnumerable doesn't expose an
            // indexer, so ListItems sees 0 entries for it).
            var candidates = new List<(int id, int rank, int rarity, int level)>();
            int lastId = 0;
            try { lastId = Convert.ToInt32(Prop(artData, "LastArtifactId")); } catch { }
            var oneMethod = equipment.GetType().GetMethod("One");
            int seen = 0, skipNoId = 0, skipEquipped = 0, skipRank = 0, skipLevel = 0;
            if (oneMethod != null && lastId > 0)
            {
                for (int aid = 1; aid <= lastId; aid++)
                {
                    object art = null;
                    try { art = oneMethod.Invoke(equipment, new object[] { aid }); } catch { continue; }
                    if (art == null) continue;
                    seen++;
                    if (equippedIds.Contains(aid)) { skipEquipped++; continue; }
                    int rank = TryInt(Prop(art, "RankId"));
                    if (rank <= 0 || rank >= 6) { skipRank++; continue; }
                    int rarity = TryInt(Prop(art, "RarityId"));
                    int level = TryInt(Prop(art, "Level"));
                    if (level >= 16) { skipLevel++; continue; }
                    candidates.Add((aid, rank, rarity, level));
                }
            }
            Logger.LogInfo("[UpgradeJunk] last_id=" + lastId + " seen=" + seen
                           + " equipped=" + skipEquipped + " rank_excluded=" + skipRank
                           + " level_excluded=" + skipLevel
                           + " candidates=" + candidates.Count);
            candidates.Sort((a, b) =>
            {
                int c = a.rank.CompareTo(b.rank);
                if (c != 0) return c;
                c = a.rarity.CompareTo(b.rarity);
                if (c != 0) return c;
                return a.level.CompareTo(b.level);
            });

            if (candidates.Count == 0)
                return "{\"error\":\"no upgradable junk artifacts found\"}";

            // Construct UpgradeArtifactRequestDto for each pick. The DTO
            // has ArtifactId (int), ArtifactLocation (1=UserInventory),
            // UpgradeLevelLimit (Nullable<int>, leave null → +1 only).
            var dtoT = FindType("SharedModel.Meta.Artifacts.Dtos.UpgradeArtifactRequestDto");
            if (dtoT == null) return "{\"error\":\"UpgradeArtifactRequestDto type not found\"}";
            var cmdT = FindType("Client.Model.Gameplay.Artifacts.Commands.UpgradeArtifactCmd");
            if (cmdT == null)
            {
                // Some namespaces ship under "MagicShop" or a sibling — try fallback.
                cmdT = FindTypeByLeafName("UpgradeArtifactCmd");
            }
            if (cmdT == null) return "{\"error\":\"UpgradeArtifactCmd type not found\"}";

            var ctor = cmdT.GetConstructor(new[] { dtoT });
            if (ctor == null) return "{\"error\":\"UpgradeArtifactCmd(dto) ctor not found\"}";
            var dtoCtor = dtoT.GetConstructor(System.Type.EmptyTypes);
            if (dtoCtor == null) return "{\"error\":\"UpgradeArtifactRequestDto() ctor not found\"}";

            int fired = 0, errors = 0;
            int pick = Math.Min(count, candidates.Count);
            var sb = new StringBuilder();
            sb.Append("{\"results\":[");
            for (int i = 0; i < pick; i++)
            {
                var c = candidates[i];
                if (i > 0) sb.Append(",");
                sb.Append("{\"i\":").Append(i)
                  .Append(",\"artifact_id\":").Append(c.id)
                  .Append(",\"rank\":").Append(c.rank)
                  .Append(",\"rarity\":").Append(c.rarity)
                  .Append(",\"level\":").Append(c.level);
                try
                {
                    object dto = dtoCtor.Invoke(null);
                    // IL2Cpp wraps public fields as properties — SetField is a
                    // silent no-op. Always set via property.
                    var idP = dtoT.GetProperty("ArtifactId");
                    var locP = dtoT.GetProperty("ArtifactLocation");
                    if (idP == null || locP == null)
                    {
                        sb.Append(",\"error\":\"DTO property setters missing\"}");
                        errors++; continue;
                    }
                    idP.SetValue(dto, c.id);
                    locP.SetValue(dto, 1);  // UserInventory

                    object cmd = ctor.Invoke(new[] { dto });
                    InvokeExecute(cmd);
                    sb.Append(",\"ok\":true}");
                    fired++;
                    Logger.LogInfo("[UpgradeArtifact] dispatched id=" + c.id + " rank=" + c.rank);
                }
                catch (System.Reflection.TargetInvocationException tex)
                {
                    var inner = tex.InnerException ?? tex;
                    sb.Append(",\"error\":\"").Append(Esc(inner.GetType().Name + ": " + inner.Message)).Append("\"}");
                    errors++;
                }
                catch (Exception ex)
                {
                    sb.Append(",\"error\":\"").Append(Esc(ex.GetType().Name + ": " + ex.Message)).Append("\"}");
                    errors++;
                }
                System.Threading.Thread.Sleep(350);
            }
            sb.Append("],\"fired\":").Append(fired);
            sb.Append(",\"errors\":").Append(errors);
            sb.Append(",\"vault_candidates\":").Append(candidates.Count).Append("}");
            return sb.ToString();
        }

        // =====================================================
        // API: /collect-loyalty-day
        //
        // Fires CollectLoyaltyProgramRewardCmd to claim the next
        // available daily reward from the active loyalty / chase
        // program (Skeletor Chase, Daily14DaysRewardProgramOverlay
        // etc.). The in-game UI's Collect button is dispatching a
        // broken cmd that NREs at Start ("StaticOffer.Buy l:1
        // c:Start NullReferenceException"); this endpoint fires the
        // documented loyalty cmd instead, which is a zero-arg
        // UserPostEditCmdNoIn that the server resolves against the
        // currently-active program.
        // =====================================================
        private string CollectLoyaltyDay()
        {
            object uw = GetUserWrapper();
            if (uw == null) return "{\"error\":\"not logged in\"}";

            var cmdType = FindType(
                "Client.Model.Gameplay.DailyRewards.Commands.CollectLoyaltyProgramRewardCmd")
                ?? FindTypeByLeafName("CollectLoyaltyProgramRewardCmd");
            if (cmdType == null)
                return "{\"error\":\"CollectLoyaltyProgramRewardCmd type not found\"}";

            var ctor = cmdType.GetConstructor(System.Type.EmptyTypes);
            if (ctor == null)
                return "{\"error\":\"CollectLoyaltyProgramRewardCmd() ctor not found\"}";

            object cmd;
            try { cmd = ctor.Invoke(null); }
            catch (System.Exception ex)
            {
                return "{\"error\":\"ctor failed: " +
                       Esc(ex.GetType().Name + ": " + ex.Message) + "\"}";
            }

            try
            {
                var ifErrorM = cmd.GetType().GetMethod("IfError",
                    BindingFlags.Instance | BindingFlags.Public | BindingFlags.FlattenHierarchy,
                    null, new[] { typeof(System.Action) }, null);
                if (ifErrorM != null)
                {
                    System.Action errCb = () =>
                        Logger.LogWarning("[CollectLoyaltyDay] server rejected");
                    ifErrorM.Invoke(cmd, new object[] { errCb });
                }
            }
            catch { }

            try { InvokeExecute(cmd); }
            catch (System.Exception ex)
            {
                return "{\"error\":\"InvokeExecute failed: " +
                       Esc(ex.GetType().Name + ": " + ex.Message) + "\"}";
            }

            Logger.LogInfo("[CollectLoyaltyDay] enqueued");
            return "{\"ok\":true,\"note\":\"enqueued; server claims next available day on active program\"}";
        }


        // =====================================================
        // API: /start-cb-battle?boss=5&heroes=15120,18607,2643,13615,5692&preset=1
        //
        // Bypass the broken in-game OnStartClick→HeroesSelection
        // transition by constructing CreateAllianceBossBattleCmd
        // directly. Same pattern as /buy-static-offer for the
        // PurchaseStaticOfferCmd workaround.
        //
        // Cmd ctor (from dump.cs):
        //   .ctor(AllianceBossTypeId bossId, int[] heroIds,
        //         Nullable<int> presetId, Nullable<bool> isQuickBattle)
        //
        // boss: 0=Easy 1=Normal 2=Hard 3=Brutal 4=Nightmare 5=UltraNightmare
        // heroes: comma-separated owned hero instance IDs (5 for CB)
        // preset: optional preset ID; passing it makes the cmd apply the
        //   skill priorities/starters. Pass 0 or omit for no preset.
        // =====================================================
        private string StartCbBattle(string bossStr, string heroesStr, string presetStr)
        {
            if (string.IsNullOrEmpty(bossStr) || !int.TryParse(bossStr, out int bossId)
                || bossId < 0 || bossId > 5)
                return "{\"error\":\"boss must be 0-5 (0=Easy ... 5=UltraNightmare)\"}";
            if (string.IsNullOrEmpty(heroesStr))
                return "{\"error\":\"heroes required (comma-separated instance IDs)\"}";

            var heroIds = new List<int>();
            foreach (var s in heroesStr.Split(','))
            {
                if (int.TryParse(s.Trim(), out int hid) && hid > 0)
                    heroIds.Add(hid);
            }
            if (heroIds.Count == 0)
                return "{\"error\":\"no valid hero IDs parsed\"}";

            int presetId = 0;
            if (!string.IsNullOrEmpty(presetStr)) int.TryParse(presetStr, out presetId);

            object uw = GetUserWrapper();
            if (uw == null) return "{\"error\":\"not logged in\"}";

            var cmdType = FindType("Client.Model.Gameplay.Battle.Commands.CreateAllianceBossBattleCmd")
                          ?? FindTypeByLeafName("CreateAllianceBossBattleCmd");
            if (cmdType == null)
                return "{\"error\":\"CreateAllianceBossBattleCmd type not found\"}";

            // Find the 4-arg ctor.
            object cmd = null;
            string ctorErr = null;
            foreach (var c in cmdType.GetConstructors(
                BindingFlags.Public | BindingFlags.Instance))
            {
                var ps = c.GetParameters();
                if (ps.Length != 4) continue;
                try
                {
                    // ps[0] = AllianceBossTypeId (enum, int-compatible)
                    // ps[1] = int[]
                    // ps[2] = Nullable<int>
                    // ps[3] = Nullable<bool>
                    object bossEnumVal;
                    try { bossEnumVal = System.Enum.ToObject(ps[0].ParameterType, bossId); }
                    catch { bossEnumVal = bossId; }

                    // Build Il2CppStructArray<int> — managed int[] doesn't
                    // auto-convert. Use the param's actual type (which IS
                    // Il2CppStructArray<int>) and instantiate with a length,
                    // then index-assign each value.
                    var arrType = ps[1].ParameterType;
                    object idsArray;
                    var arrCtor = arrType.GetConstructor(new[] { typeof(long) });
                    if (arrCtor != null)
                    {
                        idsArray = arrCtor.Invoke(new object[] { (long)heroIds.Count });
                    }
                    else
                    {
                        var arrCtor2 = arrType.GetConstructor(new[] { typeof(int) });
                        if (arrCtor2 == null)
                            throw new System.Exception("Il2CppStructArray<int> has no recognized ctor");
                        idsArray = arrCtor2.Invoke(new object[] { heroIds.Count });
                    }
                    var indexer = arrType.GetProperty("Item");
                    if (indexer == null)
                        throw new System.Exception("Il2CppStructArray<int> Item indexer not found");
                    for (int i = 0; i < heroIds.Count; i++)
                    {
                        indexer.SetValue(idsArray, heroIds[i], new object[] { i });
                    }

                    // Nullable<int> presetId
                    var nullableIntT = ps[2].ParameterType;
                    object nullableInt;
                    if (presetId > 0)
                    {
                        // Construct with value
                        var ctorWithVal = nullableIntT.GetConstructor(new[] { typeof(int) });
                        if (ctorWithVal != null)
                            nullableInt = ctorWithVal.Invoke(new object[] { presetId });
                        else
                            nullableInt = System.Activator.CreateInstance(nullableIntT, presetId);
                    }
                    else
                    {
                        var c0 = nullableIntT.GetConstructor(System.Type.EmptyTypes);
                        nullableInt = c0 != null ? c0.Invoke(null)
                                                  : System.Activator.CreateInstance(nullableIntT);
                    }

                    // Nullable<bool> isQuickBattle.
                    // Empirical: isQuickBattle=true means PARALLEL/background battle,
                    // which fails with Battle_ParallelInvalidRegion on this account.
                    // isQuickBattle=false = standard foreground battle requiring the
                    // BattleScene transition. Setting false here.
                    var nullableBoolT = ps[3].ParameterType;
                    object nullableBool;
                    var bValCtor = nullableBoolT.GetConstructor(new[] { typeof(bool) });
                    if (bValCtor != null)
                        nullableBool = bValCtor.Invoke(new object[] { false });
                    else
                        nullableBool = System.Activator.CreateInstance(nullableBoolT, false);

                    cmd = c.Invoke(new object[] {
                        bossEnumVal, idsArray, nullableInt, nullableBool
                    });
                    break;
                }
                catch (System.Reflection.TargetInvocationException tex)
                {
                    var inner = tex.InnerException ?? tex;
                    ctorErr = inner.GetType().Name + ": " + inner.Message;
                }
                catch (System.Exception cex)
                {
                    ctorErr = cex.GetType().Name + ": " + cex.Message;
                }
            }
            if (cmd == null)
                return "{\"error\":\"CreateAllianceBossBattleCmd ctor failed: " +
                       Esc(ctorErr ?? "no matching ctor") + "\"}";

            // Hook server-side rejection for visibility.
            try
            {
                var ifErrorM = cmd.GetType().GetMethod("IfError",
                    BindingFlags.Instance | BindingFlags.Public | BindingFlags.FlattenHierarchy,
                    null, new[] { typeof(System.Action) }, null);
                if (ifErrorM != null)
                {
                    int capturedBoss = bossId;
                    System.Action errCb = () =>
                        Logger.LogWarning("[StartCbBattle] server rejected boss=" + capturedBoss);
                    ifErrorM.Invoke(cmd, new object[] { errCb });
                }
            }
            catch { }

            try
            {
                InvokeExecute(cmd);
                Logger.LogInfo("[StartCbBattle] enqueued boss=" + bossId +
                               " heroes=" + heroIds.Count + " preset=" + presetId);
            }
            catch (System.Exception ex)
            {
                return "{\"error\":\"InvokeExecute failed: " +
                       Esc(ex.GetType().Name + ": " + ex.Message) + "\"}";
            }

            return "{\"ok\":true,\"boss\":" + bossId +
                   ",\"heroes\":[" + string.Join(",", heroIds) + "]" +
                   ",\"preset\":" + presetId + "}";
        }


        // =====================================================
        // API: /list-static-offer-catalog
        //
        // Dumps OffersWrapper.Static — the full catalog of
        // ClientStaticOffer entries (~63 typical), including champion-
        // collection offers that the user has never interacted with
        // (so /list-static-offers won't show them).
        //
        // Used to find the offer_id for /buy-static-offer when the
        // in-game client's "Buy" button NREs.
        // =====================================================
        private string ListStaticOfferCatalog()
        {
            object uw = GetUserWrapper();
            if (uw == null) return "{\"error\":\"not logged in\"}";
            object offersWrapper = Prop(uw, "Offers");
            if (offersWrapper == null) return "{\"error\":\"Offers wrapper null\"}";
            object catalog = Prop(offersWrapper, "Static");
            if (catalog == null) return "{\"error\":\"Static catalog null\"}";

            var sb = new StringBuilder();
            sb.Append("{\"offers\":[");
            int n = 0;
            foreach (var offer in ListItems(catalog))
            {
                if (offer == null) continue;
                int oid = TryInt(Prop(offer, "OfferId"));
                string title = SafeStr(Prop(offer, "Title"));
                string desc = SafeStr(Prop(offer, "Description"));
                if (n > 0) sb.Append(",");
                sb.Append("{\"offer_id\":").Append(oid);
                sb.Append(",\"title\":\"").Append(Esc(title ?? "")).Append("\"");
                sb.Append(",\"description\":\"").Append(Esc(desc ?? "")).Append("\"");
                // Try to extract price (Price is a Resources object)
                object price = Prop(offer, "Price");
                if (price != null)
                {
                    object isE = Prop(price, "IsEmpty");
                    bool isEmpty = isE is bool be && be;
                    sb.Append(",\"price_empty\":").Append(isEmpty ? "true" : "false");
                    // Try to read Gems / Silver fields off Resources
                    object gems = null, silver = null;
                    try { gems = Prop(price, "Gems"); } catch { }
                    try { silver = Prop(price, "Silver"); } catch { }
                    if (gems != null) sb.Append(",\"gems\":").Append(TryInt(gems));
                    if (silver != null) sb.Append(",\"silver\":").Append(TryInt(silver));
                }
                sb.Append("}");
                n++;
            }
            sb.Append("],\"count\":").Append(n).Append("}");
            return sb.ToString();
        }


        // =====================================================
        // API: /buy-static-offer?id=X
        //
        // Purchase a PAID static offer (Collection champion, gem pack,
        // etc.) by promo offer id. The in-game client builds
        // PurchaseStaticOfferCmd with managed `null` for its
        // Nullable<bool>/Nullable<int> params, which NREs in the cmd's
        // Edit pipeline ("StaticOffer.Buy 102 NullReferenceException").
        //
        // This endpoint builds the same cmd with empty
        // Il2CppSystem.Nullable<X> instances instead — the workaround
        // already used by /claim-free-shop-offers for free offers.
        //
        // Returns {ok, id} on enqueue; server is authoritative for
        // currency / availability checks (insufficient gems shows up
        // server-side, not here).
        // =====================================================
        private string BuyStaticOffer(string idStr)
        {
            if (!int.TryParse(idStr, out int offerId) || offerId <= 0)
                return "{\"error\":\"id required (positive int)\"}";

            object uw = GetUserWrapper();
            if (uw == null) return "{\"error\":\"not logged in\"}";

            var cmdType = FindType(
                "Client.Model.Gameplay.Bank.Payments.Commands.PurchaseStaticOfferCmd");
            if (cmdType == null)
                return "{\"error\":\"PurchaseStaticOfferCmd type not found\"}";

            // Ctor (from il2cppdumper):
            //   (int promoOfferId, string name = "", bool activate = false,
            //    Nullable<bool> isAutoBattle, Nullable<int> count)
            object cmd = null;
            string ctorErr = null;
            foreach (var c in cmdType.GetConstructors(
                BindingFlags.Public | BindingFlags.Instance))
            {
                var ps = c.GetParameters();
                if (ps.Length != 5) continue;
                try
                {
                    var nullableBoolT = ps[3].ParameterType;
                    var nullableIntT = ps[4].ParameterType;
                    object nullableBool = null;
                    object nullableInt = null;
                    try
                    {
                        var c0 = nullableBoolT.GetConstructor(System.Type.EmptyTypes);
                        nullableBool = c0 != null
                            ? c0.Invoke(null)
                            : System.Activator.CreateInstance(nullableBoolT);
                    }
                    catch { }
                    try
                    {
                        var c0 = nullableIntT.GetConstructor(System.Type.EmptyTypes);
                        nullableInt = c0 != null
                            ? c0.Invoke(null)
                            : System.Activator.CreateInstance(nullableIntT);
                    }
                    catch { }

                    cmd = c.Invoke(new object[] {
                        offerId,        // promoOfferId
                        "",             // name (analytics tag)
                        false,          // activate (must be false; true crashes)
                        nullableBool,   // isAutoBattle empty
                        nullableInt,    // count empty (server defaults to 1)
                    });
                    break;
                }
                catch (System.Reflection.TargetInvocationException tex)
                {
                    var inner = tex.InnerException ?? tex;
                    ctorErr = inner.GetType().Name + ": " + inner.Message;
                }
                catch (System.Exception cex)
                {
                    ctorErr = cex.GetType().Name + ": " + cex.Message;
                }
            }
            if (cmd == null)
                return "{\"error\":\"PurchaseStaticOfferCmd ctor failed: " +
                       Esc(ctorErr ?? "no matching ctor") + "\"}";

            // Hook server-side rejection so we can log it.
            try
            {
                var ifErrorM = cmd.GetType().GetMethod("IfError",
                    BindingFlags.Instance | BindingFlags.Public | BindingFlags.FlattenHierarchy,
                    null, new[] { typeof(System.Action) }, null);
                if (ifErrorM != null)
                {
                    int captured = offerId;
                    System.Action errCb = () =>
                        Logger.LogWarning("[BuyStaticOffer] server rejected id=" + captured);
                    ifErrorM.Invoke(cmd, new object[] { errCb });
                }
            }
            catch { }

            try
            {
                InvokeExecute(cmd);
                Logger.LogInfo("[BuyStaticOffer] enqueued id=" + offerId);
            }
            catch (System.Exception ex)
            {
                return "{\"error\":\"InvokeExecute failed: " +
                       Esc(ex.GetType().Name + ": " + ex.Message) + "\"}";
            }

            return "{\"ok\":true,\"id\":" + offerId +
                   ",\"note\":\"enqueued; server validates currency/availability\"}";
        }


        // =====================================================
        // API: /upgrade-artifact?id=X&to_level=N
        //
        // Fire UpgradeArtifactCmd against a SPECIFIC artifact in the
        // vault until it reaches `to_level` (max 16). Each cmd is +1
        // level (server-enforced; the DTO's UpgradeLevelLimit field is
        // unreliable). We loop and re-read the artifact's level after
        // each fire, bailing on insufficient silver / failure.
        //
        // Returns {ok, artifact_id, start_level, final_level, fired,
        //          silver_spent, errors[]}.
        // =====================================================
        private string UpgradeArtifactToLevel(string idStr, string toLevelStr)
        {
            if (!int.TryParse(idStr, out int targetId) || targetId <= 0)
                return "{\"error\":\"id required (positive int)\"}";
            int targetLevel = 16;
            if (!string.IsNullOrEmpty(toLevelStr) &&
                (!int.TryParse(toLevelStr, out targetLevel) ||
                 targetLevel < 1 || targetLevel > 16))
                return "{\"error\":\"to_level must be 1..16\"}";

            object uw = GetUserWrapper();
            if (uw == null) return "{\"error\":\"not logged in\"}";
            object equipment = Prop(uw, "Artifacts");
            if (equipment == null) return "{\"error\":\"no equipment wrapper\"}";

            var oneMethod = equipment.GetType().GetMethod("One");
            if (oneMethod == null) return "{\"error\":\"One method not found\"}";

            object art = null;
            try { art = oneMethod.Invoke(equipment, new object[] { targetId }); } catch { }
            if (art == null) return "{\"error\":\"artifact not found\"}";

            int startLevel = TryInt(Prop(art, "Level"));
            if (startLevel >= targetLevel)
                return "{\"ok\":true,\"artifact_id\":" + targetId +
                       ",\"start_level\":" + startLevel +
                       ",\"final_level\":" + startLevel +
                       ",\"fired\":0,\"note\":\"already at or above target\"}";

            // Read starting silver to compute spend.
            long startSilver = 0;
            try
            {
                var res = Prop(uw, "Resources");
                var silverProp = res?.GetType().GetMethod("Silver") ?? res?.GetType().GetMethod("get_Silver");
                if (silverProp != null) startSilver = Convert.ToInt64(silverProp.Invoke(res, null) ?? 0);
            }
            catch { }

            var dtoT = FindType("SharedModel.Meta.Artifacts.Dtos.UpgradeArtifactRequestDto");
            var cmdT = FindType("Client.Model.Gameplay.Artifacts.Commands.UpgradeArtifactCmd")
                       ?? FindTypeByLeafName("UpgradeArtifactCmd");
            if (dtoT == null || cmdT == null)
                return "{\"error\":\"upgrade types not found\"}";
            var ctor = cmdT.GetConstructor(new[] { dtoT });
            var dtoCtor = dtoT.GetConstructor(System.Type.EmptyTypes);
            if (ctor == null || dtoCtor == null)
                return "{\"error\":\"upgrade ctors not found\"}";
            var idP = dtoT.GetProperty("ArtifactId");
            var locP = dtoT.GetProperty("ArtifactLocation");
            if (idP == null || locP == null)
                return "{\"error\":\"DTO property setters missing\"}";

            var errors = new List<string>();
            int fired = 0;
            int currentLevel = startLevel;
            int maxIters = 20;  // safety cap: 16 + 4 retries
            while (currentLevel < targetLevel && fired < maxIters)
            {
                try
                {
                    object dto = dtoCtor.Invoke(null);
                    idP.SetValue(dto, targetId);
                    locP.SetValue(dto, 1);
                    object cmd = ctor.Invoke(new[] { dto });
                    InvokeExecute(cmd);
                    fired++;
                }
                catch (System.Reflection.TargetInvocationException tex)
                {
                    var inner = tex.InnerException ?? tex;
                    errors.Add(inner.GetType().Name + ": " + inner.Message);
                    break;
                }
                catch (Exception ex)
                {
                    errors.Add(ex.GetType().Name + ": " + ex.Message);
                    break;
                }
                // Wait for server commit then re-read level.
                System.Threading.Thread.Sleep(500);
                try { art = oneMethod.Invoke(equipment, new object[] { targetId }); } catch { }
                int newLevel = TryInt(Prop(art, "Level"));
                if (newLevel <= currentLevel)
                {
                    // No progress — likely insufficient silver or cmd rejected
                    errors.Add("no level progress after fire " + fired +
                               " (stuck at L" + currentLevel + ")");
                    break;
                }
                currentLevel = newLevel;
            }

            long endSilver = 0;
            try
            {
                var res = Prop(uw, "Resources");
                var silverProp = res?.GetType().GetMethod("Silver") ?? res?.GetType().GetMethod("get_Silver");
                if (silverProp != null) endSilver = Convert.ToInt64(silverProp.Invoke(res, null) ?? 0);
            }
            catch { }

            var sb = new StringBuilder();
            sb.Append("{\"ok\":").Append(currentLevel >= targetLevel ? "true" : "false");
            sb.Append(",\"artifact_id\":").Append(targetId);
            sb.Append(",\"start_level\":").Append(startLevel);
            sb.Append(",\"final_level\":").Append(currentLevel);
            sb.Append(",\"fired\":").Append(fired);
            sb.Append(",\"silver_spent\":").Append(startSilver - endSilver);
            if (errors.Count > 0)
            {
                sb.Append(",\"errors\":[");
                for (int i = 0; i < errors.Count; i++)
                {
                    if (i > 0) sb.Append(",");
                    sb.Append("\"").Append(Esc(errors[i])).Append("\"");
                }
                sb.Append("]");
            }
            sb.Append("}");
            return sb.ToString();
        }

        // =====================================================
        // API: /magic-shop — list current daily slots (id, type, price,
        //                   purchased flag) so consumers can pick one.
        //       /magic-shop-buy?id=N — fire BuyMagicShopItemCmd(id).
        //       /magic-shop-buy-cheapest — pick cheapest silver-only item
        //                                  the user can afford and buy it.
        //
        // Daily quest "Purchase Item in Magic Shop ×1" wants exactly one
        // BuyMagicShopItemCmd dispatch — buy-cheapest is the safe default
        // for the orchestrator; explicit id is for the dashboard.
        // =====================================================
        private string ListMagicShop()
        {
            try
            {
                object uw = GetUserWrapper();
                if (uw == null) return "{\"error\":\"not logged in\"}";
                object shopWrapper = Prop(uw, "MagicShop");
                if (shopWrapper == null) return "{\"error\":\"no MagicShop wrapper\"}";
                // MagicShopWrapper exposes the Items either directly or via
                // an inner data object. Probe both.
                object data = Prop(shopWrapper, "MagicShopData");
                object itemsCollection = Prop(data ?? shopWrapper, "Items");
                if (itemsCollection == null && data != null)
                    itemsCollection = Prop(data, "Items");
                if (itemsCollection == null)
                    return "{\"error\":\"no Items collection found\"}";

                var purchased = new HashSet<int>();
                object purchasedList = Prop(data ?? shopWrapper, "PurchasedItems");
                if (purchasedList != null)
                {
                    foreach (var p in ListItems(purchasedList))
                    {
                        int pid = TryInt(Prop(p, "Id"));
                        if (pid > 0) purchased.Add(pid);
                    }
                }

                var sb = new StringBuilder();
                sb.Append("{\"items\":[");
                int n = 0;
                foreach (var item in ListItems(itemsCollection))
                {
                    if (item == null) continue;
                    int id = TryInt(Prop(item, "Id"));
                    int typeId = TryInt(Prop(item, "TypeId"));
                    string typeName;
                    switch (typeId)
                    {
                        case 0: typeName = "Artifact"; break;
                        case 1: typeName = "ShardMystery"; break;
                        case 2: typeName = "ShardAncient"; break;
                        case 3: typeName = "HeroCommon"; break;
                        case 4: typeName = "HeroUncommon"; break;
                        default: typeName = "T" + typeId; break;
                    }
                    bool isRare = Prop(item, "IsRare") is bool rb && rb;
                    long silver = 0, gems = 0, energy = 0;
                    object price = Prop(item, "Price");
                    if (price != null)
                    {
                        try { silver = Convert.ToInt64(Prop(price, "Silver")); } catch { }
                        try { gems = Convert.ToInt64(Prop(price, "Gems")); } catch { }
                        try { energy = Convert.ToInt64(Prop(price, "Energy")); } catch { }
                    }
                    if (n > 0) sb.Append(",");
                    sb.Append("{\"id\":").Append(id);
                    sb.Append(",\"type\":\"").Append(typeName).Append("\"");
                    sb.Append(",\"is_rare\":").Append(isRare ? "true" : "false");
                    sb.Append(",\"price\":{\"silver\":").Append(silver);
                    sb.Append(",\"gems\":").Append(gems);
                    sb.Append(",\"energy\":").Append(energy).Append("}");
                    sb.Append(",\"purchased\":").Append(purchased.Contains(id) ? "true" : "false");
                    sb.Append("}");
                    n++;
                }
                sb.Append("],\"slot_count\":").Append(n).Append("}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.GetType().Name + ": " + ex.Message) + "\"}";
            }
        }

        // =====================================================
        // API: /magic-shop-buy-via-ui — buy cheapest silver-only Magic
        // Shop item by orchestrating the in-game UI click path.
        //
        // The direct BuyMagicShopItemCmd dispatch (via Activator OR raw
        // IL2CPP) silently no-ops server-side — the cmd is in the
        // UserPreEditCmdNoOut family whose validate/preedit flow depends
        // on UI state set up by the click chain. Replaying the click
        // chain works:
        //   1. OpenMarket (static on WebViewInGameTransition) — opens
        //      ShopAggregatorDialog with Market tab selected.
        //   2. OnBuyItem on Items/{slotIdx} MarketSlotContext — opens
        //      PrizeInfoOverlay with the item details + buy/cancel.
        //   3. OnClick on Buttons/1 of the overlay (the green Buy) —
        //      fires the actual cmd through the proper orchestration.
        //
        // Verified 2026-05-16: silver dropped 641K, MagicShop daily
        // quest 0/1 -> 1/1 ✓.
        // =====================================================
        private string BuyMagicShopViaUi() => BuyMagicShopViaUi(null);

        private string BuyMagicShopViaUi(string slotOverrideStr)
        {
            int slotOverride = -1;
            if (!string.IsNullOrEmpty(slotOverrideStr))
            {
                if (!int.TryParse(slotOverrideStr, out slotOverride) || slotOverride < 0)
                    return "{\"error\":\"slot must be non-negative int\"}";
            }
            try
            {
                // Step 1: ensure Market dialog is open. We can't poll for the
                // dialog to render in this same call because we're already
                // on the Unity main thread — Thread.Sleep here blocks Unity's
                // frame update, so any GameObject Raid would have created
                // can't appear until we return. The caller (daily_progress.py)
                // is responsible for sleeping between OpenMarket and the buy
                // by calling /magic-shop-open-dialog first, sleeping ~3s,
                // then /magic-shop-buy-via-ui.
                //
                // If the ShopAggregatorDialog isn't up yet, fire OpenMarket
                // and return early — caller should retry after a sleep.
                string shopDlgPath = "UIManager/Canvas (Ui Root)/Dialogs/"
                                   + "[DV] ShopAggregatorDialog";
                var shopGo = UnityEngine.GameObject.Find(shopDlgPath);
                if (shopGo == null)
                {
                    var transType = FindType(
                        "Client.ViewModel.Contextes.GlobalEvents.InGameTransition.WebViewInGameTransition");
                    if (transType == null)
                        return "{\"error\":\"WebViewInGameTransition type not found\"}";
                    var openMarketM = transType.GetMethod("OpenMarket",
                        BindingFlags.Public | BindingFlags.NonPublic |
                        BindingFlags.Static | BindingFlags.FlattenHierarchy);
                    if (openMarketM == null)
                        return "{\"error\":\"static OpenMarket method not found\"}";
                    openMarketM.Invoke(null, null);
                    return "{\"error\":\"market_opening\",\"hint\":\"OpenMarket fired; retry this endpoint after 3s sleep\"}";
                }

                // Step 2: find cheapest silver-only un-purchased item slot.
                object uw = GetUserWrapper();
                if (uw == null) return "{\"error\":\"not logged in\"}";
                object shopWrapper = Prop(uw, "MagicShop");
                object data = Prop(shopWrapper, "MagicShopData");
                object itemsCollection = Prop(data ?? shopWrapper, "Items");
                if (itemsCollection == null && data != null)
                    itemsCollection = Prop(data, "Items");
                if (itemsCollection == null)
                    return "{\"error\":\"no Items collection\"}";

                var purchased = new HashSet<int>();
                object purchasedList = Prop(data ?? shopWrapper, "PurchasedItems");
                if (purchasedList != null)
                {
                    foreach (var p in ListItems(purchasedList))
                    {
                        int pid = TryInt(Prop(p, "Id"));
                        if (pid > 0) purchased.Add(pid);
                    }
                }

                int slotIdx = -1;
                long bestSilver = long.MaxValue;
                int probe = 0;
                int bestTypeId = -1;
                int bestId = -1;
                bool bestIsRare = false;
                foreach (var item in ListItems(itemsCollection))
                {
                    if (item == null) { probe++; continue; }
                    int id = TryInt(Prop(item, "Id"));
                    object price = Prop(item, "Price");
                    long silver = 0, gems = 0, energy = 0;
                    try { silver = Convert.ToInt64(Prop(price, "Silver")); } catch { }
                    try { gems = Convert.ToInt64(Prop(price, "Gems")); } catch { }
                    try { energy = Convert.ToInt64(Prop(price, "Energy")); } catch { }
                    bool isAffordable = (gems == 0 && energy == 0 && !purchased.Contains(id));
                    // Direct-slot mode: caller picked a slot explicitly
                    // (e.g. for buying a specific Mystery Shard).
                    if (slotOverride >= 0)
                    {
                        if (probe == slotOverride)
                        {
                            if (!isAffordable)
                                return "{\"error\":\"slot " + probe + " not affordable (gems/energy/purchased)\"}";
                            slotIdx = probe;
                            bestSilver = silver;
                            bestId = id;
                            bestTypeId = TryInt(Prop(item, "TypeId"));
                            bestIsRare = Prop(item, "IsRare") is bool rb && rb;
                            probe++;
                            break;
                        }
                    }
                    else
                    {
                        // Cheapest-silver-only mode (default)
                        if (!isAffordable) { probe++; continue; }
                        if (silver < bestSilver)
                        {
                            bestSilver = silver;
                            slotIdx = probe;
                            bestId = id;
                            bestTypeId = TryInt(Prop(item, "TypeId"));
                            bestIsRare = Prop(item, "IsRare") is bool rb && rb;
                        }
                    }
                    probe++;
                }
                if (slotIdx < 0)
                    return slotOverride >= 0
                        ? "{\"error\":\"slot " + slotOverride + " not found in shop\"}"
                        : "{\"error\":\"no affordable silver-only item in shop\"}";

                string typeName;
                switch (bestTypeId)
                {
                    case 0: typeName = "Artifact"; break;
                    case 1: typeName = "ShardMystery"; break;
                    case 2: typeName = "ShardAncient"; break;
                    case 3: typeName = "HeroCommon"; break;
                    case 4: typeName = "HeroUncommon"; break;
                    default: typeName = "T" + bestTypeId; break;
                }

                // Step 3: invoke OnBuyItem on the slot's MarketSlotContext.
                string slotPath = "UIManager/Canvas (Ui Root)/Dialogs/"
                                + "[DV] ShopAggregatorDialog/Workspace/Content/"
                                + "TabsContent/Market_h/InnerContext/"
                                + "Scroll View/Viewport/Items/" + slotIdx;
                var slotGo = UnityEngine.GameObject.Find(slotPath);
                if (slotGo == null)
                    return "{\"error\":\"slot " + slotIdx + " GameObject not found — "
                           + "OpenMarket may have failed; try /invoke-static "
                           + "WebViewInGameTransition.OpenMarket manually first\"}";

                // Use the existing /context-call resolver to invoke OnBuyItem.
                // We have the path; piggyback on CallOnViewContext.
                var openResult = CallOnViewContext(slotPath, "OnBuyItem", null);
                if (openResult.Contains("error"))
                    return "{\"error\":\"OnBuyItem failed: " + Esc(openResult) + "\"}";

                // Step 4: click Buy button on PrizeInfoOverlay. Can't poll
                // here (main-thread block) — check if it's up; if not, return
                // an "overlay_opening" sentinel and let caller retry.
                string buyBtnPath = "UIManager/Canvas (Ui Root)/OverlayDialogs/"
                                  + "[OV] PrizeInfoOverlay/BoxContainer/Box/"
                                  + "Content/Buttons/1";
                var buyBtnGo = UnityEngine.GameObject.Find(buyBtnPath);
                if (buyBtnGo == null)
                    return "{\"error\":\"overlay_opening\",\"hint\":\"OnBuyItem fired on slot "
                           + slotIdx + "; retry after 3s sleep\",\"slot\":" + slotIdx + "}";

                var confirmResult = CallOnViewContext(buyBtnPath, "OnClick", null);
                if (confirmResult.Contains("error"))
                    return "{\"error\":\"buy-confirm failed: " + Esc(confirmResult) + "\"}";

                Logger.LogInfo("[MagicShopUI] purchased slot=" + slotIdx
                               + " id=" + bestId
                               + " type=" + typeName
                               + " rare=" + bestIsRare
                               + " silver=" + bestSilver);
                return "{\"ok\":true"
                       + ",\"slot\":" + slotIdx
                       + ",\"item_id\":" + bestId
                       + ",\"type\":\"" + typeName + "\""
                       + ",\"is_rare\":" + (bestIsRare ? "true" : "false")
                       + ",\"silver_cost\":" + bestSilver + "}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.GetType().Name + ": " + ex.Message) + "\"}";
            }
        }

        private string BuyMagicShopItem(string idStr, bool cheapestSilverOnly)
        {
            try
            {
                int targetId = 0;
                if (cheapestSilverOnly)
                {
                    // Walk vault, pick cheapest non-purchased silver-only item.
                    object uw = GetUserWrapper();
                    if (uw == null) return "{\"error\":\"not logged in\"}";
                    object shopWrapper = Prop(uw, "MagicShop");
                    object data = Prop(shopWrapper, "MagicShopData");
                    object itemsCollection = Prop(data ?? shopWrapper, "Items");
                    if (itemsCollection == null && data != null)
                        itemsCollection = Prop(data, "Items");
                    if (itemsCollection == null)
                        return "{\"error\":\"no Items collection\"}";

                    var purchased = new HashSet<int>();
                    object purchasedList = Prop(data ?? shopWrapper, "PurchasedItems");
                    if (purchasedList != null)
                    {
                        foreach (var p in ListItems(purchasedList))
                        {
                            int pid = TryInt(Prop(p, "Id"));
                            if (pid > 0) purchased.Add(pid);
                        }
                    }

                    long bestSilver = long.MaxValue;
                    foreach (var item in ListItems(itemsCollection))
                    {
                        if (item == null) continue;
                        int id = TryInt(Prop(item, "Id"));
                        if (id <= 0 || purchased.Contains(id)) continue;
                        object price = Prop(item, "Price");
                        long silver = 0, gems = 0, energy = 0;
                        try { silver = Convert.ToInt64(Prop(price, "Silver")); } catch { }
                        try { gems = Convert.ToInt64(Prop(price, "Gems")); } catch { }
                        try { energy = Convert.ToInt64(Prop(price, "Energy")); } catch { }
                        // Silver-only filter: skip gem/energy purchases by default.
                        if (gems > 0 || energy > 0) continue;
                        if (silver < bestSilver)
                        {
                            bestSilver = silver;
                            targetId = id;
                        }
                    }
                    if (targetId == 0)
                        return "{\"error\":\"no affordable silver-only item in shop\"}";
                }
                else
                {
                    if (string.IsNullOrEmpty(idStr) || !int.TryParse(idStr, out targetId))
                        return "{\"error\":\"id required\"}";
                }

                // IL2CPP-direct path (Activator left pooledPtr=0). Wire IfError
                // on the keep-alive wrapper so server rejections surface.
                string err = FireIntCmd(
                    "Client.Model.Gameplay.MagicShop.Commands.BuyMagicShopItemCmd",
                    targetId, out object cmdMgd);
                if (err != null)
                {
                    GC.KeepAlive(cmdMgd);
                    return "{\"error\":\"" + Esc(err) + "\",\"id\":" + targetId + "}";
                }
                bool[] errored = { false };
                if (cmdMgd != null)
                {
                    try
                    {
                        var ifErrorM = cmdMgd.GetType().GetMethod("IfError",
                            BindingFlags.Instance | BindingFlags.Public | BindingFlags.FlattenHierarchy,
                            null, new[] { typeof(System.Action) }, null);
                        if (ifErrorM != null)
                        {
                            System.Action errCb = () =>
                            {
                                errored[0] = true;
                                Logger.LogWarning("[MagicShop] id=" + targetId + " server rejected");
                            };
                            ifErrorM.Invoke(cmdMgd, new object[] { errCb });
                        }
                    }
                    catch { }
                }
                Logger.LogInfo("[MagicShop] dispatched BuyMagicShopItemCmd id=" + targetId);
                System.Threading.Thread.Sleep(800);
                GC.KeepAlive(cmdMgd);
                if (errored[0])
                    return "{\"error\":\"server_rejected\",\"id\":" + targetId + "}";
                return "{\"ok\":true,\"id\":" + targetId + "}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.GetType().Name + ": " + ex.Message) + "\"}";
            }
        }

        // =====================================================
        // API: /level-up-hero?target=N&food=A,B,C
        //
        // Fires LevelUpHeroCmd(int heroId, int[] heroMaterialIds,
        //   BlackMarketItemId[] bmiMaterialIds, bool isFastFeeding,
        //   bool deactivateArtifacts) to sacrifice food heroes onto a
        // target hero, gaining XP/levels.
        //
        // Used for the cyclical daily-quest loop: Phase A's mystery
        // summons produce R2/R3 fodder; sacrifice those onto a target
        // to tick the "Increase Champion's Level in Tavern N times"
        // daily quest. Each level the target gains = +1 tick.
        //
        // Args:
        //   target — hero id to receive XP (will gain levels)
        //   food — comma-separated hero ids to sacrifice (consumed)
        // Auto-strips gear from food before sacrifice (deactivate=true)
        // and uses fast-feeding (no slot animation).
        // =====================================================
        private string LevelUpHero(string targetStr, string foodCsv)
        {
            if (string.IsNullOrEmpty(targetStr) || !int.TryParse(targetStr, out int targetId))
                return "{\"error\":\"target (int hero_id) required\"}";
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

            var cmdType = FindType("Client.Model.Gameplay.Heroes.Commands.LevelUpHeroCmd");
            if (cmdType == null)
                return "{\"error\":\"LevelUpHeroCmd type not found\"}";

            // IL2CPP-direct construction (Activator path leaves
            // pooledPtr=0 — same root cause as inbox/magic-shop). The
            // earlier attempt crashed Raid; this retry adds extensive
            // logging at each step so the crash point is identifiable
            // from BepInEx log. Key change: use byte[] for bool args
            // (IL2CPP bool marshalls as 1 byte, not 4).
            try
            {
                Logger.LogInfo("[LevelUpHero] STEP 1: find ctor + IL2CPP class");
                IntPtr cmdCls = GetIL2CppClassPtr(cmdType);
                if (cmdCls == IntPtr.Zero)
                    return "{\"error\":\"cmd IL2Cpp class ptr is zero\"}";

                IntPtr ctorM = FindIL2CPPMethod(cmdCls, ".ctor", 5);
                if (ctorM == IntPtr.Zero)
                    return "{\"error\":\".ctor(5 args) not found via raw IL2CPP\"}";
                IntPtr execM = FindIL2CppMethodOnHierarchy(cmdCls, "Execute", 0);
                if (execM == IntPtr.Zero)
                    return "{\"error\":\"Execute() not found\"}";

                Logger.LogInfo("[LevelUpHero] STEP 2: get bmiArrType from managed ctor");
                ConstructorInfo ctorR = null;
                foreach (var c in cmdType.GetConstructors(
                    BindingFlags.Public | BindingFlags.Instance))
                {
                    if (c.GetParameters().Length == 5) { ctorR = c; break; }
                }
                if (ctorR == null)
                    return "{\"error\":\"managed 5-arg ctor not found\"}";
                var bmiArrType = ctorR.GetParameters()[2].ParameterType;
                Logger.LogInfo("[LevelUpHero] STEP 2: bmiArrType=" + bmiArrType.FullName);

                Logger.LogInfo("[LevelUpHero] STEP 3: allocate cmd via il2cpp_object_new");
                IntPtr cmdPtr = il2cpp_object_new(cmdCls);
                if (cmdPtr == IntPtr.Zero)
                    return "{\"error\":\"il2cpp_object_new returned null\"}";
                Logger.LogInfo("[LevelUpHero] STEP 3: cmdPtr=0x" + cmdPtr.ToString("X"));

                Logger.LogInfo("[LevelUpHero] STEP 4: build foodArr Il2CppStructArray<int>");
                var foodArr = new Il2CppInterop.Runtime.InteropTypes.Arrays
                    .Il2CppStructArray<int>(foodIds.ToArray());
                IntPtr foodArrPtr = (IntPtr)foodArr.GetType()
                    .GetProperty("Pointer").GetValue(foodArr);
                Logger.LogInfo("[LevelUpHero] STEP 4: foodArrPtr=0x" + foodArrPtr.ToString("X")
                               + " (foodIds.Count=" + foodIds.Count + ")");
                if (foodArrPtr == IntPtr.Zero)
                    return "{\"error\":\"foodArr Pointer is zero\"}";

                Logger.LogInfo("[LevelUpHero] STEP 5: build empty BMI array");
                object bmiArr = Activator.CreateInstance(bmiArrType, new object[] { 0 });
                if (bmiArr == null)
                    return "{\"error\":\"bmiArr Activator returned null\"}";
                IntPtr bmiArrPtr = (IntPtr)bmiArr.GetType()
                    .GetProperty("Pointer").GetValue(bmiArr);
                Logger.LogInfo("[LevelUpHero] STEP 5: bmiArrPtr=0x" + bmiArrPtr.ToString("X"));
                if (bmiArrPtr == IntPtr.Zero)
                    return "{\"error\":\"bmiArr Pointer is zero\"}";

                Logger.LogInfo("[LevelUpHero] STEP 6: pin args (bool as byte[])");
                // Args:
                //   [0] int heroId (value, 4 bytes)
                //   [1] int[] heroMaterialIds (ref) — pointer-to-pointer
                //   [2] BlackMarketItemId[] bmiMaterialIds (ref) — pointer-to-pointer
                //   [3] bool isFastFeeding (value, 1 byte in IL2CPP)
                //   [4] bool deactivateArtifacts (value, 1 byte in IL2CPP)
                int[] arg0_heroId  = { targetId };
                IntPtr[] arg1_food = { foodArrPtr };
                IntPtr[] arg2_bmi  = { bmiArrPtr };
                byte[] arg3_fast   = { 1 };
                byte[] arg4_deactv = { 1 };

                var pinH0 = System.Runtime.InteropServices.GCHandle.Alloc(
                    arg0_heroId, System.Runtime.InteropServices.GCHandleType.Pinned);
                var pinH1 = System.Runtime.InteropServices.GCHandle.Alloc(
                    arg1_food,   System.Runtime.InteropServices.GCHandleType.Pinned);
                var pinH2 = System.Runtime.InteropServices.GCHandle.Alloc(
                    arg2_bmi,    System.Runtime.InteropServices.GCHandleType.Pinned);
                var pinH3 = System.Runtime.InteropServices.GCHandle.Alloc(
                    arg3_fast,   System.Runtime.InteropServices.GCHandleType.Pinned);
                var pinH4 = System.Runtime.InteropServices.GCHandle.Alloc(
                    arg4_deactv, System.Runtime.InteropServices.GCHandleType.Pinned);

                IntPtr[] argList = {
                    pinH0.AddrOfPinnedObject(),
                    pinH1.AddrOfPinnedObject(),
                    pinH2.AddrOfPinnedObject(),
                    pinH3.AddrOfPinnedObject(),
                    pinH4.AddrOfPinnedObject(),
                };
                var pinList = System.Runtime.InteropServices.GCHandle.Alloc(
                    argList, System.Runtime.InteropServices.GCHandleType.Pinned);
                Logger.LogInfo("[LevelUpHero] STEP 6: all args pinned, calling ctor");

                IntPtr exc = IntPtr.Zero;
                try
                {
                    il2cpp_runtime_invoke(ctorM, cmdPtr,
                        pinList.AddrOfPinnedObject(), ref exc);
                }
                catch (Exception cex)
                {
                    Logger.LogError("[LevelUpHero] STEP 7 ctor C# exception: "
                                    + cex.GetType().Name + ": " + cex.Message);
                    pinList.Free();
                    pinH4.Free(); pinH3.Free(); pinH2.Free(); pinH1.Free(); pinH0.Free();
                    return "{\"error\":\"ctor C# throw: " + Esc(cex.Message) + "\"}";
                }
                finally
                {
                    pinList.Free();
                    pinH4.Free(); pinH3.Free(); pinH2.Free(); pinH1.Free(); pinH0.Free();
                }
                Logger.LogInfo("[LevelUpHero] STEP 7: ctor returned, exc=0x" + exc.ToString("X"));
                if (exc != IntPtr.Zero)
                    return "{\"error\":\"ctor threw IL2Cpp exception\"}";

                Logger.LogInfo("[LevelUpHero] STEP 8: wrap managed");
                object cmdMgd = null;
                try { cmdMgd = Activator.CreateInstance(cmdType, cmdPtr); }
                catch (Exception wex)
                {
                    Logger.LogError("[LevelUpHero] managed wrap failed: " + wex.Message);
                    return "{\"error\":\"managed wrap failed: " + Esc(wex.Message) + "\"}";
                }
                if (cmdMgd == null)
                    return "{\"error\":\"managed wrap returned null\"}";

                // Optional: wire IfError so we see server rejections clearly
                bool[] errored = { false };
                string[] errMsg = { null };
                try
                {
                    var ifErrorM = cmdMgd.GetType().GetMethod("IfError",
                        BindingFlags.Instance | BindingFlags.Public |
                        BindingFlags.FlattenHierarchy,
                        null, new[] { typeof(Action) }, null);
                    if (ifErrorM != null)
                    {
                        Action errCb = () =>
                        {
                            errored[0] = true;
                            errMsg[0] = "server_rejected";
                            Logger.LogWarning("[LevelUpHero] SERVER REJECTED target="
                                              + targetId);
                        };
                        ifErrorM.Invoke(cmdMgd, new object[] { errCb });
                        Logger.LogInfo("[LevelUpHero] STEP 8b: IfError wired");
                    }
                }
                catch (Exception ifex)
                {
                    Logger.LogWarning("[LevelUpHero] IfError wire failed: " + ifex.Message);
                }

                // STEP 9 INTENTIONALLY SKIPPED — Execute crashes Raid
                // hard whether called via managed wrapper (InvokeExecute)
                // or raw IL2CPP. The ctor runs cleanly (STEP 7 exc=0x0)
                // and the managed wrapper attaches (STEP 8). But the cmd's
                // Validate/Edit machinery inside Execute hits null state
                // somewhere our il2cpp_object_new + ctor invoke didn't
                // initialize, causing a process-killing AV.
                //
                // Verified 2026-05-17: every Execute attempt crashed Raid
                // hard. Each test costs a full restart + session loss.
                //
                // Future fix path: either (a) replay the Tavern UI click
                // chain through HeroesDevelopmentDialogContext methods
                // (SelectHero/SetMaterialsSelection/click LevelUpButton),
                // OR (b) trace exactly which field Execute dereferences
                // via Harmony pre-hook on the IL2CPP method.
                Logger.LogWarning("[LevelUpHero] STEP 9 INTENTIONALLY SKIPPED "
                                  + "(Execute crashes Raid; ctor works but Execute is unsafe)");
                return "{\"error\":\"execute_unsafe\",\"hint\":\"cmd ctor succeeded "
                       + "(IL2CPP instance valid) but Execute crashes Raid — see "
                       + "comments in LevelUpHero for details\",\"target\":"
                       + targetId + "}";

                System.Threading.Thread.Sleep(1500);
                GC.KeepAlive(cmdMgd);
                GC.KeepAlive(foodArr);
                GC.KeepAlive(bmiArr);

                Logger.LogInfo("[LevelUpHero] STEP 10: SUCCESS — cmd dispatched");
                if (errored[0])
                    return "{\"error\":\"server_rejected\",\"target\":" + targetId + "}";
                return "{\"ok\":true,\"target\":" + targetId
                       + ",\"food_count\":" + foodIds.Count + "}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.GetType().Name + ": " + ex.Message) + "\"}";
            }
        }

        // =====================================================
        // API: /arena-set-autobattle?on=1
        //
        // Flips the auto-battle checkbox on the active Arena heroes-
        // selection dialog. Without this, Classic Arena battles started
        // via cmd dispatch debit the token but never auto-resolve —
        // they queue on the server waiting for client to play out the
        // fight. Setting auto-battle BEFORE StartBattle makes the
        // server resolve immediately.
        //
        // The checkbox lives on HeroesSelectionArenaDialogContext as
        // private field `_autoBattleCheckbox` (type AutoBattleCheckboxContext).
        // Managed reflection can't see IL2CPP-defined fields on proxy
        // types, so we use raw IL2CPP (same pattern as the MessageBox
        // _buttons fix): find the dialog's view → get its Context →
        // walk class fields for _autoBattleCheckbox → read pointer at
        // offset → find Set(bool) method on the checkbox class →
        // invoke with the bool arg.
        // =====================================================
        private string ArenaSetAutoBattle(string onStr)
        {
            bool turnOn = true;
            if (!string.IsNullOrEmpty(onStr))
            {
                turnOn = (onStr == "1" || onStr.ToLowerInvariant() == "true");
            }
            try
            {
                string dialogPath = "UIManager/Canvas (Ui Root)/Dialogs/"
                                  + "[DV] ArenaHeroesSelectionDialog";
                var dlgGo = UnityEngine.GameObject.Find(dialogPath);
                if (dlgGo == null)
                    return "{\"error\":\"ArenaHeroesSelectionDialog not open — "
                           + "open arena + click an opponent first\"}";

                // Find dialog's Context (HeroesSelectionArenaDialogContext) via
                // raw IL2CPP get_Context walk.
                IntPtr dlgCtxPtr = IntPtr.Zero;
                IntPtr dlgCtxClass = IntPtr.Zero;
                foreach (var mono in dlgGo.GetComponentsInChildren<MonoBehaviour>(true))
                {
                    if (mono == null) continue;
                    IntPtr monoPtr = mono.Pointer;
                    if (monoPtr == IntPtr.Zero) continue;
                    IntPtr monoClass = il2cpp_object_get_class(monoPtr);
                    if (monoClass == IntPtr.Zero) continue;

                    IntPtr getCtxM = IntPtr.Zero;
                    IntPtr scan = monoClass;
                    while (scan != IntPtr.Zero && getCtxM == IntPtr.Zero)
                    {
                        IntPtr mIter = IntPtr.Zero; IntPtr m;
                        while ((m = il2cpp_class_get_methods(scan, ref mIter)) != IntPtr.Zero)
                        {
                            string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                            if (mn == "get_Context" && il2cpp_method_get_param_count(m) == 0)
                            {
                                getCtxM = m;
                                break;
                            }
                        }
                        if (getCtxM == IntPtr.Zero)
                            scan = il2cpp_class_get_parent(scan);
                    }
                    if (getCtxM == IntPtr.Zero) continue;

                    IntPtr exc = IntPtr.Zero;
                    IntPtr ctxObj = il2cpp_runtime_invoke(getCtxM, monoPtr, IntPtr.Zero, ref exc);
                    if (exc != IntPtr.Zero || ctxObj == IntPtr.Zero) continue;

                    IntPtr ctxClass = il2cpp_object_get_class(ctxObj);
                    if (ctxClass == IntPtr.Zero) continue;
                    string ctxName = Marshal.PtrToStringAnsi(il2cpp_class_get_name(ctxClass));
                    if (ctxName == "HeroesSelectionArenaDialogContext")
                    {
                        dlgCtxPtr = ctxObj;
                        dlgCtxClass = ctxClass;
                        break;
                    }
                }
                if (dlgCtxPtr == IntPtr.Zero)
                    return "{\"error\":\"HeroesSelectionArenaDialogContext not found\"}";

                // Walk class fields for _autoBattleCheckbox.
                uint cbOffset = uint.MaxValue;
                IntPtr scanCls = dlgCtxClass;
                while (scanCls != IntPtr.Zero && cbOffset == uint.MaxValue)
                {
                    IntPtr fIter = IntPtr.Zero; IntPtr f;
                    while ((f = il2cpp_class_get_fields(scanCls, ref fIter)) != IntPtr.Zero)
                    {
                        string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(f));
                        if (fn == "_autoBattleCheckbox")
                        {
                            cbOffset = il2cpp_field_get_offset(f);
                            break;
                        }
                    }
                    if (cbOffset == uint.MaxValue)
                        scanCls = il2cpp_class_get_parent(scanCls);
                }
                if (cbOffset == uint.MaxValue)
                    return "{\"error\":\"_autoBattleCheckbox field not found\"}";

                IntPtr cbPtr = Marshal.ReadIntPtr(dlgCtxPtr + (int)cbOffset);
                if (cbPtr == IntPtr.Zero)
                    return "{\"error\":\"_autoBattleCheckbox is null\"}";

                // Find Set(bool) method on AutoBattleCheckboxContext.
                IntPtr cbClass = il2cpp_object_get_class(cbPtr);
                IntPtr setM = FindIL2CppMethodOnHierarchy(cbClass, "Set", 1);
                if (setM == IntPtr.Zero)
                    return "{\"error\":\"AutoBattleCheckboxContext.Set(bool) not found\"}";

                // Invoke Set(bool). IL2CPP marshals bool as 4-byte int.
                int[] argBuf = { turnOn ? 1 : 0 };
                var pinArg = System.Runtime.InteropServices.GCHandle.Alloc(
                    argBuf, System.Runtime.InteropServices.GCHandleType.Pinned);
                IntPtr[] argList = { pinArg.AddrOfPinnedObject() };
                var pinList = System.Runtime.InteropServices.GCHandle.Alloc(
                    argList, System.Runtime.InteropServices.GCHandleType.Pinned);
                IntPtr exc2 = IntPtr.Zero;
                try
                {
                    il2cpp_runtime_invoke(setM, cbPtr, pinList.AddrOfPinnedObject(), ref exc2);
                }
                finally { pinList.Free(); pinArg.Free(); }
                if (exc2 != IntPtr.Zero)
                    return "{\"error\":\"Set threw IL2Cpp exception\"}";

                // Read back AutoBattleSelected to confirm.
                bool nowSelected = false;
                IntPtr getM = FindIL2CppMethodOnHierarchy(cbClass, "get_AutoBattleSelected", 0);
                if (getM != IntPtr.Zero)
                {
                    IntPtr excG = IntPtr.Zero;
                    IntPtr result = il2cpp_runtime_invoke(getM, cbPtr, IntPtr.Zero, ref excG);
                    if (result != IntPtr.Zero)
                    {
                        // Boxed bool: read at offset 0x10
                        byte v = Marshal.ReadByte(result + 0x10);
                        nowSelected = v != 0;
                    }
                }

                Logger.LogInfo("[ArenaAutoBattle] Set(" + turnOn + ") -> AutoBattleSelected="
                               + nowSelected);
                return "{\"ok\":true,\"requested\":" + (turnOn ? "true" : "false")
                       + ",\"now_selected\":" + (nowSelected ? "true" : "false") + "}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.GetType().Name + ": " + ex.Message) + "\"}";
            }
        }

        // Find a managed type by its leaf class name, scanning all loaded
        // assemblies. Used as a fallback when a fully-qualified namespace
        // is wrong but the class name is unique enough to match.
        private System.Type FindTypeByLeafName(string leafName)
        {
            foreach (var asm in System.AppDomain.CurrentDomain.GetAssemblies())
            {
                System.Type[] ts = null;
                try { ts = asm.GetTypes(); } catch { continue; }
                foreach (var t in ts)
                {
                    if (t == null) continue;
                    if (t.Name == leafName) return t;
                }
            }
            return null;
        }

        // Read a StringProperty field from an IL2CPP object, returning the
        // current Value or null. StringProperty is a wrapper class with a
        // _value (or similar) field holding the actual System.String. We
        // walk the class for the field, read the pointer, then call its
        // get_Value method (StringProperty exposes Value publicly).
        private string ReadStringPropertyField(IntPtr objPtr, IntPtr objClass,
                                                string fieldName)
        {
            try
            {
                // Find the StringProperty field offset.
                uint fieldOffset = uint.MaxValue;
                IntPtr scan = objClass;
                while (scan != IntPtr.Zero && fieldOffset == uint.MaxValue)
                {
                    IntPtr fIter = IntPtr.Zero; IntPtr f;
                    while ((f = il2cpp_class_get_fields(scan, ref fIter)) != IntPtr.Zero)
                    {
                        string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(f));
                        if (fn == fieldName)
                        {
                            fieldOffset = il2cpp_field_get_offset(f);
                            break;
                        }
                    }
                    if (fieldOffset == uint.MaxValue)
                        scan = il2cpp_class_get_parent(scan);
                }
                if (fieldOffset == uint.MaxValue) return null;

                IntPtr propPtr = Marshal.ReadIntPtr(objPtr + (int)fieldOffset);
                if (propPtr == IntPtr.Zero) return null;

                // Call get_Value() on the StringProperty.
                IntPtr propClass = il2cpp_object_get_class(propPtr);
                IntPtr getValueM = FindIL2CppMethodOnHierarchy(propClass, "get_Value", 0);
                if (getValueM == IntPtr.Zero) return null;
                IntPtr exc = IntPtr.Zero;
                IntPtr strPtr = il2cpp_runtime_invoke(getValueM, propPtr, IntPtr.Zero, ref exc);
                if (exc != IntPtr.Zero || strPtr == IntPtr.Zero) return null;
                // IL2CPP string layout: header(0x10) + length(int) + chars(UTF-16).
                int len = Marshal.ReadInt32(strPtr + 0x10);
                if (len <= 0 || len > 4096) return "";
                return Marshal.PtrToStringUni(strPtr + 0x14, len);
            }
            catch { return null; }
        }

        // =====================================================
        // API: /messagebox-click?index=N — invoke OnClick on the Nth button
        // of the active MessageBox dialog.
        //
        // The button contexts live INSIDE MessageBoxContext._buttons
        // (ContextList<MessageBoxButtonContext>), NOT on MonoBehaviours.
        // Raid's MVVM keeps view + context layers separate. Managed
        // reflection can't see IL2CPP-defined fields on Il2CppInterop
        // proxy types — so we use raw IL2CPP plumbing throughout:
        //   1. Find MessageBox GameObject + its bound MessageBoxContext via
        //      raw `il2cpp_class_get_methods` walk for get_Context (same
        //      pattern as SearchContextAndInvoke in Navigate.cs).
        //   2. Walk MessageBoxContext's class fields for `_buttons`,
        //      get its offset, read the ContextList pointer at that offset.
        //   3. Call the ContextList's `get_Count()` and `get_Item(int)`
        //      via raw `il2cpp_runtime_invoke` to get the Nth button context.
        //   4. Find OnClick on the button context's class, invoke it
        //      raw — fires the bound action callback on MessageBoxContext.
        //
        // OnClick (vs Close) PROCEEDS with the underlying action
        // (e.g. arena fight, defense-team-warning continue). Close cancels.
        // =====================================================
        private string MessageBoxClick(string idxStr)
        {
            int idx = 1;  // default 1 = typically the green "Confirm" button
            if (!string.IsNullOrEmpty(idxStr) && !int.TryParse(idxStr, out idx))
                return "{\"error\":\"index must be int\"}";

            try
            {
                string mbPath = "UIManager/Canvas (Ui Root)/MessageBoxes/MessageBox";
                var mbGo = UnityEngine.GameObject.Find(mbPath);
                if (mbGo == null)
                    return "{\"error\":\"no active MessageBox\"}";

                // Step 1: Find MessageBoxContext via raw IL2CPP get_Context walk.
                IntPtr mbCtxPtr = IntPtr.Zero;
                IntPtr mbCtxClass = IntPtr.Zero;
                foreach (var mono in mbGo.GetComponentsInChildren<MonoBehaviour>(true))
                {
                    if (mono == null) continue;
                    IntPtr monoPtr = mono.Pointer;
                    if (monoPtr == IntPtr.Zero) continue;
                    IntPtr monoClass = il2cpp_object_get_class(monoPtr);
                    if (monoClass == IntPtr.Zero) continue;

                    // Walk class hierarchy looking for get_Context (0 args).
                    IntPtr getCtxM = IntPtr.Zero;
                    IntPtr scan = monoClass;
                    while (scan != IntPtr.Zero && getCtxM == IntPtr.Zero)
                    {
                        IntPtr mIter = IntPtr.Zero; IntPtr m;
                        while ((m = il2cpp_class_get_methods(scan, ref mIter)) != IntPtr.Zero)
                        {
                            string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                            if (mn == "get_Context" && il2cpp_method_get_param_count(m) == 0)
                            {
                                getCtxM = m;
                                break;
                            }
                        }
                        if (getCtxM == IntPtr.Zero)
                            scan = il2cpp_class_get_parent(scan);
                    }
                    if (getCtxM == IntPtr.Zero) continue;

                    IntPtr exc = IntPtr.Zero;
                    IntPtr ctxObj = il2cpp_runtime_invoke(getCtxM, monoPtr, IntPtr.Zero, ref exc);
                    if (exc != IntPtr.Zero || ctxObj == IntPtr.Zero) continue;

                    IntPtr ctxClass = il2cpp_object_get_class(ctxObj);
                    if (ctxClass == IntPtr.Zero) continue;
                    string ctxName = Marshal.PtrToStringAnsi(il2cpp_class_get_name(ctxClass));
                    if (ctxName == "MessageBoxContext")
                    {
                        mbCtxPtr = ctxObj;
                        mbCtxClass = ctxClass;
                        break;
                    }
                }
                if (mbCtxPtr == IntPtr.Zero)
                    return "{\"error\":\"MessageBoxContext not found via raw IL2CPP\"}";

                // Diagnostic: read all 4 text fields. _errorData carries
                // the server-side error code (e.g. specific cmd-rejection
                // reason) which is much more useful than the generic
                // "experiencing issues" main message.
                string mainMsg = ReadStringPropertyField(mbCtxPtr, mbCtxClass, "_mainMessage");
                string titleMsg = ReadStringPropertyField(mbCtxPtr, mbCtxClass, "_titleText");
                string addMsg = ReadStringPropertyField(mbCtxPtr, mbCtxClass, "_additionalMessage");
                string errData = ReadStringPropertyField(mbCtxPtr, mbCtxClass, "_errorData");
                Logger.LogInfo("[MessageBoxClick] title=\"" + (titleMsg ?? "?")
                               + "\" main=\"" + (mainMsg ?? "?")
                               + "\" addl=\"" + (addMsg ?? "?")
                               + "\" errData=\"" + (errData ?? "?") + "\"");

                // Step 2: Find _buttons field offset on MessageBoxContext class.
                uint buttonsOffset = uint.MaxValue;
                IntPtr scanCls = mbCtxClass;
                while (scanCls != IntPtr.Zero && buttonsOffset == uint.MaxValue)
                {
                    IntPtr fIter = IntPtr.Zero; IntPtr f;
                    while ((f = il2cpp_class_get_fields(scanCls, ref fIter)) != IntPtr.Zero)
                    {
                        string fn = Marshal.PtrToStringAnsi(il2cpp_field_get_name(f));
                        if (fn == "_buttons")
                        {
                            buttonsOffset = il2cpp_field_get_offset(f);
                            break;
                        }
                    }
                    if (buttonsOffset == uint.MaxValue)
                        scanCls = il2cpp_class_get_parent(scanCls);
                }
                if (buttonsOffset == uint.MaxValue)
                    return "{\"error\":\"_buttons field not found on MessageBoxContext\"}";

                IntPtr buttonsList = Marshal.ReadIntPtr(mbCtxPtr + (int)buttonsOffset);
                if (buttonsList == IntPtr.Zero)
                    return "{\"error\":\"_buttons null at offset 0x" + buttonsOffset.ToString("X") + "\"}";

                // Step 3: Read Count + Item(int) on the ContextList.
                IntPtr listClass = il2cpp_object_get_class(buttonsList);
                if (listClass == IntPtr.Zero)
                    return "{\"error\":\"buttons list class null\"}";

                IntPtr countM = FindIL2CppMethodOnHierarchy(listClass, "get_Count", 0);
                if (countM == IntPtr.Zero)
                    return "{\"error\":\"get_Count not found on ContextList\"}";
                IntPtr itemM = FindIL2CppMethodOnHierarchy(listClass, "get_Item", 1);
                if (itemM == IntPtr.Zero)
                    return "{\"error\":\"get_Item(int) not found on ContextList\"}";

                IntPtr eC = IntPtr.Zero;
                IntPtr countResult = il2cpp_runtime_invoke(countM, buttonsList, IntPtr.Zero, ref eC);
                if (eC != IntPtr.Zero || countResult == IntPtr.Zero)
                    return "{\"error\":\"get_Count threw\"}";
                // Boxed int: read at offset 0x10 (Il2Cpp boxing layout).
                int count = Marshal.ReadInt32(countResult + 0x10);

                if (count == 0)
                    return "{\"error\":\"_buttons list empty\"}";
                if (idx < 0 || idx >= count)
                    return "{\"error\":\"index " + idx + " out of range (have "
                           + count + " buttons)\"}";

                // Call get_Item(int idx) — pin int arg, build args array.
                int[] argBuf = { idx };
                var pinArg = System.Runtime.InteropServices.GCHandle.Alloc(
                    argBuf, System.Runtime.InteropServices.GCHandleType.Pinned);
                IntPtr[] argList = { pinArg.AddrOfPinnedObject() };
                var pinList = System.Runtime.InteropServices.GCHandle.Alloc(
                    argList, System.Runtime.InteropServices.GCHandleType.Pinned);
                IntPtr btnCtx = IntPtr.Zero;
                IntPtr eI = IntPtr.Zero;
                try
                {
                    btnCtx = il2cpp_runtime_invoke(itemM, buttonsList,
                                                   pinList.AddrOfPinnedObject(), ref eI);
                }
                finally { pinList.Free(); pinArg.Free(); }
                if (eI != IntPtr.Zero || btnCtx == IntPtr.Zero)
                    return "{\"error\":\"get_Item(" + idx + ") threw or returned null\"}";

                // Step 4: Find + invoke OnClick on the button context.
                IntPtr btnClass = il2cpp_object_get_class(btnCtx);
                IntPtr onClickM = FindIL2CppMethodOnHierarchy(btnClass, "OnClick", 0);
                if (onClickM == IntPtr.Zero)
                    return "{\"error\":\"OnClick not found on button context\"}";

                IntPtr eK = IntPtr.Zero;
                il2cpp_runtime_invoke(onClickM, btnCtx, IntPtr.Zero, ref eK);
                if (eK != IntPtr.Zero)
                    return "{\"error\":\"OnClick threw IL2Cpp exception\"}";

                string btnClassName = Marshal.PtrToStringAnsi(il2cpp_class_get_name(btnClass));
                Logger.LogInfo("[MessageBoxClick] invoked OnClick on button " + idx
                               + " (" + btnClassName + ") of " + count + " total");
                return "{\"ok\":true,\"index\":" + idx + ",\"button_count\":" + count
                       + ",\"context\":\"" + Esc(btnClassName) + "\"}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.GetType().Name + ": " + ex.Message) + "\"}";
            }
        }

        // =====================================================
        // Tavern helpers — drive the in-game level-up flow through
        // the game's own UI click chain instead of constructing
        // LevelUpHeroCmd manually (which crashes on Execute).
        //
        // Strategy: Tavern UI fires LevelUpHeroCmd via
        //   HeroesLevelUpTabContext.OnLevelUpButtonClick()
        //   → ExecuteCommand(...)
        // We replay that path by walking from the dialog Context.
        //
        // The HeroesDevelopmentDialogContext holds the LevelUp tab in
        //   <LevelUpTab>k__BackingField (offset 0x120, IL2CPP dump)
        // along with selection state and the main-hero binding.
        //
        // Endpoints:
        //   /tavern-state           — read current state (target, food count)
        //   /tavern-select-main     — call SelectHero(Main)(heroId)
        //   /tavern-select-food     — Select(itemId, Material) for each id
        //   /tavern-fire-levelup    — OnLevelUpButtonClick (fires the cmd)
        // =====================================================

        // Walk to the active HeroesDevelopmentDialogContext and return
        // (ctxPtr, ctxClass). Returns IntPtr.Zero on either if not found.
        private void GetTavernDialogContext(out IntPtr ctxPtr, out IntPtr ctxClass)
        {
            ctxPtr = IntPtr.Zero;
            ctxClass = IntPtr.Zero;
            string dialogPath = "UIManager/Canvas (Ui Root)/Dialogs/"
                              + "[DV] HeroesDevelopmentDialog";
            var dlgGo = UnityEngine.GameObject.Find(dialogPath);
            if (dlgGo == null) return;

            foreach (var mono in dlgGo.GetComponentsInChildren<MonoBehaviour>(true))
            {
                if (mono == null) continue;
                IntPtr monoPtr = mono.Pointer;
                if (monoPtr == IntPtr.Zero) continue;
                IntPtr monoClass = il2cpp_object_get_class(monoPtr);
                if (monoClass == IntPtr.Zero) continue;

                IntPtr getCtxM = IntPtr.Zero;
                IntPtr scan = monoClass;
                while (scan != IntPtr.Zero && getCtxM == IntPtr.Zero)
                {
                    IntPtr mIter = IntPtr.Zero; IntPtr m;
                    while ((m = il2cpp_class_get_methods(scan, ref mIter)) != IntPtr.Zero)
                    {
                        string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                        if (mn == "get_Context" && il2cpp_method_get_param_count(m) == 0)
                        {
                            getCtxM = m;
                            break;
                        }
                    }
                    if (getCtxM == IntPtr.Zero)
                        scan = il2cpp_class_get_parent(scan);
                }
                if (getCtxM == IntPtr.Zero) continue;

                IntPtr exc = IntPtr.Zero;
                IntPtr ctxObj = il2cpp_runtime_invoke(getCtxM, monoPtr, IntPtr.Zero, ref exc);
                if (exc != IntPtr.Zero || ctxObj == IntPtr.Zero) continue;

                IntPtr cls = il2cpp_object_get_class(ctxObj);
                if (cls == IntPtr.Zero) continue;
                string ctxName = Marshal.PtrToStringAnsi(il2cpp_class_get_name(cls));
                if (ctxName == "HeroesDevelopmentDialogContext")
                {
                    ctxPtr = ctxObj;
                    ctxClass = cls;
                    return;
                }
            }
        }

        // Extract the IL2CPP exception's class name and Message string.
        // Used to learn WHY private methods reject our calls instead of just
        // logging "threw IL2Cpp exception". Returns a JSON snippet to append
        // to error responses, e.g. `,"exc_type":"NullReferenceException",
        // "exc_msg":"Object reference not set..."`.
        private string ReadIL2CppException(IntPtr exc)
        {
            try
            {
                if (exc == IntPtr.Zero) return "";
                IntPtr cls = il2cpp_object_get_class(exc);
                string clsName = cls == IntPtr.Zero ? "?" :
                    Marshal.PtrToStringAnsi(il2cpp_class_get_name(cls));

                // Walk hierarchy for get_Message (System.Exception slot).
                IntPtr getMsg = FindIL2CppMethodOnHierarchy(cls, "get_Message", 0);
                string msg = "";
                if (getMsg != IntPtr.Zero)
                {
                    IntPtr ex2 = IntPtr.Zero;
                    IntPtr s = il2cpp_runtime_invoke(getMsg, exc, IntPtr.Zero, ref ex2);
                    if (ex2 == IntPtr.Zero && s != IntPtr.Zero)
                    {
                        int len = Marshal.ReadInt32(s + 0x10);
                        if (len > 0 && len < 4096)
                            msg = Marshal.PtrToStringUni(s + 0x14, len);
                    }
                }
                return ",\"exc_type\":\"" + Esc(clsName)
                       + "\",\"exc_msg\":\"" + Esc(msg) + "\"";
            }
            catch { return ""; }
        }

        // API: /tavern-state — diagnostic read-only probe.
        // Reports whether the dialog is open, what tab is active,
        // whether a main hero is selected, and the count of selected
        // materials. Safe to call any time.
        private string TavernState()
        {
            try
            {
                IntPtr ctxPtr, ctxClass;
                GetTavernDialogContext(out ctxPtr, out ctxClass);
                if (ctxPtr == IntPtr.Zero)
                    return "{\"open\":false,\"error\":\"Tavern dialog not found\"}";

                // Read MainHero backing field (offset 0x168).
                uint mhOff = FindFieldOffset(ctxClass, "<MainHero>k__BackingField");
                int mainHeroId = -1;
                string mainHeroName = "";
                if (mhOff != uint.MaxValue)
                {
                    IntPtr heroPtr = Marshal.ReadIntPtr(ctxPtr + (int)mhOff);
                    if (heroPtr != IntPtr.Zero)
                    {
                        IntPtr heroClass = il2cpp_object_get_class(heroPtr);
                        IntPtr getIdM = FindIL2CppMethodOnHierarchy(heroClass, "get_Id", 0);
                        if (getIdM != IntPtr.Zero)
                        {
                            IntPtr excI = IntPtr.Zero;
                            IntPtr boxed = il2cpp_runtime_invoke(getIdM, heroPtr, IntPtr.Zero, ref excI);
                            if (excI == IntPtr.Zero && boxed != IntPtr.Zero)
                                mainHeroId = Marshal.ReadInt32(boxed + 0x10);
                        }
                    }
                }

                // Read CurrentTabType (int property, slot 52).
                IntPtr getTabTypeM = FindIL2CppMethodOnHierarchy(
                    ctxClass, "get_CurrentTabType", 0);
                int tabType = -1;
                if (getTabTypeM != IntPtr.Zero)
                {
                    IntPtr excT = IntPtr.Zero;
                    IntPtr boxed = il2cpp_runtime_invoke(getTabTypeM, ctxPtr, IntPtr.Zero, ref excT);
                    if (excT == IntPtr.Zero && boxed != IntPtr.Zero)
                        tabType = Marshal.ReadInt32(boxed + 0x10);
                }

                // Read LevelUp tab pointer (offset 0x120).
                uint luOff = FindFieldOffset(ctxClass, "<LevelUpTab>k__BackingField");
                bool levelUpTabFound = false;
                if (luOff != uint.MaxValue)
                {
                    IntPtr tabPtr = Marshal.ReadIntPtr(ctxPtr + (int)luOff);
                    levelUpTabFound = tabPtr != IntPtr.Zero;
                }

                // Count selected materials via get_SelectedMaterialItemIds.
                int selectedCount = 0;
                IntPtr getSelM = FindIL2CppMethodOnHierarchy(
                    ctxClass, "get_SelectedMaterialItemIds", 0);
                if (getSelM != IntPtr.Zero)
                {
                    IntPtr excS = IntPtr.Zero;
                    IntPtr enumObj = il2cpp_runtime_invoke(getSelM, ctxPtr, IntPtr.Zero, ref excS);
                    // We don't enumerate (avoid deep IL2CPP work) —
                    // just record whether it's non-null.
                    if (excS == IntPtr.Zero && enumObj != IntPtr.Zero)
                        selectedCount = -1;  // sentinel: present but uncounted
                }

                // Probe critical field nullability for diagnostics.
                bool selectionHolderNull = true;
                bool currentTabNull = true;
                bool heroesCollectionNull = true;
                uint shOff = FindFieldOffset(ctxClass, "_selectionHolder");
                if (shOff != uint.MaxValue)
                    selectionHolderNull = Marshal.ReadIntPtr(ctxPtr + (int)shOff) == IntPtr.Zero;
                uint ctOff = FindFieldOffset(ctxClass, "_currentTab");
                if (ctOff != uint.MaxValue)
                    currentTabNull = Marshal.ReadIntPtr(ctxPtr + (int)ctOff) == IntPtr.Zero;
                uint hsOff = FindFieldOffset(ctxClass, "_heroes");
                if (hsOff != uint.MaxValue)
                    heroesCollectionNull = Marshal.ReadIntPtr(ctxPtr + (int)hsOff) == IntPtr.Zero;

                return "{\"open\":true,\"main_hero_id\":" + mainHeroId
                       + ",\"current_tab_type\":" + tabType
                       + ",\"level_up_tab_found\":" + (levelUpTabFound ? "true" : "false")
                       + ",\"selected_materials_present\":" + (selectedCount != 0 ? "true" : "false")
                       + ",\"selection_holder_null\":" + (selectionHolderNull ? "true" : "false")
                       + ",\"current_tab_null\":" + (currentTabNull ? "true" : "false")
                       + ",\"heroes_collection_null\":" + (heroesCollectionNull ? "true" : "false")
                       + "}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.GetType().Name + ": " + ex.Message) + "\"}";
            }
        }

        // API: /tavern-fire-levelup — invoke OnLevelUpButtonClick on the
        // active HeroesLevelUpTabContext. Assumes the Tavern is open and
        // selection state is already set up (manually by the user, or by
        // the /tavern-select-main + /tavern-select-food endpoints).
        //
        // If selection is empty or invalid, the game's own validation
        // either short-circuits silently or shows a MessageBox — neither
        // crashes. That's why this path is safer than building the cmd
        // by hand.
        private string TavernFireLevelUp()
        {
            try
            {
                IntPtr ctxPtr, ctxClass;
                GetTavernDialogContext(out ctxPtr, out ctxClass);
                if (ctxPtr == IntPtr.Zero)
                    return "{\"error\":\"Tavern dialog not open\"}";

                uint luOff = FindFieldOffset(ctxClass, "<LevelUpTab>k__BackingField");
                if (luOff == uint.MaxValue)
                    return "{\"error\":\"<LevelUpTab>k__BackingField not found\"}";
                IntPtr tabPtr = Marshal.ReadIntPtr(ctxPtr + (int)luOff);
                if (tabPtr == IntPtr.Zero)
                    return "{\"error\":\"LevelUpTab is null (not initialized?)\"}";

                IntPtr tabClass = il2cpp_object_get_class(tabPtr);
                if (tabClass == IntPtr.Zero)
                    return "{\"error\":\"LevelUpTab class ptr is zero\"}";

                IntPtr clickM = FindIL2CppMethodOnHierarchy(
                    tabClass, "OnLevelUpButtonClick", 0);
                if (clickM == IntPtr.Zero)
                    return "{\"error\":\"OnLevelUpButtonClick not found on LevelUpTab\"}";

                Logger.LogInfo("[TavernFireLevelUp] invoking OnLevelUpButtonClick");
                IntPtr exc = IntPtr.Zero;
                il2cpp_runtime_invoke(clickM, tabPtr, IntPtr.Zero, ref exc);
                if (exc != IntPtr.Zero)
                {
                    string detail = ReadIL2CppException(exc);
                    Logger.LogWarning("[TavernFireLevelUp] threw" + detail);
                    return "{\"error\":\"OnLevelUpButtonClick threw IL2Cpp exception\""
                           + detail + "}";
                }

                Logger.LogInfo("[TavernFireLevelUp] click returned cleanly");
                return "{\"ok\":true}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.GetType().Name + ": " + ex.Message) + "\"}";
            }
        }

        // API: /tavern-select-main?hero_id=N — call SelectHero(Main)(N) to
        // set the target hero. Internally:
        //   1. SelectHero(DevelopmentItemSelectionType.Main) returns
        //      Action<int> bound to the dialog
        //   2. Invoke that action with the hero id
        // We bypass the closure-builder by calling the dialog's private
        // SwitchItemSelection directly: SwitchItemSelection(itemId, Main).
        // HeroesDevelopmentItemId wraps an int (HeroId).
        //
        // DevelopmentItemSelectionType enum (from dump.cs):
        //   None = 0, Main = 1, Material = 2, Locked = 3
        private string TavernSelectMain(string heroIdStr)
        {
            if (string.IsNullOrEmpty(heroIdStr) ||
                !int.TryParse(heroIdStr, out int heroId))
                return "{\"error\":\"hero_id (int) required\"}";

            return TavernSwitchSelection(heroId, 1 /* Main */);
        }

        // API: /tavern-select-food?ids=A,B,C — toggle each food hero into
        // the Material selection. Calls SwitchItemSelection(itemId, Material)
        // for each id in turn. Stops on first error.
        private string TavernSelectFood(string idsCsv)
        {
            if (string.IsNullOrEmpty(idsCsv))
                return "{\"error\":\"ids (comma-separated hero ids) required\"}";

            var ids = new List<int>();
            foreach (var p in idsCsv.Split(','))
            {
                var s = p.Trim();
                if (string.IsNullOrEmpty(s)) continue;
                if (!int.TryParse(s, out int v))
                    return "{\"error\":\"ids must be int csv, got: " + Esc(s) + "\"}";
                ids.Add(v);
            }
            if (ids.Count == 0)
                return "{\"error\":\"at least 1 food id required\"}";

            int ok = 0;
            string lastErr = null;
            foreach (var id in ids)
            {
                string r = TavernSwitchSelection(id, 2 /* Material */);
                if (r.Contains("\"ok\":true")) ok++;
                else { lastErr = r; break; }
            }
            return "{\"selected\":" + ok + ",\"requested\":" + ids.Count
                   + (lastErr != null ? ",\"last_error\":" + lastErr : "")
                   + "}";
        }

        // API: /level-up-hero-brews?target=N&brews=5501,5501,5501 — fire
        // LevelUpHeroCmd with BMI brew materials (no hero food). Same
        // managed-reflection ctor + CmdQueue.Enqueue dispatch path as
        // /level-up-hero-managed, just with BMI list populated.
        //
        // Pass a CSV of BlackMarketItemId values (one entry per brew).
        // Example: brews=5501,5501,5501 = 3 Magic level-up brews.
        // Use brew affinity matching the target hero, OR 5506 (Max) /
        // 5505 (Random) for universal use.
        private string LevelUpHeroBrews(string targetStr, string brewsCsv)
        {
            if (string.IsNullOrEmpty(targetStr) || !int.TryParse(targetStr, out int targetId))
                return "{\"error\":\"target (int hero_id) required\"}";
            if (string.IsNullOrEmpty(brewsCsv))
                return "{\"error\":\"brews (csv BMI ids) required\"}";

            var brewIds = new List<int>();
            foreach (var p in brewsCsv.Split(','))
            {
                var s = p.Trim();
                if (string.IsNullOrEmpty(s)) continue;
                if (!int.TryParse(s, out int v))
                    return "{\"error\":\"brews csv: bad int '" + Esc(s) + "'\"}";
                brewIds.Add(v);
            }
            if (brewIds.Count == 0)
                return "{\"error\":\"at least 1 brew id required\"}";

            try
            {
                var cmdType = FindType("Client.Model.Gameplay.Heroes.Commands.LevelUpHeroCmd");
                if (cmdType == null) return "{\"error\":\"LevelUpHeroCmd not found\"}";

                // Find 5-arg ctor.
                ConstructorInfo theCtor = null;
                foreach (var c in cmdType.GetConstructors(BindingFlags.Public | BindingFlags.Instance))
                {
                    if (c.GetParameters().Length == 5) { theCtor = c; break; }
                }
                if (theCtor == null) return "{\"error\":\"5-arg ctor not found\"}";

                var pars2 = theCtor.GetParameters();
                // arg 1 = int[] (heroMaterialIds, empty)
                // arg 2 = BlackMarketItemId[] (brews)
                object heroEmpty = Activator.CreateInstance(pars2[1].ParameterType, new object[] { 0 });
                object bmiArr = Activator.CreateInstance(pars2[2].ParameterType, new object[] { brewIds.ToArray() });

                object cmd;
                try
                {
                    cmd = theCtor.Invoke(new object[] {
                        targetId, heroEmpty, bmiArr,
                        true,   // isFastFeeding
                        false,  // deactivateArtifacts (no hero food, no relevant artifacts)
                    });
                }
                catch (TargetInvocationException tex)
                {
                    var inner = tex.InnerException ?? tex;
                    return "{\"error\":\"ctor.Invoke threw: " + Esc(inner.GetType().Name)
                           + ": " + Esc(inner.Message) + "\"}";
                }
                if (cmd == null) return "{\"error\":\"ctor returned null\"}";

                IntPtr cmdPtr = IntPtr.Zero;
                try { cmdPtr = (IntPtr)cmd.GetType().GetProperty("Pointer").GetValue(cmd); }
                catch { }
                if (cmdPtr == IntPtr.Zero) return "{\"error\":\"cmd Pointer zero\"}";
                Logger.LogInfo("[LevelUpBrews] cmd ptr=0x" + cmdPtr.ToString("X"));

                // Dispatch via AppModel CmdQueue.Enqueue (same as managed path).
                bool dispatchOk = false;
                string dispatchPath = "?";
                string excDetail = "";
                try
                {
                    var appModel = GetAppModel();
                    if (appModel != null)
                    {
                        var editUserM = appModel.GetType().GetMethod("EditUser",
                            BindingFlags.Instance | BindingFlags.Public);
                        if (editUserM != null)
                        {
                            object guard = editUserM.Invoke(appModel, null);
                            if (guard != null)
                            {
                                object cmdQueue = Prop(appModel, "CmdQueue");
                                if (cmdQueue != null)
                                {
                                    IntPtr cqPtr = (IntPtr)cmdQueue.GetType()
                                        .GetProperty("Pointer").GetValue(cmdQueue);
                                    IntPtr gPtr  = (IntPtr)guard.GetType()
                                        .GetProperty("Pointer").GetValue(guard);
                                    if (cqPtr != IntPtr.Zero && gPtr != IntPtr.Zero)
                                    {
                                        IntPtr cqCls = il2cpp_object_get_class(cqPtr);
                                        IntPtr enqIM = FindIL2CppMethodOnHierarchy(cqCls, "Enqueue", 2);
                                        if (enqIM != IntPtr.Zero)
                                        {
                                            IntPtr[] argArr = { gPtr, cmdPtr };
                                            var pinArg = System.Runtime.InteropServices.GCHandle.Alloc(
                                                argArr, System.Runtime.InteropServices.GCHandleType.Pinned);
                                            IntPtr ex3 = IntPtr.Zero;
                                            try {
                                                il2cpp_runtime_invoke(enqIM, cqPtr,
                                                    pinArg.AddrOfPinnedObject(), ref ex3);
                                            } finally { pinArg.Free(); }
                                            if (ex3 != IntPtr.Zero)
                                            {
                                                excDetail = ReadIL2CppException(ex3);
                                                Logger.LogWarning("[LevelUpBrews] Enqueue threw" + excDetail);
                                            }
                                            else
                                            {
                                                Logger.LogInfo("[LevelUpBrews] Enqueue ok");
                                                dispatchOk = true;
                                                dispatchPath = "CmdQueue.Enqueue";
                                            }
                                        }
                                    }
                                }
                                // Dispose guard.
                                try {
                                    var gPtr2 = (IntPtr)guard.GetType().GetProperty("Pointer").GetValue(guard);
                                    var gCls2 = il2cpp_object_get_class(gPtr2);
                                    var dM = FindIL2CppMethodOnHierarchy(gCls2, "Dispose", 0);
                                    if (dM != IntPtr.Zero)
                                    {
                                        IntPtr ex4 = IntPtr.Zero;
                                        il2cpp_runtime_invoke(dM, gPtr2, IntPtr.Zero, ref ex4);
                                    }
                                } catch (Exception dex) {
                                    Logger.LogWarning("[LevelUpBrews] dispose threw: " + dex.Message);
                                }
                            }
                        }
                    }
                }
                catch (Exception ex2)
                {
                    Logger.LogError("[LevelUpBrews] dispatch threw: " + ex2.Message);
                    return "{\"error\":\"dispatch: " + Esc(ex2.Message) + "\"}";
                }

                System.Threading.Thread.Sleep(2000);
                GC.KeepAlive(heroEmpty);
                GC.KeepAlive(bmiArr);

                return "{\"ok\":" + (dispatchOk ? "true" : "false")
                    + ",\"target\":" + targetId
                    + ",\"brews\":" + brewIds.Count
                    + ",\"dispatch_path\":\"" + Esc(dispatchPath) + "\""
                    + (excDetail.Length > 0 ? excDetail : "")
                    + "}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.GetType().Name + ": " + ex.Message) + "\"}";
            }
        }

        // API: /brew-counts — read all HeroLevelUpItem brew counts from
        // user.BlackMarket via CountFor(BlackMarketItemId). The 6 brew BMIs
        // (5501-5506) are per-affinity level-up consumables. If non-zero,
        // they can be used as BMI materials in LevelUpHeroCmd (ticks the
        // daily quest WITHOUT needing hero food).
        private string BrewCounts()
        {
            try
            {
                var uw = GetUserWrapper();
                if (uw == null) return "{\"error\":\"not logged in\"}";
                var bm = Prop(uw, "BlackMarket");
                if (bm == null) return "{\"error\":\"BlackMarket wrapper not found\"}";

                // Find CountFor(BlackMarketItemId) — managed wrapper exposes it.
                var bmiType = FindType("SharedModel.Meta.BlackMarket.BlackMarketItemId")
                              ?? FindTypeByLeafName("BlackMarketItemId");
                if (bmiType == null) return "{\"error\":\"BlackMarketItemId type not found\"}";

                System.Reflection.MethodInfo countForM = null;
                foreach (var m in bm.GetType().GetMethods(
                    BindingFlags.Instance | BindingFlags.Public | BindingFlags.FlattenHierarchy))
                {
                    if (m.Name == "CountFor" && m.GetParameters().Length == 1
                        && m.GetParameters()[0].ParameterType == bmiType)
                    {
                        countForM = m;
                        break;
                    }
                }
                if (countForM == null)
                    return "{\"error\":\"CountFor(BlackMarketItemId) not found\"}";

                var ids = new (int id, string name)[] {
                    (5501, "HeroLevelUpItemMagic"),
                    (5502, "HeroLevelUpItemForce"),
                    (5503, "HeroLevelUpItemSpirit"),
                    (5504, "HeroLevelUpItemVoid"),
                    (5505, "HeroLevelUpItemRandom"),
                    (5506, "HeroLevelUpItemMax"),
                };
                var sb = new StringBuilder("{\"brews\":[");
                int total = 0;
                for (int i = 0; i < ids.Length; i++)
                {
                    // Convert int to BlackMarketItemId enum value.
                    object bmiVal = Enum.ToObject(bmiType, ids[i].id);
                    int n = 0;
                    try { n = (int)countForM.Invoke(bm, new object[] { bmiVal }); }
                    catch { }
                    total += n;
                    if (i > 0) sb.Append(",");
                    sb.Append("{\"id\":").Append(ids[i].id)
                      .Append(",\"name\":\"").Append(ids[i].name)
                      .Append("\",\"count\":").Append(n).Append("}");
                }
                sb.Append("],\"total\":").Append(total).Append("}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.GetType().Name + ": " + ex.Message) + "\"}";
            }
        }

        // API: /level-up-hero-managed?target=N&food=A,B,C — same intent as
        // /level-up-hero but uses managed `ConstructorInfo.Invoke` instead
        // of raw IL2CPP ctor invoke. This mirrors the working `/rank-up`
        // dispatch flow exactly: get ctor by parameter types, invoke with
        // Il2CppStructArray<int> objects as the array args, then dispatch
        // via InvokeExecute (which tries direct Execute then falls back to
        // CmdQueue.Enqueue).
        //
        // Hypothesis: Activator earlier failed for LevelUpHeroCmd with
        // pooledPtr=0, but ConstructorInfo.Invoke (which rank-up uses)
        // may take a different code path through Il2CppInterop and properly
        // initialise the cmd's readonly fields, allowing Execute to run.
        private string LevelUpHeroManaged(string targetStr, string foodCsv)
        {
            if (string.IsNullOrEmpty(targetStr) || !int.TryParse(targetStr, out int targetId))
                return "{\"error\":\"target (int hero_id) required\"}";
            if (string.IsNullOrEmpty(foodCsv))
                return "{\"error\":\"food (csv hero ids) required\"}";

            var foodIds = new List<int>();
            foreach (var part in foodCsv.Split(','))
            {
                var s = part.Trim();
                if (string.IsNullOrEmpty(s)) continue;
                if (!int.TryParse(s, out int fid))
                    return "{\"error\":\"food csv: bad int '" + Esc(s) + "'\"}";
                foodIds.Add(fid);
            }
            if (foodIds.Count == 0)
                return "{\"error\":\"at least 1 food id required\"}";

            try
            {
                var cmdType = FindType("Client.Model.Gameplay.Heroes.Commands.LevelUpHeroCmd");
                if (cmdType == null)
                    return "{\"error\":\"LevelUpHeroCmd type not found\"}";

                // Build the wrapped arrays.
                var heroMaterialArr = new Il2CppInterop.Runtime.InteropTypes.Arrays
                    .Il2CppStructArray<int>(foodIds.ToArray());

                // BlackMarketItemId is an enum (int). Find the right array type.
                var bmiType = FindType("SharedModel.Meta.BlackMarket.BlackMarketItemId");
                if (bmiType == null)
                    bmiType = FindTypeByLeafName("BlackMarketItemId");
                if (bmiType == null)
                    return "{\"error\":\"BlackMarketItemId type not found\"}";
                var bmiArrType = bmiType.MakeArrayType();

                // Find the 5-arg ctor (int, int[], BMI[], bool, bool).
                ConstructorInfo theCtor = null;
                foreach (var c in cmdType.GetConstructors(BindingFlags.Public | BindingFlags.Instance))
                {
                    var pars = c.GetParameters();
                    if (pars.Length != 5) continue;
                    if (pars[0].ParameterType != typeof(int)) continue;
                    if (pars[3].ParameterType != typeof(bool)) continue;
                    if (pars[4].ParameterType != typeof(bool)) continue;
                    theCtor = c;
                    break;
                }
                if (theCtor == null)
                    return "{\"error\":\"5-arg ctor not found via reflection\"}";

                var pars2 = theCtor.GetParameters();
                Logger.LogInfo("[LevelUpManaged] ctor params: "
                    + pars2[0].ParameterType.FullName + ", "
                    + pars2[1].ParameterType.FullName + ", "
                    + pars2[2].ParameterType.FullName + ", "
                    + pars2[3].ParameterType.FullName + ", "
                    + pars2[4].ParameterType.FullName);

                // Build empty BMI array using the ctor's actual parameter type.
                object bmiEmpty = Activator.CreateInstance(pars2[2].ParameterType, new object[] { 0 });

                // Build hero material array using the ctor's actual int[] type.
                object heroArrAsCtor;
                var p1Type = pars2[1].ParameterType;
                if (p1Type.IsAssignableFrom(heroMaterialArr.GetType()))
                {
                    heroArrAsCtor = heroMaterialArr;
                }
                else
                {
                    // Build via ctor(int[]) on the IL2CPP array type.
                    heroArrAsCtor = Activator.CreateInstance(p1Type, new object[] { foodIds.ToArray() });
                }

                object cmd;
                try
                {
                    cmd = theCtor.Invoke(new object[] {
                        targetId,
                        heroArrAsCtor,
                        bmiEmpty,
                        true,      // isFastFeeding
                        true,      // deactivateArtifacts
                    });
                }
                catch (TargetInvocationException tex)
                {
                    var inner = tex.InnerException ?? tex;
                    return "{\"error\":\"ctor.Invoke threw: " + Esc(inner.GetType().Name)
                           + ": " + Esc(inner.Message) + "\"}";
                }
                if (cmd == null)
                    return "{\"error\":\"ctor.Invoke returned null\"}";
                Logger.LogInfo("[LevelUpManaged] cmd constructed");

                // Check pooledPtr to detect the Activator issue we hit before.
                IntPtr cmdPtr = IntPtr.Zero;
                try
                {
                    var ptrProp = cmd.GetType().GetProperty("Pointer");
                    if (ptrProp != null)
                        cmdPtr = (IntPtr)ptrProp.GetValue(cmd);
                }
                catch { }
                Logger.LogInfo("[LevelUpManaged] cmdPtr=0x" + cmdPtr.ToString("X"));
                if (cmdPtr == IntPtr.Zero)
                    return "{\"error\":\"cmd Pointer is zero (Activator wrap failed)\"}";

                // DIAGNOSTIC: check the cmd's internal field state. If
                // _bmiCountByItemId / _artifactsByHeroId / _input is null,
                // our reflection ctor didn't initialise things properly.
                try
                {
                    IntPtr cmdCls2 = il2cpp_object_get_class(cmdPtr);
                    uint bmiOff = FindFieldOffset(cmdCls2, "_bmiCountByItemId");
                    uint artOff = FindFieldOffset(cmdCls2, "_artifactsByHeroId");
                    uint inOff  = FindFieldOffset(cmdCls2, "_input");
                    uint reqOff = FindFieldOffset(cmdCls2, "_request");
                    string fieldReport = "fields:";
                    if (bmiOff != uint.MaxValue) {
                        IntPtr p = Marshal.ReadIntPtr(cmdPtr + (int)bmiOff);
                        fieldReport += " _bmiCountByItemId@0x" + bmiOff.ToString("X")
                                       + "=" + (p == IntPtr.Zero ? "NULL" : "0x" + p.ToString("X"));
                    } else fieldReport += " _bmiCountByItemId=missing";
                    if (artOff != uint.MaxValue) {
                        IntPtr p = Marshal.ReadIntPtr(cmdPtr + (int)artOff);
                        fieldReport += " _artifactsByHeroId@0x" + artOff.ToString("X")
                                       + "=" + (p == IntPtr.Zero ? "NULL" : "0x" + p.ToString("X"));
                    } else fieldReport += " _artifactsByHeroId=missing";
                    if (inOff != uint.MaxValue) {
                        IntPtr p = Marshal.ReadIntPtr(cmdPtr + (int)inOff);
                        fieldReport += " _input@0x" + inOff.ToString("X")
                                       + "=" + (p == IntPtr.Zero ? "NULL" : "0x" + p.ToString("X"));
                    } else fieldReport += " _input=missing";
                    if (reqOff != uint.MaxValue) {
                        IntPtr p = Marshal.ReadIntPtr(cmdPtr + (int)reqOff);
                        fieldReport += " _request@0x" + reqOff.ToString("X")
                                       + "=" + (p == IntPtr.Zero ? "NULL" : "0x" + p.ToString("X"));
                    } else fieldReport += " _request=missing";
                    Logger.LogInfo("[LevelUpManaged] " + fieldReport);
                }
                catch (Exception fex)
                {
                    Logger.LogWarning("[LevelUpManaged] field diag failed: " + fex.Message);
                }

                // Try setting cmd to background mode (UserPostEditCmd has
                // AsBackground() which sets _background=true). Some cmds
                // require this to fire without UI binding.
                try
                {
                    var asBgM = cmd.GetType().GetMethod("AsBackground",
                        BindingFlags.Instance | BindingFlags.Public | BindingFlags.FlattenHierarchy,
                        null, new System.Type[0], null);
                    if (asBgM != null)
                    {
                        asBgM.Invoke(cmd, null);
                        Logger.LogInfo("[LevelUpManaged] AsBackground() called");
                    }
                }
                catch (Exception bex)
                {
                    Logger.LogWarning("[LevelUpManaged] AsBackground failed: " + bex.Message);
                }

                // Hook lifecycle callbacks to learn what the cmd does.
                // IfStarting fires when Execute begins; IfSuccess fires after
                // server confirms; IfError fires on rejection or exception.
                bool sawStart = false, sawSuccess = false, sawError = false;
                string errorMsg = null;
                try
                {
                    var cmdT = cmd.GetType();
                    BindingFlags bf = BindingFlags.Instance | BindingFlags.Public | BindingFlags.FlattenHierarchy;
                    void hook(string mName, Action cb)
                    {
                        var m = cmdT.GetMethod(mName, bf, null, new[] { typeof(Action) }, null);
                        if (m != null) m.Invoke(cmd, new object[] { cb });
                    }
                    hook("IfStarting", () => { sawStart = true;
                        Logger.LogInfo("[LevelUpManaged] IfStarting fired"); });
                    hook("IfSuccess",  () => { sawSuccess = true;
                        Logger.LogInfo("[LevelUpManaged] IfSuccess fired"); });
                    hook("IfError",    () => { sawError = true; errorMsg = "server_rejected";
                        Logger.LogWarning("[LevelUpManaged] IfError target=" + targetId); });
                    hook("IfComplete", () => Logger.LogInfo("[LevelUpManaged] IfComplete fired"));
                }
                catch (Exception hex)
                {
                    Logger.LogWarning("[LevelUpManaged] callback wire failed: " + hex.Message);
                }

                Logger.LogInfo("[LevelUpManaged] dispatch target=" + targetId
                    + " food=[" + string.Join(",", foodIds) + "]");
                // Proper dispatch: enqueue via AppModel.CmdQueue.Enqueue(
                //   appModel.EditUser(), cmd). Direct Execute() runs the body
                // but doesn't actually fire the cmd over HTTP — the in-game
                // flow always enqueues. Without enqueuing, the cmd is built
                // but never sent.
                bool dispatchOk = false;
                string dispatchPath = "?";
                try
                {
                    var appModel = GetAppModel();
                    if (appModel == null)
                    {
                        Logger.LogWarning("[LevelUpManaged] AppModel null, falling back to Execute");
                    }
                    else
                    {
                        // Grab UserEditGuard via EditUser().
                        var editUserM = appModel.GetType().GetMethod("EditUser",
                            BindingFlags.Instance | BindingFlags.Public);
                        if (editUserM == null)
                        {
                            Logger.LogWarning("[LevelUpManaged] EditUser not found");
                        }
                        else
                        {
                            object guard = editUserM.Invoke(appModel, null);
                            if (guard == null)
                            {
                                Logger.LogWarning("[LevelUpManaged] EditUser returned null");
                            }
                            else
                            {
                                // CmdQueue is an internal field on AppModel.
                                var cmdQueueProp = appModel.GetType().GetField("CmdQueue",
                                    BindingFlags.Instance | BindingFlags.Public |
                                    BindingFlags.NonPublic);
                                object cmdQueue = cmdQueueProp != null
                                    ? cmdQueueProp.GetValue(appModel)
                                    : Prop(appModel, "CmdQueue");
                                if (cmdQueue == null)
                                {
                                    Logger.LogWarning("[LevelUpManaged] CmdQueue null");
                                }
                                else
                                {
                                    // Raw IL2CPP Enqueue(UserEditGuard, ICmdQueueItem).
                                    // Managed reflection fails because Il2CppInterop
                                    // doesn't expose ICmdQueueItem on LevelUpHeroCmd's
                                    // managed wrapper. We pass the raw pointers.
                                    IntPtr cqPtr = IntPtr.Zero;
                                    try
                                    {
                                        cqPtr = (IntPtr)cmdQueue.GetType()
                                            .GetProperty("Pointer").GetValue(cmdQueue);
                                    }
                                    catch (Exception cpe)
                                    {
                                        Logger.LogWarning("[LevelUpManaged] CmdQueue Pointer read failed: "
                                                          + cpe.Message);
                                    }
                                    IntPtr gPtr = IntPtr.Zero;
                                    try
                                    {
                                        gPtr = (IntPtr)guard.GetType()
                                            .GetProperty("Pointer").GetValue(guard);
                                    }
                                    catch (Exception gpe)
                                    {
                                        Logger.LogWarning("[LevelUpManaged] Guard Pointer read failed: "
                                                          + gpe.Message);
                                    }
                                    if (cqPtr == IntPtr.Zero || gPtr == IntPtr.Zero)
                                    {
                                        Logger.LogWarning("[LevelUpManaged] cqPtr/gPtr is zero: cq=0x"
                                                          + cqPtr.ToString("X") + " g=0x"
                                                          + gPtr.ToString("X"));
                                    }
                                    else
                                    {
                                        IntPtr cqCls = il2cpp_object_get_class(cqPtr);
                                        IntPtr enqIM = FindIL2CppMethodOnHierarchy(
                                            cqCls, "Enqueue", 2);
                                        if (enqIM == IntPtr.Zero)
                                        {
                                            Logger.LogWarning("[LevelUpManaged] Enqueue(2) IL2CPP not found");
                                        }
                                        else
                                        {
                                            IntPtr[] argArr = { gPtr, cmdPtr };
                                            var pinArg = System.Runtime.InteropServices.GCHandle.Alloc(
                                                argArr, System.Runtime.InteropServices.GCHandleType.Pinned);
                                            IntPtr ex3 = IntPtr.Zero;
                                            try
                                            {
                                                il2cpp_runtime_invoke(enqIM, cqPtr,
                                                    pinArg.AddrOfPinnedObject(), ref ex3);
                                            }
                                            finally { pinArg.Free(); }
                                            if (ex3 != IntPtr.Zero)
                                            {
                                                string d = ReadIL2CppException(ex3);
                                                Logger.LogWarning("[LevelUpManaged] Enqueue threw" + d);
                                                errorMsg = "enqueue_exc";
                                            }
                                            else
                                            {
                                                Logger.LogInfo("[LevelUpManaged] Enqueue via raw IL2CPP ok");
                                                dispatchOk = true;
                                                dispatchPath = "CmdQueue.Enqueue(raw)";
                                            }
                                        }
                                    }
                                }
                            }
                            // Dispose the guard (commits the user-edit transaction
                            // and triggers CmdQueue processing).
                            try
                            {
                                // Try IDisposable.Dispose via the interop wrapper —
                                // walk hierarchy. Some Il2CppInterop wrappers expose
                                // Dispose under the explicit-interface name.
                                System.Reflection.MethodInfo disposeM = null;
                                foreach (var dm in guard.GetType().GetMethods(
                                    BindingFlags.Instance | BindingFlags.Public |
                                    BindingFlags.NonPublic | BindingFlags.FlattenHierarchy))
                                {
                                    if ((dm.Name == "Dispose" ||
                                         dm.Name.EndsWith(".Dispose"))
                                        && dm.GetParameters().Length == 0)
                                    {
                                        disposeM = dm;
                                        break;
                                    }
                                }
                                if (disposeM != null)
                                {
                                    Logger.LogInfo("[LevelUpManaged] disposing guard via " + disposeM.Name);
                                    disposeM.Invoke(guard, null);
                                }
                                else
                                {
                                    // Raw IL2CPP dispose fallback.
                                    var gPtr2 = (IntPtr)guard.GetType().GetProperty("Pointer").GetValue(guard);
                                    if (gPtr2 != IntPtr.Zero)
                                    {
                                        var gCls2 = il2cpp_object_get_class(gPtr2);
                                        var dM = FindIL2CppMethodOnHierarchy(gCls2, "Dispose", 0);
                                        if (dM != IntPtr.Zero)
                                        {
                                            IntPtr ex4 = IntPtr.Zero;
                                            il2cpp_runtime_invoke(dM, gPtr2, IntPtr.Zero, ref ex4);
                                            Logger.LogInfo("[LevelUpManaged] raw Dispose called (exc=0x"
                                                           + ex4.ToString("X") + ")");
                                        }
                                    }
                                }
                            }
                            catch (Exception dex)
                            {
                                Logger.LogWarning("[LevelUpManaged] guard.Dispose threw: " + dex.Message);
                            }
                        }
                    }
                    if (!dispatchOk)
                    {
                        // Fallback to direct Execute (won't actually fire on
                        // the server but harmless if CmdQueue path failed).
                        InvokeExecute(cmd);
                        dispatchPath = "InvokeExecute-fallback";
                        dispatchOk = true;
                    }
                }
                catch (System.Reflection.TargetInvocationException tex)
                {
                    var inner = tex.InnerException ?? tex;
                    Logger.LogError("[LevelUpManaged] dispatch threw: "
                        + inner.GetType().Name + ": " + inner.Message);
                    return "{\"error\":\"dispatch: " + Esc(inner.Message) + "\"}";
                }
                catch (Exception eExec)
                {
                    Logger.LogError("[LevelUpManaged] dispatch threw: "
                        + eExec.GetType().Name + ": " + eExec.Message);
                    return "{\"error\":\"dispatch: " + Esc(eExec.Message) + "\"}";
                }
                // Give the cmd a moment to fire IfStarting/IfSuccess.
                System.Threading.Thread.Sleep(2500);

                return "{\"ok\":" + (dispatchOk ? "true" : "false")
                    + ",\"target\":" + targetId
                    + ",\"food_count\":" + foodIds.Count
                    + ",\"dispatch_path\":\"" + Esc(dispatchPath) + "\""
                    + ",\"saw_start\":" + (sawStart ? "true" : "false")
                    + ",\"saw_success\":" + (sawSuccess ? "true" : "false")
                    + ",\"saw_error\":" + (sawError ? "true" : "false")
                    + (errorMsg != null ? ",\"error_msg\":\"" + Esc(errorMsg) + "\"" : "")
                    + "}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.GetType().Name + ": " + ex.Message) + "\"}";
            }
        }

        // API: /tavern-execute-command?food=A,B,C&prev_level=N — call
        // HeroesLevelUpTabContext.ExecuteCommand(int[] hero, BMI[], int prev)
        // directly. This is the method that OnLevelUpButtonClick calls
        // internally AFTER gathering selection state — bypassing the
        // selection-state machinery entirely. Requires MainHero set
        // (via /tavern-force-main-hero first).
        //
        // BlackMarketItemId is an int enum, so its array is Il2CppStructArray<int>
        // with empty contents.
        private string TavernExecuteCommand(string foodCsv, string prevLevelStr)
        {
            if (string.IsNullOrEmpty(foodCsv))
                return "{\"error\":\"food (csv hero ids) required\"}";
            int prevLevel = 1;
            int.TryParse(prevLevelStr, out prevLevel);

            var ids = new List<int>();
            foreach (var p in foodCsv.Split(','))
            {
                var s = p.Trim();
                if (string.IsNullOrEmpty(s)) continue;
                if (!int.TryParse(s, out int v))
                    return "{\"error\":\"food must be int csv, got: " + Esc(s) + "\"}";
                ids.Add(v);
            }
            if (ids.Count == 0)
                return "{\"error\":\"at least 1 food id required\"}";

            try
            {
                IntPtr ctxPtr, ctxClass;
                GetTavernDialogContext(out ctxPtr, out ctxClass);
                if (ctxPtr == IntPtr.Zero)
                    return "{\"error\":\"Tavern dialog not open\"}";

                uint luOff = FindFieldOffset(ctxClass, "<LevelUpTab>k__BackingField");
                if (luOff == uint.MaxValue)
                    return "{\"error\":\"<LevelUpTab>k__BackingField not found\"}";
                IntPtr tabPtr = Marshal.ReadIntPtr(ctxPtr + (int)luOff);
                if (tabPtr == IntPtr.Zero)
                    return "{\"error\":\"LevelUpTab is null\"}";

                IntPtr tabClass = il2cpp_object_get_class(tabPtr);
                IntPtr execM = FindIL2CppMethodOnHierarchy(
                    tabClass, "ExecuteCommand", 3);
                if (execM == IntPtr.Zero)
                    return "{\"error\":\"ExecuteCommand(3) not found on LevelUpTab\"}";

                // Build int[] for heroMaterialIds.
                var foodArr = new Il2CppInterop.Runtime.InteropTypes.Arrays
                    .Il2CppStructArray<int>(ids.ToArray());
                IntPtr foodArrPtr = (IntPtr)foodArr.GetType()
                    .GetProperty("Pointer").GetValue(foodArr);
                if (foodArrPtr == IntPtr.Zero)
                    return "{\"error\":\"foodArr ptr is zero\"}";

                // Build BlackMarketItemId[] empty.
                var bmiArr = new Il2CppInterop.Runtime.InteropTypes.Arrays
                    .Il2CppStructArray<int>(new int[0]);
                IntPtr bmiArrPtr = (IntPtr)bmiArr.GetType()
                    .GetProperty("Pointer").GetValue(bmiArr);

                // Pin args: arg0 = ptr-to-arrayPtr, arg1 = ptr-to-arrayPtr,
                // arg2 = ptr-to-int.
                IntPtr[] arg0_arr = { foodArrPtr };
                IntPtr[] arg1_arr = { bmiArrPtr };
                int[] arg2_int = { prevLevel };

                var pin0 = System.Runtime.InteropServices.GCHandle.Alloc(
                    arg0_arr, System.Runtime.InteropServices.GCHandleType.Pinned);
                var pin1 = System.Runtime.InteropServices.GCHandle.Alloc(
                    arg1_arr, System.Runtime.InteropServices.GCHandleType.Pinned);
                var pin2 = System.Runtime.InteropServices.GCHandle.Alloc(
                    arg2_int, System.Runtime.InteropServices.GCHandleType.Pinned);
                IntPtr[] argList = {
                    pin0.AddrOfPinnedObject(),
                    pin1.AddrOfPinnedObject(),
                    pin2.AddrOfPinnedObject(),
                };
                var pinList = System.Runtime.InteropServices.GCHandle.Alloc(
                    argList, System.Runtime.InteropServices.GCHandleType.Pinned);

                Logger.LogInfo("[TavernExecuteCommand] food.count=" + ids.Count
                               + " prevLevel=" + prevLevel);
                IntPtr exc = IntPtr.Zero;
                try
                {
                    il2cpp_runtime_invoke(execM, tabPtr,
                        pinList.AddrOfPinnedObject(), ref exc);
                }
                finally
                {
                    pinList.Free(); pin2.Free(); pin1.Free(); pin0.Free();
                }
                if (exc != IntPtr.Zero)
                {
                    string detail = ReadIL2CppException(exc);
                    Logger.LogWarning("[TavernExecuteCommand] threw" + detail);
                    return "{\"error\":\"ExecuteCommand threw IL2Cpp exception\""
                           + detail + "}";
                }

                GC.KeepAlive(foodArr); GC.KeepAlive(bmiArr);
                Logger.LogInfo("[TavernExecuteCommand] dispatched ok");
                return "{\"ok\":true,\"food_count\":" + ids.Count
                       + ",\"prev_level\":" + prevLevel + "}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.GetType().Name + ": " + ex.Message) + "\"}";
            }
        }

        // API: /tavern-force-main-hero?hero_id=N — write Hero* directly to
        // <MainHero>k__BackingField at offset 0x168 on the dialog context.
        // Bypasses the dialog's SwitchItemSelection path which keeps NRE'ing
        // because something in the selection-holder logic isn't initialised.
        //
        // After this, OnLevelUpButtonClick (or a direct cmd dispatch using
        // the now-set MainHero) should be able to fire.
        private string TavernForceMainHero(string heroIdStr)
        {
            if (string.IsNullOrEmpty(heroIdStr) ||
                !int.TryParse(heroIdStr, out int heroId))
                return "{\"error\":\"hero_id (int) required\"}";

            try
            {
                IntPtr ctxPtr, ctxClass;
                GetTavernDialogContext(out ctxPtr, out ctxClass);
                if (ctxPtr == IntPtr.Zero)
                    return "{\"error\":\"Tavern dialog not open\"}";

                // Find Hero* by walking user heroes.
                var uw = GetUserWrapper();
                if (uw == null) return "{\"error\":\"Not logged in\"}";
                var heroes = Prop(uw, "Heroes");
                var heroData = Prop(heroes, "HeroData");
                var heroDict = Prop(heroData, "HeroById");
                if (heroDict == null)
                    return "{\"error\":\"HeroById null\"}";

                // Try-get the hero by id.
                object heroObj = null;
                var tryGetM = heroDict.GetType().GetMethod("TryGetValue");
                if (tryGetM != null)
                {
                    object[] args = { heroId, null };
                    bool ok = (bool)tryGetM.Invoke(heroDict, args);
                    if (ok) heroObj = args[1];
                }
                if (heroObj == null)
                    return "{\"error\":\"hero " + heroId + " not in HeroById\"}";

                // Extract IL2CPP pointer.
                IntPtr heroPtr = IntPtr.Zero;
                var ptrProp = heroObj.GetType().GetProperty("Pointer");
                if (ptrProp != null)
                    heroPtr = (IntPtr)ptrProp.GetValue(heroObj);
                if (heroPtr == IntPtr.Zero)
                    return "{\"error\":\"Hero IL2CPP pointer is zero\"}";

                // Write to <MainHero>k__BackingField (offset from class fields).
                uint mhOff = FindFieldOffset(ctxClass, "<MainHero>k__BackingField");
                if (mhOff == uint.MaxValue)
                    return "{\"error\":\"<MainHero>k__BackingField not found\"}";

                Marshal.WriteIntPtr(ctxPtr + (int)mhOff, heroPtr);
                Logger.LogInfo("[TavernForceMainHero] wrote hero=" + heroId
                               + " ptr=0x" + heroPtr.ToString("X")
                               + " to offset=0x" + mhOff.ToString("X"));
                return "{\"ok\":true,\"hero_id\":" + heroId
                       + ",\"ptr\":\"0x" + heroPtr.ToString("X") + "\"}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.GetType().Name + ": " + ex.Message) + "\"}";
            }
        }

        // API: /tavern-invoke-private?method=NAME — diagnostic helper to
        // invoke any 0-arg private method on the HeroesDevelopmentDialogContext.
        // Reports IL2Cpp exception type+message on failure. Used to find which
        // private setup method initialises the state for level-up.
        // Whitelist of safe-ish names (no destructive ops):
        //   SelectMainHero, SetCurrentTabContext, ResetAllMaterialsSelection,
        //   ResetStackableItems, UpdateSelectableContexts
        private string TavernInvokePrivate(string methodName)
        {
            if (string.IsNullOrEmpty(methodName))
                return "{\"error\":\"method param required\"}";

            var allowed = new System.Collections.Generic.HashSet<string> {
                "SelectMainHero", "SetCurrentTabContext",
                "ResetAllMaterialsSelection", "ResetStackableItems",
                "UpdateSelectableContexts",
            };
            if (!allowed.Contains(methodName))
                return "{\"error\":\"method not in safe whitelist: " + Esc(methodName)
                       + "\",\"whitelist\":[\"SelectMainHero\",\"SetCurrentTabContext\","
                       + "\"ResetAllMaterialsSelection\",\"ResetStackableItems\","
                       + "\"UpdateSelectableContexts\"]}";

            try
            {
                IntPtr ctxPtr, ctxClass;
                GetTavernDialogContext(out ctxPtr, out ctxClass);
                if (ctxPtr == IntPtr.Zero)
                    return "{\"error\":\"Tavern dialog not open\"}";

                IntPtr m = FindIL2CppMethodOnHierarchy(ctxClass, methodName, 0);
                if (m == IntPtr.Zero)
                    return "{\"error\":\"" + Esc(methodName) + "(0) not found\"}";

                Logger.LogInfo("[TavernInvokePrivate] " + methodName);
                IntPtr exc = IntPtr.Zero;
                il2cpp_runtime_invoke(m, ctxPtr, IntPtr.Zero, ref exc);
                if (exc != IntPtr.Zero)
                {
                    string detail = ReadIL2CppException(exc);
                    Logger.LogWarning("[TavernInvokePrivate] " + methodName + " threw" + detail);
                    return "{\"error\":\"" + Esc(methodName) + " threw\""
                           + detail + "}";
                }
                return "{\"ok\":true,\"method\":\"" + Esc(methodName) + "\"}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.GetType().Name + ": " + ex.Message) + "\"}";
            }
        }

        // Shared helper: call HeroesDevelopmentDialogContext.SwitchItemSelection
        // (private 2-arg method) with (HeroesDevelopmentItemId, selectionType).
        //
        // HeroesDevelopmentItemId is a 24-byte struct:
        //   0x00 EntityId (int)
        //   0x04 TypeId (ItemTypeId int — Hero=1, Bmi=2)
        //   0x08 _bmiNumber (int)
        //   0x0C padding (4 bytes)
        //   0x10 <Stack>k__BackingField (StackableItem ptr, 8 bytes)
        // Total: 0x18 (24) bytes.
        //
        // We marshal the struct as a byte[24] buffer with the right layout.
        // IL2CPP invoke passes a pointer to the struct data via argList[0].
        private string TavernSwitchSelection(int itemHeroId, int selectionType)
        {
            try
            {
                IntPtr ctxPtr, ctxClass;
                GetTavernDialogContext(out ctxPtr, out ctxClass);
                if (ctxPtr == IntPtr.Zero)
                    return "{\"error\":\"Tavern dialog not open\"}";

                IntPtr switchM = FindIL2CppMethodOnHierarchy(
                    ctxClass, "SwitchItemSelection", 2);
                if (switchM == IntPtr.Zero)
                    return "{\"error\":\"SwitchItemSelection(2) not found\"}";

                // Build the HeroesDevelopmentItemId struct (24 bytes).
                byte[] idStruct = new byte[24];
                BitConverter.GetBytes(itemHeroId).CopyTo(idStruct, 0);   // EntityId
                BitConverter.GetBytes((int)1).CopyTo(idStruct, 4);       // TypeId = Hero
                BitConverter.GetBytes((int)0).CopyTo(idStruct, 8);       // _bmiNumber = 0
                // Bytes 12-23 stay zero (padding + null Stack ptr).
                int[] argEnum = { selectionType };

                var pinId   = System.Runtime.InteropServices.GCHandle.Alloc(
                    idStruct,  System.Runtime.InteropServices.GCHandleType.Pinned);
                var pinEnum = System.Runtime.InteropServices.GCHandle.Alloc(
                    argEnum,   System.Runtime.InteropServices.GCHandleType.Pinned);
                IntPtr[] argList = {
                    pinId.AddrOfPinnedObject(),
                    pinEnum.AddrOfPinnedObject(),
                };
                var pinList = System.Runtime.InteropServices.GCHandle.Alloc(
                    argList, System.Runtime.InteropServices.GCHandleType.Pinned);

                IntPtr exc = IntPtr.Zero;
                try
                {
                    il2cpp_runtime_invoke(switchM, ctxPtr,
                        pinList.AddrOfPinnedObject(), ref exc);
                }
                finally
                {
                    pinList.Free(); pinEnum.Free(); pinId.Free();
                }
                if (exc != IntPtr.Zero)
                {
                    string detail = ReadIL2CppException(exc);
                    Logger.LogWarning("[TavernSwitchSelection] threw" + detail);
                    return "{\"error\":\"SwitchItemSelection threw IL2Cpp exception\""
                           + detail + "}";
                }

                Logger.LogInfo("[TavernSwitchSelection] item=" + itemHeroId
                               + " type=" + selectionType + " ok");
                return "{\"ok\":true,\"item\":" + itemHeroId
                       + ",\"selection_type\":" + selectionType + "}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.GetType().Name + ": " + ex.Message) + "\"}";
            }
        }
    }
}
