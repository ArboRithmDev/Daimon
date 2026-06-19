"""Pure find(text)->coords core — Vue-only fallback when a11y goes mute (AXE 3).

No real screen, no OCR engine, no OS. A `FakeOCR` returns deterministic word
boxes for an image; the pure matcher picks the best label and AXE 1's CoordSpace
reprojects its centre to a GLOBAL desktop pixel. DoD: find("Etat_FACTURECLIENT")
on a fixture returns coords that, fed to main_click (global space), land on the
label's centre.

These tests pin the matching math + the reprojection so the locator is provably
a *localiser* (returns a position), never an interpreter — the doctrine
exception is scoped to localisation, not comprehension.
"""

from daimon.capture.coordspace import CoordSpace
from daimon.senses.find import (
    Match,
    WordBox,
    best_match,
    locate,
    rank_matches,
)


# --- fixture: deterministic OCR word boxes for a WinDev-ish form ------------
# Boxes are in IMAGE pixels (top-left origin), as a real OCR backend reports
# after normalisation. The form has a couple of look-alike labels so matching
# has to actually discriminate, not just substring-hit the first row.

_WORDS = [
    WordBox(text="Fichier", x=10, y=8, width=60, height=18),
    WordBox(text="Etat_FACTURE", x=40, y=120, width=110, height=20),
    WordBox(text="Etat_FACTURECLIENT", x=40, y=160, width=180, height=22),
    WordBox(text="Etat_FACTUREFOURNISSEUR", x=40, y=200, width=230, height=22),
    WordBox(text="Valider", x=300, y=400, width=70, height=24),
]


# --- WordBox geometry -------------------------------------------------------


def test_wordbox_centre_is_box_middle():
    wb = WordBox(text="X", x=40, y=160, width=180, height=22)
    assert wb.center() == (130, 171)


# --- rank_matches: pure, discriminating -------------------------------------


def test_exact_match_ranks_first():
    ranked = rank_matches(_WORDS, "Etat_FACTURECLIENT")
    assert ranked[0].word.text == "Etat_FACTURECLIENT"
    assert ranked[0].score == 1.0


def test_exact_match_beats_prefix_sibling():
    # "Etat_FACTURE" is a prefix of the query but not equal; the exact label wins.
    ranked = rank_matches(_WORDS, "Etat_FACTURECLIENT")
    texts = [m.word.text for m in ranked]
    assert texts[0] == "Etat_FACTURECLIENT"
    assert texts.index("Etat_FACTURECLIENT") < texts.index("Etat_FACTURE")


def test_matching_is_case_insensitive():
    ranked = rank_matches(_WORDS, "etat_factureclient")
    assert ranked[0].word.text == "Etat_FACTURECLIENT"
    assert ranked[0].score == 1.0


def test_matching_ignores_surrounding_whitespace():
    ranked = rank_matches(_WORDS, "  Valider  ")
    assert ranked[0].word.text == "Valider"
    assert ranked[0].score == 1.0


def test_substring_query_matches_containing_label():
    # A partial query still locates the label that contains it.
    ranked = rank_matches(_WORDS, "FACTURECLIENT")
    assert ranked[0].word.text == "Etat_FACTURECLIENT"
    assert 0.0 < ranked[0].score < 1.0


def test_unrelated_query_scores_below_threshold():
    ranked = rank_matches(_WORDS, "ZZZ_NOPE", min_score=0.5)
    assert ranked == []


def test_rank_matches_is_sorted_descending():
    ranked = rank_matches(_WORDS, "Etat_FACTURE", min_score=0.0)
    scores = [m.score for m in ranked]
    assert scores == sorted(scores, reverse=True)


# --- best_match -------------------------------------------------------------


def test_best_match_returns_top_candidate():
    m = best_match(_WORDS, "Etat_FACTURECLIENT")
    assert isinstance(m, Match)
    assert m.word.text == "Etat_FACTURECLIENT"


def test_best_match_none_when_no_candidate():
    assert best_match(_WORDS, "totally-absent-xyz") is None
    assert best_match([], "anything") is None


# --- locate: matching + AXE 1 reprojection round-trip -----------------------


def test_locate_resolves_label_centre_to_global():
    # left display: origin -1920, snapshot downscaled (source 1920 -> image 1600)
    cs = CoordSpace(display_origin_x=-1920, display_origin_y=0, image_scale=1600 / 1920)
    hit = locate(_WORDS, "Etat_FACTURECLIENT", cs)
    assert hit is not None
    # image centre of the label box
    icx, icy = WordBox(text="", x=40, y=160, width=180, height=22).center()
    assert (hit["image_x"], hit["image_y"]) == (icx, icy)
    # global coords are AXE 1's deterministic reprojection of that centre
    assert (hit["global_x"], hit["global_y"]) == cs.to_global(icx, icy)
    assert hit["text"] == "Etat_FACTURECLIENT"
    assert hit["score"] == 1.0


def test_locate_global_coords_round_trip_back_to_image():
    cs = CoordSpace(display_origin_x=-1920, display_origin_y=0, image_scale=1600 / 1920)
    hit = locate(_WORDS, "Etat_FACTURECLIENT", cs)
    # DoD spirit: the global coords main_click would receive map back onto the box.
    bx = cs.to_image(hit["global_x"], hit["global_y"])
    assert bx == (hit["image_x"], hit["image_y"])


def test_locate_returns_none_when_absent():
    cs = CoordSpace(display_origin_x=0, display_origin_y=0, image_scale=1.0)
    assert locate(_WORDS, "no-such-label", cs) is None


def test_locate_identity_coord_space_passthrough():
    # no offset, no downscale: global == image centre (single main display).
    cs = CoordSpace(display_origin_x=0, display_origin_y=0, image_scale=1.0)
    hit = locate(_WORDS, "Valider", cs)
    assert (hit["global_x"], hit["global_y"]) == (hit["image_x"], hit["image_y"])
