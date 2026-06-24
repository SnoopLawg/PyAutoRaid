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

            // Resolve the AcademyGuardiansWrapper.Has(Hero) check once so
            // each AppendHero call can decide per-hero whether the champ is
            // currently assigned to a Faction Guardian slot. Heroes assigned
            // as guardians can NEVER be sacrificed/ranked-up — the cmd will
            // fail server-side with AcademyGuardians_HeroAlreadyInSlot.
            object guardiansWrap = null;
            MethodInfo guardiansHasM = null;
            try
            {
                var academy = Prop(uw, "Academy");
                if (academy != null)
                {
                    guardiansWrap = Prop(academy, "Guardians");
                    if (guardiansWrap != null)
                    {
                        var heroT = FindType("SharedModel.Meta.Heroes.Hero");
                        if (heroT != null)
                        {
                            guardiansHasM = guardiansWrap.GetType().GetMethod("Has",
                                BindingFlags.Public | BindingFlags.Instance,
                                null, new[] { heroT }, null);
                        }
                    }
                }
            }
            catch { /* leave guardians* null; per-hero check returns false */ }

            // Pre-compute set of hero TypeIds that are ingredients in any
            // fusion recipe AVAILABLE TO THIS USER (per UserHeroData
            // FuseInfosByOutputHeroId). Walks SharedModelManager.GameParameters
            // .FuseSettings.FuseHeroRecipesSettings, filters to recipes whose
            // OutputHeroId appears in the user's FuseInfosByOutputHeroId map,
            // then collects each recipe's HeroMaterials[].HeroTypeId.
            var fusionIngredientTypeIds = TryReadFusionIngredientTypeIds(uw);

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
                bool isGuardian = false;
                try
                {
                    if (guardiansHasM != null)
                        isGuardian = (bool)guardiansHasM.Invoke(guardiansWrap, new object[] { hero });
                }
                catch { }
                bool isFusionIngredient = false;
                try
                {
                    if (fusionIngredientTypeIds != null && fusionIngredientTypeIds.Count > 0)
                    {
                        int tid = IntProp(hero, "TypeId");
                        isFusionIngredient = fusionIngredientTypeIds.Contains(tid);
                    }
                }
                catch { }
                try { AppendHero(sb, hero, equipment, isGuardian, isFusionIngredient); }
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

        /// <summary>
        /// Walk SharedModelManager.GameParameters.FuseSettings.FuseHeroRecipesSettings,
        /// filter recipes whose OutputHeroId appears in the user's
        /// FuseInfosByOutputHeroId (i.e. fusions currently AVAILABLE to this user),
        /// and return the set of HeroTypeIds that appear as ingredients in those
        /// recipes. Heroes with these TypeIds should NEVER be sacrificed.
        /// Empty set on any reflection failure.
        /// </summary>
        private HashSet<int> TryReadFusionIngredientTypeIds(object uw)
        {
            var typeIds = new HashSet<int>();
            try
            {
                // The game pre-computes a HashSet<int> of fusion-material hero
                // TypeIds inside HeroFuseWrapper._fuseMaterialHeroes. We just
                // mirror it. This already filters by availability windows AND
                // by which fusions the user has access to.
                var heroes = Prop(uw, "Heroes");
                var fuseWrap = Prop(heroes, "Fuse");
                if (fuseWrap == null) { Logger.LogWarning("[Fusion] Heroes.Fuse null"); return typeIds; }

                // Il2CppInterop exposes private IL2CPP fields as properties on
                // the C# side (same gotcha as the rank-up DTO). Use GetProperty.
                var matProp = fuseWrap.GetType().GetProperty("_fuseMaterialHeroes",
                    BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                int matCountObserved = 0;
                if (matProp != null)
                {
                    var matSet = matProp.GetValue(fuseWrap);
                    if (matSet is IEnumerable matEnum)
                    {
                        foreach (var v in matEnum)
                        {
                            if (v is int vi) { typeIds.Add(vi); matCountObserved++; }
                            else if (int.TryParse(v?.ToString() ?? "", out int vp)) { typeIds.Add(vp); matCountObserved++; }
                        }
                    }
                }
                Logger.LogInfo("[Fusion] _fuseMaterialHeroes count=" + matCountObserved);

                // Walk _availableRecipes — if matCountObserved was 0, this also
                // gives us materials directly from each recipe's HeroMaterials.
                var availProp = fuseWrap.GetType().GetProperty("_availableRecipes",
                    BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                int recipeCount = 0;
                if (availProp != null)
                {
                    var availList = availProp.GetValue(fuseWrap);
                    if (availList != null)
                    {
                        foreach (var recipe in ListItems(availList))
                        {
                            if (recipe == null) continue;
                            recipeCount++;
                            int outputId = IntProp(recipe, "OutputHeroId");
                            if (outputId == 0) outputId = IntProp(recipe, "InitialOutputHeroId");
                            if (outputId > 0) typeIds.Add(outputId);
                            // Walk this recipe's materials too as a fallback.
                            var materials = Prop(recipe, "HeroMaterials");
                            if (materials != null)
                            {
                                foreach (var mat in ListItems(materials))
                                {
                                    if (mat == null) continue;
                                    int matTypeId = IntProp(mat, "HeroTypeId");
                                    if (matTypeId > 0) typeIds.Add(matTypeId);
                                }
                            }
                        }
                    }
                }
                Logger.LogInfo("[Fusion] _availableRecipes count=" + recipeCount);

                // Static fallback: walk every recipe in
                // SharedModelManager.GameParameters.FuseSettings.FuseHeroRecipesSettings
                // and add every hero TypeId that's used (active or historical).
                // The "permissive" approach matches the user's mental model:
                // "Diabolist is a fusion hero" — Plarium reuses common heroes
                // across many time-limited fusion events, so even if today's
                // recipes don't include Diabolist, the next event might.
                int activeHits = 0, historicalHits = 0;
                try
                {
                    var smm = FindType("SharedModel.SharedModelManager") ?? FindType("SharedModelManager");
                    var gpAcc = smm?.GetProperty("GameParameters",
                        BindingFlags.Public | BindingFlags.Static | BindingFlags.NonPublic);
                    var gp = gpAcc?.GetValue(null);
                    var fuseSettings = gp != null ? Prop(gp, "FuseSettings") : null;
                    var settingsList = fuseSettings != null ? Prop(fuseSettings, "FuseHeroRecipesSettings") : null;
                    if (settingsList != null)
                    {
                        var nowUtc = DateTime.UtcNow;
                        foreach (var rec in ListItems(settingsList))
                        {
                            if (rec == null) continue;
                            historicalHits++;
                            var fromCdt = Prop(rec, "AvailableFrom");
                            var toCdt = Prop(rec, "AvailableTo");
                            if (IsConfigDateInRange(fromCdt, toCdt, nowUtc)) activeHits++;
                            int outputId = IntProp(rec, "OutputHeroId");
                            if (outputId > 0) typeIds.Add(outputId);
                            var materials = Prop(rec, "HeroMaterials");
                            if (materials == null) continue;
                            foreach (var mat in ListItems(materials))
                            {
                                if (mat == null) continue;
                                int matTypeId = IntProp(mat, "HeroTypeId");
                                if (matTypeId > 0) typeIds.Add(matTypeId);
                            }
                        }
                    }
                }
                catch (Exception ex2)
                {
                    Logger.LogWarning("[Fusion] static walk failed: " + ex2.Message);
                }
                Logger.LogInfo("[Fusion] static recipes: " + activeHits + " active / "
                    + historicalHits + " total, " + typeIds.Count + " unique TypeIds protected");
                Logger.LogInfo("[Fusion] ingredient TypeIds=" + typeIds.Count);
            }
            catch (Exception ex)
            {
                Logger.LogWarning("[Fusion] read failed: " + ex.Message);
            }
            return typeIds;
        }

        /// <summary>
        /// ConfigDateTime range check. Returns true if `now` is within
        /// [from, to]. Either bound may be null (treat as open-ended).
        /// </summary>
        private bool IsConfigDateInRange(object fromCdt, object toCdt, DateTime now)
        {
            try
            {
                DateTime? from = ConfigDateToDateTime(fromCdt);
                DateTime? to = ConfigDateToDateTime(toCdt);
                if (from.HasValue && now < from.Value) return false;
                if (to.HasValue && now > to.Value) return false;
                return true;
            }
            catch { return false; }
        }

        private DateTime? ConfigDateToDateTime(object cdt)
        {
            if (cdt == null) return null;
            try
            {
                int y = IntProp(cdt, "Year"), mo = IntProp(cdt, "Month"), d = IntProp(cdt, "Day");
                int h = IntProp(cdt, "Hour"), mi = IntProp(cdt, "Minute"), s = IntProp(cdt, "Second");
                if (y == 0) return null;
                return new DateTime(y, mo == 0 ? 1 : mo, d == 0 ? 1 : d,
                                    h, mi, s, DateTimeKind.Utc);
            }
            catch { return null; }
        }

        /// <summary>
        /// Walk userdata's Academy Guardians data structure and collect every hero ID
        /// currently assigned to a guardian slot (across all factions and rarities).
        /// Returns a HashSet of hero instance IDs. Empty on any failure.
        /// (No longer wired into /all-heroes — superseded by Guardians.Has(Hero) per-hero.)
        /// </summary>
        private HashSet<int> TryReadAcademyGuardianHeroIds(object uw)
        {
            var ids = new HashSet<int>();
            try
            {
                // Try several paths to find AcademyGuardians data on the user wrapper.
                // The IL2Cpp class is UserAcademyGuardiansData with field SlotsByFraction.
                object academy = null;
                foreach (var name in new[] { "Academy", "AcademyData", "AcademyGuardians" })
                {
                    try { academy = Prop(uw, name); if (academy != null) break; } catch { }
                }
                if (academy == null) return ids;
                // If we got "Academy" wrapper, drill into Guardians/AcademyGuardians.
                object guardians = academy;
                foreach (var name in new[] { "AcademyGuardians", "Guardians", "Data" })
                {
                    try
                    {
                        var sub = Prop(guardians, name);
                        if (sub != null && sub.GetType().GetProperty("SlotsByFraction") != null)
                        {
                            guardians = sub;
                            break;
                        }
                    }
                    catch { }
                }
                var slotsByFraction = Prop(guardians, "SlotsByFraction");
                if (slotsByFraction == null) return ids;

                // SlotsByFraction is Dictionary<HeroFraction, AcademyGuardiansRaritySlots>.
                // Iterate Values, then SlotsByRarity Values, then List<AcademyGuardiansSlot>.
                foreach (var raritySlots in DictValues(slotsByFraction))
                {
                    if (raritySlots == null) continue;
                    var slotsByRarity = Prop(raritySlots, "SlotsByRarity");
                    if (slotsByRarity == null) continue;
                    foreach (var slotList in DictValues(slotsByRarity))
                    {
                        if (slotList == null) continue;
                        foreach (var slot in ListItems(slotList))
                        {
                            if (slot == null) continue;
                            // FirstHero / SecondHero are Nullable<int>.
                            foreach (var name in new[] { "FirstHero", "SecondHero" })
                            {
                                try
                                {
                                    var v = slot.GetType().GetProperty(name)?.GetValue(slot);
                                    if (v == null) continue;
                                    // Nullable wrapper — try Value/HasValue, fallback to direct cast.
                                    var hasValueProp = v.GetType().GetProperty("HasValue");
                                    var valueProp = v.GetType().GetProperty("Value");
                                    if (hasValueProp != null && valueProp != null)
                                    {
                                        bool has = (bool)hasValueProp.GetValue(v);
                                        if (has)
                                        {
                                            int hid = (int)valueProp.GetValue(v);
                                            if (hid > 0) ids.Add(hid);
                                        }
                                    }
                                    else if (v is int i)
                                    {
                                        if (i > 0) ids.Add(i);
                                    }
                                }
                                catch { }
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Logger.LogWarning("[Guardians] read failed: " + ex.Message);
            }
            return ids;
        }

        private void AppendHero(StringBuilder sb, object hero, object equipment, bool isGuardian = false, bool isFusionIngredient = false)
        {
            int id = IntProp(hero, "Id");
            int typeId = IntProp(hero, "TypeId");
            int grade = IntProp(hero, "Grade");
            int level = IntProp(hero, "Level");
            int empower = IntProp(hero, "EmpowerLevel");

            bool locked = false, inStorage = false, inBathhouse = false;
            try { var p = hero.GetType().GetProperty("Locked"); if (p != null) locked = (bool)p.GetValue(hero); } catch { }
            try { var p = hero.GetType().GetProperty("InStorage"); if (p != null) inStorage = (bool)p.GetValue(hero); } catch { }
            try { var p = hero.GetType().GetProperty("InBathhouse"); if (p != null) inBathhouse = (bool)p.GetValue(hero); } catch { }

            sb.Append("{\"id\":" + id + ",\"type_id\":" + typeId +
                      ",\"grade\":" + grade + ",\"level\":" + level +
                      ",\"empower\":" + empower +
                      ",\"locked\":" + (locked ? "true" : "false") +
                      ",\"in_storage\":" + (inStorage ? "true" : "false") +
                      ",\"in_bathhouse\":" + (inBathhouse ? "true" : "false") +
                      ",\"is_faction_guardian\":" + (isGuardian ? "true" : "false") +
                      ",\"is_fusion_ingredient\":" + (isFusionIngredient ? "true" : "false"));

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

                    // BlessingId is Nullable<BlessingTypeId> (IL2CPP nullable enum).
                    // The .Value property getter returns marshaled garbage for
                    // IL2CPP Nullable wrappers — read the lowercase backing
                    // fields `hasValue` and `value` directly. Same pattern as
                    // StaticData.cs SerializeValue's Nullable handling.
                    blessingId = ReadIl2CppNullableEnumInt(
                        Prop(dblAscend, "BlessingId"));

                    if (blessingId > 0)
                        sb.Append(",\"blessing\":{\"id\":" + blessingId +
                                  ",\"grade\":" + ascendGrade + "}");
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

            // PREFER raw long fields — Fixed64.ToString() truncates precision
            // (often to ~2 decimals), so the underlying 32.32 raw value via
            // raw / 2^32 is more accurate. Only fall back to ToString if the
            // raw access fails.
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

            // Fallback: ToString parse, then Convert.ToDouble.
            string str = fixedVal.ToString();
            if (double.TryParse(str, System.Globalization.NumberStyles.Any,
                System.Globalization.CultureInfo.InvariantCulture, out double parsed))
            {
                if (!double.IsNaN(parsed) && !double.IsInfinity(parsed))
                    return parsed;
            }
            try { return Convert.ToDouble(fixedVal); } catch { }
            return 0;
        }

        private string FixedToJson(double val)
        {
            if (double.IsNaN(val) || double.IsInfinity(val)) return "0";
            // F10 preserves enough precision to reveal the real Fixed64 fractional
            // bits (e.g. 125.4999990463 vs apparent 125.5) so Python summation
            // matches the in-game total exactly when floored.
            return val.ToString("F10", System.Globalization.CultureInfo.InvariantCulture);
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

            // RequiredFraction — non-zero for accessories (kinds 7/8/9), which
            // are faction-locked. Picker must match this against hero.fraction.
            try
            {
                int reqFraction = IntProp(art, "RequiredFraction");
                if (reqFraction != 0)
                    sb.Append(",\"req_fraction\":" + reqFraction);
            }
            catch { }

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
                                // Emit ALL 8 stats. RES/ACC/CR/CD are "absolute"
                                // stats stored in FlatBonus (they were 0 in
                                // PercentBonus). Summing these across pieces gives
                                // the game-truth per-artifact contribution
                                // INCLUDING accessory ascension — which the
                                // Python-side substat reconstruction can't see.
                                // CR/CD come out as fractions (0.07 = +7% CR,
                                // 1.30 = +130% CD); the consumer scales ×100.
                                sb.Append(",\"flat_bonus\":{");
                                AppendFixed(sb, flatBonus, "Health", "HP");
                                sb.Append(","); AppendFixed(sb, flatBonus, "Attack", "ATK");
                                sb.Append(","); AppendFixed(sb, flatBonus, "Defence", "DEF");
                                sb.Append(","); AppendFixed(sb, flatBonus, "Speed", "SPD");
                                sb.Append(","); AppendFixed(sb, flatBonus, "Resistance", "RES");
                                sb.Append(","); AppendFixed(sb, flatBonus, "Accuracy", "ACC");
                                sb.Append(","); AppendFixed(sb, flatBonus, "CriticalChance", "CR");
                                sb.Append(","); AppendFixed(sb, flatBonus, "CriticalDamage", "CD");
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
                                // Use the same GetEnumerator + MoveNext + Current pattern that
                                // AppendEquippedArtifacts uses successfully. The IL2CPP-wrapped
                                // Dictionary<ArtifactKindId, int> rejects ContainsKey(int) but
                                // the enumerator pattern works.
                                // CalcArtifactsBonus takes List<ArtifactSetup>, not List<Artifact>.
                                // Wrap each Artifact via ArtifactSetup.FromArtifact before adding.
                                var artSetupType = FindType("SharedModel.Battle.Core.Setup.ArtifactSetup");
                                var fromArtMeth = artSetupType?.GetMethod("FromArtifact");
                                if (heroArtData != null && oneMeth != null && addArt != null && fromArtMeth != null)
                                {
                                    var byKind = Prop(heroArtData, "ArtifactIdByKind");
                                    if (byKind != null)
                                    {
                                        try
                                        {
                                            var dictType2 = byKind.GetType();
                                            var getEnum2 = dictType2.GetMethod("GetEnumerator");
                                            if (getEnum2 != null)
                                            {
                                                var enum2 = getEnum2.Invoke(byKind, null);
                                                var enumType2 = enum2.GetType();
                                                var moveNext2 = enumType2.GetMethod("MoveNext");
                                                var currentProp2 = enumType2.GetProperty("Current");
                                                while ((bool)moveNext2.Invoke(enum2, null))
                                                {
                                                    try
                                                    {
                                                        var kvp = currentProp2.GetValue(enum2);
                                                        int aid = IntProp(kvp, "Value");
                                                        if (aid <= 0) continue;
                                                        var artObj = oneMeth.Invoke(artWrapper, new object[] { aid });
                                                        if (artObj == null) continue;
                                                        var setup = fromArtMeth.Invoke(null, new object[] { artObj });
                                                        if (setup != null) { addArt.Invoke(artList, new object[] { setup }); artListN++; }
                                                    }
                                                    catch { }
                                                }
                                            }
                                        }
                                        catch { }
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

                        // CalcMasteriesBonus(Hero, List<ArtifactSetup>, HeroMetamorphForm).
                        // BUG FIX 2026-06-04: previous version passed hero.Masteries
                        // (List<int>) as the 2nd arg — IL2CPP silently coerced and
                        // returned 0 SPD/ACC/etc., dropping all flat mastery bonuses.
                        // The real signature wants the SAME List<ArtifactSetup> the
                        // artifact calc uses (because masteries like Lore of Steel
                        // depend on set bonuses from equipped gear).
                        // Verified vs in-game UI: Maneater +5 SPD, Demytha +2 SPD,
                        // Ninja +4 SPD from masteries column — all returned 0
                        // before this fix.
                        try
                        {
                            var masteryMethod = heroExtType.GetMethod("CalcMasteriesBonus");
                            if (masteryMethod == null)
                            {
                                sb.Append(",\"_mast_err\":\"CalcMasteriesBonus not found\"");
                            }
                            else
                            {
                                // Re-build List<ArtifactSetup> for the hero (same shape
                                // as the artifact_bonus calc uses above). Scoped inside
                                // a try block; outer try preserved by the parent.
                                var paramType = masteryMethod.GetParameters()[1].ParameterType;
                                var mastArtList = Activator.CreateInstance(paramType);
                                var addM = paramType.GetMethod("Add");
                                var artSetupTypeM = FindType("SharedModel.Battle.Core.Setup.ArtifactSetup");
                                var fromArtMethM = artSetupTypeM?.GetMethod("FromArtifact");
                                var uwM = GetUserWrapper();
                                var artWrapperM = Prop(uwM, "Artifacts");
                                var oneMethM = artWrapperM?.GetType().GetMethod("One");
                                var artDataM = Prop(artWrapperM, "ArtifactData");
                                var byHeroM = Prop(artDataM, "ArtifactDataByHeroId");
                                int hidM = IntProp(hero, "Id");
                                if (byHeroM != null && oneMethM != null && addM != null && fromArtMethM != null)
                                {
                                    var ckM = byHeroM.GetType().GetMethod("ContainsKey");
                                    if (ckM != null && (bool)ckM.Invoke(byHeroM, new object[] { hidM }))
                                    {
                                        var itemPropM = byHeroM.GetType().GetProperty("Item");
                                        var heroArtDataM = itemPropM?.GetValue(byHeroM, new object[] { hidM });
                                        var byKindM = Prop(heroArtDataM, "ArtifactIdByKind");
                                        if (byKindM != null)
                                        {
                                            try
                                            {
                                                var getEnumM = byKindM.GetType().GetMethod("GetEnumerator");
                                                if (getEnumM != null)
                                                {
                                                    var enumM = getEnumM.Invoke(byKindM, null);
                                                    var moveNextM = enumM.GetType().GetMethod("MoveNext");
                                                    var currentPropM = enumM.GetType().GetProperty("Current");
                                                    while ((bool)moveNextM.Invoke(enumM, null))
                                                    {
                                                        try
                                                        {
                                                            var kvpM = currentPropM.GetValue(enumM);
                                                            int aidM = IntProp(kvpM, "Value");
                                                            if (aidM <= 0) continue;
                                                            var artObjM = oneMethM.Invoke(artWrapperM, new object[] { aidM });
                                                            if (artObjM == null) continue;
                                                            var setupM = fromArtMethM.Invoke(null, new object[] { artObjM });
                                                            if (setupM != null) addM.Invoke(mastArtList, new object[] { setupM });
                                                        }
                                                        catch { }
                                                    }
                                                }
                                            }
                                            catch { }
                                        }
                                    }
                                }
                                var formType5 = FindType("SharedModel.Meta.Heroes.HeroMetamorphForm");
                                object form5 = 0;
                                if (formType5 != null) try { form5 = Enum.ToObject(formType5, 0); } catch { }
                                var mastStats = masteryMethod.Invoke(null, new object[] { hero, mastArtList, form5 });
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

            // Default limit raised from 200 to 50000 so a single call returns the
            // whole vault. 200 hid 90%+ of the artifacts on real accounts (verified
            // 2026-05-04: account had 2692 artifacts; default returned only 200,
            // making top SPD substats look capped at +18 when real max was +24).
            // Pagination still available via explicit ?offset=N&limit=M.
            int offset = 0, limit = 50000;
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

        // =====================================================
        // API: /user-relics
        //
        // Returns the live relic state on the user account:
        //   - relics:      every relic in the user's vault
        //   - stones:      every relic stone in the user's vault
        //   - hero_assign: { hero_id -> [relic_id, ...] } (per-hero equipped relics)
        //
        // Consumers (hero_stats / gear_optimizer) use this to know which
        // stats are already supplied by the equipped relic so they can
        // factor it into the per-hero optimization target. Static catalog
        // lives in data/static/relics.json (refreshed by
        // tools/refresh_relic_blessing_truth.py).
        // =====================================================
        private string GetUserRelics()
        {
            var sb = new StringBuilder(8192);
            var uw = GetUserWrapper();
            if (uw == null) return "{\"error\":\"not logged in\"}";

            var relicWrapper = Prop(uw, "Relics");
            if (relicWrapper == null) return "{\"error\":\"UserWrapper.Relics is null\"}";

            sb.Append("{\"relics\":[");
            int written = 0;
            try
            {
                var relicsList = Prop(relicWrapper, "Relics");
                if (relicsList != null)
                {
                    int relN = IntProp(relicsList, "_size");
                    var relItems = Prop(relicsList, "_items");
                    if (relItems != null && relN > 0)
                    {
                        var getRel = relItems.GetType().GetMethod("get_Item", new[] { typeof(int) });
                        for (int i = 0; i < relN; i++)
                        {
                            var r = getRel.Invoke(relItems, new object[] { i });
                            if (r == null) continue;
                            if (written > 0) sb.Append(",");
                            written++;
                            int id = IntProp(r, "Id");
                            int typeId = IntProp(r, "TypeId");
                            int rank = IntProp(r, "Rank");
                            int level = IntProp(r, "Level");
                            bool activated = false;
                            // IsActivated is Nullable<bool> — peek via Prop, default false.
                            try {
                                var ia = Prop(r, "IsActivated");
                                if (ia != null) {
                                    var hv = ia.GetType().GetProperty("HasValue");
                                    var vp = ia.GetType().GetProperty("Value");
                                    if (hv != null && (bool)hv.GetValue(ia) && vp != null)
                                        activated = (bool)vp.GetValue(ia);
                                }
                            } catch { }
                            sb.Append("{\"id\":").Append(id);
                            sb.Append(",\"type_id\":").Append(typeId);
                            sb.Append(",\"rank\":").Append(rank);
                            sb.Append(",\"level\":").Append(level);
                            sb.Append(",\"activated\":").Append(activated ? "true" : "false");
                            // Sockets: list of { shape, stone_id? }
                            sb.Append(",\"sockets\":[");
                            int sw = 0;
                            try {
                                var sockets = Prop(r, "Sockets");
                                if (sockets != null) {
                                    int sN = IntProp(sockets, "_size");
                                    var sItems = Prop(sockets, "_items");
                                    if (sItems != null && sN > 0) {
                                        var getS = sItems.GetType().GetMethod("get_Item", new[] { typeof(int) });
                                        for (int j = 0; j < sN; j++) {
                                            var sk = getS.Invoke(sItems, new object[] { j });
                                            if (sk == null) continue;
                                            if (sw > 0) sb.Append(",");
                                            sw++;
                                            int shape = IntProp(sk, "ShapeKindId");
                                            // StoneId is Nullable<int>; default null
                                            int stoneId = -1;
                                            try {
                                                var sid = Prop(sk, "StoneId");
                                                if (sid != null) {
                                                    var hv = sid.GetType().GetProperty("HasValue");
                                                    var vp = sid.GetType().GetProperty("Value");
                                                    if (hv != null && (bool)hv.GetValue(sid) && vp != null)
                                                        stoneId = (int)vp.GetValue(sid);
                                                }
                                            } catch { }
                                            sb.Append("{\"shape\":").Append(shape);
                                            if (stoneId >= 0) sb.Append(",\"stone_id\":").Append(stoneId);
                                            sb.Append("}");
                                        }
                                    }
                                }
                            } catch { }
                            sb.Append("]}");
                        }
                    }
                }
            }
            catch (Exception ex) {
                Logger.LogWarning("[GetUserRelics] relics walk threw: " + ex.Message);
            }
            sb.Append("]");

            // Stones
            sb.Append(",\"stones\":[");
            int stoneWritten = 0;
            try {
                var stonesList = Prop(relicWrapper, "Stones");
                if (stonesList != null) {
                    int sN = IntProp(stonesList, "_size");
                    var sItems = Prop(stonesList, "_items");
                    if (sItems != null && sN > 0) {
                        var getS = sItems.GetType().GetMethod("get_Item", new[] { typeof(int) });
                        for (int i = 0; i < sN; i++) {
                            var s = getS.Invoke(sItems, new object[] { i });
                            if (s == null) continue;
                            if (stoneWritten > 0) sb.Append(",");
                            stoneWritten++;
                            int id = IntProp(s, "Id");
                            int typeId = IntProp(s, "TypeId");
                            int level = IntProp(s, "Level");
                            sb.Append("{\"id\":").Append(id)
                              .Append(",\"type_id\":").Append(typeId)
                              .Append(",\"level\":").Append(level).Append("}");
                        }
                    }
                }
            } catch (Exception ex) {
                Logger.LogWarning("[GetUserRelics] stones walk threw: " + ex.Message);
            }
            sb.Append("]");

            // Per-hero assignment via RelicDataByHeroId
            sb.Append(",\"hero_assign\":{");
            int assignWritten = 0;
            try {
                var relicsData = Prop(relicWrapper, "RelicsData");
                var byHero = Prop(relicsData, "RelicDataByHeroId");
                if (byHero != null) {
                    foreach (var entry in DictEntries(byHero)) {
                        var heroId = entry.Key;
                        var heroRelicData = entry.Value;
                        if (heroRelicData == null) continue;
                        var ridList = Prop(heroRelicData, "RelicIds");
                        if (ridList == null) continue;
                        int ridN = IntProp(ridList, "_size");
                        if (ridN == 0) continue;
                        var ridItems = Prop(ridList, "_items");
                        if (ridItems == null) continue;
                        if (assignWritten > 0) sb.Append(",");
                        assignWritten++;
                        sb.Append("\"").Append(heroId).Append("\":[");
                        var getRid = ridItems.GetType().GetMethod("get_Item", new[] { typeof(int) });
                        for (int i = 0; i < ridN; i++) {
                            var v = getRid.Invoke(ridItems, new object[] { i });
                            if (i > 0) sb.Append(",");
                            sb.Append(v);
                        }
                        sb.Append("]");
                    }
                }
            } catch (Exception ex) {
                Logger.LogWarning("[GetUserRelics] hero_assign walk threw: " + ex.Message);
            }
            sb.Append("}");

            sb.Append(",\"relic_count\":").Append(written);
            sb.Append(",\"stone_count\":").Append(stoneWritten);
            sb.Append(",\"hero_assign_count\":").Append(assignWritten);
            sb.Append("}");
            return sb.ToString();
        }

        // =====================================================
        // API: /hero-blessings
        //
        // Returns { hero_id -> {blessing_id, divinity_grade} } for every
        // hero with an active blessing applied. Reads Hero.DoubleAscendData
        // which holds:
        //   - Grade  (DoubleAscendGrade, 0..5+)
        //   - BlessingId (Nullable<BlessingTypeId>)
        //   - FreeResetUsed
        //
        // Per memory project_il2cpp_nullable_enum.md: Il2CppInterop's
        // wrapped Nullable<enum>.HasValue / .Value return 0 in some
        // contexts — use the safe `Prop(...)` walk + HasValue check
        // pattern from /user-relics above.
        // =====================================================
        private string GetHeroBlessings()
        {
            var sb = new StringBuilder(8192);
            var uw = GetUserWrapper();
            if (uw == null) return "{\"error\":\"not logged in\"}";

            var heroes = Prop(uw, "Heroes");
            var heroData = Prop(heroes, "HeroData");
            var heroDict = Prop(heroData, "HeroById");
            if (heroDict == null) return "{\"error\":\"HeroById null\"}";

            sb.Append("{\"blessings\":{");
            int written = 0;
            int totalHeroes = 0;
            int withBlessing = 0;
            foreach (var hero in DictValues(heroDict)) {
                totalHeroes++;
                if (hero == null) continue;
                int heroId = IntProp(hero, "Id");
                var da = Prop(hero, "DoubleAscendData");
                if (da == null) continue;
                int grade = 0;
                try { grade = IntProp(da, "Grade"); } catch { }
                int blessingId = 0;
                bool hasBlessing = false;
                try {
                    var bid = Prop(da, "BlessingId");
                    if (bid != null) {
                        var hv = bid.GetType().GetProperty("HasValue");
                        var vp = bid.GetType().GetProperty("Value");
                        if (hv != null && (bool)hv.GetValue(bid) && vp != null) {
                            var ev = vp.GetValue(bid);
                            blessingId = Convert.ToInt32(ev);
                            hasBlessing = blessingId != 0;
                        }
                    }
                } catch { }
                // Surface every hero with grade>0 OR a non-null blessing; this lets
                // callers see which heroes are Soul-summoned but not yet blessed.
                if (grade == 0 && !hasBlessing) continue;
                if (hasBlessing) withBlessing++;
                if (written > 0) sb.Append(",");
                written++;
                sb.Append("\"").Append(heroId).Append("\":{");
                sb.Append("\"grade\":").Append(grade);
                if (hasBlessing) sb.Append(",\"blessing_id\":").Append(blessingId);
                sb.Append("}");
            }
            sb.Append("}");
            sb.Append(",\"heroes_scanned\":").Append(totalHeroes);
            sb.Append(",\"heroes_with_blessing\":").Append(withBlessing);
            sb.Append("}");
            return sb.ToString();
        }

        // Walk a Dictionary<EnumKey, X> and return a list of (enum_int,
        // enum_name, value) tuples. The generic /static-export serializer
        // emits the IL2Cpp metadata pointer instead of the enum value
        // when serializing dict keys — this helper bypasses that by
        // reading the entries directly and resolving the enum via the
        // boxed-key's type.
        private List<(int enumInt, string enumName, object value)> DecodeEnumKeyedDict(object dict)
        {
            var result = new List<(int, string, object)>();
            if (dict == null) return result;
            var t = dict.GetType();
            var entries = t.GetProperty("_entries", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public)?.GetValue(dict)
                       ?? t.GetField("_entries", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public)?.GetValue(dict);
            if (entries == null) return result;
            int count = IntProp(dict, "Count");
            int n = IntProp(entries, "Length");
            var get = entries.GetType().GetMethod("get_Item", new[] { typeof(int) });
            int seen = 0;
            for (int i = 0; i < n && seen < count; i++)
            {
                object e = null;
                try { e = get?.Invoke(entries, new object[] { i }); } catch { }
                if (e == null) continue;
                int hash = IntProp(e, "hashCode");
                if (hash == 0) continue;
                var key = Prop(e, "key");
                var value = Prop(e, "value");
                if (key == null) continue;
                seen++;
                int enumInt = 0;
                string enumName = "?";
                try {
                    var keyType = key.GetType();
                    if (keyType.IsEnum) {
                        try { enumInt = Convert.ToInt32(key); }
                        catch { enumInt = 0; }
                        enumName = Enum.GetName(keyType, key) ?? key.ToString();
                    } else {
                        // Might be a struct-wrapper around an int (IL2Cpp pattern).
                        // Fall through: try Convert.ToInt32 to extract the value.
                        try { enumInt = Convert.ToInt32(key); } catch { }
                        enumName = key.ToString();
                    }
                } catch { }
                result.Add((enumInt, enumName, value));
            }
            return result;
        }

        // =====================================================
        // API: /relic-upgrade-prices
        //
        // Returns per-level relic level-up costs (Starstones / Meteors),
        // rank-up materials per rank, and stat-bonus opening levels.
        // Enum dict keys (RelicRank, BlackMarketItemId) are properly
        // decoded instead of being serialised as metadata pointers
        // like the generic /static-export does.
        // =====================================================
        private string GetRelicUpgradePrices()
        {
            var sb = new StringBuilder(2048);
            sb.Append("{");
            try {
                var appModel = GetAppModel();
                var staticDataRoot = Prop(appModel, "StaticData");
                var relicData = Prop(staticDataRoot, "RelicData");
                if (relicData == null) { sb.Append("\"error\":\"RelicData null\"}"); return sb.ToString(); }

                // MaxRelicLevelByRank — Dict<RelicRank, int>
                sb.Append("\"max_level_by_rank\":{");
                int w = 0;
                var maxLevelDict = Prop(relicData, "MaxRelicLevelByRank");
                foreach (var (rint, rname, val) in DecodeEnumKeyedDict(maxLevelDict)) {
                    if (w > 0) sb.Append(",");
                    sb.Append("\"").Append(rname).Append("\":").Append(Convert.ToInt32(val));
                    w++;
                }
                sb.Append("}");

                // BasicRelicRankByRarity — Dict<ItemRarity, RelicRank>
                sb.Append(",\"basic_rank_by_rarity\":{");
                w = 0;
                var basicRank = Prop(relicData, "BasicRelicRankByRarity");
                foreach (var (rint, rname, val) in DecodeEnumKeyedDict(basicRank)) {
                    if (w > 0) sb.Append(",");
                    string rankName = val?.GetType().IsEnum == true ? Enum.GetName(val.GetType(), val) : val?.ToString();
                    sb.Append("\"").Append(rname).Append("\":\"").Append(Esc(rankName ?? "?")).Append("\"");
                    w++;
                }
                sb.Append("}");

                // RelicRankUpgradeBmiByRank — Dict<RelicRank, BlackMarketItemId>
                sb.Append(",\"rank_upgrade_bmi\":{");
                w = 0;
                var bmiByRank = Prop(relicData, "RelicRankUpgradeBmiByRank");
                foreach (var (rint, rname, val) in DecodeEnumKeyedDict(bmiByRank)) {
                    if (w > 0) sb.Append(",");
                    int bmiInt = 0;
                    string bmiName = "?";
                    try {
                        var vt = val.GetType();
                        if (vt.IsEnum) {
                            bmiInt = Convert.ToInt32(val);
                            bmiName = Enum.GetName(vt, val) ?? val.ToString();
                        }
                    } catch { }
                    sb.Append("\"").Append(rname).Append("\":{\"bmi_id\":").Append(bmiInt)
                      .Append(",\"bmi_name\":\"").Append(Esc(bmiName)).Append("\"}");
                    w++;
                }
                sb.Append("}");

                // StatBonusOpeningLevels — list<int>
                sb.Append(",\"stat_bonus_opening_levels\":[");
                w = 0;
                var openings = Prop(relicData, "StatBonusOpeningLevels");
                if (openings != null) {
                    int n = IntProp(openings, "Count");
                    var items = Prop(openings, "_items");
                    var getI = items?.GetType().GetMethod("get_Item", new[] { typeof(int) });
                    for (int i = 0; i < n; i++) {
                        if (w > 0) sb.Append(",");
                        sb.Append(Convert.ToInt32(getI.Invoke(items, new object[] { i })));
                        w++;
                    }
                }
                sb.Append("]");

                // HeroActivatedRelicsLimit
                sb.Append(",\"hero_activated_limit\":").Append(IntProp(relicData, "HeroActivatedRelicsLimit"));
                // RelicCraftMaterialCount, CraftSlotsCount
                try { sb.Append(",\"craft_slots_count\":").Append(IntProp(relicData, "CraftSlotsCount")); } catch { }
                try { sb.Append(",\"craft_material_count\":").Append(IntProp(relicData, "RelicCraftMaterialCount")); } catch { }
            } catch (Exception ex) {
                sb.Append(",\"error\":\"").Append(Esc(ex.Message)).Append("\"");
            }
            sb.Append("}");
            return sb.ToString();
        }

        // =====================================================
        // API: /ascend-prices
        //
        // Returns artifact + accessory ascension price tables with
        // properly-decoded enum keys (ItemRarity, ArtifactRankId).
        // Used by sell evaluators to know "if I ascend this rank-6
        // Legendary, what does it cost in Lesser/Greater/Superior Oil?"
        // =====================================================
        private string GetAscendPrices()
        {
            var sb = new StringBuilder(4096);
            sb.Append("{");
            try {
                var appModel = GetAppModel();
                var staticDataRoot = Prop(appModel, "StaticData");
                var artData = Prop(staticDataRoot, "ArtifactData");
                if (artData == null) { sb.Append("\"error\":\"ArtifactData null\"}"); return sb.ToString(); }

                // AscendPricesByRank — Dict<ArtifactRankId, Resources>
                sb.Append("\"ascend_prices_by_rank\":[");
                int w = 0;
                var pricesByRank = Prop(artData, "AscendPricesByRank");
                foreach (var (rint, rname, val) in DecodeEnumKeyedDict(pricesByRank)) {
                    if (w > 0) sb.Append(",");
                    sb.Append("{\"rank\":\"").Append(Esc(rname)).Append("\",\"price\":");
                    SerializeResource(sb, val);
                    sb.Append("}");
                    w++;
                }
                sb.Append("]");

                // AscendPricesByRankAccessories — same shape, accessory variant
                sb.Append(",\"ascend_prices_by_rank_accessories\":[");
                w = 0;
                var accPrices = Prop(artData, "AscendPricesByRankAccessories");
                foreach (var (rint, rname, val) in DecodeEnumKeyedDict(accPrices)) {
                    if (w > 0) sb.Append(",");
                    sb.Append("{\"rank\":\"").Append(Esc(rname)).Append("\",\"price\":");
                    SerializeResource(sb, val);
                    sb.Append("}");
                    w++;
                }
                sb.Append("]");

                // AscendItemsAmountByRerollCount — Dict<int, int>
                sb.Append(",\"reroll_cost_by_attempt\":{");
                w = 0;
                var rerollDict = Prop(artData, "AscendItemsAmountByRerollCount");
                if (rerollDict != null) {
                    foreach (var entry in DictEntries(rerollDict)) {
                        if (w > 0) sb.Append(",");
                        sb.Append("\"").Append(entry.Key).Append("\":").Append(entry.Value);
                        w++;
                    }
                }
                sb.Append("}");
            } catch (Exception ex) {
                sb.Append(",\"error\":\"").Append(Esc(ex.Message)).Append("\"");
            }
            sb.Append("}");
            return sb.ToString();
        }

        // =====================================================
        // API: /daily-reset-times
        //
        // Reads the game's authoritative reset clocks so we don't have to
        // guess from in-game timer screenshots. Two sources:
        //   1. UserWrapper.DailyUpdates.DailyUpdateData.DailyUpdates — a
        //      List<DailyUpdate> with TypeId + NextUpdateDate. Each entry
        //      tracks a specific subsystem reset (Arena=5, DoomTowerKeys=6,
        //      CursedCityKeys=10, FoggyForest=11, etc.).
        //   2. UserWrapper.Alliance.AllianceData.BossData.NextRefreshTime —
        //      the Demon Lord / CB key refresh DateTime (most important
        //      one for the daily-schedule alignment).
        //
        // Returns ISO-8601 UTC strings + the seconds-until-now for each.
        // Consumers use this to align scheduled tasks to the actual reset
        // moment rather than hard-coded UTC guesses.
        // =====================================================
        // Read a Nullable<T> backing-field value. IL2Cpp wraps Nullable<T>
        // such that .HasValue / .Value properties return zeroed defaults
        // via reflection — same root cause as the project_il2cpp_nullable_enum
        // memory. The working pattern (also used in StaticData.cs:134-167)
        // is to read the lowercase `hasValue` (bool) + `value` (T) BACKING
        // FIELDS directly. Returns the unboxed inner value or null.
        private object ReadNullableField(object boxedNullable)
        {
            if (boxedNullable == null) return null;
            var t = boxedNullable.GetType();
            if (t.Name != "Nullable`1") return boxedNullable;  // already unwrapped
            try {
                var hvField = t.GetField("hasValue",
                    BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                var valField = t.GetField("value",
                    BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                bool hasValue = false;
                if (hvField != null) hasValue = (bool)hvField.GetValue(boxedNullable);
                if (!hasValue) return null;
                if (valField != null) return valField.GetValue(boxedNullable);
            } catch { }
            return null;
        }

        // Il2Cpp DateTime (Il2CppSystem.DateTime) doesn't pattern-match to
        // System.DateTime. Reads Ticks reflectively and reconstructs a
        // managed DateTime. Returns null when value can't be extracted or
        // is MinValue.
        private DateTime? ReadDateTimeValue(object dtBoxed)
        {
            if (dtBoxed == null) return null;
            if (dtBoxed is DateTime dt) return dt == DateTime.MinValue ? (DateTime?)null : dt;
            try {
                var t = dtBoxed.GetType();
                var ticksProp = t.GetProperty("Ticks");
                if (ticksProp != null) {
                    long ticks = Convert.ToInt64(ticksProp.GetValue(dtBoxed));
                    if (ticks <= 0 || ticks > DateTime.MaxValue.Ticks) return null;
                    DateTimeKind kind = DateTimeKind.Utc;
                    try {
                        var kindProp = t.GetProperty("Kind");
                        if (kindProp != null) {
                            var k = kindProp.GetValue(dtBoxed);
                            if (k != null) kind = (DateTimeKind)Convert.ToInt32(k);
                        }
                    } catch { }
                    return new DateTime(ticks, kind);
                }
            } catch { }
            return null;
        }

        // Il2Cpp TimeSpan (Il2CppSystem.TimeSpan) doesn't pattern-match to
        // System.TimeSpan. Read TotalSeconds (or Ticks) reflectively.
        // Returns -1 when the value can't be extracted.
        private double ReadTimeSpanSeconds(object tsBoxed)
        {
            if (tsBoxed == null) return -1;
            if (tsBoxed is TimeSpan tsr) return tsr.TotalSeconds;
            try {
                var totSecProp = tsBoxed.GetType().GetProperty("TotalSeconds");
                if (totSecProp != null)
                    return Convert.ToDouble(totSecProp.GetValue(tsBoxed));
            } catch { }
            try {
                var ticksProp = tsBoxed.GetType().GetProperty("Ticks");
                if (ticksProp != null) {
                    long ticks = Convert.ToInt64(ticksProp.GetValue(tsBoxed));
                    return ticks / 10_000_000.0;
                }
            } catch { }
            return -1;
        }

        // Il2Cpp Nullable<DateTime> reflection returns DateTime.MinValue from
        // Value even when populated. The Plarium DateTime backing-store is the
        // `_dateData` ulong (low 62 bits = ticks, top 2 bits = Kind), placed
        // at byte offset 16 inside the Il2Cpp wrapper (same offset used for
        // Nullable<TEnum> ints — see StaticData.NullableEnumInt).
        // Returns null when HasValue=false or the read fails.
        private DateTime? ReadNullableDateTime(object boxedNullable)
        {
            if (boxedNullable == null) return null;
            try {
                var t = boxedNullable.GetType();
                // First check HasValue — this property returns correctly even
                // when Value reads return zeroed.
                var hvProp = t.GetProperty("HasValue");
                if (hvProp != null) {
                    var hv = hvProp.GetValue(boxedNullable);
                    if (hv is bool hb && !hb) return null;
                }
                // Il2Cpp wrapper exposes a Pointer to the native struct.
                var ptrProp = t.GetProperty("Pointer");
                if (ptrProp != null) {
                    var ptrVal = ptrProp.GetValue(boxedNullable);
                    if (ptrVal is IntPtr ptr && ptr != IntPtr.Zero) {
                        long raw = System.Runtime.InteropServices.Marshal.ReadInt64(ptr, 16);
                        // Mask out DateTimeKind bits (top 2) → ticks (low 62).
                        long ticks = raw & 0x3FFFFFFFFFFFFFFFL;
                        long kindBits = (long)((ulong)raw >> 62);
                        var kind = (DateTimeKind)kindBits;
                        if (ticks < 0 || ticks > DateTime.MaxValue.Ticks) return null;
                        return new DateTime(ticks, kind);
                    }
                }
                // Managed Nullable<DateTime> fallback.
                var inner = ReadNullableField(boxedNullable);
                if (inner is DateTime dt) return dt;
            } catch { }
            return null;
        }

        private string GetDailyResetTimes()
        {
            var sb = new StringBuilder(2048);
            sb.Append("{");
            DateTime now = DateTime.UtcNow;
            sb.Append("\"now_utc\":\"").Append(now.ToString("o")).Append("\"");

            var uw = GetUserWrapper();
            if (uw == null) {
                sb.Append(",\"error\":\"not logged in\"}");
                return sb.ToString();
            }

            // DailyUpdates list — per-subsystem reset clocks.
            string DailyUpdateTypeName(int id) {
                switch (id) {
                    case 1: return "SeenOffers";
                    case 2: return "FractionWarKeys";
                    case 3: return "AmazonIntegration";
                    case 4: return "AutoOpenKeys";
                    case 5: return "Arena";
                    case 6: return "DoomTowerKeys";
                    case 7: return "Arena3x3";
                    case 8: return "DoubleAscendKeys";
                    case 9: return "LiveArena";
                    case 10: return "CursedCityKeys";
                    case 11: return "FoggyForest";
                    default: return "Type" + id;
                }
            }

            sb.Append(",\"daily_updates\":[");
            int w = 0;
            try {
                var dailyWrapper = Prop(uw, "DailyUpdates");
                var dailyData = Prop(dailyWrapper, "DailyUpdateData");
                var updates = Prop(dailyData, "DailyUpdates");
                if (updates != null) {
                    int n = IntProp(updates, "_size");
                    var items = Prop(updates, "_items");
                    var getI = items?.GetType().GetMethod("get_Item", new[] { typeof(int) });
                    for (int i = 0; i < n; i++) {
                        var entry = getI?.Invoke(items, new object[] { i });
                        if (entry == null) continue;
                        int typeIdInt = 0;
                        try { typeIdInt = Convert.ToInt32(Prop(entry, "TypeId")); } catch { }
                        // Time is Nullable<DateTime> — Pointer-offset read.
                        DateTime? time = ReadNullableDateTime(Prop(entry, "Time"));
                        // NextUpdateDate is DateTime (non-nullable); reads
                        // back as MinValue when Time isn't yet populated.
                        DateTime? nextUpdate = null;
                        try {
                            var nud = Prop(entry, "NextUpdateDate");
                            if (nud is DateTime dt && dt != DateTime.MinValue) nextUpdate = dt;
                        } catch { }
                        if (w > 0) sb.Append(",");
                        w++;
                        sb.Append("{\"type_id\":").Append(typeIdInt);
                        sb.Append(",\"type_name\":\"").Append(DailyUpdateTypeName(typeIdInt)).Append("\"");
                        if (time.HasValue)
                            sb.Append(",\"last_time_utc\":\"").Append(time.Value.ToUniversalTime().ToString("o")).Append("\"");
                        if (nextUpdate.HasValue) {
                            var nu = nextUpdate.Value.ToUniversalTime();
                            sb.Append(",\"next_update_utc\":\"").Append(nu.ToString("o")).Append("\"");
                            sb.Append(",\"seconds_until\":").Append((long)(nu - now).TotalSeconds);
                        }
                        sb.Append("}");
                    }
                }
            } catch (Exception ex) {
                sb.Append("{\"error\":\"").Append(Esc(ex.Message)).Append("\"}");
            }
            sb.Append("]");

            // AllianceSettings — static, has the canonical daily reset hour
            // (RefreshTimeHoursUtc) plus key/regen tuning. This is what
            // anchors the alliance-boss daily refresh moment.
            // Path: StaticData.AllianceData.Settings (StaticAllianceData wrapper).
            sb.Append(",\"alliance_settings\":");
            try {
                object staticData = Prop(GetAppModel(), "StaticData");
                object staticAllianceData = Prop(staticData, "AllianceData");
                object allianceSettings = Prop(staticAllianceData, "Settings");
                if (allianceSettings == null) {
                    sb.Append("{\"error\":\"AllianceSettings null\"}");
                } else {
                    double refreshHr = 0; double freeKeyHr = 0; int maxKeys = 0;
                    double bossLifeDays = 0;
                    try { refreshHr = Convert.ToDouble(Prop(allianceSettings, "RefreshTimeHoursUtc")); } catch { }
                    try { freeKeyHr = Convert.ToDouble(Prop(allianceSettings, "FreeBossKeyHours")); } catch { }
                    try { maxKeys = Convert.ToInt32(Prop(allianceSettings, "MaxBossKeys")); } catch { }
                    try { bossLifeDays = Convert.ToDouble(Prop(allianceSettings, "BossLifetimeDays")); } catch { }
                    // Compute next reset moment from today's UTC anchor.
                    var today = new DateTime(now.Year, now.Month, now.Day, 0, 0, 0, DateTimeKind.Utc);
                    var todayAnchor = today.AddHours(refreshHr);
                    var nextAnchor = todayAnchor;
                    if (nextAnchor <= now) nextAnchor = nextAnchor.AddDays(1);
                    sb.Append("{\"refresh_time_hours_utc\":").Append(refreshHr.ToString("R", System.Globalization.CultureInfo.InvariantCulture));
                    sb.Append(",\"free_boss_key_hours\":").Append(freeKeyHr.ToString("R", System.Globalization.CultureInfo.InvariantCulture));
                    sb.Append(",\"max_boss_keys\":").Append(maxKeys);
                    sb.Append(",\"boss_lifetime_days\":").Append(bossLifeDays.ToString("R", System.Globalization.CultureInfo.InvariantCulture));
                    sb.Append(",\"todays_reset_utc\":\"").Append(todayAnchor.ToString("o")).Append("\"");
                    sb.Append(",\"next_reset_utc\":\"").Append(nextAnchor.ToString("o")).Append("\"");
                    sb.Append(",\"next_reset_seconds_until\":").Append((long)(nextAnchor - now).TotalSeconds);
                    sb.Append("}");
                }
            } catch (Exception ex) {
                sb.Append("{\"error\":\"").Append(Esc(ex.Message)).Append("\"}");
            }

            // Helper: emit a Nullable<DateTime> field as JSON if HasValue.
            void EmitNullableDt(StringBuilder buf, string key, object dtNullable, ref bool firstFlag) {
                var dt = ReadNullableDateTime(dtNullable);
                if (!dt.HasValue) return;
                if (!firstFlag) buf.Append(",");
                firstFlag = false;
                var u = dt.Value.ToUniversalTime();
                buf.Append("\"").Append(key).Append("\":\"").Append(u.ToString("o")).Append("\"");
                buf.Append(",\"").Append(key).Append("_seconds_until\":").Append((long)(u - now).TotalSeconds);
            }
            void EmitDt(StringBuilder buf, string key, object dtMaybe, ref bool firstFlag) {
                if (!(dtMaybe is DateTime dt) || dt == DateTime.MinValue) return;
                if (!firstFlag) buf.Append(",");
                firstFlag = false;
                var u = dt.ToUniversalTime();
                buf.Append("\"").Append(key).Append("\":\"").Append(u.ToString("o")).Append("\"");
                buf.Append(",\"").Append(key).Append("_seconds_until\":").Append((long)(u - now).TotalSeconds);
            }

            // AllianceBoss / Demon Lord — surface the multiple Bosses wrapper
            // clocks. StartTime / NextRefreshTime / BattleLockedUntil exist
            // on the wrapper; the underlying Data has raw server fields.
            sb.Append(",\"alliance_boss\":");
            try {
                var alliance = Prop(uw, "Alliance");
                var bossWrapper = Prop(alliance, "Bosses");
                if (bossWrapper == null) {
                    sb.Append("{\"error\":\"uw.Alliance.Bosses null\"}");
                } else {
                    DateTime? nrt = ReadNullableDateTime(Prop(bossWrapper, "NextRefreshTime"));
                    DateTime? startTime = ReadNullableDateTime(Prop(bossWrapper, "StartTime"));
                    DateTime? lockedUntil = ReadNullableDateTime(Prop(bossWrapper, "BattleLockedUntil"));
                    // Inner data — read non-nullable DateTime StartTime there too.
                    DateTime? dataStartTime = null;
                    DateTime? dataNrt = null;
                    try {
                        var bossData = Prop(bossWrapper, "Data");
                        if (bossData != null) {
                            var dst = Prop(bossData, "StartTime");
                            if (dst is DateTime ddst && ddst != DateTime.MinValue) dataStartTime = ddst;
                            dataNrt = ReadNullableDateTime(Prop(bossData, "NextRefreshTime"));
                        }
                    } catch { }
                    sb.Append("{");
                    bool first = true;
                    void EmitTs(string key, DateTime ts) {
                        if (!first) sb.Append(",");
                        first = false;
                        var u = ts.ToUniversalTime();
                        sb.Append("\"").Append(key).Append("\":\"").Append(u.ToString("o")).Append("\"");
                        sb.Append(",\"").Append(key).Append("_seconds_until\":").Append((long)(u - now).TotalSeconds);
                    }
                    if (startTime.HasValue) EmitTs("wrapper_start_time_utc", startTime.Value);
                    if (nrt.HasValue) EmitTs("wrapper_next_refresh_utc", nrt.Value);
                    if (lockedUntil.HasValue) EmitTs("wrapper_battle_locked_until_utc", lockedUntil.Value);
                    if (dataStartTime.HasValue) EmitTs("data_start_time_utc", dataStartTime.Value);
                    if (dataNrt.HasValue) EmitTs("data_next_refresh_utc", dataNrt.Value);
                    sb.Append("}");
                }
            } catch (Exception ex) {
                sb.Append("{\"error\":\"").Append(Esc(ex.Message)).Append("\"}");
            }

            // Hydra — alliance Hydras wrapper exposes NextRaidRefreshTime
            // and NextSeasonRefreshTime (both Nullable<DateTime>).
            sb.Append(",\"alliance_hydra\":");
            try {
                var alliance = Prop(uw, "Alliance");
                var hyd = Prop(alliance, "Hydras");
                if (hyd == null) { sb.Append("{\"error\":\"uw.Alliance.Hydras null\"}"); }
                else {
                    sb.Append("{");
                    bool first = true;
                    EmitNullableDt(sb, "next_raid_refresh_utc", Prop(hyd, "NextRaidRefreshTime"), ref first);
                    EmitNullableDt(sb, "next_season_refresh_utc", Prop(hyd, "NextSeasonRefreshTime"), ref first);
                    sb.Append("}");
                }
            } catch (Exception ex) {
                sb.Append("{\"error\":\"").Append(Esc(ex.Message)).Append("\"}");
            }

            // Chimera — alliance Chimeras wrapper. The static DynamicData
            // (ChimeraData) holds non-nullable DateTime fields:
            // NextRaidStartTime + NextKeysRefreshTime.
            sb.Append(",\"alliance_chimera\":");
            try {
                var alliance = Prop(uw, "Alliance");
                var chi = Prop(alliance, "Chimeras");
                if (chi == null) { sb.Append("{\"error\":\"uw.Alliance.Chimeras null\"}"); }
                else {
                    sb.Append("{");
                    bool first = true;
                    // Try the DynamicData (ChimeraData) static property.
                    object dynData = Prop(chi, "DynamicData");
                    if (dynData != null) {
                        EmitDt(sb, "next_raid_start_utc", Prop(dynData, "NextRaidStartTime"), ref first);
                        EmitDt(sb, "next_keys_refresh_utc", Prop(dynData, "NextKeysRefreshTime"), ref first);
                    }
                    sb.Append("}");
                }
            } catch (Exception ex) {
                sb.Append("{\"error\":\"").Append(Esc(ex.Message)).Append("\"}");
            }

            // Doom Tower — rotation cycle uses DoomTowerSettings.UpdateTowerMinutes
            // (typically 14 days). last_update is when the current tower opened;
            // next rotation = last_update + UpdateTowerMinutes minutes.
            sb.Append(",\"doom_tower\":");
            try {
                var dt = Prop(uw, "DoomTower");
                if (dt == null) { sb.Append("{\"error\":\"uw.DoomTower null\"}"); }
                else {
                    sb.Append("{");
                    bool first = true;
                    // LeftTime is the wrapper's computed remaining rotation time.
                    var lt = Prop(dt, "LeftTime");
                    double leftSecs = ReadTimeSpanSeconds(lt);
                    if (leftSecs > 0) {
                        var expires = now.AddSeconds(leftSecs);
                        first = false;
                        sb.Append("\"rotation_expires_utc\":\"").Append(expires.ToString("o")).Append("\"");
                        sb.Append(",\"rotation_expires_seconds_until\":").Append((long)leftSecs);
                    }
                    var lastUpdate = Prop(dt, "LastUpdate");
                    DateTime? lu = ReadNullableDateTime(lastUpdate);
                    if (lu.HasValue) {
                        if (!first) sb.Append(",");
                        first = false;
                        sb.Append("\"last_update_utc\":\"").Append(lu.Value.ToUniversalTime().ToString("o")).Append("\"");
                    }
                    // Compute rotation expiry from static + last_update if
                    // LeftTime didn't read directly.
                    try {
                        object staticData = Prop(GetAppModel(), "StaticData");
                        object stageData = Prop(staticData, "StageData");
                        object stageSettings = Prop(stageData, "Settings");
                        object dtSettings = Prop(stageSettings, "DoomTowerSettings");
                        int updateMinutes = 0;
                        if (dtSettings != null) {
                            try { updateMinutes = Convert.ToInt32(Prop(dtSettings, "UpdateTowerMinutes")); } catch { }
                        }
                        if (updateMinutes > 0 && lu.HasValue) {
                            var computedExpires = lu.Value.AddMinutes(updateMinutes).ToUniversalTime();
                            if (!first) sb.Append(",");
                            first = false;
                            sb.Append("\"computed_rotation_expires_utc\":\"").Append(computedExpires.ToString("o")).Append("\"");
                            sb.Append(",\"computed_rotation_seconds_until\":").Append((long)(computedExpires - now).TotalSeconds);
                            sb.Append(",\"rotation_period_minutes\":").Append(updateMinutes);
                        }
                    } catch { }
                    sb.Append("}");
                }
            } catch (Exception ex) {
                sb.Append("{\"error\":\"").Append(Esc(ex.Message)).Append("\"}");
            }

            // Arena (Classic) — opponent list refresh + weekly rewards cycle.
            // Free opponent refresh = LastListRefreshTime +
            //   StaticArenaData.OpponentFreeRefreshTimeSec (typically 1h).
            // Weekly rewards anchor = StaticStandardArenaData.{WeeklyRewardsDay,
            //   WeeklyRewardsHour}.
            sb.Append(",\"arena_classic\":");
            try {
                var ar = Prop(uw, "Arena");
                if (ar == null) { sb.Append("{\"error\":\"uw.Arena null\"}"); }
                else {
                    sb.Append("{");
                    bool first = true;
                    var lastWeekly = ReadDateTimeValue(Prop(ar, "LastWeeklyRewardTime"));
                    if (lastWeekly.HasValue) {
                        first = false;
                        var u = lastWeekly.Value.ToUniversalTime();
                        sb.Append("\"last_weekly_reward_utc\":\"").Append(u.ToString("o")).Append("\"");
                    }
                    // GetFreeRefreshTimeLeft returns Il2CppSystem.TimeSpan.
                    // Positive = available in N secs. <=0 = available now.
                    try {
                        var arType = ar.GetType();
                        var m = arType.GetMethod("GetFreeRefreshTimeLeft", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                        if (m == null)
                            m = arType.GetMethod("FreeRefreshTimeLeft", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                        if (m != null) {
                            var tsResult = m.Invoke(ar, null);
                            double totalSeconds = ReadTimeSpanSeconds(tsResult);
                            if (totalSeconds > 0) {
                                if (!first) sb.Append(",");
                                first = false;
                                var u = now.AddSeconds(totalSeconds);
                                sb.Append("\"next_opponent_refresh_utc\":\"").Append(u.ToString("o")).Append("\"");
                                sb.Append(",\"next_opponent_refresh_seconds_until\":").Append((long)totalSeconds);
                            } else if (totalSeconds > -1e10) {
                                if (!first) sb.Append(",");
                                first = false;
                                sb.Append("\"opponent_refresh_available_now\":true");
                            }
                        }
                    } catch { }
                    // Static config + last refresh moment.
                    try {
                        object userArenaData = Prop(ar, "ArenaData");
                        DateTime? lastListRefresh = ReadDateTimeValue(Prop(userArenaData, "LastListRefreshTime"));
                        object staticData = Prop(GetAppModel(), "StaticData");
                        object staticArenaData = Prop(staticData, "ArenaData");
                        int opRefreshSecs = 0;
                        if (staticArenaData != null) {
                            try { opRefreshSecs = Convert.ToInt32(Prop(staticArenaData, "OpponentFreeRefreshTimeSec")); } catch { }
                        }
                        if (lastListRefresh.HasValue) {
                            if (!first) sb.Append(",");
                            first = false;
                            sb.Append("\"last_opponent_list_refresh_utc\":\"").Append(lastListRefresh.Value.ToUniversalTime().ToString("o")).Append("\"");
                        }
                        if (opRefreshSecs > 0) {
                            if (!first) sb.Append(",");
                            first = false;
                            sb.Append("\"opponent_refresh_period_seconds\":").Append(opRefreshSecs);
                        }
                        // Weekly rewards anchor.
                        if (staticArenaData != null) {
                            int weeklyHour = 0; object weeklyDay = null;
                            try { weeklyHour = Convert.ToInt32(Prop(staticArenaData, "WeeklyRewardsHour")); } catch { }
                            try { weeklyDay = Prop(staticArenaData, "WeeklyRewardsDay"); } catch { }
                            // WeeklyRewardsDay is Nullable<DayOfWeek>.
                            int? dayIdx = null;
                            if (weeklyDay != null) {
                                try {
                                    var hv = weeklyDay.GetType().GetProperty("HasValue")?.GetValue(weeklyDay);
                                    if (hv is bool hb && hb) {
                                        var v = weeklyDay.GetType().GetProperty("Value")?.GetValue(weeklyDay);
                                        if (v != null) dayIdx = Convert.ToInt32(v);
                                    }
                                } catch { }
                            }
                            if (dayIdx.HasValue) {
                                // Compute next weekly rewards moment.
                                var nowDow = (int)now.DayOfWeek;
                                int daysAhead = (dayIdx.Value - nowDow + 7) % 7;
                                var todayAtHour = new DateTime(now.Year, now.Month, now.Day, weeklyHour, 0, 0, DateTimeKind.Utc);
                                var nextWeekly = todayAtHour.AddDays(daysAhead);
                                if (nextWeekly <= now) nextWeekly = nextWeekly.AddDays(7);
                                if (!first) sb.Append(",");
                                first = false;
                                sb.Append("\"next_weekly_reward_utc\":\"").Append(nextWeekly.ToString("o")).Append("\"");
                                sb.Append(",\"next_weekly_reward_seconds_until\":").Append((long)(nextWeekly - now).TotalSeconds);
                                sb.Append(",\"weekly_rewards_day\":").Append(dayIdx.Value);
                                sb.Append(",\"weekly_rewards_hour_utc\":").Append(weeklyHour);
                            }
                        }
                    } catch { }
                    // Battle counter — daily quest context.
                    try {
                        var bs = Prop(ar, "BattlesStartedThisWeek");
                        if (bs != null) {
                            if (!first) sb.Append(",");
                            first = false;
                            sb.Append("\"battles_started_this_week\":").Append(Convert.ToInt32(bs));
                        }
                    } catch { }
                    sb.Append("}");
                }
            } catch (Exception ex) {
                sb.Append("{\"error\":\"").Append(Esc(ex.Message)).Append("\"}");
            }

            // Helper: settings path StaticData.StageData.Settings exposes
            // {FoggyForest,CursedCity,DoomTower}Settings via StageSettings.
            object stageSettingsForResets = null;
            try {
                object _sd = Prop(GetAppModel(), "StaticData");
                object _stageData = Prop(_sd, "StageData");
                stageSettingsForResets = Prop(_stageData, "Settings");
            } catch { }

            // Foggy Forest — wrapper.NextRefreshTime (Nullable<DateTime>) is
            // populated only once the user has engaged this cycle. Always
            // emit the static refresh hour and computed next anchor.
            sb.Append(",\"foggy_forest\":");
            try {
                var ff = Prop(uw, "FoggyForest");
                if (ff == null) { sb.Append("{\"error\":\"uw.FoggyForest null\"}"); }
                else {
                    sb.Append("{");
                    bool first = true;
                    EmitNullableDt(sb, "next_refresh_utc", Prop(ff, "NextRefreshTime"), ref first);
                    try {
                        object ffSettings = Prop(stageSettingsForResets, "FoggyForestSettings");
                        if (ffSettings != null) {
                            int refreshHour = Convert.ToInt32(Prop(ffSettings, "RefreshHour"));
                            var today = new DateTime(now.Year, now.Month, now.Day, refreshHour, 0, 0, DateTimeKind.Utc);
                            var nextAnchor = today <= now ? today.AddDays(1) : today;
                            if (!first) sb.Append(",");
                            first = false;
                            sb.Append("\"refresh_hour_utc\":").Append(refreshHour);
                            sb.Append(",\"computed_next_refresh_utc\":\"").Append(nextAnchor.ToString("o")).Append("\"");
                            sb.Append(",\"computed_next_refresh_seconds_until\":").Append((long)(nextAnchor - now).TotalSeconds);
                        }
                    } catch { }
                    sb.Append("}");
                }
            } catch (Exception ex) {
                sb.Append("{\"error\":\"").Append(Esc(ex.Message)).Append("\"}");
            }

            // Cursed City — same pattern.
            sb.Append(",\"cursed_city\":");
            try {
                var cc = Prop(uw, "CursedCity");
                if (cc == null) { sb.Append("{\"error\":\"uw.CursedCity null\"}"); }
                else {
                    sb.Append("{");
                    bool first = true;
                    EmitNullableDt(sb, "next_refresh_utc", Prop(cc, "NextRefreshTime"), ref first);
                    try {
                        object ccSettings = Prop(stageSettingsForResets, "CursedCitySettings");
                        if (ccSettings != null) {
                            int refreshHour = Convert.ToInt32(Prop(ccSettings, "RefreshHour"));
                            var today = new DateTime(now.Year, now.Month, now.Day, refreshHour, 0, 0, DateTimeKind.Utc);
                            var nextAnchor = today <= now ? today.AddDays(1) : today;
                            if (!first) sb.Append(",");
                            first = false;
                            sb.Append("\"refresh_hour_utc\":").Append(refreshHour);
                            sb.Append(",\"computed_next_refresh_utc\":\"").Append(nextAnchor.ToString("o")).Append("\"");
                            sb.Append(",\"computed_next_refresh_seconds_until\":").Append((long)(nextAnchor - now).TotalSeconds);
                        }
                    } catch { }
                    sb.Append("}");
                }
            } catch (Exception ex) {
                sb.Append("{\"error\":\"").Append(Esc(ex.Message)).Append("\"}");
            }

            // Live Arena — CurrentPhaseEndTime (DateTime, non-nullable) is the
            // end of the current season phase. SeasonPhase tells you whether
            // it's an active or rest phase. Use IL2Cpp DateTime reader.
            sb.Append(",\"live_arena\":");
            try {
                var la = Prop(uw, "LiveArena");
                if (la == null) { sb.Append("{\"error\":\"uw.LiveArena null\"}"); }
                else {
                    sb.Append("{");
                    bool first = true;
                    DateTime? phaseEnd = ReadDateTimeValue(Prop(la, "CurrentPhaseEndTime"));
                    if (phaseEnd.HasValue) {
                        first = false;
                        var u = phaseEnd.Value.ToUniversalTime();
                        sb.Append("\"current_phase_end_utc\":\"").Append(u.ToString("o")).Append("\"");
                        sb.Append(",\"current_phase_end_seconds_until\":").Append((long)(u - now).TotalSeconds);
                    }
                    // SeasonPhase Nullable<LiveArenaSeasonsPhaseTypeId> — emit numeric.
                    try {
                        var sp = Prop(la, "SeasonPhase");
                        if (sp != null) {
                            int spInt = ReadIl2CppNullableEnumInt(sp);
                            if (spInt != 0) {
                                if (!first) sb.Append(",");
                                first = false;
                                sb.Append("\"season_phase_id\":").Append(spInt);
                            }
                        }
                    } catch { }
                    try {
                        var sn = Prop(la, "SeasonNumber");
                        if (sn != null) {
                            // Nullable<long>
                            var inner = ReadNullableField(sn);
                            if (inner != null) {
                                if (!first) sb.Append(",");
                                first = false;
                                sb.Append("\"season_number\":").Append(Convert.ToInt64(inner));
                            }
                        }
                    } catch { }
                    sb.Append("}");
                }
            } catch (Exception ex) {
                sb.Append("{\"error\":\"").Append(Esc(ex.Message)).Append("\"}");
            }

            // Magic Shop — free refresh cooldown. Wrapper exposes
            // GetLastRefreshDateTime() and IsFreeRefreshAvailable() methods.
            // Static: MagicShopSettings.RefreshSec (interval seconds).
            sb.Append(",\"magic_shop\":");
            try {
                var ms = Prop(uw, "MagicShop");
                if (ms == null) { sb.Append("{\"error\":\"uw.MagicShop null\"}"); }
                else {
                    sb.Append("{");
                    bool first = true;
                    DateTime? lastRefresh = null;
                    bool? freeAvail = null;
                    try {
                        var msType = ms.GetType();
                        var lrM = msType.GetMethod("GetLastRefreshDateTime",
                            BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                        if (lrM != null) {
                            var r = lrM.Invoke(ms, null);
                            lastRefresh = ReadDateTimeValue(r);
                        }
                        var faM = msType.GetMethod("IsFreeRefreshAvailable",
                            BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance,
                            null, Type.EmptyTypes, null);
                        if (faM != null) {
                            var r = faM.Invoke(ms, null);
                            if (r is bool b) freeAvail = b;
                        }
                    } catch { }
                    if (lastRefresh.HasValue) {
                        first = false;
                        sb.Append("\"last_refresh_utc\":\"").Append(lastRefresh.Value.ToUniversalTime().ToString("o")).Append("\"");
                    }
                    if (freeAvail.HasValue) {
                        if (!first) sb.Append(",");
                        first = false;
                        sb.Append("\"free_refresh_available_now\":").Append(freeAvail.Value ? "true" : "false");
                    }
                    // Static refresh interval + computed next free refresh.
                    try {
                        object staticData = Prop(GetAppModel(), "StaticData");
                        object staticMS = Prop(staticData, "MagicShopData");  // StaticMagicShopData
                        object msSettings = Prop(staticMS, "Settings");
                        int refreshSec = 0;
                        if (msSettings != null) {
                            try { refreshSec = Convert.ToInt32(Prop(msSettings, "RefreshSec")); } catch { }
                        }
                        if (refreshSec > 0) {
                            if (!first) sb.Append(",");
                            first = false;
                            sb.Append("\"refresh_period_seconds\":").Append(refreshSec);
                            if (lastRefresh.HasValue) {
                                var nextFree = lastRefresh.Value.AddSeconds(refreshSec).ToUniversalTime();
                                sb.Append(",\"next_free_refresh_utc\":\"").Append(nextFree.ToString("o")).Append("\"");
                                sb.Append(",\"next_free_refresh_seconds_until\":").Append((long)(nextFree - now).TotalSeconds);
                            }
                        }
                    } catch { }
                    sb.Append("}");
                }
            } catch (Exception ex) {
                sb.Append("{\"error\":\"").Append(Esc(ex.Message)).Append("\"}");
            }

            // Battle Pass — enumerate AvailablePasses (broader than
            // ActivePasses) and read each pass's Start + DurationDays
            // fields directly (Nullable<DateTime> EndTime(passId) is also
            // available on the wrapper but Start/DurationDays are simpler).
            sb.Append(",\"battle_pass\":");
            try {
                var bp = Prop(uw, "BattlePass");
                if (bp == null) { sb.Append("{\"error\":\"uw.BattlePass null\"}"); }
                else {
                    // IL2Cpp IEnumerable<BattlePass> from `yield return`
                    // doesn't enumerate via System.Collections.IEnumerable.
                    // Use the static dictionary StaticBattlePassData.BattlePasses
                    // (Dictionary<int, BattlePass>) and filter to currently-
                    // active passes (Start..Start+DurationDays brackets now).
                    sb.Append("{\"passes\":[");
                    int n = 0;
                    try {
                        object staticData = Prop(GetAppModel(), "StaticData");
                        object bpData = Prop(staticData, "BattlePassData");
                        object dict = Prop(bpData, "BattlePasses");
                        // IL2Cpp Dictionary<int, BattlePass> doesn't implement
                        // System.Collections.IDictionary. Walk Keys + indexer.
                        if (dict != null) {
                            // IL2Cpp Dictionary/List don't implement managed
                            // IEnumerable. Use the StaticBattlePassData.LastPasses
                            // List<BattlePass> + iterate via _items / _size.
                            object lastPasses = Prop(bpData, "LastPasses");
                            int lpCount = 0;
                            object lpItems = null;
                            System.Reflection.MethodInfo lpGetI = null;
                            if (lastPasses != null) {
                                try { lpCount = IntProp(lastPasses, "_size"); } catch { }
                                lpItems = Prop(lastPasses, "_items");
                                if (lpCount == 0) {
                                    try { lpCount = IntProp(lastPasses, "Count"); } catch { }
                                }
                                if (lpItems != null) {
                                    lpGetI = lpItems.GetType().GetMethod("get_Item", new[] { typeof(int) });
                                }
                            }
                            // Fallback: iterate dict via keys range.
                            for (int idx = 0; idx < lpCount && lpGetI != null; idx++) {
                                object pass = null;
                                try { pass = lpGetI.Invoke(lpItems, new object[] { idx }); } catch { }
                                if (pass == null) continue;
                                int passId = 0;
                                try { passId = Convert.ToInt32(Prop(pass, "Id")); } catch { }
                                {  // open block to match the old foreach structure
                                DateTime? start = ReadDateTimeValue(Prop(pass, "Start"));
                                int durationDays = 0;
                                try { durationDays = Convert.ToInt32(Prop(pass, "DurationDays")); } catch { }
                                DateTime? end = null;
                                if (start.HasValue && durationDays > 0)
                                    end = start.Value.AddDays(durationDays);
                                // Filter: only currently-active or upcoming-soon passes.
                                if (!end.HasValue || end.Value < now) continue;
                                if (start.HasValue && start.Value > now.AddDays(60)) continue;
                                if (n > 0) sb.Append(",");
                                n++;
                                sb.Append("{\"pass_id\":").Append(passId);
                                if (durationDays > 0)
                                    sb.Append(",\"duration_days\":").Append(durationDays);
                                if (start.HasValue) {
                                    var u = start.Value.ToUniversalTime();
                                    sb.Append(",\"start_utc\":\"").Append(u.ToString("o")).Append("\"");
                                }
                                if (end.HasValue) {
                                    var u = end.Value.ToUniversalTime();
                                    sb.Append(",\"end_utc\":\"").Append(u.ToString("o")).Append("\"");
                                    sb.Append(",\"end_seconds_until\":").Append((long)(u - now).TotalSeconds);
                                }
                                sb.Append("}");
                                }
                            }
                        }
                    } catch { }
                    sb.Append("]}");
                }
            } catch (Exception ex) {
                sb.Append("{\"error\":\"").Append(Esc(ex.Message)).Append("\"}");
            }

            sb.Append("}");
            return sb.ToString();
        }

        // Clan boss (Demon Lord) leaderboard — per-member damage + team
        // composition + keys used. Mirrors the in-game "Demon Lord" tab
        // (Member Info / Champions Used / Team Power).
        //
        // Data flow:
        //   uw.Alliance.Bosses.Data       → AllianceBossData
        //     .Bosses                     → List<AllianceBoss> (one per difficulty)
        //       .Id (AllianceBossTypeId)  → Hard/Brutal/NM/UNM
        //       .HealthLeft, .DamageTaken, .Element, .IsDefeated
        //       .AttackInfoByUserId       → Dictionary<long, AllianceAttackShortInfo>
        //         .HeroInfos (List<ShortHeroInfo>) — 5 champs per attack
        //         .GivenDamage, .SpentKeys, .TotalPower
        //
        // Names: AppModel.ShortUserNotes[userId] → ShortUserNote.Name/Level.
        // Hero names: HeroTypeId → SharedModelManager.StaticData.HeroData.HeroById[heroId].
        private string GetClanBossLeaderboard()
        {
            var sb = new StringBuilder(8192);
            sb.Append("{");
            DateTime now = DateTime.UtcNow;
            sb.Append("\"now_utc\":\"").Append(now.ToString("o")).Append("\"");

            var uw = GetUserWrapper();
            if (uw == null) {
                sb.Append(",\"error\":\"not logged in\"}");
                return sb.ToString();
            }

            // Current logged-in user — uw.User.Id (not AccountWrapper.Id;
            // the Account wrapper doesn't expose Id directly, only the
            // base User struct does).
            long currentUserId = 0;
            try {
                var userStruct = Prop(uw, "User");
                if (userStruct != null) currentUserId = LongProp(userStruct, "Id");
            } catch { }
            sb.Append(",\"current_user_id\":").Append(currentUserId);

            // CB cycle end — daily anchor from AllianceSettings.RefreshTimeHoursUtc.
            try {
                object staticData = Prop(GetAppModel(), "StaticData");
                object staticAllianceData = Prop(staticData, "AllianceData");
                object allianceSettings = Prop(staticAllianceData, "Settings");
                if (allianceSettings != null) {
                    double refreshHr = Convert.ToDouble(Prop(allianceSettings, "RefreshTimeHoursUtc"));
                    var today = new DateTime(now.Year, now.Month, now.Day, 0, 0, 0, DateTimeKind.Utc);
                    var anchor = today.AddHours(refreshHr);
                    if (anchor <= now) anchor = anchor.AddDays(1);
                    sb.Append(",\"cycle_ends_utc\":\"").Append(anchor.ToString("o")).Append("\"");
                    sb.Append(",\"cycle_seconds_remaining\":").Append((long)(anchor - now).TotalSeconds);
                }
            } catch { }

            // User's CB key count — surfaces "did we run today?" at a glance.
            try {
                var account = Prop(uw, "Account");
                var accountData = Prop(account, "AccountData") ?? Prop(account, "Data");
                var resources = Prop(accountData, "Resources");
                // Resources has named accessor properties incl. AllianceBossKey.
                var keys = Prop(resources, "AllianceBossKey");
                if (keys != null) {
                    sb.Append(",\"my_cb_keys\":").Append(Convert.ToDouble(keys).ToString("0.###",
                        System.Globalization.CultureInfo.InvariantCulture));
                }
            } catch { }

            // Resolve UserNoteManager + Hero static data once.
            // UserNoteManager (NoteManager<UserNote>) exposes Request(ids)
            // which fires GetUserNotesCmd + populates the cache. The
            // ShortUserNoteManager has no Request method — it's only
            // populated when other features (arena/leaderboard) push to it.
            object userNotes = null;
            try {
                var appModel = GetAppModel();
                userNotes = Prop(appModel, "UserNotes");
            } catch { }

            object heroByIdDict = null;
            try {
                var appModel = GetAppModel();
                var staticData = Prop(appModel, "StaticData");
                var heroData = Prop(staticData, "HeroData");
                heroByIdDict = Prop(heroData, "HeroById");
            } catch { }

            System.Reflection.MethodInfo userNotesIndexer = null;
            try {
                if (userNotes != null) {
                    // Walk inheritance chain to find get_Item(long) — base class generic.
                    for (var t = userNotes.GetType(); t != null; t = t.BaseType) {
                        userNotesIndexer = t.GetMethod("get_Item", new[] { typeof(long) });
                        if (userNotesIndexer != null) break;
                    }
                }
            } catch { }
            object LookupNote(long uid) {
                if (userNotesIndexer == null || userNotes == null) return null;
                try { return userNotesIndexer.Invoke(userNotes, new object[] { uid }); } catch { return null; }
            }
            string LookupUserName(long uid) {
                var note = LookupNote(uid);
                if (note == null) return null;
                try { return Prop(note, "Name")?.ToString(); } catch { return null; }
            }
            int LookupUserLevel(long uid) {
                var note = LookupNote(uid);
                if (note == null) return 0;
                try { return IntProp(note, "Level"); } catch { return 0; }
            }
            string LookupHeroName(int heroTypeId) {
                if (heroByIdDict == null) return null;
                try {
                    var indexer = heroByIdDict.GetType().GetMethod("get_Item", new[] { typeof(int) });
                    if (indexer == null) return null;
                    var hero = indexer.Invoke(heroByIdDict, new object[] { heroTypeId });
                    if (hero == null) return null;
                    // Hero name comes from text resources keyed by NameId/Id.
                    // Use heroTypeId directly so caller can resolve via skill_descriptions.json.
                    var nameId = Prop(hero, "NameId") ?? Prop(hero, "Id");
                    return nameId?.ToString();
                } catch { return null; }
            }

            // Pre-fetch member UserIds (with rank + level) — used to look
            // up per-member attack info in each boss's AttackInfoByUserId
            // dictionary (IL2Cpp Dictionary.Keys doesn't enumerate cleanly).
            var memberIds = new List<long>();
            try {
                var alliance0 = Prop(uw, "Alliance");
                var membership = Prop(alliance0, "Membership");
                var membersCol = Prop(membership, "Members");
                if (membersCol != null) {
                    // ReadOnlyCollection<AllianceMember> — walk via Count + indexer.
                    int memberCount = 0;
                    try { memberCount = IntProp(membersCol, "Count"); } catch { }
                    var memberIdx = membersCol.GetType().GetMethod("get_Item", new[] { typeof(int) });
                    for (int i = 0; i < memberCount && memberIdx != null; i++) {
                        var mem = memberIdx.Invoke(membersCol, new object[] { i });
                        if (mem == null) continue;
                        long uid = LongProp(mem, "UserId");
                        if (uid != 0) memberIds.Add(uid);
                    }
                }
            } catch { }

            sb.Append(",\"member_count\":").Append(memberIds.Count);

            // Populate UserNote cache for all clan members via the
            // NoteManager<T>.Request(IEnumerable<long>) base method. This
            // fires GetUserNotesCmd internally + writes to _notes dict.
            // Poll briefly for the response to land before reading names.
            int initialCacheCount = 0;
            System.Reflection.FieldInfo notesField = null;
            object notesDict0 = null;
            try {
                if (userNotes != null) {
                    for (var t = userNotes.GetType(); t != null && notesField == null; t = t.BaseType) {
                        notesField = t.GetField("_notes",
                            BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                    }
                    notesDict0 = notesField?.GetValue(userNotes);
                    if (notesDict0 != null) {
                        try { initialCacheCount = IntProp(notesDict0, "Count"); } catch { }
                    }
                }
            } catch { }
            if (initialCacheCount < memberIds.Count && memberIds.Count > 0 && userNotes != null) {
                try {
                    // Find Request(IEnumerable<long>) on the base NoteManager<T>.
                    System.Reflection.MethodInfo reqM = null;
                    for (var t = userNotes.GetType(); t != null && reqM == null; t = t.BaseType) {
                        foreach (var m in t.GetMethods(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.DeclaredOnly)) {
                            if (m.Name != "Request") continue;
                            var ps = m.GetParameters();
                            if (ps.Length == 1 && typeof(System.Collections.IEnumerable).IsAssignableFrom(ps[0].ParameterType)) {
                                reqM = m;
                                break;
                            }
                        }
                    }
                    if (reqM != null) {
                        reqM.Invoke(userNotes, new object[] { memberIds });
                    }
                } catch { }
                // Poll up to 3s for the response.
                for (int i = 0; i < 30; i++) {
                    System.Threading.Thread.Sleep(100);
                    int c = 0;
                    try {
                        var nd = notesField?.GetValue(userNotes);
                        if (nd != null) c = IntProp(nd, "Count");
                    } catch { }
                    if (c >= memberIds.Count) break;
                }
            }
            sb.Append(",\"bosses\":[");
            int bw = 0;
            try {
                var alliance = Prop(uw, "Alliance");
                var bossWrapper = Prop(alliance, "Bosses");
                var bossData = Prop(bossWrapper, "Data");
                var bossesList = Prop(bossData, "Bosses");
                if (bossesList != null) {
                    int n = IntProp(bossesList, "_size");
                    var items = Prop(bossesList, "_items");
                    var getI = items?.GetType().GetMethod("get_Item", new[] { typeof(int) });
                    for (int i = 0; i < n && getI != null; i++) {
                        var boss = getI.Invoke(items, new object[] { i });
                        if (boss == null) continue;
                        int bossTypeId = ReadIl2CppNullableEnumInt(Prop(boss, "Id"));
                        if (bossTypeId == 0) {
                            // Id might not be Nullable<> here; try direct read.
                            try { bossTypeId = Convert.ToInt32(Prop(boss, "Id")); } catch { }
                        }
                        long healthLeft = LongProp(boss, "HealthLeft");
                        long damageTaken = LongProp(boss, "DamageTaken");
                        int element = 0;
                        try { element = Convert.ToInt32(Prop(boss, "Element")); } catch { }
                        bool isDefeated = false;
                        try { var d = Prop(boss, "IsDefeated"); if (d is bool db) isDefeated = db; } catch { }

                        if (bw > 0) sb.Append(",");
                        bw++;
                        sb.Append("{\"boss_type_id\":").Append(bossTypeId);
                        sb.Append(",\"boss_type_name\":\"").Append(BossTypeName(bossTypeId)).Append("\"");
                        sb.Append(",\"element\":").Append(element);
                        sb.Append(",\"element_name\":\"").Append(ElementName(element)).Append("\"");
                        sb.Append(",\"health_left\":").Append(healthLeft);
                        sb.Append(",\"damage_taken\":").Append(damageTaken);
                        sb.Append(",\"is_defeated\":").Append(isDefeated ? "true" : "false");

                        // AttackInfoByUserId — Dictionary<long, AllianceAttackShortInfo>.
                        // IL2Cpp dict enumeration via Keys is broken — iterate
                        // our pre-fetched member list and use ContainsKey/get_Item.
                        sb.Append(",\"members\":[");
                        int mw = 0;
                        try {
                            var attackDict = Prop(boss, "AttackInfoByUserId");
                            if (attackDict != null) {
                                var dictType = attackDict.GetType();
                                var idx = dictType.GetMethod("get_Item", new[] { typeof(long) });
                                var containsKey = dictType.GetMethod("ContainsKey", new[] { typeof(long) });
                                foreach (long uid in memberIds) {
                                    bool present = false;
                                    if (containsKey != null) {
                                        try { present = (bool)containsKey.Invoke(attackDict, new object[] { uid }); } catch { }
                                    }
                                    if (!present) continue;
                                    object attack = null;
                                    try { attack = idx?.Invoke(attackDict, new object[] { uid }); } catch { }
                                    if (attack == null) continue;
                                        long damage = LongProp(attack, "GivenDamage");
                                        int keysSpent = IntProp(attack, "SpentKeys");
                                        int teamPower = IntProp(attack, "TotalPower");
                                        string name = LookupUserName(uid);
                                        int lvl = LookupUserLevel(uid);
                                        if (mw > 0) sb.Append(",");
                                        mw++;
                                        sb.Append("{\"user_id\":").Append(uid);
                                        if (name != null)
                                            sb.Append(",\"name\":\"").Append(Esc(name)).Append("\"");
                                        if (lvl > 0)
                                            sb.Append(",\"level\":").Append(lvl);
                                        sb.Append(",\"damage\":").Append(damage);
                                        sb.Append(",\"keys_spent\":").Append(keysSpent);
                                        sb.Append(",\"team_power\":").Append(teamPower);

                                        // HeroInfos — 5 champs per attack.
                                        sb.Append(",\"heroes\":[");
                                        int hw = 0;
                                        try {
                                            var heroInfos = Prop(attack, "HeroInfos");
                                            if (heroInfos != null) {
                                                int hn = IntProp(heroInfos, "_size");
                                                var hItems = Prop(heroInfos, "_items");
                                                var hGetI = hItems?.GetType().GetMethod("get_Item", new[] { typeof(int) });
                                                for (int j = 0; j < hn && hGetI != null; j++) {
                                                    var hero = hGetI.Invoke(hItems, new object[] { j });
                                                    if (hero == null) continue;
                                                    int htId = IntProp(hero, "HeroTypeId");
                                                    int grade = 0;
                                                    try { grade = Convert.ToInt32(Prop(hero, "Grade")); } catch { }
                                                    int hLvl = IntProp(hero, "Level");
                                                    int emp = IntProp(hero, "EmpowerLevel");
                                                    if (hw > 0) sb.Append(",");
                                                    hw++;
                                                    sb.Append("{\"hero_type_id\":").Append(htId);
                                                    sb.Append(",\"grade\":").Append(grade);
                                                    sb.Append(",\"level\":").Append(hLvl);
                                                    if (emp > 0) sb.Append(",\"empower_level\":").Append(emp);
                                                    sb.Append("}");
                                                }
                                            }
                                        } catch { }
                                        sb.Append("]");
                                        sb.Append("}");
                                }
                            }
                        } catch (Exception ex) {
                            sb.Append("{\"_err\":\"").Append(Esc(ex.Message)).Append("\"}");
                        }
                        sb.Append("]");
                        sb.Append("}");
                    }
                }
            } catch (Exception ex) {
                sb.Append("{\"error\":\"").Append(Esc(ex.Message)).Append("\"}");
            }
            sb.Append("]");

            sb.Append("}");
            return sb.ToString();
        }

        // List arena opponents with status (None=0 / Defeated=1 / Won=2)
        // so callers can skip already-defeated ones rather than firing
        // failed cmds. Path: uw.Arena.ArenaData.Opponents (List<ArenaOpponent>).
        private string GetArenaOpponents()
        {
            var sb = new StringBuilder(2048);
            var uw = GetUserWrapper();
            if (uw == null) return "{\"error\":\"not logged in\"}";
            try
            {
                var ar = Prop(uw, "Arena");
                var arData = Prop(ar, "ArenaData");
                var opps = Prop(arData, "Opponents");
                if (opps == null) return "{\"opponents\":[]}";
                int n = IntProp(opps, "_size");
                var items = Prop(opps, "_items");
                var getI = items?.GetType().GetMethod("get_Item", new[] { typeof(int) });
                sb.Append("{\"opponents\":[");
                int w = 0;
                for (int i = 0; i < n && getI != null; i++)
                {
                    var opp = getI.Invoke(items, new object[] { i });
                    if (opp == null) continue;
                    long uid = LongProp(opp, "UserId");
                    int status = 0;
                    try { status = Convert.ToInt32(Prop(opp, "Status")); } catch { }
                    long points = LongProp(opp, "ArenaPoints");
                    int power = IntProp(opp, "TotalPower");
                    string name = null;
                    try { name = Prop(opp, "Name") as string; } catch { }
                    if (w > 0) sb.Append(",");
                    w++;
                    sb.Append("{\"index\":").Append(i);
                    sb.Append(",\"user_id\":").Append(uid);
                    sb.Append(",\"name\":\"").Append(Esc(name ?? "")).Append("\"");
                    sb.Append(",\"status\":").Append(status);
                    // Status enum: 0=None (not fought), 1=Defeated (we won, can't refight), 2=Won (we lost, refightable)
                    sb.Append(",\"status_name\":\"")
                      .Append(status == 1 ? "Defeated" : status == 2 ? "Won" : "None")
                      .Append("\"");
                    // Empirical 2026-05-24: server rejects ANY fought opponent
                    // (status != None) with Arena_OpponentAlreadyDefeated.
                    // Both Defeated (we won) and Won (they won) mean
                    // "already engaged this pool" → not refightable until refresh.
                    sb.Append(",\"available\":").Append(status == 0 ? "true" : "false");
                    sb.Append(",\"power\":").Append(power);
                    sb.Append(",\"points\":").Append(points);
                    sb.Append("}");
                }
                sb.Append("]");
                // Also include free-refresh time-left so caller can decide
                // to wait/refresh when all are defeated.
                try
                {
                    var m = ar.GetType().GetMethod("GetFreeRefreshTimeLeft",
                        BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                    if (m != null)
                    {
                        var tsResult = m.Invoke(ar, null);
                        double secs = ReadTimeSpanSeconds(tsResult);
                        sb.Append(",\"free_refresh_seconds_until\":").Append((long)Math.Max(0, secs));
                        sb.Append(",\"free_refresh_available_now\":").Append(secs <= 0 ? "true" : "false");
                    }
                }
                catch { }
                sb.Append("}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // Fire RefreshArenaOpponentsCmd. Server-side checks if free
        // (GetFreeRefreshTimeLeft <= 0) or charges gems. Uses the
        // existing ClaimByZeroArgCmd dispatcher.
        private string ArenaRefreshOpponents()
        {
            return ClaimByZeroArgCmd("Client.Model.Gameplay.Battle.Commands.RefreshArenaOpponentsCmd");
        }

        // AllianceBossTypeId enum -> UI difficulty name (verified from dump.cs
        // — starts at 0): Easy=0, Normal=1, Hard=2, Brutal=3, Nightmare=4,
        // UltraNightmare=5.
        private static string BossTypeName(int id) {
            switch (id) {
                case 0: return "Easy";
                case 1: return "Normal";
                case 2: return "Hard";
                case 3: return "Brutal";
                case 4: return "Nightmare";
                case 5: return "UltraNightmare";
                default: return "Type" + id;
            }
        }

        // Element enum: Force=1, Magic=2, Spirit=3, Void=4 (verified against
        // CB rotation logs).
        private static string ElementName(int id) {
            // CORRECTED 2026-06-18: prior mapping had Force/Magic swapped, which
            // propagated through 70+ tick-log analyses (every "Magic UNM" capture
            // was actually a Force UNM). Verified game-truth: Ninja (Magic affinity)
            // has element=1, matching this mapping. Boss aoe2 skill ID prefix
            // also confirms: 222[1=M][...]02 maps as below.
            switch (id) {
                case 1: return "Magic";
                case 2: return "Force";
                case 3: return "Spirit";
                case 4: return "Void";
                default: return "Element" + id;
            }
        }

        // Compact JSON for a Resources struct — emits only non-zero
        // amounts so callers see costs at a glance (Silver, Oil ids, etc).
        // ForgeMaterials is an inner dict; we surface its keyed entries too.
        private void SerializeResource(StringBuilder sb, object res)
        {
            if (res == null) { sb.Append("null"); return; }
            sb.Append("{");
            bool first = true;
            foreach (var p in res.GetType().GetProperties(BindingFlags.Instance | BindingFlags.Public)) {
                if (p.GetIndexParameters().Length > 0) continue;
                if (p.Name == "Pointer" || p.Name == "ObjectClass" || p.Name == "WasCollected") continue;
                object pv = null;
                try { pv = p.GetValue(res); } catch { continue; }
                if (pv == null) continue;
                // Numerics: only emit if non-zero
                if (pv is int iv && iv == 0) continue;
                if (pv is long lv && lv == 0) continue;
                if (pv is double dv && dv == 0) continue;
                if (!first) sb.Append(",");
                first = false;
                sb.Append("\"").Append(p.Name).Append("\":");
                // Special-case Dictionary fields (ForgeMaterials, RawValues, ToRawValues).
                if (pv is System.Collections.IDictionary || pv.GetType().Name.StartsWith("Dictionary")) {
                    sb.Append("{");
                    int dw = 0;
                    foreach (var (eInt, eName, eVal) in DecodeEnumKeyedDict(pv)) {
                        if (dw > 0) sb.Append(",");
                        sb.Append("\"").Append(Esc(eName)).Append("\":").Append(Convert.ToInt32(eVal));
                        dw++;
                    }
                    sb.Append("}");
                } else if (pv is double || pv is float) {
                    sb.Append(Convert.ToDouble(pv).ToString("R", System.Globalization.CultureInfo.InvariantCulture));
                } else if (pv is int || pv is long) {
                    sb.Append(pv);
                } else {
                    sb.Append("\"").Append(Esc(pv.ToString())).Append("\"");
                }
            }
            sb.Append("}");
        }
    }
}
