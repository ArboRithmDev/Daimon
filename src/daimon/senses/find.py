"""Pure find(text)->coords core — the Vue-only fallback locator (AXE 3).

OS-agnostic, no screen access, no OCR engine. Given OCR word boxes for a snapshot
(in image pixels) plus a query string, this picks the best-matching visible label
and — via AXE 1's `CoordSpace` — reprojects its centre to a GLOBAL desktop pixel
the Hands can click directly.

Why this exists: `touche_tree`/`touche_probe` go mute on WinDev / old Win32 /
custom-drawn / Electron surfaces ({"summary":"None"}, generic PaneControl). With
no accessibility tree, the pilot otherwise falls back to raw pixel guessing. This
lets it click a *visible* label without any a11y tree.

DOCTRINE EXCEPTION (acted by Ben, 2026-06-19 — see docs/cadrage AXE 3 / P5):
  Daimon's principle "does no vision/OCR" is about INTERPRETATION — turning pixels
  into meaning/decisions. A find(text) LOCATOR returns a *position*, not a
  comprehension: localisation != interprétation. Returning "the label you named is
  at (x, y)" is the same category as returning a pixel — it carries no semantic
  reading of the screen. This is a scoped, allowed exception, kept strictly
  local-first / no network (the OCR backend is on-device: Apple Vision on macOS,
  Win32/Tesseract on Windows). The matcher below is deliberately a dumb string
  comparator, not an NLP model, to keep the locator on the localisation side of
  that line.

The matching is pure and unit-tested; the OCR engine is injected (see find_ocr).
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from ..capture.coordspace import CoordSpace


@dataclass(frozen=True)
class WordBox:
    """One OCR-recognised word/line and its bounding box in IMAGE pixels.

    The box is top-left origin (x, y) with width/height, matching the snapshot
    the coord-space was built for. A backend converts its native coordinate
    convention (e.g. Vision's normalised bottom-left) into this shape before
    matching, so the pure core never sees engine-specific geometry.
    """

    text: str
    x: int
    y: int
    width: int
    height: int

    def center(self) -> tuple[int, int]:
        """Centre of the box in image pixels — the natural click point."""
        return self.x + self.width // 2, self.y + self.height // 2


@dataclass(frozen=True)
class Match:
    """A scored candidate: the word box and how well it matches the query (0..1)."""

    word: WordBox
    score: float


def _normalise(s: str) -> str:
    """Casefold + strip surrounding whitespace — the comparison normal form."""
    return s.strip().casefold()


def _score(query: str, candidate: str) -> float:
    """Pure string-similarity score in [0, 1] between a query and a label.

    Deterministic and dumb on purpose (a locator, not an interpreter):
    - exact (normalised) equality -> 1.0;
    - the query being a substring of the label (or vice-versa) gets a strong
      partial score scaled by length overlap, so "FACTURECLIENT" still finds
      "Etat_FACTURECLIENT";
    - otherwise a character-level ratio (handles minor OCR noise / typos).
    Never higher than an exact equality, so a perfect label always wins over a
    look-alike prefix sibling.
    """
    q = _normalise(query)
    c = _normalise(candidate)
    if not q or not c:
        return 0.0
    if q == c:
        return 1.0
    if q in c or c in q:
        shorter, longer = (q, c) if len(q) <= len(c) else (c, q)
        # length overlap, capped below 1.0 so it never ties an exact match
        return 0.5 + 0.49 * (len(shorter) / len(longer))
    return SequenceMatcher(None, q, c).ratio()


def rank_matches(words, query: str, min_score: float = 0.6) -> list[Match]:
    """Score every word box against the query, best first, above `min_score`.

    Ties broken by reading order (top-to-bottom, then left-to-right) so the
    result is stable. Returns [] when nothing clears the threshold.
    """
    scored = [Match(word=w, score=_score(query, w.text)) for w in words]
    kept = [m for m in scored if m.score >= min_score]
    kept.sort(key=lambda m: (-m.score, m.word.y, m.word.x))
    return kept


def best_match(words, query: str, min_score: float = 0.6) -> Match | None:
    """The single best-matching word box for `query`, or None if none clears it."""
    ranked = rank_matches(words, query, min_score=min_score)
    return ranked[0] if ranked else None


def locate(words, query: str, coord_space: CoordSpace,
           min_score: float = 0.6) -> dict | None:
    """Find `query` among OCR `words` and resolve its centre to global pixels.

    Returns a dict with the matched text, its score, the image-space centre, and
    the GLOBAL desktop coords (AXE 1 reprojection of that centre) — ready to feed
    straight to a positional Hand. None when no label clears `min_score`.
    """
    m = best_match(words, query, min_score=min_score)
    if m is None:
        return None
    icx, icy = m.word.center()
    gx, gy = coord_space.to_global(icx, icy)
    return {
        "text": m.word.text,
        "score": round(m.score, 4),
        "image_x": icx,
        "image_y": icy,
        "global_x": gx,
        "global_y": gy,
    }
