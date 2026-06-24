# Plan — Pacte v1.1 Delta facilitators (Daimon side, TDD)

**STATUS: DONE (2026-06-24).** All 7 capabilities shipped on `internal`. Suite 551
passed / 18 skipped (was 522). New tools `pacte_capture/pacte_expect/pacte_events`;
verbs `set_prop`/`set_motion` + fields `inspector/tree/serialized/quiescent` ride the
generic act/probe. pid liveness added to discovery. Live tests against a real Delta
`--dev` remain pending per the interop note (unit fake-server proofs stand).


Spec: `docs/superpowers/specs/2026-06-24-pacte-delta-facilitators-v1.1.md`.
Branch `internal`. Method: red → minimal impl → green → commit, one capability per commit.
Test runner: `/Users/Ben/.hfenv/bin/pytest`. Mock Delta with the fake endpoint double.

## Task 0 — discovery pid liveness (security)
- RED: `test_pacte_discovery.py` — a discovery file with a dead pid is rejected; a live pid
  (current process) accepted; `pid<=0` accepted (no liveness info).
- GREEN: `discovery._alive(pid)` via `os.kill(pid,0)` (ADR-3); `_load` rejects dead pids.
- Keep existing discovery tests green (their files use a live/own pid or pid<=0).
- Commit: `feat(pacte): reject discovery files whose pid is dead (liveness check)`.

## Task 1 — extend the fake endpoint to the frozen contract
- Add handlers/state to `tests/fakes/cooperative_endpoint.py`: `capture`, probe fields
  `events`/`inspector`/`tree`/`serialized`/`quiescent`, `events_since` filtering, act verbs
  `set_prop`/`set_motion`. Pure double, no Qt. Default-tolerant so old tests still pass.
- No production code; lands with Task 2's first red test. (Test infra only.)

## Task 2 — pacte_capture (NEW tool, READ 0)
- RED: organ test — `pacte_capture("viewport")` returns `[TextContent(scene_rect), MCPImage]`;
  base64 decoded to PNG bytes; refused when no session.
- GREEN: `Pacte.register` adds `pacte_capture(target, max_width=1024, padding=0)`; calls
  `client.call("capture", {...})`; decodes `image_base64`; returns content list.
- Commit: `feat(pacte): pacte_capture — return targeted scene pixels as an image`.

## Task 3 — pacte_expect (NEW tool, READ 0, pure loop)
- New module `src/daimon/pacte/expect.py`: pure DSL evaluator + dotted-field resolver +
  field-root extractor. RED unit tests for eq/ne/gte/lte/contains/len_eq, all/any,
  quiescent shortcut, dotted paths, missing-field → unsatisfied.
- RED organ test: poll loop satisfies / times out; injectable clock+sleep; clamp [20,500];
  probes only referenced field roots; `final` carries the last probe subset.
- GREEN: evaluator module + `pacte_expect` tool wired with `monotonic`/`sleep` (injectable).
- Commit: `feat(pacte): pacte_expect — client-side poll-until on a frozen condition DSL`.

## Task 4 — pacte_events (NEW tool, READ 0)
- RED: `pacte_probe(["events"])` passes through; `pacte_events(since)` sends `events_since`
  and returns only `seq > since`.
- GREEN: add `pacte_events(since: int | None = None)` tool (probe with `events_since`).
- Commit: `feat(pacte): pacte_events — causal event log with since-delta`.

## Task 5 — set_prop + inspector (existing surfaces, contract proof)
- RED: `pacte_act(verb="set_prop", level=2, ...)` routes through the gate (allowed within
  ceiling, refused above) and forwards `{node_id,path,value}` to the endpoint `act`;
  `pacte_probe(["inspector"])` passes through.
- GREEN: expected to pass with zero production change (generic act/probe). If a gap shows,
  fix minimally. Confirms the contract + levels.
- Commit: `test(pacte): set_prop verb routing + inspector probe passthrough`.

## Task 6 — tree + serialized passthrough (existing surface, contract proof)
- RED/GREEN: `pacte_probe(["tree"])` and `pacte_probe(["serialized"])` pass through intact
  (nested tree not mangled by `redact_nodes`; ADR-1).
- Commit: `test(pacte): tree + serialized probe passthrough`.

## Task 7 — set_motion + quiescent (existing surface, contract proof)
- RED/GREEN: `pacte_act(verb="set_motion", level=1, args={enabled})` routes at L1;
  `pacte_probe(["quiescent"])` passes through; `pacte_expect({quiescent:true})` end-to-end
  against the fake driving `quiescent` false→true.
- Commit: `test(pacte): set_motion verb + quiescent field + expect integration`.

## Task 8 — finalize
- Full suite green. Update the Pacte memory + this plan's status. Note any deferral
  (e.g. `_register_pacte` silent swallow) as ADR if touched.
- Live tests: marked `pytest.mark.skip`/`xfail` pending a real Delta `--dev` exposing the
  field/verb, per the interop note.
