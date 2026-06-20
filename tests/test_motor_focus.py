# tests/test_motor_focus.py
"""F3 — focus awareness for positional Hands.

A positional click issued before the target window is frontmost is a silent
no-op on the host. These seams make that observable: the organ either
auto-focuses the target window (ensure_focus) or surfaces an explicit
focus warning, so 'emitted, no effect' never masquerades as 'success'.
"""
from daimon.config import ExclusionConfig
from daimon.exclusions import ExclusionFilter
from daimon.motor.actuator import FakeActuator
from daimon.motor.audit import AppendOnlyLedger
from daimon.motor.focus import FakeFocusProbe, FocusState, window_is_frontmost
from daimon.motor.gate import FakeGate
from daimon.motor.guard import PolicyGuard
from daimon.motor.organ import MotorOrgan
from daimon.motor.probe import FakeProber
from daimon.motor.types import Declaration, Level, MotorAction, Target


def _organ(tmp_path, *, focus, observed=None, actuator=None, ceiling=Level.INPUT):
    guard = PolicyGuard(ExclusionFilter(ExclusionConfig()), ceiling_provider=lambda: ceiling)
    return MotorOrgan(
        guard=guard, gate=FakeGate(answer=True),
        actuator=actuator or FakeActuator(),
        session_log=AppendOnlyLedger(tmp_path / "s.jsonl"), clock=lambda: "T",
        prober=FakeProber(target=observed or Target(role="AXButton", label="Tab", observed=True)),
        focus_probe=focus,
    )


def _click(window=None, ensure_focus=False):
    params = {"x": 10, "y": 20}
    if window is not None:
        params["window"] = window
    if ensure_focus:
        params["ensure_focus"] = True
    return MotorAction(
        name="click", level=Level.INPUT,
        target=Target(role="AXButton", label="Tab", x=10, y=20),
        declaration=Declaration(reversible=True, intent="click a tab"),
        params=params,
    )


# --- pure matcher -----------------------------------------------------------

def test_window_is_frontmost_matches_bundle():
    fs = FocusState(bundle="com.acme.editor", title="Editor", pid=42)
    assert window_is_frontmost(fs, {"bundle": "com.acme.editor"}) is True
    assert window_is_frontmost(fs, {"bundle": "com.other"}) is False


def test_window_is_frontmost_matches_title_and_pid():
    fs = FocusState(bundle="com.acme.editor", title="Editor", pid=42)
    assert window_is_frontmost(fs, {"title": "Editor"}) is True
    assert window_is_frontmost(fs, {"pid": 42}) is True
    assert window_is_frontmost(fs, {"pid": 7}) is False


def test_window_is_frontmost_unknown_focus_is_false():
    assert window_is_frontmost(None, {"bundle": "x"}) is False


def test_no_target_window_means_no_judgement():
    # With no window declared, there is nothing to compare against → no warning.
    fs = FocusState(bundle="com.acme.editor", title="Editor", pid=42)
    assert window_is_frontmost(fs, {}) is None
    assert window_is_frontmost(fs, None) is None


# --- organ: warning path ----------------------------------------------------

def test_click_when_target_not_frontmost_warns(tmp_path):
    focus = FakeFocusProbe(state=FocusState(bundle="com.other", title="Other", pid=1))
    act = FakeActuator()
    organ = _organ(tmp_path, focus=focus, actuator=act)
    out = organ.act(_click(window={"bundle": "com.acme.editor"}))
    assert out["status"] == "done"          # the click is still emitted
    assert out.get("focus_warning") is True  # but flagged as possibly ineffective
    assert "frontmost" in out["focus_detail"].lower()
    assert act.executed and act.executed[0].name == "click"


def test_click_when_target_is_frontmost_no_warning(tmp_path):
    focus = FakeFocusProbe(state=FocusState(bundle="com.acme.editor", title="Editor", pid=42))
    organ = _organ(tmp_path, focus=focus)
    out = organ.act(_click(window={"bundle": "com.acme.editor"}))
    assert out["status"] == "done"
    assert "focus_warning" not in out


def test_click_without_window_never_warns(tmp_path):
    focus = FakeFocusProbe(state=FocusState(bundle="com.other", title="Other", pid=1))
    organ = _organ(tmp_path, focus=focus)
    out = organ.act(_click())  # no window declared
    assert out["status"] == "done"
    assert "focus_warning" not in out


def test_no_focus_probe_is_inert(tmp_path):
    # Back-compat: an organ wired without a focus probe behaves exactly as before.
    guard = PolicyGuard(ExclusionFilter(ExclusionConfig()), ceiling_provider=lambda: Level.INPUT)
    organ = MotorOrgan(
        guard=guard, gate=FakeGate(answer=True), actuator=FakeActuator(),
        session_log=AppendOnlyLedger(tmp_path / "s.jsonl"), clock=lambda: "T",
        prober=FakeProber(target=Target(observed=True)),
    )
    out = organ.act(_click(window={"bundle": "com.acme.editor"}))
    assert out["status"] == "done"
    assert "focus_warning" not in out


# --- organ: ensure_focus (auto-activate) path -------------------------------

