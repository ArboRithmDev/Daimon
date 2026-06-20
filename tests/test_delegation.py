import re
from daimon.senses.delegation import delegation_protocol_text

_BRANDS = re.compile(r"haiku|claude|gpt|gemini|opus|sonnet|llama|mistral", re.I)


def test_protocol_text_is_agnostic_and_tiered():
    txt = delegation_protocol_text()
    assert txt.strip()
    assert not _BRANDS.search(txt), "protocol must name no model/brand"
    low = txt.lower()
    assert "vue_pilot_brief" in low
    assert "sub-agent" in low or "subagent" in low      # tier 1: delegate
    assert "inline" in low                               # tier 2: run inline
    assert "vue_calibrate" in low                        # go/no-go fallback
    assert "space='image'" in txt or 'space="image"' in txt
