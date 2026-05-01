// Auto-extracted from RaidAutomationPlugin.cs (slice: live data export).
// All these methods are partial-class members of RaidAutomationPlugin.
// Behavior is identical; this file isolates the heavy live-account
// extraction endpoints (heroes / artifacts / skills / account / computed
// stats / enemy skills) from the HTTP router, battle-state polling, and
// artifact mutation code.
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
        // API: /all-heroes — full hero + artifact data
        // =====================================================

        private string GetAllHeroes(string offsetStr = "", string limitStr = "", string minGradeStr = "")
        {
            var sb = new StringBuilder(65536);
            var uw = GetUserWrapper();
            if (uw == null) return "{\"error\":\"Not logged in\"}";

            int offset = 0, limit = 600, minGrade = 0;
            int.TryParse(offsetStr, out offset);
            if (int.TryParse(limitStr, out int parsedLimit) && parsedLimit > 0) limit = parsedLimit;
            if (limit > 600) limit = 600;
            int.TryParse(minGradeStr, out minGrade);

            var heroes = Prop(uw, "Heroes");
            var equipment = Prop(uw, "Artifacts");

            var heroData = Prop(heroes, "HeroData");
            var heroDict = Prop(heroData, "HeroById");

            if (heroDict == null) return "{\"error\":\"HeroById null\"}";

            int total = IntProp(heroDict, "Count");
            sb.Append("{\"count\":" + total + ",\"offset\":" + offset + ",\"limit\":" + limit + ",\"heroes\":[");

            int idx = 0;
            int written = 0;
            int skipped = 0;
            foreach (var hero in DictValues(heroDict))
            {
                // Filter by grade if specified
                if (minGrade > 0)
                {
                    int grade = IntProp(hero, "Grade");
                    if (grade < minGrade) { skipped++; continue; }
                }
                if (idx < offset) { idx++; continue; }
                if (written >= limit) break;
                if (written > 0) sb.Append(",");
                int mark = sb.Length;
                try { AppendHero(sb, hero, equipment); }
                catch (Exception ex)
                {
                    sb.Length = mark; // Revert partial output
                    sb.Append("{\"id\":" + IntProp(hero, "Id") + ",\"error\":\"" + Esc(ex.Message) + "\"}");
                }
                idx++;
                written++;
            }
            sb.Append("]}");
            return sb.ToString();
        }

        private void AppendHero(StringBuilder sb, object hero, object equipment)
        {
            int id = IntProp(hero, "Id");
            int typeId = IntProp(hero, "TypeId");
            int grade = IntProp(hero, "Grade");
            int level = IntProp(hero, "Level");
            int empower = IntProp(hero, "EmpowerLevel");

            bool locked = false, inStorage = false;
            try { var p = hero.GetType().GetProperty("Locked"); if (p != null) locked = (bool)p.GetValue(hero); } catch { }
            try { var p = hero.GetType().GetProperty("InStorage"); if (p != null) inStorage = (bool)p.GetValue(hero); } catch { }

            sb.Append("{\"id\":" + id + ",\"type_id\":" + typeId +
                      ",\"grade\":" + grade + ",\"level\":" + level +
                      ",\"empower\":" + empower +
                      ",\"locked\":" + (locked ? "true" : "false") +
                      ",\"in_storage\":" + (inStorage ? "true" : "false"));

            // HeroType — name, fraction, rarity, element, role
            object heroType = null;
            try { heroType = Prop(hero, "Type"); } catch { }
            if (heroType == null || IntProp(heroType, "Id") == 0)
            {
                try { heroType = Prop(hero, "_type"); } catch { }
            }
            // If Type still null, try getting it from the game's static data
            if (heroType == null && typeId > 0)
            {
                try
                {
                    // Try to find HeroType via StaticData
                    var appModel = GetAppModel();
                    if (appModel != null)
                    {
                        var staticData = Prop(appModel, "StaticData");
                        if (staticData != null)
                        {
                            var heroTypes = Prop(staticData, "HeroData");
                            if (heroTypes != null)
                            {
                                var htDict = Prop(heroTypes, "HeroTypeById");
                                if (htDict != null)
                                {
                                    var containsKey = htDict.GetType().GetMethod("ContainsKey");
                                    if (containsKey != null && (bool)containsKey.Invoke(htDict, new object[] { typeId }))
                                    {
                                        var itemProp = htDict.GetType().GetProperty("Item");
                                        heroType = itemProp?.GetValue(htDict, new object[] { typeId });
                                    }
                                }
                            }
                        }
                    }
                }
                catch { }
            }

            if (heroType != null)
            {
                try
                {
                    int fraction = IntProp(heroType, "Fraction");
                    int rarity = IntProp(heroType, "Rarity");
                    sb.Append(",\"fraction\":" + fraction + ",\"rarity\":" + rarity);
                }
                catch { }

                // Name
                try
                {
                    var nameObj = Prop(heroType, "Name");
                    if (nameObj != null)
                    {
                        string name = null;
                        try { name = Prop(nameObj, "LocalizedValue")?.ToString(); } catch { }
                        if (string.IsNullOrEmpty(name) || name.Contains("SharedLTextKey"))
                            try { name = Prop(nameObj, "DefaultValue")?.ToString(); } catch { }
                        if (string.IsNullOrEmpty(name) || name.Contains("SharedLTextKey"))
                            try { name = Prop(nameObj, "Key")?.ToString(); } catch { }
                        if (!string.IsNullOrEmpty(name) && !name.Contains("SharedLTextKey"))
                            sb.Append(",\"name\":\"" + Esc(name) + "\"");
                    }
                }
                catch { }

                // Forms[0] -> Element, Role, BaseStats
                try
                {
                    var forms = Prop(heroType, "Forms");
                    if (forms != null)
                    {
                        foreach (var form in ListItems(forms))
                        {
                            int element = IntProp(form, "Element");
                            int role = IntProp(form, "Role");
                            sb.Append(",\"element\":" + element + ",\"role\":" + role);

                            var baseStats = Prop(form, "BaseStats");
                            if (baseStats != null)
                            {
                                sb.Append(",\"base_stats\":{");
                                AppendFixed(sb, baseStats, "Health", "HP");
                                sb.Append(","); AppendFixed(sb, baseStats, "Attack", "ATK");
                                sb.Append(","); AppendFixed(sb, baseStats, "Defence", "DEF");
                                sb.Append(","); AppendFixed(sb, baseStats, "Speed", "SPD");
                                sb.Append(","); AppendFixed(sb, baseStats, "Resistance", "RES");
                                sb.Append(","); AppendFixed(sb, baseStats, "Accuracy", "ACC");
                                sb.Append(","); AppendFixed(sb, baseStats, "CriticalChance", "CR");
                                sb.Append(","); AppendFixed(sb, baseStats, "CriticalDamage", "CD");
                                sb.Append("}");
                            }
                            break;
                        }
                    }
                }
                catch { }

                // Leader skills
                try
                {
                    var leaderSkills = Prop(heroType, "LeaderSkills");
                    if (leaderSkills != null)
                    {
                        int lsCount = IntProp(leaderSkills, "Count");
                        if (lsCount > 0)
                        {
                            sb.Append(",\"leader_skills\":[");
                            int lsi = 0;
                            foreach (var ls in ListItems(leaderSkills))
                            {
                                if (lsi > 0) sb.Append(",");
                                int stat = IntProp(ls, "StatKindId");
                                bool isAbs = false;
                                try { isAbs = (bool)Prop(ls, "IsAbsolute"); } catch { }
                                // Use GetAmount (int property) which is pre-computed
                                int getAmount = IntProp(ls, "GetAmount");
                                double amount = getAmount > 0 ? getAmount :
                                    ReadFixed(Prop(ls, "Amount")) * 100;
                                // Area is Nullable<int>
                                int area = 0;
                                try { var areaObj = Prop(ls, "Area"); if (areaObj != null) area = Convert.ToInt32(areaObj); } catch { }
                                // Element filter (Nullable)
                                int lsElement = -1;
                                try { var eObj = Prop(ls, "Element"); if (eObj != null) lsElement = Convert.ToInt32(eObj); } catch { }
                                // Faction filter (Nullable)
                                int lsFaction = -1;
                                try { var fObj = Prop(ls, "Faction"); if (fObj != null) lsFaction = Convert.ToInt32(fObj); } catch { }

                                sb.Append("{\"stat\":" + stat + ",\"amount\":" + FixedToJson(amount) +
                                          ",\"area\":" + area + ",\"absolute\":" + (isAbs ? "true" : "false"));
                                if (lsElement >= 0) sb.Append(",\"element\":" + lsElement);
                                if (lsFaction >= 0) sb.Append(",\"faction\":" + lsFaction);
                                sb.Append("}");
                                lsi++;
                            }
                            sb.Append("]");
                        }
                    }
                }
                catch { }
            }

            // Skills
            try
            {
                var skills = Prop(hero, "Skills");
                if (skills != null)
                {
                    sb.Append(",\"skills\":[");
                    int si = 0;
                    foreach (var skill in ListItems(skills))
                    {
                        if (si > 0) sb.Append(",");
                        sb.Append("{\"type_id\":" + IntProp(skill, "TypeId") +
                                  ",\"level\":" + IntProp(skill, "Level") + "}");
                        si++;
                    }
                    sb.Append("]");
                }
            }
            catch { }

            // Masteries — read the actual mastery IDs
            try
            {
                var masteryData = Prop(hero, "MasteryData");
                if (masteryData != null)
                {
                    var masteries = Prop(masteryData, "Masteries");
                    if (masteries != null)
                    {
                        int mcount = IntProp(masteries, "Count");
                        sb.Append(",\"mastery_count\":" + mcount);
                        // Read actual mastery IDs
                        sb.Append(",\"masteries\":[");
                        int mi = 0;
                        foreach (var m in ListItems(masteries))
                        {
                            if (mi > 0) sb.Append(",");
                            try { sb.Append(Convert.ToInt32(m)); } catch { sb.Append("0"); }
                            mi++;
                        }
                        sb.Append("]");
                    }
                }
            }
            catch { }

            // Blessing (DoubleAscend)
            try
            {
                var dblAscend = Prop(hero, "DoubleAscendData");
                if (dblAscend != null)
                {
                    int ascendGrade = IntProp(dblAscend, "Grade");
                    int blessingId = 0;

                    // BlessingId is Nullable<BlessingTypeId> (IL2CPP nullable enum)
                    // Try multiple approaches to read it:
                    try
                    {
                        // Approach 1: Direct property with HasValue/Value
                        var blessingProp = dblAscend.GetType().GetProperty("BlessingId");
                        if (blessingProp != null)
                        {
                            var rawVal = blessingProp.GetValue(dblAscend);
                            if (rawVal != null)
                            {
                                // IL2CPP Nullable<T> has HasValue and Value properties
                                var hasValueProp = rawVal.GetType().GetProperty("HasValue");
                                var valueProp = rawVal.GetType().GetProperty("Value");
                                if (hasValueProp != null && valueProp != null)
                                {
                                    bool hasValue = (bool)hasValueProp.GetValue(rawVal);
                                    if (hasValue)
                                    {
                                        var val = valueProp.GetValue(rawVal);
                                        try { blessingId = Convert.ToInt32(val); } catch { }
                                    }
                                }
                                else
                                {
                                    // Fallback: try direct ToString → parse
                                    string s = rawVal.ToString();
                                    if (!string.IsNullOrEmpty(s) && s != "0" && !s.Contains("Null"))
                                        int.TryParse(s, out blessingId);
                                }
                            }
                        }
                    }
                    catch { }

                    // Approach 2: Try reading the backing field directly
                    if (blessingId == 0)
                    {
                        try
                        {
                            var field = dblAscend.GetType().GetField("_blessingId",
                                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
                            if (field != null)
                            {
                                var val = field.GetValue(dblAscend);
                                if (val != null) try { blessingId = Convert.ToInt32(val); } catch { }
                            }
                        }
                        catch { }
                    }

                    // Approach 3: Enumerate all properties and try to find blessing-like values
                    if (blessingId == 0)
                    {
                        try
                        {
                            foreach (var prop in dblAscend.GetType().GetProperties())
                            {
                                string pname = prop.Name.ToLower();
                                if (pname.Contains("blessing") && pname != "blessingid")
                                {
                                    try
                                    {
                                        var val = prop.GetValue(dblAscend);
                                        if (val != null)
                                        {
                                            int tryId = 0;
                                            try { tryId = Convert.ToInt32(val); } catch { }
                                            if (tryId > 0) { blessingId = tryId; break; }
                                        }
                                    }
                                    catch { }
                                }
                            }
                        }
                        catch { }
                    }

                    if (blessingId > 0)
                        sb.Append(",\"blessing\":{\"id\":" + blessingId + ",\"grade\":" + ascendGrade + "}");
                    else
                    {
                        // Debug: output all DoubleAscendData properties for diagnosis
                        sb.Append(",\"_dbl_ascend_debug\":{\"grade\":" + ascendGrade);
                        try
                        {
                            foreach (var prop in dblAscend.GetType().GetProperties())
                            {
                                try
                                {
                                    var val = prop.GetValue(dblAscend);
                                    string vs = val != null ? val.ToString() : "null";
                                    if (vs.Length < 50)
                                        sb.Append(",\"" + prop.Name + "\":\"" + vs.Replace("\"", "'") + "\"");
                                }
                                catch { }
                            }
                        }
                        catch { }
                        sb.Append("}");
                    }
                }
            }
            catch { }

            // Equipped artifacts
            if (equipment != null)
            {
                try
                {
                    AppendEquippedArtifacts(sb, id, equipment);
                }
                catch (Exception ex)
                {
                    sb.Append(",\"artifacts_error\":\"" + Esc(ex.Message) + "\"");
                }
            }

            sb.Append("}");
        }

        private void AppendFixed(StringBuilder sb, object stats, string propName, string jsonName)
        {
            var val = Prop(stats, propName);
            if (val == null) { sb.Append("\"" + jsonName + "\":0"); return; }

            double d = ReadFixed(val);
            sb.Append("\"" + jsonName + "\":" + FixedToJson(d));
        }

        // Emit a stat block (BattleHero stats / bonus stats) with all 8 game
        // stats in a single dict. Centralised so per-bonus code paths don't
        // each have to remember to include every stat — a missing field on
        // a bonus that turns out to need it (e.g. Relic +CD% on a CD relic)
        // becomes a silent gap in the dashboard otherwise.
        private void AppendAllStats(StringBuilder sb, object stats)
        {
            sb.Append("{");
            AppendFixed(sb, stats, "Health", "HP");
            sb.Append(","); AppendFixed(sb, stats, "Attack", "ATK");
            sb.Append(","); AppendFixed(sb, stats, "Defence", "DEF");
            sb.Append(","); AppendFixed(sb, stats, "Speed", "SPD");
            sb.Append(","); AppendFixed(sb, stats, "Resistance", "RES");
            sb.Append(","); AppendFixed(sb, stats, "Accuracy", "ACC");
            sb.Append(","); AppendFixed(sb, stats, "CriticalChance", "CR");
            sb.Append(","); AppendFixed(sb, stats, "CriticalDamage", "CD");
            sb.Append("}");
        }

        private double ReadFixed(object fixedVal)
        {
            if (fixedVal == null) return 0;
            var ft = fixedVal.GetType();

            // Try ToString() — might output the double value
            string str = fixedVal.ToString();
            if (double.TryParse(str, System.Globalization.NumberStyles.Any,
                System.Globalization.CultureInfo.InvariantCulture, out double parsed))
            {
                if (!double.IsNaN(parsed) && !double.IsInfinity(parsed))
                    return parsed;
            }

            // Try RawValue / m_value / _value field
            foreach (var fname in new[] { "RawValue", "m_value", "_value", "Value" })
            {
                var f = ft.GetField(fname, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                if (f != null && f.FieldType == typeof(long))
                {
                    long raw = (long)f.GetValue(fixedVal);
                    return raw / 4294967296.0;
                }
                var p = ft.GetProperty(fname);
                if (p != null)
                {
                    try
                    {
                        var v = p.GetValue(fixedVal);
                        if (v is long l) return l / 4294967296.0;
                        if (v is double dv && !double.IsNaN(dv) && !double.IsInfinity(dv)) return dv;
                        if (v is float fv && !float.IsNaN(fv) && !float.IsInfinity(fv)) return fv;
                    }
                    catch { }
                }
            }

            try { return Convert.ToDouble(fixedVal); } catch { }

            return 0;
        }

        private string FixedToJson(double val)
        {
            if (double.IsNaN(val) || double.IsInfinity(val)) return "0";
            return val.ToString("F1");
        }

        private void AppendEquippedArtifacts(StringBuilder sb, int heroId, object equipment)
        {
            var eqType = equipment.GetType();

            // Use ArtifactData.ArtifactDataByHeroId to get slot -> artifact_id mapping,
            // then use One(id) to get the actual artifact objects
            var artDataProp = eqType.GetProperty("ArtifactData");
            if (artDataProp == null)
            {
                sb.Append(",\"artifacts\":[]");
                return;
            }

            var artData = artDataProp.GetValue(equipment);
            if (artData == null) { sb.Append(",\"artifacts\":[]"); return; }

            // ArtifactDataByHeroId: Dictionary<int, HeroArtifactData>
            var byHeroProp = artData.GetType().GetProperty("ArtifactDataByHeroId");
            if (byHeroProp == null) { sb.Append(",\"artifacts\":[]"); return; }

            var byHeroDict = byHeroProp.GetValue(artData);
            if (byHeroDict == null) { sb.Append(",\"artifacts\":[]"); return; }

            // Look up this hero's artifact data
            // Dictionary<int, HeroArtifactData> - use Item indexer with hero ID
            object heroArtData = null;
            try
            {
                // Try TryGetValue or Item indexer
                var containsKey = byHeroDict.GetType().GetMethod("ContainsKey");
                if (containsKey != null && (bool)containsKey.Invoke(byHeroDict, new object[] { heroId }))
                {
                    var itemProp = byHeroDict.GetType().GetProperty("Item");
                    heroArtData = itemProp?.GetValue(byHeroDict, new object[] { heroId });
                }
            }
            catch { }

            if (heroArtData == null) { sb.Append(",\"artifacts\":[]"); return; }

            // HeroArtifactData has ArtifactIdByKind: Dictionary<ArtifactKindId, int>
            var idByKindProp = heroArtData.GetType().GetProperty("ArtifactIdByKind");
            if (idByKindProp == null) { sb.Append(",\"artifacts\":[]"); return; }

            var idByKind = idByKindProp.GetValue(heroArtData);
            if (idByKind == null) { sb.Append(",\"artifacts\":[]"); return; }

            // Get the One(int id) method on equipment to fetch artifact objects
            var oneMethod = eqType.GetMethod("One");

            sb.Append(",\"artifacts\":[");
            int ai = 0;

            // Iterate the slot -> id dictionary
            foreach (var kvp in DictValues(idByKind))
            {
                // kvp is the value (artifact ID as int)
                // Actually DictValues gives values, not KVP. Let me iterate differently.
                break;
            }

            // Use reflection to iterate the dictionary properly
            var dictType = idByKind.GetType();
            var getEnumerator = dictType.GetMethod("GetEnumerator");
            var enumerator = getEnumerator.Invoke(idByKind, null);
            var enumType = enumerator.GetType();
            var moveNext = enumType.GetMethod("MoveNext");
            var currentProp = enumType.GetProperty("Current");

            while ((bool)moveNext.Invoke(enumerator, null))
            {
                try
                {
                    var kvp = currentProp.GetValue(enumerator);
                    var kvpType = kvp.GetType();
                    int artId = IntProp(kvp, "Value"); // artifact ID
                    int slotKind = IntProp(kvp, "Key"); // ArtifactKindId

                    if (artId <= 0) continue;

                    // Get the actual artifact via One(id)
                    object artifact = null;
                    if (oneMethod != null)
                    {
                        try { artifact = oneMethod.Invoke(equipment, new object[] { artId }); }
                        catch { }
                    }

                    if (ai > 0) sb.Append(",");
                    if (artifact != null)
                    {
                        AppendArtifact(sb, artifact);
                    }
                    else
                    {
                        // Just output the ID and slot
                        sb.Append("{\"id\":" + artId + ",\"kind\":" + slotKind + "}");
                    }
                    ai++;
                }
                catch { }
            }
            sb.Append("]");
        }

        private void AppendArtifact(StringBuilder sb, object art)
        {
            int artId = IntProp(art, "Id");
            int level = IntProp(art, "Level");
            int kind = IntProp(art, "KindId");
            int rank = IntProp(art, "RankId");
            int rarity = IntProp(art, "RarityId");
            int setKind = IntProp(art, "SetKindId");

            sb.Append("{\"id\":" + artId + ",\"level\":" + level +
                      ",\"kind\":" + kind + ",\"rank\":" + rank +
                      ",\"rarity\":" + rarity + ",\"set\":" + setKind);

            // Use ArtifactSetup.FromArtifact to get COMPUTED stats (includes main stat)
            try
            {
                var setupType = FindType("SharedModel.Battle.Core.Setup.ArtifactSetup");
                if (setupType != null)
                {
                    var fromMethod = setupType.GetMethod("FromArtifact");
                    if (fromMethod != null)
                    {
                        var setup = fromMethod.Invoke(null, new object[] { art });
                        if (setup != null)
                        {
                            // PercentBonus has all % stats, FlatBonus has all flat stats
                            var pctBonus = Prop(setup, "PercentBonus");
                            var flatBonus = Prop(setup, "FlatBonus");
                            if (pctBonus != null)
                            {
                                sb.Append(",\"pct_bonus\":{");
                                AppendFixed(sb, pctBonus, "Health", "HP");
                                sb.Append(","); AppendFixed(sb, pctBonus, "Attack", "ATK");
                                sb.Append(","); AppendFixed(sb, pctBonus, "Defence", "DEF");
                                sb.Append(","); AppendFixed(sb, pctBonus, "Speed", "SPD");
                                sb.Append(","); AppendFixed(sb, pctBonus, "Resistance", "RES");
                                sb.Append(","); AppendFixed(sb, pctBonus, "Accuracy", "ACC");
                                sb.Append(","); AppendFixed(sb, pctBonus, "CriticalChance", "CR");
                                sb.Append(","); AppendFixed(sb, pctBonus, "CriticalDamage", "CD");
                                sb.Append("}");
                            }
                            if (flatBonus != null)
                            {
                                sb.Append(",\"flat_bonus\":{");
                                AppendFixed(sb, flatBonus, "Health", "HP");
                                sb.Append(","); AppendFixed(sb, flatBonus, "Attack", "ATK");
                                sb.Append(","); AppendFixed(sb, flatBonus, "Defence", "DEF");
                                sb.Append(","); AppendFixed(sb, flatBonus, "Speed", "SPD");
                                sb.Append("}");
                            }
                            // Also output ascend bonus from setup
                            var ascBonus = Prop(setup, "AscendBonus");
                            if (ascBonus != null)
                                AppendBonus(sb, ascBonus, "ascend_bonus");
                            else
                                sb.Append(",\"_no_setup_ascend\":1");
                        }
                    }
                }
            }
            catch (Exception artSetupEx) { sb.Append(",\"_setup_err\":\"" + Esc(artSetupEx.Message) + "\""); }

            // Read Artifact.AscendBonus directly too (not via Setup) — sometimes
            // the Setup version is null while the Artifact's own AscendBonus is set.
            try
            {
                var artAscend = Prop(art, "AscendBonus");
                if (artAscend != null)
                    AppendBonus(sb, artAscend, "art_ascend_bonus");
                var ascLevel = Prop(art, "AscendLevel");
                if (ascLevel != null)
                {
                    var asLvlVal = Prop(ascLevel, "Value");
                    if (asLvlVal != null) sb.Append(",\"ascend_level\":" + Convert.ToInt32(asLvlVal));
                }
            }
            catch { }

            // Raw PrimaryBonus — AppendBonus reads StatKindId which loses CR/CD info.
            // Also serialize via MessagePack to get the real ArtifactStatKindId.
            var primary = Prop(art, "PrimaryBonus");
            if (primary != null)
            {
                AppendBonus(sb, primary, "primary");

                // Get the REAL stat ID via MessagePack serialization
                // ArtifactBonusFormatter writes "k" field as ArtifactStatKindId (10=CR, 11=CD)
                try
                {
                    var fmtType = FindType("MessagePack.Formatters.SharedModel.Meta.Artifacts.Bonuses.ArtifactBonusFormatter");
                    if (fmtType != null)
                    {
                        var fmt = Activator.CreateInstance(fmtType);
                        var serializeMethod = fmtType.GetMethod("Serialize");
                        if (serializeMethod != null)
                        {
                            // Create a MessagePackWriter and serialize
                            var optType = FindType("MessagePack.MessagePackSerializerOptions");
                            var stdProp = optType?.GetProperty("Standard");
                            var opts = stdProp?.GetValue(null);

                            // Use MessagePackSerializer.Serialize<ArtifactBonus>(bonus)
                            var mpType = FindType("MessagePack.MessagePackSerializer");
                            if (mpType != null)
                            {
                                // Find generic Serialize<T>(T, options) method
                                var bonusType = primary.GetType();
                                foreach (var m in mpType.GetMethods())
                                {
                                    if (m.Name == "Serialize" && m.IsGenericMethod)
                                    {
                                        var ps = m.GetParameters();
                                        if (ps.Length == 2 && ps[1].ParameterType.Name.Contains("Options"))
                                        {
                                            try
                                            {
                                                var generic = m.MakeGenericMethod(bonusType);
                                                var bytes = generic.Invoke(null, new object[] { primary, opts });
                                                if (bytes is byte[] data && data.Length > 4)
                                                {
                                                    // MessagePack map: find "k" key and read its int value
                                                    // The "k" key is encoded as fixstr (0xA1 0x6B) followed by int
                                                    for (int bi = 0; bi < data.Length - 2; bi++)
                                                    {
                                                        if (data[bi] == 0xA1 && data[bi+1] == 0x6B) // "k"
                                                        {
                                                            int realStat = data[bi+2]; // positive fixint
                                                            sb.Append(",\"primary_real_stat\":" + realStat);
                                                            break;
                                                        }
                                                    }
                                                }
                                            }
                                            catch { }
                                            break;
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                catch { }
            }

            // Secondary bonuses
            var secondaries = Prop(art, "SecondaryBonuses");
            if (secondaries != null)
            {
                sb.Append(",\"substats\":[");
                int si = 0;
                foreach (var sub in ListItems(secondaries))
                {
                    if (si > 0) sb.Append(",");
                    AppendBonusObj(sb, sub);
                    si++;
                }
                sb.Append("]");
            }

            sb.Append("}");
        }

        private void AppendBonus(StringBuilder sb, object bonus, string key)
        {
            // KindId uses ArtifactStatKindId enum (different from battle StatKindId!):
            // 0=Unknown, 1=HPflat, 2=HP%, 3=ATKflat, 4=ATK%, 5=DEFflat, 6=DEF%,
            // 7=SPD, 8=RES, 9=ACC, 10=CritChance, 11=CritDmg, 12=CritHeal
            // We normalize to: 1=HP, 2=ATK, 3=DEF, 4=SPD, 5=RES, 6=ACC, 7=CR, 8=CD
            // with flat vs % determined by the Value's IsAbsolute flag
            int stat = 0;
            int rawStat = 0;
            bool isAbsOverride = false;
            bool hasAbsOverride = false;
            try
            {
                var kindProp = bonus.GetType().GetProperty("KindId");
                if (kindProp != null)
                {
                    var kindVal = kindProp.GetValue(bonus);
                    if (kindVal != null)
                    {
                        // Try string name first
                        string ks = kindVal.ToString();
                        // ArtifactStatKindId names:
                        if (ks == "HealthFlat" || ks == "HealthPerc" || ks == "Health") { stat = 1; }
                        else if (ks == "AttackFlat" || ks == "AttackPerc" || ks == "Attack") { stat = 2; }
                        else if (ks == "DefenceFlat" || ks == "DefencePerc" || ks == "Defence") { stat = 3; }
                        else if (ks == "Speed") { stat = 4; }
                        else if (ks == "Resistance") { stat = 5; }
                        else if (ks == "Accuracy") { stat = 6; }
                        else if (ks == "CriticalChance") { stat = 7; }
                        else if (ks == "CriticalDamage") { stat = 8; }
                        else if (ks == "CriticalHeal") { stat = 7; } // map to CR

                        // Numeric fallback — IL2CPP returns battle StatKindId (1-8),
                        // NOT ArtifactStatKindId (1-12). Direct mapping:
                        // 1=HP, 2=ATK, 3=DEF, 4=SPD, 5=RES, 6=ACC, 7=CR, 8=CD
                        if (stat == 0)
                        {
                            rawStat = Convert.ToInt32(kindVal);
                            if (rawStat >= 1 && rawStat <= 8)
                                stat = rawStat;
                        }
                    }
                }
            }
            catch { }

            // Read raw _kindId from IL2CPP object using Il2CppObjectBase.Pointer
            // The IL2CPP enum interop returns wrong values for CR(7)/CD(8) → mapped to HP(1)/SPD(4)
            // Read the raw int32 at offset 0x10 in the native IL2CPP object
            {
                try
                {
                    // Il2CppObjectBase has Pointer property returning IntPtr
                    if (bonus is Il2CppSystem.Object il2cppObj)
                    {
                        IntPtr ptr = il2cppObj.Pointer;
                        if (ptr != IntPtr.Zero)
                        {
                            int raw = System.Runtime.InteropServices.Marshal.ReadInt32(ptr, 0x10);
                            if (raw >= 1 && raw <= 8)
                                stat = raw;
                            else if (raw == 10) stat = 7;  // ArtifactStatKindId.CR
                            else if (raw == 11) stat = 8;  // ArtifactStatKindId.CD
                        }
                    }
                }
                catch { }
            }

            // Use ArtifactExtensions.ToStatKindId(bonus) to get the real ArtifactStatKindId.
            // This method combines KindId + IsAbsolute to reconstruct the original type.
            // Then also try ToStatKey() and read its KindId via raw memory (bypass IL2CPP marshaling).
            try
            {
                // Method 1: ArtifactExtensions.ToStatKindId(ArtifactBonus) — returns ArtifactStatKindId
                var extType = FindType("SharedModel.Meta.Artifacts.ArtifactExtensions");
                if (extType != null)
                {
                    // Find the static method that takes ArtifactBonus
                    foreach (var m in extType.GetMethods(BindingFlags.Static | BindingFlags.Public))
                    {
                        if (m.Name == "ToStatKindId")
                        {
                            var ps = m.GetParameters();
                            if (ps.Length == 1 && ps[0].ParameterType.Name.Contains("ArtifactBonus"))
                            {
                                try
                                {
                                    var result = m.Invoke(null, new object[] { bonus });
                                    if (result != null)
                                    {
                                        int artStatId = Convert.ToInt32(result);
                                        string artStatStr = result.ToString();
                                        // ArtifactStatKindId: 1=HPflat,2=HP%,3=ATKflat,4=ATK%,5=DEFflat,6=DEF%,
                                        // 7=SPD,8=RES,9=ACC,10=CR,11=CD,12=CritHeal
                                        int mapped = 0;
                                        bool mappedFlat = false;
                                        switch (artStatId)
                                        {
                                            case 1: mapped = 1; mappedFlat = true; break;   // HP flat
                                            case 2: mapped = 1; mappedFlat = false; break;  // HP%
                                            case 3: mapped = 2; mappedFlat = true; break;   // ATK flat
                                            case 4: mapped = 2; mappedFlat = false; break;  // ATK%
                                            case 5: mapped = 3; mappedFlat = true; break;   // DEF flat
                                            case 6: mapped = 3; mappedFlat = false; break;  // DEF%
                                            case 7: mapped = 4; mappedFlat = true; break;   // SPD
                                            case 8: mapped = 5; mappedFlat = true; break;   // RES
                                            case 9: mapped = 6; mappedFlat = true; break;   // ACC
                                            case 10: mapped = 7; mappedFlat = false; break; // CR
                                            case 11: mapped = 8; mappedFlat = false; break; // CD
                                            case 12: mapped = 7; mappedFlat = false; break; // CritHeal→CR
                                        }
                                        // Also try string parsing
                                        if (mapped == 0)
                                        {
                                            if (artStatStr.Contains("CriticalChance") || artStatStr.Contains("CritChance")) mapped = 7;
                                            else if (artStatStr.Contains("CriticalDamage") || artStatStr.Contains("CritDmg")) mapped = 8;
                                            else if (artStatStr.Contains("HealthFlat")) { mapped = 1; mappedFlat = true; }
                                            else if (artStatStr.Contains("HealthPerc")) { mapped = 1; mappedFlat = false; }
                                            else if (artStatStr.Contains("AttackFlat")) { mapped = 2; mappedFlat = true; }
                                            else if (artStatStr.Contains("AttackPerc")) { mapped = 2; mappedFlat = false; }
                                            else if (artStatStr.Contains("DefenceFlat")) { mapped = 3; mappedFlat = true; }
                                            else if (artStatStr.Contains("DefencePerc")) { mapped = 3; mappedFlat = false; }
                                            else if (artStatStr.Contains("Speed")) { mapped = 4; mappedFlat = true; }
                                            else if (artStatStr.Contains("Resistance")) { mapped = 5; mappedFlat = true; }
                                            else if (artStatStr.Contains("Accuracy")) { mapped = 6; mappedFlat = true; }
                                        }
                                        if (mapped > 0)
                                        {
                                            stat = mapped;
                                            // Override IsAbsolute from the mapping
                                            isAbsOverride = mappedFlat;
                                            hasAbsOverride = true;
                                        }
                                        if (key == "primary")
                                            Logger.LogInfo("ARTSTAT " + key + ": artStatId=" + artStatId +
                                                " str=" + artStatStr + " mapped=" + mapped + " flat=" + mappedFlat);
                                    }
                                }
                                catch { }
                                break;
                            }
                        }
                    }
                }
            }
            catch { }

            // Fallback: ToStatKey() + raw memory read on the result
            if (stat <= 0)
            {
                try
                {
                    var toStatKeyMethod = bonus.GetType().GetMethod("ToStatKey");
                    if (toStatKeyMethod != null)
                    {
                        var statKey = toStatKeyMethod.Invoke(bonus, null);
                        if (statKey != null)
                        {
                            // Read KindId via raw memory at offset 0x10
                            if (statKey is Il2CppSystem.Object skObj)
                            {
                                IntPtr skPtr = skObj.Pointer;
                                if (skPtr != IntPtr.Zero)
                                {
                                    int rawKind = System.Runtime.InteropServices.Marshal.ReadInt32(skPtr, 0x10);
                                    bool rawAbs = System.Runtime.InteropServices.Marshal.ReadByte(skPtr, 0x14) != 0;
                                    if (rawKind >= 1 && rawKind <= 8) stat = rawKind;
                                    if (key == "primary")
                                        Logger.LogInfo("STATKEY_RAW " + key + ": rawKind=" + rawKind + " rawAbs=" + rawAbs);
                                }
                            }
                        }
                    }
                }
                catch { }
            }

            // _kindId via property getter removed — it overrides the correct ToStatKey result
            // ToStatKey() is the authoritative source for stat identification

            var bonusVal = Prop(bonus, "Value");
            bool isAbs = false;
            double val = 0;
            if (bonusVal != null)
            {
                try { isAbs = (bool)Prop(bonusVal, "IsAbsolute"); } catch { }
                val = ReadFixed(Prop(bonusVal, "Value"));
                if (!isAbs) val *= 100; // Convert fraction to percentage
            }
            // Apply IsAbsolute override from ArtifactExtensions.ToStatKindId mapping
            if (hasAbsOverride)
                isAbs = isAbsOverride;

            // Also read PowerUpValue (glyph) and add to value for complete stat
            double glyphVal = 0;
            try
            {
                var puv = Prop(bonus, "PowerUpValue");
                if (puv != null)
                {
                    glyphVal = ReadFixed(puv);
                    if (!isAbs) glyphVal *= 100;
                }
            }
            catch { }

            int lvl = IntProp(bonus, "Level");
            sb.Append(",\"" + key + "\":{\"stat\":" + stat + ",\"value\":" + FixedToJson(val) +
                      ",\"flat\":" + (isAbs ? "true" : "false") + ",\"level\":" + lvl +
                      (glyphVal != 0 ? ",\"glyph\":" + FixedToJson(glyphVal) : "") + "}");
        }

        private void AppendBonusObj(StringBuilder sb, object bonus)
        {
            // Same ArtifactStatKindId mapping as AppendBonus
            int stat = 0;
            try
            {
                var kindProp = bonus.GetType().GetProperty("KindId");
                if (kindProp != null)
                {
                    var kindVal = kindProp.GetValue(bonus);
                    if (kindVal != null)
                    {
                        string ks = kindVal.ToString();
                        if (ks == "HealthFlat" || ks == "HealthPerc" || ks == "Health") stat = 1;
                        else if (ks == "AttackFlat" || ks == "AttackPerc" || ks == "Attack") stat = 2;
                        else if (ks == "DefenceFlat" || ks == "DefencePerc" || ks == "Defence") stat = 3;
                        else if (ks == "Speed") stat = 4;
                        else if (ks == "Resistance") stat = 5;
                        else if (ks == "Accuracy") stat = 6;
                        else if (ks == "CriticalChance") stat = 7;
                        else if (ks == "CriticalDamage") stat = 8;
                        if (stat == 0)
                        {
                            int raw = Convert.ToInt32(kindVal);
                            if (raw >= 1 && raw <= 8)
                                stat = raw;  // battle StatKindId direct
                        }
                    }
                }
            }
            catch { }
            if (stat == 0) stat = IntProp(bonus, "KindId");
            var bonusVal = Prop(bonus, "Value");
            bool isAbs = false;
            double val = 0;
            if (bonusVal != null)
            {
                try { isAbs = (bool)Prop(bonusVal, "IsAbsolute"); } catch { }
                val = ReadFixed(Prop(bonusVal, "Value"));
                if (!isAbs) val *= 100;
            }
            // Read glyph (PowerUpValue) for substats too
            double glyphVal = 0;
            try
            {
                var puv = Prop(bonus, "PowerUpValue");
                if (puv != null)
                {
                    glyphVal = ReadFixed(puv);
                    if (!isAbs) glyphVal *= 100;
                }
            }
            catch { }
            int lvl = IntProp(bonus, "Level");
            sb.Append("{\"stat\":" + stat + ",\"value\":" + FixedToJson(val) +
                      ",\"flat\":" + (isAbs ? "true" : "false") + ",\"rolls\":" + lvl +
                      (glyphVal != 0 ? ",\"glyph\":" + FixedToJson(glyphVal) : "") + "}");
        }

        // =====================================================
        // API: /hero-computed-stats — compute ACTUAL stats for each hero
        // Uses the game's own stat calculation: base * grade_mult + artifacts + GH + arena
        // =====================================================

        private string GetHeroComputedStats(string minGradeStr)
        {
            var sb = new StringBuilder(8192);
            var uw = GetUserWrapper();
            if (uw == null) return "{\"error\":\"Not logged in\"}";

            int minGrade = 6;
            if (!string.IsNullOrEmpty(minGradeStr)) int.TryParse(minGradeStr, out minGrade);

            var heroes = Prop(uw, "Heroes");
            var heroData = Prop(heroes, "HeroData");
            var heroDict = Prop(heroData, "HeroById");
            if (heroDict == null) return "{\"error\":\"HeroById null\"}";

            sb.Append("{\"heroes\":[");
            int count = 0;

            foreach (var hero in DictValues(heroDict))
            {
                int grade = IntProp(hero, "Grade");
                if (grade < minGrade) continue;

                int id = IntProp(hero, "Id");
                int level = IntProp(hero, "Level");

                // Try to get the game's computed stats via reflection
                // The Hero class might have a Stats, TotalStats, or BattleStats property
                if (count > 0) sb.Append(",");
                sb.Append("{\"id\":" + id + ",\"grade\":" + grade + ",\"level\":" + level);

                // Call game's OWN stat calculator: HeroExtensions.GetBaseStats + CalcHeroStatBonuses
                try
                {
                    // Find HeroExtensions type
                    var heroExtType = FindType("SharedModel.Meta.Heroes.HeroExtensions");
                    if (heroExtType != null)
                    {
                        // GetBaseStats(Hero hero, HeroMetamorphForm form = 0)
                        try
                        {
                            var getBaseMethod = heroExtType.GetMethod("GetBaseStats");
                            if (getBaseMethod != null)
                            {
                                var baseStats = getBaseMethod.Invoke(null, new object[] { hero, 0 });
                                if (baseStats != null)
                                {
                                    sb.Append(",\"base_computed\":{");
                                    AppendFixed(sb, baseStats, "Health", "HP");
                                    sb.Append(","); AppendFixed(sb, baseStats, "Attack", "ATK");
                                    sb.Append(","); AppendFixed(sb, baseStats, "Defence", "DEF");
                                    sb.Append(","); AppendFixed(sb, baseStats, "Speed", "SPD");
                                    sb.Append(","); AppendFixed(sb, baseStats, "Resistance", "RES");
                                    sb.Append(","); AppendFixed(sb, baseStats, "Accuracy", "ACC");
                                    sb.Append(","); AppendFixed(sb, baseStats, "CriticalChance", "CR");
                                    sb.Append(","); AppendFixed(sb, baseStats, "CriticalDamage", "CD");
                                    sb.Append("}");
                                }
                            }
                        }
                        catch (Exception ex) { sb.Append(",\"_base_err\":\"" + Esc(ex.Message) + "\""); }

                        // CalcBlessingBonus(Hero hero, HeroMetamorphForm form = 0)
                        try
                        {
                            var blessMethod = heroExtType.GetMethod("CalcBlessingBonus");
                            if (blessMethod != null)
                            {
                                var blessStats = blessMethod.Invoke(null, new object[] { hero, 0 });
                                if (blessStats != null)
                                {
                                    sb.Append(",\"blessing_bonus\":");
                                    AppendAllStats(sb, blessStats);
                                }
                            }
                        }
                        catch (Exception ex) { sb.Append(",\"_bless_err\":\"" + Esc(ex.Message) + "\""); }

                        // CalcEmpowerBonus(Hero hero, HeroMetamorphForm form = 0)
                        try
                        {
                            var empMethod = heroExtType.GetMethod("CalcEmpowerBonus");
                            if (empMethod != null)
                            {
                                var empStats = empMethod.Invoke(null, new object[] { hero, 0 });
                                if (empStats != null)
                                {
                                    sb.Append(",\"empower_bonus\":");
                                    AppendAllStats(sb, empStats);
                                }
                            }
                        }
                        catch (Exception ex) { sb.Append(",\"_emp_err\":\"" + Esc(ex.Message) + "\""); }

                        // CalcArenaBonus(Hero hero, ArenaLeagueId leagueId, HeroMetamorphForm form = 0)
                        try
                        {
                            var arenaMethod = heroExtType.GetMethod("CalcArenaBonus");
                            if (arenaMethod != null)
                            {
                                // Get ArenaLeagueId enum type and convert int to it
                                var arenaEnumType = FindType("SharedModel.Meta.Battle.Arena.ArenaLeagueId");

                                var uw2 = GetUserWrapper();
                                var arenaWrapper = Prop(uw2, "Arena");

                                // LeagueId is Nullable<ArenaLeagueId> — unwrap it
                                object leagueEnum = null;
                                try
                                {
                                    var leagueProp = arenaWrapper.GetType().GetProperty("LeagueId");
                                    if (leagueProp != null)
                                    {
                                        var rawVal = leagueProp.GetValue(arenaWrapper);
                                        if (rawVal != null)
                                        {
                                            // Unwrap Nullable<T>.Value
                                            var valueProp = rawVal.GetType().GetProperty("Value");
                                            if (valueProp != null)
                                                leagueEnum = valueProp.GetValue(rawVal);
                                            else
                                                leagueEnum = rawVal; // might already be unwrapped
                                        }
                                    }
                                }
                                catch { }

                                // Read the user's CURRENT league directly from Arena.League. This
                                // is the in-game *Classic Arena* league (BronzeI..PlatinumIII).
                                // The Nullable<>-wrapped Arena.LeagueId field returns a different
                                // (probably "highest reached") value and gave wrong stat bonuses.
                                if (arenaEnumType != null)
                                {
                                    int knownLeague = 0;
                                    try
                                    {
                                        var leagueProp = arenaWrapper.GetType().GetProperty("League");
                                        if (leagueProp != null)
                                        {
                                            var leagueVal = leagueProp.GetValue(arenaWrapper);
                                            if (leagueVal != null)
                                                knownLeague = ExtractEnumInt(leagueVal);
                                        }
                                    }
                                    catch { }

                                    try { leagueEnum = Enum.ToObject(arenaEnumType, knownLeague); }
                                    catch { leagueEnum = knownLeague; }
                                }

                                // HeroMetamorphForm = 0 (None) - construct proper enum
                                var formType = FindType("SharedModel.Meta.Heroes.HeroMetamorphForm");
                                object form = 0;
                                if (formType != null)
                                    try { form = Enum.ToObject(formType, 0); } catch { }

                                sb.Append(",\"_arena_league\":\"" + Esc(leagueEnum != null ? leagueEnum.ToString() : "null") + "\"");

                                var arenaStats = arenaMethod.Invoke(null, new object[] { hero, leagueEnum, form });
                                if (arenaStats != null)
                                {
                                    // Renamed: this is the in-game "Classic Arena" column.
                                    sb.Append(",\"classic_arena_bonus\":");
                                    AppendAllStats(sb, arenaStats);
                                }
                            }
                        }
                        catch (Exception ex) { sb.Append(",\"_arena_err\":\"" + Esc(ex.Message) + "\""); }

                        // CalcHeroPower — uses all UserWrapper data, validates our computation
                        try
                        {
                            var powerMethod = heroExtType.GetMethod("CalcHeroPower");
                            if (powerMethod != null)
                            {
                                var uw3 = GetUserWrapper();
                                long userId = 0;
                                try { userId = (long)Prop(Prop(uw3, "Account"), "Id"); } catch { }
                                var userAccount = Prop(uw3, "Account");
                                var artifactData = Prop(Prop(uw3, "Artifacts"), "ArtifactData");
                                var relicData = Prop(uw3, "Relics");
                                var villageData = Prop(uw3, "Village");
                                var arenaData = Prop(uw3, "Arena");
                                var academyData = Prop(uw3, "Academy");

                                // Try to call CalcHeroPower
                                try
                                {
                                    var power = powerMethod.Invoke(null, new object[] {
                                        hero, userId, userAccount, artifactData,
                                        relicData, villageData, arenaData, academyData
                                    });
                                    sb.Append(",\"power\":" + Convert.ToInt32(power));
                                }
                                catch (Exception pex)
                                {
                                    sb.Append(",\"_power_err\":\"" + Esc(pex.InnerException != null ? pex.InnerException.Message : pex.Message) + "\"");
                                }
                            }
                        }
                        catch (Exception ex) { sb.Append(",\"_power_err\":\"" + Esc(ex.Message) + "\""); }

                        // CalcBuildingsBonus — use BuildCapitolBonus(VillageData, Element)
                        try
                        {
                            var buildSetupType = FindType("SharedModel.Battle.Core.Setup.BuildingSetup");
                            if (buildSetupType != null)
                            {
                                // Use BuildCapitolBonus which only needs VillageData + Element
                                var capitalMethod = buildSetupType.GetMethod("BuildCapitolBonus");
                                if (capitalMethod != null)
                                {
                                    var uw4 = GetUserWrapper();
                                    var village = Prop(uw4, "Village");

                                    // Get VillageData (protected field at offset 0x18)
                                    object villageData = null;
                                    // Try multiple reflection approaches for IL2CPP
                                    try
                                    {
                                        // Approach 1: direct field lookup on current type
                                        var vdField = village.GetType().GetField("VillageData",
                                            System.Reflection.BindingFlags.NonPublic |
                                            System.Reflection.BindingFlags.Instance |
                                            System.Reflection.BindingFlags.Public |
                                            System.Reflection.BindingFlags.FlattenHierarchy);
                                        if (vdField != null)
                                            villageData = vdField.GetValue(village);
                                    }
                                    catch { }

                                    if (villageData == null)
                                    {
                                        // Approach 2: walk base types
                                        try
                                        {
                                            var baseType = village.GetType().BaseType;
                                            while (baseType != null && villageData == null)
                                            {
                                                var f = baseType.GetField("VillageData",
                                                    System.Reflection.BindingFlags.NonPublic |
                                                    System.Reflection.BindingFlags.Instance);
                                                if (f != null)
                                                    villageData = f.GetValue(village);
                                                baseType = baseType.BaseType;
                                            }
                                        }
                                        catch { }
                                    }

                                    if (villageData == null)
                                    {
                                        // Approach 3: try as property
                                        try { villageData = Prop(village, "VillageData"); } catch { }
                                    }

                                    // Get hero element
                                    int heroElement = 0;
                                    try
                                    {
                                        var heroType = Prop(hero, "Type");
                                        if (heroType == null) heroType = Prop(hero, "_type");
                                        if (heroType != null)
                                        {
                                            var forms = Prop(heroType, "Forms");
                                            if (forms != null)
                                            {
                                                foreach (var form in ListItems(forms))
                                                {
                                                    heroElement = IntProp(form, "Element");
                                                    break;
                                                }
                                            }
                                        }
                                    }
                                    catch { }

                                    if (villageData != null && heroElement > 0)
                                    {
                                        // Convert element int to enum
                                        var elementType = FindType("SharedModel.Meta.Heroes.Element");
                                        object elementEnum = heroElement;
                                        if (elementType != null)
                                            try { elementEnum = Enum.ToObject(elementType, heroElement); } catch { }

                                        var buildingSetup = capitalMethod.Invoke(null, new object[] { villageData, elementEnum });
                                        if (buildingSetup != null)
                                        {
                                            var buildMethod = heroExtType.GetMethod("CalcBuildingsBonus");
                                            var formType3 = FindType("SharedModel.Meta.Heroes.HeroMetamorphForm");
                                            object form3 = 0;
                                            if (formType3 != null) try { form3 = Enum.ToObject(formType3, 0); } catch { }

                                            var buildStats = buildMethod.Invoke(null, new object[] { hero, buildingSetup, form3 });
                                            if (buildStats != null)
                                            {
                                                // Renamed: this is the in-game "Affinity Bonuses" column
                                                // (the Village Faction Guardian towers, applied per-element).
                                                // Previously misnamed "great_hall_bonus" — the actual Great
                                                // Hall is the Classic Arena rank tier, which is a different
                                                // calc.
                                                sb.Append(",\"affinity_bonus\":");
                                                AppendAllStats(sb, buildStats);
                                            }
                                        }
                                    }
                                    else
                                    {
                                        sb.Append(",\"_gh_err\":\"villageData=" + (villageData != null) + " element=" + heroElement + "\"");
                                    }
                                }
                            }
                        }
                        catch (Exception ex) { sb.Append(",\"_gh_err\":\"" + Esc(ex.InnerException != null ? ex.InnerException.Message : ex.Message) + "\""); }

                        // CalcArtifactsBonus(Hero, List<Artifact>, HeroMetamorphForm) —
                        // authoritative Artifacts column from the in-game's own calc,
                        // including ascend bonuses + glyph upgrades + any hidden bonus
                        // we'd miss aggregating from primary+substats manually.
                        try
                        {
                            var artMethod = heroExtType.GetMethod("CalcArtifactsBonus");
                            if (artMethod == null)
                            {
                                sb.Append(",\"_art_err\":\"CalcArtifactsBonus not found\"");
                            }
                            else
                            {
                                var uwArt = GetUserWrapper();
                                var artWrapper = Prop(uwArt, "Artifacts");
                                var artData = Prop(artWrapper, "ArtifactData");
                                var byHero = Prop(artData, "ArtifactDataByHeroId");
                                int hid = IntProp(hero, "Id");
                                // Use ContainsKey/Item path on the Dictionary (same as
                                // AppendEquippedArtifacts elsewhere in this file).
                                object heroArtData = null;
                                if (byHero != null)
                                {
                                    var ck = byHero.GetType().GetMethod("ContainsKey");
                                    if (ck != null && (bool)ck.Invoke(byHero, new object[] { hid }))
                                    {
                                        var itemProp = byHero.GetType().GetProperty("Item");
                                        heroArtData = itemProp?.GetValue(byHero, new object[] { hid });
                                    }
                                }
                                // Build List<Artifact> via equipment.One(id) for each
                                // equipped artifact_id (same pattern as the existing
                                // AppendEquippedArtifacts code path).
                                Type listOfArt = artMethod.GetParameters()[1].ParameterType;
                                var artList = Activator.CreateInstance(listOfArt);
                                var addArt = listOfArt.GetMethod("Add");
                                var oneMeth = artWrapper.GetType().GetMethod("One");
                                int artListN = 0;
                                if (heroArtData != null && oneMeth != null && addArt != null)
                                {
                                    var byKind = Prop(heroArtData, "ArtifactIdByKind");
                                    if (byKind != null)
                                    {
                                        // Iterate via slot indexer 1..9 (ArtifactKindId enum
                                        // values map to slots; 1=Helmet ... 9=Banner). The
                                        // standard enumerator pattern returns empty for this
                                        // IL2CPP-wrapped Dictionary<EnumKey, Int32>.
                                        var ck = byKind.GetType().GetMethod("ContainsKey");
                                        var idxr = byKind.GetType().GetProperty("Item");
                                        if (ck != null && idxr != null)
                                        {
                                            for (int slot = 1; slot <= 9; slot++)
                                            {
                                                bool has = false;
                                                try { has = (bool)ck.Invoke(byKind, new object[] { slot }); }
                                                catch { continue; }
                                                if (!has) continue;
                                                int aid = 0;
                                                try
                                                {
                                                    var v = idxr.GetValue(byKind, new object[] { slot });
                                                    if (v != null) aid = Convert.ToInt32(v);
                                                }
                                                catch { }
                                                if (aid <= 0) continue;
                                                try
                                                {
                                                    var artObj = oneMeth.Invoke(artWrapper, new object[] { aid });
                                                    if (artObj != null) { addArt.Invoke(artList, new object[] { artObj }); artListN++; }
                                                }
                                                catch { }
                                            }
                                        }
                                    }
                                }
                                var formTypeA = FindType("SharedModel.Meta.Heroes.HeroMetamorphForm");
                                object formA = 0;
                                if (formTypeA != null) try { formA = Enum.ToObject(formTypeA, 0); } catch { }
                                var artStats = artMethod.Invoke(null, new object[] { hero, artList, formA });
                                if (artStats != null)
                                {
                                    sb.Append(",\"artifact_bonus\":");
                                    AppendAllStats(sb, artStats);
                                }
                                else
                                {
                                    sb.Append(",\"_art_err\":\"CalcArtifactsBonus returned null\"");
                                }
                            }
                        }
                        catch (Exception ex)
                        {
                            sb.Append(",\"_art_err\":\"" + Esc(ex.InnerException != null ? ex.InnerException.Message : ex.Message) + "\"");
                        }

                        // CalcRelicsBonus — every silent-exit path now reports a reason.
                        try
                        {
                            var relicSetupType = FindType("SharedModel.Battle.Core.Setup.RelicSetup")
                                              ?? FindType("SharedModel.Meta.Relics.RelicSetup");
                            if (relicSetupType == null)
                            {
                                sb.Append(",\"_relic_err\":\"RelicSetup type not found\"");
                            }
                            else
                            {
                                var uw5 = GetUserWrapper();
                                var relicWrapper = Prop(uw5, "Relics");
                                if (relicWrapper == null)
                                {
                                    sb.Append(",\"_relic_err\":\"UserWrapper.Relics is null\"");
                                }
                                else
                                {
                                    var relicsList = Prop(relicWrapper, "Relics");
                                    if (relicsList == null)
                                    {
                                        sb.Append(",\"_relic_err\":\"Relics list null\"");
                                    }
                                    else
                                    {
                                        // Real method name: PartialCreateFromRelic(Relic) — per
                                        // relic, not a batch. Build a List<RelicSetup> ourselves.
                                        var partialCreate = relicSetupType.GetMethod("PartialCreateFromRelic");
                                        if (partialCreate == null)
                                        {
                                            sb.Append(",\"_relic_err\":\"PartialCreateFromRelic method not found\"");
                                        }
                                        else
                                        {
                                            // Construct a List<RelicSetup>. CalcRelicsBonus expects
                                            // List`1 — match the method's actual parameter type.
                                            var relicMethod = heroExtType.GetMethod("CalcRelicsBonus");
                                            if (relicMethod == null)
                                            {
                                                sb.Append(",\"_relic_err\":\"CalcRelicsBonus method not found\"");
                                            }
                                            else
                                            {
                                                Type listOfSetupType = relicMethod.GetParameters()[1].ParameterType;
                                                var setupList = Activator.CreateInstance(listOfSetupType);
                                                var addMeth = listOfSetupType.GetMethod("Add");
                                                // Filter to relics equipped on THIS hero only.
                                                // RelicDataByHeroId[hero.Id].RelicIds → list of int relic IDs;
                                                // each id resolves to a Relic in relicsList by Relic.Id.
                                                var relicsData = Prop(relicWrapper, "RelicsData");
                                                var byHero = Prop(relicsData, "RelicDataByHeroId");
                                                int heroId = IntProp(hero, "Id");
                                                var byHeroIdx = byHero?.GetType().GetMethod("get_Item", new[] { typeof(int) });
                                                object heroRelicData = null;
                                                if (byHeroIdx != null)
                                                {
                                                    try { heroRelicData = byHeroIdx.Invoke(byHero, new object[] { heroId }); }
                                                    catch { /* hero has no relics — leave list empty */ }
                                                }
                                                var equippedIds = new HashSet<int>();
                                                if (heroRelicData != null)
                                                {
                                                    var ridList = Prop(heroRelicData, "RelicIds");
                                                    if (ridList != null)
                                                    {
                                                        int ridN = IntProp(ridList, "_size");
                                                        var ridItems = Prop(ridList, "_items");
                                                        if (ridItems != null && ridN > 0)
                                                        {
                                                            var getRid = ridItems.GetType().GetMethod("get_Item", new[] { typeof(int) });
                                                            for (int i = 0; i < ridN; i++)
                                                            {
                                                                var idVal = getRid.Invoke(ridItems, new object[] { i });
                                                                if (idVal != null) equippedIds.Add(Convert.ToInt32(idVal));
                                                            }
                                                        }
                                                    }
                                                }
                                                // Only iterate if the hero has at least one
                                                // equipped relic — empty equippedIds means this
                                                // hero has none, so the bonus is 0 (don't sum
                                                // every relic in the vault as a fallback).
                                                if (equippedIds.Count > 0)
                                                {
                                                    int relN = IntProp(relicsList, "_size");
                                                    var relItems = Prop(relicsList, "_items");
                                                    if (relItems != null && relN > 0 && addMeth != null)
                                                    {
                                                        var getRel = relItems.GetType().GetMethod("get_Item", new[] { typeof(int) });
                                                        for (int ri = 0; ri < relN; ri++)
                                                        {
                                                            var relicEntry = getRel.Invoke(relItems, new object[] { ri });
                                                            if (relicEntry == null) continue;
                                                            int rid = IntProp(relicEntry, "Id");
                                                            if (!equippedIds.Contains(rid)) continue;
                                                            try
                                                            {
                                                                var setup = partialCreate.Invoke(null, new object[] { relicEntry });
                                                                if (setup != null) addMeth.Invoke(setupList, new object[] { setup });
                                                            }
                                                            catch { }
                                                        }
                                                    }
                                                }
                                                var formType4 = FindType("SharedModel.Meta.Heroes.HeroMetamorphForm");
                                                object form4 = 0;
                                                if (formType4 != null) try { form4 = Enum.ToObject(formType4, 0); } catch { }
                                                var relicStats = relicMethod.Invoke(null, new object[] { hero, setupList, form4 });
                                                if (relicStats == null)
                                                {
                                                    sb.Append(",\"_relic_err\":\"CalcRelicsBonus returned null\"");
                                                }
                                                else
                                                {
                                                    sb.Append(",\"relic_bonus\":");
                                                    AppendAllStats(sb, relicStats);
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        catch (Exception ex)
                        {
                            sb.Append(",\"_relic_err\":\"" + Esc(ex.InnerException != null ? ex.InnerException.Message : ex.Message) + "\"");
                        }

                        // CalcMasteriesBonus(Hero, List<int> masteryIds, HeroMetamorphForm).
                        // Use the hero's actual Masteries list directly — it's already a
                        // List<int> shape that the IL2CPP runtime accepts.
                        try
                        {
                            var masteryMethod = heroExtType.GetMethod("CalcMasteriesBonus");
                            if (masteryMethod == null)
                            {
                                sb.Append(",\"_mast_err\":\"CalcMasteriesBonus not found\"");
                            }
                            else
                            {
                                var heroMasteries = Prop(hero, "Masteries");
                                var formType5 = FindType("SharedModel.Meta.Heroes.HeroMetamorphForm");
                                object form5 = 0;
                                if (formType5 != null) try { form5 = Enum.ToObject(formType5, 0); } catch { }
                                var mastStats = masteryMethod.Invoke(null, new object[] { hero, heroMasteries, form5 });
                                if (mastStats != null)
                                {
                                    sb.Append(",\"mastery_bonus\":");
                                    AppendAllStats(sb, mastStats);
                                }
                            }
                        }
                        catch (Exception ex)
                        {
                            sb.Append(",\"_mast_err\":\"" + Esc(ex.InnerException != null ? ex.InnerException.Message : ex.Message) + "\"");
                        }

                        // CalcAcademyBonus(Hero, AcademySetup, HeroMetamorphForm) — Faction Guardians.
                        // AcademySetup.Create(UserAcademyGuardiansData, HeroType) — found via
                        // /list-static-methods. The Guardians data lives at
                        // UserWrapper.Academy.Guardians.AcademyData.Guardians, and HeroType
                        // is StaticData.HeroData.HeroTypeById[hero.TypeId].
                        try
                        {
                            var acadMethod = heroExtType.GetMethod("CalcAcademyBonus");
                            if (acadMethod == null)
                            {
                                sb.Append(",\"_fg_err\":\"CalcAcademyBonus method not found\"");
                            }
                            else
                            {
                                var acadSetupType = FindType("SharedModel.Battle.Core.Setup.AcademySetup");
                                if (acadSetupType == null)
                                {
                                    sb.Append(",\"_fg_err\":\"AcademySetup type not found\"");
                                }
                                else
                                {
                                    var createMethod = acadSetupType.GetMethod("Create",
                                        new[] {
                                            FindType("SharedModel.Meta.Academy.User.UserAcademyGuardiansData"),
                                            FindType("SharedModel.Meta.Heroes.HeroType"),
                                        });
                                    if (createMethod == null)
                                    {
                                        sb.Append(",\"_fg_err\":\"AcademySetup.Create overload not found\"");
                                    }
                                    else
                                    {
                                        var uw6 = GetUserWrapper();
                                        var guardians = Prop(Prop(Prop(uw6, "Academy"), "Guardians"), "AcademyData");
                                        var userGuardiansData = Prop(guardians, "Guardians");
                                        // Hero.Type is the resolved HeroType — no dictionary lookup needed.
                                        var heroType = Prop(hero, "Type");
                                        if (userGuardiansData == null || heroType == null)
                                        {
                                            sb.Append(",\"_fg_err\":\"guardians=" + (userGuardiansData != null) + " heroType=" + (heroType != null) + "\"");
                                        }
                                        else
                                        {
                                            object acadSetup = null;
                                            try { acadSetup = createMethod.Invoke(null, new object[] { userGuardiansData, heroType }); }
                                            catch (Exception cex) { sb.Append(",\"_fg_err\":\"Create threw: " + Esc(cex.InnerException != null ? cex.InnerException.Message : cex.Message) + "\""); }
                                            if (acadSetup != null)
                                            {
                                                var formType6 = FindType("SharedModel.Meta.Heroes.HeroMetamorphForm");
                                                object form6 = 0;
                                                if (formType6 != null) try { form6 = Enum.ToObject(formType6, 0); } catch { }
                                                var acadStats = acadMethod.Invoke(null, new object[] { hero, acadSetup, form6 });
                                                if (acadStats != null)
                                                {
                                                    sb.Append(",\"faction_guardians_bonus\":");
                                                    AppendAllStats(sb, acadStats);
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        catch (Exception ex)
                        {
                            sb.Append(",\"_fg_err\":\"" + Esc(ex.InnerException != null ? ex.InnerException.Message : ex.Message) + "\"");
                        }
                    }
                    else
                    {
                        sb.Append(",\"_err\":\"HeroExtensions type not found\"");
                    }
                }
                catch (Exception ex) { sb.Append(",\"_calc_err\":\"" + Esc(ex.Message) + "\""); }

                sb.Append("}");
                count++;
            }

            sb.Append("]}");
            return sb.ToString();
        }

        // =====================================================
        // API: /skill-texts — dump skill names + descriptions (localized text)
        // Lightweight endpoint focused on resolving localization keys.
        // =====================================================

        private string GetSkillTexts(string heroIdStr, string minGradeStr = "")
        {
            var sb = new StringBuilder(32768);
            var uw = GetUserWrapper();
            if (uw == null) return "{\"error\":\"Not logged in\"}";

            int heroId = 0;
            int.TryParse(heroIdStr ?? "", out heroId);
            int minGrade = 0;  // default: all heroes
            if (!string.IsNullOrEmpty(minGradeStr)) int.TryParse(minGradeStr, out minGrade);

            var heroes = Prop(uw, "Heroes");
            var heroData = Prop(heroes, "HeroData");
            var heroDict = Prop(heroData, "HeroById");
            if (heroDict == null) return "{\"error\":\"HeroById null\"}";

            sb.Append("{\"skills\":[");
            int count = 0;

            foreach (var hero in DictValues(heroDict))
            {
                int id = IntProp(hero, "Id");
                if (heroId > 0 && id != heroId) continue;
                int grade = IntProp(hero, "Grade");
                if (heroId == 0 && grade < minGrade) continue;

                var skills = Prop(hero, "Skills");
                if (skills == null) continue;

                foreach (var skill in ListItems(skills))
                {
                    int skillTypeId = IntProp(skill, "TypeId");
                    if (skillTypeId == 0) continue;

                    if (count > 0) sb.Append(",");
                    sb.Append("{\"hero_id\":" + id + ",\"skill_type_id\":" + skillTypeId);

                    try
                    {
                        var skillType = Prop(skill, "Type");
                        if (skillType != null)
                        {
                            bool isDefault = false;
                            try { isDefault = (bool)Prop(skillType, "IsDefault"); } catch { }
                            if (isDefault) sb.Append(",\"is_a1\":true");

                            int cd = IntProp(skillType, "Cooldown");
                            if (cd > 0) sb.Append(",\"cooldown\":" + cd);

                            // Name and Description — resolve via ResolveLocalizedText()
                            foreach (var (propName, jsonKey) in new[] { ("Name", "name"), ("Description", "desc") })
                            {
                                try
                                {
                                    var textObj = Prop(skillType, propName);
                                    if (textObj == null) continue;
                                    string val = ResolveLocalizedText(textObj);
                                    if (!string.IsNullOrEmpty(val) && val.Length > 3 && !val.StartsWith("l10n:"))
                                        sb.Append(",\"" + jsonKey + "\":\"" + Esc(val) + "\"");
                                }
                                catch { }
                            }
                        }
                    }
                    catch { }

                    sb.Append("}");
                    count++;
                }
            }

            sb.Append("],\"count\":" + count + ",\"loc_debug\":\"" + Esc(_locDbg) + "\"}");
            return sb.ToString();
        }

        // =====================================================
        // API: /skill-data — read skill types with multipliers/effects
        // =====================================================

        private string GetSkillData(string heroIdStr, string minGradeStr = "")
        {
            var sb = new StringBuilder(8192);
            var uw = GetUserWrapper();
            if (uw == null) return "{\"error\":\"Not logged in\"}";

            int heroId = 0;
            int.TryParse(heroIdStr, out heroId);
            int minGrade = 6;
            if (!string.IsNullOrEmpty(minGradeStr)) int.TryParse(minGradeStr, out minGrade);

            var heroes = Prop(uw, "Heroes");
            var heroData = Prop(heroes, "HeroData");
            var heroDict = Prop(heroData, "HeroById");
            if (heroDict == null) return "{\"error\":\"HeroById null\"}";

            sb.Append("{\"skills\":[");
            int count = 0;

            // If heroId specified, just get that hero's skills; else filter by min_grade
            foreach (var hero in DictValues(heroDict))
            {
                int id = IntProp(hero, "Id");
                if (heroId > 0 && id != heroId) continue;
                int grade = IntProp(hero, "Grade");
                if (heroId == 0 && grade < minGrade) continue;

                var skills = Prop(hero, "Skills");
                if (skills == null) continue;

                foreach (var skill in ListItems(skills))
                {
                    if (count > 0) sb.Append(",");
                    sb.Append("{\"hero_id\":" + id);

                    int skillTypeId = IntProp(skill, "TypeId");
                    int skillLevel = IntProp(skill, "Level");
                    sb.Append(",\"skill_type_id\":" + skillTypeId + ",\"level\":" + skillLevel);

                    try
                    {
                        var skillType = Prop(skill, "Type");
                        if (skillType != null)
                        {
                            // Name and Description — resolve via ResolveLocalizedText()
                            foreach (var (propName, jsonField) in new[] { ("Name", "name"), ("Description", "desc") })
                            {
                                try
                                {
                                    var textObj = Prop(skillType, propName);
                                    if (textObj == null) continue;
                                    string val = ResolveLocalizedText(textObj);
                                    if (!string.IsNullOrEmpty(val) && val.Length > 3 && !val.StartsWith("l10n:"))
                                        sb.Append(",\"" + jsonField + "\":\"" + Esc(val) + "\"");
                                }
                                catch { }
                            }

                            int cd = IntProp(skillType, "Cooldown");
                            if (cd > 0) sb.Append(",\"cooldown\":" + cd);

                            bool isDefault = false;
                            try { isDefault = (bool)Prop(skillType, "IsDefault"); } catch { }
                            if (isDefault) sb.Append(",\"is_a1\":true");

                            // Effects
                            var effects = Prop(skillType, "Effects");
                            if (effects != null)
                            {
                                sb.Append(",\"effects\":[");
                                int ei = 0;
                                foreach (var eff in ListItems(effects))
                                {
                                    if (ei > 0) sb.Append(",");
                                    sb.Append("{");

                                    int kindId = IntProp(eff, "KindId");
                                    sb.Append("\"kind\":" + kindId);

                                    int effCount = IntProp(eff, "Count");
                                    if (effCount > 0) sb.Append(",\"count\":" + effCount);

                                    // Chance (nullable)
                                    try
                                    {
                                        var chance = Prop(eff, "Chance");
                                        if (chance != null)
                                        {
                                            double ch = ReadFixed(chance);
                                            if (ch > 0) sb.Append(",\"chance\":" + FixedToJson(ch * 100));
                                        }
                                    }
                                    catch { }

                                    // MultiplierFormula
                                    try
                                    {
                                        var formula = Prop(eff, "MultiplierFormula");
                                        if (formula != null)
                                        {
                                            string f = formula.ToString();
                                            if (!string.IsNullOrEmpty(f))
                                                sb.Append(",\"formula\":\"" + Esc(f) + "\"");
                                        }
                                    }
                                    catch { }

                                    // ApplyStatusEffectParams → StatusEffectInfos → TypeId + Duration
                                    // This gives the EXACT buff/debuff type (Poison=80, DEF Down=151, etc.)
                                    try
                                    {
                                        var applyParams = Prop(eff, "ApplyStatusEffectParams");
                                        if (applyParams != null)
                                        {
                                            var infos = Prop(applyParams, "StatusEffectInfos");
                                            if (infos != null)
                                            {
                                                sb.Append(",\"status_effects\":[");
                                                int sei = 0;
                                                foreach (var info in ListItems(infos))
                                                {
                                                    if (sei > 0) sb.Append(",");
                                                    int seTypeId = IntProp(info, "TypeId");
                                                    int seDuration = IntProp(info, "Duration");
                                                    sb.Append("{\"type\":" + seTypeId + ",\"duration\":" + seDuration + "}");
                                                    sei++;
                                                }
                                                sb.Append("]");
                                            }
                                        }
                                    }
                                    catch { }

                                    // StatusParams for debuff details
                                    try
                                    {
                                        var statusParams = Prop(eff, "StatusParams");
                                        if (statusParams != null)
                                        {
                                            int turns = IntProp(statusParams, "Turns");
                                            if (turns > 0) sb.Append(",\"turns\":" + turns);
                                        }
                                    }
                                    catch { }

                                    sb.Append("}");
                                    ei++;
                                }
                                sb.Append("]");
                            }

                            // Skill level bonuses
                            var bonuses = Prop(skillType, "SkillLevelBonuses");
                            if (bonuses != null)
                            {
                                int bCount = IntProp(bonuses, "Count");
                                if (bCount > 0)
                                {
                                    sb.Append(",\"level_bonuses\":[");
                                    int bi = 0;
                                    foreach (var bonus in ListItems(bonuses))
                                    {
                                        if (bi > 0) sb.Append(",");
                                        int bonusType = IntProp(bonus, "SkillBonusType");
                                        double bonusVal = ReadFixed(Prop(bonus, "Value"));
                                        sb.Append("{\"type\":" + bonusType + ",\"value\":" + FixedToJson(bonusVal * 100) + "}");
                                        bi++;
                                    }
                                    sb.Append("]");
                                }
                            }
                        }
                    }
                    catch { }

                    sb.Append("}");
                    count++;
                }

                if (heroId > 0) break;
            }

            sb.Append("]}");
            return sb.ToString();
        }

        // =====================================================
        // API: /enemy-skills?type_id=X — dump any HeroType's skills
        // with full effect details. Reads StaticData.HeroData.HeroTypeById
        // so it works for bosses and enemies (not just user-owned heroes).
        // =====================================================
        private string GetEnemySkills(string typeIdStr)
        {
            if (string.IsNullOrEmpty(typeIdStr)) return "{\"error\":\"type_id required\"}";
            if (!int.TryParse(typeIdStr, out int typeId)) return "{\"error\":\"type_id must be int\"}";
            var sb = new StringBuilder(8192);
            var appModel = GetAppModel();
            if (appModel == null) return "{\"error\":\"AppModel null\"}";

            object heroType = null;
            try
            {
                var staticData = Prop(appModel, "StaticData");
                var heroData = Prop(staticData, "HeroData");
                var htDict = Prop(heroData, "HeroTypeById");
                if (htDict != null)
                {
                    var containsKey = htDict.GetType().GetMethod("ContainsKey");
                    if (containsKey != null && (bool)containsKey.Invoke(htDict, new object[] { typeId }))
                    {
                        var itemProp = htDict.GetType().GetProperty("Item");
                        heroType = itemProp?.GetValue(htDict, new object[] { typeId });
                    }
                }
            }
            catch (Exception ex) { return "{\"error\":\"" + Esc(ex.Message) + "\"}"; }

            if (heroType == null) return "{\"error\":\"type_id " + typeId + " not found\"}";

            sb.Append("{\"type_id\":" + typeId);
            try
            {
                var nameObj = Prop(heroType, "Name");
                string nm = null;
                if (nameObj != null)
                {
                    try { nm = Prop(nameObj, "LocalizedValue")?.ToString(); } catch { }
                    if (string.IsNullOrEmpty(nm) || nm.Contains("SharedLTextKey"))
                        try { nm = Prop(nameObj, "Key")?.ToString(); } catch { }
                }
                if (!string.IsNullOrEmpty(nm)) sb.Append(",\"name\":\"" + Esc(nm) + "\"");
            }
            catch { }

            sb.Append(",\"skills\":[");
            int si = 0;
            try
            {
                // Use AllSkillTypes on HeroType — HeroForm only has SkillTypeIds (ints)
                var skills = Prop(heroType, "AllSkillTypes");
                if (skills != null)
                {
                    {
                        foreach (var skillType in ListItems(skills))
                        {
                            if (si > 0) sb.Append(",");
                            sb.Append("{");

                            int stTypeId = IntProp(skillType, "Id");
                            if (stTypeId == 0) stTypeId = IntProp(skillType, "TypeId");
                            sb.Append("\"skill_type_id\":" + stTypeId);

                            try
                            {
                                foreach (var (propName, jsonField) in new[] { ("Name", "name"), ("Description", "desc") })
                                {
                                    var textObj = Prop(skillType, propName);
                                    if (textObj == null) continue;
                                    string val = ResolveLocalizedText(textObj);
                                    if (!string.IsNullOrEmpty(val) && val.Length > 3 && !val.StartsWith("l10n:"))
                                        sb.Append(",\"" + jsonField + "\":\"" + Esc(val) + "\"");
                                }
                            }
                            catch { }

                            int cd = IntProp(skillType, "Cooldown");
                            if (cd > 0) sb.Append(",\"cooldown\":" + cd);

                            var effects = Prop(skillType, "Effects");
                            if (effects != null)
                            {
                                sb.Append(",\"effects\":[");
                                int ei = 0;
                                foreach (var eff in ListItems(effects))
                                {
                                    if (ei > 0) sb.Append(",");
                                    sb.Append("{");
                                    int kindId = IntProp(eff, "KindId");
                                    sb.Append("\"kind\":" + kindId);
                                    int effCount = IntProp(eff, "Count");
                                    if (effCount > 0) sb.Append(",\"count\":" + effCount);
                                    try
                                    {
                                        var chance = Prop(eff, "Chance");
                                        if (chance != null)
                                        {
                                            double ch = ReadFixed(chance);
                                            if (ch > 0) sb.Append(",\"chance\":" + FixedToJson(ch * 100));
                                        }
                                    } catch { }
                                    try
                                    {
                                        var formula = Prop(eff, "MultiplierFormula");
                                        if (formula != null)
                                        {
                                            string f = formula.ToString();
                                            if (!string.IsNullOrEmpty(f)) sb.Append(",\"formula\":\"" + Esc(f) + "\"");
                                        }
                                    } catch { }
                                    try
                                    {
                                        var applyParams = Prop(eff, "ApplyStatusEffectParams");
                                        if (applyParams != null)
                                        {
                                            var infos = Prop(applyParams, "StatusEffectInfos");
                                            if (infos != null)
                                            {
                                                sb.Append(",\"status_effects\":[");
                                                int sei = 0;
                                                foreach (var info in ListItems(infos))
                                                {
                                                    if (sei > 0) sb.Append(",");
                                                    int seType = IntProp(info, "TypeId");
                                                    int seDur = IntProp(info, "Duration");
                                                    sb.Append("{\"type\":" + seType + ",\"duration\":" + seDur + "}");
                                                    sei++;
                                                }
                                                sb.Append("]");
                                            }
                                        }
                                    } catch { }
                                    sb.Append("}");
                                    ei++;
                                }
                                sb.Append("]");
                            }
                            sb.Append("}");
                            si++;
                        }
                    }
                }
            }
            catch (Exception ex) { sb.Append("],\"_err\":\"" + Esc(ex.Message) + "\""); sb.Append("}"); return sb.ToString(); }
            sb.Append("]}");
            return sb.ToString();
        }

        // =====================================================
        // API: /all-artifacts — every artifact in the account
        // =====================================================

        private string GetAllArtifacts(string offsetStr = "", string limitStr = "")
        {
            var sb = new StringBuilder(65536);
            var uw = GetUserWrapper();
            if (uw == null) return "{\"error\":\"Not logged in\"}";

            int offset = 0, limit = 200;
            int.TryParse(offsetStr, out offset);
            if (int.TryParse(limitStr, out int pl) && pl > 0) limit = pl;

            var equipment = Prop(uw, "Artifacts");
            if (equipment == null) return "{\"error\":\"No equipment wrapper\"}";

            var artData = Prop(equipment, "ArtifactData");

            // Build reverse map: artifact_id -> (hero_id, slot)
            var artToHero = new Dictionary<int, (int heroId, int slot)>();
            if (artData != null)
            {
                var byHero = Prop(artData, "ArtifactDataByHeroId");
                if (byHero != null)
                {
                    foreach (var heroEntry in DictEntries(byHero))
                    {
                        int heroId = heroEntry.Key;
                        var heroArtData = heroEntry.Value;
                        if (heroArtData == null) continue;
                        var idByKind = Prop(heroArtData, "ArtifactIdByKind");
                        if (idByKind == null) continue;
                        foreach (var slotEntry in DictEntries(idByKind))
                        {
                            int slot = slotEntry.Key;
                            int artId = 0;
                            try { artId = Convert.ToInt32(slotEntry.Value); } catch { }
                            if (artId > 0)
                                artToHero[artId] = (heroId, slot);
                        }
                    }
                }
            }

            // Try TWO approaches to get artifacts:
            // 1. Use the "All" IEnumerable property (iterates all artifacts correctly)
            // 2. Fall back to One(id) scan if All doesn't work

            var allProp = Prop(equipment, "All");
            var oneMethod = equipment.GetType().GetMethod("One");
            int lastId = 0;
            try { lastId = IntProp(artData, "LastArtifactId"); } catch { }

            sb.Append("{\"last_id\":" + lastId + ",\"equipped_map\":" + artToHero.Count + ",\"artifacts\":[");

            int idx = 0, written = 0;

            // Approach 1: Use All property (IEnumerable<Artifact>)
            if (allProp != null)
            {
                try
                {
                    foreach (var art in ListItems(allProp))
                    {
                        if (art == null) continue;
                        int kind = IntProp(art, "KindId");
                        if (kind <= 0) continue;

                        if (idx < offset) { idx++; continue; }
                        if (written >= limit) break;

                        if (written > 0) sb.Append(",");
                        int mark = sb.Length;
                        try
                        {
                            int artId = IntProp(art, "Id");
                            AppendArtifact(sb, art);
                            if (artToHero.TryGetValue(artId, out var equip))
                            {
                                sb.Length--;
                                sb.Append(",\"hero_id\":" + equip.heroId + ",\"slot\":" + equip.slot + "}");
                            }
                        }
                        catch
                        {
                            sb.Length = mark;
                        }
                        written++;
                        idx++;
                    }
                }
                catch (Exception ex)
                {
                    sb.Append("],\"_all_err\":\"" + Esc(ex.Message) + "\"}");
                    return sb.ToString();
                }
            }

            // Approach 2: Fallback to One(id) scan if All didn't find anything
            if (written == 0 && oneMethod != null && lastId > 0)
            {
                idx = 0;
                for (int artId = 1; artId <= lastId && written < limit; artId++)
                {
                    object art = null;
                    try { art = oneMethod.Invoke(equipment, new object[] { artId }); } catch { continue; }
                    if (art == null) continue;

                    int kind = IntProp(art, "KindId");
                    if (kind <= 0) continue;

                    if (idx < offset) { idx++; continue; }

                    if (written > 0) sb.Append(",");
                    int mark = sb.Length;
                    try
                    {
                        AppendArtifact(sb, art);
                        if (artToHero.TryGetValue(artId, out var equip))
                        {
                            sb.Length--;
                            sb.Append(",\"hero_id\":" + equip.heroId + ",\"slot\":" + equip.slot + "}");
                        }
                    }
                    catch
                    {
                        sb.Length = mark;
                        sb.Append("{\"id\":" + artId + ",\"error\":true}");
                    }
                    written++;
                }
            }

            sb.Append("],\"method\":\"" + (written > 0 && allProp != null ? "All" : "One") + "\"}");
            return sb.ToString();
        }

        // Iterate dict as KeyValuePair entries
        private static IEnumerable<(int Key, object Value)> DictEntries(object dict)
        {
            if (dict == null) yield break;
            var getEnum = dict.GetType().GetMethod("GetEnumerator");
            var enumerator = getEnum.Invoke(dict, null);
            var enumType = enumerator.GetType();
            var moveNext = enumType.GetMethod("MoveNext");
            var currentProp = enumType.GetProperty("Current");
            while ((bool)moveNext.Invoke(enumerator, null))
            {
                var kvp = currentProp.GetValue(enumerator);
                int key = 0;
                try { key = Convert.ToInt32(Prop(kvp, "Key")); } catch { }
                var val = Prop(kvp, "Value");
                yield return (key, val);
            }
        }

        // =====================================================
        // API: /account — Great Hall, Arena, Alliance data
        // =====================================================

        private string GetAccountData()
        {
            var sb = new StringBuilder(4096);
            var uw = GetUserWrapper();
            if (uw == null) return "{\"error\":\"Not logged in\"}";

            sb.Append("{");

            // Great Hall — read from Village data's CapitolBonusLevelByStatByElement dict
            try
            {
                var village = Prop(uw, "Village");
                if (village != null)
                {
                    var villageData = Prop(village, "VillageData");
                    if (villageData == null) villageData = Prop(village, "Data");
                    if (villageData != null)
                    {
                        var capitolDict = Prop(villageData, "CapitolBonusLevelByStatByElement");
                        if (capitolDict != null)
                        {
                            sb.Append("\"great_hall\":");
                            // Dict<Element, Dict<StatKindId, int>> — serialize as nested JSON
                            AppendDictOfDicts(sb, capitolDict);
                        }
                        else
                        {
                            sb.Append("\"great_hall\":{}");
                        }
                    }
                    else
                    {
                        sb.Append("\"great_hall_note\":\"no village data\"");
                    }
                }
            }
            catch (Exception ex) { sb.Append("\"great_hall_error\":\"" + Esc(ex.Message) + "\""); }

            // Arena — league tier
            try
            {
                var arena = Prop(uw, "Arena");
                if (arena != null)
                {
                    var league = Prop(arena, "League");
                    int points = IntProp(arena, "Points");
                    sb.Append(",\"arena\":{\"league\":" + Convert.ToInt32(league) +
                              ",\"points\":" + points + "}");
                }
            }
            catch (Exception ex) { sb.Append(",\"arena_error\":\"" + Esc(ex.Message) + "\""); }

            // Alliance — clan level
            try
            {
                var alliance = Prop(uw, "Alliance");
                if (alliance != null)
                {
                    // Use reflection to get the specific "Level" property (AllianceLevelWrapperReadOnly type)
                    var allianceType = alliance.GetType();
                    System.Reflection.PropertyInfo levelProp = null;
                    foreach (var p in allianceType.GetProperties())
                    {
                        if (p.Name == "Level" && p.PropertyType.Name.Contains("AllianceLevel"))
                        {
                            levelProp = p;
                            break;
                        }
                    }
                    if (levelProp != null)
                    {
                        var levelWrapper = levelProp.GetValue(alliance);
                        int clanLevel = IntProp(levelWrapper, "Current");
                        sb.Append(",\"clan\":{\"level\":" + clanLevel + "}");
                    }
                    else
                    {
                        // Fallback via Data property
                        var data = Prop(alliance, "Data");
                        if (data != null)
                        {
                            int clanLevel = IntProp(data, "Level");
                            sb.Append(",\"clan\":{\"level\":" + clanLevel + "}");
                        }
                    }
                }
            }
            catch (Exception ex) { sb.Append(",\"clan_error\":\"" + Esc(ex.Message) + "\""); }

            // Account level
            try
            {
                var account = Prop(uw, "Account");
                if (account != null)
                {
                    // AccountWrapper should have Level property
                    int accountLevel = IntProp(account, "Level");
                    sb.Append(",\"account_level\":" + accountLevel);
                }
            }
            catch { }

            sb.Append("}");
            return sb.ToString();
        }
    }
}
