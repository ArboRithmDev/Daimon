from daimon.tray.state import ClientStatus, TrayState
from daimon.motor.types import Level


def test_tray_state_holds_fields():
    s = TrayState(
        version="1.2.3", screen_ok=True, accessibility_ok=False,
        clients=(ClientStatus("Claude Code", True), ClientStatus("Cursor", False)),
        ceiling=Level.INPUT, l4_active=False, overlay_on=True,
    )
    assert s.version == "1.2.3"
    assert s.screen_ok and not s.accessibility_ok
    assert s.clients[0].registered and not s.clients[1].registered
    assert s.ceiling == Level.INPUT and s.overlay_on and not s.l4_active
