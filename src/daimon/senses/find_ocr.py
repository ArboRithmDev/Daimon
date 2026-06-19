"""OCR backends for find(text) — INJECTED into the Vue sense (AXE 3).

Three twins, one shared output contract (`list[WordBox]` in top-left image
pixels), so the pure matcher in `find.py` never sees engine-specific geometry:

  - `FakeOCR`     — deterministic word boxes for tests (the injectable double);
  - `VisionOCR`   — the REAL macOS backend (Apple Vision, VNRecognizeTextRequest
                    via pyobjc-framework-Vision), 100% on-device / no network;
  - `WindowsOCR`  — a parity-ready SCAFFOLD (clear NotImplementedError naming the
                    future Win32/Tesseract twin) so the seam exists, never unstubbed.

DOCTRINE: see find.py — this is a LOCATOR (returns positions), a scoped, allowed
exception to "Daimon does no vision/OCR". Both real engines are strictly
local-first / on-device. No text leaves the machine; Vision and Tesseract run in
the host process.

The Vision/Tesseract imports are LAZY (inside `recognize`), mirroring screen.py
importing Quartz inside its functions: importing this module never requires the
OCR framework to be installed, so the pure core + tests run on any box.
"""

from __future__ import annotations

from typing import Protocol

from .find import WordBox


class OCRBackend(Protocol):
    """The injected OCR seam: turn a PIL image into image-pixel word boxes."""

    def recognize(self, image) -> list[WordBox]:
        ...


class FakeOCR:
    """Deterministic OCR double: returns the boxes it was constructed with.

    The image argument is ignored — tests pin the word boxes directly so the
    pure matcher + reprojection can be exercised without any real engine.
    """

    def __init__(self, boxes: list[WordBox] | None = None) -> None:
        self._boxes = list(boxes or [])

    def recognize(self, image) -> list[WordBox]:
        return list(self._boxes)


def vision_box_to_image(text: str, nx: float, ny: float, nw: float, nh: float,
                        img_w: int, img_h: int) -> WordBox:
    """Convert one Apple Vision observation to a top-left image-pixel WordBox.

    Vision reports `boundingBox` normalised to [0, 1] in a BOTTOM-LEFT origin
    space (origin at the box's lower-left, y growing upward). The snapshot the
    matcher works in is top-left origin in pixels, so we scale by the image size
    and flip Y: top_px = (1 - ny - nh) * img_h. Pure + unit-tested so the Y-flip
    can never silently drift.
    """
    x = round(nx * img_w)
    y = round((1.0 - ny - nh) * img_h)
    w = round(nw * img_w)
    h = round(nh * img_h)
    return WordBox(text=text, x=x, y=y, width=w, height=h)


class VisionOCR:
    """REAL macOS OCR via Apple Vision (VNRecognizeTextRequest), fully on-device.

    `recognize` lazily imports Vision/Quartz, runs an accurate text-recognition
    request over the snapshot, and maps each observation's top candidate +
    normalised bounding box into a top-left image-pixel `WordBox` via
    `vision_box_to_image`. No network: Vision's recogniser runs in-process.

    Importing this class never touches the framework; only calling `recognize`
    does, so the module imports cleanly where pyobjc-framework-Vision is absent.
    """

    def __init__(self, recognition_level: str = "accurate") -> None:
        self._level = recognition_level

    def recognize(self, image) -> list[WordBox]:
        import Quartz
        import Vision
        from Foundation import NSData

        img_w, img_h = image.width, image.height

        # PIL image -> PNG bytes -> CGImage (the form Vision's handler accepts).
        import io
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        data = NSData.dataWithBytes_length_(buf.getvalue(), len(buf.getvalue()))
        src = Quartz.CGImageSourceCreateWithData(data, None)
        if src is None or Quartz.CGImageSourceGetCount(src) == 0:
            return []
        cg_image = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)

        request = Vision.VNRecognizeTextRequest.alloc().init()
        level = (
            Vision.VNRequestTextRecognitionLevelAccurate
            if self._level == "accurate"
            else Vision.VNRequestTextRecognitionLevelFast
        )
        request.setRecognitionLevel_(level)
        request.setUsesLanguageCorrection_(False)  # locator, not interpreter

        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(
            cg_image, None
        )
        ok, _err = handler.performRequests_error_([request], None)
        if not ok:
            return []

        out: list[WordBox] = []
        for obs in request.results() or []:
            candidate = obs.topCandidates_(1)
            if not candidate or len(candidate) == 0:
                continue
            text = str(candidate[0].string())
            box = obs.boundingBox()  # normalised, bottom-left origin
            origin, size = box.origin, box.size
            out.append(vision_box_to_image(
                text, origin.x, origin.y, size.width, size.height, img_w, img_h))
        return out


class WindowsOCR:
    """Windows OCR backend — parity-ready SCAFFOLD (not yet wired).

    The real twin will run on-device OCR over the captured monitor image and emit
    the same top-left image-pixel `WordBox` contract as Vision, so `find.py`'s
    matcher and AXE 1's reprojection stay platform-identical. Two viable local
    engines, both no-network: the built-in Windows.Media.Ocr (WinRT) or a bundled
    Tesseract via pytesseract. Until one is wired, the seam fails loud rather than
    silently returning nothing.
    """

    def recognize(self, image) -> list[WordBox]:
        raise NotImplementedError(
            "find_ocr.WindowsOCR.recognize: wire the Windows OCR twin on win32 "
            "(Windows.Media.Ocr WinRT, or bundled Tesseract via pytesseract) "
            "emitting top-left image-pixel WordBoxes like VisionOCR. Keep it "
            "on-device / no network. TODO real Win runtime."
        )


def default_ocr() -> OCRBackend:
    """Pick the on-device OCR backend for the current platform.

    macOS -> Apple Vision; Windows -> the (scaffolded) Win twin. Importing the
    chosen class is cheap; the heavy framework import only happens on recognize().
    """
    import sys

    if sys.platform == "darwin":
        return VisionOCR()
    if sys.platform.startswith("win"):
        return WindowsOCR()
    # Other platforms have no supported on-device engine yet; the Fake keeps the
    # seam usable in tests/headless without pretending to OCR.
    return FakeOCR()
