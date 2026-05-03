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

        // save-preset: Clone existing preset, replace heroes, set priorities.
        // params: name, heroes (comma-sep instance IDs), type (1=PvE)
        //   priorities: heroId:skillId=pri,skillId=pri;heroId:... (optional)
        //   pri: 0=Default, 1=First, 2=Second, 3=Third, 4=NotUsed
        private string SavePreset(string nameStr, string heroIdsStr, string typeStr)
        {
            if (string.IsNullOrEmpty(heroIdsStr))
                return "{\"error\":\"heroes required (comma-separated hero IDs)\"}";

            string presetName = string.IsNullOrEmpty(nameStr) ? "New Team" : nameStr;
            int presetType = 1; // GeneralPve
            if (!string.IsNullOrEmpty(typeStr))
                int.TryParse(typeStr, out presetType);

            var heroIds = new List<int>();
            foreach (var s in heroIdsStr.Split(','))
            {
                if (int.TryParse(s.Trim(), out int hid) && hid > 0)
                    heroIds.Add(hid);
            }
            if (heroIds.Count == 0) return "{\"error\":\"no valid hero IDs\"}";

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

                // === Strategy A: Clone an existing preset and modify it ===
                // This is the most reliable approach — Clone() produces a proper IL2CPP object
                // with all native memory correctly allocated.
                object existingPreset = null;
                try
                {
                    var heroes = Prop(uw, "Heroes");
                    var heroData = Prop(heroes, "HeroData");
                    object presetList = Prop(heroData, "HeroesAiPresets");
                    if (presetList == null) presetList = Prop(heroes, "HeroesAiPresets");
                    if (presetList != null)
                    {
                        foreach (var p in ListItems(presetList))
                        {
                            existingPreset = p;
                            break; // Take the first one
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

                // Force Id to 0 — try multiple approaches since IL2CPP cloned
                // objects may have the original Id baked into native memory.
                bool idSet = false;
                // Approach 1: property setter
                try {
                    var setId = presetT.GetMethod("set_Id");
                    if (setId != null) { setId.Invoke(preset, new object[] { 0 }); idSet = true; }
                } catch {}
                // Approach 2: field
                if (!idSet) {
                    try {
                        var idField = presetT.GetField("Id", BindingFlags.Public | BindingFlags.Instance);
                        if (idField != null) { idField.SetValue(preset, 0); idSet = true; }
                    } catch {}
                }
                // Approach 3: IL2CPP raw write via Pointer offset
                if (!idSet) {
                    try {
                        var ptrProp = presetT.GetProperty("Pointer");
                        if (ptrProp != null) {
                            IntPtr ptr = (IntPtr)ptrProp.GetValue(preset);
                            if (ptr != IntPtr.Zero) {
                                // Id is typically the first int field after the IL2CPP header
                                // Write 0 at common offsets
                                foreach (var off in new[] { 0x10, 0x18, 0x20 }) {
                                    int cur = Marshal.ReadInt32(ptr + off);
                                    if (cur == 1) { // Found the cloned Id=1
                                        Marshal.WriteInt32(ptr + off, 0);
                                        idSet = true;
                                        break;
                                    }
                                }
                            }
                        }
                    } catch {}
                }
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

                // Clear the cloned list and add fresh entries
                var clearList = setupListT.GetMethod("Clear");
                if (clearList != null) clearList.Invoke(setupList, null);
                var addSetup = setupListT.GetMethod("Add");

                // Get the SkillPrioritiesSetup(heroId, dict, presetType) constructor
                var setupCtor3 = presetTypeEnum != null
                    ? setupT.GetConstructor(new[] { typeof(int), dictT, presetTypeEnum })
                    : null;
                sb.Append(",\"setupCtor3\":" + (setupCtor3 != null ? "true" : "false"));

                // Prepare presetType enum value
                object presetTypeEnumVal = presetTypeEnum != null
                    ? Enum.ToObject(presetTypeEnum, presetType)
                    : null;

                sb.Append("},\"heroes\":[");
                bool first = true;

                foreach (int heroId in heroIds)
                {
                    // Get hero's skills
                    object hero = null;
                    try {
                        var ck = heroDict.GetType().GetMethod("ContainsKey");
                        if (ck != null && (bool)ck.Invoke(heroDict, new object[] { heroId }))
                            hero = heroDict.GetType().GetProperty("Item")?.GetValue(heroDict, new object[] { heroId });
                    } catch {}

                    var skillIds = new List<int>();
                    if (hero != null)
                    {
                        try {
                            var skills = Prop(hero, "Skills");
                            if (skills != null)
                            {
                                var getCount = skills.GetType().GetProperty("Count");
                                int cnt = getCount != null ? (int)getCount.GetValue(skills) : 0;
                                var getItem = skills.GetType().GetProperty("Item");
                                for (int si = 0; si < cnt; si++)
                                {
                                    var skill = getItem?.GetValue(skills, new object[] { si });
                                    if (skill != null)
                                    {
                                        var typeId = Prop(skill, "TypeId");
                                        if (typeId != null) skillIds.Add((int)typeId);
                                    }
                                }
                            }
                        } catch {}
                    }

                    // Create skill priority dict: all skills = Default (0)
                    var priDict = Activator.CreateInstance(dictT);
                    var dictAdd = dictT.GetMethod("Add");
                    // Try specific overload first, then fall back to generic Add
                    if (dictAdd == null)
                        dictAdd = dictT.GetMethod("Add", new[] { typeof(int), sptEnum });

                    foreach (int sid in skillIds)
                    {
                        try { dictAdd.Invoke(priDict, new object[] { sid, Enum.ToObject(sptEnum, 0) }); } catch {}
                    }

                    object setup = null;

                    // Strategy 1: Use the 3-arg constructor which creates sequences properly
                    if (setupCtor3 != null)
                    {
                        try
                        {
                            setup = setupCtor3.Invoke(new object[] { heroId, priDict, presetTypeEnumVal });
                        }
                        catch (Exception ctorEx)
                        {
                            Logger.LogWarning("PRESET: 3-arg ctor failed for hero " + heroId + ": " + ctorEx.Message);
                        }
                    }

                    // Strategy 2: Default ctor + set fields directly
                    if (setup == null)
                    {
                        setup = Activator.CreateInstance(setupT);
                        SetFieldOrProp(setupT, setup, "HeroId", heroId);
                        SetFieldOrProp(setupT, setup, "PriorityBySkillId", priDict);

                        // Create sequences manually using HeroAiPresetSequence(dict) ctor
                        var seqT = FindType("SharedModel.Meta.Heroes.HeroAiPresetSequence");
                        if (seqT != null)
                        {
                            var seqField = setupT.GetField("Sequences",
                                BindingFlags.Public | BindingFlags.Instance);
                            Type seqListT = seqField != null ? seqField.FieldType
                                : (FindType("System.Collections.Generic.List`1") ?? typeof(List<>)).MakeGenericType(seqT);
                            var seqList = Activator.CreateInstance(seqListT);
                            var addSeq = seqListT.GetMethod("Add");

                            // HeroAiPresetSequence has a ctor(Dictionary<int,SPT>)
                            var seqCtor = seqT.GetConstructor(new[] { dictT });
                            int numSeqs = 3; // Default for GeneralPve

                            for (int r = 0; r < numSeqs; r++)
                            {
                                object seq = null;
                                if (seqCtor != null)
                                {
                                    // Clone the dict for each sequence
                                    var seqDict = Activator.CreateInstance(dictT);
                                    foreach (int sid in skillIds)
                                    {
                                        try { dictAdd.Invoke(seqDict, new object[] { sid, Enum.ToObject(sptEnum, 0) }); } catch {}
                                    }
                                    try { seq = seqCtor.Invoke(new object[] { seqDict }); } catch {}
                                }
                                if (seq == null)
                                {
                                    seq = Activator.CreateInstance(seqT);
                                    var seqDict = Activator.CreateInstance(dictT);
                                    foreach (int sid in skillIds)
                                    {
                                        try { dictAdd.Invoke(seqDict, new object[] { sid, Enum.ToObject(sptEnum, 0) }); } catch {}
                                    }
                                    SetFieldOrProp(seqT, seq, "PriorityBySkillId", seqDict);
                                }
                                addSeq.Invoke(seqList, new object[] { seq });
                            }
                            SetFieldOrProp(setupT, setup, "Sequences", seqList);
                        }
                    }

                    addSetup.Invoke(setupList, new object[] { setup });

                    if (!first) sb.Append(",");
                    first = false;
                    sb.Append("{\"id\":" + heroId + ",\"skills\":[" + string.Join(",", skillIds) + "]}");
                }

                // Set the SkillPrioritiesSetups field on the preset
                SetFieldOrProp(presetT, preset, "SkillPrioritiesSetups", setupList);

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
        private string UpdatePreset(string idStr, string prioritiesStr, string startersStr = null)
        {
            if (string.IsNullOrEmpty(idStr))
                return "{\"error\":\"id required\"}";
            int targetId;
            if (!int.TryParse(idStr, out targetId))
                return "{\"error\":\"invalid id\"}";

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
    }
}
