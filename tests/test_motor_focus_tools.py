# tests/test_motor_focus_tools.py
"""Tool-level wiring for F3 (focus) and F4 (targeted navigate).

A recording fake organ captures the MotorAction each Hand builds, so we assert
the window descriptor / ensure_focus flag / navigate point reach the organ —
without any real input or OS backend.
"""
import asyncio

import pytest

from daimon import server


class _RecordingOrgan:
    def __init__(self):
        self.actions = []

    def act(self, action):
        self.actions.append(action)
        return {"status": "done"}


def _tools_with_recording_organ(monkeypatch):
    organ = _RecordingOrgan()
    monkeypatch.setattr(server, "build_organ", lambda: organ)
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("daimon-test")
    server._register_motor(mcp)
    return organ, mcp


def _call(mcp, name, **kwargs):
    # FastMCP keeps the original function on the tool manager.
    tool = mcp._tool_manager.get_tool(name)
    return tool.fn(**kwargs)


def test_main_click_passes_window_and_ensure_focus(monkeypatch):
    organ, mcp = _tools_with_recording_organ(monkeypatch)
    _call(mcp, "main_click", x=10, y=20, intent="click tab",
          window_bundle="com.acme.editor", ensure_focus=True)
    act = organ.actions[0]
    assert act.params["window"] == {"bundle": "com.acme.editor"}
    assert act.params["ensure_focus"] is True


def test_main_click_without_window_has_no_focus_keys(monkeypatch):
    organ, mcp = _tools_with_recording_organ(monkeypatch)
    _call(mcp, "main_click", x=1, y=2, intent="plain click")
    act = organ.actions[0]
    assert "window" not in act.params
    assert "ensure_focus" not in act.params


def test_main_navigate_carries_target_point(monkeypatch):
    organ, mcp = _tools_with_recording_organ(monkeypatch)
    _call(mcp, "main_navigate", intent="scroll editor", scroll_y=-120, x=800, y=400)
    act = organ.actions[0]
    assert act.params["scroll_y"] == -120
    assert act.params["x"] == 800 and act.params["y"] == 400


def test_main_navigate_without_point_omits_xy(monkeypatch):
    organ, mcp = _tools_with_recording_organ(monkeypatch)
    _call(mcp, "main_navigate", intent="scroll", scroll_y=60)
    act = organ.actions[0]
    assert "x" not in act.params and "y" not in act.params


def test_main_press_supports_focus(monkeypatch):
    organ, mcp = _tools_with_recording_organ(monkeypatch)
    _call(mcp, "main_press", x=5, y=6, intent="press", window_title="Editor")
    assert organ.actions[0].params["window"] == {"title": "Editor"}
