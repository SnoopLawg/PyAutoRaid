// GENERATED from direction_b_pages.jsx by tools/build_dashboard.mjs — do not edit; edit the .jsx and rebuild.
/* ===================== DIRECTION B — Page components ===================== */

function PanelDailyCollect() {
  const [state, setState] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState(null);
  const refresh = React.useCallback(async () => {
    try {
      const r = await fetch('/api/daily-collect/status', {
        cache: 'no-store'
      });
      if (r.ok) setState(await r.json());
    } catch (e) {
      setErr(String(e));
    }
  }, []);
  React.useEffect(() => {
    refresh();
    const id = setInterval(refresh, 4000);
    return () => clearInterval(id);
  }, [refresh]);
  const start = async (force = false) => {
    setBusy(true);
    setErr(null);
    try {
      const r = await fetch('/api/daily-collect/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          force,
          quiet: true
        })
      });
      const j = await r.json();
      if (!r.ok) setErr(j.error || `HTTP ${r.status}`);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
      refresh();
    }
  };
  const stop = async () => {
    setBusy(true);
    try {
      await fetch('/api/daily-collect/stop', {
        method: 'POST'
      });
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
      refresh();
    }
  };
  const phases = state?.phases || [];
  const doneN = phases.filter(p => p.status === 'done').length;
  const failN = phases.filter(p => p.status === 'failed').length;
  const running = state?.running;
  const dot = status => {
    if (status === 'done') return {
      color: 'var(--ok)',
      glyph: '●'
    };
    if (status === 'failed') return {
      color: 'var(--danger)',
      glyph: '●'
    };
    return {
      color: 'var(--text-dim)',
      glyph: '○'
    };
  };
  return /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 0,
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement(PanelHeader, {
    title: "daily collect",
    right: running ? 'running' : `${doneN}/${phases.length}`
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 10
    }
  }, phases.map(p => {
    const d = dot(p.status);
    return /*#__PURE__*/React.createElement("div", {
      key: p.key,
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '3px 4px',
        fontSize: 11.5
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        color: d.color,
        fontSize: 13,
        lineHeight: 1
      }
    }, d.glyph), /*#__PURE__*/React.createElement("span", {
      style: {
        flex: 1
      },
      className: "truncate"
    }, p.label), p.elapsed_sec != null && /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        fontSize: 10,
        color: 'var(--text-dim)'
      }
    }, p.elapsed_sec.toFixed(1), "s"));
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 6,
      marginTop: 8
    }
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn btn-sm",
    disabled: busy || running,
    onClick: () => start(false),
    style: {
      flex: 1
    }
  }, running ? 'collecting…' : doneN === phases.length ? 'all done' : 'collect now'), running ? /*#__PURE__*/React.createElement("button", {
    className: "btn btn-sm",
    disabled: busy,
    onClick: stop,
    title: "stop"
  }, "stop") : doneN === phases.length ? /*#__PURE__*/React.createElement("button", {
    className: "btn btn-sm",
    disabled: busy,
    onClick: () => start(true),
    title: "force re-run"
  }, "force") : null), failN > 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--danger)',
      marginTop: 6
    }
  }, failN, " phase", failN === 1 ? '' : 's', " failed today \u2014 see log tail"), err && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      color: 'var(--danger)',
      marginTop: 6
    }
  }, err), state?.log_tail && /*#__PURE__*/React.createElement("details", {
    style: {
      marginTop: 8
    }
  }, /*#__PURE__*/React.createElement("summary", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      cursor: 'pointer'
    }
  }, "log tail"), /*#__PURE__*/React.createElement("pre", {
    className: "mono",
    style: {
      maxHeight: 140,
      overflow: 'auto',
      fontSize: 10,
      background: 'var(--bg-subtle)',
      padding: 6,
      borderRadius: 3,
      marginTop: 4,
      whiteSpace: 'pre-wrap'
    }
  }, state.log_tail.split('\n').slice(-40).join('\n')))));
}
function PageOverview({
  s,
  pct,
  doneCount,
  activeTask,
  running
}) {
  const totalMs = s.tasks.reduce((a, t) => a + t.duration, 0);
  const elapsedMs = s.tasks.reduce((a, t, i) => a + (t.status === 'done' ? t.duration : i === s.queueIdx ? t.ms : 0), 0);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '320px 1fr 260px',
      gap: 10,
      minHeight: '100%'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      minHeight: 0
    }
  }, /*#__PURE__*/React.createElement(PanelTaskQueue, {
    s: s
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateRows: 'auto 1fr auto',
      gap: 10,
      minHeight: 0
    }
  }, /*#__PURE__*/React.createElement(PanelActiveTask, {
    s: s,
    activeTask: activeTask,
    running: running,
    doneCount: doneCount,
    totalMs: totalMs,
    elapsedMs: elapsedMs
  }), /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 0,
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      minHeight: 0
    }
  }, /*#__PURE__*/React.createElement(PanelHeader, {
    title: "14-day earnings",
    right: "gems \xB7 silver \xB7 cb dmg"
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 10,
      flex: 1,
      minHeight: 0,
      display: 'flex',
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement(HistoryChartB, {
    data: s.history,
    height: 140
  }))), /*#__PURE__*/React.createElement(PanelResources, {
    s: s
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateRows: 'auto auto auto auto',
      gap: 10,
      minHeight: 0
    }
  }, /*#__PURE__*/React.createElement(PanelDailyCollect, null), /*#__PURE__*/React.createElement(PanelLayers, {
    s: s
  }), /*#__PURE__*/React.createElement(PanelCB, {
    s: s,
    compact: true
  }), /*#__PURE__*/React.createElement(PanelArena, {
    s: s
  })));
}
function PageLive({
  s,
  pct,
  doneCount,
  activeTask,
  running
}) {
  const totalMs = s.tasks.reduce((a, t) => a + t.duration, 0);
  const elapsedMs = s.tasks.reduce((a, t, i) => a + (t.status === 'done' ? t.duration : i === s.queueIdx ? t.ms : 0), 0);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '420px 1fr',
      gap: 10,
      minHeight: '100%'
    }
  }, /*#__PURE__*/React.createElement(PanelTaskQueue, {
    s: s
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateRows: 'auto 1fr',
      gap: 10,
      minHeight: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 0,
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement(PanelHeader, {
    title: "active task",
    right: running ? 'running' : 'idle'
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 22,
      display: 'grid',
      gridTemplateColumns: '1fr auto',
      gap: 22
    }
  }, /*#__PURE__*/React.createElement("div", null, activeTask && running ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      marginBottom: 6
    }
  }, "Step ", s.queueIdx + 1, " / ", s.tasks.length), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 28,
      fontWeight: 500,
      letterSpacing: '-0.015em',
      marginBottom: 12
    }
  }, activeTask.label), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      marginBottom: 14
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: `layer-badge layer-${activeTask.layer}`
  }, "via ", activeTask.layer), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 12,
      color: 'var(--text-sub)'
    }
  }, Math.min(100, Math.round(activeTask.ms / activeTask.duration * 100)), "% \xB7 elapsed ", (activeTask.ms / 1000).toFixed(1), "s")), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 6,
      background: 'var(--bg-subtle)',
      borderRadius: 3,
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: '100%',
      width: `${Math.min(100, activeTask.ms / activeTask.duration * 100)}%`,
      background: 'var(--accent)'
    }
  }))) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      marginBottom: 6
    }
  }, "Idle"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 28,
      fontWeight: 500,
      marginBottom: 10
    }
  }, doneCount === s.tasks.length ? 'Daily run complete' : 'Awaiting schedule'), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      color: 'var(--text-sub)'
    }
  }, "Next trigger ", relTime(s.nextRunAt), " \xB7 Windows Task Scheduler"))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      minWidth: 160
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em'
    }
  }, "Total progress"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 24,
      fontWeight: 500
    },
    className: "num"
  }, pct, "%"), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 4,
      background: 'var(--bg-subtle)',
      borderRadius: 2,
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: '100%',
      width: pct + '%',
      background: running ? 'var(--accent)' : 'var(--text-dim)'
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: 'var(--text-sub)',
      marginTop: 4
    },
    className: "mono"
  }, doneCount, " / ", s.tasks.length, " steps")))), /*#__PURE__*/React.createElement(PanelLayers, {
    s: s
  })));
}
function PageTasks({
  s
}) {
  const selectedCount = s.tasks.filter(t => t.selected).length;
  const allSelected = selectedCount === s.tasks.length;
  const noneSelected = selectedCount === 0;
  const scheduleRight = /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10
    }
  }, /*#__PURE__*/React.createElement("div", {
    onClick: s.running ? undefined : () => window.PARSim.setAllSelected(!allSelected),
    title: s.running ? '' : allSelected ? 'Deselect all' : 'Select all',
    style: {
      width: 14,
      height: 14,
      borderRadius: 3,
      border: '1px solid',
      borderColor: allSelected || !noneSelected ? 'var(--accent)' : 'var(--border-strong)',
      background: allSelected ? 'var(--accent-soft)' : 'transparent',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      cursor: s.running ? 'default' : 'pointer'
    }
  }, allSelected && /*#__PURE__*/React.createElement(SvgIcon.check, {
    style: {
      color: 'var(--accent)',
      opacity: 0.85
    }
  }), !allSelected && !noneSelected && /*#__PURE__*/React.createElement("div", {
    style: {
      width: 6,
      height: 2,
      background: 'var(--accent)'
    }
  })), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 11,
      color: 'var(--text-dim)'
    }
  }, selectedCount, "/", s.tasks.length, " selected"), /*#__PURE__*/React.createElement("button", {
    className: `btn ${s.running ? '' : 'primary'}`,
    onClick: () => window.PARSim.setRunning(!s.running),
    disabled: !s.running && selectedCount === 0,
    style: {
      height: 26,
      padding: '0 12px',
      fontSize: 12
    }
  }, s.running ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(SvgIcon.pause, null), " Pause") : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(SvgIcon.play, null), " Run selected")));
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 320px',
      gap: 10,
      minHeight: '100%'
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 0,
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column'
    }
  }, /*#__PURE__*/React.createElement(PanelHeader, {
    title: "full task schedule",
    right: scheduleRight
  }), /*#__PURE__*/React.createElement("div", {
    className: "scroll",
    style: {
      flex: 1,
      overflowY: 'auto'
    }
  }, s.tasks.map((t, i) => {
    const clickable = !s.running && (t.status === 'pending' || t.status === 'skipped');
    const label = t.status === 'pending' && !t.selected ? 'skip' : t.status;
    return /*#__PURE__*/React.createElement("div", {
      key: t.id,
      onClick: clickable ? () => window.PARSim.toggleSelected(t.id) : undefined,
      style: {
        display: 'grid',
        gridTemplateColumns: '30px 1fr 140px 100px 80px',
        gap: 12,
        alignItems: 'center',
        padding: '10px 16px',
        borderBottom: '1px solid var(--border)',
        background: t.status === 'running' ? 'var(--accent-soft)' : 'transparent',
        opacity: t.status === 'skipped' || t.status === 'pending' && !t.selected ? 0.55 : 1,
        cursor: clickable ? 'pointer' : 'default'
      },
      title: clickable ? t.selected ? 'Click to skip' : 'Click to include' : ''
    }, /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        color: 'var(--text-dim)',
        fontSize: 11
      }
    }, String(i + 1).padStart(2, '0')), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 13,
        fontWeight: t.status === 'running' ? 500 : 400,
        color: t.status === 'pending' || t.status === 'skipped' ? 'var(--text-sub)' : 'var(--text)',
        textDecoration: t.status === 'skipped' ? 'line-through' : 'none'
      }
    }, t.label), /*#__PURE__*/React.createElement("div", {
      className: "mono",
      style: {
        fontSize: 10.5,
        color: 'var(--text-dim)',
        marginTop: 2
      }
    }, t.id)), /*#__PURE__*/React.createElement("span", {
      className: `layer-badge layer-${t.layer}`,
      style: {
        justifySelf: 'start'
      }
    }, t.layer), /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        fontSize: 11,
        color: 'var(--text-sub)'
      }
    }, (t.duration / 1000).toFixed(1), "s"), /*#__PURE__*/React.createElement("span", {
      className: "chip",
      style: {
        color: t.status === 'done' ? 'var(--ok)' : t.status === 'running' ? 'var(--accent)' : label === 'skip' ? 'var(--text-dim)' : t.selected ? 'var(--accent)' : 'var(--text-dim)',
        borderColor: 'transparent',
        background: t.selected && t.status === 'pending' ? 'var(--accent-soft)' : 'var(--bg-subtle)',
        justifySelf: 'start'
      }
    }, /*#__PURE__*/React.createElement("span", {
      className: `dot ${t.status === 'done' ? 'ok' : t.status === 'running' ? 'run' : t.selected && t.status === 'pending' ? 'ok' : ''}`
    }), label));
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateRows: 'auto 1fr',
      gap: 10,
      minHeight: 0
    }
  }, /*#__PURE__*/React.createElement(ScheduleCard, null), /*#__PURE__*/React.createElement(PanelEvents, {
    s: s
  })));
}
function PageResources({
  s
}) {
  // Build each sparkline from the last 7 real history snapshots. When a field
  // isn't in the snapshots yet (we only started tracking arena tokens / shards
  // recently) the trend comes back with fewer points.
  const history = (s.history || []).slice(-7);
  const trend = getter => history.map(h => getter(h)).filter(v => v != null);
  const [openRes, setOpenRes] = React.useState(null);
  const rows = [{
    key: 'energy',
    icon: 'energy',
    label: 'Energy',
    val: fmt(s.resources.energy),
    get: h => h.energy,
    color: 'oklch(0.82 0.17 85)',
    detail: 'Cap 130. Overflow drains on regen.'
  }, {
    key: 'silver',
    icon: 'silver',
    label: 'Silver',
    val: fmt(s.resources.silver, 'silver'),
    get: h => h.silver_m,
    color: 'var(--violet)',
    detail: 'Account silver. Market buy reserve.',
    valueFmt: v => fmt(v * 1e6, 'silver')
  }, {
    key: 'gems',
    icon: 'shard',
    label: 'Gems',
    val: fmt(s.resources.gems),
    get: h => h.gems,
    color: 'var(--accent)',
    detail: 'Reserved for Arena refreshes only.'
  }, {
    key: 'arena',
    icon: 'arena',
    label: 'Arena tokens',
    val: s.resources.arena_tokens != null ? Number(s.resources.arena_tokens).toFixed(1) : '—',
    get: h => h.arena_tokens,
    color: 'oklch(0.75 0.18 180)',
    detail: 'Auto-regen 1 / 2h.'
  }, {
    key: 'cb',
    icon: 'cb',
    label: 'CB keys',
    val: `${s.resources.cb_keys}/2`,
    get: h => h.cb_keys,
    color: 'oklch(0.70 0.20 25)',
    detail: 'Reset 06:00 UTC.'
  }
  // Mystery Shards removed from this row — already rendered in
  // <ShardsInventory/> below alongside Ancient/Void/Sacred/Primal.
  ];
  const active = openRes ? rows.find(r => r.key === openRes) : null;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(3, 1fr)',
      gap: 10
    }
  }, rows.map(r => {
    const t = trend(r.get);
    return /*#__PURE__*/React.createElement("div", {
      key: r.label,
      className: "card",
      onClick: () => setOpenRes(r.key),
      style: {
        padding: 16,
        cursor: 'pointer'
      },
      title: "Click for history"
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        fontSize: 11,
        color: 'var(--text-sub)',
        textTransform: 'uppercase',
        letterSpacing: '0.06em'
      }
    }, /*#__PURE__*/React.createElement(Icon, {
      name: r.icon,
      size: 14
    }), " ", r.label), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'end',
        justifyContent: 'space-between',
        marginTop: 8
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 26,
        fontWeight: 600,
        letterSpacing: '-0.01em'
      },
      className: "num"
    }, r.val), t.length >= 2 ? /*#__PURE__*/React.createElement(Spark, {
      data: t,
      color: r.color,
      width: 80,
      height: 32,
      fill: true
    }) : /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 10,
        color: 'var(--text-dim)',
        fontStyle: 'italic'
      }
    }, "collecting\u2026")), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 11,
        color: 'var(--text-dim)',
        marginTop: 10
      }
    }, r.detail));
  }), active && /*#__PURE__*/React.createElement(ResourceHistoryModal, {
    row: active,
    history: s.history,
    onClose: () => setOpenRes(null)
  }), /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 16,
      gridColumn: 'span 3'
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-title",
    style: {
      marginBottom: 10
    }
  }, "Keys & tokens"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(6, 1fr)',
      gap: 10
    }
  }, [
  // Numbers all use the unified `--text` color now — icons carry
  // the visual identity. The previous rainbow palette was loud
  // and made empty (0) values blend with full ones.
  ['Classic Arena', 'classic_arena_tokens', 'arena_token'], ['Tag Arena 3v3', 'tag_arena_tokens', 'arena_token'], ['Live Arena', 'live_arena_tokens', 'live_arena'], ['CB (Demon Lord)', 'demon_lord_keys', 'cb_key'], ['Hydra', 'hydra_keys', 'hydra'], ['Chimera', 'chimera_keys', 'chimera'], ['Fortress', 'fortress_keys', 'cb_key'], ['Cursed City', 'cursed_city_keys', 'cb_key'], ['Doom Tower (Gold)', 'doom_tower_gold_keys', 'doom_gold'], ['Doom Tower (Silver)', 'doom_tower_silver_keys', 'doom_silver'], ['Faction Wars', 'faction_keys', 'fw'], ['Auto tickets', 'auto_tickets', 'auto_ticket']].map(([label, key, icon]) => {
    const v = (s.resources.keys || {})[key];
    const isEmpty = v == null || v === 0;
    return /*#__PURE__*/React.createElement("div", {
      key: key,
      style: {
        padding: '10px 12px',
        background: 'var(--bg-subtle)',
        borderRadius: 6,
        border: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        gap: 10
      }
    }, /*#__PURE__*/React.createElement(Icon, {
      name: icon,
      size: 22,
      style: isEmpty ? {
        opacity: 0.4
      } : undefined
    }), /*#__PURE__*/React.createElement("div", {
      style: {
        minWidth: 0,
        flex: 1
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 10,
        color: 'var(--text-dim)',
        textTransform: 'uppercase',
        letterSpacing: '0.04em'
      },
      className: "truncate"
    }, label), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 18,
        fontWeight: 600,
        color: isEmpty ? 'var(--text-dim)' : 'var(--text)',
        marginTop: 2
      },
      className: "num"
    }, v == null ? '—' : v)));
  }))), /*#__PURE__*/React.createElement(ShardsInventory, {
    s: s
  }), /*#__PURE__*/React.createElement(AllResourcesGrid, {
    s: s
  }));
}

/* All-resources catalog. Pulls /api/state.resources.all_raw which is the
 * raw mod /all-resources dump (90+ keys: crafting mats, soul coins, foggy
 * forest tokens, etc). Renders every nonzero key with an icon + count.
 * Icons missing from extraction render as an empty rarity-colored frame
 * (per user req: no fallback hotlinks). */
function AllResourcesGrid({
  s
}) {
  const raw = (s.resources || {}).all_raw || {};
  const entries = Object.entries(raw).filter(([k, v]) => v > 0).sort((a, b) => RESOURCE_GROUP_ORDER(a[0]) - RESOURCE_GROUP_ORDER(b[0]) || a[0].localeCompare(b[0]));
  if (entries.length === 0) return null;
  return /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 16,
      gridColumn: 'span 3'
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-title",
    style: {
      marginBottom: 8
    }
  }, "All resources ", /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      fontWeight: 400,
      marginLeft: 6
    }
  }, "\xB7 ", entries.length, " types live")), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      marginBottom: 10
    }
  }, "Crafting mats, dungeon-specific items, soul coins/essences. Live from mod's /all-resources."), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
      gap: 8
    }
  }, entries.map(([k, v]) => /*#__PURE__*/React.createElement(ResourceTile, {
    key: k,
    resourceKey: k,
    value: v
  }))));
}

// Group ordering for sort: keys/energy first, then currencies, mats, etc.
function RESOURCE_GROUP_ORDER(k) {
  if (/^(Energy|Silver|Gems|Tokens|AutoBattleTickets|MythicalDust|PlariumPoints)$/.test(k)) return 0;
  if (/Key/.test(k)) return 1;
  if (/Token/.test(k)) return 2;
  if (/Medal/.test(k)) return 3;
  if (/Coin|Essence|Currency/.test(k)) return 4;
  if (/Soulstone|Bloodstone/.test(k)) return 5;
  if (/Magisteel|Corehammer|Meteors/.test(k)) return 6;
  if (/(Spider|Dragon|Scarab|Magma|Frost|Griffin|Dreadhorn|Fae|Instinct|Nether)/.test(k)) return 7; // dungeon mats
  if (/FoggyForest/.test(k)) return 8;
  if (/Siege/.test(k)) return 9;
  if (/CursedCity/.test(k)) return 10;
  return 99;
}
function ResourceTile({
  resourceKey,
  value
}) {
  // Try the extracted icon at assets/resources/<key>.png. If it 404s,
  // <Icon> hides the img; the empty frame fills naturally.
  const display = value >= 1e6 ? (value / 1e6).toFixed(1) + 'M' : value >= 1e3 ? (value / 1e3).toFixed(1) + 'k' : value % 1 ? value.toFixed(1) : value;
  // Prettify: SoulstoneRare -> "Soulstone Rare"
  const label = resourceKey.replace(/([A-Z])/g, ' $1').trim();
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      padding: '8px 10px',
      background: 'var(--bg-subtle)',
      border: '1px solid var(--border)',
      borderRadius: 5
    },
    title: resourceKey
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 32,
      height: 32,
      flexShrink: 0,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: '#1a1d21',
      border: '1px solid var(--border)',
      borderRadius: 4
    }
  }, /*#__PURE__*/React.createElement("img", {
    src: `assets/resources/${resourceKey}.png`,
    width: 28,
    height: 28,
    style: {
      objectFit: 'contain'
    },
    onError: e => {
      e.target.style.display = 'none';
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      minWidth: 0,
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "truncate",
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.04em'
    }
  }, label), /*#__PURE__*/React.createElement("div", {
    className: "num",
    style: {
      fontSize: 14,
      fontWeight: 600,
      color: 'var(--text)'
    }
  }, display)));
}
function ShardsInventory({
  s
}) {
  const [open, setOpen] = React.useState(null); // which shard key is open, or null
  const shards = [{
    key: 'mystery',
    label: 'Mystery',
    icon: 'shard_mystery',
    val: s.resources.mystery_shards,
    color: 'var(--text-sub)'
  }, {
    key: 'ancient',
    label: 'Ancient',
    icon: 'shard_ancient',
    val: s.resources.ancient_shards,
    color: 'oklch(0.65 0.18 255)'
  }, {
    key: 'void',
    label: 'Void',
    icon: 'shard_void',
    val: s.resources.void_shards,
    color: 'var(--violet)'
  }, {
    key: 'sacred',
    label: 'Sacred',
    icon: 'shard_sacred',
    val: s.resources.sacred_shards,
    color: 'oklch(0.78 0.15 85)'
  }, {
    key: 'primal',
    label: 'Primal',
    icon: 'shard_primal',
    val: s.resources.primal_shards,
    color: 'oklch(0.68 0.22 20)'
  }];
  const active = open ? shards.find(x => x.key === open) : null;
  return /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 16,
      gridColumn: 'span 3'
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-title",
    style: {
      marginBottom: 10
    }
  }, "Shards inventory"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(5, 1fr)',
      gap: 12
    }
  }, shards.map(sh => /*#__PURE__*/React.createElement("div", {
    key: sh.key,
    onClick: () => sh.val != null && setOpen(sh.key),
    style: {
      padding: '12px 14px',
      background: 'var(--bg-subtle)',
      borderRadius: 6,
      border: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      cursor: sh.val != null ? 'pointer' : 'default'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: sh.icon,
    size: 40,
    alt: sh.label + ' shard'
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em'
    }
  }, sh.label), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 22,
      fontWeight: 600,
      color: sh.val == null ? 'var(--text-dim)' : sh.color,
      marginTop: 2
    },
    className: "num"
  }, sh.val == null ? '—' : sh.val))))), active && /*#__PURE__*/React.createElement(ShardHistoryModal, {
    shard: active,
    history: s.history,
    onClose: () => setOpen(null)
  }));
}

