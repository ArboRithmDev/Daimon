"""Daimon's independent point-of-no-return verdict.

Defense in depth: the AI *declares* reversibility per action; this module
computes Daimon's *own* verdict from the target. The guard reconciles the two
and the stricter wins. Pure — no macOS imports — so it is fully unit-tested.
"""

from __future__ import annotations

import re

from .types import Level, MotorAction, Reversibility, Target

# Multilingual verbs/labels that mark an engaging, typically irreversible action.
_DANGER_TEXT = re.compile(
    r"(?i)\b("
    r"send|envoyer|envoie|"
    r"delete|supprimer|effacer|remove|"
    r"empty|vider|"
    r"pay|payer|buy|acheter|purchase|"
    r"publish|publier|post|"
    r"confirm|confirmer|valider|"
    r"reset|réinitialiser|"
    r"destroy|détruire|discard|jeter|"
    r"submit|soumettre"
    r")\b"
)

# Key combinations that are destructive regardless of the target.
_DANGER_KEYS = re.compile(r"(?i)\bcmd\+(shift\+)?delete\b")


def _target_text(target: Target) -> str:
    return " ".join(p for p in (target.label, target.value, target.role) if p)


def classify(action: MotorAction) -> Reversibility:
    text = _target_text(action.target)
    if text and _DANGER_TEXT.search(text):
        return Reversibility(True, f"target matches non-return verb: {text!r}")

    keys = action.params.get("keys") or action.params.get("keystr")
    if not keys and action.params.get("key"):
        # Build the combo defensively so a directly-constructed key action can't
        # skip the danger check by omitting keystr.
        mods = action.params.get("modifiers") or []
        keys = "+".join([*mods, action.params["key"]])
    if keys and _DANGER_KEYS.search(keys):
        return Reversibility(True, f"dangerous key combo: {keys}")

    # Fail-safe: an unidentified target at INPUT level or above is treated as risky.
    # Keyboard actions are exempt by NAME (they target the keyboard, not a UI
    # element). Keyed off action.name — not a params probe — so a pointer action
    # cannot dodge the fail-safe by smuggling a bogus `key` param.
    identified = bool(action.target.role or action.target.label)
    is_key_action = action.name == "key"
    if action.level >= Level.INPUT and not identified and not is_key_action:
        return Reversibility(True, "unidentified target at input level (fail-safe)")

    return Reversibility(False, "no non-return signal")
