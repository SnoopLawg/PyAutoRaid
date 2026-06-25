// GENERATED from shared.jsx by tools/build_dashboard.mjs — do not edit; edit the .jsx and rebuild.
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/* ---------- Shared tiny helpers used by both dashboards ---------- */
function fmt(n, kind) {
  if (n == null) return '—';
  if (kind === 'silver') {
    if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(0) + 'K';
    return String(Math.round(n));
  }
  if (kind === 'power') return (n / 1e6).toFixed(2) + 'M';
  if (kind === 'compact') {
    if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
    return String(Math.round(n));
  }
  return n.toLocaleString();
}
function relTime(ts) {
  if (!ts) return '—';
  const diff = Math.abs(Date.now() - ts);
  const sign = ts < Date.now() ? 'ago' : 'in';
  const m = Math.floor(diff / 60000);
  const h = Math.floor(m / 60);
  if (h >= 24) return `${sign} ${Math.floor(h / 24)}d ${h % 24}h`;
  if (h > 0) return `${sign} ${h}h ${m % 60}m`;
  if (m > 0) return `${sign} ${m}m`;
  return `${sign} ${Math.floor(diff / 1000)}s`;
}
function timeHM(ts) {
  if (!ts) return '—';
  const d = new Date(ts);
  return d.toTimeString().slice(0, 5);
}
function useSim() {
  const [s, set] = React.useState(window.PARSim.state);
  React.useEffect(() => window.PARSim.subscribe(v => set({
    ...v
  })), []);
  return s;
}

/* ---------- Icon thumbnail helper ---------- */
// Logical name -> game-extracted PNG path. Sources (most authentic first):
//   assets/resources/*  - extracted from ResourceIcons.unity3d (game truth)
//   assets/icons/*      - hand-curated fallback set
const ICON_SRC = {
  // Currencies / shards
  shard: 'resources/Gem.png',
  gems: 'resources/Gem.png',
  gem: 'resources/Gem.png',
  silver: 'resources/Silver.png',
  energy: 'resources/Energy.png',
  // Arena tokens
  arena: 'resources/Token.png',
  // Classic Arena (5v5)
  arena_token: 'resources/Token.png',
  arena3x3: 'resources/Arena3x3Token.png',
  // Tag Arena 3v3
  arena_3v3: 'resources/Arena3x3Token.png',
  arena_3x3_shop: 'resources/Arena3X3ShopCurrency.png',
  live_arena: 'resources/LiveArenaToken.png',
  // Boss keys
  cb: 'resources/AllianceBossKey.png',
  cb_key: 'resources/AllianceBossKey.png',
  hydra: 'resources/AllianceHydraKey.png',
  chimera: 'resources/AllianceChimeraKey.png',
  fw: 'resources/FractionWarKey.png',
  faction: 'resources/FractionWarKey.png',
  faction_war: 'resources/FractionWarKey.png',
  doom_silver: 'resources/DoomTowerSilverKey.png',
  doom_gold: 'resources/DoomTowerGoldKey.png',
  // Misc
  alliance: 'resources/AllianceCoin.png',
  alliance_coin: 'resources/AllianceCoin.png',
  life_token: 'resources/LifeToken.png',
  mythical_dust: 'resources/MythicalDust.png',
  plarium_point: 'resources/PlariumPoint.png',
  plarium_ticket_gold: 'resources/PlariumTicket_Gold.png',
  plarium_ticket_silver: 'resources/PlariumTicket_Silver.png',
  auto_ticket: 'resources/AutoBattleTicket.png',
  particle_summon: 'resources/ParticleSummon.png',
  foggy_energy: 'resources/FoggyForest_Energy.png',
  // Affinities
  affinity_force: 'affinities/force.png',
  affinity_magic: 'affinities/magic.png',
  affinity_spirit: 'affinities/spirit.png',
  affinity_void: 'affinities/void.png'
};
function Icon({
  name,
  size = 20,
  alt
}) {
  // If name maps directly to extracted PNG, use it. Otherwise fall back
  // to the legacy assets/icons/<name>.png path.
  const mapped = ICON_SRC[name];
  const src = mapped ? `assets/${mapped}` : `assets/icons/${name}.png`;
  return /*#__PURE__*/React.createElement("img", {
    src: src,
    width: size,
    height: size,
    alt: alt || name,
    style: {
      objectFit: 'contain',
      display: 'inline-block',
      verticalAlign: 'middle'
    },
    onError: e => {
      e.target.style.visibility = 'hidden';
    }
  });
}

