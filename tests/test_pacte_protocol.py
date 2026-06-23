import pytest
from daimon.pacte.protocol import build_request, parse_response, ProtocolError, PROTOCOL_VERSION


def test_build_request_is_jsonrpc_2_and_carries_token():
    req = build_request("probe", {"fields": ["dirty"]}, token="abc", rid=7)
    assert req == {
        "jsonrpc": "2.0", "id": 7, "method": "probe",
        "params": {"fields": ["dirty"], "token": "abc"},
    }


def test_parse_response_returns_result_on_matching_id():
    assert parse_response({"jsonrpc": "2.0", "id": 7, "result": {"dirty": True}}, rid=7) == {"dirty": True}


def test_parse_response_raises_on_id_mismatch():
    with pytest.raises(ProtocolError):
        parse_response({"jsonrpc": "2.0", "id": 9, "result": {}}, rid=7)


def test_parse_response_raises_on_error_object():
    with pytest.raises(ProtocolError):
        parse_response({"jsonrpc": "2.0", "id": 7, "error": {"code": -32000, "message": "bad verb"}}, rid=7)


def test_protocol_version_is_one():
    assert PROTOCOL_VERSION == "1.0"
