/* ===================== DIRECTION B — Page components ===================== */

function PageOverview({s, pct, doneCount, activeTask, running}) {
  const totalMs = s.tasks.reduce((a,t) => a + t.duration, 0);
  const elapsedMs = s.tasks.reduce((a, t, i) => a + (t.status==='done'?t.duration : i===s.queueIdx? t.ms : 0), 0);
  return (
    <div style={{display:'grid', gridTemplateColumns: '320px 1fr 260px', gap: 10, minHeight: '100%'}}>
      <div style={{display:'flex', flexDirection:'column', minHeight: 0}}>
        <PanelTaskQueue s={s}/>
      </div>
      <div style={{display:'grid', gridTemplateRows: 'auto 1fr auto', gap: 10, minHeight: 0}}>
        <PanelActiveTask s={s} activeTask={activeTask} running={running} doneCount={doneCount} totalMs={totalMs} elapsedMs={elapsedMs}/>
        <div className="card" style={{padding: 0, overflow:'hidden', display:'flex', flexDirection:'column', minHeight: 0}}>
          <PanelHeader title="14-day earnings" right="gems · silver · cb dmg"/>
          <div style={{padding: 10, flex: 1, minHeight: 0, display:'flex', alignItems:'center'}}>
            <HistoryChartB data={s.history} height={140}/>
          </div>
        </div>
        <PanelResources s={s}/>
      </div>
      <div style={{display:'grid', gridTemplateRows: 'auto auto auto', gap: 10, minHeight: 0}}>
        <PanelLayers s={s}/>
        <PanelCB s={s} compact/>
        <PanelArena s={s}/>
      </div>
    </div>
  );
}

