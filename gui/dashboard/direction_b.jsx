/* ===================== DIRECTION B — Console (dense ops, dark) ===================== */

const B_NAV = [
  { id: 'overview',  label: 'Overview',        hint: '⌘1' },
  { id: 'live',      label: 'Live run',        hint: '⌘2' },
  { id: 'tasks',     label: 'Task schedule',   hint: '⌘3' },
  { id: 'resources', label: 'Resources',       hint: '⌘4' },
  { id: 'cb',        label: 'Clan Boss',       hint: '⌘5' },
  { id: 'dungeons',  label: 'Dungeons',        hint: '⌘D' },
  { id: 'heroes',    label: 'Heroes & artifacts', hint: '⌘6' },
  { id: 'gear',      label: 'Gear gaps',       hint: '⌘G' },
  { id: 'events',    label: 'Events',          hint: '⌘7' },
  { id: 'history',   label: 'History',         hint: '⌘8' },
  { id: 'mod',       label: 'Mod & offsets',   hint: '⌘9' },
];

function DirectionB() {
  const s = useSim();
  const running = s.running;
  const [sec, setSec] = React.useState(() => {
    try { return localStorage.getItem('par_b_section') || 'overview'; } catch(e) { return 'overview'; }
  });
  React.useEffect(() => { try { localStorage.setItem('par_b_section', sec); } catch(e){} }, [sec]);

  const activeTask = s.tasks[s.queueIdx] || null;
  const doneCount = s.tasks.filter(t => t.status === 'done').length;
  const totalMs = s.tasks.reduce((a,t) => a + t.duration, 0);
  const elapsedMs = s.tasks.reduce((a, t, i) => a + (t.status==='done'?t.duration : i===s.queueIdx? t.ms : 0), 0);
  const pct = Math.round((elapsedMs / totalMs) * 100);

  const secMeta = B_NAV.find(n => n.id === sec);

  return (
    <div className="B" style={{display: 'grid', gridTemplateColumns: '200px 1fr', height: '100%'}}>
      {/* ==== Sidebar ==== */}
      <aside style={{
        borderRight: '1px solid var(--border)',
        background: '#07090b',
        display: 'flex', flexDirection: 'column',
      }}>
        <div style={{padding: '12px 14px 10px', borderBottom: '1px solid var(--border)'}}>
          <div style={{display:'flex', alignItems:'center', gap: 8}}>
            <div style={{width: 20, height: 20, borderRadius: 4, background:'var(--accent)', display:'flex', alignItems:'center', justifyContent:'center', color:'#0b0d10', fontWeight:700, fontSize:11}}>▲</div>
            <div style={{fontFamily:"'JetBrains Mono', monospace", fontSize: 12, fontWeight: 600}}>pyautoraid</div>
          </div>
          <div style={{fontSize: 10.5, color:'var(--text-dim)', marginTop: 6}} className="mono">v2.1-beta · {s.account.name}</div>
        </div>

        <nav className="scroll" style={{padding: '8px 6px', display:'flex', flexDirection:'column', gap: 1, flex: 1, overflowY:'auto'}}>
          {B_NAV.map(n => (
            <a key={n.id} href="#" onClick={e=>{e.preventDefault(); setSec(n.id);}} style={{
              display:'flex', alignItems:'center', justifyContent:'space-between',
              padding: '6px 10px', borderRadius: 5,
              textDecoration:'none',
              color: sec === n.id ? 'var(--text)' : 'var(--text-sub)',
              background: sec === n.id ? 'var(--bg-hover)' : 'transparent',
              borderLeft: '2px solid ' + (sec === n.id ? 'var(--accent)' : 'transparent'),
              fontSize: 12,
              fontWeight: sec === n.id ? 500 : 400,
            }}>
              <span>{n.label}</span>
              <span className="mono" style={{fontSize: 10, color: 'var(--text-dim)'}}>{n.hint}</span>
            </a>
          ))}
        </nav>

        {/* Run state footer */}
        <div style={{padding: '10px 12px', borderTop: '1px solid var(--border)', fontSize: 11}}>
          <div style={{display:'flex', alignItems:'center', gap: 6, marginBottom: 4}}>
            <span className={`dot ${running ? 'run' : 'ok'}`}/>
            <span className="mono" style={{color: running ? 'var(--accent)' : 'var(--text-sub)', textTransform:'uppercase', letterSpacing:'0.08em', fontSize: 10}}>{running ? 'running' : 'idle'}</span>
          </div>
          <div style={{color:'var(--text-dim)', fontSize: 10.5}} className="mono">{doneCount}/{s.tasks.length} tasks · {pct}%</div>
          <button
            className={`btn ${running ? '' : 'primary'}`}
            onClick={()=>window.PARSim.setRunning(!running)}
            style={{width:'100%', marginTop: 8, height: 28, justifyContent:'center'}}
          >
            {running ? <><SvgIcon.pause/> Pause</> : <><SvgIcon.play/> Start run</>}
          </button>
        </div>
      </aside>

      {/* ==== Main area ==== */}
      <div style={{display:'grid', gridTemplateRows: '44px 1fr 160px', height: '100%', minWidth: 0, minHeight: 0, overflow: 'hidden'}}>
        {/* Top strip */}
        <header style={{
          display:'flex', alignItems:'center', gap: 14,
          padding: '0 16px',
          borderBottom:'1px solid var(--border)',
          background: 'var(--bg-elev)',
        }}>
          <div style={{fontSize: 13, fontWeight: 500}}>{secMeta?.label}</div>
          <span style={{color:'var(--text-dim)', fontSize: 11}}>/</span>
          <span className="mono" style={{color:'var(--text-dim)', fontSize: 11}}>{sec}</span>
          <span style={{flex: 1}}/>
          <div style={{display:'flex', gap: 14, alignItems:'center', fontSize: 11.5, color:'var(--text-sub)'}}>
            <StripMetric label="Lv" val={s.account.level} accent/>
            <StripMetric label="Power" val={fmt(s.account.power,'power')}/>
            <Sep/>
            <StripMetric icon="energy" val={fmt(s.resources.energy)}/>
            <StripMetric icon="silver" val={fmt(s.resources.silver,'silver')}/>
            <StripMetric icon="shard" val={fmt(s.resources.gems)}/>
            <StripMetric icon="arena" val={s.resources.arena_tokens.toFixed(1)}/>
            <StripMetric icon="cb" val={`${s.resources.cb_keys}/2`}/>
            <Sep/>
            <span className="mono" style={{color:'var(--text-dim)', fontSize: 10.5}}>{s.vm.host} · {Math.round(s.vm.cpu)}% · {s.vm.ram.toFixed(1)}G</span>
          </div>
        </header>

        {/* Page body — scrolls vertically when page content exceeds viewport */}
        <div className="scroll page-body" style={{
          overflowY: 'auto',
          overflowX: 'hidden',
          padding: 12,
          minHeight: 0,
          height: '100%',
        }}>
          {sec === 'overview'  && <PageOverview s={s} pct={pct} doneCount={doneCount} activeTask={activeTask} running={running}/>}
          {sec === 'live'      && <PageLive s={s} pct={pct} doneCount={doneCount} activeTask={activeTask} running={running}/>}
          {sec === 'tasks'     && <PageTasks s={s}/>}
          {sec === 'resources' && <PageResources s={s}/>}
          {sec === 'cb'        && <PageCB s={s}/>}
          {sec === 'dungeons'  && <PageDungeons s={s}/>}
          {sec === 'heroes'    && <PageHeroes s={s}/>}
          {sec === 'gear'      && <PageGear s={s}/>}
          {sec === 'events'    && <PageEvents s={s}/>}
          {sec === 'history'   && <PageHistory s={s}/>}
          {sec === 'mod'       && <PageMod s={s}/>}
        </div>

        {/* Terminal log */}
        <div style={{borderTop: '1px solid var(--border)', background: '#07090b', display: 'flex', flexDirection:'column'}}>
          <div style={{padding:'6px 14px', borderBottom:'1px solid var(--border)', display:'flex', alignItems:'center', gap: 10}}>
            <span style={{fontSize: 10.5, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'0.08em'}}>stdout · HybridController.log</span>
            <span style={{flex:1}}/>
            <span className="mono" style={{fontSize: 10.5, color:'var(--text-dim)'}}>{s.log.length} lines · tail -f</span>
          </div>
          <div style={{flex: 1, minHeight: 0}}><LogFeed limit={40} theme="B"/></div>
        </div>
      </div>
    </div>
  );
}

