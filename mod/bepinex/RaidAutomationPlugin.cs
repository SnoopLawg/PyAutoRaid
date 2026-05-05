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

                // CRASH ISOLATION (2026-05-03): Raid.exe is crashing
                // mid-battle (~boss turn 27-28) with APPCRASH in
                // coreclr.dll at offset 0x1d1fdd, exception 0xC0000005.
                // Pre-existing pattern in WER ReportArchive going back
                // to 4/25 — same bucket ID 220d01ff7dc7a28946e7dc0f36236cd7.
                //
                // Suspect: our battle-event Harmony postfixes do raw
                // Marshal.ReadIntPtr walks (BattleHook_DamageChange has
                // multi-level pointer derefs at 2255-2291; ReadActiveEffects
                // walks HeroState memory). When a pointer is freed mid-
                // battle, the read triggers an SEH access violation.
                // Modern .NET 6 corrupted-state exceptions bypass our
                // try/catch — runtime crashes.
                //
                // DISABLED until the unsafe walks are wrapped in
                // SafeHandle-style validation OR replaced with
                // Il2CppInterop typed accessors. Mod still works for
                // its primary HTTP API surface (navigation, context-call,
                // resources, view-contexts, etc.) — only loses per-
                // damage-event hooks during battle.
                bool _ENABLE_BATTLE_PROCESSOR_HOOKS = false;
                if (_ENABLE_BATTLE_PROCESSOR_HOOKS)
                {
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
                }
                else
                {
                    lock (_hookPatchLog) { _hookPatchLog.Add("battle_processor_hooks:DISABLED_for_crash_isolation"); }
                    Logger.LogInfo("Harmony: battle processor hooks DISABLED for crash isolation");
                }

                // DamageReductionByDefence + Fixed.op_Subtraction hooks
                // were used to extract the literal DEF mitigation formula
                // (factor = 1 - 0.85 * (1 - exp((Defence - acc_mod) *
                //  (1 + defence_modifier) * (-1/1500)))) and the -0.02
                // base armor pierce. See `cb_constants.def_mitigation_factor`
                // and commit 8501dc7. The hooks are now DISABLED because
                // they triggered a coreclr.dll APPCRASH (c0000005 access
                // violation) at battle teardown — the BattleHero pointers
                // we read via Marshal.ReadIntPtr are freed before the
                // final DamageReductionByDefence call completes.
                //
                // Re-enable only when:
                //   (a) acc_mod or defence_modifier needs re-derivation
                //       after a game patch, AND
                //   (b) the Marshal.ReadIntPtr walks have been wrapped in
                //       try/catch with pointer-validity checks.

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
                    "/save-preset" => RunOnMainThread(() => SavePreset(QP(query, "name"), QP(query, "heroes"), QP(query, "type"), QP(query, "empty")), 30000),
                    "/update-preset" => RunOnMainThread(() => UpdatePreset(QP(query, "id"), QP(query, "priorities"), QP(query, "starters"), QP(query, "name")), 30000),
                    "/preset-schema" => RunOnMainThread(() => PresetSchema(QP(query, "id")), 15000),
                    "/preset-deep" => RunOnMainThread(() => PresetDeepDump(QP(query, "id")), 15000),
                    "/name-limits" => RunOnMainThread(() => GetPresetNameLimits(), 5000),
                    "/apply-preset" => RunOnMainThread(() => ApplyPreset(QP(query, "id")), 15000),
                    "/set-dungeon-difficulty" => RunOnMainThread(() => SetDungeonDifficulty(QP(query, "hard")), 10000),
                    "/events" => RunOnMainThread(() => GetEvents(), 15000),
                    "/event-progress" => RunOnMainThread(() => GetEventProgress(), 10000),
                    "/apply-blessing" => RunOnMainThread(() => ApplyBlessing(QP(query, "hero_id"), QP(query, "blessing_id")), 15000),
                    "/rank-up" => RunOnMainThread(() => RankUpHero(QP(query, "hero_id"), QP(query, "food")), 30000),
                    "/skill-up" => RunOnMainThread(() => SkillUpHero(QP(query, "hero_id"), QP(query, "food"), QP(query, "books")), 30000),
                    "/move-heroes" => RunOnMainThread(() => MoveHeroes(QP(query, "dest"), QP(query, "ids")), 30000),
                    "/squad-current" => RunOnMainThread(() => SquadCurrent(), 10000),
                    "/squad-set" => RunOnMainThread(() => SquadSet(QP(query, "ids")), 30000),
                    "/squad-add" => RunOnMainThread(() => SquadAdd(QP(query, "hero_id")), 15000),
                    "/squad-remove" => RunOnMainThread(() => SquadRemove(QP(query, "hero_id")), 15000),
                    "/squad-clear" => RunOnMainThread(() => SquadClear(), 30000),
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
                    "/static-field" => RunOnMainThread(() => GetStaticField(QP(query, "type"), QP(query, "name"), QP(query, "depth")), 30000),
                    "/effect-kind-group" => RunOnMainThread(() => GetEffectKindGroup(QP(query, "group")), 30000),
                    "/damage-calc-probe" => RunOnMainThread(() => GetDamageCalcProbe(), 30000),
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
                lock (_tickLog) { if (_tickLog.Count < 20000) _tickLog.Add(sb.ToString()); }
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

        // Single-arg overload — read a Fixed-typed property directly off `obj`.
        // Used by the damage hook to capture stats (e.g. Stats.Attack,
        // BattleHero.HealthMax) where we already have the immediate parent.
        private static long ReadFixedRaw(object obj, string fieldName)
        {
            try
            {
                if (obj == null) return -1;
                var val = Prop(obj, fieldName);
                if (val == null) return -1;
                var raw = Prop(val, "RawValue");
                if (raw == null) return -1;
                return Convert.ToInt64(raw) >> 32;
            }
            catch { return -1; }
        }

        // Like ReadFixedRaw(obj, fieldName) but multiplies by 1000 before
        // truncating, preserving 3 decimals. Use for percent stats
        // (CritDamage, CritChance) where the actual value is < 10.0 so
        // the integer-only reader loses the fractional bits.
        private static long ReadFixedScaled(object obj, string fieldName, long scale)
        {
            try
            {
                if (obj == null) return -1;
                var val = Prop(obj, fieldName);
                if (val == null) return -1;
                var raw = Prop(val, "RawValue");
                if (raw == null) return -1;
                long r = Convert.ToInt64(raw);
                // Multiply first then shift, keeping precision. r is already
                // 32.32 (raw bits), multiplying by `scale` and shifting >>32
                // yields raw_value * scale.
                return (r * scale) >> 32;
            }
            catch { return -1; }
        }

        // Walk a BattleHero's HeroState.AppliedEffects and emit a compact
        // string like "[470,151,80]" — list of EffectTypeIds currently
        // active. Same memory layout pattern as the per-tick log walker
        // (HeroState @ 0xC0, AppliedEffects @ 0x38, item EffectTypeId @ 0x38).
        // Empty string on any read failure or empty list.
        private static string ReadActiveEffects(object hero)
        {
            try
            {
                IntPtr heroPtr = IL2CPPHandleOf(hero);
                if ((long)heroPtr <= 0x10000) return "";
                IntPtr hstate = Marshal.ReadIntPtr(heroPtr + 0xC0);
                if ((long)hstate <= 0x10000) return "";
                IntPtr listObj = Marshal.ReadIntPtr(hstate + 0x38);
                if ((long)listObj <= 0x10000) return "";
                int sz = Marshal.ReadInt32(listObj + 0x18);
                if (sz <= 0 || sz > 100) return "";
                IntPtr items = Marshal.ReadIntPtr(listObj + 0x10);
                if ((long)items <= 0x10000) return "";
                var sb = new StringBuilder("[");
                IntPtr basePtr = items + 0x20;
                for (int i = 0; i < sz && i < 50; i++)
                {
                    IntPtr ae = Marshal.ReadIntPtr(basePtr + (i * 8));
                    if ((long)ae <= 0x10000) continue;
                    int etype = Marshal.ReadInt32(ae + 0x38);
                    if (i > 0) sb.Append(",");
                    sb.Append(etype);
                }
                sb.Append("]");
                return sb.ToString();
            }
            catch { return ""; }
        }

        // Read a BattleHero's primary Element by walking
        // BattleHero.Type.DefaultElement. Returns the Element enum int
        // (1=Magic 2=Force 3=Spirit 4=Void) or -1 on read failure.
        private static int ReadHeroElement(object hero)
        {
            try
            {
                if (hero == null) return -1;
                var ht = Prop(hero, "Type");
                if (ht == null) return -1;
                var elem = Prop(ht, "DefaultElement");
                if (elem == null) return -1;
                return Convert.ToInt32(elem);
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

        // Counter for diagnostic visibility in /battle-state output.
        private static int _hookDiag_DefReduction = 0;

        // Coordination state for the dual DefReduction + op_Subtraction
        // hook chain. Plarium's battle code runs on Unity's main thread,
        // so a static flag suffices (no thread-locals needed). Reset by
        // the DefReduction prefix and consumed by the postfix.
        [ThreadStatic] private static bool _inDefReduction;
        [ThreadStatic] private static int  _defReductionSubCount;
        [ThreadStatic] private static long _defReductionAccModRaw;

        public static void BattleHook_DefReduction_Prefix()
        {
            _inDefReduction = true;
            _defReductionSubCount = 0;
            _defReductionAccModRaw = 0;
        }

        // Postfix on Fixed.op_Subtraction. Called for EVERY subtraction
        // game-wide; we early-out unless the DefReduction prefix has
        // armed us. The first sub call inside DamageReductionByDefence
        // is `Stats.Defence - acc_mod` — capture its second arg.
        public static void BattleHook_FixedSubtraction(object[] __args)
        {
            if (!_inDefReduction) return;
            _defReductionSubCount++;
            if (_defReductionSubCount != 1) return;
            // Args: [0] = Fixed x (Stats.Defence), [1] = Fixed y (acc_mod)
            try
            {
                if (__args == null || __args.Length < 2 || __args[1] == null) return;
                var rv = Prop(__args[1], "RawValue");
                if (rv != null) _defReductionAccModRaw = Convert.ToInt64(rv);
            }
            catch { }
        }

        // Postfix for DamageCalculator.DamageReductionByDefence
        // (EffectContext, BattleHero, Fixed) -> Fixed.
        // Captures (input_value_raw, target_def_raw, returned_factor_raw)
        // per call so we can fit the literal mitigation function from
        // real game execution. Result type is Fixed (32.32 raw long).
        public static void BattleHook_DefReduction(object[] __args, object __result)
        {
            _hookDiag_DefReduction++;
            try
            {
                if (__args == null || __args.Length < 3) return;
                long inputRaw  = 0;
                bool inputCaptured = false;
                long targetDef = -1;
                long resultRaw = -1;
                long pAtk = -1, pDef = -1;
                int pLevel = -1, tLevel = -1;
                int pTypeId = -1, tTypeId = -1;
                int targetId = 0, producerId = 0;
                string pBuffs = null, tDebuffs = null;

                try
                {
                    // arg[0] = EffectContext, arg[1] = BattleHero (target),
                    // arg[2] = Fixed input damage value.
                    var ctx = __args[0];
                    object prodHero = null, tgtHero = null;
                    if (ctx != null)
                    {
                        try { prodHero = Prop(ctx, "Producer"); if (prodHero != null) producerId = IntProp(prodHero, "Id"); } catch { }
                        try { tgtHero  = Prop(ctx, "Target");   if (tgtHero  != null) targetId   = IntProp(tgtHero,  "Id"); } catch { }
                    }
                    var battleHero = __args[1] ?? tgtHero;
                    if (battleHero != null)
                    {
                        try
                        {
                            var stats = Prop(battleHero, "Stats");
                            if (stats != null) targetDef = ReadFixedRaw(stats, "Defence");
                        } catch { }
                        try { tLevel  = IntProp(battleHero, "Level"); } catch { }
                        try { tTypeId = IntProp(battleHero, "TypeId"); } catch { }
                        try { tDebuffs = ReadActiveEffects(battleHero); } catch { }
                    }
                    if (prodHero != null)
                    {
                        try
                        {
                            var pStats = Prop(prodHero, "Stats");
                            if (pStats != null)
                            {
                                pAtk = ReadFixedRaw(pStats, "Attack");
                                pDef = ReadFixedRaw(pStats, "Defence");
                            }
                        } catch { }
                        try { pLevel  = IntProp(prodHero, "Level"); } catch { }
                        try { pTypeId = IntProp(prodHero, "TypeId"); } catch { }
                        try { pBuffs  = ReadActiveEffects(prodHero); } catch { }
                    }
                    var fixedIn = __args[2];
                    if (fixedIn != null)
                    {
                        try
                        {
                            var rv = Prop(fixedIn, "RawValue");
                            if (rv != null) { inputRaw = Convert.ToInt64(rv); inputCaptured = true; }
                        } catch { }
                    }
                    if (__result != null)
                    {
                        try { var rv = Prop(__result, "RawValue"); if (rv != null) resultRaw = Convert.ToInt64(rv); } catch { }
                    }
                }
                catch { }

                // One tick-log entry per call. Fixed values are 32.32 —
                // consumer scales by (>> 32) to get the integer game value.
                var sb = new StringBuilder();
                sb.Append("{\"kind\":\"def_reduction\",\"tick\":").Append(_battleCommandCount);
                sb.Append(",\"producer_id\":").Append(producerId);
                sb.Append(",\"target_id\":").Append(targetId);
                if (pTypeId  >= 0) sb.Append(",\"p_typeid\":").Append(pTypeId);
                if (tTypeId  >= 0) sb.Append(",\"t_typeid\":").Append(tTypeId);
                if (pLevel   >= 0) sb.Append(",\"p_lvl\":").Append(pLevel);
                if (tLevel   >= 0) sb.Append(",\"t_lvl\":").Append(tLevel);
                if (pAtk     >= 0) sb.Append(",\"p_atk\":").Append(pAtk);
                if (pDef     >= 0) sb.Append(",\"p_def\":").Append(pDef);
                if (inputCaptured) sb.Append(",\"in_raw\":").Append(inputRaw);
                if (targetDef>= 0) sb.Append(",\"t_def\":").Append(targetDef);
                if (resultRaw>= 0) sb.Append(",\"out_raw\":").Append(resultRaw);
                // acc_mod captured by the FixedSubtraction sub-hook.
                // Game-truth value of the AppliedEffects-loop accumulator
                // — closes the residual that empirical fitting otherwise
                // had to back-derive.
                sb.Append(",\"acc_mod_raw\":").Append(_defReductionAccModRaw);
                sb.Append(",\"sub_calls\":").Append(_defReductionSubCount);
                if (!string.IsNullOrEmpty(pBuffs)   && pBuffs   != "[]") sb.Append(",\"p_buffs\":").Append(pBuffs);
                if (!string.IsNullOrEmpty(tDebuffs) && tDebuffs != "[]") sb.Append(",\"t_debuffs\":").Append(tDebuffs);
                sb.Append("}");
                lock (_tickLog) { _tickLog.Add(sb.ToString()); }
                // Clear the dual-hook coordination state so the next
                // call starts fresh (the [ThreadStatic] fields persist
                // until reset).
                _inDefReduction = false;
            }
            catch { }
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
                // Phase 5 (research) — capture in-battle ATK/DEF/HP_max so DEF
                // mitigation formula can be back-solved from real events.
                long pAtk = -1, pCd = -1, pCr = -1;       // producer ATK / CritDmg / CritChance
                long tDef = -1, tHpMax = -1, tHp = -1;    // target DEF / max HP / current HP
                long pStamina = -1, tStamina = -1;        // turn meter at attack moment
                int pLevel = -1, tLevel = -1;             // level (boss=250, heroes=60)
                long calcDefMod = -1, calcMul = -1;       // DamageContext._defenceModifier and _multiplierValue
                // Phase 5 (active effects + boss element).
                int pElem = -1, tElem = -1;               // attacker/target Element (1=Magic 2=Force 3=Spirit 4=Void)
                int pTypeId = -1, tTypeId = -1;           // attacker/target HeroType id
                string pEff = null, tEff = null;          // active effect ID lists per side
                try
                {
                    if (__args != null && __args.Length > 0 && __args[0] != null)
                    {
                        var eff = __args[0];
                        object prodHero = null, tgtHero = null;
                        try { prodHero = Prop(eff, "Producer"); if (prodHero != null) producerId = IntProp(prodHero, "Id"); } catch { }
                        try { tgtHero = Prop(eff, "Target"); if (tgtHero != null) targetId = IntProp(tgtHero, "Id"); } catch { }
                        // Stat snapshot at damage time. We only need ATK/CD/CR
                        // from the producer and DEF/HP from the target — those
                        // are sufficient to back-solve the DEF mitigation
                        // formula's hidden coefficient. Soft-fail: captures
                        // are -1 if any read throws.
                        try
                        {
                            if (prodHero != null)
                            {
                                var pStats = Prop(prodHero, "Stats");
                                if (pStats != null)
                                {
                                    pAtk = ReadFixedRaw(pStats, "Attack");
                                    // CritDamage / CritChance are stored as
                                    // fractions (0.15 for 15%, 2.50 for 250%).
                                    // Truncating to integer part loses
                                    // everything below 1.0 — scale by 1000
                                    // to preserve 3 decimals (so 2.500 → 2500
                                    // in JSON; consumer divides by 1000).
                                    pCd  = ReadFixedScaled(pStats, "CriticalDamage", 1000);
                                    pCr  = ReadFixedScaled(pStats, "CriticalChance", 1000);
                                }
                            }
                            if (tgtHero != null)
                            {
                                var tStats = Prop(tgtHero, "Stats");
                                if (tStats != null) tDef = ReadFixedRaw(tStats, "Defence");
                                tHpMax = ReadFixedRaw(tgtHero, "HealthMax");
                                tHp = ReadFixedRaw(tgtHero, "Health");
                            }
                            // Element + HeroType id for both sides — needed
                            // to compute affinity advantage / disadvantage
                            // per event without inferring it from skill IDs.
                            // Magic boss (today's affinity) vs Force hero
                            // gives the boss an Advantage; reading element
                            // here makes it explicit per damage event.
                            if (prodHero != null)
                            {
                                pElem = ReadHeroElement(prodHero);
                                try { pTypeId = IntProp(prodHero, "TypeId"); } catch { }
                                pEff = ReadActiveEffects(prodHero);
                                try { pStamina = ReadFixedRaw(prodHero, "Stamina"); } catch { }
                                try { pLevel = IntProp(prodHero, "Level"); } catch { }
                            }
                            if (tgtHero != null)
                            {
                                tElem = ReadHeroElement(tgtHero);
                                try { tTypeId = IntProp(tgtHero, "TypeId"); } catch { }
                                tEff = ReadActiveEffects(tgtHero);
                                try { tStamina = ReadFixedRaw(tgtHero, "Stamina"); } catch { }
                                try { tLevel = IntProp(tgtHero, "Level"); } catch { }
                            }
                        }
                        catch { }
                        try { isEvaded = (bool)Prop(eff, "IsEvaded"); } catch { }
                        // EffectContext exposes AppliedEffect + Effect (an
                        // EffectType) directly — no need to go through the
                        // ApplyContext path which returns null on damage events.
                        try
                        {
                            var ae = Prop(eff, "AppliedEffect");
                            if (ae != null)
                            {
                                skillTypeId = IntProp(ae, "SkillTypeId");
                            }
                            // Fallback: native memory walk via EffectContext.
                            // Boss-source events have AppliedEffect=null at
                            // the EffectContext+0x40 offset; the actual skill
                            // info lives in SkillContext+SomeField. Try the
                            // top-level AppliedEffect first, then walk
                            // SkillContext (offset 0x98) for the boss path.
                            if (skillTypeId == 0 && eff is Il2CppSystem.Object il2eff)
                            {
                                try
                                {
                                    IntPtr effPtr = il2eff.Pointer;
                                    if ((long)effPtr > 0x10000)
                                    {
                                        // EffectContext.AppliedEffect @0x40
                                        IntPtr aePtr = Marshal.ReadIntPtr(effPtr + 0x40);
                                        if ((long)aePtr > 0x10000)
                                        {
                                            skillTypeId = Marshal.ReadInt32(aePtr + 0x28);
                                        }
                                        // SkillContext path: offset 0x98 →
                                        // walk to find skill TypeId. Per the
                                        // diag schema dump 2026-04-13: EffectContext.
                                        // SkillContext:0x98 → BattleSkill → Type:0x10
                                        // → SkillType.Id:0x10
                                        if (skillTypeId == 0)
                                        {
                                            IntPtr skCtx = Marshal.ReadIntPtr(effPtr + 0x98);
                                            if ((long)skCtx > 0x10000)
                                            {
                                                // SkillContext.Skill (BattleSkill) @0x28 typically
                                                IntPtr battleSk = Marshal.ReadIntPtr(skCtx + 0x28);
                                                if ((long)battleSk > 0x10000)
                                                {
                                                    // BattleSkill.Type (SkillType) @0x10
                                                    IntPtr skType = Marshal.ReadIntPtr(battleSk + 0x10);
                                                    if ((long)skType > 0x10000)
                                                    {
                                                        // SkillType.Id @0x10
                                                        skillTypeId = Marshal.ReadInt32(skType + 0x10);
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                                catch { }
                            }
                            var et = Prop(eff, "Effect");
                            if (et != null)
                            {
                                // EffectType.KindId is an enum (Damage=6000,
                                // ApplyDebuff=5000, ContinuousDamage=3007,
                                // AoEContinuousDamage=3014, ...).
                                var kindObj = Prop(et, "KindId");
                                if (kindObj != null)
                                {
                                    try { effectKind = Convert.ToInt32(kindObj); } catch { effectKind = 0; }
                                }
                            }
                        }
                        catch { }
                        var dctx = Prop(eff, "DamageContext");
                        if (dctx != null)
                        {
                            try { isBlocked = (bool)Prop(dctx, "IsBlocked"); } catch { }
                            // HitType is Nullable<HitType>. Unwrap via HasValue/Value
                            // — direct ToString() of a Nullable wrapper returns
                            // the wrapper's type name, not the underlying enum.
                            try
                            {
                                var ht = Prop(dctx, "HitType");
                                if (ht != null)
                                {
                                    var hasValProp = ht.GetType().GetProperty("HasValue");
                                    var valProp = ht.GetType().GetProperty("Value");
                                    if (hasValProp != null && (bool)hasValProp.GetValue(ht))
                                    {
                                        var enumVal = valProp.GetValue(ht);
                                        if (enumVal != null)
                                        {
                                            hitType = enumVal.ToString();
                                            // HitType { Normal=0, Crushing=1, Critical=2, Glancing=3 }
                                            try { isCrit = (Convert.ToInt32(enumVal) == 2); } catch { }
                                        }
                                    }
                                }
                            }
                            catch { }
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
                            // DamageContext exposes the resolved DEF modifier
                            // (post DEF-Down, Weaken, IgnoreDef etc.) and the
                            // raw multiplier value used in the calc. Capturing
                            // both means we can verify each stage of the
                            // pipeline against the IL2CPP method behaviour.
                            try { calcDefMod = ReadFixedRaw(dctx, "DefenceModifier"); } catch { }
                            try { calcMul    = ReadFixedRaw(dctx, "MultiplierValuePositive"); } catch { }
                            // Trigger the schema dump on first hit (already wired).
                            try { var calc = Prop(dctx, "CalculatedDamage"); if (calc != null) DumpDamageResultOnce(calc, "CalculatedDamage"); } catch { }
                        }
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
                // Phase 5 stat snapshot — only emit when read succeeded.
                if (pAtk     >= 0) sb.Append(",\"p_atk\":").Append(pAtk);
                if (pCd      >= 0) sb.Append(",\"p_cd\":").Append(pCd);
                if (pCr      >= 0) sb.Append(",\"p_cr\":").Append(pCr);
                if (tDef     >= 0) sb.Append(",\"t_def\":").Append(tDef);
                if (tHpMax   >= 0) sb.Append(",\"t_hp_max\":").Append(tHpMax);
                if (tHp      >= 0) sb.Append(",\"t_hp\":").Append(tHp);
                if (pStamina >= 0) sb.Append(",\"p_tm\":").Append(pStamina);
                if (tStamina >= 0) sb.Append(",\"t_tm\":").Append(tStamina);
                if (pLevel   >= 0) sb.Append(",\"p_lvl\":").Append(pLevel);
                if (tLevel   >= 0) sb.Append(",\"t_lvl\":").Append(tLevel);
                if (calcDefMod >= 0) sb.Append(",\"def_mod\":").Append(calcDefMod);
                if (calcMul    >= 0) sb.Append(",\"mul\":").Append(calcMul);
                if (pElem      >= 0) sb.Append(",\"p_elem\":").Append(pElem);
                if (tElem      >= 0) sb.Append(",\"t_elem\":").Append(tElem);
                if (pTypeId    >= 0) sb.Append(",\"p_typeid\":").Append(pTypeId);
                if (tTypeId    >= 0) sb.Append(",\"t_typeid\":").Append(tTypeId);
                if (!string.IsNullOrEmpty(pEff)) sb.Append(",\"p_eff\":").Append(pEff);
                if (!string.IsNullOrEmpty(tEff)) sb.Append(",\"t_eff\":").Append(tEff);
                sb.Append("}");
                string entry = sb.ToString();
                lock (_tickLog) { if (_tickLog.Count < 20000) _tickLog.Add(entry); }
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
                lock (_tickLog) { if (_tickLog.Count < 20000) _tickLog.Add(entry); }
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
                lock (_tickLog) { if (_tickLog.Count < 20000) _tickLog.Add(entry); }
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
                lock (_tickLog) { if (_tickLog.Count < 20000) _tickLog.Add(entry); }
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
                lock (_tickLog) { if (_tickLog.Count < 20000) _tickLog.Add(sb.ToString()); }
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
                lock (_tickLog) { if (_tickLog.Count < 20000) _tickLog.Add(sb.ToString()); }
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
                lock (_tickLog) { if (_tickLog.Count < 20000) _tickLog.Add(entry); }
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
                    lock (_tickLog) { if (_tickLog.Count < 20000) _tickLog.Add(d); }
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
                lock (_tickLog) { if (_tickLog.Count < 20000) _tickLog.Add(entry); }
            }
            catch (Exception ex)
            {
                string d = "{\"kind\":\"diag_cmd\",\"tick\":" + _battleCommandCount + ",\"err\":\"" + Esc(ex.Message) + "\"}";
                lock (_tickLog) { if (_tickLog.Count < 20000) _tickLog.Add(d); }
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
                     + ",\"UnapplyExecute\":" + _hookDiag_UnapplyExecute
                     + ",\"DefReduction\":" + _hookDiag_DefReduction + "}");
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
                            if (_tickLog.Count < 20000)
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
                lock (_tickLog) { if (_tickLog.Count < 20000) _tickLog.Add(sbe.ToString()); }
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
