# Pacte — cooperative app channel for autonomous e2e

**Date**: 2026-06-23
**Status**: Design approved, pending implementation plan
**Scope**: New Daimon organ (`Pacte`) + the cooperative-channel protocol it speaks. The
cooperating app's endpoint (Delta) is specified here as a *contract*, not implemented in this repo.

## Problem

Daimon perceives the world through OS surfaces only:

- **Vue** — pixels (screenshots).
- **Touché** — the accessibility tree, which exposes *widgets* only.

A Qt application built on `QGraphicsScene` (Delta) keeps its real state in `QGraphicsItem`
objects, not widgets. Those items, the canvas decorators drawn over them (selection handles,
dimension labels, alignment guides, nested overlays, multi-selection bounding boxes), and the
drag-commit pipeline that runs through Qt's own event queue are **all invisible to Touché and
undriveable by the Mains** (synthetic OS-level drags do not fire the Qt event dispatch that
produces commands, snap, magnetism, and commit).

Consequence observed during the e2e campaign: every manipulation gate had to fall back to
N1 `QTest` as the sole authoritative check. Daimon could neither *drive* nor *observe* in-app
manipulation — it was reduced to pixel-guessing for "did it render" and could never assert
"the move committed and is undoable".

Goal: let an autonomous agent **drive and observe** in-app manipulation through Daimon, so the
manipulation gates become real (N2 "it works") instead of N1-only.

## Doctrine constraint

Daimon is **app-agnostic, OS-agnostic, pull-only**, and it enforces a security contract
(secret redaction on perception + a Hands ceiling L0–L4 with consent + an immutable audit
ledger). Embedding Qt knowledge in Daimon would break agnosticism and bloat the frozen binary.

Therefore the Qt-specific knowledge lives **on the app side**. Daimon gains a *generic
cooperative channel*: the cooperating app, when launched in `--dev`, exposes a debug endpoint;
Daimon speaks a protocol to it and never imports Qt. Any cooperating app that implements the
endpoint benefits — Delta is the first consumer, not a special case.

This is a *pact*, and it respects pull-only: the app must opt in (launch `--dev`, stand up the
endpoint, mint and share a token). Daimon never reaches into an app that has not offered itself.

## Architecture

New organ: **Pacte** — `src/daimon/pacte/`. It registers three MCP tools.

| Tool | Role | Ceiling |
|------|------|---------|
| `pacte_describe` | Handshake + capability manifest: which probe fields and which act verbs the app exposes, plus each act verb's declared Hands level. | L0 (read) |
| `pacte_probe` | Read the app's internal state: `selected_ids`, item geometries, `metadata.canvas` (x/y/w/h), undo/redo depth, `dirty` flag, active decorators (handles / dim-labels / guides / nested overlay / multi-sel bbox) with their rects + visibility. | L0 + redaction |
| `pacte_act` | Invoke an app verb (drag, resize, marquee, click@scene-coords, load_fixture, shortcut, …) with arguments. | Motor gate L0–L4 |

The two generic verbs (`pacte_probe` / `pacte_act`) plus a vocabulary of capabilities the app
declares are what make this maintainable: **adding a new app verb later is zero change in
Daimon** — Delta declares it in its manifest, Daimon discovers it via `pacte_describe`.

### Units (boundaries)

- `pacte/protocol.py` — JSON-RPC 2.0 envelope + message schema for describe/probe/act. Pure;
  no I/O. Independently testable.
- `pacte/discovery.py` — scan the discovery directory, parse discovery files, perform the token
  handshake. Filesystem + validation only; no socket.
- `pacte/client.py` — socket transport (loopback TCP), request/response correlation, timeouts.
- `pacte/organ.py` — register the three MCP tools; wire `pacte_act` to the existing motor gate
  (`motor/gate.py`), wire `pacte_probe` output through the existing redaction filter.

Each unit has one purpose, a well-defined interface, and can be understood and tested without
the others. `organ.py` is the only unit that touches motor + redaction.

## Transport & discovery (cross-platform: macOS + Windows)

- The app, in `--dev`, binds a **loopback (`127.0.0.1`) TCP** server and writes a discovery file:
  `~/.daimon/cooperative/<name>-<pid>.json` containing
  `{ "port": int, "token": str, "pid": int, "app": str, "protocol_version": str }`.
  File permissions `0600`.
- `pacte_describe` scans `~/.daimon/cooperative/`, connects to the advertised loopback port,
  and presents the token in the handshake. Mismatched/absent token → refused.
