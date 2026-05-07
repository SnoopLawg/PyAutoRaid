// Auto-extracted from RaidAutomationPlugin.cs (slice: static data export).
// All these methods are partial-class members of RaidAutomationPlugin.
// Behavior is identical; this file just isolates static-data extraction
// (HeroTypes / AllianceBosses / ArtifactSets / Masteries / Blessings /
// DungeonDrops / ForgeSets / generic /static-export) from the main HTTP
// router and battle-state code.
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
        private string ExportStaticDataPath(string path, int depth, int max)
        {
            var appModel = GetAppModel();
            if (appModel == null) return "{\"error\":\"appmodel not ready\"}";
            object target = Prop(appModel, "StaticData");
            if (target == null) return "{\"error\":\"AppModel.StaticData null\"}";
            // Reuse the same path-walker as /explore-sd
            if (!string.IsNullOrEmpty(path))
            {
                foreach (var seg in path.Split('.'))
                {
                    object next;
                    if (seg.StartsWith("Item[") && seg.EndsWith("]"))
                    {
                        var keyStr = seg.Substring(5, seg.Length - 6);
                        var idx = target.GetType().GetProperty("Item");
                        if (idx == null) return "{\"error\":\"no indexer at " + Esc(seg) + "\"}";
                        var paramT = idx.GetIndexParameters()[0].ParameterType;
                        object key = keyStr;
                        if (paramT.IsEnum)
                        {
                            try { key = Enum.ToObject(paramT, int.Parse(keyStr)); }
                            catch { try { key = Enum.Parse(paramT, keyStr); } catch { } }
                        }
                        else
                        {
                            try { key = Convert.ChangeType(keyStr, paramT); } catch { }
                        }
                        try { next = idx.GetValue(target, new object[] { key }); }
                        catch (Exception ex) { return "{\"error\":\"indexer threw " + Esc(ex.Message) + "\"}"; }
                    }
                    else if (seg.StartsWith("[") && seg.EndsWith("]"))
                    {
                        var nStr = seg.Substring(1, seg.Length - 2);
                        if (!int.TryParse(nStr, out int n)) return "{\"error\":\"bad index " + Esc(nStr) + "\"}";
                        var get = target.GetType().GetMethod("get_Item", new[] { typeof(int) });
                        if (get == null) return "{\"error\":\"no get_Item(int) at " + Esc(seg) + "\"}";
                        try { next = get.Invoke(target, new object[] { n }); }
                        catch (Exception ex) { return "{\"error\":\"index threw " + Esc(ex.Message) + "\"}"; }
                    }
                    else
                    {
                        next = Prop(target, seg);
                    }
                    if (next == null) return "{\"error\":\"no segment " + Esc(seg) + " on " + Esc(target.GetType().FullName) + "\"}";
                    target = next;
                }
            }
            var sb = new StringBuilder(8192);
            try
            {
                SerializeValue(sb, target, depth, max, new HashSet<object>(new ReferenceEqualityComparer()));
            }
            catch (Exception ex)
            {
                return "{\"error\":\"serialize threw " + Esc(ex.Message) + "\"}";
            }
            return sb.ToString();
        }

        // Custom equality comparer for cycle detection — defaults to
        // reference equality but works on Il2Cpp wrapper objects too.
        private class ReferenceEqualityComparer : IEqualityComparer<object>
        {
            public new bool Equals(object x, object y) => ReferenceEquals(x, y);
            public int GetHashCode(object obj) =>
                obj == null ? 0 : System.Runtime.CompilerServices.RuntimeHelpers.GetHashCode(obj);
        }

        private void SerializeValue(StringBuilder sb, object v, int depth, int max,
                                     HashSet<object> seen)
        {
            if (v == null) { sb.Append("null"); return; }
            var t = v.GetType();
            // Skip noisy / unhelpful types: delegates leak IL2CPP internal
            // pointers, IntPtrs are just memory addresses, MethodInfo is a
            // reflection wrapper. Render as a stub so nesting still works.
            if (typeof(System.Delegate).IsAssignableFrom(t)
                || t.Name == "MethodInfo" || t.Name == "RuntimeMethodInfo"
                || v is IntPtr)
            {
                sb.Append("\"<").Append(Esc(t.Name)).Append(">\"");
                return;
            }
            // Primitives & string
            if (v is bool b) { sb.Append(b ? "true" : "false"); return; }
            if (v is string s) { sb.Append("\"").Append(Esc(s)).Append("\""); return; }
            if (t.IsPrimitive)
            {
                // double/float need invariant culture; ints append directly
                if (v is double d)
                    sb.Append(d.ToString("R", System.Globalization.CultureInfo.InvariantCulture));
                else if (v is float f)
                    sb.Append(f.ToString("R", System.Globalization.CultureInfo.InvariantCulture));
                else
                    sb.Append(Convert.ToString(v, System.Globalization.CultureInfo.InvariantCulture));
                return;
            }
            if (t.IsEnum) { sb.Append("\"").Append(v.ToString()).Append("\""); return; }
            // Nullable<T> wrapper — both .NET System.Nullable<T> AND
            // IL2CPP's Il2CppSystem.Nullable<T> appear here. Match by
            // type name "Nullable`1" since the generic-type-definition
            // check fails for IL2CPP wrappers (different identity).
            // Read the lowercase backing fields `hasValue` / `value`
            // directly — IL2CPP's `Value` property getter returns a
            // default value (zeroed Fixed) due to runtime marshaling.
            if (t.Name == "Nullable`1")
            {
                try
                {
                    // IL2CPP wrappers expose backing fields directly.
                    var hvField = t.GetField("hasValue",
                        BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                    var valField = t.GetField("value",
                        BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                    bool? hasValue = null;
                    object inner = null;
                    if (hvField != null) hasValue = (bool)hvField.GetValue(v);
                    if (valField != null) inner = valField.GetValue(v);
                    // Fallback to managed Property access if fields unavailable
                    if (hasValue == null)
                    {
                        var hvProp = t.GetProperty("HasValue");
                        if (hvProp != null) hasValue = (bool)hvProp.GetValue(v);
                    }
                    if (inner == null)
                    {
                        var valProp = t.GetProperty("Value");
                        if (valProp != null) inner = valProp.GetValue(v);
                    }
                    if (hasValue == false) { sb.Append("null"); return; }
                    if (hasValue == true && inner != null)
                    {
                        SerializeValue(sb, inner, depth, max, seen);
                        return;
                    }
                    // hasValue couldn't be determined — emit null defensively
                    sb.Append("null");
                    return;
                }
                catch { }
            }
            // Plarium "Fixed" stat type — read via RawValue (Int64 backing)
            // and divide by 2^32. Convert.ToDouble() returns garbage for
            // Fixed wrappers that don't override IConvertible — in static
            // data context produces stale values from Nullable<Fixed>
            // backing fields whose HasValue=false (uninitialized memory).
            if (t.Name == "Fixed" || t.Name == "Fixed64")
            {
                // PREFER ToString() over RawValue field — when a Fixed is
                // unboxed from a Nullable<Fixed>.value backing field via
                // FieldInfo.GetValue, the resulting boxed copy's RawValue
                // field reads stale memory (returns garbage long). The
                // type's overridden ToString() goes through IL2CPP managed
                // call and returns the correct decimal text.
                try
                {
                    string str = v.ToString();
                    if (double.TryParse(str,
                        System.Globalization.NumberStyles.Any,
                        System.Globalization.CultureInfo.InvariantCulture,
                        out var dd) && !double.IsNaN(dd) && !double.IsInfinity(dd))
                    {
                        sb.Append(dd.ToString("R", System.Globalization.CultureInfo.InvariantCulture));
                        return;
                    }
                }
                catch { }
                // Fallback: try RawValue / m_value / _value / Value field/property
                try
                {
                    foreach (var fname in new[] { "RawValue", "m_value", "_value", "Value" })
                    {
                        var f = t.GetField(fname, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                        if (f != null && f.FieldType == typeof(long))
                        {
                            long raw = (long)f.GetValue(v);
                            double dval = raw / 4294967296.0;
                            sb.Append(dval.ToString("R", System.Globalization.CultureInfo.InvariantCulture));
                            return;
                        }
                        var p = t.GetProperty(fname);
                        if (p != null)
                        {
                            var pv = p.GetValue(v);
                            if (pv is long l)
                            {
                                double dval = l / 4294967296.0;
                                sb.Append(dval.ToString("R", System.Globalization.CultureInfo.InvariantCulture));
                                return;
                            }
                        }
                    }
                }
                catch { }
                sb.Append("0");
                return;
            }
            // Cycle / depth guard
            if (depth < 0 || seen.Contains(v))
            {
                sb.Append("\"<").Append(Esc(t.Name)).Append(">\"");
                return;
            }
            // Dictionary: { "key": serialized_value, ... }
            // We detect by looking for an "_entries" array (Il2Cpp Dictionary
            // layout) OR via IDictionary interface as fallback.
            var entries = t.GetProperty("_entries", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public)?.GetValue(v)
                       ?? t.GetField("_entries", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public)?.GetValue(v);
            if (entries != null)
            {
                int count = IntProp(v, "Count");
                seen.Add(v);
                sb.Append("{");
                int written = 0;
                int n = IntProp(entries, "Length");
                var get = entries.GetType().GetMethod("get_Item", new[] { typeof(int) });
                bool truncated = false;
                for (int i = 0; i < n && written < count; i++)
                {
                    if (written >= max) { truncated = true; break; }
                    object e = null;
                    try { e = get?.Invoke(entries, new object[] { i }); } catch { }
                    if (e == null) continue;
                    int hash = IntProp(e, "hashCode");
                    if (hash == 0) continue;  // skip empty slots
                    var key = Prop(e, "key");
                    var value = Prop(e, "value");
                    if (value == null && key == null) continue;
                    // Fall back: if key is the kind of int that hashes to itself (most ids)
                    // hashCode == key. Otherwise serialize key directly.
                    string keyStr;
                    if (key == null || key.GetType() == typeof(int))
                        keyStr = (key ?? hash).ToString();
                    else if (key is string ks)
                        keyStr = ks;
                    else
                        keyStr = key.ToString();
                    if (written > 0) sb.Append(",");
                    sb.Append("\"").Append(Esc(keyStr)).Append("\":");
                    SerializeValue(sb, value, depth - 1, max, seen);
                    written++;
                }
                if (truncated) sb.Append(",\"_truncated\":true");
                sb.Append("}");
                seen.Remove(v);
                return;
            }
            // List / array: iterate via get_Item(int) + Count
            var countProp = t.GetProperty("Count");
            var getItem = t.GetMethod("get_Item", new[] { typeof(int) });
            if (countProp != null && getItem != null)
            {
                int n = (int)countProp.GetValue(v);
                seen.Add(v);
                sb.Append("[");
                int limit = Math.Min(n, max);
                for (int i = 0; i < limit; i++)
                {
                    object item = null;
                    try { item = getItem.Invoke(v, new object[] { i }); } catch { }
                    if (i > 0) sb.Append(",");
                    SerializeValue(sb, item, depth - 1, max, seen);
                }
                if (n > limit) sb.Append(",\"<truncated_at_" + limit + "_of_" + n + ">\"");
                sb.Append("]");
                seen.Remove(v);
                return;
            }
            // Generic object: walk public properties + non-static fields.
            // Skip uninteresting ones (Pointer, ObjectClass, WasCollected,
            // Backing fields, Il2Cpp-internal).
            seen.Add(v);
            sb.Append("{");
            bool first = true;
            foreach (var p in t.GetProperties(BindingFlags.Instance | BindingFlags.Public))
            {
                if (p.GetIndexParameters().Length > 0) continue;
                var name = p.Name;
                if (name == "Pointer" || name == "ObjectClass" || name == "WasCollected") continue;
                if (name.StartsWith("_") || name.EndsWith("_k__BackingField")) continue;
                if (!p.CanRead) continue;
                object pv = null;
                try { pv = p.GetValue(v); } catch { continue; }
                if (pv == null) continue;
                if (!first) sb.Append(",");
                first = false;
                sb.Append("\"").Append(Esc(name)).Append("\":");
                SerializeValue(sb, pv, depth - 1, max, seen);
            }
            sb.Append("}");
            seen.Remove(v);
        }

        // Walk AppModel.StaticData → StageData and emit per-region artifact +
        // accessory drop pools. Pulls from each Stage's FlexibleReward, which
        // exposes ArtifactProbsBySetKindId / ArtifactProbsByKindId /
        // AccessoryProbsByKindId / AccessoryProbsByHeroFraction etc.
        private string GetDungeonDrops()
        {
            var appModel = GetAppModel();
            if (appModel == null) return "{\"error\":\"appmodel not ready\"}";
            var sd = Prop(appModel, "StaticData");
            if (sd == null) return "{\"error\":\"AppModel.StaticData null\"}";
            var stageData = Prop(sd, "StageData");
            if (stageData == null) return "{\"error\":\"StaticData.StageData null\"}";
            var regionsById = Prop(stageData, "RegionsById");
            var allStages = Prop(stageData, "Stages");
            if (regionsById == null || allStages == null) return "{\"error\":\"StageData.RegionsById/Stages null\"}";

            // Build stage_id -> Stage map.
            var stageById = new Dictionary<int, object>();
            try
            {
                int n = IntProp(allStages, "_size");
                var items = Prop(allStages, "_items");
                if (items != null)
                {
                    var get = items.GetType().GetMethod("get_Item", new[] { typeof(int) })
                              ?? items.GetType().GetProperty("Item")?.GetGetMethod();
                    for (int i = 0; i < n; i++)
                    {
                        var st = get.Invoke(items, new object[] { i });
                        if (st == null) continue;
                        int sid = IntProp(st, "Id");
                        stageById[sid] = st;
                    }
                }
            }
            catch (Exception ex) { return "{\"error\":\"stage walk: " + Esc(ex.Message) + "\"}"; }

            var sb = new StringBuilder(16384);
            sb.Append("{\"regions\":{");
            bool firstRegion = true;
            try
            {
                // Walk RegionsById._entries; the value (Region) is reliable even
                // when entry.key gives garbage for Il2Cpp enum dicts. Dedupe by
                // region.Id so free-slot ghosts don't double-up.
                var entries = Prop(regionsById, "_entries");
                int len = entries != null ? IntProp(entries, "Length") : 0;
                var get = entries != null
                    ? (entries.GetType().GetMethod("get_Item", new[] { typeof(int) })
                       ?? entries.GetType().GetProperty("Item")?.GetGetMethod())
                    : null;
                var seenIds = new HashSet<int>();
                for (int i = 0; i < len; i++)
                {
                    var entry = get.Invoke(entries, new object[] { i });
                    if (entry == null) continue;
                    var region = Prop(entry, "value");
                    if (region == null) continue;
                    var idVal = Prop(region, "Id");
                    if (idVal == null) continue;
                    int rid = ExtractEnumInt(idVal);
                    if (rid == 0) continue;
                    if (!seenIds.Add(rid)) continue;
                    EmitRegion(sb, ref firstRegion, region, idVal, rid, stageById);
                }
            }
            catch (Exception ex) { return "{\"error\":\"region walk: " + Esc(ex.Message) + "\"}"; }
            sb.Append("}}");
            return sb.ToString();
        }

        // Walk AppModel.StaticData.ForgeData.ForgeArtifactRecipes and emit
        // the unique set IDs that can be crafted in the Forge. These typically
        // include Lethal, Stoneskin, Bolster, Guardian, Protection, Curing,
        // Untouchable, etc. — sets that don't drop in any dungeon.
        private string GetForgeSets()
        {
            var appModel = GetAppModel();
            if (appModel == null) return "{\"error\":\"appmodel not ready\"}";
            var sd = Prop(appModel, "StaticData");
            if (sd == null) return "{\"error\":\"AppModel.StaticData null\"}";
            var forgeData = Prop(sd, "ForgeData");
            if (forgeData == null) return "{\"error\":\"StaticData.ForgeData null\"}";
            var recipes = Prop(forgeData, "ForgeArtifactRecipes");
            if (recipes == null) return "{\"error\":\"ForgeData.ForgeArtifactRecipes null\"}";

            var sb = new StringBuilder(4096);
            sb.Append("{\"recipes\":[");
            bool first = true;
            try
            {
                int n = IntProp(recipes, "_size");
                var items = Prop(recipes, "_items");
                if (items != null && n > 0)
                {
                    var get = items.GetType().GetMethod("get_Item", new[] { typeof(int) })
                              ?? items.GetType().GetProperty("Item")?.GetGetMethod();
                    var seenSets = new HashSet<int>();
                    for (int i = 0; i < n; i++)
                    {
                        var r = get.Invoke(items, new object[] { i });
                        if (r == null) continue;
                        int recipeId = IntProp(r, "Id");
                        var setKind = Prop(r, "ArtifactSetKindId");
                        int setId = ExtractEnumInt(setKind);
                        string setName = setKind != null ? setKind.ToString() : "?";
                        var rankVar = Prop(r, "OutputRankVariationId");
                        string rankName = rankVar != null ? rankVar.ToString() : "?";
                        if (!first) sb.Append(",");
                        first = false;
                        // Extract Resource cost (Resources.RawValues : Dict<ResourceTypeId, double>)
                        var price = Prop(r, "Price");
                        var rvBuilder = new StringBuilder();
                        rvBuilder.Append("{");
                        bool firstRv = true;
                        if (price != null)
                        {
                            try
                            {
                                var rawDict = Prop(price, "RawValues");
                                if (rawDict != null)
                                {
                                    var rvEntries = Prop(rawDict, "_entries");
                                    int rvLen = rvEntries != null ? IntProp(rvEntries, "Length") : 0;
                                    int rvCount = IntProp(rawDict, "Count");
                                    var rvGet = rvEntries?.GetType().GetMethod("get_Item", new[] { typeof(int) })
                                                ?? rvEntries?.GetType().GetProperty("Item")?.GetGetMethod();
                                    int rvFound = 0;
                                    for (int j = 0; j < rvLen && rvFound < rvCount; j++)
                                    {
                                        var rve = rvGet.Invoke(rvEntries, new object[] { j });
                                        if (rve == null) continue;
                                        var rk = Prop(rve, "key");
                                        var rv = Prop(rve, "value");
                                        if (rk == null || rv == null) continue;
                                        rvFound++;
                                        string keyName = rk.ToString();
                                        double valNum = 0;
                                        try { valNum = Convert.ToDouble(rv); } catch { }
                                        if (!firstRv) rvBuilder.Append(",");
                                        firstRv = false;
                                        rvBuilder.Append("\"").Append(Esc(keyName)).Append("\":")
                                                 .Append(valNum.ToString("0.####",
                                                    System.Globalization.CultureInfo.InvariantCulture));
                                    }
                                }
                            }
                            catch { }
                        }
                        rvBuilder.Append("}");

                        sb.Append("{\"recipe_id\":").Append(recipeId)
                          .Append(",\"set_id\":").Append(setId)
                          .Append(",\"set_kind\":\"").Append(Esc(setName))
                          .Append("\",\"rank_variation\":\"").Append(Esc(rankName))
                          .Append("\",\"price\":").Append(rvBuilder.ToString())
                          .Append("}");
                        if (setId > 0) seenSets.Add(setId);
                    }
                    sb.Append("],\"unique_set_ids\":[");
                    AppendIntList(sb, seenSets);
                    sb.Append("]");
                }
                else
                {
                    sb.Append("],\"unique_set_ids\":[]");
                }
            }
            catch (Exception ex) { return "{\"error\":\"forge walk: " + Esc(ex.Message) + "\"}"; }
            sb.Append("}");
            return sb.ToString();
        }

        // /masteries-truth — dumps all 66 mastery types + per-id stat bonuses
        // for the 13 stat masteries in MasteryBonusById. Conditional masteries
        // (Warmaster etc.) are emitted with a stat_bonus=null; their effects
        // live in tools/raid_data.py keyed by mastery id. See plan §masteries.
        private string GetMasteriesTruth()
        {
            var sd = Prop(GetAppModel(), "StaticData");
            if (sd == null) return "{\"error\":\"appmodel/staticdata not ready\"}";
            var md = Prop(sd, "MasteryData");
            if (md == null) return "{\"error\":\"StaticData.MasteryData null\"}";

            // Stat-bonus map: mastery_id → {stat, value, absolute}
            var bonusMap = new Dictionary<int, string>();
            try
            {
                var bd = Prop(md, "MasteryBonusById");
                if (bd != null)
                {
                    var entries = Prop(bd, "_entries");
                    int n = entries != null ? IntProp(entries, "Length") : 0;
                    var get = entries?.GetType().GetMethod("get_Item", new[] { typeof(int) })
                              ?? entries?.GetType().GetProperty("Item")?.GetGetMethod();
                    int dictCount = IntProp(bd, "Count");
                    int found = 0;
                    for (int i = 0; i < n && found < dictCount; i++)
                    {
                        var e = get.Invoke(entries, new object[] { i });
                        if (e == null) continue;
                        // Il2Cpp Dictionary<int, T>: .key reflection returns a
                        // garbage pointer; the actual int key lives in
                        // .hashCode (since hash(int)==int).
                        int key = IntProp(e, "hashCode");
                        if (key <= 0) continue;
                        var v = Prop(e, "value");
                        if (v == null) continue;
                        found++;
                        var stat = Prop(v, "StatKindId");
                        var val = Prop(v, "Value");
                        var abs = Prop(v, "IsAbsolute");
                        // Plarium.Common.Numerics.Fixed — has a Value or
                        // _value field; ToString() yields a parseable
                        // number like "75.000".
                        double valNum = 0;
                        if (val != null)
                        {
                            try { valNum = Convert.ToDouble(val); }
                            catch
                            {
                                if (!double.TryParse(val.ToString(), System.Globalization.NumberStyles.Any, System.Globalization.CultureInfo.InvariantCulture, out valNum))
                                    valNum = 0;
                            }
                        }
                        var sb2 = new StringBuilder();
                        sb2.Append("{\"stat\":\"").Append(Esc(stat?.ToString() ?? ""))
                           .Append("\",\"value\":").Append(valNum.ToString("0.####", System.Globalization.CultureInfo.InvariantCulture))
                           .Append(",\"absolute\":").Append((abs is bool ab && ab) ? "true" : "false").Append("}");
                        bonusMap[key] = sb2.ToString();
                    }
                }
            }
            catch (Exception ex) { return "{\"error\":\"bonus walk: " + Esc(ex.Message) + "\"}"; }

            var sb = new StringBuilder(8192);
            sb.Append("{\"masteries\":[");
            try
            {
                var types = Prop(md, "MasteryTypes");
                int n = IntProp(types, "_size");
                var items = Prop(types, "_items");
                var get = items?.GetType().GetMethod("get_Item", new[] { typeof(int) })
                          ?? items?.GetType().GetProperty("Item")?.GetGetMethod();
                bool first = true;
                for (int i = 0; i < n; i++)
                {
                    var m = get.Invoke(items, new object[] { i });
                    if (m == null) continue;
                    int id = IntProp(m, "Id");
                    if (id == 0) continue;
                    var tree = Prop(m, "TreeId");
                    int row = IntProp(m, "Row");
                    int col = IntProp(m, "Column");
                    if (!first) sb.Append(",");
                    first = false;
                    sb.Append("{\"id\":").Append(id)
                      .Append(",\"tree\":\"").Append(Esc(tree?.ToString() ?? "?"))
                      .Append("\",\"row\":").Append(row)
                      .Append(",\"col\":").Append(col);
                    if (bonusMap.TryGetValue(id, out var bj))
                        sb.Append(",\"stat_bonus\":").Append(bj);
                    sb.Append("}");
                }
            }
            catch (Exception ex) { return "{\"error\":\"mastery walk: " + Esc(ex.Message) + "\"}"; }
            sb.Append("]}");
            return sb.ToString();
        }

        // /blessings-truth — dumps the 30 blessings with per-grade bonuses.
        // BlessingBonus carries SkillTypeId / StatKindIds / Description; numeric
        // stat values for stat-bonus blessings come from BlessingStatsByRarity.
        // Skill-modifier blessings need hand-coded logic per blessing id.
        private string GetBlessingsTruth()
        {
            var sd = Prop(GetAppModel(), "StaticData");
            if (sd == null) return "{\"error\":\"appmodel/staticdata not ready\"}";
            var dad = Prop(sd, "DoubleAscendData");
            if (dad == null) return "{\"error\":\"StaticData.DoubleAscendData null\"}";

            var sb = new StringBuilder(16384);
            sb.Append("{\"blessings\":[");
            try
            {
                var list = Prop(dad, "Blessings");
                int n = IntProp(list, "_size");
                var items = Prop(list, "_items");
                var get = items?.GetType().GetMethod("get_Item", new[] { typeof(int) })
                          ?? items?.GetType().GetProperty("Item")?.GetGetMethod();
                bool first = true;
                for (int i = 0; i < n; i++)
                {
                    var b = get.Invoke(items, new object[] { i });
                    if (b == null) continue;
                    var idObj = Prop(b, "Id");
                    var rarity = Prop(b, "Rarity");
                    var divinity = Prop(b, "DivinityId");
                    if (!first) sb.Append(",");
                    first = false;
                    sb.Append("{\"id\":\"").Append(Esc(idObj?.ToString() ?? "?"))
                      .Append("\",\"rarity\":\"").Append(Esc(rarity?.ToString() ?? "?"))
                      .Append("\",\"divinity\":\"").Append(Esc(divinity?.ToString() ?? "?"))
                      .Append("\",\"grade_bonuses\":[");
                    // Walk GradeBonuses dict (DoubleAscendGrade → BlessingBonus)
                    bool gFirst = true;
                    int gradeIdx = 0;
                    try
                    {
                        var gb = Prop(b, "GradeBonuses");
                        var entries = Prop(gb, "_entries");
                        int gn = entries != null ? IntProp(entries, "Length") : 0;
                        var gget = entries?.GetType().GetMethod("get_Item", new[] { typeof(int) })
                                   ?? entries?.GetType().GetProperty("Item")?.GetGetMethod();
                        for (int j = 0; j < gn; j++)
                        {
                            var ge = gget.Invoke(entries, new object[] { j });
                            if (ge == null) continue;
                            var gv = Prop(ge, "value");
                            if (gv == null) continue;
                            var skillId = Prop(gv, "SkillTypeId");
                            var statKinds = Prop(gv, "StatKindIds");
                            int statCount = statKinds != null ? IntProp(statKinds, "_size") : 0;
                            if (!gFirst) sb.Append(",");
                            gFirst = false;
                            sb.Append("{\"grade_index\":").Append(gradeIdx);
                            gradeIdx++;
                            // Nullable<int>.HasValue + .Value. Skip 0 — that's
                            // Plarium's sentinel for "no skill modifier"; only
                            // emit when the blessing actually targets a skill.
                            if (skillId != null)
                            {
                                try
                                {
                                    var hv = skillId.GetType().GetProperty("HasValue");
                                    bool has = hv != null && (bool)hv.GetValue(skillId);
                                    if (has)
                                    {
                                        var vv = skillId.GetType().GetProperty("Value")?.GetValue(skillId);
                                        int sid = vv != null ? Convert.ToInt32(vv) : 0;
                                        if (sid > 0)
                                            sb.Append(",\"skill_type_id\":").Append(sid);
                                    }
                                }
                                catch { }
                            }
                            if (statCount > 0)
                            {
                                sb.Append(",\"stat_kinds\":[");
                                bool sFirst = true;
                                var sItems = Prop(statKinds, "_items");
                                var sget = sItems?.GetType().GetMethod("get_Item", new[] { typeof(int) })
                                           ?? sItems?.GetType().GetProperty("Item")?.GetGetMethod();
                                for (int k = 0; k < statCount; k++)
                                {
                                    var s = sget.Invoke(sItems, new object[] { k });
                                    if (!sFirst) sb.Append(",");
                                    sFirst = false;
                                    sb.Append("\"").Append(Esc(s?.ToString() ?? "?")).Append("\"");
                                }
                                sb.Append("]");
                            }
                            sb.Append("}");
                        }
                    }
                    catch { }
                    sb.Append("]}");
                }
            }
            catch (Exception ex) { return "{\"error\":\"blessing walk: " + Esc(ex.Message) + "\"}"; }
            sb.Append("]}");
            return sb.ToString();
        }

        // /hero-types — pristine base-stat profile per HeroType row.
        //   id, name, fraction, rarity, ascend_level, base_id, default_element,
        //   default_role, is_boss, base_stats {hp, atk, def, spd, res, acc, cr,
        //   cd, ch, ignore_def, weight}, skill_ids[], leader_skills[].
        // Skips bloat (AscendMaterials Resources struct, 100+ zero-valued fields).
        // Each row is small — full ~2k entries fits well under 5MB JSON.
        private string GetHeroTypes()
        {
            var sd = Prop(GetAppModel(), "StaticData");
            if (sd == null) return "{\"error\":\"appmodel/staticdata not ready\"}";
            var hd = Prop(sd, "HeroData");
            if (hd == null) return "{\"error\":\"StaticData.HeroData null\"}";
            var types = Prop(hd, "HeroTypes");
            if (types == null) return "{\"error\":\"HeroData.HeroTypes null\"}";

            var sb = new StringBuilder(1 << 18);
            sb.Append("{\"hero_types\":[");
            try
            {
                int n = IntProp(types, "_size");
                var items = Prop(types, "_items");
                var get = items?.GetType().GetMethod("get_Item", new[] { typeof(int) })
                          ?? items?.GetType().GetProperty("Item")?.GetGetMethod();
                if (get == null) return "{\"error\":\"HeroTypes._items has no indexer\"}";
                bool first = true;
                for (int i = 0; i < n; i++)
                {
                    var h = get.Invoke(items, new object[] { i });
                    if (h == null) continue;
                    int id = IntProp(h, "Id");
                    if (id == 0) continue;
                    var fraction = Prop(h, "Fraction");
                    var rarity = Prop(h, "Rarity");
                    var elem = Prop(h, "DefaultElement");
                    var role = Prop(h, "DefaultRole");
                    int baseId = IntProp(h, "BaseId");
                    int ascend = IntProp(h, "AscendLevel");
                    bool isBoss = false; try { isBoss = (bool)Prop(h, "IsBoss"); } catch { }
                    bool isMax = false; try { isMax = (bool)Prop(h, "IsMaxAscended"); } catch { }
                    string name = "?";
                    var nameLs = Prop(h, "Name");
                    if (nameLs != null)
                    {
                        var nv = Prop(nameLs, "DefaultValue");
                        if (nv != null) name = nv.ToString();
                    }
                    if (!first) sb.Append(",");
                    first = false;
                    sb.Append("{\"id\":").Append(id)
                      .Append(",\"name\":\"").Append(Esc(name))
                      .Append("\",\"fraction\":\"").Append(Esc(fraction?.ToString() ?? "?"))
                      .Append("\",\"rarity\":\"").Append(Esc(rarity?.ToString() ?? "?"))
                      .Append("\",\"element\":\"").Append(Esc(elem?.ToString() ?? "?"))
                      .Append("\",\"role\":\"").Append(Esc(role?.ToString() ?? "?"))
                      .Append("\",\"ascend_level\":").Append(ascend)
                      .Append(",\"base_id\":").Append(baseId)
                      .Append(",\"is_boss\":").Append(isBoss ? "true" : "false")
                      .Append(",\"is_max_ascended\":").Append(isMax ? "true" : "false");

                    // base_stats
                    var bs = Prop(h, "DefaultBaseStats");
                    if (bs != null)
                    {
                        sb.Append(",\"base_stats\":{")
                          .Append("\"hp\":").Append(StatNum(bs, "Health"))
                          .Append(",\"atk\":").Append(StatNum(bs, "Attack"))
                          .Append(",\"def\":").Append(StatNum(bs, "Defence"))
                          .Append(",\"spd\":").Append(StatNum(bs, "Speed"))
                          .Append(",\"res\":").Append(StatNum(bs, "Resistance"))
                          .Append(",\"acc\":").Append(StatNum(bs, "Accuracy"))
                          .Append(",\"cr\":").Append(StatNum(bs, "CriticalChance"))
                          .Append(",\"cd\":").Append(StatNum(bs, "CriticalDamage"))
                          .Append(",\"ch\":").Append(StatNum(bs, "CriticalHeal"))
                          .Append(",\"ignore_def\":").Append(StatNum(bs, "IgnoreDefence"))
                          .Append(",\"weight\":").Append(StatNum(bs, "Weight"))
                          .Append("}");
                    }

                    // skill ids
                    var skillIds = Prop(h, "DefaultSkillTypeIds");
                    if (skillIds != null)
                    {
                        sb.Append(",\"skill_ids\":[");
                        try
                        {
                            int sn = IntProp(skillIds, "_size");
                            var sitems = Prop(skillIds, "_items");
                            var sget = sitems?.GetType().GetMethod("get_Item", new[] { typeof(int) })
                                       ?? sitems?.GetType().GetProperty("Item")?.GetGetMethod();
                            for (int k = 0; k < sn; k++)
                            {
                                if (k > 0) sb.Append(",");
                                sb.Append(IntFrom(sget.Invoke(sitems, new object[] { k })));
                            }
                        }
                        catch { }
                        sb.Append("]");
                    }

                    // leader skills
                    var leaders = Prop(h, "AllLeaderSkills");
                    if (leaders != null)
                    {
                        sb.Append(",\"leader_skills\":[");
                        try
                        {
                            int ln = IntProp(leaders, "_size");
                            var litems = Prop(leaders, "_items");
                            var lget = litems?.GetType().GetMethod("get_Item", new[] { typeof(int) })
                                       ?? litems?.GetType().GetProperty("Item")?.GetGetMethod();
                            bool lf = true;
                            for (int k = 0; k < ln; k++)
                            {
                                var ls = lget.Invoke(litems, new object[] { k });
                                if (ls == null) continue;
                                var stat = Prop(ls, "StatKindId");
                                bool abs = false; try { abs = (bool)Prop(ls, "IsAbsolute"); } catch { }
                                double amt = TryGetDouble(ls, "Amount", 0);
                                int amtI = (int)TryGetDouble(ls, "GetAmount", 0);
                                if (!lf) sb.Append(",");
                                lf = false;
                                sb.Append("{\"stat\":\"").Append(Esc(stat?.ToString() ?? "?"))
                                  .Append("\",\"amount\":").Append(amt.ToString("0.######", System.Globalization.CultureInfo.InvariantCulture))
                                  .Append(",\"amount_int\":").Append(amtI)
                                  .Append(",\"absolute\":").Append(abs ? "true" : "false")
                                  .Append("}");
                            }
                        }
                        catch { }
                        sb.Append("]");
                    }

                    sb.Append("}");
                }
            }
            catch (Exception ex) { return "{\"error\":\"hero-type walk: " + Esc(ex.Message) + "\"}"; }
            sb.Append("]}");
            return sb.ToString();
        }

        // /cb-bosses — per-stage boss stat profiles for CB / Hydra / Chimera /
        // DT-bosses. Walks StageData.Stages and emits any stage where any
        // HeroSlotsSetup row has IsHeroBoss==true OR IsMainBoss==true. For each
        // boss, joins to HeroData.HeroTypes for the base stats. Adds Modifiers
        // (per-round Accuracy/Resistance scalers) which the live game applies
        // on top of the boss's base.
        private string GetCbBosses()
        {
            var sd = Prop(GetAppModel(), "StaticData");
            if (sd == null) return "{\"error\":\"appmodel/staticdata not ready\"}";
            var sgd = Prop(sd, "StageData");
            var hd = Prop(sd, "HeroData");
            if (sgd == null || hd == null) return "{\"error\":\"StageData/HeroData null\"}";
            var stages = Prop(sgd, "Stages");
            if (stages == null) return "{\"error\":\"StageData.Stages null\"}";

            // Build a HeroType lookup table: id -> HeroType.
            var heroById = new Dictionary<int, object>();
            try
            {
                var types = Prop(hd, "HeroTypes");
                int hn = IntProp(types, "_size");
                var hitems = Prop(types, "_items");
                var hget = hitems?.GetType().GetMethod("get_Item", new[] { typeof(int) })
                           ?? hitems?.GetType().GetProperty("Item")?.GetGetMethod();
                for (int i = 0; i < hn; i++)
                {
                    var h = hget.Invoke(hitems, new object[] { i });
                    if (h == null) continue;
                    int hid = IntProp(h, "Id");
                    if (hid > 0 && !heroById.ContainsKey(hid)) heroById[hid] = h;
                }
            }
            catch (Exception ex) { return "{\"error\":\"hero index: " + Esc(ex.Message) + "\"}"; }

            var sb = new StringBuilder(1 << 16);
            sb.Append("{\"stages\":[");
            try
            {
                int n = IntProp(stages, "_size");
                var sitems = Prop(stages, "_items");
                var sget = sitems?.GetType().GetMethod("get_Item", new[] { typeof(int) })
                           ?? sitems?.GetType().GetProperty("Item")?.GetGetMethod();
                bool first = true;
                for (int i = 0; i < n; i++)
                {
                    var stage = sget.Invoke(sitems, new object[] { i });
                    if (stage == null) continue;
                    bool hasBoss = false; try { hasBoss = (bool)Prop(stage, "HasBoss"); } catch { }
                    bool hasDouble = false; try { hasDouble = (bool)Prop(stage, "HasDoubleBoss"); } catch { }
                    if (!hasBoss && !hasDouble) continue;
                    int stageId = IntProp(stage, "Id");
                    var diff = Prop(stage, "Difficulty");
                    var area = Prop(stage, "Area");
                    var region = Prop(stage, "Region");
                    string areaId = "?", regionId = "?";
                    try { areaId = Prop(area, "Id")?.ToString() ?? "?"; } catch { }
                    try { regionId = Prop(region, "Id")?.ToString() ?? "?"; } catch { }

                    // Find boss heroes in formations (any IsHeroBoss/IsMainBoss row).
                    var bossList = new List<(int round, int slot, int heroTypeId, int level, string grade, bool main)>();
                    var formations = Prop(stage, "Formations");
                    if (formations != null)
                    {
                        try
                        {
                            int fn = IntProp(formations, "_size");
                            var fitems = Prop(formations, "_items");
                            var fget = fitems?.GetType().GetMethod("get_Item", new[] { typeof(int) })
                                       ?? fitems?.GetType().GetProperty("Item")?.GetGetMethod();
                            for (int f = 0; f < fn; f++)
                            {
                                var formation = fget.Invoke(fitems, new object[] { f });
                                if (formation == null) continue;
                                var setup = Prop(formation, "HeroSlotsSetup");
                                if (setup == null) continue;
                                int hn = IntProp(setup, "_size");
                                var hitems = Prop(setup, "_items");
                                var hget = hitems?.GetType().GetMethod("get_Item", new[] { typeof(int) })
                                           ?? hitems?.GetType().GetProperty("Item")?.GetGetMethod();
                                for (int h = 0; h < hn; h++)
                                {
                                    var slot = hget.Invoke(hitems, new object[] { h });
                                    if (slot == null) continue;
                                    bool hb = false; try { hb = (bool)Prop(slot, "IsHeroBoss"); } catch { }
                                    bool mb = false; try { mb = (bool)Prop(slot, "IsMainBoss"); } catch { }
                                    if (!hb && !mb) continue;
                                    int round = IntProp(slot, "Round");
                                    int slotN = IntProp(slot, "Slot");
                                    int htId = IntProp(slot, "HeroTypeId");
                                    int lvl = IntProp(slot, "Level");
                                    string grade = Prop(slot, "Grade")?.ToString() ?? "?";
                                    bossList.Add((round, slotN, htId, lvl, grade, mb));
                                }
                            }
                        }
                        catch { }
                    }
                    if (bossList.Count == 0) continue;

                    // Modifiers (per-round flat-stat modifiers, e.g. CB UNM Acc/Res).
                    var modList = new List<(int round, string stat, double val, bool absolute, bool bossOnly)>();
                    var mods = Prop(stage, "Modifiers");
                    if (mods != null)
                    {
                        try
                        {
                            int mn = IntProp(mods, "_size");
                            var mitems = Prop(mods, "_items");
                            var mget = mitems?.GetType().GetMethod("get_Item", new[] { typeof(int) })
                                       ?? mitems?.GetType().GetProperty("Item")?.GetGetMethod();
                            for (int m = 0; m < mn; m++)
                            {
                                var mod = mget.Invoke(mitems, new object[] { m });
                                if (mod == null) continue;
                                int round = IntProp(mod, "Round");
                                string stat = Prop(mod, "KindId")?.ToString() ?? "?";
                                double val = TryGetDouble(mod, "Value", 0);
                                bool abs = false; try { abs = (bool)Prop(mod, "IsAbsolute"); } catch { }
                                bool bo = false; try { bo = (bool)Prop(mod, "BossOnly"); } catch { }
                                modList.Add((round, stat, val, abs, bo));
                            }
                        }
                        catch { }
                    }

                    if (!first) sb.Append(",");
                    first = false;
                    sb.Append("{\"stage_id\":").Append(stageId)
                      .Append(",\"area\":\"").Append(Esc(areaId))
                      .Append("\",\"region\":\"").Append(Esc(regionId))
                      .Append("\",\"difficulty\":\"").Append(Esc(diff?.ToString() ?? "?"))
                      .Append("\",\"bosses\":[");
                    bool bf = true;
                    foreach (var b in bossList)
                    {
                        if (!bf) sb.Append(",");
                        bf = false;
                        sb.Append("{\"round\":").Append(b.round)
                          .Append(",\"slot\":").Append(b.slot)
                          .Append(",\"hero_type_id\":").Append(b.heroTypeId)
                          .Append(",\"level\":").Append(b.level)
                          .Append(",\"grade\":\"").Append(Esc(b.grade))
                          .Append("\",\"is_main\":").Append(b.main ? "true" : "false");
                        // Resolve base stats from HeroType.
                        if (heroById.TryGetValue(b.heroTypeId, out var ht))
                        {
                            string name = "?";
                            try { name = Prop(Prop(ht, "Name"), "DefaultValue")?.ToString() ?? "?"; } catch { }
                            string elem = Prop(ht, "DefaultElement")?.ToString() ?? "?";
                            sb.Append(",\"name\":\"").Append(Esc(name))
                              .Append("\",\"element\":\"").Append(Esc(elem)).Append("\"");
                            var bs = Prop(ht, "DefaultBaseStats");
                            if (bs != null)
                            {
                                sb.Append(",\"base_stats\":{")
                                  .Append("\"hp\":").Append(StatNum(bs, "Health"))
                                  .Append(",\"atk\":").Append(StatNum(bs, "Attack"))
                                  .Append(",\"def\":").Append(StatNum(bs, "Defence"))
                                  .Append(",\"spd\":").Append(StatNum(bs, "Speed"))
                                  .Append(",\"res\":").Append(StatNum(bs, "Resistance"))
                                  .Append(",\"acc\":").Append(StatNum(bs, "Accuracy"))
                                  .Append(",\"cr\":").Append(StatNum(bs, "CriticalChance"))
                                  .Append(",\"cd\":").Append(StatNum(bs, "CriticalDamage"))
                                  .Append("}");
                            }
                        }
                        sb.Append("}");
                    }
                    sb.Append("],\"modifiers\":[");
                    bool mf = true;
                    foreach (var m in modList)
                    {
                        if (!mf) sb.Append(",");
                        mf = false;
                        sb.Append("{\"round\":").Append(m.round)
                          .Append(",\"stat\":\"").Append(Esc(m.stat))
                          .Append("\",\"value\":").Append(m.val.ToString("0.####", System.Globalization.CultureInfo.InvariantCulture))
                          .Append(",\"absolute\":").Append(m.absolute ? "true" : "false")
                          .Append(",\"boss_only\":").Append(m.bossOnly ? "true" : "false")
                          .Append("}");
                    }
                    sb.Append("]}");
                }
            }
            catch (Exception ex) { return "{\"error\":\"stage walk: " + Esc(ex.Message) + "\"}"; }
            sb.Append("]}");
            return sb.ToString();
        }

        // /alliance-bosses — CB boss profile per difficulty.
        //   AllianceData.BossTypes is a 6-row list (Easy/Normal/Hard/Brutal/
        //   Nightmare/UltraNightmare). Each row carries Health, HeroTypeId,
        //   Level. We join to HeroData.HeroTypes for ATK/DEF/SPD/RES/ACC/CR/CD
        //   base stats. Replaces hardcoded CB_ATK/UNM_DEF/CB_SPEED constants.
        private string GetAllianceBosses()
        {
            var sd = Prop(GetAppModel(), "StaticData");
            if (sd == null) return "{\"error\":\"appmodel/staticdata not ready\"}";
            var ad = Prop(sd, "AllianceData");
            var hd = Prop(sd, "HeroData");
            if (ad == null || hd == null) return "{\"error\":\"AllianceData/HeroData null\"}";
            var bossTypes = Prop(ad, "BossTypes");
            if (bossTypes == null) return "{\"error\":\"AllianceData.BossTypes null\"}";

            // Build hero type lookup.
            var heroById = new Dictionary<int, object>();
            try
            {
                var types = Prop(hd, "HeroTypes");
                int hn = IntProp(types, "_size");
                var hitems = Prop(types, "_items");
                var hget = hitems?.GetType().GetMethod("get_Item", new[] { typeof(int) })
                           ?? hitems?.GetType().GetProperty("Item")?.GetGetMethod();
                for (int i = 0; i < hn; i++)
                {
                    var h = hget.Invoke(hitems, new object[] { i });
                    if (h == null) continue;
                    int hid = IntProp(h, "Id");
                    if (hid > 0 && !heroById.ContainsKey(hid)) heroById[hid] = h;
                }
            }
            catch (Exception ex) { return "{\"error\":\"hero index: " + Esc(ex.Message) + "\"}"; }

            var sb = new StringBuilder(2048);
            sb.Append("{\"bosses\":[");
            try
            {
                int n = IntProp(bossTypes, "_size");
                var items = Prop(bossTypes, "_items");
                var get = items?.GetType().GetMethod("get_Item", new[] { typeof(int) })
                          ?? items?.GetType().GetProperty("Item")?.GetGetMethod();
                bool first = true;
                for (int i = 0; i < n; i++)
                {
                    var bt = get.Invoke(items, new object[] { i });
                    if (bt == null) continue;
                    string diffId = Prop(bt, "Id")?.ToString() ?? "?";
                    long hp = 0;
                    try { hp = Convert.ToInt64(Prop(bt, "Health")); } catch { }
                    int htId = IntProp(bt, "HeroTypeId");
                    int lvl = IntProp(bt, "Level");
                    if (!first) sb.Append(",");
                    first = false;
                    sb.Append("{\"difficulty\":\"").Append(Esc(diffId))
                      .Append("\",\"hp\":").Append(hp)
                      .Append(",\"hero_type_id\":").Append(htId)
                      .Append(",\"level\":").Append(lvl);
                    if (heroById.TryGetValue(htId, out var ht))
                    {
                        string name = "?";
                        try { name = Prop(Prop(ht, "Name"), "DefaultValue")?.ToString() ?? "?"; } catch { }
                        string elem = Prop(ht, "DefaultElement")?.ToString() ?? "?";
                        sb.Append(",\"name\":\"").Append(Esc(name))
                          .Append("\",\"element\":\"").Append(Esc(elem)).Append("\"");
                        var bs = Prop(ht, "DefaultBaseStats");
                        if (bs != null)
                        {
                            sb.Append(",\"base_stats\":{")
                              .Append("\"hp_base\":").Append(StatNum(bs, "Health"))
                              .Append(",\"atk\":").Append(StatNum(bs, "Attack"))
                              .Append(",\"def\":").Append(StatNum(bs, "Defence"))
                              .Append(",\"spd\":").Append(StatNum(bs, "Speed"))
                              .Append(",\"res\":").Append(StatNum(bs, "Resistance"))
                              .Append(",\"acc\":").Append(StatNum(bs, "Accuracy"))
                              .Append(",\"cr\":").Append(StatNum(bs, "CriticalChance"))
                              .Append(",\"cd\":").Append(StatNum(bs, "CriticalDamage"))
                              .Append("}");
                        }
                        // Skill ids for the boss (so consumers can look up skill text).
                        var skillIds = Prop(ht, "DefaultSkillTypeIds");
                        if (skillIds != null)
                        {
                            sb.Append(",\"skill_ids\":[");
                            try
                            {
                                int sn = IntProp(skillIds, "_size");
                                var sitems = Prop(skillIds, "_items");
                                var sget = sitems?.GetType().GetMethod("get_Item", new[] { typeof(int) })
                                           ?? sitems?.GetType().GetProperty("Item")?.GetGetMethod();
                                for (int k = 0; k < sn; k++)
                                {
                                    if (k > 0) sb.Append(",");
                                    sb.Append(IntFrom(sget.Invoke(sitems, new object[] { k })));
                                }
                            }
                            catch { }
                            sb.Append("]");
                        }
                    }
                    sb.Append("}");
                }
            }
            catch (Exception ex) { return "{\"error\":\"boss walk: " + Esc(ex.Message) + "\"}"; }
            sb.Append("]}");
            return sb.ToString();
        }

        // /artifact-sets-truth — clean SetInfo records with both StatBonus and
        // SkillBonus expanded. SkillBonus.SkillTypeId is dereferenced through
        // SkillData.SkillTypeById to give consumers the proc effect at first
        // level: Group, Cooldown, Effects[]{KindId, Condition, MultiplierFormula,
        // Phases}. Replaces the "+0% ?" rows in artifact_sets.json with
        // structured proc data.
        private string GetArtifactSetsTruth()
        {
            var sd = Prop(GetAppModel(), "StaticData");
            if (sd == null) return "{\"error\":\"appmodel/staticdata not ready\"}";
            var ad = Prop(sd, "ArtifactData");
            var skd = Prop(sd, "SkillData");
            if (ad == null || skd == null) return "{\"error\":\"ArtifactData/SkillData null\"}";
            var setInfos = Prop(ad, "SetInfos");
            if (setInfos == null) return "{\"error\":\"ArtifactData.SetInfos null\"}";

            // Build a SkillType lookup: id -> SkillType (for proc deref).
            var skillById = new Dictionary<int, object>();
            try
            {
                var stTypes = Prop(skd, "SkillTypes");
                if (stTypes != null)
                {
                    int sn = IntProp(stTypes, "_size");
                    var sitems = Prop(stTypes, "_items");
                    var sget = sitems?.GetType().GetMethod("get_Item", new[] { typeof(int) })
                               ?? sitems?.GetType().GetProperty("Item")?.GetGetMethod();
                    for (int i = 0; i < sn; i++)
                    {
                        var s = sget.Invoke(sitems, new object[] { i });
                        if (s == null) continue;
                        int sid = IntProp(s, "Id");
                        if (sid > 0) skillById[sid] = s;
                    }
                }
            }
            catch { /* best-effort; we'll emit SkillTypeId without deref */ }

            var sb = new StringBuilder(1 << 14);
            sb.Append("{\"sets\":[");
            try
            {
                int n = IntProp(setInfos, "_size");
                var items = Prop(setInfos, "_items");
                var get = items?.GetType().GetMethod("get_Item", new[] { typeof(int) })
                          ?? items?.GetType().GetProperty("Item")?.GetGetMethod();
                bool first = true;
                for (int i = 0; i < n; i++)
                {
                    var si = get.Invoke(items, new object[] { i });
                    if (si == null) continue;
                    string kindId = Prop(si, "ArtifactSetKindId")?.ToString() ?? "?";
                    int pieces = IntProp(si, "ArtifactCount");
                    int maxPieces = IntProp(si, "MaxArtifactCount");
                    if (!first) sb.Append(",");
                    first = false;
                    // Numeric set ID — extract from the localization key
                    // ("l10n:artifact-set/name?id=4#static" → 4). The same int
                    // is what the artifact-on-hero `set` field carries.
                    int numericId = 0;
                    try
                    {
                        var nameLs = Prop(si, "Name");
                        var key = Prop(nameLs, "Key")?.ToString() ?? "";
                        var m = System.Text.RegularExpressions.Regex.Match(key, "id=(\\d+)");
                        if (m.Success) int.TryParse(m.Groups[1].Value, out numericId);
                    }
                    catch { }
                    sb.Append("{\"id\":").Append(numericId)
                      .Append(",\"set\":\"").Append(Esc(kindId))
                      .Append("\",\"pieces\":").Append(pieces)
                      .Append(",\"max_pieces\":").Append(maxPieces);

                    // StatBonus block — singular for simple sets, list for
                    // combo sets like AccuracyAndSpeed (StatBonuses: list).
                    // Always emit as a list under "stat_bonuses" for uniform
                    // consumer handling; also keep "stat_bonus" alias for the
                    // first entry for back-compat.
                    var bonusList = new List<(string stat, double val, bool abs)>();
                    var statBonus = Prop(si, "StatBonus");
                    if (statBonus != null)
                    {
                        string stat = Prop(statBonus, "StatKindId")?.ToString() ?? "?";
                        double val = TryGetDouble(statBonus, "Value", 0);
                        bool abs = false; try { abs = (bool)Prop(statBonus, "IsAbsolute"); } catch { }
                        if (stat != "?") bonusList.Add((stat, val, abs));
                    }
                    var statBonuses = Prop(si, "StatBonuses");
                    if (statBonuses != null)
                    {
                        try
                        {
                            int bn = IntProp(statBonuses, "_size");
                            var bitems = Prop(statBonuses, "_items");
                            var bget = bitems?.GetType().GetMethod("get_Item", new[] { typeof(int) })
                                       ?? bitems?.GetType().GetProperty("Item")?.GetGetMethod();
                            for (int b = 0; b < bn; b++)
                            {
                                var bonus = bget.Invoke(bitems, new object[] { b });
                                if (bonus == null) continue;
                                string stat = Prop(bonus, "StatKindId")?.ToString() ?? "?";
                                double val = TryGetDouble(bonus, "Value", 0);
                                bool abs = false; try { abs = (bool)Prop(bonus, "IsAbsolute"); } catch { }
                                if (stat != "?") bonusList.Add((stat, val, abs));
                            }
                        }
                        catch { }
                    }
                    if (bonusList.Count > 0)
                    {
                        sb.Append(",\"stat_bonuses\":[");
                        for (int b = 0; b < bonusList.Count; b++)
                        {
                            if (b > 0) sb.Append(",");
                            sb.Append("{\"stat\":\"").Append(Esc(bonusList[b].stat))
                              .Append("\",\"value\":").Append(bonusList[b].val.ToString("0.######", System.Globalization.CultureInfo.InvariantCulture))
                              .Append(",\"absolute\":").Append(bonusList[b].abs ? "true" : "false")
                              .Append("}");
                        }
                        sb.Append("]");
                        // back-compat: also emit stat_bonus = first entry
                        sb.Append(",\"stat_bonus\":{\"stat\":\"").Append(Esc(bonusList[0].stat))
                          .Append("\",\"value\":").Append(bonusList[0].val.ToString("0.######", System.Globalization.CultureInfo.InvariantCulture))
                          .Append(",\"absolute\":").Append(bonusList[0].abs ? "true" : "false")
                          .Append("}");
                    }

                    // SubSetInfos — tiered relic sets like UnkillableAndSpdAndCrDmg
                    // (9 piece thresholds, each adds its own StatBonuses).
                    var subSetInfos = Prop(si, "SubSetInfos");
                    if (subSetInfos != null)
                    {
                        try
                        {
                            int sub_n = IntProp(subSetInfos, "_size");
                            var sub_items = Prop(subSetInfos, "_items");
                            var sub_get = sub_items?.GetType().GetMethod("get_Item", new[] { typeof(int) })
                                       ?? sub_items?.GetType().GetProperty("Item")?.GetGetMethod();
                            if (sub_n > 0)
                            {
                                sb.Append(",\"sub_sets\":[");
                                for (int s_i = 0; s_i < sub_n; s_i++)
                                {
                                    var sub = sub_get.Invoke(sub_items, new object[] { s_i });
                                    if (sub == null) continue;
                                    if (s_i > 0) sb.Append(",");
                                    string subId = Prop(sub, "SubSetId")?.ToString() ?? "?";
                                    int subPieces = IntProp(sub, "ArtifactCount");
                                    sb.Append("{\"sub_set_id\":\"").Append(Esc(subId))
                                      .Append("\",\"pieces\":").Append(subPieces);
                                    var subBonuses = Prop(sub, "StatBonuses");
                                    if (subBonuses != null)
                                    {
                                        try
                                        {
                                            int sbn = IntProp(subBonuses, "_size");
                                            var sbitems = Prop(subBonuses, "_items");
                                            var sbget = sbitems?.GetType().GetMethod("get_Item", new[] { typeof(int) })
                                                       ?? sbitems?.GetType().GetProperty("Item")?.GetGetMethod();
                                            sb.Append(",\"stat_bonuses\":[");
                                            bool sbf = true;
                                            for (int b = 0; b < sbn; b++)
                                            {
                                                var bonus = sbget.Invoke(sbitems, new object[] { b });
                                                if (bonus == null) continue;
                                                string stat = Prop(bonus, "StatKindId")?.ToString() ?? "?";
                                                double val = TryGetDouble(bonus, "Value", 0);
                                                bool abs = false; try { abs = (bool)Prop(bonus, "IsAbsolute"); } catch { }
                                                if (!sbf) sb.Append(",");
                                                sbf = false;
                                                sb.Append("{\"stat\":\"").Append(Esc(stat))
                                                  .Append("\",\"value\":").Append(val.ToString("0.######", System.Globalization.CultureInfo.InvariantCulture))
                                                  .Append(",\"absolute\":").Append(abs ? "true" : "false")
                                                  .Append("}");
                                            }
                                            sb.Append("]");
                                        }
                                        catch { }
                                    }
                                    // SubSet may also carry a SkillBonus (tiered procs).
                                    var subSkill = Prop(sub, "SkillBonus");
                                    if (subSkill != null)
                                    {
                                        int subSkillId = IntProp(subSkill, "SkillTypeId");
                                        sb.Append(",\"skill_type_id\":").Append(subSkillId);
                                    }
                                    sb.Append("}");
                                }
                                sb.Append("]");
                            }
                        }
                        catch { }
                    }

                    // SkillBonus block (new) — the proc that drives Stoneskin/
                    // Lifesteal/Stun/etc. Deref through SkillData when found.
                    var skillBonus = Prop(si, "SkillBonus");
                    if (skillBonus != null)
                    {
                        int skillTypeId = IntProp(skillBonus, "SkillTypeId");
                        sb.Append(",\"skill_bonus\":{\"skill_type_id\":").Append(skillTypeId);
                        if (skillById.TryGetValue(skillTypeId, out var skill))
                        {
                            string group = Prop(skill, "Group")?.ToString() ?? "?";
                            int cd = IntProp(skill, "Cooldown");
                            sb.Append(",\"group\":\"").Append(Esc(group))
                              .Append("\",\"cooldown\":").Append(cd)
                              .Append(",\"effects\":[");
                            // Walk skill.Effects[] — emit a compact form per effect.
                            var effs = Prop(skill, "Effects");
                            if (effs != null)
                            {
                                try
                                {
                                    int en = IntProp(effs, "_size");
                                    var eitems = Prop(effs, "_items");
                                    var eget = eitems?.GetType().GetMethod("get_Item", new[] { typeof(int) })
                                               ?? eitems?.GetType().GetProperty("Item")?.GetGetMethod();
                                    bool ef = true;
                                    for (int e = 0; e < en; e++)
                                    {
                                        var eff = eget.Invoke(eitems, new object[] { e });
                                        if (eff == null) continue;
                                        string kind = Prop(eff, "KindId")?.ToString() ?? "?";
                                        string egroup = Prop(eff, "Group")?.ToString() ?? "?";
                                        string mform = Prop(eff, "MultiplierFormula")?.ToString() ?? "";
                                        string cond = Prop(eff, "Condition")?.ToString() ?? "";
                                        int stack = IntProp(eff, "StackCount");
                                        if (!ef) sb.Append(",");
                                        ef = false;
                                        sb.Append("{\"kind\":\"").Append(Esc(kind))
                                          .Append("\",\"group\":\"").Append(Esc(egroup))
                                          .Append("\",\"stack\":").Append(stack)
                                          .Append(",\"formula\":\"").Append(Esc(mform))
                                          .Append("\",\"condition\":\"").Append(Esc(cond))
                                          .Append("\"");
                                        // Phases (when this effect triggers): AfterDamageDealt etc.
                                        var rel = Prop(eff, "Relation");
                                        if (rel != null)
                                        {
                                            var phases = Prop(rel, "Phases");
                                            if (phases != null)
                                            {
                                                try
                                                {
                                                    int pn = IntProp(phases, "_size");
                                                    var pitems = Prop(phases, "_items");
                                                    var pget = pitems?.GetType().GetMethod("get_Item", new[] { typeof(int) })
                                                               ?? pitems?.GetType().GetProperty("Item")?.GetGetMethod();
                                                    sb.Append(",\"phases\":[");
                                                    for (int p = 0; p < pn; p++)
                                                    {
                                                        if (p > 0) sb.Append(",");
                                                        var ph = pget.Invoke(pitems, new object[] { p });
                                                        sb.Append("\"").Append(Esc(ph?.ToString() ?? "?")).Append("\"");
                                                    }
                                                    sb.Append("]");
                                                }
                                                catch { }
                                            }
                                        }
                                        sb.Append("}");
                                    }
                                }
                                catch { }
                            }
                            sb.Append("]");
                        }
                        sb.Append("}");
                    }
                    sb.Append("}");
                }
            }
            catch (Exception ex) { return "{\"error\":\"sets walk: " + Esc(ex.Message) + "\"}"; }
            sb.Append("]}");
            return sb.ToString();
        }

        // Helper for emitting a numeric stat field; handles Plarium Fixed types
        // (via Convert.ToDouble) and falls back to ToString-parse for IL2CPP
        // wrappers that don't implement IConvertible cleanly.
        private static string StatNum(object holder, string fieldName)
        {
            var v = Prop(holder, fieldName);
            if (v == null) return "0";
            try { return Convert.ToDouble(v).ToString("0.######", System.Globalization.CultureInfo.InvariantCulture); }
            catch
            {
                if (double.TryParse(v.ToString(), System.Globalization.NumberStyles.Any,
                    System.Globalization.CultureInfo.InvariantCulture, out var d))
                    return d.ToString("0.######", System.Globalization.CultureInfo.InvariantCulture);
                return "0";
            }
        }

        private static int IntFrom(object v)
        {
            if (v == null) return 0;
            try { return Convert.ToInt32(v); } catch { }
            if (int.TryParse(v.ToString(), out int i)) return i;
            return 0;
        }

        private static void EmitRegion(StringBuilder sb, ref bool firstRegion,
            object region, object idVal, int rid, Dictionary<int, object> stageById)
        {
            string regionName = idVal.ToString();
            // Walk StageIdsByDifficulty._entries directly. The key field is an
            // Il2Cpp value-typed enum (DifficultyId) that doesn't unbox cleanly,
            // so we identify buckets by the non-null value list and name them
            // by inspecting the FIRST stage's properties for a difficulty hint.
            // Order is preserved (Normal first → harder later in Plarium's data).
            var byDiff = new List<(string diffName, int diffIdx, List<int> stageIds)>();
            var sidByDiff = Prop(region, "StageIdsByDifficulty");
            if (sidByDiff != null)
            {
                try
                {
                    var entries = Prop(sidByDiff, "_entries");
                    int len = entries != null ? IntProp(entries, "Length") : 0;
                    var get = entries != null
                        ? (entries.GetType().GetMethod("get_Item", new[] { typeof(int) })
                           ?? entries.GetType().GetProperty("Item")?.GetGetMethod())
                        : null;
                    int diffIdx = 0;
                    for (int j = 0; j < len; j++)
                    {
                        var diffEntry = get.Invoke(entries, new object[] { j });
                        if (diffEntry == null) continue;
                        var idsList = Prop(diffEntry, "value");
                        if (idsList == null) continue;
                        int idsCount = IntProp(idsList, "_size");
                        if (idsCount <= 0) continue;
                        var idsItems = Prop(idsList, "_items");
                        if (idsItems == null) continue;
                        var idsGet = idsItems.GetType().GetMethod("get_Item", new[] { typeof(int) })
                                     ?? idsItems.GetType().GetProperty("Item")?.GetGetMethod();
                        var stageIds = new List<int>();
                        for (int k = 0; k < idsCount; k++)
                        {
                            var sidObj = idsGet.Invoke(idsItems, new object[] { k });
                            if (sidObj == null) continue;
                            stageIds.Add(Convert.ToInt32(sidObj));
                        }
                        // Dedupe a possible doppelganger from free-slot iteration
                        // by checking if this stage-id list overlaps an earlier
                        // bucket. Plarium's _entries are typically packed near
                        // the start, so duplicates would occur in adjacent slots.
                        bool dup = false;
                        if (stageIds.Count > 0)
                        {
                            int firstSid = stageIds[0];
                            foreach (var prev in byDiff)
                            {
                                if (prev.stageIds.Count > 0 && prev.stageIds[0] == firstSid)
                                {
                                    dup = true; break;
                                }
                            }
                        }
                        if (dup) continue;
                        // Best-effort name: by index ordering. Plarium's enum
                        // declaration order tends to be Normal, Brutal,
                        // Nightmare, etc. — so bucket index matches that.
                        string diffName = DifficultyName(diffIdx);
                        byDiff.Add((diffName, diffIdx, stageIds));
                        diffIdx++;
                    }
                }
                catch { }
            }
            if (byDiff.Count == 0) return;

            // Sort by enum int so Normal (typically 0) comes first.
            // Already in declaration order from the entries walk; no sort.

            var diffPayloads = new List<string>();
            foreach (var (diffName, diffId, stageIds) in byDiff)
            {
                var setCount = new Dictionary<int, int>();
                var setMaxProb = new Dictionary<int, double>();
                var accKindCount = new Dictionary<int, int>();
                var accSetCount = new Dictionary<int, int>();
                int stagesWithRewards = 0;
                foreach (int sid in stageIds)
                {
                    if (!stageById.TryGetValue(sid, out var stage)) continue;
                    var reward = Prop(stage, "Reward");
                    if (reward == null) continue;
                    stagesWithRewards++;
                    // Path A: Dungeon-style probability dicts (Dragon, IG, FK, Spider).
                    AggregateProbs(reward, "ArtifactProbsBySetKindId", setCount, setMaxProb);
                    AggregateProbsCountOnly(reward, "AccessoryProbsByKindId", accKindCount);
                    AggregateProbsCountOnly(reward, "AccessoryProbsBySetKindId", accSetCount);
                    // Path B: Doom-Tower-style FlexibleRewardInfo list. Each entry
                    // can carry SetKindId / KindId for sets and accessories.
                    AggregateRewardList(reward, setCount, setMaxProb, accKindCount, accSetCount);
                    // Path C: First-time UserPrize artifact-drop settings.
                    AggregatePrizeArtifacts(stage, setCount, setMaxProb, accKindCount, accSetCount);
                }
                if (stagesWithRewards == 0) continue;

                var dsb = new StringBuilder(2048);
                dsb.Append("{\"difficulty\":\"").Append(Esc(diffName)).Append("\",");
                dsb.Append("\"difficulty_id\":").Append(diffId);
                dsb.Append(",\"stages\":").Append(stagesWithRewards);
                dsb.Append(",\"set_drops\":");
                AppendIntDoubleMap(dsb, setCount, setMaxProb);
                dsb.Append(",\"accessory_kinds\":[");
                AppendIntList(dsb, accKindCount.Keys);
                dsb.Append("],\"accessory_sets\":[");
                AppendIntList(dsb, accSetCount.Keys);
                dsb.Append("]}");
                diffPayloads.Add(dsb.ToString());
            }
            if (diffPayloads.Count == 0) return;

            if (!firstRegion) sb.Append(",");
            firstRegion = false;
            sb.Append("\"").Append(Esc(regionName)).Append("\":{");
            sb.Append("\"id\":").Append(rid);
            sb.Append(",\"by_difficulty\":[").Append(string.Join(",", diffPayloads)).Append("]");
            sb.Append("}");
        }

        // Walk reward.Rewards (List<FlexibleRewardInfo>) and harvest any entry
        // that carries a SetKindId or KindId — that's how Doom Tower stages and
        // some events encode artifact drops instead of the prob dicts.
        private static void AggregateRewardList(object reward,
            Dictionary<int,int> setCount, Dictionary<int,double> setMaxProb,
            Dictionary<int,int> accKindCount, Dictionary<int,int> accSetCount)
        {
            var rewards = Prop(reward, "Rewards");
            if (rewards == null) return;
            try
            {
                int sz = IntProp(rewards, "_size");
                if (sz <= 0) return;
                var items = Prop(rewards, "_items");
                if (items == null) return;
                var get = items.GetType().GetMethod("get_Item", new[] { typeof(int) })
                          ?? items.GetType().GetProperty("Item")?.GetGetMethod();
                for (int i = 0; i < sz; i++)
                {
                    var info = get.Invoke(items, new object[] { i });
                    if (info == null) continue;
                    double prob = TryGetDouble(info, "Probability", 1.0);
                    var setNullable = Prop(info, "SetKindId");
                    int setId = NullableEnumInt(setNullable);
                    if (setId > 0 && prob > 0)
                    {
                        setCount[setId] = setCount.TryGetValue(setId, out int c) ? c + 1 : 1;
                        if (!setMaxProb.TryGetValue(setId, out double mp) || prob > mp) setMaxProb[setId] = prob;
                    }
                    var kindNullable = Prop(info, "KindId");
                    int kindId = NullableEnumInt(kindNullable);
                    if (kindId >= 7 && kindId <= 9) // accessories: ring/amulet/banner
                    {
                        accKindCount[kindId] = accKindCount.TryGetValue(kindId, out int c) ? c + 1 : 1;
                    }
                }
            }
            catch { }
        }

        // Walk Stage.FirstTimeReward.SetsOfArtifacts / ArtifactDropSettings —
        // Doom Tower boss floors etc. encode their first-clear set rewards here.
        private static void AggregatePrizeArtifacts(object stage,
            Dictionary<int,int> setCount, Dictionary<int,double> setMaxProb,
            Dictionary<int,int> accKindCount, Dictionary<int,int> accSetCount)
        {
            var prize = Prop(stage, "FirstTimeReward");
            if (prize == null) return;
            try
            {
                var setsList = Prop(prize, "SetsOfArtifacts") ?? Prop(prize, "_setsOfArtifacts");
                if (setsList != null)
                {
                    int n = IntProp(setsList, "_size");
                    var items = Prop(setsList, "_items");
                    if (items != null && n > 0)
                    {
                        var get = items.GetType().GetMethod("get_Item", new[] { typeof(int) })
                                  ?? items.GetType().GetProperty("Item")?.GetGetMethod();
                        for (int i = 0; i < n; i++)
                        {
                            var s = get.Invoke(items, new object[] { i });
                            if (s == null) continue;
                            var sk = Prop(s, "SetKindId");
                            int setId = NullableEnumInt(sk);
                            if (setId > 0)
                            {
                                setCount[setId] = setCount.TryGetValue(setId, out int c) ? c + 1 : 1;
                                if (!setMaxProb.ContainsKey(setId)) setMaxProb[setId] = 1.0;
                            }
                        }
                    }
                }
            }
            catch { }
        }

        private static double TryGetDouble(object obj, string name, double dflt)
        {
            var v = Prop(obj, name);
            if (v == null) return dflt;
            try { return Convert.ToDouble(v); } catch { }
            // Fallback for Plarium Fixed / IL2CPP wrappers that don't implement
            // IConvertible cleanly: parse the type's ToString output. Fixed
            // types print as "0.150" or similar, so this round-trips correctly.
            if (double.TryParse(v.ToString(), System.Globalization.NumberStyles.Any,
                System.Globalization.CultureInfo.InvariantCulture, out double d))
                return d;
            return dflt;
        }

        // Il2Cpp Nullable<TEnum> — the .Value / .HasValue / GetValueOrDefault
        // accessors all return 0 due to IL2Cpp marshaling. The actual enum
        // int lives in native IL2Cpp memory at offset 16 from the object's
        // Pointer (verified empirically 2026-05-02 with BlessingTypeId on
        // a Brimstone hero — read returned 4101 = Brimstone).
        // Returns 0 when null or HasValue=false.
        private static int NullableEnumInt(object nullable)
        {
            if (nullable == null) return 0;
            try
            {
                // Bail early if HasValue=false (the property reads correctly
                // for the bool even when Value is broken).
                var t = nullable.GetType();
                var hvProp = t.GetProperty("HasValue");
                if (hvProp != null)
                {
                    var hv = hvProp.GetValue(nullable);
                    if (hv is bool hb && !hb) return 0;
                }
                var ptrProp = t.GetProperty("Pointer");
                if (ptrProp != null)
                {
                    var ptrVal = ptrProp.GetValue(nullable);
                    if (ptrVal is System.IntPtr ptr && ptr != System.IntPtr.Zero)
                    {
                        return System.Runtime.InteropServices
                            .Marshal.ReadInt32(ptr, 16);
                    }
                }
                // Fallback for non-IL2Cpp Nullables (managed System.Nullable):
                // backing fields work directly.
                var valField = t.GetField("value",
                    BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                if (valField != null)
                {
                    var inner = valField.GetValue(nullable);
                    if (inner != null) return ExtractEnumInt(inner);
                }
            }
            catch { }
            return 0;
        }

        // Public alias for cross-partial-file callers (LiveData, Battle).
        // Same semantics as NullableEnumInt; named for clarity at call sites.
        private static int ReadIl2CppNullableEnumInt(object nullable) =>
            NullableEnumInt(nullable);

        private static void AggregateProbs(object reward, string propName,
            Dictionary<int,int> count, Dictionary<int,double> maxProb, int maxKey = 100)
        {
            var d = Prop(reward, propName);
            if (d == null) return;
            try
            {
                int dictCount = IntProp(d, "Count");
                if (dictCount <= 0) return;
                var dt = d.GetType();
                var ck = dt.GetMethod("ContainsKey");
                var idx = dt.GetProperty("Item");
                if (ck == null || idx == null) return;
                int found = 0;
                for (int key = 0; key <= maxKey && found < dictCount; key++)
                {
                    bool hit;
                    try { hit = (bool)ck.Invoke(d, new object[] { key }); }
                    catch { hit = false; }
                    if (!hit) continue;
                    found++;
                    object v;
                    try { v = idx.GetValue(d, new object[] { key }); }
                    catch { continue; }
                    double prob = v != null ? Convert.ToDouble(v) : 0.0;
                    if (prob <= 0) continue;
                    count[key] = count.TryGetValue(key, out int c) ? c + 1 : 1;
                    if (!maxProb.TryGetValue(key, out double mp) || prob > mp) maxProb[key] = prob;
                }
            }
            catch { }
        }

        private static void AggregateProbsCountOnly(object reward, string propName,
            Dictionary<int,int> count, int maxKey = 100)
        {
            var d = Prop(reward, propName);
            if (d == null) return;
            try
            {
                int dictCount = IntProp(d, "Count");
                if (dictCount <= 0) return;
                var dt = d.GetType();
                var ck = dt.GetMethod("ContainsKey");
                if (ck == null) return;
                int found = 0;
                for (int key = 0; key <= maxKey && found < dictCount; key++)
                {
                    bool hit;
                    try { hit = (bool)ck.Invoke(d, new object[] { key }); }
                    catch { hit = false; }
                    if (!hit) continue;
                    found++;
                    count[key] = count.TryGetValue(key, out int c) ? c + 1 : 1;
                }
            }
            catch { }
        }

        // Friendly name for DifficultyId enum int. Hardcoded because Il2Cpp's
        // Enum.GetName isn't reliable on the interop wrapper.
        private static string DifficultyName(int diffInt)
        {
            switch (diffInt)
            {
                case 0: return "Normal";
                case 1: return "Brutal";
                case 2: return "Nightmare";
                case 3: return "Hard";    // doom tower / dungeon hard
                case 4: return "Heroic";
                default: return "diff" + diffInt;
            }
        }

        // Best-effort enum-to-int. Tries Convert.ToInt32 first, falls back to
        // the value__ field that Il2Cpp/CLR enums use for the underlying value.
        private static int ExtractEnumInt(object enumVal)
        {
            if (enumVal == null) return 0;
            try { return Convert.ToInt32(enumVal); } catch { }
            try
            {
                var f = enumVal.GetType().GetField("value__", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                if (f != null) return (int)f.GetValue(enumVal);
            }
            catch { }
            // Last resort: parse ToString as an int.
            int n;
            if (int.TryParse(enumVal.ToString(), out n)) return n;
            return 0;
        }

        private static void AppendIntDoubleMap(StringBuilder sb, Dictionary<int,int> count, Dictionary<int,double> maxProb)
        {
            sb.Append("{");
            bool first = true;
            foreach (var kv in count)
            {
                if (!first) sb.Append(",");
                first = false;
                double mp = maxProb.TryGetValue(kv.Key, out double v) ? v : 0.0;
                sb.Append("\"").Append(kv.Key).Append("\":{\"stages\":").Append(kv.Value)
                  .Append(",\"max_prob\":").Append(mp.ToString("0.######", System.Globalization.CultureInfo.InvariantCulture)).Append("}");
            }
            sb.Append("}");
        }

        private static void AppendIntList(StringBuilder sb, IEnumerable<int> ints)
        {
            bool first = true;
            foreach (var n in ints.OrderBy(x => x))
            {
                if (!first) sb.Append(",");
                first = false;
                sb.Append(n);
            }
        }
    }
}