// Generic resource history modal — works for the top-row Energy/Silver/etc.
// cards. Same look as ShardHistoryModal but pulls the series via a
// caller-provided `row.get(historyEntry)` getter.
function ResourceHistoryModal({
  row,
  history,
  onClose
}) {
  const series = (history || []).map(h => ({
    day: h.day,
    v: row.get(h)
  })).filter(p => p.v != null);
  const hasData = series.length >= 1;
  const values = series.map(p => p.v);
  const min = hasData ? Math.min(...values) : 0;
  const max = hasData ? Math.max(...values) : 0;
  const W = 560,
    H = 180,
    P = 28;
  const range = max - min || 1;
  const pts = series.map((p, i) => {
    const x = P + (series.length > 1 ? i * (W - 2 * P) / (series.length - 1) : (W - 2 * P) / 2);
    const y = H - P - (p.v - min) / range * (H - 2 * P);
    return [x, y, p.v, p.day];
  });
  const path = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');
  const jumps = series.slice(1).map((p, i) => ({
    day: p.day,
    delta: p.v - series[i].v
  })).filter(j => j.delta !== 0).sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta)).slice(0, 5);
  const fmtV = row.valueFmt || (v => v);
  return /*#__PURE__*/React.createElement("div", {
    onClick: onClose,
    style: {
      position: 'fixed',
      inset: 0,
      background: 'rgba(0,0,0,0.55)',
      zIndex: 200,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    }
  }, /*#__PURE__*/React.createElement("div", {
    onClick: e => e.stopPropagation(),
    className: "card",
    style: {
      padding: 20,
      width: 640,
      maxWidth: '92vw',
      maxHeight: '88vh',
      overflow: 'auto',
      background: 'var(--bg-elev)',
      border: '1px solid var(--border-strong)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      marginBottom: 16
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: row.icon,
    size: 32
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em'
    }
  }, row.label), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 26,
      fontWeight: 600,
      color: row.color
    },
    className: "num"
  }, row.val)), /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    onClick: onClose,
    style: {
      height: 28,
      padding: '0 10px'
    }
  }, "Close")), !hasData && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 28,
      fontSize: 12,
      color: 'var(--text-dim)',
      textAlign: 'center'
    }
  }, "No history yet. Snapshots start recording now \u2014 come back later."), hasData && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("svg", {
    viewBox: `0 0 ${W} ${H + 20}`,
    width: "100%",
    height: H + 22,
    style: {
      display: 'block',
      marginBottom: 12
    }
  }, [0, 0.25, 0.5, 0.75, 1].map((t, i) => /*#__PURE__*/React.createElement("line", {
    key: i,
    x1: P,
    x2: W - P,
    y1: P + t * (H - 2 * P),
    y2: P + t * (H - 2 * P),
    stroke: "var(--border)",
    strokeDasharray: "2 4"
  })), /*#__PURE__*/React.createElement("path", {
    d: path + ` L${pts[pts.length - 1][0]},${H - P} L${pts[0][0]},${H - P} Z`,
    fill: row.color,
    opacity: 0.12
  }), /*#__PURE__*/React.createElement("path", {
    d: path,
    fill: "none",
    stroke: row.color,
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }), pts.map((p, i) => /*#__PURE__*/React.createElement("g", {
    key: i
  }, /*#__PURE__*/React.createElement("circle", {
    cx: p[0],
    cy: p[1],
    r: "3",
    fill: row.color
  }), /*#__PURE__*/React.createElement("text", {
    x: p[0],
    y: H + 14,
    fontSize: "10",
    fill: "var(--text-dim)",
    textAnchor: "middle",
    fontFamily: "'JetBrains Mono', monospace"
  }, p[3]))), /*#__PURE__*/React.createElement("text", {
    x: P - 6,
    y: P + 4,
    fontSize: "10",
    fill: "var(--text-dim)",
    textAnchor: "end",
    fontFamily: "'JetBrains Mono', monospace"
  }, fmtV(max)), /*#__PURE__*/React.createElement("text", {
    x: P - 6,
    y: H - P + 4,
    fontSize: "10",
    fill: "var(--text-dim)",
    textAnchor: "end",
    fontFamily: "'JetBrains Mono', monospace"
  }, fmtV(min))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gap: 16
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "card-title",
    style: {
      marginBottom: 6
    }
  }, "Stats"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      lineHeight: 1.8,
      color: 'var(--text-sub)'
    }
  }, /*#__PURE__*/React.createElement("div", null, "Data points \xB7 ", /*#__PURE__*/React.createElement("span", {
    className: "mono"
  }, series.length)), /*#__PURE__*/React.createElement("div", null, "Min / Max \xB7 ", /*#__PURE__*/React.createElement("span", {
    className: "mono"
  }, fmtV(min), " / ", fmtV(max))), /*#__PURE__*/React.createElement("div", null, "Latest \xB7 ", /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: row.color
    }
  }, fmtV(series[series.length - 1].v))))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "card-title",
    style: {
      marginBottom: 6
    }
  }, "Biggest changes"), jumps.length === 0 ? /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11.5,
      color: 'var(--text-dim)'
    }
  }, "No day-over-day changes yet.") : /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      lineHeight: 1.8
    },
    className: "mono"
  }, jumps.map(j => /*#__PURE__*/React.createElement("div", {
    key: j.day,
    style: {
      display: 'flex',
      justifyContent: 'space-between'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-dim)'
    }
  }, j.day), /*#__PURE__*/React.createElement("span", {
    style: {
      color: j.delta > 0 ? 'var(--ok)' : 'var(--danger)'
    }
  }, j.delta > 0 ? '+' : '', fmtV(j.delta))))))))));
}
function ShardHistoryModal({
  shard,
  history,
  onClose
}) {
  // Pull this shard's count from each day's history entry (history[i].shards[key])
  const series = (history || []).map(h => ({
    day: h.day,
    v: (h.shards || {})[shard.key]
  })).filter(p => p.v != null);
  const hasData = series.length >= 1;
  const values = series.map(p => p.v);
  const min = hasData ? Math.min(...values) : 0;
  const max = hasData ? Math.max(...values) : 0;
  // Chart dimensions
  const W = 560,
    H = 180,
    P = 28;
  const range = max - min || 1;
  const pts = series.map((p, i) => {
    const x = P + (series.length > 1 ? i * (W - 2 * P) / (series.length - 1) : (W - 2 * P) / 2);
    const y = H - P - (p.v - min) / range * (H - 2 * P);
    return [x, y, p.v, p.day];
  });
  const path = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');
  // Deltas between consecutive days (show biggest jumps)
  const jumps = series.slice(1).map((p, i) => ({
    day: p.day,
    delta: p.v - series[i].v
  })).filter(j => j.delta !== 0).sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta)).slice(0, 5);
  return /*#__PURE__*/React.createElement("div", {
    onClick: onClose,
    style: {
      position: 'fixed',
      inset: 0,
      background: 'rgba(0,0,0,0.55)',
      zIndex: 200,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    }
  }, /*#__PURE__*/React.createElement("div", {
    onClick: e => e.stopPropagation(),
    className: "card",
    style: {
      padding: 20,
      width: 640,
      maxWidth: '92vw',
      maxHeight: '88vh',
      overflow: 'auto',
      background: 'var(--bg-elev)',
      border: '1px solid var(--border-strong)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      marginBottom: 16
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: shard.icon,
    size: 40
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em'
    }
  }, shard.label, " shard"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 26,
      fontWeight: 600,
      color: shard.color
    },
    className: "num"
  }, shard.val != null ? shard.val : '—')), /*#__PURE__*/React.createElement("button", {
    className: "btn ghost",
    onClick: onClose,
    style: {
      height: 28,
      padding: '0 10px'
    }
  }, "Close")), !hasData && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 28,
      fontSize: 12,
      color: 'var(--text-dim)',
      textAlign: 'center'
    }
  }, "No history yet for this shard. Snapshots start recording now \u2014 come back tomorrow."), hasData && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("svg", {
    viewBox: `0 0 ${W} ${H + 20}`,
    width: "100%",
    height: H + 22,
    style: {
      display: 'block',
      marginBottom: 12
    }
  }, [0, 0.25, 0.5, 0.75, 1].map((t, i) => /*#__PURE__*/React.createElement("line", {
    key: i,
    x1: P,
    x2: W - P,
    y1: P + t * (H - 2 * P),
    y2: P + t * (H - 2 * P),
    stroke: "var(--border)",
    strokeDasharray: "2 4"
  })), /*#__PURE__*/React.createElement("path", {
    d: path + ` L${pts[pts.length - 1][0]},${H - P} L${pts[0][0]},${H - P} Z`,
    fill: shard.color,
    opacity: 0.12
  }), /*#__PURE__*/React.createElement("path", {
    d: path,
    fill: "none",
    stroke: shard.color,
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }), pts.map((p, i) => /*#__PURE__*/React.createElement("g", {
    key: i
  }, /*#__PURE__*/React.createElement("circle", {
    cx: p[0],
    cy: p[1],
    r: "3",
    fill: shard.color
  }), /*#__PURE__*/React.createElement("text", {
    x: p[0],
    y: H + 14,
    fontSize: "10",
    fill: "var(--text-dim)",
    textAnchor: "middle",
    fontFamily: "'JetBrains Mono', monospace"
  }, p[3]))), /*#__PURE__*/React.createElement("text", {
    x: P - 6,
    y: P + 4,
    fontSize: "10",
    fill: "var(--text-dim)",
    textAnchor: "end",
    fontFamily: "'JetBrains Mono', monospace"
  }, max), /*#__PURE__*/React.createElement("text", {
    x: P - 6,
    y: H - P + 4,
    fontSize: "10",
    fill: "var(--text-dim)",
    textAnchor: "end",
    fontFamily: "'JetBrains Mono', monospace"
  }, min)), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gap: 16
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "card-title",
    style: {
      marginBottom: 6
    }
  }, "Stats"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      lineHeight: 1.8,
      color: 'var(--text-sub)'
    }
  }, /*#__PURE__*/React.createElement("div", null, "Data points \xB7 ", /*#__PURE__*/React.createElement("span", {
    className: "mono"
  }, series.length)), /*#__PURE__*/React.createElement("div", null, "Min / Max \xB7 ", /*#__PURE__*/React.createElement("span", {
    className: "mono"
  }, min, " / ", max)), /*#__PURE__*/React.createElement("div", null, "Latest \xB7 ", /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: shard.color
    }
  }, series[series.length - 1].v)))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "card-title",
    style: {
      marginBottom: 6
    }
  }, "Biggest changes"), jumps.length === 0 ? /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11.5,
      color: 'var(--text-dim)'
    }
  }, "No day-over-day changes yet.") : /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      lineHeight: 1.8
    },
    className: "mono"
  }, jumps.map(j => /*#__PURE__*/React.createElement("div", {
    key: j.day,
    style: {
      display: 'flex',
      justifyContent: 'space-between'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-dim)'
    }
  }, j.day), /*#__PURE__*/React.createElement("span", {
    style: {
      color: j.delta > 0 ? 'var(--ok)' : 'var(--danger)'
    }
  }, j.delta > 0 ? '+' : '', j.delta)))))))));
}
function PageCB({
  s
}) {
  const avg = s.cb.history.reduce((a, h) => a + h.dmg, 0) / s.cb.history.length;
  const lr = s.cb.last_run;
  const team = s.cb.team;
  const totalDealt = team.reduce((a, t) => a + t.dmg_dealt, 0);
  const totalTaken = team.reduce((a, t) => a + t.dmg_taken, 0);
  const rarityColor = RARITY_COLORS;
  const [runDetailOpen, setRunDetailOpen] = React.useState(false);
  // CB reset countdown — fetched once, ticks per second.
  const [resetInfo, setResetInfo] = React.useState(null);
  const [resetTick, setResetTick] = React.useState(0);
  React.useEffect(() => {
    fetch('/api/cb-reset-info').then(r => r.json()).then(setResetInfo).catch(() => {});
    const id = setInterval(() => setResetTick(t => t + 1), 1000);
    return () => clearInterval(id);
  }, []);
  const secsUntilReset = resetInfo ? Math.max(0, resetInfo.seconds_until_reset - resetTick) : null;
  const fmtReset = s => {
    if (s == null) return '—';
    const h = Math.floor(s / 3600),
      m = Math.floor(s % 3600 / 60),
      sec = s % 60;
    return `${h}h ${String(m).padStart(2, '0')}m ${String(sec).padStart(2, '0')}s`;
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 340px',
      gap: 10,
      minHeight: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 18,
      gridColumn: '1 / -1'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'flex-start',
      marginBottom: 14
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em'
    }
  }, "Clan boss"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 22,
      fontWeight: 500,
      marginTop: 4,
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, s.cb.difficulty, " \xB7 ", /*#__PURE__*/React.createElement(AffinityIcon, {
    element: s.cb.affinity,
    size: 20
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-sub)'
    }
  }, s.cb.affinity, " affinity")), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: 'var(--text-dim)',
      marginTop: 4
    },
    className: "mono"
  }, s.cb.clan, " \xB7 boss HP ", (s.cb.boss_hp / 1e6).toFixed(0), "M")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(4, auto)',
      gap: 22,
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em'
    }
  }, "Today"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 24,
      fontWeight: 600
    },
    className: "num"
  }, s.cb.damage_today ? (s.cb.damage_today / 1e6).toFixed(1) + 'M' : '—')), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em'
    }
  }, "7-day avg"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 24,
      fontWeight: 600
    },
    className: "num"
  }, (avg / 1e6).toFixed(1), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 12,
      color: 'var(--text-sub)',
      fontWeight: 400
    }
  }, "M"))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em'
    }
  }, "Keys"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 24,
      fontWeight: 600,
      color: s.resources.cb_keys > 0 ? 'var(--accent)' : 'var(--text-dim)'
    },
    className: "num"
  }, s.resources.cb_keys, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 12,
      color: 'var(--text-sub)',
      fontWeight: 400
    }
  }, "/2"))), /*#__PURE__*/React.createElement("div", {
    title: resetInfo ? `Resets at ${resetInfo.reset_hour_utc}:00 UTC` : ''
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em'
    }
  }, "Next reset"), /*#__PURE__*/React.createElement("div", {
    className: "num mono",
    style: {
      fontSize: 18,
      fontWeight: 600,
      color: secsUntilReset != null && secsUntilReset < 3600 ? 'var(--accent)' : 'var(--text)',
      letterSpacing: '-0.02em'
    }
  }, fmtReset(secsUntilReset)))))), /*#__PURE__*/React.createElement("div", {
    className: "card",
    onClick: () => setRunDetailOpen(true),
    style: {
      padding: 0,
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      cursor: 'pointer'
    },
    title: "Click for turn-by-turn detail"
  }, /*#__PURE__*/React.createElement(PanelHeader, {
    title: "team composition \xB7 last run",
    right: `${team.length} heroes · ${lr.turns_total || 0} turns · click for detail →`
  }), (() => {
    // Shared column template — applied to header, body rows, and total row
    // so everything aligns to the same grid. Numeric columns are right-
    // aligned; the preset index and hero name are left-aligned.
    const cols = '28px minmax(0, 1.8fr) 96px 56px 56px 96px 96px 52px';
    const numR = {
      textAlign: 'right'
    };
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: cols,
        padding: '8px 16px',
        fontSize: 10.5,
        color: 'var(--text-dim)',
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
        borderBottom: '1px solid var(--border)',
        background: 'var(--bg-subtle)',
        columnGap: 10,
        alignItems: 'center'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: numR
    }, "#"), /*#__PURE__*/React.createElement("span", null, "Hero"), /*#__PURE__*/React.createElement("span", null, "Role"), /*#__PURE__*/React.createElement("span", {
      style: numR
    }, "SPD"), /*#__PURE__*/React.createElement("span", {
      style: numR
    }, "Turns"), /*#__PURE__*/React.createElement("span", {
      style: numR
    }, "Dmg dealt"), /*#__PURE__*/React.createElement("span", {
      style: numR
    }, "Dmg taken"), /*#__PURE__*/React.createElement("span", {
      style: numR
    }, "Ctr")), /*#__PURE__*/React.createElement("div", null, team.map((h, i) => {
      const slot = h.preset_slot || i + 1;
      return /*#__PURE__*/React.createElement("div", {
        key: h.name,
        style: {
          padding: '10px 16px',
          borderBottom: '1px solid var(--border)'
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'grid',
          gridTemplateColumns: cols,
          alignItems: 'center',
          fontSize: 12,
          columnGap: 10
        }
      }, /*#__PURE__*/React.createElement("span", {
        className: "mono",
        style: {
          ...numR,
          color: 'var(--text-dim)',
          fontSize: 11
        }
      }, slot), /*#__PURE__*/React.createElement("div", {
        style: {
          minWidth: 0,
          display: 'flex',
          alignItems: 'center',
          gap: 8
        }
      }, /*#__PURE__*/React.createElement(HeroPortrait, {
        typeId: h.type_id,
        size: 32,
        rarity: {
          Common: 1,
          Uncommon: 2,
          Rare: 3,
          Epic: 4,
          Legendary: 5
        }[h.rarity] || 0,
        name: h.name
      }), /*#__PURE__*/React.createElement("div", {
        style: {
          minWidth: 0
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          fontWeight: 500,
          display: 'flex',
          alignItems: 'center',
          gap: 6
        }
      }, i === 0 && /*#__PURE__*/React.createElement("span", {
        style: {
          fontSize: 9,
          color: 'var(--accent)',
          border: '1px solid var(--accent)',
          padding: '1px 4px',
          borderRadius: 3
        }
      }, "LEAD"), /*#__PURE__*/React.createElement("span", {
        className: "truncate"
      }, h.name)), /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 10.5,
          color: rarityColor[h.rarity],
          marginTop: 2,
          display: 'flex',
          alignItems: 'center',
          gap: 4
        }
      }, /*#__PURE__*/React.createElement(AffinityIcon, {
        element: h.element,
        size: 11
      }), /*#__PURE__*/React.createElement("span", null, h.rarity, " \xB7 ", h.faction)))), /*#__PURE__*/React.createElement("span", {
        style: {
          color: 'var(--text-sub)',
          fontSize: 11.5
        },
        className: "truncate"
      }, h.role), /*#__PURE__*/React.createElement("span", {
        className: "mono",
        style: {
          ...numR,
          color: 'var(--text-sub)'
        }
      }, h.spd), /*#__PURE__*/React.createElement("span", {
        className: "mono",
        style: {
          ...numR,
          color: 'var(--text-sub)'
        }
      }, h.turns), /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'stretch',
          width: '100%'
        }
      }, /*#__PURE__*/React.createElement("div", {
        className: "mono num",
        style: {
          textAlign: 'right'
        }
      }, (h.dmg_dealt / 1e6).toFixed(2), "M"), /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'block',
          width: '100%',
          height: 4,
          background: 'var(--bg-subtle)',
          borderRadius: 2,
          marginTop: 4,
          overflow: 'hidden'
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          width: `${Math.min(100, h.dmg_dealt / totalDealt * 100)}%`,
          height: '100%',
          background: 'var(--accent)'
        }
      }))), /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'stretch',
          width: '100%'
        }
      }, /*#__PURE__*/React.createElement("div", {
        className: "mono num",
        style: {
          color: 'var(--text-sub)',
          textAlign: 'right'
        }
      }, (h.dmg_taken / 1e6).toFixed(2), "M"), /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'block',
          width: '100%',
          height: 4,
          background: 'var(--bg-subtle)',
          borderRadius: 2,
          marginTop: 4,
          overflow: 'hidden'
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          width: `${Math.min(100, h.dmg_taken / totalTaken * 100)}%`,
          height: '100%',
          background: 'oklch(0.70 0.18 25)'
        }
      }))), /*#__PURE__*/React.createElement("span", {
        className: "mono",
        style: {
          ...numR,
          color: h.counters > 0 ? 'var(--violet)' : 'var(--text-dim)'
        }
      }, h.counters || '—')));
    }), (() => {
      // Authoritative boss damage from battle log (lr.damage). Always
      // >= the sum of attributed per-hero damage — the gap is DoT
      // ticks / counter damage not tied to a specific hero slot.
      const runDmg = lr.damage || totalDealt;
      const unattributed = Math.max(0, runDmg - totalDealt);
      const attrNote = unattributed > 0 ? ` (${(totalDealt / 1e6).toFixed(2)}M attributed + ${(unattributed / 1e6).toFixed(2)}M DoT/other)` : '';
      return /*#__PURE__*/React.createElement("div", {
        style: {
          padding: '8px 16px',
          display: 'grid',
          gridTemplateColumns: cols,
          fontSize: 11,
          color: 'var(--text-dim)',
          background: 'var(--bg-subtle)',
          columnGap: 10,
          alignItems: 'center'
        },
        title: unattributed > 0 ? `Per-hero sum ${(totalDealt / 1e6).toFixed(2)}M plus ${(unattributed / 1e6).toFixed(2)}M of DoT ticks & other unattributed damage = run total ${(runDmg / 1e6).toFixed(2)}M` : undefined
      }, /*#__PURE__*/React.createElement("span", null), /*#__PURE__*/React.createElement("span", null, "Total", attrNote), /*#__PURE__*/React.createElement("span", null), /*#__PURE__*/React.createElement("span", null), /*#__PURE__*/React.createElement("span", {
        className: "mono",
        style: numR
      }, team.reduce((a, t) => a + t.turns, 0)), /*#__PURE__*/React.createElement("span", {
        className: "mono num",
        style: {
          ...numR,
          color: 'var(--accent)'
        }
      }, (runDmg / 1e6).toFixed(2), "M"), /*#__PURE__*/React.createElement("span", {
        className: "mono num",
        style: {
          ...numR,
          color: 'oklch(0.70 0.18 25)'
        }
      }, (totalTaken / 1e6).toFixed(2), "M"), /*#__PURE__*/React.createElement("span", {
        className: "mono",
        style: {
          ...numR,
          color: 'var(--violet)'
        }
      }, team.reduce((a, t) => a + t.counters, 0)));
    })()));
  })()), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateRows: 'auto auto auto',
      gap: 10
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-title",
    style: {
      marginBottom: 10
    }
  }, "Run stats"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gap: 10,
      fontSize: 12
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase'
    }
  }, "Duration"), /*#__PURE__*/React.createElement("div", {
    className: "mono num",
    style: {
      fontSize: 15,
      marginTop: 2
    }
  }, lr.duration_s ? `${Math.floor(lr.duration_s / 60)}:${String(lr.duration_s % 60).padStart(2, '0')}` : '—')), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase'
    }
  }, "Turns"), /*#__PURE__*/React.createElement("div", {
    className: "mono num",
    style: {
      fontSize: 15,
      marginTop: 2
    }
  }, lr.turns_total)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase'
    }
  }, "Damage"), /*#__PURE__*/React.createElement("div", {
    className: "mono num",
    style: {
      fontSize: 15,
      marginTop: 2,
      color: 'var(--accent)'
    }
  }, (lr.damage / 1e6).toFixed(2), "M")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase'
    }
  }, "Dmg taken"), /*#__PURE__*/React.createElement("div", {
    className: "mono num",
    style: {
      fontSize: 15,
      marginTop: 2,
      color: 'oklch(0.70 0.18 25)'
    }
  }, (lr.damage_taken / 1e6).toFixed(2), "M")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase'
    }
  }, "Unkillable"), /*#__PURE__*/React.createElement("div", {
    className: "mono num",
    style: {
      fontSize: 15,
      marginTop: 2
    }
  }, lr.unkillable_triggers, "\xD7")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase'
    }
  }, "Counters"), /*#__PURE__*/React.createElement("div", {
    className: "mono num",
    style: {
      fontSize: 15,
      marginTop: 2,
      color: 'var(--violet)'
    }
  }, lr.counters_total, "\xD7")))), /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-title",
    style: {
      marginBottom: 10
    }
  }, "Debuffs applied"), Object.entries(lr.debuffs_applied).map(([d, n]) => {
    const max = Math.max(...Object.values(lr.debuffs_applied));
    return /*#__PURE__*/React.createElement("div", {
      key: d,
      style: {
        marginBottom: 7
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        justifyContent: 'space-between',
        fontSize: 11.5,
        marginBottom: 3
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        color: 'var(--text-sub)'
      }
    }, d), /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        color: 'var(--text)'
      }
    }, n, "\xD7")), /*#__PURE__*/React.createElement("div", {
      style: {
        height: 3,
        background: 'var(--bg-subtle)',
        borderRadius: 2,
        overflow: 'hidden'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        width: `${n / max * 100}%`,
        height: '100%',
        background: 'var(--violet)'
      }
    })));
  })), /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 0,
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column'
    }
  }, /*#__PURE__*/React.createElement(PanelHeader, {
    title: "boss turns",
    right: `${(lr.turn_log || []).length} of 50 · ${s.cb.difficulty || ''}`
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '4px 0',
      maxHeight: 360,
      overflowY: 'auto'
    }
  }, (() => {
    const tl = lr.turn_log || [];
    if (!tl.length) {
      return /*#__PURE__*/React.createElement("div", {
        style: {
          padding: '10px 14px',
          fontSize: 11.5,
          color: 'var(--text-dim)'
        }
      }, "No turn-by-turn log captured for this run.");
    }
    const maxDmg = Math.max(1, ...tl.map(t => t.damage || 0));
    const actionColor = {
      AOE1: 'oklch(0.70 0.18 25)',
      AOE2: 'oklch(0.70 0.18 25)',
      STUN: 'var(--violet)'
    };
    return tl.map((t, i) => {
      const prot = t.protection || {};
      const heroes = Object.keys(prot);
      const naked = heroes.filter(h => !(prot[h].uk || prot[h].bd || prot[h].sh));
      const dmgPct = (t.damage || 0) / maxDmg * 100;
      return /*#__PURE__*/React.createElement("div", {
        key: i,
        style: {
          display: 'grid',
          gridTemplateColumns: '42px 56px 1fr 80px',
          gap: 8,
          padding: '4px 14px',
          fontSize: 11.5,
          alignItems: 'center',
          borderBottom: i < tl.length - 1 ? '1px solid var(--border)' : 'none'
        }
      }, /*#__PURE__*/React.createElement("span", {
        className: "mono",
        style: {
          color: 'var(--text-dim)',
          fontSize: 10.5
        }
      }, "bt ", t.boss_turn), /*#__PURE__*/React.createElement("span", {
        className: "mono",
        style: {
          fontSize: 10,
          color: actionColor[t.boss_action] || 'var(--text-sub)',
          fontWeight: 500
        }
      }, t.boss_action || '—'), /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'flex',
          flexDirection: 'column',
          gap: 2
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          height: 3,
          background: 'var(--bg-subtle)',
          borderRadius: 2,
          overflow: 'hidden'
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          width: `${dmgPct}%`,
          height: '100%',
          background: 'var(--accent)'
        }
      })), heroes.length > 0 && /*#__PURE__*/React.createElement("span", {
        className: "mono",
        style: {
          fontSize: 9.5,
          color: naked.length ? 'var(--danger)' : 'var(--text-dim)'
        }
      }, heroes.map(h => {
        const p = prot[h];
        if (p.uk) return 'U';
        if (p.bd) return 'B';
        if (p.sh) return 'S';
        return '·';
      }).join(''), naked.length > 0 && ` · ${naked.length} naked`)), /*#__PURE__*/React.createElement("span", {
        className: "mono num",
        style: {
          textAlign: 'right',
          color: 'var(--accent)'
        }
      }, ((t.damage || 0) / 1e6).toFixed(2), "M"));
    });
  })()), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '6px 14px',
      fontSize: 9.5,
      color: 'var(--text-dim)',
      borderTop: '1px solid var(--border)',
      background: 'var(--bg-subtle)'
    },
    className: "mono"
  }, "U=unkillable \xB7 B=block-dmg \xB7 S=shield \xB7 \xB7=naked"))), runDetailOpen && /*#__PURE__*/React.createElement(CBRunDetailModal, {
    s: s,
    lr: lr,
    team: team,
    totalDealt: totalDealt,
    totalTaken: totalTaken,
    rarityColor: rarityColor,
    onClose: () => setRunDetailOpen(false)
  }), /*#__PURE__*/React.createElement(CBTuneLab, null), /*#__PURE__*/React.createElement(CBHistoryPanel, {
    history: s.cb.history,
    perKey: s.cb.per_key_history
  }));
}
const RARITY_NAMES_BY_ID = {
  1: 'Common',
  2: 'Uncommon',
  3: 'Rare',
  4: 'Epic',
  5: 'Legendary',
  6: 'Mythical'
};
// Palette mirrors Raid's shard colors: legendary=gold (ancient shard), epic=pink/purple (void),
// rare=blue (ancient frame), uncommon=green, mythical=red (primal).
const RARITY_COLORS = {
  Common: 'var(--text-sub)',
  Uncommon: 'oklch(0.72 0.17 145)',
  // green
  Rare: 'oklch(0.68 0.18 250)',
  // blue
  Epic: 'oklch(0.68 0.22 315)',
  // pink/purple
  Legendary: 'oklch(0.80 0.16 85)',
  // gold
  Mythical: 'oklch(0.64 0.24 20)' // red
};

/* ===================== Dungeons ===================== */

