// Auto-extracted from RaidAutomationPlugin.cs (slice: navigation + context-call).
// All methods are partial-class members of RaidAutomationPlugin.
// Behavior identical; isolates the /navigate UI-target dispatcher,
// the /context-call viewmodel-method invocation path, and
// supporting helpers (FindContextByPath, NAV_TARGETS, dialog open),
// from the rest of the plugin.
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
        // API: /navigate — navigate to game screens
        // =====================================================

        private static readonly Dictionary<string, string> NAV_TARGETS = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            {"arena", "OpenArenaDialog"},
            {"arena3x3", "OpenArena3x3Dialog"},
            {"cb", "OpenClanBossDialog"},
            {"clanboss", "OpenClanBossDialog"},
            {"campaign", "OpenBattleMode"},
            {"dungeon", "OpenDungeonsHUD"},
            {"faction", "OpenFactionWarsDialog"},
            {"live_arena", "OpenLiveArena"},
            {"siege", "OpenSiege"},
            {"village", "MoveToVillage"},
            {"home", "MoveToVillage"},
            {"alliance", "OpenAlliance"},
        };

        private string NavigateTo(string target)
        {
            if (string.IsNullOrEmpty(target) || !NAV_TARGETS.ContainsKey(target))
                return "{\"error\":\"unknown target. Valid: " + string.Join(",", NAV_TARGETS.Keys) + "\"}";

            string methodName = NAV_TARGETS[target];

            // Try multiple type name patterns for the transition class
            string[] typeNames = new string[]
            {
                "Client.ViewModel.InGameTransition.WebViewInGameTransition",
                "WebViewInGameTransition",
                "Client.ViewModel.Contextes.InGameTransition.WebViewInGameTransition",
            };

            Type transType = null;
            string foundTypeName = null;
            foreach (var tn in typeNames)
            {
                transType = FindType(tn);
                if (transType != null) { foundTypeName = tn; break; }
            }

            // Fallback: search all loaded types for WebViewInGameTransition
            if (transType == null)
            {
                foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
                {
                    try
                    {
                        foreach (var t in asm.GetTypes())
                        {
                            if (t.Name == "WebViewInGameTransition")
                            {
                                transType = t;
                                foundTypeName = t.FullName;
                                break;
                            }
                        }
                    }
                    catch { }
                    if (transType != null) break;
                }
            }

            if (transType == null)
                return "{\"error\":\"WebViewInGameTransition type not found\"}";

            // Find the static method
            var method = transType.GetMethod(methodName,
                BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static | BindingFlags.FlattenHierarchy);

            if (method == null)
            {
                // List available methods for debugging
                var methods = new List<string>();
                foreach (var m in transType.GetMethods(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static))
                {
                    methods.Add(m.Name);
                }
                return "{\"error\":\"method " + Esc(methodName) + " not found on " + Esc(foundTypeName) +
                       "\",\"available\":[" + string.Join(",", methods.ConvertAll(m => "\"" + Esc(m) + "\"")) + "]}";
            }

            try
            {
                method.Invoke(null, null);
                return "{\"navigated\":\"" + Esc(target) + "\",\"method\":\"" + Esc(methodName) +
                       "\",\"class\":\"" + Esc(foundTypeName) + "\"}";
            }
            catch (Exception ex)
            {
                string msg = ex.InnerException != null ? ex.InnerException.Message : ex.Message;
                return "{\"error\":\"" + Esc(msg) + "\",\"target\":\"" + Esc(target) + "\"}";
            }
        }

        // /open-dungeon?type=<key|int>
        // Calls WebViewInGameTransition.OpenDungeonOfType(RegionTypeId).
        // RegionTypeId values verified from the game enum (2026-04-25):
        //   void_keep=201, spirit_keep=202, magic_keep=203, force_keep=204,
        //   arcane_keep=205, dragon=206, ice_golem=207, fire_knight=208,
        //   spider=209, minotaur=210
        // Numbers can be passed directly; aliases are resolved by name.
        private static readonly Dictionary<string, int> DUNGEON_TYPE_IDS = new(StringComparer.OrdinalIgnoreCase)
        {
            {"void_keep", 201},
            {"spirit_keep", 202},
            {"magic_keep", 203},
            {"force_keep", 204},
            {"arcane_keep", 205},
            {"dragon", 206},
            {"ice_golem", 207},
            {"fire_knight", 208},
            {"spider", 209},
            {"minotaur", 210},
        };

        private string OpenDungeon(string typeArg, string methodOverride)
        {
            if (string.IsNullOrEmpty(typeArg))
                return "{\"error\":\"type required. Aliases: " + string.Join(",", DUNGEON_TYPE_IDS.Keys) + " or pass an int\"}";

            // Resolve int from alias or parse directly.
            int typeId;
            if (!DUNGEON_TYPE_IDS.TryGetValue(typeArg, out typeId))
            {
                if (!int.TryParse(typeArg, out typeId))
                    return "{\"error\":\"unknown alias '" + Esc(typeArg) + "'. Known: " + string.Join(",", DUNGEON_TYPE_IDS.Keys) + "\"}";
            }

            // Locate WebViewInGameTransition
            Type transType = FindType("Client.ViewModel.Contextes.GlobalEvents.InGameTransition.WebViewInGameTransition");
            if (transType == null)
            {
                foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
                {
                    try
                    {
                        foreach (var t in asm.GetTypes())
                        {
                            if (t.Name == "WebViewInGameTransition") { transType = t; break; }
                        }
                    } catch { }
                    if (transType != null) break;
                }
            }
            if (transType == null) return "{\"error\":\"WebViewInGameTransition type not found\"}";

            // OpenDungeonOfType opens the DungeonsDialog stage list directly
            // (one-shot Village→stages). OpenDungeonsMapWithFocusOn opens
            // the map view with the camera focused on the sector. Default
            // to OpenDungeonOfType for full automation; pass method=focus
            // for the camera-focus variant.
            string usedMethodName;
            if (string.Equals(methodOverride, "focus", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(methodOverride, "OpenDungeonsMapWithFocusOn", StringComparison.OrdinalIgnoreCase))
                usedMethodName = "OpenDungeonsMapWithFocusOn";
            else
                usedMethodName = "OpenDungeonOfType";

            var method = transType.GetMethod(usedMethodName,
                BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static | BindingFlags.FlattenHierarchy);
            if (method == null) return "{\"error\":\"" + Esc(usedMethodName) + " not found on WebViewInGameTransition\"}";

            // Inspect parameter type and convert int → enum if needed.
            var paras = method.GetParameters();
            if (paras.Length != 1)
                return "{\"error\":\"" + Esc(usedMethodName) + " expected 1 param, got " + paras.Length + "\"}";

            object arg;
            try
            {
                if (paras[0].ParameterType.IsEnum)
                    arg = Enum.ToObject(paras[0].ParameterType, typeId);
                else
                    arg = Convert.ChangeType(typeId, paras[0].ParameterType);
            }
            catch (Exception ex)
            {
                return "{\"error\":\"arg conversion failed: " + Esc(ex.Message) + "\"}";
            }

            try
            {
                method.Invoke(null, new[] { arg });
                return "{\"opened\":\"" + Esc(typeArg) + "\",\"type_id\":" + typeId +
                       ",\"method\":\"" + Esc(usedMethodName) + "\"}";
            }
            catch (Exception ex)
            {
                string msg = ex.InnerException != null ? ex.InnerException.Message : ex.Message;
                return "{\"error\":\"" + Esc(msg) + "\",\"type\":\"" + Esc(typeArg) + "\",\"type_id\":" + typeId + "}";
            }
        }

        // /list-static-methods?type=<typeName>&filter=<substring>
        // Lists static methods on the given type. Type lookup uses the same
        // FindType + assembly walk fallback as OpenDungeon. Optional filter
        // narrows by case-insensitive substring match. Read-only — does not
        // touch live MonoBehaviours, so cannot crash the game.
        private string ListStaticMethods(string typeName, string filter)
        {
            if (string.IsNullOrEmpty(typeName))
                return "{\"error\":\"type required\"}";

            Type t = FindType(typeName);
            if (t == null)
            {
                foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
                {
                    try
                    {
                        foreach (var ti in asm.GetTypes())
                        {
                            if (ti.Name == typeName || ti.FullName == typeName) { t = ti; break; }
                        }
                    } catch { }
                    if (t != null) break;
                }
            }
            if (t == null) return "{\"error\":\"type not found: " + Esc(typeName) + "\"}";

            // Enum types: dump names + numeric values (much more useful than methods).
            if (t.IsEnum)
            {
                var er = new List<string>();
                try
                {
                    foreach (var name in Enum.GetNames(t))
                    {
                        if (!string.IsNullOrEmpty(filter) &&
                            name.IndexOf(filter, StringComparison.OrdinalIgnoreCase) < 0)
                            continue;
                        var val = Enum.Parse(t, name);
                        long iv = Convert.ToInt64(val);
                        er.Add("{\"name\":\"" + Esc(name) + "\",\"value\":" + iv + "}");
                    }
                }
                catch (Exception ex)
                {
                    return "{\"error\":\"enum dump failed: " + Esc(ex.Message) + "\"}";
                }
                return "{\"type\":\"" + Esc(t.FullName) + "\",\"is_enum\":true,\"count\":" +
                       er.Count + ",\"values\":[" + string.Join(",", er) + "]}";
            }

            var rows = new List<string>();
            foreach (var m in t.GetMethods(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static | BindingFlags.FlattenHierarchy))
            {
                if (!string.IsNullOrEmpty(filter) &&
                    m.Name.IndexOf(filter, StringComparison.OrdinalIgnoreCase) < 0)
                    continue;
                var paras = m.GetParameters();
                var sb = new StringBuilder();
                sb.Append("{\"name\":\"").Append(Esc(m.Name)).Append("\",\"params\":[");
                for (int i = 0; i < paras.Length; i++)
                {
                    if (i > 0) sb.Append(",");
                    sb.Append("\"").Append(Esc(paras[i].ParameterType.Name)).Append("\"");
                }
                sb.Append("]}");
                rows.Add(sb.ToString());
            }
            return "{\"type\":\"" + Esc(t.FullName) + "\",\"count\":" + rows.Count +
                   ",\"methods\":[" + string.Join(",", rows) + "]}";
        }

        // /static-field?type=<typeName>&name=<fieldName>[&depth=N]
        // Reads a static field or property by name from the given type.
        // Walks the result up to `depth` levels (default 3) and returns
        // a JSON dump using the same SerializeValue logic as
        // /static-export. Useful for inspecting hardcoded game-side
        // tables that aren't on `ClientStaticData` (e.g.
        // ChangeEffectLifetimeProcessor.NonIncreaseableEffects).
        private string GetStaticField(string typeName, string fieldName, string depthArg)
        {
            if (string.IsNullOrEmpty(typeName) || string.IsNullOrEmpty(fieldName))
                return "{\"error\":\"type and name required\"}";

            int depth = 3;
            if (!string.IsNullOrEmpty(depthArg)) int.TryParse(depthArg, out depth);

            Type t = FindType(typeName);
            if (t == null) return "{\"error\":\"type not found: " + Esc(typeName) + "\"}";

            object value = null;
            string source = null;
            try
            {
                // Try public static field
                var f = t.GetField(fieldName, BindingFlags.Public | BindingFlags.Static |
                                              BindingFlags.NonPublic | BindingFlags.FlattenHierarchy);
                if (f != null) { value = f.GetValue(null); source = "field"; }
                else
                {
                    var p = t.GetProperty(fieldName, BindingFlags.Public | BindingFlags.Static |
                                                     BindingFlags.NonPublic | BindingFlags.FlattenHierarchy);
                    if (p != null) { value = p.GetValue(null); source = "property"; }
                    else
                    {
                        // Try get_Name accessor for IL2CPP-style properties
                        var m = t.GetMethod("get_" + fieldName,
                            BindingFlags.Public | BindingFlags.Static |
                            BindingFlags.NonPublic | BindingFlags.FlattenHierarchy);
                        if (m != null) { value = m.Invoke(null, null); source = "getter"; }
                    }
                }
            }
            catch (Exception ex)
            {
                return "{\"error\":\"read failed: " + Esc(ex.Message) + "\"}";
            }

            if (value == null && source == null)
                return "{\"error\":\"no static field/property/getter named " + Esc(fieldName) + " on " + Esc(t.FullName) + "\"}";

            var sb = new StringBuilder();
            sb.Append("{\"type\":\"").Append(Esc(t.FullName)).Append("\",\"name\":\"")
              .Append(Esc(fieldName)).Append("\",\"source\":\"")
              .Append(Esc(source ?? "null")).Append("\",\"value\":");
            try
            {
                SerializeValue(sb, value, depth, 5000, new HashSet<object>());
            }
            catch (Exception ex)
            {
                sb.Append("null,\"err\":\"").Append(Esc(ex.Message)).Append("\"");
            }
            sb.Append("}");
            return sb.ToString();
        }

        // /damage-calc-probe — invokes static helpers in DamageCalculator
        // with synthetic args to extract the exact damage modifier per
        // hit type and element relation. No battle needed; values come
        // straight from the IL2CPP method bodies.
        //
        // For HitTypeBonus(BattleHero, HitType) we can't synthesise a
        // BattleHero, so this endpoint focuses on ElementAdvantageBonus
        // (single enum arg) which IS readable directly. For HitTypeBonus
        // we capture observations from real damage events instead.
        private string GetDamageCalcProbe()
        {
            var sb = new StringBuilder("{");
            var dcType = FindType("SharedModel.Battle.Core.DamageCalculator");
            if (dcType == null) return "{\"error\":\"DamageCalculator type not found\"}";

            // ElementAdvantageBonus(ElementRelation) — returns Fixed
            try
            {
                var erType = FindType("SharedModel.Meta.Heroes.ElementRelation");
                var meth = dcType.GetMethod("ElementAdvantageBonus",
                    BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static);
                sb.Append("\"ElementAdvantageBonus\":{");
                bool first = true;
                if (erType != null && meth != null)
                {
                    foreach (var name in Enum.GetNames(erType))
                    {
                        var enumVal = Enum.Parse(erType, name);
                        try
                        {
                            var result = meth.Invoke(null, new object[] { enumVal });
                            if (result == null) continue;
                            // Result is Fixed; read RawValue.
                            var raw = Prop(result, "RawValue");
                            if (raw == null) continue;
                            // Scale to 4 decimals: (raw * 10000) >> 32
                            long r = Convert.ToInt64(raw);
                            long scaled = (r * 10000) >> 32;
                            if (!first) sb.Append(",");
                            first = false;
                            sb.Append("\"").Append(Esc(name)).Append("\":").Append(scaled / 10000.0);
                        }
                        catch (Exception ex)
                        {
                            if (!first) sb.Append(",");
                            first = false;
                            sb.Append("\"").Append(Esc(name)).Append("_err\":\"")
                              .Append(Esc(ex.Message)).Append("\"");
                        }
                    }
                }
                sb.Append("}");
            }
            catch (Exception ex)
            {
                sb.Append("\"_eab_err\":\"").Append(Esc(ex.Message)).Append("\"");
            }

            // HitTypeBonus(BattleHero, HitType) — needs a BattleHero,
            // can't synthesise. Document the constraint.
            sb.Append(",\"HitTypeBonus_note\":\"requires live BattleHero arg, see GameplayData.{Crushing,Glancing,Critical}HitCoef instead\"");

            sb.Append("}");
            return sb.ToString();
        }

        // /effect-kind-group?group=<groupName>
        // Walks every EffectKindId enum value and asks
        // EffectKindGroupExtensions.Contains(group, kindId) to figure
        // out which kinds belong to the named group. Surfaces the
        // BossImmunitiesEffects / ControlEffects / EffectThatApplyStatusDebuffs
        // groups as flat ID lists for the sim.
        private string GetEffectKindGroup(string groupName)
        {
            if (string.IsNullOrEmpty(groupName))
                return "{\"error\":\"group required\"}";
            var groupType = FindType("SharedModel.Battle.Effects.EffectKindGroup");
            if (groupType == null)
                return "{\"error\":\"EffectKindGroup type not found\"}";
            var kindType = FindType("SharedModel.Battle.Effects.EffectKindId");
            if (kindType == null)
                return "{\"error\":\"EffectKindId type not found\"}";
            var extType = FindType("SharedModel.Battle.Effects.EffectKindGroupExtensions");
            if (extType == null)
                return "{\"error\":\"EffectKindGroupExtensions type not found\"}";

            object groupVal;
            try { groupVal = Enum.Parse(groupType, groupName, true); }
            catch (Exception ex)
            {
                return "{\"error\":\"unknown group: " + Esc(groupName) + " (" + Esc(ex.Message) + ")\"}";
            }

            var containsMethod = extType.GetMethod("Contains",
                new[] { groupType, kindType });
            if (containsMethod == null)
                return "{\"error\":\"Contains(EffectKindGroup, EffectKindId) not found\"}";

            var sb = new StringBuilder();
            sb.Append("{\"group\":\"").Append(Esc(groupName)).Append("\",\"kinds\":[");
            int n = 0;
            try
            {
                foreach (var name in Enum.GetNames(kindType))
                {
                    var kindVal = Enum.Parse(kindType, name);
                    bool contained = false;
                    try { contained = (bool)containsMethod.Invoke(null, new object[] { groupVal, kindVal }); }
                    catch { continue; }
                    if (!contained) continue;
                    long iv = Convert.ToInt64(kindVal);
                    if (n > 0) sb.Append(",");
                    sb.Append("{\"name\":\"").Append(Esc(name)).Append("\",\"id\":").Append(iv).Append("}");
                    n++;
                }
            }
            catch (Exception ex)
            {
                return "{\"error\":\"enum walk failed: " + Esc(ex.Message) + "\"}";
            }
            sb.Append("],\"count\":").Append(n).Append("}");
            return sb.ToString();
        }

        // /list-active?path=X[&depth=N&filter=substr]
        // Walks GameObjects under path and returns active ones by name. Used
        // for UI state inspection (e.g. is "VictoryHeader" active vs
        // "DefeatHeader"). Default depth 4. Optional substring filter on
        // GameObject name. Read-only.
        private string ListActive(string path, string depthArg, string filter)
        {
            if (string.IsNullOrEmpty(path)) return "{\"error\":\"path required\"}";
            int maxDepth = 4;
            if (!string.IsNullOrEmpty(depthArg)) int.TryParse(depthArg, out maxDepth);

            var go = GameObject.Find(path);
            if (go == null) return "{\"error\":\"not found: " + Esc(path) + "\"}";

            var rows = new List<string>();
            int total = 0;
            void Walk(Transform t, int d)
            {
                if (d > maxDepth) return;
                if (!t.gameObject.activeSelf) return;
                total++;
                string name = t.gameObject.name;
                if (string.IsNullOrEmpty(filter) ||
                    name.IndexOf(filter, StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    rows.Add("{\"name\":\"" + Esc(name) + "\",\"depth\":" + d +
                             ",\"path\":\"" + Esc(GetGameObjectPath(t)) + "\"}");
                }
                int n = t.childCount;
                for (int i = 0; i < n && i < 60; i++) Walk(t.GetChild(i), d + 1);
            }
            Walk(go.transform, 0);
            return "{\"root\":\"" + Esc(path) + "\",\"total_active\":" + total +
                   ",\"matches\":[" + string.Join(",", rows) + "]}";
        }

        // /set-scroll?path=X[&v=0..1&h=0..1]
        // Finds a Unity ScrollRect on the GameObject (or anywhere in its
        // children) and sets verticalNormalizedPosition / horizontalNormalizedPosition.
        // 0 = bottom/right, 1 = top/left. Used to scroll virtualized lists
        // so that off-screen items render. Safe — pure Unity component access.
        private string SetScroll(string path, string vArg, string hArg)
        {
            if (string.IsNullOrEmpty(path)) return "{\"error\":\"path required\"}";
            var go = GameObject.Find(path);
            if (go == null) return "{\"error\":\"not found: " + Esc(path) + "\"}";

            var sr = go.GetComponent<UnityEngine.UI.ScrollRect>();
            if (sr == null) sr = go.GetComponentInChildren<UnityEngine.UI.ScrollRect>(true);
            if (sr == null) return "{\"error\":\"no ScrollRect under " + Esc(path) + "\"}";

            float? v = null, h = null;
            if (!string.IsNullOrEmpty(vArg) && float.TryParse(vArg, out var vf)) v = Mathf.Clamp01(vf);
            if (!string.IsNullOrEmpty(hArg) && float.TryParse(hArg, out var hf)) h = Mathf.Clamp01(hf);
            if (v.HasValue) sr.verticalNormalizedPosition = v.Value;
            if (h.HasValue) sr.horizontalNormalizedPosition = h.Value;

            return "{\"set\":true,\"v\":" + sr.verticalNormalizedPosition.ToString("0.000") +
                   ",\"h\":" + sr.horizontalNormalizedPosition.ToString("0.000") + "}";
        }

        // /list-components?path=X[&hier=1] - dump component types. With
        // hier=1, also shows the parent class chain for each component.
        private string ListComponents(string path)
        {
            if (string.IsNullOrEmpty(path)) return "{\"error\":\"path required\"}";
            var go = GameObject.Find(path);
            if (go == null) return "{\"error\":\"not found: " + Esc(path) + "\"}";
            var rows = new List<string>();
            foreach (var c in go.GetComponents<Component>())
            {
                if (c == null) continue;
                string name = "?";
                var hierarchy = new List<string>();
                try
                {
                    IntPtr ptr = c.Pointer;
                    if (ptr != IntPtr.Zero)
                    {
                        IntPtr klass = il2cpp_object_get_class(ptr);
                        IntPtr k = klass;
                        while (k != IntPtr.Zero && hierarchy.Count < 10)
                        {
                            string cn = Marshal.PtrToStringAnsi(il2cpp_class_get_name(k));
                            string ns = Marshal.PtrToStringAnsi(il2cpp_class_get_namespace(k));
                            string full = string.IsNullOrEmpty(ns) ? cn : ns + "." + cn;
                            hierarchy.Add(full);
                            if (cn == "Object" || cn == "Il2CppObjectBase") break;
                            k = il2cpp_class_get_parent(k);
                        }
                        if (hierarchy.Count > 0) name = hierarchy[0];
                    }
                }
                catch { }
                if (name == "?") name = c.GetType().FullName;
                var hierJson = string.Join(",", hierarchy.ConvertAll(h => "\"" + Esc(h) + "\""));
                rows.Add("{\"name\":\"" + Esc(name) + "\",\"hier\":[" + hierJson + "]}");
            }
            return "{\"path\":\"" + Esc(path) + "\",\"components\":[" +
                   string.Join(",", rows) + "]}";
        }

        // /get-text?path=X - read TMP/Text component text from a GameObject
        // and any active descendants. Returns concatenated text snippets so
        // labels with nested structure (header + body) can be inspected.
        private string GetText(string path)
        {
            if (string.IsNullOrEmpty(path)) return "{\"error\":\"path required\"}";
            var go = GameObject.Find(path);
            if (go == null) return "{\"error\":\"not found: " + Esc(path) + "\"}";
            var rows = new List<string>();
            void Walk(Transform t, int d)
            {
                if (d > 6) return;
                if (!t.gameObject.activeSelf) return;
                foreach (var c in t.gameObject.GetComponents<Component>())
                {
                    if (c == null) continue;
                    string txt = null;
                    string cn = null;
                    try
                    {
                        // First, identify if this component is a Text-like type
                        // by walking the IL2CPP class hierarchy.
                        IntPtr ptr = c.Pointer;
                        if (ptr == IntPtr.Zero) continue;
                        IntPtr klass = il2cpp_object_get_class(ptr);
                        bool isText = false;
                        IntPtr k = klass;
                        for (int hops = 0; k != IntPtr.Zero && hops < 12; hops++)
                        {
                            string kn = Marshal.PtrToStringAnsi(il2cpp_class_get_name(k));
                            if (cn == null) cn = kn;
                            if (kn == "Text" || kn == "TMP_Text" ||
                                kn == "TextMeshProUGUI" || kn == "TextExtended")
                            { isText = true; break; }
                            k = il2cpp_class_get_parent(k);
                        }
                        if (!isText) continue;
                        // Use the managed Il2CppSystem wrapper to read .text
                        try
                        {
                            // Cast through Il2CppSystem.Object then to UI.Text
                            var asText = c.TryCast<UnityEngine.UI.Text>();
                            if (asText != null) txt = asText.text;
                        }
                        catch { }
                    }
                    catch { }
                    if (!string.IsNullOrEmpty(txt))
                        rows.Add("{\"name\":\"" + Esc(t.gameObject.name) +
                                 "\",\"type\":\"" + Esc(cn ?? "") +
                                 "\",\"text\":\"" + Esc(txt) + "\"}");
                }
                int n = t.childCount;
                for (int i = 0; i < n && i < 30; i++) Walk(t.GetChild(i), d + 1);
            }
            Walk(go.transform, 0);
            return "{\"path\":\"" + Esc(path) + "\",\"texts\":[" + string.Join(",", rows) + "]}";
        }

        private static string GetGameObjectPath(Transform t)
        {
            var parts = new List<string>();
            var cur = t;
            while (cur != null) { parts.Insert(0, cur.gameObject.name); cur = cur.parent; }
            return string.Join("/", parts);
        }

        // =====================================================
        // API: /context-call — invoke method on a view's context
        // =====================================================

        private string CallOnViewContext(string objPath, string methodName, string arg)
        {
            if (string.IsNullOrEmpty(methodName))
                return "{\"error\":\"method required\"}";

            // Collect roots to search: the given path, then dialog/overlay/messagebox parents
            var roots = new List<Transform>();
            if (!string.IsNullOrEmpty(objPath))
            {
                var go = GameObject.Find(objPath);
                if (go == null)
                    return "{\"error\":\"not found: " + Esc(objPath) + "\"}";
                roots.Add(go.transform);
            }
            else
            {
                // No path — search all active dialogs, overlays, messageboxes
                string[] parentPaths = new string[]
                {
                    "UIManager/Canvas (Ui Root)/Dialogs",
                    "UIManager/Canvas (Ui Root)/OverlayDialogs",
                    "UIManager/Canvas (Ui Root)/MessageBoxes",
                };
                foreach (var pp in parentPaths)
                {
                    var parent = GameObject.Find(pp);
                    if (parent == null) continue;
                    for (int i = 0; i < parent.transform.childCount; i++)
                    {
                        var child = parent.transform.GetChild(i).gameObject;
                        if (child.activeSelf) roots.Add(child.transform);
                    }
                }
                if (roots.Count == 0)
                    return "{\"error\":\"no active dialogs found and no path provided\"}";
            }

            // Track found contexts + their methods for error reporting.
            // The methods list lets callers discover the right method name
            // without trial-and-error or a separate "list-methods" endpoint.
            var foundContexts = new List<string>();
            var contextMethods = new Dictionary<string, List<string>>();

            foreach (var root in roots)
            {
                string result = SearchContextAndInvoke(root, methodName, arg, 6, foundContexts, contextMethods);
                if (result != null) return result;
            }

            if (foundContexts.Count > 0)
            {
                var sb = new StringBuilder();
                sb.Append("{\"error\":\"method ").Append(Esc(methodName))
                  .Append(" not found\",\"searched\":[");
                bool first = true;
                foreach (var c in foundContexts)
                {
                    if (!first) sb.Append(",");
                    first = false;
                    sb.Append("{\"context\":\"").Append(Esc(c)).Append("\"");
                    if (contextMethods.TryGetValue(c, out var methods))
                    {
                        sb.Append(",\"methods\":[");
                        bool firstM = true;
                        foreach (var m in methods)
                        {
                            if (!firstM) sb.Append(",");
                            firstM = false;
                            sb.Append("\"").Append(Esc(m)).Append("\"");
                        }
                        sb.Append("]");
                    }
                    sb.Append("}");
                }
                sb.Append("]}");
                return sb.ToString();
            }

            return "{\"error\":\"no context with method " + Esc(methodName) + " found in hierarchy\"}";
        }

        /// <summary>
        /// BFS through a transform hierarchy using RAW IL2CPP pointers to find
        /// MonoBehaviours with a get_Context method (BaseView subclasses).
        /// Standard C# reflection cannot see IL2CPP-defined properties on proxy types,
        /// so we use il2cpp_object_get_class + il2cpp_class_get_methods directly.
        /// </summary>
        private string SearchContextAndInvoke(Transform root, string methodName, string arg, int maxDepth, List<string> foundContexts, Dictionary<string, List<string>> contextMethods = null)
        {
            var toScan = new Queue<KeyValuePair<Transform, int>>();
            toScan.Enqueue(new KeyValuePair<Transform, int>(root, 0));

            while (toScan.Count > 0)
            {
                var pair = toScan.Dequeue();
                var t = pair.Key;
                int depth = pair.Value;

                var monos = t.gameObject.GetComponents<MonoBehaviour>();
                if (monos != null)
                {
                    foreach (var mono in monos)
                    {
                        if (mono == null) continue;
                        try
                        {
                            // Use raw IL2CPP to find get_Context method
                            IntPtr monoPtr = mono.Pointer;
                            if (monoPtr == IntPtr.Zero) continue;
                            IntPtr monoClass = il2cpp_object_get_class(monoPtr);
                            if (monoClass == IntPtr.Zero) continue;

                            // Walk class hierarchy looking for get_Context
                            IntPtr klass = monoClass;
                            IntPtr getCtxMethod = IntPtr.Zero;
                            while (klass != IntPtr.Zero && getCtxMethod == IntPtr.Zero)
                            {
                                IntPtr mIter = IntPtr.Zero;
                                IntPtr m;
                                while ((m = il2cpp_class_get_methods(klass, ref mIter)) != IntPtr.Zero)
                                {
                                    string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                                    if (mn == "get_Context" && il2cpp_method_get_param_count(m) == 0)
                                    {
                                        getCtxMethod = m;
                                        break;
                                    }
                                }
                                if (getCtxMethod == IntPtr.Zero)
                                    klass = il2cpp_class_get_parent(klass);
                            }
                            if (getCtxMethod == IntPtr.Zero) continue;

                            // Call get_Context to get the context object
                            IntPtr exc = IntPtr.Zero;
                            IntPtr ctxObj = il2cpp_runtime_invoke(getCtxMethod, monoPtr, IntPtr.Zero, ref exc);
                            if (exc != IntPtr.Zero || ctxObj == IntPtr.Zero) continue;

                            IntPtr ctxClass = il2cpp_object_get_class(ctxObj);
                            if (ctxClass == IntPtr.Zero) continue;

                            string ctxClassName = Marshal.PtrToStringAnsi(il2cpp_class_get_name(ctxClass));
                            string ctxNs = Marshal.PtrToStringAnsi(il2cpp_class_get_namespace(ctxClass));
                            if (ctxClassName == null || ctxClassName.StartsWith("Il2Cpp")) continue;

                            string fullCtxName = ctxNs + "." + ctxClassName;
                            if (foundContexts != null) foundContexts.Add(fullCtxName);

                            // Find the target method on the context (walk hierarchy).
                            // While iterating, also collect ALL method names if the
                            // caller asked for them — costs nothing extra since we're
                            // already walking the methods enumeration.
                            IntPtr targetMethod = IntPtr.Zero;
                            IntPtr ck = ctxClass;
                            List<string> seenMethods = null;
                            if (contextMethods != null && !contextMethods.ContainsKey(fullCtxName))
                            {
                                seenMethods = new List<string>();
                                contextMethods[fullCtxName] = seenMethods;
                            }
                            while (ck != IntPtr.Zero && targetMethod == IntPtr.Zero)
                            {
                                IntPtr mi = IntPtr.Zero;
                                IntPtr m2;
                                while ((m2 = il2cpp_class_get_methods(ck, ref mi)) != IntPtr.Zero)
                                {
                                    string mn2 = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m2));
                                    if (seenMethods != null && mn2 != null && !mn2.StartsWith("get_") && !mn2.StartsWith("set_") && mn2 != ".ctor")
                                        seenMethods.Add(mn2 + "/" + il2cpp_method_get_param_count(m2));
                                    if (mn2 == methodName)
                                    {
                                        uint pc = il2cpp_method_get_param_count(m2);
                                        if (pc == 0)
                                        {
                                            targetMethod = m2;
                                            break;
                                        }
                                    }
                                }
                                ck = il2cpp_class_get_parent(ck);
                                string pn = ck != IntPtr.Zero ? Marshal.PtrToStringAnsi(il2cpp_class_get_name(ck)) : "";
                                if (pn == "Object" || pn == "Il2CppObjectBase") break;
                            }

                            if (targetMethod == IntPtr.Zero) continue;

                            // Invoke the method on the context
                            IntPtr exc2 = IntPtr.Zero;
                            IntPtr retObj = il2cpp_runtime_invoke(targetMethod, ctxObj, IntPtr.Zero, ref exc2);

                            if (exc2 != IntPtr.Zero)
                                return "{\"error\":\"invoke exception\",\"context\":\"" + Esc(fullCtxName) +
                                       "\",\"method\":\"" + Esc(methodName) + "\"}";

                            // Try to extract a primitive return value (bool/int/string).
                            // IL2CPP value-type returns are boxed; we unbox via il2cpp_object_unbox.
                            string retJson = "";
                            try
                            {
                                if (retObj != IntPtr.Zero)
                                {
                                    IntPtr retClass = il2cpp_object_get_class(retObj);
                                    string rcn = retClass != IntPtr.Zero ?
                                        Marshal.PtrToStringAnsi(il2cpp_class_get_name(retClass)) : null;
                                    if (rcn == "Boolean")
                                    {
                                        IntPtr unbox = il2cpp_object_unbox(retObj);
                                        byte b = Marshal.ReadByte(unbox);
                                        retJson = ",\"return\":" + (b != 0 ? "true" : "false");
                                    }
                                    else if (rcn == "Int32")
                                    {
                                        IntPtr unbox = il2cpp_object_unbox(retObj);
                                        int iv = Marshal.ReadInt32(unbox);
                                        retJson = ",\"return\":" + iv;
                                    }
                                    else if (rcn == "String")
                                    {
                                        // Use the managed string conversion via Il2CppToManagedString-equivalent.
                                        // Easiest: use Il2CppSystem.String wrapper if available.
                                        try
                                        {
                                            var wrapper = new Il2CppSystem.Object(retObj).Cast<Il2CppSystem.String>();
                                            string s = wrapper;
                                            retJson = ",\"return\":\"" + Esc(s ?? "") + "\"";
                                        }
                                        catch { }
                                    }
                                }
                            }
                            catch { }

                            return "{\"invoked\":\"" + Esc(methodName) + "\",\"on_context\":\"" + Esc(fullCtxName) +
                                   "\",\"view_path\":\"" + Esc(GetPath(t)) + "\"" + retJson + "}";
                        }
                        catch { }
                    }
                }

                if (depth < maxDepth)
                {
                    for (int ci = 0; ci < t.childCount && ci < 30; ci++)
                        toScan.Enqueue(new KeyValuePair<Transform, int>(t.GetChild(ci), depth + 1));
                }
            }
            return null;
        }
    }
}
