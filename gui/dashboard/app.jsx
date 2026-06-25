// App root — extracted from the inline <script type="text/babel"> so it can be
// pre-transpiled by tools/build_dashboard.mjs (no in-browser Babel). Depends on
// globals from shared.jsx / direction_b.jsx / direction_b_pages.jsx.
function App() {
  const [tweaksOn, setTweaksOn] = React.useState(false);
  const s = useSim();

  // Apply initial TWEAKS.running
  const bootedRunning = React.useRef(false);
  React.useEffect(() => {
    if (!bootedRunning.current) {
      bootedRunning.current = true;
      if (window.TWEAKS.running) window.PARSim.setRunning(true);
    }
  }, []);

  // Tweaks protocol
  React.useEffect(() => {
    function onMsg(e) {
      if (!e.data) return;
      if (e.data.type === '__activate_edit_mode') setTweaksOn(true);
      if (e.data.type === '__deactivate_edit_mode') setTweaksOn(false);
    }
    window.addEventListener('message', onMsg);
    window.parent.postMessage({type:'__edit_mode_available'}, '*');
    return () => window.removeEventListener('message', onMsg);
  }, []);

  function setRunningPersist(v) {
    window.PARSim.setRunning(v);
    window.parent.postMessage({type:'__edit_mode_set_keys', edits: {running: v}}, '*');
  }

  return (
    <>
      <div className="dash-frame">
        <DirectionB/>
      </div>

      {tweaksOn && (
        <div className="tweaks-panel" data-dir="B">
          <h4>Tweaks</h4>
          <div className="tweaks-row">
            <span>Bot running</span>
            <div className={`toggle ${s.running ? 'on' : ''}`} onClick={()=>setRunningPersist(!s.running)}/>
          </div>
          <div className="tweaks-row">
            <span style={{fontSize: 11, color:'#999'}}>Reset queue</span>
            <button className="btn" style={{height: 24, padding:'0 8px', fontSize: 11}} onClick={()=>window.PARSim.reset()}>Reset</button>
          </div>
        </div>
      )}
    </>
  );
}
ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
