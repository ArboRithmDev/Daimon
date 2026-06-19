"""OCR backends for find(text): Fake (tests), macOS Vision (lazy), Windows scaffold.

The OCR engine is INJECTED into find(text). These tests exercise the three
backends' *seam* without needing the real engines:
- FakeOCR returns deterministic word boxes (used everywhere else as the test double);
- the macOS Vision backend imports its framework lazily, so importing the module
  never requires pyobjc-framework-Vision to be installed (parity with screen.py
  importing Quartz inside functions);
- the Windows backend is a parity-ready SCAFFOLD: a clear NotImplementedError that
  names the future Win32/Tesseract twin, never an un-stubbed seam.
"""

import importlib

import pytest

from daimon.senses.find import WordBox


def test_fake_ocr_returns_injected_boxes():
    from daimon.senses.find_ocr import FakeOCR

    boxes = [WordBox(text="Hello", x=1, y=2, width=30, height=10)]
    ocr = FakeOCR(boxes)
    out = ocr.recognize(object())  # image arg ignored by the fake
    assert out == boxes


def test_fake_ocr_default_is_empty():
    from daimon.senses.find_ocr import FakeOCR

    assert FakeOCR().recognize(object()) == []


def test_find_ocr_module_imports_without_vision():
    # The module must import on a box with no pyobjc-framework-Vision installed:
    # the Vision import has to be lazy (inside the method), like Quartz in screen.py.
    mod = importlib.import_module("daimon.senses.find_ocr")
    assert hasattr(mod, "VisionOCR")
    assert hasattr(mod, "WindowsOCR")
    assert hasattr(mod, "FakeOCR")


def test_windows_ocr_is_a_parity_scaffold():
    from daimon.senses.find_ocr import WindowsOCR

    with pytest.raises(NotImplementedError) as exc:
        WindowsOCR().recognize(object())
    # the stub must point at the future twin, not fail blankly
    msg = str(exc.value).lower()
    assert "win" in msg
    assert "tesseract" in msg or "win32" in msg


def test_vision_ocr_recognize_without_framework_raises_cleanly():
    # Constructing is fine (no framework touched); recognize() lazily imports
    # Vision and so raises ImportError-derived/RuntimeError when it's absent here.
    from daimon.senses.find_ocr import VisionOCR

    ocr = VisionOCR()
    with pytest.raises((ImportError, ModuleNotFoundError, RuntimeError)):
        ocr.recognize(object())


def test_vision_normalized_box_to_image_pixels():
    # Vision reports boxes in a normalised, BOTTOM-LEFT origin space [0..1].
    # The pure converter flips Y and scales to top-left image pixels so the
    # boxes line up with the snapshot the coord-space was built for.
    from daimon.senses.find_ocr import vision_box_to_image

    # full-width band near the TOP of a 1000x500 image:
    #   normalised x=0.1, y=0.8 (bottom-left), w=0.2, h=0.1
    wb = vision_box_to_image("Etat", 0.1, 0.8, 0.2, 0.1, img_w=1000, img_h=500)
    assert wb.text == "Etat"
    assert wb.x == 100            # 0.1 * 1000
    assert wb.width == 200        # 0.2 * 1000
    assert wb.height == 50        # 0.1 * 500
    # bottom-left y 0.8 with height 0.1 -> top edge at 0.9 from bottom = 0.1 from top
    assert wb.y == 50             # (1 - 0.8 - 0.1) * 500
