"""Overlay — Daimon's "show" organ.

A separate helper process draws a premium, click-through, capture-invisible
overlay; the MCP server drives it over a Unix-socket JSON protocol via an
injected Presenter. Purely presentational: it never acts, never intercepts
input, never leaks secret content, and is never on an action's critical path.
"""
