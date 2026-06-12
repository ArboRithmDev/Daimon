from daimon.motor.reversibility import classify
from daimon.motor.types import Declaration, Level, MotorAction, Target


def _action(target, name="click", level=Level.INPUT, params=None):
    return MotorAction(
        name=name, level=level, target=target,
        declaration=Declaration(reversible=True, intent="x"),
        params=params or {},
    )


def test_danger_verb_in_label_is_irreversible():
    for label in ["Send", "Envoyer", "Delete", "Supprimer", "Pay", "Payer", "Publier", "Empty Trash"]:
        rev = classify(_action(Target(role="AXButton", label=label)))
        assert rev.irreversible, label


def test_plain_label_is_reversible():
    rev = classify(_action(Target(role="AXButton", label="Cancel")))
    assert not rev.irreversible


def test_dangerous_key_combo_is_irreversible():
    rev = classify(_action(Target(role="AXTextArea", label="editor"),
                           name="navigate", level=Level.NONDESTRUCTIVE,
                           params={"keys": "cmd+delete"}))
    assert rev.irreversible


def test_unidentified_target_at_input_level_fails_safe():
    rev = classify(_action(Target()))  # no role, no label, INPUT level
    assert rev.irreversible
    assert "fail-safe" in rev.reason


def test_unidentified_target_at_navigate_level_is_ok():
    rev = classify(_action(Target(), name="navigate", level=Level.NONDESTRUCTIVE))
    assert not rev.irreversible
