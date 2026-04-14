using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;
using System.Net;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using MelonLoader;
using UnityEngine;
using UnityEngine.SceneManagement;

[assembly: MelonInfo(typeof(RaidAutomation.RaidPlugin), "RaidAutomation", "1.0.0", "PyAutoRaid")]

namespace RaidAutomation
{
    public class RaidPlugin : MelonPlugin
    {
        private HttpListener _listener;
        private Thread _serverThread;
        private bool _running;
        private const int PORT = 6790;
        private bool _autoDismissOverlays = true;
        private float _lastOverlayCheck;
        private int _overlaysDismissed;

        // Known overlay prefixes to auto-dismiss
        private static readonly string[] AUTO_DISMISS_PREFIXES = {
            "[OV] OneTimeOfferOverlay",
            "[OV] BankOfferOverlay",
            "[OV] SpecialOfferOverlay",
            "[OV] Daily14DaysRewardProgram",
            "[OV] CompensationInfoOverlay",
            "[OV] GiftCodeOverlay",
            "[OV] PromoCodeOverlay",
        };

        // IL2CPP native API imports for runtime type discovery
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_domain_get();
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_domain_get_assemblies(IntPtr domain, ref uint count);
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_assembly_get_image(IntPtr assembly);
        [DllImport("GameAssembly")]
        static extern uint il2cpp_image_get_class_count(IntPtr image);
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_image_get_class(IntPtr image, uint index);
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_class_get_name(IntPtr klass);
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_class_get_namespace(IntPtr klass);
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_class_get_fields(IntPtr klass, ref IntPtr iter);
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_field_get_name(IntPtr field);
        [DllImport("GameAssembly")]
        static extern int il2cpp_field_get_offset(IntPtr field);
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_class_get_methods(IntPtr klass, ref IntPtr iter);
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_method_get_name(IntPtr method);
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_runtime_invoke(IntPtr method, IntPtr obj, IntPtr args, ref IntPtr exc);

        // Queue for main-thread execution (Unity API is not thread-safe)
        private static readonly ConcurrentQueue<Action> MainThreadQueue = new ConcurrentQueue<Action>();

        public override void OnInitializeMelon()
        {
            LoggerInstance.Msg("RaidAutomation starting on port " + PORT);
            // Subscribe to Unity's update loop for main-thread work
            MelonEvents.OnUpdate.Subscribe(ProcessMainThreadQueue);
            StartHttpServer();
        }

        public override void OnDeinitializeMelon()
        {
            _running = false;
            try { _listener.Stop(); } catch { }
        }

        private void ProcessMainThreadQueue()
        {
            while (MainThreadQueue.TryDequeue(out var action))
            {
                try { action(); } catch { }
            }
            // Auto-dismiss known overlays every 2 seconds
            if (_autoDismissOverlays && Time.time - _lastOverlayCheck > 2f)
            {
                _lastOverlayCheck = Time.time;
                try { AutoDismissOverlays(); } catch { }
            }
        }

        private void AutoDismissOverlays()
        {
            var overlayParent = GameObject.Find("UIManager/Canvas (Ui Root)/OverlayDialogs");
            if (overlayParent == null) return;
            for (int i = 0; i < overlayParent.transform.childCount; i++)
            {
                var child = overlayParent.transform.GetChild(i).gameObject;
                if (!child.activeSelf) continue;
                string name = child.name;
                foreach (var prefix in AUTO_DISMISS_PREFIXES)
                {
                    if (name.StartsWith(prefix))
                    {
                        // Destroy the overlay — SetActive/raycaster disable gets undone by game
                        UnityEngine.Object.Destroy(child);
                        _overlaysDismissed++;
                        LoggerInstance.Msg($"Auto-dismissed (destroyed): {name}");
                        break;
                    }
                }
            }
            // Also dismiss MessageBoxes (confirmation dialogs from offer closes)
            var msgParent = GameObject.Find("UIManager/Canvas (Ui Root)/MessageBoxes");
            if (msgParent == null) return;
            for (int i = 0; i < msgParent.transform.childCount; i++)
            {
                var child = msgParent.transform.GetChild(i).gameObject;
                if (!child.activeSelf) continue;
                // Click the close/decline button (last button)
                var btns = child.GetComponentsInChildren<UnityEngine.UI.Button>();
                if (btns != null && btns.Length > 0)
                {
                    var closeBtn = btns[btns.Length - 1]; // last button = usually close
                    closeBtn.onClick.Invoke();
                    _overlaysDismissed++;
                }
            }
        }

        /// <summary>
        /// Execute a function on Unity's main thread and wait for the result.
        /// All Unity API calls MUST go through this.
        /// </summary>
        private T RunOnMainThread<T>(Func<T> func, int timeoutMs = 5000)
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

            if (!done.Wait(timeoutMs))
                throw new TimeoutException("Main thread call timed out");
            if (error != null)
                throw error;
            return result;
        }

        // === HTTP Server ===

        private void StartHttpServer()
        {
            _running = true;
            _serverThread = new Thread(ServerLoop);
            _serverThread.IsBackground = true;
            _serverThread.Start();
        }

        private void ServerLoop()
        {
            try
            {
                _listener = new HttpListener();
                _listener.Prefixes.Add("http://localhost:" + PORT + "/");
                _listener.Start();
                LoggerInstance.Msg("HTTP API ready on port " + PORT);
                while (_running)
                {
                    try
                    {
                        var ctx = _listener.GetContext();
                        var c = ctx;
                        ThreadPool.QueueUserWorkItem(delegate { HandleRequest(c); });
                    }
                    catch (HttpListenerException) { if (!_running) break; }
                    catch (Exception ex) { LoggerInstance.Error("HTTP: " + ex.Message); }
                }
            }
            catch (Exception ex) { LoggerInstance.Error("Server: " + ex); }
        }