/* ---------- Hero portrait ---------- */
// Game ships only ~38 hero portraits locally + ~100 in on-demand cache;
// missing heroes render as an empty frame (per user req — no HH fallback).
function HeroPortrait({
  typeId,
  size = 40,
  name,
  rarity,
  grade
}) {
  const [failed, setFailed] = React.useState(false);
  const src = `assets/heroes/${typeId}.png`;
  const rarityColor = {
    1: '#9b9b9b',
    2: '#48b948',
    3: '#3a8be0',
    4: '#9b59c5',
    5: '#e1a126'
  }[rarity] || '#444';
  return /*#__PURE__*/React.createElement("div", {
    style: {
      width: size,
      height: size,
      position: 'relative',
      border: `1.5px solid ${rarityColor}`,
      borderRadius: 4,
      background: 'var(--bg-subtle)',
      overflow: 'hidden',
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      flexShrink: 0
    },
    title: name || `hero ${typeId}`
  }, !failed ? /*#__PURE__*/React.createElement("img", {
    src: src,
    width: size - 3,
    height: size - 3,
    style: {
      objectFit: 'cover'
    },
    onError: () => setFailed(true),
    alt: name || ''
  }) : /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 8,
      color: 'var(--text-dim)'
    }
  }, "?"), grade && /*#__PURE__*/React.createElement("span", {
    style: {
      position: 'absolute',
      bottom: -1,
      right: 1,
      fontSize: 8,
      color: '#ffd45e',
      fontWeight: 600,
      textShadow: '0 0 2px #000'
    }
  }, grade, "\u2605"));
}

/* ---------- Affinity badge ---------- */
// Accepts string ("Magic"/"force"/etc) or game enum int (1=Magic 2=Force 3=Spirit 4=Void).
const AFFINITY_INT_MAP = {
  1: 'magic',
  2: 'force',
  3: 'spirit',
  4: 'void'
};
function AffinityIcon({
  element,
  size = 14
}) {
  let fname;
  if (typeof element === 'number') fname = AFFINITY_INT_MAP[element];else fname = (element || '').toLowerCase();
  if (!['force', 'magic', 'spirit', 'void'].includes(fname)) return null;
  return /*#__PURE__*/React.createElement("img", {
    src: `assets/affinities/${fname}.png`,
    width: size,
    height: size,
    style: {
      objectFit: 'contain',
      verticalAlign: 'middle'
    },
    alt: fname
  });
}

/* ---------- Super Raid toggle widget ---------- */
// Polls /api/super-raid every 4s. Renders state + click-to-toggle button.
// Reflects the in-game battle-setup checkbox: x1 / x2 / x3.
function SuperRaidWidget({
  size = 'md'
}) {
  const [s, setS] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  React.useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const r = await fetch('/api/super-raid?action=status', {
          cache: 'no-store'
        });
        if (!alive) return;
        if (r.ok) setS(await r.json());
      } catch (e) {}
    };
    tick();
    const id = setInterval(tick, 4000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);
  const toggle = async () => {
    setBusy(true);
    try {
      const r = await fetch('/api/super-raid?action=toggle', {
        cache: 'no-store'
      });
      if (r.ok) setS(await r.json());
    } catch (e) {}
    setBusy(false);
  };
  if (!s) return /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)'
    }
  }, "super-raid: \u2026");
  const compact = size === 'sm';
  if (s.error || !s.available) {
    return /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        fontSize: compact ? 9.5 : 10.5,
        color: 'var(--text-dim)'
      },
      title: s.note || s.error || 'Super Raid not available here'
    }, "super-raid: n/a");
  }
  const mult = s.multiplier || 1;
  const color = mult >= 2 ? 'var(--accent)' : 'var(--text-sub)';
  const lockTitle = s.locked ? 'locked' : !s.enabled ? 'pass stage once first' : '';
  return /*#__PURE__*/React.createElement("button", {
    onClick: toggle,
    disabled: busy || s.locked || !s.enabled,
    title: lockTitle,
    style: {
      padding: compact ? '2px 8px' : '4px 10px',
      fontSize: compact ? 10 : 11.5,
      lineHeight: 1.2,
      cursor: 'pointer',
      fontFamily: "'JetBrains Mono', monospace",
      background: mult >= 2 ? 'var(--accent-soft)' : 'var(--bg-subtle)',
      color: color,
      border: `1px solid ${mult >= 2 ? 'var(--accent)' : 'var(--border)'}`,
      borderRadius: 4,
      opacity: s.locked || !s.enabled ? 0.5 : 1
    }
  }, "super-raid \xB7 x", mult);
}

