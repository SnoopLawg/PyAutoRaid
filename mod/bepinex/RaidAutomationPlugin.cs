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
    [BepInPlugin("com.pyautoraid.automation", "RaidAutomation", "2.0.0")]
    public class RaidAutomationPlugin : BasePlugin
    {
        internal static ManualLogSource Logger;
        private HttpListener _listener;
        private Thread _serverThread;
        private bool _running;
        private const int PORT = 6790;
        private static readonly ConcurrentQueue<Action> MainThreadQueue = new();

        // IL2CPP native API — direct DllImport (same as MelonLoader mod)
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_object_get_class(IntPtr obj);
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_class_get_methods(IntPtr klass, ref IntPtr iter);
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_method_get_name(IntPtr method);
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_class_get_parent(IntPtr klass);
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_class_get_name(IntPtr klass);
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_class_get_namespace(IntPtr klass);
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_runtime_invoke(IntPtr method, IntPtr obj, IntPtr args, ref IntPtr exc);
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_object_unbox(IntPtr obj);
        [DllImport("GameAssembly")]
        static extern uint il2cpp_method_get_param_count(IntPtr method);
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_class_get_fields(IntPtr klass, ref IntPtr iter);
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_field_get_name(IntPtr field);
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_field_get_type(IntPtr field);
        [DllImport("GameAssembly")]
        static extern uint il2cpp_field_get_offset(IntPtr field);
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_domain_get();
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_domain_get_assemblies(IntPtr domain, ref uint size);
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_assembly_get_image(IntPtr assembly);
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_class_from_name(IntPtr image, IntPtr namespaze, IntPtr name);
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_image_get_name(IntPtr image);
        [DllImport("GameAssembly")]
        static extern void il2cpp_field_get_value(IntPtr obj, IntPtr field, IntPtr value);
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_type_get_name(IntPtr type);

        // Real ArtifactStatKindId captured from MessagePack deserialization
        // Key = ArtifactBonus IL2CPP pointer, Value = raw ArtifactStatKindId (10=CR, 11=CD)
        internal static readonly ConcurrentDictionary<long, int> RealStatKindMap = new();

        // Live battle state captured via Harmony hooks on ProcessStartTurn
        internal static object _activeBattleProcessor;
        internal static readonly List<string> _battleLog = new();
        // Preserved snapshot of the most recently completed battle. Served from
        // /battle-log when no battle is active, so cb_daily can fetch the last
        // run even after the game transitions back to the CB screen (which
        // re-fires ProcessStartBattle and wipes _battleLog).
        internal static readonly List<string> _completedBattleLog = new();
        internal static int _completedTurnCount = 0;
        internal static int _completedPollCount = 0;
        internal static int _battleCommandCount;   // incremented per Harmony turn hook
        internal static int _pollCount;             // incremented per Update() poll during battle
        internal static bool _battleActive;
        internal static bool _ctxDiagLogged;        // logs Context properties once per battle on heroes-lookup failure
        internal static bool _skillCmdDiagLogged;   // logs SkillCommand properties once per mod lifetime
        internal static bool _effectDiagLogged;     // logs AppliedEffect schema once per mod lifetime (needs populated dict)
        internal static int _effectDiagAttempts;    // cap retry attempts per battle so we don't flood log
        internal static bool _challengeDiagLogged;  // logs Challenge schema once per mod lifetime
        internal static int _challengeDiagAttempts; // cap retry attempts for Challenge schema
        internal static bool _statImpactDiagLogged; // logs EffectContext schema from StatImpactByEffects once
        internal static int _statImpactDiagAttempts;
        internal static bool _buffApiDiagLogged;   // logs BattleHero buff/effect method scan once per battle
        internal static int _lastStatsLogTurn;      // last turn we emitted the context/hero snapshot

        // Cached offsets for HeroState buff lists (discovered once via IL2CPP field scan)
        internal static int _hsAppliedBuffsOff = -1;   // HeroState.AppliedBuffs field offset
        internal static int _hsAppliedDebuffsOff = -1;  // HeroState.AppliedDebuffs field offset
        internal static IntPtr _aeEffectTypeIdField;      // AppliedEffect.EffectTypeId IL2CPP field handle
        internal static IntPtr _aeTurnLeftField;         // AppliedEffect.TurnLeft IL2CPP field handle
        internal static IntPtr _aeProducerIdField;       // AppliedEffect.ProducerId IL2CPP field handle
        internal static bool _hsBuffFieldsResolved;      // true once we've attempted to resolve
        internal static bool _aeFieldsResolved;          // true once we've resolved AppliedEffect fields

        // Queue for artifact commands to dispatch from game context
        internal static readonly ConcurrentQueue<ArtifactCmd> ArtifactCmdQueue = new();
        internal static readonly ConcurrentDictionary<int, ArtifactCmdResult> ArtifactCmdResults = new();
        private static int _cmdIdCounter;

        internal class ArtifactCmd
        {
            public int Id;
            public string Action; // "activate", "deactivate", "swap"
            public int HeroId;
            public int ArtifactId;
            public int ArtifactFromId; // for swap
            public int ArtifactOwnerId; // for swap
        }

        internal class ArtifactCmdResult
        {
            public bool Done;
            public bool Ok;
            public string Error;
        }

        // Cached reflection info
        private static Type _appModelType;
        private static PropertyInfo _instanceProp;
        private static bool _reflectionCached;

        public override void Load()
        {
            Instance = this;
            Logger = Log;
            Logger.LogInfo("RaidAutomation v2.0 (BepInEx) starting...");
            ClassInjector.RegisterTypeInIl2Cpp<RaidUpdateBehaviour>();
            var go = new GameObject("RaidAutomation");
            GameObject.DontDestroyOnLoad(go);
            go.hideFlags = HideFlags.HideAndDontSave;
            go.AddComponent<RaidUpdateBehaviour>();
            StartHttpServer();

            // Apply Harmony patches
            try
            {
                var harmony = new Harmony("com.pyautoraid.automation");

                // Patch ArtifactBonus.set_KindId to capture raw stat values
                // The deserializer converts ArtifactStatKindId → StatKindId before calling this.
                // But we can't see the original. Instead, patch the Deserialize method postfix
                // to re-read the bonus and try to determine real type from context.

                // Actually: patch set__kindId (backing field setter) which receives StatKindId
                // The caller (Deserialize) reads the raw int and converts INLINE before calling.
                // We need to go deeper — patch at the IL2CPP level.

                // Simplest working approach: after ALL artifacts are loaded, scan each artifact's
                // PrimaryBonus and use the Value to disambiguate:
                // - HP% 6*L16 = 60% (0.60), CR% 6*L16 = 60% (0.60), CD% 6*L16 = 80% (0.80)
                // CD% has DIFFERENT values from HP%/CR% at the same rank!
                // CD% is always higher: 6*L16=80 vs HP/CR=60, 5*L16=65 vs 50, 4*L16=50 vs 35
                // So if value > expected_max_for_HP_at_rank, it's CD%!
                // And CR% vs HP% can be distinguished by substat exclusion.

                // ArtifactBonus Harmony patch — DISABLED (crashes during login deserialization)
                Logger.LogInfo("Harmony: ArtifactBonus patch disabled");
                // BattleProcessor hooks — ProcessStartTurn, ProcessStartBattle, ProcessEndBattle
                // These only fire during battles, never during login (safe)
                var procType = FindTypeStatic("SharedModel.Battle.Core.BattleProcessor");
                if (procType != null)
                {
                    foreach (var hookName in new[] { "ProcessStartTurn", "ProcessEndTurn", "ProcessStartBattle", "ProcessEndBattle", "ProcessStartRound", "ProcessEndRound", "ApplySkillCommand", "ApplyCommand", "ProcessBeforeStartTurn" })
                    {
                        var method = procType.GetMethod(hookName, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                        if (method == null)
                        {
                            // Multiple overloads? Pick the one with the right arity
                            var all = procType.GetMethods(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                            foreach (var mm in all)
                            {
                                if (mm.Name == hookName)
                                {
                                    int want = (hookName == "ApplySkillCommand" || hookName == "ApplyCommand" || hookName == "ProcessEndTurn" || hookName == "ProcessStartTurn") ? -1 : 0;
                                    if (want == -1 || mm.GetParameters().Length == want) { method = mm; break; }
                                }
                            }
                        }
                        if (method != null)
                        {
                            try
                            {
                                var postfix = new HarmonyMethod(typeof(RaidAutomationPlugin)
                                    .GetMethod("BattleHook_" + hookName, BindingFlags.Static | BindingFlags.Public));
                                if (postfix.method != null)
                                {
                                    harmony.Patch(method, postfix: postfix);
                                    Logger.LogInfo("Harmony: patched " + hookName);
                                    int argc = method.GetParameters().Length;
                                    lock (_hookPatchLog) { _hookPatchLog.Add(hookName + ":patched(argc=" + argc + ")"); }
                                }
                                else
                                {
                                    Logger.LogWarning("Postfix method BattleHook_" + hookName + " not found");
                                    lock (_hookPatchLog) { _hookPatchLog.Add(hookName + ":no_postfix_method"); }
                                }
                            }
                            catch (Exception pex) { Logger.LogWarning(hookName + " patch: " + pex.Message); lock (_hookPatchLog) { _hookPatchLog.Add(hookName + ":patch_error:" + pex.Message); } }
                        }
                        else
                        {
                            lock (_hookPatchLog) { _hookPatchLog.Add(hookName + ":method_not_found"); }
                        }
                    }
                }

                // Hook MakeNodesFromUnapplyResultSystem.Execute — ECS system
                // that fires whenever an applied effect is unapplied (expired,
                // cleansed, removed). Each Execute iterates the _unapplyEffectResults
                // group containing UnappliedEffectResult records.
                try
                {
                    var unapplyType = FindTypeStatic("ECS.BattleSystems.MakeNodesFromUnapplyResultSystem");
                    if (unapplyType != null)
                    {
                        var execM = unapplyType.GetMethod("Execute", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                        if (execM != null)
                        {
                            var prefix = new HarmonyMethod(typeof(RaidAutomationPlugin)
                                .GetMethod("BattleHook_UnapplyExecute", BindingFlags.Static | BindingFlags.Public));
                            if (prefix.method != null)
                            {
                                // Use PREFIX — postfix sees emptied group since Execute drains it
                                harmony.Patch(execM, prefix: prefix);
                                lock (_hookPatchLog) { _hookPatchLog.Add("UnapplyExecute:patched_prefix"); }
                            }
                        }
                        else { lock (_hookPatchLog) { _hookPatchLog.Add("UnapplyExecute:no_Execute"); } }
                    }
                    else { lock (_hookPatchLog) { _hookPatchLog.Add("UnapplyExecute:type_not_found"); } }
                }
                catch (Exception ex) { lock (_hookPatchLog) { _hookPatchLog.Add("UnapplyExecute:err:" + ex.Message); } }

                // Hook AppliedEffect.set_TurnLeft — catches EVERY duration assignment
                // including natural tick-down (extend processors only cover explicit changes)
                try
                {
                    var aeType = FindTypeStatic("SharedModel.Battle.Core.Skill.AppliedEffect");
                    if (aeType != null)
                    {
                        var setM = aeType.GetMethod("set_TurnLeft", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                        if (setM != null)
                        {
                            var postfix = new HarmonyMethod(typeof(RaidAutomationPlugin)
                                .GetMethod("BattleHook_TurnLeftSet", BindingFlags.Static | BindingFlags.Public));
                            if (postfix.method != null)
                            {
                                harmony.Patch(setM, postfix: postfix);
                                lock (_hookPatchLog) { _hookPatchLog.Add("TurnLeftSet:patched"); }
                            }
                        }
                    }
                }
                catch (Exception ex) { lock (_hookPatchLog) { _hookPatchLog.Add("TurnLeftSet:err:" + ex.Message); } }

                // Re-process the processor list
                foreach (var (typeName, hookSuffix) in new[] {
                    ("SharedModel.Battle.Core.Skill.EffectProcessing.Processors.DamageProcessor", "DamageChange"),
                    ("SharedModel.Battle.Core.Skill.EffectProcessing.Processors.ApplyStatusEffectProcessor", "ApplyStatus"),
                    ("SharedModel.Battle.Core.Skill.EffectProcessing.Processors.RemoveStatusEffectsProcessor", "RemoveStatus"),
                    ("SharedModel.Battle.Core.Skill.EffectProcessing.Processors.ChangeAppliedEffectDurationProcessor", "DurationChange"),
                })
                {
                    try
                    {
                        var t = FindTypeStatic(typeName);
                        if (t == null) { lock (_hookPatchLog) { _hookPatchLog.Add(hookSuffix + ":type_not_found"); } continue; }
                        var procM = t.GetMethod("Process", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                        if (procM == null) { lock (_hookPatchLog) { _hookPatchLog.Add(hookSuffix + ":no_Process"); } continue; }
                        var postfix = new HarmonyMethod(typeof(RaidAutomationPlugin)
                            .GetMethod("BattleHook_" + hookSuffix, BindingFlags.Static | BindingFlags.Public));
                        if (postfix.method == null) { lock (_hookPatchLog) { _hookPatchLog.Add(hookSuffix + ":no_postfix_method"); } continue; }
                        harmony.Patch(procM, postfix: postfix);
                        int argc = procM.GetParameters().Length;
                        lock (_hookPatchLog) { _hookPatchLog.Add(hookSuffix + ":patched(argc=" + argc + ")"); }
                        Logger.LogInfo("Harmony: patched " + hookSuffix);
                    }
                    catch (Exception ex) { lock (_hookPatchLog) { _hookPatchLog.Add(hookSuffix + ":err:" + ex.Message); } }
                }

                Logger.LogInfo("Harmony initialized");
            }
            catch (Exception ex)
            {
                Logger.LogWarning("Harmony init failed: " + ex.Message);
            }

            Logger.LogInfo("HTTP API ready on port " + PORT);
        }

        /// <summary>
        /// Process queued artifact commands from the game's main thread context.
        /// Called from RaidUpdateBehaviour.Update() where game infrastructure is live.
        /// </summary>
        internal static void ProcessArtifactCmds()
        {
            if (ArtifactCmdQueue.IsEmpty) return;

            // Only process one command per frame to avoid lag
            if (!ArtifactCmdQueue.TryDequeue(out var cmd)) return;

            var result = new ArtifactCmdResult();
            try
            {
                // We're on the game's main thread — all game infrastructure is available.
                // Find and invoke the game's own command dispatch.
                var activateCmdType = FindTypeStatic("Client.Model.Gameplay.Artifacts.Commands.ActivateArtifactCmd");
                var deactivateCmdType = FindTypeStatic("Client.Model.Gameplay.Artifacts.Commands.DeactivateArtifactCmd");
                var swapCmdType = FindTypeStatic("Client.Model.Gameplay.Artifacts.Commands.SwapArtifactCmd");

                object gameCmd = null;
                switch (cmd.Action)
                {
                    case "activate":
                        if (activateCmdType != null)
                        {
                            var ctor = activateCmdType.GetConstructor(new[] { typeof(int), typeof(int) });
                            if (ctor != null)
                                gameCmd = ctor.Invoke(new object[] { cmd.HeroId, cmd.ArtifactId });
                        }
                        break;
                    case "deactivate":
                        if (deactivateCmdType != null)
                        {
                            var ctor = deactivateCmdType.GetConstructor(new[] { typeof(int), typeof(int) });
                            if (ctor != null)
                                gameCmd = ctor.Invoke(new object[] { cmd.HeroId, cmd.ArtifactId });
                        }
                        break;
                    case "swap":
                        if (swapCmdType != null)
                        {
                            var ctor = swapCmdType.GetConstructor(new[] { typeof(int), typeof(int), typeof(int), typeof(int) });
                            if (ctor != null)
                                gameCmd = ctor.Invoke(new object[] { cmd.HeroId, cmd.ArtifactOwnerId, cmd.ArtifactFromId, cmd.ArtifactId });
                        }
                        break;
                }

                if (gameCmd == null)
                {
                    result.Error = "Failed to create " + cmd.Action + " command";
                    result.Done = true;
                    ArtifactCmdResults[cmd.Id] = result;
                    return;
                }

                // Call Execute() — from the main thread, the game's infrastructure should be live
                var executeMethod = gameCmd.GetType().GetMethod("Execute",
                    BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.FlattenHierarchy,
                    null, Type.EmptyTypes, null);

                if (executeMethod != null)
                {
                    // Debug: log command state before execute
                    try
                    {
                        var req = gameCmd.GetType().GetProperty("Request",
                            BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.FlattenHierarchy);
                        var failProp = gameCmd.GetType().GetProperty("_failover",
                            BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.FlattenHierarchy);
                        var tagProp = gameCmd.GetType().GetProperty("Tag",
                            BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.FlattenHierarchy);
                        Logger.LogInfo("ArtifactCmd: request=" + (req?.GetValue(gameCmd) != null ? "SET" : "NULL") +
                                       " failover=" + (failProp?.GetValue(gameCmd) != null ? "SET" : "NULL") +
                                       " tag=" + tagProp?.GetValue(gameCmd));
                    }
                    catch (Exception ex) { Logger.LogInfo("ArtifactCmd debug: " + ex.Message); }

                    executeMethod.Invoke(gameCmd, null);
                    result.Ok = true;
                }
                else
                {
                    // Walk hierarchy for Execute
                    var t = gameCmd.GetType();
                    while (t != null)
                    {
                        foreach (var m in t.GetMethods(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly))
                        {
                            if (m.Name == "Execute" && m.GetParameters().Length == 0)
                            {
                                m.Invoke(gameCmd, null);
                                result.Ok = true;
                                goto done;
                            }
                        }
                        t = t.BaseType;
                    }
                    done:
                    if (!result.Ok) result.Error = "Execute method not found";
                }
            }
            catch (TargetInvocationException tex)
            {
                result.Error = (tex.InnerException ?? tex).Message;
                Logger.LogWarning("ArtifactCmd error: " + result.Error);
            }
            catch (Exception ex)
            {
                result.Error = ex.Message;
                Logger.LogWarning("ArtifactCmd error: " + result.Error);
            }

            result.Done = true;
            ArtifactCmdResults[cmd.Id] = result;
        }

        private static Type FindTypeStatic(string fullName)
        {
            foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
            {
                try { var t = asm.GetType(fullName); if (t != null) return t; } catch { }
            }
            return null;
        }

        private void StartHttpServer()
        {
            _running = true;
            _serverThread = new Thread(() =>
            {
                try
                {
                    _listener = new HttpListener();
                    // Loopback only - doesn't require URL ACL / admin elevation.
                    _listener.Prefixes.Add("http://localhost:" + PORT + "/");
                    _listener.Start();
                    Logger.LogInfo("HTTP listener started on port " + PORT);
                    while (_running)
                    {
                        try
                        {
                            var ctx = _listener.GetContext();
                            ThreadPool.QueueUserWorkItem(_ => HandleRequest(ctx));
                        }
                        catch (HttpListenerException) { if (!_running) break; }
                        catch (Exception ex) { Logger.LogError("HTTP: " + ex.Message); }
                    }
                }
                catch (Exception ex) { Logger.LogError("Server: " + ex); }
            }) { IsBackground = true };
            _serverThread.Start();
        }

        private void HandleRequest(HttpListenerContext ctx)
        {
            string path = ctx.Request.Url.AbsolutePath;
            string query = ctx.Request.Url.Query;
            string response;
            try
            {
                response = path switch
                {
                    "/status" => RunOnMainThread(() => GetStatus()),
                    "/all-heroes" => RunOnMainThread(() => GetAllHeroes(QP(query, "offset"), QP(query, "limit"), QP(query, "min_grade")), 60000),
                    "/buttons" => RunOnMainThread(() => ListButtons()),
                    "/click" => RunOnMainThread(() => ClickByPath(QP(query, "path"))),
                    "/dismiss" => RunOnMainThread(() => DismissOverlays()),
                    "/account" => RunOnMainThread(() => GetAccountData()),
                    "/skill-data" => RunOnMainThread(() => GetSkillData(QP(query, "hero_id"), QP(query, "min_grade")), 30000),
                    "/enemy-skills" => RunOnMainThread(() => GetEnemySkills(QP(query, "type_id")), 30000),
                    "/hook-diag" => GetHookDiag(),
                    "/hero-computed-stats" => RunOnMainThread(() => GetHeroComputedStats(QP(query, "min_grade")), 60000),
                    "/all-artifacts" => RunOnMainThread(() => GetAllArtifacts(QP(query, "offset"), QP(query, "limit")), 60000),
                    "/types" => RunOnMainThread(() => SearchTypes(QP(query, "q"))),
                    "/props" => RunOnMainThread(() => InspectType(QP(query, "type"))),
                    "/server-info" => RunOnMainThread(() => GetServerInfo()),
                    "/equip" => RunOnMainThread(() => EquipArtifact(QP(query, "hero_id"), QP(query, "artifact_id")), 30000),
                    "/unequip" => RunOnMainThread(() => UnequipArtifact(QP(query, "hero_id"), QP(query, "artifact_id")), 30000),
                    "/swap" => RunOnMainThread(() => SwapArtifact(QP(query, "hero_id"), QP(query, "from_id"), QP(query, "to_id"), QP(query, "owner_id")), 30000),
                    "/bulk-equip" => RunOnMainThread(() => BulkEquipArtifacts(QP(query, "hero_id"), QP(query, "artifacts")), 30000),
                    "/presets" => RunOnMainThread(() => GetPresets(), 30000),
                    "/remove-preset" => RunOnMainThread(() => RemovePreset(QP(query, "id")), 30000),
                    "/save-preset" => RunOnMainThread(() => SavePreset(QP(query, "name"), QP(query, "heroes"), QP(query, "type")), 30000),
                    "/update-preset" => RunOnMainThread(() => UpdatePreset(QP(query, "id"), QP(query, "priorities"), QP(query, "starters")), 30000),
                    "/preset-schema" => RunOnMainThread(() => PresetSchema(QP(query, "id")), 15000),
                    "/set-preset-team" => RunOnMainThread(() => SetPresetTeam(QP(query, "id"), QP(query, "heroes")), 30000),
                    "/skill-texts" => RunOnMainThread(() => GetSkillTexts(QP(query, "hero_id"), QP(query, "min_grade")), 60000),
                    "/mastery-data" => RunOnMainThread(() => GetMasteryData(QP(query, "hero_id"))),
                    "/open-mastery" => RunOnMainThread(() => OpenMastery(QP(query, "hero_id"), QP(query, "mastery_id")), 30000),
                    "/reset-masteries" => RunOnMainThread(() => ResetMasteries(QP(query, "hero_id")), 30000),
                    "/battle-state" => RunOnMainThread(() => GetBattleState(), 15000),
                    "/battle-log" => GetBattleLogFull(QP(query, "clear") == "1"),
                    "/tick-log" => GetTickLog(QP(query, "clear") == "1"),
                    "/navigate" => RunOnMainThread(() => NavigateTo(QP(query, "target"))),
                    "/open-dungeon" => RunOnMainThread(() => OpenDungeon(QP(query, "type"), QP(query, "method"))),
                    "/context-call" => RunOnMainThread(() => CallOnViewContext(QP(query, "path"), QP(query, "method"), QP(query, "arg"))),
                    "/resources" => RunOnMainThread(() => GetResources()),
                    "/all-resources" => RunOnMainThread(() => GetAllResources()),
                    "/shards" => RunOnMainThread(() => GetShards(QP(query, "debug") == "1")),
                    "/explore-uw" => RunOnMainThread(() => ExploreUserWrapper(QP(query, "path"))),
                    "/explore-sd" => RunOnMainThread(() => ExploreStaticData(QP(query, "path"))),
                    "/dungeon-drops" => RunOnMainThread(() => GetDungeonDrops()),
                    "/view-contexts" => RunOnMainThread(() => GetViewContexts(QP(query, "path"))),
                    "/invoke-context" => RunOnMainThread(() => InvokeOnContext(QP(query, "type"), QP(query, "method"))),
                    "/list-static-methods" => ListStaticMethods(QP(query, "type"), QP(query, "filter")),
                    "/list-active" => RunOnMainThread(() => ListActive(QP(query, "path"), QP(query, "depth"), QP(query, "filter"))),
                    "/set-scroll" => RunOnMainThread(() => SetScroll(QP(query, "path"), QP(query, "v"), QP(query, "h"))),
                    "/list-components" => RunOnMainThread(() => ListComponents(QP(query, "path"))),
                    "/get-text" => RunOnMainThread(() => GetText(QP(query, "path"))),
                    _ => "{\"endpoints\":[\"/status\",\"/all-heroes\",\"/battle-state\",\"/navigate?target=cb\",\"/context-call?path=X&method=Y\",\"/invoke-context?type=X&method=Y\",\"/resources\",\"/view-contexts\",\"/mastery-data?hero_id=X\",\"/open-mastery?hero_id=X&mastery_id=Y\",\"/reset-masteries?hero_id=X\"]}"
                };
            }
            catch (Exception ex)
            {
                response = "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
            byte[] buf = Encoding.UTF8.GetBytes(response);
            ctx.Response.ContentType = "application/json";
            ctx.Response.ContentLength64 = buf.Length;
            try { ctx.Response.OutputStream.Write(buf, 0, buf.Length); ctx.Response.Close(); } catch { }
        }

        private T RunOnMainThread<T>(Func<T> func, int timeoutMs = 15000)
        {
            T result = default;
            Exception error = null;
            var done = new ManualResetEventSlim(false);
            MainThreadQueue.Enqueue(() =>
            {
                try { result = func(); }
                catch (Exception ex) { error = ex; }
                finally { done.Set(); }
            });
            if (!done.Wait(timeoutMs)) throw new TimeoutException("Main thread timeout");
            if (error != null) throw error;
            return result;
        }

        internal static void ProcessQueue()
        {
            while (MainThreadQueue.TryDequeue(out var action))
            {
                try { action(); }
                catch (Exception ex) { Logger.LogError("Queue: " + ex); }
            }
        }

        // =====================================================
        // Reflection helpers — navigate game objects dynamically
        // =====================================================

        private object GetAppModel()
        {
            if (!_reflectionCached)
            {
                _appModelType = FindType("Client.Model.AppModel");
                if (_appModelType != null)
                    _instanceProp = _appModelType.GetProperty("Instance",
                        BindingFlags.Public | BindingFlags.Static | BindingFlags.FlattenHierarchy);
                _reflectionCached = true;
            }
            return _instanceProp?.GetValue(null);
        }

        private object GetUserWrapper()
        {
            var am = GetAppModel();
            if (am == null) return null;
            // Search for UserWrapper property
            foreach (var prop in _appModelType.GetProperties(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic))
            {
                if (prop.PropertyType.Name.Contains("UserWrapper") || prop.PropertyType.Name.Contains("IUserWrapper"))
                {
                    try { return prop.GetValue(am); } catch { }
                }
            }
            return null;
        }

        private static object Prop(object obj, string name)
        {
            if (obj == null) return null;
            var t = obj.GetType();
            // Try property first (standard managed access).
            var p = t.GetProperty(name);
            if (p != null)
            {
                try { return p.GetValue(obj); } catch { }
            }
            // Fallback to field — IL2CPP types like DamageResult expose Amount
            // as a public field, not a property, so GetProperty alone misses it.
            var f = t.GetField(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            if (f != null)
            {
                try { return f.GetValue(obj); } catch { }
            }
            return null;
        }

        private static int IntProp(object obj, string name)
        {
            var v = Prop(obj, name);
            if (v is int i) return i;
            if (v != null) try { return Convert.ToInt32(v); } catch { }
            return 0;
        }

        private static long LongProp(object obj, string name)
        {
            var v = Prop(obj, name);
            if (v is long l) return l;
            if (v != null) try { return Convert.ToInt64(v); } catch { }
            return 0;
        }

        private static double DblProp(object obj, string name)
        {
            var v = Prop(obj, name);
            if (v is double d) return d;
            if (v is float f) return f;
            if (v != null) try { return Convert.ToDouble(v); } catch { }
            return 0;
        }

        private static string StrProp(object obj, string name)
        {
            var v = Prop(obj, name);
            return v?.ToString() ?? "";
        }

        // Iterate a dictionary's values via reflection
        private static IEnumerable<object> DictValues(object dict)
        {
            if (dict == null) yield break;
            var values = Prop(dict, "Values");
            if (values == null) yield break;
            var getEnum = values.GetType().GetMethod("GetEnumerator");
            if (getEnum == null) yield break;
            var enumerator = getEnum.Invoke(values, null);
            var enumType = enumerator.GetType();
            var moveNext = enumType.GetMethod("MoveNext");
            var current = enumType.GetProperty("Current");
            while ((bool)moveNext.Invoke(enumerator, null))
            {
                yield return current.GetValue(enumerator);
            }
        }

        // Iterate a list via reflection
        private static IEnumerable<object> ListItems(object list)
        {
            if (list == null) yield break;
            int count = IntProp(list, "Count");
            var indexer = list.GetType().GetProperty("Item");
            if (indexer == null) yield break;
            for (int i = 0; i < count; i++)
            {
                object item = null;
                try { item = indexer.GetValue(list, new object[] { i }); } catch { }
                if (item != null) yield return item;
            }
        }

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
                            // Also output ascend bonus
                            var ascBonus = Prop(setup, "AscendBonus");
                            if (ascBonus != null)
                                AppendBonus(sb, ascBonus, "ascend_bonus");
                        }
                    }
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
                                    sb.Append(",\"blessing_bonus\":{");
                                    AppendFixed(sb, blessStats, "Health", "HP");
                                    sb.Append(","); AppendFixed(sb, blessStats, "Attack", "ATK");
                                    sb.Append(","); AppendFixed(sb, blessStats, "Defence", "DEF");
                                    sb.Append("}");
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
                                    sb.Append(",\"empower_bonus\":{");
                                    AppendFixed(sb, empStats, "Health", "HP");
                                    sb.Append(","); AppendFixed(sb, empStats, "Attack", "ATK");
                                    sb.Append(","); AppendFixed(sb, empStats, "Defence", "DEF");
                                    sb.Append("}");
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

                                // Always try constructing from known league value
                                if (arenaEnumType != null)
                                {
                                    // Get league from account data endpoint (we know it's 22 = GoldII)
                                    int knownLeague = 22;
                                    try
                                    {
                                        // Read from the account data we already parse
                                        var arenaData = Prop(arenaWrapper, "ArenaData");
                                        if (arenaData != null)
                                        {
                                            int league = IntProp(arenaData, "LeagueId");
                                            if (league > 0) knownLeague = league;
                                        }
                                    }
                                    catch { }

                                    // Construct the enum — IL2CPP enums are just ints underneath
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
                                    sb.Append(",\"arena_bonus\":{");
                                    AppendFixed(sb, arenaStats, "Health", "HP");
                                    sb.Append(","); AppendFixed(sb, arenaStats, "Attack", "ATK");
                                    sb.Append(","); AppendFixed(sb, arenaStats, "Defence", "DEF");
                                    sb.Append(","); AppendFixed(sb, arenaStats, "Speed", "SPD");
                                    sb.Append("}");
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
                                                sb.Append(",\"great_hall_bonus\":{");
                                                AppendFixed(sb, buildStats, "Health", "HP");
                                                sb.Append(","); AppendFixed(sb, buildStats, "Attack", "ATK");
                                                sb.Append(","); AppendFixed(sb, buildStats, "Defence", "DEF");
                                                sb.Append(","); AppendFixed(sb, buildStats, "Accuracy", "ACC");
                                                sb.Append(","); AppendFixed(sb, buildStats, "Resistance", "RES");
                                                sb.Append(","); AppendFixed(sb, buildStats, "CriticalDamage", "CD");
                                                sb.Append("}");
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

                        // CalcRelicsBonus
                        try
                        {
                            var relicSetupType = FindType("SharedModel.Battle.Core.Setup.RelicSetup");
                            if (relicSetupType == null)
                                relicSetupType = FindType("SharedModel.Meta.Relics.RelicSetup");

                            if (relicSetupType != null)
                            {
                                var uw5 = GetUserWrapper();
                                // Get Relics list via the public property on RelicsWrapper
                                try
                                {
                                    var relicWrapper = Prop(uw5, "Relics");
                                    if (relicWrapper != null)
                                    {
                                        // RelicsWrapperReadonly has a public List<Relic> Relics property
                                        var relicsList = Prop(relicWrapper, "Relics");
                                        if (relicsList != null)
                                        {
                                            var toSetupsMethod = relicSetupType.GetMethod("ToRelicSetups");
                                            if (toSetupsMethod != null)
                                            {
                                                var setups = toSetupsMethod.Invoke(null, new object[] { relicsList });
                                                if (setups != null)
                                                {
                                                    var formType4 = FindType("SharedModel.Meta.Heroes.HeroMetamorphForm");
                                                    object form4 = 0;
                                                    if (formType4 != null) try { form4 = Enum.ToObject(formType4, 0); } catch { }

                                                    var relicMethod = heroExtType.GetMethod("CalcRelicsBonus");
                                                    var relicStats = relicMethod.Invoke(null, new object[] { hero, setups, form4 });
                                                    if (relicStats != null)
                                                    {
                                                        sb.Append(",\"relic_bonus\":{");
                                                        AppendFixed(sb, relicStats, "Health", "HP");
                                                        sb.Append(","); AppendFixed(sb, relicStats, "Attack", "ATK");
                                                        sb.Append(","); AppendFixed(sb, relicStats, "Defence", "DEF");
                                                        sb.Append("}");
                                                    }
                                                }
                                            }
                                        }
                                        else
                                        {
                                            sb.Append(",\"_relic_err\":\"Relics list null\"");
                                        }
                                    }
                                }
                                catch (Exception rex) { sb.Append(",\"_relic_err\":\"" + Esc(rex.InnerException != null ? rex.InnerException.Message : rex.Message) + "\""); }
                            }
                        }
                        catch (Exception ex) { sb.Append(",\"_relic_err\":\"" + Esc(ex.Message) + "\""); }
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

        // =====================================================
        // API: /status, /buttons, /click, /dismiss, /types
        // =====================================================

        private string GetServerInfo()
        {
            var sb = new StringBuilder();
            sb.Append("{");
            var am = GetAppModel();
            if (am == null) return "{\"error\":\"AppModel null\"}";

            // Use Prop() which works for IL2CPP interop properties
            // Server URL from _configuration.Server
            try
            {
                var config = Prop(am, "_configuration");
                if (config == null)
                {
                    // Try scanning all properties for BuildConfiguration type
                    foreach (var p in am.GetType().GetProperties(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic))
                    {
                        if (p.PropertyType.Name.Contains("BuildConfiguration"))
                        {
                            try { config = p.GetValue(am); break; } catch { }
                        }
                    }
                }
                if (config != null)
                {
                    sb.Append("\"server\":\"" + Esc(StrProp(config, "Server")) + "\"");
                    sb.Append(",\"sandbox\":" + (Prop(config, "IsSandbox")?.ToString()?.ToLower() ?? "null"));
                    sb.Append(",\"config_type\":\"" + Esc(config.GetType().Name) + "\"");
                }
                else
                {
                    sb.Append("\"server\":null");
                }
            }
            catch (Exception ex) { sb.Append("\"server_err\":\"" + Esc(ex.Message) + "\""); }

            // Session + CmdQueue via Prop()
            try
            {
                var cs = Prop(am, "_commandsSession");
                if (cs == null) cs = Prop(am, "CommandsSession");
                if (cs != null)
                {
                    sb.Append(",\"session_id\":" + IntProp(cs, "Id"));
                    sb.Append(",\"session_type\":\"" + Esc(cs.GetType().Name) + "\"");
                }
                else
                {
                    sb.Append(",\"session\":null");
                    // List ALL property names for debugging
                    var propNames = am.GetType().GetProperties(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
                        .Select(p => p.Name).Take(30).ToArray();
                    sb.Append(",\"am_props\":[" + string.Join(",", propNames.Select(n => "\"" + n + "\"")) + "]");
                }
            }
            catch (Exception ex) { sb.Append(",\"session_err\":\"" + Esc(ex.Message) + "\""); }

            // CmdQueue
            try
            {
                var queue = Prop(am, "CmdQueue");
                if (queue != null)
                    sb.Append(",\"queue_type\":\"" + Esc(queue.GetType().Name) + "\"");
            }
            catch { }

            // User ID
            try
            {
                var uw = GetUserWrapper();
                if (uw != null)
                {
                    long userId = LongProp(Prop(uw, "Account"), "Id");
                    sb.Append(",\"user_id\":" + userId);
                }
            }
            catch { }

            sb.Append("}");
            return sb.ToString();
        }

        private string GetStatus()
        {
            var scene = UnityEngine.SceneManagement.SceneManager.GetActiveScene();
            var uw = GetUserWrapper();
            return "{\"mod\":\"RaidAutomation\",\"version\":\"2.0-bepinex\"," +
                   "\"scene\":\"" + Esc(scene.name) + "\"," +
                   "\"logged_in\":" + (uw != null ? "true" : "false") + "," +
                   "\"unity\":\"" + Application.unityVersion + "\"}";
        }

        private string ListButtons()
        {
            var all = UnityEngine.Object.FindObjectsOfType<UnityEngine.UI.Button>();
            var sb = new StringBuilder();
            sb.Append("{\"count\":" + all.Length + ",\"buttons\":[");
            int n = 0;
            foreach (var btn in all)
            {
                if (!btn.gameObject.activeInHierarchy || !btn.interactable) continue;
                if (n > 0) sb.Append(",");
                sb.Append("{\"path\":\"" + Esc(GetPath(btn.transform)) + "\"}");
                if (++n >= 200) break;
            }
            sb.Append("]}");
            return sb.ToString();
        }

        private string ClickByPath(string objPath)
        {
            if (string.IsNullOrEmpty(objPath)) return "{\"error\":\"path required\"}";
            var go = GameObject.Find(objPath);
            if (go == null) return "{\"error\":\"not found\"}";
            var btn = go.GetComponent<UnityEngine.UI.Button>();
            if (btn != null) btn.onClick.Invoke();
            var ped = new UnityEngine.EventSystems.PointerEventData(
                UnityEngine.EventSystems.EventSystem.current);
            ped.button = UnityEngine.EventSystems.PointerEventData.InputButton.Left;
            UnityEngine.EventSystems.ExecuteEvents.Execute(go, ped,
                UnityEngine.EventSystems.ExecuteEvents.pointerClickHandler);
            UnityEngine.EventSystems.ExecuteEvents.Execute(go, ped,
                UnityEngine.EventSystems.ExecuteEvents.submitHandler);
            return "{\"clicked\":\"" + Esc(objPath) + "\"}";
        }

        private string DismissOverlays()
        {
            int dismissed = 0;
            var parent = GameObject.Find("UIManager/Canvas (Ui Root)/OverlayDialogs");
            if (parent != null)
            {
                for (int i = parent.transform.childCount - 1; i >= 0; i--)
                {
                    var child = parent.transform.GetChild(i).gameObject;
                    if (child.activeSelf && child.name.StartsWith("[OV]"))
                    {
                        UnityEngine.Object.Destroy(child);
                        dismissed++;
                    }
                }
            }
            return "{\"dismissed\":" + dismissed + "}";
        }

        private string SearchTypes(string query)
        {
            if (string.IsNullOrEmpty(query)) query = "AppModel";
            var sb = new StringBuilder();
            sb.Append("{\"types\":[");
            int count = 0;
            foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
            {
                try
                {
                    foreach (var type in asm.GetTypes())
                    {
                        if (type.FullName != null && type.FullName.Contains(query, StringComparison.OrdinalIgnoreCase))
                        {
                            if (count > 0) sb.Append(",");
                            sb.Append("{\"name\":\"" + Esc(type.FullName) + "\",\"asm\":\"" + Esc(asm.GetName().Name) + "\"}");
                            if (++count >= 50) break;
                        }
                    }
                }
                catch { }
                if (count >= 50) break;
            }
            sb.Append("]}");
            return sb.ToString();
        }

        private string InspectType(string typeName)
        {
            if (string.IsNullOrEmpty(typeName)) return "{\"error\":\"type param required\"}";
            var type = FindType(typeName);
            if (type == null) return "{\"error\":\"type not found\"}";
            var sb = new StringBuilder();
            sb.Append("{\"type\":\"" + Esc(type.FullName) + "\",\"props\":[");
            int pc = 0;
            foreach (var p in type.GetProperties())
            {
                if (pc > 0) sb.Append(",");
                sb.Append("\"" + Esc(p.Name + ":" + p.PropertyType.Name) + "\"");
                if (++pc >= 80) break;
            }
            sb.Append("],\"methods\":[");
            int mc = 0;
            foreach (var m in type.GetMethods(BindingFlags.Public | BindingFlags.Instance | BindingFlags.DeclaredOnly))
            {
                if (mc > 0) sb.Append(",");
                sb.Append("\"" + Esc(m.Name) + "\"");
                if (++mc >= 40) break;
            }
            sb.Append("]}");
            return sb.ToString();
        }

        // =====================================================
        // Utilities
        // =====================================================

        private void AppendDictOfDicts(StringBuilder sb, object outerDict)
        {
            sb.Append("{");
            var dictType = outerDict.GetType();
            var getEnumerator = dictType.GetMethod("GetEnumerator");
            var enumerator = getEnumerator.Invoke(outerDict, null);
            var enumType = enumerator.GetType();
            var moveNext = enumType.GetMethod("MoveNext");
            var currentProp = enumType.GetProperty("Current");
            int outer = 0;
            while ((bool)moveNext.Invoke(enumerator, null))
            {
                var kvp = currentProp.GetValue(enumerator);
                var key = Prop(kvp, "Key");
                var val = Prop(kvp, "Value");
                if (outer > 0) sb.Append(",");
                sb.Append("\"" + Convert.ToInt32(key) + "\":{");
                // Inner dict
                if (val != null)
                {
                    var innerEnum = val.GetType().GetMethod("GetEnumerator").Invoke(val, null);
                    var innerType = innerEnum.GetType();
                    var innerMoveNext = innerType.GetMethod("MoveNext");
                    var innerCurrent = innerType.GetProperty("Current");
                    int inner = 0;
                    while ((bool)innerMoveNext.Invoke(innerEnum, null))
                    {
                        var ikvp = innerCurrent.GetValue(innerEnum);
                        var ikey = Prop(ikvp, "Key");
                        var ival = Prop(ikvp, "Value");
                        if (inner > 0) sb.Append(",");
                        sb.Append("\"" + Convert.ToInt32(ikey) + "\":" + Convert.ToInt32(ival));
                        inner++;
                    }
                }
                sb.Append("}");
                outer++;
            }
            sb.Append("}");
        }

        // =====================================================
        // API: /equip, /unequip, /swap, /bulk-equip
        // Artifact management via game command system
        // =====================================================

        /// <summary>
        /// Queue an artifact command for execution from the game's main thread.
        /// Waits up to 5 seconds for the result.
        /// </summary>
        private string QueueArtifactCmd(string action, int heroId, int artifactId,
                                         int fromId = 0, int ownerId = 0)
        {
            int cmdId = Interlocked.Increment(ref _cmdIdCounter);
            ArtifactCmdQueue.Enqueue(new ArtifactCmd
            {
                Id = cmdId,
                Action = action,
                HeroId = heroId,
                ArtifactId = artifactId,
                ArtifactFromId = fromId,
                ArtifactOwnerId = ownerId
            });

            // Wait for result (processed on next Update frame)
            for (int i = 0; i < 50; i++) // 50 × 100ms = 5s timeout
            {
                Thread.Sleep(100);
                if (ArtifactCmdResults.TryRemove(cmdId, out var result))
                {
                    if (result.Ok)
                        return "{\"ok\":true,\"action\":\"" + action + "\",\"synced\":true}";
                    else
                        return "{\"error\":\"" + Esc(result.Error) + "\",\"action\":\"" + action + "\"}";
                }
            }
            return "{\"error\":\"timeout waiting for command\",\"action\":\"" + action + "\"}";
        }

        private string EquipArtifact(string heroIdStr, string artifactIdStr)
        {
            if (string.IsNullOrEmpty(heroIdStr) || string.IsNullOrEmpty(artifactIdStr))
                return "{\"error\":\"hero_id and artifact_id required\"}";

            int heroId, artifactId;
            if (!int.TryParse(heroIdStr, out heroId) || !int.TryParse(artifactIdStr, out artifactId))
                return "{\"error\":\"invalid hero_id or artifact_id\"}";

            var uw = GetUserWrapper();
            if (uw == null) return "{\"error\":\"Not logged in\"}";

            var equipment = Prop(uw, "Artifacts");
            if (equipment == null) return "{\"error\":\"EquipmentWrapper null\"}";

            // Get the hero and artifact objects
            var heroes = Prop(uw, "Heroes");
            var heroData = Prop(heroes, "HeroData");
            var heroDict = Prop(heroData, "HeroById");

            // Get hero object
            object hero = null;
            try
            {
                var containsKey = heroDict.GetType().GetMethod("ContainsKey");
                if (containsKey != null && (bool)containsKey.Invoke(heroDict, new object[] { heroId }))
                {
                    hero = heroDict.GetType().GetProperty("Item")?.GetValue(heroDict, new object[] { heroId });
                }
            }
            catch { }
            if (hero == null) return "{\"error\":\"hero " + heroId + " not found\"}";

            // Get artifact object via One(id)
            var oneMethod = equipment.GetType().GetMethod("One");
            if (oneMethod == null) return "{\"error\":\"One method not found\"}";
            object artifact = null;
            try { artifact = oneMethod.Invoke(equipment, new object[] { artifactId }); }
            catch { }
            if (artifact == null) return "{\"error\":\"artifact " + artifactId + " not found\"}";

            int artKind = IntProp(artifact, "KindId");
            int existingArtId = GetEquippedArtifactId(equipment, heroId, artKind);

            if (existingArtId == artifactId)
                return "{\"ok\":true,\"msg\":\"already equipped\"}";

            // We're on the main thread via RunOnMainThread — create and execute command directly.
            // The command's Execute() handles BOTH local PreEdit AND server HTTP sync.
            var sb = new StringBuilder();
            sb.Append("{\"hero_id\":" + heroId + ",\"artifact_id\":" + artifactId + ",\"slot\":" + artKind);

            try
            {
                object gameCmd = null;
                int artOwner = GetArtifactOwner(equipment, artifactId);

                // Determine the right command:
                // - SwapArtifactCmd: if target slot occupied OR artifact is on another hero
                // - ActivateArtifactCmd: only if target slot empty AND artifact is in vault
                bool needsSwap = (existingArtId > 0 && existingArtId != artifactId) ||
                                  (artOwner > 0 && artOwner != heroId);

                if (needsSwap)
                {
                    // SwapArtifactCmd(heroId, ownerHeroId, fromArtId, toArtId)
                    int ownerId = artOwner > 0 ? artOwner : heroId;
                    int fromId = existingArtId > 0 ? existingArtId : 0;

                    // If slot is empty but artifact is on another hero, we still need swap
                    // The "from" artifact is what's currently in our target slot (0 if empty)
                    // SwapArtifactCmd handles: take toArtId from ownerId, put on heroId, return fromId to ownerId
                    if (fromId <= 0)
                    {
                        // No artifact in target slot — use the owner hero's artifact in same slot
                        // Actually, SwapArtifactCmd needs a valid fromId.
                        // If slot is empty, first unequip from owner, then activate on target.
                        // Unequip from owner:
                        var deactType = FindType("Client.Model.Gameplay.Artifacts.Commands.DeactivateArtifactCmd");
                        if (deactType != null)
                        {
                            var dctor = deactType.GetConstructor(new[] { typeof(int), typeof(int) });
                            if (dctor != null)
                            {
                                var deactCmd = dctor.Invoke(new object[] { ownerId, artifactId });
                                InvokeExecute(deactCmd);
                                sb.Append(",\"unequipped_from\":" + ownerId);
                            }
                        }
                        // Now activate on target (artifact is in vault)
                        var actType = FindType("Client.Model.Gameplay.Artifacts.Commands.ActivateArtifactCmd");
                        if (actType != null)
                        {
                            var actor = actType.GetConstructor(new[] { typeof(int), typeof(int) });
                            if (actor != null)
                                gameCmd = actor.Invoke(new object[] { heroId, artifactId });
                        }
                        sb.Append(",\"action\":\"unequip_then_activate\"");
                    }
                    else
                    {
                        var cmdType = FindType("Client.Model.Gameplay.Artifacts.Commands.SwapArtifactCmd");
                        if (cmdType != null)
                        {
                            var ctor = cmdType.GetConstructor(new[] { typeof(int), typeof(int), typeof(int), typeof(int) });
                            if (ctor != null)
                                gameCmd = ctor.Invoke(new object[] { heroId, ownerId, fromId, artifactId });
                        }
                        sb.Append(",\"action\":\"swap\",\"replaced\":" + fromId);
                    }
                }
                else
                {
                    // Pure activate: artifact in vault, slot empty
                    var cmdType = FindType("Client.Model.Gameplay.Artifacts.Commands.ActivateArtifactCmd");
                    if (cmdType != null)
                    {
                        var ctor = cmdType.GetConstructor(new[] { typeof(int), typeof(int) });
                        if (ctor != null)
                            gameCmd = ctor.Invoke(new object[] { heroId, artifactId });
                    }
                    sb.Append(",\"action\":\"activate\"");
                }

                if (gameCmd == null)
                {
                    sb.Append(",\"error\":\"command creation failed\"}");
                    return sb.ToString();
                }

                // Log command state before execute
                try
                {
                    var reqProp = gameCmd.GetType().GetProperty("Request",
                        BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.FlattenHierarchy);
                    var failProp = gameCmd.GetType().GetProperty("_failover",
                        BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.FlattenHierarchy);
                    var tagProp = gameCmd.GetType().GetProperty("Tag",
                        BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.FlattenHierarchy);
                    var reqSet = reqProp?.GetValue(gameCmd) != null ? "SET" : "NULL";
                    var failSet = failProp?.GetValue(gameCmd) != null ? "SET" : "NULL";
                    var tagVal = tagProp?.GetValue(gameCmd)?.ToString() ?? "null";
                    Logger.LogInfo("EQUIP cmd=" + gameCmd.GetType().Name + " req=" + reqSet +
                                   " fail=" + failSet + " tag=" + tagVal);
                }
                catch { }

                // Check if hero is locked (arena defense, siege, etc.)
                try
                {
                    var heroObj = Prop(Prop(Prop(GetUserWrapper(), "Heroes"), "HeroData"), "HeroById");
                    if (heroObj != null)
                    {
                        var containsKey = heroObj.GetType().GetMethod("ContainsKey");
                        if (containsKey != null && (bool)containsKey.Invoke(heroObj, new object[] { heroId }))
                        {
                            var h = heroObj.GetType().GetProperty("Item")?.GetValue(heroObj, new object[] { heroId });
                            if (h != null)
                            {
                                var lockedProp = h.GetType().GetProperty("Locked");
                                if (lockedProp != null)
                                {
                                    bool locked = (bool)lockedProp.GetValue(h);
                                    if (locked)
                                        sb.Append(",\"hero_locked\":true");
                                }
                            }
                        }
                    }
                }
                catch { }

                // Add IfError callback to catch server-side rejection
                try
                {
                    var ifErrorMethod = gameCmd.GetType().GetMethod("IfError",
                        BindingFlags.Instance | BindingFlags.Public | BindingFlags.FlattenHierarchy,
                        null, new[] { typeof(Action) }, null);
                    if (ifErrorMethod != null)
                    {
                        Action errorCallback = () =>
                        {
                            Logger.LogWarning("EQUIP SERVER REJECTED for hero " + heroId + " art " + artifactId);
                        };
                        ifErrorMethod.Invoke(gameCmd, new object[] { errorCallback });
                    }
                }
                catch { }

                // Find and call Execute()
                var t = gameCmd.GetType();
                while (t != null)
                {
                    foreach (var m in t.GetMethods(BindingFlags.Instance | BindingFlags.Public |
                                                    BindingFlags.NonPublic | BindingFlags.DeclaredOnly))
                    {
                        if (m.Name == "Execute" && m.GetParameters().Length == 0)
                        {
                            m.Invoke(gameCmd, null);
                            sb.Append(",\"ok\":true}");
                            return sb.ToString();
                        }
                    }
                    t = t.BaseType;
                }
                sb.Append(",\"error\":\"Execute not found\"}");
            }
            catch (TargetInvocationException tex)
            {
                sb.Append(",\"error\":\"" + Esc((tex.InnerException ?? tex).Message) + "\"}");
            }
            catch (Exception ex)
            {
                sb.Append(",\"error\":\"" + Esc(ex.Message) + "\"}");
            }
            return sb.ToString();
        }

        private string UnequipArtifact(string heroIdStr, string artifactIdStr)
        {
            if (string.IsNullOrEmpty(heroIdStr) || string.IsNullOrEmpty(artifactIdStr))
                return "{\"error\":\"hero_id and artifact_id required\"}";

            int heroId, artifactId;
            if (!int.TryParse(heroIdStr, out heroId) || !int.TryParse(artifactIdStr, out artifactId))
                return "{\"error\":\"invalid hero_id or artifact_id\"}";

            // Use DeactivateArtifactCmd — handles local change + server sync
            var cmdType = FindType("Client.Model.Gameplay.Artifacts.Commands.DeactivateArtifactCmd");
            if (cmdType == null) return "{\"error\":\"DeactivateArtifactCmd type not found\"}";

            var ctor = cmdType.GetConstructor(new[] { typeof(int), typeof(int) });
            if (ctor == null) return "{\"error\":\"DeactivateArtifactCmd ctor not found\"}";

            try
            {
                var cmd = ctor.Invoke(new object[] { heroId, artifactId });
                InvokeExecute(cmd);
                return "{\"ok\":true,\"action\":\"deactivate\",\"hero_id\":" + heroId +
                       ",\"artifact_id\":" + artifactId + "}";
            }
            catch (TargetInvocationException tex)
            {
                return "{\"error\":\"" + Esc((tex.InnerException ?? tex).Message) + "\"}";
            }
        }

        private string SwapArtifact(string heroIdStr, string fromIdStr, string toIdStr, string ownerIdStr)
        {
            if (string.IsNullOrEmpty(heroIdStr) || string.IsNullOrEmpty(fromIdStr) || string.IsNullOrEmpty(toIdStr))
                return "{\"error\":\"hero_id, from_id, and to_id required\"}";

            int heroId, fromId, toId, ownerId;
            if (!int.TryParse(heroIdStr, out heroId) || !int.TryParse(fromIdStr, out fromId) || !int.TryParse(toIdStr, out toId))
                return "{\"error\":\"invalid parameters\"}";

            // Owner defaults to heroId if not specified (artifact coming from vault)
            if (string.IsNullOrEmpty(ownerIdStr) || !int.TryParse(ownerIdStr, out ownerId))
                ownerId = heroId;

            return DoSwap(heroId, ownerId, fromId, toId);
        }

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

                                        // StarterSkillId for this round
                                        try
                                        {
                                            var rStarter = Prop(seq, "StarterSkillId");
                                            if (rStarter != null)
                                            {
                                                var hasVal = Prop(rStarter, "HasValue");
                                                if (hasVal != null && (bool)hasVal)
                                                {
                                                    var val = Prop(rStarter, "Value");
                                                    if (val != null)
                                                        sb.Append("\"starter\":" + Convert.ToInt32(val));
                                                }
                                            }
                                        }
                                        catch { }

                                        // StarterSkillIds list
                                        var rStarterIds = Prop(seq, "StarterSkillIds");
                                        if (rStarterIds != null)
                                        {
                                            sb.Append(",\"starter_ids\":[");
                                            int sti = 0;
                                            foreach (var sid in ListItems(rStarterIds))
                                            {
                                                if (sti > 0) sb.Append(",");
                                                try { sb.Append(Convert.ToInt32(sid)); } catch { }
                                                sti++;
                                            }
                                            sb.Append("]");
                                        }

                                        // PriorityBySkillId for this round
                                        var rPrios = Prop(seq, "PriorityBySkillId");
                                        if (rPrios != null)
                                        {
                                            sb.Append(",\"priorities\":{");
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

        // =====================================================
        // API: /battle-state — live battle snapshot
        // =====================================================

        // =====================================================
        // Harmony postfix methods — called by patched game methods
        // =====================================================

        public static void ArtifactBonusDeserializePostfix()
        {
            // Stub — the artifact stat capture is handled elsewhere
        }

        public static void BattleProcessorCtorPostfix(object __instance) { }
        public static void BattleProcessorApplyCommandPostfix(object __instance) { }

        // Active battle hooks
        /// <summary>
        /// Called from Update() every 0.5s. Finds the active BattleProcessor by
        /// scanning the scene name and using the BattleHUD view context chain.
        /// </summary>
        internal static void PollBattleState()
        {
            try
            {
                // Check scene name — battles happen in "Dungeon_Clan", "Arena", etc.
                string scene = UnityEngine.SceneManagement.SceneManager.GetActiveScene().name;
                bool sceneLooksBattle = scene != null && (scene.Contains("Dungeon") || scene.Contains("Arena") ||
                    scene.Contains("Campaign") || scene.Contains("Battle"));

                // Authoritative battle-active signal: BattleHUD must exist in the scene.
                // (Harmony ProcessStartBattle/EndBattle also toggle _battleActive, but scene
                //  names like "GoldArena" stick around on selection screens without a fight.)
                var battleHUD = sceneLooksBattle
                    ? GameObject.Find("UIManager/Canvas (Ui Root)/Dialogs/[DV] BattleHUD")
                    : null;
                bool inBattle = battleHUD != null;

                if (inBattle && !_battleActive)
                {
                    // Battle just started
                    _battleActive = true;
                    _battleCommandCount = 0;
                    _pollCount = 0;
                    _ctxDiagLogged = false;
                    _lastStatsLogTurn = -1;
                    lock (_battleLog) { _battleLog.Clear(); }
                }
                else if (!inBattle && _battleActive)
                {
                    // Battle just ended — capture final hero state from the last
                    // known processor before the scene transitions.
                    if (_activeBattleProcessor != null && Instance != null)
                    {
                        try
                        {
                            IntPtr procPtr3 = IntPtr.Zero;
                            var t3 = _activeBattleProcessor.GetType();
                            while (t3 != null)
                            {
                                var p3 = t3.GetProperty("Pointer", BindingFlags.Public | BindingFlags.Instance);
                                if (p3 != null) { procPtr3 = (IntPtr)p3.GetValue(_activeBattleProcessor); break; }
                                t3 = t3.BaseType;
                            }
                            if (procPtr3 != IntPtr.Zero)
                            {
                                string finalHeroes = Instance.ReadBattleHeroesIL2CPP(procPtr3);
                                if (finalHeroes != null)
                                {
                                    lock (_battleLog)
                                    {
                                        if (_battleLog.Count < 2000)
                                            _battleLog.Add("{\"poll\":" + _pollCount +
                                                ",\"turn\":" + _battleCommandCount +
                                                ",\"scene\":\"final\",\"heroes\":" + finalHeroes + "}");
                                    }
                                }
                            }
                        }
                        catch { /* hero data may be torn down — ignore */ }
                    }

                    _battleActive = false;
                    lock (_battleLog)
                    {
                        if (_battleLog.Count < 2000)
                            _battleLog.Add("{\"event\":\"battle_end\",\"turns\":" + _battleCommandCount + ",\"polls\":" + _pollCount + "}");
                    }
                    return;
                }

                if (!_battleActive || battleHUD == null) return;

                _pollCount++;

                // Only log verbose poll entries when the turn advances (or once every 10 polls).
                bool logThisPoll = (_battleCommandCount != _lastStatsLogTurn) || (_pollCount % 10 == 0);

                // PRIMARY PATH: use Harmony-captured BattleProcessor for hero reads.
                // The processor is captured on every ProcessStartTurn hook and remains valid
                // across polls. This is the only known path that actually returns hero state.
                if (_activeBattleProcessor != null)
                {
                    try
                    {
                        IntPtr procPtr2 = IntPtr.Zero;
                        if (_activeBattleProcessor is Il2CppSystem.Object il2obj2)
                            procPtr2 = il2obj2.Pointer;
                        if (procPtr2 == IntPtr.Zero)
                        {
                            var t2 = _activeBattleProcessor.GetType();
                            while (t2 != null)
                            {
                                var p2 = t2.GetProperty("Pointer", BindingFlags.Public | BindingFlags.Instance);
                                if (p2 != null) { procPtr2 = (IntPtr)p2.GetValue(_activeBattleProcessor); break; }
                                t2 = t2.BaseType;
                            }
                        }

                        if (procPtr2 != IntPtr.Zero && Instance != null)
                        {
                            string heroes2 = Instance.ReadBattleHeroesIL2CPP(procPtr2);

                            // ALWAYS emit schema diag once per battle on first successful read
                            if (heroes2 != null && !_ctxDiagLogged)
                            {
                                _ctxDiagLogged = true;
                                Instance.EmitBattleSchemaDiag(procPtr2);
                            }
                            // Effect schema requires a populated AppliedEffectsByHeroes dict — retry
                            // each poll until we capture it (typically after first debuff/buff is placed)
                            // Retry effect probe every ~5th poll for up to ~60 polls (until buffs land)
                            if (heroes2 != null && !_effectDiagLogged && _effectDiagAttempts < 60
                                && _pollCount % 5 == 0)
                            {
                                _effectDiagAttempts++;
                                if (Instance.TryEmitAppliedEffectDiag(procPtr2))
                                    _effectDiagLogged = true;
                            }
                            // Challenge schema: Dictionary<int, Challenge> @ 0xE0 on BattleHero.
                            // Populated during fights (`chl` count > 0). May hold active UK/BD buff tracking.
                            if (heroes2 != null && !_challengeDiagLogged && _challengeDiagAttempts < 60
                                && _pollCount % 5 == 0)
                            {
                                _challengeDiagAttempts++;
                                if (Instance.TryEmitChallengeDiag(procPtr2))
                                    _challengeDiagLogged = true;
                            }
                            // StatImpactByEffects schema: Dictionary<int, ValueTuple<Fixed, StatKindId, EffectContext>>
                            // @ 0xA0 → 0x18 on BattleHero. EffectContext should carry per-effect duration + source.
                            if (heroes2 != null && !_statImpactDiagLogged && _statImpactDiagAttempts < 60
                                && _pollCount % 5 == 0)
                            {
                                _statImpactDiagAttempts++;
                                if (Instance.TryEmitStatImpactDiag(procPtr2))
                                    _statImpactDiagLogged = true;
                            }
                            // Counters dict raw-bytes schema probe — reveals real field layout
                            if (heroes2 != null && _pollCount < 40 && _pollCount % 7 == 0)
                            {
                                Instance.TryEmitCountersDiag(procPtr2);
                            }
                            // Buff-API diag — DISABLED: il2cpp_runtime_invoke on AppliedEffect methods crashes
                            // if (heroes2 != null && !_buffApiDiagLogged)
                            // {
                            //     _buffApiDiagLogged = true;
                            //     Instance.TryEmitBuffApiDiag(procPtr2);
                            // }

                            if (heroes2 != null)
                            {
                                if (logThisPoll)
                                {
                                    lock (_battleLog)
                                    {
                                        if (_battleLog.Count < 2000)
                                            _battleLog.Add("{\"poll\":" + _pollCount + ",\"turn\":" + _battleCommandCount +
                                                ",\"scene\":\"" + scene + "\",\"heroes\":" + heroes2 + "}");
                                    }
                                }
                                _lastStatsLogTurn = _battleCommandCount;
                                return;
                            }
                            else if (!_ctxDiagLogged)
                            {
                                // One-shot diagnostic: list Context's get_* properties so we can
                                // figure out the real path to heroes.
                                _ctxDiagLogged = true;
                                try
                                {
                                    IntPtr ctxObj2 = IntPtr.Zero;
                                    IntPtr getCtxM = FindIL2CPPMethodStatic(il2cpp_object_get_class(procPtr2), "get_Context", 0);
                                    if (getCtxM != IntPtr.Zero)
                                    {
                                        IntPtr ex0 = IntPtr.Zero;
                                        ctxObj2 = il2cpp_runtime_invoke(getCtxM, procPtr2, IntPtr.Zero, ref ex0);
                                    }
                                    IntPtr procClass = il2cpp_object_get_class(procPtr2);
                                    string procName = Marshal.PtrToStringAnsi(il2cpp_class_get_name(procClass));
                                    var sbDiag = new StringBuilder();
                                    sbDiag.Append("{\"diag\":\"ctx_props\",\"proc_type\":\"" + Esc(procName ?? "?") + "\"");
                                    // List processor's get_* methods too
                                    {
                                        var pp = new List<string>();
                                        IntPtr k = procClass;
                                        while (k != IntPtr.Zero && pp.Count < 60)
                                        {
                                            IntPtr mIter = IntPtr.Zero; IntPtr m;
                                            while ((m = il2cpp_class_get_methods(k, ref mIter)) != IntPtr.Zero)
                                            {
                                                string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                                                if (mn != null && mn.StartsWith("get_") && il2cpp_method_get_param_count(m) == 0)
                                                    pp.Add(mn.Substring(4));
                                            }
                                            k = il2cpp_class_get_parent(k);
                                            string pn = k != IntPtr.Zero ? Marshal.PtrToStringAnsi(il2cpp_class_get_name(k)) : "";
                                            if (pn == "Object" || pn == "Il2CppObjectBase" || string.IsNullOrEmpty(pn)) break;
                                        }
                                        sbDiag.Append(",\"proc_props\":[");
                                        for (int i = 0; i < pp.Count; i++) { if (i>0) sbDiag.Append(","); sbDiag.Append("\""+Esc(pp[i])+"\""); }
                                        sbDiag.Append("]");
                                    }
                                    // Drill one level deeper: list State.PlayerTeam's properties
                                    try
                                    {
                                        IntPtr getStateM = FindIL2CPPMethodStatic(procClass, "get_State", 0);
                                        if (getStateM != IntPtr.Zero)
                                        {
                                            IntPtr exS = IntPtr.Zero;
                                            IntPtr stateObj2 = il2cpp_runtime_invoke(getStateM, procPtr2, IntPtr.Zero, ref exS);
                                            if (stateObj2 != IntPtr.Zero)
                                            {
                                                IntPtr getPT = FindIL2CPPMethodStatic(il2cpp_object_get_class(stateObj2), "get_PlayerTeam", 0);
                                                if (getPT != IntPtr.Zero)
                                                {
                                                    IntPtr exPT = IntPtr.Zero;
                                                    IntPtr teamObj = il2cpp_runtime_invoke(getPT, stateObj2, IntPtr.Zero, ref exPT);
                                                    if (teamObj != IntPtr.Zero)
                                                    {
                                                        IntPtr tc = il2cpp_object_get_class(teamObj);
                                                        string tcName = Marshal.PtrToStringAnsi(il2cpp_class_get_name(tc));
                                                        var tp = new List<string>();
                                                        IntPtr k2 = tc;
                                                        while (k2 != IntPtr.Zero && tp.Count < 60)
                                                        {
                                                            IntPtr mIter = IntPtr.Zero; IntPtr m;
                                                            while ((m = il2cpp_class_get_methods(k2, ref mIter)) != IntPtr.Zero)
                                                            {
                                                                string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                                                                if (mn != null && mn.StartsWith("get_") && il2cpp_method_get_param_count(m) == 0)
                                                                    tp.Add(mn.Substring(4));
                                                            }
                                                            k2 = il2cpp_class_get_parent(k2);
                                                            string pn = k2 != IntPtr.Zero ? Marshal.PtrToStringAnsi(il2cpp_class_get_name(k2)) : "";
                                                            if (pn == "Object" || pn == "Il2CppObjectBase" || string.IsNullOrEmpty(pn)) break;
                                                        }
                                                        sbDiag.Append(",\"PlayerTeam_type\":\"" + Esc(tcName ?? "?") + "\"");
                                                        sbDiag.Append(",\"PlayerTeam_props\":[");
                                                        for (int i = 0; i < tp.Count; i++) { if (i>0) sbDiag.Append(","); sbDiag.Append("\""+Esc(tp[i])+"\""); }
                                                        sbDiag.Append("]");

                                                        // Drill into team's hero collection and dump the first hero's schema
                                                        IntPtr heroesColl = IntPtr.Zero;
                                                        string heroesAccessor = null;
                                                        foreach (var n in new[] { "get_HeroesWithGuardian", "get_Heroes", "get_Members", "get_Units", "get_Items", "get_All" })
                                                        {
                                                            IntPtr hM = FindIL2CPPMethodStatic(tc, n, 0);
                                                            if (hM == IntPtr.Zero) continue;
                                                            IntPtr exH = IntPtr.Zero;
                                                            IntPtr r = il2cpp_runtime_invoke(hM, teamObj, IntPtr.Zero, ref exH);
                                                            if (r != IntPtr.Zero) { heroesColl = r; heroesAccessor = n.Substring(4); break; }
                                                        }
                                                        sbDiag.Append(",\"team_heroes_accessor\":\"" + Esc(heroesAccessor ?? "none") + "\"");

                                                        if (heroesColl != IntPtr.Zero)
                                                        {
                                                            IntPtr hc = il2cpp_object_get_class(heroesColl);
                                                            IntPtr getC = FindIL2CPPMethodStatic(hc, "get_Count", 0);
                                                            IntPtr getI = FindIL2CPPMethodStatic(hc, "get_Item", 1);
                                                            if (getC != IntPtr.Zero && getI != IntPtr.Zero)
                                                            {
                                                                IntPtr exCnt = IntPtr.Zero;
                                                                IntPtr cntR = il2cpp_runtime_invoke(getC, heroesColl, IntPtr.Zero, ref exCnt);
                                                                int cnt = cntR != IntPtr.Zero ? Marshal.ReadInt32(cntR + 0x10) : 0;
                                                                sbDiag.Append(",\"team_hero_count\":" + cnt);
                                                                if (cnt > 0)
                                                                {
                                                                    IntPtr ib = Marshal.AllocHGlobal(4); Marshal.WriteInt32(ib, 0);
                                                                    IntPtr ab = Marshal.AllocHGlobal(IntPtr.Size); Marshal.WriteIntPtr(ab, ib);
                                                                    IntPtr exIt = IntPtr.Zero;
                                                                    IntPtr heroObj = il2cpp_runtime_invoke(getI, heroesColl, ab, ref exIt);
                                                                    Marshal.FreeHGlobal(ib); Marshal.FreeHGlobal(ab);
                                                                    if (heroObj != IntPtr.Zero)
                                                                    {
                                                                        IntPtr heroClass = il2cpp_object_get_class(heroObj);
                                                                        string heroTypeName = Marshal.PtrToStringAnsi(il2cpp_class_get_name(heroClass));
                                                                        var hp = new List<string>();
                                                                        IntPtr kH = heroClass;
                                                                        while (kH != IntPtr.Zero && hp.Count < 120)
                                                                        {
                                                                            IntPtr mIter = IntPtr.Zero; IntPtr m;
                                                                            while ((m = il2cpp_class_get_methods(kH, ref mIter)) != IntPtr.Zero)
                                                                            {
                                                                                string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                                                                                if (mn != null && mn.StartsWith("get_") && il2cpp_method_get_param_count(m) == 0)
                                                                                    hp.Add(mn.Substring(4));
                                                                            }
                                                                            kH = il2cpp_class_get_parent(kH);
                                                                            string pnH = kH != IntPtr.Zero ? Marshal.PtrToStringAnsi(il2cpp_class_get_name(kH)) : "";
                                                                            if (pnH == "Object" || pnH == "Il2CppObjectBase" || string.IsNullOrEmpty(pnH)) break;
                                                                        }
                                                                        sbDiag.Append(",\"hero_type\":\"" + Esc(heroTypeName ?? "?") + "\"");
                                                                        sbDiag.Append(",\"hero_props\":[");
                                                                        for (int i = 0; i < hp.Count; i++) { if (i>0) sbDiag.Append(","); sbDiag.Append("\""+Esc(hp[i])+"\""); }
                                                                        sbDiag.Append("]");

                                                                        // Drill into Buffs/Debuffs collections — find first element, dump its props
                                                                        foreach (var coll in new[] { "get_Buffs", "get_Debuffs", "get_StatusEffects", "get_Effects", "get_Skills" })
                                                                        {
                                                                            try
                                                                            {
                                                                                IntPtr cM = FindIL2CPPMethodStatic(heroClass, coll, 0);
                                                                                if (cM == IntPtr.Zero) continue;
                                                                                IntPtr exC = IntPtr.Zero;
                                                                                IntPtr cObj = il2cpp_runtime_invoke(cM, heroObj, IntPtr.Zero, ref exC);
                                                                                if (cObj == IntPtr.Zero) continue;
                                                                                IntPtr cCls = il2cpp_object_get_class(cObj);
                                                                                string cTy = Marshal.PtrToStringAnsi(il2cpp_class_get_name(cCls));
                                                                                IntPtr gC = FindIL2CPPMethodStatic(cCls, "get_Count", 0);
                                                                                IntPtr gI = FindIL2CPPMethodStatic(cCls, "get_Item", 1);
                                                                                sbDiag.Append(",\"" + coll.Substring(4) + "_type\":\"" + Esc(cTy ?? "?") + "\"");
                                                                                if (gC == IntPtr.Zero || gI == IntPtr.Zero) { sbDiag.Append(",\"" + coll.Substring(4) + "_note\":\"not_list\""); continue; }
                                                                                IntPtr exN = IntPtr.Zero;
                                                                                IntPtr nR = il2cpp_runtime_invoke(gC, cObj, IntPtr.Zero, ref exN);
                                                                                int n = nR != IntPtr.Zero ? Marshal.ReadInt32(nR + 0x10) : 0;
                                                                                sbDiag.Append(",\"" + coll.Substring(4) + "_count\":" + n);
                                                                                if (n <= 0) continue;
                                                                                IntPtr ib2 = Marshal.AllocHGlobal(4); Marshal.WriteInt32(ib2, 0);
                                                                                IntPtr ab2 = Marshal.AllocHGlobal(IntPtr.Size); Marshal.WriteIntPtr(ab2, ib2);
                                                                                IntPtr exIt2 = IntPtr.Zero;
                                                                                IntPtr elObj = il2cpp_runtime_invoke(gI, cObj, ab2, ref exIt2);
                                                                                Marshal.FreeHGlobal(ib2); Marshal.FreeHGlobal(ab2);
                                                                                if (elObj == IntPtr.Zero) continue;
                                                                                IntPtr elCls = il2cpp_object_get_class(elObj);
                                                                                string elTy = Marshal.PtrToStringAnsi(il2cpp_class_get_name(elCls));
                                                                                var ep = new List<string>();
                                                                                IntPtr kE = elCls;
                                                                                while (kE != IntPtr.Zero && ep.Count < 60)
                                                                                {
                                                                                    IntPtr mIterE = IntPtr.Zero; IntPtr mE;
                                                                                    while ((mE = il2cpp_class_get_methods(kE, ref mIterE)) != IntPtr.Zero)
                                                                                    {
                                                                                        string mnE = Marshal.PtrToStringAnsi(il2cpp_method_get_name(mE));
                                                                                        if (mnE != null && mnE.StartsWith("get_") && il2cpp_method_get_param_count(mE) == 0)
                                                                                            ep.Add(mnE.Substring(4));
                                                                                    }
                                                                                    kE = il2cpp_class_get_parent(kE);
                                                                                    string pnE = kE != IntPtr.Zero ? Marshal.PtrToStringAnsi(il2cpp_class_get_name(kE)) : "";
                                                                                    if (pnE == "Object" || pnE == "Il2CppObjectBase" || string.IsNullOrEmpty(pnE)) break;
                                                                                }
                                                                                sbDiag.Append(",\"" + coll.Substring(4) + "_el_type\":\"" + Esc(elTy ?? "?") + "\"");
                                                                                sbDiag.Append(",\"" + coll.Substring(4) + "_el_props\":[");
                                                                                for (int i = 0; i < ep.Count; i++) { if (i>0) sbDiag.Append(","); sbDiag.Append("\""+Esc(ep[i])+"\""); }
                                                                                sbDiag.Append("]");
                                                                            }
                                                                            catch { }
                                                                        }
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                    catch { }

                                    // List BattleProcessor methods that look damage/skill/command related
                                    try
                                    {
                                        var interesting = new List<string>();
                                        IntPtr kP = procClass;
                                        while (kP != IntPtr.Zero && interesting.Count < 80)
                                        {
                                            IntPtr mIterP = IntPtr.Zero; IntPtr mP;
                                            while ((mP = il2cpp_class_get_methods(kP, ref mIterP)) != IntPtr.Zero)
                                            {
                                                string mnP = Marshal.PtrToStringAnsi(il2cpp_method_get_name(mP));
                                                if (mnP == null) continue;
                                                if (mnP.IndexOf("Apply", StringComparison.OrdinalIgnoreCase) >= 0
                                                    || mnP.IndexOf("Execute", StringComparison.OrdinalIgnoreCase) >= 0
                                                    || mnP.IndexOf("Damage", StringComparison.OrdinalIgnoreCase) >= 0
                                                    || mnP.IndexOf("Skill", StringComparison.OrdinalIgnoreCase) >= 0
                                                    || mnP.IndexOf("Command", StringComparison.OrdinalIgnoreCase) >= 0
                                                    || mnP.IndexOf("Process", StringComparison.OrdinalIgnoreCase) >= 0)
                                                    interesting.Add(mnP + "/" + il2cpp_method_get_param_count(mP));
                                            }
                                            kP = il2cpp_class_get_parent(kP);
                                            string pnP = kP != IntPtr.Zero ? Marshal.PtrToStringAnsi(il2cpp_class_get_name(kP)) : "";
                                            if (pnP == "Object" || pnP == "Il2CppObjectBase" || string.IsNullOrEmpty(pnP)) break;
                                        }
                                        sbDiag.Append(",\"proc_methods\":[");
                                        for (int i = 0; i < interesting.Count; i++) { if (i>0) sbDiag.Append(","); sbDiag.Append("\""+Esc(interesting[i])+"\""); }
                                        sbDiag.Append("]");
                                    }
                                    catch { }
                                    // Also list Setup and State props on the processor
                                    foreach (var sub in new[] { "get_Setup", "get_State", "get_Statistics" })
                                    {
                                        try
                                        {
                                            IntPtr subM = FindIL2CPPMethodStatic(procClass, sub, 0);
                                            if (subM == IntPtr.Zero) continue;
                                            IntPtr exS = IntPtr.Zero;
                                            IntPtr subObj = il2cpp_runtime_invoke(subM, procPtr2, IntPtr.Zero, ref exS);
                                            if (subObj == IntPtr.Zero) { sbDiag.Append(",\"" + sub.Substring(4) + "\":null"); continue; }
                                            IntPtr subClass = il2cpp_object_get_class(subObj);
                                            string subClassName = Marshal.PtrToStringAnsi(il2cpp_class_get_name(subClass));
                                            var sp = new List<string>();
                                            IntPtr k = subClass;
                                            while (k != IntPtr.Zero && sp.Count < 40)
                                            {
                                                IntPtr mIter = IntPtr.Zero; IntPtr m;
                                                while ((m = il2cpp_class_get_methods(k, ref mIter)) != IntPtr.Zero)
                                                {
                                                    string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                                                    if (mn != null && mn.StartsWith("get_") && il2cpp_method_get_param_count(m) == 0)
                                                        sp.Add(mn.Substring(4));
                                                }
                                                k = il2cpp_class_get_parent(k);
                                                string pn = k != IntPtr.Zero ? Marshal.PtrToStringAnsi(il2cpp_class_get_name(k)) : "";
                                                if (pn == "Object" || pn == "Il2CppObjectBase" || string.IsNullOrEmpty(pn)) break;
                                            }
                                            sbDiag.Append(",\"" + sub.Substring(4) + "_type\":\"" + Esc(subClassName ?? "?") + "\"");
                                            sbDiag.Append(",\"" + sub.Substring(4) + "_props\":[");
                                            for (int i = 0; i < sp.Count; i++) { if (i>0) sbDiag.Append(","); sbDiag.Append("\""+Esc(sp[i])+"\""); }
                                            sbDiag.Append("]");
                                        }
                                        catch { }
                                    }
                                    if (ctxObj2 != IntPtr.Zero)
                                    {
                                        IntPtr ctxClass = il2cpp_object_get_class(ctxObj2);
                                        string ctxName = Marshal.PtrToStringAnsi(il2cpp_class_get_name(ctxClass));
                                        sbDiag.Append(",\"ctx_type\":\"" + Esc(ctxName ?? "?") + "\"");
                                        var props = new List<string>();
                                        IntPtr k = ctxClass;
                                        while (k != IntPtr.Zero && props.Count < 60)
                                        {
                                            IntPtr mIter = IntPtr.Zero; IntPtr m;
                                            while ((m = il2cpp_class_get_methods(k, ref mIter)) != IntPtr.Zero)
                                            {
                                                string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                                                if (mn != null && mn.StartsWith("get_") && il2cpp_method_get_param_count(m) == 0)
                                                    props.Add(mn.Substring(4));
                                            }
                                            k = il2cpp_class_get_parent(k);
                                            string pn = k != IntPtr.Zero ? Marshal.PtrToStringAnsi(il2cpp_class_get_name(k)) : "";
                                            if (pn == "Object" || pn == "Il2CppObjectBase" || string.IsNullOrEmpty(pn)) break;
                                        }
                                        sbDiag.Append(",\"ctx_props\":[");
                                        for (int i = 0; i < props.Count; i++) { if (i>0) sbDiag.Append(","); sbDiag.Append("\""+Esc(props[i])+"\""); }
                                        sbDiag.Append("]");
                                    }
                                    sbDiag.Append("}");
                                    lock (_battleLog)
                                    {
                                        if (_battleLog.Count < 2000) _battleLog.Add(sbDiag.ToString());
                                    }
                                }
                                catch (Exception dex)
                                {
                                    lock (_battleLog)
                                    {
                                        if (_battleLog.Count < 2000)
                                            _battleLog.Add("{\"diag\":\"ctx_props_fail\",\"err\":\"" + Esc(dex.Message) + "\"}");
                                    }
                                }
                            }
                        }
                    }
                    catch { }
                }

                if (!logThisPoll) return;

                // Get hero turn info from the BattleHUD's MonoBehaviours
                // Walk MonoBehaviours on the HUD looking for one with Context
                var monos = battleHUD.GetComponentsInChildren<MonoBehaviour>(true);
                foreach (var mono in monos)
                {
                    if (mono == null) continue;
                    try
                    {
                        IntPtr monoPtr = mono.Pointer;
                        if (monoPtr == IntPtr.Zero) continue;
                        IntPtr monoClass = il2cpp_object_get_class(monoPtr);
                        string cn = Marshal.PtrToStringAnsi(il2cpp_class_get_name(monoClass));
                        if (cn == null || !cn.Contains("View")) continue;

                        // Look for get_Context
                        IntPtr getCtx = FindIL2CPPMethodStatic(monoClass, "get_Context", 0);
                        if (getCtx == IntPtr.Zero) continue;

                        IntPtr exc = IntPtr.Zero;
                        IntPtr ctxObj = il2cpp_runtime_invoke(getCtx, monoPtr, IntPtr.Zero, ref exc);
                        if (ctxObj == IntPtr.Zero) continue;

                        IntPtr ctxClass = il2cpp_object_get_class(ctxObj);
                        string ctxName = Marshal.PtrToStringAnsi(il2cpp_class_get_name(ctxClass));
                        if (ctxName == null || !ctxName.Contains("BattleHUD")) continue;

                        // Found BattleHUDContext! Now find BattleProcessor through
                        // the view's Game context chain.
                        // View -> Game (GameContext) -> battleView -> BattleView -> BattleMode -> Processor

                        // Actually: the MonoBehaviour itself IS the view.
                        // Try: mono -> Game property -> then find processor
                        IntPtr getGame = FindIL2CPPMethodStatic(monoClass, "get_Game", 0);
                        IntPtr gameCtx = IntPtr.Zero;
                        if (getGame != IntPtr.Zero)
                        {
                            IntPtr eg = IntPtr.Zero;
                            gameCtx = il2cpp_runtime_invoke(getGame, monoPtr, IntPtr.Zero, ref eg);
                        }

                        var entry = new System.Text.StringBuilder();
                        entry.Append("{\"poll\":" + _pollCount + ",\"turn\":" + _battleCommandCount);
                        entry.Append(",\"scene\":\"" + scene + "\"");

                        // If we got GameContext, try to read battle state from it
                        if (gameCtx != IntPtr.Zero)
                        {
                            // GameContext has BattleView property which has heroes
                            // But reading hero state requires deep IL2CPP calls
                            // For now, just confirm we have the game context
                            entry.Append(",\"game_ctx\":true");
                        }
                        else
                        {
                            entry.Append(",\"game_ctx\":false");
                        }

                        entry.Append("}");
                        lock (_battleLog)
                        {
                            if (_battleLog.Count < 2000)
                                _battleLog.Add(entry.ToString());
                        }
                        return;
                    }
                    catch { }
                }

                // Just log scene
                lock (_battleLog)
                {
                    if (_battleLog.Count < 2000)
                        _battleLog.Add("{\"poll\":" + _pollCount + ",\"turn\":" + _battleCommandCount + ",\"scene\":\"" + scene + "\"}");
                }
            }
            catch { }
        }

        public static void BattleHook_ProcessStartBattle(object __instance)
        {
            if (++_hookDiag_StartBattle <= 3)
                BepInEx.Logging.Logger.CreateLogSource("CBHookDiag").LogInfo("ProcessStartBattle fired (count=" + _hookDiag_StartBattle + ") instance_type=" + (__instance == null ? "null" : __instance.GetType().FullName));
            try
            {
                _battleActive = true;
                _battleCommandCount = 0;
                _pollCount = 0;
                _ctxDiagLogged = false;
                _effectDiagLogged = false;
                _effectDiagAttempts = 0;
                _challengeDiagLogged = false;
                _challengeDiagAttempts = 0;
                _statImpactDiagLogged = false;
                _statImpactDiagAttempts = 0;
                _buffApiDiagLogged = false;
                _hsBuffFieldsResolved = false;
                _hsAppliedBuffsOff = -1;
                _hsAppliedDebuffsOff = -1;
                _aeFieldsResolved = false;
                _aeEffectTypeIdField = IntPtr.Zero;
                _aeTurnLeftField = IntPtr.Zero;
                _aeProducerIdField = IntPtr.Zero;
                _lastStatsLogTurn = -1;
                _activeBattleProcessor = __instance;
                lock (_battleLog)
                {
                    _battleLog.Clear();
                    _battleLog.Add("{\"event\":\"battle_start\"}");
                }
                lock (_tickLog) { _tickLog.Clear(); }
            }
            catch { }
        }

        public static void BattleHook_ProcessEndBattle(object __instance)
        {
            try
            {
                // Capture final hero snapshot before battle state is torn down.
                // This catches damage from the last 2-3 turns that the poll loop
                // often misses (enrage kills happen between polls).
                if (_battleActive && _activeBattleProcessor != null && Instance != null)
                {
                    IntPtr procPtr = IntPtr.Zero;
                    try
                    {
                        var t = _activeBattleProcessor.GetType();
                        while (t != null)
                        {
                            var p = t.GetProperty("Pointer",
                                System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Instance);
                            if (p != null) { procPtr = (IntPtr)p.GetValue(_activeBattleProcessor); break; }
                            t = t.BaseType;
                        }
                    }
                    catch { }

                    if (procPtr != IntPtr.Zero)
                    {
                        string heroData = Instance.ReadBattleHeroesIL2CPP(procPtr);
                        if (heroData != null)
                        {
                            lock (_battleLog)
                            {
                                if (_battleLog.Count < 2000)
                                {
                                    _battleLog.Add("{\"poll\":" + _pollCount + ",\"turn\":" +
                                        _battleCommandCount + ",\"scene\":\"final\",\"heroes\":" + heroData + "}");
                                    _battleLog.Add("{\"event\":\"battle_end\",\"turns\":" +
                                        _battleCommandCount + ",\"polls\":" + _pollCount + "}");
                                }
                            }
                        }
                    }
                }

                // Snapshot the completed battle so /battle-log can serve it
                // even after ProcessStartBattle fires again (which wipes _battleLog).
                lock (_battleLog)
                {
                    _completedBattleLog.Clear();
                    _completedBattleLog.AddRange(_battleLog);
                    _completedTurnCount = _battleCommandCount;
                    _completedPollCount = _pollCount;
                }

                _battleActive = false;
            }
            catch { _battleActive = false; }
        }

        public static void BattleHook_ProcessStartRound(object __instance)
        {
            try
            {
                lock (_battleLog)
                {
                    if (_battleLog.Count < 2000)
                        _battleLog.Add("{\"event\":\"round_start\",\"turn\":" + _battleCommandCount + "}");
                }
            }
            catch { }
        }

        public static void BattleHook_ProcessEndRound(object __instance)
        {
            try
            {
                lock (_battleLog)
                {
                    if (_battleLog.Count < 2000)
                        _battleLog.Add("{\"event\":\"round_end\",\"turn\":" + _battleCommandCount + "}");
                }
            }
            catch { }
        }

        public static void BattleHook_ProcessEndTurn(object __instance)
        {
            // Force a fresh heroes snapshot on the NEXT poll by resetting _lastStatsLogTurn
            // so the logger emits a complete end-of-turn row.
            try { _lastStatsLogTurn = -1; } catch { }
        }

        /// <summary>
        /// Fires when any hero (player or enemy) executes a skill.
        /// The single argument is the SkillCommand (contains caster, target, skill id).
        /// </summary>
        private static int _hookDiag_ApplyCommand = 0;
        private static int _hookDiag_DamageChange = 0;
        private static int _hookDiag_ApplyStatus = 0;
        private static int _hookDiag_RemoveStatus = 0;
        private static int _hookDiag_DurationChange = 0;
        internal static readonly Dictionary<string, int> _applyCmdClasses = new();

        // Best-effort dump of an Il2Cpp/wrapper object's fields via reflection.
        // Used for processor event logging where we don't know exact param types.
        private static string DumpEventArgs(object[] args)
        {
            var sb = new StringBuilder();
            sb.Append("[");
            for (int i = 0; i < args.Length; i++)
            {
                if (i > 0) sb.Append(",");
                var a = args[i];
                if (a == null) { sb.Append("null"); continue; }
                string tname = a.GetType().Name;
                sb.Append("{\"i\":" + i + ",\"type\":\"" + Esc(tname) + "\"");
                // Extract common fields. BattleHero objects → extract their Id.
                // Numerics (Fixed, int, bool) → extract the value.
                // Nested contexts (DamageContext, ApplyContext) → depth-1 recurse into key fields.
                ExtractFieldsInto(sb, a, new[] {
                    "Producer", "Target", "InitialTarget",
                    "Amount", "Damage", "DamageAmount", "Value", "Health",
                    "StatusEffectTypeId", "TypeId", "Duration",
                    "IsCritical", "IsCrit", "CritChance",
                    "Chance", "Count", "SkillTypeId",
                    "Accuracy", "Resistance", "BaseAccuracy",
                    "IsGuaranteedBlocked", "ApplyResult", "ApplyFailReason",
                    "AppliedEffect",
                    "IsBlocked", "IsEvaded", "IsNullified", "WasRedirected",
                    "HitType", "GlanceReason", "ElementRelation",
                    "CalculatedDamage", "DealtDamage", "TargetHealthAfterDamage",
                    "AbsorbedByBlockDamage", "DefenceModifier",
                    "CriticalHitChance", "GlancingHitChance", "CrushingHitChance",
                });
                // Depth-1 recurse into known sub-contexts
                foreach (var sub in new[] { "DamageContext", "ApplyContext", "HealContext", "ChangeStaminaContext" })
                {
                    object subCtx = null;
                    try { subCtx = Prop(a, sub); } catch { }
                    if (subCtx == null) continue;
                    sb.Append(",\"" + sub + "\":{\"_type\":\"" + Esc(subCtx.GetType().Name) + "\"");
                    ExtractFieldsInto(sb, subCtx, new[] {
                        "HitType", "IsBlocked", "IsCritical",
                        "CalculatedDamage", "DealtDamage", "TargetHealthAfterDamage",
                        "AbsorbedByBlockDamage", "DefenceModifier",
                        "CriticalHitChance", "GlancingHitChance", "CrushingHitChance",
                        "ElementRelation", "GlanceReason", "MultiplierValuePositive",
                        "Accuracy", "Resistance", "BaseAccuracy", "ApplyResult",
                        "ApplyFailReason", "IsGuaranteedBlocked",
                        "Amount",
                    });
                    // For ApplyContext: also pull the nested AppliedEffect details
                    // (EffectTypeId, TurnLeft, ProducerId, SkillTypeId, Lifetime)
                    if (sub == "ApplyContext")
                    {
                        try
                        {
                            // AppliedEffect is a direct field (no property accessor), use GetField
                            object applied = null;
                            try
                            {
                                var f = subCtx.GetType().GetField("AppliedEffect",
                                    BindingFlags.Public | BindingFlags.Instance | BindingFlags.NonPublic);
                                if (f != null) applied = f.GetValue(subCtx);
                            }
                            catch { }
                            if (applied == null) applied = Prop(subCtx, "AppliedEffect");
                            if (applied != null)
                            {
                                sb.Append(",\"applied_effect\":{");
                                bool first = true;
                                foreach (var af in new[] { "Id", "EffectTypeId", "TurnLeft", "Lifetime", "ProducerId", "SkillTypeId", "ApplyTurn" })
                                {
                                    try
                                    {
                                        int v = IntProp(applied, af);
                                        if (!first) sb.Append(",");
                                        sb.Append("\"" + af + "\":" + v);
                                        first = false;
                                    } catch { }
                                }
                                sb.Append("}");
                            }
                        }
                        catch { }
                    }
                    sb.Append("}");
                }
                sb.Append("}");
            }
            sb.Append("]");
            return sb.ToString();
        }

        // Extract a flat list of field names from an object into the given
        // StringBuilder (each as JSON ",\"name\":value"). Handles BattleHero
        // objects (extract .Id), Fixed-point numerics (unbox via .RawValue),
        // primitives and enums.
        private static void ExtractFieldsInto(StringBuilder sb, object obj, string[] fields)
        {
            if (obj == null) return;
            foreach (var fieldName in fields)
            {
                try
                {
                    var v = Prop(obj, fieldName);
                    if (v == null) continue;
                    // BattleHero → use Id
                    if (fieldName == "Producer" || fieldName == "Target" || fieldName == "InitialTarget")
                    {
                        try { var hid = Prop(v, "Id"); if (hid != null) { sb.Append(",\"" + fieldName + "\":" + Convert.ToInt32(hid)); continue; } }
                        catch { }
                    }
                    // Boolean / numeric primitives
                    if (v is int || v is long || v is short || v is byte) { sb.Append(",\"" + fieldName + "\":" + v); continue; }
                    if (v is bool bv) { sb.Append(",\"" + fieldName + "\":" + (bv ? "true" : "false")); continue; }
                    // Fixed-point (game's Fixed type has .RawValue — 32.32)
                    try
                    {
                        var raw = Prop(v, "RawValue");
                        if (raw != null)
                        {
                            long rawL = Convert.ToInt64(raw);
                            sb.Append(",\"" + fieldName + "\":" + (rawL >> 32));
                            continue;
                        }
                    }
                    catch { }
                    // DamageResult — has Amount or similar
                    try
                    {
                        var amt = Prop(v, "Amount");
                        if (amt != null)
                        {
                            try { var raw2 = Prop(amt, "RawValue"); if (raw2 != null) { long rl = Convert.ToInt64(raw2); sb.Append(",\"" + fieldName + "\":" + (rl >> 32)); continue; } } catch { }
                            try { double d2 = Convert.ToDouble(amt); sb.Append(",\"" + fieldName + "\":" + d2); continue; } catch { }
                        }
                    }
                    catch { }
                    try
                    {
                        double dv = Convert.ToDouble(v);
                        sb.Append(",\"" + fieldName + "\":" + dv);
                        continue;
                    }
                    catch { }
                    // String / enum
                    var s = v.ToString();
                    if (s != null && s.Length < 60) sb.Append(",\"" + fieldName + "\":\"" + Esc(s) + "\"");
                }
                catch { }
            }
        }

        // Diagnostic dump of DamageResult class structure — fires once.
        // We need this because Prop() (managed reflection) couldn't find
        // an Amount field/property — IL2CPP types may expose data via runtime
        // methods or distinct field names (m_Amount, _value, etc.).
        private static int _damageResultDumped = 0;
        private static void DumpDamageResultOnce(object damageResult, string label)
        {
            if (damageResult == null) return;
            if (Interlocked.CompareExchange(ref _damageResultDumped, 1, 0) != 0) return;
            try
            {
                var sb = new StringBuilder();
                sb.Append("{\"diag\":\"damage_result_schema\",\"label\":\"").Append(Esc(label)).Append("\"");
                var t = damageResult.GetType();
                sb.Append(",\"type\":\"").Append(Esc(t.FullName ?? t.Name)).Append("\"");
                // Managed properties
                var props = t.GetProperties(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                sb.Append(",\"props\":[");
                bool firstP = true;
                foreach (var p in props)
                {
                    if (!firstP) sb.Append(","); firstP = false;
                    sb.Append("{\"n\":\"").Append(Esc(p.Name)).Append("\",\"t\":\"").Append(Esc(p.PropertyType.Name)).Append("\"");
                    try { var v = p.GetValue(damageResult); if (v != null) sb.Append(",\"v\":\"").Append(Esc(v.ToString() ?? "")).Append("\""); } catch { }
                    sb.Append("}");
                }
                sb.Append("]");
                // Managed fields
                var fields = t.GetFields(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                sb.Append(",\"fields\":[");
                bool firstF = true;
                foreach (var f in fields)
                {
                    if (!firstF) sb.Append(","); firstF = false;
                    sb.Append("{\"n\":\"").Append(Esc(f.Name)).Append("\",\"t\":\"").Append(Esc(f.FieldType.Name)).Append("\"");
                    try { var v = f.GetValue(damageResult); if (v != null) sb.Append(",\"v\":\"").Append(Esc(v.ToString() ?? "")).Append("\""); } catch { }
                    sb.Append("}");
                }
                sb.Append("]");
                // IL2CPP class methods (especially get_*)
                try
                {
                    IntPtr klass = il2cpp_object_get_class(IL2CPPHandleOf(damageResult));
                    if (klass != IntPtr.Zero)
                    {
                        sb.Append(",\"il2cpp_methods\":[");
                        IntPtr iter = IntPtr.Zero;
                        IntPtr m;
                        bool firstM = true;
                        int count = 0;
                        while ((m = il2cpp_class_get_methods(klass, ref iter)) != IntPtr.Zero && count < 60)
                        {
                            string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                            int parc = (int)il2cpp_method_get_param_count(m);
                            if (mn != null && (mn.StartsWith("get_") || mn == "ToString"))
                            {
                                if (!firstM) sb.Append(","); firstM = false;
                                sb.Append("{\"n\":\"").Append(Esc(mn)).Append("\",\"argc\":").Append(parc).Append("}");
                                count++;
                            }
                        }
                        sb.Append("]");
                    }
                }
                catch (Exception ex) { sb.Append(",\"il2cpp_err\":\"").Append(Esc(ex.Message)).Append("\""); }
                sb.Append("}");
                lock (_tickLog) { if (_tickLog.Count < 3000) _tickLog.Add(sb.ToString()); }
            }
            catch { }
        }

        // Walk obj.subProp.fieldName.RawValue and return the integer part of
        // the Fixed-point value (>>32). Returns -1 if any link is null.
        // Used to extract DamageResult fields exactly without fitting clusters.
        private static long ReadFixedRaw(object obj, string subProp, string fieldName)
        {
            try
            {
                var sub = Prop(obj, subProp);
                if (sub == null) return -1;
                var val = Prop(sub, fieldName);
                if (val == null) return -1;
                var raw = Prop(val, "RawValue");
                if (raw == null) return -1;
                return Convert.ToInt64(raw) >> 32;
            }
            catch { return -1; }
        }

        // Convert a managed wrapper object to its underlying IL2CPP IntPtr handle.
        // Most BepInEx Il2CppObjectBase derivatives have a `Pointer` property.
        private static IntPtr IL2CPPHandleOf(object o)
        {
            if (o == null) return IntPtr.Zero;
            try { var p = o.GetType().GetProperty("Pointer"); if (p != null) { var v = p.GetValue(o); if (v != null) return (IntPtr)v; } } catch { }
            try { var f = o.GetType().GetField("m_Pointer", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance); if (f != null) { var v = f.GetValue(o); if (v != null) return (IntPtr)v; } } catch { }
            return IntPtr.Zero;
        }

        public static void BattleHook_DamageChange(object __instance, object[] __args)
        {
            _hookDiag_DamageChange++;
            try
            {
                // Walk EffectContext.DamageContext.{CalculatedDamage,DealtDamage}
                // and extract .Amount.RawValue — this is the ground-truth per-hit
                // damage the game just applied. The generic DumpEventArgs path
                // only catches managed properties; IL2CPP DamageResult exposes
                // Amount as a field so we extract it explicitly here.
                // Capture every field the game exposes so we can derive
                // exact damage formulas from the data instead of guessing
                // caps from cluster medians.
                long calcAmt = -1, dealtAmt = -1;
                long calcRaw = -1, dealtRaw = -1;       // pre-mitigation (MultiplierValuePositive)
                long calcMitig = -1, dealtMitig = -1;   // calc/dealt damage absorbed by block/UK
                int producerId = 0, targetId = 0;
                int skillTypeId = 0;
                int effectKind = 0;          // 6000=damage, 5000=poison, 5002=hp_burn, etc.
                string hitType = null;
                bool isCrit = false, isBlocked = false, isEvaded = false;
                try
                {
                    if (__args != null && __args.Length > 0 && __args[0] != null)
                    {
                        var eff = __args[0];
                        try { var prod = Prop(eff, "Producer"); if (prod != null) producerId = IntProp(prod, "Id"); } catch { }
                        try { var tgt = Prop(eff, "Target"); if (tgt != null) targetId = IntProp(tgt, "Id"); } catch { }
                        try { isEvaded = (bool)Prop(eff, "IsEvaded"); } catch { }
                        var dctx = Prop(eff, "DamageContext");
                        if (dctx != null)
                        {
                            try { isBlocked = (bool)Prop(dctx, "IsBlocked"); } catch { }
                            try { var ht = Prop(dctx, "HitType"); if (ht != null) hitType = ht.ToString(); } catch { }
                            try { var ic = Prop(dctx, "IsCritical"); if (ic != null) isCrit = (bool)ic; } catch { }
                            // DamageResult fields (per schema dump 2026-04-24):
                            //   ActualValue                = post-cap, post-mitigation damage applied
                            //   ValuePositive              = same as ActualValue (alias)
                            //   MultiplierValuePositive    = pre-cap, pre-mitigation raw damage
                            //   _value / _multiplierValue  = backing fields for the above
                            //   DamageAbsorbedByBlockAndUnkillable = portion absorbed
                            // Capturing all of them lets us derive the exact cap/mitigation
                            // formula instead of fitting clusters.
                            calcAmt    = ReadFixedRaw(dctx, "CalculatedDamage", "ActualValue");
                            calcRaw    = ReadFixedRaw(dctx, "CalculatedDamage", "MultiplierValuePositive");
                            calcMitig  = ReadFixedRaw(dctx, "CalculatedDamage", "DamageAbsorbedByBlockAndUnkillable");
                            dealtAmt   = ReadFixedRaw(dctx, "DealtDamage", "ActualValue");
                            dealtRaw   = ReadFixedRaw(dctx, "DealtDamage", "MultiplierValuePositive");
                            dealtMitig = ReadFixedRaw(dctx, "DealtDamage", "DamageAbsorbedByBlockAndUnkillable");
                            // Trigger the schema dump on first hit (already wired).
                            try { var calc = Prop(dctx, "CalculatedDamage"); if (calc != null) DumpDamageResultOnce(calc, "CalculatedDamage"); } catch { }
                        }
                        try
                        {
                            var actx = Prop(eff, "ApplyContext");
                            if (actx != null)
                            {
                                var applied = Prop(actx, "AppliedEffect");
                                if (applied != null)
                                {
                                    skillTypeId = IntProp(applied, "SkillTypeId");
                                    // EffectKindId tells us if this is a 6000 (skill damage),
                                    // 5000 (poison), 5002 (HP burn), 4017 (passive damage), etc.
                                    // Lets us label every observed cluster precisely.
                                    try { effectKind = IntProp(applied, "EffectKindId"); } catch { }
                                }
                            }
                        }
                        catch { }
                    }
                }
                catch { }

                var sb = new StringBuilder();
                sb.Append("{\"kind\":\"damage\",\"tick\":").Append(_battleCommandCount);
                sb.Append(",\"producer\":").Append(producerId);
                sb.Append(",\"target\":").Append(targetId);
                if (calcAmt   >= 0) sb.Append(",\"calc\":").Append(calcAmt);
                if (calcRaw   >= 0) sb.Append(",\"calc_raw\":").Append(calcRaw);
                if (calcMitig >= 0) sb.Append(",\"calc_absorbed\":").Append(calcMitig);
                if (dealtAmt  >= 0) sb.Append(",\"dealt\":").Append(dealtAmt);
                if (dealtRaw  >= 0) sb.Append(",\"dealt_raw\":").Append(dealtRaw);
                if (dealtMitig>= 0) sb.Append(",\"dealt_absorbed\":").Append(dealtMitig);
                if (skillTypeId != 0) sb.Append(",\"skill\":").Append(skillTypeId);
                if (effectKind  != 0) sb.Append(",\"kind_id\":").Append(effectKind);
                if (hitType != null && hitType.Length < 30) sb.Append(",\"hit\":\"").Append(Esc(hitType)).Append("\"");
                if (isCrit) sb.Append(",\"crit\":true");
                if (isBlocked) sb.Append(",\"blocked\":true");
                if (isEvaded) sb.Append(",\"evaded\":true");
                sb.Append("}");
                string entry = sb.ToString();
                lock (_tickLog) { if (_tickLog.Count < 3000) _tickLog.Add(entry); }
            }
            catch { }
        }

        // Extract AppliedEffect fields from an EffectContext via raw IL2CPP memory reads.
        // Layout (from Il2CppDumper): EffectContext.ApplyContext@0xB0, ApplyContext.AppliedEffect@0x40,
        // AppliedEffect.{Id@0x10, ProducerId@0x14, SkillTypeId@0x28, EffectTypeId@0x38,
        //               ApplyTurn@0x40, Lifetime@0x44, TurnLeft@0x48}
        private static string ExtractAppliedEffectFromCx(object[] __args)
        {
            try
            {
                if (__args == null || __args.Length == 0 || __args[0] == null) return "";
                if (!(__args[0] is Il2CppSystem.Object il2Obj)) return "";
                IntPtr cx = il2Obj.Pointer;
                if ((long)cx < 0x10000) return "";
                IntPtr applyCtx = Marshal.ReadIntPtr(cx + 0xB0);
                if ((long)applyCtx < 0x10000) return "";
                // StatusEffectContext @ ApplyContext+0x38 with StatusEffectTypeIdToApply@+0x18
                //                       EffectTurnsModifier (Nullable<int>) @ +0x10 (HasValue@0x10, Value@0x14)
                int setype = -1;
                int turnModHas = 0, turnModVal = 0;
                IntPtr sec = Marshal.ReadIntPtr(applyCtx + 0x38);
                if ((long)sec > 0x10000)
                {
                    turnModHas = Marshal.ReadInt32(sec + 0x14);
                    turnModVal = Marshal.ReadInt32(sec + 0x10);
                    setype = Marshal.ReadInt32(sec + 0x18);
                }
                // Producer/target BattleHero refs from ApplyContext: 0x58 / 0x60
                // BattleHero: TypeId@0x18, Id@0x1C
                int producerId = -1, targetId = -1, producerType = -1, targetType = -1;
                try
                {
                    IntPtr prod = Marshal.ReadIntPtr(applyCtx + 0x58);
                    if ((long)prod > 0x10000)
                    {
                        producerType = Marshal.ReadInt32(prod + 0x18);
                        producerId = Marshal.ReadInt32(prod + 0x1C);
                    }
                    IntPtr tgt = Marshal.ReadIntPtr(applyCtx + 0x60);
                    if ((long)tgt > 0x10000)
                    {
                        targetType = Marshal.ReadInt32(tgt + 0x18);
                        targetId = Marshal.ReadInt32(tgt + 0x1C);
                    }
                }
                catch { }
                long accMod = Marshal.ReadInt64(applyCtx + 0x20);
                long resMod = Marshal.ReadInt64(applyCtx + 0x28);
                byte applyResHas = Marshal.ReadByte(applyCtx + 0x30);
                byte applyResVal = Marshal.ReadByte(applyCtx + 0x31);
                int failReason = Marshal.ReadInt32(applyCtx + 0x34);

                IntPtr ae = Marshal.ReadIntPtr(applyCtx + 0x40);
                string aeJson;
                if ((long)ae < 0x10000)
                {
                    aeJson = "null";
                }
                else
                {
                    int id = Marshal.ReadInt32(ae + 0x10);
                    int pid = Marshal.ReadInt32(ae + 0x14);
                    int skillTypeId = Marshal.ReadInt32(ae + 0x28);
                    int effectTypeId = Marshal.ReadInt32(ae + 0x38);
                    int applyTurn = Marshal.ReadInt32(ae + 0x40);
                    int lifetime = Marshal.ReadInt32(ae + 0x44);
                    int turnLeft = Marshal.ReadInt32(ae + 0x48);
                    aeJson = "{\"id\":" + id + ",\"p\":" + pid + ",\"s\":" + skillTypeId
                        + ",\"e\":" + effectTypeId + ",\"at\":" + applyTurn + ",\"l\":" + lifetime
                        + ",\"tl\":" + turnLeft + "}";
                }
                return ",\"ae\":" + aeJson
                    + ",\"setype\":" + setype
                    + ",\"tmodH\":" + turnModHas + ",\"tmodV\":" + turnModVal
                    + ",\"acc_mod\":" + accMod + ",\"res_mod\":" + resMod
                    + ",\"res_has\":" + applyResHas + ",\"res_val\":" + applyResVal
                    + ",\"fail\":" + failReason
                    + ",\"prod\":" + producerId + ",\"prodT\":" + producerType
                    + ",\"tgt\":" + targetId + ",\"tgtT\":" + targetType;
            }
            catch (Exception ex)
            {
                return ",\"ae_err\":\"" + ex.GetType().Name + "\"";
            }
        }

        public static void BattleHook_ApplyStatus(object __instance, object[] __args)
        {
            _hookDiag_ApplyStatus++;
            try
            {
                string ae = ExtractAppliedEffectFromCx(__args);
                string entry = "{\"kind\":\"apply_status\",\"tick\":" + _battleCommandCount + ae + ",\"args\":" + DumpEventArgs(__args ?? new object[0]) + "}";
                lock (_tickLog) { if (_tickLog.Count < 3000) _tickLog.Add(entry); }
            }
            catch { }
        }

        public static void BattleHook_RemoveStatus(object __instance, object[] __args)
        {
            _hookDiag_RemoveStatus++;
            try
            {
                string ae = ExtractAppliedEffectFromCx(__args);
                string entry = "{\"kind\":\"remove_status\",\"tick\":" + _battleCommandCount + ae + ",\"args\":" + DumpEventArgs(__args ?? new object[0]) + "}";
                lock (_tickLog) { if (_tickLog.Count < 3000) _tickLog.Add(entry); }
            }
            catch { }
        }

        public static void BattleHook_DurationChange(object __instance, object[] __args)
        {
            _hookDiag_DurationChange++;
            try
            {
                string ae = ExtractAppliedEffectFromCx(__args);
                string entry = "{\"kind\":\"duration_change\",\"tick\":" + _battleCommandCount + ae + ",\"args\":" + DumpEventArgs(__args ?? new object[0]) + "}";
                lock (_tickLog) { if (_tickLog.Count < 3000) _tickLog.Add(entry); }
            }
            catch { }
        }

        private static int _hookDiag_TurnLeftSet = 0;
        private static int _hookDiag_BeforeStartTurn = 0;
        private static int _hookDiag_UnapplyExecute = 0;

        // Fires when the ECS system runs its unapply-result group.
        // __instance holds _unapplyEffectResults group, which we iterate.
        public static void BattleHook_UnapplyExecute(object __instance)
        {
            _hookDiag_UnapplyExecute++;
            try
            {
                // Iterate _unapplyEffectResults group (IGroup<Entity>). Each entity has
                // an UnappliedEffectResult component. Walk members + dump fields.
                var group = Prop(__instance, "_unapplyEffectResults");
                if (group == null) return;
                int count = IntProp(group, "Count");
                // Only log when count > 0 — most Execute fires have empty group
                if (count == 0) return;
                // Log that we found something (always tracks even if iteration fails)
                int fireNum = _hookDiag_UnapplyExecute;
                var sb = new StringBuilder();
                sb.Append("{\"kind\":\"unapply\",\"tick\":" + _battleCommandCount + ",\"count\":" + count + ",\"items\":[");
                try
                {
                    var entities = Prop(group, "GetEntities") ?? Prop(group, "Entities") ?? Prop(group, "entities") ?? group;
                    var enm = entities.GetType().GetMethod("GetEnumerator");
                    if (enm != null)
                    {
                        var en = enm.Invoke(entities, null);
                        var mn = en.GetType().GetMethod("MoveNext");
                        var cur = en.GetType().GetProperty("Current");
                        int i = 0;
                        while ((bool)mn.Invoke(en, null) && i < 10)
                        {
                            var entity = cur.GetValue(en);
                            // Entity has UnappliedEffectResult component — reflect for Effect/Target/Cause
                            if (i > 0) sb.Append(",");
                            // Try to extract result directly from entity
                            var eff = Prop(entity, "Effect") ?? Prop(entity, "effect");
                            var tgt = Prop(entity, "Target") ?? Prop(entity, "target");
                            var cause = Prop(entity, "Cause") ?? Prop(entity, "cause");
                            int tgtId = 0, effType = 0;
                            if (tgt != null) tgtId = IntProp(tgt, "Id");
                            if (eff != null) effType = IntProp(eff, "EffectTypeId");
                            sb.Append("{\"target\":" + tgtId + ",\"effect_type\":" + effType + ",\"cause\":\"" + Esc(cause?.ToString() ?? "?") + "\"}");
                            i++;
                        }
                    }
                }
                catch { }
                sb.Append("]}");
                lock (_tickLog) { if (_tickLog.Count < 3000) _tickLog.Add(sb.ToString()); }
            }
            catch { }
        }

        // ProcessBeforeStartTurn fires right before a hero takes their turn.
        // This is where durations typically tick down for effects on that hero.
        // We dump the pre-turn state of their effects so Python can diff vs
        // next poll to detect naturally expired effects.
        public static void BattleHook_ProcessBeforeStartTurn(object __instance)
        {
            _hookDiag_BeforeStartTurn++;
            try
            {
                // Dump all heroes' effects — but only if we can find the ActiveHero
                // from state.CurrentHero or similar. Simpler: just snapshot all.
                var sb = new StringBuilder();
                sb.Append("{\"kind\":\"before_start_turn\",\"tick\":" + _battleCommandCount + ",\"effects\":[");
                int n = 0;
                try
                {
                    var state = Prop(__instance, "State");
                    foreach (var teamGetter in new[] { "PlayerTeam", "EnemyTeam" })
                    {
                        var team = Prop(state, teamGetter);
                        if (team == null) continue;
                        object heroes = Prop(team, "HeroesWithGuardian") ?? Prop(team, "Heroes");
                        if (heroes == null) continue;
                        // Use Count + indexer
                        int count = IntProp(heroes, "Count");
                        for (int i = 0; i < count && i < 10; i++)
                        {
                            object hero = null;
                            try
                            {
                                var idxer = heroes.GetType().GetProperty("Item");
                                if (idxer != null) hero = idxer.GetValue(heroes, new object[] { i });
                            }
                            catch { }
                            if (hero == null) continue;
                            int hid = IntProp(hero, "Id");
                            // AppliedEffectsByHeroes: Dict<BattleHero, List<AppliedEffect>>
                            var aeByH = Prop(hero, "AppliedEffectsByHeroes");
                            if (aeByH == null) continue;
                            // Dict.Values
                            var values = Prop(aeByH, "Values");
                            if (values == null) continue;
                            // Iterate values (each is a List<AppliedEffect>)
                            try
                            {
                                var enumer = values.GetType().GetMethod("GetEnumerator");
                                if (enumer == null) continue;
                                var en = enumer.Invoke(values, null);
                                var moveNext = en.GetType().GetMethod("MoveNext");
                                var current = en.GetType().GetProperty("Current");
                                while ((bool)moveNext.Invoke(en, null))
                                {
                                    var list = current.GetValue(en);
                                    if (list == null) continue;
                                    int lc = IntProp(list, "Count");
                                    var idxr = list.GetType().GetProperty("Item");
                                    for (int k = 0; k < lc && k < 20; k++)
                                    {
                                        var eff = idxr?.GetValue(list, new object[] { k });
                                        if (eff == null) continue;
                                        int etype = IntProp(eff, "EffectTypeId");
                                        int tLeft = IntProp(eff, "TurnLeft");
                                        int pid = IntProp(eff, "ProducerId");
                                        if (n > 0) sb.Append(",");
                                        sb.Append("{\"h\":" + hid + ",\"t\":" + etype + ",\"tl\":" + tLeft + ",\"pid\":" + pid + "}");
                                        n++;
                                    }
                                }
                            }
                            catch { }
                        }
                    }
                }
                catch { }
                sb.Append("]}");
                lock (_tickLog) { if (_tickLog.Count < 3000) _tickLog.Add(sb.ToString()); }
            }
            catch { }
        }
        // __instance = the AppliedEffect being modified; __0 = the new TurnLeft value
        public static void BattleHook_TurnLeftSet(object __instance, int __0)
        {
            _hookDiag_TurnLeftSet++;
            try
            {
                int producerId = IntProp(__instance, "ProducerId");
                int effectType = IntProp(__instance, "EffectTypeId");
                int lifetime = IntProp(__instance, "Lifetime");
                int skillTypeId = IntProp(__instance, "SkillTypeId");
                string entry = "{\"kind\":\"turn_left_set\",\"tick\":" + _battleCommandCount
                              + ",\"producer_id\":" + producerId
                              + ",\"effect_type\":" + effectType
                              + ",\"new_turn_left\":" + __0
                              + ",\"lifetime\":" + lifetime
                              + ",\"skill_type_id\":" + skillTypeId + "}";
                lock (_tickLog) { if (_tickLog.Count < 3000) _tickLog.Add(entry); }
            }
            catch { }
        }

        public static void BattleHook_ApplyCommand(object __instance, object __0)
        {
            _hookDiag_ApplyCommand++;
            // ApplyCommand is the generic dispatcher. Track class name of each
            // command that comes through so we can identify SkillCommand variants.
            try
            {
                if (__0 == null) return;
                IntPtr cmdPtr = IntPtr.Zero;
                if (__0 is Il2CppSystem.Object il2obj) cmdPtr = il2obj.Pointer;
                if (cmdPtr == IntPtr.Zero) return;
                IntPtr cls = il2cpp_object_get_class(cmdPtr);
                string cmdClassName = Marshal.PtrToStringAnsi(il2cpp_class_get_name(cls)) ?? "?";
                lock (_applyCmdClasses)
                {
                    _applyCmdClasses[cmdClassName] = _applyCmdClasses.GetValueOrDefault(cmdClassName, 0) + 1;
                }
                // Always attempt extraction — IL2CPP returns the static type
                // (BattleCommand) not the runtime subclass, so we can't filter
                // on name. The extractor itself gracefully produces a 0-filled
                // cast entry if the command isn't actually a skill.
                BattleHook_ApplySkillCommand(__instance, __0);
            }
            catch { }
        }

        public static void BattleHook_ApplySkillCommand(object __instance, object __0)
        {
            if (++_hookDiag_ApplySkill <= 5 || _hookDiag_ApplySkill % 50 == 0)
                BepInEx.Logging.Logger.CreateLogSource("CBHookDiag").LogInfo("ApplySkillCommand fired (count=" + _hookDiag_ApplySkill + ")");

            // Clean cast event for tick log: {kind:"cast", producer_id, target_id, skill_type_id, source, tick}
            // SkillCommand schema (from /props on SharedModel.Battle.Core.Commands.SkillCommand):
            //   - SkillTypeId (Int32)
            //   - Producer (BattleTarget { HeroId, PlayerId })
            //   - Target (BattleTarget)
            //   - Source (SkillCommandSource enum)
            // Use C# reflection via Prop/IntProp — works on Il2Cpp wrapper types
            // where raw FindIL2CPPMethodStatic lookups fail.
            try
            {
                int bcType = IntProp(__0, "Type");
                object sc = Prop(__0, "SkillCommand");
                if (sc == null)
                {
                    string d = "{\"kind\":\"diag_cmd\",\"tick\":" + _battleCommandCount + ",\"bc_type\":" + bcType + ",\"err\":\"sc_null\"}";
                    lock (_tickLog) { if (_tickLog.Count < 3000) _tickLog.Add(d); }
                    return;
                }
                int skillId = IntProp(sc, "SkillTypeId");
                int source = IntProp(sc, "Source");
                int prodId = 0, tgtId = 0;
                object prod = Prop(sc, "Producer");
                object tgt = Prop(sc, "Target");
                if (prod != null) prodId = IntProp(prod, "HeroId");
                if (tgt != null) tgtId = IntProp(tgt, "HeroId");
                string entry = "{\"kind\":\"cast\",\"tick\":" + _battleCommandCount
                              + ",\"bc_type\":" + bcType
                              + ",\"producer_id\":" + prodId
                              + ",\"target_id\":" + tgtId
                              + ",\"skill_type_id\":" + skillId
                              + ",\"source\":" + source + "}";
                lock (_tickLog) { if (_tickLog.Count < 3000) _tickLog.Add(entry); }
            }
            catch (Exception ex)
            {
                string d = "{\"kind\":\"diag_cmd\",\"tick\":" + _battleCommandCount + ",\"err\":\"" + Esc(ex.Message) + "\"}";
                lock (_tickLog) { if (_tickLog.Count < 3000) _tickLog.Add(d); }
            }

            try
            {
                if (__0 == null) return;
                IntPtr cmdPtr = IntPtr.Zero;
                if (__0 is Il2CppSystem.Object il2obj) cmdPtr = il2obj.Pointer;
                if (cmdPtr == IntPtr.Zero)
                {
                    var t = __0.GetType();
                    while (t != null)
                    {
                        var p = t.GetProperty("Pointer", BindingFlags.Public | BindingFlags.Instance);
                        if (p != null) { cmdPtr = (IntPtr)p.GetValue(__0); break; }
                        t = t.BaseType;
                    }
                }
                if (cmdPtr == IntPtr.Zero) return;

                IntPtr cmdClass = il2cpp_object_get_class(cmdPtr);
                string cmdClassName = Marshal.PtrToStringAnsi(il2cpp_class_get_name(cmdClass));

                var sb = new StringBuilder();
                sb.Append("{\"event\":\"skill_cmd\",\"turn\":" + _battleCommandCount);
                sb.Append(",\"cmd_type\":\"" + Esc(cmdClassName ?? "?") + "\"");

                // Common SkillCommand-shaped fields — probe both with current known names.
                foreach (var getter in new[] { "get_CasterTypeId", "get_Caster", "get_HeroTypeId", "get_SkillId", "get_SkillTypeId", "get_TargetsTypeId", "get_TargetTypeId", "get_SkillKindId" })
                {
                    try
                    {
                        IntPtr gm = FindIL2CPPMethodStatic(cmdClass, getter, 0);
                        if (gm == IntPtr.Zero) continue;
                        IntPtr e = IntPtr.Zero;
                        IntPtr r = il2cpp_runtime_invoke(gm, cmdPtr, IntPtr.Zero, ref e);
                        if (r == IntPtr.Zero) continue;
                        IntPtr rCls = il2cpp_object_get_class(r);
                        string rTy = Marshal.PtrToStringAnsi(il2cpp_class_get_name(rCls));
                        string field = getter.Substring(4);
                        // Boxed primitive (int/enum): read int32 at +0x10
                        if (rTy == "Int32" || rTy == "Int64" || (rTy != null && rTy.EndsWith("Id")))
                            sb.Append(",\"" + field + "\":" + Marshal.ReadInt32(r + 0x10));
                        else
                            sb.Append(",\"" + field + "_type\":\"" + Esc(rTy ?? "?") + "\"");
                    }
                    catch { }
                }

                // If we haven't captured command props yet, do a one-shot schema dump
                if (!_skillCmdDiagLogged)
                {
                    _skillCmdDiagLogged = true;
                    var cp = new List<string>();
                    IntPtr kC = cmdClass;
                    while (kC != IntPtr.Zero && cp.Count < 40)
                    {
                        IntPtr mIter = IntPtr.Zero; IntPtr m;
                        while ((m = il2cpp_class_get_methods(kC, ref mIter)) != IntPtr.Zero)
                        {
                            string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                            if (mn != null && mn.StartsWith("get_") && il2cpp_method_get_param_count(m) == 0)
                                cp.Add(mn.Substring(4));
                        }
                        kC = il2cpp_class_get_parent(kC);
                        string pnC = kC != IntPtr.Zero ? Marshal.PtrToStringAnsi(il2cpp_class_get_name(kC)) : "";
                        if (pnC == "Object" || pnC == "Il2CppObjectBase" || string.IsNullOrEmpty(pnC)) break;
                    }
                    sb.Append(",\"cmd_props\":[");
                    for (int i = 0; i < cp.Count; i++) { if (i>0) sb.Append(","); sb.Append("\""+Esc(cp[i])+"\""); }
                    sb.Append("]");
                }

                sb.Append("}");
                lock (_battleLog)
                {
                    if (_battleLog.Count < 2000) _battleLog.Add(sb.ToString());
                }
                // Next poll must include a fresh heroes snapshot
                _lastStatsLogTurn = -1;
            }
            catch { }
        }

        private static int _hookDiag_StartTurn = 0;
        private static int _hookDiag_StartBattle = 0;
        private static int _hookDiag_ApplySkill = 0;
        // Patch outcomes: which hook names attached, which failed, with reasons
        internal static readonly List<string> _hookPatchLog = new();

        private string GetHookDiag()
        {
            var sb = new StringBuilder();
            sb.Append("{\"fires\":{\"StartBattle\":" + _hookDiag_StartBattle
                     + ",\"StartTurn\":" + _hookDiag_StartTurn
                     + ",\"ApplySkill\":" + _hookDiag_ApplySkill
                     + ",\"ApplyCommand\":" + _hookDiag_ApplyCommand
                     + ",\"DamageChange\":" + _hookDiag_DamageChange
                     + ",\"ApplyStatus\":" + _hookDiag_ApplyStatus
                     + ",\"RemoveStatus\":" + _hookDiag_RemoveStatus
                     + ",\"DurationChange\":" + _hookDiag_DurationChange
                     + ",\"TurnLeftSet\":" + _hookDiag_TurnLeftSet
                     + ",\"BeforeStartTurn\":" + _hookDiag_BeforeStartTurn
                     + ",\"UnapplyExecute\":" + _hookDiag_UnapplyExecute + "}");
            sb.Append(",\"cmd_classes\":{");
            lock (_applyCmdClasses)
            {
                int i = 0;
                foreach (var kv in _applyCmdClasses)
                {
                    if (i > 0) sb.Append(",");
                    sb.Append("\"" + Esc(kv.Key) + "\":" + kv.Value);
                    i++;
                }
            }
            sb.Append("}");
            sb.Append(",\"patches\":[");
            lock (_hookPatchLog)
            {
                for (int i = 0; i < _hookPatchLog.Count; i++)
                {
                    if (i > 0) sb.Append(",");
                    sb.Append("\"" + Esc(_hookPatchLog[i]) + "\"");
                }
            }
            sb.Append("]}");
            return sb.ToString();
        }

        // Per-tick TM log, populated inside BattleHook_ProcessStartTurn. Each
        // entry is one turn-start event with TM + turn_n for every unit at
        // that exact moment — ground truth for sim calibration. Kept small
        // (just ids, tm, turn_n — no skills, stats, effects).
        internal static readonly List<string> _tickLog = new();

        public static void BattleHook_ProcessStartTurn(object __instance)
        {
            _activeBattleProcessor = __instance;
            _battleCommandCount++;
            if (++_hookDiag_StartTurn <= 5 || _hookDiag_StartTurn % 20 == 0)
                BepInEx.Logging.Logger.CreateLogSource("CBHookDiag").LogInfo("ProcessStartTurn fired (count=" + _hookDiag_StartTurn + ")");

            // Capture per-tick TM + turn_n snapshot of all units. Wrapped in
            // try/catch so hook failures never crash the game; the fallback
            // is the simpler log entry below.
            try
            {
                IntPtr procPtrTM = IntPtr.Zero;
                if (__instance is Il2CppSystem.Object ilo) procPtrTM = ilo.Pointer;
                if (procPtrTM != IntPtr.Zero)
                {
                    // Teams live on processor.State, NOT processor.Context (the working
                    // ReadBattleHeroesIL2CPP path uses get_State — mirror it here).
                    IntPtr stateObj = IntPtr.Zero;
                    IntPtr getState = FindIL2CPPMethodStatic(il2cpp_object_get_class(procPtrTM), "get_State", 0);
                    if (getState != IntPtr.Zero) { IntPtr eS = IntPtr.Zero; stateObj = il2cpp_runtime_invoke(getState, procPtrTM, IntPtr.Zero, ref eS); }
                    if (stateObj != IntPtr.Zero)
                    {
                        var sbtl = new StringBuilder();
                        sbtl.Append("{\"tick\":" + _battleCommandCount + ",\"units\":[");
                        int uidx = 0;
                        foreach (var teamGetter in new[] { "get_PlayerTeam", "get_EnemyTeam" })
                        {
                            IntPtr getTeam = FindIL2CPPMethodStatic(il2cpp_object_get_class(stateObj), teamGetter, 0);
                            if (getTeam == IntPtr.Zero) continue;
                            IntPtr e2 = IntPtr.Zero;
                            IntPtr team = il2cpp_runtime_invoke(getTeam, stateObj, IntPtr.Zero, ref e2);
                            if (team == IntPtr.Zero) continue;
                            IntPtr getH = FindIL2CPPMethodStatic(il2cpp_object_get_class(team), "get_HeroesWithGuardian", 0);
                            if (getH == IntPtr.Zero) getH = FindIL2CPPMethodStatic(il2cpp_object_get_class(team), "get_Heroes", 0);
                            if (getH == IntPtr.Zero) continue;
                            IntPtr e3 = IntPtr.Zero;
                            IntPtr heroesColl = il2cpp_runtime_invoke(getH, team, IntPtr.Zero, ref e3);
                            if (heroesColl == IntPtr.Zero) continue;
                            // Iterate via get_Count + get_Item
                            IntPtr hClass = il2cpp_object_get_class(heroesColl);
                            IntPtr getCount = FindIL2CPPMethodStatic(hClass, "get_Count", 0);
                            IntPtr getItem = FindIL2CPPMethodStatic(hClass, "get_Item", 1);
                            if (getCount == IntPtr.Zero || getItem == IntPtr.Zero) continue;
                            IntPtr e4 = IntPtr.Zero;
                            IntPtr countRes = il2cpp_runtime_invoke(getCount, heroesColl, IntPtr.Zero, ref e4);
                            if (countRes == IntPtr.Zero) continue;
                            int count = Marshal.ReadInt32(countRes + 0x10);
                            string side = teamGetter == "get_PlayerTeam" ? "p" : "e";
                            for (int i = 0; i < count && i < 10; i++)
                            {
                                IntPtr intBuf = Marshal.AllocHGlobal(4); Marshal.WriteInt32(intBuf, i);
                                IntPtr argsArr = Marshal.AllocHGlobal(IntPtr.Size); Marshal.WriteIntPtr(argsArr, intBuf);
                                IntPtr e5 = IntPtr.Zero;
                                IntPtr heroObj = il2cpp_runtime_invoke(getItem, heroesColl, argsArr, ref e5);
                                Marshal.FreeHGlobal(intBuf); Marshal.FreeHGlobal(argsArr);
                                if (heroObj == IntPtr.Zero) continue;
                                IntPtr hc = il2cpp_object_get_class(heroObj);
                                int id = 0, turnN = 0;
                                long tmRaw = 0;
                                IntPtr getId = FindIL2CPPMethodStatic(hc, "get_Id", 0);
                                if (getId != IntPtr.Zero) { IntPtr e6 = IntPtr.Zero; IntPtr r = il2cpp_runtime_invoke(getId, heroObj, IntPtr.Zero, ref e6); if (r != IntPtr.Zero) id = Marshal.ReadInt32(r + 0x10); }
                                // Stamina (TM) at offset 0x58+ via get_Stamina — returns Fixed (32.32)
                                IntPtr getStam = FindIL2CPPMethodStatic(hc, "get_Stamina", 0);
                                if (getStam != IntPtr.Zero) { IntPtr e7 = IntPtr.Zero; IntPtr r = il2cpp_runtime_invoke(getStam, heroObj, IntPtr.Zero, ref e7); if (r != IntPtr.Zero) tmRaw = Marshal.ReadInt64(r + 0x10); }
                                // TurnCount @ 0xE8
                                turnN = Marshal.ReadInt32(heroObj + 0xE8);
                                long tmDisplay = tmRaw >> 32;  // 32.32 fixed → display
                                if (uidx > 0) sbtl.Append(",");
                                sbtl.Append("{\"s\":\"" + side + "\",\"id\":" + id + ",\"tm\":" + tmDisplay + ",\"tn\":" + turnN);
                                // Read AppliedEffectsByHeroes dict pointer directly from field offset 0x108
                                // (getter is inlined by IL2CPP AOT — field offset found via Il2CppDumper against GameAssembly.dll).
                                // Dict is Dictionary<int, List<AppliedEffect>>; iterate via get_Values on raw pointer.
                                try
                                {
                                    // Walk Dictionary<int, List<AppliedEffect>> via pure memory reads.
                                    // Struct layouts extracted from Il2CppDumper output (il2cpp.h):
                                    //   Dictionary fields: _buckets@0x10, _entries@0x18, _count@0x20
                                    //   Entry: hashCode(4) next(4) key_int(4) pad(4) value_ptr(8) = 24 bytes
                                    //   Array header: 0x20 bytes, items start at +0x20
                                    //   List<T>: _items@0x10, _size@0x18
                                    //   AppliedEffect: Id@0x10 ProducerId@0x14 SkillTypeId@0x28 EffectTypeId@0x38 TurnLeft@0x48
                                    // Batch lookups across multiple runtime-populated collections on BattleHero.
                                    // Offsets confirmed via Il2CppDumper output (dump.cs) against GameAssembly.dll.
                                    //   _appliedStatModifications @ 0xB0 (List<StatModification>) — stat buffs/debuffs
                                    //   AbsorbedDamageByEffectKindId @ 0x68 (Dictionary<int, Fixed>) — active shield/absorb
                                    //   AppliedEffectsByHeroes @ 0x108 (Dictionary, serialization-only, stays null)
                                    //   PhaseEffects @ 0xF0, Challenges @ 0xE0, PassiveBonuses @ 0x110

                                    // AbsorbedDamageByEffectKindId: dict count gives us active shield/block count
                                    try
                                    {
                                        IntPtr absDict = Marshal.ReadIntPtr(heroObj + 0x68);
                                        if ((long)absDict > 0x10000)
                                        {
                                            int absCount = Marshal.ReadInt32(absDict + 0x20);
                                            if (absCount > 0 && absCount < 20)
                                                sbtl.Append(",\"abs\":" + absCount);
                                        }
                                    } catch { }

                                    IntPtr smList = Marshal.ReadIntPtr(heroObj + 0xB0);
                                    if ((long)smList > 0x10000)
                                    {
                                        IntPtr smItems = Marshal.ReadIntPtr(smList + 0x10);
                                        int smSize = Marshal.ReadInt32(smList + 0x18);
                                        sbtl.Append(",\"sm\":" + smSize);
                                        if ((long)smItems > 0x10000 && smSize > 0 && smSize < 100)
                                        {
                                            sbtl.Append(",\"smods\":[");
                                            IntPtr smBase = smItems + 0x20;
                                            for (int sIdx = 0; sIdx < smSize && sIdx < 50; sIdx++)
                                            {
                                                IntPtr sm = Marshal.ReadIntPtr(smBase + (sIdx * 8));
                                                if ((long)sm <= 0x10000) continue;
                                                IntPtr fromHero = Marshal.ReadIntPtr(sm + 0x10);
                                                int fromHeroId = 0;
                                                if ((long)fromHero > 0x10000) fromHeroId = Marshal.ReadInt32(fromHero + 0x1C);
                                                int statKind = Marshal.ReadInt32(sm + 0x18);
                                                int modType = Marshal.ReadInt32(sm + 0x1C);
                                                long valRaw = Marshal.ReadInt64(sm + 0x20);
                                                long valDisp = valRaw >> 32;
                                                if (sIdx > 0) sbtl.Append(",");
                                                sbtl.Append("{\"from\":" + fromHeroId + ",\"st\":" + statKind + ",\"ty\":" + modType + ",\"v\":" + valDisp + "}");
                                            }
                                            sbtl.Append("]");
                                        }
                                    }
                                    // Read applied effects from HeroState.AppliedEffects (List<AppliedEffect>)
                                    //   BattleHero._heroState @ 0xC0
                                    //   HeroState.AppliedEffects @ 0x38, AppliedBuffs @ 0x58, AppliedDebuffs @ 0x60
                                    //   List<T>: _items@0x10, _size@0x18; Array header 0x20, items at +0x20
                                    //   AppliedEffect: Id@0x10 ProducerId@0x14 SkillTypeId@0x28 EffectTypeId@0x38
                                    //     ApplyTurn@0x40 Lifetime@0x44 TurnLeft@0x48
                                    IntPtr hstate = Marshal.ReadIntPtr(heroObj + 0xC0);
                                    if ((long)hstate > 0x10000)
                                    {
                                        sbtl.Append(",\"hs\":1");
                                        foreach (var (fname, offL) in new[] {
                                            ("ae", 0x38), ("bf", 0x58), ("db", 0x60)
                                        })
                                        {
                                            IntPtr listObj = Marshal.ReadIntPtr(hstate + offL);
                                            if ((long)listObj <= 0x10000) continue;
                                            int listSize = Marshal.ReadInt32(listObj + 0x18);
                                            if (listSize <= 0 || listSize > 100) { sbtl.Append(",\"" + fname + "_n\":" + listSize); continue; }
                                            IntPtr listItems = Marshal.ReadIntPtr(listObj + 0x10);
                                            if ((long)listItems <= 0x10000) continue;
                                            sbtl.Append(",\"" + fname + "\":[");
                                            IntPtr itemsBase = listItems + 0x20;
                                            for (int li = 0; li < listSize && li < 50; li++)
                                            {
                                                IntPtr eff = Marshal.ReadIntPtr(itemsBase + (li * 8));
                                                if ((long)eff <= 0x10000) continue;
                                                int effId = Marshal.ReadInt32(eff + 0x10);
                                                int pid = Marshal.ReadInt32(eff + 0x14);
                                                int stid = Marshal.ReadInt32(eff + 0x28);
                                                int etype = Marshal.ReadInt32(eff + 0x38);
                                                int aTurn = Marshal.ReadInt32(eff + 0x40);
                                                int life = Marshal.ReadInt32(eff + 0x44);
                                                int tleft = Marshal.ReadInt32(eff + 0x48);
                                                if (li > 0) sbtl.Append(",");
                                                sbtl.Append("{\"id\":" + effId + ",\"t\":" + etype + ",\"tl\":" + tleft
                                                    + ",\"l\":" + life + ",\"at\":" + aTurn + ",\"p\":" + pid + ",\"s\":" + stid + "}");
                                            }
                                            sbtl.Append("]");
                                        }
                                    }
                                    else
                                    {
                                        sbtl.Append(",\"hs\":0");
                                    }
                                }
                                catch (Exception exAe) { sbtl.Append(",\"ae_err\":\"" + Esc(exAe.Message) + "\""); }

                                sbtl.Append("}");
                                uidx++;
                            }
                        }
                        sbtl.Append("]}");
                        lock (_tickLog)
                        {
                            if (_tickLog.Count < 3000)
                                _tickLog.Add(sbtl.ToString());
                        }
                    }
                }
            }
            catch { }

            // Dump every hero's state booleans (HeroState) + active effect IDs
            // (StatImpactByEffects.EffectIds) via C# reflection. Much more reliable
            // than iterating AppliedEffectsByHeroes which failed silently.
            // Python diffs consecutive snapshots to detect expiry/removal precisely.
            try
            {
                var sbe = new StringBuilder();
                sbe.Append("{\"kind\":\"effects_snapshot\",\"tick\":" + _battleCommandCount + ",\"heroes\":[");
                int nH = 0;
                var stateE = Prop(__instance, "State");
                if (stateE != null)
                {
                    foreach (var teamGetter in new[] { "PlayerTeam", "EnemyTeam" })
                    {
                        var team = Prop(stateE, teamGetter);
                        if (team == null) continue;
                        var heroes = Prop(team, "HeroesWithGuardian") ?? Prop(team, "Heroes");
                        if (heroes == null) continue;
                        int count = IntProp(heroes, "Count");
                        var idxer = heroes.GetType().GetProperty("Item");
                        for (int i = 0; i < count && i < 10; i++)
                        {
                            object hero = null;
                            try { hero = idxer?.GetValue(heroes, new object[] { i }); } catch { }
                            if (hero == null) continue;
                            int hid = IntProp(hero, "Id");
                            // Core state booleans (from HeroState)
                            var hs = Prop(hero, "_heroState") ?? Prop(hero, "State");
                            if (nH > 0) sbe.Append(",");
                            sbe.Append("{\"h\":" + hid);
                            if (hs != null)
                            {
                                foreach (var bk in new[] { "IsStunned", "IsFrozen", "IsSleep", "IsProvoked",
                                    "IsInvincible", "IsBlockDebuff", "IsBlockHeal", "IsDead",
                                    "IsStrongInvisible", "IsWeakInvisible", "IsBurning",
                                    "IsUnderPoisonCloud", "IsTaunt" })
                                {
                                    try
                                    {
                                        var v = Prop(hs, bk);
                                        if (v is bool bv && bv) sbe.Append(",\"" + bk + "\":true");
                                    }
                                    catch { }
                                }
                            }
                            // Try multiple paths to find applied-effects list
                            object aeByH = Prop(hero, "AppliedEffectsByHeroes");
                            if (aeByH == null)
                            {
                                // Fall back to backing field via direct reflection
                                try
                                {
                                    var f = hero.GetType().GetField("_AppliedEffectsByHeroes_k__BackingField", BindingFlags.Instance | BindingFlags.NonPublic);
                                    if (f != null) aeByH = f.GetValue(hero);
                                }
                                catch { }
                            }
                            int dictCount = aeByH != null ? IntProp(aeByH, "Count") : -1;
                            sbe.Append(",\"ae_dict_count\":" + dictCount);
                            if (aeByH != null && dictCount > 0)
                            {
                                sbe.Append(",\"effs\":[");
                                int ne = 0;
                                try
                                {
                                    foreach (var list in DictValues(aeByH))
                                    {
                                        if (list == null) continue;
                                        foreach (var eff in ListItems(list))
                                        {
                                            int et = IntProp(eff, "EffectTypeId");
                                            int tl = IntProp(eff, "TurnLeft");
                                            int pid = IntProp(eff, "ProducerId");
                                            int eid = IntProp(eff, "Id");
                                            if (ne > 0) sbe.Append(",");
                                            sbe.Append("{\"id\":" + eid + ",\"t\":" + et + ",\"tl\":" + tl + ",\"pid\":" + pid + "}");
                                            ne++;
                                            if (ne >= 30) break;
                                        }
                                        if (ne >= 30) break;
                                    }
                                }
                                catch { }
                                sbe.Append("]");
                            }
                            // Also dump _appliedStatModifications — this is a List<AppliedStatModification>
                            // which at least gives us stat-modifying effects (DefDown, Weaken, etc.)
                            try
                            {
                                var asmField = hero.GetType().GetField("_appliedStatModifications", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
                                if (asmField != null)
                                {
                                    var asm = asmField.GetValue(hero);
                                    if (asm != null)
                                    {
                                        int asmCount = IntProp(asm, "Count");
                                        sbe.Append(",\"asm_count\":" + asmCount);
                                    }
                                }
                            }
                            catch { }
                            sbe.Append("}");
                            nH++;
                        }
                    }
                }
                sbe.Append("]}");
                lock (_tickLog) { if (_tickLog.Count < 3000) _tickLog.Add(sbe.ToString()); }
            }
            catch { }

            try
            {
                // Get pointer
                IntPtr procPtr = IntPtr.Zero;
                if (__instance is Il2CppSystem.Object il2obj) procPtr = il2obj.Pointer;
                if (procPtr == IntPtr.Zero)
                {
                    var t = __instance.GetType();
                    while (t != null)
                    {
                        var p = t.GetProperty("Pointer", BindingFlags.Public | BindingFlags.Instance);
                        if (p != null) { procPtr = (IntPtr)p.GetValue(__instance); break; }
                        t = t.BaseType;
                    }
                }

                // Get ActiveHeroId
                int activeHeroId = 0;
                if (procPtr != IntPtr.Zero)
                {
                    IntPtr ctxObj = IntPtr.Zero;
                    IntPtr getCtx = FindIL2CPPMethodStatic(il2cpp_object_get_class(procPtr), "get_Context", 0);
                    if (getCtx != IntPtr.Zero) { IntPtr e = IntPtr.Zero; ctxObj = il2cpp_runtime_invoke(getCtx, procPtr, IntPtr.Zero, ref e); }
                    if (ctxObj != IntPtr.Zero)
                    {
                        IntPtr getAHI = FindIL2CPPMethodStatic(il2cpp_object_get_class(ctxObj), "get_ActiveHeroId", 0);
                        if (getAHI != IntPtr.Zero) { IntPtr e = IntPtr.Zero; IntPtr r = il2cpp_runtime_invoke(getAHI, ctxObj, IntPtr.Zero, ref e); if (r != IntPtr.Zero) activeHeroId = Marshal.ReadInt32(r + 0x10); }
                    }
                }

                lock (_battleLog)
                {
                    if (_battleLog.Count < 2000)
                        _battleLog.Add("{\"turn\":" + _battleCommandCount + ",\"active_hero\":" + activeHeroId + ",\"ptr\":" + (procPtr != IntPtr.Zero ? 1 : 0) + "}");
                }
            }
            catch { }
        }

        // Static version of FindIL2CPPMethod for use in static hooks
        private static IntPtr FindIL2CPPMethodStatic(IntPtr klass, string methodName, uint paramCount)
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

        internal static RaidAutomationPlugin Instance;

        /// <summary>
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

        private string ReadBattleHeroesIL2CPP_OLD(IntPtr processorPtr)
        {
            return null;
#if false
            try
            {
                IntPtr heroesObj = IntPtr.Zero;
                if (heroesObj == IntPtr.Zero) return null;

                // heroesObj is a List<BattleHero> — iterate via get_Count + get_Item
                IntPtr heroesClass = il2cpp_object_get_class(heroesObj);
                IntPtr getCount = FindIL2CPPMethod(heroesClass, "get_Count", 0);
                IntPtr getItem = FindIL2CPPMethod(heroesClass, "get_Item", 1);

                if (getCount == IntPtr.Zero || getItem == IntPtr.Zero) return null;

                IntPtr exc = IntPtr.Zero;
                IntPtr countResult = il2cpp_runtime_invoke(getCount, heroesObj, IntPtr.Zero, ref exc);
                if (countResult == IntPtr.Zero) return null;
                int count = Marshal.ReadInt32(countResult + 0x10); // unbox int from Il2CppObject (data at +0x10)

                var sb = new StringBuilder();
                sb.Append("[");
                for (int i = 0; i < count && i < 20; i++)
                {
                    if (i > 0) sb.Append(",");
                    sb.Append("{");
                    try
                    {
                        // Call get_Item(i) — need to box the int argument
                        IntPtr argPtr = Marshal.AllocHGlobal(IntPtr.Size);
                        Marshal.WriteIntPtr(argPtr, countResult); // reuse as template, overwrite value
                        // Actually, il2cpp_runtime_invoke for methods with args needs IntPtr* array
                        // pointing to the argument values. For int, point to a 4-byte int.
                        IntPtr intBuf = Marshal.AllocHGlobal(4);
                        Marshal.WriteInt32(intBuf, i);
                        IntPtr argsArr = Marshal.AllocHGlobal(IntPtr.Size);
                        Marshal.WriteIntPtr(argsArr, intBuf);

                        IntPtr exc2 = IntPtr.Zero;
                        IntPtr heroObj = il2cpp_runtime_invoke(getItem, heroesObj, argsArr, ref exc2);

                        Marshal.FreeHGlobal(intBuf);
                        Marshal.FreeHGlobal(argsArr);

                        if (heroObj == IntPtr.Zero) { sb.Append("\"null\":true}"); continue; }

                        // Read hero fields
                        IntPtr heroClass = il2cpp_object_get_class(heroObj);
                        string heroClassName = Marshal.PtrToStringAnsi(il2cpp_class_get_name(heroClass));

                        // TypeId
                        IntPtr getTypeId = FindIL2CPPMethod(heroClass, "get_TypeId", 0);
                        int typeId = 0;
                        if (getTypeId != IntPtr.Zero)
                        {
                            IntPtr exc3 = IntPtr.Zero;
                            IntPtr tidResult = il2cpp_runtime_invoke(getTypeId, heroObj, IntPtr.Zero, ref exc3);
                            if (tidResult != IntPtr.Zero) typeId = Marshal.ReadInt32(tidResult + 0x10);
                        }
                        sb.Append("\"type_id\":" + typeId);

                        // TurnCount
                        IntPtr getTurnCount = FindIL2CPPMethod(heroClass, "get_TurnCount", 0);
                        if (getTurnCount != IntPtr.Zero)
                        {
                            IntPtr exc3 = IntPtr.Zero;
                            IntPtr tcResult = il2cpp_runtime_invoke(getTurnCount, heroObj, IntPtr.Zero, ref exc3);
                            if (tcResult != IntPtr.Zero) sb.Append(",\"turn_count\":" + Marshal.ReadInt32(tcResult + 0x10));
                        }

                        // Health (Fixed type — toString gives the value)
                        IntPtr getHealth = FindIL2CPPMethod(heroClass, "get_Health", 0);
                        if (getHealth != IntPtr.Zero)
                        {
                            IntPtr exc3 = IntPtr.Zero;
                            IntPtr hpResult = il2cpp_runtime_invoke(getHealth, heroObj, IntPtr.Zero, ref exc3);
                            if (hpResult != IntPtr.Zero)
                            {
                                // Fixed is a struct — the invoke returns a boxed value
                                // Read the raw long at offset 0x10 and convert
                                long rawFixed = Marshal.ReadInt64(hpResult + 0x10);
                                double hp = rawFixed / 65536.0; // Fixed uses 16-bit fractional
                                sb.Append(",\"health\":" + ((int)hp));
                            }
                        }

                        // Stamina (TM)
                        IntPtr getStamina = FindIL2CPPMethod(heroClass, "get_Stamina", 0);
                        if (getStamina != IntPtr.Zero)
                        {
                            IntPtr exc3 = IntPtr.Zero;
                            IntPtr tmResult = il2cpp_runtime_invoke(getStamina, heroObj, IntPtr.Zero, ref exc3);
                            if (tmResult != IntPtr.Zero)
                            {
                                long rawFixed = Marshal.ReadInt64(tmResult + 0x10);
                                double tm = rawFixed / 65536.0;
                                sb.Append(",\"stamina\":" + ((int)tm));
                            }
                        }

                        // IsUnkillable
                        IntPtr getUK = FindIL2CPPMethod(heroClass, "get_IsUnkillable", 0);
                        if (getUK != IntPtr.Zero)
                        {
                            IntPtr exc3 = IntPtr.Zero;
                            IntPtr ukResult = il2cpp_runtime_invoke(getUK, heroObj, IntPtr.Zero, ref exc3);
                            if (ukResult != IntPtr.Zero)
                            {
                                bool uk = Marshal.ReadByte(ukResult + 0x10) != 0;
                                sb.Append(",\"is_unkillable\":" + (uk ? "true" : "false"));
                            }
                        }

                        // IsDead (via _heroState)
                        IntPtr getHeroState = FindIL2CPPMethod(heroClass, "get__heroState", 0);
                        if (getHeroState == IntPtr.Zero) getHeroState = FindIL2CPPMethod(heroClass, "get_IsDead", 0);

                        // SlotId (position)
                        IntPtr getSlot = FindIL2CPPMethod(heroClass, "get_SlotId", 0);
                        if (getSlot != IntPtr.Zero)
                        {
                            IntPtr exc3 = IntPtr.Zero;
                            IntPtr slotResult = il2cpp_runtime_invoke(getSlot, heroObj, IntPtr.Zero, ref exc3);
                            if (slotResult != IntPtr.Zero) sb.Append(",\"slot\":" + Marshal.ReadInt32(slotResult + 0x10));
                        }
                    }
                    catch { }
                    sb.Append("}");
                }
                sb.Append("]");
                return sb.ToString();
            }
            catch
            {
                return null;
            }
#endif
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

        // Cached IL2CPP method pointer for SharedLTextKeyExtension.get_LocalizedValue
        private IntPtr _localizedValueMethod = IntPtr.Zero;
        private bool _localizedValueSearched = false;

        // Debug info from last localization attempt
        private string _locDbg = "";

        /// <summary>
        /// Resolve a SharedLTextKey object to its localized string via raw IL2CPP.
        /// Finds SharedLTextKeyExtension class, calls get_LocalizedValue(key) static method.
        /// </summary>
        private string ResolveLocalizedText(object textKeyProxy)
        {
            if (textKeyProxy == null) return null;

            IntPtr textKeyPtr = IntPtr.Zero;
            try
            {
                var ptrProp = textKeyProxy.GetType().GetProperty("Pointer");
                if (ptrProp != null) textKeyPtr = (IntPtr)ptrProp.GetValue(textKeyProxy);
            }
            catch { }
            if (textKeyPtr == IntPtr.Zero) { _locDbg = "no_ptr"; return null; }

            if (!_localizedValueSearched)
            {
                _localizedValueSearched = true;
                var dbg = new System.Text.StringBuilder();
                try
                {
                    IntPtr domain = il2cpp_domain_get();
                    uint asmCount = 0;
                    IntPtr asmsPtr = il2cpp_domain_get_assemblies(domain, ref asmCount);
                    dbg.Append($"asm={asmCount};");

                    for (uint i = 0; i < asmCount; i++)
                    {
                        IntPtr asmI = Marshal.ReadIntPtr(asmsPtr, (int)(i * (uint)IntPtr.Size));
                        IntPtr image = il2cpp_assembly_get_image(asmI);
                        if (image == IntPtr.Zero) continue;

                        IntPtr ns = Marshal.StringToHGlobalAnsi("Client.Model.Common.Localization");
                        IntPtr cn = Marshal.StringToHGlobalAnsi("SharedLTextKeyExtension");
                        IntPtr klass = il2cpp_class_from_name(image, ns, cn);
                        Marshal.FreeHGlobal(ns); Marshal.FreeHGlobal(cn);

                        if (klass != IntPtr.Zero)
                        {
                            string imgN = Marshal.PtrToStringAnsi(il2cpp_image_get_name(image)) ?? "?";
                            dbg.Append($"cls_in={imgN};");
                            // Enumerate methods
                            IntPtr mIter = IntPtr.Zero; IntPtr m;
                            while ((m = il2cpp_class_get_methods(klass, ref mIter)) != IntPtr.Zero)
                            {
                                string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                                uint pc = il2cpp_method_get_param_count(m);
                                dbg.Append($"{mn}/{pc};");
                                // The extension method is GetLocalizedOrDefault (2 params: key + defaultValue)
                                // or (3 params: key + defaultValue + args). Use the 2-param version.
                                if (mn == "GetLocalizedOrDefault" && pc == 2)
                                    _localizedValueMethod = m;
                                else if (mn == "get_LocalizedValue" && pc == 1 && _localizedValueMethod == IntPtr.Zero)
                                    _localizedValueMethod = m;
                                else if (mn == "LocalizedValue" && pc == 1 && _localizedValueMethod == IntPtr.Zero)
                                    _localizedValueMethod = m;
                            }
                            if (_localizedValueMethod != IntPtr.Zero) dbg.Append("FOUND;");
                            break;
                        }
                    }
                    if (_localizedValueMethod == IntPtr.Zero) dbg.Append("NOT_FOUND;");
                }
                catch (Exception ex) { dbg.Append($"ex:{ex.Message};"); }
                _locDbg = dbg.ToString();
            }

            if (_localizedValueMethod == IntPtr.Zero) return null;

            try
            {
                // GetLocalizedOrDefault(SharedLTextKey key, string defaultValue)
                // Args array: [textKeyPtr, il2cpp_string("")]
                IntPtr defaultStr = Il2CppInterop.Runtime.IL2CPP.ManagedStringToIl2Cpp("");
                IntPtr argBuf = Marshal.AllocHGlobal(IntPtr.Size * 2);
                Marshal.WriteIntPtr(argBuf, 0, textKeyPtr);
                Marshal.WriteIntPtr(argBuf, IntPtr.Size, defaultStr);
                IntPtr exc = IntPtr.Zero;
                IntPtr result = il2cpp_runtime_invoke(_localizedValueMethod, IntPtr.Zero, argBuf, ref exc);
                Marshal.FreeHGlobal(argBuf);

                if (exc != IntPtr.Zero) { _locDbg += "exc;"; return null; }
                if (result == IntPtr.Zero) { _locDbg += "null_result;"; return null; }

                return Il2CppInterop.Runtime.IL2CPP.Il2CppStringToManaged(result);
            }
            catch (Exception ex) { _locDbg += $"call:{ex.Message};"; }
            return null;
        }

        /// <summary>
        /// Replace the heroes in an existing preset by swapping HeroId on each
        /// SkillPrioritiesSetup entry and rebuilding skill priorities from the
        /// new hero's actual skills. Works entirely with existing IL2CPP objects
        /// (no new list allocation).
        ///
        /// Usage: /set-preset-team?id=1&heroes=15120,18607,18086,4736,13575
        /// Heroes are comma-separated instance IDs, in slot order (1-5).
        /// </summary>
        private string SetPresetTeam(string idStr, string heroIdsStr)
        {
            if (string.IsNullOrEmpty(idStr) || string.IsNullOrEmpty(heroIdsStr))
                return "{\"error\":\"id and heroes required\"}";

            int targetId;
            if (!int.TryParse(idStr, out targetId)) return "{\"error\":\"invalid id\"}";

            var newHeroIds = new List<int>();
            foreach (var s in heroIdsStr.Split(','))
                if (int.TryParse(s.Trim(), out int hid) && hid > 0)
                    newHeroIds.Add(hid);
            if (newHeroIds.Count == 0) return "{\"error\":\"no valid hero IDs\"}";

            var sptEnum = FindType("SharedModel.Meta.Heroes.SkillPriorityType");
            var presetT = FindType("SharedModel.Meta.Heroes.HeroesAiPreset");
            if (sptEnum == null || presetT == null) return "{\"error\":\"types not found\"}";

            try
            {
                var uw = GetUserWrapper();
                var heroDict = Prop(Prop(Prop(uw, "Heroes"), "HeroData"), "HeroById");

                // Find the target preset
                object presetList = Prop(Prop(Prop(uw, "Heroes"), "HeroData"), "HeroesAiPresets");
                if (presetList == null) presetList = Prop(Prop(uw, "Heroes"), "HeroesAiPresets");
                if (presetList == null) return "{\"error\":\"no presets\"}";

                object targetPreset = null;
                foreach (var p in ListItems(presetList))
                {
                    if (IntProp(p, "Id") == targetId) { targetPreset = p; break; }
                }
                if (targetPreset == null) return "{\"error\":\"preset not found\"}";

                // Get the SkillPrioritiesSetups list
                object setups = null;
                var spsField = presetT.GetField("SkillPrioritiesSetups", BindingFlags.Public | BindingFlags.Instance);
                if (spsField != null) setups = spsField.GetValue(targetPreset);
                if (setups == null) { var g = presetT.GetMethod("get_SkillPrioritiesSetups"); if (g != null) setups = g.Invoke(targetPreset, null); }
                if (setups == null) return "{\"error\":\"setups null\"}";

                // Get list count and indexer
                int setupCount = 0;
                try { setupCount = (int)setups.GetType().GetProperty("Count").GetValue(setups); } catch {}

                var sb = new StringBuilder("{\"ok\":true,\"slots\":[");

                // For each slot, update the HeroId and rebuild PriorityBySkillId
                int slotIdx = 0;
                var getItem = setups.GetType().GetProperty("Item");

                foreach (var setup in ListItems(setups))
                {
                    if (slotIdx >= newHeroIds.Count) break;
                    int newHeroId = newHeroIds[slotIdx];

                    // Set HeroId
                    try
                    {
                        var setHero = setup.GetType().GetMethod("set_HeroId");
                        if (setHero != null) setHero.Invoke(setup, new object[] { newHeroId });
                        else SetFieldOrProp(setup.GetType(), setup, "HeroId", newHeroId);
                    }
                    catch {}

                    // Get new hero's skill type IDs
                    var skillIds = new List<int>();
                    try
                    {
                        object hero = null;
                        var ck = heroDict.GetType().GetMethod("ContainsKey");
                        if (ck != null && (bool)ck.Invoke(heroDict, new object[] { newHeroId }))
                            hero = heroDict.GetType().GetProperty("Item")?.GetValue(heroDict, new object[] { newHeroId });
                        if (hero != null)
                        {
                            var skills = Prop(hero, "Skills");
                            if (skills != null)
                            {
                                int cnt = (int)skills.GetType().GetProperty("Count").GetValue(skills);
                                var gi = skills.GetType().GetProperty("Item");
                                for (int i = 0; i < cnt; i++)
                                {
                                    var skill = gi?.GetValue(skills, new object[] { i });
                                    if (skill != null)
                                    {
                                        var tid = Prop(skill, "TypeId");
                                        if (tid != null) skillIds.Add((int)tid);
                                    }
                                }
                            }
                        }
                    }
                    catch {}

                    // Rebuild PriorityBySkillId dict: clear old entries, add new hero's skills
                    try
                    {
                        object priDict = null;
                        var pf = setup.GetType().GetField("PriorityBySkillId", BindingFlags.Public | BindingFlags.Instance);
                        if (pf != null) priDict = pf.GetValue(setup);
                        if (priDict == null) { var g = setup.GetType().GetMethod("get_PriorityBySkillId"); if (g != null) priDict = g.Invoke(setup, null); }

                        if (priDict != null)
                        {
                            // Clear existing entries
                            var clearM = priDict.GetType().GetMethod("Clear");
                            if (clearM != null) clearM.Invoke(priDict, null);

                            // Add new hero's skills with Default priority
                            var addM = priDict.GetType().GetMethod("Add");
                            foreach (int sid in skillIds)
                            {
                                try { addM.Invoke(priDict, new object[] { sid, Enum.ToObject(sptEnum, 0) }); } catch {}
                            }
                        }

                        // Also rebuild each Sequence's PriorityBySkillId
                        object seqs = null;
                        var sf = setup.GetType().GetField("Sequences", BindingFlags.Public | BindingFlags.Instance);
                        if (sf != null) seqs = sf.GetValue(setup);
                        if (seqs == null) { var g = setup.GetType().GetMethod("get_Sequences"); if (g != null) seqs = g.Invoke(setup, null); }
                        if (seqs != null)
                        {
                            bool firstSeq = true;
                            foreach (var seq in ListItems(seqs))
                            {
                                object seqDict = null;
                                var sqf = seq.GetType().GetField("PriorityBySkillId", BindingFlags.Public | BindingFlags.Instance);
                                if (sqf != null) seqDict = sqf.GetValue(seq);
                                if (seqDict == null) { var g = seq.GetType().GetMethod("get_PriorityBySkillId"); if (g != null) seqDict = g.Invoke(seq, null); }
                                if (seqDict != null)
                                {
                                    var clrSeq = seqDict.GetType().GetMethod("Clear");
                                    if (clrSeq != null) clrSeq.Invoke(seqDict, null);
                                    var addSeq = seqDict.GetType().GetMethod("Add");
                                    foreach (int sid in skillIds)
                                    {
                                        try { addSeq.Invoke(seqDict, new object[] { sid, Enum.ToObject(sptEnum, 0) }); } catch {}
                                    }
                                }

                                // Clear StarterSkillTypeIds on non-first sequences
                                if (!firstSeq)
                                {
                                    try
                                    {
                                        var ssi = seq.GetType().GetField("StarterSkillTypeIds", BindingFlags.Public | BindingFlags.Instance);
                                        if (ssi != null)
                                        {
                                            object starterList = ssi.GetValue(seq);
                                            if (starterList != null)
                                            {
                                                var clrStarter = starterList.GetType().GetMethod("Clear");
                                                if (clrStarter != null) clrStarter.Invoke(starterList, null);
                                            }
                                        }
                                    }
                                    catch {}
                                }
                                firstSeq = false;
                            }
                        }
                    }
                    catch {}

                    if (slotIdx > 0) sb.Append(",");
                    sb.Append("{\"slot\":" + slotIdx + ",\"hero\":" + newHeroId + ",\"skills\":[" + string.Join(",", skillIds) + "]}");
                    slotIdx++;
                }

                // Save the modified preset
                var cmdType = FindType("Client.Model.Gameplay.Heroes.Commands.SaveAiPresetCmd");
                if (cmdType != null)
                {
                    var ctor = cmdType.GetConstructor(new[] { presetT });
                    if (ctor != null)
                    {
                        var cmd = ctor.Invoke(new object[] { targetPreset });
                        InvokeExecute(cmd);
                        sb.Append("],\"saved\":true}");
                    }
                    else sb.Append("],\"saved\":false,\"reason\":\"no ctor\"}");
                }
                else sb.Append("],\"saved\":false,\"reason\":\"no cmd type\"}");

                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }


        /// <summary>
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

        private string GetMasteryData(string heroIdStr)
        {
            if (string.IsNullOrEmpty(heroIdStr))
                return "{\"error\":\"hero_id required\"}";

            int heroId;
            if (!int.TryParse(heroIdStr, out heroId))
                return "{\"error\":\"invalid hero_id\"}";

            var uw = GetUserWrapper();
            if (uw == null) return "{\"error\":\"Not logged in\"}";

            // Get hero object
            var heroDict = Prop(Prop(Prop(uw, "Heroes"), "HeroData"), "HeroById");
            if (heroDict == null) return "{\"error\":\"HeroById null\"}";

            object hero = null;
            try
            {
                var containsKey = heroDict.GetType().GetMethod("ContainsKey");
                if (containsKey != null && (bool)containsKey.Invoke(heroDict, new object[] { heroId }))
                    hero = heroDict.GetType().GetProperty("Item")?.GetValue(heroDict, new object[] { heroId });
            }
            catch { }
            if (hero == null) return "{\"error\":\"hero not found\"}";

            var sb = new StringBuilder();
            sb.Append("{\"hero_id\":" + heroId);

            // Read MasteryData
            try
            {
                var masteryData = Prop(hero, "MasteryData");
                if (masteryData != null)
                {
                    // CurrentAmount: Dict<MasteryPointType, int>
                    var current = Prop(masteryData, "CurrentAmount");
                    if (current != null)
                    {
                        sb.Append(",\"points\":{");
                        int pi = 0;
                        foreach (var (key, val) in DictEntries(current))
                        {
                            // MasteryPointType: 1=Bronze, 2=Silver, 3=Gold
                            string ptName = key == 1 ? "bronze" : (key == 2 ? "silver" : (key == 3 ? "gold" : "t" + key));
                            if (pi > 0) sb.Append(",");
                            sb.Append("\"" + ptName + "\":" + Convert.ToInt32(val));
                            pi++;
                        }
                        sb.Append("}");
                    }

                    // TotalAmount
                    var total = Prop(masteryData, "TotalAmount");
                    if (total != null)
                    {
                        sb.Append(",\"total_points\":{");
                        int ti = 0;
                        foreach (var (key, val) in DictEntries(total))
                        {
                            string ptName = key == 1 ? "bronze" : (key == 2 ? "silver" : (key == 3 ? "gold" : "t" + key));
                            if (ti > 0) sb.Append(",");
                            sb.Append("\"" + ptName + "\":" + Convert.ToInt32(val));
                            ti++;
                        }
                        sb.Append("}");
                    }

                    // Masteries list (opened mastery IDs)
                    var masteries = Prop(masteryData, "Masteries");
                    if (masteries != null)
                    {
                        sb.Append(",\"masteries\":[");
                        int mi = 0;
                        foreach (var item in ListItems(masteries))
                        {
                            if (mi > 0) sb.Append(",");
                            sb.Append(Convert.ToInt32(item));
                            mi++;
                        }
                        sb.Append("]");
                        sb.Append(",\"mastery_count\":" + mi);
                    }

                    // ResetCount
                    int resets = IntProp(masteryData, "ResetCount");
                    sb.Append(",\"reset_count\":" + resets);
                }
                else
                {
                    sb.Append(",\"mastery_data\":null");
                }
            }
            catch (Exception ex)
            {
                sb.Append(",\"error\":\"" + Esc(ex.Message) + "\"");
            }

            sb.Append("}");
            return sb.ToString();
        }

        private string OpenMastery(string heroIdStr, string masteryIdStr)
        {
            if (string.IsNullOrEmpty(heroIdStr) || string.IsNullOrEmpty(masteryIdStr))
                return "{\"error\":\"hero_id and mastery_id required\"}";

            int heroId, masteryId;
            if (!int.TryParse(heroIdStr, out heroId) || !int.TryParse(masteryIdStr, out masteryId))
                return "{\"error\":\"invalid hero_id or mastery_id\"}";

            // OpenHeroMasteryCmd takes OpenMasteryRequestDto{MasteryId, HeroId}
            var dtoType = FindType("SharedModel.Meta.Masteries.Dto.OpenMasteryRequestDto");
            var cmdType = FindType("Client.Model.Gameplay.Heroes.Commands.OpenHeroMasteryCmd");

            if (dtoType == null) return "{\"error\":\"OpenMasteryRequestDto type not found\"}";
            if (cmdType == null) return "{\"error\":\"OpenHeroMasteryCmd type not found\"}";

            try
            {
                // Create DTO — try BOTH field and property setter to ensure IL2CPP gets the value
                var dto = System.Activator.CreateInstance(dtoType);

                // Set MasteryId — try field first (IL2CPP types use public fields), then property
                var mField = dtoType.GetField("MasteryId", BindingFlags.Public | BindingFlags.Instance);
                if (mField != null) mField.SetValue(dto, masteryId);
                var setMasteryId = dtoType.GetMethod("set_MasteryId");
                if (setMasteryId != null) setMasteryId.Invoke(dto, new object[] { masteryId });

                // Set HeroId
                var hField = dtoType.GetField("HeroId", BindingFlags.Public | BindingFlags.Instance);
                if (hField != null) hField.SetValue(dto, heroId);
                var setHeroId = dtoType.GetMethod("set_HeroId");
                if (setHeroId != null) setHeroId.Invoke(dto, new object[] { heroId });

                // Verify the DTO values
                int checkM = 0, checkH = 0;
                try { checkM = (int)(mField?.GetValue(dto) ?? Prop(dto, "MasteryId") ?? 0); } catch {}
                try { checkH = (int)(hField?.GetValue(dto) ?? Prop(dto, "HeroId") ?? 0); } catch {}
                Logger.LogInfo("MASTERY: opening " + masteryId + " on hero " + heroId + " (dto check: M=" + checkM + " H=" + checkH + ")");

                // Create command
                var ctor = cmdType.GetConstructor(new[] { dtoType });
                if (ctor == null) return "{\"error\":\"OpenHeroMasteryCmd ctor not found\"}";

                var cmd = ctor.Invoke(new object[] { dto });
                InvokeExecute(cmd);

                return "{\"ok\":true,\"hero_id\":" + heroId + ",\"mastery_id\":" + masteryId + "}";
            }
            catch (TargetInvocationException tex)
            {
                var inner = tex.InnerException ?? tex;
                return "{\"error\":\"" + Esc(inner.Message) + "\"}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        private string ResetMasteries(string heroIdStr)
        {
            if (string.IsNullOrEmpty(heroIdStr))
                return "{\"error\":\"hero_id required\"}";

            int heroId;
            if (!int.TryParse(heroIdStr, out heroId))
                return "{\"error\":\"invalid hero_id\"}";

            var cmdType = FindType("Client.Model.Gameplay.Heroes.Commands.ResetHeroMasteriesCmd");
            if (cmdType == null) return "{\"error\":\"ResetHeroMasteriesCmd type not found\"}";

            try
            {
                var ctor = cmdType.GetConstructor(new[] { typeof(int) });
                if (ctor == null) return "{\"error\":\"ResetHeroMasteriesCmd ctor not found\"}";

                var cmd = ctor.Invoke(new object[] { heroId });
                InvokeExecute(cmd);

                return "{\"ok\":true,\"hero_id\":" + heroId + ",\"action\":\"reset\"}";
            }
            catch (TargetInvocationException tex)
            {
                var inner = tex.InnerException ?? tex;
                return "{\"error\":\"" + Esc(inner.Message) + "\"}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        private void InvokeExecute(object gameCmd)
        {
            // Try to enqueue through the game's CmdQueue first (proper server round-trip).
            // Falls back to direct Execute() if queue not available.
            try
            {
                var appModelType = FindType("Client.Model.AppModel");
                if (appModelType != null)
                {
                    var instProp = appModelType.GetProperty("Instance", BindingFlags.Public | BindingFlags.Static);
                    if (instProp != null)
                    {
                        object appModel = instProp.GetValue(null);
                        if (appModel != null)
                        {
                            object cmdQueue = Prop(appModel, "CmdQueue");
                            if (cmdQueue != null)
                            {
                                var enqueueM = cmdQueue.GetType().GetMethod("Enqueue");
                                if (enqueueM != null)
                                {
                                    enqueueM.Invoke(cmdQueue, new object[] { gameCmd });
                                    return;
                                }
                            }
                        }
                    }
                }
            }
            catch { }

            // Fallback: direct Execute()
            var t = gameCmd.GetType();
            while (t != null)
            {
                foreach (var m in t.GetMethods(BindingFlags.Instance | BindingFlags.Public |
                                                BindingFlags.NonPublic | BindingFlags.DeclaredOnly))
                {
                    if (m.Name == "Execute" && m.GetParameters().Length == 0)
                    {
                        m.Invoke(gameCmd, null);
                        return;
                    }
                }
                t = t.BaseType;
            }
            throw new Exception("Execute method not found on " + gameCmd.GetType().Name);
        }

        private string DoSwap(int heroId, int ownerId, int fromId, int toId)
        {
            var cmdType = FindType("Client.Model.Gameplay.Artifacts.Commands.SwapArtifactCmd");
            if (cmdType == null) return "{\"error\":\"SwapArtifactCmd type not found\"}";

            var ctor = cmdType.GetConstructor(new[] { typeof(int), typeof(int), typeof(int), typeof(int) });
            if (ctor == null) return "{\"error\":\"SwapArtifactCmd ctor not found\"}";

            try
            {
                var cmd = ctor.Invoke(new object[] { heroId, ownerId, fromId, toId });
                InvokeExecute(cmd);
                return "{\"ok\":true,\"action\":\"swap\",\"hero_id\":" + heroId +
                       ",\"from\":" + fromId + ",\"to\":" + toId + "}";
            }
            catch (TargetInvocationException tex)
            {
                return "{\"error\":\"" + Esc((tex.InnerException ?? tex).Message) + "\"}";
            }
        }

        private string BulkEquipArtifacts(string heroIdStr, string artifactsJson)
        {
            if (string.IsNullOrEmpty(heroIdStr) || string.IsNullOrEmpty(artifactsJson))
                return "{\"error\":\"hero_id and artifacts required\"}";

            int heroId;
            if (!int.TryParse(heroIdStr, out heroId))
                return "{\"error\":\"invalid hero_id\"}";

            var uw = GetUserWrapper();
            if (uw == null) return "{\"error\":\"Not logged in\"}";
            var equipment = Prop(uw, "Artifacts");
            if (equipment == null) return "{\"error\":\"EquipmentWrapper null\"}";

            var oneMethod = equipment.GetType().GetMethod("One");
            if (oneMethod == null) return "{\"error\":\"One method not found\"}";

            // Parse artifact IDs
            var ids = new List<int>();
            try
            {
                var cleaned = artifactsJson.Trim().TrimStart('[').TrimEnd(']');
                foreach (var s in cleaned.Split(','))
                {
                    if (int.TryParse(s.Trim(), out int id) && id > 0)
                        ids.Add(id);
                }
            }
            catch { return "{\"error\":\"failed to parse artifacts array\"}"; }

            if (ids.Count == 0) return "{\"error\":\"no artifact IDs provided\"}";

            var activateCmdType = FindType("Client.Model.Gameplay.Artifacts.Commands.ActivateArtifactCmd");
            var swapCmdType = FindType("Client.Model.Gameplay.Artifacts.Commands.SwapArtifactCmd");

            var sb = new StringBuilder();
            sb.Append("{\"bulk\":true,\"hero_id\":" + heroId + ",\"results\":[");
            int equipped = 0;

            foreach (int artId in ids)
            {
                if (equipped > 0) sb.Append(",");
                try
                {
                    object artifact = oneMethod.Invoke(equipment, new object[] { artId });
                    if (artifact == null) { sb.Append("{\"id\":" + artId + ",\"error\":\"not found\"}"); continue; }

                    int artKind = IntProp(artifact, "KindId");
                    int existingArtId = GetEquippedArtifactId(equipment, heroId, artKind);

                    if (existingArtId == artId)
                    {
                        sb.Append("{\"id\":" + artId + ",\"action\":\"already\"}");
                        equipped++;
                        continue;
                    }

                    if (existingArtId > 0)
                    {
                        // Slot occupied — use SwapArtifactCmd
                        int ownerId = GetArtifactOwner(equipment, artId);
                        if (ownerId <= 0) ownerId = heroId;
                        if (swapCmdType != null)
                        {
                            var ctor = swapCmdType.GetConstructor(new[] { typeof(int), typeof(int), typeof(int), typeof(int) });
                            if (ctor != null)
                            {
                                var cmd = ctor.Invoke(new object[] { heroId, ownerId, existingArtId, artId });
                                InvokeExecute(cmd);
                                sb.Append("{\"id\":" + artId + ",\"action\":\"swap\",\"replaced\":" + existingArtId + "}");
                            }
                        }
                    }
                    else
                    {
                        // Empty slot — use ActivateArtifactCmd
                        if (activateCmdType != null)
                        {
                            var ctor = activateCmdType.GetConstructor(new[] { typeof(int), typeof(int) });
                            if (ctor != null)
                            {
                                var cmd = ctor.Invoke(new object[] { heroId, artId });
                                InvokeExecute(cmd);
                                sb.Append("{\"id\":" + artId + ",\"action\":\"activate\"}");
                            }
                        }
                    }
                    equipped++;
                }
                catch (Exception ex)
                {
                    var msg = ex is TargetInvocationException tex ? (tex.InnerException?.Message ?? ex.Message) : ex.Message;
                    sb.Append("{\"id\":" + artId + ",\"error\":\"" + Esc(msg) + "\"}");
                }
            }

            sb.Append("],\"equipped\":" + equipped + "}");
            return sb.ToString();
        }

        // Helper: find which artifact ID is equipped on a hero in a given slot
        private int GetEquippedArtifactId(object equipment, int heroId, int slotKind)
        {
            try
            {
                var artData = Prop(equipment, "ArtifactData");
                if (artData == null) return 0;
                var byHeroDict = Prop(artData, "ArtifactDataByHeroId");
                if (byHeroDict == null) return 0;

                var containsKey = byHeroDict.GetType().GetMethod("ContainsKey");
                if (containsKey == null || !(bool)containsKey.Invoke(byHeroDict, new object[] { heroId }))
                    return 0;

                var heroArtData = byHeroDict.GetType().GetProperty("Item")?.GetValue(byHeroDict, new object[] { heroId });
                if (heroArtData == null) return 0;

                var idByKind = Prop(heroArtData, "ArtifactIdByKind");
                if (idByKind == null) return 0;

                // ArtifactKindId is an enum — convert slotKind int to enum
                var kindType = FindType("SharedModel.Meta.Artifacts.ArtifactKindId");
                object kindEnum = slotKind;
                if (kindType != null)
                    try { kindEnum = Enum.ToObject(kindType, slotKind); } catch { }

                var containsSlot = idByKind.GetType().GetMethod("ContainsKey");
                if (containsSlot != null && (bool)containsSlot.Invoke(idByKind, new object[] { kindEnum }))
                {
                    var artIdObj = idByKind.GetType().GetProperty("Item")?.GetValue(idByKind, new object[] { kindEnum });
                    if (artIdObj != null) return Convert.ToInt32(artIdObj);
                }
            }
            catch { }
            return 0;
        }

        // Helper: find which hero owns a given artifact (0 = in vault)
        private int GetArtifactOwner(object equipment, int artifactId)
        {
            try
            {
                var artData = Prop(equipment, "ArtifactData");
                if (artData == null) return 0;
                var byHeroDict = Prop(artData, "ArtifactDataByHeroId");
                if (byHeroDict == null) return 0;

                foreach (var (heroId, heroArtData) in DictEntries(byHeroDict))
                {
                    if (heroArtData == null) continue;
                    var idByKind = Prop(heroArtData, "ArtifactIdByKind");
                    if (idByKind == null) continue;

                    foreach (var val in DictValues(idByKind))
                    {
                        try
                        {
                            if (Convert.ToInt32(val) == artifactId) return heroId;
                        }
                        catch { }
                    }
                }
            }
            catch { }
            return 0;
        }

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

        // =====================================================
        // API: /resources — energy, silver, gems, arena tokens, CB keys, etc.
        // =====================================================

        private string GetResources()
        {
            var uw = GetUserWrapper();
            if (uw == null) return "{\"error\":\"Not logged in\"}";

            var sb = new StringBuilder(1024);
            sb.Append("{");

            try
            {
                // Navigate: UserWrapper -> Account -> AccountData -> Resources -> RawValues (Dict<ResourceTypeId, double>)
                var account = Prop(uw, "Account");
                if (account == null)
                    return "{\"error\":\"Account wrapper not found on UserWrapper\"}";

                // Try AccountData or Data property
                var accountData = Prop(account, "AccountData");
                if (accountData == null) accountData = Prop(account, "Data");
                if (accountData == null)
                {
                    // Fallback: search all properties on account for something with Resources
                    foreach (var p in account.GetType().GetProperties(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic))
                    {
                        try
                        {
                            if (p.Name.Contains("Data") || p.Name.Contains("Account"))
                            {
                                var candidate = p.GetValue(account);
                                if (candidate != null && Prop(candidate, "Resources") != null)
                                {
                                    accountData = candidate;
                                    break;
                                }
                            }
                        }
                        catch { }
                    }
                }
                if (accountData == null)
                    return "{\"error\":\"AccountData not found. Account type: " + Esc(account.GetType().FullName) + "\"}";

                var resources = Prop(accountData, "Resources");
                if (resources == null)
                    return "{\"error\":\"Resources not found on AccountData. Type: " + Esc(accountData.GetType().FullName) + "\"}";

                // Get RawValues dictionary — Dict<ResourceTypeId, double> or similar
                var rawValues = Prop(resources, "RawValues");
                if (rawValues == null) rawValues = Prop(resources, "Values");
                if (rawValues == null) rawValues = Prop(resources, "Data");

                // ResourceTypeId constants (from memory_reader.py)
                // 1=Energy, 2=Silver, 3=ArenaToken, 4=Gem, 6=Arena3x3, 7=LiveArena, 300=CBKey, 400=AutoTicket
                var resourceNames = new Dictionary<int, string>
                {
                    { 1, "energy" }, { 2, "silver" }, { 3, "arena_tokens" }, { 4, "gems" },
                    { 6, "arena_3x3_tokens" }, { 7, "live_arena_tokens" },
                    { 300, "cb_keys" }, { 400, "auto_tickets" }
                };

                if (rawValues != null)
                {
                    // Iterate the dictionary via reflection
                    int found = 0;
                    try
                    {
                        var getEnum = rawValues.GetType().GetMethod("GetEnumerator");
                        if (getEnum != null)
                        {
                            var enumerator = getEnum.Invoke(rawValues, null);
                            var enumType = enumerator.GetType();
                            var moveNext = enumType.GetMethod("MoveNext");
                            var current = enumType.GetProperty("Current");

                            while ((bool)moveNext.Invoke(enumerator, null))
                            {
                                var kvp = current.GetValue(enumerator);
                                var key = Prop(kvp, "Key");
                                var val = Prop(kvp, "Value");
                                if (key == null || val == null) continue;

                                int keyInt = Convert.ToInt32(key);
                                double valDbl = Convert.ToDouble(val.ToString());

                                string name;
                                if (!resourceNames.TryGetValue(keyInt, out name))
                                    name = "resource_" + keyInt;

                                if (found > 0) sb.Append(",");
                                sb.Append("\"" + name + "\":" + valDbl.ToString("F0"));
                                found++;
                            }
                        }
                    }
                    catch (Exception dictEx)
                    {
                        sb.Append("\"dict_error\":\"" + Esc(dictEx.Message) + "\"");
                    }

                    if (found == 0)
                    {
                        // Fallback: try individual property reads for known resource types
                        sb.Append("\"raw_type\":\"" + Esc(rawValues.GetType().FullName) + "\"");
                    }
                }
                else
                {
                    // No RawValues found — try reading individual properties on Resources directly
                    sb.Append("\"resources_type\":\"" + Esc(resources.GetType().FullName) + "\"");
                    // Try common property names
                    string[] tryProps = new string[] { "Energy", "Silver", "Gems", "ArenaTokens", "ClanBossKeys" };
                    foreach (var propName in tryProps)
                    {
                        try
                        {
                            var v = Prop(resources, propName);
                            if (v != null)
                                sb.Append(",\"" + propName.ToLower() + "\":" + Convert.ToDouble(v.ToString()).ToString("F0"));
                        }
                        catch { }
                    }
                }
            }
            catch (Exception ex)
            {
                sb.Append("\"error\":\"" + Esc(ex.Message) + "\"");
            }

            sb.Append("}");
            return sb.ToString();
        }

        // =====================================================
        // API: /all-resources — dump every named numeric property on Resources
        // =====================================================

        private string GetAllResources()
        {
            var uw = GetUserWrapper();
            if (uw == null) return "{\"error\":\"not logged in\"}";
            var account = Prop(uw, "Account");
            var accountData = Prop(account, "AccountData") ?? Prop(account, "Data");
            var resources = Prop(accountData, "Resources");
            if (resources == null) return "{\"error\":\"Resources not found\"}";
            var sb = new StringBuilder(4096);
            sb.Append("{");
            int n = 0;
            foreach (var p in resources.GetType().GetProperties(BindingFlags.Instance | BindingFlags.Public))
            {
                if (p.PropertyType != typeof(double)) continue;
                try
                {
                    var v = p.GetValue(resources);
                    if (v == null) continue;
                    double d = Convert.ToDouble(v);
                    if (n > 0) sb.Append(",");
                    sb.Append("\"").Append(Esc(p.Name)).Append("\":");
                    if (d == Math.Floor(d) && Math.Abs(d) < 1e15)
                        sb.Append(((long)d).ToString());
                    else
                        sb.Append(d.ToString("F2"));
                    n++;
                }
                catch { }
            }
            sb.Append("}");
            return sb.ToString();
        }

        // =====================================================
        // API: /explore-uw — list UserWrapper properties (debug)
        // =====================================================

        // Walk AppModel.StaticData.<path> and return instance props (same shape as
        // ExploreUserWrapper). Lets us discover the stage/artifact reward schema
        // without needing a debugger attached. Path supports "Item[KEY]" segments
        // for indexer access on dictionaries (e.g. HeroData.HeroTypeById.Item[123]).
        private string ExploreStaticData(string path)
        {
            var appModel = GetAppModel();
            if (appModel == null) return "{\"error\":\"appmodel not ready\"}";
            object target = Prop(appModel, "StaticData");
            if (target == null) return "{\"error\":\"AppModel.StaticData null\"}";
            if (!string.IsNullOrEmpty(path))
            {
                foreach (var seg in path.Split('.'))
                {
                    object next;
                    if (seg.StartsWith("Item[") && seg.EndsWith("]"))
                    {
                        var keyStr = seg.Substring(5, seg.Length - 6);
                        var idx = target.GetType().GetProperty("Item");
                        if (idx == null) return "{\"error\":\"no indexer on " + Esc(target.GetType().FullName) + "\"}";
                        var paramT = idx.GetIndexParameters()[0].ParameterType;
                        object key = keyStr;
                        // Handle Il2Cpp enum / numeric types: parse to int then ToObject onto the param type.
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
                        catch (Exception ex) { return "{\"error\":\"indexer threw " + Esc(ex.Message) + " (param=" + Esc(paramT.FullName) + ")\"}"; }
                    }
                    else if (seg.StartsWith("[") && seg.EndsWith("]"))
                    {
                        // List/array index: [N]
                        var nStr = seg.Substring(1, seg.Length - 2);
                        if (!int.TryParse(nStr, out int n)) return "{\"error\":\"bad index " + Esc(nStr) + "\"}";
                        var get = target.GetType().GetMethod("get_Item", new[] { typeof(int) });
                        if (get == null) return "{\"error\":\"no get_Item(int) on " + Esc(target.GetType().FullName) + "\"}";
                        try { next = get.Invoke(target, new object[] { n }); }
                        catch (Exception ex) { return "{\"error\":\"index threw " + Esc(ex.Message) + "\"}"; }
                    }
                    else
                    {
                        next = Prop(target, seg);
                    }
                    if (next == null) return "{\"error\":\"no property " + Esc(seg) + " on " + Esc(target.GetType().FullName) + "\"}";
                    target = next;
                }
            }
            var sb = new StringBuilder(2048);
            sb.Append("{\"path\":\"sd").Append(string.IsNullOrEmpty(path) ? "" : "." + path)
              .Append("\",\"type\":\"").Append(Esc(target.GetType().FullName)).Append("\",\"props\":[");
            int i = 0;
            foreach (var p in target.GetType().GetProperties(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic))
            {
                string valType = "?";
                string sample = null;
                int? collCount = null;
                try
                {
                    var v = p.GetValue(target);
                    if (v != null)
                    {
                        valType = v.GetType().FullName;
                        try
                        {
                            var cp = v.GetType().GetProperty("Count");
                            if (cp != null && cp.PropertyType == typeof(int))
                                collCount = (int)cp.GetValue(v);
                        }
                        catch { }
                        var s = v.ToString();
                        if (s != null && s.Length < 80 && !s.Contains("Il2Cpp") && !s.StartsWith("System."))
                            sample = s;
                    }
                }
                catch (Exception ex) { valType = "err:" + ex.GetType().Name; }
                if (i++ > 0) sb.Append(",");
                sb.Append("{\"name\":\"").Append(Esc(p.Name))
                  .Append("\",\"declared\":\"").Append(Esc(p.PropertyType.FullName))
                  .Append("\",\"actual\":\"").Append(Esc(valType)).Append("\"");
                if (collCount.HasValue) sb.Append(",\"count\":").Append(collCount.Value);
                if (sample != null) sb.Append(",\"sample\":\"").Append(Esc(sample)).Append("\"");
                sb.Append("}");
            }
            sb.Append("]}");
            return sb.ToString();
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

        private static void EmitRegion(StringBuilder sb, ref bool firstRegion,
            object region, object idVal, int rid, Dictionary<int, object> stageById)
        {
            string regionName = idVal.ToString();
            // Collect stage IDs across all difficulties via the dict's _entries;
            // for Dict<DifficultyId, List<int>>, only the value (List<int>) matters.
            var stageIds = new List<int>();
            var sidByDiff = Prop(region, "StageIdsByDifficulty");
            if (sidByDiff != null)
            {
                try
                {
                    var entries = Prop(sidByDiff, "_entries");
                    int n = entries != null ? IntProp(entries, "Length") : 0;
                    var get = entries != null
                        ? (entries.GetType().GetMethod("get_Item", new[] { typeof(int) })
                           ?? entries.GetType().GetProperty("Item")?.GetGetMethod())
                        : null;
                    for (int j = 0; j < n; j++)
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
                        for (int k = 0; k < idsCount; k++)
                        {
                            var sidObj = idsGet.Invoke(idsItems, new object[] { k });
                            if (sidObj == null) continue;
                            stageIds.Add(Convert.ToInt32(sidObj));
                        }
                    }
                }
                catch { }
            }

            // Aggregate per-set / per-accessory probs across stages.
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
                AggregateProbs(reward, "ArtifactProbsBySetKindId", setCount, setMaxProb);
                AggregateProbsCountOnly(reward, "AccessoryProbsByKindId", accKindCount);
                AggregateProbsCountOnly(reward, "AccessoryProbsBySetKindId", accSetCount);
            }
            if (stagesWithRewards == 0) return;

            if (!firstRegion) sb.Append(",");
            firstRegion = false;
            sb.Append("\"").Append(Esc(regionName)).Append("\":{");
            sb.Append("\"id\":").Append(rid);
            sb.Append(",\"stages\":").Append(stagesWithRewards);
            sb.Append(",\"set_drops\":");
            AppendIntDoubleMap(sb, setCount, setMaxProb);
            sb.Append(",\"accessory_kinds\":[");
            AppendIntList(sb, accKindCount.Keys);
            sb.Append("],\"accessory_sets\":[");
            AppendIntList(sb, accSetCount.Keys);
            sb.Append("]}");
        }

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

        private string ExploreUserWrapper(string path)
        {
            var uw = GetUserWrapper();
            if (uw == null) return "{\"error\":\"not logged in\"}";
            object target = uw;
            if (!string.IsNullOrEmpty(path))
            {
                foreach (var seg in path.Split('.'))
                {
                    var next = Prop(target, seg);
                    if (next == null) return "{\"error\":\"no property " + Esc(seg) + " on " + Esc(target.GetType().FullName) + "\"}";
                    target = next;
                }
            }
            var sb = new StringBuilder(2048);
            sb.Append("{\"path\":\"uw").Append(string.IsNullOrEmpty(path) ? "" : "." + path)
              .Append("\",\"type\":\"").Append(Esc(target.GetType().FullName)).Append("\",\"props\":[");
            int i = 0;
            foreach (var p in target.GetType().GetProperties(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic))
            {
                string valType = "?";
                string sample = null;
                try
                {
                    var v = p.GetValue(target);
                    if (v != null)
                    {
                        valType = v.GetType().FullName;
                        // Include a short sample for scalars / small values
                        var s = v.ToString();
                        if (s != null && s.Length < 60 && !s.Contains("Il2Cpp") && !s.Contains("System."))
                            sample = s;
                    }
                }
                catch (Exception ex) { valType = "err:" + ex.GetType().Name; }
                if (i++ > 0) sb.Append(",");
                sb.Append("{\"name\":\"").Append(Esc(p.Name))
                  .Append("\",\"declared\":\"").Append(Esc(p.PropertyType.FullName))
                  .Append("\",\"actual\":\"").Append(Esc(valType)).Append("\"");
                if (sample != null) sb.Append(",\"sample\":\"").Append(Esc(sample)).Append("\"");
                sb.Append("}");
            }
            sb.Append("]}");
            return sb.ToString();
        }

        // =====================================================
        // API: /shards — find and dump the player's summon shards
        // =====================================================

        // Raid's ShardType enum -> canonical output key the dashboard uses.
        // The game renamed "Primal" to "Mythical" internally; keep both mapped.
        private static readonly Dictionary<string, string> ShardKeyByEnum = new Dictionary<string, string>
        {
            { "Mystery",  "mystery"  },
            { "Ancient",  "ancient"  },
            { "Void",     "void"     },
            { "Sacred",   "sacred"   },
            { "Mythical", "primal"   },
            { "Primal",   "primal"   },
        };

        private string GetShards(bool debug)
        {
            var uw = GetUserWrapper();
            if (uw == null) return "{\"error\":\"not logged in\"}";

            // Raid path: UserWrapper -> Shards -> ShardData -> Shards (List<Shard>)
            var shardWrapper = Prop(uw, "Shards");
            if (shardWrapper == null) return "{\"error\":\"UserWrapper.Shards missing\"}";
            var shardData = Prop(shardWrapper, "ShardData");
            if (shardData == null) return "{\"error\":\"ShardWrapper.ShardData missing\"}";
            var list = Prop(shardData, "Shards");
            if (list == null) return "{\"error\":\"UserShardData.Shards missing\"}";

            var sb = new StringBuilder(2048);
            sb.Append("{");
            if (debug)
            {
                sb.Append("\"list_type\":\"").Append(Esc(list.GetType().FullName)).Append("\",");
                sb.Append("\"list_size\":").Append(IntProp(list, "_size")).Append(",");
                sb.Append("\"items\":[");
                try
                {
                    int sz = IntProp(list, "_size");
                    var items = Prop(list, "_items");
                    if (items != null)
                    {
                        var arrT = items.GetType();
                        var getItem = arrT.GetMethod("get_Item");
                        for (int i = 0; i < sz; i++)
                        {
                            object shard = null;
                            try { shard = getItem?.Invoke(items, new object[] { i }); } catch { }
                            if (i > 0) sb.Append(",");
                            if (shard == null) { sb.Append("null"); continue; }
                            sb.Append("{\"type\":\"").Append(Esc(shard.GetType().FullName)).Append("\",\"props\":{");
                            int pi = 0;
                            foreach (var p in shard.GetType().GetProperties(BindingFlags.Instance | BindingFlags.Public))
                            {
                                try
                                {
                                    var v = p.GetValue(shard);
                                    var s = v == null ? "null" : v.ToString();
                                    if (s != null && s.Length < 50)
                                    {
                                        if (pi++ > 0) sb.Append(",");
                                        sb.Append("\"").Append(Esc(p.Name)).Append("\":\"").Append(Esc(s)).Append("\"");
                                    }
                                } catch { }
                            }
                            sb.Append("}}");
                        }
                    }
                }
                catch (Exception ex) { sb.Append("{\"err\":\"").Append(Esc(ex.Message)).Append("\"}"); }
                sb.Append("],");
            }
            sb.Append("\"shards\":{");
            int found = 0;
            // Seed the output with 0 for every known shard so the UI always
            // shows the full set (empty shards aren't present in the list).
            var counts = new Dictionary<string, int>();
            foreach (var k in ShardKeyByEnum.Values) counts[k] = 0;

            try
            {
                var listType = list.GetType();
                // _items is the raw backing array; _size is element count
                var items = Prop(list, "_items");
                int size = IntProp(list, "_size");
                if (items == null || size <= 0)
                {
                    // Fall back to GetEnumerator iteration
                    var getEnum = listType.GetMethod("GetEnumerator");
                    if (getEnum != null)
                    {
                        var en = getEnum.Invoke(list, null);
                        var enT = en.GetType();
                        var mn = enT.GetMethod("MoveNext");
                        var cur = enT.GetProperty("Current");
                        while ((bool)mn.Invoke(en, null))
                        {
                            var shard = cur.GetValue(en);
                            if (shard == null) continue;
                            TallyShard(shard, counts);
                        }
                    }
                }
                else
                {
                    // Il2CppReferenceArray<T>: indexer takes int, or use .Length
                    var arrT = items.GetType();
                    var indexer = arrT.GetProperty("Item") ?? arrT.GetProperty("_items");
                    for (int i = 0; i < size; i++)
                    {
                        object shard = null;
                        try { shard = indexer.GetValue(items, new object[] { i }); }
                        catch
                        {
                            // Some Il2CppReferenceArray variants expose array via reflection
                            var method = arrT.GetMethod("get_Item");
                            if (method != null) shard = method.Invoke(items, new object[] { i });
                        }
                        if (shard != null) TallyShard(shard, counts);
                    }
                }
            }
            catch (Exception ex)
            {
                sb.Append("\"iter_error\":\"").Append(Esc(ex.Message)).Append("\",");
            }

            foreach (var kv in counts)
            {
                if (found > 0) sb.Append(",");
                sb.Append("\"").Append(Esc(kv.Key)).Append("\":").Append(kv.Value);
                found++;
            }
            sb.Append("}}");
            return sb.ToString();
        }

        private void TallyShard(object shard, Dictionary<string, int> counts)
        {
            // TypeId is a ShardType enum — its ToString() yields "Mystery" / "Ancient" / ...
            var tid = Prop(shard, "TypeId");
            var cnt = Prop(shard, "Count") ?? Prop(shard, "Quantity") ?? Prop(shard, "Amount");
            if (tid == null || cnt == null) return;
            int count;
            if (!int.TryParse(cnt.ToString(), out count)) return;
            string key;
            if (!ShardKeyByEnum.TryGetValue(tid.ToString(), out key))
                key = tid.ToString().ToLowerInvariant();
            if (!counts.ContainsKey(key)) counts[key] = 0;
            counts[key] += count;
        }

        // =====================================================
        // API: /view-contexts — list all active dialog MVVM contexts
        // =====================================================

        /// <summary>
        /// Find a context instance by type name (partial match) and invoke a method on it.
        /// Works by scanning all MonoBehaviours in the scene for BaseView components,
        /// reading their Context property, and matching the context type name.
        /// Usage: /invoke-context?type=HeroesSelectionAllianceBoss&method=StartBattle
        /// </summary>
        private string InvokeOnContext(string typeName, string methodName)
        {
            if (string.IsNullOrEmpty(typeName) || string.IsNullOrEmpty(methodName))
                return "{\"error\":\"type and method required\"}";

            try
            {
                // Scan all dialogs for MonoBehaviours with a Context property
                // (can't use FindObjectsOfType with IL2CPP reflection types)
                var dialogContainers = new List<Transform>();
                var uiRoot = GameObject.Find("UIManager/Canvas (Ui Root)/Dialogs");
                if (uiRoot != null) dialogContainers.Add(uiRoot.transform);
                var ovRoot = GameObject.Find("UIManager/Canvas (Ui Root)/OverlayDialogs");
                if (ovRoot != null) dialogContainers.Add(ovRoot.transform);

                var viewInstances = new List<object>();
                foreach (var container in dialogContainers)
                {
                    for (int di = 0; di < container.childCount; di++)
                    {
                        var dialog = container.GetChild(di);
                        if (!dialog.gameObject.activeSelf) continue;
                        // BFS through dialog hierarchy
                        var queue = new Queue<Transform>();
                        queue.Enqueue(dialog);
                        int searched = 0;
                        while (queue.Count > 0 && searched < 200)
                        {
                            var t = queue.Dequeue();
                            searched++;
                            foreach (var comp in t.GetComponents<MonoBehaviour>())
                            {
                                if (comp == null) continue;
                                try
                                {
                                    // Check if this component has a Context property
                                    // IL2CPP interop: properties are accessed via get_X methods
                                    var ctxGetter = comp.GetType().GetMethod("get_Context",
                                        BindingFlags.Public | BindingFlags.Instance);
                                    if (ctxGetter == null)
                                    {
                                        var bt = comp.GetType().BaseType;
                                        while (bt != null && bt != typeof(object) && ctxGetter == null)
                                        {
                                            ctxGetter = bt.GetMethod("get_Context",
                                                BindingFlags.Public | BindingFlags.Instance | BindingFlags.DeclaredOnly);
                                            bt = bt.BaseType;
                                        }
                                    }
                                    if (ctxGetter != null)
                                    {
                                        viewInstances.Add(comp);
                                    }
                                }
                                catch { }
                            }
                            for (int ci = 0; ci < t.childCount && ci < 30; ci++)
                                queue.Enqueue(t.GetChild(ci));
                        }
                    }
                }

                // If BFS didn't find contexts, try direct approach:
                // Find the context TYPE and scan MonoBehaviours for matching types
                if (viewInstances.Count == 0)
                {
                    // Search ALL MonoBehaviours in scene for any whose type hierarchy
                    // contains a "Context" property returning a type matching our search
                    // Use Il2CppType to find BaseView instances properly
                    // FindObjectsOfType with System.Type doesn't work for IL2CPP —
                    // we need to use the IL2CPP type system via Il2CppType.Of<T>()
                    // But we can't use generics with a runtime type. Instead, find
                    // the dialog root and GetComponentsInChildren with the IL2CPP type.
                    var baseViewCSharpType = FindType("Client.MVVM.Base.View.BaseView");
                    if (baseViewCSharpType != null)
                    {
                        // Scan active dialogs
                        var roots = new List<Transform>();
                        var dr = GameObject.Find("UIManager/Canvas (Ui Root)/Dialogs");
                        if (dr != null) roots.Add(dr.transform);
                        var or2 = GameObject.Find("UIManager/Canvas (Ui Root)/OverlayDialogs");
                        if (or2 != null) roots.Add(or2.transform);

                        foreach (var root in roots)
                        {
                            for (int di = 0; di < root.childCount; di++)
                            {
                                var dialog = root.GetChild(di);
                                if (!dialog.gameObject.activeSelf) continue;
                                // Get ALL components on this dialog tree
                                var comps = dialog.GetComponentsInChildren<Component>(true);
                                foreach (var comp in comps)
                                {
                                    if (comp == null) continue;
                                    try
                                    {
                                        // Check type name chain for "View" or "Dialog"
                                        string tn = comp.GetType().Name;
                                        if (tn.Contains("View") || tn.Contains("Dialog"))
                                        {
                                            // Try reading Context via Prop helper
                                            try
                                            {
                                                var ctx = Prop(comp, "Context");
                                                if (ctx != null)
                                                    viewInstances.Add(comp);
                                            }
                                            catch { }
                                        }
                                    }
                                    catch { }
                                }
                            }
                        }
                    }
                }

                if (viewInstances.Count == 0)
                    return "{\"error\":\"no views with Context found (scanned " +
                           UnityEngine.Object.FindObjectsOfType<MonoBehaviour>().Length + " MBs)\"}";

                // Search for matching context
                foreach (var view in viewInstances)
                {
                    if (view == null) continue;
                    try
                    {
                        var ctx = Prop(view, "Context");
                        if (ctx == null) continue;

                        string ctxTypeName = ctx.GetType().Name;
                        if (!ctxTypeName.Contains(typeName)) continue;

                        // Found matching context! Invoke the method
                        var m = ctx.GetType().GetMethod(methodName,
                            BindingFlags.Public | BindingFlags.Instance);
                        if (m == null)
                        {
                            var allMethods = ctx.GetType().GetMethods(BindingFlags.Public | BindingFlags.Instance);
                            var names = new List<string>();
                            foreach (var am in allMethods)
                            {
                                if (!am.Name.StartsWith("get_") && !am.Name.StartsWith("set_"))
                                    names.Add(am.Name);
                            }
                            return "{\"error\":\"method " + methodName + " not found on " + ctxTypeName +
                                   "\",\"available\":[" +
                                   string.Join(",", names.ConvertAll(n => "\"" + Esc(n) + "\"")) + "]}";
                        }

                        if (m.GetParameters().Length == 0)
                        {
                            m.Invoke(ctx, null);
                        }
                        else
                        {
                            // Try with default args
                            var pars = m.GetParameters();
                            var args = new object[pars.Length];
                            for (int pi = 0; pi < pars.Length; pi++)
                            {
                                if (pars[pi].ParameterType == typeof(int)) args[pi] = 0;
                                else if (pars[pi].ParameterType == typeof(bool)) args[pi] = false;
                                else if (pars[pi].ParameterType == typeof(string)) args[pi] = "";
                                else args[pi] = null;
                            }
                            m.Invoke(ctx, args);
                        }

                        return "{\"invoked\":\"" + Esc(methodName) + "\",\"context\":\"" +
                               Esc(ctxTypeName) + "\",\"view\":\"" +
                               Esc(view.GetType().Name) + "\"}";
                    }
                    catch (Exception ex)
                    {
                        Logger.LogWarning("InvokeOnContext: " + ex.Message);
                    }
                }

                return "{\"error\":\"no context matching " + typeName + " found among " +
                       viewInstances.Count + " views\"}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        private string GetViewContexts(string specificPath)
        {
            var sb = new StringBuilder(4096);

            if (!string.IsNullOrEmpty(specificPath))
            {
                // Scan a specific object
                var go = GameObject.Find(specificPath);
                if (go == null)
                    return "{\"error\":\"not found: " + Esc(specificPath) + "\"}";

                var info = FindContextInfo(go.transform, 6);
                if (info != null)
                    return "{" + info + "}";
                return "{\"error\":\"no context found on " + Esc(specificPath) + "\"}";
            }

            // Scan all active dialogs, overlays, and messageboxes
            sb.Append("{\"contexts\":[");
            int found = 0;

            string[] parentPaths = new string[]
            {
                "UIManager/Canvas (Ui Root)/Dialogs",
                "UIManager/Canvas (Ui Root)/OverlayDialogs",
                "UIManager/Canvas (Ui Root)/MessageBoxes",
            };

            foreach (var parentPath in parentPaths)
            {
                var parent = GameObject.Find(parentPath);
                if (parent == null) continue;

                for (int i = 0; i < parent.transform.childCount; i++)
                {
                    var child = parent.transform.GetChild(i).gameObject;
                    if (!child.activeSelf) continue;

                    string contextInfo = FindContextInfo(child.transform, 5);
                    if (found > 0) sb.Append(",");
                    if (contextInfo != null)
                    {
                        sb.Append("{\"dialog\":\"" + Esc(child.name) + "\"," + contextInfo + "}");
                    }
                    else
                    {
                        sb.Append("{\"dialog\":\"" + Esc(child.name) + "\",\"context\":null}");
                    }
                    found++;
                }
            }

            sb.Append("],\"total\":" + found + "}");
            return sb.ToString();
        }

        /// <summary>
        /// BFS through hierarchy to find a MonoBehaviour with a Context property (BaseView).
        /// Returns JSON fragment with context_class, view_path, and methods list, or null.
        /// </summary>
        private string FindContextInfo(Transform root, int maxDepth)
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
                            // Look for a Context property via reflection (BaseView subclasses)
                            var ctxProp = mono.GetType().GetProperty("Context",
                                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.FlattenHierarchy);
                            if (ctxProp == null)
                            {
                                var baseType = mono.GetType().BaseType;
                                while (baseType != null && ctxProp == null)
                                {
                                    ctxProp = baseType.GetProperty("Context",
                                        BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly);
                                    baseType = baseType.BaseType;
                                }
                            }
                            if (ctxProp == null) continue;

                            var ctx = ctxProp.GetValue(mono);
                            if (ctx == null) continue;

                            string ctxClassName = ctx.GetType().FullName ?? ctx.GetType().Name;
                            string viewClassName = mono.GetType().Name;

                            // Skip framework/generic contexts
                            if (ctxClassName.StartsWith("Il2Cpp")) continue;

                            // Collect methods on the context class (walk up hierarchy)
                            var methods = new List<string>();
                            var ck = ctx.GetType();
                            int classDepth = 0;
                            while (ck != null && classDepth < 5)
                            {
                                foreach (var m in ck.GetMethods(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly))
                                {
                                    if (!m.Name.StartsWith(".") && !m.Name.StartsWith("<") &&
                                        !m.Name.StartsWith("get_") && !m.Name.StartsWith("set_"))
                                    {
                                        string sig = m.Name + "(" + m.GetParameters().Length + ")";
                                        if (!methods.Contains(sig))
                                            methods.Add(sig);
                                    }
                                }
                                ck = ck.BaseType;
                                if (ck == null || ck.Name == "Object" || ck.Name == "Il2CppObjectBase") break;
                                classDepth++;
                            }

                            var result = new StringBuilder();
                            result.Append("\"context_class\":\"" + Esc(ctxClassName) + "\"");
                            result.Append(",\"view_class\":\"" + Esc(viewClassName) + "\"");
                            result.Append(",\"view_path\":\"" + Esc(GetPath(t)) + "\"");
                            result.Append(",\"methods\":[");
                            for (int mi = 0; mi < methods.Count && mi < 60; mi++)
                            {
                                if (mi > 0) result.Append(",");
                                result.Append("\"" + Esc(methods[mi]) + "\"");
                            }
                            result.Append("]");
                            return result.ToString();
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

        private Type FindType(string fullName)
        {
            foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
            {
                try { var t = asm.GetType(fullName); if (t != null) return t; } catch { }
            }
            return null;
        }

        private static string GetPath(Transform t)
        {
            string path = t.name;
            while (t.parent != null) { t = t.parent; path = t.name + "/" + path; }
            return path;
        }

        private static string QP(string query, string key)
        {
            if (string.IsNullOrEmpty(query)) return "";
            foreach (var p in query.TrimStart('?').Split('&'))
            {
                var kv = p.Split('=');
                if (kv.Length == 2 && kv[0] == key) return Uri.UnescapeDataString(kv[1]);
            }
            return "";
        }

        private static string Esc(string s)
        {
            if (s == null) return "";
            return s.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n").Replace("\r", "\\r");
        }
    }

    public class RaidUpdateBehaviour : MonoBehaviour
    {
        private float _lastBattlePoll;

        void Update()
        {
            RaidAutomationPlugin.ProcessQueue();
            RaidAutomationPlugin.ProcessArtifactCmds();

            // Poll battle state every 0.5 seconds during active battles
            if (Time.time - _lastBattlePoll >= 0.5f)
            {
                _lastBattlePoll = Time.time;
                RaidAutomationPlugin.PollBattleState();
            }
        }
    }
}