        private void HandleRequest(HttpListenerContext ctx)
        {
            string path = ctx.Request.Url.AbsolutePath;
            string query = ctx.Request.Url.Query;
            string response;

            try
            {
                switch (path)
                {
                    case "/status":
                        response = RunOnMainThread(() => GetStatus());
                        break;
                    case "/buttons":
                        response = RunOnMainThread(() => ListButtons());
                        break;
                    case "/click":
                        string cp = QP(query, "path");
                        response = RunOnMainThread(() => ClickByPath(cp));
                        break;
                    case "/find":
                        string fn = QP(query, "name");
                        response = RunOnMainThread(() => FindObjects(fn));
                        break;
                    case "/pointer-click":
                        string pp = QP(query, "path");
                        response = RunOnMainThread(() => PointerClick(pp));
                        break;
                    case "/components":
                        string cp2 = QP(query, "path");
                        response = RunOnMainThread(() => ListComponents(cp2));
                        break;
                    case "/navigate":
                        string target = QP(query, "target");
                        response = RunOnMainThread(() => NavigateTo(target));
                        break;
                    case "/arena/fight":
                        int aidx = int.TryParse(QP(query, "index"), out int ai) ? ai : 0;
                        response = RunOnMainThread(() => ArenaFight(aidx));
                        break;
                    case "/arena/select":
                        int sidx = int.TryParse(QP(query, "index"), out int si) ? si : 0;
                        response = RunOnMainThread(() => ArenaSelectOpponent(sidx));
                        break;
                    case "/invoke":
                        string className2 = QP(query, "class");
                        string methodName = QP(query, "method");
                        response = InvokeOnInstance(className2, methodName);
                        break;
                    case "/scene":
                        int md = int.TryParse(QP(query, "depth"), out int d) ? d : 2;
                        response = RunOnMainThread(() => DumpScene(md));
                        break;
                    case "/offsets":
                        response = GetOffsets();
                        break;
                    case "/dismiss":
                        response = RunOnMainThread(() => DismissOverlays());
                        break;
                    case "/auto-dismiss":
                        string adVal = QP(query, "enabled");
                        if (adVal == "false" || adVal == "0")
                            _autoDismissOverlays = false;
                        else if (adVal == "true" || adVal == "1")
                            _autoDismissOverlays = true;
                        response = "{\"auto_dismiss\":" + (_autoDismissOverlays ? "true" : "false") +
                                   ",\"dismissed_total\":" + _overlaysDismissed + "}";
                        break;
                    case "/view-context":
                        string vcPath = QP(query, "path");
                        response = RunOnMainThread(() => GetViewContext(vcPath));
                        break;
                    case "/context-call":
                        string ccPath = QP(query, "path");
                        string ccMethod = QP(query, "method");
                        string ccArg = QP(query, "arg");
                        response = RunOnMainThread(() => CallOnViewContext(ccPath, ccMethod, ccArg));
                        break;
                    case "/bindings":
                        string bPath = QP(query, "path");
                        response = RunOnMainThread(() => InspectBindings(bPath));
                        break;
                    case "/hero-gear":
                        int hgHeroId = int.TryParse(QP(query, "hero_id"), out int hgId) ? hgId : 0;
                        response = RunOnMainThread(() => GetHeroGear(hgHeroId));
                        break;
                    case "/all-heroes":
                        response = RunOnMainThread(() => GetAllHeroesData());
                        break;
                    default:
                        response = "{\"endpoints\":[\"/status\",\"/buttons\",\"/click?path=X\",\"/find?name=X\",\"/scene?depth=N\",\"/offsets\"]}";
                        break;
                }
            }
            catch (Exception ex)
            {
                response = "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }

            byte[] buf = Encoding.UTF8.GetBytes(response);
            ctx.Response.ContentType = "application/json";
            ctx.Response.ContentLength64 = buf.Length;
            ctx.Response.OutputStream.Write(buf, 0, buf.Length);
            ctx.Response.Close();
        }

        // === API Handlers (run on main thread) ===

        private string GetStatus()
        {
            var scene = SceneManager.GetActiveScene();
            return "{\"mod\":\"RaidAutomation\",\"scene\":\"" + Esc(scene.name) +
                   "\",\"roots\":" + scene.GetRootGameObjects().Length + "}";
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
            if (string.IsNullOrEmpty(objPath))
                return "{\"error\":\"path required\"}";
            var go = GameObject.Find(objPath);
            if (go == null)
                return "{\"error\":\"not found\"}";
            // Use both onClick AND pointer events for maximum compatibility
            // (onClick.Invoke alone fails with new Unity Input System)
            var btn = go.GetComponent<UnityEngine.UI.Button>();
            var ped = new UnityEngine.EventSystems.PointerEventData(
                UnityEngine.EventSystems.EventSystem.current);
            ped.button = UnityEngine.EventSystems.PointerEventData.InputButton.Left;
            if (btn != null)
                btn.onClick.Invoke();
            UnityEngine.EventSystems.ExecuteEvents.Execute(go,
                ped, UnityEngine.EventSystems.ExecuteEvents.pointerClickHandler);
            UnityEngine.EventSystems.ExecuteEvents.Execute(go,
                ped, UnityEngine.EventSystems.ExecuteEvents.submitHandler);
            return "{\"clicked\":\"" + Esc(objPath) + "\"}";
        }

        // === Arena Direct IL2CPP Fight ===

        [DllImport("GameAssembly")]
        static extern int il2cpp_method_get_param_count(IntPtr method);

        private string ArenaFight(int opponentIndex)
        {
            // Find OpenHeroesSelectionDialog(ArenaOpponent) static method
            // Prefer the classic ArenaDialog context, not Arena3x3
            IntPtr domain = il2cpp_domain_get();
            uint asmCount = 0;
            IntPtr asmArray = il2cpp_domain_get_assemblies(domain, ref asmCount);

            IntPtr targetMethod = IntPtr.Zero;
            string targetClass = "";
            IntPtr fallbackMethod = IntPtr.Zero;
            string fallbackClass = "";
            for (uint a = 0; a < asmCount; a++)
            {
                IntPtr asm = Marshal.ReadIntPtr(asmArray, (int)(a * (uint)IntPtr.Size));
                IntPtr image = il2cpp_assembly_get_image(asm);
                uint classCount = il2cpp_image_get_class_count(image);
                for (uint c = 0; c < classCount; c++)
                {
                    IntPtr klass = il2cpp_image_get_class(image, c);
                    if (klass == IntPtr.Zero) continue;
                    string cn = Marshal.PtrToStringAnsi(il2cpp_class_get_name(klass));
                    string cns = Marshal.PtrToStringAnsi(il2cpp_class_get_namespace(klass));
                    IntPtr mIter = IntPtr.Zero;
                    IntPtr m;
                    while ((m = il2cpp_class_get_methods(klass, ref mIter)) != IntPtr.Zero)
                    {
                        string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                        if (mn == "OpenHeroesSelectionDialog" && il2cpp_method_get_param_count(m) == 1)
                        {
                            string full = cns + "." + cn;
                            // Prefer classic ArenaBattleTabContext over Arena3x3
                            if (cn == "ArenaBattleTabContext" || (cns.Contains("ArenaDialog") && !cns.Contains("3x3")))
                            {
                                targetMethod = m;
                                targetClass = full;
                            }
                            else if (fallbackMethod == IntPtr.Zero)
                            {
                                fallbackMethod = m;
                                fallbackClass = full;
                            }
                        }
                    }
                    if (targetMethod != IntPtr.Zero) break;
                }
                if (targetMethod != IntPtr.Zero) break;
            }
            if (targetMethod == IntPtr.Zero && fallbackMethod != IntPtr.Zero)
            {
                targetMethod = fallbackMethod;
                targetClass = fallbackClass;
            }

            if (targetMethod == IntPtr.Zero)
                return "{\"error\":\"OpenHeroesSelectionDialog(1 param) not found\"}";

            // Get the ArenaOpponent object from memory
            // Chain: AppModel._userWrapper.Arena.Opponents[index]
            // We need to find AppModel first
            IntPtr gaBase = IntPtr.Zero;
            foreach (System.Diagnostics.ProcessModule mod in System.Diagnostics.Process.GetCurrentProcess().Modules)
            {
                if (mod.ModuleName.Equals("GameAssembly.dll", StringComparison.OrdinalIgnoreCase))
                { gaBase = mod.BaseAddress; break; }
            }

            // Use our type resolution to find AppModel singleton
            IntPtr appModelClass = IntPtr.Zero;
            for (uint a = 0; a < asmCount && appModelClass == IntPtr.Zero; a++)
            {
                IntPtr asm = Marshal.ReadIntPtr(asmArray, (int)(a * (uint)IntPtr.Size));
                IntPtr image = il2cpp_assembly_get_image(asm);
                uint cc = il2cpp_image_get_class_count(image);
                for (uint c = 0; c < cc; c++)
                {
                    IntPtr k = il2cpp_image_get_class(image, c);
                    if (k == IntPtr.Zero) continue;
                    string cn = Marshal.PtrToStringAnsi(il2cpp_class_get_name(k));
                    if (cn == "AppModel")
                    {
                        string ns = Marshal.PtrToStringAnsi(il2cpp_class_get_namespace(k));
                        if (ns == "Client.Model") { appModelClass = k; break; }
                    }
                }
            }

            if (appModelClass == IntPtr.Zero)
                return "{\"error\":\"AppModel class not found\"}";

            // Get singleton: klass -> +0xC8 -> +0x08 -> +0xB8 -> +0x08
            IntPtr p = appModelClass;
            int[] chain = { 0xC8, 0x08, 0xB8, 0x08 };
            foreach (int off in chain)
            {
                p = Marshal.ReadIntPtr(p, off);
                if (p == IntPtr.Zero) return "{\"error\":\"singleton chain broken\"}";
            }
            IntPtr appModel = p;

            // Navigate: AppModel._userWrapper (0x1C8) -> Arena (0xB0) -> data
            IntPtr userWrapper = Marshal.ReadIntPtr(appModel, 0x1C8);
            if (userWrapper == IntPtr.Zero) return "{\"error\":\"userWrapper null\"}";

            IntPtr arenaWrapper = Marshal.ReadIntPtr(userWrapper, 0xB0);
            if (arenaWrapper == IntPtr.Zero) return "{\"error\":\"arenaWrapper null\"}";

            // ArenaWrapper -> _data (0x40) -> opponents (0x18) -> List._items (0x10) -> array[index]
            IntPtr arenaData = Marshal.ReadIntPtr(arenaWrapper, 0x40);
            if (arenaData == IntPtr.Zero) return "{\"error\":\"arenaData null (0x40)\"}";

            IntPtr opponentsList = Marshal.ReadIntPtr(arenaData, 0x18);
            if (opponentsList == IntPtr.Zero) return "{\"error\":\"opponents list null (0x18)\"}";

            IntPtr items = Marshal.ReadIntPtr(opponentsList, 0x10);  // List._items
            int size = Marshal.ReadInt32(opponentsList, 0x18);       // List._size
            if (items == IntPtr.Zero || size <= 0)
                return "{\"error\":\"opponents empty\",\"size\":" + size + "}";

            if (opponentIndex >= size)
                return "{\"error\":\"index out of range\",\"size\":" + size + ",\"index\":" + opponentIndex + "}";

            // Array items start at +0x20 (IL2CPP array header)
            IntPtr opponent = Marshal.ReadIntPtr(items, 0x20 + opponentIndex * 8);
            if (opponent == IntPtr.Zero)
                return "{\"error\":\"opponent at index " + opponentIndex + " is null\"}";

            // Call OpenHeroesSelectionDialog(opponent)
            try
            {
                IntPtr exc = IntPtr.Zero;
                IntPtr argsBuffer = Marshal.AllocHGlobal(IntPtr.Size);
                Marshal.WriteIntPtr(argsBuffer, opponent);
                il2cpp_runtime_invoke(targetMethod, IntPtr.Zero, argsBuffer, ref exc);
                Marshal.FreeHGlobal(argsBuffer);
                if (exc != IntPtr.Zero)
                    return "{\"error\":\"invoke exception\"}";
                return "{\"arena_fight\":" + opponentIndex + ",\"size\":" + size +
                       ",\"class\":\"" + Esc(targetClass) + "\"}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // === Invoke method on IL2CPP instance by class name ===

        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_class_get_type(IntPtr klass);
        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_type_get_object(IntPtr type);

        private string InvokeOnInstance(string className, string methodName)
        {
            if (string.IsNullOrEmpty(className) || string.IsNullOrEmpty(methodName))
                return "{\"error\":\"class and method required\"}";

            // Find the IL2CPP class
            IntPtr domain = il2cpp_domain_get();
            uint asmCount = 0;
            IntPtr asmArray = il2cpp_domain_get_assemblies(domain, ref asmCount);

            IntPtr targetClass = IntPtr.Zero;
            IntPtr targetMethod = IntPtr.Zero;
            string foundNs = "";

            for (uint a = 0; a < asmCount && targetClass == IntPtr.Zero; a++)
            {
                IntPtr asm = Marshal.ReadIntPtr(asmArray, (int)(a * (uint)IntPtr.Size));
                IntPtr image = il2cpp_assembly_get_image(asm);
                uint classCount = il2cpp_image_get_class_count(image);
                for (uint c = 0; c < classCount; c++)
                {
                    IntPtr k = il2cpp_image_get_class(image, c);
                    if (k == IntPtr.Zero) continue;
                    string cn = Marshal.PtrToStringAnsi(il2cpp_class_get_name(k));
                    if (cn == className)
                    {
                        // Find the method
                        IntPtr mIter = IntPtr.Zero;
                        IntPtr m;
                        while ((m = il2cpp_class_get_methods(k, ref mIter)) != IntPtr.Zero)
                        {
                            string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                            if (mn == methodName && il2cpp_method_get_param_count(m) == 0)
                            {
                                targetClass = k;
                                targetMethod = m;
                                foundNs = Marshal.PtrToStringAnsi(il2cpp_class_get_namespace(k));
                                break;
                            }
                        }
                        if (targetClass != IntPtr.Zero) break;
                    }
                }
            }

            if (targetClass == IntPtr.Zero)
            {
                // Class found but method not? List available methods
                IntPtr foundClass = IntPtr.Zero;
                for (uint a = 0; a < asmCount && foundClass == IntPtr.Zero; a++)
                {
                    IntPtr asm2 = Marshal.ReadIntPtr(asmArray, (int)(a * (uint)IntPtr.Size));
                    IntPtr image2 = il2cpp_assembly_get_image(asm2);
                    uint cc2 = il2cpp_image_get_class_count(image2);
                    for (uint c2 = 0; c2 < cc2; c2++)
                    {
                        IntPtr k2 = il2cpp_image_get_class(image2, c2);
                        if (k2 == IntPtr.Zero) continue;
                        if (Marshal.PtrToStringAnsi(il2cpp_class_get_name(k2)) == className)
                        { foundClass = k2; break; }
                    }
                }
                if (foundClass != IntPtr.Zero)
                {
                    var methods = new List<string>();
                    IntPtr mIter2 = IntPtr.Zero;
                    IntPtr m2;
                    while ((m2 = il2cpp_class_get_methods(foundClass, ref mIter2)) != IntPtr.Zero)
                        methods.Add(Marshal.PtrToStringAnsi(il2cpp_method_get_name(m2)));
                    return "{\"error\":\"method not found\",\"class\":\"" + className +
                           "\",\"methods\":[" + string.Join(",", methods.ConvertAll(m => "\"" + m + "\"")) + "]}";
                }
                return "{\"error\":\"class not found: " + className + "\"}";
            }

            // Find the context instance by scanning MonoBehaviours on dialog GameObjects
            // Each View MonoBehaviour has a _context field (we don't know the exact offset,
            // so we'll read each MonoBehaviour's IL2CPP fields to find the context)

            string[] dialogPaths = {
                "UIManager/Canvas (Ui Root)/Dialogs/[DV] ArenaDialog",
                "UIManager/Canvas (Ui Root)/Dialogs/[DV] ArenaDialog/Workspace",
                "UIManager/Canvas (Ui Root)/Dialogs/[DV] ArenaDialog/Workspace/Content",
                "UIManager/Canvas (Ui Root)/Dialogs/[DV] ArenaDialog/Workspace/Content/Tabs/Battle_h",
                "UIManager/Canvas (Ui Root)/Dialogs/[DV] ArenaDialog/Workspace/Content/Tabs/Battle_h/ArenaBattleTab(Clone)",
                "UIManager/Canvas (Ui Root)/Dialogs/[DV] AllianceEnemiesDialog",
                "UIManager/Canvas (Ui Root)/Dialogs/[DV] AllianceEnemiesDialog/Workspace",
            };

            return RunOnMainThread(() =>
            {
                string scanned = "";
                foreach (string path in dialogPaths)
                {
                    var go = GameObject.Find(path);
                    if (go == null) continue;

                    // Scan this GO and all children (depth 3)
                    var toScan = new List<Transform> { go.transform };
                    for (int d = 0; d < 3; d++)
                    {
                        var next = new List<Transform>();
                        foreach (var t in toScan)
                        {
                            for (int i = 0; i < t.childCount && i < 20; i++)
                                next.Add(t.GetChild(i));
                        }
                        toScan.AddRange(next);
                    }

                    foreach (var t in toScan)
                    {
                        var monos = t.gameObject.GetComponents<MonoBehaviour>();
                        if (monos == null) continue;
                        foreach (var mono in monos)
                        {
                            if (mono == null) continue;
                            IntPtr monoPtr = mono.Pointer;
                            IntPtr monoClass = il2cpp_object_get_class(monoPtr);

                            // Check all pointer-sized fields for context objects
                            // Scan first 20 fields (covering offset 0x10 to 0xB0)
                            for (int off = 0x10; off <= 0xB0; off += 8)
                            {
                                try
                                {
                                    IntPtr fieldVal = Marshal.ReadIntPtr(monoPtr, off);
                                    if (fieldVal == IntPtr.Zero || fieldVal.ToInt64() < 0x10000) continue;

                                    IntPtr fieldClass = il2cpp_object_get_class(fieldVal);
                                    if (fieldClass == IntPtr.Zero) continue;

                                    string fieldClassName = Marshal.PtrToStringAnsi(il2cpp_class_get_name(fieldClass));
                                    if (fieldClassName == className)
                                    {
                                        // Found the context! Call the method
                                        IntPtr exc = IntPtr.Zero;
                                        il2cpp_runtime_invoke(targetMethod, fieldVal, IntPtr.Zero, ref exc);
                                        if (exc != IntPtr.Zero)
                                            return "{\"error\":\"invoke exception on " + className + "\"}";
                                        return "{\"invoked\":\"" + methodName + "\",\"on\":\"" + className +
                                               "\",\"at\":\"" + Esc(t.name) + "\",\"offset\":\"0x" + off.ToString("X") + "\"}";
                                    }

                                    if (fieldClassName != null && !fieldClassName.StartsWith("Il2Cpp") &&
                                        fieldClassName.Length > 3 && fieldClassName.Contains("Context"))
                                        scanned += fieldClassName + ",";
                                }
                                catch { }
                            }
                        }
                    }
                }
                return "{\"error\":\"context instance not found\",\"contexts_found\":\"" + Esc(scanned) + "\"}";
            });
        }

        // === Arena Opponent Selection via Context ===

        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_object_get_class(IntPtr obj);

        private string ArenaSelectOpponent(int index)
        {
            // Find the ArenaBattleTab(Clone) via partial path match
            var tabGo = GameObject.Find(
                "UIManager/Canvas (Ui Root)/Dialogs/[DV] ArenaDialog/Workspace/Content/Tabs/Battle_h/ArenaBattleTab(Clone)");
            if (tabGo == null)
                return "{\"error\":\"ArenaBattleTab not found — is Arena dialog open?\"}";

            // The opponent row is Content/Opponents/Viewport/Content/{index}
            var opRow = tabGo.transform.Find($"Content/Opponents/Viewport/Content/{index}");
            if (opRow == null)
                return "{\"error\":\"opponent row " + index + " not found\"}";

            // The opponent row itself might have a click handler.
            // Try: simulate a full pointer event sequence on the row
            var ped = new UnityEngine.EventSystems.PointerEventData(
                UnityEngine.EventSystems.EventSystem.current);
            ped.button = UnityEngine.EventSystems.PointerEventData.InputButton.Left;
            // Set position to center of the opponent row (important for scroll rect handling)
            ped.position = opRow.GetComponent<RectTransform>() != null
                ? (Vector2)opRow.GetComponent<RectTransform>().position
                : Vector2.zero;
            ped.pressPosition = ped.position;
            ped.delta = Vector2.zero;

            var rowGo = opRow.gameObject;

            // First: try PointerDown + PointerUp + Click (simulates tap without drag)
            UnityEngine.EventSystems.ExecuteEvents.Execute(rowGo,
                ped, UnityEngine.EventSystems.ExecuteEvents.pointerDownHandler);
            UnityEngine.EventSystems.ExecuteEvents.Execute(rowGo,
                ped, UnityEngine.EventSystems.ExecuteEvents.pointerUpHandler);
            UnityEngine.EventSystems.ExecuteEvents.Execute(rowGo,
                ped, UnityEngine.EventSystems.ExecuteEvents.pointerClickHandler);

            // Also try the StartBattle_h child
            var startBattle = opRow.Find("StartBattle_h");
            string btnInfo = "no btn";
            if (startBattle != null)
            {
                var btn = startBattle.GetComponent<UnityEngine.UI.Button>();
                if (btn != null)
                {
                    int listenerCount = btn.onClick.GetPersistentEventCount();
                    btnInfo = $"listeners={listenerCount},interactable={btn.interactable}";
                    // Use OnSubmit instead of onClick.Invoke — provides EventSystem context
                    var submitData = new UnityEngine.EventSystems.BaseEventData(
                        UnityEngine.EventSystems.EventSystem.current);
                    btn.OnSubmit(submitData);
                }
                UnityEngine.EventSystems.ExecuteEvents.Execute(startBattle.gameObject,
                    ped, UnityEngine.EventSystems.ExecuteEvents.pointerClickHandler);
                UnityEngine.EventSystems.ExecuteEvents.Execute(startBattle.gameObject,
                    ped, UnityEngine.EventSystems.ExecuteEvents.submitHandler);
            }

            // Disable ScrollRect to prevent it from consuming click events
            var scrollParent = tabGo.transform.Find("Content/Opponents");
            if (scrollParent != null)
            {
                var scrollRect = scrollParent.GetComponent<UnityEngine.UI.ScrollRect>();
                if (scrollRect != null)
                {
                    scrollRect.enabled = false;
                    LoggerInstance.Msg("Disabled ScrollRect on Opponents");
                }
            }

            // Now retry the click with ScrollRect disabled
            if (startBattle != null)
            {
                var btn2 = startBattle.GetComponent<UnityEngine.UI.Button>();
                if (btn2 != null)
                {
                    btn2.onClick.Invoke();
                }
                var ped2 = new UnityEngine.EventSystems.PointerEventData(
                    UnityEngine.EventSystems.EventSystem.current);
                ped2.button = UnityEngine.EventSystems.PointerEventData.InputButton.Left;
                UnityEngine.EventSystems.ExecuteEvents.ExecuteHierarchy(startBattle.gameObject,
                    ped2, UnityEngine.EventSystems.ExecuteEvents.pointerClickHandler);
            }

            // Re-enable ScrollRect
            if (scrollParent != null)
            {
                var scrollRect2 = scrollParent.GetComponent<UnityEngine.UI.ScrollRect>();
                if (scrollRect2 != null)
                    scrollRect2.enabled = true;
            }

            // Try EventSystem select + submit (keyboard-style activation)
            if (startBattle != null)
            {
                var eventSys = UnityEngine.EventSystems.EventSystem.current;
                if (eventSys != null)
                {
                    eventSys.SetSelectedGameObject(startBattle.gameObject);
                    var submitData = new UnityEngine.EventSystems.BaseEventData(eventSys);
                    UnityEngine.EventSystems.ExecuteEvents.Execute(startBattle.gameObject,
                        submitData, UnityEngine.EventSystems.ExecuteEvents.submitHandler);
                }
            }

            // Find the MVVM context via the View component and invoke command
            // Search the tab and its parents for a BaseView component with a context
            string contextInfo = "none";
            Transform searchT = tabGo.transform;
            for (int depth = 0; depth < 5 && searchT != null; depth++)
            {
                // Try to find BaseView on this object by searching all components
                // Use IL2CPP to get the component's class name
                var allComps = searchT.gameObject.GetComponents<Component>();
                if (allComps != null)
                {
                    foreach (var comp in allComps)
                    {
                        if (comp == null) continue;
                        try
                        {
                            // Check if this component has InvokeCommandWithInt method
                            var type = comp.GetType();
                            var method = type.GetMethod("InvokeCommandWithInt",
                                System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Instance);
                            if (method != null)
                            {
                                method.Invoke(comp, new object[] { index });
                                contextInfo = "invoked on " + type.Name + " at depth " + depth;
                                break;
                            }
                        }
                        catch { }
                    }
                }
                if (contextInfo != "none") break;
                searchT = searchT.parent;
            }

            return "{\"selected\":" + index + ",\"btn\":\"" + Esc(btnInfo) +
                   "\",\"context\":\"" + Esc(contextInfo) +
                   "\",\"path\":\"" + Esc(GetPath(opRow)) + "\"}";
        }

        // Map navigation targets to their BattleModeEnabling class names
        private static readonly Dictionary<string, string> NAV_TARGETS = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            {"arena",     "ArenaBattleModeEnabling"},
            {"cb",        "AllianceActivityBattleModeEnabling"},
            {"clanboss",  "AllianceActivityBattleModeEnabling"},
            {"campaign",  "CampaignBattleModeEnabling"},
            {"dungeon",   "DungeonBattleModeEnabling"},
            {"faction",   "FactionWarsBattleModeEnabling"},
            {"find_openmode", "___SEARCH___"},
            {"list_context", "BattleModeSelectionDialogContext"},
        };

        private unsafe string NavigateTo(string target)
        {
            if (string.IsNullOrEmpty(target) || !NAV_TARGETS.ContainsKey(target))
                return "{\"error\":\"unknown target. Valid: " + string.Join(",", NAV_TARGETS.Keys) + "\"}";

            string className = NAV_TARGETS[target];
            string ns = className.Contains("Context")
                ? "Client.ViewModel.Contextes.BattleModeSelectionDialog"
                : "Client.ViewModel.Contextes.BattleModeSelectionDialog.ModeEnabling";

            // Find the class via IL2CPP
            IntPtr domain = il2cpp_domain_get();
            uint asmCount = 0;
            IntPtr asmArray = il2cpp_domain_get_assemblies(domain, ref asmCount);

            IntPtr klass = IntPtr.Zero;
            for (uint a = 0; a < asmCount && klass == IntPtr.Zero; a++)
            {
                IntPtr asm = Marshal.ReadIntPtr(asmArray, (int)(a * (uint)IntPtr.Size));
                IntPtr image = il2cpp_assembly_get_image(asm);
                uint classCount = il2cpp_image_get_class_count(image);
                for (uint c = 0; c < classCount; c++)
                {
                    IntPtr k = il2cpp_image_get_class(image, c);
                    if (k == IntPtr.Zero) continue;
                    string n = Marshal.PtrToStringAnsi(il2cpp_class_get_name(k));
                    if (n == className)
                    {
                        string cns = Marshal.PtrToStringAnsi(il2cpp_class_get_namespace(k));
                        if (cns == ns) { klass = k; break; }
                    }
                }
            }

            if (klass == IntPtr.Zero)
            {
                // If searching for a specific class failed, search for OpenBattleMode across all classes
                if (target == "find_openmode")
                {
                    IntPtr domain2 = il2cpp_domain_get();
                    uint ac2 = 0;
                    IntPtr aa2 = il2cpp_domain_get_assemblies(domain2, ref ac2);
                    var found2 = new List<string>();
                    for (uint a2 = 0; a2 < ac2 && found2.Count < 5; a2++)
                    {
                        IntPtr asm2 = Marshal.ReadIntPtr(aa2, (int)(a2 * (uint)IntPtr.Size));
                        IntPtr img2 = il2cpp_assembly_get_image(asm2);
                        uint cc2 = il2cpp_image_get_class_count(img2);
                        for (uint c2 = 0; c2 < cc2; c2++)
                        {
                            IntPtr k2 = il2cpp_image_get_class(img2, c2);
                            if (k2 == IntPtr.Zero) continue;
                            IntPtr mi = IntPtr.Zero;
                            IntPtr mm;
                            while ((mm = il2cpp_class_get_methods(k2, ref mi)) != IntPtr.Zero)
                            {
                                string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(mm));
                                if (mn == "OpenBattleMode")
                                {
                                    string cn = Marshal.PtrToStringAnsi(il2cpp_class_get_name(k2));
                                    string cns = Marshal.PtrToStringAnsi(il2cpp_class_get_namespace(k2));
                                    found2.Add(cns + "." + cn);
                                }
                            }
                        }
                    }
                    return "{\"classes_with_OpenBattleMode\":[" +
                        string.Join(",", found2.ConvertAll(f => "\"" + f + "\"")) + "]}";
                }
                return "{\"error\":\"class " + className + " not found\"}";
            }

            // Map target to static method name to search for
            var methodNames = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                {"arena", "OpenArenaDialog"},
                {"cb", "OpenClanBossDialog"},
                {"clanboss", "OpenClanBossDialog"},
                {"alliance", "OpenAlliance"},
                {"campaign", "OpenBattleMode"},
                {"dungeon", "OpenDungeonsHUD"},
                {"live_arena", "OpenLiveArena"},
                {"siege", "OpenSiege"},
                {"village", "MoveToVillage"},
                {"home", "MoveToVillage"},
            };
            string searchMethod = methodNames.ContainsKey(target) ? methodNames[target] : "OpenBattleMode";
            // Restrict search to the InGameTransition class for reliability
            string preferredClass = "WebViewInGameTransition";

            // Search for the method on WebViewInGameTransition first, then fall back to any class
            IntPtr openMethod = IntPtr.Zero;
            string foundOnClass = "";
            {
                uint asmCount2 = 0;
                IntPtr asmArray2 = il2cpp_domain_get_assemblies(domain, ref asmCount2);
                IntPtr fallbackMethod = IntPtr.Zero;
                string fallbackClass = "";
                for (uint a = 0; a < asmCount2; a++)
                {
                    IntPtr asm2 = Marshal.ReadIntPtr(asmArray2, (int)(a * (uint)IntPtr.Size));
                    IntPtr image2 = il2cpp_assembly_get_image(asm2);
                    uint classCount2 = il2cpp_image_get_class_count(image2);
                    for (uint c = 0; c < classCount2; c++)
                    {
                        IntPtr k2 = il2cpp_image_get_class(image2, c);
                        if (k2 == IntPtr.Zero) continue;
                        string cn = Marshal.PtrToStringAnsi(il2cpp_class_get_name(k2));
                        IntPtr mIter = IntPtr.Zero;
                        IntPtr m;
                        while ((m = il2cpp_class_get_methods(k2, ref mIter)) != IntPtr.Zero)
                        {
                            string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                            if (mn == searchMethod)
                            {
                                string fullName = Marshal.PtrToStringAnsi(il2cpp_class_get_namespace(k2)) + "." + cn;
                                if (cn == preferredClass)
                                {
                                    openMethod = m;
                                    foundOnClass = fullName;
                                }
                                else if (fallbackMethod == IntPtr.Zero)
                                {
                                    fallbackMethod = m;
                                    fallbackClass = fullName;
                                }
                            }
                        }
                        if (openMethod != IntPtr.Zero) break;
                    }
                    if (openMethod != IntPtr.Zero) break;
                }
                if (openMethod == IntPtr.Zero && fallbackMethod != IntPtr.Zero)
                {
                    openMethod = fallbackMethod;
                    foundOnClass = fallbackClass;
                }
            }

            if (openMethod == IntPtr.Zero)
            {
                // List all methods for debugging
                var methods = new List<string>();
                IntPtr iter2 = IntPtr.Zero;
                IntPtr m2;
                while ((m2 = il2cpp_class_get_methods(klass, ref iter2)) != IntPtr.Zero)
                {
                    methods.Add(Marshal.PtrToStringAnsi(il2cpp_method_get_name(m2)));
                }
                return "{\"error\":\"OpenBattleMode not found\",\"class\":\"" + className +
                       "\",\"methods\":[" + string.Join(",", methods.ConvertAll(m => "\"" + m + "\"")) + "]}";
            }

            // Invoke the static method
            try
            {
                IntPtr exc = IntPtr.Zero;
                il2cpp_runtime_invoke(openMethod, IntPtr.Zero, IntPtr.Zero, ref exc);
                if (exc != IntPtr.Zero)
                    return "{\"error\":\"invoke exception\",\"target\":\"" + Esc(target) + "\"}";
                return "{\"navigated\":\"" + Esc(target) + "\",\"method\":\"" + Esc(searchMethod) + "\",\"class\":\"" + Esc(foundOnClass) + "\"}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        private string ListComponents(string objPath)
        {
            if (string.IsNullOrEmpty(objPath))
                return "{\"error\":\"path required\"}";
            var go = GameObject.Find(objPath);
            if (go == null)
                return "{\"error\":\"not found\"}";
            // Try SendMessage to trigger any click handler
            try { go.SendMessage("OnClick", UnityEngine.SendMessageOptions.DontRequireReceiver); } catch {}
            try { go.SendMessage("OnPointerClick", UnityEngine.SendMessageOptions.DontRequireReceiver); } catch {}
            try { go.SendMessage("OnSubmit", UnityEngine.SendMessageOptions.DontRequireReceiver); } catch {}
            return "{\"sent_messages\":[\"OnClick\",\"OnPointerClick\",\"OnSubmit\"],\"path\":\"" + Esc(objPath) + "\"}";
        }

        private string PointerClick(string objPath)
        {
            if (string.IsNullOrEmpty(objPath))
                return "{\"error\":\"path required\"}";
            var go = GameObject.Find(objPath);
            if (go == null)
                return "{\"error\":\"not found\"}";
            // Force pointer event (bypasses Button.onClick — handles IPointerClickHandler, EventTrigger, etc.)
            var ped = new UnityEngine.EventSystems.PointerEventData(
                UnityEngine.EventSystems.EventSystem.current);
            ped.button = UnityEngine.EventSystems.PointerEventData.InputButton.Left;
            // Fire all pointer events: Enter, Down, Click, Up
            UnityEngine.EventSystems.ExecuteEvents.Execute(go,
                ped, UnityEngine.EventSystems.ExecuteEvents.pointerEnterHandler);
            UnityEngine.EventSystems.ExecuteEvents.Execute(go,
                ped, UnityEngine.EventSystems.ExecuteEvents.pointerDownHandler);
            UnityEngine.EventSystems.ExecuteEvents.Execute(go,
                ped, UnityEngine.EventSystems.ExecuteEvents.pointerClickHandler);
            UnityEngine.EventSystems.ExecuteEvents.Execute(go,
                ped, UnityEngine.EventSystems.ExecuteEvents.pointerUpHandler);
            return "{\"pointer_clicked\":\"" + Esc(objPath) + "\"}";
        }

        private string FindObjects(string search)
        {
            if (string.IsNullOrEmpty(search))
                return "{\"error\":\"name required\"}";
            var results = new List<string>();
            search = search.ToLower();
            foreach (var root in SceneManager.GetActiveScene().GetRootGameObjects())
                Search(root.transform, search, "", results, 50);
            var sb = new StringBuilder();
            sb.Append("{\"count\":" + results.Count + ",\"results\":[");
            for (int i = 0; i < results.Count; i++)
            {
                if (i > 0) sb.Append(",");
                sb.Append("\"" + Esc(results[i]) + "\"");
            }
            sb.Append("]}");
            return sb.ToString();
        }

        private string DumpScene(int maxDepth)
        {
            var sb = new StringBuilder();
            sb.Append("{\"roots\":[");
            var roots = SceneManager.GetActiveScene().GetRootGameObjects();
            for (int i = 0; i < roots.Length; i++)
            {
                if (i > 0) sb.Append(",");
                DumpGO(roots[i], sb, 0, maxDepth);
            }
            sb.Append("]}");
            return sb.ToString();
        }

        // === Overlay Dismissal ===

        private string DismissOverlays()
        {
            int dismissed = 0;
            // Click close buttons on overlays (don't deactivate — that breaks UI state)
            var overlayParent = GameObject.Find("UIManager/Canvas (Ui Root)/OverlayDialogs");
            if (overlayParent != null)
            {
                for (int i = 0; i < overlayParent.transform.childCount; i++)
                {
                    var child = overlayParent.transform.GetChild(i).gameObject;
                    if (!child.activeSelf) continue;
                    var btns = child.GetComponentsInChildren<UnityEngine.UI.Button>();
                    foreach (var btn in btns)
                    {
                        if (btn.gameObject.name.Contains("Close"))
                        {
                            btn.onClick.Invoke();
                            dismissed++;
                            break;
                        }
                    }
                }
            }
            var msgParent = GameObject.Find("UIManager/Canvas (Ui Root)/MessageBoxes");
            if (msgParent != null)
            {
                for (int i = 0; i < msgParent.transform.childCount; i++)
                {
                    var child = msgParent.transform.GetChild(i).gameObject;
                    if (!child.activeSelf) continue;
                    var btns = child.GetComponentsInChildren<UnityEngine.UI.Button>();
                    if (btns.Length > 0)
                    {
                        btns[btns.Length - 1].onClick.Invoke();
                        dismissed++;
                    }
                }
            }
            return "{\"dismissed\":" + dismissed + "}";
        }

        // === Offset Discovery (runs off main thread — no Unity API needed) ===

        // Types the memory reader needs, keyed by (namespace, name)
        private static readonly (string ns, string name)[] WatchedTypes = {
            ("Client.Model", "AppModel"),
            ("Client.ViewModel", "AppViewModel"),
            ("Client.Model.Gameplay.Wrappers", "UserWrapper"),
            ("Client.Model.Gameplay.Wrappers", "AccountWrapperReadOnly"),
            ("Client.Model.Gameplay.Wrappers", "HeroesWrapperReadOnly"),
            ("Client.Model.Gameplay.Wrappers", "ArenaWrapperReadOnly"),
            ("Client.Model.Gameplay.Wrappers", "BattleWrapperReadOnly"),
            ("SharedModel.Meta.Heroes", "Hero"),
            ("SharedModel.Meta.Heroes", "HeroType"),
            ("SharedModel.Meta.Account", "UserAccount"),
            ("SharedModel.Meta.Account", "Resources"),
            ("SharedModel.Meta.Battle", "BattleStateNotifier"),
        };

        private string GetOffsets()
        {
            var sb = new StringBuilder();
            sb.Append("{");

            // Find GameAssembly.dll base address
            IntPtr gaBase = IntPtr.Zero;
            foreach (ProcessModule mod in Process.GetCurrentProcess().Modules)
            {
                if (mod.ModuleName.Equals("GameAssembly.dll", StringComparison.OrdinalIgnoreCase))
                {
                    gaBase = mod.BaseAddress;
                    break;
                }
            }

            sb.Append("\"ga_base\":\"0x" + gaBase.ToString("X") + "\"");

            // Get IL2CPP domain and iterate all types
            IntPtr domain = il2cpp_domain_get();
            uint asmCount = 0;
            IntPtr asmArray = il2cpp_domain_get_assemblies(domain, ref asmCount);

            var found = new Dictionary<string, IntPtr>(); // "ns.name" -> klass ptr
            var watchSet = new HashSet<string>();
            foreach (var (ns, name) in WatchedTypes)
                watchSet.Add(ns + "." + name);

            for (uint a = 0; a < asmCount && found.Count < WatchedTypes.Length; a++)
            {
                IntPtr asm = Marshal.ReadIntPtr(asmArray, (int)(a * (uint)IntPtr.Size));
                IntPtr image = il2cpp_assembly_get_image(asm);
                uint classCount = il2cpp_image_get_class_count(image);

                for (uint c = 0; c < classCount; c++)
                {
                    IntPtr klass = il2cpp_image_get_class(image, c);
                    if (klass == IntPtr.Zero) continue;

                    string cName = Marshal.PtrToStringAnsi(il2cpp_class_get_name(klass));
                    string cNs = Marshal.PtrToStringAnsi(il2cpp_class_get_namespace(klass));
                    string full = cNs + "." + cName;

                    if (watchSet.Contains(full))
                        found[full] = klass;
                }
            }

            // Emit type info with singleton pointers and field offsets
            sb.Append(",\"types\":{");
            int ti = 0;
            foreach (var (ns, name) in WatchedTypes)
            {
                string full = ns + "." + name;
                if (!found.ContainsKey(full)) continue;

                IntPtr klass = found[full];
                if (ti > 0) sb.Append(",");
                ti++;

                sb.Append("\"" + Esc(name) + "\":{");
                sb.Append("\"klass\":\"0x" + klass.ToString("X") + "\"");

                // Try to resolve singleton instance for AppModel/AppViewModel
                // Chain: klass -> +0xC8 -> +0x08 -> +0xB8 (static_fields) -> +0x08 (_instance)
                if (name == "AppModel" || name == "AppViewModel")
                {
                    try
                    {
                        IntPtr p = klass;
                        int[] chain = { 0xC8, 0x08, 0xB8, 0x08 };
                        foreach (int off in chain)
                        {
                            p = Marshal.ReadIntPtr(p, off);
                            if (p == IntPtr.Zero) break;
                        }
                        if (p != IntPtr.Zero)
                            sb.Append(",\"instance\":\"0x" + p.ToString("X") + "\"");
                    }
                    catch { }
                }

                // Enumerate field offsets
                sb.Append(",\"fields\":{");
                IntPtr iter = IntPtr.Zero;
                int fi = 0;
                IntPtr field;
                while ((field = il2cpp_class_get_fields(klass, ref iter)) != IntPtr.Zero)
                {
                    string fname = Marshal.PtrToStringAnsi(il2cpp_field_get_name(field));
                    int foff = il2cpp_field_get_offset(field);
                    if (fi > 0) sb.Append(",");
                    sb.Append("\"" + Esc(fname) + "\":" + foff);
                    fi++;
                }
                sb.Append("}}");
            }
            sb.Append("}}");
            return sb.ToString();
        }

        // === View Context Discovery & Invocation ===

        /// <summary>
        /// Discover the MVVM context on a dialog/view by finding the BaseView component
        /// and reading its Context property. Returns context class name and methods.
        /// </summary>
        private string GetViewContext(string objPath)
        {
            if (string.IsNullOrEmpty(objPath))
            {
                // Default: scan all active dialogs
                var dialogParent = GameObject.Find("UIManager/Canvas (Ui Root)/Dialogs");
                if (dialogParent == null)
                    return "{\"error\":\"no dialog parent found\"}";

                var sb = new StringBuilder();
                sb.Append("{\"dialogs\":[");
                int found = 0;
                for (int i = 0; i < dialogParent.transform.childCount; i++)
                {
                    var child = dialogParent.transform.GetChild(i).gameObject;
                    if (!child.activeSelf) continue;
                    var contextInfo = FindContextOnHierarchy(child.transform, 5);
                    if (contextInfo != null)
                    {
                        if (found > 0) sb.Append(",");
                        sb.Append("{\"dialog\":\"" + Esc(child.name) + "\"," + contextInfo + "}");
                        found++;
                    }
                    else
                    {
                        if (found > 0) sb.Append(",");
                        sb.Append("{\"dialog\":\"" + Esc(child.name) + "\",\"context\":null}");
                        found++;
                    }
                }
                sb.Append("]}");
                return sb.ToString();
            }

            var go = GameObject.Find(objPath);
            if (go == null)
                return "{\"error\":\"not found: " + Esc(objPath) + "\"}";

            var info = FindContextOnHierarchy(go.transform, 6);
            if (info != null)
                return "{" + info + "}";

            return "{\"error\":\"no BaseView context found on hierarchy\"}";
        }

        /// <summary>
        /// Search a hierarchy for MonoBehaviours that have a Context property (BaseView subclasses).
        /// Returns JSON fragment with context class, ptr, and methods, or null.
        /// </summary>
        private string FindContextOnHierarchy(Transform root, int maxDepth)
        {
            var toScan = new Queue<(Transform t, int depth)>();
            toScan.Enqueue((root, 0));

            while (toScan.Count > 0)
            {
                var (t, depth) = toScan.Dequeue();
                var monos = t.gameObject.GetComponents<MonoBehaviour>();
                if (monos != null)
                {
                    foreach (var mono in monos)
                    {
                        if (mono == null) continue;
                        try
                        {
                            // Check if this MonoBehaviour has a Context property (BaseView)
                            IntPtr monoPtr = mono.Pointer;
                            IntPtr monoClass = il2cpp_object_get_class(monoPtr);
                            if (monoClass == IntPtr.Zero) continue;

                            // Walk up the class hierarchy looking for get_Context method
                            IntPtr klass = monoClass;
                            IntPtr getContextMethod = IntPtr.Zero;
                            while (klass != IntPtr.Zero && getContextMethod == IntPtr.Zero)
                            {
                                IntPtr mIter = IntPtr.Zero;
                                IntPtr m;
                                while ((m = il2cpp_class_get_methods(klass, ref mIter)) != IntPtr.Zero)
                                {
                                    string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                                    if (mn == "get_Context" && il2cpp_method_get_param_count(m) == 0)
                                    {
                                        getContextMethod = m;
                                        break;
                                    }
                                }
                                if (getContextMethod == IntPtr.Zero)
                                    klass = il2cpp_class_get_parent(klass);
                            }

                            if (getContextMethod == IntPtr.Zero) continue;

                            // Call get_Context on this mono to get the context instance
                            IntPtr exc = IntPtr.Zero;
                            IntPtr contextObj = il2cpp_runtime_invoke(getContextMethod, monoPtr, IntPtr.Zero, ref exc);
                            if (exc != IntPtr.Zero || contextObj == IntPtr.Zero) continue;

                            // Unbox if needed — get_Context returns an object reference
                            // The returned value is an Il2CppObject* wrapping the context
                            // For reference types, the pointer IS the object
                            IntPtr contextPtr = contextObj;

                            IntPtr contextClass = il2cpp_object_get_class(contextPtr);
                            if (contextClass == IntPtr.Zero) continue;

                            string contextClassName = Marshal.PtrToStringAnsi(il2cpp_class_get_name(contextClass));
                            string contextNs = Marshal.PtrToStringAnsi(il2cpp_class_get_namespace(contextClass));

                            // Skip generic/framework contexts
                            if (contextClassName == null || contextClassName.StartsWith("Il2Cpp")) continue;

                            // Collect methods on the context class (and parent classes)
                            var methods = new List<string>();
                            IntPtr ck = contextClass;
                            int classDepth = 0;
                            while (ck != IntPtr.Zero && classDepth < 5)
                            {
                                IntPtr mi2 = IntPtr.Zero;
                                IntPtr m2;
                                while ((m2 = il2cpp_class_get_methods(ck, ref mi2)) != IntPtr.Zero)
                                {
                                    string mn2 = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m2));
                                    if (!mn2.StartsWith(".") && !mn2.StartsWith("<"))
                                        methods.Add(mn2);
                                }
                                ck = il2cpp_class_get_parent(ck);
                                string parentName = ck != IntPtr.Zero ? Marshal.PtrToStringAnsi(il2cpp_class_get_name(ck)) : "";
                                if (parentName == "Object" || parentName == "Il2CppObjectBase") break;
                                classDepth++;
                            }

                            var sb = new StringBuilder();
                            sb.Append("\"context_class\":\"" + Esc(contextNs + "." + contextClassName) + "\"");
                            sb.Append(",\"context_ptr\":\"0x" + contextPtr.ToString("X") + "\"");
                            sb.Append(",\"view_class\":\"" + Esc(Marshal.PtrToStringAnsi(il2cpp_class_get_name(monoClass))) + "\"");
                            sb.Append(",\"view_path\":\"" + Esc(GetPath(t)) + "\"");
                            sb.Append(",\"methods\":[");
                            for (int mi = 0; mi < methods.Count && mi < 50; mi++)
                            {
                                if (mi > 0) sb.Append(",");
                                sb.Append("\"" + Esc(methods[mi]) + "\"");
                            }
                            sb.Append("]");
                            return sb.ToString();
                        }
                        catch { }
                    }
                }

                if (depth < maxDepth)
                {
                    for (int ci = 0; ci < t.childCount && ci < 30; ci++)
                        toScan.Enqueue((t.GetChild(ci), depth + 1));
                }
            }
            return null;
        }