function PageLive({s, pct, doneCount, activeTask, running}) {
  const totalMs = s.tasks.reduce((a,t) => a + t.duration, 0);
  const elapsedMs = s.tasks.reduce((a, t, i) => a + (t.status==='done'?t.duration : i===s.queueIdx? t.ms : 0), 0);
  return (
    <div style={{display:'grid', gridTemplateColumns: '420px 1fr', gap: 10, minHeight: '100%'}}>
      <PanelTaskQueue s={s}/>
      <div style={{display:'grid', gridTemplateRows: 'auto 1fr', gap: 10, minHeight: 0}}>
        <div className="card" style={{padding: 0, overflow:'hidden'}}>
          <PanelHeader title="active task" right={running ? 'running' : 'idle'}/>
          <div style={{padding: 22, display:'grid', gridTemplateColumns: '1fr auto', gap: 22}}>
            <div>
              {activeTask && running ? (
                <>
                  <div style={{fontSize: 11, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em', marginBottom: 6}}>Step {s.queueIdx+1} / {s.tasks.length}</div>
                  <div style={{fontSize: 28, fontWeight: 500, letterSpacing:'-0.015em', marginBottom: 12}}>{activeTask.label}</div>
                  <div style={{display:'flex', alignItems:'center', gap: 12, marginBottom: 14}}>
                    <span className={`layer-badge layer-${activeTask.layer}`}>via {activeTask.layer}</span>
                    <span className="mono" style={{fontSize: 12, color:'var(--text-sub)'}}>
                      {Math.min(100, Math.round((activeTask.ms/activeTask.duration)*100))}% · elapsed {(activeTask.ms/1000).toFixed(1)}s
                    </span>
                  </div>
                  <div style={{height: 6, background:'var(--bg-subtle)', borderRadius: 3, overflow:'hidden'}}>
                    <div style={{height:'100%', width: `${Math.min(100, (activeTask.ms/activeTask.duration)*100)}%`, background:'var(--accent)'}}/>
                  </div>
                </>
              ) : (
                <>
                  <div style={{fontSize: 11, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em', marginBottom: 6}}>Idle</div>
                  <div style={{fontSize: 28, fontWeight: 500, marginBottom: 10}}>
                    {doneCount === s.tasks.length ? 'Daily run complete' : 'Awaiting schedule'}
                  </div>
                  <div style={{fontSize: 13, color:'var(--text-sub)'}}>Next trigger {relTime(s.nextRunAt)} · Windows Task Scheduler</div>
                </>
              )}
            </div>
            <div style={{display:'flex', flexDirection:'column', gap: 6, minWidth: 160}}>
              <div style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em'}}>Total progress</div>
              <div style={{fontSize: 24, fontWeight: 500}} className="num">{pct}%</div>
              <div style={{height: 4, background:'var(--bg-subtle)', borderRadius: 2, overflow:'hidden'}}>
                <div style={{height:'100%', width: pct+'%', background: running ? 'var(--accent)' : 'var(--text-dim)'}}/>
              </div>
              <div style={{fontSize: 11, color:'var(--text-sub)', marginTop: 4}} className="mono">{doneCount} / {s.tasks.length} steps</div>
            </div>
          </div>
        </div>
        <PanelLayers s={s}/>
      </div>
    </div>
  );
}

function PageTasks({s}) {
  const selectedCount = s.tasks.filter(t=>t.selected).length;
  const allSelected = selectedCount === s.tasks.length;
  const noneSelected = selectedCount === 0;
  const scheduleRight = (
    <div style={{display:'flex', alignItems:'center', gap: 10}}>
      <div
        onClick={s.running ? undefined : ()=>window.PARSim.setAllSelected(!allSelected)}
        title={s.running ? '' : (allSelected ? 'Deselect all' : 'Select all')}
        style={{
          width: 14, height: 14, borderRadius: 3,
          border: '1px solid',
          borderColor: allSelected || !noneSelected ? 'var(--accent)' : 'var(--border-strong)',
          background: allSelected ? 'var(--accent-soft)' : 'transparent',
          display:'flex', alignItems:'center', justifyContent:'center',
          cursor: s.running ? 'default' : 'pointer',
        }}
      >
        {allSelected && <SvgIcon.check style={{color:'var(--accent)', opacity: 0.85}}/>}
        {!allSelected && !noneSelected && <div style={{width: 6, height: 2, background: 'var(--accent)'}}/>}
      </div>
      <span className="mono" style={{fontSize: 11, color:'var(--text-dim)'}}>{selectedCount}/{s.tasks.length} selected</span>
      <button
        className={`btn ${s.running ? '' : 'primary'}`}
        onClick={()=>window.PARSim.setRunning(!s.running)}
        disabled={!s.running && selectedCount===0}
        style={{height: 26, padding:'0 12px', fontSize: 12}}
      >
        {s.running ? <><SvgIcon.pause/> Pause</> : <><SvgIcon.play/> Run selected</>}
      </button>
    </div>
  );
  return (
    <div style={{display:'grid', gridTemplateColumns: '1fr 320px', gap: 10, minHeight: '100%'}}>
      <div className="card" style={{padding: 0, overflow:'hidden', display:'flex', flexDirection:'column'}}>
        <PanelHeader title="full task schedule" right={scheduleRight}/>
        <div className="scroll" style={{flex:1, overflowY:'auto'}}>
          {s.tasks.map((t, i) => {
            const clickable = !s.running && (t.status === 'pending' || t.status === 'skipped');
            const label = t.status === 'pending' && !t.selected ? 'skip' : t.status;
            return (
            <div key={t.id}
              onClick={clickable ? ()=>window.PARSim.toggleSelected(t.id) : undefined}
              style={{
                display:'grid', gridTemplateColumns: '30px 1fr 140px 100px 80px', gap: 12, alignItems:'center',
                padding:'10px 16px', borderBottom:'1px solid var(--border)',
                background: t.status==='running' ? 'var(--accent-soft)' : 'transparent',
                opacity: t.status==='skipped' || (t.status==='pending' && !t.selected) ? 0.55 : 1,
                cursor: clickable ? 'pointer' : 'default',
              }}
              title={clickable ? (t.selected ? 'Click to skip' : 'Click to include') : ''}
            >
              <span className="mono" style={{color:'var(--text-dim)', fontSize: 11}}>{String(i+1).padStart(2,'0')}</span>
              <div>
                <div style={{
                  fontSize: 13,
                  fontWeight: t.status==='running' ? 500 : 400,
                  color: t.status==='pending' || t.status==='skipped' ? 'var(--text-sub)' : 'var(--text)',
                  textDecoration: t.status==='skipped' ? 'line-through' : 'none',
                }}>{t.label}</div>
                <div className="mono" style={{fontSize: 10.5, color:'var(--text-dim)', marginTop: 2}}>{t.id}</div>
              </div>
              <span className={`layer-badge layer-${t.layer}`} style={{justifySelf: 'start'}}>{t.layer}</span>
              <span className="mono" style={{fontSize: 11, color:'var(--text-sub)'}}>{(t.duration/1000).toFixed(1)}s</span>
              <span className="chip" style={{
                color: t.status==='done' ? 'var(--ok)' : t.status==='running' ? 'var(--accent)' : label==='skip' ? 'var(--text-dim)' : t.selected ? 'var(--accent)' : 'var(--text-dim)',
                borderColor: 'transparent',
                background: t.selected && t.status==='pending' ? 'var(--accent-soft)' : 'var(--bg-subtle)',
                justifySelf: 'start',
              }}>
                <span className={`dot ${t.status==='done'?'ok':t.status==='running'?'run':t.selected && t.status==='pending'?'ok':''}`}/>
                {label}
              </span>
            </div>
            );
          })}
        </div>
      </div>
      <div style={{display:'grid', gridTemplateRows: 'auto 1fr', gap: 10, minHeight: 0}}>
        <ScheduleCard/>
        <PanelEvents s={s}/>
      </div>
    </div>
  );
}

function PageResources({s}) {
  // Build each sparkline from the last 7 real history snapshots. When a field
  // isn't in the snapshots yet (we only started tracking arena tokens / shards
  // recently) the trend comes back with fewer points.
  const history = (s.history || []).slice(-7);
  const trend = (getter) => history.map(h => getter(h)).filter(v => v != null);
  const rows = [
    {icon:'energy', label:'Energy', val: fmt(s.resources.energy),
     trend: trend(h => h.energy), color:'oklch(0.82 0.17 85)', detail: 'Cap 130. Overflow drains on regen.'},
    {icon:'silver', label:'Silver', val: fmt(s.resources.silver,'silver'),
     trend: trend(h => h.silver_m), color:'var(--violet)', detail: 'Account silver. Market buy reserve.'},
    {icon:'shard',  label:'Gems', val: fmt(s.resources.gems),
     trend: trend(h => h.gems), color:'var(--accent)', detail: 'Reserved for Arena refreshes only.'},
    {icon:'arena',  label:'Arena tokens',
     val: s.resources.arena_tokens != null ? Number(s.resources.arena_tokens).toFixed(1) : '—',
     trend: trend(h => h.arena_tokens), color:'oklch(0.75 0.18 180)', detail: 'Auto-regen 1 / 2h.'},
    {icon:'cb',     label:'CB keys', val: `${s.resources.cb_keys}/2`,
     trend: trend(h => h.cb_keys), color:'oklch(0.70 0.20 25)', detail: 'Reset 06:00 UTC.'},
    {icon:'shard_mystery', label:'Mystery shards',
     val: s.resources.mystery_shards != null ? s.resources.mystery_shards : '—',
     trend: trend(h => (h.shards || {}).mystery), color:'var(--text-sub)', detail: 'Weekly quest source.'},
  ];
  return (
    <div style={{display:'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10}}>
      {rows.map(r => (
        <div key={r.label} className="card" style={{padding: 16}}>
          <div style={{display:'flex', alignItems:'center', gap:8, fontSize: 11, color:'var(--text-sub)', textTransform:'uppercase', letterSpacing:'0.06em'}}>
            <Icon name={r.icon} size={14}/> {r.label}
          </div>
          <div style={{display:'flex', alignItems:'end', justifyContent:'space-between', marginTop: 8}}>
            <div style={{fontSize: 26, fontWeight: 600, letterSpacing:'-0.01em'}} className="num">{r.val}</div>
            {r.trend && r.trend.length >= 2
              ? <Spark data={r.trend} color={r.color} width={80} height={32} fill/>
              : <span style={{fontSize: 10, color:'var(--text-dim)', fontStyle:'italic'}}>collecting…</span>
            }
          </div>
          <div style={{fontSize: 11, color:'var(--text-dim)', marginTop: 10}}>{r.detail}</div>
        </div>
      ))}
      <div className="card" style={{padding: 16, gridColumn: 'span 3'}}>
        <div className="card-title" style={{marginBottom: 10}}>Keys & tokens</div>
        <div style={{display:'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 10}}>
          {[
            ['Classic Arena',      'classic_arena_tokens', 'arena',     'oklch(0.72 0.18 180)'],
            ['Tag Arena 3v3',      'tag_arena_tokens',     'arena',     'oklch(0.72 0.18 180)'],
            ['Live Arena',         'live_arena_tokens',    'arena',     'oklch(0.68 0.18 250)'],
            ['CB (Demon Lord)',    'demon_lord_keys',      'cb',        'oklch(0.70 0.20 25)'],
            ['Hydra',              'hydra_keys',           'cb',        'oklch(0.72 0.17 145)'],
            ['Chimera',            'chimera_keys',         'cb',        'oklch(0.68 0.22 315)'],
            ['Fortress',           'fortress_keys',        'cb',        'oklch(0.78 0.17 85)'],
            ['Cursed City',        'cursed_city_keys',     'cb',        'oklch(0.64 0.24 20)'],
            ['Doom Tower (Gold)',  'doom_tower_gold_keys', 'cb',        'oklch(0.80 0.16 85)'],
            ['Doom Tower (Silver)','doom_tower_silver_keys','cb',       'var(--text-sub)'],
            ['Auto tickets',       'auto_tickets',         'arena',     'var(--text-sub)'],
          ].map(([label, key, icon, col]) => {
            const v = (s.resources.keys || {})[key];
            return (
              <div key={key} style={{padding:'10px 12px', background:'var(--bg-subtle)', borderRadius: 6, border:'1px solid var(--border)', display:'flex', alignItems:'center', gap: 10}}>
                <Icon name={icon} size={22}/>
                <div style={{minWidth: 0, flex: 1}}>
                  <div style={{fontSize: 10, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.04em'}} className="truncate">{label}</div>
                  <div style={{fontSize: 18, fontWeight: 600, color: v == null ? 'var(--text-dim)' : col, marginTop: 2}} className="num">
                    {v == null ? '—' : v}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <ShardsInventory s={s}/>
    </div>
  );
}

function ShardsInventory({s}) {
  const [open, setOpen] = React.useState(null); // which shard key is open, or null
  const shards = [
    {key:'mystery', label:'Mystery', icon:'shard_mystery', val: s.resources.mystery_shards, color:'var(--text-sub)'},
    {key:'ancient', label:'Ancient', icon:'shard_ancient', val: s.resources.ancient_shards, color:'oklch(0.65 0.18 255)'},
    {key:'void',    label:'Void',    icon:'shard_void',    val: s.resources.void_shards,    color:'var(--violet)'},
    {key:'sacred',  label:'Sacred',  icon:'shard_sacred',  val: s.resources.sacred_shards,  color:'oklch(0.78 0.15 85)'},
    {key:'primal',  label:'Primal',  icon:'shard_primal',  val: s.resources.primal_shards,  color:'oklch(0.68 0.22 20)'},
  ];
  const active = open ? shards.find(x => x.key === open) : null;
  return (
    <div className="card" style={{padding: 16, gridColumn: 'span 3'}}>
      <div className="card-title" style={{marginBottom: 10}}>Shards inventory</div>
      <div style={{display:'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12}}>
        {shards.map(sh => (
          <div key={sh.key}
               onClick={() => sh.val != null && setOpen(sh.key)}
               style={{padding:'12px 14px', background:'var(--bg-subtle)', borderRadius: 6, border:'1px solid var(--border)', display:'flex', alignItems:'center', gap: 12, cursor: sh.val != null ? 'pointer' : 'default'}}>
            <Icon name={sh.icon} size={40} alt={sh.label + ' shard'}/>
            <div style={{minWidth: 0}}>
              <div style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em'}}>{sh.label}</div>
              <div style={{fontSize: 22, fontWeight: 600, color: sh.val == null ? 'var(--text-dim)' : sh.color, marginTop: 2}} className="num">
                {sh.val == null ? '—' : sh.val}
              </div>
            </div>
          </div>
        ))}
      </div>
      {active && <ShardHistoryModal shard={active} history={s.history} onClose={()=>setOpen(null)}/>}
    </div>
  );
}

function ShardHistoryModal({shard, history, onClose}) {
  // Pull this shard's count from each day's history entry (history[i].shards[key])
  const series = (history || [])
    .map(h => ({day: h.day, v: (h.shards || {})[shard.key]}))
    .filter(p => p.v != null);
  const hasData = series.length >= 1;
  const values = series.map(p => p.v);
  const min = hasData ? Math.min(...values) : 0;
  const max = hasData ? Math.max(...values) : 0;
  // Chart dimensions
  const W = 560, H = 180, P = 28;
  const range = max - min || 1;
  const pts = series.map((p, i) => {
    const x = P + (series.length > 1 ? i * (W - 2*P) / (series.length - 1) : (W - 2*P)/2);
    const y = H - P - ((p.v - min) / range) * (H - 2*P);
    return [x, y, p.v, p.day];
  });
  const path = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');
  // Deltas between consecutive days (show biggest jumps)
  const jumps = series.slice(1).map((p, i) => ({
    day: p.day, delta: p.v - series[i].v
  })).filter(j => j.delta !== 0).sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta)).slice(0, 5);

  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', zIndex: 200,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div onClick={e => e.stopPropagation()} className="card" style={{
        padding: 20, width: 640, maxWidth: '92vw', maxHeight: '88vh', overflow: 'auto',
        background: 'var(--bg-elev)', border: '1px solid var(--border-strong)',
      }}>
        <div style={{display:'flex', alignItems:'center', gap: 12, marginBottom: 16}}>
          <Icon name={shard.icon} size={40}/>
          <div style={{flex: 1}}>
            <div style={{fontSize: 11, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em'}}>{shard.label} shard</div>
            <div style={{fontSize: 26, fontWeight: 600, color: shard.color}} className="num">
              {shard.val != null ? shard.val : '—'}
            </div>
          </div>
          <button className="btn ghost" onClick={onClose} style={{height: 28, padding: '0 10px'}}>Close</button>
        </div>

        {!hasData && (
          <div style={{padding: 28, fontSize: 12, color:'var(--text-dim)', textAlign:'center'}}>
            No history yet for this shard. Snapshots start recording now — come back tomorrow.
          </div>
        )}

        {hasData && (
          <>
            <svg viewBox={`0 0 ${W} ${H+20}`} width="100%" height={H + 22} style={{display:'block', marginBottom: 12}}>
              {[0, 0.25, 0.5, 0.75, 1].map((t, i) => (
                <line key={i} x1={P} x2={W-P} y1={P + t*(H-2*P)} y2={P + t*(H-2*P)} stroke="var(--border)" strokeDasharray="2 4"/>
              ))}
              <path d={path + ` L${pts[pts.length-1][0]},${H-P} L${pts[0][0]},${H-P} Z`} fill={shard.color} opacity={0.12}/>
              <path d={path} fill="none" stroke={shard.color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              {pts.map((p, i) => (
                <g key={i}>
                  <circle cx={p[0]} cy={p[1]} r="3" fill={shard.color}/>
                  <text x={p[0]} y={H+14} fontSize="10" fill="var(--text-dim)" textAnchor="middle" fontFamily="'JetBrains Mono', monospace">{p[3]}</text>
                </g>
              ))}
              {/* min/max y labels */}
              <text x={P-6} y={P+4} fontSize="10" fill="var(--text-dim)" textAnchor="end" fontFamily="'JetBrains Mono', monospace">{max}</text>
              <text x={P-6} y={H-P+4} fontSize="10" fill="var(--text-dim)" textAnchor="end" fontFamily="'JetBrains Mono', monospace">{min}</text>
            </svg>

            <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap: 16}}>
              <div>
                <div className="card-title" style={{marginBottom: 6}}>Stats</div>
                <div style={{fontSize: 12, lineHeight: 1.8, color:'var(--text-sub)'}}>
                  <div>Data points · <span className="mono">{series.length}</span></div>
                  <div>Min / Max · <span className="mono">{min} / {max}</span></div>
                  <div>Latest · <span className="mono" style={{color: shard.color}}>{series[series.length-1].v}</span></div>
                </div>
              </div>
              <div>
                <div className="card-title" style={{marginBottom: 6}}>Biggest changes</div>
                {jumps.length === 0 ? (
                  <div style={{fontSize: 11.5, color:'var(--text-dim)'}}>No day-over-day changes yet.</div>
                ) : (
                  <div style={{fontSize: 12, lineHeight: 1.8}} className="mono">
                    {jumps.map(j => (
                      <div key={j.day} style={{display:'flex', justifyContent:'space-between'}}>
                        <span style={{color:'var(--text-dim)'}}>{j.day}</span>
                        <span style={{color: j.delta > 0 ? 'var(--ok)' : 'var(--danger)'}}>{j.delta > 0 ? '+' : ''}{j.delta}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function PageCB({s}) {
  const avg = s.cb.history.reduce((a,h)=>a+h.dmg,0) / s.cb.history.length;
  const lr = s.cb.last_run;
  const team = s.cb.team;
  const totalDealt = team.reduce((a,t)=>a+t.dmg_dealt,0);
  const totalTaken = team.reduce((a,t)=>a+t.dmg_taken,0);
  const rarityColor = RARITY_COLORS;
  const [runDetailOpen, setRunDetailOpen] = React.useState(false);
  // CB reset countdown — fetched once, ticks per second.
  const [resetInfo, setResetInfo] = React.useState(null);
  const [resetTick, setResetTick] = React.useState(0);
  React.useEffect(() => {
    fetch('/api/cb-reset-info').then(r => r.json()).then(setResetInfo).catch(()=>{});
    const id = setInterval(() => setResetTick(t => t + 1), 1000);
    return () => clearInterval(id);
  }, []);
  const secsUntilReset = resetInfo ? Math.max(0, resetInfo.seconds_until_reset - resetTick) : null;
  const fmtReset = (s) => {
    if (s == null) return '—';
    const h = Math.floor(s/3600), m = Math.floor((s%3600)/60), sec = s%60;
    return `${h}h ${String(m).padStart(2,'0')}m ${String(sec).padStart(2,'0')}s`;
  };
  return (
    <div style={{display:'grid', gridTemplateColumns: '1fr 340px', gap: 10, minHeight: 0}}>
      {/* Top — summary + day chart */}
      <div className="card" style={{padding: 18, gridColumn: '1 / -1'}}>
        <div style={{display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom: 14}}>
          <div>
            <div style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em'}}>Clan boss</div>
            <div style={{fontSize: 22, fontWeight: 500, marginTop: 4}}>{s.cb.difficulty} · <span style={{color:'var(--text-sub)'}}>{s.cb.affinity} affinity</span></div>
            <div style={{fontSize: 11, color:'var(--text-dim)', marginTop: 4}} className="mono">{s.cb.clan} · boss HP {(s.cb.boss_hp/1e6).toFixed(0)}M</div>
          </div>
          <div style={{display:'grid', gridTemplateColumns: 'repeat(4, auto)', gap: 22, alignItems:'center'}}>
            <div><div style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em'}}>Today</div>
              <div style={{fontSize: 24, fontWeight: 600}} className="num">
                {s.cb.damage_today ? (s.cb.damage_today/1e6).toFixed(1) + 'M' : '—'}
              </div></div>
            <div><div style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em'}}>7-day avg</div>
              <div style={{fontSize: 24, fontWeight: 600}} className="num">{(avg/1e6).toFixed(1)}<span style={{fontSize: 12, color:'var(--text-sub)', fontWeight: 400}}>M</span></div></div>
            <div><div style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em'}}>Keys</div>
              <div style={{fontSize: 24, fontWeight: 600, color: s.resources.cb_keys > 0 ? 'var(--accent)' : 'var(--text-dim)'}} className="num">{s.resources.cb_keys}<span style={{fontSize: 12, color:'var(--text-sub)', fontWeight: 400}}>/2</span></div></div>
            <div title={resetInfo ? `Resets at ${resetInfo.reset_hour_utc}:00 UTC` : ''}>
              <div style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em'}}>Next reset</div>
              <div className="num mono" style={{fontSize: 18, fontWeight: 600, color: secsUntilReset != null && secsUntilReset < 3600 ? 'var(--accent)' : 'var(--text)', letterSpacing: '-0.02em'}}>
                {fmtReset(secsUntilReset)}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom-left — Team composition summary (click to open full detail modal) */}
      <div className="card"
           onClick={() => setRunDetailOpen(true)}
           style={{padding: 0, overflow:'hidden', display:'flex', flexDirection:'column', cursor:'pointer'}}
           title="Click for turn-by-turn detail">
        <PanelHeader title="team composition · last run"
                     right={`${team.length} heroes · ${lr.turns_total || 0} turns · click for detail →`}/>
        {(() => {
          // Shared column template — applied to header, body rows, and total row
          // so everything aligns to the same grid. Numeric columns are right-
          // aligned; the preset index and hero name are left-aligned.
          const cols = '28px minmax(0, 1.8fr) 96px 56px 56px 96px 96px 52px';
          const numR = {textAlign: 'right'};
          return (
            <>
              <div style={{display:'grid', gridTemplateColumns: cols, padding:'8px 16px', fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em', borderBottom:'1px solid var(--border)', background:'var(--bg-subtle)', columnGap: 10, alignItems:'center'}}>
                <span style={numR}>#</span>
                <span>Hero</span>
                <span>Role</span>
                <span style={numR}>SPD</span>
                <span style={numR}>Turns</span>
                <span style={numR}>Dmg dealt</span>
                <span style={numR}>Dmg taken</span>
                <span style={numR}>Ctr</span>
              </div>
              <div>
                {team.map((h,i) => {
                  const slot = h.preset_slot || (i + 1);
                  return (
                    <div key={h.name} style={{padding:'10px 16px', borderBottom:'1px solid var(--border)'}}>
                      <div style={{display:'grid', gridTemplateColumns: cols, alignItems:'center', fontSize: 12, columnGap: 10}}>
                        <span className="mono" style={{...numR, color:'var(--text-dim)', fontSize: 11}}>{slot}</span>
                        <div style={{minWidth: 0}}>
                          <div style={{fontWeight: 500, display:'flex', alignItems:'center', gap: 6}}>
                            {i===0 && <span style={{fontSize: 9, color:'var(--accent)', border:'1px solid var(--accent)', padding:'1px 4px', borderRadius: 3}}>LEAD</span>}
                            <span className="truncate">{h.name}</span>
                          </div>
                          <div style={{fontSize: 10.5, color: rarityColor[h.rarity], marginTop: 2}}>{h.rarity} · {h.faction}</div>
                        </div>
                        <span style={{color:'var(--text-sub)', fontSize: 11.5}} className="truncate">{h.role}</span>
                        <span className="mono" style={{...numR, color:'var(--text-sub)'}}>{h.spd}</span>
                        <span className="mono" style={{...numR, color:'var(--text-sub)'}}>{h.turns}</span>
                        <div style={{display:'flex', flexDirection:'column', alignItems:'stretch', width:'100%'}}>
                          <div className="mono num" style={{textAlign:'right'}}>{(h.dmg_dealt/1e6).toFixed(2)}M</div>
                          <div style={{display:'block', width:'100%', height: 4, background:'var(--bg-subtle)', borderRadius: 2, marginTop: 4, overflow:'hidden'}}>
                            <div style={{width:`${Math.min(100, (h.dmg_dealt/totalDealt)*100)}%`, height:'100%', background:'var(--accent)'}}/>
                          </div>
                        </div>
                        <div style={{display:'flex', flexDirection:'column', alignItems:'stretch', width:'100%'}}>
                          <div className="mono num" style={{color:'var(--text-sub)', textAlign:'right'}}>{(h.dmg_taken/1e6).toFixed(2)}M</div>
                          <div style={{display:'block', width:'100%', height: 4, background:'var(--bg-subtle)', borderRadius: 2, marginTop: 4, overflow:'hidden'}}>
                            <div style={{width:`${Math.min(100, (h.dmg_taken/totalTaken)*100)}%`, height:'100%', background:'oklch(0.70 0.18 25)'}}/>
                          </div>
                        </div>
                        <span className="mono" style={{...numR, color: h.counters > 0 ? 'var(--violet)' : 'var(--text-dim)'}}>{h.counters || '—'}</span>
                      </div>
                    </div>
                  );
                })}
                {(() => {
                  // Authoritative boss damage from battle log (lr.damage). Always
                  // >= the sum of attributed per-hero damage — the gap is DoT
                  // ticks / counter damage not tied to a specific hero slot.
                  const runDmg = lr.damage || totalDealt;
                  const unattributed = Math.max(0, runDmg - totalDealt);
                  const attrNote = unattributed > 0
                    ? ` (${(totalDealt/1e6).toFixed(2)}M attributed + ${(unattributed/1e6).toFixed(2)}M DoT/other)`
                    : '';
                  return (
                    <div style={{padding:'8px 16px', display:'grid', gridTemplateColumns: cols, fontSize: 11, color:'var(--text-dim)', background:'var(--bg-subtle)', columnGap: 10, alignItems:'center'}}
                         title={unattributed > 0 ? `Per-hero sum ${(totalDealt/1e6).toFixed(2)}M plus ${(unattributed/1e6).toFixed(2)}M of DoT ticks & other unattributed damage = run total ${(runDmg/1e6).toFixed(2)}M` : undefined}>
                      <span></span>
                      <span>Total{attrNote}</span>
                      <span></span>
                      <span></span>
                      <span className="mono" style={numR}>{team.reduce((a,t)=>a+t.turns,0)}</span>
                      <span className="mono num" style={{...numR, color:'var(--accent)'}}>{(runDmg/1e6).toFixed(2)}M</span>
                      <span className="mono num" style={{...numR, color:'oklch(0.70 0.18 25)'}}>{(totalTaken/1e6).toFixed(2)}M</span>
                      <span className="mono" style={{...numR, color:'var(--violet)'}}>{team.reduce((a,t)=>a+t.counters,0)}</span>
                    </div>
                  );
                })()}
              </div>
            </>
          );
        })()}
      </div>

      {/* Bottom-right — Run stats + debuffs + timeline */}
      <div style={{display:'grid', gridTemplateRows: 'auto auto auto', gap: 10}}>
        <div className="card" style={{padding: 14}}>
          <div className="card-title" style={{marginBottom: 10}}>Run stats</div>
          <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap: 10, fontSize: 12}}>
            <div><div style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase'}}>Duration</div><div className="mono num" style={{fontSize: 15, marginTop: 2}}>
              {lr.duration_s ? `${Math.floor(lr.duration_s/60)}:${String(lr.duration_s%60).padStart(2,'0')}` : '—'}
            </div></div>
            <div><div style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase'}}>Turns</div><div className="mono num" style={{fontSize: 15, marginTop: 2}}>{lr.turns_total}</div></div>
            <div><div style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase'}}>Damage</div><div className="mono num" style={{fontSize: 15, marginTop: 2, color:'var(--accent)'}}>{(lr.damage/1e6).toFixed(2)}M</div></div>
            <div><div style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase'}}>Dmg taken</div><div className="mono num" style={{fontSize: 15, marginTop: 2, color:'oklch(0.70 0.18 25)'}}>{(lr.damage_taken/1e6).toFixed(2)}M</div></div>
            <div><div style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase'}}>Unkillable</div><div className="mono num" style={{fontSize: 15, marginTop: 2}}>{lr.unkillable_triggers}×</div></div>
            <div><div style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase'}}>Counters</div><div className="mono num" style={{fontSize: 15, marginTop: 2, color:'var(--violet)'}}>{lr.counters_total}×</div></div>
          </div>
        </div>
        <div className="card" style={{padding: 14}}>
          <div className="card-title" style={{marginBottom: 10}}>Debuffs applied</div>
          {Object.entries(lr.debuffs_applied).map(([d,n]) => {
            const max = Math.max(...Object.values(lr.debuffs_applied));
            return (
              <div key={d} style={{marginBottom: 7}}>
                <div style={{display:'flex', justifyContent:'space-between', fontSize: 11.5, marginBottom: 3}}>
                  <span style={{color:'var(--text-sub)'}}>{d}</span>
                  <span className="mono" style={{color:'var(--text)'}}>{n}×</span>
                </div>
                <div style={{height: 3, background:'var(--bg-subtle)', borderRadius: 2, overflow:'hidden'}}>
                  <div style={{width:`${(n/max)*100}%`, height:'100%', background:'var(--violet)'}}/>
                </div>
              </div>
            );
          })}
        </div>
        <div className="card" style={{padding: 0, overflow:'hidden', display:'flex', flexDirection:'column'}}>
          <PanelHeader title="boss turns" right={`${(lr.turn_log || []).length} of 50 · ${s.cb.difficulty || ''}`}/>
          <div style={{padding: '4px 0', maxHeight: 360, overflowY: 'auto'}}>
            {(() => {
              const tl = lr.turn_log || [];
              if (!tl.length) {
                return <div style={{padding:'10px 14px', fontSize: 11.5, color:'var(--text-dim)'}}>No turn-by-turn log captured for this run.</div>;
              }
              const maxDmg = Math.max(1, ...tl.map(t => t.damage || 0));
              const actionColor = {AOE1:'oklch(0.70 0.18 25)', AOE2:'oklch(0.70 0.18 25)', STUN:'var(--violet)'};
              return tl.map((t,i) => {
                const prot = t.protection || {};
                const heroes = Object.keys(prot);
                const naked = heroes.filter(h => !(prot[h].uk || prot[h].bd || prot[h].sh));
                const dmgPct = ((t.damage || 0) / maxDmg) * 100;
                return (
                  <div key={i} style={{display:'grid', gridTemplateColumns:'42px 56px 1fr 80px', gap: 8, padding:'4px 14px', fontSize: 11.5, alignItems:'center', borderBottom: i < tl.length-1 ? '1px solid var(--border)' : 'none'}}>
                    <span className="mono" style={{color:'var(--text-dim)', fontSize: 10.5}}>bt {t.boss_turn}</span>
                    <span className="mono" style={{fontSize: 10, color: actionColor[t.boss_action] || 'var(--text-sub)', fontWeight: 500}}>{t.boss_action || '—'}</span>
                    <div style={{display:'flex', flexDirection:'column', gap: 2}}>
                      <div style={{height: 3, background:'var(--bg-subtle)', borderRadius: 2, overflow:'hidden'}}>
                        <div style={{width: `${dmgPct}%`, height:'100%', background:'var(--accent)'}}/>
                      </div>
                      {heroes.length > 0 && (
                        <span className="mono" style={{fontSize: 9.5, color: naked.length ? 'var(--danger)' : 'var(--text-dim)'}}>
                          {heroes.map(h => {
                            const p = prot[h];
                            if (p.uk) return 'U';
                            if (p.bd) return 'B';
                            if (p.sh) return 'S';
                            return '·';
                          }).join('')}
                          {naked.length > 0 && ` · ${naked.length} naked`}
                        </span>
                      )}
                    </div>
                    <span className="mono num" style={{textAlign:'right', color: 'var(--accent)'}}>{((t.damage || 0)/1e6).toFixed(2)}M</span>
                  </div>
                );
              });
            })()}
          </div>
          <div style={{padding:'6px 14px', fontSize: 9.5, color:'var(--text-dim)', borderTop:'1px solid var(--border)', background:'var(--bg-subtle)'}} className="mono">
            U=unkillable · B=block-dmg · S=shield · ·=naked
          </div>
        </div>
      </div>

      {runDetailOpen && (
        <CBRunDetailModal s={s} lr={lr} team={team} totalDealt={totalDealt} totalTaken={totalTaken}
                          rarityColor={rarityColor} onClose={()=>setRunDetailOpen(false)}/>
      )}

      {/* ======= Tune Lab — DWJ comps + parity sim + compliance + recommender ======= */}
      <CBTuneLab potentialTeams={s.cb.potential_teams || []} initialSim={s.cb.calc_parity_sim || null}/>

      {/* ======= 7-day damage history ======= */}
      <CBHistoryPanel history={s.cb.history} perKey={s.cb.per_key_history}/>

    </div>
  );
}

const RARITY_NAMES_BY_ID = {1:'Common', 2:'Uncommon', 3:'Rare', 4:'Epic', 5:'Legendary', 6:'Mythical'};
// Palette mirrors Raid's shard colors: legendary=gold (ancient shard), epic=pink/purple (void),
// rare=blue (ancient frame), uncommon=green, mythical=red (primal).
const RARITY_COLORS = {
  Common:    'var(--text-sub)',
  Uncommon:  'oklch(0.72 0.17 145)',   // green
  Rare:      'oklch(0.68 0.18 250)',   // blue
  Epic:      'oklch(0.68 0.22 315)',   // pink/purple
  Legendary: 'oklch(0.80 0.16 85)',    // gold
  Mythical:  'oklch(0.64 0.24 20)',    // red
};

/* ===================== Dungeons ===================== */

const DUNGEON_OPTIONS = [
  {id: 'dragon',       label: "Dragon's Lair"},
  {id: 'spider',       label: "Spider's Den"},
  {id: 'fire_knight',  label: 'Fire Knight Castle'},
  {id: 'ice_golem',    label: 'Ice Golem Peak'},
  {id: 'minotaur',     label: "Minotaur's Labyrinth"},
  {id: 'void_keep',    label: 'Void Keep'},
  {id: 'spirit_keep',  label: 'Spirit Keep'},
  {id: 'magic_keep',   label: 'Magic Keep'},
  {id: 'force_keep',   label: 'Force Keep'},
  {id: 'arcane_keep',  label: 'Arcane Keep'},
];

function PageDungeons({s}) {
  const [dungeon, setDungeon] = React.useState('minotaur');
  const [stageMode, setStageMode] = React.useState('max');   // 'max' | 'fixed'
  const [stageNum, setStageNum] = React.useState(15);
  const [stopType, setStopType] = React.useState('capped');  // 'capped' | 'runs'
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
        const r = await fetch('/api/dungeons/state', {cache: 'no-store'});
        if (r.ok && alive) setState(await r.json());
      } catch (e) {}
    }
    poll();
    const id = setInterval(poll, 1000);
    return () => { alive = false; clearInterval(id); };
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
  const elapsedRun = startedAt && running ? Math.floor(Date.now()/1000 - startedAt) : null;
  const energyUsed = state && state.energy_start != null && state.energy_now != null
    ? Math.max(0, state.energy_start - state.energy_now) : null;
  const silverEarned = state && state.silver_start != null && state.silver_now != null
    ? Math.max(0, state.silver_now - state.silver_start) : null;

  // Cap stop is minotaur-only — auto-switch to runs if user picks another dungeon.
  const stopTypeEffective = (dungeon !== 'minotaur' && stopType === 'capped')
    ? 'runs' : stopType;

  async function start() {
    setErrorMsg('');
    setStarting(true);
    const stage = stageMode === 'max' ? 'max' : Number(stageNum);
    const stop_condition = stopTypeEffective === 'capped'
      ? {type: 'capped'}
      : {type: 'runs', n: Math.max(1, Number(runsN))};
    try {
      const r = await fetch('/api/dungeons/start', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({dungeon, stage, stop_condition}),
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
    try { await fetch('/api/dungeons/run', {method: 'DELETE'}); }
    catch (e) { setErrorMsg(String(e)); setStopping(false); }
  }

  const fmtSec = (sec) => {
    if (sec == null) return '—';
    const m = Math.floor(sec/60), s = sec%60;
    return m > 0 ? `${m}m${String(s).padStart(2,'0')}s` : `${s}s`;
  };

  const dungeonLabel = (DUNGEON_OPTIONS.find(d => d.id === (state && state.dungeon))
                       || {label: '—'}).label;

  return (
    <div style={{display:'grid', gap: 12, gridTemplateColumns: '380px 1fr', alignItems: 'start'}}>
      {/* ==== Config card ==== */}
      <div className="card" style={{padding: 0, overflow:'hidden'}}>
        <PanelHeader title="dungeon loop" right={running ? <span className="mono" style={{color:'var(--accent)'}}>RUNNING</span> : null}/>
        <div style={{padding: 12, display:'grid', gap: 10}}>

          <div>
            <label style={lbl}>Dungeon</label>
            <select disabled={running} value={dungeon}
                    onChange={e=>setDungeon(e.target.value)} style={sel}>
              {DUNGEON_OPTIONS.map(d => (
                <option key={d.id} value={d.id}>{d.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label style={lbl}>Stage</label>
            <div style={{display:'flex', gap: 6}}>
              <select disabled={running} value={stageMode}
                      onChange={e=>setStageMode(e.target.value)} style={{...sel, flex: '0 0 140px'}}>
                <option value="max">Max visible</option>
                <option value="fixed">Specific stage</option>
              </select>
              {stageMode === 'fixed' && (
                <select disabled={running} value={stageNum}
                        onChange={e=>setStageNum(Number(e.target.value))} style={sel}>
                  {Array.from({length:25}, (_,i)=>i+1).map(n => (
                    <option key={n} value={n}>Stage {n}</option>
                  ))}
                </select>
              )}
            </div>
          </div>

          <div>
            <label style={lbl}>Stop condition</label>
            <select disabled={running} value={stopTypeEffective}
                    onChange={e=>setStopType(e.target.value)} style={sel}>
              <option value="capped" disabled={dungeon !== 'minotaur'}>
                All heroes scroll-capped {dungeon !== 'minotaur' ? '(minotaur only)' : ''}
              </option>
              <option value="runs">Number of runs</option>
            </select>
          </div>

          {stopTypeEffective === 'runs' && (
            <div>
              <label style={lbl}>Runs</label>
              <input type="number" min="1" max="9999" disabled={running}
                     value={runsN} onChange={e=>setRunsN(e.target.value)}
                     style={sel}/>
            </div>
          )}

          <div style={{display:'flex', gap: 8, marginTop: 4}}>
            {starting ? (
              <button className="btn primary" disabled style={{flex: 1, height: 30, justifyContent:'center'}}>
                <span className="dungeon-spinner" style={{
                  width: 12, height: 12, borderWidth: 2,
                  borderTopColor: '#0b0d10', borderRightColor:'transparent',
                  borderBottomColor:'rgba(11,13,16,0.4)', borderLeftColor:'rgba(11,13,16,0.4)',
                  marginRight: 8,
                }}/>
                Starting...
              </button>
            ) : stopping ? (
              <button className="btn" disabled style={{flex: 1, height: 30, justifyContent:'center'}}>
                <span className="dungeon-spinner" style={{
                  width: 12, height: 12, borderWidth: 2, marginRight: 8,
                }}/>
                Stopping (current battle finishes)...
              </button>
            ) : !running ? (
              <button className="btn primary" onClick={start} style={{flex: 1, height: 30}}>
                <SvgIcon.play/> Start loop
              </button>
            ) : (
              <button className="btn" onClick={stop} style={{flex: 1, height: 30}}>
                <SvgIcon.pause/> Stop
              </button>
            )}
          </div>

          {errorMsg && (
            <div className="mono" style={{fontSize: 11, color: '#e07a5f'}}>{errorMsg}</div>
          )}
        </div>
      </div>

      {/* ==== Status card ==== */}
      <div style={{display:'grid', gap: 12}}>
        <DungeonTeamPanel s={s} team={state && state.team} running={running}/>
      <div className="card" style={{padding: 0, overflow:'hidden'}}>
        <PanelHeader title="status"
                     right={state && state.last_status
                            ? <span className="mono" style={{color:'var(--text-dim)'}}>last: {state.last_status}</span>
                            : null}/>
        <div style={{padding: 16, display:'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14}}>
          <div>
            <div style={statLbl}>Dungeon</div>
            <div style={statVal}>{state && state.dungeon ? dungeonLabel : '—'}</div>
          </div>
          <div>
            <div style={statLbl}>Stage</div>
            <div style={statVal}>{state && state.stage != null ? state.stage : '—'}</div>
          </div>
          <div>
            <div style={statLbl}>Progress</div>
            <div style={statVal}>
              {target != null
                ? `${completed}/${target}`
                : (running ? `${completed} (capped)` : completed || '—')}
            </div>
          </div>
          <div>
            <div style={statLbl}>Elapsed</div>
            <div style={statVal}>{fmtSec(elapsedRun)}</div>
          </div>

          <div>
            <div style={statLbl}>Energy used</div>
            <div style={statVal}>{energyUsed != null ? energyUsed.toLocaleString() : '—'}</div>
          </div>
          <div>
            <div style={statLbl}>Silver earned</div>
            <div style={statVal}>{silverEarned != null ? silverEarned.toLocaleString() : '—'}</div>
          </div>
          <div>
            <div style={statLbl}>Failures</div>
            <div style={statVal}>{failures || '—'}</div>
          </div>
          <div>
            <div style={statLbl}>Last battle</div>
            <div style={statVal}>{state && state.last_elapsed_s != null ? `${state.last_elapsed_s}s` : '—'}</div>
          </div>
        </div>

        {running && (
          <div style={{padding: '10px 16px', borderTop:'1px solid var(--border)', display:'flex', alignItems:'center', gap: 10}}>
            <div className="dungeon-spinner"/>
            <span className="mono" style={{fontSize: 11, color:'var(--text-sub)'}}>
              {state.last_status === 'victory' ? 'Replaying...' : 'Battle in progress...'}
            </span>
          </div>
        )}

        {!running && state && state.result_reason && (
          <div style={{padding: '10px 16px', borderTop:'1px solid var(--border)', fontSize: 11, color:'var(--text-sub)'}}>
            <span className="mono">last result: {state.result_reason}</span>
            {state.result_reason === 'capped' && completed > 0 && (
              <span className="mono" style={{marginLeft: 8, color:'var(--accent)'}}>
                {completed} successful run{completed === 1 ? '' : 's'}
              </span>
            )}
          </div>
        )}
      </div>
      </div>
    </div>
  );
}

function DungeonTeamPanel({s, team, running}) {
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
  const status = !team || team.length === 0
    ? (running ? 'detecting team...' : 'team detected once a battle starts')
    : `${team.length} hero${team.length === 1 ? '' : 'es'} in active team`;
  return (
    <div className="card" style={{padding: 0, overflow:'hidden'}}>
      <PanelHeader title="active team" right={
        <span className="mono" style={{fontSize: 10.5, color:'var(--text-dim)'}}>{status}</span>
      }/>
      <div style={{padding: 14, display:'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10}}>
        {tids.map((tid, i) => (
          <DungeonTeamSlot key={i} idx={i} hero={tid != null ? byType.get(tid) : null}
                           tid={tid}/>
        ))}
      </div>
    </div>
  );
}

function DungeonTeamSlot({idx, hero, tid}) {
  if (!hero) {
    return (
      <div style={{
        border: '1px dashed var(--border-strong)', borderRadius: 6,
        padding: '10px 8px', minHeight: 88, textAlign: 'center',
        display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center',
        color:'var(--text-dim)', fontSize: 11,
      }}>
        <div style={{fontSize: 18, color:'var(--border-strong)', marginBottom: 2}}>{idx + 1}</div>
        <div className="mono" style={{fontSize: 10}}>
          {tid != null ? `#${tid}` : 'empty slot'}
        </div>
      </div>
    );
  }
  const rarityColor = (typeof RARITY_COLORS !== 'undefined' && RARITY_COLORS[hero.rarity])
    || 'var(--accent)';
  return (
    <div style={{
      border: `1px solid ${rarityColor}`,
      borderRadius: 6, padding: '8px 8px 10px',
      background: 'var(--bg-elev)',
      display:'flex', flexDirection:'column', gap: 4,
    }}>
      <div style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
        <span className="mono" style={{fontSize: 10, color:'var(--text-dim)'}}>
          slot {idx + 1}
        </span>
        <span className="mono" style={{fontSize: 10, color: rarityColor}}>
          {hero.rarity || ''}
        </span>
      </div>
      <div style={{fontSize: 13, fontWeight: 600, lineHeight: 1.2,
                   color:'var(--text)', minHeight: 32}}>
        {hero.name}
      </div>
      <div className="mono" style={{fontSize: 10.5, color:'var(--text-sub)',
                                    display:'flex', gap: 6, flexWrap:'wrap'}}>
        <span>{'★'.repeat(Math.min(6, hero.stars || 0))}</span>
        <span>L{hero.level || '?'}</span>
        {hero.empower ? <span>+{hero.empower}</span> : null}
        {hero.element ? <span style={{color:'var(--text-dim)'}}>{hero.element}</span> : null}
      </div>
    </div>
  );
}

const lbl = {display:'block', fontSize: 10.5, color:'var(--text-dim)',
             textTransform:'uppercase', letterSpacing:'0.06em',
             marginBottom: 4, fontWeight: 600};
const sel = {width:'100%', height: 28, padding:'0 8px',
             background:'var(--bg-elev)', color:'var(--text)',
             border:'1px solid var(--border-strong)', borderRadius: 4,
             fontSize: 12, fontFamily: 'inherit'};
const statLbl = {fontSize: 10.5, color:'var(--text-dim)',
                 textTransform:'uppercase', letterSpacing:'0.06em', marginBottom: 4};
const statVal = {fontSize: 16, fontWeight: 600, color:'var(--text)',
                 fontFamily: "'JetBrains Mono', monospace"};

function PageHeroes({s}) {
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
    setGapLoading(true); setGapErr('');
    try {
      const params = new URLSearchParams({
        threshold: String(gapThreshold), min_rarity: String(gapMinRarity), top: String(gapTopN),
      });
      const r = await fetch('/api/gear-gaps?' + params, {cache:'no-store'});
      const j = await r.json();
      if (j.error) { setGapErr(j.error); setGapData(null); }
      else { setGapData(j); }
    } catch (e) { setGapErr(String(e)); }
    setGapLoading(false);
  }, [gapThreshold, gapMinRarity, gapTopN]);
  React.useEffect(() => { if (tab === 'gaps') fetchGaps(); }, [tab, fetchGaps]);

  const heroes = s.heroes.filter(h =>
    (heroFilter === 'all' || (h.rarity && h.rarity.toLowerCase() === heroFilter)) &&
    (heroWhere === 'all' || (heroWhere === 'vault' ? h.in_storage : !h.in_storage))
  );
  const vaultCount = s.heroes.filter(h => h.in_storage).length;
  const allArtifacts = s.artifacts || [];
  // Unique sets observed in inventory for the dropdown
  const sets = React.useMemo(() => {
    const m = new Map();
    for (const a of allArtifacts) if (a.set_name) m.set(a.set_name, (m.get(a.set_name) || 0) + 1);
    return [...m.entries()].sort((a,b) => b[1] - a[1]);
  }, [allArtifacts]);
  const artifacts = allArtifacts.filter(a =>
    (artSlotFilter === 'all' || String(a.slot_id) === artSlotFilter) &&
    (artRarityFilter === 'all' || String(a.rarity) === artRarityFilter) &&
    (artSetFilter === 'all' || a.set_name === artSetFilter) &&
    (artPrimaryFilter === 'all' || a.primary_stat === artPrimaryFilter) &&
    (artSubFilter === 'all' || (a.sub_stat_set || []).includes(artSubFilter)) &&
    (artMinRank === 'all' || a.rank >= Number(artMinRank)) &&
    (artEquip === 'all' || (artEquip === 'equipped' ? !!a.equipped_on : !a.equipped_on))
  );

  return (
    <div style={{display:'grid', gridTemplateColumns:'1fr 300px', gap: 10, minHeight: '100%'}}>
      <div className="card" style={{padding: 0, display:'flex', flexDirection:'column', overflow:'hidden'}}>
        {/* Tab bar */}
        <div style={{padding:'6px 6px 0', borderBottom:'1px solid var(--border)', display:'flex', gap: 4, background:'var(--bg-subtle)'}}>
          {[['heroes', `Heroes · ${s.heroes.length}`], ['artifacts', `Artifacts · ${allArtifacts.length}`], ['gaps', 'Gaps']].map(([k, label]) => (
            <button key={k} onClick={()=>setTab(k)} style={{
              border: 0, background: tab===k ? 'var(--bg-elev)' : 'transparent',
              color: tab===k ? 'var(--text)' : 'var(--text-sub)',
              padding: '7px 14px', fontSize: 12, fontWeight: tab===k ? 500 : 400,
              cursor: 'pointer', borderRadius: '6px 6px 0 0',
              borderBottom: tab===k ? '2px solid var(--accent)' : '2px solid transparent',
              marginBottom: -1,
            }}>{label}</button>
          ))}
        </div>

        {tab === 'heroes' && (
          <>
            <div style={{padding:'8px 12px', borderBottom:'1px solid var(--border)', display:'flex', alignItems:'center', gap: 6, flexWrap:'wrap'}}>
              <label style={filterLbl}>where</label>
              <select value={heroWhere} onChange={e => setHeroWhere(e.target.value)} style={filterSel}>
                <option value="all">all ({s.heroes.length})</option>
                <option value="active">active ({s.heroes.length - vaultCount})</option>
                <option value="vault">vault ({vaultCount})</option>
              </select>
              <span style={{flex: 1}}/>
              {['all','legendary','epic','rare'].map(f => (
                <button key={f} className="btn" onClick={()=>setHeroFilter(f)} style={{height: 22, padding: '0 8px', fontSize: 11, background: heroFilter===f?'var(--bg-hover)':'transparent', borderColor: heroFilter===f?'var(--accent)':'var(--border)'}}>{f}</button>
              ))}
            </div>
            <div className="scroll" style={{flex: 1, overflowY:'auto'}}>
              <div style={{display:'grid', gridTemplateColumns: '1.4fr 100px 80px 70px 56px 80px 76px 56px 56px', gap: 6, padding:'8px 16px', fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em', borderBottom:'1px solid var(--border)', background:'var(--bg-subtle)'}}>
                <span>Name</span><span>Faction</span><span>Rarity</span><span>Lv / ★</span><span>Emp</span><span>Skills</span><span>Masteries</span><span>Bless</span><span>Gear</span>
              </div>
              {heroes.map((h,i) => {
                const mtrees = h.mastery_trees || [0,0,0];
                const mtotal = h.mastery_count || mtrees.reduce((a,b)=>a+b,0);
                const mComplete = mtotal >= 15;
                return (
                <div key={(h.id || h.name) + '-' + i} style={{display:'grid', gridTemplateColumns: '1.4fr 100px 80px 70px 56px 80px 76px 56px 56px', gap: 6, padding:'7px 16px', fontSize: 12, borderBottom:'1px solid var(--border)', alignItems:'center'}}>
                  <div style={{minWidth: 0}}>
                    <div style={{fontWeight: 500, display:'flex', alignItems:'center', gap: 6}}>
                      {h.in_storage && <span title="Vaulted" style={{fontSize: 9, padding:'1px 5px', border:'1px solid var(--border-strong)', borderRadius: 3, color:'var(--text-dim)', letterSpacing:'0.04em'}}>VAULT</span>}
                      {h.locked && !h.in_storage && <span title="Locked" style={{fontSize: 10, color:'var(--text-dim)'}}>🔒</span>}
                      <span className="truncate">{h.name}</span>
                    </div>
                    <div style={{fontSize: 10, color:'var(--text-dim)'}} className="mono">{h.role || ''}{h.element ? ' · ' + h.element : ''}</div>
                  </div>
                  <span style={{color:'var(--text-sub)'}} className="truncate">{h.faction}</span>
                  <span style={{color: RARITY_COLORS[h.rarity]}}>{h.rarity}</span>
                  <span className="mono" style={{color:'var(--text-sub)'}}>{h.level} · {h.stars}★</span>
                  <span className="mono" style={{color: h.empower > 0 ? 'var(--violet)' : 'var(--text-dim)'}}>
                    {h.empower > 0 ? '+' + h.empower : '—'}
                  </span>
                  <span className="mono" style={{color:'var(--text-sub)', fontSize: 11}}>
                    {h.skills && h.skills.length ? h.skills.join('/') : '—'}
                  </span>
                  <span className="mono" style={{fontSize: 11, color: mComplete ? 'var(--accent)' : mtotal > 0 ? 'var(--text-sub)' : 'var(--text-dim)'}}
                        title={`Offense ${mtrees[0]} · Defense ${mtrees[1]} · Support ${mtrees[2]}`}>
                    {mtotal > 0 ? `${mtrees[0]}/${mtrees[1]}/${mtrees[2]}` : '—'}
                  </span>
                  <span className="mono" style={{fontSize: 11, color: h.ascend_grade > 0 ? 'oklch(0.72 0.16 85)' : 'var(--text-dim)'}}
                        title={h.ascend_grade ? `Ascension grade ${h.ascend_grade}` : ''}>
                    {h.ascend_grade > 0 ? '★'.repeat(Math.min(h.ascend_grade, 3)) : '—'}
                  </span>
                  <span className="mono" style={{color: (h.equipped_count || 0) >= 6 ? 'var(--accent)' : 'var(--text-dim)'}}>
                    {h.equipped_count || 0}/9
                  </span>
                </div>
                );
              })}
            </div>
          </>
        )}

        {tab === 'artifacts' && (
          <>
            <div style={{padding:'8px 12px', borderBottom:'1px solid var(--border)', display:'flex', alignItems:'center', gap: 6, flexWrap:'wrap'}}>
              <label style={filterLbl}>slot</label>
              <select value={artSlotFilter} onChange={e => setArtSlotFilter(e.target.value)} style={filterSel}>
                <option value="all">all</option>
                {Object.entries({1:'Helmet',2:'Chest',3:'Gloves',4:'Boots',5:'Weapon',6:'Shield',7:'Ring',8:'Amulet',9:'Banner'}).map(([id, name]) => (
                  <option key={id} value={id}>{name}</option>
                ))}
              </select>
              <label style={filterLbl}>rarity</label>
              <select value={artRarityFilter} onChange={e => setArtRarityFilter(e.target.value)} style={filterSel}>
                <option value="all">all</option>
                {[6,5,4,3,2,1].map(r => <option key={r} value={r}>{RARITY_NAMES_BY_ID[r]}</option>)}
              </select>
              <label style={filterLbl}>set</label>
              <select value={artSetFilter} onChange={e => setArtSetFilter(e.target.value)} style={{...filterSel, maxWidth: 140}}>
                <option value="all">all</option>
                {sets.map(([n, c]) => <option key={n} value={n}>{n} ({c})</option>)}
              </select>
              <label style={filterLbl}>primary</label>
              <select value={artPrimaryFilter} onChange={e => setArtPrimaryFilter(e.target.value)} style={filterSel}>
                <option value="all">all</option>
                {['HP','ATK','DEF','SPD','RES','ACC','CR','CD'].map(st => <option key={st} value={st}>{st}</option>)}
              </select>
              <label style={filterLbl}>sub</label>
              <select value={artSubFilter} onChange={e => setArtSubFilter(e.target.value)} style={filterSel}>
                <option value="all">all</option>
                {['SPD','CR','CD','ATK','HP','DEF','RES','ACC'].map(st => <option key={st} value={st}>{st}</option>)}
              </select>
              <label style={filterLbl}>rank ≥</label>
              <select value={artMinRank} onChange={e => setArtMinRank(e.target.value)} style={filterSel}>
                <option value="all">all</option>
                {[6,5,4,3].map(r => <option key={r} value={r}>{r}★</option>)}
              </select>
              <label style={filterLbl}>where</label>
              <select value={artEquip} onChange={e => setArtEquip(e.target.value)} style={filterSel}>
                <option value="all">any</option>
                <option value="equipped">equipped</option>
                <option value="vault">vault</option>
              </select>
              <span style={{flex: 1, minWidth: 8}}/>
              <span className="mono" style={{fontSize: 11, color:'var(--text-sub)'}}>{artifacts.length} / {allArtifacts.length}</span>
            </div>
            <div className="scroll" style={{flex: 1, overflowY:'auto'}}>
              {allArtifacts.length === 0 ? (
                <div style={{padding: 24, fontSize: 12, color:'var(--text-dim)', textAlign:'center'}}>
                  No artifacts loaded yet. The mod is paginating — refresh in a few seconds.
                </div>
              ) : (
                <>
                  <div style={{display:'grid', gridTemplateColumns: '70px 100px 70px 40px 36px 130px 1fr 100px', gap: 4, padding:'8px 16px', fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em', borderBottom:'1px solid var(--border)', background:'var(--bg-subtle)'}}>
                    <span>Slot</span><span>Set</span><span>Rarity</span><span>Rk</span><span>Lv</span><span>Primary</span><span>Substats</span><span>Equipped</span>
                  </div>
                  {artifacts.slice(0, 500).map(a => {
                    const rname = RARITY_NAMES_BY_ID[a.rarity] || '?';
                    const rcolor = RARITY_COLORS[rname] || 'var(--text-sub)';
                    const fmtVal = (v, flat) => {
                      const n = Math.round((v || 0) * 10) / 10;
                      return flat ? `${n}` : `${n}%`;
                    };
                    const primary = a.primary_stat ? `${a.primary_stat} +${fmtVal(a.primary_value, a.primary_flat)}` : '';
                    return (
                      <div key={a.id} style={{display:'grid', gridTemplateColumns: '70px 100px 70px 40px 36px 130px 1fr 100px', gap: 4, padding:'7px 16px', fontSize: 12, borderBottom:'1px solid var(--border)', alignItems:'center'}}>
                        <span style={{color:'var(--text)'}}>{a.slot}</span>
                        <span style={{color:'var(--text-sub)'}} className="truncate">{a.set_name}</span>
                        <span style={{color: rcolor}}>{rname}</span>
                        <span className="mono" style={{color:'var(--text-sub)'}}>{a.rank}★</span>
                        <span className="mono" style={{color:'var(--text-sub)'}}>{a.level}</span>
                        <span className="mono" style={{fontSize: 11}}>{primary}</span>
                        <span style={{display:'flex', flexWrap:'wrap', gap: '4px 10px', fontSize: 11}}>
                          {(a.substats || []).map((sb, i) => (
                            <span key={i} className="mono" style={{color: sb.stat === 'SPD' ? 'var(--accent)' : sb.stat === 'CR' || sb.stat === 'CD' ? 'var(--violet)' : 'var(--text-sub)'}}>
                              {sb.stat} +{fmtVal(sb.value, sb.flat)}
                              {sb.rolls > 0 && <span style={{color:'var(--text-dim)'}}> ·{sb.rolls}</span>}
                              {sb.glyph > 0 && <span style={{color:'oklch(0.72 0.16 85)'}}> +{fmtVal(sb.glyph, sb.flat)}</span>}
                            </span>
                          ))}
                        </span>
                        <span className="truncate" style={{fontSize: 11, color: a.equipped_on ? 'var(--accent)' : 'var(--text-dim)'}}>
                          {a.equipped_on ? a.equipped_on.hero_name : '—'}
                        </span>
                      </div>
                    );
                  })}
                  {artifacts.length > 500 && (
                    <div style={{padding: 10, fontSize: 11, color:'var(--text-dim)', textAlign:'center'}}>
                      showing first 500 of {artifacts.length}
                    </div>
                  )}
                </>
              )}
            </div>
          </>
        )}

        {tab === 'gaps' && (
          <>
            <div style={{padding:'8px 12px', borderBottom:'1px solid var(--border)', display:'flex', alignItems:'center', gap: 10, flexWrap:'wrap'}}>
              <label style={filterLbl}>HH ≥</label>
              <input type="number" step="0.5" min="0" max="6" value={gapThreshold}
                     onChange={e=>setGapThreshold(parseFloat(e.target.value)||0)}
                     style={{...filterSel, width: 60}}/>
              <label style={filterLbl}>inv. rarity ≥</label>
              <select value={gapMinRarity} onChange={e=>setGapMinRarity(parseInt(e.target.value))}
                      style={{...filterSel, width: 100}}>
                <option value={3}>Rare+</option>
                <option value={4}>Epic+</option>
                <option value={5}>Legendary</option>
              </select>
              <label style={filterLbl}>top</label>
              <input type="number" min="5" max="50" value={gapTopN}
                     onChange={e=>setGapTopN(parseInt(e.target.value)||15)}
                     style={{...filterSel, width: 50}}/>
              <span style={{flex: 1}}/>
              <button className="btn" onClick={fetchGaps} disabled={gapLoading}
                      style={{height: 22, padding: '0 10px', fontSize: 11}}>
                {gapLoading ? 'Loading…' : 'Refresh'}
              </button>
              {gapData && (
                <span className="mono" style={{fontSize: 11, color:'var(--text-sub)'}}>
                  {gapData.unique_viable_heroes} heroes · {gapData.inventory_total} pieces
                </span>
              )}
            </div>
            <div className="scroll" style={{flex: 1, overflowY:'auto', padding: 12}}>
              {gapErr && <div style={{padding: 12, color:'var(--danger,#ff6b6b)'}}>{gapErr}</div>}
              {gapData && (
                <div style={{display:'flex', flexDirection:'column', gap: 14}}>
                  {gapData.forge && gapData.forge.length > 0 && (
                    <div className="card" style={{padding: 0, overflow:'hidden'}}>
                      <div style={{padding:'8px 12px', borderBottom:'1px solid var(--border)',
                                   background:'var(--bg-subtle)', fontSize: 10.5,
                                   color:'var(--text-sub)', textTransform:'uppercase',
                                   letterSpacing:'0.06em', fontWeight: 600}}>
                        Forge crafting priority — gaps you fix in the Forge, not a dungeon
                      </div>
                      <table style={{width:'100%', borderCollapse:'collapse', fontSize: 12}}>
                        <thead>
                          <tr style={{borderBottom:'1px solid var(--border)', background:'var(--bg-subtle)'}}>
                            <th style={_th}>Set</th>
                            <th style={{..._th, textAlign:'right'}}>Gap</th>
                            <th style={{..._th, textAlign:'right'}}>Demand</th>
                            <th style={{..._th, textAlign:'right'}}>Supply</th>
                            <th style={_th}>Top areas driving demand</th>
                          </tr>
                        </thead>
                        <tbody>
                          {gapData.forge.map(r => (
                            <tr key={r.set_id} style={{borderBottom:'1px solid var(--border)'}}>
                              <td style={{..._td, fontWeight: 600}}>{r.set_name}</td>
                              <td style={{..._td, textAlign:'right', fontWeight: 600,
                                          color:'var(--danger,#ff6b6b)'}} className="mono">
                                {r.gap > 0 ? '+' : ''}{r.gap}
                              </td>
                              <td style={{..._td, textAlign:'right'}} className="mono">{r.demand}</td>
                              <td style={{..._td, textAlign:'right'}} className="mono">{r.supply}</td>
                              <td style={_td}><TopAreas areas={r.top_areas}/></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  {gapData.dungeons && gapData.dungeons.length > 0 && (
                    <div className="card" style={{padding: 0, overflow:'hidden'}}>
                      <div style={{padding:'8px 12px', borderBottom:'1px solid var(--border)',
                                   background:'var(--bg-subtle)', fontSize: 10.5,
                                   color:'var(--text-sub)', textTransform:'uppercase',
                                   letterSpacing:'0.06em', fontWeight: 600}}>
                        Dungeon farming priority — highest gap-points closed first
                      </div>
                      <table style={{width:'100%', borderCollapse:'collapse', fontSize: 12}}>
                        <thead>
                          <tr style={{borderBottom:'1px solid var(--border)', background:'var(--bg-subtle)'}}>
                            <th style={_th}>Dungeon</th>
                            <th style={{..._th, textAlign:'right'}}>Score</th>
                            <th style={_th}>Sets it closes</th>
                            <th style={_th}>Accessory gaps</th>
                          </tr>
                        </thead>
                        <tbody>
                          {gapData.dungeons.map(d => (
                            <tr key={d.region} style={{borderBottom:'1px solid var(--border)'}}>
                              <td style={_td}>
                                <div style={{fontWeight: 600}}>{d.label}</div>
                                {d.difficulties && d.difficulties.length > 0 && (
                                  <div style={{fontSize: 10.5, color:'var(--text-dim)', marginTop: 2}}>
                                    {d.difficulties.map(x => `${x.difficulty} (${x.stages} stages)`).join(' · ')}
                                  </div>
                                )}
                              </td>
                              <td style={{..._td, textAlign:'right', fontWeight: 600,
                                          color:'var(--accent, #6bd0ff)'}} className="mono">
                                {d.score}
                              </td>
                              <td style={_td}>
                                {d.gap_sets.length === 0
                                  ? <span style={{color:'var(--text-dim)'}}>—</span>
                                  : d.gap_sets.map((s, i) => (
                                    <span key={i} style={{marginRight: 8}}>
                                      <span style={{color:'var(--text)'}}>{s.set_name}</span>
                                      <span className="mono" style={{color:'var(--danger,#ff6b6b)', marginLeft: 3}}>
                                        ({s.gap > 0 ? '+' : ''}{s.gap})
                                      </span>
                                    </span>
                                  ))}
                              </td>
                              <td style={_td}>
                                {d.accessory_kinds.length === 0
                                  ? <span style={{color:'var(--text-dim)'}}>—</span>
                                  : (
                                    <span>
                                      <span style={{color:'var(--text)'}}>
                                        {d.accessory_kinds.map(s => ({7:'Ring',8:'Amulet',9:'Banner'}[s] || `slot${s}`)).join(', ')}
                                      </span>
                                      {d.accessory_bonus > 0 && (
                                        <span className="mono" style={{color:'var(--danger,#ff6b6b)', marginLeft: 6}}>
                                          (-{d.accessory_bonus})
                                        </span>
                                      )}
                                    </span>
                                  )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  <GapTable
                    title="Set gaps (most under-supplied first)"
                    rows={gapData.sets}
                    cols={[
                      {h:'Set',  v:r=>r.set_name},
                      {h:'Demand', v:r=>r.demand, mono:1, align:'right'},
                      {h:'Supply', v:r=>r.supply, mono:1, align:'right'},
                      {h:'Gap',    v:r=>(r.gap>0?'+':'')+r.gap, mono:1, align:'right',
                                   color:r=>r.gap<0?'var(--danger,#ff6b6b)':'var(--success,#6bd06b)', bold:1},
                      {h:'Top areas', v:r=>(<TopAreas areas={r.top_areas}/>)},
                    ]}/>
                  <GapTable
                    title="Primary stat × slot gaps"
                    rows={gapData.primaries}
                    cols={[
                      {h:'Slot', v:r=>r.slot_name},
                      {h:'Stat', v:r=>r.stat},
                      {h:'Demand', v:r=>r.demand, mono:1, align:'right'},
                      {h:'Supply', v:r=>r.supply, mono:1, align:'right'},
                      {h:'Gap',    v:r=>(r.gap>0?'+':'')+r.gap, mono:1, align:'right',
                                   color:r=>r.gap<0?'var(--danger,#ff6b6b)':'var(--success,#6bd06b)', bold:1},
                      {h:'Top areas', v:r=>(<TopAreas areas={r.top_areas}/>)},
                    ]}/>
                  <GapTable
                    title="Substat gaps (recommendation count vs total inventory substat appearances)"
                    rows={gapData.substats}
                    cols={[
                      {h:'Stat', v:r=>r.stat},
                      {h:'Demand', v:r=>r.demand, mono:1, align:'right'},
                      {h:'Supply', v:r=>r.supply, mono:1, align:'right'},
                      {h:'Gap',    v:r=>(r.gap>0?'+':'')+r.gap, mono:1, align:'right',
                                   color:r=>r.gap<0?'var(--danger,#ff6b6b)':'var(--success,#6bd06b)', bold:1},
                      {h:'Top areas', v:r=>(<TopAreas areas={r.top_areas}/>)},
                    ]}/>
                  <div className="card" style={{padding: 10}}>
                    <div style={{fontSize: 10.5, color:'var(--text-sub)', textTransform:'uppercase',
                                 letterSpacing:'0.06em', marginBottom: 6}}>Viable heroes per area</div>
                    <div style={{display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(110px, 1fr))', gap: 6}}>
                      {Object.entries(gapData.viable_per_area).map(([area, n]) => (
                        <div key={area} style={{display:'flex', justifyContent:'space-between', padding:'3px 8px',
                                                 background:'var(--bg-subtle)', borderRadius: 3, fontSize: 11}}>
                          <span style={{color:'var(--text-sub)'}}>{area}</span>
                          <span className="mono" style={{fontWeight: 600}}>{n}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* Right sidebar */}
      <div style={{display:'grid', gridTemplateRows:'auto auto 1fr', gap: 10, minHeight: 0}}>
        <div className="card" style={{padding: 16}}>
          <div className="card-title" style={{marginBottom: 10}}>Vault</div>
          <div style={{display:'flex', justifyContent:'space-between', fontSize: 12, marginBottom: 6}}>
            <span style={{color:'var(--text-sub)'}}>Artifacts</span>
            <span className="mono">{allArtifacts.length || '—'}</span>
          </div>
          <div style={{display:'flex', justifyContent:'space-between', fontSize: 12, marginBottom: 6}}>
            <span style={{color:'var(--text-sub)'}}>Legendary</span>
            <span className="mono">{allArtifacts.filter(a => a.rarity === 5).length}</span>
          </div>
          <div style={{display:'flex', justifyContent:'space-between', fontSize: 12}}>
            <span style={{color:'var(--text-sub)'}}>Epic</span>
            <span className="mono">{allArtifacts.filter(a => a.rarity === 4).length}</span>
          </div>
        </div>
        <div className="card" style={{padding: 16}}>
          <div className="card-title" style={{marginBottom: 10}}>Hero rarity mix</div>
          {['Legendary','Epic','Rare','Uncommon'].map(r => {
            const n = s.heroes.filter(h=>h.rarity===r).length;
            return (
              <div key={r} style={{marginBottom: 8}}>
                <div style={{display:'flex', justifyContent:'space-between', fontSize: 11.5, marginBottom: 3}}>
                  <span style={{color: RARITY_COLORS[r]}}>{r}</span>
                  <span className="mono" style={{color:'var(--text-sub)'}}>{n}</span>
                </div>
                <div style={{height: 3, background:'var(--bg-subtle)', borderRadius:2, overflow:'hidden'}}>
                  <div style={{width:`${s.heroes.length ? (n/s.heroes.length)*100 : 0}%`, height:'100%', background: RARITY_COLORS[r]}}/>
                </div>
              </div>
            );
          })}
        </div>
        <div className="card" style={{padding: 16}}>
          <div className="card-title" style={{marginBottom: 10}}>Auto-sell rules</div>
          <div style={{fontSize: 11.5, color:'var(--text-sub)', lineHeight: 1.7}}>
            <div>• Rank ≤ 3 → sell</div>
            <div>• No speed/crit subs → sell</div>
            <div>• Common + Uncommon → sell</div>
            <div style={{color:'var(--text-dim)', marginTop: 6}}>Rule engine queued · phase 4</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function CBRunDetailModal({s, lr, team, totalDealt, totalTaken, rarityColor, onClose}) {
  const turns = (lr && lr.turn_log) || [];
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
    return () => { cancelled = true; };
  }, []);
  // Build a quick lookup of (boss_turn -> {ukCount, bdCount, alive}) from the sim
  const simByTurn = {};
  if (simPred && simPred.protection_by_turn) {
    for (const [btStr, prot] of Object.entries(simPred.protection_by_turn)) {
      const heroes = Object.values(prot || {});
      simByTurn[parseInt(btStr, 10)] = {
        alive: heroes.filter(h => h.alive).length,
        uk: heroes.filter(h => h.uk).length,
        bd: heroes.filter(h => h.bd).length,
      };
    }
  }
  const buffColor = (b) => /unkillable/i.test(b) ? 'oklch(0.80 0.16 85)'
                         : /counter/i.test(b)   ? 'var(--violet)'
                         : /shield|block/i.test(b) ? 'oklch(0.68 0.18 250)'
                         : /heal/i.test(b) ? 'oklch(0.72 0.17 145)'
                         : 'var(--text-sub)';
  const evIcon = { hero_turn: '▸', debuff: '↓', buff: '↑' };
  const evColor = { hero_turn: 'var(--text-sub)', debuff: 'var(--violet)', buff: 'oklch(0.80 0.16 85)' };
  const debuffMax = Math.max(1, ...Object.values(lr.debuffs_applied || {}));

  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 200,
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20,
    }}>
      <div onClick={e => e.stopPropagation()} className="card scroll" style={{
        padding: 0, width: 1100, maxWidth: '96vw', maxHeight: '92vh', overflow: 'auto',
        background: 'var(--bg-elev)', border: '1px solid var(--border-strong)', display: 'flex', flexDirection: 'column',
      }}>
        {/* Header */}
        <div style={{padding:'14px 20px', borderBottom:'1px solid var(--border)', display:'flex', alignItems:'center', gap: 14, position:'sticky', top: 0, background:'var(--bg-elev)', zIndex: 1}}>
          <div>
            <div style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em'}}>Clan boss · last run detail</div>
            <div style={{fontSize: 18, fontWeight: 500, marginTop: 2}}>{team.length} heroes · {lr.turns_total || 0} boss turns · {((lr.damage || 0)/1e6).toFixed(2)}M damage</div>
          </div>
          <span style={{flex: 1}}/>
          <button className="btn" onClick={onClose} style={{height: 28, padding:'0 12px'}}>Close</button>
        </div>

        <div style={{padding: 20, display:'grid', gridTemplateColumns:'1fr 300px', gap: 16}}>
          {/* Left — run stats + per-hero detail + turn log */}
          <div style={{display:'flex', flexDirection:'column', gap: 14, minWidth: 0}}>
            {/* Run stats strip */}
            <div style={{display:'grid', gridTemplateColumns:'repeat(6, 1fr)', gap: 10}}>
              {[
                ['Turns',   lr.turns_total || 0, 'var(--text)'],
                ['Damage',  `${((lr.damage || 0)/1e6).toFixed(2)}M`, 'var(--accent)'],
                ['Taken',   `${((lr.damage_taken || 0)/1e6).toFixed(2)}M`, 'oklch(0.70 0.18 25)'],
                ['Absorbed',`${((lr.damage_absorbed || 0)/1e6).toFixed(2)}M`, 'oklch(0.68 0.18 250)'],
                ['UK saves', (lr.unkillable_triggers != null ? lr.unkillable_triggers : '—') + '×', 'oklch(0.80 0.16 85)'],
                ['Counters', (lr.counters_total != null ? lr.counters_total : '—') + '×', 'var(--violet)'],
              ].map(([lbl, val, col]) => (
                <div key={lbl} style={{padding:'10px 12px', background:'var(--bg-subtle)', borderRadius: 6, border:'1px solid var(--border)'}}>
                  <div style={{fontSize: 10, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em'}}>{lbl}</div>
                  <div className="mono num" style={{fontSize: 18, fontWeight: 600, color: col, marginTop: 3}}>{val}</div>
                </div>
              ))}
            </div>

            {/* Per-hero detailed breakdown */}
            <div className="card" style={{padding: 0, overflow:'hidden'}}>
              <PanelHeader title="champion detail" right={`${team.length} heroes`}/>
              {team.map((h,i) => (
                <div key={h.name} style={{padding:'10px 14px', borderBottom:'1px solid var(--border)'}}>
                  <div style={{display:'grid', gridTemplateColumns:'1.2fr 80px 80px 80px 80px 60px', gap: 8, alignItems:'center', fontSize: 12}}>
                    <div style={{minWidth: 0}}>
                      <div style={{fontWeight: 500, display:'flex', alignItems:'center', gap: 6}}>
                        {i===0 && <span style={{fontSize: 9, color:'var(--accent)', border:'1px solid var(--accent)', padding:'1px 4px', borderRadius: 3}}>LEAD</span>}
                        <span className="truncate">{h.name}</span>
                      </div>
                      <div style={{fontSize: 10.5, color: rarityColor[h.rarity], marginTop: 2}}>{h.rarity} · {h.faction} · {h.role}</div>
                    </div>
                    <div style={{textAlign:'right'}}>
                      <div style={{fontSize: 10, color:'var(--text-dim)'}}>Dealt</div>
                      <div className="mono num">{(h.dmg_dealt/1e6).toFixed(2)}M</div>
                    </div>
                    <div style={{textAlign:'right'}}>
                      <div style={{fontSize: 10, color:'var(--text-dim)'}}>Taken</div>
                      <div className="mono num" style={{color:'oklch(0.70 0.18 25)'}}>{(h.dmg_taken/1e6).toFixed(2)}M</div>
                    </div>
                    <div style={{textAlign:'right'}}>
                      <div style={{fontSize: 10, color:'var(--text-dim)'}}>Absorbed</div>
                      <div className="mono num" style={{color: h.absorbed > 0 ? 'oklch(0.68 0.18 250)' : 'var(--text-dim)'}}>
                        {h.absorbed > 0 ? (h.absorbed/1e6).toFixed(2) + 'M' : '—'}
                      </div>
                    </div>
                    <div style={{textAlign:'right'}}>
                      <div style={{fontSize: 10, color:'var(--text-dim)'}}>Turns</div>
                      <div className="mono num">{h.turns}</div>
                    </div>
                    <div style={{textAlign:'right'}}>
                      <div style={{fontSize: 10, color:'var(--text-dim)'}}>Counters</div>
                      <div className="mono num" style={{color: h.counters > 0 ? 'var(--violet)' : 'var(--text-dim)'}}>{h.counters || '—'}</div>
                    </div>
                  </div>
                  {(h.buffs || []).length > 0 && (
                    <div style={{marginTop: 8}}>
                      <div style={{fontSize: 9.5, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em', marginBottom: 4}}>
                        Buffs received during run
                      </div>
                      <div style={{display:'flex', flexWrap:'wrap', gap: 4}}>
                        {h.buffs.map(b => {
                          const name = typeof b === 'string' ? b : b.name;
                          const srcs = typeof b === 'object' ? (b.sources || []) : [];
                          const selfOnly = srcs.length === 1 && srcs[0] === 'self';
                          const fromText = srcs.length ? ' · from ' + srcs.join('/') : '';
                          return (
                            <span key={name}
                                  title={srcs.length ? `Source: ${srcs.join(', ')}` : name}
                                  style={{fontSize: 9.5, padding:'1px 6px', borderRadius: 3,
                                          border: `1px solid ${buffColor(name)}`, color: buffColor(name),
                                          textTransform: 'uppercase', letterSpacing: '0.03em',
                                          fontStyle: selfOnly ? 'italic' : 'normal'}}>
                              {name}
                              {srcs.length > 0 && (
                                <span style={{marginLeft: 4, opacity: 0.65, textTransform:'none', letterSpacing: 0, fontSize: 9}}>
                                  {selfOnly ? '(self)' : `← ${srcs.join('/')}`}
                                </span>
                              )}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Turn-by-turn log */}
            <div className="card" style={{padding: 0, overflow:'hidden'}}>
              <PanelHeader title={`turn-by-turn · ${turns.length} boss turns`} right="click a row to expand"/>
              {turns.length === 0 ? (
                <div style={{padding: 16, fontSize: 12, color:'var(--text-dim)'}}>No battle log available.</div>
              ) : turns.map(t => {
                const isOpen = expanded === t.boss_turn;
                const pct = (t.damage || 0) / maxDmg;
                const heroMoves = t.events.filter(e => e.k === 'hero_turn');
                const debuffs = t.events.filter(e => e.k === 'debuff');
                const buffs = t.events.filter(e => e.k === 'buff');
                return (
                  <div key={t.boss_turn} style={{borderBottom:'1px solid var(--border)'}}>
                    {(() => {
                      // Action-type color + protection summary (how many heroes
                      // had UK or BD at the moment of boss action).
                      const actColor = {AOE1:'oklch(0.68 0.16 30)', AOE2:'oklch(0.60 0.22 10)', STUN:'oklch(0.70 0.18 300)'};
                      const prot = t.protection || {};
                      const protHeroes = Object.keys(prot);
                      const ukCount = protHeroes.filter(n => prot[n]?.uk).length;
                      const bdCount = protHeroes.filter(n => prot[n]?.bd).length;
                      const n = protHeroes.length || 5;
                      const protStr = (ukCount === 0 && bdCount === 0) ? 'NONE'
                        : [ukCount ? `UK ${ukCount}/${n}` : null, bdCount ? `BD ${bdCount}/${n}` : null].filter(Boolean).join(' · ');
                      const protOk = (ukCount + bdCount) >= n;   // covered
                      const protColor = protOk ? 'var(--accent)' : (ukCount + bdCount > 0 ? 'oklch(0.75 0.13 85)' : 'oklch(0.65 0.23 25)');
                      return (
                        <div onClick={()=>setExpanded(isOpen ? null : t.boss_turn)}
                             style={{display:'grid', gridTemplateColumns:'44px 56px 1fr 120px 80px 100px 24px', gap: 10, padding:'8px 14px', fontSize: 12, alignItems:'center', cursor:'pointer', background: isOpen ? 'var(--bg-hover)' : 'transparent'}}>
                          <span className="mono" style={{color:'var(--text-dim)'}}>T{t.boss_turn}</span>
                          <span className="mono" style={{fontSize: 10, padding:'2px 5px', borderRadius: 3, border: `1px solid ${actColor[t.boss_action] || 'var(--border)'}`, color: actColor[t.boss_action] || 'var(--text-dim)', textAlign:'center'}}>
                            {t.boss_action || '—'}
                          </span>
                          <div style={{display:'flex', gap: 3, flexWrap:'wrap'}}>
                            {heroMoves.map((m, i) => (
                              <span key={i} style={{fontSize: 10, padding:'1px 5px', background:'var(--bg-subtle)', borderRadius: 3, color:'var(--text-sub)'}}>
                                {m.by}
                              </span>
                            ))}
                          </div>
                          <div>
                            <span className="mono" style={{color: protColor, fontSize: 11, fontWeight: 500}}>
                              {protStr}
                            </span>
                            {(() => {
                              // Sim prediction for this boss turn. Green if sim
                              // and actual agree on full coverage; amber when
                              // they disagree (prediction divergence).
                              const pred = simByTurn[t.boss_turn];
                              if (!pred) return null;
                              const predOk = (pred.uk + pred.bd) >= pred.alive;
                              const match = predOk === protOk;
                              const color = match ? 'var(--text-dim)' : 'oklch(0.75 0.17 85)';
                              const predStr = (pred.uk === 0 && pred.bd === 0) ? 'NONE'
                                : [pred.uk ? `UK ${pred.uk}/${pred.alive}` : null,
                                   pred.bd ? `BD ${pred.bd}/${pred.alive}` : null].filter(Boolean).join(' · ');
                              return (
                                <span className="mono" title="cb_sim prediction for this turn" style={{fontSize: 9.5, color, display:'block', marginTop: 1}}>
                                  sim: {predStr}{!match && ' ⚠'}
                                </span>
                              );
                            })()}
                          </div>
                          <span className="mono" style={{color: debuffs.length ? 'var(--violet)' : 'var(--text-dim)', fontSize: 10.5}}>
                            {debuffs.length ? debuffs.length + ' db' : '—'}
                          </span>
                          <div style={{textAlign:'right'}}>
                            <div className="mono num" style={{fontSize: 12, color: t.damage > 0 ? 'var(--accent)' : 'var(--text-dim)'}}>
                              {t.damage > 0 ? (t.damage/1e6).toFixed(2) + 'M' : '—'}
                            </div>
                            <div style={{height: 2, background:'var(--bg-subtle)', borderRadius: 1, marginTop: 2, overflow:'hidden'}}>
                              <div style={{width:`${pct*100}%`, height:'100%', background:'var(--accent)'}}/>
                            </div>
                          </div>
                          <span style={{color:'var(--text-dim)', fontSize: 10, textAlign:'center'}}>{isOpen ? '▾' : '▸'}</span>
                        </div>
                      );
                    })()}
                    {isOpen && (
                      <div style={{padding:'10px 18px 14px 58px', background:'var(--bg-subtle)', fontSize: 11.5}}>
                        {t.events.length === 0 ? (
                          <span style={{color:'var(--text-dim)'}}>(no recorded events)</span>
                        ) : (
                          <div style={{display:'grid', gridTemplateColumns:'16px 1fr', gap:'4px 8px', alignItems:'start'}}>
                            {t.events.map((ev, i) => (
                              <React.Fragment key={i}>
                                <span style={{color: evColor[ev.k] || 'var(--text-dim)', fontFamily:'monospace'}}>
                                  {evIcon[ev.k] || '·'}
                                </span>
                                <span style={{color: evColor[ev.k] || 'var(--text-sub)'}}>
                                  {ev.k === 'hero_turn' && <><span style={{color:'var(--text)'}}>{ev.by}</span> takes a turn</>}
                                  {ev.k === 'debuff'    && <><span style={{color:'var(--text)'}}>{ev.by}</span> applies <b>{ev.name}</b></>}
                                  {ev.k === 'buff'      && <><b>{ev.name}</b> gained by <span style={{color:'var(--text)'}}>{ev.on}</span></>}
                                </span>
                              </React.Fragment>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right sidebar — debuffs chart + status flags */}
          <div style={{display:'flex', flexDirection:'column', gap: 14}}>
            <div className="card" style={{padding: 14}}>
              <div className="card-title" style={{marginBottom: 10}}>Debuffs on boss</div>
              {Object.keys(lr.debuffs_applied || {}).length === 0 ? (
                <div style={{fontSize: 11.5, color:'var(--text-dim)'}}>No debuff data for this run.</div>
              ) : Object.entries(lr.debuffs_applied || {}).map(([d,n]) => (
                <div key={d} style={{marginBottom: 7}}>
                  <div style={{display:'flex', justifyContent:'space-between', fontSize: 11.5, marginBottom: 3}}>
                    <span style={{color:'var(--text-sub)'}}>{d}</span>
                    <span className="mono" style={{color:'var(--text)'}}>{n}×</span>
                  </div>
                  <div style={{height: 3, background:'var(--bg-subtle)', borderRadius: 2, overflow:'hidden'}}>
                    <div style={{width:`${(n/debuffMax)*100}%`, height:'100%', background:'var(--violet)'}}/>
                  </div>
                </div>
              ))}
            </div>

            <div className="card" style={{padding: 14}}>
              <div className="card-title" style={{marginBottom: 10}}>Timeline</div>
              {(lr.timeline || []).length === 0 ? (
                <div style={{fontSize: 11.5, color:'var(--text-dim)'}}>No major events.</div>
              ) : (lr.timeline || []).map((t,i) => (
                <div key={i} style={{display:'grid', gridTemplateColumns: '40px 1fr', gap: 8, padding:'5px 0', fontSize: 11.5, alignItems:'baseline', borderTop: i > 0 ? '1px dashed var(--border)' : 'none'}}>
                  <span className="mono" style={{color:'var(--text-dim)', fontSize: 10.5}}>T{t.t}</span>
                  <div>
                    <div>{t.ev}</div>
                    <div style={{fontSize: 10.5, color:'var(--text-dim)'}} className="mono">{t.by}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function CBHistoryPanel({history, perKey}) {
  // Full-width 7-day CB damage panel. When per-key data is available, each key
  // entry is {damage, turns, team, time, iso_time, file}; hover reveals details.
  const stackedHist = Array.isArray(perKey) && perKey.length ? perKey : null;
  const flatHist = Array.isArray(history) && history.length ? history : [];
  // Normalise key entries to always be objects with a damage field so tooltip
  // logic doesn't have to handle two shapes.
  const toKeyObjs = (arr) => (arr || []).map(k => typeof k === 'number' ? {damage: k} : k);
  const data = stackedHist
    ? stackedHist.map(h => ({...h, keys: toKeyObjs(h.keys)}))
    : flatHist.map(h => ({date: h.day, day: h.day, total: h.dmg, keys: h.dmg > 0 ? [{damage: h.dmg}] : []}));
  const maxTotal = data.reduce((m, h) => Math.max(m, h.total || 0), 0) || 1;
  const barH = 160;
  const avg = data.length ? data.reduce((a, h) => a + (h.total || 0), 0) / data.length : 0;
  const best = data.reduce((m, h) => (h.total || 0) > (m.total || 0) ? h : m, data[0] || {total: 0});
  const todayTotal = data.length ? (data[data.length - 1].total || 0) : 0;

  const [hover, setHover] = React.useState(null); // {dayIdx, keyIdx, clientX, clientY}

  return (
    <div className="card" style={{padding: 0, gridColumn: '1 / -1', overflow: 'visible', position: 'relative'}}>
      <PanelHeader title="7-day clan boss damage" right={`${data.filter(h => h.total > 0).length} windows with data`}/>
      <div style={{padding: '18px 22px', display:'grid', gridTemplateColumns: '1fr 220px', gap: 20, alignItems:'stretch'}}>
        {/* Bars */}
        <div style={{display:'flex', alignItems:'flex-end', gap: 14, minHeight: barH + 52}}>
          {data.map((h, i) => {
            const isToday = i === data.length - 1;
            const pct = h.total ? Math.max(0.025, h.total / maxTotal) : 0;
            const keys = h.keys || [];
            const baseColor = isToday ? 'var(--accent)' : 'var(--border-strong)';
            const altColor = isToday ? 'oklch(0.72 0.17 150)' : 'oklch(0.55 0.08 250)';
            return (
              <div key={h.day + '-' + i} style={{flex: '1 1 0', display:'flex', flexDirection:'column', alignItems:'center', gap: 6, minWidth: 44}}>
                <div style={{fontSize: 12, fontWeight: 600, color: isToday ? 'var(--accent)' : (h.total > 0 ? 'var(--text)' : 'var(--text-dim)'), lineHeight: 1}} className="mono num">
                  {h.total > 0 ? (h.total/1e6).toFixed(1) + 'M' : '—'}
                </div>
                <div style={{width: '100%', maxWidth: 80, height: barH, display:'flex', alignItems:'end'}}>
                  <div style={{width: '100%', height: `${pct*100}%`, display:'flex', flexDirection:'column-reverse', borderRadius: 4, overflow:'hidden', border: h.total > 0 ? 'none' : '1px dashed var(--border)'}}>
                    {keys.map((k, idx) => (
                      <div key={idx}
                           onMouseEnter={e => setHover({dayIdx: i, keyIdx: idx, x: e.clientX, y: e.clientY})}
                           onMouseMove={e => setHover({dayIdx: i, keyIdx: idx, x: e.clientX, y: e.clientY})}
                           onMouseLeave={() => setHover(null)}
                           style={{
                             width: '100%',
                             flex: k.damage || 1,
                             background: idx % 2 === 0 ? baseColor : altColor,
                             borderTop: idx > 0 ? '1px solid rgba(0,0,0,0.45)' : 'none',
                             minHeight: 3,
                             cursor: 'pointer',
                             transition: 'filter 0.12s',
                             filter: hover && hover.dayIdx === i && hover.keyIdx === idx ? 'brightness(1.25)' : 'none',
                           }}/>
                    ))}
                  </div>
                </div>
                <div style={{fontSize: 11, color: isToday ? 'var(--accent)' : 'var(--text-sub)', lineHeight: 1}} className="mono">
                  {h.day}
                </div>
                <div style={{fontSize: 10, color:'var(--text-dim)', lineHeight: 1}} className="mono">
                  {keys.length ? `${keys.length} key${keys.length !== 1 ? 's' : ''}` : '—'}
                </div>
              </div>
            );
          })}
        </div>

        {/* Right: summary stats */}
        <div style={{display:'flex', flexDirection:'column', justifyContent:'space-around', gap: 10, paddingLeft: 18, borderLeft: '1px solid var(--border)'}}>
          <div>
            <div style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em'}}>Today</div>
            <div className="mono num" style={{fontSize: 22, fontWeight: 600, color: 'var(--accent)', marginTop: 2}}>
              {todayTotal > 0 ? (todayTotal/1e6).toFixed(2) + 'M' : '—'}
            </div>
          </div>
          <div>
            <div style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em'}}>7-day avg</div>
            <div className="mono num" style={{fontSize: 18, fontWeight: 600, marginTop: 2}}>
              {(avg/1e6).toFixed(2)}M
            </div>
          </div>
          <div>
            <div style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em'}}>Best day</div>
            <div className="mono num" style={{fontSize: 16, fontWeight: 600, marginTop: 2}}>
              {(best.total || 0) > 0 ? `${(best.total/1e6).toFixed(2)}M · ${best.day}` : '—'}
            </div>
          </div>
        </div>
      </div>

      {hover && (() => {
        const h = data[hover.dayIdx];
        const k = h && h.keys && h.keys[hover.keyIdx];
        if (!k) return null;
        const keyIndex = hover.keyIdx + 1;
        const totalKeys = h.keys.length;
        // Position tooltip near cursor, fixed to viewport
        const tipX = Math.min(hover.x + 14, window.innerWidth - 320);
        const tipY = Math.min(hover.y - 10, window.innerHeight - 220);
        return (
          <div style={{
            position: 'fixed', left: tipX, top: tipY, zIndex: 500,
            background: 'var(--bg-elev)', border: '1px solid var(--border-strong)',
            borderRadius: 8, padding: '12px 14px', minWidth: 240, maxWidth: 320,
            boxShadow: '0 10px 30px rgba(0,0,0,0.45)',
            pointerEvents: 'none',
          }}>
            <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom: 8}}>
              <span style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em'}}>
                {h.day} · Key {keyIndex}/{totalKeys}
              </span>
              {k.time && <span className="mono" style={{fontSize: 10.5, color:'var(--text-dim)'}}>{k.time}</span>}
            </div>
            <div style={{display:'flex', alignItems:'baseline', gap: 8, marginBottom: 10}}>
              <span className="mono num" style={{fontSize: 22, fontWeight: 600, color:'var(--accent)'}}>
                {(k.damage/1e6).toFixed(2)}M
              </span>
              {k.turns && <span style={{fontSize: 11, color:'var(--text-sub)'}}>· {k.turns} turns</span>}
            </div>
            {k.team && k.team.length > 0 ? (
              <div>
                <div style={{fontSize: 10, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em', marginBottom: 4}}>Team</div>
                <div style={{display:'flex', flexWrap:'wrap', gap: 4}}>
                  {k.team.map((name, i) => (
                    <span key={i} style={{fontSize: 10.5, padding:'2px 6px', background:'var(--bg-subtle)',
                                          border: '1px solid var(--border)', borderRadius: 3,
                                          color: i === 0 ? 'var(--accent)' : 'var(--text-sub)'}}>
                      {i === 0 ? '★ ' : ''}{name}
                    </span>
                  ))}
                </div>
              </div>
            ) : (
              <div style={{fontSize: 10.5, color:'var(--text-dim)'}}>team composition not recorded</div>
            )}
          </div>
        );
      })()}
    </div>
  );
}

const filterSel = {
  background: 'var(--bg-subtle)',
  border: '1px solid var(--border)',
  borderRadius: 4,
  padding: '3px 6px',
  fontSize: 11,
  color: 'var(--text)',
  fontFamily: 'inherit',
};
const filterLbl = {
  fontSize: 10.5,
  color: 'var(--text-dim)',
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  marginLeft: 4,
};

/* ============== Gear gaps helpers (used by PageHeroes 'gaps' tab) ============== */

const _th = {padding:'8px 10px', textAlign:'left', fontSize: 10.5,
             color:'var(--text-sub)', textTransform:'uppercase',
             letterSpacing:'0.06em', fontWeight: 600};
const _td = {padding:'6px 10px', color:'var(--text)'};

function GapTable({title, rows, cols}) {
  return (
    <div className="card" style={{padding: 0, overflow:'hidden'}}>
      <div style={{padding:'8px 12px', borderBottom:'1px solid var(--border)',
                   background:'var(--bg-subtle)', fontSize: 10.5,
                   color:'var(--text-sub)', textTransform:'uppercase', letterSpacing:'0.06em', fontWeight: 600}}>
        {title}
      </div>
      <table style={{width:'100%', borderCollapse:'collapse', fontSize: 12}}>
        <thead>
          <tr style={{borderBottom:'1px solid var(--border)', background:'var(--bg-subtle)'}}>
            {cols.map((c, i) => (
              <th key={i} style={{..._th, textAlign: c.align || 'left'}}>{c.h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, ri) => (
            <tr key={ri} style={{borderBottom:'1px solid var(--border)'}}>
              {cols.map((c, i) => (
                <td key={i} style={{
                  ..._td, textAlign: c.align || 'left',
                  ...(c.color ? {color: c.color(r)} : null),
                  ...(c.bold ? {fontWeight: 600} : null),
                }} className={c.mono ? 'mono' : undefined}>
                  {c.v(r)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TopAreas({areas}) {
  return (
    <span>
      {(areas || []).map((a, i) => (
        <span key={i} style={{marginRight: 8, color:'var(--text-dim)'}}>
          <span style={{color:'var(--text-sub)'}}>{a.area}</span>
          <span style={{marginLeft: 3}}>{a.demand}</span>
        </span>
      ))}
    </span>
  );
}

function PageEvents({s}) {
  return (
    <div style={{display:'grid', gridTemplateColumns: '1fr 320px', gap: 10, minHeight: '100%'}}>
      <div className="card" style={{padding: 20, overflow:'auto'}} className="card scroll">
        <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom: 14}}>
          <div className="card-title">Active events · solo & tournaments</div>
          <span className="chip" style={{background:'var(--accent-soft)', color:'var(--accent)', borderColor:'transparent'}}>Double-dip mode on</span>
        </div>
        {s.events.map(e => (
          <div key={e.name} style={{padding:'14px 0', borderBottom:'1px solid var(--border)', opacity: e.upcoming ? 0.55 : 1}}>
            <div style={{display:'flex', justifyContent:'space-between', alignItems:'baseline', marginBottom: 6}}>
              <div style={{fontSize: 15, fontWeight: 500}}>{e.name}</div>
              <div className="mono" style={{fontSize: 11, color:'var(--text-dim)'}}>{e.ends_in}</div>
            </div>
            <div style={{fontSize: 12, color:'var(--text-sub)', marginBottom: 8}}>{e.reward} · {e.type}</div>
            <div style={{height: 5, background:'var(--bg-subtle)', borderRadius: 3, overflow:'hidden'}}>
              <div style={{width: `${e.progress*100}%`, height:'100%', background: e.type==='tournament' ? 'var(--violet)' : 'var(--accent)'}}/>
            </div>
            <div style={{display:'flex', justifyContent:'space-between', fontSize: 10.5, color:'var(--text-dim)', marginTop: 4}} className="mono">
              <span>{Math.round(e.progress*100)}% to next tier</span>
              <span>{e.upcoming ? 'upcoming' : 'active'}</span>
            </div>
          </div>
        ))}
      </div>
      <div style={{display:'grid', gridTemplateRows:'auto auto 1fr', gap: 10, minHeight: 0}}>
        <div className="card" style={{padding: 16}}>
          <div className="card-title" style={{marginBottom: 10}}>Farming routing</div>
          <div style={{fontSize: 12.5, marginBottom: 6}}>Dragon 20 → Dungeon Divers + Tournament</div>
          <div style={{fontSize: 11, color:'var(--text-sub)'}}>Picked by <span className="mono">_detect_best_dungeon()</span></div>
        </div>
        <div className="card" style={{padding: 16}}>
          <div className="card-title" style={{marginBottom: 10}}>Energy policy</div>
          <div style={{fontSize: 11.5, color:'var(--text-sub)', lineHeight: 1.7}}>
            <div>Floor · 1,000</div>
            <div>Cap · 130 (overflow loss)</div>
            <div>Burn only during events</div>
          </div>
        </div>
        <PanelArena s={s}/>
      </div>
    </div>
  );
}

function PageHistory({s}) {
  return (
    <div style={{display:'grid', gridTemplateRows: '1fr 1fr', gap: 10, minHeight: '100%'}}>
      <div className="card" style={{padding: 16, display:'flex', flexDirection:'column', minHeight: 0}}>
        <div className="card-title" style={{marginBottom: 10}}>14-day earnings</div>
        <div style={{flex: 1, display:'flex', alignItems:'center'}}>
          <HistoryChartB data={s.history} height={200}/>
        </div>
        <div style={{display:'flex', gap: 16, fontSize: 11, color:'var(--text-sub)', marginTop: 8}}>
          <span><span style={{display:'inline-block', width:8, height:8, borderRadius: 2, background:'var(--accent)', marginRight: 5}}/>Gems</span>
          <span><span style={{display:'inline-block', width:8, height:8, borderRadius: 2, background:'var(--violet)', marginRight: 5}}/>Silver (M)</span>
          <span><span style={{display:'inline-block', width:8, height:8, borderRadius: 2, background:'oklch(0.82 0.17 85)', marginRight: 5}}/>CB dmg (M)</span>
        </div>
      </div>
      <div className="card" style={{padding: 0, overflow:'hidden', display:'flex', flexDirection:'column', minHeight: 0}}>
        <PanelHeader title="daily log" right={`${s.history.length} days`}/>
        <div className="scroll" style={{overflowY:'auto', flex: 1}}>
          <div style={{display:'grid', gridTemplateColumns: 'repeat(5, 1fr)', padding:'8px 16px', fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em', borderBottom:'1px solid var(--border)', background:'var(--bg-subtle)'}}>
            <span>Day</span><span>Gems</span><span>Silver</span><span>Energy</span><span>CB dmg</span>
          </div>
          {[...s.history].reverse().map(h => (
            <div key={h.day} style={{display:'grid', gridTemplateColumns: 'repeat(5, 1fr)', padding:'7px 16px', fontSize: 12, borderBottom:'1px solid var(--border)'}} className="mono">
              <span>{h.day}</span>
              <span style={{color:'var(--accent)'}}>{h.gems}</span>
              <span style={{color:'var(--violet)'}}>{h.silver_m != null ? h.silver_m.toFixed(1) + 'M' : '—'}</span>
              <span style={{color:'oklch(0.72 0.16 85)'}}>{h.energy != null ? h.energy.toLocaleString() : '—'}</span>
              <span style={{color: h.cb_dmg_m > 0 ? 'oklch(0.82 0.17 85)' : 'var(--text-dim)'}}>
                {h.cb_dmg_m > 0 ? h.cb_dmg_m.toFixed(1) + 'M' : '—'}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function PageMod({s}) {
  return (
    <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap: 10, minHeight: '100%'}}>
      <div className="card" style={{padding: 18}}>
        <div className="card-title" style={{marginBottom: 12}}>MelonLoader mod</div>
        <div className="mono" style={{fontSize: 12, lineHeight: 1.8, color:'var(--text-sub)'}}>
          <div>RaidAutomationMod.dll · v1.4</div>
          <div>HTTP · <span style={{color:'var(--accent)'}}>127.0.0.1:6790</span></div>
          <div>Handlers · /status, /buttons, /click, /find, /scene</div>
          <div>Queue · Unity main-thread</div>
          <div style={{color:'var(--ok)', marginTop: 6}}>● 14 interactable buttons online</div>
        </div>
      </div>
      <div className="card" style={{padding: 18}}>
        <div className="card-title" style={{marginBottom: 12}}>IL2CPP offsets</div>
        <div className="mono" style={{fontSize: 11.5, lineHeight: 1.8, color:'var(--text-sub)'}}>
          <div>AppModel · <span style={{color:'var(--accent)'}}>0x4DC1558</span></div>
          <div>AppViewModel · <span style={{color:'var(--accent)'}}>0x4DC2A28</span></div>
          <div>Unity · 6000.0.60</div>
          <div>Metadata · v31</div>
          <div>Game ver · 11.30.0</div>
          <div style={{color:'var(--text-dim)', marginTop: 6}}>Source: Il2CppDumper v6.7.46</div>
        </div>
      </div>
      <div className="card" style={{padding: 18, gridColumn: 'span 2'}}>
        <div className="card-title" style={{marginBottom: 12}}>VM · mothership2</div>
        <div style={{display:'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16}}>
          <div><div style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase'}}>Host</div><div className="mono" style={{fontSize: 13, marginTop: 4}}>{s.vm.host}</div></div>
          <div><div style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase'}}>IP</div><div className="mono" style={{fontSize: 13, marginTop: 4}}>{s.vm.ip}</div></div>
          <div><div style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase'}}>CPU</div><div className="mono" style={{fontSize: 13, marginTop: 4, color:'var(--accent)'}}>{Math.round(s.vm.cpu)}%</div></div>
          <div><div style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase'}}>RAM</div><div className="mono" style={{fontSize: 13, marginTop: 4}}>{s.vm.ram.toFixed(1)} / {s.vm.ramMax} GB</div></div>
        </div>
      </div>
    </div>
  );
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
    } catch (e) { setErr(String(e)); }
  }, []);

  React.useEffect(() => { load(); const id = setInterval(load, 5000); return () => clearInterval(id); }, [load]);

  const add = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await fetch('/api/schedule', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name, time, command: cmd}),
      });
      const d = await r.json();
      if (r.ok && d.ok) { setName(''); load(); }
      else setErr(d.message || d.error || 'create failed');
    } catch (e) { setErr(String(e)); }
    setBusy(false);
  };

  const del = async (n) => {
    if (!confirm(`Delete \\PyAutoRaid\\${n}?`)) return;
    try {
      const r = await fetch('/api/schedule/' + encodeURIComponent(n), {method: 'DELETE'});
      const d = await r.json();
      if (!d.ok) setErr(d.message || d.error);
      load();
    } catch (e) { setErr(String(e)); }
  };

  const toggle = async (n, enabled) => {
    try {
      const r = await fetch('/api/schedule/' + encodeURIComponent(n) + '/toggle', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({enabled}),
      });
      const d = await r.json();
      if (!d.ok) setErr(d.message || d.error);
      load();
    } catch (e) { setErr(String(e)); }
  };

  const input = {
    background: 'var(--bg-subtle)',
    border: '1px solid var(--border)',
    borderRadius: 5,
    padding: '5px 8px',
    fontSize: 12,
    fontFamily: "'JetBrains Mono', monospace",
    color: 'var(--text)',
    outline: 'none',
  };

  const fmtTime = (iso) => {
    if (!iso || !iso.includes('T')) return iso || '—';
    return iso.split('T')[1].slice(0, 5);
  };

  return (
    <div className="card" style={{padding: 16}}>
      <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom: 10}}>
        <div className="card-title">Windows Task Scheduler</div>
        <span className="mono" style={{fontSize: 10.5, color:'var(--text-dim)'}}>\PyAutoRaid\</span>
      </div>

      {err && (
        <div style={{fontSize: 11, color:'var(--danger)', marginBottom: 8, wordBreak: 'break-word'}}>
          {err}
        </div>
      )}

      {tasks === null && <div style={{fontSize: 11, color:'var(--text-dim)'}}>Loading…</div>}
      {Array.isArray(tasks) && tasks.length === 0 && (
        <div style={{fontSize: 11, color:'var(--text-dim)', marginBottom: 10}}>No triggers in \PyAutoRaid\</div>
      )}
      {Array.isArray(tasks) && tasks.map(t => (
        <div key={t.name} style={{
          display: 'grid',
          gridTemplateColumns: '14px 1fr 46px 20px',
          gap: 8, alignItems: 'center',
          padding: '6px 0',
          borderBottom: '1px solid var(--border)',
          opacity: t.enabled ? 1 : 0.55,
        }}>
          <div
            onClick={()=>toggle(t.name, !t.enabled)}
            title={t.enabled ? 'Disable' : 'Enable'}
            style={{
              width: 14, height: 14, borderRadius: 3,
              border: '1px solid',
              borderColor: t.enabled ? 'var(--accent)' : 'var(--border-strong)',
              background: t.enabled ? 'var(--accent-soft)' : 'transparent',
              cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            {t.enabled && <SvgIcon.check style={{color:'var(--accent)', opacity: 0.85}}/>}
          </div>
          <div style={{minWidth: 0}}>
            <div style={{fontSize: 12, fontWeight: 500}}>{t.name}</div>
            <div className="mono truncate" style={{fontSize: 10, color:'var(--text-dim)'}}>
              {(t.execute || '') + (t.arguments ? ' ' + t.arguments : '')}
            </div>
          </div>
          <span className="mono" style={{fontSize: 11, color:'var(--text-sub)', textAlign:'right'}}>
            {fmtTime(t.startBoundary)}
          </span>
          <button
            onClick={()=>del(t.name)}
            className="btn ghost"
            title="Delete"
            style={{width: 20, height: 20, padding: 0, fontSize: 14, lineHeight: 1, color:'var(--danger)'}}
          >×</button>
        </div>
      ))}

      <div style={{marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border)'}}>
        <div className="card-title" style={{marginBottom: 8}}>Add trigger</div>
        <div style={{display:'grid', gridTemplateColumns: '1fr 110px', gap: 6, marginBottom: 6}}>
          <input
            type="text"
            placeholder="name"
            value={name}
            onChange={e => setName(e.target.value.replace(/[^A-Za-z0-9_\-]/g, ''))}
            style={input}
          />
          <input type="time" value={time} onChange={e => setTime(e.target.value)} style={input}/>
        </div>
        <input
          type="text"
          placeholder="command"
          value={cmd}
          onChange={e => setCmd(e.target.value)}
          style={{...input, width: '100%', marginBottom: 6}}
        />
        <button
          className="btn primary"
          onClick={add}
          disabled={busy || !name || !cmd}
          style={{width: '100%', height: 26, fontSize: 12, justifyContent: 'center'}}
        >
          {busy ? 'Adding…' : 'Add trigger'}
        </button>
      </div>
    </div>
  );
}

// ============================================================================
// CBTuneLab — tune picker, compliance diff, affinity matrix, apply-tune button.
// Combines /api/tune-library, /api/tune-compliance, /api/sim-affinity-matrix,
// and POST /api/apply-tune into a single panel on the CB page.
// ============================================================================
function CBTuneLab({potentialTeams = [], initialSim = null}) {
  const [tunes, setTunes] = React.useState([]);
  const [selectedTune, setSelectedTune] = React.useState('myth_eater');
  const [compliance, setCompliance] = React.useState(null);
  const [affMatrix, setAffMatrix] = React.useState(null);
  const [recommend, setRecommend] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const [applyMsg, setApplyMsg] = React.useState(null);
  const [showSweep, setShowSweep] = React.useState(false);
  // DWJ-parity sim — defaults to top-runnable; clicking a comp swaps it.
  const [parity, setParity] = React.useState(initialSim);
  const [parityBusy, setParityBusy] = React.useState(false);
  const [pickedComp, setPickedComp] = React.useState(null);   // comp.id
  React.useEffect(() => { if (initialSim && !parity) setParity(initialSim); }, [initialSim]);

  const loadParity = (hash) => {
    if (!hash) return;
    setParityBusy(true);
    fetch(`/api/calc-parity-sim?hash=${encodeURIComponent(hash)}&turns=20`)
      .then(r => r.json())
      .then(d => { if (!d.error) setParity(d); setParityBusy(false); })
      .catch(() => setParityBusy(false));
  };

  React.useEffect(() => {
    fetch('/api/tune-library').then(r => r.json()).then(d => setTunes(d.tunes || []));
    fetch('/api/sim-affinity-matrix').then(r => r.json()).then(d => setAffMatrix(d.results || null));
    fetch('/api/tune-recommend').then(r => r.json()).then(setRecommend);
  }, []);

  React.useEffect(() => {
    if (!selectedTune) return;
    setCompliance(null);
    fetch('/api/tune-compliance?tune=' + selectedTune).then(r => r.json()).then(setCompliance);
  }, [selectedTune]);

  const apply = async (tuneId) => {
    setBusy(true); setApplyMsg(null);
    try {
      const r = await fetch('/api/apply-tune', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({tune: tuneId || selectedTune, preset_id: 1}),
      });
      const d = await r.json();
      setApplyMsg(d.ok ? `Applied ${tuneId || selectedTune} to preset #1 ✓` : `${d.error || 'failed'}`);
    } catch (e) { setApplyMsg(String(e)); }
    setBusy(false);
  };

  const statusColor = {
    on_target: 'var(--accent)',
    too_fast:  'oklch(0.75 0.17 85)',
    too_slow:  'oklch(0.65 0.23 25)',
  };

  return (
    <div className="card" style={{padding: 0, gridColumn: '1 / -1', overflow: 'hidden'}}>
      <PanelHeader title="tune lab" right={`${potentialTeams.length} DWJ comps · 100% parity vs DWJ calc · ${tunes.length} sim tunes`}/>

      {/* ======= Section 1: DWJ tunes vs your roster (potential teams) ======= */}
      {potentialTeams.length > 0 && (
        <div style={{borderBottom:'1px solid var(--border)'}}>
          <div style={{padding:'10px 14px', display:'flex', alignItems:'baseline', justifyContent:'space-between'}}>
            <span style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em'}}>DWJ tunes vs your roster · sim-validated</span>
            <span style={{fontSize: 10, color:'var(--text-dim)'}}>click a comp to load its DWJ-parity cast timeline below</span>
          </div>
          <div style={{display:'grid', gridTemplateColumns:'repeat(2, 1fr)', gap: 1, background:'var(--border)'}}>
            {potentialTeams.map(pt => {
              const statusColor = pt.status==='active' ? 'var(--accent)' : pt.status==='backup' ? 'var(--text-dim)' : 'var(--violet)';
              const calcUnm = (pt.calculator_links || []).find(l => /ultra|unm/i.test(l.name || ''))
                           || (pt.calculator_links || [])[0];
              const isPicked = pickedComp === pt.id;
              return (
                <div key={pt.id || pt.name}
                     onClick={() => { setPickedComp(pt.id); if (calcUnm?.hash) loadParity(calcUnm.hash); }}
                     style={{padding: 14, background: isPicked ? 'var(--bg-subtle)' : 'var(--bg-elev)', display:'flex', flexDirection:'column', gap: 8, cursor:'pointer', borderLeft: isPicked ? '2px solid var(--accent)' : '2px solid transparent'}}>
                  <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', gap: 8}}>
                    <div style={{display:'flex', gap: 6, alignItems:'center', flexWrap:'wrap'}}>
                      <span style={{fontSize: 9, textTransform:'uppercase', letterSpacing:'0.08em', color: statusColor, border:`1px solid ${statusColor}`, padding:'1px 5px', borderRadius: 3}}>
                        {pt.status}
                      </span>
                      {pt.key_capability && <span style={{fontSize: 9, padding:'1px 5px', background:'var(--bg-subtle)', border:'1px solid var(--border)', borderRadius: 3, color:'var(--text-sub)'}}>{pt.key_capability}</span>}
                      {pt.affinity && <span style={{fontSize: 9, padding:'1px 5px', background:'var(--bg-subtle)', border:'1px solid var(--border)', borderRadius: 3, color:'var(--text-sub)'}}>{pt.affinity}</span>}
                      {pt.parity_sim && (
                        <span title="DWJ-parity scheduler simulation (100% calc match across 4 tested variants)"
                              style={{
                                fontSize: 9, padding:'1px 5px', borderRadius: 3,
                                background: pt.parity_sim.survived ? 'oklch(0.55 0.15 145 / 0.18)' : 'oklch(0.55 0.17 25 / 0.18)',
                                border: `1px solid ${pt.parity_sim.survived ? 'var(--ok)' : 'var(--danger)'}`,
                                color: pt.parity_sim.survived ? 'var(--ok)' : 'var(--danger)',
                              }}>
                          {pt.parity_sim.survived ? `✓ 50T sim` : `✗ dies bt${pt.parity_sim.boss_turns}`}
                        </span>
                      )}
                    </div>
                    <span className="mono" style={{fontSize: 10.5, color:'var(--text-dim)'}}>conf {(pt.confidence*100).toFixed(0)}%</span>
                  </div>
                  <div style={{display:'flex', alignItems:'baseline', justifyContent:'space-between', gap: 8}}>
                    <div style={{fontSize: 14, fontWeight: 500}}>{pt.name}</div>
                    <div style={{display:'flex', alignItems:'baseline', gap: 5}}>
                      <span className="num mono" style={{fontSize: 18, fontWeight: 600, color: pt.status==='active' ? 'var(--accent)' : 'var(--text)'}}>{(pt.est_damage/1e6).toFixed(1)}</span>
                      <span style={{fontSize: 10, color:'var(--text-sub)'}}>M est</span>
                    </div>
                  </div>
                  {pt.slots && pt.slots.length > 0 && (
                    <div style={{display:'grid', gridTemplateColumns:'24px 1fr 110px 50px', gap: 4, fontSize: 10.5, lineHeight: 1.5}}>
                      {pt.slots.map((sl, i) => {
                        const mark = sl.status === 'filled_6star' ? '✓' : sl.status === 'filled_ascending' ? '~' : sl.status === 'generic' ? '·' : '✗';
                        const markColor = sl.status === 'filled_6star' ? 'var(--ok)' : sl.status === 'filled_ascending' ? 'var(--warn)' : sl.status === 'generic' ? 'var(--text-dim)' : 'var(--danger)';
                        const spdRange = (sl.min_spd !== null && sl.max_spd !== null)
                          ? (sl.min_spd === sl.max_spd ? String(sl.min_spd) : `${sl.min_spd}-${sl.max_spd}`)
                          : '—';
                        return (
                          <React.Fragment key={i}>
                            <span style={{color: markColor, textAlign:'center'}}>{mark}</span>
                            <span style={{color:'var(--text)'}}>{sl.hero || '—'}</span>
                            <span className="mono" style={{color:'var(--text-sub)', textAlign:'right', fontSize: 10}}>SPD {spdRange}</span>
                            <span className="mono" style={{color:'var(--text-dim)', textAlign:'right', fontSize: 10}}>{sl.roster_grade ? `${sl.roster_grade}★` : ''}</span>
                          </React.Fragment>
                        );
                      })}
                    </div>
                  )}
                  {pt.note && (
                    <div style={{fontSize: 10.5, color:'var(--text-sub)', lineHeight: 1.5, marginTop: 2}}>
                      {pt.note}
                    </div>
                  )}
                  <div style={{display:'flex', gap: 6, marginTop: 4}} onClick={e => e.stopPropagation()}>
                    {calcUnm && calcUnm.url && (
                      <a href={calcUnm.url} target="_blank" rel="noreferrer" className="mono" style={{fontSize: 10, color:'var(--accent)', textDecoration:'none', padding:'2px 6px', border:'1px solid var(--accent)', borderRadius: 3}}>
                        open DWJ calc ↗
                      </a>
                    )}
                    {pt.dwj_url && (
                      <a href={pt.dwj_url} target="_blank" rel="noreferrer" className="mono" style={{fontSize: 10, color:'var(--text-dim)', textDecoration:'none', padding:'2px 6px', border:'1px solid var(--border)', borderRadius: 3}}>
                        tune page ↗
                      </a>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ======= Section 2: DWJ-parity cast timeline (driven by Section 1 selection) ======= */}
      {parity && (
        <div style={{borderBottom:'1px solid var(--border)'}}>
          <div style={{padding:'10px 14px', display:'flex', alignItems:'baseline', justifyContent:'space-between'}}>
            <span style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em'}}>
              cast timeline · {parity.variant?.name || '?'}{parityBusy ? ' · loading…' : ''}
            </span>
            <span style={{fontSize: 10, color:'var(--text-dim)'}}>
              DWJ-parity scheduler · {parity.boss_turn_count} boss turns · {parity.turn_count} actions
            </span>
          </div>
          <div style={{display:'grid', gridTemplateColumns:'1.1fr 1fr', gap: 1, background:'var(--border)'}}>
            {/* left: slot overview */}
            <div style={{padding: 14, background:'var(--bg-elev)'}}>
              <div style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em', marginBottom: 10}}>
                Team ({(parity.variant?.slots || []).length} slots, boss SPD {parity.variant?.boss_speed})
              </div>
              {(parity.variant?.slots || []).map((sl, i, arr) => (
                <div key={i} style={{display:'grid', gridTemplateColumns:'1fr 60px 200px', gap: 8, fontSize: 11, lineHeight: 1.7, borderBottom: i < arr.length - 1 ? '1px dashed var(--border)' : 'none', padding:'3px 0'}}>
                  <span>{sl.name}</span>
                  <span className="mono" style={{textAlign:'right', color:'var(--text-sub)'}}>SPD {sl.total_speed}</span>
                  <span className="mono" style={{fontSize: 9.5, color:'var(--text-dim)'}}>
                    {(sl.skill_configs || []).filter(c => c.alias !== 'A4').map(c => `${c.alias}${c.delay ? `d${c.delay}` : ''}${c.cooldown ? `/${c.cooldown}` : ''}`).join(' · ')}
                  </span>
                </div>
              ))}
              {parity.cast_summary && parity.cast_summary.length > 0 && (
                <div style={{marginTop: 14, borderTop:'1px solid var(--border)', paddingTop: 10}}>
                  <div style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em', marginBottom: 6}}>
                    Cast counts (top)
                  </div>
                  <div style={{display:'grid', gridTemplateColumns:'1fr 60px 30px', gap: 4, fontSize: 11, lineHeight: 1.6}}>
                    {parity.cast_summary.slice(0, 10).map((c, i) => (
                      <React.Fragment key={i}>
                        <span>{c.actor}</span>
                        <span className="mono" style={{color:'var(--text-sub)'}}>{c.skill}</span>
                        <span className="mono num" style={{textAlign:'right'}}>{c.count}</span>
                      </React.Fragment>
                    ))}
                  </div>
                </div>
              )}
            </div>
            {/* right: boss-turn grouped timeline */}
            <div style={{padding: 14, background:'var(--bg-elev)', maxHeight: 400, overflowY:'auto'}}>
              <div style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em', marginBottom: 10}}>
                Turn order (champion actions between boss turns)
              </div>
              {(() => {
                const groups = [];
                let current = {boss_turn: null, actions: []};
                for (const t of (parity.timeline || [])) {
                  if (t.actor === 'Clanboss') {
                    current.actions.push({...t, isBoss: true});
                    groups.push(current);
                    current = {boss_turn: t.boss_turn + 1, actions: []};
                  } else {
                    if (current.boss_turn === null) current.boss_turn = t.boss_turn;
                    current.actions.push({...t, isBoss: false});
                  }
                }
                if (current.actions.length) groups.push(current);
                return groups.map((g, gi) => (
                  <div key={gi} style={{marginBottom: 10}}>
                    {g.actions.map((a, ai) => (
                      <div key={ai} style={{
                        display:'flex', gap: 6, padding:'3px 8px', fontSize: 11, lineHeight: 1.6,
                        background: a.isBoss ? 'var(--bg-subtle)' : 'transparent',
                        color: a.isBoss ? 'var(--violet)' : 'var(--text)',
                        borderRadius: 3, marginBottom: 1,
                      }}>
                        <span className="mono" style={{width: 30, color:'var(--text-dim)', fontSize: 10}}>
                          {a.isBoss ? `bt${a.boss_turn}` : ''}
                        </span>
                        <span style={{flex: 1}}>{a.actor}</span>
                        <span className="mono" style={{color: a.isBoss ? 'var(--violet)' : 'var(--text-sub)', fontSize: 10.5}}>{a.skill}</span>
                      </div>
                    ))}
                  </div>
                ));
              })()}
            </div>
          </div>
        </div>
      )}

      {/* ======= Section 3: Hand-tune compliance (cb_sim using your real gear) ======= */}
      <div style={{padding:'10px 14px 4px 14px', fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.06em', borderBottom:'1px solid var(--border)'}}>
        Hand-maintained tunes · run cb_sim on your live gear
      </div>
      <div style={{display: 'grid', gridTemplateColumns: '280px 1fr 340px', gap: 14, padding: 14, alignItems: 'start'}}>

        {/* LEFT: Tune picker + Apply */}
        <div>
          <div style={{fontSize: 10.5, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6}}>Tune</div>
          <select value={selectedTune} onChange={e => setSelectedTune(e.target.value)}
            style={{width: '100%', padding: '6px 8px', background: 'var(--bg-subtle)', border: '1px solid var(--border)',
                    borderRadius: 4, color: 'var(--text)', fontSize: 12.5, fontFamily: 'inherit'}}>
            {tunes.map(t => (
              <option key={t.id} value={t.id}>{t.name} · {t.performance} · {t.difficulty}</option>
            ))}
          </select>
          {(() => {
            const t = tunes.find(x => x.id === selectedTune);
            if (!t) return null;
            return (
              <div style={{marginTop: 8, fontSize: 11, color: 'var(--text-sub)', lineHeight: 1.5}}>
                {t.notes?.slice(0, 250)}
              </div>
            );
          })()}
          <button className="btn primary"
                  onClick={apply} disabled={busy || selectedTune !== 'myth_eater'}
                  title={selectedTune !== 'myth_eater' ? 'Auto-apply only supported for myth_eater currently' : 'Push tune opener+priorities to preset #1'}
                  style={{marginTop: 10, width: '100%', height: 28, fontSize: 12, justifyContent: 'center'}}>
            {busy ? 'Applying…' : 'Apply to CB preset #1'}
          </button>
          {applyMsg && <div style={{marginTop: 6, fontSize: 10.5, color: 'var(--text-sub)'}}>{applyMsg}</div>}
        </div>

        {/* CENTER: Per-hero tune compliance */}
        <div>
          <div style={{fontSize: 10.5, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6}}>Team vs Tune</div>
          {!compliance ? (
            <div style={{fontSize: 11, color: 'var(--text-dim)'}}>Loading…</div>
          ) : compliance.error ? (
            <div style={{fontSize: 11, color: 'oklch(0.65 0.23 25)'}}>{compliance.error}</div>
          ) : (
            <div>
              {(compliance.slots || []).map(s => {
                const c = statusColor[s.status] || 'var(--text-dim)';
                const bandTxt = s.target_low === s.target_high ? `${s.target_low}` : `${s.target_low}–${s.target_high}`;
                return (
                  <div key={s.slot} style={{display: 'grid', gridTemplateColumns: '24px 1fr 60px 80px 110px', gap: 8, padding: '4px 0', fontSize: 12, alignItems: 'center', borderBottom: '1px solid var(--border)'}}>
                    <span className="mono" style={{color: 'var(--text-dim)'}}>{s.slot}</span>
                    <div>
                      <div>{s.hero}</div>
                      <div style={{fontSize: 10, color: 'var(--text-dim)'}}>{s.role}</div>
                    </div>
                    <span className="mono num" style={{color: c, fontWeight: 500}}>{s.actual_spd}</span>
                    <span className="mono" style={{color: 'var(--text-dim)', fontSize: 11}}>target {bandTxt}</span>
                    <span className="mono" style={{color: c, fontSize: 11}}>
                      {s.status === 'on_target' ? '✓ on target' :
                       s.status === 'too_fast'  ? `+${s.delta} too fast` :
                                                   `${s.delta} too slow`}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* RIGHT: Affinity matrix */}
        <div>
          <div style={{fontSize: 10.5, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6}}>
            Sim on all 4 affinities
          </div>
          {!affMatrix ? (
            <div style={{fontSize: 11, color: 'var(--text-dim)'}}>Running sim…</div>
          ) : (
            <div>
              <div style={{display: 'grid', gridTemplateColumns: '70px 50px 80px 50px', gap: 6, padding: '4px 0', fontSize: 10.5, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.04em', borderBottom: '1px solid var(--border)'}}>
                <span>Affinity</span><span>Turns</span><span style={{textAlign:'right'}}>Damage</span><span style={{textAlign:'right'}}>Gaps</span>
              </div>
              {['magic', 'force', 'spirit', 'void'].map(a => {
                const r = affMatrix[a];
                if (!r) return null;
                const isBest = Object.values(affMatrix).reduce((m, x) => Math.max(m, x.total_damage || 0), 0) === (r.total_damage || 0);
                const isDead = r.first_death_bt != null && r.first_death_bt < 50;
                return (
                  <div key={a} style={{display: 'grid', gridTemplateColumns: '70px 50px 80px 50px', gap: 6, padding: '5px 0', fontSize: 12, borderBottom: '1px solid var(--border)'}}>
                    <span style={{color: isBest ? 'var(--accent)' : 'var(--text)'}}>{r.affinity}</span>
                    <span className="mono num" style={{color: isDead ? 'oklch(0.65 0.23 25)' : 'var(--text-sub)'}}>
                      {isDead ? `✗${r.first_death_bt}` : r.cb_turns}
                    </span>
                    <span className="mono num" style={{textAlign: 'right', color: isBest ? 'var(--accent)' : 'var(--text)'}}>
                      {r.total_damage ? (r.total_damage/1e6).toFixed(1) + 'M' : '—'}
                    </span>
                    <span className="mono" style={{textAlign: 'right', color: r.gaps > 2 ? 'oklch(0.65 0.23 25)' : 'var(--text-dim)', fontSize: 11}}>
                      {r.gaps ?? '—'}
                    </span>
                  </div>
                );
              })}
              <div style={{marginTop: 6, fontSize: 10.5, color: 'var(--text-dim)', lineHeight: 1.4}}>
                Sim currently predicts 50T survival on all affinities — real gameplay may still fail on Force due to weak-affinity damage amp.
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Bottom row: tune recommender + CB reset countdown + SPD sweep toggle */}
      <div style={{borderTop: '1px solid var(--border)', padding: '12px 14px', display: 'grid', gridTemplateColumns: '1fr 260px', gap: 14}}>
        {/* Tune recommender: ranks all tunes by predicted damage on today's affinity */}
        <div>
          <div style={{display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 4}}>
            <span style={{fontSize: 10.5, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em'}}>
              Best tune for {recommend?.affinity || 'today'}
            </span>
            <span style={{fontSize: 10, color: 'var(--text-dim)'}} title="Sim damage across the full 50-turn prediction per tune.">
              ranked by sim damage
            </span>
          </div>
          {!recommend ? (
            <div style={{fontSize: 11, color: 'var(--text-dim)'}}>Running sim on each tune…</div>
          ) : (
            <div style={{display: 'grid', gridTemplateColumns: '180px 80px 80px 70px 1fr 100px', gap: 6, fontSize: 11.5}}>
              <span style={{color: 'var(--text-dim)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.04em'}}>Tune</span>
              <span style={{color: 'var(--text-dim)', fontSize: 10, textTransform: 'uppercase'}}>Difficulty</span>
              <span style={{color: 'var(--text-dim)', fontSize: 10, textTransform: 'uppercase'}}>Perf</span>
              <span style={{color: 'var(--text-dim)', fontSize: 10, textTransform: 'uppercase', textAlign: 'right'}}>Turns</span>
              <span style={{color: 'var(--text-dim)', fontSize: 10, textTransform: 'uppercase', textAlign: 'right'}}>Damage</span>
              <span></span>
              {(recommend.results || []).map((r, i) => {
                if (r.incompatible) {
                  return (
                    <React.Fragment key={r.tune}>
                      <span style={{color: 'var(--text-dim)', textDecoration: 'line-through'}} title={`Missing: ${(r.missing_heroes||[]).join(', ')}`}>
                        {r.name}
                      </span>
                      <span style={{color: 'var(--text-dim)', fontSize: 10.5}}>—</span>
                      <span style={{color: 'var(--text-dim)', fontSize: 10.5}}>—</span>
                      <span style={{color: 'var(--text-dim)', textAlign: 'right'}}>—</span>
                      <span style={{color: 'oklch(0.65 0.23 25)', textAlign: 'right', fontSize: 10.5}}>
                        need {(r.missing_heroes || []).join(', ')}
                      </span>
                      <span></span>
                    </React.Fragment>
                  );
                }
                // Index among compatibles only
                const compIdx = (recommend.results || []).filter(x => !x.incompatible).indexOf(r);
                return (
                  <React.Fragment key={r.tune}>
                    <span style={{color: compIdx === 0 ? 'var(--accent)' : 'var(--text)', fontWeight: compIdx === 0 ? 500 : 400}}>
                      {compIdx === 0 ? '🏆 ' : ''}{r.name}
                    </span>
                    <span style={{color: 'var(--text-sub)', fontSize: 10.5}}>{r.difficulty}</span>
                    <span style={{color: 'var(--text-sub)', fontSize: 10.5}}>{r.performance}</span>
                    <span className="mono" style={{textAlign: 'right', color: 'var(--text-sub)'}}>
                      {r.cb_turns ?? '—'}
                    </span>
                    <span className="mono num" style={{textAlign: 'right', color: compIdx === 0 ? 'var(--accent)' : 'var(--text)'}}>
                      {r.damage ? (r.damage/1e6).toFixed(1) + 'M' : '—'}
                    </span>
                    <button className="btn" onClick={() => apply(r.tune)} disabled={busy}
                            style={{height: 20, fontSize: 10, padding: '0 6px', justifyContent: 'center'}}>
                      Apply
                    </button>
                  </React.Fragment>
                );
              })}
            </div>
          )}
        </div>

        {/* Right: SPD sweep toggle (reset countdown moved to CB page header) */}
        <div style={{alignSelf: 'start'}}>
          <button className="btn" onClick={() => setShowSweep(!showSweep)}
                  style={{height: 24, fontSize: 11, justifyContent: 'center', width: '100%'}}>
            {showSweep ? 'Hide' : 'Show'} SPD sweep
          </button>
        </div>
      </div>

      {showSweep && <CBSpeedSweep/>}
      <CBPresetEditor/>
    </div>
  );
}


// ============================================================================
// CBPresetEditor — edit Openers (∞) + per-skill priority ranks without
// leaving the dashboard. Mirrors Raid's in-game Skill Instructions UI.
// ============================================================================
function CBPresetEditor() {
  const [preset, setPreset] = React.useState(null);
  const [edits, setEdits] = React.useState({});  // hero_id -> {opener, priorities:{sid:rank}}
  const [busy, setBusy] = React.useState(false);
  const [msg, setMsg] = React.useState(null);

  const load = () => {
    fetch('/api/preset?id=1').then(r => r.json()).then(d => {
      setPreset(d); setEdits({});
    });
  };
  React.useEffect(() => { load(); }, []);

  const setField = (hero_id, patch) => {
    setEdits(prev => ({...prev, [hero_id]: {...(prev[hero_id] || {}), ...patch}}));
  };

  // Build effective state per hero: original + user edits overlay
  const effective = (h) => {
    const e = edits[h.hero_id] || {};
    return {
      opener: e.opener !== undefined ? e.opener : (h.starter_ids[0] || null),
      priorities: e.priorities || h.priorities,
    };
  };

  const save = async () => {
    if (!preset) return;
    setBusy(true); setMsg(null);
    try {
      const payload = {
        preset_id: preset.id,
        heroes: (preset.heroes || []).map(h => {
          const eff = effective(h);
          return {
            hero_id: h.hero_id,
            opener: eff.opener,
            priorities: eff.priorities,
          };
        }),
      };
      const r = await fetch('/api/preset/edit', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload),
      });
      const d = await r.json();
      setMsg(d.ok ? 'Saved ✓' : (d.error || 'failed'));
      setTimeout(load, 600);
    } catch (e) { setMsg(String(e)); }
    setBusy(false);
  };

  if (!preset) return null;
  if (preset.error) {
    return (
      <div style={{borderTop: '1px solid var(--border)', padding: 12, fontSize: 11, color: 'var(--text-dim)'}}>
        Preset editor: {preset.error}
      </div>
    );
  }

  const RANK_OPTS = [
    {v: 0, label: 'Default'},
    {v: 1, label: '1st'},
    {v: 2, label: '2nd'},
    {v: 3, label: '3rd'},
    {v: 4, label: 'Don\'t use'},
  ];

  return (
    <div style={{borderTop: '1px solid var(--border)', padding: '12px 14px'}}>
      <div style={{display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 8}}>
        <span style={{fontSize: 10.5, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em'}}>
          Preset #{preset.id} · {preset.name} · Skill Instructions
        </span>
        <div style={{display: 'flex', gap: 6, alignItems: 'center'}}>
          {msg && <span style={{fontSize: 10.5, color: msg === 'Saved ✓' ? 'var(--accent)' : 'oklch(0.65 0.23 25)'}}>{msg}</span>}
          <button className="btn" onClick={load} disabled={busy}
                  style={{height: 20, fontSize: 10, padding: '0 8px'}}>Reload</button>
          <button className="btn primary" onClick={save} disabled={busy}
                  style={{height: 20, fontSize: 10, padding: '0 10px'}}>{busy ? 'Saving…' : 'Save'}</button>
        </div>
      </div>

      {(preset.heroes || []).map(h => {
        const eff = effective(h);
        const labelEntries = Object.entries(h.skill_labels || {});
        // Sort by label (A1 → A2 → A3)
        labelEntries.sort((a, b) => (a[1].label || '').localeCompare(b[1].label || ''));
        return (
          <div key={h.hero_id} style={{display: 'grid', gridTemplateColumns: '140px 1fr', gap: 10, padding: '6px 0', borderBottom: '1px solid var(--border)', fontSize: 12, alignItems: 'center'}}>
            <div>
              <div style={{fontWeight: 500}}>{h.name}</div>
              <div style={{fontSize: 10, color: 'var(--text-dim)'}}>slot · hero {h.hero_id}</div>
            </div>
            <div style={{display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8}}>
              {labelEntries.map(([sid, info]) => {
                const isOpener = eff.opener == sid;
                const rank = eff.priorities[sid] ?? 0;
                return (
                  <div key={sid} style={{display: 'flex', flexDirection: 'column', gap: 2, padding: 6, background: 'var(--bg-subtle)', border: '1px solid var(--border)', borderRadius: 3}}>
                    <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 4}}>
                      <span className="mono" style={{fontSize: 11, color: 'var(--accent)'}}>{info.label}</span>
                      <span style={{fontSize: 10, color: 'var(--text-dim)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>
                        {info.name}{info.cd ? ` · CD${info.cd}` : ''}
                      </span>
                    </div>
                    <div style={{display: 'flex', gap: 4}}>
                      <label style={{fontSize: 10, color: 'var(--text-sub)', display: 'flex', gap: 3, alignItems: 'center', cursor: 'pointer'}}>
                        <input type="checkbox" checked={isOpener}
                               onChange={e => {
                                 const curEdits = edits[h.hero_id] || {};
                                 setField(h.hero_id, {opener: e.target.checked ? sid : null});
                               }}
                               style={{margin: 0}}/>
                        ∞ Opener
                      </label>
                      <select value={rank}
                              onChange={e => {
                                const curPrios = {...(effective(h).priorities)};
                                curPrios[sid] = parseInt(e.target.value, 10);
                                setField(h.hero_id, {priorities: curPrios});
                              }}
                              style={{flex: 1, background: 'var(--bg-elev)', border: '1px solid var(--border)', borderRadius: 2, padding: '1px 4px', fontSize: 10, color: 'var(--text)', fontFamily: 'inherit'}}>
                        {RANK_OPTS.map(o => <option key={o.v} value={o.v}>{o.label}</option>)}
                      </select>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
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
    setBusy(true); setData(null);
    try {
      const r = await fetch(`/api/sim-sweep?hero=${encodeURIComponent(hero)}&lo=${lo}&hi=${hi}`);
      setData(await r.json());
    } catch (e) { setData({error: String(e)}); }
    setBusy(false);
  };
  const maxDmg = (data?.sweep || []).reduce((m, r) => Math.max(m, r.damage || 0), 0) || 1;
  return (
    <div style={{borderTop: '1px solid var(--border)', padding: '12px 14px'}}>
      <div style={{display: 'flex', gap: 10, alignItems: 'center', marginBottom: 10}}>
        <span style={{fontSize: 11, color: 'var(--text-dim)'}}>Hero:</span>
        <input type="text" value={hero} onChange={e => setHero(e.target.value)}
               style={{background: 'var(--bg-subtle)', border: '1px solid var(--border)', borderRadius: 3, padding: '3px 6px', fontSize: 12, color: 'var(--text)', width: 100}}/>
        <span style={{fontSize: 11, color: 'var(--text-dim)'}}>SPD range:</span>
        <input type="number" value={lo} onChange={e => setLo(+e.target.value)}
               style={{background: 'var(--bg-subtle)', border: '1px solid var(--border)', borderRadius: 3, padding: '3px 6px', fontSize: 12, color: 'var(--text)', width: 60}}/>
        <span style={{fontSize: 10}}>→</span>
        <input type="number" value={hi} onChange={e => setHi(+e.target.value)}
               style={{background: 'var(--bg-subtle)', border: '1px solid var(--border)', borderRadius: 3, padding: '3px 6px', fontSize: 12, color: 'var(--text)', width: 60}}/>
        <button className="btn primary" onClick={run} disabled={busy}
                style={{height: 22, fontSize: 11, padding: '0 10px'}}>
          {busy ? 'Running…' : 'Run sweep'}
        </button>
      </div>
      {data?.error && <div style={{fontSize: 11, color: 'oklch(0.65 0.23 25)'}}>{data.error}</div>}
      {data?.sweep && (
        <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(60px, 1fr))', gap: 4}}>
          {data.sweep.map(r => {
            const pct = (r.damage || 0) / maxDmg;
            const barHeight = Math.max(4, pct * 50);
            return (
              <div key={r.spd} style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2}}
                   title={`SPD ${r.spd}: ${(r.damage||0)/1e6}M damage, ${r.cb_turns} turns, ${r.gaps} gaps`}>
                <div style={{height: 50, display: 'flex', alignItems: 'flex-end'}}>
                  <div style={{width: '100%', maxWidth: 20, height: barHeight, background: r.gaps === 0 ? 'var(--accent)' : r.gaps < 3 ? 'oklch(0.75 0.17 85)' : 'oklch(0.65 0.23 25)'}}/>
                </div>
                <span className="mono" style={{fontSize: 9, color: 'var(--text-dim)'}}>{r.spd}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}


Object.assign(window, {
  PageOverview, PageLive, PageTasks, PageResources, PageCB, PageHeroes, PageEvents, PageHistory, PageMod,
  ScheduleCard,
});