/* ================ Small shared panels ================ */

function PanelHeader({title, right}) {
  return (
    <div style={{
      padding: '8px 12px',
      borderBottom: '1px solid var(--border)',
      display:'flex', justifyContent:'space-between', alignItems:'center',
      background:'var(--bg-subtle)',
    }}>
      <span style={{fontSize: 10.5, color:'var(--text-sub)', textTransform:'uppercase', letterSpacing:'0.08em', fontWeight: 600}}>{title}</span>
      {right && <span className="mono" style={{fontSize: 10.5, color:'var(--text-dim)'}}>{right}</span>}
    </div>
  );
}
function StripMetric({icon, label, val, accent}) {
  return (
    <span style={{display:'inline-flex', alignItems:'center', gap:5}}>
      {icon && <Icon name={icon} size={12}/>}
      {label && <span style={{color:'var(--text-dim)', fontSize: 10.5, textTransform:'uppercase', letterSpacing:'0.04em'}}>{label}</span>}
      <span className="num mono" style={{color: accent ? 'var(--accent)' : 'var(--text)'}}>{val}</span>
    </span>
  );
}
function Sep() { return <span style={{width: 1, height: 14, background: 'var(--border)'}}/>; }

function PanelTaskQueue({s, compact}) {
  const done = s.tasks.filter(t=>t.status==='done').length;
  const selectedCount = s.tasks.filter(t=>t.selected).length;
  const allSelected = selectedCount === s.tasks.length;
  const noneSelected = selectedCount === 0;
  const headerRight = (
    <div style={{display:'flex', alignItems:'center', gap: 8}}>
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
      <span className="mono" style={{fontSize: 10.5, color:'var(--text-dim)'}}>{done}/{s.tasks.length}</span>
      <button
        className={`btn ${s.running ? '' : 'primary'}`}
        onClick={()=>window.PARSim.setRunning(!s.running)}
        disabled={!s.running && selectedCount===0}
        style={{height: 22, padding:'0 10px', fontSize: 11}}
      >
        {s.running ? <><SvgIcon.pause/> Pause</> : <><SvgIcon.play/> Run {selectedCount < s.tasks.length ? `(${selectedCount})` : ''}</>}
      </button>
    </div>
  );
  return (
    <div className="card" style={{padding: 0, overflow:'hidden', display:'flex', flexDirection:'column'}}>
      <PanelHeader title="task queue" right={headerRight}/>
      <div className="scroll" style={{overflowY:'auto', flex: 1}}>
        {s.tasks.map(t => {
          const pendingSelected = t.status === 'pending' && t.selected;
          const pendingUnselected = t.status === 'pending' && !t.selected;
          const clickable = !s.running && (t.status === 'pending' || t.status === 'skipped');
          return (
          <div key={t.id} style={{
            padding: compact ? '7px 12px' : '9px 12px',
            borderBottom: '1px solid var(--border)',
            background: t.status==='running' ? 'var(--accent-soft)' : 'transparent',
            display:'grid', gridTemplateColumns: '18px 1fr auto', gap: 8, alignItems:'center',
            opacity: (pendingUnselected || t.status==='skipped') ? 0.5 : 1,
          }}>
            <div
              onClick={clickable ? ()=>window.PARSim.toggleSelected(t.id) : undefined}
              title={clickable ? (t.selected ? 'Click to skip' : 'Click to include') : ''}
              style={{
                width: 14, height: 14, borderRadius: 3,
                border: '1px solid',
                borderColor: t.status==='done' ? 'var(--ok)' : t.status==='running' ? 'var(--accent)' : pendingSelected ? 'var(--accent)' : 'var(--border-strong)',
                background: t.status==='done' ? 'var(--ok)' : pendingSelected ? 'var(--accent-soft)' : 'transparent',
                display:'flex', alignItems:'center', justifyContent:'center', color:'#0b0d10',
                cursor: clickable ? 'pointer' : 'default',
            }}>
              {t.status==='done' && <SvgIcon.check/>}
              {t.status==='running' && <div style={{width:4, height:4, background:'var(--accent)', animation:'pulse 1s infinite'}}/>}
              {t.status==='skipped' && <span style={{fontSize: 10, color:'var(--text-dim)', lineHeight: 1}}>-</span>}
              {pendingSelected && <SvgIcon.check style={{color:'var(--accent)', opacity: 0.85}}/>}
            </div>
            <div style={{minWidth: 0}}>
              <div style={{
                fontSize: 12.5,
                color: t.status==='pending' || t.status==='skipped' ? 'var(--text-dim)' : 'var(--text)',
                fontWeight: t.status==='running' ? 500 : 400,
                textDecoration: t.status==='skipped' ? 'line-through' : 'none',
              }}>{t.label}</div>
              <div style={{display:'flex', alignItems:'center', gap:6, marginTop:2}}>
                <span className={`layer-badge layer-${t.layer}`}>{t.layer}</span>
                <span className="mono" style={{fontSize: 10.5, color:'var(--text-dim)'}}>
                  {t.status==='running' ? `${(t.ms/1000).toFixed(1)}s / ${(t.duration/1000).toFixed(1)}s` : `${(t.duration/1000).toFixed(1)}s`}
                </span>
              </div>
            </div>
            {t.status==='running' && (
              <div style={{width: 40, height: 3, borderRadius: 2, background:'var(--bg-subtle)', overflow:'hidden'}}>
                <div style={{height:'100%', width: `${Math.min(100, (t.ms/t.duration)*100)}%`, background:'var(--accent)'}}/>
              </div>
            )}
          </div>
          );
        })}
      </div>
    </div>
  );
}

