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
    setText("tmHeading", "Turn-by-Turn Plan");
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
      setText("tmHeading", "Battle Replay");
      setText("tmVariant", "Battle · " + (m.file || "").replace("battle_logs_cb_", "").replace(".json", ""));
      var affEl = document.getElementById("tmAffinityIcon"); if (affEl) affEl.src = "assets/ui/demon_lord.png";
      setText("tmDamage", fmtAbbrev(m.damage || 0));
      setText("tmTurns", String(m.boss_turns || 0));
      var cleared = (m.boss_turns || 0) >= 50;
      setText("tmResult", cleared ? "Clear" : "T" + (m.boss_turns || 0));
      var resEl = document.getElementById("tmResult"); if (resEl) resEl.style.color = cleared ? "#6fcf6f" : "#e8a657";
    });
  }

  // ---- team recommendation panel (left side of the CB page) ---------------
  // Tried-and-true templates split into "ready to build" vs "need heroes", with
  // a traffic-light status (ready / lacking gear / need heroes). Data is the
  // cheap ownership + gear-feasibility pass from /api/cb-recommendations.
  function wireRecommender() {
    var host = document.getElementById("cbRecommender");
    if (!host) return Promise.resolve();
    return getJSON("/api/cb-recommendations").then(function (d) {
      if (!d || (!d.ready && !d.need_heroes)) {
        host.innerHTML = '<div style="font-family:\'JetBrains Mono\',monospace;font-size:10px;color:#6f6555;padding:14px 6px;">No recommendations yet.</div>';
        return;
      }
      var ready = d.ready || [], need = d.need_heroes || [];
      var state = { tab: "ready", open: {}, solved: {}, solving: {} };
      var mono = "'JetBrains Mono',monospace";

      function mechColor(m) {
        if (m === "Unkillable") return "#4a86c5";
        if (m === "Speed") return "#d8a657";
        return "#6f6555";
      }
      function statusDot(r) {
        if (r.status === "ready") return ['#6fcf6f', 'Ready'];
        if (r.status === "lacking-gear") return ['#d8a657', 'Lacking gear'];
        return ['#6f6555', 'Need heroes'];
      }
      function chip(text, color) {
        return '<span style="font-family:' + mono + ';font-size:8px;letter-spacing:.08em;text-transform:uppercase;color:' + color + ';border:1px solid ' + color + '55;border-radius:3px;padding:2px 5px;flex:none;">' + text + '</span>';
      }
      function simM(r) { return '~' + (r.sim_damage / 1e6).toFixed(1) + 'M sim'; }
      function readySub(r) {
        if (r.status !== "ready") {
          var g = (r.gear_gaps || []).slice(0, 3).map(function (x) { return x.hero + ' −' + x.short; }).join(", ");
          return '<span style="color:#d8a657;">short SPD: ' + g + (r.gear_gaps && r.gear_gaps.length > 3 ? " …" : "") + '</span>';
        }
        var parts = ['<span style="color:#6fcf6f;">gear hits the tune</span>'];
        if (r.holds_t50) parts.push('<span style="color:#6fcf6f;">holds T50 ✓</span>');
        else if (r.dwj_boss_turns) parts.push('<span style="color:#d8a657;">DWJ holds T' + r.dwj_boss_turns + '</span>');
        if (r.sim_damage) parts.push('<span style="color:#caa063;">' + simM(r) + '</span>');
        return parts.join(' · ');
      }
      function renderSolve(o) {
        if (!o || o.error) return '<span style="color:#c25a3a;font-size:9px;">solve failed' + (o && o.error ? ': ' + o.error : '') + '</span>';
        var head = o.feasible
          ? '<span style="color:#6fcf6f;">✓ Regear-feasible — your vault can hit every speed</span>'
          : '<span style="color:#c25a3a;">✗ Can\'t reach this tune even with your best gear</span>';
        var outcome = "";
        if (o.feasible) {
          var bits = [];
          if (o.key_capability) bits.push(o.key_capability);
          if (o.holds_t50) bits.push("holds T50 (DWJ)");
          else if (o.dwj_boss_turns) bits.push("DWJ holds T" + o.dwj_boss_turns);
          if (bits.length) outcome = '<div style="margin-top:4px;color:#caa063;">→ ' + bits.join(" · ") + '</div>';
        }
        var rows = (o.per_hero || []).map(function (h) {
          var t = h.target ? h.target[0] + '–' + h.target[1] : 'any';
          var c = h.ok ? '#6fcf6f' : '#c25a3a';
          return '<div style="display:flex;justify-content:space-between;gap:8px;"><span style="color:#cdbfa6;">' + h.hero + '</span><span style="color:' + c + ';">SPD ' + (h.achieved_spd != null ? h.achieved_spd : '?') + ' / ' + t + (h.ok ? ' ✓' : ' ✗') + '</span></div>';
        }).join("");
        return '<div style="font-family:' + mono + ';font-size:9px;border-top:1px solid #241d15;margin-top:7px;padding-top:7px;">' + head + outcome + '<div style="margin-top:5px;display:grid;gap:2px;">' + rows + '</div></div>';
      }
      function solveTeam(id, btn) {
        if (state.solving[id]) return;
        state.solving[id] = true;
        if (btn) { btn.textContent = "Solving… (~20s)"; btn.disabled = true; btn.style.opacity = ".6"; }
        getJSON("/api/cb-solve-gear?id=" + encodeURIComponent(id)).then(function (o) {
          state.solving[id] = false; state.solved[id] = o || { error: "no response" }; render();
        }).catch(function () {
          state.solving[id] = false; state.solved[id] = { error: "request failed" }; render();
        });
      }
      function expand(r) {
        var rows = (r.slots || []).map(function (s) {
          if (!s.hero || s.status === "generic") {
            return '<div style="display:flex;justify-content:space-between;color:#6f6555;"><span>' + (s.hero || "flex DPS") + '</span><span>any</span></div>';
          }
          var want = s.min_spd ? (s.min_spd + (s.max_spd && s.max_spd !== s.min_spd ? "–" + s.max_spd : "") + " SPD") : "—";
          return '<div style="display:flex;justify-content:space-between;"><span style="color:#e8dcc4;">' + s.hero + '</span><span style="color:#948876;">' + want + '</span></div>';
        }).join("");
        return '<div style="margin-top:8px;border-top:1px solid #241d15;padding-top:7px;font-family:' + mono + ';font-size:9px;display:grid;gap:2px;">' + rows + '</div>';
      }
      function card(r) {
        var d2 = statusDot(r), open = state.open[r.id];
        var right = state.tab === "ready"
          ? '<span style="font-family:' + mono + ';font-size:9px;color:' + d2[0] + ';flex:none;">● ' + d2[1] + '</span>'
          : '<span style="font-family:' + mono + ';font-size:9px;color:#c46f5a;flex:none;">need ' + (r.missing_heroes || []).join(", ") + '</span>';
        var sub = state.tab === "ready"
          ? readySub(r)
          : '<span style="color:#6f6555;">' + (r.key_capability || "") + '</span>';
        var solveBlock = "";
        if (state.tab === "ready" && r.status === "lacking-gear") {
          if (state.solved[r.id]) solveBlock = renderSolve(state.solved[r.id]);
          else solveBlock = '<div style="margin-top:7px;"><button data-solve="' + r.id + '" style="font-family:' + mono + ';font-size:9px;color:#d8a657;background:transparent;border:1px solid #6e4f24;border-radius:3px;padding:5px 10px;cursor:pointer;">' + (state.solving[r.id] ? "Solving… (~20s)" : "Solve gear → can I regear?") + '</button></div>';
        }
        return '<div data-rid="' + r.id + '" style="background:#1a150e;border:1px solid #2c241a;border-left:2px solid ' + mechColor(r.mechanic) + ';border-radius:4px;padding:9px 11px;margin-bottom:7px;cursor:pointer;">' +
          '<div style="display:flex;align-items:center;gap:8px;">' +
            chip(r.mechanic, mechColor(r.mechanic)) +
            '<span style="font-family:Cinzel,serif;font-size:14px;color:#f3ead8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + r.name + '</span>' +
            '<span style="flex:1;"></span>' + right +
          '</div>' +
          '<div style="margin-top:5px;font-family:' + mono + ';font-size:9px;color:#948876;">' +
            (state.tab === "ready" ? (r.key_capability || "") + ' · ' : "") + sub +
          '</div>' +
          solveBlock +
          (open ? expand(r) : "") +
        '</div>';
      }
      function tabBtn(id, label, n) {
        var on = state.tab === id;
        return '<button data-tab="' + id + '" style="font-family:' + mono + ';font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:' + (on ? "#0c0a07" : "#cdbfa6") + ';background:' + (on ? "linear-gradient(180deg,#e6b765,#cf9a44)" : "transparent") + ';border:1px solid ' + (on ? "#cf9a44" : "#3a2f1f") + ';border-radius:3px;padding:6px 12px;cursor:pointer;font-weight:' + (on ? "700" : "400") + ';">' + label + ' (' + n + ')</button>';
      }
      function render() {
        var rows = state.tab === "ready" ? ready : need;
        var top = ready.filter(function (x) { return x.status === "ready"; })[0];
        var topMeta = top
          ? (top.key_capability || "") + (top.holds_t50 ? ' · holds T50' : (top.dwj_boss_turns ? ' · holds T' + top.dwj_boss_turns : '')) + (top.sim_damage ? ' · ' + simM(top) : '')
          : "";
        var runToday = top
          ? '<div style="display:flex;align-items:center;gap:8px;margin:10px 0 14px;padding:10px 12px;background:linear-gradient(100deg,#1f160d,#15110b);border:1px solid #3a2f1f;border-radius:3px;">' +
              '<span style="font-family:' + mono + ';font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:#6fcf6f;flex:none;">▶ Run today</span>' +
              '<span style="font-family:Cinzel,serif;font-size:15px;color:#f3ead8;">' + top.name + '</span>' +
              '<span style="flex:1;"></span>' +
              '<span style="font-family:' + mono + ';font-size:9px;color:#948876;">' + topMeta + '</span>' +
            '</div>'
          : '';
        host.innerHTML =
          '<div style="display:flex;align-items:center;justify-content:space-between;">' +
            '<div style="font-family:' + mono + ';font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:#a0734a;">Team Recommendation</div>' +
            '<div style="font-family:' + mono + ';font-size:8px;color:#6f6555;">' + ready.length + ' ready · ' + need.length + ' to unlock</div>' +
          '</div>' +
          runToday +
          '<div style="display:flex;gap:8px;margin-bottom:12px;">' + tabBtn("ready", "Ready to build", ready.length) + tabBtn("need", "Need heroes", need.length) + '</div>' +
          '<div style="max-height:430px;overflow-y:auto;padding-right:4px;">' +
            (rows.length ? rows.map(card).join("") : '<div style="font-family:' + mono + ';font-size:10px;color:#6f6555;padding:10px;">Nothing here.</div>') +
          '</div>';
        Array.prototype.forEach.call(host.querySelectorAll("[data-tab]"), function (b) {
          b.addEventListener("click", function () { state.tab = b.getAttribute("data-tab"); render(); });
        });
        Array.prototype.forEach.call(host.querySelectorAll("[data-rid]"), function (c) {
          c.addEventListener("click", function () {
            var id = c.getAttribute("data-rid");
            state.open[id] = !state.open[id];
            render();
          });
        });
        Array.prototype.forEach.call(host.querySelectorAll("[data-solve]"), function (b) {
          b.addEventListener("click", function (e) {
            e.stopPropagation();          // don't toggle the card expand
            solveTeam(b.getAttribute("data-solve"), b);
          });
        });
      }
      render();
      // Deep link / capture helper: ?solve=<id> auto-runs that team's gear solve
      // (server result is cached, so a screenshot shows the verdict).
      var sp = (location.search.match(/[?&]solve=([^&]+)/) || [])[1];
      if (sp) { state.tab = "ready"; solveTeam(decodeURIComponent(sp), null); }
    }).catch(function () {});
  }

  // ---- refresh loop -------------------------------------------------------
  function refreshAll() {
    // Each panel is independent; a failure in one must not stop the others.
    wireResources().catch(function () {});
    wireCB().catch(function () {});
    wireRecommender().catch(function () {});
    wireRecentBattles().catch(function () {});
  }

  // The turn grid is built lazily when the Turn-by-Turn view opens. In sim mode
  // it runs /api/calc-parity-sim (~35s cold); in replay mode it loads a real
  // battle log (window.__replayFile). Re-loads only when the mode/file changes.
  window.__replayFile = null;
  var _tmKey = null;
  var _tmInit = false;
  window.__loadTmGrid = function () {
    // On the very first load, honour a ?replay deep-link BEFORE the default sim
    // fetch can start — otherwise the slow sim load can resolve last and paint
    // over the replay (and a refresh would drop back to the sim plan).
    if (!_tmInit) {
      _tmInit = true;
      if (!window.__replayFile) {
        var rp0 = (location.search.match(/[?&]replay=([^&]+)/) || [])[1];
        if (rp0) window.__replayFile = decodeURIComponent(rp0);
      }
    }
    var key = window.__replayFile ? "replay:" + window.__replayFile : "sim";
    if (_tmKey === key) return;
    _tmKey = key;
    var p = window.__replayFile ? wireReplay(window.__replayFile) : wireRotation();
    p.catch(function () { _tmKey = null; });
  };
  window.__openReplay = function (file) {
    window.__replayFile = file;
    // Persist the replay in the URL (?replay=…#cb-telemetry) so a refresh keeps
    // showing the same battle instead of falling back to the sim plan.
    try { history.replaceState(null, "", location.pathname + "?replay=" + encodeURIComponent(file) + "#cb-telemetry"); } catch (e) {}
    if (window.__setView) window.__setView("cb-telemetry"); else location.hash = "cb-telemetry";
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
