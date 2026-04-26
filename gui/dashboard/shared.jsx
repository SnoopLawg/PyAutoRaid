/* ---------- Shared tiny helpers used by both dashboards ---------- */
function fmt(n, kind) {
  if (n == null) return '—';
  if (kind === 'silver') {
    if (n >= 1e6) return (n/1e6).toFixed(1) + 'M';
    if (n >= 1e3) return (n/1e3).toFixed(0) + 'K';
    return String(Math.round(n));
  }
  if (kind === 'power') return (n/1e6).toFixed(2) + 'M';
  if (kind === 'compact') {
    if (n >= 1e6) return (n/1e6).toFixed(1) + 'M';
    if (n >= 1e3) return (n/1e3).toFixed(1) + 'K';
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
  if (h >= 24) return `${sign} ${Math.floor(h/24)}d ${h%24}h`;
  if (h > 0) return `${sign} ${h}h ${m%60}m`;
  if (m > 0) return `${sign} ${m}m`;
  return `${sign} ${Math.floor(diff/1000)}s`;
}
function timeHM(ts) {
  if (!ts) return '—';
  const d = new Date(ts);
  return d.toTimeString().slice(0,5);
}
function useSim() {
  const [s, set] = React.useState(window.PARSim.state);
  React.useEffect(() => window.PARSim.subscribe(v => set({...v})), []);
  return s;
}

/* ---------- Icon thumbnail helper ---------- */
// Logical icon names map to specific transparent-bg PNGs where provided.
const ICON_SRC = {
  shard: 'gems.png',
  gems: 'gems.png',
  arena: 'arena_token.png',
  cb: 'cb_key.png',
};
function Icon({name, size=20, alt}) {
  const src = `assets/icons/${ICON_SRC[name] || name + '.png'}`;
  return <img src={src} width={size} height={size} alt={alt||name}
    style={{objectFit:'contain', display:'inline-block', verticalAlign:'middle'}}/>;
}

/* ---------- Inline SVG icons ---------- */
const SvgIcon = {
  play: (p) => <svg viewBox="0 0 16 16" width="12" height="12" fill="currentColor" {...p}><path d="M4 2l9 6-9 6z"/></svg>,
  pause: (p) => <svg viewBox="0 0 16 16" width="12" height="12" fill="currentColor" {...p}><rect x="4" y="2" width="3" height="12"/><rect x="9" y="2" width="3" height="12"/></svg>,
  check: (p) => <svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" {...p}><polyline points="2.5,8 6.5,12 13.5,4"/></svg>,
  clock: (p) => <svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="1.5" {...p}><circle cx="8" cy="8" r="6"/><path d="M8 4v4l2.5 2" strokeLinecap="round"/></svg>,
  cpu: (p) => <svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="1.2" {...p}><rect x="3" y="3" width="10" height="10" rx="1"/><rect x="5.5" y="5.5" width="5" height="5"/><path d="M1 5h2M1 8h2M1 11h2M13 5h2M13 8h2M13 11h2M5 1v2M8 1v2M11 1v2M5 13v2M8 13v2M11 13v2"/></svg>,
  arrow: (p) => <svg viewBox="0 0 16 16" width="10" height="10" fill="currentColor" {...p}><path d="M6 3l5 5-5 5z"/></svg>,
  restart: (p) => <svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="1.5" {...p}><path d="M13 8a5 5 0 1 1-1.5-3.5" strokeLinecap="round"/><path d="M13 2v3h-3" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  dot: () => <span style={{display:'inline-block', width:4, height:4, borderRadius:'50%', background:'currentColor', margin:'0 6px', verticalAlign:'middle', opacity:0.4}}/>,
};

/* ---------- Sparkline ---------- */
function Spark({data, height=28, width=120, color='currentColor', fill=false}) {
  if (!data || !data.length) return null;
  const max = Math.max(...data), min = Math.min(...data);
  const range = max - min || 1;
  const step = width / (data.length - 1 || 1);
  const pts = data.map((v, i) => [i*step, height - ((v-min)/range)*(height-4) - 2]);
  const path = pts.map((p,i)=> (i?'L':'M')+p[0].toFixed(1)+','+p[1].toFixed(1)).join(' ');
  return <svg width={width} height={height} style={{overflow:'visible'}}>
    {fill && <path d={path + ` L${width},${height} L0,${height} Z`} fill={color} opacity={0.15}/>}
    <path d={path} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>;
}

/* ---------- Log list (shared) ---------- */
function LogFeed({limit=40, theme='A'}) {
  const s = useSim();
  const rows = s.log.slice(0, limit);
  const mono = theme === 'B';
  return <div className="scroll" style={{overflowY:'auto', height:'100%', padding: mono ? '6px 4px' : '4px 2px'}}>
    {rows.map((r, i) => (
      <div key={r.t + '-' + i} style={{
        display: 'grid',
        gridTemplateColumns: '54px 64px 1fr',
        gap: 10,
        padding: mono ? '2px 10px' : '5px 10px',
        fontFamily: mono ? "'JetBrains Mono', monospace" : 'inherit',
        fontSize: mono ? 11.5 : 12,
        lineHeight: 1.5,
        borderBottom: mono ? '0' : '1px solid var(--border)',
        opacity: i > 18 ? 0.5 : 1,
      }}>
        <span style={{color: 'var(--text-dim)'}} className="mono">{new Date(r.t).toTimeString().slice(0,8)}</span>
        <span className={`layer-badge layer-${r.tag || 'system'}`} style={{alignSelf:'center', justifySelf:'start'}}>{r.tag || 'sys'}</span>
        <span className={`log-${r.level}`}>{r.text}</span>
      </div>
    ))}
  </div>;
}
