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
        "- If you can spawn sub-agents: run the returned subagent_prompt on the smallest, "
        "fastest model you have that can reliably click and read; keep its screenshots inside "
        "the sub-agent and bubble up only the extracted text.\n"
        "- If you cannot spawn sub-agents: run the same prompt inline with your current model.\n"
        "Always drive with space='image' + display=k (Daimon resolves pixels itself — never "
        "reason about coordinates); Daimon enforces the L0-L4 Hands ceiling and secret redaction "
        "regardless. If the gate is not ready, calibrate first (vue_calibrate); do not drive blind."
    )
