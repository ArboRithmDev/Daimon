# Contributing to Daimon

Thanks for considering a contribution. Daimon is a young, security‑sensitive
project — issues, bug reports, and PRs are all welcome.

## Ground rules

These are the invariants that keep Daimon trustworthy. A PR that weakens any of
them won't be merged, however convenient:

1. **The AI is never trusted.** Every limit is enforced in Daimon's code, on
   observed facts. The AI requests; Daimon decides. Don't add a path where the
   AI's declaration alone lifts a restriction.
2. **The core stays pure.** Security logic — guard, reversibility, consent,
   audit, redaction — must remain pyobjc‑free and unit‑tested without macOS. Keep
   AppKit/Quartz confined to the thin surfaces (`senses/`, `capture/`,
   `motor/actuator.py`, `motor/gate.py`, `overlay/app/`, `setup/gui/`, `tray/app/`).
3. **Default to denial.** New gates, timeouts, and ambiguity resolve to *deny* /
   *no act*. `no‑log = no‑act` stays true.
4. **Secrets never leave.** Anything new that serializes screen content must run
   through `exclusions.py` first.

See [ARCHITECTURE.md](ARCHITECTURE.md) for how the pieces fit and where each
guarantee lives.

## Dev setup

```bash
git clone https://github.com/ArboRithmDev/Daimon.git
cd Daimon
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Requires Python 3.12+. The full GUI / capture stack needs macOS, but the pure
core runs and tests anywhere.

## Tests

```bash
PYTHONPATH=src python -m pytest -q
```

- New behaviour needs tests. Security‑relevant logic (a new gate, a
  reversibility rule, a consent path) needs tests that cover the **deny** branch,
  not just the happy path.
- Keep tests macOS‑free where the logic is pure; use the injectable seams
  (recording presenters, fake scenes, stubbed schedulers/terminate) rather than
  real AppKit.

## Style

- Match the surrounding code: concise module docstrings that say *why*, absolute
  imports, deferred AppKit imports inside functions.
- Public functions and classes get a one‑line docstring describing intent.
- No new runtime dependencies without a clear reason.

## Pull requests

1. Branch from `main`.
2. Keep the diff focused; one concern per PR.
3. Run the test suite and note any platform‑specific manual checks (e.g. "tested
   the gate dialog on macOS 14").
4. Describe the change and, for anything touching the security model, *why it
   preserves the invariants above*.

## Building a release

Maintainers build the signed DMG locally (`build/macos/build_macos.sh`, needs an
Apple Developer ID) and attach only the DMG to a `vX.Y.Z-beta` GitHub
pre‑release. The version lives in `pyproject.toml`; `tests/test_version.py` pins
the frozen‑app fallback to it.

## Reporting security issues

Do **not** use public issues for vulnerabilities — see [SECURITY.md](SECURITY.md).

## License

By contributing, you agree your contributions are licensed under the project's
[AGPL‑3.0‑or‑later](LICENSE).
