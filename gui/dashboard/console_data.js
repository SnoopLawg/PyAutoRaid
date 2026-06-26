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
      }
      // Re-feed the damage bar chart with the real per-key (or daily) series,
      // scaled to millions so the design's bar geometry stays comparable.
      var series = Array.isArray(cb.bars) && cb.bars.length ? cb.bars
                 : (Array.isArray(cb.daily) ? cb.daily.map(function (d) { return d.dmg; }) : []);
      series = series.filter(function (v) { return v != null; }).map(function (v) { return v / 1e6; });
      if (series.length && window.__console && window.__console.cbBars) {
        window.__console.cbBars(series);
      }
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
    });
  }

  // ---- refresh loop -------------------------------------------------------
  function refreshAll() {
    // Each panel is independent; a failure in one must not stop the others.
    wireResources().catch(function () {});
    wireCB().catch(function () {});
  }

  // The turn-meter grid is built from /api/calc-parity-sim, which is ~35s cold.
  // It only lives in the CB telemetry drawer, so load it lazily the first time
  // the drawer is opened — never on initial page load.
  var _tmLoaded = false;
  window.__loadTmGrid = function () {
    if (_tmLoaded) return;
    _tmLoaded = true;
    wireRotation().catch(function () { _tmLoaded = false; });
  };

  document.addEventListener("DOMContentLoaded", function () {
    refreshAll();
    // Resources drift slowly (energy regen, key spend); a 60s poll is plenty.
    setInterval(refreshAll, 60000);
  });
})();