        /// <summary>
        /// Call a method on the MVVM context of a view/dialog.
        /// First finds the BaseView, gets its Context, then invokes the named method.
        /// </summary>
        private string CallOnViewContext(string objPath, string methodName, string arg)
        {
            if (string.IsNullOrEmpty(objPath) || string.IsNullOrEmpty(methodName))
                return "{\"error\":\"path and method required\"}";

            var go = GameObject.Find(objPath);
            if (go == null)
                return "{\"error\":\"not found: " + Esc(objPath) + "\"}";

            // Find BaseView with context on this hierarchy
            var toScan = new Queue<(Transform t, int depth)>();
            toScan.Enqueue((go.transform, 0));

            while (toScan.Count > 0)
            {
                var (t, depth) = toScan.Dequeue();
                var monos = t.gameObject.GetComponents<MonoBehaviour>();
                if (monos != null)
                {
                    foreach (var mono in monos)
                    {
                        if (mono == null) continue;
                        try
                        {
                            IntPtr monoPtr = mono.Pointer;
                            IntPtr monoClass = il2cpp_object_get_class(monoPtr);
                            if (monoClass == IntPtr.Zero) continue;

                            // Find get_Context
                            IntPtr klass = monoClass;
                            IntPtr getCtxM = IntPtr.Zero;
                            while (klass != IntPtr.Zero && getCtxM == IntPtr.Zero)
                            {
                                IntPtr mIter = IntPtr.Zero;
                                IntPtr m;
                                while ((m = il2cpp_class_get_methods(klass, ref mIter)) != IntPtr.Zero)
                                {
                                    if (Marshal.PtrToStringAnsi(il2cpp_method_get_name(m)) == "get_Context" &&
                                        il2cpp_method_get_param_count(m) == 0)
                                    {
                                        getCtxM = m;
                                        break;
                                    }
                                }
                                if (getCtxM == IntPtr.Zero) klass = il2cpp_class_get_parent(klass);
                            }
                            if (getCtxM == IntPtr.Zero) continue;

                            IntPtr exc = IntPtr.Zero;
                            IntPtr ctxObj = il2cpp_runtime_invoke(getCtxM, monoPtr, IntPtr.Zero, ref exc);
                            if (exc != IntPtr.Zero || ctxObj == IntPtr.Zero) continue;

                            IntPtr ctxClass = il2cpp_object_get_class(ctxObj);
                            if (ctxClass == IntPtr.Zero) continue;

                            string ctxClassName = Marshal.PtrToStringAnsi(il2cpp_class_get_name(ctxClass));

                            // Find the target method on context (search hierarchy)
                            IntPtr targetMethod = IntPtr.Zero;
                            int targetParamCount = -1;
                            IntPtr ck = ctxClass;
                            while (ck != IntPtr.Zero && targetMethod == IntPtr.Zero)
                            {
                                IntPtr mi = IntPtr.Zero;
                                IntPtr m;
                                while ((m = il2cpp_class_get_methods(ck, ref mi)) != IntPtr.Zero)
                                {
                                    string mn = Marshal.PtrToStringAnsi(il2cpp_method_get_name(m));
                                    if (mn == methodName)
                                    {
                                        int pc = il2cpp_method_get_param_count(m);
                                        // Prefer 0-param version, but accept 1-param if arg provided
                                        if (pc == 0 && string.IsNullOrEmpty(arg))
                                        {
                                            targetMethod = m;
                                            targetParamCount = 0;
                                            break;
                                        }
                                        if (pc == 1 && !string.IsNullOrEmpty(arg))
                                        {
                                            targetMethod = m;
                                            targetParamCount = 1;
                                        }
                                        if (pc == 0 && targetMethod == IntPtr.Zero)
                                        {
                                            targetMethod = m;
                                            targetParamCount = 0;
                                        }
                                    }
                                }
                                ck = il2cpp_class_get_parent(ck);
                                string pn = ck != IntPtr.Zero ? Marshal.PtrToStringAnsi(il2cpp_class_get_name(ck)) : "";
                                if (pn == "Object" || pn == "Il2CppObjectBase") break;
                            }

                            if (targetMethod == IntPtr.Zero)
                            {
                                // Method not on this context, keep searching
                                continue;
                            }

                            // Invoke the method
                            IntPtr exc2 = IntPtr.Zero;
                            il2cpp_runtime_invoke(targetMethod, ctxObj, IntPtr.Zero, ref exc2);

                            if (exc2 != IntPtr.Zero)
                                return "{\"error\":\"invoke exception\",\"context\":\"" + Esc(ctxClassName) + "\",\"method\":\"" + Esc(methodName) + "\"}";

                            return "{\"invoked\":\"" + Esc(methodName) + "\",\"on_context\":\"" + Esc(ctxClassName) + "\",\"view_path\":\"" + Esc(GetPath(t)) + "\"}";
                        }
                        catch { }
                    }
                }

                if (depth < 6)
                {
                    for (int ci = 0; ci < t.childCount && ci < 30; ci++)
                        toScan.Enqueue((t.GetChild(ci), depth + 1));
                }
            }

            return "{\"error\":\"no context with method " + Esc(methodName) + " found in hierarchy\"}";
        }

        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_value_box(IntPtr klass, IntPtr data);

