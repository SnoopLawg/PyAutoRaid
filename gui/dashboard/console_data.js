/* console_data.js — wires the PyAutoRaid Console to live backend data.
 *
 * The Console design (console.html) ships with static sample numbers so it
 * renders standalone. This script patches the live values in over the top by
 * element id, fetching from the dashboard server's /api/* endpoints (which in
 * turn read the BepInEx mod on :6790). Each panel degrades gracefully: if an
 * endpoint is offline the design's placeholder simply stays visible.
 *
 * Wiring is incremental — panels are added here as they're hooked up. Keep the
 * DOM ids in console.html and the setters here in sync.
 */
(function () {
  "use strict";

  // ---- formatting helpers -------------------------------------------------
  function fmtAbbrev(n) {
    if (n == null || isNaN(n)) return "—";
    var a = Math.abs(n);
    if (a >= 1e9) return (n / 1e9).toFixed(2).replace(/\.?0+$/, "") + "B";
    if (a >= 1e6) return (n / 1e6).toFixed(1).replace(/\.0$/, "") + "M";
    if (a >= 1e3) return (n / 1e3).toFixed(1).replace(/\.0$/, "") + "K";
    return String(Math.round(n));
  }
  function fmtInt(n) {
    if (n == null || isNaN(n)) return "—";
    return Math.round(n).toLocaleString("en-US");
  }
  function setText(id, val) {
    var el = document.getElementById(id);
    if (el != null && val != null) el.textContent = val;
  }

  function getJSON(path) {
    return fetch(path, { cache: "no-store" }).then(function (r) {
      if (!r.ok) throw new Error(path + " -> " + r.status);
      return r.json();
    });
  }

  // ---- panel: top resource bar (gems / silver / energy / CB keys) ---------
  function wireResources() {
    return getJSON("/api/resources").then(function (res) {
      if (!res || typeof res !== "object") return;
      if (res.gems != null) setText("kpiGems", fmtInt(res.gems));
      if (res.silver != null) setText("kpiSilver", fmtAbbrev(res.silver));
      if (res.energy != null) setText("kpiEnergy", fmtInt(res.energy));
      if (res.cb_keys != null) setText("kpiCbKeys", res.cb_keys + " / 2");
    });
  }

  // ---- panel: Clan Boss (damage today / last run / bar chart) -------------
  function wireCB() {
    return getJSON("/api/cb-summary").then(function (cb) {
      if (!cb || typeof cb !== "object") return;
      var today = cb.damage_today != null ? cb.damage_today : cb.last_run_damage;
      if (today != null && today > 0) {
        setText("cbCardDmg", fmtAbbrev(today));
        setText("cbPageDmg", fmtAbbrev(today));
        setText("cbTodayDmg", fmtAbbrev(today));
        setText("tmDamage", fmtAbbrev(today));   // turn-by-turn page "Today" stat
      }
      // (The CB Damage chart is fed from /api/cb-battles in wireRecentBattles.)
    });
  }

  // ---- panel: DWJ-style rotation grid (live calc-parity sim) --------------
  var SKILL_IDX = { A1: 1, A2: 2, A3: 3, A4: 4 };
  function styleKey(alias) {
    if (alias === "A2") return "a2";
    if (alias === "A3" || alias === "A4") return "a3";
    return "a1";
  }
  function bossSkillLabel(sk) {
    if (!sk) return "acts";
    if (/aoe/i.test(sk)) return "AoE slam · " + sk;
    return sk;
  }
  function wireRotation() {
    if (!window.__console || !window.__console.rotation) return Promise.resolve();
    return getJSON("/api/calc-parity-sim?turns=50").then(function (d) {
      if (!d || d.error || !d.variant || !Array.isArray(d.timeline)) return;
      var ids = d.actor_type_ids || {};
      var slots = d.variant.slots || [];
      var champs = slots.map(function (s) {
        return { name: s.name, typeId: ids[s.name] || null };
      });
      // alias -> cooldown per slot, so we can chip the real CD on each cast.
      var cdmap = {};
      slots.forEach(function (s) {
        var m = {};
        (s.skill_configs || []).forEach(function (c) { m[c.alias] = c.cooldown; });
        cdmap[s.name] = m;
      });
      var slotIndex = function (name) {
        for (var i = 0; i < slots.length; i++) if (slots[i].name === name) return i;
        return -1;
      };
      // Group the flat timeline by boss turn; show the opening + first 7 rounds
      // (enough to see the full speed cycle before it repeats).
      var byBt = {}, order = [];
      d.timeline.forEach(function (t) {
        if (byBt[t.boss_turn] === undefined) { byBt[t.boss_turn] = []; order.push(t.boss_turn); }
        byBt[t.boss_turn].push(t);
      });
      var groups = order.slice(0, 8).map(function (bt) {
        var items = byBt[bt].map(function (t) {
          if (t.actor === "Clanboss") return { kind: "boss", text: bossSkillLabel(t.skill) };
          var ci = slotIndex(t.actor);
          if (ci < 0) return null;
          var cd = (cdmap[t.actor] && cdmap[t.actor][t.skill] > 0) ? "CD " + cdmap[t.actor][t.skill] : "";
          // Buffs/debuffs this cast applies → cell label + colour. Defensive
          // buff > debuff > offensive buff wins the cell style; a plain attack
          // keeps the neutral skill-alias colour.
          var fx = Array.isArray(t.effects) ? t.effects : [];
          var label = fx.map(function (e) {
            return e.label + (e.turns ? " " + e.turns + "T" : "");
          }).join(" · ");
          var k = fx.some(function (e) { return e.kind === "def"; }) ? "def"
                : fx.some(function (e) { return e.kind === "debuff"; }) ? "a3"
                : fx.some(function (e) { return e.kind === "buff"; }) ? "a2"
                : styleKey(t.skill);
          var icons = fx.map(function (e) { return e.icon; }).filter(Boolean);
          return {
            kind: "action", c: ci, s: t.skill, l: label, k: k, cd: cd, icons: icons,
          };
        }).filter(Boolean);
        return { label: bt === 0 ? "Opener" : "Round " + bt, items: items };
      });
      var survived = d.boss_turn_count || order.length;
      var footer = "↻ cycle repeats · " + (d.variant.name || "tune") +
                   " · survives to boss turn " + survived;
      if (window.__console.rotation) window.__console.rotation(champs, groups, footer);
      if (window.__console.tmGrid) window.__console.tmGrid(d.tm_grid);
      wireTelemetryHeader(d);
    });
  }

  // ---- Turn-by-turn page: header (tune/turns/result) + casts-by-champion ---
  function titleCase(s) {
    return (s || "").split(/[-_ ]/).map(function (w) {
      return w ? w.charAt(0).toUpperCase() + w.slice(1) : "";
    }).join(" ");
  }
  function diffAbbrev(s) {
    s = (s || "").toLowerCase();
    if (s.indexOf("ultra") >= 0) return "UNM";
    if (s.indexOf("night") >= 0) return "NM";
    if (s.indexOf("brutal") >= 0) return "Brutal";
    if (s.indexOf("hard") >= 0) return "Hard";
    return s ? titleCase(s) : "";
  }
  function wireTelemetryHeader(d) {
    var v = d.variant || {};
    var aff = (v.boss_affinity || "").toLowerCase();
    setText("tmVariant", titleCase(v.slug || v.name || "tune") +
      (aff ? " · " + titleCase(aff) : "") + " " + diffAbbrev(v.boss_difficulty));
    var affEl = document.getElementById("tmAffinityIcon");
    if (affEl && aff) affEl.src = "assets/ui/" + aff + ".png";
    var survived = d.boss_turn_count || 0;
    setText("tmTurns", String(survived));
    var gaps = (d.tm_grid || {}).protection_gaps || 0;
    var cleared = gaps === 0 && survived >= 50;
    setText("tmResult", cleared ? "Clear" : (gaps > 0 ? gaps + " gaps" : "T" + survived));
    var resEl = document.getElementById("tmResult");
    if (resEl) resEl.style.color = cleared ? "#6fcf6f" : "#e8896f";
    // Casts by champion (the sim is a scheduler — this is its per-hero metric).
    var byActor = {};
    (d.cast_summary || []).forEach(function (c) {
      if (c.actor === "Clanboss") return;
      byActor[c.actor] = (byActor[c.actor] || 0) + (c.count || 0);
    });
    var arr = Object.keys(byActor).map(function (n) { return { name: n, count: byActor[n] }; })
      .sort(function (a, b) { return b.count - a.count; });
    var maxC = arr.length ? arr[0].count : 1;
    var total = arr.reduce(function (s, x) { return s + x.count; }, 0) || 1;
    var host = document.getElementById("tmActBars");
    if (host) {
      host.innerHTML = arr.map(function (x) {
        var pct = Math.round(x.count / total * 100);
        var w = Math.round(x.count / maxC * 100);
        return '<div><div style="display:flex;justify-content:space-between;font-family:\'JetBrains Mono\',monospace;font-size:11px;margin-bottom:4px;">' +
          '<span style="color:#f3ead8;">' + x.name + '</span>' +
          '<span style="color:#caa063;">' + x.count + ' casts · ' + pct + '%</span></div>' +
          '<div style="height:8px;background:#241d15;border-radius:4px;overflow:hidden;">' +
          '<div style="width:' + w + '%;height:100%;background:linear-gradient(90deg,#a07a3a,#d8a657);"></div></div></div>';
      }).join("");
    }
  }

  // ---- panel: Recent Battles (CB page) — clickable -> replay --------------
  function affIcon(aff) {
    var a = (aff || "").toLowerCase();
    return (a === "magic" || a === "force" || a === "spirit" || a === "void")
      ? "assets/ui/" + a + ".png" : "assets/ui/demon_lord.png";
  }
  function wireRecentBattles() {
    return getJSON("/api/cb-battles?n=8").then(function (d) {
      var host = document.getElementById("recentBattles");
      if (!host) return;
      var bs = (d && d.battles) || [];
      if (!bs.length) { host.innerHTML = '<div style="font-family:\'JetBrains Mono\',monospace;font-size:9px;color:#6f6555;padding:10px 6px;">No captured battles yet.</div>'; return; }
      host.innerHTML = bs.map(function (b) {
        var top = ((b.date ? b.date.slice(5) : "") + (b.time ? " " + b.time : "")).trim() || "battle";
        var sub = (b.affinity || "") + (b.turns ? " · " + b.turns + "T" : "");
        return '<div class="replayrow" data-file="' + b.file + '" style="display:flex;justify-content:space-between;align-items:center;padding:8px 6px;border-top:1px solid #241d15;cursor:pointer;border-radius:3px;">' +
          '<div style="display:flex;align-items:center;gap:8px;"><img src="' + affIcon(b.affinity) + '" alt="" style="width:15px;height:15px;">' +
          '<div><div style="font-family:\'JetBrains Mono\',monospace;font-size:11px;color:#ece3d2;">' + top + '</div>' +
          '<div style="font-family:\'JetBrains Mono\',monospace;font-size:8.5px;color:#6f6555;">' + sub + '</div></div></div>' +
          '<div style="font-family:Cinzel,serif;font-size:16px;color:#d8a657;">' + fmtAbbrev(b.damage) + '</div></div>';
      }).join("");
      Array.prototype.forEach.call(host.querySelectorAll(".replayrow"), function (row) {
        row.addEventListener("click", function () { window.__openReplay(row.getAttribute("data-file")); });
        row.addEventListener("mouseenter", function () { row.style.background = "#1d1810"; });
        row.addEventListener("mouseleave", function () { row.style.background = "transparent"; });
      });
      // Feed the CB Damage chart with the recent battles' damage as a filled
      // area line (oldest -> newest, left -> right).
      var series = bs.map(function (b) { return (b.damage || 0) / 1e6; }).reverse();
      if (series.length && window.__console && window.__console.cbArea) window.__console.cbArea(series);
      setText("cbRuns", String(bs.length));
      var peak = bs.reduce(function (m, b) { return Math.max(m, b.damage || 0); }, 0);
      setText("cbPeak", fmtAbbrev(peak));
    });
  }

  // ---- replay mode (a real battle log) ------------------------------------
  function wireReplay(file) {
    return getJSON("/api/cb-replay?file=" + encodeURIComponent(file)).then(function (g) {
      if (!g || g.error || !g.rows) return;
      if (window.__console && window.__console.tmGrid) window.__console.tmGrid(g);
      var m = g.meta || {};
      var team = (g.columns || []).filter(function (c) { return c !== "Demon Lord"; });
      setText("tmVariant", "Battle · " + (m.file || "").replace("battle_logs_cb_", "").replace(".json", ""));
      var affEl = document.getElementById("tmAffinityIcon"); if (affEl) affEl.src = "assets/ui/demon_lord.png";
      setText("tmDamage", fmtAbbrev(m.damage || 0));
      setText("tmTurns", String(m.boss_turns || 0));
      var cleared = (m.boss_turns || 0) >= 50;
      setText("tmResult", cleared ? "Clear" : "T" + (m.boss_turns || 0));
      var resEl = document.getElementById("tmResult"); if (resEl) resEl.style.color = cleared ? "#6fcf6f" : "#e8a657";
    });
  }

  // ---- refresh loop -------------------------------------------------------
  function refreshAll() {
    // Each panel is independent; a failure in one must not stop the others.
    wireResources().catch(function () {});
    wireCB().catch(function () {});
    wireRecentBattles().catch(function () {});
  }

  // The turn grid is built lazily when the Turn-by-Turn view opens. In sim mode
  // it runs /api/calc-parity-sim (~35s cold); in replay mode it loads a real
  // battle log (window.__replayFile). Re-loads only when the mode/file changes.
  window.__replayFile = null;
  var _tmKey = null;
  window.__loadTmGrid = function () {
    var key = window.__replayFile ? "replay:" + window.__replayFile : "sim";
    if (_tmKey === key) return;
    _tmKey = key;
    var p = window.__replayFile ? wireReplay(window.__replayFile) : wireRotation();
    p.catch(function () { _tmKey = null; });
  };
  window.__openReplay = function (file) {
    window.__replayFile = file;
    location.hash = "cb-telemetry";
    window.__loadTmGrid();
  };

  document.addEventListener("DOMContentLoaded", function () {
    refreshAll();
    // Resources drift slowly (energy regen, key spend); a 60s poll is plenty.
    setInterval(refreshAll, 60000);
    // The "Turn-by-Turn" nav item shows the sim plan (clears any active replay).
    var navTb = document.querySelector('.navitem[data-view="cb-telemetry"]');
    if (navTb) navTb.addEventListener("click", function () {
      window.__replayFile = null; window.__loadTmGrid();
    });
    // Deep link: ?replay=<battle file> opens that replay directly.
    var rp = (location.search.match(/[?&]replay=([^&]+)/) || [])[1];
    if (rp) window.__openReplay(decodeURIComponent(rp));
  });
})();
