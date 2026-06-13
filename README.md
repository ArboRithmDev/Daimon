# Daimon

**A local organ that gives any AI eyes, hands, and a face on your Mac.**

Daimon is a local daemon for macOS that lets any MCP-capable AI client — Claude
Code, Claude Desktop, Cursor, Codex, Copilot CLI, Antigravity, and more —
**see your screen, act on it, and show you what it's doing.** It speaks the
standard [Model Context Protocol](https://modelcontextprotocol.io), so it works
with any client and is tied to none.

It is an *organ*, not a driver: **pull, not push.** Daimon owns no loop and
**calls no AI** — the client connects over MCP and pulls a sense or moves a hand
when it wants. Being fully local and open, you can audit exactly what it does
with your screen.

> ⚠️ **Public beta.** Daimon works end-to-end (installed, signed, driving real
> apps) but it is young. Use a sensible ceiling, read the security model below,
> and report issues.

---

## The triad

**👁 Perceive — the senses**

| Sense | What | Tool |
|-------|------|------|
| **Vue** | screen capture (pixels) | `vue_snapshot`, `vue_displays` |
| **Touché passif** | accessibility tree of a window | `touche_tree` |
| **Touché actif** | the element under a point | `touche_probe` |

Daimon supplies pixels and structure only — it does **no** vision/OCR itself; the
client looks with its own eyes. Bounded by default for token cost (`max_depth`,
`root`, `roles`, `summary`, `region`, …).

**✋ Act — the hands**

Acting is a separate organ under a ceiling Daimon enforces itself (default
**L0**, hands off):

| Level | Scope | Gate |
|-------|-------|------|
| L0 READ | nothing | — |
| L1 NONDESTRUCTIVE | scroll, focus, navigate, hover | none |
| L2 INPUT | click (left/right/middle, double, modifiers), type, key, drag | none, unless the target is a point of no return |
| L3 VALIDATION | engaging buttons | human confirmation on any non-return |
| L4 AUTONOMOUS | full autonomy | none — everything traced |

Tools: `main_click`, `main_type`, `main_key`, `main_drag`, `main_hover`,
`main_press`, `main_navigate`, `main_activate` (+ L4-gated held-input primitives).

**🪞 Show — the face**

A premium, click-through, capture-invisible overlay highlights what the agent
targets, ripples where it clicks, and **emphasises the exact element you confirm
at the gate**. Never on an action's critical path. Off by default.

---

## Security model

Daimon is built so an AI can act on your machine *safely*:

- **Daimon enforces the ceiling**, not the client — any AI plugs in, none is
  trusted. The AI can never raise its own limit.
- **Points of no return** (send / delete / pay / drop-on-Trash …) are classified
  on the **observed** element (the AI re-probes the real target — a lying agent
  can't dodge the gate by mislabelling a button) and gated by a **native macOS
  confirmation dialog**. Timeout = deny.
- **L4 full autonomy** is unlocked only by a human typing a phrase out-of-band;
  consent is recorded in an append-only, hash-chained ledger. `no-log = no-act`.
  A forged state file can't escalate to L4.
- **Secrets never leave**: secret-role fields (`AXSecureTextField`) and declared
  apps are blanked in Touché and blacked out in Vue, *before* anything is served.
- **Kill the process at any time** — the physical override always wins.

---

## Install (macOS)

1. Download `Daimon-<version>.dmg` from the [latest release](../../releases/latest).
2. Open it and drag **Daimon** to **Applications**.
3. Launch **Daimon** — the **aperture** glyph appears in the menu bar (no Dock
   icon). First run opens the onboarding window.
4. **Register your AI clients** (one click) and **grant** Screen Recording +
   Accessibility when guided.
5. Restart your AI client. It now has `vue_*`, `touche_*`, `main_*`, `overlay_*`.

The menu-bar dropdown lets you set the **hands ceiling** (L0–L3), toggle the
overlay, re-run setup, and quit, any time.

> macOS permissions attach to the **app that launches Daimon** (your terminal /
> IDE / AI app), not to Daimon.app — the onboarding explains this.

### Supported AI clients (auto-detect + one-click register)

Claude Code · Claude Desktop · Cursor · Windsurf · GitHub Copilot CLI · Codex
(CLI + Desktop) · Mistral Vibe · Antigravity (Desktop / IDE / CLI).

Registration is idempotent, reversible, and **backed up** — a malformed client
config is refused, never overwritten. (Codex and Vibe use TOML; Daimon edits a
`# DAIMON:START/END` marker block in place and leaves the rest of your config
untouched.)

---

## Run from source

```bash
pip install -e ".[dev]"
daimon setup        # register into detected clients + guide permissions
daimon serve        # the MCP stdio server (what clients launch)
```

CLI: `daimon install [--all] | uninstall | status | onboard | setup`.
Set the ceiling in `~/Library/Application Support/Daimon/config/motor.yaml`
(or via the menu bar). L4: `python -m daimon.motor.control engage`.

## Build the signed DMG

See [`build/macos/README.md`](build/macos/README.md). Requires Xcode CLT, an
Apple Developer ID, and notary credentials. `./build/macos/build_macos.sh`
(use `--no-sign` for a fast local build).

## Tests

```bash
PYTHONPATH=src python -m pytest -q
```

The pure core (guard, reversibility, consent, audit, secrets filter, client
registration, tray/menu, …) is unit-tested without macOS; the AppKit surfaces
are smoke-validated.

---

## License

[GNU AGPL-3.0-or-later](LICENSE). © Arborithm. If you run a modified version as a
network service, the AGPL requires you to offer your users its source.

Reference & kinship: [Omi](https://github.com/BasedHardware/omi) —
perception/action decoupled on macOS via the Accessibility API.
