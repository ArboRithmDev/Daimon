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


def test_key_action_ignores_focused_field_text_content():
    # Typing into a field whose existing text contains "delete" must NOT gate —
    # the field's content is not a destructiveness signal for a keystroke.
    field = Target(role="AXTextArea", label="editor", value="please delete and send everything")
    rev = classify(_action(field, name="key", params={"key": "a", "keystr": "a"}))
    assert not rev.irreversible


def test_type_action_ignores_focused_field_text_content():
    field = Target(role="AXTextField", label="message", value="supprimer le compte")
    rev = classify(_action(field, name="type"))
    assert not rev.irreversible


def test_key_dangerous_combo_still_gates_even_in_text_field():
    field = Target(role="AXTextArea", label="editor", value="harmless")
    rev = classify(_action(field, name="key",
                           params={"key": "delete", "modifiers": ["cmd"], "keystr": "cmd+delete"}))
    assert rev.irreversible


def test_click_still_uses_value():
    # Non-keyboard actions keep scanning value (a control whose value is a verb).
    rev = classify(_action(Target(role="AXButton", value="Delete"), name="click"))
    assert rev.irreversible
