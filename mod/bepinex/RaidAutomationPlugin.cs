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
    public partial class RaidAutomationPlugin : BasePlugin
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
                    "/sell-artifacts" => RunOnMainThread(() => SellArtifactsViaDto(QP(query, "ids")), 30000),
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
                    "/static-export" => RunOnMainThread(() => ExportStaticDataPath(
                        QP(query, "path"),
                        int.TryParse(QP(query, "depth"), out var __d) ? __d : 4,
                        int.TryParse(QP(query, "max"), out var __m) ? __m : 5000), 60000),
                    "/dungeon-drops" => RunOnMainThread(() => GetDungeonDrops(), 90000),
                    "/forge-sets" => RunOnMainThread(() => GetForgeSets(), 30000),
                    "/masteries-truth" => RunOnMainThread(() => GetMasteriesTruth(), 30000),
                    "/blessings-truth" => RunOnMainThread(() => GetBlessingsTruth(), 30000),
                    "/hero-types" => RunOnMainThread(() => GetHeroTypes(), 90000),
                    "/stage-bosses" => RunOnMainThread(() => GetCbBosses(), 90000),
                    "/cb-bosses" => RunOnMainThread(() => GetCbBosses(), 90000),  // alias
                    "/alliance-bosses" => RunOnMainThread(() => GetAllianceBosses(), 30000),
                    "/artifact-sets-truth" => RunOnMainThread(() => GetArtifactSetsTruth(), 30000),
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
                                // Stats.Speed: the FULLY RESOLVED in-battle SPD value (base + gear +
                                // sets + masteries + buffs). The Python sim's calc_stats produces a
                                // SPD that doesn't match real-game action ratios; the gap was
                                // unmeasurable without this ground-truth value. BattleStats has
                                // get_Speed returning Fixed (32.32). 0 if read fails.
                                long sSpd = 0;
                                try {
                                    IntPtr getStats = FindIL2CPPMethodStatic(hc, "get_Stats", 0);
                                    if (getStats != IntPtr.Zero) {
                                        IntPtr eS1 = IntPtr.Zero;
                                        IntPtr statsObj = il2cpp_runtime_invoke(getStats, heroObj, IntPtr.Zero, ref eS1);
                                        if (statsObj != IntPtr.Zero) {
                                            IntPtr statsClass = il2cpp_object_get_class(statsObj);
                                            IntPtr getSpd = FindIL2CPPMethodStatic(statsClass, "get_Speed", 0);
                                            if (getSpd != IntPtr.Zero) {
                                                IntPtr eS2 = IntPtr.Zero;
                                                IntPtr spdRes = il2cpp_runtime_invoke(getSpd, statsObj, IntPtr.Zero, ref eS2);
                                                if (spdRes != IntPtr.Zero) sSpd = Marshal.ReadInt64(spdRes + 0x10) >> 32;
                                            }
                                        }
                                    }
                                } catch { }
                                if (uidx > 0) sbtl.Append(",");
                                sbtl.Append("{\"s\":\"" + side + "\",\"id\":" + id + ",\"tm\":" + tmDisplay + ",\"tn\":" + turnN + ",\"s_spd\":" + sSpd);
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

        // Recursively serialize any StaticData subtree to JSON.
        //
        // Path format mirrors /explore-sd: dot-separated property names,
        // with `Item[key]` for dictionary indexing and `[N]` for list index.
        //   /static-export?path=EffectData.EffectTypeById&depth=4&max=200
        //
        // depth: how many levels of nested objects to expand. Below depth=0
        // values render as "<TypeName>" stubs.
        // max:   per-collection cap (so a 8100-entry HeroTypeById doesn't
        // OOM the response). Truncated collections include _truncated:true.

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
