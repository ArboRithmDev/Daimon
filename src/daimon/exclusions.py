"""The secrets filter — applied BEFORE any sense serves data.

Common layer for every sense. Vue passes its captured image through
`redact_image`; Touché will pass its accessibility nodes through
`redact_nodes` (stub until Touché lands). Both consult the same
`ExclusionConfig`, so a zone declared once is hidden everywhere.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .config import ExclusionConfig, Rect


@dataclass(frozen=True)
class ExclusionResult:
    """Outcome of evaluating the filter against a perception request."""

    # When True, the whole snapshot must be refused (an excluded app is in view).
    refused: bool = False
    reason: str = ""


class ExclusionFilter:
    def __init__(self, config: ExclusionConfig) -> None:
        self._config = config
        self._title_patterns = tuple(re.compile(p) for p in config.window_titles)
        self._secret_roles = set(config.secret_roles)
        self._secret_apps = set(config.secret_apps)

    # -- app-level gate ---------------------------------------------------
    def is_app_excluded(self, bundle_id: str | None) -> bool:
        return bool(bundle_id) and bundle_id in self._config.apps

    def evaluate_frontmost(self, bundle_id: str | None) -> ExclusionResult:
        """If the frontmost app is excluded, the snapshot is refused wholesale."""
        if self.is_app_excluded(bundle_id):
            return ExclusionResult(refused=True, reason=f"frontmost app excluded: {bundle_id}")
        return ExclusionResult()

    # -- title-level gate -------------------------------------------------
    def is_title_excluded(self, title: str | None) -> bool:
        if not title:
            return False
        return any(p.search(title) for p in self._title_patterns)

    # -- secret-target check ----------------------------------------------
    def is_target_secret(self, role: str | None = None, bundle_id: str | None = None) -> bool:
        """A target is secret if its role is a secret role or its app is declared secret."""
        if role and role in self._secret_roles:
            return True
        if bundle_id and bundle_id in self._secret_apps:
            return True
        return False

    # -- point-in-region check --------------------------------------------
    def is_point_excluded(self, x, y) -> bool:
        """True if (x, y) falls inside any configured exclusion rectangle."""
        if x is None or y is None:
            return False
        for r in self._config.regions:
            if r.x <= x <= r.x + r.width and r.y <= y <= r.y + r.height:
                return True
        return False

    # -- region redaction -------------------------------------------------
    @property
    def regions(self) -> tuple[Rect, ...]:
        return self._config.regions

    def redact_image(self, image):  # image: PIL.Image.Image
        """Black out every fixed exclusion region on a captured frame.

        Returns the same image object, mutated. Imported lazily so the module
        stays importable on machines without Pillow (e.g. CI doing unit tests).
        """
        if not self._config.regions:
            return image
        from PIL import ImageDraw

        draw = ImageDraw.Draw(image)
        for r in self._config.regions:
            draw.rectangle([r.x, r.y, r.x + r.width, r.y + r.height], fill="black")
        return image

    def redact_nodes(self, nodes):
        """Drop title-excluded subtrees and blank values of secret-role nodes.

        Same title patterns that redact windows for Vue prune the a11y tree for
        Touché — one declared zone, hidden in every sense. Secret-role nodes (e.g.
        AXSecureTextField) have their value blanked and gain ``redacted=True`` so
        callers know the field was intentionally suppressed. Does not mutate the
        input; works on plain dict trees from the accessibility backend.
        """
        def walk(items):
            kept = []
            for node in items:
                if self.is_title_excluded(node.get("title")):
                    continue
                node = dict(node)
                if node.get("role") in self._secret_roles:
                    node["value"] = "█" if node.get("value") else node.get("value")
                    node["redacted"] = True
                children = node.get("children")
                if children:
                    node["children"] = walk(children)
                kept.append(node)
            return kept

        return walk(nodes)


def _image_draw(image):
    from PIL import ImageDraw
    return ImageDraw.Draw(image)


def black_out_rects(image, rects):
    """Fill each {x,y,width,height} rect with black on a PIL image. Pure-ish
    (PIL import isolated in _image_draw for testability)."""
    if not rects:
        return image
    draw = _image_draw(image)
    for r in rects:
        x, y = int(r["x"]), int(r["y"])
        draw.rectangle((x, y, x + int(r["width"]), y + int(r["height"])), fill="black")
    return image
