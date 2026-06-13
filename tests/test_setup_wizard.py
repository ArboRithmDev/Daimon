from daimon.setup.wizard import Step, Wizard, RecordingIO


def test_already_satisfied_step_is_skipped():
    io = RecordingIO()
    done = {"x": True}
    s = Step(id="x", title="X", check=lambda: done["x"], act=lambda: io.say("acting"), guidance="g")
    assert Wizard([s]).run(io) is True
    assert "acting" not in "\n".join(io.lines)


def test_pending_step_acts_then_verifies():
    io = RecordingIO()
    flips = {"n": 0}
    def check():
        flips["n"] += 1
        return flips["n"] >= 3   # becomes true on the 3rd check (after act + polls)
    acted = []
    s = Step(id="p", title="Grant", check=check, act=lambda: acted.append(True), guidance="do it")
    ok = Wizard([s]).run(io, max_polls=5)
    assert ok is True and acted == [True]


def test_never_satisfied_gives_up():
    io = RecordingIO()
    s = Step(id="p", title="Grant", check=lambda: False, act=lambda: None, guidance="g")
    assert Wizard([s]).run(io, max_polls=3) is False


def test_steps_run_in_order():
    io = RecordingIO()
    order = []
    steps = [Step(id=str(i), title=f"S{i}", check=lambda: True,
                  act=lambda: None, guidance="") for i in range(3)]
    Wizard(steps).run(io)
    assert [l for l in io.lines if l.startswith("STEP")] == ["STEP S0", "STEP S1", "STEP S2"]
