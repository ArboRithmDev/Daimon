# Spec — Pacte cooperative channel v1.1: Delta facilitator toolpack (Daimon side)

**Date**: 2026-06-24
**Branch**: `internal` only (Pacte never ships in the public AGPL `main`).
**Status**: frozen wire contract; this spec covers the **Daimon half** only.

## Context

The cooperative channel (Pacte, 5th organ) already works: Delta, launched under
`--dev`, exposes a JSON-RPC 2.0 endpoint on loopback TCP, published via
`~/.daimon/cooperative/delta-<pid>.json` (`{port, token, pid, app, protocol_version}`,
perms 0600). Daimon already speaks it through three MCP tools:

- `pacte_describe` → handshake + capability manifest, opens a cooperative session.
- `pacte_probe(fields?)` → reads internal state (redacted).
- `pacte_act(verb, args, intent, level, reversible)` → routes a verb through the
  Hands ceiling + audit ledger.

The token always travels in `params.token`. Hands levels: 0 READ · 1 NONDESTRUCTIVE ·
2 INPUT · 3 VALIDATION · 4 AUTONOMOUS. The session ceiling is hard-clamped
`min(ceiling, VALIDATION)` so the channel can never reach AUTONOMOUS.

This spec adds **7 capabilities** to close the gaps the Delta e2e campaign exposed.
The wire contract is **FROZEN** — Delta implements the same contract independently.
Every open question is already decided below; none are reopened.

## Cross-cutting frozen principles

1. Token always in `params.token`. A request without a valid token → error `-32001`,
   zero execution. (Already enforced by the protocol layer + Delta.)
2. The Delta server is single-thread, QTimer-polled: **no Daimon call may make the
   server block**. All waiting/polling lives on the Daimon side (`pacte_expect`).
3. Coordinate space: Daimon reasons in SCENE units or `node_id`. Delta resolves
   scene→viewport→pixels. Daimon never sends screen pixels.
4. Redaction is **Delta-side**: any secret-zone item is expurgated by Delta before it
   leaves the endpoint (capture included — painted as a neutral block). Daimon keeps its
   existing second-layer `redact_nodes` for the legacy `items/decorators/selected` keys;
   it does **not** newly recurse into the new nested probe fields (see ADR-1).
5. Every new capability declares its exact Hands level and flows through the audit
   ledger exactly like `pacte_act`. Nothing executes outside an open cooperative session.

## Capabilities

### Surface map — what is genuinely new

| Capability       | Wire (Delta)                    | Daimon surface                         | Level |
|------------------|---------------------------------|----------------------------------------|-------|
| 1 capture        | NEW method `capture`            | **NEW tool** `pacte_capture`           | 0 READ |
| 2 expect         | (none — pure Daimon loop)       | **NEW tool** `pacte_expect`            | 0 READ |
| 3 events         | NEW probe field `events` + `events_since` param | **NEW tool** `pacte_events` + `pacte_probe(["events"])` | 0 READ |
| 4 set_prop       | NEW act verb `set_prop`         | `pacte_act(verb="set_prop", level=2)`  | 2 INPUT |
| 4 inspector      | NEW probe field `inspector`     | `pacte_probe(["inspector"])`           | 0 READ |
| 5 tree           | NEW probe field `tree`          | `pacte_probe(["tree"])`                | 0 READ |
| 6 serialized     | NEW probe field `serialized`    | `pacte_probe(["serialized"])`          | 0 READ |
| 7 set_motion     | NEW act verb `set_motion`       | `pacte_act(verb="set_motion", level=1)`| 1 NONDESTRUCTIVE |
| 7 quiescent      | NEW probe field `quiescent`     | `pacte_probe(["quiescent"])`           | 0 READ |

Genuinely new MCP tools: **`pacte_capture`, `pacte_expect`, `pacte_events`**. Verbs
`set_prop`/`set_motion` ride the existing generic `pacte_act`; fields
`inspector/tree/serialized/quiescent` ride the existing generic `pacte_probe`. The
probe/act generality is the whole point — adding a Delta verb or field is **zero**
Daimon change beyond confirming level + (for probe fields needing redaction) coverage.

### 1 — `pacte_capture` (targeted pixels) — READ 0

NEW JSON-RPC method `capture` (read-only; **not** an act verb).
- params: `{ token, target, max_width?=1024, padding?=0 }`, where
  `target` = `node_id:str` | `{"scene":{x,y,w,h}}` | `"viewport"`.
- result: `{ ok, image_base64:str, mime:"image/png", width:int, height:int,
  scene_rect:{x,y,w,h} }`. PNG, downscaled keeping ratio if wider than `max_width`.
- Daimon surface: `pacte_capture(target, max_width=1024, padding=0)` RETURNS the image
  to the agent (like `vue_snapshot`): a `TextContent` with `{scene_rect}` + an `MCPImage`.
- Requires an open session (client present). Level READ ⇒ no ceremony, but never outside
  a session. No re-redaction in Daimon — Delta already painted secret items neutral.

### 2 — `pacte_expect` (determinism: poll-until) — READ 0

