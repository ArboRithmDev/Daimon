"""AXE 5 MCP tool: vue_profile_brief — what a delegated sub-agent boots from.

The orchestrator passes a sub-agent only a profile NAME (its `expected` arg).
The tool confirms that name is the one auto-matched to the live topology and
returns the addressable display indices, so the sub-agent drives mechanically
without any geometric reasoning. Wired against fake displays + a
FakeProfileStore — no real screen, no disk.
"""

from daimon.capture.screen import Display
from daimon.senses.calibration import profile_from_displays
from daimon.senses.calibration_store import FakeProfileStore


_DESK = [
    Display(index=0, display_id=1, width=1920, height=1080, is_main=True,
            origin_x=0, origin_y=0, dpi=96),
    Display(index=1, display_id=2, width=1920, height=1080, is_main=False,
            origin_x=-1920, origin_y=0, dpi=96),
]


class _FakeExclusions:
    def evaluate_frontmost(self, bundle):
        class _G:
            refused = False
            reason = ""
        return _G()

    def redact_image(self, image):
        return image


class _ToolReg:
    def __init__(self):
        self.tools = {}

    def tool(self, name, description=""):
        def deco(fn):
            self.tools[name] = fn
            return fn
        return deco


def _register(monkeypatch, displays, store):
    import daimon.capture.screen as screen
    from daimon.senses.vue import Vue
    monkeypatch.setattr(screen, "list_displays", lambda: displays)
    reg = _ToolReg()
    Vue(_FakeExclusions(), profile_store=store).register(reg)
    return reg


def test_profile_brief_tool_confirms_handed_down_name(monkeypatch):
    store = FakeProfileStore()
    store.save(profile_from_displays("bureau-3-ecrans", _DESK))
    reg = _register(monkeypatch, _DESK, store)
    out = reg.tools["vue_profile_brief"](expected="bureau-3-ecrans")
    assert out["matched"] is True
    assert out["expected_ok"] is True
    assert out["active_profile"] == "bureau-3-ecrans"
    assert [d["index"] for d in out["displays"]] == [0, 1]


def test_profile_brief_tool_flags_wrong_name(monkeypatch):
    store = FakeProfileStore()
    store.save(profile_from_displays("bureau-3-ecrans", _DESK))
    reg = _register(monkeypatch, _DESK, store)
    out = reg.tools["vue_profile_brief"](expected="portable-seul")
    assert out["matched"] is True
    assert out["expected_ok"] is False