const DUNGEON_OPTIONS = [{
  id: 'dragon',
  label: "Dragon's Lair"
}, {
  id: 'spider',
  label: "Spider's Den"
}, {
  id: 'fire_knight',
  label: 'Fire Knight Castle'
}, {
  id: 'ice_golem',
  label: 'Ice Golem Peak'
}, {
  id: 'minotaur',
  label: "Minotaur's Labyrinth"
}, {
  id: 'void_keep',
  label: 'Void Keep'
}, {
  id: 'spirit_keep',
  label: 'Spirit Keep'
}, {
  id: 'magic_keep',
  label: 'Magic Keep'
}, {
  id: 'force_keep',
  label: 'Force Keep'
}, {
  id: 'arcane_keep',
  label: 'Arcane Keep'
}];
function PageDungeons({
  s
}) {
  const [dungeon, setDungeon] = React.useState('minotaur');
  const [stageMode, setStageMode] = React.useState('max'); // 'max' | 'fixed'
  const [stageNum, setStageNum] = React.useState(15);
  const [stopType, setStopType] = React.useState('capped'); // 'capped' | 'runs'
  const [runsN, setRunsN] = React.useState(10);
  const [state, setState] = React.useState(null);
  const [errorMsg, setErrorMsg] = React.useState('');
  // Local UI states for immediate button feedback during the gap between
  // click and the next poll (~1s). Cleared once the polled state confirms.
  const [starting, setStarting] = React.useState(false);
  const [stopping, setStopping] = React.useState(false);

  // Poll backend state
  React.useEffect(() => {
    let alive = true;
    async function poll() {
      try {
        const r = await fetch('/api/dungeons/state', {
          cache: 'no-store'
        });
        if (r.ok && alive) setState(await r.json());
      } catch (e) {}
    }
    poll();
    const id = setInterval(poll, 1000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);
  const running = state && state.running;
  // Once the backend confirms running/idle, drop the transient local flag.
  React.useEffect(() => {
    if (running && starting) setStarting(false);
    if (!running && stopping) setStopping(false);
  }, [running, starting, stopping]);
  const completed = state ? state.completed || 0 : 0;
  const failures = state ? state.failures || 0 : 0;
  const target = state ? state.target : null;
  const startedAt = state ? state.started_at : null;
  const elapsedRun = startedAt && running ? Math.floor(Date.now() / 1000 - startedAt) : null;
  const energyUsed = state && state.energy_start != null && state.energy_now != null ? Math.max(0, state.energy_start - state.energy_now) : null;
  const silverEarned = state && state.silver_start != null && state.silver_now != null ? Math.max(0, state.silver_now - state.silver_start) : null;

  // Cap stop is minotaur-only — auto-switch to runs if user picks another dungeon.
  const stopTypeEffective = dungeon !== 'minotaur' && stopType === 'capped' ? 'runs' : stopType;
  async function start() {
    setErrorMsg('');
    setStarting(true);
    const stage = stageMode === 'max' ? 'max' : Number(stageNum);
    const stop_condition = stopTypeEffective === 'capped' ? {
      type: 'capped'
    } : {
      type: 'runs',
      n: Math.max(1, Number(runsN))
    };
    try {
      const r = await fetch('/api/dungeons/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          dungeon,
          stage,
          stop_condition
        })
      });
      const d = await r.json();
      if (!d.ok) {
        setErrorMsg(d.message || 'failed to start');
        setStarting(false);
      }
      // On success, leave starting=true; the running-state effect will clear
      // it as soon as the next poll confirms the loop is live.
    } catch (e) {
      setErrorMsg(String(e));
      setStarting(false);
    }
  }
  async function stop() {
    setErrorMsg('');
    setStopping(true);
    try {
      await fetch('/api/dungeons/run', {
        method: 'DELETE'
      });
    } catch (e) {
      setErrorMsg(String(e));
      setStopping(false);
    }
  }
  const fmtSec = sec => {
    if (sec == null) return '—';
    const m = Math.floor(sec / 60),
      s = sec % 60;
    return m > 0 ? `${m}m${String(s).padStart(2, '0')}s` : `${s}s`;
  };
  const dungeonLabel = (DUNGEON_OPTIONS.find(d => d.id === (state && state.dungeon)) || {
    label: '—'
  }).label;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gap: 12,
      gridTemplateColumns: '380px 1fr',
      alignItems: 'start'
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 0,
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement(PanelHeader, {
    title: "dungeon loop",
    right: running ? /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        color: 'var(--accent)'
      }
    }, "RUNNING") : null
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 12,
      display: 'grid',
      gap: 10
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("label", {
    style: lbl
  }, "Dungeon"), /*#__PURE__*/React.createElement("select", {
    disabled: running,
    value: dungeon,
    onChange: e => setDungeon(e.target.value),
    style: sel
  }, DUNGEON_OPTIONS.map(d => /*#__PURE__*/React.createElement("option", {
    key: d.id,
    value: d.id
  }, d.label)))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("label", {
    style: lbl
  }, "Stage"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 6
    }
  }, /*#__PURE__*/React.createElement("select", {
    disabled: running,
    value: stageMode,
    onChange: e => setStageMode(e.target.value),
    style: {
      ...sel,
      flex: '0 0 140px'
    }
  }, /*#__PURE__*/React.createElement("option", {
    value: "max"
  }, "Max visible"), /*#__PURE__*/React.createElement("option", {
    value: "fixed"
  }, "Specific stage")), stageMode === 'fixed' && /*#__PURE__*/React.createElement("select", {
    disabled: running,
    value: stageNum,
    onChange: e => setStageNum(Number(e.target.value)),
    style: sel
  }, Array.from({
    length: 25
  }, (_, i) => i + 1).map(n => /*#__PURE__*/React.createElement("option", {
    key: n,
    value: n
  }, "Stage ", n))))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("label", {
    style: lbl
  }, "Stop condition"), /*#__PURE__*/React.createElement("select", {
    disabled: running,
    value: stopTypeEffective,
    onChange: e => setStopType(e.target.value),
    style: sel
  }, /*#__PURE__*/React.createElement("option", {
    value: "capped",
    disabled: dungeon !== 'minotaur'
  }, "All heroes scroll-capped ", dungeon !== 'minotaur' ? '(minotaur only)' : ''), /*#__PURE__*/React.createElement("option", {
    value: "runs"
  }, "Number of runs"))), stopTypeEffective === 'runs' && /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("label", {
    style: lbl
  }, "Runs"), /*#__PURE__*/React.createElement("input", {
    type: "number",
    min: "1",
    max: "9999",
    disabled: running,
    value: runsN,
    onChange: e => setRunsN(e.target.value),
    style: sel
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 8,
      marginTop: 4
    }
  }, starting ? /*#__PURE__*/React.createElement("button", {
    className: "btn primary",
    disabled: true,
    style: {
      flex: 1,
      height: 30,
      justifyContent: 'center'
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "dungeon-spinner",
    style: {
      width: 12,
      height: 12,
      borderWidth: 2,
      borderTopColor: '#0b0d10',
      borderRightColor: 'transparent',
      borderBottomColor: 'rgba(11,13,16,0.4)',
      borderLeftColor: 'rgba(11,13,16,0.4)',
      marginRight: 8
    }
  }), "Starting...") : stopping ? /*#__PURE__*/React.createElement("button", {
    className: "btn",
    disabled: true,
    style: {
      flex: 1,
      height: 30,
      justifyContent: 'center'
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "dungeon-spinner",
    style: {
      width: 12,
      height: 12,
      borderWidth: 2,
      marginRight: 8
    }
  }), "Stopping (current battle finishes)...") : !running ? /*#__PURE__*/React.createElement("button", {
    className: "btn primary",
    onClick: start,
    style: {
      flex: 1,
      height: 30
    }
  }, /*#__PURE__*/React.createElement(SvgIcon.play, null), " Start loop") : /*#__PURE__*/React.createElement("button", {
    className: "btn",
    onClick: stop,
    style: {
      flex: 1,
      height: 30
    }
  }, /*#__PURE__*/React.createElement(SvgIcon.pause, null), " Stop")), errorMsg && /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 11,
      color: '#e07a5f'
    }
  }, errorMsg))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement(DungeonTeamPanel, {
    s: s,
    team: state && state.team,
    running: running
  }), /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 0,
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement(PanelHeader, {
    title: "status",
    right: state && state.last_status ? /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        color: 'var(--text-dim)'
      }
    }, "last: ", state.last_status) : null
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 16,
      display: 'grid',
      gridTemplateColumns: 'repeat(4, 1fr)',
      gap: 14
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: statLbl
  }, "Dungeon"), /*#__PURE__*/React.createElement("div", {
    style: statVal
  }, state && state.dungeon ? dungeonLabel : '—')), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: statLbl
  }, "Stage"), /*#__PURE__*/React.createElement("div", {
    style: statVal
  }, state && state.stage != null ? state.stage : '—')), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: statLbl
  }, "Progress"), /*#__PURE__*/React.createElement("div", {
    style: statVal
  }, target != null ? `${completed}/${target}` : running ? `${completed} (capped)` : completed || '—')), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: statLbl
  }, "Elapsed"), /*#__PURE__*/React.createElement("div", {
    style: statVal
  }, fmtSec(elapsedRun))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: statLbl
  }, "Energy used"), /*#__PURE__*/React.createElement("div", {
    style: statVal
  }, energyUsed != null ? energyUsed.toLocaleString() : '—')), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: statLbl
  }, "Silver earned"), /*#__PURE__*/React.createElement("div", {
    style: statVal
  }, silverEarned != null ? silverEarned.toLocaleString() : '—')), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: statLbl
  }, "Failures"), /*#__PURE__*/React.createElement("div", {
    style: statVal
  }, failures || '—')), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: statLbl
  }, "Last battle"), /*#__PURE__*/React.createElement("div", {
    style: statVal
  }, state && state.last_elapsed_s != null ? `${state.last_elapsed_s}s` : '—'))), running && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '10px 16px',
      borderTop: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      gap: 10
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "dungeon-spinner"
  }), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 11,
      color: 'var(--text-sub)'
    }
  }, state.last_status === 'victory' ? 'Replaying...' : 'Battle in progress...')), !running && state && state.result_reason && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '10px 16px',
      borderTop: '1px solid var(--border)',
      fontSize: 11,
      color: 'var(--text-sub)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "mono"
  }, "last result: ", state.result_reason), state.result_reason === 'capped' && completed > 0 && /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      marginLeft: 8,
      color: 'var(--accent)'
    }
  }, completed, " successful run", completed === 1 ? '' : 's')))));
}
function DungeonTeamPanel({
  s,
  team,
  running
}) {
  // team is a list of type_ids (length up to 5). Look up names + meta from
  // s.heroes (already populated by /api/state). Always show 5 slots so the
  // shape is constant before/after data arrives.
  const heroes = Array.isArray(s.heroes) ? s.heroes : [];
  const byType = new Map();
  for (const h of heroes) {
    if (h.type_id != null) byType.set(h.type_id, h);
  }
  const tids = Array.isArray(team) ? team.slice(0, 5) : [];
  while (tids.length < 5) tids.push(null);
  const status = !team || team.length === 0 ? running ? 'detecting team...' : 'team detected once a battle starts' : `${team.length} hero${team.length === 1 ? '' : 'es'} in active team`;
  return /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 0,
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement(PanelHeader, {
    title: "active team",
    right: /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        fontSize: 10.5,
        color: 'var(--text-dim)'
      }
    }, status)
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 14,
      display: 'grid',
      gridTemplateColumns: 'repeat(5, 1fr)',
      gap: 10
    }
  }, tids.map((tid, i) => /*#__PURE__*/React.createElement(DungeonTeamSlot, {
    key: i,
    idx: i,
    hero: tid != null ? byType.get(tid) : null,
    tid: tid
  }))));
}
function DungeonTeamSlot({
  idx,
  hero,
  tid
}) {
  if (!hero) {
    return /*#__PURE__*/React.createElement("div", {
      style: {
        border: '1px dashed var(--border-strong)',
        borderRadius: 6,
        padding: '10px 8px',
        minHeight: 88,
        textAlign: 'center',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--text-dim)',
        fontSize: 11
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 18,
        color: 'var(--border-strong)',
        marginBottom: 2
      }
    }, idx + 1), /*#__PURE__*/React.createElement("div", {
      className: "mono",
      style: {
        fontSize: 10
      }
    }, tid != null ? `#${tid}` : 'empty slot'));
  }
  const rarityColor = typeof RARITY_COLORS !== 'undefined' && RARITY_COLORS[hero.rarity] || 'var(--accent)';
  return /*#__PURE__*/React.createElement("div", {
    style: {
      border: `1px solid ${rarityColor}`,
      borderRadius: 6,
      padding: '8px 8px 10px',
      background: 'var(--bg-elev)',
      display: 'flex',
      flexDirection: 'column',
      gap: 4
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 10,
      color: 'var(--text-dim)'
    }
  }, "slot ", idx + 1), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 10,
      color: rarityColor
    }
  }, hero.rarity || '')), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      minHeight: 48
    }
  }, /*#__PURE__*/React.createElement(HeroPortrait, {
    typeId: hero.type_id,
    size: 42,
    rarity: {
      Common: 1,
      Uncommon: 2,
      Rare: 3,
      Epic: 4,
      Legendary: 5
    }[hero.rarity] || 0,
    name: hero.name
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      minWidth: 0,
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      fontWeight: 600,
      lineHeight: 1.2,
      color: 'var(--text)'
    }
  }, hero.name), /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 10.5,
      color: 'var(--text-sub)',
      display: 'flex',
      alignItems: 'center',
      gap: 5,
      flexWrap: 'wrap',
      marginTop: 2
    }
  }, /*#__PURE__*/React.createElement(AffinityIcon, {
    element: hero.element,
    size: 11
  }), /*#__PURE__*/React.createElement("span", null, '★'.repeat(Math.min(6, hero.stars || 0))), /*#__PURE__*/React.createElement("span", null, "L", hero.level || '?'), hero.empower ? /*#__PURE__*/React.createElement("span", null, "+", hero.empower) : null))));
}
const lbl = {
  display: 'block',
  fontSize: 10.5,
  color: 'var(--text-dim)',
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
  marginBottom: 4,
  fontWeight: 600
};
const sel = {
  width: '100%',
  height: 28,
  padding: '0 8px',
  background: 'var(--bg-elev)',
  color: 'var(--text)',
  border: '1px solid var(--border-strong)',
  borderRadius: 4,
  fontSize: 12,
  fontFamily: 'inherit'
};
const statLbl = {
  fontSize: 10.5,
  color: 'var(--text-dim)',
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
  marginBottom: 4
};
const statVal = {
  fontSize: 16,
  fontWeight: 600,
  color: 'var(--text)',
  fontFamily: "'JetBrains Mono', monospace"
};
function PageHeroes({
  s
}) {
  const [tab, setTab] = React.useState('heroes');
  const [heroFilter, setHeroFilter] = React.useState('all');
  const [heroWhere, setHeroWhere] = React.useState('all'); // all | active | vault
  const [artSlotFilter, setArtSlotFilter] = React.useState('all');
  const [artRarityFilter, setArtRarityFilter] = React.useState('all');
  const [artSetFilter, setArtSetFilter] = React.useState('all');
  const [artPrimaryFilter, setArtPrimaryFilter] = React.useState('all');
  const [artSubFilter, setArtSubFilter] = React.useState('all');
  const [artMinRank, setArtMinRank] = React.useState('all');
  const [artEquip, setArtEquip] = React.useState('all'); // all | equipped | vault
  // Gap-analysis tab state.
  const [gapData, setGapData] = React.useState(null);
  const [gapErr, setGapErr] = React.useState('');
  const [gapLoading, setGapLoading] = React.useState(false);
  const [gapThreshold, setGapThreshold] = React.useState(4.0);
  const [gapMinRarity, setGapMinRarity] = React.useState(4);
  const [gapTopN, setGapTopN] = React.useState(15);
  const fetchGaps = React.useCallback(async () => {
    setGapLoading(true);
    setGapErr('');
    try {
      const params = new URLSearchParams({
        threshold: String(gapThreshold),
        min_rarity: String(gapMinRarity),
        top: String(gapTopN)
      });
      const r = await fetch('/api/gear-gaps?' + params, {
        cache: 'no-store'
      });
      const j = await r.json();
      if (j.error) {
        setGapErr(j.error);
        setGapData(null);
      } else {
        setGapData(j);
      }
    } catch (e) {
      setGapErr(String(e));
    }
    setGapLoading(false);
  }, [gapThreshold, gapMinRarity, gapTopN]);
  React.useEffect(() => {
    if (tab === 'gaps') fetchGaps();
  }, [tab, fetchGaps]);
  const heroes = s.heroes.filter(h => (heroFilter === 'all' || h.rarity && h.rarity.toLowerCase() === heroFilter) && (heroWhere === 'all' || (heroWhere === 'vault' ? h.in_storage : !h.in_storage)));
  const vaultCount = s.heroes.filter(h => h.in_storage).length;
  const allArtifacts = s.artifacts || [];
  // Unique sets observed in inventory for the dropdown
  const sets = React.useMemo(() => {
    const m = new Map();
    for (const a of allArtifacts) if (a.set_name) m.set(a.set_name, (m.get(a.set_name) || 0) + 1);
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [allArtifacts]);
  const artifacts = allArtifacts.filter(a => (artSlotFilter === 'all' || String(a.slot_id) === artSlotFilter) && (artRarityFilter === 'all' || String(a.rarity) === artRarityFilter) && (artSetFilter === 'all' || a.set_name === artSetFilter) && (artPrimaryFilter === 'all' || a.primary_stat === artPrimaryFilter) && (artSubFilter === 'all' || (a.sub_stat_set || []).includes(artSubFilter)) && (artMinRank === 'all' || a.rank >= Number(artMinRank)) && (artEquip === 'all' || (artEquip === 'equipped' ? !!a.equipped_on : !a.equipped_on)));
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 340px',
      gap: 10,
      minHeight: '100%',
      maxHeight: '100%',
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 0,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '6px 6px 0',
      borderBottom: '1px solid var(--border)',
      display: 'flex',
      gap: 4,
      background: 'var(--bg-subtle)'
    }
  }, [['heroes', `Heroes · ${s.heroes.length}`], ['artifacts', `Artifacts · ${allArtifacts.length}`], ['gaps', 'Gaps']].map(([k, label]) => /*#__PURE__*/React.createElement("button", {
    key: k,
    onClick: () => setTab(k),
    style: {
      border: 0,
      background: tab === k ? 'var(--bg-elev)' : 'transparent',
      color: tab === k ? 'var(--text)' : 'var(--text-sub)',
      padding: '7px 14px',
      fontSize: 12,
      fontWeight: tab === k ? 500 : 400,
      cursor: 'pointer',
      borderRadius: '6px 6px 0 0',
      borderBottom: tab === k ? '2px solid var(--accent)' : '2px solid transparent',
      marginBottom: -1
    }
  }, label))), tab === 'heroes' && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '8px 12px',
      borderBottom: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      flexWrap: 'wrap'
    }
  }, /*#__PURE__*/React.createElement("label", {
    style: filterLbl
  }, "where"), /*#__PURE__*/React.createElement("select", {
    value: heroWhere,
    onChange: e => setHeroWhere(e.target.value),
    style: filterSel
  }, /*#__PURE__*/React.createElement("option", {
    value: "all"
  }, "all (", s.heroes.length, ")"), /*#__PURE__*/React.createElement("option", {
    value: "active"
  }, "active (", s.heroes.length - vaultCount, ")"), /*#__PURE__*/React.createElement("option", {
    value: "vault"
  }, "vault (", vaultCount, ")")), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }), ['all', 'legendary', 'epic', 'rare'].map(f => /*#__PURE__*/React.createElement("button", {
    key: f,
    className: "btn",
    onClick: () => setHeroFilter(f),
    style: {
      height: 22,
      padding: '0 8px',
      fontSize: 11,
      background: heroFilter === f ? 'var(--bg-hover)' : 'transparent',
      borderColor: heroFilter === f ? 'var(--accent)' : 'var(--border)'
    }
  }, f))), /*#__PURE__*/React.createElement("div", {
    className: "scroll",
    style: {
      flex: 1,
      overflowY: 'auto'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '36px 1.4fr 100px 80px 70px 56px 80px 76px 56px 56px',
      gap: 6,
      padding: '8px 16px',
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      borderBottom: '1px solid var(--border)',
      background: 'var(--bg-subtle)'
    }
  }, /*#__PURE__*/React.createElement("span", null), /*#__PURE__*/React.createElement("span", null, "Name"), /*#__PURE__*/React.createElement("span", null, "Faction"), /*#__PURE__*/React.createElement("span", null, "Rarity"), /*#__PURE__*/React.createElement("span", null, "Lv / \u2605"), /*#__PURE__*/React.createElement("span", null, "Emp"), /*#__PURE__*/React.createElement("span", null, "Skills"), /*#__PURE__*/React.createElement("span", null, "Masteries"), /*#__PURE__*/React.createElement("span", null, "Bless"), /*#__PURE__*/React.createElement("span", null, "Gear")), heroes.map((h, i) => {
    const mtrees = h.mastery_trees || [0, 0, 0];
    const mtotal = h.mastery_count || mtrees.reduce((a, b) => a + b, 0);
    const mComplete = mtotal >= 15;
    return /*#__PURE__*/React.createElement("div", {
      key: (h.id || h.name) + '-' + i,
      style: {
        display: 'grid',
        gridTemplateColumns: '36px 1.4fr 100px 80px 70px 56px 80px 76px 56px 56px',
        gap: 6,
        padding: '7px 16px',
        fontSize: 12,
        borderBottom: '1px solid var(--border)',
        alignItems: 'center'
      }
    }, /*#__PURE__*/React.createElement(HeroPortrait, {
      typeId: h.type_id,
      size: 32,
      rarity: {
        Common: 1,
        Uncommon: 2,
        Rare: 3,
        Epic: 4,
        Legendary: 5
      }[h.rarity] || 0,
      name: h.name
    }), /*#__PURE__*/React.createElement("div", {
      style: {
        minWidth: 0
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontWeight: 500,
        display: 'flex',
        alignItems: 'center',
        gap: 6
      }
    }, h.in_storage && /*#__PURE__*/React.createElement("span", {
      title: "Vaulted",
      style: {
        fontSize: 9,
        padding: '1px 5px',
        border: '1px solid var(--border-strong)',
        borderRadius: 3,
        color: 'var(--text-dim)',
        letterSpacing: '0.04em'
      }
    }, "VAULT"), h.locked && !h.in_storage && /*#__PURE__*/React.createElement("span", {
      title: "Locked",
      style: {
        fontSize: 10,
        color: 'var(--text-dim)'
      }
    }, "\uD83D\uDD12"), /*#__PURE__*/React.createElement("span", {
      className: "truncate"
    }, h.name)), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 10,
        color: 'var(--text-dim)',
        display: 'flex',
        alignItems: 'center',
        gap: 4
      },
      className: "mono"
    }, /*#__PURE__*/React.createElement(AffinityIcon, {
      element: h.element,
      size: 11
    }), /*#__PURE__*/React.createElement("span", null, h.role || '', h.element ? ' · ' + h.element : ''))), /*#__PURE__*/React.createElement("span", {
      style: {
        color: 'var(--text-sub)'
      },
      className: "truncate"
    }, h.faction), /*#__PURE__*/React.createElement("span", {
      style: {
        color: RARITY_COLORS[h.rarity]
      }
    }, h.rarity), /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        color: 'var(--text-sub)'
      }
    }, h.level, " \xB7 ", h.stars, "\u2605"), /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        color: h.empower > 0 ? 'var(--violet)' : 'var(--text-dim)'
      }
    }, h.empower > 0 ? '+' + h.empower : '—'), /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        color: 'var(--text-sub)',
        fontSize: 11
      }
    }, h.skills && h.skills.length ? h.skills.join('/') : '—'), /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        fontSize: 11,
        color: mComplete ? 'var(--accent)' : mtotal > 0 ? 'var(--text-sub)' : 'var(--text-dim)'
      },
      title: `Offense ${mtrees[0]} · Defense ${mtrees[1]} · Support ${mtrees[2]}`
    }, mtotal > 0 ? `${mtrees[0]}/${mtrees[1]}/${mtrees[2]}` : '—'), /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        fontSize: 11,
        color: h.ascend_grade > 0 ? 'oklch(0.72 0.16 85)' : 'var(--text-dim)'
      },
      title: h.ascend_grade ? `Ascension grade ${h.ascend_grade}` : ''
    }, h.ascend_grade > 0 ? '★'.repeat(Math.min(h.ascend_grade, 3)) : '—'), /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        color: (h.equipped_count || 0) >= 6 ? 'var(--accent)' : 'var(--text-dim)'
      }
    }, h.equipped_count || 0, "/9"));
  }))), tab === 'artifacts' && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '8px 12px',
      borderBottom: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      flexWrap: 'wrap'
    }
  }, /*#__PURE__*/React.createElement("label", {
    style: filterLbl
  }, "slot"), /*#__PURE__*/React.createElement("select", {
    value: artSlotFilter,
    onChange: e => setArtSlotFilter(e.target.value),
    style: filterSel
  }, /*#__PURE__*/React.createElement("option", {
    value: "all"
  }, "all"), Object.entries({
    1: 'Helmet',
    2: 'Chest',
    3: 'Gloves',
    4: 'Boots',
    5: 'Weapon',
    6: 'Shield',
    7: 'Ring',
    8: 'Amulet',
    9: 'Banner'
  }).map(([id, name]) => /*#__PURE__*/React.createElement("option", {
    key: id,
    value: id
  }, name))), /*#__PURE__*/React.createElement("label", {
    style: filterLbl
  }, "rarity"), /*#__PURE__*/React.createElement("select", {
    value: artRarityFilter,
    onChange: e => setArtRarityFilter(e.target.value),
    style: filterSel
  }, /*#__PURE__*/React.createElement("option", {
    value: "all"
  }, "all"), [6, 5, 4, 3, 2, 1].map(r => /*#__PURE__*/React.createElement("option", {
    key: r,
    value: r
  }, RARITY_NAMES_BY_ID[r]))), /*#__PURE__*/React.createElement("label", {
    style: filterLbl
  }, "set"), /*#__PURE__*/React.createElement("select", {
    value: artSetFilter,
    onChange: e => setArtSetFilter(e.target.value),
    style: {
      ...filterSel,
      maxWidth: 140
    }
  }, /*#__PURE__*/React.createElement("option", {
    value: "all"
  }, "all"), sets.map(([n, c]) => /*#__PURE__*/React.createElement("option", {
    key: n,
    value: n
  }, n, " (", c, ")"))), /*#__PURE__*/React.createElement("label", {
    style: filterLbl
  }, "primary"), /*#__PURE__*/React.createElement("select", {
    value: artPrimaryFilter,
    onChange: e => setArtPrimaryFilter(e.target.value),
    style: filterSel
  }, /*#__PURE__*/React.createElement("option", {
    value: "all"
  }, "all"), ['HP', 'ATK', 'DEF', 'SPD', 'RES', 'ACC', 'CR', 'CD'].map(st => /*#__PURE__*/React.createElement("option", {
    key: st,
    value: st
  }, st))), /*#__PURE__*/React.createElement("label", {
    style: filterLbl
  }, "sub"), /*#__PURE__*/React.createElement("select", {
    value: artSubFilter,
    onChange: e => setArtSubFilter(e.target.value),
    style: filterSel
  }, /*#__PURE__*/React.createElement("option", {
    value: "all"
  }, "all"), ['SPD', 'CR', 'CD', 'ATK', 'HP', 'DEF', 'RES', 'ACC'].map(st => /*#__PURE__*/React.createElement("option", {
    key: st,
    value: st
  }, st))), /*#__PURE__*/React.createElement("label", {
    style: filterLbl
  }, "rank \u2265"), /*#__PURE__*/React.createElement("select", {
    value: artMinRank,
    onChange: e => setArtMinRank(e.target.value),
    style: filterSel
  }, /*#__PURE__*/React.createElement("option", {
    value: "all"
  }, "all"), [6, 5, 4, 3].map(r => /*#__PURE__*/React.createElement("option", {
    key: r,
    value: r
  }, r, "\u2605"))), /*#__PURE__*/React.createElement("label", {
    style: filterLbl
  }, "where"), /*#__PURE__*/React.createElement("select", {
    value: artEquip,
    onChange: e => setArtEquip(e.target.value),
    style: filterSel
  }, /*#__PURE__*/React.createElement("option", {
    value: "all"
  }, "any"), /*#__PURE__*/React.createElement("option", {
    value: "equipped"
  }, "equipped"), /*#__PURE__*/React.createElement("option", {
    value: "vault"
  }, "vault")), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1,
      minWidth: 8
    }
  }), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 11,
      color: 'var(--text-sub)'
    }
  }, artifacts.length, " / ", allArtifacts.length)), /*#__PURE__*/React.createElement("div", {
    className: "scroll",
    style: {
      flex: 1,
      overflowY: 'auto'
    }
  }, allArtifacts.length === 0 ? /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 24,
      fontSize: 12,
      color: 'var(--text-dim)',
      textAlign: 'center'
    }
  }, "No artifacts loaded yet. The mod is paginating \u2014 refresh in a few seconds.") : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '70px 100px 70px 40px 36px 130px 1fr 100px',
      gap: 4,
      padding: '8px 16px',
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      borderBottom: '1px solid var(--border)',
      background: 'var(--bg-subtle)'
    }
  }, /*#__PURE__*/React.createElement("span", null, "Slot"), /*#__PURE__*/React.createElement("span", null, "Set"), /*#__PURE__*/React.createElement("span", null, "Rarity"), /*#__PURE__*/React.createElement("span", null, "Rk"), /*#__PURE__*/React.createElement("span", null, "Lv"), /*#__PURE__*/React.createElement("span", null, "Primary"), /*#__PURE__*/React.createElement("span", null, "Substats"), /*#__PURE__*/React.createElement("span", null, "Equipped")), artifacts.slice(0, 500).map(a => {
    const rname = RARITY_NAMES_BY_ID[a.rarity] || '?';
    const rcolor = RARITY_COLORS[rname] || 'var(--text-sub)';
    const fmtVal = (v, flat) => {
      const n = Math.round((v || 0) * 10) / 10;
      return flat ? `${n}` : `${n}%`;
    };
    const primary = a.primary_stat ? `${a.primary_stat} +${fmtVal(a.primary_value, a.primary_flat)}` : '';
    return /*#__PURE__*/React.createElement("div", {
      key: a.id,
      style: {
        display: 'grid',
        gridTemplateColumns: '70px 100px 70px 40px 36px 130px 1fr 100px',
        gap: 4,
        padding: '7px 16px',
        fontSize: 12,
        borderBottom: '1px solid var(--border)',
        alignItems: 'center'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        color: 'var(--text)'
      }
    }, a.slot), /*#__PURE__*/React.createElement("span", {
      style: {
        color: 'var(--text-sub)'
      },
      className: "truncate"
    }, a.set_name), /*#__PURE__*/React.createElement("span", {
      style: {
        color: rcolor
      }
    }, rname), /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        color: 'var(--text-sub)'
      }
    }, a.rank, "\u2605"), /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        color: 'var(--text-sub)'
      }
    }, a.level), /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        fontSize: 11
      }
    }, primary), /*#__PURE__*/React.createElement("span", {
      style: {
        display: 'flex',
        flexWrap: 'wrap',
        gap: '4px 10px',
        fontSize: 11
      }
    }, (a.substats || []).map((sb, i) => /*#__PURE__*/React.createElement("span", {
      key: i,
      className: "mono",
      style: {
        color: sb.stat === 'SPD' ? 'var(--accent)' : sb.stat === 'CR' || sb.stat === 'CD' ? 'var(--violet)' : 'var(--text-sub)'
      }
    }, sb.stat, " +", fmtVal(sb.value, sb.flat), sb.rolls > 0 && /*#__PURE__*/React.createElement("span", {
      style: {
        color: 'var(--text-dim)'
      }
    }, " \xB7", sb.rolls), sb.glyph > 0 && /*#__PURE__*/React.createElement("span", {
      style: {
        color: 'oklch(0.72 0.16 85)'
      }
    }, " +", fmtVal(sb.glyph, sb.flat))))), /*#__PURE__*/React.createElement("span", {
      className: "truncate",
      style: {
        fontSize: 11,
        color: a.equipped_on ? 'var(--accent)' : 'var(--text-dim)'
      }
    }, a.equipped_on ? a.equipped_on.hero_name : '—'));
  }), artifacts.length > 500 && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 10,
      fontSize: 11,
      color: 'var(--text-dim)',
      textAlign: 'center'
    }
  }, "showing first 500 of ", artifacts.length)))), tab === 'gaps' && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '8px 12px',
      borderBottom: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      flexWrap: 'wrap'
    }
  }, /*#__PURE__*/React.createElement("label", {
    style: filterLbl
  }, "HH \u2265"), /*#__PURE__*/React.createElement("input", {
    type: "number",
    step: "0.5",
    min: "0",
    max: "6",
    value: gapThreshold,
    onChange: e => setGapThreshold(parseFloat(e.target.value) || 0),
    style: {
      ...filterSel,
      width: 60
    }
  }), /*#__PURE__*/React.createElement("label", {
    style: filterLbl
  }, "inv. rarity \u2265"), /*#__PURE__*/React.createElement("select", {
    value: gapMinRarity,
    onChange: e => setGapMinRarity(parseInt(e.target.value)),
    style: {
      ...filterSel,
      width: 100
    }
  }, /*#__PURE__*/React.createElement("option", {
    value: 3
  }, "Rare+"), /*#__PURE__*/React.createElement("option", {
    value: 4
  }, "Epic+"), /*#__PURE__*/React.createElement("option", {
    value: 5
  }, "Legendary")), /*#__PURE__*/React.createElement("label", {
    style: filterLbl
  }, "top"), /*#__PURE__*/React.createElement("input", {
    type: "number",
    min: "5",
    max: "50",
    value: gapTopN,
    onChange: e => setGapTopN(parseInt(e.target.value) || 15),
    style: {
      ...filterSel,
      width: 50
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement("button", {
    className: "btn",
    onClick: fetchGaps,
    disabled: gapLoading,
    style: {
      height: 22,
      padding: '0 10px',
      fontSize: 11
    }
  }, gapLoading ? 'Loading…' : 'Refresh'), gapData && /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 11,
      color: 'var(--text-sub)'
    }
  }, gapData.unique_viable_heroes, " heroes \xB7 ", gapData.inventory_total, " pieces")), /*#__PURE__*/React.createElement("div", {
    className: "scroll",
    style: {
      flex: 1,
      overflowY: 'auto',
      padding: 12
    }
  }, gapErr && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 12,
      color: 'var(--danger,#ff6b6b)'
    }
  }, gapErr), gapData && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 14
    }
  }, gapData.forge && gapData.forge.length > 0 && /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 0,
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '8px 12px',
      borderBottom: '1px solid var(--border)',
      background: 'var(--bg-subtle)',
      fontSize: 10.5,
      color: 'var(--text-sub)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      fontWeight: 600
    }
  }, "Forge crafting priority \u2014 gaps you fix in the Forge, not a dungeon"), /*#__PURE__*/React.createElement("table", {
    style: {
      width: '100%',
      borderCollapse: 'collapse',
      fontSize: 12
    }
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", {
    style: {
      borderBottom: '1px solid var(--border)',
      background: 'var(--bg-subtle)'
    }
  }, /*#__PURE__*/React.createElement("th", {
    style: _th
  }, "Set"), /*#__PURE__*/React.createElement("th", {
    style: {
      ..._th,
      textAlign: 'right'
    }
  }, "Gap"), /*#__PURE__*/React.createElement("th", {
    style: {
      ..._th,
      textAlign: 'right'
    }
  }, "Demand"), /*#__PURE__*/React.createElement("th", {
    style: {
      ..._th,
      textAlign: 'right'
    }
  }, "Supply"), /*#__PURE__*/React.createElement("th", {
    style: _th
  }, "Top areas driving demand"))), /*#__PURE__*/React.createElement("tbody", null, gapData.forge.map(r => /*#__PURE__*/React.createElement("tr", {
    key: r.set_id,
    style: {
      borderBottom: '1px solid var(--border)'
    }
  }, /*#__PURE__*/React.createElement("td", {
    style: {
      ..._td,
      fontWeight: 600
    }
  }, r.set_name), /*#__PURE__*/React.createElement("td", {
    style: {
      ..._td,
      textAlign: 'right',
      fontWeight: 600,
      color: 'var(--danger,#ff6b6b)'
    },
    className: "mono"
  }, r.gap > 0 ? '+' : '', r.gap), /*#__PURE__*/React.createElement("td", {
    style: {
      ..._td,
      textAlign: 'right'
    },
    className: "mono"
  }, r.demand), /*#__PURE__*/React.createElement("td", {
    style: {
      ..._td,
      textAlign: 'right'
    },
    className: "mono"
  }, r.supply), /*#__PURE__*/React.createElement("td", {
    style: _td
  }, /*#__PURE__*/React.createElement(TopAreas, {
    areas: r.top_areas
  }))))))), gapData.dungeons && gapData.dungeons.length > 0 && /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 0,
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '8px 12px',
      borderBottom: '1px solid var(--border)',
      background: 'var(--bg-subtle)',
      fontSize: 10.5,
      color: 'var(--text-sub)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      fontWeight: 600
    }
  }, "Dungeon farming priority \u2014 highest gap-points closed first"), /*#__PURE__*/React.createElement("table", {
    style: {
      width: '100%',
      borderCollapse: 'collapse',
      fontSize: 12
    }
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", {
    style: {
      borderBottom: '1px solid var(--border)',
      background: 'var(--bg-subtle)'
    }
  }, /*#__PURE__*/React.createElement("th", {
    style: _th
  }, "Dungeon"), /*#__PURE__*/React.createElement("th", {
    style: {
      ..._th,
      textAlign: 'right'
    }
  }, "Score"), /*#__PURE__*/React.createElement("th", {
    style: _th
  }, "Sets it closes"), /*#__PURE__*/React.createElement("th", {
    style: _th
  }, "Accessory gaps"))), /*#__PURE__*/React.createElement("tbody", null, gapData.dungeons.map(d => /*#__PURE__*/React.createElement("tr", {
    key: d.region,
    style: {
      borderBottom: '1px solid var(--border)'
    }
  }, /*#__PURE__*/React.createElement("td", {
    style: _td
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontWeight: 600
    }
  }, d.label), d.difficulties && d.difficulties.length > 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      marginTop: 2
    }
  }, d.difficulties.map(x => `${x.difficulty} (${x.stages} stages)`).join(' · '))), /*#__PURE__*/React.createElement("td", {
    style: {
      ..._td,
      textAlign: 'right',
      fontWeight: 600,
      color: 'var(--accent, #6bd0ff)'
    },
    className: "mono"
  }, d.score), /*#__PURE__*/React.createElement("td", {
    style: _td
  }, d.gap_sets.length === 0 ? /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-dim)'
    }
  }, "\u2014") : d.gap_sets.map((s, i) => /*#__PURE__*/React.createElement("span", {
    key: i,
    style: {
      marginRight: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text)'
    }
  }, s.set_name), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: 'var(--danger,#ff6b6b)',
      marginLeft: 3
    }
  }, "(", s.gap > 0 ? '+' : '', s.gap, ")")))), /*#__PURE__*/React.createElement("td", {
    style: _td
  }, d.accessory_kinds.length === 0 ? /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-dim)'
    }
  }, "\u2014") : /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text)'
    }
  }, d.accessory_kinds.map(s => ({
    7: 'Ring',
    8: 'Amulet',
    9: 'Banner'
  })[s] || `slot${s}`).join(', ')), d.accessory_bonus > 0 && /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: 'var(--danger,#ff6b6b)',
      marginLeft: 6
    }
  }, "(-", d.accessory_bonus, ")")))))))), /*#__PURE__*/React.createElement(GapTable, {
    title: "Set gaps (most under-supplied first)",
    rows: gapData.sets,
    cols: [{
      h: 'Set',
      v: r => r.set_name
    }, {
      h: 'Demand',
      v: r => r.demand,
      mono: 1,
      align: 'right'
    }, {
      h: 'Supply',
      v: r => r.supply,
      mono: 1,
      align: 'right'
    }, {
      h: 'Gap',
      v: r => (r.gap > 0 ? '+' : '') + r.gap,
      mono: 1,
      align: 'right',
      color: r => r.gap < 0 ? 'var(--danger,#ff6b6b)' : 'var(--success,#6bd06b)',
      bold: 1
    }, {
      h: 'Top areas',
      v: r => /*#__PURE__*/React.createElement(TopAreas, {
        areas: r.top_areas
      })
    }]
  }), /*#__PURE__*/React.createElement(GapTable, {
    title: "Primary stat \xD7 slot gaps",
    rows: gapData.primaries,
    cols: [{
      h: 'Slot',
      v: r => r.slot_name
    }, {
      h: 'Stat',
      v: r => r.stat
    }, {
      h: 'Demand',
      v: r => r.demand,
      mono: 1,
      align: 'right'
    }, {
      h: 'Supply',
      v: r => r.supply,
      mono: 1,
      align: 'right'
    }, {
      h: 'Gap',
      v: r => (r.gap > 0 ? '+' : '') + r.gap,
      mono: 1,
      align: 'right',
      color: r => r.gap < 0 ? 'var(--danger,#ff6b6b)' : 'var(--success,#6bd06b)',
      bold: 1
    }, {
      h: 'Top areas',
      v: r => /*#__PURE__*/React.createElement(TopAreas, {
        areas: r.top_areas
      })
    }]
  }), /*#__PURE__*/React.createElement(GapTable, {
    title: "Substat gaps (recommendation count vs total inventory substat appearances)",
    rows: gapData.substats,
    cols: [{
      h: 'Stat',
      v: r => r.stat
    }, {
      h: 'Demand',
      v: r => r.demand,
      mono: 1,
      align: 'right'
    }, {
      h: 'Supply',
      v: r => r.supply,
      mono: 1,
      align: 'right'
    }, {
      h: 'Gap',
      v: r => (r.gap > 0 ? '+' : '') + r.gap,
      mono: 1,
      align: 'right',
      color: r => r.gap < 0 ? 'var(--danger,#ff6b6b)' : 'var(--success,#6bd06b)',
      bold: 1
    }, {
      h: 'Top areas',
      v: r => /*#__PURE__*/React.createElement(TopAreas, {
        areas: r.top_areas
      })
    }]
  }), /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 10
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-sub)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      marginBottom: 6
    }
  }, "Viable heroes per area"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))',
      gap: 6
    }
  }, Object.entries(gapData.viable_per_area).map(([area, n]) => /*#__PURE__*/React.createElement("div", {
    key: area,
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      padding: '3px 8px',
      background: 'var(--bg-subtle)',
      borderRadius: 3,
      fontSize: 11
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-sub)'
    }
  }, area), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontWeight: 600
    }
  }, n))))))))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateRows: 'auto auto minmax(0, 1fr)',
      gap: 10,
      minHeight: 0,
      maxHeight: '100%'
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-title",
    style: {
      marginBottom: 10
    }
  }, "Vault"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      fontSize: 12,
      marginBottom: 6
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-sub)'
    }
  }, "Artifacts"), /*#__PURE__*/React.createElement("span", {
    className: "mono"
  }, allArtifacts.length || '—')), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      fontSize: 12,
      marginBottom: 6
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-sub)'
    }
  }, "Legendary"), /*#__PURE__*/React.createElement("span", {
    className: "mono"
  }, allArtifacts.filter(a => a.rarity === 5).length)), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      fontSize: 12
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-sub)'
    }
  }, "Epic"), /*#__PURE__*/React.createElement("span", {
    className: "mono"
  }, allArtifacts.filter(a => a.rarity === 4).length))), /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-title",
    style: {
      marginBottom: 10
    }
  }, "Hero rarity mix"), ['Legendary', 'Epic', 'Rare', 'Uncommon'].map(r => {
    const n = s.heroes.filter(h => h.rarity === r).length;
    return /*#__PURE__*/React.createElement("div", {
      key: r,
      style: {
        marginBottom: 8
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        justifyContent: 'space-between',
        fontSize: 11.5,
        marginBottom: 3
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        color: RARITY_COLORS[r]
      }
    }, r), /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        color: 'var(--text-sub)'
      }
    }, n)), /*#__PURE__*/React.createElement("div", {
      style: {
        height: 3,
        background: 'var(--bg-subtle)',
        borderRadius: 2,
        overflow: 'hidden'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        width: `${s.heroes.length ? n / s.heroes.length * 100 : 0}%`,
        height: '100%',
        background: RARITY_COLORS[r]
      }
    })));
  })), /*#__PURE__*/React.createElement(SellRulesPanel, null)));
}

