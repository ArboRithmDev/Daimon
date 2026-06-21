# AXE 7 — Cross-Platform Release (v0.0.10) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Do the integration on an isolated worktree** (superpowers:using-git-worktrees) — Phase A rewrites `main` via a large merge; keep it off the live checkout until the suite is green.

**Goal:** Integrate `origin/feat/windows-port` into `main`, fill the cross-platform parity gaps the merge exposes, and cut a public, auto-update-capable **v0.0.10** release for macOS + Windows.

**Architecture:** `main` (35 commits: AXE 4b window control, four-state focus, window-server focus probe, delegation, OCR, calibration) absorbs `origin/feat/windows-port` (33 commits: the `backends/` platform-abstraction layer, the `src/daimon/update/` auto-update subsystem, the full Windows port W0–W5, and the `build/make_manifest.py` release tooling). The merge keeps `main`'s version single-source resolver and feature scope while adopting windows-port's `backends.build_*()` dispatch and update subsystem. Parity gaps (Windows window ops, `WindowsFocusProbe`) are filled post-merge. The release is published as the GitHub **latest** (non-prerelease) so the updater's `…/releases/latest/download/latest.json` resolves.

**Tech Stack:** Python 3.12 (macOS) / 3.13 (Windows), pyobjc (AppKit/ApplicationServices/Quartz), pywin32/ctypes (Win32), FastMCP, PySide6 (tray), PyInstaller, Inno Setup 6, pytest. Release via `gh` CLI.

## Global Constraints