- Wire protocol: **JSON-RPC 2.0** over the socket. Methods: `describe`, `probe`, `act`.

Loopback TCP is chosen over a unix socket / named pipe because it is **one code path on both
macOS and Windows**. Loopback-only binding + a per-session token (minted by the app, `0600`
file) prevents any other local process from driving the endpoint.

## Security integration

This is the load-bearing part: a cooperative channel that injects synthetic drags/commits is a
real action surface and must not become a back door around Daimon's enforced security contract.

- **`pacte_act` → motor gate.** Each verb carries a Hands level *declared by the app* in the
  manifest (e.g. `drag=L2`, `commit=L3`, `load_fixture=L1`, `shortcut=L2`). Daimon **enforces**:
  it caps the declared level at the active session ceiling, refuses anything above, and writes an
  **audit ledger entry per act** — identical discipline to `main_*`.
- **Durable `--dev` consent.** Opening a cooperative session writes **one** ledger entry —
  `cooperative test session: <app> <pid>, ceiling ≤ Lx` — that pre-authorizes the session's acts
  up to that ceiling. It is **revocable and auditable**. This replaces a per-action L4 dialog,
  which would stall autonomous e2e; the audit trail stays complete because every act is still
  journaled.
- **`pacte_probe` → redaction.** Probe output passes the same secret-redaction filter as Vue and
  Touché. Secrets in item text or metadata never surface to the agent.
- **Channel auth.** Loopback-only bind + token handshake (above).

## The 6 frictions → mapped onto the two verbs

| # | Friction | Mapping |
|---|----------|---------|
| 1 | Synthetic drag does not fire Qt dispatch | `pacte_act` verb `drag` — Delta fires QTest-style press/move/release on the `NodeItem`, producing commands, snap, magnetism, commit. Unblocks F4 move, F5 resize, F2 marquee, nested move/resize as N2. |
| 2 | `QGraphicsScene` invisible to Touché | `pacte_probe` fields — real assertions ("move committed and is undoable") instead of pixel-guessing. |
| 3 | Fine handles / proxy-layout coords | `pacte_act` `click`/`drag` accept a scene point **or** a `node_id`; Delta resolves scene→viewport→pixel. Lifts the 8px-handle limit and the deferred Axe 2 reorder rule-parent (children rendered at layout positions ≠ metadata). |
| 4 | No deterministic start state | `pacte_act` verb `load_fixture` — inject a known IR project (or screen + widgets) via the endpoint, no slow dialog navigation. Every visual gate starts reproducible. |
| 5 | Canvas decorators only eye-validatable | `pacte_probe` fields — visibility + rects of handles, dim-labels, alignment guides (red lines), nested overlay, multi-sel bbox. Confirms the Figma "feel" mechanically. |
| 6 | Keyboard effects unverifiable end-to-end | `pacte_act` verb `shortcut` returns the state delta in one round-trip (act + probe). Verifies nudge / Cmd+D / Delete / z-order / fit (F6/F9/F10/F11). |

## Delta side (the real architectural work — contract only)

Delta, in `--dev`, embeds a small cooperative-endpoint module:

- JSON-RPC 2.0 server on loopback; writes the discovery file; mints the session token.
- **Capability manifest** for `describe`: the probe fields it exposes and the act verbs it
  supports, each verb tagged with its Hands level.
- **Scene introspection accessor** backing `probe` (reads `QGraphicsScene` state).
- **QTest-fidelity action executors** backing `act` (press/move/release through the Qt event
  queue; scene→viewport→pixel resolution; fixture loader; shortcut dispatch + delta capture).

This module is **Delta-repo work**. This spec defines only the contract Daimon expects.

## Testing

- **Daimon side**: an in-repo **Fake cooperative endpoint** (test double) speaking the same
  JSON-RPC protocol, with **no Qt dependency**. Unit-test `pacte_describe` / `pacte_probe` /
  `pacte_act` against it. Verify: gate enforcement (caps at session ceiling, refuses over-ceiling,
  writes ledger entries), durable-consent ledger entry on session open, redaction of probe output,
  token handshake (accept valid / refuse invalid), protocol schema validation, transport timeouts.
- **Delta side**: its own tests for the endpoint module (out of scope here).

## Non-goals

- No Qt or PyQt/PySide dependency added to Daimon.
- No change to the existing `main_*` / `touche_*` / `vue_*` tools.
- Delta's endpoint implementation is not built in this repo.
