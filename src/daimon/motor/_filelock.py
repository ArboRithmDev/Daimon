"""Cross-platform exclusive advisory lock for the append-only ledger.

The ledger may be appended to by several Daimon processes (one MCP server per
AI client). The read-last-record + append step must be atomic across processes
or the hash chain could interleave. POSIX uses ``fcntl.flock`` (whole file);
Windows uses ``msvcrt.locking`` over a fixed nominal region from offset 0
(locking beyond EOF is permitted on Windows, and the ledger is small, so the
region comfortably covers every append). The lock is held only for the brief
critical section.
"""

from __future__ import annotations

import os
from contextlib import contextmanager

# Nominal region size for the Windows byte-range lock. Locking beyond EOF is
# allowed on Windows; the ledger never approaches this size.
_WIN_LOCK_BYTES = 0x10000000  # 256 MiB


@contextmanager
def exclusive_lock(f):
    """Hold an exclusive lock on the open file object ``f`` for the with-block.

    Best-effort on the unlock path: a failure to release (e.g. the region was
    never granted) must never mask the caller's own exception.
    """
    if os.name == "nt":
        import msvcrt

        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, _WIN_LOCK_BYTES)
        try:
            yield
        finally:
            try:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, _WIN_LOCK_BYTES)
            except OSError:
                pass
    else:
        import fcntl

        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
