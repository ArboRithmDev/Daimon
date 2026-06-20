import re as _re
import pytest
from daimon.senses.delegation import delegation_protocol_text, pilot_brief

_BRANDS = _re.compile(r"haiku|claude|gpt|gemini|opus|sonnet|llama|mistral", _re.I)


def test_protocol_text_is_agnostic_and_tiered():
    txt = delegation_protocol_text()
    assert txt.strip()
    assert not _BRANDS.search(txt), "protocol must name no model/brand"
    low = txt.lower()
    assert "vue_pilot_brief" in low
    assert "sub-agent" in low or "subagent" in low      # tier 1: delegate
    assert "inline" in low                               # tier 2: run inline
    assert "vue_calibrate" in low                        # go/no-go fallback
    assert "space='image'" in txt or 'space="image"' in txt


# Task 2: pilot_brief tests
_READY_BRIEF = {
    "matched": True, "active_profile": "bureau-3-ecrans", "signature": "abc",
    "expected_ok": True,
    "displays": [
        {"index": 0, "width": 1512, "height": 982, "is_main": True, "origin_x": 0, "origin_y": 0, "dpi": 255},
        {"index": 1, "width": 1600, "height": 900, "is_main": False, "origin_x": 1512, "origin_y": 34, "dpi": 239},
    ],
}
_UNMATCHED_BRIEF = {"matched": False, "active_profile": None, "signature": "z",
                    "expected_ok": False, "displays": []}
_MISMATCH_BRIEF = {**_READY_BRIEF, "expected_ok": False}


def test_pilot_brief_ready_builds_coord_free_prompt():
    out = pilot_brief(_READY_BRIEF, "open the invoice and read the total")
    assert out["ready"] is True
    assert out["mode_hint"] == "delegate_to_smallest_capable_subagent_else_run_inline"
    p = out["subagent_prompt"]
    assert "open the invoice and read the total" in p
    assert "display=0" in p and "display=1" in p
    assert not _re.search(r"\d+\s*,\s*\d+", p), "prompt must carry no coordinate pairs"
    assert _BRANDS.search(p) is None
    joined = " ".join(out["contract"]["rules"]).lower()
    assert "ceiling" in joined and "secret" in joined


def test_pilot_brief_not_ready_when_unmatched():
    out = pilot_brief(_UNMATCHED_BRIEF, "do X")
    assert out["ready"] is False
    assert out["subagent_prompt"] == ""
    assert "vue_calibrate" in out["next"]


def test_pilot_brief_not_ready_on_expected_mismatch():
    out = pilot_brief(_MISMATCH_BRIEF, "do X")
    assert out["ready"] is False
    assert "vue_calibrate" in out["next"]


def test_pilot_brief_rejects_empty_objective():
    with pytest.raises(ValueError):
        pilot_brief(_READY_BRIEF, "   ")


# Task 3: build_server_instructions tests
from daimon.senses.delegation import build_server_instructions


def test_server_instructions_carry_the_protocol():
    instr = build_server_instructions()
    assert "Daimon" in instr
    assert "vue_pilot_brief" in instr               # the delegation protocol is included
    assert not _BRANDS.search(instr)
