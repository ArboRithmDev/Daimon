// menu.jsx — the menu-bar panel, de-playgrounded from the Claude Design mock and
// bound to the organ via the bridge. Functional reality wins over the mock: the
// Hands ceiling is the REAL L0-L4 ladder, and L4 AUTONOMOUS is consent-gated
// (a distinct affordance, never a meter stop).
import React, { useState } from "react";
import { DuoGlyph } from "./marks.jsx";

// Real Hands ceiling. L0-L3 are settable from the meter; L4 is consent-gated.
export const RUNGS = [
  { code: "L0", key: "READ", name: "Read", color: "#6E8AB0", desc: "Read-only. Sees the screen, never acts." },
  { code: "L1", key: "NONDESTRUCTIVE", name: "Nondestructive", color: "#4FA38C", desc: "Reversible actions — focus, window, scroll." },
  { code: "L2", key: "INPUT", name: "Input", color: "#C39A4E", desc: "Clicks & types in the focused app." },
  { code: "L3", key: "VALIDATION", name: "Validation", color: "#C56B5A", desc: "Acts, but you validate each commit." },
];
const L4 = { code: "L4", key: "AUTONOMOUS", name: "Autonomy", color: "#C7567E", desc: "Full autonomy — every action runs. Consent-gated." };

const SF = '-apple-system, "SF Pro Text", BlinkMacSystemFont, "Helvetica Neue", sans-serif';

const C = {
  bg: "rgba(26,29,36,0.74)", border: "rgba(255,255,255,0.10)", ring: "rgba(255,255,255,0.06)",
  text: "#ECEEF2", sub: "rgba(236,238,242,0.5)", faint: "rgba(236,238,242,0.34)",
  sep: "rgba(255,255,255,0.08)", hover: "rgba(255,255,255,0.08)", track: "rgba(255,255,255,0.16)",
  segBg: "rgba(255,255,255,0.07)", scrim: "rgba(22,25,32,0.66)", chipBg: "rgba(255,255,255,0.07)",
};

function Toggle({ on, onClick, accent }) {
  return (
    <button onClick={onClick} aria-pressed={on} style={{
      width: 38, height: 23, borderRadius: 12, border: "none", cursor: "pointer", padding: 0,
      position: "relative", flex: "0 0 auto", background: on ? accent : C.track, transition: "background .18s",
      boxShadow: on ? `0 0 0 0.5px ${accent}, 0 1px 6px ${accent}66` : "inset 0 0 0 0.5px rgba(0,0,0,.12)" }}>
      <span style={{ position: "absolute", top: 2, left: on ? 17 : 2, width: 19, height: 19, borderRadius: "50%",
        background: "#fff", transition: "left .2s cubic-bezier(.3,1.4,.5,1)", boxShadow: "0 1px 3px rgba(0,0,0,.35)" }} />
    </button>
  );
}

function StatusChip({ ok, accent, onClick }) {
  return (
    <span onClick={onClick} style={{ cursor: onClick ? "pointer" : "default", display: "inline-flex", alignItems: "center",
      gap: 5, fontSize: 11.5, fontWeight: 590, padding: "3px 9px 3px 7px", borderRadius: 999, whiteSpace: "nowrap",
      color: ok ? accent : "#D98A6A", background: ok ? `${accent}1f` : "rgba(217,138,106,0.16)" }}>
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: ok ? accent : "#D98A6A",
        boxShadow: ok ? `0 0 6px ${accent}` : "none" }} />
      {ok ? "Granted" : "Grant…"}
    </span>
  );
}

function Row({ children, onClick }) {
  const [h, setH] = useState(false);
  return (
    <div onClick={onClick} onMouseEnter={() => setH(true)} onMouseLeave={() => setH(false)}
      style={{ display: "flex", alignItems: "center", gap: 10, padding: "7px 10px", margin: "0 6px",
        borderRadius: 9, background: h ? C.hover : "transparent", transition: "background .12s", cursor: onClick ? "pointer" : "default" }}>
      {children}
    </div>
  );
}

const Sep = () => <div style={{ height: 1, background: C.sep, margin: "6px 14px" }} />;
const SectionLabel = ({ children }) => (
  <div style={{ padding: "10px 16px 4px", fontSize: 10.5, fontWeight: 680, letterSpacing: "0.07em",
    color: C.faint, textTransform: "uppercase" }}>{children}</div>
);