100% Daimon-side: loop calling `pacte_probe` until a condition holds or timeout. No new
blocking Delta call. Delta only supplies the `quiescent` field (capability 7).
- Surface: `pacte_expect(condition, timeout_ms=2000, poll_ms=50)`.
- Condition DSL (FROZEN):
  - leaf: `{ field:str, op:"eq|ne|gte|lte|contains|len_eq", value:any }`
  - shortcut: `{ quiescent:true }` ≡ `{field:"quiescent",op:"eq",value:true}`
  - `field` may be dotted into a probe object, e.g. `"decorators.nested_overlay.visible"`.
  - combinators: `{ all:[cond,...] }` / `{ any:[cond,...] }` (recursive).
- result: `{ ok:bool, satisfied:bool, elapsed_ms:int, final:<probe subset read> }`.
  `ok=false` on timeout (`satisfied=false`).
- Frozen: poll 50 ms default, timeout 2000 ms default; cadence clamped to [20, 500] ms;
  the implementation probes only the top-level fields the condition references.

### 3 — `events` probe field (causal verification) — READ 0

NEW probe field `events`:
- `pacte_probe(["events"])` → `{ events:[ {seq:int, kind:"command|event", type:str,
  node_id:str|null, summary:str} ] }`. Last N (default 50), chronological ascending.
- `pacte_probe` accepts `params.events_since:int` → returns only `seq > since`.
- Frozen (Delta): ring buffer 200, fed at `UndoStack.push` (kind=command, type=class name)
  and `event_bus.publish` (kind=event, type=event name). `seq` monotonic (no wall clock).
- Daimon surface: `pacte_probe(fields=["events"])` + helper `pacte_events(since?)` that
  returns only the delta (passes `events_since`).

### 4 — `set_prop` verb + `inspector` probe — INPUT 2 / READ 0

NEW act verb `set_prop`: args `{ node_id, path, value }`, `path` dotted (e.g.
`"metadata.canvas.x"`, `"content"`, `"style_class"`, `"on_press"`). Delta executes it
through the **undoable** Inspector/ChangeProperty path (never a raw mutation) → commit +
undoable + canvas sync; result `{ ok, state_delta? }`.
NEW probe field `inspector`: `{ bound_node_id, mode:"widget|screen|canvas|multi|none",
fields:[ {path, label, value, editable} ] }`.
- Daimon surface: `pacte_act(verb="set_prop", level=2, args={node_id,path,value})` +
  `pacte_probe(["inspector"])`. No new Daimon tool — generic act/probe already cover it.

### 5 — `tree` probe field (IR hierarchy + layout coords) — READ 0

NEW probe field `tree`: full IR tree from the active screen root, recursive:
`{ id, type, canvas:{x,y,w,h}|null, layout_rule:str|null, rendered_rect:{x,y,w,h}|null,
children:[...] }`. `rendered_rect` = real laid-out scene rect (resolved for nested/rule
children via the `collect_node_regions` proxy hit-test). Unlimited depth.
- Daimon surface: `pacte_probe(["tree"])`.

### 6 — `serialized` probe field (persistence round-trip) — READ 0

NEW probe field `serialized`: `{ serialized:str }` = `.delta` DSL of the active screen via
the existing serializer.
- Daimon surface: `pacte_probe(["serialized"])`.

### 7 — `set_motion` verb + `quiescent` field — NONDESTRUCTIVE 1 / READ 0

NEW act verb `set_motion`: args `{enabled:bool}` → toggles `window._motion_enabled`; at
`false`, force-finishes any running animation.
NEW probe field `quiescent:bool` = (event queue drained) AND (no active animation) AND (no
in-flight drag). Feeds `pacte_expect({quiescent:true})`.
- Daimon surface: `pacte_act(verb="set_motion", level=1, args={enabled})` +
  `pacte_probe(["quiescent"])`.

## Security (Daimon side)

- Everything flows through the audit ledger + Hands ceiling, like `pacte_act`.
  `capture`/`probe*` = READ 0; `set_motion` = 1; `set_prop` = 2. Refuse above the
  session ceiling. Never execute outside an open cooperative session.
- Never persist token/port beyond the session; re-read the discovery file on each open;
  **liveness-check the `pid`** (a stale file from an unclean kill carries a dead pid).

## Decisions / ADRs

- **ADR-1 — New nested probe fields rely on Delta-side redaction.** The frozen principle
  puts redaction on Delta (it owns the secret-zone model and the scene). Daimon's
  `redact_nodes` second layer stays scoped to the legacy flat keys
  `items/decorators/selected`; it does not recurse into `tree`/`inspector`/`events`.
  Rationale: re-deriving secret membership in Daimon would duplicate Delta's authority and
  the contract already guarantees Delta redacts before send. Revisit if a non-Delta app
  ever speaks the protocol without server-side redaction.
- **ADR-2 — `pacte_expect` is pure client-side polling.** No blocking Delta call (server is
  single-thread). Time source is injectable (`monotonic`/`sleep`) for deterministic tests.
- **ADR-3 — pid liveness uses `os.kill(pid, 0)`.** `pid <= 0` (e.g. test doubles) skips the
  check (no liveness info ⇒ accept); `ProcessLookupError` ⇒ dead ⇒ reject;
  `PermissionError` ⇒ alive (different owner) ⇒ accept.

## Done

7 surfaces callable, manifest coherent, tests green (unit against the fake endpoint +
≥1 live against a real `--dev` app where the field/verb exists), docs current. Any gap
documented as ADR/deferral — never a silent patch. If a Delta-side field/verb is missing
at live-test time, the fake-server unit test stands as proof; mark the live test pending.
