// panel/index.jsx — menu-bar panel entry. Mounts the Panel, pulls initial state
// from the bridge, re-renders on Python-pushed state, and refreshes after each
// action so the UI reflects the organ's truth (never optimistic local state).
import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Panel } from "../lib/menu.jsx";
import { bridge } from "../bridge.js";

function App() {
  const [state, setState] = useState(null);

  async function refresh() {
    if (window.pywebview && window.pywebview.api) setState(await bridge.getState());
  }

  useEffect(() => {
    refresh();
    bridge.onState((s) => setState(s));
    // pywebview injects window.pywebview.api asynchronously; it fires
    // 'pywebviewready' once the api is live — refresh then (robust vs a timeout).
    window.addEventListener("pywebviewready", refresh);
    return () => window.removeEventListener("pywebviewready", refresh);
  }, []);

  // Fit the window to the rendered content (any client count) — measure after paint.
  useEffect(() => {
    if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.resize_to) return;
    requestAnimationFrame(() => {
      const h = document.getElementById("root").scrollHeight;
      window.pywebview.api.resize_to(340, h);
    });
  });

  async function invoke(actionId, args) {
    await bridge.invoke(actionId, args);
    await refresh();
  }

  // Small inset so the card's rounded corners + drop shadow float clear of the
  // transparent window edge.
  const shell = (child) => <div style={{ padding: 9 }}>{child}</div>;
  if (!state) {
    return shell(
      <div style={{ padding: 20, fontFamily: "-apple-system, sans-serif", color: "#B66CFF",
        fontSize: 13, display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#B66CFF",
          boxShadow: "0 0 8px #B66CFF", animation: "daimonPulse 1.2s ease-in-out infinite" }} />
        Daimon — connecting…
      </div>
    );
  }
  return shell(<Panel state={state} invoke={invoke} />);
}

createRoot(document.getElementById("root")).render(<App />);