function CeilingMeter({ currentKey, l4Active, accent, onSet, onEngageL4, onDisengageL4 }) {
  const idx = Math.max(0, RUNGS.findIndex(r => r.key === currentKey));
  const active = l4Active ? L4 : RUNGS[idx];
  const ramp = `linear-gradient(90deg, ${RUNGS.map(r => r.color).join(",")})`;
  const p = l4Active ? 1 : idx / (RUNGS.length - 1);
  return (
    <div style={{ margin: "0 16px" }}>
      <div style={{ position: "relative", height: 12, borderRadius: 999, background: C.segBg, marginTop: 2, opacity: l4Active ? 0.5 : 1 }}>
        <div style={{ position: "absolute", inset: 0, borderRadius: 999, background: ramp, opacity: 0.95 }} />
        <div style={{ position: "absolute", top: 0, bottom: 0, left: `${p * 100}%`, right: 0, background: C.scrim, borderRadius: "0 999px 999px 0" }} />
        {RUNGS.map((r, i) => (
          <button key={r.key} onClick={() => !l4Active && onSet(r.key)} aria-label={r.name}
            style={{ position: "absolute", top: -7, bottom: -7, left: `${(i / (RUNGS.length - 1)) * 100}%`, width: 26,
              transform: "translateX(-50%)", background: "transparent", border: "none", cursor: l4Active ? "default" : "pointer", padding: 0 }} />
        ))}
        <div style={{ position: "absolute", top: "50%", left: `${p * 100}%`, width: 20, height: 20, borderRadius: "50%",
          transform: "translate(-50%,-50%)", background: "#fff", boxShadow: `0 0 0 3px ${active.color}, 0 2px 6px rgba(0,0,0,.35)`, pointerEvents: "none" }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", padding: "8px 0 0" }}>
        {RUNGS.map((r, i) => (
          <button key={r.key} onClick={() => !l4Active && onSet(r.key)} style={{ background: "none", border: "none",
            cursor: l4Active ? "default" : "pointer", fontFamily: SF, fontSize: 11, fontWeight: (!l4Active && i === idx) ? 750 : 560,
            color: (!l4Active && i === idx) ? r.color : C.faint, letterSpacing: ".02em", padding: 0 }}>{r.code}</button>
        ))}
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8, padding: "11px 2px 4px" }}>
        <span style={{ fontSize: 12.5, fontWeight: 650, color: active.color }}>{active.name}</span>
        <span style={{ fontSize: 12, color: C.sub, lineHeight: 1.3 }}>{active.desc}</span>
      </div>
      <Row onClick={l4Active ? onDisengageL4 : onEngageL4}>
        <span style={{ width: 7, height: 7, borderRadius: "50%", background: l4Active ? L4.color : C.faint,
          boxShadow: l4Active ? `0 0 8px ${L4.color}` : "none", flex: "0 0 auto" }} />
        <span style={{ fontSize: 12.5, color: l4Active ? L4.color : C.text }}>
          {l4Active ? "L4 autonomy engaged — disengage" : "Engage L4 autonomy…"}
        </span>
      </Row>
    </div>
  );
}

