// Auto-extracted from RaidAutomationPlugin.cs (slice: artifact mutations).
// All methods are partial-class members of RaidAutomationPlugin.
// Behavior identical; isolates command-system invocations for
// equip / unequip / swap / bulk-equip / sell from the rest of the
// plugin (HTTP routing, battle state, navigation, etc.).
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


        // Vault-only sell: build ArtifactsToSellDto with empty
        // ArtifactsOnHeroes and the IDs in ArtifactsFromStorage. Dispatch
        // SellArtifactsWithEquippedCmd which is the canonical current
        // server endpoint. The plain SellArtifactsCmd returns 404 — likely
        // deprecated.
        private string SellArtifactsViaDto(string idsStr)
        {
            if (string.IsNullOrEmpty(idsStr))
                return "{\"error\":\"ids required (comma-separated artifact IDs)\"}";

            var uw = GetUserWrapper();
            if (uw == null) return "{\"error\":\"Not logged in\"}";
            var equipment = Prop(uw, "Artifacts");
            if (equipment == null) return "{\"error\":\"EquipmentWrapper null\"}";
            var oneMethod = equipment.GetType().GetMethod("One");

            var requested = new List<int>();
            foreach (var s in idsStr.Trim().TrimStart('[').TrimEnd(']').Split(','))
            {
                if (int.TryParse(s.Trim(), out int id) && id > 0) requested.Add(id);
            }
            if (requested.Count == 0)
                return "{\"error\":\"no valid IDs in ids parameter\"}";

            // Validate: each ID must exist in vault, not equipped, not locked.
            var vaultIds = new List<int>();
            var skippedSb = new StringBuilder();
            int sk = 0;
            foreach (int aid in requested)
            {
                if (oneMethod == null) { vaultIds.Add(aid); continue; }
                object art = null;
                try { art = oneMethod.Invoke(equipment, new object[] { aid }); } catch { }
                string skipReason = null;
                if (art == null) skipReason = "not_found";
                else
                {
                    int owner = GetArtifactOwner(equipment, aid);
                    if (owner > 0) skipReason = "equipped_on_" + owner;
                    else
                    {
                        bool locked = false;
                        try { locked = (bool)(art.GetType().GetProperty("Locked")?.GetValue(art) ?? false); } catch { }
                        if (locked) skipReason = "locked";
                    }
                }
                if (skipReason != null)
                {
                    if (sk > 0) skippedSb.Append(",");
                    skippedSb.Append("{\"id\":" + aid + ",\"reason\":\"" + skipReason + "\"}");
                    sk++;
                }
                else
                {
                    vaultIds.Add(aid);
                }
            }
            if (vaultIds.Count == 0)
                return "{\"ok\":true,\"sold\":[],\"skipped\":[" + skippedSb + "]}";

            // Build ArtifactsToSellDto
            var dtoType = FindType("SharedModel.Meta.Artifacts.Dtos.ArtifactsToSellDto");
            if (dtoType == null)
                return "{\"error\":\"ArtifactsToSellDto type not found\"}";
            object dto;
            try { dto = Activator.CreateInstance(dtoType); }
            catch (Exception ex) { return "{\"error\":\"failed to construct DTO: " + Esc(ex.Message) + "\"}"; }

            // Set ArtifactsFromStorage = Il2CppSystem.Collections.Generic.List<int>(vault IDs)
            var artsFromStorageProp = dtoType.GetProperty("ArtifactsFromStorage");
            if (artsFromStorageProp == null)
                return "{\"error\":\"ArtifactsFromStorage property missing\"}";
            var listType = artsFromStorageProp.PropertyType;
            object listInst;
            try
            {
                listInst = Activator.CreateInstance(listType);
                MethodInfo addM = null;
                foreach (var m in listType.GetMethods(BindingFlags.Public | BindingFlags.Instance))
                {
                    if (m.Name == "Add" && m.GetParameters().Length == 1) { addM = m; break; }
                }
                if (addM == null) return "{\"error\":\"List<int>.Add not found on " + listType.FullName + "\"}";
                foreach (int i in vaultIds) addM.Invoke(listInst, new object[] { i });
                artsFromStorageProp.SetValue(dto, listInst);
            }
            catch (Exception ex)
            {
                return "{\"error\":\"failed to populate ArtifactsFromStorage: " + Esc(ex.Message) + "\"}";
            }

            // Set ArtifactsOnHeroes to an empty Il2Cpp dict (the cmd may
            // dereference it during request body build even if empty).
            var artsOnHeroesProp = dtoType.GetProperty("ArtifactsOnHeroes");
            if (artsOnHeroesProp != null)
            {
                try
                {
                    var dictType = artsOnHeroesProp.PropertyType;
                    var dictInst = Activator.CreateInstance(dictType);
                    artsOnHeroesProp.SetValue(dto, dictInst);
                }
                catch { /* leave null if construction fails */ }
            }

            // Find SellArtifactsWithEquippedCmd ctor that takes the Dto.
            var cmdType = FindType("Client.Model.Gameplay.Artifacts.Commands.SellArtifactsWithEquippedCmd");
            if (cmdType == null)
                return "{\"error\":\"SellArtifactsWithEquippedCmd type not found\"}";
            ConstructorInfo ctor = null;
            foreach (var c in cmdType.GetConstructors(BindingFlags.Public | BindingFlags.Instance))
            {
                var ps = c.GetParameters();
                if (ps.Length == 1 && ps[0].ParameterType == dtoType)
                {
                    ctor = c; break;
                }
            }
            if (ctor == null)
                return "{\"error\":\"SellArtifactsWithEquippedCmd(Dto) ctor not found\"}";

            try
            {
                var cmd = ctor.Invoke(new object[] { dto });
                InvokeExecute(cmd);
            }
            catch (TargetInvocationException tex)
            {
                return "{\"error\":\"" + Esc((tex.InnerException ?? tex).Message) + "\"}";
            }
            catch (Exception ex)
            {
                return "{\"error\":\"" + Esc(ex.Message) + "\"}";
            }

            var sb = new StringBuilder();
            sb.Append("{\"ok\":true,\"sold\":[");
            for (int i = 0; i < vaultIds.Count; i++)
            {
                if (i > 0) sb.Append(",");
                sb.Append(vaultIds[i]);
            }
            sb.Append("],\"skipped\":[" + skippedSb + "]}");
            return sb.ToString();
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
    }
}