        [DllImport("GameAssembly")]
        static extern IntPtr il2cpp_class_get_parent(IntPtr klass);

        /// <summary>
        /// Inspect MVVM bindings (CommandBinding, OnClickBinding) on a GameObject.
        /// Shows what commands are bound and their state.
        /// </summary>
        private string InspectBindings(string objPath)
        {
            if (string.IsNullOrEmpty(objPath))
                return "{\"error\":\"path required\"}";

            var go = GameObject.Find(objPath);
            if (go == null)
                return "{\"error\":\"not found\"}";

            var sb = new StringBuilder();
            sb.Append("{\"path\":\"" + Esc(objPath) + "\",\"components\":[");

            var allComps = go.GetComponents<Component>();
            int ci = 0;
            foreach (var comp in allComps)
            {
                if (comp == null) continue;
                if (ci > 0) sb.Append(",");
                ci++;

                IntPtr compPtr = comp is MonoBehaviour mb ? mb.Pointer : IntPtr.Zero;
                IntPtr compClass = compPtr != IntPtr.Zero ? il2cpp_object_get_class(compPtr) : IntPtr.Zero;
                string compClassName = compClass != IntPtr.Zero
                    ? Marshal.PtrToStringAnsi(il2cpp_class_get_name(compClass))
                    : comp.GetType().Name;

                sb.Append("{\"type\":\"" + Esc(compClassName) + "\"");

                // For CommandBinding types, try to read the command name field
                if (compClassName != null && (compClassName.Contains("Binding") || compClassName.Contains("Command")))
                {
                    if (compPtr != IntPtr.Zero && compClass != IntPtr.Zero)
                    {
                        // Read fields to find command name
                        IntPtr fIter = IntPtr.Zero;
                        IntPtr field;
                        while ((field = il2cpp_class_get_fields(compClass, ref fIter)) != IntPtr.Zero)
                        {
                            string fname = Marshal.PtrToStringAnsi(il2cpp_field_get_name(field));
                            int foff = il2cpp_field_get_offset(field);
                            sb.Append(",\"" + Esc(fname) + "_off\":" + foff);
                        }
                        // Also check parent class fields
                        IntPtr parentClass = il2cpp_class_get_parent(compClass);
                        if (parentClass != IntPtr.Zero)
                        {
                            string parentName = Marshal.PtrToStringAnsi(il2cpp_class_get_name(parentClass));
                            sb.Append(",\"parent\":\"" + Esc(parentName) + "\"");
                            IntPtr pfIter = IntPtr.Zero;
                            IntPtr pfield;
                            while ((pfield = il2cpp_class_get_fields(parentClass, ref pfIter)) != IntPtr.Zero)
                            {
                                string pfname = Marshal.PtrToStringAnsi(il2cpp_field_get_name(pfield));
                                int pfoff = il2cpp_field_get_offset(pfield);
                                sb.Append(",\"p_" + Esc(pfname) + "_off\":" + pfoff);

                                // If this looks like a string field (command name), try to read it
                                if (pfname.ToLower().Contains("command") || pfname.ToLower().Contains("name"))
                                {
                                    try
                                    {
                                        IntPtr strPtr = Marshal.ReadIntPtr(compPtr, pfoff);
                                        if (strPtr != IntPtr.Zero)
                                        {
                                            // IL2CPP string: first 16 bytes are header, then UTF-16 chars
                                            int strLen = Marshal.ReadInt32(strPtr, 0x10);
                                            if (strLen > 0 && strLen < 200)
                                            {
                                                string val = Marshal.PtrToStringUni(strPtr + 0x14, strLen);
                                                sb.Append(",\"p_" + Esc(pfname) + "\":\"" + Esc(val) + "\"");
                                            }
                                        }
                                    }
                                    catch { }
                                }
                            }
                        }
                    }
                }

                sb.Append("}");
            }
            sb.Append("]}");
            return sb.ToString();
        }