// Sell rules editor + preview. Mirrors RSL-helper's filter chain: each rule
// is a set of AND'd conditions; rules evaluate top-to-bottom and the first
// match marks the artifact for sale. Backend is /api/sell-rules.
function SellRulesPanel() {
  const [cfg, setCfg] = React.useState(null);
  const [summary, setSummary] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const [dirty, setDirty] = React.useState(false);
  const [showPreview, setShowPreview] = React.useState(false);
  const [previewItems, setPreviewItems] = React.useState(null);
  const fetchRules = React.useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch('/api/sell-rules', {
        cache: 'no-store'
      });
      const j = await r.json();
      setCfg(j.config);
      setSummary(j.summary);
      setDirty(false);
    } catch (e) {}
    setLoading(false);
  }, []);
  React.useEffect(() => {
    fetchRules();
  }, [fetchRules]);
  const save = React.useCallback(async () => {
    if (!cfg) return;
    setLoading(true);
    try {
      const r = await fetch('/api/sell-rules', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(cfg)
      });
      const j = await r.json();
      if (j.ok) {
        setCfg(j.config);
        setDirty(false);
        // Refresh summary after save
        const r2 = await fetch('/api/sell-rules', {
          cache: 'no-store'
        });
        const j2 = await r2.json();
        setSummary(j2.summary);
      }
    } catch (e) {}
    setLoading(false);
  }, [cfg]);
  const loadPreview = React.useCallback(async () => {
    // Open the modal immediately with a null/loading state so there's
    // visual feedback while the (potentially slow) /api/sell-rules/preview
    // call finishes. The vault fetch can take a few seconds when the
    // mod-side artifact cache is cold.
    setPreviewItems(null);
    setShowPreview(true);
    setLoading(true);
    try {
      const r = await fetch('/api/sell-rules/preview', {
        cache: 'no-store'
      });
      const j = await r.json();
      setPreviewItems(j.sell || []);
    } catch (e) {
      setPreviewItems([]);
    }
    setLoading(false);
  }, []);
  const updateRule = (idx, patch) => {
    setCfg({
      ...cfg,
      rules: cfg.rules.map((r, i) => i === idx ? {
        ...r,
        ...patch
      } : r)
    });
    setDirty(true);
  };
  const toggleRule = idx => updateRule(idx, {
    enabled: !cfg.rules[idx].enabled
  });
  const deleteRule = idx => {
    setCfg({
      ...cfg,
      rules: cfg.rules.filter((_, i) => i !== idx)
    });
    setDirty(true);
  };
  const moveRule = (idx, dir) => {
    const next = [...cfg.rules];
    const target = idx + dir;
    if (target < 0 || target >= next.length) return;
    [next[idx], next[target]] = [next[target], next[idx]];
    setCfg({
      ...cfg,
      rules: next
    });
    setDirty(true);
  };
  const addRule = () => {
    const id = `rule_${Date.now().toString(36)}`;
    setCfg({
      ...cfg,
      rules: [...cfg.rules, {
        id,
        name: 'New rule',
        enabled: false
      }]
    });
    setDirty(true);
  };
  const [expanded, setExpanded] = React.useState(null); // index of expanded rule
  const [showAdvanced, setShowAdvanced] = React.useState(false);
  if (!cfg) {
    return /*#__PURE__*/React.createElement("div", {
      className: "card",
      style: {
        padding: 16
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: "card-title",
      style: {
        marginBottom: 10
      }
    }, "Sell rules"), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 11.5,
        color: 'var(--text-dim)'
      }
    }, loading ? 'Loading…' : 'Failed to load.'));
  }
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "card scroll",
    style: {
      padding: 16,
      overflowY: 'auto',
      minHeight: 0,
      maxHeight: '100%'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      marginBottom: 10
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-title"
  }, "Sell rules"), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 11,
      color: 'var(--accent)'
    }
  }, summary ? `${summary.sell_count} match` : '…')), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: 'var(--text-sub)',
      marginBottom: 10,
      lineHeight: 1.5
    }
  }, "First-match wins. Equipped pieces are always kept."), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      marginBottom: 10
    }
  }, cfg.rules.map((r, i) => {
    const ruleCount = (summary?.by_rule || {})[r.id] || 0;
    const isOpen = expanded === i;
    return /*#__PURE__*/React.createElement("div", {
      key: r.id || i,
      style: {
        background: 'var(--bg-subtle)',
        borderRadius: 4,
        opacity: r.enabled ? 1 : 0.55,
        borderLeft: `2px solid ${r.enabled ? 'var(--accent)' : 'var(--border)'}`,
        minWidth: 0
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '6px 8px',
        fontSize: 11.5,
        cursor: 'pointer'
      },
      onClick: () => setExpanded(isOpen ? null : i)
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: !!r.enabled,
      onChange: e => {
        e.stopPropagation();
        toggleRule(i);
      },
      onClick: e => e.stopPropagation(),
      style: {
        margin: 0,
        cursor: 'pointer'
      }
    }), /*#__PURE__*/React.createElement("span", {
      style: {
        flex: 1,
        minWidth: 0
      },
      className: "truncate"
    }, r.name), r.enabled && /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        fontSize: 10,
        color: 'var(--text-sub)',
        minWidth: 30,
        textAlign: 'right'
      }
    }, ruleCount), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 10,
        color: 'var(--text-dim)',
        width: 12,
        textAlign: 'center'
      }
    }, isOpen ? '▾' : '▸')), isOpen && /*#__PURE__*/React.createElement(RuleEditor, {
      rule: r,
      onChange: patch => updateRule(i, patch),
      onDelete: () => deleteRule(i),
      onMoveUp: i > 0 ? () => moveRule(i, -1) : null,
      onMoveDown: i < cfg.rules.length - 1 ? () => moveRule(i, 1) : null
    }));
  }), /*#__PURE__*/React.createElement("button", {
    className: "btn",
    onClick: addRule,
    style: {
      height: 24,
      fontSize: 11,
      marginTop: 2,
      color: 'var(--text-sub)',
      borderStyle: 'dashed'
    }
  }, "+ Add rule")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 6
    }
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn",
    onClick: save,
    disabled: !dirty || loading,
    style: {
      flex: 1,
      height: 26,
      fontSize: 11,
      background: dirty ? 'var(--accent)' : 'transparent',
      color: dirty ? 'var(--bg)' : 'var(--text-sub)',
      borderColor: dirty ? 'var(--accent)' : 'var(--border)'
    }
  }, dirty ? 'Save' : 'Saved'), /*#__PURE__*/React.createElement("button", {
    className: "btn",
    onClick: loadPreview,
    disabled: loading,
    style: {
      flex: 1,
      height: 26,
      fontSize: 11
    }
  }, "Preview")), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 10
    }
  }, /*#__PURE__*/React.createElement("button", {
    onClick: () => setShowAdvanced(!showAdvanced),
    style: {
      background: 'transparent',
      border: 0,
      padding: 0,
      fontSize: 10.5,
      color: 'var(--text-sub)',
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      gap: 4
    }
  }, /*#__PURE__*/React.createElement("span", null, showAdvanced ? '▾' : '▸'), /*#__PURE__*/React.createElement("span", null, "Global config")), showAdvanced && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '8px 4px',
      display: 'flex',
      flexDirection: 'column',
      gap: 8,
      marginTop: 6
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      color: 'var(--text-dim)',
      marginBottom: 3
    }
  }, "Junk sets (always sell)"), /*#__PURE__*/React.createElement(CSVField, {
    value: cfg.junk_sets || [],
    onChange: v => {
      setCfg({
        ...cfg,
        junk_sets: v
      });
      setDirty(true);
    },
    placeholder: "Avenge, Frenzy, \u2026"
  })), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      color: 'var(--text-dim)',
      marginBottom: 3
    }
  }, "Useful substats"), /*#__PURE__*/React.createElement(CSVField, {
    value: cfg.useful_substats || [],
    onChange: v => {
      setCfg({
        ...cfg,
        useful_substats: v
      });
      setDirty(true);
    },
    placeholder: "SPD, ACC, CR, CD, HP%, \u2026"
  })), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      color: 'var(--text-dim)',
      marginBottom: 3
    }
  }, "Slot \u2192 required primary"), Object.entries(cfg.slot_required_primary || {}).map(([slot, prims]) => /*#__PURE__*/React.createElement("div", {
    key: slot,
    style: {
      display: 'flex',
      gap: 4,
      marginBottom: 3,
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 10,
      color: 'var(--text-sub)',
      width: 56
    }
  }, slot), /*#__PURE__*/React.createElement(CSVField, {
    value: prims,
    onChange: v => {
      const next = {
        ...(cfg.slot_required_primary || {}),
        [slot]: v
      };
      setCfg({
        ...cfg,
        slot_required_primary: next
      });
      setDirty(true);
    }
  })))), /*#__PURE__*/React.createElement("label", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      fontSize: 11
    }
  }, /*#__PURE__*/React.createElement("input", {
    type: "checkbox",
    checked: !!cfg.exclude_equipped,
    onChange: e => {
      setCfg({
        ...cfg,
        exclude_equipped: e.target.checked
      });
      setDirty(true);
    }
  }), /*#__PURE__*/React.createElement("span", null, "Exclude equipped pieces (recommended)")))), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      color: 'var(--text-dim)',
      marginTop: 8,
      lineHeight: 1.4
    }
  }, "Settings file: ", /*#__PURE__*/React.createElement("span", {
    className: "mono"
  }, "data/sell_rules.json"))), showPreview && /*#__PURE__*/React.createElement(SellPreviewModal, {
    items: previewItems,
    onClose: () => setShowPreview(false)
  }));
}

// --- helpers for rule editing -----------------------------------------------

