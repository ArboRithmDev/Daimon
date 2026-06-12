"""Common contract for senses.

A sense is read-only and stateless across calls: given the shared exclusion
filter, it produces a perception payload on demand. Keeping a tiny base lets
`server.py` register every sense the same way and guarantees the filter is
threaded through uniformly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..exclusions import ExclusionFilter


class Sense(ABC):
    #: short, stable name used as the MCP tool/resource identifier
    name: str

    def __init__(self, exclusions: ExclusionFilter) -> None:
        self._exclusions = exclusions

    @abstractmethod
    def register(self, mcp) -> None:
        """Register this sense's tools/resources on the FastMCP server."""
        raise NotImplementedError
