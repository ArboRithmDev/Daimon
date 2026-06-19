"""Pure calibration core — environment signature, profile model, match logic.

No real screen, no OS. A profile captures the screen topology (per-display
origin/size/dpi) once; a deterministic signature lets Daimon auto-match the
active environment at boot. These tests pin the math and the matching so the
coord-space (AXE 1) can be served from a saved profile instead of re-probing.
"""

import pytest

from daimon.capture.screen import Display
from daimon.senses.calibration import (
    DisplayProfile,
    EnvironmentProfile,
    coord_space_from_profile,
    environment_signature,
    match_profile,
    profile_from_displays,
)


# --- fixture topologies -----------------------------------------------------

_DESK = [
    Display(index=0, display_id=1, width=1920, height=1080, is_main=True,
            origin_x=0, origin_y=0, dpi=96),
    Display(index=1, display_id=2, width=1920, height=1080, is_main=False,
            origin_x=-1920, origin_y=0, dpi=96),
    Display(index=2, display_id=3, width=2560, height=1440, is_main=False,
            origin_x=1920, origin_y=0, dpi=144),
]

_LAPTOP = [
    Display(index=0, display_id=9, width=1512, height=982, is_main=True,
            origin_x=0, origin_y=0, dpi=226),
]


# --- environment_signature: deterministic over the layout -------------------


def test_signature_is_deterministic():
    sig1 = environment_signature(_DESK)
    sig2 = environment_signature(list(_DESK))
    assert sig1 == sig2
    assert isinstance(sig1, str) and len(sig1) == 16


def test_signature_independent_of_display_id_and_index_order():
    # display_id is a volatile hardware handle; reordering the active-list must
    # not change the environment identity as long as the layout is the same.
    shuffled = [
        Display(index=5, display_id=999, width=1920, height=1080, is_main=False,
                origin_x=-1920, origin_y=0, dpi=96),
        Display(index=7, display_id=111, width=2560, height=1440, is_main=False,
                origin_x=1920, origin_y=0, dpi=144),
        Display(index=2, display_id=222, width=1920, height=1080, is_main=True,
                origin_x=0, origin_y=0, dpi=96),
    ]
    assert environment_signature(shuffled) == environment_signature(_DESK)


def test_signature_changes_with_count():
    assert environment_signature(_DESK) != environment_signature(_DESK[:2])


def test_signature_changes_with_resolution():
    bumped = [
        Display(index=0, display_id=1, width=3840, height=2160, is_main=True,
                origin_x=0, origin_y=0, dpi=96),
    ]
    assert environment_signature(bumped) != environment_signature(_LAPTOP)


def test_signature_changes_with_position():
    moved = [
        Display(index=0, display_id=1, width=1920, height=1080, is_main=True,
                origin_x=0, origin_y=0, dpi=96),
        Display(index=1, display_id=2, width=1920, height=1080, is_main=False,
                origin_x=1920, origin_y=0, dpi=96),  # right instead of left
    ]
    assert environment_signature(moved) != environment_signature(_DESK[:2])


def test_signature_changes_with_dpi():
    other = [
        Display(index=0, display_id=9, width=1512, height=982, is_main=True,
                origin_x=0, origin_y=0, dpi=96),  # was 226
    ]
    assert environment_signature(other) != environment_signature(_LAPTOP)


# --- profile_from_displays --------------------------------------------------


def test_profile_from_displays_captures_topology():
    prof = profile_from_displays("bureau-3-ecrans", _DESK)
    assert prof.name == "bureau-3-ecrans"
    assert prof.signature == environment_signature(_DESK)
    assert len(prof.displays) == 3
    main = next(d for d in prof.displays if d.is_main)
    assert (main.origin_x, main.origin_y, main.width, main.height, main.dpi) == (
        0, 0, 1920, 1080, 96)
    # captured in index order
    assert [d.index for d in prof.displays] == [0, 1, 2]


# --- match_profile ----------------------------------------------------------


def test_match_profile_by_signature():
    desk = profile_from_displays("bureau-3-ecrans", _DESK)
    laptop = profile_from_displays("portable-seul", _LAPTOP)
    matched = match_profile([desk, laptop], _DESK)
    assert matched is desk


def test_match_profile_unknown_returns_none():
    laptop = profile_from_displays("portable-seul", _LAPTOP)
    assert match_profile([laptop], _DESK) is None


def test_match_profile_empty_store():
    assert match_profile([], _DESK) is None


# --- coord_space_from_profile: AXE 1 fed from a saved profile ---------------


def test_coord_space_from_profile_round_trip():
    prof = profile_from_displays("bureau-3-ecrans", _DESK)
    # the left display (index 1, origin -1920), downscaled snapshot
    cs = coord_space_from_profile(prof, display_index=1, max_width=1600)
    # image right edge 1600 -> source 1920 -> global -1920 + 1920 = 0
    assert cs.to_global(1600, 0) == (0, 0)
    assert cs.to_global(0, 0) == (-1920, 0)
    # round trip
    assert cs.to_image(*cs.to_global(800, 400)) == (800, 400)


def test_coord_space_from_profile_no_downscale():
    prof = profile_from_displays("bureau-3-ecrans", _DESK)
    cs = coord_space_from_profile(prof, display_index=1, max_width=3000)
    assert cs.to_global(100, 50) == (-1820, 50)


def test_coord_space_from_profile_with_region():
    prof = profile_from_displays("bureau-3-ecrans", _DESK)
    region = {"x": 200, "y": 300, "width": 800, "height": 600}
    cs = coord_space_from_profile(prof, display_index=1, max_width=400, region=region)
    # source_w=800, scale 0.5; image (100,50) -> source (200,100)
    assert cs.to_global(100, 50) == (-1920 + 200 + 200, 0 + 300 + 100)


def test_coord_space_from_profile_index_out_of_range():
    prof = profile_from_displays("portable-seul", _LAPTOP)
    with pytest.raises(IndexError):
        coord_space_from_profile(prof, display_index=3, max_width=720)


# --- serialization round-trip (the persisted form) --------------------------


def test_profile_to_dict_from_dict_round_trip():
    prof = profile_from_displays("teletravail-ultralarge", _DESK)
    again = EnvironmentProfile.from_dict(prof.to_dict())
    assert again == prof
    assert again.signature == prof.signature


def test_display_profile_to_dict_shape():
    dp = DisplayProfile(index=1, width=1920, height=1080, is_main=False,
                        origin_x=-1920, origin_y=0, dpi=96)
    assert dp.to_dict() == {
        "index": 1, "width": 1920, "height": 1080, "is_main": False,
        "origin_x": -1920, "origin_y": 0, "dpi": 96,
    }
