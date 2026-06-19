# Architecture

Daimon is a local macOS daemon that exposes three *organs* — perception, motor,
and an overlay — to any MCP client, under a safety ceiling Daimon enforces
itself. This document maps how the pieces fit, the process model, and where the
security guarantees actually live.

The guiding principle: **the AI is never trusted.** Every limit is enforced in
Daimon's own code path, on observed facts, not on what the AI declares.

---

## The organ metaphor

Daimon is an *organ*, not a driver — **pull, not push**. It owns no loop and
calls no AI. The client connects over MCP and pulls a sense or moves a hand when
it wants. This is what makes Daimon agnostic: any MCP‑capable client plugs in
with no per‑AI adapter, and Daimon can be audited in isolation because it has no
autonomy of its own.

```
        ┌────────────────────────── your Mac ──────────────────────────┐
        │                                                               │
 AI ───►│  MCP (stdio)  ►  Daimon serve  ►  ┌── 👁 senses  (read‑only)  │
client  │                                   ├── ✋ motor   (ceiling)    │──► screen / OS
        │                                   └── 🪞 overlay (feedback)   │
        │                                            ▲                  │
        │                          menu‑bar tray ────┘  (ceiling, state)│
        └───────────────────────────────────────────────────────────────┘
```

---

## Process model

One signed `.app` ships **one dispatching binary** (`daimon/__main__.py`) that
becomes different things depending on how it's invoked. PyInstaller does not
cleanly support several executables in one bundle, so argv dispatch is the
mechanism.

| Process | How it starts | Lifetime | Role |
|---------|---------------|----------|------|
| **Tray** | you launch `Daimon.app` (no args) | resident | Menu‑bar UI: set the ceiling, toggle overlay, register clients, open config/logs. The one persistent "main". |
| **`serve`** | your AI client spawns `Daimon serve` over MCP stdio | one **per client connection**, dies on stdin EOF | The MCP server: registers the sense/motor/overlay tools and handles calls. |
| **`overlay`** | auto‑spawned on demand by `serve` (`Daimon overlay`) | **singleton**, reaped when idle | The on‑screen face. One shared process for all clients. |

Several `serve` processes is **normal**, not a leak: MCP stdio is one server
process per client connection, and the client owns that lifetime. Only the
overlay must be unique.

> Why a subcommand and not `-m`? In the frozen app `sys.executable` is the
> Daimon binary, not python, so `Daimon -m some.module` would be misrouted to
> the default (tray) branch. Helper processes therefore address explicit
> dispatcher subcommands (`serve`, `overlay`). See `daimon/__main__.py`.

### Overlay singleton & lifecycle

The overlay must be exactly one process, shared by every client, and must never
outlive its drivers:

- **Singleton** via a kernel `flock` on `…/Daimon/overlay.lock`
  (`overlay/launcher.py:bind_singleton`). Of N racing spawns the kernel grants
  the lock to exactly one; losers exit before opening a window. No bind/unlink
  race can produce a twin.
- **Env‑independent socket** at `~/Library/Application Support/Daimon/overlay.sock`
  (the per‑user data dir, *not* `$TMPDIR`), so every process — however launched —
  agrees on one path.
- **Idle‑reaped**: the server reference‑counts live client connections and
  terminates the process when the last one drops (after a short grace). On‑screen
  marks also self‑expire, so a missed `overlay_clear` can't leave a ghost.

---

## Data flow

### Perception (pull)

```
client → vue_snapshot / touche_tree / touche_probe
       → Sense  → ExclusionFilter (blank secrets)  → capture (Quartz / AXUIElement)
       → bounded result (region, depth, roles, summary)  → client
```

Daimon returns pixels and structure only — no vision, no OCR. Secret‑role fields
and declared apps are redacted **before** anything is serialized
(`exclusions.py`, applied inside the senses).

**Scoped exception — `vue_find` locator (AXE 3).** "No vision/OCR" is a principle
about *interpretation* (turning pixels into meaning/decisions). `vue_find` runs
on‑device OCR to answer one narrow question — *where is the label you named?* — and
returns a **position**, not a comprehension: localisation ≠ interprétation. It is
the Vue‑only fallback for surfaces with no accessibility tree (WinDev, old Win32,
custom‑drawn, Electron). It stays strictly local‑first / no network (Apple Vision
on macOS, a Win32/Tesseract twin on Windows) and the matcher is a dumb string
comparator, never an NLP model, so the locator stays on the localisation side of
the line. Daimon still does not read the screen *for* you.

### Motor (act → guard → gate → actuate)

Every `main_*` tool builds a `MotorAction` and runs it through the organ
(`motor/organ.py`):

