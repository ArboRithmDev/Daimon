from daimon.motor.reversibility import classify
from daimon.motor.types import Declaration, Level, MotorAction, Target


def _drag(dest_label):
    # the organ sets the observed target to the destination element (Task 6 / MacOSProber)
    return MotorAction(name="drag", level=Level.INPUT,
                       target=Target(role="AXImage", label=dest_label, observed=True),
                       declaration=Declaration(reversible=True, intent="x"),
                       params={"from_x": 0, "from_y": 0, "to_x": 9, "to_y": 9})


def test_drag_onto_trash_is_irreversible():
    assert classify(_drag("Trash")).irreversible
    assert classify(_drag("Corbeille")).irreversible


def test_drag_onto_plain_target_is_reversible():
    assert not classify(_drag("Folder A")).irreversible


def test_trash_regex_no_over_match():
    # "bin" must not match inside longer words
    assert not classify(_drag("cabinet")).irreversible
    assert not classify(_drag("binder")).irreversible
    # standalone "bin" should match (it is a trash synonym)
    assert classify(_drag("bin")).irreversible
