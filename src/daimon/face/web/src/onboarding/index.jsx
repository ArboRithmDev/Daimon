// onboarding/index.jsx — first-run journey: Welcome -> Permissions -> Clients ->
// Done. Bound to the organ via the bridge (real grant state, real client
// registration). Frameless frosted window; "Finish" closes via the bridge.
import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { DuoMark } from "../lib/marks.jsx";
import { bridge } from "../bridge.js";

const SF = '-apple-system, "SF Pro Text", BlinkMacSystemFont, sans-serif';
const ACCENT = "#B66CFF";
const C = { text: "#ECEEF2", sub: "rgba(236,238,242,0.55)", faint: "rgba(236,238,242,0.34)",
  hover: "rgba(255,255,255,0.08)", sep: "rgba(255,255,255,0.09)", chip: "rgba(255,255,255,0.07)" };

function Btn({ children, onClick, kind = "primary", disabled }) {
  const base = { fontFamily: SF, fontSize: 13.5, fontWeight: 600, borderRadius: 10, padding: "9px 16px",
    border: "none", cursor: disabled ? "default" : "pointer", opacity: disabled ? 0.4 : 1, transition: "filter .15s" };
  const styles = {
    primary: { ...base, background: ACCENT, color: "#0b0612", boxShadow: `0 4px 14px -4px ${ACCENT}88` },
    ghost: { ...base, background: "transparent", color: C.sub },
    soft: { ...base, background: C.chip, color: C.text },
  };
  return <button style={styles[kind]} disabled={disabled} onClick={onClick}>{children}</button>;
}

function PermRow({ label, hint, ok, onGrant, onSettings }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 2px" }}>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 14, fontWeight: 560 }}>{label}</div>
        <div style={{ fontSize: 12, color: C.sub, marginTop: 2 }}>{hint}</div>
      </div>
      {ok
        ? <span style={{ fontSize: 12.5, fontWeight: 600, color: ACCENT, display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: ACCENT, boxShadow: `0 0 6px ${ACCENT}` }} /> Granted
          </span>
        : <div style={{ display: "flex", gap: 8 }}>
            <Btn kind="soft" onClick={onSettings}>Settings…</Btn>
            <Btn onClick={onGrant}>Grant</Btn>
          </div>}
    </div>
  );
}

