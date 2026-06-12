"""Daimon — a local sensory organ for AI clients on macOS.

Daimon is an *organ*, not a driver. It never calls an AI and never owns a
perception loop. It exposes senses (Vue, Touché) over MCP; the AI client
pulls perception whenever it wants. Agnostic by construction: any MCP-capable
client (Claude, or any other) plugs in with no per-AI adapter.

Senses are read-only by contract. Daimon reports; it never clicks or types.
The motor organ ("the hands") is out of scope and lives elsewhere.
"""

__version__ = "0.0.1"
