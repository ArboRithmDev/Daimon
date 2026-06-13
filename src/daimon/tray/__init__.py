"""Tray — Daimon's resident menu-bar control surface.

A native NSStatusItem app for day-to-day status + settings. Pure core (state /
menu model / settings writers) under a thin AppKit layer; the tray and the MCP
servers are separate processes that share state through config files.
"""
