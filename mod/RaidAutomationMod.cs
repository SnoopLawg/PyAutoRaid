using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Net;
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

        private static void ProcessMainThreadQueue()
        {
            while (MainThreadQueue.TryDequeue(out var action))
            {
                try { action(); } catch { }
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
                    case "/scene":
                        int md = int.TryParse(QP(query, "depth"), out int d) ? d : 2;
                        response = RunOnMainThread(() => DumpScene(md));
                        break;
                    case "/toggles":
                        response = RunOnMainThread(() => ListToggles());
                        break;
                    case "/toggle":
                        string tp = QP(query, "path");
                        response = RunOnMainThread(() => SetToggle(tp));
                        break;
                    case "/simclick":
                        string sp = QP(query, "path");
                        response = RunOnMainThread(() => SimulateClick(sp));
                        break;
                    default:
                        response = "{\"endpoints\":[\"/status\",\"/buttons\",\"/click?path=X\",\"/find?name=X\",\"/scene?depth=N\",\"/toggles\",\"/toggle?path=X\"]}";
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
            var btn = go.GetComponent<UnityEngine.UI.Button>();
            if (btn != null)
            {
                btn.onClick.Invoke();
                return "{\"clicked\":\"" + Esc(objPath) + "\"}";
            }
            // Fallback: ExecuteEvents
            var ped = new UnityEngine.EventSystems.PointerEventData(
                UnityEngine.EventSystems.EventSystem.current);
            UnityEngine.EventSystems.ExecuteEvents.Execute(go,
                ped, UnityEngine.EventSystems.ExecuteEvents.pointerClickHandler);
            return "{\"clicked\":\"" + Esc(objPath) + "\",\"method\":\"pointer\"}";
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

        private string ListToggles()
        {
            var all = UnityEngine.Object.FindObjectsOfType<UnityEngine.UI.Toggle>();
            var sb = new StringBuilder();
            sb.Append("{\"count\":" + all.Length + ",\"toggles\":[");
            int n = 0;
            foreach (var tog in all)
            {
                if (!tog.gameObject.activeInHierarchy) continue;
                if (n > 0) sb.Append(",");
                sb.Append("{\"path\":\"" + Esc(GetPath(tog.transform)) +
                          "\",\"on\":" + (tog.isOn ? "true" : "false") +
                          ",\"interactable\":" + (tog.interactable ? "true" : "false") + "}");
                if (++n >= 100) break;
            }
            sb.Append("]}");
            return sb.ToString();
        }

        private string SetToggle(string objPath)
        {
            if (string.IsNullOrEmpty(objPath))
                return "{\"error\":\"path required\"}";
            var go = GameObject.Find(objPath);
            if (go == null)
                return "{\"error\":\"not found\"}";
            var tog = go.GetComponent<UnityEngine.UI.Toggle>();
            if (tog == null)
                return "{\"error\":\"no Toggle component\"}";
            // Use the property setter which triggers onValueChanged
            bool newVal = !tog.isOn;
            tog.Set(newVal, true);
            // Also invoke onValueChanged manually to ensure listeners fire
            tog.onValueChanged.Invoke(newVal);
            return "{\"toggled\":\"" + Esc(objPath) + "\",\"now\":" + (tog.isOn ? "true" : "false") + "}";
        }

        private string SimulateClick(string objPath)
        {
            if (string.IsNullOrEmpty(objPath))
                return "{\"error\":\"path required\"}";
            var go = GameObject.Find(objPath);
            if (go == null)
                return "{\"error\":\"not found\"}";
            // Full pointer event sequence — triggers all handlers including sell mode selection
            var ped = new UnityEngine.EventSystems.PointerEventData(
                UnityEngine.EventSystems.EventSystem.current);
            ped.button = UnityEngine.EventSystems.PointerEventData.InputButton.Left;
            ped.clickCount = 1;
            // Get world position from the object's RectTransform
            var rt = go.GetComponent<RectTransform>();
            if (rt != null)
            {
                ped.position = new Vector2(rt.position.x, rt.position.y);
            }
            // Fire the full sequence: Down, Click, Up
            UnityEngine.EventSystems.ExecuteEvents.Execute(go,
                ped, UnityEngine.EventSystems.ExecuteEvents.pointerDownHandler);
            UnityEngine.EventSystems.ExecuteEvents.Execute(go,
                ped, UnityEngine.EventSystems.ExecuteEvents.pointerClickHandler);
            UnityEngine.EventSystems.ExecuteEvents.Execute(go,
                ped, UnityEngine.EventSystems.ExecuteEvents.pointerUpHandler);
            // Also bubble up through parents
            UnityEngine.EventSystems.ExecuteEvents.ExecuteHierarchy(go,
                ped, UnityEngine.EventSystems.ExecuteEvents.pointerClickHandler);
            return "{\"simulated\":\"" + Esc(objPath) + "\"}";
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
    }
}