const SLOT_OPTIONS = ['Helmet', 'Chest', 'Gloves', 'Boots', 'Weapon', 'Shield', 'Ring', 'Amulet', 'Banner'];
const PRIMARY_OPTIONS = ['HP', 'HP%', 'ATK', 'ATK%', 'DEF', 'DEF%', 'SPD', 'RES', 'ACC', 'CR', 'CD'];
function CSVField({
  value,
  onChange,
  placeholder
}) {
  const [raw, setRaw] = React.useState((value || []).join(', '));
  React.useEffect(() => {
    setRaw((value || []).join(', '));
  }, [value]);
  return /*#__PURE__*/React.createElement("input", {
    type: "text",
    value: raw,
    placeholder: placeholder || '',
    onChange: e => setRaw(e.target.value),
    onBlur: () => {
      const parsed = raw.split(',').map(s => s.trim()).filter(Boolean);
      onChange(parsed);
    },
    style: {
      width: '100%',
      boxSizing: 'border-box',
      height: 22,
      padding: '0 6px',
      fontSize: 11,
      fontFamily: 'inherit',
      background: 'var(--bg)',
      color: 'var(--text)',
      border: '1px solid var(--border)',
      borderRadius: 3
    }
  });
}
function NumField({
  value,
  onChange,
  placeholder,
  min,
  max
}) {
  return /*#__PURE__*/React.createElement("input", {
    type: "number",
    value: value ?? '',
    placeholder: placeholder || '',
    min: min,
    max: max,
    onChange: e => {
      const v = e.target.value;
      if (v === '') onChange(undefined);else onChange(Number(v));
    },
    style: {
      width: 44,
      boxSizing: 'border-box',
      height: 22,
      padding: '0 4px',
      fontSize: 11,
      fontFamily: 'inherit',
      background: 'var(--bg)',
      color: 'var(--text)',
      border: '1px solid var(--border)',
      borderRadius: 3
    }
  });
}
function MultiSelect({
  options,
  value,
  onChange
}) {
  const set = new Set(value || []);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexWrap: 'wrap',
      gap: 3
    }
  }, options.map(o => {
    const on = set.has(o);
    return /*#__PURE__*/React.createElement("button", {
      key: o,
      onClick: () => {
        const next = on ? value.filter(v => v !== o) : [...(value || []), o];
        onChange(next);
      },
      style: {
        height: 20,
        padding: '0 6px',
        fontSize: 10,
        background: on ? 'var(--accent)' : 'transparent',
        color: on ? 'var(--bg)' : 'var(--text-sub)',
        border: `1px solid ${on ? 'var(--accent)' : 'var(--border)'}`,
        borderRadius: 3,
        cursor: 'pointer'
      }
    }, o);
  }));
}
function RuleEditor({
  rule,
  onChange,
  onDelete,
  onMoveUp,
  onMoveDown
}) {
  const labelStyle = {
    fontSize: 10,
    color: 'var(--text-dim)',
    marginBottom: 2,
    marginTop: 4
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '8px 10px 10px',
      borderTop: '1px solid var(--border)',
      display: 'flex',
      flexDirection: 'column',
      gap: 4
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: labelStyle
  }, "Name"), /*#__PURE__*/React.createElement("input", {
    type: "text",
    value: rule.name || '',
    onChange: e => onChange({
      name: e.target.value
    }),
    style: {
      width: '100%',
      boxSizing: 'border-box',
      height: 22,
      padding: '0 6px',
      fontSize: 11,
      fontFamily: 'inherit',
      background: 'var(--bg)',
      color: 'var(--text)',
      border: '1px solid var(--border)',
      borderRadius: 3
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexWrap: 'wrap',
      gap: '8px 14px'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: labelStyle
  }, "Rank"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 3
    }
  }, /*#__PURE__*/React.createElement(NumField, {
    value: rule.min_rank,
    onChange: v => onChange({
      min_rank: v
    }),
    placeholder: "\u2013",
    min: 1,
    max: 6
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-dim)',
      fontSize: 10
    }
  }, "\u2013"), /*#__PURE__*/React.createElement(NumField, {
    value: rule.max_rank,
    onChange: v => onChange({
      max_rank: v
    }),
    placeholder: "\u2013",
    min: 1,
    max: 6
  }))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: labelStyle
  }, "Rarity"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 3
    }
  }, /*#__PURE__*/React.createElement(NumField, {
    value: rule.min_rarity,
    onChange: v => onChange({
      min_rarity: v
    }),
    placeholder: "\u2013",
    min: 1,
    max: 6
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-dim)',
      fontSize: 10
    }
  }, "\u2013"), /*#__PURE__*/React.createElement(NumField, {
    value: rule.max_rarity,
    onChange: v => onChange({
      max_rarity: v
    }),
    placeholder: "\u2013",
    min: 1,
    max: 6
  }))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: labelStyle,
    title: "Upgrade level (+0 to +16). Rolls reveal/upgrade at +0/+4/+8/+12/+16."
  }, "Level"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 3
    }
  }, /*#__PURE__*/React.createElement(NumField, {
    value: rule.min_level,
    onChange: v => onChange({
      min_level: v
    }),
    placeholder: "\u2013",
    min: 0,
    max: 16
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-dim)',
      fontSize: 10
    }
  }, "\u2013"), /*#__PURE__*/React.createElement(NumField, {
    value: rule.max_level,
    onChange: v => onChange({
      max_level: v
    }),
    placeholder: "\u2013",
    min: 0,
    max: 16
  }))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: labelStyle
  }, "Useful subs"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 3
    }
  }, /*#__PURE__*/React.createElement(NumField, {
    value: rule.min_useful_subs,
    onChange: v => onChange({
      min_useful_subs: v
    }),
    placeholder: "\u2013",
    min: 0,
    max: 4
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-dim)',
      fontSize: 10
    }
  }, "\u2013"), /*#__PURE__*/React.createElement(NumField, {
    value: rule.max_useful_subs,
    onChange: v => onChange({
      max_useful_subs: v
    }),
    placeholder: "\u2013",
    min: 0,
    max: 4
  })))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: labelStyle
  }, "Slots (any of)"), /*#__PURE__*/React.createElement(MultiSelect, {
    options: SLOT_OPTIONS,
    value: rule.slots || [],
    onChange: v => onChange({
      slots: v.length ? v : undefined
    })
  })), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: labelStyle
  }, "Primary stat"), /*#__PURE__*/React.createElement("label", {
    style: {
      display: 'flex',
      alignItems: 'flex-start',
      gap: 4,
      fontSize: 10.5,
      lineHeight: 1.4,
      marginBottom: 4
    }
  }, /*#__PURE__*/React.createElement("input", {
    type: "checkbox",
    checked: !!rule.primary_not_in_slot_required,
    onChange: e => onChange({
      primary_not_in_slot_required: e.target.checked || undefined
    }),
    style: {
      marginTop: 2
    }
  }), /*#__PURE__*/React.createElement("span", null, "Primary NOT in slot's required list")), /*#__PURE__*/React.createElement("div", {
    style: labelStyle
  }, "Primary IS one of (any selected)"), /*#__PURE__*/React.createElement(MultiSelect, {
    options: PRIMARY_OPTIONS,
    value: rule.primary_in || [],
    onChange: v => onChange({
      primary_in: v.length ? v : undefined
    })
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      ...labelStyle,
      marginTop: 4
    }
  }, "Primary IS NOT one of"), /*#__PURE__*/React.createElement(MultiSelect, {
    options: PRIMARY_OPTIONS,
    value: rule.primary_not_in || [],
    onChange: v => onChange({
      primary_not_in: v.length ? v : undefined
    })
  })), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: labelStyle
  }, "Sets"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 3
    }
  }, /*#__PURE__*/React.createElement("label", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 4,
      fontSize: 10.5
    }
  }, /*#__PURE__*/React.createElement("input", {
    type: "checkbox",
    checked: !!rule.set_in_junk_list,
    onChange: e => onChange({
      set_in_junk_list: e.target.checked || undefined
    })
  }), /*#__PURE__*/React.createElement("span", null, "Set in global junk list")), /*#__PURE__*/React.createElement(CSVField, {
    value: rule.sets || [],
    onChange: v => onChange({
      sets: v.length ? v : undefined
    }),
    placeholder: "Specific sets (comma-separated)"
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 4,
      marginTop: 6
    }
  }, onMoveUp && /*#__PURE__*/React.createElement("button", {
    className: "btn",
    onClick: onMoveUp,
    style: {
      height: 22,
      padding: '0 8px',
      fontSize: 10
    }
  }, "\u2191"), onMoveDown && /*#__PURE__*/React.createElement("button", {
    className: "btn",
    onClick: onMoveDown,
    style: {
      height: 22,
      padding: '0 8px',
      fontSize: 10
    }
  }, "\u2193"), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement("button", {
    onClick: onDelete,
    style: {
      height: 22,
      padding: '0 8px',
      fontSize: 10,
      background: 'transparent',
      color: 'oklch(0.70 0.18 25)',
      border: '1px solid oklch(0.40 0.10 25)',
      borderRadius: 3,
      cursor: 'pointer'
    }
  }, "Delete")));
}
function SellPreviewModal({
  items,
  onClose
}) {
  const [filter, setFilter] = React.useState('all');
  const [selling, setSelling] = React.useState(false);
  const [confirm, setConfirm] = React.useState(false);
  const [result, setResult] = React.useState(null);
  const [elapsed, setElapsed] = React.useState(0); // seconds since sell started
  const isLoading = items == null;
  const safeItems = Array.isArray(items) ? items : [];
  const ruleIds = [...new Set(safeItems.map(i => i.rule_id))];
  const filtered = filter === 'all' ? safeItems : safeItems.filter(i => i.rule_id === filter);

  // Tick a counter while selling so the user sees the request is active
  React.useEffect(() => {
    if (!selling) return;
    setElapsed(0);
    const t0 = Date.now();
    const handle = setInterval(() => setElapsed(Math.floor((Date.now() - t0) / 1000)), 250);
    return () => clearInterval(handle);
  }, [selling]);
  const sellNow = async () => {
    setSelling(true);
    setResult(null);
    try {
      const r = await fetch('/api/sell-rules/bulk-sell', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          ids: filtered.map(i => i.id)
        })
      });
      const j = await r.json();
      setResult(j);
    } catch (e) {
      setResult({
        error: String(e)
      });
    }
    setSelling(false);
    setConfirm(false);
  };
  return /*#__PURE__*/React.createElement("div", {
    onClick: onClose,
    style: {
      position: 'fixed',
      inset: 0,
      background: 'rgba(0,0,0,0.6)',
      zIndex: 200,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 20
    }
  }, /*#__PURE__*/React.createElement("div", {
    onClick: e => e.stopPropagation(),
    className: "card scroll",
    style: {
      padding: 0,
      width: 800,
      maxWidth: '96vw',
      maxHeight: '85vh',
      overflow: 'auto',
      background: 'var(--bg-elev)',
      border: '1px solid var(--border-strong)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '14px 20px',
      borderBottom: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      position: 'sticky',
      top: 0,
      background: 'var(--bg-elev)',
      zIndex: 1
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em'
    }
  }, "Sell preview"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 18,
      fontWeight: 500,
      marginTop: 2
    }
  }, isLoading ? 'Loading vault…' : `${safeItems.length} artifacts match current rules`)), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }), !isLoading && /*#__PURE__*/React.createElement("select", {
    value: filter,
    onChange: e => setFilter(e.target.value),
    style: {
      height: 26,
      padding: '0 8px',
      fontSize: 11,
      background: 'var(--bg-subtle)',
      color: 'var(--text)',
      border: '1px solid var(--border)',
      borderRadius: 4
    }
  }, /*#__PURE__*/React.createElement("option", {
    value: "all"
  }, "all rules (", safeItems.length, ")"), ruleIds.map(rid => /*#__PURE__*/React.createElement("option", {
    key: rid,
    value: rid
  }, rid, " (", safeItems.filter(i => i.rule_id === rid).length, ")"))), !isLoading && filtered.length > 0 && !result && (confirm ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("button", {
    className: "btn",
    onClick: sellNow,
    disabled: selling,
    style: {
      height: 26,
      padding: '0 12px',
      fontSize: 11,
      background: 'oklch(0.55 0.18 25)',
      color: '#fff',
      borderColor: 'oklch(0.55 0.18 25)'
    }
  }, selling ? `Selling ${filtered.length}… ${elapsed}s` : `Confirm sell ${filtered.length}`), !selling && /*#__PURE__*/React.createElement("button", {
    className: "btn",
    onClick: () => setConfirm(false),
    style: {
      height: 26,
      padding: '0 12px',
      fontSize: 11
    }
  }, "Cancel")) : /*#__PURE__*/React.createElement("button", {
    className: "btn",
    onClick: () => setConfirm(true),
    style: {
      height: 26,
      padding: '0 12px',
      fontSize: 11,
      background: 'transparent',
      color: 'oklch(0.70 0.18 25)',
      borderColor: 'oklch(0.40 0.10 25)'
    }
  }, "Sell ", filtered.length, " now")), /*#__PURE__*/React.createElement("button", {
    className: "btn",
    onClick: onClose,
    style: {
      height: 26,
      padding: '0 12px'
    }
  }, "Close")), result && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '10px 20px',
      background: result.error ? 'oklch(0.20 0.10 25)' : 'oklch(0.20 0.12 145)',
      fontSize: 12,
      color: 'var(--text)',
      borderBottom: '1px solid var(--border)'
    }
  }, result.error ? `Error: ${result.error}` : `Sold ${result.sold?.length || 0} artifacts${result.skipped?.length ? ` · ${result.skipped.length} skipped (equipped/locked)` : ''}.`), isLoading ? /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 60,
      textAlign: 'center',
      color: 'var(--text-sub)',
      fontSize: 12
    }
  }, "Loading vault & evaluating rules\u2026") : /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '10px 20px 20px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '60px 80px 50px 50px 90px 110px 70px 1fr',
      gap: 8,
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      padding: '6px 0',
      borderBottom: '1px solid var(--border)',
      marginBottom: 4
    }
  }, /*#__PURE__*/React.createElement("span", null, "ID"), /*#__PURE__*/React.createElement("span", null, "Slot"), /*#__PURE__*/React.createElement("span", null, "Rank"), /*#__PURE__*/React.createElement("span", null, "+Lvl"), /*#__PURE__*/React.createElement("span", null, "Rarity"), /*#__PURE__*/React.createElement("span", null, "Set"), /*#__PURE__*/React.createElement("span", null, "Primary"), /*#__PURE__*/React.createElement("span", null, "Why")), filtered.slice(0, 250).map((it, i) => /*#__PURE__*/React.createElement("div", {
    key: it.id || i,
    style: {
      display: 'grid',
      gridTemplateColumns: '60px 80px 50px 50px 90px 110px 70px 1fr',
      gap: 8,
      fontSize: 11.5,
      padding: '5px 0',
      borderBottom: '1px solid var(--border)',
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: 'var(--text-dim)'
    }
  }, it.id), /*#__PURE__*/React.createElement("span", null, it.slot), /*#__PURE__*/React.createElement("span", {
    className: "mono"
  }, "R", it.rank), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: it.level >= 12 ? 'var(--accent)' : 'var(--text-sub)'
    }
  }, "+", it.level ?? 0), /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-sub)'
    }
  }, ['', 'Common', 'Uncommon', 'Rare', 'Epic', 'Legendary', 'Mythic'][it.rarity] || it.rarity), /*#__PURE__*/React.createElement("span", {
    className: "truncate",
    style: {
      color: 'var(--text-sub)'
    }
  }, it.set || '—'), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: 'var(--accent)'
    }
  }, it.primary || '—'), /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-sub)'
    },
    className: "truncate"
  }, it.rule_name))), filtered.length > 250 && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '10px 0',
      fontSize: 11,
      color: 'var(--text-dim)',
      textAlign: 'center'
    }
  }, "\u2026 ", filtered.length - 250, " more not shown"))));
}
function CBRunDetailModal({
  s,
  lr,
  team,
  totalDealt,
  totalTaken,
  rarityColor,
  onClose
}) {
  const turns = lr && lr.turn_log || [];
  const [expanded, setExpanded] = React.useState(null);
  const maxDmg = turns.reduce((m, t) => Math.max(m, t.damage || 0), 0) || 1;

  // Pull the sim prediction for this team on open. cb_sim runs the Myth-Eater
  // cycle against the actual SPDs/HPs so the user can see where reality
  // diverged from the predicted sync (e.g. UK cast 1 turn later than sim
  // said it should, leaving T19 exposed).
  const [simPred, setSimPred] = React.useState(null);
  React.useEffect(() => {
    let cancelled = false;
    fetch('/api/sim-last-run').then(r => r.json()).then(d => {
      if (!cancelled && !d.error) setSimPred(d);
    }).catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);
  // Build a quick lookup of (boss_turn -> {ukCount, bdCount, alive}) from the sim
  const simByTurn = {};
  if (simPred && simPred.protection_by_turn) {
    for (const [btStr, prot] of Object.entries(simPred.protection_by_turn)) {
      const heroes = Object.values(prot || {});
      simByTurn[parseInt(btStr, 10)] = {
        alive: heroes.filter(h => h.alive).length,
        uk: heroes.filter(h => h.uk).length,
        bd: heroes.filter(h => h.bd).length
      };
    }
  }
  const buffColor = b => /unkillable/i.test(b) ? 'oklch(0.80 0.16 85)' : /counter/i.test(b) ? 'var(--violet)' : /shield|block/i.test(b) ? 'oklch(0.68 0.18 250)' : /heal/i.test(b) ? 'oklch(0.72 0.17 145)' : 'var(--text-sub)';
  const evIcon = {
    hero_turn: '▸',
    debuff: '↓',
    buff: '↑'
  };
  const evColor = {
    hero_turn: 'var(--text-sub)',
    debuff: 'var(--violet)',
    buff: 'oklch(0.80 0.16 85)'
  };
  const debuffMax = Math.max(1, ...Object.values(lr.debuffs_applied || {}));
  return /*#__PURE__*/React.createElement("div", {
    onClick: onClose,
    style: {
      position: 'fixed',
      inset: 0,
      background: 'rgba(0,0,0,0.6)',
      zIndex: 200,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 20
    }
  }, /*#__PURE__*/React.createElement("div", {
    onClick: e => e.stopPropagation(),
    className: "card scroll",
    style: {
      padding: 0,
      width: 1100,
      maxWidth: '96vw',
      maxHeight: '92vh',
      overflow: 'auto',
      background: 'var(--bg-elev)',
      border: '1px solid var(--border-strong)',
      display: 'flex',
      flexDirection: 'column'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '14px 20px',
      borderBottom: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      gap: 14,
      position: 'sticky',
      top: 0,
      background: 'var(--bg-elev)',
      zIndex: 1
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em'
    }
  }, "Clan boss \xB7 last run detail"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 18,
      fontWeight: 500,
      marginTop: 2
    }
  }, team.length, " heroes \xB7 ", lr.turns_total || 0, " boss turns \xB7 ", ((lr.damage || 0) / 1e6).toFixed(2), "M damage")), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement("button", {
    className: "btn",
    onClick: onClose,
    style: {
      height: 28,
      padding: '0 12px'
    }
  }, "Close")), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 20,
      display: 'grid',
      gridTemplateColumns: '1fr 300px',
      gap: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 14,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(6, 1fr)',
      gap: 10
    }
  }, [['Turns', lr.turns_total || 0, 'var(--text)'], ['Damage', `${((lr.damage || 0) / 1e6).toFixed(2)}M`, 'var(--accent)'], ['Taken', `${((lr.damage_taken || 0) / 1e6).toFixed(2)}M`, 'oklch(0.70 0.18 25)'], ['Absorbed', `${((lr.damage_absorbed || 0) / 1e6).toFixed(2)}M`, 'oklch(0.68 0.18 250)'], ['UK saves', (lr.unkillable_triggers != null ? lr.unkillable_triggers : '—') + '×', 'oklch(0.80 0.16 85)'], ['Counters', (lr.counters_total != null ? lr.counters_total : '—') + '×', 'var(--violet)']].map(([lbl, val, col]) => /*#__PURE__*/React.createElement("div", {
    key: lbl,
    style: {
      padding: '10px 12px',
      background: 'var(--bg-subtle)',
      borderRadius: 6,
      border: '1px solid var(--border)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em'
    }
  }, lbl), /*#__PURE__*/React.createElement("div", {
    className: "mono num",
    style: {
      fontSize: 18,
      fontWeight: 600,
      color: col,
      marginTop: 3
    }
  }, val)))), /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 0,
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement(PanelHeader, {
    title: "champion detail",
    right: `${team.length} heroes`
  }), team.map((h, i) => /*#__PURE__*/React.createElement("div", {
    key: h.name,
    style: {
      padding: '10px 14px',
      borderBottom: '1px solid var(--border)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1.2fr 80px 80px 80px 80px 60px',
      gap: 8,
      alignItems: 'center',
      fontSize: 12
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      minWidth: 0,
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement(HeroPortrait, {
    typeId: h.type_id,
    size: 32,
    rarity: {
      Common: 1,
      Uncommon: 2,
      Rare: 3,
      Epic: 4,
      Legendary: 5
    }[h.rarity] || 0,
    name: h.name
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontWeight: 500,
      display: 'flex',
      alignItems: 'center',
      gap: 6
    }
  }, i === 0 && /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 9,
      color: 'var(--accent)',
      border: '1px solid var(--accent)',
      padding: '1px 4px',
      borderRadius: 3
    }
  }, "LEAD"), /*#__PURE__*/React.createElement("span", {
    className: "truncate"
  }, h.name)), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: rarityColor[h.rarity],
      marginTop: 2,
      display: 'flex',
      alignItems: 'center',
      gap: 4
    }
  }, /*#__PURE__*/React.createElement(AffinityIcon, {
    element: h.element,
    size: 11
  }), /*#__PURE__*/React.createElement("span", null, h.rarity, " \xB7 ", h.faction, " \xB7 ", h.role)))), /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: 'right'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      color: 'var(--text-dim)'
    }
  }, "Dealt"), /*#__PURE__*/React.createElement("div", {
    className: "mono num"
  }, (h.dmg_dealt / 1e6).toFixed(2), "M")), /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: 'right'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      color: 'var(--text-dim)'
    }
  }, "Taken"), /*#__PURE__*/React.createElement("div", {
    className: "mono num",
    style: {
      color: 'oklch(0.70 0.18 25)'
    }
  }, (h.dmg_taken / 1e6).toFixed(2), "M")), /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: 'right'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      color: 'var(--text-dim)'
    }
  }, "Absorbed"), /*#__PURE__*/React.createElement("div", {
    className: "mono num",
    style: {
      color: h.absorbed > 0 ? 'oklch(0.68 0.18 250)' : 'var(--text-dim)'
    }
  }, h.absorbed > 0 ? (h.absorbed / 1e6).toFixed(2) + 'M' : '—')), /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: 'right'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      color: 'var(--text-dim)'
    }
  }, "Turns"), /*#__PURE__*/React.createElement("div", {
    className: "mono num"
  }, h.turns)), /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: 'right'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      color: 'var(--text-dim)'
    }
  }, "Counters"), /*#__PURE__*/React.createElement("div", {
    className: "mono num",
    style: {
      color: h.counters > 0 ? 'var(--violet)' : 'var(--text-dim)'
    }
  }, h.counters || '—'))), (h.buffs || []).length > 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 8
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 9.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      marginBottom: 4
    }
  }, "Buffs received during run"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexWrap: 'wrap',
      gap: 4
    }
  }, h.buffs.map(b => {
    const name = typeof b === 'string' ? b : b.name;
    const srcs = typeof b === 'object' ? b.sources || [] : [];
    const selfOnly = srcs.length === 1 && srcs[0] === 'self';
    const fromText = srcs.length ? ' · from ' + srcs.join('/') : '';
    return /*#__PURE__*/React.createElement("span", {
      key: name,
      title: srcs.length ? `Source: ${srcs.join(', ')}` : name,
      style: {
        fontSize: 9.5,
        padding: '1px 6px',
        borderRadius: 3,
        border: `1px solid ${buffColor(name)}`,
        color: buffColor(name),
        textTransform: 'uppercase',
        letterSpacing: '0.03em',
        fontStyle: selfOnly ? 'italic' : 'normal'
      }
    }, name, srcs.length > 0 && /*#__PURE__*/React.createElement("span", {
      style: {
        marginLeft: 4,
        opacity: 0.65,
        textTransform: 'none',
        letterSpacing: 0,
        fontSize: 9
      }
    }, selfOnly ? '(self)' : `← ${srcs.join('/')}`));
  })))))), /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 0,
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement(PanelHeader, {
    title: `turn-by-turn · ${turns.length} boss turns`,
    right: "click a row to expand"
  }), turns.length === 0 ? /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 16,
      fontSize: 12,
      color: 'var(--text-dim)'
    }
  }, "No battle log available.") : turns.map(t => {
    const isOpen = expanded === t.boss_turn;
    const pct = (t.damage || 0) / maxDmg;
    const heroMoves = t.events.filter(e => e.k === 'hero_turn');
    const debuffs = t.events.filter(e => e.k === 'debuff');
    const buffs = t.events.filter(e => e.k === 'buff');
    return /*#__PURE__*/React.createElement("div", {
      key: t.boss_turn,
      style: {
        borderBottom: '1px solid var(--border)'
      }
    }, (() => {
      // Action-type color + protection summary (how many heroes
      // had UK or BD at the moment of boss action).
      const actColor = {
        AOE1: 'oklch(0.68 0.16 30)',
        AOE2: 'oklch(0.60 0.22 10)',
        STUN: 'oklch(0.70 0.18 300)'
      };
      const prot = t.protection || {};
      const protHeroes = Object.keys(prot);
      const ukCount = protHeroes.filter(n => prot[n]?.uk).length;
      const bdCount = protHeroes.filter(n => prot[n]?.bd).length;
      const n = protHeroes.length || 5;
      const protStr = ukCount === 0 && bdCount === 0 ? 'NONE' : [ukCount ? `UK ${ukCount}/${n}` : null, bdCount ? `BD ${bdCount}/${n}` : null].filter(Boolean).join(' · ');
      const protOk = ukCount + bdCount >= n; // covered
      const protColor = protOk ? 'var(--accent)' : ukCount + bdCount > 0 ? 'oklch(0.75 0.13 85)' : 'oklch(0.65 0.23 25)';
      return /*#__PURE__*/React.createElement("div", {
        onClick: () => setExpanded(isOpen ? null : t.boss_turn),
        style: {
          display: 'grid',
          gridTemplateColumns: '44px 56px 1fr 120px 80px 100px 24px',
          gap: 10,
          padding: '8px 14px',
          fontSize: 12,
          alignItems: 'center',
          cursor: 'pointer',
          background: isOpen ? 'var(--bg-hover)' : 'transparent'
        }
      }, /*#__PURE__*/React.createElement("span", {
        className: "mono",
        style: {
          color: 'var(--text-dim)'
        }
      }, "T", t.boss_turn), /*#__PURE__*/React.createElement("span", {
        className: "mono",
        style: {
          fontSize: 10,
          padding: '2px 5px',
          borderRadius: 3,
          border: `1px solid ${actColor[t.boss_action] || 'var(--border)'}`,
          color: actColor[t.boss_action] || 'var(--text-dim)',
          textAlign: 'center'
        }
      }, t.boss_action || '—'), /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'flex',
          gap: 3,
          flexWrap: 'wrap'
        }
      }, heroMoves.map((m, i) => /*#__PURE__*/React.createElement("span", {
        key: i,
        style: {
          fontSize: 10,
          padding: '1px 5px',
          background: 'var(--bg-subtle)',
          borderRadius: 3,
          color: 'var(--text-sub)'
        }
      }, m.by))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
        className: "mono",
        style: {
          color: protColor,
          fontSize: 11,
          fontWeight: 500
        }
      }, protStr), (() => {
        // Sim prediction for this boss turn. Green if sim
        // and actual agree on full coverage; amber when
        // they disagree (prediction divergence).
        const pred = simByTurn[t.boss_turn];
        if (!pred) return null;
        const predOk = pred.uk + pred.bd >= pred.alive;
        const match = predOk === protOk;
        const color = match ? 'var(--text-dim)' : 'oklch(0.75 0.17 85)';
        const predStr = pred.uk === 0 && pred.bd === 0 ? 'NONE' : [pred.uk ? `UK ${pred.uk}/${pred.alive}` : null, pred.bd ? `BD ${pred.bd}/${pred.alive}` : null].filter(Boolean).join(' · ');
        return /*#__PURE__*/React.createElement("span", {
          className: "mono",
          title: "cb_sim prediction for this turn",
          style: {
            fontSize: 9.5,
            color,
            display: 'block',
            marginTop: 1
          }
        }, "sim: ", predStr, !match && ' ⚠');
      })()), /*#__PURE__*/React.createElement("span", {
        className: "mono",
        style: {
          color: debuffs.length ? 'var(--violet)' : 'var(--text-dim)',
          fontSize: 10.5
        }
      }, debuffs.length ? debuffs.length + ' db' : '—'), /*#__PURE__*/React.createElement("div", {
        style: {
          textAlign: 'right'
        }
      }, /*#__PURE__*/React.createElement("div", {
        className: "mono num",
        style: {
          fontSize: 12,
          color: t.damage > 0 ? 'var(--accent)' : 'var(--text-dim)'
        }
      }, t.damage > 0 ? (t.damage / 1e6).toFixed(2) + 'M' : '—'), /*#__PURE__*/React.createElement("div", {
        style: {
          height: 2,
          background: 'var(--bg-subtle)',
          borderRadius: 1,
          marginTop: 2,
          overflow: 'hidden'
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          width: `${pct * 100}%`,
          height: '100%',
          background: 'var(--accent)'
        }
      }))), /*#__PURE__*/React.createElement("span", {
        style: {
          color: 'var(--text-dim)',
          fontSize: 10,
          textAlign: 'center'
        }
      }, isOpen ? '▾' : '▸'));
    })(), isOpen && /*#__PURE__*/React.createElement("div", {
      style: {
        padding: '10px 18px 14px 58px',
        background: 'var(--bg-subtle)',
        fontSize: 11.5
      }
    }, t.events.length === 0 ? /*#__PURE__*/React.createElement("span", {
      style: {
        color: 'var(--text-dim)'
      }
    }, "(no recorded events)") : /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: '16px 1fr',
        gap: '4px 8px',
        alignItems: 'start'
      }
    }, t.events.map((ev, i) => /*#__PURE__*/React.createElement(React.Fragment, {
      key: i
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        color: evColor[ev.k] || 'var(--text-dim)',
        fontFamily: 'monospace'
      }
    }, evIcon[ev.k] || '·'), /*#__PURE__*/React.createElement("span", {
      style: {
        color: evColor[ev.k] || 'var(--text-sub)'
      }
    }, ev.k === 'hero_turn' && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", {
      style: {
        color: 'var(--text)'
      }
    }, ev.by), " takes a turn"), ev.k === 'debuff' && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", {
      style: {
        color: 'var(--text)'
      }
    }, ev.by), " applies ", /*#__PURE__*/React.createElement("b", null, ev.name)), ev.k === 'buff' && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("b", null, ev.name), " gained by ", /*#__PURE__*/React.createElement("span", {
      style: {
        color: 'var(--text)'
      }
    }, ev.on))))))));
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-title",
    style: {
      marginBottom: 10
    }
  }, "Debuffs on boss"), Object.keys(lr.debuffs_applied || {}).length === 0 ? /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11.5,
      color: 'var(--text-dim)'
    }
  }, "No debuff data for this run.") : Object.entries(lr.debuffs_applied || {}).map(([d, n]) => /*#__PURE__*/React.createElement("div", {
    key: d,
    style: {
      marginBottom: 7
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      fontSize: 11.5,
      marginBottom: 3
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-sub)'
    }
  }, d), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: 'var(--text)'
    }
  }, n, "\xD7")), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 3,
      background: 'var(--bg-subtle)',
      borderRadius: 2,
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: `${n / debuffMax * 100}%`,
      height: '100%',
      background: 'var(--violet)'
    }
  }))))), /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-title",
    style: {
      marginBottom: 10
    }
  }, "Timeline"), (lr.timeline || []).length === 0 ? /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11.5,
      color: 'var(--text-dim)'
    }
  }, "No major events.") : (lr.timeline || []).map((t, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      display: 'grid',
      gridTemplateColumns: '40px 1fr',
      gap: 8,
      padding: '5px 0',
      fontSize: 11.5,
      alignItems: 'baseline',
      borderTop: i > 0 ? '1px dashed var(--border)' : 'none'
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: 'var(--text-dim)',
      fontSize: 10.5
    }
  }, "T", t.t), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", null, t.ev), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)'
    },
    className: "mono"
  }, t.by)))))))));
}
function CBHistoryPanel({
  history,
  perKey
}) {
  // Full-width 7-day CB damage panel. When per-key data is available, each key
  // entry is {damage, turns, team, time, iso_time, file}; hover reveals details.
  const stackedHist = Array.isArray(perKey) && perKey.length ? perKey : null;
  const flatHist = Array.isArray(history) && history.length ? history : [];
  // Normalise key entries to always be objects with a damage field so tooltip
  // logic doesn't have to handle two shapes.
  const toKeyObjs = arr => (arr || []).map(k => typeof k === 'number' ? {
    damage: k
  } : k);
  const data = stackedHist ? stackedHist.map(h => ({
    ...h,
    keys: toKeyObjs(h.keys)
  })) : flatHist.map(h => ({
    date: h.day,
    day: h.day,
    total: h.dmg,
    keys: h.dmg > 0 ? [{
      damage: h.dmg
    }] : []
  }));
  const maxTotal = data.reduce((m, h) => Math.max(m, h.total || 0), 0) || 1;
  const barH = 160;
  const avg = data.length ? data.reduce((a, h) => a + (h.total || 0), 0) / data.length : 0;
  const best = data.reduce((m, h) => (h.total || 0) > (m.total || 0) ? h : m, data[0] || {
    total: 0
  });
  const todayTotal = data.length ? data[data.length - 1].total || 0 : 0;
  const [hover, setHover] = React.useState(null); // {dayIdx, keyIdx, clientX, clientY}

  return /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 0,
      gridColumn: '1 / -1',
      overflow: 'visible',
      position: 'relative'
    }
  }, /*#__PURE__*/React.createElement(PanelHeader, {
    title: "7-day clan boss damage",
    right: `${data.filter(h => h.total > 0).length} windows with data`
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '18px 22px',
      display: 'grid',
      gridTemplateColumns: '1fr 220px',
      gap: 20,
      alignItems: 'stretch'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'flex-end',
      gap: 14,
      minHeight: barH + 52
    }
  }, data.map((h, i) => {
    const isToday = i === data.length - 1;
    const pct = h.total ? Math.max(0.025, h.total / maxTotal) : 0;
    const keys = h.keys || [];
    const baseColor = isToday ? 'var(--accent)' : 'var(--border-strong)';
    const altColor = isToday ? 'oklch(0.72 0.17 150)' : 'oklch(0.55 0.08 250)';
    return /*#__PURE__*/React.createElement("div", {
      key: h.day + '-' + i,
      style: {
        flex: '1 1 0',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 6,
        minWidth: 44
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 12,
        fontWeight: 600,
        color: isToday ? 'var(--accent)' : h.total > 0 ? 'var(--text)' : 'var(--text-dim)',
        lineHeight: 1
      },
      className: "mono num"
    }, h.total > 0 ? (h.total / 1e6).toFixed(1) + 'M' : '—'), /*#__PURE__*/React.createElement("div", {
      style: {
        width: '100%',
        maxWidth: 80,
        height: barH,
        display: 'flex',
        alignItems: 'end'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        width: '100%',
        height: `${pct * 100}%`,
        display: 'flex',
        flexDirection: 'column-reverse',
        borderRadius: 4,
        overflow: 'hidden',
        border: h.total > 0 ? 'none' : '1px dashed var(--border)'
      }
    }, keys.map((k, idx) => /*#__PURE__*/React.createElement("div", {
      key: idx,
      onMouseEnter: e => setHover({
        dayIdx: i,
        keyIdx: idx,
        x: e.clientX,
        y: e.clientY
      }),
      onMouseMove: e => setHover({
        dayIdx: i,
        keyIdx: idx,
        x: e.clientX,
        y: e.clientY
      }),
      onMouseLeave: () => setHover(null),
      style: {
        width: '100%',
        flex: k.damage || 1,
        background: idx % 2 === 0 ? baseColor : altColor,
        borderTop: idx > 0 ? '1px solid rgba(0,0,0,0.45)' : 'none',
        minHeight: 3,
        cursor: 'pointer',
        transition: 'filter 0.12s',
        filter: hover && hover.dayIdx === i && hover.keyIdx === idx ? 'brightness(1.25)' : 'none'
      }
    })))), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 11,
        color: isToday ? 'var(--accent)' : 'var(--text-sub)',
        lineHeight: 1
      },
      className: "mono"
    }, h.day), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 10,
        color: 'var(--text-dim)',
        lineHeight: 1
      },
      className: "mono"
    }, keys.length ? `${keys.length} key${keys.length !== 1 ? 's' : ''}` : '—'));
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'space-around',
      gap: 10,
      paddingLeft: 18,
      borderLeft: '1px solid var(--border)'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em'
    }
  }, "Today"), /*#__PURE__*/React.createElement("div", {
    className: "mono num",
    style: {
      fontSize: 22,
      fontWeight: 600,
      color: 'var(--accent)',
      marginTop: 2
    }
  }, todayTotal > 0 ? (todayTotal / 1e6).toFixed(2) + 'M' : '—')), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em'
    }
  }, "7-day avg"), /*#__PURE__*/React.createElement("div", {
    className: "mono num",
    style: {
      fontSize: 18,
      fontWeight: 600,
      marginTop: 2
    }
  }, (avg / 1e6).toFixed(2), "M")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em'
    }
  }, "Best day"), /*#__PURE__*/React.createElement("div", {
    className: "mono num",
    style: {
      fontSize: 16,
      fontWeight: 600,
      marginTop: 2
    }
  }, (best.total || 0) > 0 ? `${(best.total / 1e6).toFixed(2)}M · ${best.day}` : '—')))), hover && (() => {
    const h = data[hover.dayIdx];
    const k = h && h.keys && h.keys[hover.keyIdx];
    if (!k) return null;
    const keyIndex = hover.keyIdx + 1;
    const totalKeys = h.keys.length;
    // Position tooltip near cursor, fixed to viewport
    const tipX = Math.min(hover.x + 14, window.innerWidth - 320);
    const tipY = Math.min(hover.y - 10, window.innerHeight - 220);
    return /*#__PURE__*/React.createElement("div", {
      style: {
        position: 'fixed',
        left: tipX,
        top: tipY,
        zIndex: 500,
        background: 'var(--bg-elev)',
        border: '1px solid var(--border-strong)',
        borderRadius: 8,
        padding: '12px 14px',
        minWidth: 240,
        maxWidth: 320,
        boxShadow: '0 10px 30px rgba(0,0,0,0.45)',
        pointerEvents: 'none'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 8
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 10.5,
        color: 'var(--text-dim)',
        textTransform: 'uppercase',
        letterSpacing: '0.06em'
      }
    }, h.day, " \xB7 Key ", keyIndex, "/", totalKeys), k.time && /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        fontSize: 10.5,
        color: 'var(--text-dim)'
      }
    }, k.time)), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'baseline',
        gap: 8,
        marginBottom: 10
      }
    }, /*#__PURE__*/React.createElement("span", {
      className: "mono num",
      style: {
        fontSize: 22,
        fontWeight: 600,
        color: 'var(--accent)'
      }
    }, (k.damage / 1e6).toFixed(2), "M"), k.turns && /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 11,
        color: 'var(--text-sub)'
      }
    }, "\xB7 ", k.turns, " turns")), k.team && k.team.length > 0 ? /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 10,
        color: 'var(--text-dim)',
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
        marginBottom: 4
      }
    }, "Team"), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexWrap: 'wrap',
        gap: 4
      }
    }, k.team.map((name, i) => /*#__PURE__*/React.createElement("span", {
      key: i,
      style: {
        fontSize: 10.5,
        padding: '2px 6px',
        background: 'var(--bg-subtle)',
        border: '1px solid var(--border)',
        borderRadius: 3,
        color: i === 0 ? 'var(--accent)' : 'var(--text-sub)'
      }
    }, i === 0 ? '★ ' : '', name)))) : /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 10.5,
        color: 'var(--text-dim)'
      }
    }, "team composition not recorded"));
  })());
}
const filterSel = {
  background: 'var(--bg-subtle)',
  border: '1px solid var(--border)',
  borderRadius: 4,
  padding: '3px 6px',
  fontSize: 11,
  color: 'var(--text)',
  fontFamily: 'inherit'
};
const filterLbl = {
  fontSize: 10.5,
  color: 'var(--text-dim)',
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  marginLeft: 4
};