        // === Helpers ===

        private void DumpGO(GameObject go, StringBuilder sb, int depth, int maxDepth)
        {
            sb.Append("{\"n\":\"" + Esc(go.name) + "\"");
            if (!go.activeSelf) sb.Append(",\"off\":1");
            if (go.GetComponent<UnityEngine.UI.Button>() != null) sb.Append(",\"btn\":1");
            if (depth < maxDepth && go.transform.childCount > 0)
            {
                sb.Append(",\"c\":[");
                int max = Math.Min(go.transform.childCount, 30);
                for (int i = 0; i < max; i++)
                {
                    if (i > 0) sb.Append(",");
                    DumpGO(go.transform.GetChild(i).gameObject, sb, depth + 1, maxDepth);
                }
                sb.Append("]");
            }
            sb.Append("}");
        }

        private void Search(Transform t, string search, string path, List<string> results, int max)
        {
            if (results.Count >= max) return;
            string full = string.IsNullOrEmpty(path) ? t.name : path + "/" + t.name;
            if (t.name.ToLower().Contains(search)) results.Add(full);
            for (int i = 0; i < t.childCount; i++)
                Search(t.GetChild(i), search, full, results, max);
        }

        private string GetPath(Transform t)
        {
            var parts = new List<string>();
            while (t != null) { parts.Add(t.name); t = t.parent; }
            parts.Reverse();
            return string.Join("/", parts);
        }

