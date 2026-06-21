// overlay/index.jsx — the on-screen companion "face". A screen-wide transparent,
// click-through canvas; for now it renders an organic, breathing presence in the
// corner (the daemon, alongside you). Future: the AI draws here — a projected
// whiteboard to explain/show things — so this is a full-screen canvas by design.
import React from "react";
import { createRoot } from "react-dom/client";
import { DuoMark } from "../lib/marks.jsx";

function Companion() {
  return (
    <div style={{ position: "fixed", right: 30, bottom: 30, width: 96, height: 96,
      display: "grid", placeItems: "center", pointerEvents: "none" }}>
      {/* soft breathing aura */}
      <div style={{ position: "absolute", inset: -24, borderRadius: "50%",
        background: "radial-gradient(circle, rgba(182,108,255,0.45), rgba(232,178,58,0.12) 55%, transparent 72%)",
        animation: "faceBreathe 4.2s ease-in-out infinite" }} />
      {/* floating frosted tile carrying the Duo mark */}
      <div style={{ position: "relative", width: 66, height: 66, borderRadius: 22,
        background: "linear-gradient(160deg,#1e2660,#0b0f24)",
        boxShadow: "0 14px 34px -10px rgba(8,10,16,.65), inset 0 0.5px 0 rgba(255,255,255,.16)",
        display: "grid", placeItems: "center",
        animation: "faceFloat 5.6s ease-in-out infinite" }}>
        <DuoMark size={42} />
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<Companion />);
