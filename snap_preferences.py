"""Popup-free SNAP settings backend for KiCad 9.x.

The Appearance SNAP page must never open KiCad Preferences.  KiCad 9.0's
Python bindings do not expose PCBNEW_SETTINGS::m_MagneticItems directly, but
SETTINGS_MANAGER.Load() *is* exposed.  Therefore this backend:

1. reads KiCad's own pcbnew.json for display;
2. patches only the three Magnetic Points scalar keys in that file;
3. asks KiCad's live SETTINGS_MANAGER to reload registered settings.

No MacroBK persistence, menu command, dialog, SendKeys, or screen-coordinate
input is used.
"""
import json
import os
import re
import tempfile

import pcbnew
import wx

from . import kicad_controls as kc

SETTING_KEYS = {
    "pads": "magnetic_pads",
    "tracks_vias": "magnetic_tracks",
    "graphics": "magnetic_graphics",
}
CANONICAL_CHOICES = {
    "pads": ["Never", "When routing tracks", "Always"],
    "tracks_vias": ["Never", "When routing tracks", "Always"],
    "graphics": ["Always", "Never"],
}


def _version_series():
    text = str(pcbnew.GetBuildVersion())
    match = re.search(r"(\d+)\.(\d+)", text)
    if not match:
        raise RuntimeError("Could not determine KiCad settings version from {!r}".format(text))
    return "{}.{}".format(match.group(1), match.group(2))


def settings_path():
    base = os.environ.get("APPDATA")
    if not base:
        base = wx.StandardPaths.Get().GetUserConfigDir()
    return os.path.join(base, "kicad", _version_series(), "pcbnew.json")


def _nested_value(data, key):
    editing = data.get("editing") if isinstance(data, dict) else None
    if isinstance(editing, dict) and key in editing:
        return editing[key]

    matches = []

    def visit(value):
        if isinstance(value, dict):
            if key in value:
                matches.append(value[key])
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(data)
    if len(matches) != 1:
        raise RuntimeError("KiCad setting {!r} unavailable or ambiguous".format(key))
    return matches[0]


def _decode_saved_values(data):
    pads = _nested_value(data, "magnetic_pads")
    tracks = _nested_value(data, "magnetic_tracks")
    graphics = _nested_value(data, "magnetic_graphics")

    def three_state(name, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RuntimeError("Unexpected {} setting value: {!r}".format(name, value))
        index = int(value)
        choices = CANONICAL_CHOICES[name]
        if index < 0 or index >= len(choices):
            raise RuntimeError("Unexpected {} setting index: {!r}".format(name, value))
        return choices[index]

    if isinstance(graphics, bool):
        graphics_value = "Always" if graphics else "Never"
    elif isinstance(graphics, (int, float)) and int(graphics) in (0, 1):
        graphics_value = "Always" if int(graphics) else "Never"
    else:
        raise RuntimeError("Unexpected graphics setting value: {!r}".format(graphics))

    return {
        "pads": three_state("pads", pads),
        "tracks_vias": three_state("tracks_vias", tracks),
        "graphics": graphics_value,
    }


def _read_text_and_json():
    path = settings_path()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
        data = json.loads(text)
    except Exception as exc:
        raise RuntimeError("Could not read KiCad PCB settings {}: {}".format(path, exc))
    return path, text, data


def read_saved_settings(include_choices=False):
    """Read KiCad's saved Magnetic Points state without opening any window."""
    _path, _text, data = _read_text_and_json()
    values = _decode_saved_values(data)
    payload = {
        "values": values,
        "choices": {key: list(items) for key, items in CANONICAL_CHOICES.items()},
        "source": "kicad-pcbnew-json",
    }
    return payload if include_choices else values


def _encoded_value(key, value):
    choices = CANONICAL_CHOICES[key]
    if value not in choices:
        raise ValueError("Invalid {} option {!r}; choices: {}".format(key, value, choices))
    if key == "graphics":
        return "true" if value == "Always" else "false"
    return str(choices.index(value))


def _patch_scalar(text, json_key, encoded):
    # Preserve KiCad's file formatting and every unrelated setting.  These
    # setting names are unique in pcbnew.json; refuse to guess otherwise.
    pattern = re.compile(
        r'("' + re.escape(json_key) + r'"\s*:\s*)(true|false|-?\d+(?:\.\d+)?)',
        re.IGNORECASE,
    )
    updated, count = pattern.subn(lambda m: m.group(1) + encoded, text)
    if count != 1:
        raise RuntimeError(
            "KiCad setting {!r} unavailable or ambiguous in pcbnew.json (matches={})".format(
                json_key, count
            )
        )
    return updated


def _atomic_write(path, text):
    directory = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(prefix=".macrobk-pcbnew-", suffix=".json.tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _reload_live_settings():
    """Reload KiCad's registered settings without opening Preferences."""
    manager = pcbnew.GetSettingsManager()
    if manager is None or not hasattr(manager, "Load"):
        raise RuntimeError("KiCad SETTINGS_MANAGER.Load() is unavailable")
    manager.Load()


def cleanup():
    # No dialog/timer/worker is owned by this backend.
    return None


def request(changes=None, include_choices=False):
    """Read or update Magnetic Points with no popup window.

    Writes patch only the requested Magnetic Points keys in KiCad's pcbnew.json
    and then call the official SETTINGS_MANAGER.Load() binding so the running
    editor reloads the registered settings objects.  If reload fails, the file
    is restored and a best-effort reload of the original settings is attempted.
    """
    if not wx.IsMainThread():
        raise RuntimeError("Snap API requires the GUI thread; use MacroBK script API")

    changes = {key: value for key, value in (changes or {}).items() if value is not None}
    unknown = set(changes) - set(SETTING_KEYS)
    if unknown:
        raise ValueError("Unknown snap setting: {}".format(sorted(unknown)))

    if not changes:
        return read_saved_settings(include_choices=include_choices)

    # Validate every requested value before touching disk.
    for key, value in changes.items():
        _encoded_value(key, value)

    path, original_text, original_data = _read_text_and_json()
    before = _decode_saved_values(original_data)

    new_text = original_text
    for key, value in changes.items():
        new_text = _patch_scalar(new_text, SETTING_KEYS[key], _encoded_value(key, value))

    if new_text == original_text:
        payload = read_saved_settings(include_choices=True)
        return payload if include_choices else payload["values"]

    try:
        _atomic_write(path, new_text)
        _reload_live_settings()
        payload = read_saved_settings(include_choices=True)
        expected = dict(before)
        expected.update(changes)
        if payload["values"] != expected:
            raise RuntimeError(
                "Snap settings verification failed: expected={} actual={}".format(
                    expected, payload["values"]
                )
            )
        kc.log("SNAP settings applied without Preferences popup: {}".format(changes))
        return payload if include_choices else payload["values"]
    except Exception:
        # Never leave a half-applied settings file behind.
        try:
            _atomic_write(path, original_text)
            _reload_live_settings()
        except Exception as restore_exc:
            kc.log("SNAP settings restore failed: " + repr(restore_exc))
        raise