function App() {
  const [state, setState] = useState(null);
  const [step, setStep] = useState(0);

  async function refresh() {
    if (window.pywebview && window.pywebview.api) setState(await bridge.getState());
  }
  useEffect(() => {
    refresh();
    bridge.onState(setState);
    window.addEventListener("pywebviewready", refresh);
    return () => window.removeEventListener("pywebviewready", refresh);
  }, []);
  async function act(id) { await bridge.invoke(id); await refresh(); }

  const perms = state ? state.permissions : { screen_recording: false, accessibility: false };
  const clients = state ? state.clients : [];

  const steps = [
    {
      title: "Meet Daimon",
      body: (
        <div style={{ textAlign: "center", padding: "8px 4px" }}>
          <div style={{ width: 92, height: 92, margin: "6px auto 18px", borderRadius: 28, display: "grid", placeItems: "center",
            background: "linear-gradient(160deg,#1e2660,#0b0f24)", boxShadow: "0 16px 40px -12px rgba(8,10,16,.7), inset 0 0.5px 0 rgba(255,255,255,.16)" }}>
            <DuoMark size={58} />
          </div>
          <div style={{ fontSize: 21, fontWeight: 640, letterSpacing: "-0.02em" }}>A companion for any AI</div>
          <p style={{ fontSize: 13.5, lineHeight: 1.55, color: C.sub, maxWidth: 320, margin: "10px auto 0" }}>
            Daimon gives any AI client <strong style={{ color: C.text }}>eyes</strong> to see your screen and{" "}
            <strong style={{ color: C.text }}>hands</strong> to act — locally, on your terms. Two quick steps to set up.
          </p>
        </div>
      ),
    },
    {
      title: "Permissions",
      body: (
        <div>
          <p style={{ fontSize: 13, color: C.sub, margin: "0 0 8px" }}>Daimon needs these to see and act. Granted locally — nothing leaves your Mac.</p>
          <PermRow label="Screen Recording" hint="Lets Daimon see your screen." ok={perms.screen_recording}
            onGrant={() => act("grant_screen")} onSettings={() => act("settings_screen")} />
          <div style={{ height: 1, background: C.sep }} />
          <PermRow label="Accessibility" hint="Lets Daimon read UI structure and act." ok={perms.accessibility}
            onGrant={() => act("grant_accessibility")} onSettings={() => act("settings_accessibility")} />
        </div>
      ),
    },
    {
      title: "AI Clients",
      body: (
        <div>
          <div style={{ display: "flex", alignItems: "center", marginBottom: 6 }}>
            <p style={{ fontSize: 13, color: C.sub, margin: 0, flex: 1 }}>Register Daimon into your AI tools.</p>
            <Btn kind="soft" onClick={() => act("install_all")}>Register all</Btn>
          </div>
          <div className="daimon-scroll" style={{ maxHeight: 232, overflowY: "auto" }}>
            {clients.length === 0 && <div style={{ fontSize: 12.5, color: C.faint, padding: "8px 0" }}>No AI clients detected.</div>}
            {clients.map(cl => (
              <div key={cl.name} style={{ display: "flex", alignItems: "center", padding: "7px 2px" }}>
                <span style={{ fontSize: 13, flex: 1, color: cl.registered ? C.text : C.sub }}>{cl.name}</span>
                <button onClick={() => act(`toggle_client:${cl.name}`)} aria-pressed={cl.registered}
                  style={{ width: 38, height: 23, borderRadius: 12, border: "none", cursor: "pointer", padding: 0, position: "relative",
                    background: cl.registered ? ACCENT : "rgba(255,255,255,.16)", transition: "background .18s" }}>
                  <span style={{ position: "absolute", top: 2, left: cl.registered ? 17 : 2, width: 19, height: 19, borderRadius: "50%",
                    background: "#fff", transition: "left .2s cubic-bezier(.3,1.4,.5,1)", boxShadow: "0 1px 3px rgba(0,0,0,.35)" }} />
                </button>
              </div>
            ))}
          </div>
        </div>
      ),
    },
    {
      title: "You're set",
      body: (
        <div style={{ textAlign: "center", padding: "14px 4px" }}>
          <div style={{ fontSize: 38, marginBottom: 6 }}>✦</div>
          <div style={{ fontSize: 19, fontWeight: 640 }}>Daimon is ready</div>
          <p style={{ fontSize: 13.5, lineHeight: 1.55, color: C.sub, maxWidth: 320, margin: "10px auto 0" }}>
            Find Daimon in your menu bar anytime to manage permissions, clients, and the Hands ceiling. The Hands stay at a safe level until you raise them.
          </p>
        </div>
      ),
    },
  ];

  const last = step === steps.length - 1;
  return (
    <div style={{ width: "100%", minHeight: "100vh", boxSizing: "border-box", fontFamily: SF, color: C.text,
      borderRadius: 24, overflow: "hidden", background: "rgba(24,27,34,0.72)", padding: "26px 26px 20px",
      display: "flex", flexDirection: "column" }}>
      {/* stepper dots */}
      <div style={{ display: "flex", gap: 6, marginBottom: 18 }}>
        {steps.map((_, i) => (
          <span key={i} style={{ height: 4, flex: 1, borderRadius: 2, background: i <= step ? ACCENT : "rgba(255,255,255,.12)", transition: "background .2s" }} />
        ))}
      </div>
      <h2 style={{ margin: "0 0 14px", fontSize: 13, fontWeight: 700, letterSpacing: ".1em", textTransform: "uppercase", color: C.faint }}>{steps[step].title}</h2>
      <div style={{ flex: 1 }}>{steps[step].body}</div>
      <div style={{ display: "flex", alignItems: "center", marginTop: 18, gap: 10 }}>
        {step > 0 ? <Btn kind="ghost" onClick={() => setStep(step - 1)}>Back</Btn> : <span />}
        <span style={{ flex: 1 }} />
        {last
          ? <Btn onClick={() => bridge.invoke("close_window")}>Finish</Btn>
          : <Btn onClick={() => setStep(step + 1)}>Continue</Btn>}
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
