# Daimon

A local **sensory organ** for AI clients on macOS.

Daimon gives any AI — Claude CLI, a desktop AI app, anything that speaks
[MCP](https://modelcontextprotocol.io) — a perception of your screen. It is an
*organ*, not a driver:

- **Pull, not push.** Daimon owns no loop and calls no AI. The AI client
  connects over MCP and pulls a sense whenever it wants.
- **Agnostic by construction.** One standard transport (MCP) → no per-AI
  adapter. Claude is the most capable client today; Daimon plays fair with the
  rest.
- **Perception ≠ action, by default.** The senses only report. Acting is a
  separate organ ("the hands") under a ceiling Daimon enforces itself — off (L0)
  until a human opts in. See *The hands* below.
- **Secrets filter from day one.** Excluded apps/windows/regions are removed
  *before* any sense serves data.

## The senses

| Sense | Mode | Mechanism | Status |
|-------|------|-----------|--------|
| **Vue** | snapshot | screen capture (pixels) | implemented |
| **Touché passif** | snapshot | full accessibility tree | stub |
| **Touché actif** | probe | a11y element under a point/region | stub |

Daimon supplies pixels and structure only — it does **no** vision/OCR itself.
The client looks with its own eyes. That is what keeps it agnostic.

**Bounded by default (cost control):** `touche_tree` accepts `max_depth`,
`root={x,y}` (subtree under a point), `roles=[...]`, `prune_empty`, `summary=true`
(one line per node), and `window={pid|bundle|title}` to target a specific app
instead of the frontmost. `vue_snapshot` accepts `region={x,y,width,height}` and
defaults to `max_width=720` (pass a larger value for fine detail).

## The hands (motor organ)

Daimon can act under a ceiling it enforces itself (default **L0**, hands off):

| Level | Scope | Gate |
|-------|-------|------|
| L0 READ | nothing | — |
| L1 NONDESTRUCTIVE | scroll, focus, navigate | none |
| L2 INPUT | click, type, drag | none, unless the target is a point of no return |
| L3 VALIDATION | engaging buttons | human confirmation on any non-return |
| L4 AUTONOMOUS | full autonomy | none — everything traced |

- Tools: `main_navigate`, `main_click` (`button=left|right|middle`, `count=1|2`,
  `modifiers`), `main_key` (discrete key / chord, distinct from `main_type`),
  `main_hover`, `main_press`, `main_type`, `main_activate` (bring an app
  frontmost). Low-level press-and-hold primitives are planned (gated to L4).
- Points of no return (send/delete/pay/…) are classified (AI declares, Daimon
  verifies) and gated by a **native macOS dialog**. Timeout = deny.
- **L4** is engaged only by a human typing a phrase out-of-band:
  `python -m daimon.motor.control engage` (and `disengage`). The consent is
  recorded in an append-only, hash-chained ledger under `logs/`. `no-log = no-act`.
- Set the ceiling in `config/motor.yaml` (copy `config/motor.example.yaml`).
- Kill the process at any time to stop everything — the physical override always wins.
- **Acts on the *observed* target.** Before acting, Daimon re-probes the real
  element under the coordinates (the AI's role/label are advisory). A lying
  agent cannot dodge the gate by mislabelling a button; an unverifiable target
  gates below L4 and is refused under L4 (no blind autonomous action).
- **Secret content never leaves.** Secret-role fields (`AXSecureTextField`) and
  declared secret apps are value-blanked in Touché and blacked out in Vue.
- **Region-aware refusal.** Actions whose target falls in an excluded screen
  region are refused, even under L4.
- **Durable consent.** The L4 consent ledger is `flock`-guarded and hash-chained;
  the active ceiling requires the state file *and* the ledger tail to agree, so a
  forged state file cannot silently escalate to L4.
- **Held-input primitives** (`main_mouse_down/up`, `main_key_down/up`) are L4-only
  and auto-released by a watchdog if an `up` never arrives.

## The face (overlay)

The third organ — *show*. A premium, click-through overlay makes the agent
legible: it highlights the element being targeted, ripples where it clicks, and
**emphasises the exact element you confirm at the gate** (a security win, not
just polish).

- Runs as a separate helper process: `python -m daimon.overlay.app`. The MCP
  server drives it over a local socket; it is **never on an action's critical
  path** (if it's absent or fails, actions proceed unchanged).
- **Click-through** (never intercepts input) and **capture-invisible**
  (`anti_feedback` keeps it out of `vue_snapshot`, so Daimon never films itself).
- **Secret-safe**: labels are redacted the same way the senses are — a secret
  field shows `🔒 protégé`, never its value.
- Auto-shows what the motor does; the agent can also drive it explicitly with
  `overlay_highlight`, `overlay_spotlight`, `overlay_cursor`, `overlay_banner`,
  `overlay_clear`.
- Enable via `config/overlay.yaml` (copy `config/overlay.example.yaml`); off by default.

## The menu bar (resident control surface)

Double-clicking `Daimon.app` adds a **"δ" icon to the menu bar** — no Dock
entry, no window.  The dropdown shows at a glance:

- macOS permission status (Screen Recording, Accessibility) and which AI clients
  are registered.
- **Hands ceiling** — set the motor limit to L0 READ / L1 NONDESTRUCTIVE /
  L2 INPUT / L3 VALIDATION with a single click.  L4 full-autonomy stays
  consent-gated; it can only be engaged via `python -m daimon.motor.control engage`.
- **Show overlay** — toggle the click-through highlight layer on or off.
- **Run setup…** — reopen the onboarding window to re-grant permissions or
  re-register with a new AI client.
- **Open config folder / Open logs** — Finder shortcuts.
- **Quit Daimon** — terminate the tray process.

On the **first launch** (no existing motor or overlay config), the onboarding
window opens automatically so permissions and clients are configured before the
tray settles into the menu bar.

The tray and the MCP servers are **separate processes**: they communicate via the
config files (`config/motor.yaml`, `config/overlay.yaml`) that already exist —
no IPC bus required.

## Setup (install + onboarding)

One command gets a new user running — no manual config editing:

```bash
daimon setup       # register Daimon into detected AI clients, then guide macOS permissions
```

- `daimon install [--all]` / `daimon uninstall` — register/remove Daimon in each
  detected client's MCP config (Claude Code, Claude Desktop, Cursor, Windsurf).
  Idempotent, reversible, and every write is backed up; a malformed client config
  is refused, never overwritten.
- `daimon status` — show where Daimon is registered.
- `daimon onboard` — guide the macOS permission grants (Screen Recording,
  Accessibility) with live verification. GUI version: `python -m daimon.onboard --gui`.
- `daimon` with no arguments is still the MCP server (what clients launch).

## Layout

```
src/daimon/
  server.py          # FastMCP server, registers the senses (stdio)
  config.py          # loads exclusion zones
  exclusions.py      # the secrets filter — runs before any sense serves
  senses/
    base.py          # Sense contract
    vue.py           # Vue  → tool: vue_snapshot
    touche.py        # Touché → tools: touche_tree, touche_probe (stubs)
  capture/
    screen.py        # macOS Quartz screen capture
config/
  exclusions.example.yaml   # copy to exclusions.yaml (git-ignored) and fill in
tests/
  test_exclusions.py        # secrets filter, runs without macOS deps
```

## Run

```bash
pip install -e ".[dev]"
python -m daimon          # starts the MCP server on stdio
```

Grant the host process **Screen Recording** permission (System Settings →
Privacy & Security) for Vue, and later **Accessibility** for Touché.

Register with an MCP client (example, Claude Code):

```json
{
  "mcpServers": {
    "daimon": { "command": "python", "args": ["-m", "daimon"] }
  }
}
```

## Status

Scoping locked, Vue brick scaffolded. Touché is stubbed and lands next.
Reference: [Omi](https://github.com/BasedHardware/omi) — perception/action
decoupled, macOS 14+, Accessibility API.