- **Suite must stay green** on the merged tree: `/Users/Ben/.hfenv/bin/pytest -q` (macOS; currently 405 on `main`). Windows-only tests skip on macOS via existing platform guards — do not delete them.
- **Version is single-sourced** from `pyproject.toml` `[project] version` only. The runtime resolver lives in `src/daimon/__init__.py` (pyproject → stamped `src/daimon/_version.py` → installed metadata → `0.0.0+unknown`). `tests/test_version.py` enforces this — never hardcode a version literal elsewhere.
- **Release version = `0.0.10`** (final, not `rc`). Git tag + GitHub release = **`daimon-v0.0.10`** (matches `build/macos/build_macos.sh`'s publish hint and the per-asset URLs).
- **The release MUST be the repository's `latest` GitHub release and MUST NOT be flagged "pre-release."** GitHub's `/releases/latest/` endpoint — which `config/update.example.yaml`'s `manifest_url` depends on — skips pre-releases. A pre-release would silently break auto-update for every client.
- **Manifest platform keys are exactly `macos` and `win64`** (`src/daimon/update/core.py:platform_key`, `build/make_manifest.py` `choices=["win64","macos"]`). Do not invent `macos64`.
- **`backends` pattern wins for platform dispatch; `main`'s features win for behavior.** When a file changed on both sides, take windows-port's `backends.build_*()` imports as the structural base and layer `main`'s feature code on top.
- **Do NOT weaken security or the Hands ceiling** during the merge. The guard chokepoint, secret redaction, and L0–L4 ceiling are invariant.
- Conventional commits; end every commit body with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- **Outward/irreversible steps (push, tag push, `gh release`, build/sign/notarize) are Ben-operated** and live in Phase D. An agent executing Phases A–C stops before any push or publish.

---

## Phase A — Integration merge (`main ← origin/feat/windows-port`)

> Integration tasks: the deliverable is **the suite green + the named behaviors intact**, not pre-written merged code (the exact conflict resolution cannot be authored before the merge runs). Each task gives the per-file resolution recipe from the conflict analysis. Resolve, then verify with the listed command.

### Task A1: Start the merge on a worktree and triage conflicts

**Files:** none yet (git operation).

**Interfaces:**
- Produces: a worktree on a branch `axe7-merge` with the merge in progress and a known conflict set.

- [ ] **Step 1: Create an isolated worktree from `main`**

```bash
cd /Users/Ben/Projets/Daimon
git fetch origin feat/windows-port
git worktree add ../Daimon-axe7 -b axe7-merge main
cd ../Daimon-axe7
```

- [ ] **Step 2: Start the merge (expect conflicts — do not abort)**

```bash
git merge --no-ff origin/feat/windows-port
git diff --name-only --diff-filter=U   # the conflicted set
```

Expected conflicted files (semantic): `pyproject.toml`, `src/daimon/__init__.py`, `src/daimon/server.py`, `src/daimon/motor/factory.py`, `src/daimon/capture/screen_win.py`, `src/daimon/senses/vue.py`, `src/daimon/setup/clients/base.py`, `src/daimon/setup/clients/registry.py`, `src/daimon/setup/deploy.py`. Trivial: `.gitignore`, `tests/test_server_tools.py`, `src/daimon/tray/menu_model.py`. ~70 windows-port-only files arrive clean (additive: `src/daimon/backends/`, `src/daimon/update/`, all `*_win.py`, `src/daimon/config.py`, `src/daimon/userdata.py`, `build/windows/`, `build/make_manifest.py`, Windows tests).

- [ ] **Step 3: Resolve the three trivial conflicts**

- `.gitignore`: union both sides' entries.
- `tests/test_server_tools.py`: keep both sides' added tests (they touch different tools).
- `src/daimon/tray/menu_model.py`: keep both — windows-port's update menu states (`Check for updates` / `Checking…` / `⬆ Update to vX`) and main's menu rows coexist.

- [ ] **Step 4: Commit checkpoint is deferred** — do NOT commit the merge until Task A7 is green. Leave the merge in progress; resolve the rest in A2–A6.

---

### Task A2: Resolve `pyproject.toml` (platform-guarded dependencies)

**Files:**
- Modify (conflict): `pyproject.toml`
- Test: `tests/test_version.py`

**Interfaces:**
- Produces: a dependency table where macOS deps carry `; sys_platform == 'darwin'`, Windows deps carry `; sys_platform == 'win32'`, version = `0.0.10rc2` (bumped to `0.0.10` in Task C1).

- [ ] **Step 1: Resolve**

Take windows-port's platform-conditional structure as the base (it splits pyobjc behind `sys_platform == 'darwin'` and adds Windows deps behind `sys_platform == 'win32'`). Re-add `main`'s `pyobjc-framework-Vision>=10.0` **with a darwin guard**: `"pyobjc-framework-Vision>=10.0; sys_platform == 'darwin'"`. Keep a single `[project] version` line.

- [ ] **Step 2: Verify the file parses and version resolves**

```bash
/Users/Ben/.hfenv/bin/python -c "import tomllib,pathlib; d=tomllib.loads(pathlib.Path('pyproject.toml').read_text()); print(d['project']['version']); print([r for r in d['project']['dependencies'] if 'Vision' in r])"
/Users/Ben/.hfenv/bin/python -m pytest tests/test_version.py -q
```

Expected: prints the version + the darwin-guarded Vision line; version tests pass.

- [ ] **Step 3: Stage** `git add pyproject.toml` (no commit yet).

---

### Task A3: Resolve `src/daimon/motor/factory.py` (backends builders + focus_probe)

**Files:**
- Modify (conflict): `src/daimon/motor/factory.py`
- Test: `tests/test_motor_focus.py`, `tests/` motor factory tests

**Interfaces:**
- Consumes: windows-port `backends.build_actuator/build_gate/build_prober/...`; main `MacOSFocusProbe` (from `src/daimon/motor/focus.py`).
- Produces: `build_organ()` (or equivalent factory) that wires `focus_probe` cross-platform — the focus probe is selected per platform, NOT hardcoded to macOS on Windows.

- [ ] **Step 1: Resolve**

Use windows-port's `backends.build_*()` calls as the structural base. Where `main` added `focus_probe=MacOSFocusProbe()` to the `MotorOrgan(...)` construction, make it platform-correct: on darwin use `MacOSFocusProbe()`, on win32 use `WindowsFocusProbe()` (implemented in Task B2). Prefer a `backends.build_focus_probe()` if you add one to the `backends` package; otherwise a `sys.platform` switch in the factory mirroring how the other backends are chosen. The `sleeper` argument to `MotorOrgan` keeps its default (real `time.sleep`).

- [ ] **Step 2: Verify**

```bash
/Users/Ben/.hfenv/bin/python -c "import daimon.motor.factory"   # imports clean
/Users/Ben/.hfenv/bin/python -m pytest tests/test_motor_focus.py -q
```

Expected: import OK; focus tests pass (they use `FakeFocusProbe`, unaffected by platform wiring).

- [ ] **Step 3: Stage** `git add src/daimon/motor/factory.py`.

---

### Task A4: Resolve `src/daimon/server.py` (backends imports + coord/focus/delegation features)

**Files:**
- Modify (conflict): `src/daimon/server.py`
- Test: `tests/test_server_tools.py`

**Interfaces:**
- Consumes: windows-port `backends.build_overlay_launcher()`, `backends.build_permissions_backend()`; main's `_resolve_point()` helper, the window/focus tool params, and `senses.delegation` imports.
- Produces: a `build_server()` that registers every tool from both sides — the `main_window_*` tools, `ensure_focus` defaults, `space/display/region/window` params, AND uses backends for overlay/permissions.

- [ ] **Step 1: Resolve**

Base = windows-port's backends imports for overlay launcher + permissions. Layer in main's additions: the `_resolve_point()` coordinate resolver, the `main_window_minimize/hide/show` registrations, the `ensure_focus=True` defaults on `main_click/press/drag`, and the `senses.delegation` server-instructions wiring. Keep both sides' tool lists complete.

- [ ] **Step 2: Verify all tools register**

```bash
/Users/Ben/.hfenv/bin/python -c "import asyncio; from daimon.server import build_server; print(sorted(t.name for t in asyncio.run(build_server().list_tools())))"
/Users/Ben/.hfenv/bin/python -m pytest tests/test_server_tools.py -q
```

Expected: the printed set contains `main_window_minimize/hide/show`, `vue_find`, the overlay tools, etc.; server-tool tests pass.

- [ ] **Step 3: Stage** `git add src/daimon/server.py`.

---

### Task A5: Resolve `src/daimon/senses/vue.py` (backends dispatch + profiles/OCR)

**Files:**
- Modify (conflict): `src/daimon/senses/vue.py`
- Test: `tests/` vue/calibration/find tests

**Interfaces:**
- Consumes: windows-port `backends.build_screen()`, `backends.build_a11y()`.
- Produces: a `Vue` that dispatches capture/a11y through backends while keeping main's calibration profiles, `vue_resolve()`, `vue_find()` (OCR), and the enriched `vue_displays()` (origin + dpi) output and the frontmost secret-app exclusion gate.

- [ ] **Step 1: Resolve**

Keep windows-port's `backends.build_screen()/build_a11y()` dispatch as the base. Re-apply main's feature surface on top: calibration profiles, `vue_resolve`, `vue_find`, `vue_displays` enrichment, and the `evaluate_frontmost` secret-app gate. (Note for Phase C/backlog: `frontmost_bundle_id()` in `capture/screen.py` still uses `NSWorkspace.frontmostApplication()` — a known staleness risk recorded in memory; out of scope for this release.)

- [ ] **Step 2: Verify**

```bash
/Users/Ben/.hfenv/bin/python -c "import daimon.senses.vue"
/Users/Ben/.hfenv/bin/python -m pytest -q -k "vue or calibrat or find or display"
```

Expected: import OK; vue/calibration/find/display tests pass.

- [ ] **Step 3: Stage** `git add src/daimon/senses/vue.py`.

---

### Task A6: Resolve setup conflicts (`clients/base.py`, `clients/registry.py`, `deploy.py`, `screen_win.py`, `__init__.py`)

**Files:**
- Modify (conflict): `src/daimon/setup/clients/base.py`, `src/daimon/setup/clients/registry.py`, `src/daimon/setup/deploy.py`, `src/daimon/capture/screen_win.py`, `src/daimon/__init__.py`
- Test: `tests/test_deploy.py`, `tests/test_version.py`, setup/client tests

**Interfaces:**
- Produces: setup that has BOTH windows-port's `PermSpec` framework (cross-platform paths, grant/revoke) and main's Antigravity/Gemini client adapters; `__init__.py` keeps **main's** multi-tier version resolver; `screen_win.py` keeps **windows-port's** working Win32 implementation.

- [ ] **Step 1: Resolve each**

- `src/daimon/__init__.py`: **keep main's resolver** (pyproject → `_version.py` → metadata → sentinel). Discard windows-port's older importlib-only fallback.
- `src/daimon/capture/screen_win.py`: **keep windows-port's** full Win32 implementation (`EnumDisplayMonitors`/`GetMonitorInfo`/`ImageGrab`); main only had a NotImplementedError scaffold.
- `src/daimon/setup/clients/base.py` + `registry.py`: merge both — windows-port's `PermSpec` (path/allow rules, grant/revoke) PLUS main's Antigravity + Gemini adapters in the registry and their install/uninstall enablement markers.
- `src/daimon/setup/deploy.py`: union — keep windows-port's cross-platform deploy paths and main's per-tool whitelist derivation; ensure both client sets deploy.

- [ ] **Step 2: Verify**

```bash
/Users/Ben/.hfenv/bin/python -c "import daimon, daimon.setup.deploy, daimon.setup.clients.registry; print(daimon.__version__)"
/Users/Ben/.hfenv/bin/python -m pytest tests/test_deploy.py tests/test_version.py -q
```

Expected: imports OK, version prints (e.g. `0.0.10rc2`), deploy + version tests pass.

- [ ] **Step 3: Stage** all five.

---

### Task A7: Land the merge (full suite green)

**Files:** none new (verification + merge commit).

- [ ] **Step 1: Confirm no conflict markers remain**

```bash
git diff --name-only --diff-filter=U   # must be empty
grep -rn "^<<<<<<<\|^>>>>>>>\|^=======$" src/ tests/ pyproject.toml || echo "no markers"
```

- [ ] **Step 2: Run the full suite**

```bash
/Users/Ben/.hfenv/bin/pytest -q
```

Expected: PASS. Count ≥ 405 (main) plus windows-port's macOS-runnable tests; Windows-only tests skip cleanly on macOS. If a windows-port test fails on macOS because it was previously gated differently, confirm the skip guard, don't delete the test.

- [ ] **Step 3: Commit the merge**

```bash
git add -A
git commit --no-edit   # keep the merge commit; body already references the branch
```

(If `--no-edit` opens nothing because conflicts were staged, use: `git commit -m "merge: integrate feat/windows-port — backends + auto-update + Windows port into main\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"`.)

---

## Phase B — Cross-platform parity fill

> The merge exposes Windows gaps for features `main` shipped on macOS. Fill them so the merged product behaves consistently. TDD with the existing `Fake*`/platform-guarded patterns (these run on macOS without a Windows host).

### Task B1: Windows window ops in `WindowsActuator`

**Files:**
- Modify: `src/daimon/motor/actuator_win.py`
- Test: `tests/test_motor_actuator_win.py` (create if absent; mirror `tests/test_motor_actuator.py`)

**Interfaces:**
- Consumes: `MotorAction` with `name` in `{window_minimize, window_hide, window_show}` + `params` (`bundle`/`title`/`pid`).
- Produces: `WindowsActuator._handlers()` includes the three window verbs; each calls `ShowWindow` with `SW_MINIMIZE` / `SW_HIDE` / `SW_RESTORE` (+ `SetForegroundWindow` for show), resolving the target window by pid/title.

- [ ] **Step 1: Write the failing test (dispatch presence)**

```python
# tests/test_motor_actuator_win.py — guard so it is a no-op off Windows
import sys, pytest
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows actuator")

from daimon.motor.actuator_win import WindowsActuator

def test_windows_actuator_dispatches_window_ops():
    handlers = WindowsActuator()._handlers()
    for verb in ("window_minimize", "window_hide", "window_show"):
        assert verb in handlers
```

- [ ] **Step 2: Run (skips on macOS, runs on Windows)**

```bash
/Users/Ben/.hfenv/bin/pytest tests/test_motor_actuator_win.py -q   # SKIPPED on macOS
```

Expected on macOS: 1 skipped (still proves it collects). On Windows: FAIL until implemented.

- [ ] **Step 3: Implement** `_window_minimize/_window_hide/_window_show` on `WindowsActuator` using `ShowWindow(hwnd, SW_MINIMIZE|SW_HIDE|SW_RESTORE)` (+ `SetForegroundWindow` on show), with the same window resolution the other Windows handlers use, and register them in `_handlers()`. Mirror the macOS docstrings' "Windows twin" notes.

- [ ] **Step 4: Verify** — on macOS: `pytest -q` stays green (skip); on Windows (Ben, Phase D machine): the new test passes.

- [ ] **Step 5: Commit**

```bash
git add src/daimon/motor/actuator_win.py tests/test_motor_actuator_win.py
git commit -m "feat(motor): Windows window_minimize/hide/show via ShowWindow (parity with macOS)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task B2: `WindowsFocusProbe.frontmost()` implementation

**Files:**
- Modify: `src/daimon/motor/focus.py` (`WindowsFocusProbe`)
- Test: `tests/test_motor_focus.py` (add a Windows-guarded smoke test)

**Interfaces:**
- Produces: `WindowsFocusProbe.frontmost() -> FocusState | None` reading the live foreground window owner via `GetForegroundWindow` + `GetWindowThreadProcessId`, resolving pid → process image name / window title (NOT a `NotImplementedError`). This makes the four-state focus result work on Windows, mirroring the macOS window-server probe.

- [ ] **Step 1: Write the failing test (Windows-guarded)**

```python
# tests/test_motor_focus.py — add
import sys
def test_windows_focus_probe_reads_foreground(monkeypatch):
    if sys.platform != "win32":
        import pytest; pytest.skip("Windows focus probe")
    from daimon.motor.focus import WindowsFocusProbe
    fs = WindowsFocusProbe().frontmost()
    assert fs is None or fs.pid is not None
```

- [ ] **Step 2: Run** — `pytest tests/test_motor_focus.py -q` (skips on macOS).

- [ ] **Step 3: Implement** `WindowsFocusProbe.frontmost()` with `GetForegroundWindow()` → `GetWindowThreadProcessId()` → pid; resolve title via `GetWindowText`, image name via the process. Return `FocusState(title=..., pid=..., bundle=None)`. The OS-agnostic `window_is_frontmost` matcher and the organ are unchanged. Keep the macOS `MacOSFocusProbe` (window-server) intact.

- [ ] **Step 4: Verify** — macOS suite green (skip); Windows (Phase D): smoke passes.

- [ ] **Step 5: Commit**

```bash
git add src/daimon/motor/focus.py tests/test_motor_focus.py
git commit -m "feat(motor): WindowsFocusProbe.frontmost via GetForegroundWindow (focus parity)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

> **Out of scope (YAGNI) for this release:** a Windows `vue_find` OCR backend. If `vue_find` is called on Windows it should raise a clear "not available on Windows yet" rather than crash — confirm the existing scaffold does this; if not, that's a one-line guard, otherwise defer.

---

## Phase C — Release plumbing correctness (agent, no publish)

### Task C1: Bump version to `0.0.10`

**Files:**
- Modify: `pyproject.toml`
- Test: `tests/test_version.py`

- [ ] **Step 1:** Set `[project] version = "0.0.10"` in `pyproject.toml`.
- [ ] **Step 2: Verify**

```bash
/Users/Ben/.hfenv/bin/python -c "import daimon; print(daimon.__version__)"   # 0.0.10
/Users/Ben/.hfenv/bin/pytest tests/test_version.py -q
```

Expected: prints `0.0.10`; version tests pass.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore(release): bump version to 0.0.10

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task C2: Wire macOS release-manifest generation

**Files:**
- Modify: `build/macos/build_macos.sh`
- Reference: `build/make_manifest.py` (arrived in the merge), `src/daimon/update/core.py:platform_key` (`macos`)

**Interfaces:**
- Produces: after the DMG is built/notarized, `build_macos.sh` generates/merges the macOS entry into `dist/latest.json` + `dist/SHA256SUMS` via `make_manifest.py --platform macos`.

- [ ] **Step 1:** Append, after the notarize/staple block (before the cleanup `rm -rf`), a manifest step:

```bash
# 7. Release manifest (macOS entry). Merges into dist/latest.json + SHA256SUMS.
python3 "$REPO_ROOT/build/make_manifest.py" --version "$VERSION" --out "$DIST_DIR" \
    --platform macos --asset "$DMG_PATH" ${NOTES:+--notes "$NOTES"}
```

(Place it so it runs whether or not signing ran — the manifest just needs the DMG + its sha256. Ensure `$DIST_DIR` and `$DMG_PATH` are the same vars used above.)

- [ ] **Step 2: Verify the script is syntactically valid**

```bash
bash -n build/macos/build_macos.sh && echo "build_macos.sh OK"
/Users/Ben/.hfenv/bin/python build/make_manifest.py --help   # arg surface sanity
```

- [ ] **Step 3: Commit**

```bash
git add build/macos/build_macos.sh
git commit -m "build(macos): emit latest.json + SHA256SUMS (platform=macos) after DMG

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task C3: Pin the release identity (tag, non-prerelease, manifest URL)

**Files:**
- Create: `docs/RELEASE.md` (a short, authoritative release runbook for v0.0.10 and beyond)
- Reference: `config/update.example.yaml` (`manifest_url`)

**Interfaces:**
- Produces: a runbook that locks the tag name (`daimon-v0.0.10`), mandates publishing as **latest / not pre-release**, and lists the exact assets the manifest URLs expect.

- [ ] **Step 1:** Write `docs/RELEASE.md` containing: the tag (`daimon-v0.0.10`); the **non-prerelease** requirement with the one-line reason (GitHub `/releases/latest/` skips pre-releases, which `manifest_url` depends on); the required release assets and their exact filenames — `Daimon-0.0.10.dmg`, `Daimon-0.0.10-setup.exe`, `latest.json`, `SHA256SUMS`; and the Phase D commands below. Note that asset URLs in `latest.json` use the stable `…/releases/latest/download/<name>` form.

- [ ] **Step 2: Verify** the documented asset names match what the build scripts emit:

```bash
grep -n "Daimon-\$VERSION\|Daimon-\$version\|latest.json\|SHA256SUMS" build/macos/build_macos.sh
git show axe7-merge:build/windows/build_windows.ps1 | grep -ni "setup.exe\|make_manifest\|latest.json"
```

Expected: macOS emits `Daimon-<version>.dmg` + manifest; Windows emits `Daimon-<version>-setup.exe` + `latest.json` + `SHA256SUMS`. Reconcile any name drift in `docs/RELEASE.md`.

- [ ] **Step 3: Commit**

```bash
git add docs/RELEASE.md
git commit -m "docs(release): v0.0.10 runbook — daimon-v0.0.10 tag, must publish as latest

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task C4: Land the integration onto `main`

**Files:** none (git).

- [ ] **Step 1: Final full suite on the worktree**

```bash
cd /Users/Ben/Projets/Daimon-axe7 && /Users/Ben/.hfenv/bin/pytest -q
```

Expected: green.

- [ ] **Step 2: Fast-forward `main` to the integrated branch** (in the main checkout)

```bash
cd /Users/Ben/Projets/Daimon
git merge --ff-only axe7-merge   # main now contains the integration + parity + release plumbing
git worktree remove ../Daimon-axe7
```

Expected: `main` advances with no new merge commit (ff-only). If ff is refused (main moved), rebase `axe7-merge` on `main` first, re-run the suite, then ff.

- [ ] **STOP. Phase D is Ben-operated and irreversible.** An agent ends here and reports: suite green, `main` integrated locally, **not pushed**.

---

## Phase D — Build, sign, publish (BEN-OPERATED — irreversible, needs machines + secrets)

> Every step below is outward-facing or needs Ben's signing/notarization credentials and a Windows host. Do them deliberately; each is hard to undo.

### D1 — Push the integrated `main` (35 commits + integration)

```bash
git push origin main
```

⚠️ First publication of all AXE 4b + integration work. Confirm `git log --oneline origin/main..main` looks right before pushing.

### D2 — Tag the release

```bash
git tag -a daimon-v0.0.10 -m "Daimon 0.0.10 — cross-platform public beta"
git push origin daimon-v0.0.10
```

### D3 — macOS build + notarize (on Ben's Mac)

Requires: Developer ID Application cert (`Benjamin DUBOIS (M729622MH3)`) in login keychain; `AC_PASSWORD` notarytool keychain profile; `librsvg` (`brew install librsvg`).

```bash
./build/macos/build_macos.sh
# Verify:
codesign --verify --deep --strict --verbose=2 dist/Daimon-0.0.10.dmg \
  && spctl --assess --type install -v dist/Daimon-0.0.10.dmg \
  && stapler validate dist/Daimon-0.0.10.dmg
# Produces: dist/Daimon-0.0.10.dmg, dist/latest.json (macos entry), dist/SHA256SUMS
```

### D4 — Windows build + sign (on Ben's Windows host)

Requires: Authenticode cert in the Windows store; Inno Setup 6. Build from `main` (now cross-platform).

```powershell
$env:DAIMON_CERT_SUBJECT = "Arborithm"
.\build\windows\build_windows.ps1
# Produces: dist\Daimon-0.0.10-setup.exe, dist\latest.json (win64 entry), dist\SHA256SUMS
```

> The manifest is per-platform-merged. Build whichever platform first, then on the second platform run `make_manifest.py` against the **same** `latest.json` (copy the first platform's `dist/latest.json` over, or re-merge) so the final `latest.json` carries BOTH `macos` and `win64` assets before upload.

### D5 — Create the GitHub release as **latest** (not pre-release) and upload assets

```bash
gh release create daimon-v0.0.10 \
  dist/Daimon-0.0.10.dmg \
  dist/Daimon-0.0.10-setup.exe \
  dist/latest.json \
  dist/SHA256SUMS \
  --title "Daimon 0.0.10" \
  --notes-file docs/RELEASE.md \
  --latest
```

⚠️ **Do NOT pass `--prerelease`.** The updater's `…/releases/latest/download/latest.json` only resolves to a release marked latest. Confirm the final `latest.json` has both `assets.macos` and `assets.win64`.

### D6 — Field validation (real machines)

- **AXE 4b TEST 2b re-confirm (Mac):** against the freshly built/installed `Daimon.app`, drive a single `main_click(ensure_focus=true)` on a background window → expect `focus == "activated_and_frontmost"` (the window-server probe fix `4037a58`).
- **Auto-update end-to-end:** install 0.0.10 on both OSes; confirm the tray's background check fetches `latest.json`, shows "⬆ Update to v…", and that a future bump applies (download → SHA256 gate → `apply_macos`/`apply_win` swap → relaunch). Validate `apply_macos` replaces `/Applications/Daimon.app` and relaunches without a stale mount.
- Window ops, auto-focus background, OCR, L4-tray — smoke on both platforms.

---

## Final verification (end of Phase C, before Ben's Phase D)

- [ ] `git diff --name-only --diff-filter=U` empty; no conflict markers anywhere.
- [ ] `/Users/Ben/.hfenv/bin/pytest -q` green on the integrated `main` (≥ 405 + windows-port macOS-runnable tests; Windows-only tests skipped, not deleted).
- [ ] `daimon.__version__ == "0.0.10"`; `tests/test_version.py` green.
- [ ] `src/daimon/update/`, `src/daimon/backends/`, `build/make_manifest.py`, `build/windows/`, all `*_win.py` present on `main`.
- [ ] `WindowsActuator` has window ops; `WindowsFocusProbe.frontmost()` implemented (no `NotImplementedError`).
- [ ] `build/macos/build_macos.sh` emits `latest.json` (`--platform macos`) + `SHA256SUMS`; `bash -n` clean.
- [ ] `docs/RELEASE.md` pins `daimon-v0.0.10`, the non-prerelease requirement, and the four asset filenames.
- [ ] `main` NOT pushed; no tag created; no `gh release` run. (Phase D is Ben's.)

## Out of scope (YAGNI)

- Windows `vue_find` OCR backend (defer; guard against crash only).
- Fixing `capture/screen.py:frontmost_bundle_id()` NSWorkspace staleness for the Vue secret-app gate (separate hardening item, recorded in memory).
- GitHub Actions CI for builds (builds stay local on Ben's machines).
- `main_window_close/quit` destructive ops.