function PanelActiveTask({s, activeTask, running, doneCount, totalMs, elapsedMs}) {
  return (
    <div className="card" style={{padding: 0, overflow:'hidden'}}>
      <PanelHeader title="active task" right={running ? 'running' : 'idle'}/>
      <div style={{padding: 14}}>
        {activeTask && running ? (
          <>
            <div style={{fontSize: 10.5, color:'var(--text-dim)', letterSpacing:'0.04em', textTransform:'uppercase', marginBottom: 4}}>
              Step {s.queueIdx+1} / {s.tasks.length}
            </div>
            <div style={{fontSize: 20, fontWeight: 500, letterSpacing:'-0.01em', marginBottom: 10}}>{activeTask.label}</div>
            <div style={{display:'flex', alignItems:'center', gap: 10, marginBottom: 14}}>
              <span className={`layer-badge layer-${activeTask.layer}`}>via {activeTask.layer}</span>
              <span className="mono" style={{fontSize: 11.5, color:'var(--text-sub)'}}>
                {Math.min(100, Math.round((activeTask.ms/activeTask.duration)*100))}% · elapsed {(activeTask.ms/1000).toFixed(1)}s
              </span>
            </div>
            <div style={{height: 4, background:'var(--bg-subtle)', borderRadius: 2, overflow:'hidden'}}>
              <div style={{height:'100%', width: `${Math.min(100, (activeTask.ms/activeTask.duration)*100)}%`, background:'var(--accent)'}}/>
            </div>
          </>
        ) : (
          <>
            <div style={{fontSize: 10.5, color:'var(--text-dim)', letterSpacing:'0.04em', textTransform:'uppercase', marginBottom: 4}}>Idle</div>
            <div style={{fontSize: 20, fontWeight: 500, marginBottom: 10}}>
              {doneCount === s.tasks.length ? 'Daily run complete' : 'Awaiting schedule'}
            </div>
            <div style={{fontSize: 12, color:'var(--text-sub)', marginBottom: 14}}>
              Next trigger {relTime(s.nextRunAt)} · Windows Task Scheduler
            </div>
            <div style={{height: 4, background:'var(--bg-subtle)', borderRadius: 2, overflow:'hidden'}}>
              <div style={{height:'100%', width: `${(elapsedMs/totalMs)*100}%`, background:'var(--text-dim)'}}/>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function PanelLayers({s}) {
  return (
    <div className="card" style={{padding: 0, overflow: 'hidden'}}>
      <PanelHeader title="layers" right="3/3"/>
      <div style={{padding: 10, display:'flex', flexDirection:'column', gap: 8}}>
        {['mod','memory','screen'].map(k => {
          const L = s.layers[k];
          return (
            <div key={k} style={{padding:'8px 10px', background:'var(--bg-subtle)', borderRadius: 6, border:'1px solid var(--border)'}}>
              <div style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
                <span className={`layer-badge layer-${k}`}>{k}</span>
                <span className="mono" style={{fontSize: 10, color:'var(--ok)'}}>● {L.latency}ms</span>
              </div>
              <div style={{fontSize: 11.5, marginTop: 4}}>{L.label}</div>
              <div style={{fontSize: 10, color:'var(--text-dim)'}} className="mono truncate">{L.detail}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function PanelEvents({s}) {
  return (
    <div className="card" style={{padding: 0, overflow:'hidden'}}>
      <PanelHeader title="active events" right="double-dip"/>
      <div style={{padding: 12}}>
        {s.events.map(e => (
          <div key={e.name} style={{marginBottom: 10, opacity: e.upcoming ? 0.5 : 1}}>
            <div style={{display:'flex', justifyContent:'space-between', fontSize: 12}}>
              <span style={{fontWeight: 500}}>{e.name}</span>
              <span className="mono" style={{fontSize: 10.5, color:'var(--text-dim)'}}>{e.ends_in}</span>
            </div>
            <div style={{fontSize: 10.5, color:'var(--text-sub)', marginBottom: 4}}>{e.reward}</div>
            <div style={{height: 3, background:'var(--bg-subtle)', borderRadius: 2, overflow:'hidden'}}>
              <div style={{width: `${e.progress*100}%`, height:'100%', background: e.type==='tournament' ? 'var(--violet)' : 'var(--accent)'}}/>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function PanelCB({s, compact}) {
  return (
    <div className="card" style={{padding: 0, overflow:'hidden'}}>
      <PanelHeader title="clan boss · ultra-nightmare" right={s.cb.clan}/>
      <div style={{padding: 14}}>
        <div style={{display:'flex', alignItems:'baseline', gap: 10, marginBottom: 12}}>
          <div style={{fontSize: 24, fontWeight: 600}} className="num">{s.cb.damage_today ? (s.cb.damage_today/1e6).toFixed(1) : '—'}</div>
          <div style={{fontSize: 12, color:'var(--text-sub)'}}>M dmg today</div>
          <div style={{flex:1}}/>
          <div style={{fontSize: 11, color:'var(--text-sub)'}} className="mono">{s.resources.cb_keys}/2 keys</div>
        </div>
        <div style={{display:'flex', alignItems:'end', gap: 4, height: compact ? 56 : 72}}>
          {s.cb.history.map(h => (
            <div key={h.day} style={{flex: 1, display:'flex', flexDirection:'column', alignItems:'center'}}>
              <div style={{
                width: '100%',
                height: `${Math.max(4, (h.dmg/25e6)*(compact?48:64))}px`,
                background: h.day === 'Today' ? 'var(--accent)' : 'var(--border-strong)',
                borderRadius: 2,
              }}/>
              <div style={{fontSize: 9, color:'var(--text-dim)', marginTop: 3}} className="mono">{h.day}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function PanelResources({s}) {
  return (
    <div className="card" style={{padding: 0, overflow:'hidden'}}>
      <PanelHeader title="resources"/>
      <div style={{display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap: 1, background: 'var(--border)'}}>
        {[
          {icon:'energy', label:'energy', val: fmt(s.resources.energy)},
          {icon:'silver', label:'silver', val: fmt(s.resources.silver,'silver')},
          {icon:'shard',  label:'gems',   val: fmt(s.resources.gems)},
          {icon:'arena',  label:'arena tokens', val: s.resources.arena_tokens.toFixed(1)},
          {icon:'cb',     label:'cb keys', val: `${s.resources.cb_keys}/2`},
          {icon:'sacrifice', label:'mystery shards', val: s.resources.shards.mystery},
        ].map(r => (
          <div key={r.label} style={{padding:'10px 12px', background:'var(--bg-elev)'}}>
            <div style={{display:'flex', alignItems:'center', gap:5, fontSize:10.5, color:'var(--text-sub)', textTransform:'uppercase', letterSpacing:'0.04em'}}>
              <Icon name={r.icon} size={12}/> {r.label}
            </div>
            <div style={{fontSize: 17, fontWeight: 500, marginTop: 2}} className="num">{r.val}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function PanelArena({s}) {
  return (
    <div className="card" style={{padding: 0, overflow:'hidden'}}>
      <PanelHeader title="arena picks"/>
      <div style={{padding: 8}}>
        {s.arena_opponents.slice(0,4).map(o => (
          <div key={o.name} style={{
            padding: '5px 6px', borderRadius: 4,
            background: o.pick ? 'var(--accent-soft)' : 'transparent',
            marginBottom: 2,
          }}>
            <div style={{fontSize: 11.5, display:'flex', alignItems:'center', gap: 5}}>
              {o.pick && <span style={{color:'var(--ok)'}}>◆</span>}
              <span className="truncate" style={{flex:1}}>{o.name}</span>
              <span className="mono" style={{fontSize: 10.5, color: o.status==='weak' ? 'var(--ok)' : o.status==='strong' ? 'var(--danger)' : 'var(--text-dim)'}}>{(o.power/1e6).toFixed(2)}M</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function HistoryChartB({data, height=110}) {
  const W = 700, H = height, P = 14;
  const xs = data.map((_, i) => P + i * (W - 2*P) / (data.length - 1));
  const maxGems = Math.max(...data.map(d=>d.gems));
  const maxSilver = Math.max(...data.map(d=>d.silver_m));
  const maxCB = Math.max(...data.map(d=>d.cb_dmg_m));

  const line = (getter, max, color) => {
    const ys = data.map(d => H - P - (getter(d)/max)*(H - 2*P));
    const pts = xs.map((x,i) => [x, ys[i]]);
    const path = pts.map((p,i)=> (i?'L':'M')+p[0].toFixed(1)+','+p[1].toFixed(1)).join(' ');
    return <path d={path} fill="none" stroke={color} strokeWidth="1.4" strokeLinecap="round"/>;
  };

  return (
    <svg viewBox={`0 0 ${W} ${H+16}`} width="100%" height={H+18} style={{display:'block'}}>
      {[0, 0.25, 0.5, 0.75, 1].map((t,i) => (
        <line key={i} x1={P} x2={W-P} y1={P + t*(H-2*P)} y2={P + t*(H-2*P)} stroke="var(--border)"/>
      ))}
      {line(d=>d.silver_m, maxSilver, 'var(--violet)')}
      {line(d=>d.cb_dmg_m, maxCB, 'oklch(0.82 0.17 85)')}
      {line(d=>d.gems, maxGems, 'var(--accent)')}
      {data.map((d, i) => i % 2 === 0 && (
        <text key={d.day} x={xs[i]} y={H+12} fontSize="9" fill="var(--text-dim)" textAnchor="middle" fontFamily="'JetBrains Mono', monospace">{d.day}</text>
      ))}
    </svg>
  );
}

window.DirectionB = DirectionB;

// Expose page components via global scope for the split files
Object.assign(window, {
  PanelHeader, StripMetric, Sep,
  PanelTaskQueue, PanelActiveTask, PanelLayers, PanelEvents, PanelCB, PanelResources, PanelArena,
  HistoryChartB,
});
