from daimon.overlay.protocol import (
    Highlight, Spotlight, Cursor, Ripple, Banner, Clear, encode, decode,
)


def test_highlight_round_trip():
    h = Highlight(x=10, y=20, w=80, h=30, label='AXButton "Send"', style="gate")
    line = encode(h)
    assert isinstance(line, str) and line.endswith("\n")
    back = decode(line)
    assert isinstance(back, Highlight) and back.label == 'AXButton "Send"' and back.style == "gate"


def test_each_command_encodes_its_cmd_tag():
    assert '"cmd": "ripple"' in encode(Ripple(x=1, y=2)) or '"cmd":"ripple"' in encode(Ripple(x=1, y=2))
    assert decode(encode(Banner(text="hi", level="L2"))).text == "hi"
    assert isinstance(decode(encode(Clear())), Clear)
    assert decode(encode(Spotlight(x=0, y=0, w=5, h=5))).w == 5
    assert decode(encode(Cursor(x=3, y=4))).y == 4


def test_decode_unknown_cmd_raises():
    import pytest
    with pytest.raises(ValueError):
        decode('{"cmd": "nope"}')
