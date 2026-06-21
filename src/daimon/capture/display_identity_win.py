r"""Windows-native stable monitor identity via the CCD (Connecting and
Configuring Displays) API — `QueryDisplayConfig` + `DisplayConfigGetDeviceInfo`.

This is the Microsoft-native source for the calibration layer (AXE 2): every
active monitor has a persistent *device path* (e.g.
``\\?\DISPLAY#AUOE3AC#...#{GUID}``) derived from its EDID and physical
connection. Unlike the GDI ``\\.\DISPLAYn`` name — which Windows reassigns as
monitors are plugged/unplugged or re-arranged — the device path is stable for
the physical panel. `calibration.environment_signature` folds it in so a saved
profile re-matches the same monitors across resolution, DPI and layout changes.

Pure ctypes against ``user32`` — no new dependency. Every entry point is
best-effort: any failure yields an empty map and the caller falls back to the
geometry signature, so calibration degrades to the macOS behaviour rather than
breaking.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

_QDC_ONLY_ACTIVE_PATHS = 0x00000002
_ERROR_SUCCESS = 0
_GET_TARGET_NAME = 2
_GET_SOURCE_NAME = 1


class _LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class _PATH_SOURCE_INFO(ctypes.Structure):
    _fields_ = [
        ("adapterId", _LUID), ("id", wintypes.UINT),
        ("modeInfoIdx", wintypes.UINT), ("statusFlags", wintypes.UINT),
    ]


class _PATH_TARGET_INFO(ctypes.Structure):
    _fields_ = [
        ("adapterId", _LUID), ("id", wintypes.UINT),
        ("modeInfoIdx", wintypes.UINT), ("outputTechnology", wintypes.UINT),
        ("rotation", wintypes.UINT), ("scaling", wintypes.UINT),
        ("refreshRate_num", wintypes.UINT), ("refreshRate_den", wintypes.UINT),
        ("scanLineOrdering", wintypes.UINT), ("targetAvailable", wintypes.BOOL),
        ("statusFlags", wintypes.UINT),
    ]


class _PATH_INFO(ctypes.Structure):
    _fields_ = [
        ("sourceInfo", _PATH_SOURCE_INFO), ("targetInfo", _PATH_TARGET_INFO),
        ("flags", wintypes.UINT),
    ]


class _MODE_INFO(ctypes.Structure):
    # The mode union is 64 bytes; we never read it, only size the array right.
    _fields_ = [("_opaque", ctypes.c_byte * 64)]


class _DEVICE_INFO_HEADER(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.UINT), ("size", wintypes.UINT),
        ("adapterId", _LUID), ("id", wintypes.UINT),
    ]


class _TARGET_DEVICE_NAME(ctypes.Structure):
    _fields_ = [
        ("header", _DEVICE_INFO_HEADER),
        ("flags", wintypes.UINT), ("outputTechnology", wintypes.UINT),
        ("edidManufactureId", wintypes.WORD), ("edidProductCodeId", wintypes.WORD),
        ("connectorInstance", wintypes.UINT),
        ("monitorFriendlyDeviceName", wintypes.WCHAR * 64),
        ("monitorDevicePath", wintypes.WCHAR * 128),
    ]


class _SOURCE_DEVICE_NAME(ctypes.Structure):
    _fields_ = [
        ("header", _DEVICE_INFO_HEADER),
        ("viewGdiDeviceName", wintypes.WCHAR * 32),
    ]


def native_monitor_ids() -> dict[str, str]:
    r"""Map each active monitor's GDI device name to its stable CCD device path.

    Returns ``{ "\\\\.\\DISPLAY1": "\\\\?\\DISPLAY#...#{GUID}", ... }``. The GDI
    name is the bridge to ``win32api.GetMonitorInfo(hmon)["Device"]``; the device
    path is the stable identity. Best-effort: returns ``{}`` on any failure.
    """
    try:
        user32 = ctypes.windll.user32
        n_paths = wintypes.UINT()
        n_modes = wintypes.UINT()
        if user32.GetDisplayConfigBufferSizes(
            _QDC_ONLY_ACTIVE_PATHS, ctypes.byref(n_paths), ctypes.byref(n_modes)
        ) != _ERROR_SUCCESS:
            return {}

        paths = (_PATH_INFO * n_paths.value)()
        modes = (_MODE_INFO * n_modes.value)()
        if user32.QueryDisplayConfig(
            _QDC_ONLY_ACTIVE_PATHS,
            ctypes.byref(n_paths), paths,
            ctypes.byref(n_modes), modes, None,
        ) != _ERROR_SUCCESS:
            return {}

        out: dict[str, str] = {}
        for i in range(n_paths.value):
            path = paths[i]

            source = _SOURCE_DEVICE_NAME()
            source.header.type = _GET_SOURCE_NAME
            source.header.size = ctypes.sizeof(source)
            source.header.adapterId = path.sourceInfo.adapterId
            source.header.id = path.sourceInfo.id
            if user32.DisplayConfigGetDeviceInfo(ctypes.byref(source)) != _ERROR_SUCCESS:
                continue

            target = _TARGET_DEVICE_NAME()
            target.header.type = _GET_TARGET_NAME
            target.header.size = ctypes.sizeof(target)
            target.header.adapterId = path.targetInfo.adapterId
            target.header.id = path.targetInfo.id
            if user32.DisplayConfigGetDeviceInfo(ctypes.byref(target)) != _ERROR_SUCCESS:
                continue

            gdi = source.viewGdiDeviceName
            dev_path = target.monitorDevicePath
            if gdi and dev_path:
                out[gdi] = dev_path
        return out
    except Exception:
        return {}