def test_ensure_focus_activates_then_clicks(tmp_path):
    # The activation takes effect (fake flips), so the click is no longer flagged.
    focus = FakeFocusProbe(state=FocusState(bundle="com.other", title="Other", pid=1),
                           activates=True)
    act = FakeActuator()
    organ = _organ(tmp_path, focus=focus, actuator=act)
    out = organ.act(_click(window={"bundle": "com.acme.editor"}, ensure_focus=True))
    assert out["status"] == "done"
    # An activate must precede the click, and the focus is no longer flagged.
    names = [a.name for a in act.executed]
    assert names == ["activate", "click"]
    assert out.get("focused") is True
    assert "focus_warning" not in out
    # the activate targeted the requested window
    assert act.executed[0].params.get("bundle") == "com.acme.editor"


def test_ensure_focus_still_warns_if_activation_ineffective(tmp_path):
    # The activation does not take effect (fake does not flip) — the organ must
    # still issue the click but flag that the window never came forward.
    focus = FakeFocusProbe(state=FocusState(bundle="com.other", title="Other", pid=1))
    act = FakeActuator()
    organ = _organ(tmp_path, focus=focus, actuator=act)
    out = organ.act(_click(window={"bundle": "com.acme.editor"}, ensure_focus=True))
    assert [a.name for a in act.executed] == ["activate", "click"]
    assert out.get("focus_warning") is True
    assert out.get("focused") is True


def test_ensure_focus_noop_when_already_frontmost(tmp_path):
    focus = FakeFocusProbe(state=FocusState(bundle="com.acme.editor", title="Editor", pid=42))
    act = FakeActuator()
    organ = _organ(tmp_path, focus=focus, actuator=act)
    out = organ.act(_click(window={"bundle": "com.acme.editor"}, ensure_focus=True))
    assert [a.name for a in act.executed] == ["click"]  # no redundant activate
    assert out["status"] == "done"


def test_ensure_focus_marks_focus_after_activation(tmp_path):
    # The fake probe flips to the activated window after an activate is issued,
    # modelling the real activation effect; the organ must observe the change.
    focus = FakeFocusProbe(state=FocusState(bundle="com.other", title="Other", pid=1),
                           activates=True)
    act = FakeActuator()
    organ = _organ(tmp_path, focus=focus, actuator=act)
    out = organ.act(_click(window={"bundle": "com.acme.editor"}, ensure_focus=True))
    assert out.get("focused") is True
    assert "focus_warning" not in out


# --- organ: three-state focus result (T5) -----------------------------------
# A single `focus` key names the outcome so a pilot can branch on it without
# parsing warnings. It appears only when a window target makes focus relevant.

def test_focus_state_absent_when_focus_irrelevant(tmp_path):
    # No declared window, and no probe at all — focus is not applicable, so the
    # result carries no `focus` key (back-compat: the dict is otherwise unchanged).
    focus = FakeFocusProbe(state=FocusState(bundle="com.other", title="Other", pid=1))
    organ = _organ(tmp_path, focus=focus)
    out = organ.act(_click())  # no window declared
    assert "focus" not in out

    guard = PolicyGuard(ExclusionFilter(ExclusionConfig()), ceiling_provider=lambda: Level.INPUT)
    organ_no_probe = MotorOrgan(
        guard=guard, gate=FakeGate(answer=True), actuator=FakeActuator(),
        session_log=AppendOnlyLedger(tmp_path / "s.jsonl"), clock=lambda: "T",
        prober=FakeProber(target=Target(observed=True)),
    )
    out = organ_no_probe.act(_click(window={"bundle": "com.acme.editor"}))
    assert "focus" not in out


def test_focus_state_already_frontmost(tmp_path):
    # Window targeted and already frontmost → positive confirmation, no warning.
    focus = FakeFocusProbe(state=FocusState(bundle="com.acme.editor", title="Editor", pid=42))
    organ = _organ(tmp_path, focus=focus)
    out = organ.act(_click(window={"bundle": "com.acme.editor"}))
    assert out["focus"] == "already_frontmost"
    assert "focus_warning" not in out


def test_focus_state_not_attempted(tmp_path):
    # Not frontmost and ensure_focus off → no activation tried; explicitly flagged.
    focus = FakeFocusProbe(state=FocusState(bundle="com.other", title="Other", pid=1))
    organ = _organ(tmp_path, focus=focus)
    out = organ.act(_click(window={"bundle": "com.acme.editor"}))
    assert out["focus"] == "not_attempted"
    assert out.get("focus_warning") is True


def test_focus_state_activated_and_frontmost(tmp_path):
    # ensure_focus brings it forward and the activation takes effect.
    focus = FakeFocusProbe(state=FocusState(bundle="com.other", title="Other", pid=1),
                           activates=True)
    organ = _organ(tmp_path, focus=focus)
    out = organ.act(_click(window={"bundle": "com.acme.editor"}, ensure_focus=True))
    assert out["focus"] == "activated_and_frontmost"
    assert out.get("focused") is True
    assert "focus_warning" not in out


def test_focus_state_activated_but_not_frontmost(tmp_path):
    # ensure_focus issued an activate but the window never came forward.
    focus = FakeFocusProbe(state=FocusState(bundle="com.other", title="Other", pid=1))
    organ = _organ(tmp_path, focus=focus)
    out = organ.act(_click(window={"bundle": "com.acme.editor"}, ensure_focus=True))
    assert out["focus"] == "activated_but_not_frontmost"
    assert out.get("focused") is True
    assert out.get("focus_warning") is True