export function Panel({ state, invoke }) {
  if (!state) return null;
  const accent = state.brand.presence;
  const perms = state.permissions;
  const ceiling = state.ceiling;
  const l4 = ceiling.l4_active;
  const statusColor = l4 ? L4.color : accent;
  // macOS paints a translucent card over native vibrancy; Windows WebView2 has no
  // acrylic behind the page, so it paints an opaque indigo card, not muddy grey.
  const solid = state.brand && state.brand.backdrop === "solid";
  const panelBg = solid ? "linear-gradient(165deg,#222a57 0%,#141a3a 46%,#0b0f24 100%)" : C.bg;
  // Vivid hot frame for L4 (more saturated than the muted dot tone) so engaged
  // autonomy is unmistakable — especially on the opaque Windows card.
  const L4FRAME = "#FF4D7D";
  return (
    <div style={{ width: "100%", fontFamily: SF, color: C.text,
      // Solid (Windows): the card is square and fills the window; DWM rounds the
      // window itself (smooth, native), so the card mustn't add a competing arc.
      // Vibrancy (macOS): the card carries the rounding over the blur backing.
      borderRadius: solid ? 0 : 20, overflow: "hidden",
      background: panelBg,
      // L4 frames the whole panel in the hot autonomy colour so elevated mode is unmistakable.
      border: l4 ? `2px solid ${L4FRAME}` : `0.5px solid ${C.border}`,
      boxShadow: l4
        ? `inset 0 0 0 1px ${L4FRAME}, inset 0 0 18px -4px ${L4FRAME}aa, 0 0 0 1px ${L4FRAME}, 0 0 30px -2px ${L4FRAME}cc, 0 26px 64px -14px rgba(0,0,0,0.72)`
        : `0 0 0 0.5px ${C.ring}, 0 26px 64px -14px rgba(0,0,0,0.72), 0 8px 22px -10px rgba(0,0,0,.4)` }}>
      <div style={{ display: "flex", alignItems: "center", gap: 11, padding: "14px 16px 11px" }}>
        <div style={{ width: 32, height: 32, borderRadius: 16, flex: "0 0 auto", display: "grid", placeItems: "center",
          background: "linear-gradient(160deg,#1e2660,#0b0f24)", boxShadow: "inset 0 0.5px 0 rgba(255,255,255,.14)", color: statusColor }}>
          <DuoGlyph size={23} />
        </div>
        <div style={{ lineHeight: 1.15 }}>
          <div style={{ fontSize: 14.5, fontWeight: 640, letterSpacing: "-0.01em" }}>Daimon</div>
          <div style={{ fontSize: 11.5, color: C.sub }}>Local daemon · v{state.version}</div>
        </div>
        <div style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11.5,
          fontWeight: l4 ? 700 : 560, color: statusColor }}>
          <span style={{ width: 7, height: 7, borderRadius: "50%", background: statusColor, boxShadow: `0 0 8px ${statusColor}`,
            animation: `daimonPulse ${l4 ? "1.1s" : "2.4s"} ease-in-out infinite` }} />
          {l4 ? "L4 · Autonomous" : "Ready"}
        </div>
      </div>
      {/* Status bar: hot + animated when L4 is engaged. */}
      <div style={{ height: l4 ? 3 : 2.5, margin: "0 14px 2px", borderRadius: 2, background: statusColor,
        opacity: 0.9, boxShadow: l4 ? `0 0 8px ${L4.color}` : "none" }} />

      <Sep />
      <SectionLabel>Permissions</SectionLabel>
      <Row onClick={() => invoke("run_setup")}>
        <span style={{ fontSize: 13 }}>Screen Recording</span>
        <span style={{ marginLeft: "auto" }}><StatusChip ok={perms.screen_recording} accent={accent} /></span>
      </Row>
      <Row onClick={() => invoke("run_setup")}>
        <span style={{ fontSize: 13 }}>Accessibility</span>
        <span style={{ marginLeft: "auto" }}><StatusChip ok={perms.accessibility} accent={accent} /></span>
      </Row>

      <Sep />
      <SectionLabel>AI Clients{state.clients.length ? ` · ${state.clients.filter(c => c.registered).length}/${state.clients.length}` : ""}</SectionLabel>
      {state.clients.length === 0 && (
        <div style={{ padding: "2px 16px 6px", fontSize: 12, color: C.faint }}>No AI clients detected</div>
      )}
      {/* Compact, scrollable: caps the panel height however long the list grows. */}
      <div className="daimon-scroll" style={{ maxHeight: 198, overflowY: "auto", margin: "0 2px" }}>
        {state.clients.map(cl => (
          <div key={cl.name} style={{ display: "flex", alignItems: "center", gap: 10, padding: "4px 12px", margin: "0 4px" }}>
            <span style={{ fontSize: 12.5, color: cl.registered ? C.text : C.sub }}>{cl.name}</span>
            <span style={{ marginLeft: "auto" }}>
              <Toggle on={cl.registered} accent={accent} onClick={() => invoke(`toggle_client:${cl.name}`)} />
            </span>
          </div>
        ))}
      </div>

      <Sep />
      <SectionLabel>Hands ceiling</SectionLabel>
      <CeilingMeter currentKey={ceiling.current} l4Active={ceiling.l4_active} accent={accent}
        onSet={(k) => invoke(`set_ceiling:${k}`)} onEngageL4={() => invoke("engage_l4")} onDisengageL4={() => invoke("disengage_l4")} />

      <Sep />
      <Row onClick={() => invoke("toggle_overlay")}>
        <div style={{ lineHeight: 1.2 }}>
          <div style={{ fontSize: 13 }}>On-screen Overlay</div>
          <div style={{ fontSize: 11, color: C.sub }}>The face — your assistant on screen</div>
        </div>
        <span style={{ marginLeft: "auto" }}><Toggle on={state.overlay_on} accent={accent} onClick={() => invoke("toggle_overlay")} /></span>
      </Row>

      <Sep />
      <Row onClick={() => invoke("run_setup")}><span style={{ fontSize: 13 }}>Run Setup…</span></Row>
      <Row onClick={() => invoke("open_logs")}><span style={{ fontSize: 13 }}>Activity Log</span></Row>
      <Row onClick={() => invoke("quit")}><span style={{ fontSize: 13 }}>Quit Daimon</span></Row>
      <div style={{ height: 6 }} />
    </div>
  );
}
