from daimon.motor.probe import _COORD_ACTIONS


def test_mouse_primitives_are_coord_actions():
    assert "mouse_down" in _COORD_ACTIONS
    assert "mouse_up" in _COORD_ACTIONS