/* ============== Gear gaps helpers (used by PageHeroes 'gaps' tab) ============== */

const _th = {
  padding: '8px 10px',
  textAlign: 'left',
  fontSize: 10.5,
  color: 'var(--text-sub)',
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
  fontWeight: 600
};
const _td = {
  padding: '6px 10px',
  color: 'var(--text)'
};
function GapTable({
  title,
  rows,
  cols
}) {
  return /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 0,
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '8px 12px',
      borderBottom: '1px solid var(--border)',
      background: 'var(--bg-subtle)',
      fontSize: 10.5,
      color: 'var(--text-sub)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      fontWeight: 600
    }
  }, title), /*#__PURE__*/React.createElement("table", {
    style: {
      width: '100%',
      borderCollapse: 'collapse',
      fontSize: 12
    }
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", {
    style: {
      borderBottom: '1px solid var(--border)',
      background: 'var(--bg-subtle)'
    }
  }, cols.map((c, i) => /*#__PURE__*/React.createElement("th", {
    key: i,
    style: {
      ..._th,
      textAlign: c.align || 'left'
    }
  }, c.h)))), /*#__PURE__*/React.createElement("tbody", null, rows.map((r, ri) => /*#__PURE__*/React.createElement("tr", {
    key: ri,
    style: {
      borderBottom: '1px solid var(--border)'
    }
  }, cols.map((c, i) => /*#__PURE__*/React.createElement("td", {
    key: i,
    style: {
      ..._td,
      textAlign: c.align || 'left',
      ...(c.color ? {
        color: c.color(r)
      } : null),
      ...(c.bold ? {
        fontWeight: 600
      } : null)
    },
    className: c.mono ? 'mono' : undefined
  }, c.v(r))))))));
}
function TopAreas({
  areas
}) {
  return /*#__PURE__*/React.createElement("span", null, (areas || []).map((a, i) => /*#__PURE__*/React.createElement("span", {
    key: i,
    style: {
      marginRight: 8,
      color: 'var(--text-dim)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-sub)'
    }
  }, a.area), /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: 3
    }
  }, a.demand))));
}
function PageEvents({
  s
}) {
  const [liveEvents, setLiveEvents] = React.useState(null);
  const [err, setErr] = React.useState(null);
  React.useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const r = await fetch('/api/events', {
          cache: 'no-store'
        });
        if (!alive) return;
        if (r.ok) {
          const j = await r.json();
          setLiveEvents(j.events || []);
          if (j.error) setErr(j.error);
        }
      } catch (e) {
        setErr(String(e));
      }
    };
    tick();
    const id = setInterval(tick, 30000); // events change slowly
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);
  const events = liveEvents && liveEvents.length ? liveEvents : s.events;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 320px',
      gap: 10,
      minHeight: '100%'
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card scroll",
    style: {
      padding: 20,
      overflow: 'auto'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginBottom: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-title"
  }, "Active events \xB7 solo & tournaments"), /*#__PURE__*/React.createElement("span", {
    className: "chip",
    style: {
      background: liveEvents ? 'var(--accent-soft)' : 'var(--bg-subtle)',
      color: liveEvents ? 'var(--accent)' : 'var(--text-dim)',
      borderColor: 'transparent'
    }
  }, liveEvents ? `${liveEvents.length} live` : 'sim')), err && /*#__PURE__*/React.createElement("div", {
    style: {
      color: 'var(--red)',
      fontSize: 11,
      marginBottom: 8
    }
  }, err), events.map(e => /*#__PURE__*/React.createElement("div", {
    key: e.name,
    style: {
      padding: '14px 0',
      borderBottom: '1px solid var(--border)',
      opacity: e.upcoming ? 0.55 : 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'baseline',
      marginBottom: 6
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 15,
      fontWeight: 500
    }
  }, e.name), /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 11,
      color: 'var(--text-dim)'
    }
  }, e.ends_in)), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      color: 'var(--text-sub)',
      marginBottom: 8
    }
  }, e.reward, " \xB7 ", e.type), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 5,
      background: 'var(--bg-subtle)',
      borderRadius: 3,
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: `${e.progress * 100}%`,
      height: '100%',
      background: e.type === 'tournament' ? 'var(--violet)' : 'var(--accent)'
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      fontSize: 10.5,
      color: 'var(--text-dim)',
      marginTop: 4
    },
    className: "mono"
  }, /*#__PURE__*/React.createElement("span", null, Math.round(e.progress * 100), "% to next tier"), /*#__PURE__*/React.createElement("span", null, e.upcoming ? 'upcoming' : 'active'))))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateRows: 'auto auto 1fr',
      gap: 10,
      minHeight: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-title",
    style: {
      marginBottom: 10
    }
  }, "Farming routing"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12.5,
      marginBottom: 6
    }
  }, "Dragon 20 \u2192 Dungeon Divers + Tournament"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: 'var(--text-sub)'
    }
  }, "Picked by ", /*#__PURE__*/React.createElement("span", {
    className: "mono"
  }, "_detect_best_dungeon()"))), /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-title",
    style: {
      marginBottom: 10
    }
  }, "Energy policy"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11.5,
      color: 'var(--text-sub)',
      lineHeight: 1.7
    }
  }, /*#__PURE__*/React.createElement("div", null, "Floor \xB7 1,000"), /*#__PURE__*/React.createElement("div", null, "Cap \xB7 130 (overflow loss)"), /*#__PURE__*/React.createElement("div", null, "Burn only during events"))), /*#__PURE__*/React.createElement(PanelArena, {
    s: s
  })));
}
function PageHistory({
  s
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateRows: '1fr 1fr',
      gap: 10,
      minHeight: '100%'
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 16,
      display: 'flex',
      flexDirection: 'column',
      minHeight: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-title",
    style: {
      marginBottom: 10
    }
  }, "14-day earnings"), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: 'flex',
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement(HistoryChartB, {
    data: s.history,
    height: 200
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 16,
      fontSize: 11,
      color: 'var(--text-sub)',
      marginTop: 8
    }
  }, /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-block',
      width: 8,
      height: 8,
      borderRadius: 2,
      background: 'var(--accent)',
      marginRight: 5
    }
  }), "Gems"), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-block',
      width: 8,
      height: 8,
      borderRadius: 2,
      background: 'var(--violet)',
      marginRight: 5
    }
  }), "Silver (M)"), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-block',
      width: 8,
      height: 8,
      borderRadius: 2,
      background: 'oklch(0.82 0.17 85)',
      marginRight: 5
    }
  }), "CB dmg (M)"))), /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 0,
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      minHeight: 0
    }
  }, /*#__PURE__*/React.createElement(PanelHeader, {
    title: "daily log",
    right: `${s.history.length} days`
  }), /*#__PURE__*/React.createElement("div", {
    className: "scroll",
    style: {
      overflowY: 'auto',
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(5, 1fr)',
      padding: '8px 16px',
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      borderBottom: '1px solid var(--border)',
      background: 'var(--bg-subtle)'
    }
  }, /*#__PURE__*/React.createElement("span", null, "Day"), /*#__PURE__*/React.createElement("span", null, "Gems"), /*#__PURE__*/React.createElement("span", null, "Silver"), /*#__PURE__*/React.createElement("span", null, "Energy"), /*#__PURE__*/React.createElement("span", null, "CB dmg")), [...s.history].reverse().map(h => /*#__PURE__*/React.createElement("div", {
    key: h.day,
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(5, 1fr)',
      padding: '7px 16px',
      fontSize: 12,
      borderBottom: '1px solid var(--border)'
    },
    className: "mono"
  }, /*#__PURE__*/React.createElement("span", null, h.day), /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--accent)'
    }
  }, h.gems), /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--violet)'
    }
  }, h.silver_m != null ? h.silver_m.toFixed(1) + 'M' : '—'), /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'oklch(0.72 0.16 85)'
    }
  }, h.energy != null ? h.energy.toLocaleString() : '—'), /*#__PURE__*/React.createElement("span", {
    style: {
      color: h.cb_dmg_m > 0 ? 'oklch(0.82 0.17 85)' : 'var(--text-dim)'
    }
  }, h.cb_dmg_m > 0 ? h.cb_dmg_m.toFixed(1) + 'M' : '—'))))));
}
function PageMod({
  s
}) {
  const [info, setInfo] = React.useState(null);
  const [err, setErr] = React.useState(null);
  React.useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const r = await fetch('/api/mod-info', {
          cache: 'no-store'
        });
        if (!alive) return;
        if (r.ok) setInfo(await r.json());
      } catch (e) {
        setErr(String(e));
      }
    };
    tick();
    const id = setInterval(tick, 5000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);
  const status = info && info.status;
  const dll = info && info.plugin_dll;
  const hd = info && info.hook_diag;
  const patches = hd && hd.patches || [];
  const cmdClasses = hd && hd.cmd_classes || {};
  const modAlive = !!status;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gap: 10,
      minHeight: '100%'
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 18
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-title",
    style: {
      marginBottom: 12
    }
  }, "BepInEx plugin"), /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 12,
      lineHeight: 1.8,
      color: 'var(--text-sub)'
    }
  }, /*#__PURE__*/React.createElement("div", null, "RaidAutomationPlugin.dll", dll && /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-dim)'
    }
  }, " \xB7 ", dll.size.toLocaleString(), " bytes")), dll && /*#__PURE__*/React.createElement("div", null, "SHA-256 \xB7 ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--accent)'
    }
  }, dll.sha256_short)), dll && /*#__PURE__*/React.createElement("div", null, "Modified \xB7 ", /*#__PURE__*/React.createElement("span", {
    className: "mono"
  }, new Date(dll.modified * 1000).toLocaleString())), /*#__PURE__*/React.createElement("div", null, "HTTP \xB7 ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--accent)'
    }
  }, info && info.mod_url || 'localhost:6790')), status && /*#__PURE__*/React.createElement("div", null, "Scene \xB7 ", /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: 'var(--accent)'
    }
  }, status.scene)), status && /*#__PURE__*/React.createElement("div", null, "Logged-in \xB7 ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: status.logged_in ? 'var(--ok)' : 'var(--red)'
    }
  }, String(status.logged_in))), /*#__PURE__*/React.createElement("div", {
    style: {
      color: modAlive ? 'var(--ok)' : 'var(--red)',
      marginTop: 6
    }
  }, "\u25CF ", modAlive ? 'mod online' : 'mod offline'), info && info.status_error && /*#__PURE__*/React.createElement("div", {
    style: {
      color: 'var(--red)',
      fontSize: 10.5
    }
  }, info.status_error))), /*#__PURE__*/React.createElement("div", {
    className: "card scroll",
    style: {
      padding: 18,
      maxHeight: 360,
      overflowY: 'auto'
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-title",
    style: {
      marginBottom: 12
    }
  }, "Harmony patches (", patches.length, ")"), patches.length === 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: 'var(--text-dim)'
    }
  }, "No patch data (mod may be offline)"), /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 10.5,
      lineHeight: 1.7,
      color: 'var(--text-sub)'
    }
  }, patches.map((p, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      color: /err|fail/i.test(p) ? 'var(--red)' : 'var(--text-sub)'
    }
  }, p)))), /*#__PURE__*/React.createElement("div", {
    className: "card scroll",
    style: {
      padding: 18,
      gridColumn: 'span 2',
      maxHeight: 220,
      overflowY: 'auto'
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-title",
    style: {
      marginBottom: 12
    }
  }, "Cmd classes seen (", Object.keys(cmdClasses).length, ")"), /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 10.5,
      lineHeight: 1.7,
      color: 'var(--text-sub)',
      columnCount: 2,
      columnGap: 24
    }
  }, Object.entries(cmdClasses).sort((a, b) => b[1] - a[1]).map(([n, c]) => /*#__PURE__*/React.createElement("div", {
    key: n
  }, n, " ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-dim)'
    }
  }, "\xB7 ", c))))), /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 18,
      gridColumn: 'span 2'
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-title",
    style: {
      marginBottom: 12
    }
  }, "VM \xB7 ", s.vm.host), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(4, 1fr)',
      gap: 16
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase'
    }
  }, "Host"), /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 13,
      marginTop: 4
    }
  }, s.vm.host)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase'
    }
  }, "IP"), /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 13,
      marginTop: 4
    }
  }, s.vm.ip)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase'
    }
  }, "CPU"), /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 13,
      marginTop: 4,
      color: 'var(--accent)'
    }
  }, Math.round(s.vm.cpu), "%")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase'
    }
  }, "RAM"), /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 13,
      marginTop: 4
    }
  }, s.vm.ram.toFixed(1), " / ", s.vm.ramMax, " GB")))));
}
function ScheduleCard() {
  const [tasks, setTasks] = React.useState(null);
  const [err, setErr] = React.useState(null);
  const [name, setName] = React.useState('');
  const [time, setTime] = React.useState('07:00');
  const [cmd, setCmd] = React.useState('python tools/cb_daily.py --wait');
  const [busy, setBusy] = React.useState(false);
  const load = React.useCallback(async () => {
    try {
      const r = await fetch('/api/schedule');
      const d = await r.json();
      setTasks(d.tasks || []);
      setErr(null);
    } catch (e) {
      setErr(String(e));
    }
  }, []);
  React.useEffect(() => {
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [load]);
  const add = async () => {
    setBusy(true);
    setErr(null);
    try {
      const r = await fetch('/api/schedule', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          name,
          time,
          command: cmd
        })
      });
      const d = await r.json();
      if (r.ok && d.ok) {
        setName('');
        load();
      } else setErr(d.message || d.error || 'create failed');
    } catch (e) {
      setErr(String(e));
    }
    setBusy(false);
  };
  const del = async n => {
    if (!confirm(`Delete \\PyAutoRaid\\${n}?`)) return;
    try {
      const r = await fetch('/api/schedule/' + encodeURIComponent(n), {
        method: 'DELETE'
      });
      const d = await r.json();
      if (!d.ok) setErr(d.message || d.error);
      load();
    } catch (e) {
      setErr(String(e));
    }
  };
  const toggle = async (n, enabled) => {
    try {
      const r = await fetch('/api/schedule/' + encodeURIComponent(n) + '/toggle', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          enabled
        })
      });
      const d = await r.json();
      if (!d.ok) setErr(d.message || d.error);
      load();
    } catch (e) {
      setErr(String(e));
    }
  };
  const input = {
    background: 'var(--bg-subtle)',
    border: '1px solid var(--border)',
    borderRadius: 5,
    padding: '5px 8px',
    fontSize: 12,
    fontFamily: "'JetBrains Mono', monospace",
    color: 'var(--text)',
    outline: 'none'
  };
  const fmtTime = iso => {
    if (!iso || !iso.includes('T')) return iso || '—';
    return iso.split('T')[1].slice(0, 5);
  };
  return /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginBottom: 10
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-title"
  }, "Windows Task Scheduler"), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)'
    }
  }, "\\PyAutoRaid\\")), err && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: 'var(--danger)',
      marginBottom: 8,
      wordBreak: 'break-word'
    }
  }, err), tasks === null && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: 'var(--text-dim)'
    }
  }, "Loading\u2026"), Array.isArray(tasks) && tasks.length === 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: 'var(--text-dim)',
      marginBottom: 10
    }
  }, "No triggers in \\PyAutoRaid\\"), Array.isArray(tasks) && tasks.map(t => /*#__PURE__*/React.createElement("div", {
    key: t.name,
    style: {
      display: 'grid',
      gridTemplateColumns: '14px 1fr 46px 20px',
      gap: 8,
      alignItems: 'center',
      padding: '6px 0',
      borderBottom: '1px solid var(--border)',
      opacity: t.enabled ? 1 : 0.55
    }
  }, /*#__PURE__*/React.createElement("div", {
    onClick: () => toggle(t.name, !t.enabled),
    title: t.enabled ? 'Disable' : 'Enable',
    style: {
      width: 14,
      height: 14,
      borderRadius: 3,
      border: '1px solid',
      borderColor: t.enabled ? 'var(--accent)' : 'var(--border-strong)',
      background: t.enabled ? 'var(--accent-soft)' : 'transparent',
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    }
  }, t.enabled && /*#__PURE__*/React.createElement(SvgIcon.check, {
    style: {
      color: 'var(--accent)',
      opacity: 0.85
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      fontWeight: 500
    }
  }, t.name), /*#__PURE__*/React.createElement("div", {
    className: "mono truncate",
    style: {
      fontSize: 10,
      color: 'var(--text-dim)'
    }
  }, (t.execute || '') + (t.arguments ? ' ' + t.arguments : ''))), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 11,
      color: 'var(--text-sub)',
      textAlign: 'right'
    }
  }, fmtTime(t.startBoundary)), /*#__PURE__*/React.createElement("button", {
    onClick: () => del(t.name),
    className: "btn ghost",
    title: "Delete",
    style: {
      width: 20,
      height: 20,
      padding: 0,
      fontSize: 14,
      lineHeight: 1,
      color: 'var(--danger)'
    }
  }, "\xD7"))), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 12,
      paddingTop: 12,
      borderTop: '1px solid var(--border)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-title",
    style: {
      marginBottom: 8
    }
  }, "Add trigger"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 110px',
      gap: 6,
      marginBottom: 6
    }
  }, /*#__PURE__*/React.createElement("input", {
    type: "text",
    placeholder: "name",
    value: name,
    onChange: e => setName(e.target.value.replace(/[^A-Za-z0-9_\-]/g, '')),
    style: input
  }), /*#__PURE__*/React.createElement("input", {
    type: "time",
    value: time,
    onChange: e => setTime(e.target.value),
    style: input
  })), /*#__PURE__*/React.createElement("input", {
    type: "text",
    placeholder: "command",
    value: cmd,
    onChange: e => setCmd(e.target.value),
    style: {
      ...input,
      width: '100%',
      marginBottom: 6
    }
  }), /*#__PURE__*/React.createElement("button", {
    className: "btn primary",
    onClick: add,
    disabled: busy || !name || !cmd,
    style: {
      width: '100%',
      height: 26,
      fontSize: 12,
      justifyContent: 'center'
    }
  }, busy ? 'Adding…' : 'Add trigger')));
}

