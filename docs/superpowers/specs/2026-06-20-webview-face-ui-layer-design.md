# Daimon "Face" — Webview UI Layer Design

**Date:** 2026-06-20
**Status:** Approved (brainstorming) — ready for implementation plan
**Author:** Ben + Claude (Opus 4.8)

## Problem

Daimon's current UI is functional but basic: a native macOS `NSMenu` dropdown (from `tray/menu_model.py`), a Qt overlay canvas, and a setup window. The Claude Design (CD) project (`claude.ai/design` project `03dbace4-8af6-4625-996f-5bb507cac396`) delivered a lush, production-grade UI — a glassy menu panel, an organic risk-meter, animated toggles, the new Duo brand — as real HTML/CSS/React. Re-authoring that in QML would mean re-translating every pixel and fighting `backdrop-filter` (absent in QML). The goal: a **truly seductive end-to-end UX** that adopts the CD work with maximum fidelity and minimum re-implementation, while the CD design **adapts to functional reality** (not the reverse).

## Approach (chosen)

A **webview UI layer** — "the face" — that renders the CD HTML/CSS/JS in **system webviews** (WKWebView on macOS, WebView2 on Windows) via **pywebview** (light, Python-native, system webview — NOT QtWebEngine). The web layer is **purely presentational**: it shows tray/permission/ceiling/client state and routes user intent back to the organ. **All authority, perception, secret redaction, and the L0–L4 Hands ceiling stay enforced in the organ** — the webview never sees a secret and cannot raise the ceiling.

Rejected alternatives:
- **QML (Qt Quick) native** — re-implements all CD CSS, fidelity drift, still needs native vibrancy plumbing, designers can't ship directly.
- **Hybrid (native menu + web face/onboarding)** — two UI techs, heterogeneous feel.

## Architecture

New OS-agnostic package **`src/daimon/face/`** hosting three pywebview windows, each loading a **local** bundled HTML entry (no remote; CSP `default-src 'self'`):

| Window | Role | Window traits |
|---|---|---|
| `panel` | Menu-bar dropdown (replaces `NSMenu`) | frameless, vibrancy, anchored under the `NSStatusItem` glyph, dismiss-on-blur |
| `overlay` | On-screen companion "face" | frameless, transparent, **screen-capture-excluded**, always-on-top, click-through except interactive zones, per-display |
| `onboarding` | First-run window | frameless window |

The native `NSStatusItem` keeps the menu-bar **icon**; clicking it opens the pywebview `panel`. The native `NSMenu` is retained as an accessibility/fallback path.

### Components & boundaries

- **`face/host.py`** — owns the pywebview window lifecycle (create/show/hide/anchor/dismiss) per surface. Depends on the platform adapters for anchor/vibrancy/exclusion.
- **`face/bridge.py`** — the single typed JS↔Python API exposed via pywebview `js_api`:
  - **JS→Py:** `invoke(action_id, args) -> dict` (routes through the **same action router** the `NSMenu` uses today), `get_state() -> dict` (serialized non-secret view).
  - **Py→JS:** `push_state(json)` (organ pushes new state → JS re-renders), via `window.evaluate_js`.
  - The bridge is an **allowlist**: only known `action_id`s, only non-secret serialized state. It cannot invoke perception/Hands directly and cannot raise the ceiling.
- **`face/view_model.py`** — pure serializer: `TrayState` (`tray/state.py`) + `menu_model` semantics → a JSON view contract (permissions+grant state, clients+tints+registered, ceiling L0–L4 with consent state, overlay on/off, watch status). Unit-tested like `menu_model`. `menu_model.py` is unchanged and remains the native fallback.
- **`face/platform/`** — per-OS adapters (matches the existing `backends/` pattern): `anchor_under_statusitem()`, `apply_vibrancy()` (NSVisualEffectView / acrylic-Mica), `exclude_from_capture()` (NSWindowSharingNone / `WDA_EXCLUDEFROMCAPTURE`).
- **`face/web/`** — the production web bundle (see below).

### Data flow

```
organ state change ──> view_model.serialize() ──> bridge.push_state(json) ──> JS re-render
user clicks control ──> JS bridge.invoke(action_id) ──> same action router as NSMenu ──> organ acts ──> state change ──> (loop)
```

## The web bundle (CD → production)

The CD files are a **playground** (React via Babel CDN + a tweaks panel). Production needs an **offline, no-CDN, locked-track** bundle.

