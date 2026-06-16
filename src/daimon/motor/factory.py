"""Build a fully-wired MotorOrgan + ConsentManager from config (real backends)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .. import backends
from ..config import load_motor_config
from ..config import load_config as load_exclusions
from ..config import load_overlay_config
from ..exclusions import ExclusionFilter
from ..overlay.presenter import NullPresenter, OverlayPresenter
from .audit import AppendOnlyLedger
from .consent import ConsentManager
from .guard import PolicyGuard
from .organ import MotorOrgan
from ..userdata import config_dir, logs_dir


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_consent() -> ConsentManager:
    """Construct the ConsentManager wired to the real ledger and state file."""
    mcfg = load_motor_config()
    logs = logs_dir()
    state = config_dir() / "motor.state.json"
    logs.mkdir(parents=True, exist_ok=True)
    state.parent.mkdir(parents=True, exist_ok=True)
    return ConsentManager(
        config_ceiling=mcfg.ceiling,
        engagement_phrase=mcfg.engagement_phrase,
        disengagement_phrase=mcfg.disengagement_phrase,
        ledger=AppendOnlyLedger(logs / "consent.jsonl"),
        state_path=state,
    )


def build_organ() -> MotorOrgan:
    """Assemble the fully-wired MotorOrgan with real macOS backends from config."""
    consent = build_consent()
    exclusions = ExclusionFilter(load_exclusions().exclusions)
    guard = PolicyGuard(exclusions, ceiling_provider=consent.current_ceiling)
    logs = logs_dir()
    logs.mkdir(parents=True, exist_ok=True)
    ocfg = load_overlay_config()
    if ocfg.enabled:
        launcher = backends.build_overlay_launcher()
        launcher.ensure_running()
        presenter = OverlayPresenter(launcher.make_client(), exclusions)
    else:
        presenter = NullPresenter()
    return MotorOrgan(
        guard=guard,
        gate=backends.build_gate(),
        actuator=backends.build_actuator(),
        session_log=AppendOnlyLedger(logs / "session.jsonl"),
        clock=_now,
        prober=backends.build_prober(),
        presenter=presenter,
    )