// ============================================================================
// CBTuneLab — runnable DWJ tunes from /api/tune-lab. Click a tune to open a
// modal with per-affinity sim drilldown + DWJ-parity cast timeline.
// ============================================================================
function CBTuneLab() {
  const [lab, setLab] = React.useState(null); // {today_affinity, tunes}
  const [openSlug, setOpenSlug] = React.useState(null);
  React.useEffect(() => {
    // Guard against setState-after-unmount, and surface fetch/parse failures
    // as a visible error instead of an eternal "Loading tunes…" (the previous
    // code had no .catch, so any failure hung the panel silently).
    let alive = true;
    fetch('/api/tune-lab?runnable_only=1').then(r => {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    }).then(d => {
      if (alive) setLab(d);
    }).catch(e => {
      if (alive) setLab({
        error: 'tune-lab load failed: ' + e.message
      });
    });
    return () => {
      alive = false;
    };
  }, []);
  const openTune = lab?.tunes?.find(t => t.tune_slug === openSlug) || null;
  return /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 0,
      gridColumn: '1 / -1',
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement(PanelHeader, {
    title: "tune lab",
    right: lab ? `${lab.runnable}/${lab.total} runnable · today ${lab.today_affinity}` : 'loading…'
  }), !lab && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 14,
      fontSize: 11,
      color: 'var(--text-dim)'
    }
  }, "Loading tunes\u2026"), lab?.error && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 14,
      fontSize: 11,
      color: 'var(--danger)'
    }
  }, lab.error), lab?.tunes && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(2, 1fr)',
      gap: 1,
      background: 'var(--border)'
    }
  }, lab.tunes.map(t => {
    const sim = t.sim || {};
    const dmg = sim.total_damage || 0;
    const partial = sim.partial;
    const variantLabel = t.calc_variant || '—';
    return /*#__PURE__*/React.createElement("div", {
      key: t.tune_slug,
      onClick: () => setOpenSlug(t.tune_slug),
      style: {
        padding: 14,
        background: 'var(--bg-elev)',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        cursor: 'pointer'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'baseline',
        justifyContent: 'space-between',
        gap: 8
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 14,
        fontWeight: 500
      }
    }, t.tune_name), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        alignItems: 'baseline',
        gap: 5
      }
    }, partial ? /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 10,
        color: 'var(--warn)'
      }
    }, "partial team") : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", {
      className: "num mono",
      style: {
        fontSize: 18,
        fontWeight: 600,
        color: 'var(--accent)'
      }
    }, (dmg / 1e6).toFixed(1)), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 10,
        color: 'var(--text-sub)'
      }
    }, "M today")))), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        gap: 6,
        flexWrap: 'wrap'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 9,
        padding: '1px 5px',
        background: 'var(--bg-subtle)',
        border: '1px solid var(--border)',
        borderRadius: 3,
        color: 'var(--text-sub)'
      }
    }, variantLabel), t.todos?.length > 0 && /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 9,
        padding: '1px 5px',
        background: 'var(--bg-subtle)',
        border: '1px solid var(--border)',
        borderRadius: 3,
        color: 'var(--text-dim)'
      }
    }, t.todos.length, " todo", t.todos.length === 1 ? '' : 's'), sim.warnings > 0 && /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 9,
        padding: '1px 5px',
        background: 'var(--bg-subtle)',
        border: '1px solid var(--border)',
        borderRadius: 3,
        color: 'var(--warn)'
      }
    }, sim.warnings, " sim warning", sim.warnings === 1 ? '' : 's')), t.potential_team?.team && /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: '1fr 60px',
        gap: 4,
        fontSize: 10.5,
        lineHeight: 1.5
      }
    }, t.potential_team.team.map((sl, i) => /*#__PURE__*/React.createElement(React.Fragment, {
      key: i
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 4,
        color: sl.is_generic ? 'var(--text-dim)' : 'var(--text)'
      }
    }, !sl.is_generic && /*#__PURE__*/React.createElement(HeroPortrait, {
      typeId: sl.type_id,
      size: 18,
      grade: sl.owned_grade
    }), /*#__PURE__*/React.createElement("span", {
      style: {
        overflow: 'hidden',
        textOverflow: 'ellipsis'
      }
    }, sl.hero, sl.owned_grade ? ` ${sl.owned_grade}★` : '')), /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        color: 'var(--text-sub)',
        textAlign: 'right',
        fontSize: 10
      }
    }, "SPD ", sl.target_speed)))));
  })), openTune && /*#__PURE__*/React.createElement(CBTuneLabModal, {
    tune: openTune,
    onClose: () => setOpenSlug(null)
  }));
}

// ============================================================================
// CBTuneLabModal — opened by CBTuneLab. Per-affinity sim drilldown for one tune
// + DWJ-parity cast timeline. Re-fetches /api/tune-lab on affinity tab switch.
// ============================================================================
function CBTuneLabModal({
  tune,
  onClose
}) {
  const [affinity, setAffinity] = React.useState(tune.today_affinity || 'void');
  const [affTune, setAffTune] = React.useState(tune);
  const [affBusy, setAffBusy] = React.useState(false);
  const [parity, setParity] = React.useState(null);
  const [parityBusy, setParityBusy] = React.useState(false);
  const [gearPlan, setGearPlan] = React.useState(null);
  const [gearBusy, setGearBusy] = React.useState(false);
  const [slotAlts, setSlotAlts] = React.useState(null);
  const [slotBusy, setSlotBusy] = React.useState(false);
  const slug = tune.tune_slug;
  const hash = affTune.calc_variant_hash || tune.calc_variant_hash;

  // Refetch tune-lab when affinity tab changes (so calc variant + sim
  // both re-pick for the selected affinity).
  React.useEffect(() => {
    setAffBusy(true);
    fetch(`/api/tune-lab?slug=${encodeURIComponent(slug)}&affinity=${affinity}`).then(r => r.json()).then(d => {
      const t = (d.tunes || [])[0];
      if (t) setAffTune(t);
      setAffBusy(false);
    }).catch(() => setAffBusy(false));
  }, [slug, affinity]);

  // Load DWJ-parity cast timeline for the selected variant hash.
  React.useEffect(() => {
    if (!hash) {
      console.log('[timeline] no hash, skipping');
      setParity(null);
      return;
    }
    const t0 = performance.now();
    console.log('[timeline] fetch start hash=', hash);
    setParityBusy(true);
    let alive = true;
    fetch(`/api/calc-parity-sim?hash=${encodeURIComponent(hash)}&turns=20`).then(r => r.json()).then(d => {
      console.log('[timeline] resolved in', Math.round(performance.now() - t0), 'ms; error=', d.error, 'tl=', (d.timeline || []).length, 'alive=', alive);
      if (!alive) return;
      if (!d.error) setParity(d);
      setParityBusy(false);
    }).catch(e => {
      console.log('[timeline] FETCH ERROR', e.message);
      if (alive) setParityBusy(false);
    });
    return () => {
      console.log('[timeline] cleanup (unmount/hash-change)');
      alive = false;
    };
  }, [hash]);

  // Lazy-load the gear plan for this tune. Uses a 500-iter SA budget
  // (~8s first call, instant from cache thereafter). Doesn't block the
  // rest of the modal.
  React.useEffect(() => {
    if (!slug) return;
    setGearBusy(true);
    fetch(`/api/tune-gear-plan?slug=${encodeURIComponent(slug)}`).then(r => r.json()).then(d => {
      setGearPlan(d);
      setGearBusy(false);
    }).catch(() => setGearBusy(false));
  }, [slug]);

  // Lazy-load generic-slot alternatives. Refetches when affinity changes
  // since damage rankings shift per affinity.
  React.useEffect(() => {
    if (!slug) return;
    setSlotBusy(true);
    fetch(`/api/tune-slot-alternatives?slug=${encodeURIComponent(slug)}&affinity=${affinity}&top=5`).then(r => r.json()).then(d => {
      setSlotAlts(d);
      setSlotBusy(false);
    }).catch(() => setSlotBusy(false));
  }, [slug, affinity]);
  const sim = affTune.sim || {};
  const todos = affTune.todos || [];
  return /*#__PURE__*/React.createElement("div", {
    onClick: onClose,
    style: {
      position: 'fixed',
      inset: 0,
      background: 'rgba(0,0,0,0.55)',
      zIndex: 50,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 20
    }
  }, /*#__PURE__*/React.createElement("div", {
    onClick: e => e.stopPropagation(),
    style: {
      background: 'var(--bg)',
      border: '1px solid var(--border)',
      borderRadius: 6,
      width: 'min(960px, 96vw)',
      maxHeight: '92vh',
      overflow: 'auto',
      display: 'flex',
      flexDirection: 'column'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '12px 16px',
      borderBottom: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 16,
      fontWeight: 500
    }
  }, tune.tune_name), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      marginTop: 2
    }
  }, affTune.calc_variant || '—', affTune.calc_variant_hash && /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      marginLeft: 6,
      color: 'var(--text-dim)'
    }
  }, affTune.calc_variant_hash.slice(0, 8)))), /*#__PURE__*/React.createElement("button", {
    onClick: onClose,
    className: "btn",
    style: {
      height: 24,
      padding: '0 10px',
      fontSize: 11
    }
  }, "Close")), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '12px 16px',
      borderBottom: '1px solid var(--border)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 6,
      marginBottom: 10
    }
  }, ['magic', 'force', 'spirit', 'void'].map(a => /*#__PURE__*/React.createElement("button", {
    key: a,
    onClick: () => setAffinity(a),
    className: "btn",
    style: {
      height: 26,
      padding: '0 12px',
      fontSize: 11,
      background: a === affinity ? 'var(--accent)' : 'var(--bg-subtle)',
      color: a === affinity ? 'var(--bg)' : 'var(--text)',
      border: '1px solid var(--border)',
      textTransform: 'capitalize'
    }
  }, a)), affBusy && /*#__PURE__*/React.createElement("span", {
    style: {
      alignSelf: 'center',
      fontSize: 10.5,
      color: 'var(--text-dim)'
    }
  }, "simulating\u2026")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'auto auto auto',
      gap: 24
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em'
    }
  }, "Sim damage"), /*#__PURE__*/React.createElement("div", {
    className: "num mono",
    style: {
      fontSize: 24,
      fontWeight: 600,
      color: 'var(--accent)'
    }
  }, sim.partial ? '—' : `${((sim.total_damage || 0) / 1e6).toFixed(1)}M`)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em'
    }
  }, "Boss turns"), /*#__PURE__*/React.createElement("div", {
    className: "num mono",
    style: {
      fontSize: 24,
      fontWeight: 600
    }
  }, sim.boss_turns || '—')), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em'
    }
  }, "Sim warnings"), /*#__PURE__*/React.createElement("div", {
    className: "num mono",
    style: {
      fontSize: 24,
      fontWeight: 600,
      color: sim.warnings > 0 ? 'var(--warn)' : 'var(--text-dim)'
    }
  }, sim.warnings ?? 0)))), affTune.potential_team?.team && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '12px 16px',
      borderBottom: '1px solid var(--border)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      marginBottom: 6
    }
  }, "Team"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '30px 1fr 80px 80px 100px',
      gap: 6,
      fontSize: 11.5
    }
  }, affTune.potential_team.team.map(sl => /*#__PURE__*/React.createElement(React.Fragment, {
    key: sl.index
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    }
  }, sl.is_generic ? /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: 'var(--text-dim)'
    }
  }, sl.index) : /*#__PURE__*/React.createElement(HeroPortrait, {
    typeId: sl.type_id,
    size: 26,
    grade: sl.owned_grade
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      color: sl.is_generic ? 'var(--text-dim)' : 'var(--text)',
      alignSelf: 'center'
    }
  }, sl.hero), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: 'var(--text-sub)',
      alignSelf: 'center'
    }
  }, "SPD ", sl.target_speed), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: 'var(--text-dim)'
    }
  }, "base ", sl.base_speed || '—'), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: 'var(--text-dim)'
    }
  }, sl.owned_grade ? `${sl.owned_grade}★ lvl ${sl.owned_level}` : '—'))))), parity && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '12px 16px',
      borderBottom: '1px solid var(--border)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'baseline',
      justifyContent: 'space-between',
      marginBottom: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em'
    }
  }, "Turn-meter timeline \xB7 DWJ-parity scheduler"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 10,
      color: 'var(--text-dim)'
    }
  }, parity.boss_turn_count, " boss turns \xB7 ", parity.turn_count, " actions", parityBusy ? ' · loading…' : '')), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 14,
      alignItems: 'center',
      marginBottom: 8,
      fontSize: 9.5,
      color: 'var(--text-dim)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 4
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 12,
      height: 9,
      background: '#4ade80',
      borderRadius: 2,
      display: 'inline-block'
    }
  }), " champ acts"), /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 4
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 12,
      height: 9,
      background: 'var(--violet)',
      borderRadius: 2,
      display: 'inline-block'
    }
  }), " boss acts"), /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 4
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 12,
      height: 9,
      background: 'rgba(255,255,255,0.16)',
      borderRadius: 2,
      display: 'inline-block'
    }
  }), " filling TM"), /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 4
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 5,
      height: 5,
      background: '#fbbf24',
      borderRadius: '50%',
      display: 'inline-block'
    }
  }), " speed fx")), /*#__PURE__*/React.createElement("div", {
    style: {
      maxHeight: 420,
      overflowY: 'auto',
      background: 'var(--bg-elev)',
      border: '1px solid var(--border)',
      borderRadius: 4,
      padding: 10
    }
  }, (() => {
    const order = parity.actor_order || [];
    const tmMax = parity.tm_max || 100;
    const tl = parity.timeline || [];
    const idMap = parity.actor_type_ids || {};
    const hasState = order.length > 0 && tl.some(t => t.state && t.state.tm);
    const shortName = n => n === 'Clanboss' ? 'BOSS' : n.length > 9 ? n.slice(0, 9) : n;

    // Fallback: enriched state absent (older cached response) — plain cast list.
    if (!hasState) {
      return tl.map((a, ai) => /*#__PURE__*/React.createElement("div", {
        key: ai,
        style: {
          display: 'flex',
          gap: 6,
          padding: '2px 6px',
          fontSize: 11,
          lineHeight: 1.6,
          background: a.actor === 'Clanboss' ? 'var(--bg-subtle)' : 'transparent',
          color: a.actor === 'Clanboss' ? 'var(--violet)' : 'var(--text)',
          borderRadius: 3
        }
      }, /*#__PURE__*/React.createElement("span", {
        className: "mono",
        style: {
          width: 36,
          color: 'var(--text-dim)',
          fontSize: 10
        }
      }, "bt", a.boss_turn), /*#__PURE__*/React.createElement("span", {
        style: {
          flex: 1
        }
      }, a.actor), /*#__PURE__*/React.createElement("span", {
        className: "mono",
        style: {
          color: 'var(--text-sub)',
          fontSize: 10.5
        }
      }, a.skill)));
    }
    const cols = `52px 104px repeat(${order.length}, minmax(0, 1fr))`;
    const Row = ({
      children,
      sticky
    }) => /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'grid',
        gridTemplateColumns: cols,
        gap: 4,
        alignItems: 'center',
        ...(sticky ? {
          position: 'sticky',
          top: -10,
          background: 'var(--bg-elev)',
          zIndex: 1,
          paddingBottom: 4
        } : {})
      }
    }, children);
    return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(Row, {
      sticky: true
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 9,
        color: 'var(--text-dim)',
        textTransform: 'uppercase'
      }
    }, "turn"), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 9,
        color: 'var(--text-dim)',
        textTransform: 'uppercase'
      }
    }, "cast"), order.map(n => /*#__PURE__*/React.createElement("span", {
      key: n,
      title: n,
      style: {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 1,
        fontSize: 8.5,
        color: n === 'Clanboss' ? 'var(--violet)' : 'var(--text-dim)',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis'
      }
    }, n !== 'Clanboss' && /*#__PURE__*/React.createElement(HeroPortraitByName, {
      name: n,
      idMap: idMap,
      size: 16
    }), /*#__PURE__*/React.createElement("span", {
      style: {
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        maxWidth: '100%'
      }
    }, shortName(n))))), tl.map((t, i) => {
      const tm = t.state && t.state.tm || {};
      const spd = t.state && t.state.speed || {};
      const isBoss = t.actor === 'Clanboss';
      return /*#__PURE__*/React.createElement("div", {
        key: i,
        style: {
          display: 'grid',
          gridTemplateColumns: cols,
          gap: 4,
          alignItems: 'center',
          fontSize: 10,
          padding: '1px 0',
          borderBottom: '1px solid rgba(255,255,255,0.03)',
          background: isBoss ? 'rgba(167,139,250,0.06)' : 'transparent'
        }
      }, /*#__PURE__*/React.createElement("span", {
        className: "mono",
        style: {
          color: 'var(--text-dim)',
          fontSize: 9
        }
      }, "bt", t.boss_turn), /*#__PURE__*/React.createElement("span", {
        style: {
          display: 'flex',
          alignItems: 'center',
          gap: 3,
          color: isBoss ? 'var(--violet)' : 'var(--text)',
          whiteSpace: 'nowrap',
          overflow: 'hidden'
        }
      }, !isBoss && /*#__PURE__*/React.createElement(HeroPortraitByName, {
        name: t.actor,
        idMap: idMap,
        size: 15
      }), !isBoss && /*#__PURE__*/React.createElement(SkillIcon, {
        typeId: idMap[t.actor],
        alias: t.skill,
        size: 14
      }), /*#__PURE__*/React.createElement("span", {
        style: {
          overflow: 'hidden',
          textOverflow: 'ellipsis'
        }
      }, shortName(t.actor), " ", /*#__PURE__*/React.createElement("span", {
        className: "mono",
        style: {
          color: 'var(--text-sub)',
          fontSize: 9
        }
      }, t.skill))), order.map(n => {
        const v = tm[n] || 0;
        const frac = Math.max(0, Math.min(1, v / tmMax));
        const acted = n === t.actor;
        const nBoss = n === 'Clanboss';
        const hasSpd = (spd[n] || []).length > 0;
        const fill = acted ? nBoss ? 'var(--violet)' : '#4ade80' : nBoss ? 'rgba(167,139,250,0.4)' : 'rgba(255,255,255,0.16)';
        return /*#__PURE__*/React.createElement("div", {
          key: n,
          title: `${n}: TM ${v}${hasSpd ? ' · speed fx' : ''}${acted ? ' · ACTS' : ''}`,
          style: {
            height: 11,
            background: 'rgba(255,255,255,0.05)',
            borderRadius: 2,
            position: 'relative',
            border: acted ? '1px solid ' + (nBoss ? 'var(--violet)' : '#4ade80') : '1px solid transparent',
            overflow: 'hidden'
          }
        }, /*#__PURE__*/React.createElement("div", {
          style: {
            position: 'absolute',
            left: 0,
            top: 0,
            bottom: 0,
            width: `${frac * 100}%`,
            background: fill
          }
        }), hasSpd && /*#__PURE__*/React.createElement("div", {
          style: {
            position: 'absolute',
            right: 1,
            top: 1,
            width: 4,
            height: 4,
            borderRadius: '50%',
            background: '#fbbf24'
          }
        }));
      }));
    }));
  })())), !parity && hash && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '12px 16px',
      fontSize: 11,
      color: 'var(--text-dim)'
    }
  }, "Loading cast timeline\u2026"), (gearBusy || gearPlan) && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '12px 16px',
      borderBottom: '1px solid var(--border)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'baseline',
      justifyContent: 'space-between',
      marginBottom: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em'
    }
  }, "Gear plan \xB7 vault solver"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 10,
      color: 'var(--text-dim)'
    }
  }, gearBusy && !gearPlan ? 'solving (~8s)…' : gearPlan?.plan ? `${(gearPlan.plan.total_damage / 1e6).toFixed(1)}M planned` : '')), gearPlan?.error && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: 'var(--danger)'
    }
  }, gearPlan.error), gearPlan?.plan?.team && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr',
      gap: 6
    }
  }, gearPlan.plan.team.map((h, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      padding: 8,
      background: 'var(--bg-elev)',
      border: '1px solid var(--border)',
      borderRadius: 4
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'baseline',
      justifyContent: 'space-between',
      marginBottom: 4
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontWeight: 500,
      fontSize: 12
    }
  }, h.name), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 10.5,
      color: 'var(--text-sub)'
    }
  }, "SPD ", h.projected_stats.SPD, " \xB7 ACC ", h.projected_stats.ACC, " \xB7 CR ", h.projected_stats.CR, "% \xB7 CD ", h.projected_stats.CD, "%")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 4,
      flexWrap: 'wrap',
      marginBottom: 4
    }
  }, (h.active_sets || []).filter(s => s.count > 0).map((s, j) => /*#__PURE__*/React.createElement("span", {
    key: j,
    style: {
      fontSize: 9,
      padding: '1px 5px',
      background: 'var(--bg-subtle)',
      border: '1px solid var(--border)',
      borderRadius: 3,
      color: 'var(--text-dim)'
    }
  }, s.set_name, "\xD7", s.count))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '70px 80px 1fr',
      gap: 2,
      fontSize: 10,
      lineHeight: 1.5,
      color: 'var(--text-sub)'
    }
  }, (h.slots || []).map((sl, j) => /*#__PURE__*/React.createElement(React.Fragment, {
    key: j
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-dim)'
    }
  }, sl.slot_name), /*#__PURE__*/React.createElement("span", null, sl.set_name), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: 'var(--text-dim)'
    }
  }, "id ", sl.artifact_id)))))))), (slotBusy || slotAlts) && (slotAlts?.slots?.length > 0 || slotBusy) && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '12px 16px',
      borderBottom: '1px solid var(--border)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'baseline',
      justifyContent: 'space-between',
      marginBottom: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em'
    }
  }, "Generic-slot alternatives \xB7 best fits"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 10,
      color: 'var(--text-dim)'
    }
  }, slotBusy && !slotAlts ? 'simulating ~10s…' : slotAlts ? `${slotAlts.candidates_considered} 6★ candidates` : '')), slotAlts?.error && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: 'var(--danger)'
    }
  }, slotAlts.error), slotAlts?.slots?.map((s, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      marginBottom: 10
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: 'var(--text-sub)',
      marginBottom: 4
    }
  }, "Slot ", s.index, " \xB7 ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-dim)'
    }
  }, s.label), s.target_speed && /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      marginLeft: 6,
      color: 'var(--text-dim)'
    }
  }, "SPD ", s.target_speed)), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 80px 80px',
      gap: 4,
      fontSize: 11
    }
  }, s.alternatives.map((a, j) => {
    const deltaColor = a.delta > 0 ? 'var(--ok)' : a.delta < 0 ? 'var(--danger)' : 'var(--text-dim)';
    const deltaStr = (a.delta >= 0 ? '+' : '') + (a.delta / 1e6).toFixed(1) + 'M';
    return /*#__PURE__*/React.createElement(React.Fragment, {
      key: j
    }, /*#__PURE__*/React.createElement("span", null, a.hero), /*#__PURE__*/React.createElement("span", {
      className: "mono num",
      style: {
        textAlign: 'right',
        color: 'var(--accent)'
      }
    }, (a.damage / 1e6).toFixed(1), "M"), /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        textAlign: 'right',
        color: deltaColor,
        fontSize: 10
      }
    }, deltaStr));
  }))))), sim.projection && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '12px 16px',
      borderBottom: '1px solid var(--border)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      marginBottom: 6
    }
  }, "Projection levers (", sim.projection.projection_mode ? 'ceiling' : 'current progression', ")"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '140px 1fr',
      gap: 4,
      fontSize: 11,
      lineHeight: 1.5
    }
  }, Object.entries(sim.projection).filter(([k]) => k !== 'projection_mode').map(([k, v]) => /*#__PURE__*/React.createElement(React.Fragment, {
    key: k
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-dim)',
      textTransform: 'capitalize'
    }
  }, k.replace(/_/g, ' ')), /*#__PURE__*/React.createElement("span", {
    style: {
      color: String(v).includes('NOT YET') ? 'var(--warn)' : 'var(--text-sub)'
    }
  }, v))))), todos.length > 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '12px 16px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      marginBottom: 6
    }
  }, "Todos (", todos.length, ")"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '80px 100px 1fr',
      gap: 6,
      fontSize: 11
    }
  }, todos.map((td, i) => /*#__PURE__*/React.createElement(React.Fragment, {
    key: i
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      fontSize: 10
    }
  }, td.kind), /*#__PURE__*/React.createElement("span", null, td.hero || '—'), /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-sub)'
    }
  }, td.detail || td.recommended?.blessing_pve_high || td.recommended?.blessing_pve_low || '')))))));
}

// ============================================================================
// CBSpeedSweep — interactive slider that varies one hero's SPD and re-runs
// cb_sim. Shows the "sweet spot" SPD band where the tune survives 50 turns.
// ============================================================================
function CBSpeedSweep() {
  const [hero, setHero] = React.useState('Ninja');
  const [lo, setLo] = React.useState(180);
  const [hi, setHi] = React.useState(230);
  const [data, setData] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const run = async () => {
    setBusy(true);
    setData(null);
    try {
      const r = await fetch(`/api/sim-sweep?hero=${encodeURIComponent(hero)}&lo=${lo}&hi=${hi}`);
      setData(await r.json());
    } catch (e) {
      setData({
        error: String(e)
      });
    }
    setBusy(false);
  };
  const maxDmg = (data?.sweep || []).reduce((m, r) => Math.max(m, r.damage || 0), 0) || 1;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      borderTop: '1px solid var(--border)',
      padding: '12px 14px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 10,
      alignItems: 'center',
      marginBottom: 10
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 11,
      color: 'var(--text-dim)'
    }
  }, "Hero:"), /*#__PURE__*/React.createElement("input", {
    type: "text",
    value: hero,
    onChange: e => setHero(e.target.value),
    style: {
      background: 'var(--bg-subtle)',
      border: '1px solid var(--border)',
      borderRadius: 3,
      padding: '3px 6px',
      fontSize: 12,
      color: 'var(--text)',
      width: 100
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 11,
      color: 'var(--text-dim)'
    }
  }, "SPD range:"), /*#__PURE__*/React.createElement("input", {
    type: "number",
    value: lo,
    onChange: e => setLo(+e.target.value),
    style: {
      background: 'var(--bg-subtle)',
      border: '1px solid var(--border)',
      borderRadius: 3,
      padding: '3px 6px',
      fontSize: 12,
      color: 'var(--text)',
      width: 60
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 10
    }
  }, "\u2192"), /*#__PURE__*/React.createElement("input", {
    type: "number",
    value: hi,
    onChange: e => setHi(+e.target.value),
    style: {
      background: 'var(--bg-subtle)',
      border: '1px solid var(--border)',
      borderRadius: 3,
      padding: '3px 6px',
      fontSize: 12,
      color: 'var(--text)',
      width: 60
    }
  }), /*#__PURE__*/React.createElement("button", {
    className: "btn primary",
    onClick: run,
    disabled: busy,
    style: {
      height: 22,
      fontSize: 11,
      padding: '0 10px'
    }
  }, busy ? 'Running…' : 'Run sweep')), data?.error && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: 'oklch(0.65 0.23 25)'
    }
  }, data.error), data?.sweep && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(60px, 1fr))',
      gap: 4
    }
  }, data.sweep.map(r => {
    const pct = (r.damage || 0) / maxDmg;
    const barHeight = Math.max(4, pct * 50);
    return /*#__PURE__*/React.createElement("div", {
      key: r.spd,
      style: {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 2
      },
      title: `SPD ${r.spd}: ${(r.damage || 0) / 1e6}M damage, ${r.cb_turns} turns, ${r.gaps} gaps`
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        height: 50,
        display: 'flex',
        alignItems: 'flex-end'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        width: '100%',
        maxWidth: 20,
        height: barHeight,
        background: r.gaps === 0 ? 'var(--accent)' : r.gaps < 3 ? 'oklch(0.75 0.17 85)' : 'oklch(0.65 0.23 25)'
      }
    })), /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        fontSize: 9,
        color: 'var(--text-dim)'
      }
    }, r.spd));
  })));
}

/* ===================== Champ manager (skill-up + rank-up planner) ===================== */