```
MotorAction(intent, declared reversible, target)
   │
   ├─ guard        PolicyGuard         is the action's level ≤ the current ceiling?         (motor/guard.py)
   ├─ re‑probe     MacOSProber         observe the REAL element under the target            (motor/probe.py)
   ├─ classify     reversibility       point of no return? (multilingual verbs + key combos)(motor/reversibility.py)
   ├─ gate         MacOSGate           native confirm dialog on a non‑return; timeout = deny(motor/gate.py)
   ├─ consent      ConsentManager      L4 requires a signed, hash‑chained ledger entry      (motor/consent.py, audit.py)
   ├─ actuate      MacOSActuator       synthesize the CGEvent / AX action                   (motor/actuator.py)
   └─ trace        session ledger      append‑only record of what happened                  (motor/audit.py)
```

The key property: **reversibility is judged on the observed element, not the
AI's label.** A lying agent that calls a Delete button "reversible" still hits
the gate, because Daimon re‑probes and classifies the real target.

`motor/factory.py` wires the real backends from config; `motor/types.py` holds
the pure data classes; `motor/actions.py` maps each tool to its level.

---

## Security enforcement, by file

| Guarantee | Where it lives |
|-----------|----------------|
| Ceiling is enforced, AI can't raise it | `motor/guard.py`, ceiling from `motor/consent.py` |
| Points of no return classified on observed element | `motor/probe.py` + `motor/reversibility.py` |
| Human gate (native dialog, timeout = deny) | `motor/gate.py` |
| L4 needs out‑of‑band phrase; append‑only hash‑chained ledger; `no‑log = no‑act` | `motor/control.py`, `motor/consent.py`, `motor/audit.py` |
| Secrets blanked before serving | `exclusions.py` (in `senses/*` and the overlay presenter) |
| Overlay never on an action's critical path | `overlay/presenter.py` (fire‑and‑forget sink) |

See **[SECURITY.md](SECURITY.md)** for the threat model and reporting.

---

## Permissions & TCC

macOS attaches Screen Recording / Accessibility grants to the **responsible
parent GUI app** — the terminal, IDE, or AI app that launches `Daimon serve` —
**not** to `Daimon.app` or the python binary. So:

- The permission the AI actually uses belongs to *its* host app.
- The `serve` process, running under that host, is the only one that sees the
  true grant status; it records it (`server.py:_record_permission_status`) so the
  onboarding GUI can confirm it.

The onboarding wizard (`setup/`) explains this and guides the grant in the right
context.

---

## Module map

```
src/daimon/
├── __main__.py         argv dispatcher: serve | overlay | setup CLI | --gui | tray
├── server.py           FastMCP server; registers sense/motor/overlay tools
├── config.py           load Config / MotorConfig / OverlayConfig (user data dir)
├── userdata.py         per‑user data dir (~/Library/Application Support/Daimon)
├── exclusions.py       secret‑role / secret‑app redaction
├── applog.py           file logger (windowed app has no stderr)
├── objc_bridge.py      one shared NSObject action target (ObjC class names are global)
│
├── senses/             👁 read‑only perception
│   ├── vue.py            screen capture tools
│   ├── touche.py         accessibility‑tree tools
│   └── base.py           Sense interface
├── capture/            low‑level Quartz / AXUIElement access
│
├── motor/              ✋ the hands, under the ceiling
│   ├── organ.py          act → guard → gate → actuate pipeline
│   ├── guard.py          ceiling enforcement
│   ├── probe.py          observe the real target
│   ├── reversibility.py  point‑of‑no‑return classifier
│   ├── gate.py           native confirmation dialog
│   ├── consent.py        L4 ceiling + state
│   ├── control.py        L4 engage/disengage CLI
│   ├── audit.py          append‑only hash‑chained ledger
│   ├── actuator.py       CGEvent / AX synthesis
│   ├── actions.py        tool → level map
│   ├── factory.py        wire real backends from config
│   └── types.py          pure data classes
│
├── overlay/            🪞 the face (separate singleton process)
│   ├── launcher.py       flock singleton + spawn
│   ├── client.py         fire‑and‑forget Unix‑socket sender
│   ├── presenter.py      motor lifecycle → overlay commands (with redaction)
│   ├── protocol.py       pure command dataclasses ↔ JSON
│   └── app/              the AppKit process: server, scene, window
│
├── setup/              client registration + onboarding
│   ├── clients/          per‑client adapters (JSON / TOML formats)
│   ├── deploy.py         install into all detected clients
│   ├── invocation.py     how clients should launch Daimon
│   ├── cli.py            install | uninstall | status | onboard | setup
│   ├── gui/              first‑run onboarding window
│   └── permissions.py    TCC status probing
│
└── tray/               menu‑bar app
    ├── state.py          gather current state
    ├── menu_model.py     pure, testable menu structure
    └── app/              NSStatusItem wiring
```

The split is deliberate: everything outside `senses/`, `capture/`,
`motor/actuator.py`, `motor/gate.py`, `overlay/app/`, `setup/gui/`, and `tray/app/`
is **pyobjc‑free and unit‑tested without macOS**. The AppKit surfaces are thin
and smoke‑validated. This keeps the security‑critical logic (guard, reversibility,
consent, audit, redaction) portable and exhaustively testable.
