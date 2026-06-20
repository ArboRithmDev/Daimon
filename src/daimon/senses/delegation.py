"""Agnostic, AI-free delegation contract surfaced through the MCP protocol (AXE 5b).

Daimon never calls an LLM. It only describes — in model-agnostic terms — how an
orchestrator should hand a UI-driving task to a cheaper/faster sub-agent (or run it
inline if it cannot spawn one). The text here is injected into the MCP
server-instructions; the per-task packet is built by pilot_brief().
"""

from __future__ import annotations


def delegation_protocol_text() -> str:
    """The agnostic delegation section injected into the MCP server-instructions."""
    return (
        "## Delegating UI-driving tasks\n"
        "For multi-step tasks that drive an on-screen UI and extract text, first call "
        "vue_pilot_brief(objective, expected=<profile name if known>) to get a go/no-go "
        "gate plus a ready-to-paste sub-agent prompt.\n"
        "- If you can spawn sub-agents: run the returned subagent_prompt on a model capable of "
        "reliable multi-step tool-calling — NOT necessarily your smallest. A model that cannot "
        "reliably chain tool calls will stall or hallucinate a CLI instead of calling the tools; "
        "if your cheapest model does that, step up a tier. Keep its screenshots inside the "
        "sub-agent and bubble up only the extracted text.\n"
        "- If you cannot spawn sub-agents: run the same prompt inline with your current model.\n"
        "Always drive with space='image' + display=k (Daimon resolves pixels itself — never "
        "reason about coordinates); Daimon enforces the L0-L4 Hands ceiling and secret redaction "
        "regardless. If the gate is not ready, calibrate first (vue_calibrate); do not drive blind."
    )


_RULES = [
    "Use space='image' + display=k from the brief; never reason about pixel geometry.",
    "Keep screenshots in your own context; return only the extracted text.",
    "Daimon enforces the L0-L4 Hands ceiling and secret redaction; never try to raise the ceiling.",
]

_MODE_HINT = "delegate_to_a_model_capable_of_reliable_multi_step_tool_calling_else_run_inline"


def hands_ceiling_note() -> str:
    """Agnostic note: know your authorization envelope before acting."""
    return (
        "## Hands authorization ceiling\n"
        "Daimon enforces a Hands ceiling (L0–L4). Call main_ceiling before driving to learn the "
        "active ceiling and which tools are above it (gated_above). An action above the ceiling is "
        "refused — declare up-front that you cannot do it rather than attempting and being refused "
        "mid-flow. You never raise the ceiling; only the human does."
    )


def _subagent_prompt(profile: str, indices: list[int], objective: str) -> str:
    addr = ", ".join(f"display={i}" for i in indices)
    return (
        f"You are driving a UI through the Daimon MCP tools. Active calibration profile: "
        f"'{profile}'. Addressable displays: {addr}.\n"
        f"Objective: {objective}\n"
        "How to act:\n"
        "- Step 0 — load the tools: these are real MCP tools (vue_snapshot, vue_find, main_click, "
        "main_ceiling, …). In a fresh sub-agent thread they may be deferred — load them first "
        "(ToolSearch select the mcp daimon tools), then CALL them. They ARE callable: do not "
        "explain that you cannot call tools, and never run a `daimon ...` shell command — there is "
        "no such CLI; only the MCP tools perceive and act.\n"
        "- First call main_ceiling to learn your authorization envelope; do not attempt actions "
        "listed in gated_above — report them as out of scope instead.\n"
        "- Perceive with vue_snapshot(display=k) and read the labels. For apps with no "
        "accessibility tree, call vue_find(text=...) to get a clickable target.\n"
        "- Act with main_click/main_type using space='image' and the display index; Daimon "
        "resolves pixels to global itself. Never compute or pass raw global coordinates.\n"
        "- " + "\n- ".join(_RULES) + "\n"
        "Return ONLY the text you were asked to extract, nothing else."
    )


def pilot_brief(profile_brief: dict, objective: str) -> dict:
    """Build the per-task delegation packet from an active_profile_brief() result."""
    objective = (objective or "").strip()
    if not objective:
        raise ValueError("pilot_brief needs a non-empty objective")
    matched = bool(profile_brief.get("matched"))
    expected_ok = bool(profile_brief.get("expected_ok"))
    ready = matched and expected_ok
    displays = profile_brief.get("displays") or []
    profile_name = profile_brief.get("active_profile")
    gate = {
        "matched": matched,
        "active_profile": profile_name,
        "expected_ok": expected_ok,
        "displays": displays,
    }
    contract = {
        "input": {"profile": profile_name, "objective": objective},
        "output": "extracted text only",
        "rules": list(_RULES),
    }
    if not ready:
        return {
            "gate": gate, "ready": False, "contract": contract,
            "subagent_prompt": "", "mode_hint": _MODE_HINT,
            "next": ("Environment does not match the expected profile. Call "
                     "vue_calibrate(name=...) to register/select the right profile first; "
                     "do not drive blind."),
        }
    indices = [d["index"] for d in displays]
    return {
        "gate": gate, "ready": True, "contract": contract,
        "subagent_prompt": _subagent_prompt(profile_name, indices, objective),
        "mode_hint": _MODE_HINT,
        "next": ("Ready. If you can spawn a sub-agent, run subagent_prompt on a model capable of "
                 "reliable multi-step tool-calling (not necessarily your smallest); otherwise run "
                 "it inline."),
    }


def build_server_instructions() -> str:
    """The MCP server-instructions Daimon advertises to every client at connect."""
    return (
        "Daimon is a local perception + action organ for any AI client: see the screen "
        "(vue_*), read the accessibility tree (touche_*), act with the Hands (main_*), and "
        "show overlays (overlay_*). It is pull-only and calls no AI itself.\n\n"
        + using_daimon_note()
        + "\n\n"
        + delegation_protocol_text()
        + "\n\n"
        + hands_ceiling_note()
    )


def using_daimon_note() -> str:
    """How to actually invoke Daimon — MCP tools, never a shell CLI."""
    return (
        "## Using Daimon\n"
        "Daimon is used through its MCP tools — call vue_snapshot, vue_displays, touche_tree, "
        "main_click, overlay_* directly as tools. If your client lists them as deferred or "
        "unloaded, load them first (e.g. ToolSearch select the mcp daimon tools) before calling. "
        "There is NO `daimon` shell command for perception or action — never run `daimon ...` in a "
        "shell for these; it does not exist, will fail, and interrupts the user. The tools are "
        "callable; do not say you cannot call them — call them."
    )