function PageChampManager() {
  const [data, setData] = React.useState(null);
  const [err, setErr] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const [executing, setExecuting] = React.useState(false);
  const [maxSkill, setMaxSkill] = React.useState(0);
  const [maxRank, setMaxRank] = React.useState(0);
  const [lastResult, setLastResult] = React.useState(null);
  const refresh = React.useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const r = await fetch('/api/champ-manager');
      if (!r.ok) throw new Error('HTTP ' + r.status);
      setData(await r.json());
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }, []);
  React.useEffect(() => {
    refresh();
  }, [refresh]);
  const execute = async phase => {
    const verb = phase === 'skill' ? 'skill-ups' : phase === 'rank' ? 'rank-ups' : 'skill-ups + rank-ups';
    const cap = phase === 'skill' ? maxSkill : phase === 'rank' ? maxRank : `${maxSkill || 'all'} + ${maxRank || 'all'}`;
    if (!window.confirm(`Execute ${verb}? (cap: ${cap}) — DESTRUCTIVE`)) return;
    setExecuting(true);
    setErr(null);
    setLastResult(null);
    try {
      const r = await fetch('/api/champ-manager/execute', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          phase,
          max_skill_ups: maxSkill || 0,
          max_rank_ups: maxRank || 0
        })
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.error || 'HTTP ' + r.status);
      setLastResult(j);
      await refresh();
    } catch (e) {
      setErr(String(e));
    } finally {
      setExecuting(false);
    }
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 360px',
      gap: 10,
      minHeight: '100%'
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card scroll",
    style: {
      padding: 16,
      overflow: 'auto',
      minHeight: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      marginBottom: 12
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-title"
  }, "Champion manager \xB7 skill-up + rank-up"), /*#__PURE__*/React.createElement("button", {
    className: "btn",
    onClick: refresh,
    disabled: loading
  }, loading ? 'Loading…' : 'Refresh')), err && /*#__PURE__*/React.createElement("div", {
    style: {
      color: 'var(--red)',
      fontSize: 12,
      marginBottom: 10
    }
  }, err), !data && !err && /*#__PURE__*/React.createElement("div", {
    style: {
      color: 'var(--text-dim)',
      fontSize: 12
    }
  }, "Loading\u2026"), data && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 11,
      color: 'var(--text-dim)',
      marginBottom: 14
    }
  }, "Roster: ", data.roster_total, " \xB7 Reserved: ", data.reserved_count, " \xB7 Skill plans: ", data.skill_plans.length, " (", data.skill_consumed_count, " dups) \xB7 Rank plans: ", data.rank_plans.length, " (", data.rank_consumed_count, " fodder) \xB7 Bottlenecked: ", data.bottlenecked.length), /*#__PURE__*/React.createElement(ChampManagerSection, {
    title: "Skill-up plans",
    emptyText: "No skill-up plans (all skills maxed or no dups)."
  }, data.skill_plans.map((p, i) => /*#__PURE__*/React.createElement("div", {
    key: p.primary.id,
    style: {
      padding: '8px 0',
      borderBottom: '1px solid var(--border)',
      fontSize: 12
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement(HeroPortrait, {
    typeId: p.primary.type_id,
    size: 24,
    rarity: p.primary.rarity
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      minWidth: 0,
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap'
    }
  }, /*#__PURE__*/React.createElement("strong", null, "[", i + 1, "]"), " ", p.primary.name, " ", /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: 'var(--text-dim)'
    }
  }, "R", p.primary.rarity, "/G", p.primary.grade, "/L", p.primary.level))), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: 'var(--accent)',
      whiteSpace: 'nowrap'
    }
  }, "+", p.total_remaining, " lv \xB7 ", p.feeds.length, " feed")), /*#__PURE__*/React.createElement("div", {
    style: {
      paddingLeft: 16,
      marginTop: 4,
      color: 'var(--text-sub)',
      fontSize: 11
    }
  }, p.skill_levels.filter(s => s.remaining > 0).map(s => /*#__PURE__*/React.createElement("span", {
    key: s.name,
    className: "mono",
    style: {
      marginRight: 12
    }
  }, s.name, " ", s.current, "/", s.max)))))), /*#__PURE__*/React.createElement(ChampManagerSection, {
    title: "Rank-up plans",
    emptyText: "No rank-up plans."
  }, data.rank_plans.map((p, i) => /*#__PURE__*/React.createElement("div", {
    key: p.target.id,
    style: {
      padding: '8px 0',
      borderBottom: '1px solid var(--border)',
      fontSize: 12
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement(HeroPortrait, {
    typeId: p.target.type_id,
    size: 24,
    rarity: p.target.rarity
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      minWidth: 0,
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap'
    }
  }, /*#__PURE__*/React.createElement("strong", null, "[", i + 1, "]"), " ", p.target.name, " ", /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: 'var(--text-dim)'
    }
  }, "R", p.target.rarity, "/G", p.target.grade, "/L", p.target.level))), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: 'var(--text-dim)',
      whiteSpace: 'nowrap'
    }
  }, p.food.length, " food")), /*#__PURE__*/React.createElement("div", {
    style: {
      paddingLeft: 16,
      marginTop: 4,
      fontSize: 11,
      color: 'var(--text-sub)'
    },
    className: "mono"
  }, p.food.map(f => `${f.name}(R${f.rarity}/G${f.grade}/L${f.level})`).join(' · '))))), /*#__PURE__*/React.createElement(ChampManagerSection, {
    title: "Bottlenecked",
    emptyText: "No bottlenecks."
  }, data.bottlenecked.map(b => /*#__PURE__*/React.createElement("div", {
    key: b.target.id,
    style: {
      padding: '6px 0',
      fontSize: 12
    }
  }, /*#__PURE__*/React.createElement("span", null, b.target.name, " "), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: 'var(--text-dim)'
    }
  }, "(G", b.target.grade, "): need ", b.needed, ", have ", b.available, " (short ", b.missing, ")")))), data.multi_pass && /*#__PURE__*/React.createElement(ChampManagerSection, {
    title: `Multi-pass simulation (${data.multi_pass.passes.length} passes)`,
    emptyText: "No iterative plan."
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: 'var(--text-dim)',
      marginBottom: 6
    }
  }, "Iteratively applies rank-ups so newly-promoted heroes can feed bigger targets next pass."), data.multi_pass.passes.map(p => /*#__PURE__*/React.createElement("div", {
    key: p.pass,
    style: {
      padding: '4px 0',
      fontSize: 11.5
    },
    className: "mono"
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--accent)'
    }
  }, "Pass ", p.pass, ":"), /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: 8
    }
  }, p.rank_plans, " rank-ups"), /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: 12,
      color: 'var(--text-sub)'
    }
  }, p.rank_targets.slice(0, 5).join(', '), p.rank_targets.length > 5 ? `, +${p.rank_targets.length - 5}` : ''))), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 6,
      fontSize: 11,
      color: 'var(--text-sub)'
    }
  }, "Cumulative: ", /*#__PURE__*/React.createElement("span", {
    className: "mono"
  }, data.multi_pass.total_rank_plans), " rank-ups achievable across ", data.multi_pass.passes.length, " passes."), data.multi_pass.final_bottlenecked.length > 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 6,
      fontSize: 11,
      color: 'var(--text-dim)'
    }
  }, "Still bottlenecked after all passes:\xA0", /*#__PURE__*/React.createElement("span", {
    className: "mono"
  }, data.multi_pass.final_bottlenecked.map(b => `${b.name} G${b.grade} (need ${b.needed}, have ${b.available})`).join(' · ')))))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateRows: 'auto auto auto auto auto',
      gap: 10,
      minHeight: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-title",
    style: {
      marginBottom: 8
    }
  }, "Protection rules"), data && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11.5,
      color: 'var(--text-sub)',
      lineHeight: 1.7
    }
  }, /*#__PURE__*/React.createElement("div", null, "Legendaries: ", /*#__PURE__*/React.createElement("span", {
    className: "mono"
  }, data.protected.exclude_all_legendaries ? 'excluded' : 'allowed')), /*#__PURE__*/React.createElement("div", null, "Epics: ", /*#__PURE__*/React.createElement("span", {
    className: "mono"
  }, data.protected.exclude_all_epics ? 'excluded' : 'allowed')), /*#__PURE__*/React.createElement("div", null, "Fusions: ", /*#__PURE__*/React.createElement("span", {
    className: "mono"
  }, (data.protected.fusion_targets || []).join(', ') || '(none)')), /*#__PURE__*/React.createElement("div", null, "Named: ", /*#__PURE__*/React.createElement("span", {
    className: "mono"
  }, (data.protected.protected_names || []).join(', ') || '(none)')), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 8,
      fontSize: 10.5,
      color: 'var(--text-dim)'
    }
  }, "Edit ", /*#__PURE__*/React.createElement("span", {
    className: "mono"
  }, "data/protected_heroes.json"), " to add specific names."))), /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-title",
    style: {
      marginBottom: 10
    }
  }, "Caps (0 = no limit)"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 10,
      fontSize: 11
    }
  }, /*#__PURE__*/React.createElement("label", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      color: 'var(--text-dim)',
      marginBottom: 4
    }
  }, "Max skill-ups"), /*#__PURE__*/React.createElement("input", {
    type: "number",
    min: "0",
    value: maxSkill,
    onChange: e => setMaxSkill(Math.max(0, parseInt(e.target.value) || 0)),
    style: {
      width: '100%',
      padding: 6,
      background: 'var(--bg-subtle)',
      border: '1px solid var(--border)',
      color: 'var(--text)',
      fontFamily: 'JetBrains Mono, monospace'
    }
  })), /*#__PURE__*/React.createElement("label", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      color: 'var(--text-dim)',
      marginBottom: 4
    }
  }, "Max rank-ups"), /*#__PURE__*/React.createElement("input", {
    type: "number",
    min: "0",
    value: maxRank,
    onChange: e => setMaxRank(Math.max(0, parseInt(e.target.value) || 0)),
    style: {
      width: '100%',
      padding: 6,
      background: 'var(--bg-subtle)',
      border: '1px solid var(--border)',
      color: 'var(--text)',
      fontFamily: 'JetBrains Mono, monospace'
    }
  })))), /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-title",
    style: {
      marginBottom: 10
    }
  }, "Execute (DESTRUCTIVE)"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 6
    }
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn",
    disabled: executing || !data || data.skill_plans.length === 0,
    onClick: () => execute('skill')
  }, executing ? '…' : 'Run skill-ups only'), /*#__PURE__*/React.createElement("button", {
    className: "btn",
    disabled: executing || !data || data.rank_plans.length === 0,
    onClick: () => execute('rank')
  }, executing ? '…' : 'Run rank-ups only'), /*#__PURE__*/React.createElement("button", {
    className: "btn primary",
    disabled: executing || !data || data.skill_plans.length === 0 && data.rank_plans.length === 0,
    onClick: () => execute('both')
  }, executing ? '…' : 'Run both phases')), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 8,
      fontSize: 10.5,
      color: 'var(--text-dim)'
    }
  }, "Calls ", /*#__PURE__*/React.createElement("span", {
    className: "mono"
  }, "/skill-up"), " + ", /*#__PURE__*/React.createElement("span", {
    className: "mono"
  }, "/rank-up"), " on the live mod.")), /*#__PURE__*/React.createElement("div", {
    className: "card scroll",
    style: {
      padding: 14,
      overflow: 'auto',
      minHeight: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-title",
    style: {
      marginBottom: 8
    }
  }, "Last execution"), !lastResult && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: 'var(--text-dim)'
    }
  }, "(none yet)"), lastResult && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11.5
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      color: 'var(--accent)',
      marginBottom: 6
    }
  }, "Phase: ", lastResult.phase, " \xB7 skill ", lastResult.skill_succeeded, "/", lastResult.skill_results.length, " \xB7 rank ", lastResult.rank_succeeded, "/", lastResult.rank_results.length), lastResult.skill_results.map((r, i) => /*#__PURE__*/React.createElement("div", {
    key: 's' + i,
    style: {
      color: r.ok ? 'var(--text-sub)' : 'var(--red)'
    }
  }, r.ok ? '+' : '!', " skill ", r.primary.name, r.error ? ' — ' + r.error : '')), lastResult.rank_results.map((r, i) => /*#__PURE__*/React.createElement("div", {
    key: 'r' + i,
    style: {
      color: r.ok ? 'var(--text-sub)' : 'var(--red)'
    }
  }, r.ok ? '+' : '!', " rank ", r.target.name, r.error ? ' — ' + r.error : '')))), /*#__PURE__*/React.createElement(RankUpChainPlanner, null), /*#__PURE__*/React.createElement(ChampionTrainingPanel, null)));
}

/* ===================== Rank-up chain planner ===================== */
/* Picks targets, computes recursive rank-up cost (1*->6* via same-grade fodder).
   NOT 'Ascension' — that's Sacred Ascend, post-6*, separate Raid mechanic. */

function RankUpChainPlanner() {
  const [heroes, setHeroes] = React.useState([]);
  const [picked, setPicked] = React.useState([]); // array of hero ids
  const [toGrade, setToGrade] = React.useState(6);
  const [filter, setFilter] = React.useState('');
  const [plan, setPlan] = React.useState(null);
  const [planning, setPlanning] = React.useState(false);
  const [err, setErr] = React.useState(null);
  React.useEffect(() => {
    fetch('/api/rank-up-targets').then(r => r.json()).then(j => setHeroes(j.heroes || [])).catch(e => setErr('load: ' + e));
  }, []);
  const filtered = React.useMemo(() => {
    const f = filter.trim().toLowerCase();
    let xs = heroes;
    if (f) xs = xs.filter(h => (h.name || '').toLowerCase().includes(f));
    return xs.slice(0, 200);
  }, [heroes, filter]);
  const togglePick = id => {
    setPicked(p => p.includes(id) ? p.filter(x => x !== id) : [...p, id]);
  };
  const runPlan = async () => {
    if (picked.length === 0) return;
    setPlanning(true);
    setErr(null);
    setPlan(null);
    try {
      const r = await fetch('/api/rank-up-chain', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          target_ids: picked,
          to_grade: toGrade
        })
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.error || 'HTTP ' + r.status);
      setPlan(j);
    } catch (e) {
      setErr(String(e));
    } finally {
      setPlanning(false);
    }
  };
  return /*#__PURE__*/React.createElement("div", {
    className: "card",
    style: {
      padding: 14,
      display: 'flex',
      flexDirection: 'column',
      minHeight: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-title",
    style: {
      marginBottom: 10
    }
  }, "Rank-up chain planner"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: 'var(--text-dim)',
      marginBottom: 8
    }
  }, "Pick heroes to rank-up (1\u2605\u21926\u2605). Tool computes recursive fodder cost: short G5 \u2192 promote from G4 \u2192 from G3 \u2192 etc."), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 8,
      marginBottom: 8,
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("input", {
    placeholder: "Filter by name\u2026",
    value: filter,
    onChange: e => setFilter(e.target.value),
    style: {
      flex: 1,
      padding: 6,
      background: 'var(--bg-subtle)',
      border: '1px solid var(--border)',
      color: 'var(--text)',
      fontSize: 11,
      fontFamily: 'JetBrains Mono, monospace'
    }
  }), /*#__PURE__*/React.createElement("select", {
    value: toGrade,
    onChange: e => setToGrade(parseInt(e.target.value)),
    style: {
      padding: 6,
      background: 'var(--bg-subtle)',
      border: '1px solid var(--border)',
      color: 'var(--text)',
      fontSize: 11
    }
  }, [2, 3, 4, 5, 6].map(g => /*#__PURE__*/React.createElement("option", {
    key: g,
    value: g
  }, "To G", g)))), /*#__PURE__*/React.createElement("div", {
    className: "scroll",
    style: {
      flex: 1,
      minHeight: 100,
      maxHeight: 220,
      overflowY: 'auto',
      background: 'var(--bg-subtle)',
      border: '1px solid var(--border)',
      padding: 4,
      marginBottom: 8
    }
  }, filtered.map(h => {
    const sel = picked.includes(h.id);
    return /*#__PURE__*/React.createElement("div", {
      key: h.id,
      onClick: () => togglePick(h.id),
      style: {
        padding: '4px 8px',
        cursor: 'pointer',
        fontSize: 11.5,
        background: sel ? 'var(--accent-soft)' : 'transparent',
        color: sel ? 'var(--accent)' : 'var(--text)',
        display: 'flex',
        alignItems: 'center',
        gap: 6
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 12
      }
    }, sel ? '✓' : ''), /*#__PURE__*/React.createElement(HeroPortrait, {
      typeId: h.type_id,
      size: 22,
      rarity: h.rarity
    }), /*#__PURE__*/React.createElement("span", {
      style: {
        flex: 1,
        minWidth: 0,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap'
      }
    }, h.name), /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        color: 'var(--text-dim)',
        fontSize: 10.5
      }
    }, "R", h.rarity, "/G", h.grade, "/L", h.level, h.level_ready ? '' : ' ⚠'));
  }), filtered.length === 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 8,
      color: 'var(--text-dim)',
      fontSize: 11
    }
  }, "No heroes match.")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 6,
      alignItems: 'center',
      marginBottom: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)'
    }
  }, picked.length, " picked"), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement("button", {
    className: "btn",
    onClick: () => setPicked([]),
    disabled: picked.length === 0
  }, "Clear"), /*#__PURE__*/React.createElement("button", {
    className: "btn primary",
    onClick: runPlan,
    disabled: planning || picked.length === 0
  }, planning ? 'Planning…' : 'Compute plan')), err && /*#__PURE__*/React.createElement("div", {
    style: {
      color: 'var(--red)',
      fontSize: 11.5
    }
  }, err), plan && /*#__PURE__*/React.createElement("div", {
    className: "scroll",
    style: {
      maxHeight: 320,
      overflowY: 'auto',
      borderTop: '1px solid var(--border)',
      paddingTop: 8
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 11,
      color: 'var(--text-dim)',
      marginBottom: 8
    }
  }, "Targets: ", plan.plans.length, " \xB7 Feasible: ", plan.feasible_count, "/", plan.plans.length, " \xB7 Heroes consumed: ", plan.total_consumed, " \xB7 /rank-up calls: ", plan.total_calls || 0), plan.plans.map((p, i) => /*#__PURE__*/React.createElement(RankUpPlanRow, {
    key: i,
    p: p
  }))));
}
function RankUpPlanRow({
  p
}) {
  const [showCalls, setShowCalls] = React.useState(false);
  const t = p.target;
  const seq = p.call_sequence || [];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '6px 0',
      borderBottom: '1px solid var(--border)',
      fontSize: 11.5
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between'
    }
  }, /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("strong", null, t.name), " ", /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: 'var(--text-dim)'
    }
  }, "G", t.grade, "/L", t.level, " \u2192 G", t.to_grade)), /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      color: p.feasible ? 'var(--accent)' : 'var(--red)',
      fontSize: 10.5
    }
  }, p.already_at_grade ? 'already at grade' : p.feasible ? `OK (${seq.length} calls)` : 'INFEASIBLE')), p.level_ready === false && /*#__PURE__*/React.createElement("div", {
    style: {
      paddingLeft: 10,
      color: 'var(--yellow, #cc9933)',
      fontSize: 10.5
    }
  }, "\u26A0 at L", t.level, "; level to L", t.grade * 10, " before rank-up"), (p.chain || []).map((c, j) => /*#__PURE__*/React.createElement("div", {
    key: j,
    className: "mono",
    style: {
      paddingLeft: 12,
      fontSize: 10.5,
      color: c.short > 0 ? 'var(--text)' : 'var(--text-sub)'
    }
  }, "G", c.grade, ": need ", c.demand, ", have ", c.available, c.short > 0 && /*#__PURE__*/React.createElement("span", null, " \xB7 short ", c.short, " \u2192 promote ", c.short, " from G", c.grade - 1, " (", c.short * c.grade, " G", c.grade - 1, " heroes)"))), seq.length > 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      paddingLeft: 12,
      marginTop: 4
    }
  }, /*#__PURE__*/React.createElement("a", {
    href: "#",
    onClick: e => {
      e.preventDefault();
      setShowCalls(!showCalls);
    },
    style: {
      fontSize: 10.5,
      color: 'var(--accent)',
      textDecoration: 'none'
    }
  }, showCalls ? '▼ hide' : '▶ show', " ordered /rank-up calls (", seq.length, ")"), showCalls && /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 4,
      fontSize: 10.5
    }
  }, seq.map((c, k) => /*#__PURE__*/React.createElement("div", {
    key: k,
    className: "mono",
    style: {
      padding: '2px 0',
      color: 'var(--text-sub)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-dim)'
    }
  }, (k + 1).toString().padStart(2), "."), ' ', /*#__PURE__*/React.createElement("span", {
    style: {
      color: c.hero_id === t.id ? 'var(--accent)' : 'var(--text)'
    }
  }, c.hero_name), /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-dim)'
    }
  }, " G", c.from_grade, "\u2192G", c.to_grade), /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-dim)'
    }
  }, " \u2190 [", c.food_names.join(', '), "]"))))));
}
function ChampManagerSection({
  title,
  children,
  emptyText
}) {
  const empty = !React.Children.count(children);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      marginBottom: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-sub)',
      textTransform: 'uppercase',
      letterSpacing: '0.08em',
      fontWeight: 600,
      marginBottom: 6
    }
  }, title), empty ? /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11.5,
      color: 'var(--text-dim)'
    }
  }, emptyText) : children);
}

/* ========================== ChampionTrainingPanel =========================
 * Lives inside PageChampManager's right rail. Wraps tools/six_star.py:
 * pick a target, see the cascade plan, kick off an autonomous farm-and-
 * rank-up loop that survives Claude/dashboard exit. Polls
 * /api/six-star/status for live progress.
 */
function ChampionTrainingPanel() {
  const [heroes, setHeroes] = React.useState([]);
  const [filter, setFilter] = React.useState('');
  const [picked, setPicked] = React.useState(null); // hero id
  const [toGrade, setToGrade] = React.useState(6);
  const [plan, setPlan] = React.useState(null);
  const [planErr, setPlanErr] = React.useState(null);
  const [status, setStatus] = React.useState(null);
  const [busy, setBusy] = React.useState(false);

  // Load rank-up targets once
  React.useEffect(() => {
    fetch('/api/rank-up-targets').then(r => r.json()).then(j => setHeroes(j.heroes || [])).catch(e => setPlanErr('targets: ' + e));
  }, []);

  // Poll training status every 4s
  React.useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const r = await fetch('/api/six-star/status');
        if (!alive) return;
        if (r.ok) setStatus(await r.json());
      } catch (e) {}
    };
    tick();
    const id = setInterval(tick, 4000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  // Auto-load plan when target changes
  React.useEffect(() => {
    if (!picked) {
      setPlan(null);
      return;
    }
    setPlanErr(null);
    fetch(`/api/six-star/plan?target_id=${picked}&to_grade=${toGrade}`).then(r => r.json()).then(j => {
      if (j.error) setPlanErr(j.error);else setPlan(j);
    }).catch(e => setPlanErr(String(e)));
  }, [picked, toGrade]);
  const filtered = React.useMemo(() => {
    const f = filter.trim().toLowerCase();
    let xs = heroes;
    if (f) xs = xs.filter(h => (h.name || '').toLowerCase().includes(f));
    return xs.slice(0, 200);
  }, [heroes, filter]);
  const start = async () => {
    if (!picked) return;
    setBusy(true);
    try {
      const r = await fetch('/api/six-star/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          target_id: picked,
          to_grade: toGrade
        })
      });
      const j = await r.json();
      if (!r.ok) setPlanErr(j.error || 'HTTP ' + r.status);
    } catch (e) {
      setPlanErr(String(e));
    } finally {
      setBusy(false);
    }
  };
  const stop = async () => {
    setBusy(true);
    try {
      await fetch('/api/six-star/stop', {
        method: 'POST'
      });
    } catch (e) {} finally {
      setBusy(false);
    }
  };
  const running = status && status.running;
  const target = plan && plan.target;
  const counts = plan && plan.pool_counts;
  const protections = plan && plan.protections;
  return /*#__PURE__*/React.createElement(ChampManagerSection, {
    title: "Champion training \u2014 6\u2605 autonomous"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: 'var(--text-dim)',
      marginBottom: 6
    }
  }, "Picks target. Farms Campaign 12-3 NM unattended; cascades G1\u2192G2\u2192\u2026\u2192G5; ranks up target when fodder hits threshold."), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 6,
      marginBottom: 6,
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("input", {
    placeholder: "Filter\u2026",
    value: filter,
    onChange: e => setFilter(e.target.value),
    style: {
      flex: 1,
      padding: 4,
      background: 'var(--bg-subtle)',
      border: '1px solid var(--border)',
      color: 'var(--text)',
      fontSize: 10.5,
      fontFamily: 'JetBrains Mono, monospace'
    }
  }), /*#__PURE__*/React.createElement("select", {
    value: toGrade,
    onChange: e => setToGrade(parseInt(e.target.value)),
    style: {
      padding: 4,
      background: 'var(--bg-subtle)',
      border: '1px solid var(--border)',
      color: 'var(--text)',
      fontSize: 10.5
    }
  }, [2, 3, 4, 5, 6].map(g => /*#__PURE__*/React.createElement("option", {
    key: g,
    value: g
  }, "G", g)))), /*#__PURE__*/React.createElement("div", {
    className: "scroll",
    style: {
      maxHeight: 110,
      overflowY: 'auto',
      background: 'var(--bg-subtle)',
      border: '1px solid var(--border)',
      padding: 2,
      marginBottom: 6
    }
  }, filtered.slice(0, 80).map(h => {
    const sel = picked === h.id;
    return /*#__PURE__*/React.createElement("div", {
      key: h.id,
      onClick: () => setPicked(h.id),
      style: {
        padding: '2px 6px',
        cursor: 'pointer',
        fontSize: 10.5,
        background: sel ? 'var(--accent-soft)' : 'transparent',
        color: sel ? 'var(--accent)' : 'var(--text)',
        display: 'flex',
        alignItems: 'center',
        gap: 6
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 14
      }
    }, sel ? '●' : ''), /*#__PURE__*/React.createElement(HeroPortrait, {
      typeId: h.type_id,
      size: 20,
      rarity: h.rarity
    }), /*#__PURE__*/React.createElement("span", {
      style: {
        flex: 1,
        minWidth: 0,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap'
      }
    }, h.name), /*#__PURE__*/React.createElement("span", {
      className: "mono",
      style: {
        color: 'var(--text-dim)',
        fontSize: 10
      }
    }, "R", h.rarity, "/G", h.grade, "/L", h.level, h.level_ready ? '' : '⚠'));
  }), filtered.length === 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 4,
      color: 'var(--text-dim)',
      fontSize: 10.5
    }
  }, "No heroes match.")), planErr && /*#__PURE__*/React.createElement("div", {
    style: {
      color: 'var(--red)',
      fontSize: 10.5,
      marginBottom: 4
    }
  }, planErr), plan && /*#__PURE__*/React.createElement("div", {
    style: {
      borderTop: '1px solid var(--border)',
      paddingTop: 6,
      marginBottom: 6
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 10,
      color: 'var(--text-dim)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      marginBottom: 4
    }
  }, "cascade for ", target.name, " \u2192 G", toGrade), (plan.chain || []).map((c, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    className: "mono",
    style: {
      fontSize: 10.5,
      color: c.short > 0 ? 'var(--red)' : 'var(--accent)'
    }
  }, "G", c.grade, ": need ", c.demand, ", have ", c.available, c.short > 0 && /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text)'
    }
  }, " \xB7 short ", c.short))), /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 10.5,
      marginTop: 4,
      color: plan.feasible ? 'var(--accent)' : 'var(--red)'
    }
  }, plan.feasible ? 'FEASIBLE' : `INFEASIBLE (short at G${plan.stuck_grade || 1})`)), counts && /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 10.5,
      marginBottom: 6,
      color: 'var(--text-sub)'
    }
  }, "pool: G1=", counts[1] || 0, " G2=", counts[2] || 0, " G3=", counts[3] || 0, " G4=", counts[4] || 0, " G5=", counts[5] || 0), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 4,
      alignItems: 'center',
      marginBottom: 4
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "mono",
    style: {
      fontSize: 10,
      color: running ? 'var(--accent)' : 'var(--text-dim)'
    }
  }, running ? `running pid=${status.pid}` : 'idle'), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement(SuperRaidWidget, {
    size: "sm"
  }), !running ? /*#__PURE__*/React.createElement("button", {
    className: "btn primary",
    onClick: start,
    disabled: !picked || busy
  }, busy ? '…' : 'Start') : /*#__PURE__*/React.createElement("button", {
    className: "btn",
    onClick: stop,
    disabled: busy,
    style: {
      color: 'var(--red)'
    }
  }, busy ? '…' : 'Stop')), status && status.running && status.target_state && /*#__PURE__*/React.createElement("div", {
    className: "mono",
    style: {
      fontSize: 10.5,
      marginTop: 6,
      color: 'var(--accent)'
    }
  }, status.target_name, ": G", status.target_state.grade, "/L", status.target_state.level), status && status.running && status.log_tail && /*#__PURE__*/React.createElement("pre", {
    className: "scroll mono",
    style: {
      maxHeight: 90,
      overflow: 'auto',
      background: '#07090b',
      border: '1px solid var(--border)',
      padding: 4,
      marginTop: 4,
      fontSize: 9.5,
      color: 'var(--text-sub)',
      margin: 0,
      whiteSpace: 'pre-wrap',
      wordBreak: 'break-word'
    }
  }, status.log_tail));
}
Object.assign(window, {
  PageOverview,
  PageLive,
  PageTasks,
  PageResources,
  PageCB,
  PageHeroes,
  PageEvents,
  PageHistory,
  PageMod,
  PageChampManager,
  RankUpChainPlanner,
  RankUpPlanRow,
  ChampionTrainingPanel,
  ScheduleCard
});