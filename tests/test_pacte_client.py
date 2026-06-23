import pytest
from daimon.pacte.client import CooperativeClient
from daimon.pacte.protocol import ProtocolError
from tests.fakes.cooperative_endpoint import FakeCooperativeEndpoint


def test_client_round_trips_a_method():
    fake = FakeCooperativeEndpoint(token="secret")
    fake.handlers["probe"] = lambda params: {"dirty": True, "echo": params.get("fields")}
    ep = fake.start()
    try:
        client = CooperativeClient(ep)
        result = client.call("probe", {"fields": ["dirty"]})
        assert result == {"dirty": True, "echo": ["dirty"]}
        assert fake.requests[-1]["params"]["token"] == "secret"
    finally:
        fake.stop()


def test_client_raises_on_bad_token():
    fake = FakeCooperativeEndpoint(token="secret")
    ep = fake.start()
    # tamper: present the wrong token
    from daimon.pacte.discovery import Endpoint
    bad = Endpoint(port=ep.port, token="wrong", pid=ep.pid, app=ep.app, protocol_version=ep.protocol_version)
    try:
        with pytest.raises(ProtocolError):
            CooperativeClient(bad).call("probe", {})
    finally:
        fake.stop()
