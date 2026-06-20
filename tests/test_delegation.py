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
    assert out["mode_hint"] == "delegate_to_a_model_capable_of_reliable_multi_step_tool_calling_else_run_inline"
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


# Task 4: Hands ceiling awareness in delegation surfaces
def test_server_instructions_mention_hands_ceiling():
    instr = build_server_instructions()
    assert "main_ceiling" in instr
    assert "ceiling" in instr.lower()
    assert not _BRANDS.search(instr)


def test_subagent_prompt_tells_it_to_check_the_ceiling():
    brief = {
        "matched": True, "active_profile": "p", "signature": "s", "expected_ok": True,
        "displays": [{"index": 0, "width": 100, "height": 100, "is_main": True,
                      "origin_x": 0, "origin_y": 0, "dpi": 96}],
    }
    p = pilot_brief(brief, "read the total")["subagent_prompt"]
    assert "main_ceiling" in p


# --- Task 6: a capable model MUST delegate multi-step driving --------------
def test_protocol_makes_multistep_delegation_imperative():
    txt = delegation_protocol_text()
    low = txt.lower()
    assert "must delegate" in low                                  # imperative for driving
    assert "one-shot" in low or "single vue_snapshot" in low       # perception exemption
    assert "inline" in low                                         # the no-subagent fallback stays
    assert _BRANDS.search(txt) is None


# --- Stream B: robustness against weak/hallucinating drivers ---------------
def test_protocol_reframes_to_capability_not_smallest():
    txt = delegation_protocol_text().lower()
    assert "reliable multi-step tool-calling" in txt
    assert "not necessarily your smallest" in txt
    assert _BRANDS.search(txt) is None


def test_server_instructions_steer_to_mcp_tools_not_shell_cli():
    instr = build_server_instructions()
    low = instr.lower()
    assert "mcp tool" in low
    assert "toolsearch" in low or "load them first" in low          # deferred-tool loading
    assert "shell" in low and "daimon" in instr                     # forbid `daimon ...` shell
    assert "never run" in low
    assert _BRANDS.search(instr) is None


def test_subagent_prompt_loads_deferred_tools_and_forbids_shell():
    brief = {
        "matched": True, "active_profile": "p", "signature": "s", "expected_ok": True,
        "displays": [{"index": 0, "width": 100, "height": 100, "is_main": True,
                      "origin_x": 0, "origin_y": 0, "dpi": 96}],
    }
    p = pilot_brief(brief, "read the total")["subagent_prompt"]
    low = p.lower()
    assert "toolsearch" in low or "deferred" in low                 # step 0: load the tools
    assert "shell" in low                                           # forbid shelling out
    assert "do not" in low and "call them" in low                  # anti-abandon
    assert _BRANDS.search(p) is None
