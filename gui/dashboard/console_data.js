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

  // ---- refresh loop -------------------------------------------------------
  function refreshAll() {
    // Each panel is independent; a failure in one must not stop the others.
    wireResources().catch(function () {});
    wireCB().catch(function () {});
  }

  document.addEventListener("DOMContentLoaded", function () {
    refreshAll();
    // Resources drift slowly (energy regen, key spend); a 60s poll is plenty.
    setInterval(refreshAll, 60000);
  });
})();
