// GENERATED from app.jsx by tools/build_dashboard.mjs — do not edit; edit the .jsx and rebuild.
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
    window.parent.postMessage({
      type: '__edit_mode_available'
    }, '*');
    return () => window.removeEventListener('message', onMsg);
  }, []);
  function setRunningPersist(v) {
    window.PARSim.setRunning(v);
    window.parent.postMessage({
      type: '__edit_mode_set_keys',
      edits: {
        running: v
      }
    }, '*');
  }
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "dash-frame"
  }, /*#__PURE__*/React.createElement(DirectionB, null)), tweaksOn && /*#__PURE__*/React.createElement("div", {
    className: "tweaks-panel",
    "data-dir": "B"
  }, /*#__PURE__*/React.createElement("h4", null, "Tweaks"), /*#__PURE__*/React.createElement("div", {
    className: "tweaks-row"
  }, /*#__PURE__*/React.createElement("span", null, "Bot running"), /*#__PURE__*/React.createElement("div", {
    className: `toggle ${s.running ? 'on' : ''}`,
    onClick: () => setRunningPersist(!s.running)
  })), /*#__PURE__*/React.createElement("div", {
    className: "tweaks-row"
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 11,
      color: '#999'
    }
  }, "Reset queue"), /*#__PURE__*/React.createElement("button", {
    className: "btn",
    style: {
      height: 24,
      padding: '0 8px',
      fontSize: 11
    },
    onClick: () => window.PARSim.reset()
  }, "Reset"))));
}
ReactDOM.createRoot(document.getElementById('root')).render(/*#__PURE__*/React.createElement(App, null));