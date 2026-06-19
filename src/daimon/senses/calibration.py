"""Pure calibration core — environment signature, profile model, match logic.

OS-agnostic, no screen access. This is the deterministic core of AXE 2: capture
the screen *topology* once per environment, persist it under a named profile,
and auto-match the active environment at boot via a stable signature.

Why a profile and not a single scale factor: the topology changes by location
(desk 3 screens / laptop alone / wide remote) and DPI is mixed across displays,
so one factor can't serve them all. A profile freezes the per-display
origin/size/dpi; the active profile then feeds AXE 1's coord resolution
(`coord_space_from_profile`) so offset/scale are read from the saved layout
instead of being re-probed.

The signature is a deterministic hash of the *layout only* — display count plus,
per display, its size, global position, dpi and main-flag. It deliberately
ignores `display_id` and active-list `index`, which are volatile hardware
handles: the same physical arrangement must yield the same environment identity
regardless of probe order or which port a cable landed in.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from ..capture.coordspace import CoordSpace

#: bump if the serialized profile schema changes shape
PROFILE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class DisplayProfile:
    """One display's frozen geometry within a saved environment profile.

    Mirrors the load-bearing fields of `capture.screen.Display` (origin, size,
    dpi, main-flag) but drops the volatile `display_id`/`index` from identity —
    `index` is kept only as the stable position in the captured list so the
    coord resolution can address "display k" the same way a live probe would.
    """

    index: int
    width: int
    height: int
    is_main: bool
    origin_x: int
    origin_y: int
    dpi: int

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "width": self.width,
            "height": self.height,
            "is_main": self.is_main,
            "origin_x": self.origin_x,
            "origin_y": self.origin_y,
            "dpi": self.dpi,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DisplayProfile":
        return cls(
            index=int(d["index"]),
            width=int(d["width"]),
            height=int(d["height"]),
            is_main=bool(d["is_main"]),
            origin_x=int(d["origin_x"]),
            origin_y=int(d["origin_y"]),
            dpi=int(d["dpi"]),
        )


@dataclass(frozen=True)
class EnvironmentProfile:
    """A named, persisted screen topology + its deterministic signature.

    `name` is human-chosen (e.g. `bureau-3-ecrans`). `signature` is the hash of
    the layout; it is what auto-matches the active environment at boot.
    """

    name: str
    signature: str
    displays: tuple[DisplayProfile, ...]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "signature": self.signature,
            "displays": [d.to_dict() for d in self.displays],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EnvironmentProfile":
        return cls(
            name=str(d["name"]),
            signature=str(d["signature"]),
            displays=tuple(DisplayProfile.from_dict(x) for x in d.get("displays", [])),
        )


def _layout_key(displays) -> list[tuple]:
    """The canonical, order-independent layout descriptor used for hashing.

    Each display contributes (origin_x, origin_y, width, height, dpi, is_main);
    the list is sorted so probe/list order can't change the identity. Volatile
    `display_id`/`index` are excluded on purpose.
    """
    return sorted(
        (d.origin_x, d.origin_y, d.width, d.height, d.dpi, bool(d.is_main))
        for d in displays
    )


def environment_signature(displays) -> str:
    """Deterministic 16-hex signature of a topology (count + per-display layout).

    Accepts either live `Display`s or `DisplayProfile`s — only the geometry
    fields are read, which both expose. Same physical arrangement -> same hash,
    regardless of order, display_id, or active-list index.
    """
    payload = json.dumps(
        {"count": len(list(displays)), "layout": _layout_key(displays)},
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def profile_from_displays(name: str, displays) -> EnvironmentProfile:
    """Freeze a live display list into a named profile (capture step).

    Displays are stored in their captured order; the signature is computed from
    the order-independent layout so a later probe in any order still matches.
    """
    dps = tuple(
        DisplayProfile(
            index=d.index,
            width=d.width,
            height=d.height,
            is_main=bool(d.is_main),
            origin_x=d.origin_x,
            origin_y=d.origin_y,
            dpi=d.dpi,
        )
        for d in displays
    )
    return EnvironmentProfile(
        name=name,
        signature=environment_signature(displays),
        displays=dps,
    )


def match_profile(profiles, displays) -> EnvironmentProfile | None:
    """Return the profile whose signature matches the active topology, or None.

    The active environment is hashed once; the first profile with that signature
    wins (names are unique in the store, so there is at most one). None means an
    unknown environment — the caller should propose creating a profile.
    """
    sig = environment_signature(displays)
    for prof in profiles:
        if prof.signature == sig:
            return prof
    return None


def active_profile_brief(store, displays, expected: str | None = None) -> dict:
    """The flat, decision-free brief a delegated sub-agent boots from (AXE 5).

    A big-model orchestrator hands a small-model sub-agent only a profile *name*.
    That sub-agent must not reason about geometry; it only needs to confirm the
    handed-down name is the one auto-matched to the live topology and learn which
    display indices it may address. This builds exactly that, from the pure core:

    - ``matched`` / ``active_profile`` / ``signature``: the profile auto-matched
      to ``displays`` (by signature), or None when the environment is unknown;
    - ``expected_ok``: True when ``expected`` is omitted OR equals the matched
      profile name — the sub-agent's go/no-go gate (drive only if True);
    - ``displays``: the addressable indices + their stored geometry, so the
      sub-agent picks ``display=k`` for the Hands without any offset/scale math.

    ``store`` only needs ``.match(displays)`` (real or Fake); ``displays`` is the
    live topology, injected — this helper never touches the screen itself.
    """
    matched = store.match(displays)
    if matched is None:
        return {
            "matched": False,
            "active_profile": None,
            "signature": environment_signature(displays),
            "expected_ok": False,
            "displays": [],
        }
    expected_ok = expected is None or expected == matched.name
    return {
        "matched": True,
        "active_profile": matched.name,
        "signature": matched.signature,
        "expected_ok": expected_ok,
        "displays": [d.to_dict() for d in matched.displays],
    }


def coord_space_from_profile(profile: EnvironmentProfile, display_index: int,
                             max_width: int | None = 720,
                             region: dict | None = None) -> CoordSpace:
    """Build AXE 1's reprojection coord-space from a saved profile (no probe).

    This is the bridge to AXE 1: instead of re-probing the screen, the active
    profile supplies the per-display origin and the source width, so the
    downscale ratio and region offset are derived exactly as a live snapshot
    would, purely from stored geometry.
    """
    by_index = {d.index: d for d in profile.displays}
    d = by_index.get(display_index)
    if d is None:
        valid = sorted(by_index)
        raise IndexError(
            f"display_index {display_index} not in profile {profile.name!r} "
            f"(have {valid})"
        )
    source_w = int(region["width"]) if region else d.width
    image_scale = max_width / source_w if (max_width and source_w > max_width) else 1.0
    rx = int(region["x"]) if region else 0
    ry = int(region["y"]) if region else 0
    return CoordSpace(
        display_origin_x=d.origin_x,
        display_origin_y=d.origin_y,
        image_scale=image_scale,
        region_x=rx,
        region_y=ry,
    )