/* ---------- Faction badge ---------- */
function FactionIcon({
  factionId,
  size = 14
}) {
  if (!factionId) return null;
  return /*#__PURE__*/React.createElement("img", {
    src: `assets/factions/${factionId}.png`,
    width: size,
    height: size,
    style: {
      objectFit: 'contain',
      verticalAlign: 'middle'
    },
    alt: `faction ${factionId}`,
    onError: e => {
      e.target.style.visibility = 'hidden';
    }
  });
}

/* ---------- Hero portrait by NAME (resolves via a {name->type_id} map) ---------- */
// For data that carries only hero names (tune slots, cast-timeline actors).
function normHeroName(s) {
  return String(s || '').toLowerCase().replace(/[^a-z0-9]/g, '');
}
function HeroPortraitByName({
  name,
  idMap,
  size = 28,
  rarity,
  grade
}) {
  // idMap may be keyed by exact name (backend-resolved) or normalized name.
  let tid = null;
  if (idMap) tid = idMap[name] != null ? idMap[name] : idMap[normHeroName(name)];
  if (!tid) {
    return /*#__PURE__*/React.createElement("div", {
      style: {
        width: size,
        height: size,
        borderRadius: 4,
        border: '1.5px solid #444',
        background: 'var(--bg-subtle)',
        flexShrink: 0
      },
      title: name
    });
  }
  return /*#__PURE__*/React.createElement(HeroPortrait, {
    typeId: tid,
    size: size,
    name: name,
    rarity: rarity,
    grade: grade
  });
}

/* ---------- Skill icon (hero type_id + skill slot s1..s4) ---------- */
const SKILL_ALIAS_IDX = {
  A1: 1,
  A2: 2,
  A3: 3,
  A4: 4
};
function SkillIcon({
  typeId,
  index,
  alias,
  size = 18
}) {
  let idx = index;
  if (idx == null && alias != null) {
    idx = SKILL_ALIAS_IDX[alias] != null ? SKILL_ALIAS_IDX[alias] : /^[1-4]$/.test(String(alias)) ? +alias : null;
  }
  if (!typeId || !idx) return null;
  return /*#__PURE__*/React.createElement("img", {
    src: `assets/skills/${typeId}_s${idx}.png`,
    width: size,
    height: size,
    style: {
      objectFit: 'contain',
      verticalAlign: 'middle',
      borderRadius: 3
    },
    alt: alias || `s${idx}`,
    onError: e => {
      e.target.style.visibility = 'hidden';
    }
  });
}

/* ---------- Mastery icon (keyed by mastery id, e.g. 500161) ---------- */
function MasteryIcon({
  id,
  size = 18,
  title
}) {
  if (!id) return null;
  return /*#__PURE__*/React.createElement("img", {
    src: `assets/masteries/${id}.png`,
    width: size,
    height: size,
    style: {
      objectFit: 'contain',
      verticalAlign: 'middle'
    },
    alt: title || `mastery ${id}`,
    title: title,
    onError: e => {
      e.target.style.visibility = 'hidden';
    }
  });
}

/* ---------- Artifact-set icon (by set name) ---------- */
function SetIcon({
  name,
  size = 18
}) {
  if (!name) return null;
  return /*#__PURE__*/React.createElement("img", {
    src: `assets/artifact_sets/${name}.png`,
    width: size,
    height: size,
    style: {
      objectFit: 'contain',
      verticalAlign: 'middle'
    },
    alt: name,
    title: name,
    onError: e => {
      e.target.style.visibility = 'hidden';
    }
  });
}

