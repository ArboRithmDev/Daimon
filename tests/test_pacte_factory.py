from daimon.pacte.factory import build_pacte
from daimon.pacte.organ import Pacte


def test_build_pacte_returns_registerable_organ():
    p = build_pacte()
    assert isinstance(p, Pacte)


def test_build_pacte_registers_all_tools():
    class Rec:
        def __init__(self): self.names = []
        def tool(self, name=None, description=None):
            self.names.append(name)
            def deco(fn): return fn
            return deco
    rec = Rec()
    build_pacte().register(rec)
    assert set(rec.names) == {"pacte_describe", "pacte_probe", "pacte_act",
                              "pacte_capture", "pacte_expect", "pacte_events"}
