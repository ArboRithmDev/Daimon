"""AXE 5 helper: the active-profile brief a delegated sub-agent boots from.

The orchestrator (big model) hands a sub-agent only a PROFILE NAME. The
sub-agent must, without any geometric reasoning, confirm that name is the one
auto-matched to the live topology and learn which display index to act on. This
is exactly what `active_profile_brief` returns — a flat, decision-free summary
(matched bool, name, signature, the display indices it can address) built from
the pure calibration core, with no screen access of its own (displays injected).

Exercised with fake displays + a FakeProfileStore — no real screen, no disk.
"""

import pytest

from daimon.capture.screen import Display
from daimon.senses.calibration import active_profile_brief, profile_from_displays
from daimon.senses.calibration_store import FakeProfileStore


_DESK = [
    Display(index=0, display_id=1, width=1920, height=1080, is_main=True,
            origin_x=0, origin_y=0, dpi=96),
    Display(index=1, display_id=2, width=1920, height=1080, is_main=False,
            origin_x=-1920, origin_y=0, dpi=96),
]
_LAPTOP = [
    Display(index=0, display_id=9, width=1512, height=982, is_main=True,
            origin_x=0, origin_y=0, dpi=226),
]


def test_brief_confirms_the_expected_name_when_it_matches():
    store = FakeProfileStore()
    store.save(profile_from_displays("bureau-3-ecrans", _DESK))
    brief = active_profile_brief(store, _DESK, expected="bureau-3-ecrans")
    assert brief["matched"] is True
    assert brief["active_profile"] == "bureau-3-ecrans"
    assert brief["expected_ok"] is True
    # the sub-agent learns the display indices it can address, no geometry math
    assert [d["index"] for d in brief["displays"]] == [0, 1]
    assert brief["displays"][1]["is_main"] is False


def test_brief_flags_mismatch_between_expected_and_active():
    # The handed-down name does NOT match the live topology's profile: the
    # sub-agent must abort rather than drive blind. expected_ok is False.
    store = FakeProfileStore()
    store.save(profile_from_displays("bureau-3-ecrans", _DESK))
    brief = active_profile_brief(store, _DESK, expected="portable-seul")
    assert brief["matched"] is True
    assert brief["active_profile"] == "bureau-3-ecrans"
    assert brief["expected_ok"] is False


def test_brief_unknown_environment_has_no_active_profile():
    store = FakeProfileStore()
    store.save(profile_from_displays("portable-seul", _LAPTOP))
    brief = active_profile_brief(store, _DESK, expected="portable-seul")
    assert brief["matched"] is False
    assert brief["active_profile"] is None
    assert brief["expected_ok"] is False
    assert brief["displays"] == []


def test_brief_without_expected_just_reports_the_active_profile():
    store = FakeProfileStore()
    store.save(profile_from_displays("bureau-3-ecrans", _DESK))
    brief = active_profile_brief(store, _DESK)
    assert brief["matched"] is True
    assert brief["active_profile"] == "bureau-3-ecrans"
    # no expectation was asserted -> the check is vacuously satisfied
    assert brief["expected_ok"] is True


def test_brief_carries_the_signature_for_traceability():
    store = FakeProfileStore()
    prof = profile_from_displays("bureau-3-ecrans", _DESK)
    store.save(prof)
    brief = active_profile_brief(store, _DESK, expected="bureau-3-ecrans")
    assert brief["signature"] == prof.signature
