"""Build a fully-wired MotorOrgan + ConsentManager from config (real backends)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ..config import load_motor_config
from ..config import load_config as load_exclusions
from ..config import load_overlay_config
from ..exclusions import ExclusionFilter
from ..overlay import launcher
from ..overlay.client import OverlayClient
from ..overlay.presenter import NullPresenter, OverlayPresenter
from .actuator import MacOSActuator
from .audit import AppendOnlyLedger
from .consent import ConsentManager
from .gate import MacOSGate
from .guard import PolicyGuard
from .organ import MotorOrgan
from .probe import MacOSProber
from ..userdata import config_dir, logs_dir

_LOGS = logs_dir()
_STATE = config_dir() / "motor.state.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_consent() -> ConsentManager:
    mcfg = load_motor_config()
    _LOGS.mkdir(parents=True, exist_ok=True)
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    return ConsentManager(
        config_ceiling=mcfg.ceiling,
        engagement_phrase=mcfg.engagement_phrase,
        disengagement_phrase=mcfg.disengagement_phrase,
        ledger=AppendOnlyLedger(_LOGS / "consent.jsonl"),
        state_path=_STATE,
    )


def build_organ() -> MotorOrgan:
    consent = build_consent()
    exclusions = ExclusionFilter(load_exclusions().exclusions)
    guard = PolicyGuard(exclusions, ceiling_provider=consent.current_ceiling)
    _LOGS.mkdir(parents=True, exist_ok=True)
    ocfg = load_overlay_config()
    if ocfg.enabled:
        launcher.ensure_running()
        presenter = OverlayPresenter(OverlayClient(launcher.socket_path()), exclusions)
    else:
        presenter = NullPresenter()
    return MotorOrgan(
        guard=guard,
        gate=MacOSGate(),
        actuator=MacOSActuator(),
        session_log=AppendOnlyLedger(_LOGS / "session.jsonl"),
        clock=_now,
        prober=MacOSProber(),
        presenter=presenter,
    )
