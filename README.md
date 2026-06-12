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
- **Perception ≠ action.** Daimon reports; it never clicks or types. The motor
  organ ("the hands") is out of scope and lives elsewhere.
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

## The hands (motor organ)

Daimon can act under a ceiling it enforces itself (default **L0**, hands off):

| Level | Scope | Gate |
|-------|-------|------|
| L0 READ | nothing | — |
| L1 NONDESTRUCTIVE | scroll, focus, navigate | none |
| L2 INPUT | click, type, drag | none, unless the target is a point of no return |
| L3 VALIDATION | engaging buttons | human confirmation on any non-return |
| L4 AUTONOMOUS | full autonomy | none — everything traced |

- Tools: `main_navigate`, `main_click`, `main_type`, `main_press` (`main_drag` planned).
- Points of no return (send/delete/pay/…) are classified (AI declares, Daimon
  verifies) and gated by a **native macOS dialog**. Timeout = deny.
- **L4** is engaged only by a human typing a phrase out-of-band:
  `python -m daimon.motor.control engage` (and `disengage`). The consent is
  recorded in an append-only, hash-chained ledger under `logs/`. `no-log = no-act`.
- Set the ceiling in `config/motor.yaml` (copy `config/motor.example.yaml`).
- Kill the process at any time to stop everything — the physical override always wins.

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
