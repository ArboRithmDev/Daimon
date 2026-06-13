# tests/test_overlay_presenter.py
from daimon.config import ExclusionConfig
from daimon.exclusions import ExclusionFilter
from daimon.overlay.presenter import NullPresenter, RecordingPresenter, OverlayPresenter
from daimon.overlay.protocol import Highlight, Banner, Ripple
from daimon.motor.types import Declaration, Decision, Level, MotorAction, Target, Verdict


def _action(label, role="AXButton", x=10, y=20):
    return MotorAction(name="click", level=Level.INPUT,
                       target=Target(role=role, label=label, x=x, y=y, observed=True),
                       declaration=Declaration(reversible=True, intent="submit the form"),
                       params={"x": x, "y": y})


class _Sink:
    def __init__(self): self.lines = []
    def send(self, command): self.lines.append(command)


def test_null_presenter_is_noop():
    p = NullPresenter()
    p.present_intent(_action("Send"), Decision(Verdict.ALLOW, "ok"))  # must not raise
    p.present_gate(_action("Send")); p.present_executed(_action("Send"), {}); p.present_refused(_action("Send"), "x")


def test_overlay_presenter_emits_highlight_and_banner_on_intent():
    sink = _Sink()
    p = OverlayPresenter(sink, ExclusionFilter(ExclusionConfig()))
    p.present_intent(_action("Send"), Decision(Verdict.ALLOW, "ok"))
    kinds = [type(c) for c in sink.lines]
    assert Highlight in kinds and Banner in kinds
    hi = next(c for c in sink.lines if isinstance(c, Highlight))
    assert "Send" in hi.label and "submit the form" in next(c for c in sink.lines if isinstance(c, Banner)).text


def test_gate_uses_gate_style():
    sink = _Sink()
    p = OverlayPresenter(sink, ExclusionFilter(ExclusionConfig()))
    p.present_gate(_action("Send"))
    hi = next(c for c in sink.lines if isinstance(c, Highlight))
    assert hi.style == "gate"


def test_secret_target_label_is_redacted():
    sink = _Sink()
    f = ExclusionFilter(ExclusionConfig(secret_roles=("AXSecureTextField",)))
    p = OverlayPresenter(sink, f)
    p.present_intent(_action("hunter2", role="AXSecureTextField"), Decision(Verdict.ALLOW, "ok"))
    hi = next(c for c in sink.lines if isinstance(c, Highlight))
    assert "hunter2" not in hi.label and "🔒" in hi.label


def test_executed_emits_ripple():
    sink = _Sink()
    p = OverlayPresenter(sink, ExclusionFilter(ExclusionConfig()))
    p.present_executed(_action("Send"), {"status": "executed"})
    assert any(isinstance(c, Ripple) for c in sink.lines)


def test_l4_action_uses_l4_style():
    sink = _Sink()
    p = OverlayPresenter(sink, ExclusionFilter(ExclusionConfig()))
    action = MotorAction(name="click", level=Level.AUTONOMOUS,
                         target=Target(role="AXButton", label="Delete", x=10, y=20, observed=True),
                         declaration=Declaration(reversible=False, intent="delete everything"),
                         params={"x": 10, "y": 20})
    p.present_intent(action, Decision(Verdict.ALLOW, "ok"))
    hi = next(c for c in sink.lines if isinstance(c, Highlight))
    assert hi.style == "L4"