- **`face/web/src/`** — the CD components, de-playgrounded: the Duo marks (`daimon-icons`), the panel (`daimon-menu`), plus new `overlay-face` and `onboarding` components. The chosen brand track is **hardcoded** (Presence Purple `#B66CFF`, Companion Amber `#E8B23A`, indigo tile, `beside` organic). The tweaks/playground are removed. A `bridge.js` client replaces the mock `useState` data with real state from `get_state()` / `push_state`.
- **`build/make_face.py`** (esbuild or equivalent) compiles `face/web/src` → **`face/web/dist/`** static, offline, CSP-safe, vendored React (no CDN). This is the artifact the webviews load.
- CD remains the **design source**, synced via the `claude_design` DesignSync tool. A change in CD → re-sync → rebuild `face/web/dist`.

## Functional-reality corrections (design adapts to reality)

The CD mock must bend to Daimon's real model:

1. **Hands ceiling.** The mock's `Observe / Assist / Act / Control` names are **wrong**. The real ladder is **L0 READ · L1 NONDESTRUCTIVE · L2 INPUT · L3 VALIDATION** (settable from the panel) · **L4 AUTONOMOUS = consent-gated**. L4 is **not a slider stop**: it is reached only via a separate "engage L4" affordance that triggers the native disclaimer dialog + immutable ledger engage/disengage (mirrors today's tray/CLI consent). The risk-meter encodes the real five-rung semantics and renders L4 as a distinct, consent-guarded state.
2. **Permissions.** Real grant state (Screen Recording, Accessibility); clicking a not-granted row deep-links to the correct System Settings pane; a denied-permission walkthrough state exists.
3. **AI Clients.** Real `registered` toggles + the one-click `install_all` ("Register Daimon into all detected").
4. **Overlay toggle** reflects the real overlay on/off.

## §7 decision — overlay strategy (chosen: **wrap**)

The on-screen overlay is currently driven by the MCP `overlay_*` tools (highlight / banner / spotlight / cursor) via a Qt canvas + TCP transport, with capture-exclusion. The webview overlay **wraps** this: the existing `overlay_*` draw API and its transport **keep working and keep rendering**; the web "face" is a companion presentation layer composited with them, and the overlay window preserves **screen-capture-exclusion**. The MCP overlay tool contract does not change. (Rejected: deferring the overlay to a later phase — Ben wants all three surfaces now.)

## Security & isolation (invariants)

- Webview loads **only** local bundled assets; CSP `default-src 'self'`; no remote origins; no node/file integration beyond the typed bridge.
- The bridge exposes a small **typed allowlist**: invoke known `action_id`s, read serialized **non-secret** state. The web layer never receives secrets or perception content.
- Perception, secret redaction, and the L0–L4 Hands ceiling stay **100% enforced in the organ**. The bridge **cannot raise the ceiling** — L4 still requires the native consent dialog + ledger.
- The `overlay` window stays **screen-capture-excluded** (verified per platform).

## Cross-platform

- pywebview backends: **WKWebView** (macOS, system, free), **WebView2** (Windows). 
- Vibrancy: **NSVisualEffectView** (macOS) / **acrylic-Mica** (Windows).
- Anchor: `NSStatusItem` button frame (macOS) / tray icon geometry (Windows).
- All per-OS bits live behind `face/platform/` adapters; the `face/host.py` + `bridge.py` + `view_model.py` core is OS-agnostic and `Fake*`-testable.

## Testing

- `view_model.serialize()` — pure, unit-tested (golden JSON for representative `TrayState`s, incl. each ceiling rung + L4 consent state).
- `bridge.invoke()` routing — unit-tested: each `action_id` reaches the same router the NSMenu uses; unknown ids rejected; cannot raise ceiling.
- Web bundle — smoke test: `face/web/dist` exists after `make_face.py`, CSP header present, **no remote URLs** in the bundle (grep gate).
- Native windowing (vibrancy / anchor / capture-exclusion / dismiss-on-blur) — **manual real-Mac/Win validation** (not headless); capture-exclusion verified by screenshotting the desktop and confirming the overlay is absent.

## Relationship to AXE 7 (release timing)

This is a **large new subsystem**. It should **not block the 0.0.10 release**. The new **brand** (icon/glyph) already shipped on the existing native tray (commits `8c4f625`, `0cc926b`) and rides AXE 7's build. Recommended: cut **0.0.10** with the native tray + new brand; land the webview "face" as a follow-on (target **0.1.0**). The implementation plan phases the three surfaces (shared host/bridge/bundle infra first, then panel, overlay-wrap, onboarding).

## Out of scope (YAGNI)

- Replacing the MCP `overlay_*` draw engine (the webview overlay wraps it; the engine is untouched).
- A live-tunable tweaks panel in production (the track is locked; tuning stays in the CD project).
- Linux UI (GTK WebKit) — deferred; the architecture leaves room.
- Re-theming perception/secret internals — unaffected; the face is presentational.
