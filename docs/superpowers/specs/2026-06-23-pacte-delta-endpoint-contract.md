# Delta prompt — cooperative endpoint for Daimon's Pacte channel

This is the paste-ready prompt to run in a **Claude Code session inside the Delta repo**. It is
self-contained: the protocol below is the frozen contract Daimon's `Pacte` organ expects. Daimon
never imports Qt — all Qt/scene knowledge lives in this endpoint.

---

## PROMPT (paste into the Delta session)

We are adding a **cooperative debug endpoint** to Delta so an external organ (Daimon) can drive
and observe in-app manipulation during autonomous end-to-end testing. Today Daimon can only see
the OS accessibility tree (widgets) and inject OS-level synthetic input — which does **not** fire
Qt's event dispatch, so `QGraphicsScene` manipulation (drag-commit, snap, magnetism, handles,
decorators) is invisible and undriveable. This endpoint closes that gap.

Use brainstorming → spec → plan → TDD. The endpoint is **dev-only** and must never ship in a
production build.

### What to build

A small endpoint module, active **only when Delta is launched with `--dev`**, exposing a
**JSON-RPC 2.0** server over **loopback TCP (`127.0.0.1`)**.

**Discovery handshake (frozen):**
- On start, bind a loopback port and write a discovery file:
  `~/.daimon/cooperative/delta-<pid>.json` with exactly:
  `{ "port": <int>, "token": "<random per-session secret>", "pid": <int>, "app": "delta", "protocol_version": "1.0" }`
- File permissions **`0600`**. Mint a fresh random `token` each launch.
- Every JSON-RPC request from Daimon carries the token; reject requests whose token does not match.
- Bind loopback only (never `0.0.0.0`). Remove the discovery file on clean shutdown.

**Three JSON-RPC methods (frozen):**

1. `describe` → returns the **capability manifest**:
   - `probe_fields`: the list of state fields this app exposes (see probe below).
   - `act_verbs`: each verb with `{ "name": str, "level": int, "params": <schema> }` where `level`
     is the verb's Hands authorization level on this ladder (Daimon enforces it):
     `0 READ · 1 NONDESTRUCTIVE · 2 INPUT · 3 VALIDATION · 4 AUTONOMOUS`.
   - `protocol_version: "1.0"`.

2. `probe(fields?: [str])` → returns current internal state. Expose at least:
   - `selected_ids` — ids of selected scene items.
   - `items` — per item: `{ id, type, scene_rect: {x,y,w,h}, metadata_canvas: {x,y,w,h}, z, parent_id }`.
   - `undo_depth`, `redo_depth`, `dirty` (bool).
   - `decorators` — visibility + scene rects of: selection handles, dimension labels, alignment
     guides (the red snap lines), nested overlay, multi-selection bounding box.
   Probe is **read-only**. Return plain JSON (no Qt objects).

3. `act(verb: str, args: dict)` → execute a verb, return `{ ok, result, state_delta? }`.
   Implement these verbs (declare each with the level shown):
   - `drag` (level 2) — fire **QTest-style** mousePress / mouseMove(s) / mouseRelease on the
     target `NodeItem` through Qt's event queue, so commands are pushed, snap + magnetism run, and
     the move **commits** (must be undoable). Args: `{ target: node_id | {scene_x,scene_y}, to: {scene_x,scene_y}, modifiers?: [str] }`.
   - `resize` (level 2) — drag a resize handle by id/side. Args: `{ target: node_id, handle: str, to: {scene_x,scene_y} }`.
   - `marquee` (level 2) — rubber-band select. Args: `{ from: {scene_x,scene_y}, to: {scene_x,scene_y} }`.
   - `click` (level 2) — click at a **scene point or node_id**; resolve scene→viewport→pixel
     internally. Args: `{ target: node_id | {scene_x,scene_y}, button?, count?, modifiers?: [str] }`.
   - `load_fixture` (level 1) — load a known IR project (or screen + widgets) into a deterministic
     start state, bypassing dialog navigation. Args: `{ fixture: <id-or-inline-IR> }`.
   - `shortcut` (level 2) — dispatch a keyboard shortcut and **return the state delta** in the same
     round-trip (so Daimon verifies nudge / Cmd+D / Delete / z-order / fit in one call). Args:
     `{ keys: str }`. `result.state_delta` = the changed probe fields before/after.

   For every verb, `target` accepting a `node_id` **or** a scene point is mandatory where shown —
   Daimon drives in scene/node space and relies on the endpoint to resolve to viewport pixels.

### Security obligations (Delta side)

- The endpoint exists **only** under `--dev`. Production builds must not bind it or write the file.
- Loopback bind only; per-session random token; discovery file `0600`; remove on shutdown.
- The endpoint executes whatever Daimon's authorized requests ask — Daimon owns the authorization
  ceiling and the audit ledger. Delta's job is honest execution + an accurate manifest (correct
  `level` per verb).

### Testing

- Unit-test the manifest (`describe`), each `probe` field accessor, and each `act` verb against a
  headless `QGraphicsScene` fixture. Assert `drag` actually commits and is undoable (the whole
  point). Test token rejection and that the endpoint refuses to bind outside `--dev`.

Produce a spec, then a plan, then implement TDD. Keep the endpoint module isolated from app logic
(it reads/drives the scene through a thin accessor, not by reaching into widgets everywhere).
