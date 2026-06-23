from daimon.motor.types import MotorAction, Target, Declaration, Level
from daimon.pacte.actuator import CooperativeActuator
from daimon.pacte.client import CooperativeClient
from tests.fakes.cooperative_endpoint import FakeCooperativeEndpoint


def test_actuator_sends_act_verb_and_args():
    fake = FakeCooperativeEndpoint(token="secret")
    fake.handlers["act"] = lambda p: {"ok": True, "verb": p["verb"], "args": p["args"]}
    ep = fake.start()
    try:
        actuator = CooperativeActuator(CooperativeClient(ep))
        action = MotorAction(
            name="drag", level=Level.INPUT, target=Target(observed=True),
            declaration=Declaration(reversible=True, intent="move node"),
            params={"args": {"target": "n1", "to": {"scene_x": 10, "scene_y": 20}}},
        )
        result = actuator.execute(action)
        assert result == {"ok": True, "verb": "drag", "args": {"target": "n1", "to": {"scene_x": 10, "scene_y": 20}}}
    finally:
        fake.stop()