        private string QP(string query, string key)
        {
            if (string.IsNullOrEmpty(query)) return "";
            foreach (var part in query.TrimStart('?').Split('&'))
            {
                var kv = part.Split(new char[] { '=' }, 2);
                if (kv.Length == 2 && kv[0] == key) return Uri.UnescapeDataString(kv[1]);
            }
            return "";
        }

        private string Esc(string s)
        {
            if (s == null) return "";
            return s.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n").Replace("\r", "");
        }

        // === Hero Gear / Artifact data ===

        /// <summary>
        /// Navigate UserWrapper -> Equipment -> get artifacts for a hero.
        /// Uses raw IL2CPP pointer traversal since game objects are IL2CPP compiled.
        /// </summary>
        private string GetHeroGear(int heroId)
        {
            try
            {
                // Get AppModel singleton
                IntPtr appModel = GetAppModelSingleton();
                if (appModel == IntPtr.Zero) return "{\"error\":\"AppModel not found\"}";

                IntPtr userWrapper = Marshal.ReadIntPtr(appModel, 0x1C8);
                if (userWrapper == IntPtr.Zero) return "{\"error\":\"UserWrapper null\"}";

                // Equipment wrapper at UW+0x30
                IntPtr equipWrap = Marshal.ReadIntPtr(userWrapper, 0x30);
                if (equipWrap == IntPtr.Zero) return "{\"error\":\"EquipmentWrapper null\"}";

                // ArtifactData at EquipWrap+0x60
                IntPtr artData = Marshal.ReadIntPtr(equipWrap, 0x60);
                if (artData == IntPtr.Zero) return "{\"error\":\"ArtifactData null\"}";

                // ArtifactDataByHeroId at +0x30
                IntPtr byHero = Marshal.ReadIntPtr(artData, 0x30);
                if (byHero == IntPtr.Zero) return "{\"error\":\"ByHeroId null\"}";

                // Find the hero's HeroArtifactData in the dict
                IntPtr heroArtData = DictIntObjLookup(byHero, heroId);
                if (heroArtData == IntPtr.Zero)
                    return "{\"error\":\"hero " + heroId + " not in artifact mapping\"}";

                // ArtifactIdByKind at +0x10 (Dict<int,int>)
                IntPtr byKind = Marshal.ReadIntPtr(heroArtData, 0x10);
                if (byKind == IntPtr.Zero) return "{\"error\":\"ArtifactIdByKind null\"}";

                var slotIds = ReadDictIntInt(byKind);

                // Now we need to find the actual Artifact objects.
                // Try the EquipmentWrapperReadonly's computed property by searching
                // for a method called "GetArtifactById" or iterating the artifacts.
                // Alternative: search ALL artifacts in the game model.

                // Build artifact lookup from the EquipmentWrapper's internal state
                // The wrapper has methods to access artifacts — let's try reading
                // artifacts from the UserArtifactData by ID using its internal storage.
                var artifactLookup = BuildArtifactLookup(artData);

                var sb = new StringBuilder();
                sb.Append("{\"hero_id\":").Append(heroId).Append(",\"slots\":[");
                bool first = true;
                string[] kindNames = { "", "Weapon", "Helmet", "Shield", "Gauntlets",
                                       "Chestplate", "Boots", "Ring", "Amulet", "Banner" };

                foreach (var kv in slotIds)
                {
                    int kind = kv.Key;
                    int artId = kv.Value;

                    if (!first) sb.Append(",");
                    first = false;

                    sb.Append("{\"slot\":\"").Append(kind < kindNames.Length ? kindNames[kind] : "Slot" + kind);
                    sb.Append("\",\"kind\":").Append(kind);
                    sb.Append(",\"artifact_id\":").Append(artId);

                    IntPtr artPtr;
                    if (artifactLookup.TryGetValue(artId, out artPtr) && artPtr != IntPtr.Zero)
                    {
                        AppendArtifactJson(sb, artPtr);
                    }
                    else
                    {
                        sb.Append(",\"data\":null");
                    }
                    sb.Append("}");
                }
                sb.Append("]}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        private string GetAllHeroesData()
        {
            try
            {
                IntPtr appModel = GetAppModelSingleton();
                if (appModel == IntPtr.Zero) return "{\"error\":\"AppModel not found\"}";

                IntPtr userWrapper = Marshal.ReadIntPtr(appModel, 0x1C8);
                if (userWrapper == IntPtr.Zero) return "{\"error\":\"UserWrapper null\"}";

                // Heroes wrapper at UW+0x28
                IntPtr heroesWrap = Marshal.ReadIntPtr(userWrapper, 0x28);
                if (heroesWrap == IntPtr.Zero) return "{\"error\":\"HeroesWrapper null\"}";

                // HeroData at +0x88
                IntPtr heroData = Marshal.ReadIntPtr(heroesWrap, 0x88);
                if (heroData == IntPtr.Zero) return "{\"error\":\"HeroData null\"}";

                // HeroById dict at +0x18
                IntPtr heroDict = Marshal.ReadIntPtr(heroData, 0x18);
                if (heroDict == IntPtr.Zero) return "{\"error\":\"HeroById null\"}";

                // Equipment data
                IntPtr equipWrap = Marshal.ReadIntPtr(userWrapper, 0x30);
                IntPtr artData = equipWrap != IntPtr.Zero ? Marshal.ReadIntPtr(equipWrap, 0x60) : IntPtr.Zero;
                IntPtr byHero = artData != IntPtr.Zero ? Marshal.ReadIntPtr(artData, 0x30) : IntPtr.Zero;
                var artifactLookup = artData != IntPtr.Zero ? BuildArtifactLookup(artData) : new Dictionary<int, IntPtr>();

                // Read all heroes
                var heroEntries = ReadDictIntObj(heroDict);
                var sb = new StringBuilder();
                sb.Append("{\"count\":").Append(heroEntries.Count).Append(",\"heroes\":[");
                bool first = true;

                foreach (var kv in heroEntries)
                {
                    IntPtr ptr = kv.Value;
                    try
                    {
                        int grade = Marshal.ReadInt32(ptr, 0x20);
                        int level = Marshal.ReadInt32(ptr, 0x24);
                        if (grade < 1 || grade > 6 || level < 1 || level > 60) continue;

                        if (!first) sb.Append(",");
                        first = false;

                        int id = Marshal.ReadInt32(ptr, 0x18);
                        int typeId = Marshal.ReadInt32(ptr, 0x1C);
                        int empower = Marshal.ReadInt32(ptr, 0x30);

                        sb.Append("{\"id\":").Append(id);
                        sb.Append(",\"type_id\":").Append(typeId);
                        sb.Append(",\"grade\":").Append(grade);
                        sb.Append(",\"level\":").Append(level);
                        sb.Append(",\"empower\":").Append(empower);

                        // Read name from HeroType
                        IntPtr heroType = Marshal.ReadIntPtr(ptr, 0x10);
                        if (heroType != IntPtr.Zero)
                        {
                            IntPtr nameKey = Marshal.ReadIntPtr(heroType, 0x18);
                            if (nameKey != IntPtr.Zero)
                            {
                                IntPtr nameStr = Marshal.ReadIntPtr(nameKey, 0x18);
                                sb.Append(",\"name\":\"").Append(Esc(ReadIl2CppString(nameStr))).Append("\"");
                            }

                            int fraction = Marshal.ReadInt32(heroType, 0x3C);
                            int rarity = Marshal.ReadInt32(heroType, 0x40);
                            sb.Append(",\"fraction\":").Append(fraction);
                            sb.Append(",\"rarity\":").Append(rarity);

                            // Base stats from Forms[0]
                            IntPtr forms = Marshal.ReadIntPtr(heroType, 0x88);
                            if (forms != IntPtr.Zero)
                            {
                                IntPtr form0 = Marshal.ReadIntPtr(forms, 0x20); // array header
                                if (form0 != IntPtr.Zero)
                                {
                                    int element = Marshal.ReadInt32(form0, 0x10);
                                    int role = Marshal.ReadInt32(form0, 0x14);
                                    sb.Append(",\"element\":").Append(element);
                                    sb.Append(",\"role\":").Append(role);

                                    IntPtr bs = Marshal.ReadIntPtr(form0, 0x18);
                                    if (bs != IntPtr.Zero)
                                    {
                                        sb.Append(",\"base_stats\":{");
                                        sb.Append("\"HP\":").Append(ReadFixed(bs, 0x10));
                                        sb.Append(",\"ATK\":").Append(ReadFixed(bs, 0x18));
                                        sb.Append(",\"DEF\":").Append(ReadFixed(bs, 0x20));
                                        sb.Append(",\"SPD\":").Append(ReadFixed(bs, 0x28));
                                        sb.Append(",\"RES\":").Append(ReadFixed(bs, 0x30));
                                        sb.Append(",\"ACC\":").Append(ReadFixed(bs, 0x38));
                                        sb.Append(",\"CR\":").Append(ReadFixed(bs, 0x40));
                                        sb.Append(",\"CD\":").Append(ReadFixed(bs, 0x48));
                                        sb.Append("}");
                                    }
                                }
                            }
                        }

                        // Artifacts for this hero
                        if (byHero != IntPtr.Zero)
                        {
                            IntPtr heroArtData = DictIntObjLookup(byHero, id);
                            if (heroArtData != IntPtr.Zero)
                            {
                                IntPtr byKind = Marshal.ReadIntPtr(heroArtData, 0x10);
                                if (byKind != IntPtr.Zero)
                                {
                                    var slots = ReadDictIntInt(byKind);
                                    sb.Append(",\"artifacts\":[");
                                    bool firstArt = true;
                                    foreach (var slot in slots)
                                    {
                                        if (!firstArt) sb.Append(",");
                                        firstArt = false;
                                        sb.Append("{\"kind\":").Append(slot.Key);
                                        sb.Append(",\"id\":").Append(slot.Value);
                                        IntPtr ap;
                                        if (artifactLookup.TryGetValue(slot.Value, out ap))
                                            AppendArtifactJson(sb, ap);
                                        sb.Append("}");
                                    }
                                    sb.Append("]");
                                }
                            }
                        }

                        sb.Append("}");
                    }
                    catch { continue; }
                }
                sb.Append("]}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }
        }

        // === IL2CPP helper methods ===

        private IntPtr GetAppModelSingleton()
        {
            IntPtr domain = il2cpp_domain_get();
            uint asmCount = 0;
            IntPtr asmArray = il2cpp_domain_get_assemblies(domain, ref asmCount);

            for (uint a = 0; a < asmCount; a++)
            {
                IntPtr asm = Marshal.ReadIntPtr(asmArray, (int)(a * (uint)IntPtr.Size));
                IntPtr image = il2cpp_assembly_get_image(asm);
                uint cc = il2cpp_image_get_class_count(image);
                for (uint c = 0; c < cc; c++)
                {
                    IntPtr k = il2cpp_image_get_class(image, c);
                    if (k == IntPtr.Zero) continue;
                    string cn = Marshal.PtrToStringAnsi(il2cpp_class_get_name(k));
                    if (cn == "AppModel")
                    {
                        string ns = Marshal.PtrToStringAnsi(il2cpp_class_get_namespace(k));
                        if (ns != "Client.Model") continue;
                        // Singleton chain: klass -> +0xC8 -> +0x08 -> +0xB8 -> +0x08
                        IntPtr p = k;
                        int[] chain = { 0xC8, 0x08, 0xB8, 0x08 };
                        foreach (int off in chain)
                        {
                            p = Marshal.ReadIntPtr(p, off);
                            if (p == IntPtr.Zero) return IntPtr.Zero;
                        }
                        return p;
                    }
                }
            }
            return IntPtr.Zero;
        }

        private Dictionary<int, int> ReadDictIntInt(IntPtr dict)
        {
            var result = new Dictionary<int, int>();
            IntPtr entries = Marshal.ReadIntPtr(dict, 0x18); // _entries
            int count = Marshal.ReadInt32(dict, 0x20); // _count
            if (entries == IntPtr.Zero || count <= 0) return result;
            for (int i = 0; i < count; i++)
            {
                IntPtr addr = entries + 0x20 + i * 16; // ARRAY_HEADER + i * entry_size
                int hc = Marshal.ReadInt32(addr);
                if (hc < 0) continue;
                int key = Marshal.ReadInt32(addr, 8);
                int val = Marshal.ReadInt32(addr, 12);
                result[key] = val;
            }
            return result;
        }

        private Dictionary<int, IntPtr> ReadDictIntObj(IntPtr dict)
        {
            var result = new Dictionary<int, IntPtr>();
            IntPtr entries = Marshal.ReadIntPtr(dict, 0x18);
            int count = Marshal.ReadInt32(dict, 0x20);
            if (entries == IntPtr.Zero || count <= 0) return result;
            for (int i = 0; i < count; i++)
            {
                IntPtr addr = entries + 0x20 + i * 24;
                int hc = Marshal.ReadInt32(addr);
                if (hc < 0) continue;
                int key = Marshal.ReadInt32(addr, 8);
                IntPtr val = Marshal.ReadIntPtr(addr, 16);
                if (val != IntPtr.Zero)
                    result[key] = val;
            }
            return result;
        }

        private IntPtr DictIntObjLookup(IntPtr dict, int key)
        {
            var entries = ReadDictIntObj(dict);
            IntPtr val;
            entries.TryGetValue(key, out val);
            return val;
        }

        private Dictionary<int, IntPtr> BuildArtifactLookup(IntPtr artData)
        {
            // Try to build artifact ID -> ptr lookup.
            // Strategy: iterate ALL hero artifact mappings and collect unique artifact IDs,
            // then search for artifact objects in the game's data structures.
            // Since we can't find a central list, try the EquipmentWrapper's
            // computed property via different storage paths.

            var lookup = new Dictionary<int, IntPtr>();

            // Approach: scan ArtifactDataByHeroId (+0x30), for each hero's
            // ArtifactIdByKind, the VALUES might actually be stored as object refs
            // in a parallel structure. Let's check UpdatedArtifacts at +0x40
            IntPtr updatedDict = Marshal.ReadIntPtr(artData, 0x40);
            if (updatedDict != IntPtr.Zero)
            {
                try
                {
                    var updated = ReadDictIntObj(updatedDict);
                    foreach (var kv in updated)
                        lookup[kv.Key] = kv.Value;
                }
                catch { }
            }

            // Also check the Artifacts list at +0x28
            IntPtr artList = Marshal.ReadIntPtr(artData, 0x28);
            if (artList != IntPtr.Zero)
            {
                try
                {
                    IntPtr items = Marshal.ReadIntPtr(artList, 0x10);
                    int size = Marshal.ReadInt32(artList, 0x18);
                    if (items != IntPtr.Zero && size > 0)
                    {
                        for (int i = 0; i < Math.Min(size, 2000); i++)
                        {
                            IntPtr ap = Marshal.ReadIntPtr(items, 0x20 + i * 8);
                            if (ap != IntPtr.Zero)
                            {
                                int aid = Marshal.ReadInt32(ap, 0x10); // ART_ID
                                lookup[aid] = ap;
                            }
                        }
                    }
                }
                catch { }
            }

            // Broad scan: check every sub-pointer of artData for dicts/lists of artifacts
            for (int off = 0x10; off < 0xB0; off += 8)
            {
                if (lookup.Count > 50) break; // already found enough
                IntPtr p = IntPtr.Zero;
                try { p = Marshal.ReadIntPtr(artData, off); } catch { continue; }
                if (p == IntPtr.Zero) continue;

                // Try as dict
                try
                {
                    int c = Marshal.ReadInt32(p, 0x20);
                    if (c > 50 && c < 5000)
                    {
                        IntPtr ents = Marshal.ReadIntPtr(p, 0x18);
                        if (ents != IntPtr.Zero)
                        {
                            IntPtr testAddr = ents + 0x20;
                            if (Marshal.ReadInt32(testAddr) >= 0)
                            {
                                IntPtr testVal = Marshal.ReadIntPtr(testAddr, 16);
                                if (testVal != IntPtr.Zero)
                                {
                                    int testLev = Marshal.ReadInt32(testVal, 0x30);
                                    int testRnk = Marshal.ReadInt32(testVal, 0x44);
                                    if (testLev >= 0 && testLev <= 16 && testRnk >= 1 && testRnk <= 6)
                                    {
                                        // Found artifact dict!
                                        for (int i = 0; i < Math.Min(c, 2000); i++)
                                        {
                                            IntPtr a = ents + 0x20 + i * 24;
                                            if (Marshal.ReadInt32(a) < 0) continue;
                                            int k = Marshal.ReadInt32(a, 8);
                                            IntPtr v = Marshal.ReadIntPtr(a, 16);
                                            if (v != IntPtr.Zero) lookup[k] = v;
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                catch { }
            }

            return lookup;
        }

        private void AppendArtifactJson(StringBuilder sb, IntPtr artPtr)
        {
            try
            {
                int level = Marshal.ReadInt32(artPtr, 0x30);
                int rank = Marshal.ReadInt32(artPtr, 0x44);
                int rarity = Marshal.ReadInt32(artPtr, 0x48);
                int setId = Marshal.ReadInt32(artPtr, 0x68);
                int kindId = Marshal.ReadInt32(artPtr, 0x40);

                sb.Append(",\"level\":").Append(level);
                sb.Append(",\"rank\":").Append(rank);
                sb.Append(",\"rarity\":").Append(rarity);
                sb.Append(",\"set\":").Append(setId);
                sb.Append(",\"art_kind\":").Append(kindId);

                // Primary bonus
                IntPtr primary = Marshal.ReadIntPtr(artPtr, 0x50);
                if (primary != IntPtr.Zero)
                {
                    AppendBonusJson(sb, primary, "primary");
                }

                // Substats
                IntPtr subsList = Marshal.ReadIntPtr(artPtr, 0x58);
                if (subsList != IntPtr.Zero)
                {
                    IntPtr subItems = Marshal.ReadIntPtr(subsList, 0x10);
                    int subSize = Marshal.ReadInt32(subsList, 0x18);
                    if (subItems != IntPtr.Zero && subSize > 0)
                    {
                        sb.Append(",\"substats\":[");
                        for (int i = 0; i < Math.Min(subSize, 4); i++)
                        {
                            IntPtr sp = Marshal.ReadIntPtr(subItems, 0x20 + i * 8);
                            if (sp == IntPtr.Zero) continue;
                            if (i > 0) sb.Append(",");
                            sb.Append("{");
                            AppendBonusJsonInner(sb, sp);
                            sb.Append("}");
                        }
                        sb.Append("]");
                    }
                }
            }
            catch (Exception ex)
            {
                sb.Append(",\"art_error\":\"").Append(Esc(ex.Message)).Append("\"");
            }
        }

        private void AppendBonusJson(StringBuilder sb, IntPtr bonusPtr, string label)
        {
            sb.Append(",\"").Append(label).Append("\":{");
            AppendBonusJsonInner(sb, bonusPtr);
            sb.Append("}");
        }

        private void AppendBonusJsonInner(StringBuilder sb, IntPtr bonusPtr)
        {
            int statKind = Marshal.ReadInt32(bonusPtr, 0x10);
            int level = Marshal.ReadInt32(bonusPtr, 0x38);
            sb.Append("\"stat\":").Append(statKind);
            sb.Append(",\"level\":").Append(level);

            // BonusValue at +0x18
            IntPtr bv = Marshal.ReadIntPtr(bonusPtr, 0x18);
            if (bv != IntPtr.Zero)
            {
                bool isFlat = Marshal.ReadByte(bv, 0x10) != 0;
                double val = ReadFixed(bv, 0x18);
                sb.Append(",\"value\":").Append(val);
                sb.Append(",\"flat\":").Append(isFlat ? "true" : "false");
            }
        }

        private double ReadFixed(IntPtr obj, int offset)
        {
            long raw = Marshal.ReadInt64(obj, offset);
            return raw / 4294967296.0;  // 2^32
        }

        private string ReadIl2CppString(IntPtr strPtr)
        {
            if (strPtr == IntPtr.Zero) return "";
            try
            {
                int len = Marshal.ReadInt32(strPtr, 0x10);
                if (len <= 0 || len > 200) return "";
                byte[] buf = new byte[len * 2];
                Marshal.Copy(strPtr + 0x14, buf, 0, buf.Length);
                return System.Text.Encoding.Unicode.GetString(buf);
            }
            catch { return ""; }
        }
    }
}
