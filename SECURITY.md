# Security Policy

Daimon gives an AI the ability to see and act on your Mac. We take that
responsibility seriously: the safety properties below are **enforced by Daimon's
own code**, on observed facts — never requested from, or trusted to, the AI.

## Supported versions

Daimon is in public beta. Security fixes land on `main` and ship in the next
tagged release. Please run the [latest release](https://github.com/ArboRithmDev/Daimon/releases/latest).

| Version | Supported |
|---------|-----------|
| latest `0.0.x-beta` | ✅ |
| older pre‑releases | ❌ (upgrade) |

## Reporting a vulnerability

**Please do not open a public issue for a security vulnerability.**

- Preferred: open a private report via **GitHub → Security →
  [Report a vulnerability](https://github.com/ArboRithmDev/Daimon/security/advisories/new)**.
- Or email **imagerienumerique@gmail.com** with `[Daimon security]` in the
  subject.

Include what you found, how to reproduce it, and the impact. We aim to
acknowledge within a few days and to coordinate a fix and disclosure timeline
with you. Good‑faith research is welcome; please avoid privacy violations and
data destruction while testing.

## Threat model

Daimon assumes the **AI client is untrusted** and possibly adversarial (a
prompt‑injected or misaligned agent). The user, the macOS TCC layer, and
Daimon's own process are trusted. The goal is that no sequence of MCP calls can:

- exceed the ceiling the user set,
- cross a point of no return (send / delete / pay / drop‑on‑Trash …) without an
  explicit human confirmation,
- reach full autonomy (L4) without an out‑of‑band human engagement,
- exfiltrate the contents of secret fields or excluded apps.

What is **out of scope**: a compromised host OS or user account; malware running
with the user's privileges outside Daimon; physical access. Daimon is a safety
ceiling for an AI, not a sandbox against local malware.

## How the guarantees are enforced

| Guarantee | Mechanism |
|-----------|-----------|
| **The AI can't raise its own limit.** | The ceiling lives in Daimon (`motor/guard.py`), sourced from user config / the L4 ledger. The AI only *requests* actions; Daimon decides. |
| **Points of no return are gated.** | Daimon **re‑probes the real element** under the target (`motor/probe.py`) and classifies reversibility on *that* (`motor/reversibility.py`) — a multilingual verb denylist plus dangerous key‑combos. Mislabelling a Delete button "reversible" does not dodge the gate. |
| **The gate is a real human decision.** | A native macOS confirmation dialog (`motor/gate.py`). **Timeout = deny.** Never auto‑answered. |
| **L4 autonomy needs a human, out of band.** | Unlocked only by typing an engagement phrase via `python -m daimon.motor.control engage`. Consent is written to an **append‑only, hash‑chained ledger** (`motor/audit.py`). `no‑log = no‑act`; a forged or edited state file fails the ledger cross‑check and cannot escalate. |
| **Secrets never leave the machine.** | Secret‑role fields (`AXSecureTextField`) and user‑declared apps are blanked in Touché and blacked out in Vue **before** serialization (`exclusions.py`), and the overlay redacts the same way (`overlay/presenter.py`). |
| **The overlay can't interfere.** | It runs in a separate process, is click‑through and capture‑invisible, and is a fire‑and‑forget sink — never on an action's critical path. |
| **You always win.** | Kill the process at any time; the physical override is final. Default ceiling is **L0** (hands off). |

## Hardening notes for operators

- Keep the ceiling as low as the task allows. L0/L1 for observation, L2 for
  routine input, L3 when you want to confirm every consequential click.
- L4 is for unattended runs you've explicitly engaged. The ledger is your audit
  trail — it lives in `~/Library/Application Support/Daimon/logs/`.
- Permissions attach to the **app that launches Daimon** (your terminal / IDE /
  AI app), not to `Daimon.app`. Grant Screen Recording / Accessibility only to
  the host you intend to drive. See [ARCHITECTURE.md](ARCHITECTURE.md#permissions--tcc).
- The release DMG is a signed Developer ID build, notarized and stapled by Apple.
  Verify with `spctl --assess --type install -v Daimon-<version>.dmg`.