/* ---------- Inline SVG icons ---------- */
const SvgIcon = {
  play: p => /*#__PURE__*/React.createElement("svg", _extends({
    viewBox: "0 0 16 16",
    width: "12",
    height: "12",
    fill: "currentColor"
  }, p), /*#__PURE__*/React.createElement("path", {
    d: "M4 2l9 6-9 6z"
  })),
  pause: p => /*#__PURE__*/React.createElement("svg", _extends({
    viewBox: "0 0 16 16",
    width: "12",
    height: "12",
    fill: "currentColor"
  }, p), /*#__PURE__*/React.createElement("rect", {
    x: "4",
    y: "2",
    width: "3",
    height: "12"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "9",
    y: "2",
    width: "3",
    height: "12"
  })),
  check: p => /*#__PURE__*/React.createElement("svg", _extends({
    viewBox: "0 0 16 16",
    width: "12",
    height: "12",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2.2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, p), /*#__PURE__*/React.createElement("polyline", {
    points: "2.5,8 6.5,12 13.5,4"
  })),
  clock: p => /*#__PURE__*/React.createElement("svg", _extends({
    viewBox: "0 0 16 16",
    width: "12",
    height: "12",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.5"
  }, p), /*#__PURE__*/React.createElement("circle", {
    cx: "8",
    cy: "8",
    r: "6"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M8 4v4l2.5 2",
    strokeLinecap: "round"
  })),
  cpu: p => /*#__PURE__*/React.createElement("svg", _extends({
    viewBox: "0 0 16 16",
    width: "12",
    height: "12",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.2"
  }, p), /*#__PURE__*/React.createElement("rect", {
    x: "3",
    y: "3",
    width: "10",
    height: "10",
    rx: "1"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "5.5",
    y: "5.5",
    width: "5",
    height: "5"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M1 5h2M1 8h2M1 11h2M13 5h2M13 8h2M13 11h2M5 1v2M8 1v2M11 1v2M5 13v2M8 13v2M11 13v2"
  })),
  arrow: p => /*#__PURE__*/React.createElement("svg", _extends({
    viewBox: "0 0 16 16",
    width: "10",
    height: "10",
    fill: "currentColor"
  }, p), /*#__PURE__*/React.createElement("path", {
    d: "M6 3l5 5-5 5z"
  })),
  restart: p => /*#__PURE__*/React.createElement("svg", _extends({
    viewBox: "0 0 16 16",
    width: "12",
    height: "12",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.5"
  }, p), /*#__PURE__*/React.createElement("path", {
    d: "M13 8a5 5 0 1 1-1.5-3.5",
    strokeLinecap: "round"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M13 2v3h-3",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  })),
  dot: () => /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-block',
      width: 4,
      height: 4,
      borderRadius: '50%',
      background: 'currentColor',
      margin: '0 6px',
      verticalAlign: 'middle',
      opacity: 0.4
    }
  })
};

/* ---------- Sparkline ---------- */
function Spark({
  data,
  height = 28,
  width = 120,
  color = 'currentColor',
  fill = false
}) {
  if (!data || !data.length) return null;
  const max = Math.max(...data),
    min = Math.min(...data);
  const range = max - min || 1;
  const step = width / (data.length - 1 || 1);
  const pts = data.map((v, i) => [i * step, height - (v - min) / range * (height - 4) - 2]);
  const path = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');
  return /*#__PURE__*/React.createElement("svg", {
    width: width,
    height: height,
    style: {
      overflow: 'visible'
    }
  }, fill && /*#__PURE__*/React.createElement("path", {
    d: path + ` L${width},${height} L0,${height} Z`,
    fill: color,
    opacity: 0.15
  }), /*#__PURE__*/React.createElement("path", {
    d: path,
    fill: "none",
    stroke: color,
    strokeWidth: "1.5",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }));
}

/* ---------- Log list (shared) ---------- */
function LogFeed({
  limit = 40,
  theme = 'A'
}) {
  const s = useSim();
  const [realRows, setRealRows] = React.useState(null);

  // Poll /api/mod-log for live BepInEx + six_star feed every 2s.
  React.useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const r = await fetch(`/api/mod-log?n=${limit}`, {
          cache: 'no-store'
        });
        if (!alive) return;
        if (r.ok) {
          const j = await r.json();
          setRealRows(j.entries || []);
        }
      } catch (e) {}
    };
    tick();
    const id = setInterval(tick, 2000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [limit]);
  const rows = (realRows && realRows.length ? realRows : s.log).slice(0, limit);
  const mono = theme === 'B';
  return /*#__PURE__*/React.createElement("div", {
    className: "scroll",
    style: {
      overflowY: 'auto',
      height: '100%',
      padding: mono ? '6px 4px' : '4px 2px'
    }
  }, rows.map((r, i) => /*#__PURE__*/React.createElement("div", {
    key: r.t + '-' + i,
    style: {
      display: 'grid',
      gridTemplateColumns: '64px 70px 1fr',
      gap: 12,
      padding: mono ? '2px 10px' : '5px 10px',
      fontFamily: mono ? "'JetBrains Mono', monospace" : 'inherit',
      fontSize: mono ? 11.5 : 12,
      lineHeight: 1.5,
      borderBottom: mono ? '0' : '1px solid var(--border)',
      opacity: i > 18 ? 0.5 : 1,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-dim)'
    },
    className: "mono"
  }, new Date(r.t).toTimeString().slice(0, 8)), /*#__PURE__*/React.createElement("span", {
    className: `layer-badge layer-${r.tag || 'system'}`,
    style: {
      alignSelf: 'center',
      justifySelf: 'start',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap',
      maxWidth: '100%'
    }
  }, r.tag || 'sys'), /*#__PURE__*/React.createElement("span", {
    className: `log-${r.level}`,
    style: {
      minWidth: 0,
      overflow: 'hidden',
      textOverflow: 'ellipsis'
    }
  }, r.text))));
}