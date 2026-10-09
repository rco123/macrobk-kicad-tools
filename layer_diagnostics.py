"""Read-only active-layer investigation; load in PCB Editor, not standalone Python.

No plugin import, registrations, layer changes, cached selection or production
getter. Every capture samples the live wx objects on the GUI thread.
"""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import threading

import pcbnew
import wx

ROOT = Path(__file__).resolve().parent
FRAME_METHODS = (
    "GetActiveLayer", "SetActiveLayer", "GetCanvas", "GetToolManager", "GetBoard",
    "GetScreen", "GetAppearancePanel", "GetLayerManager", "GetLayerSelector",
    "GetLayerPair", "GetCurrentLayer",
)
TARGETS = ("F.Cu", "B.Cu", "F.Adhesive", "Edge.Cuts")


def _plain(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return {"class": type(value).__name__, "repr": repr(value)[:300]}


def _read(obj, name, *args):
    try:
        member = getattr(obj, name, None)
        if not callable(member):
            return {"available": False}
        return {"available": True, "value": _plain(member(*args))}
    except Exception as exc:
        return {"available": True, "error": type(exc).__name__ + ": " + str(exc)}


def _walk(window):
    for child in window.GetChildren():
        yield child
        yield from _walk(child)


def _identity(window):
    if window is None:
        return None
    result = {"python_ref": hex(id(window)), "wx_class": type(window).__name__}
    for name in ("GetId", "GetName", "GetLabel", "GetHandle"):
        result[name] = _read(window, name)
    try:
        result["native_class"] = window.GetClassInfo().GetClassName()
    except Exception as exc:
        result["native_class_error"] = str(exc)
    return result


def _colour(window, name):
    try:
        colour = getattr(window, name)()
        return [colour.Red(), colour.Green(), colour.Blue(), colour.Alpha()]
    except Exception as exc:
        return {"error": str(exc)}


def bitmap_metrics(bitmap):
    """Count raw/effective alpha. OFF icons may contain a near-transparent pixel."""
    if not bitmap.IsOk():
        return {"ok": False}
    image = bitmap.ConvertToImage()
    width, height = image.GetWidth(), image.GetHeight()
    rgb = bytes(image.GetData())
    alpha = bytes(image.GetAlpha()) if image.HasAlpha() else None
    mask = [image.GetMaskRed(), image.GetMaskGreen(), image.GetMaskBlue()] if image.HasMask() else None
    effective = bytearray()
    for i in range(width * height):
        is_mask = mask is not None and list(rgb[3*i:3*i+3]) == mask
        effective.append(0 if is_mask else (alpha[i] if alpha is not None else 255))
    return {
        "ok": True, "width": width, "height": height,
        "scale_factor": _read(bitmap, "GetScaleFactor"),
        "has_alpha": image.HasAlpha(), "has_mask": image.HasMask(), "mask_rgb": mask,
        "nontransparent_pixel_count": sum(a > 0 for a in effective),
        "alpha_gt_16_count": sum(a > 16 for a in effective),
        "opaque_pixel_count": sum(a == 255 for a in effective),
        "rgb_sum": sum(rgb), "rgb_checksum": hashlib.sha256(rgb).hexdigest(),
        "alpha_sum": sum(alpha) if alpha is not None else None,
        "alpha_checksum": hashlib.sha256(alpha).hexdigest() if alpha is not None else None,
        "effective_alpha_checksum": hashlib.sha256(effective).hexdigest(),
    }


def _control(window, path):
    info = _identity(window)
    info["path"] = path
    info["parent"] = _identity(window.GetParent())
    info["background"] = _colour(window, "GetBackgroundColour")
    info["foreground"] = _colour(window, "GetForegroundColour")
    info["has_focus"] = window == wx.Window.FindFocus()
    for name in ("IsEnabled", "IsShown", "IsShownOnScreen", "IsBeingDeleted",
                 "GetWindowStyleFlag", "GetPosition", "GetSize", "GetScreenPosition",
                 "GetToolTipText", "GetValue", "GetSelection", "GetCurrentSelection",
                 "GetStringSelection", "GetEvtHandlerEnabled", "HasClientData",
                 "HasClientObjectData", "HasClientUntypedData"):
        info[name] = _read(window, name)
    info["selection_members"] = [n for n in dir(window) if any(
        term in n.lower() for term in ("select", "current", "active", "indicator", "client", "accessib"))]
    # Native KiCad client data can be an untyped C++ pointer, not a PyObject.
    # Do not reinterpret or dereference that pointer through Python wx APIs.
    info["client_data"] = {"GetClientData_present": callable(getattr(window, "GetClientData", None)),
                           "GetClientObject_present": callable(getattr(window, "GetClientObject", None)),
                           "value": "NOT READ: native client-data ownership/type is unknown"}
    try:
        handler = window.GetEventHandler()
        info["event_handler"] = {"class": type(handler).__name__, "python_ref": hex(id(handler)),
                                 "is_window": handler == window,
                                 "binding_list": "NOT EXPOSED by public wx API"}
    except Exception as exc:
        info["event_handler"] = {"error": str(exc)}
    try:
        accessible = window.GetAccessible() if callable(getattr(window, "GetAccessible", None)) else None
        info["accessible"] = {"present": accessible is not None}
        if accessible is not None:
            info["accessible"].update({"class": type(accessible).__name__,
                "state": _read(accessible, "GetState", wx.ACC_SELF),
                "role": _read(accessible, "GetRole", wx.ACC_SELF),
                "name": _read(accessible, "GetName", wx.ACC_SELF)})
    except Exception as exc:
        info["accessible"] = {"error": str(exc)}
    if isinstance(window, wx.StaticBitmap):
        try:
            info["bitmap"] = bitmap_metrics(window.GetBitmap())
        except Exception as exc:
            info["bitmap"] = {"error": str(exc)}
    info["children"] = [_control(child, path + "/" + str(i))
                        for i, child in enumerate(window.GetChildren())]
    return info


def _find_frame():
    candidates = []
    for frame in wx.GetTopLevelWindows():
        if not isinstance(frame, wx.Frame) or frame.GetMenuBar() is None:
            continue
        labels = {child.GetLabel() for child in _walk(frame) if isinstance(child, wx.StaticText)}
        if len(labels.intersection(TARGETS)) >= 2:
            candidates.append(frame)
    if len(candidates) != 1:
        raise RuntimeError("Expected exactly one PCB Layers frame, found {}. Pass frame explicitly.".format(len(candidates)))
    return candidates[0]


def _bitmaps(control):
    if "bitmap" in control:
        yield {"path": control["path"], "control": {k: control[k] for k in (
            "python_ref", "wx_class", "GetId", "GetName")}, "metrics": control["bitmap"]}
    for child in control["children"]:
        yield from _bitmaps(child)


def dump_layer_selection_state(expected=None, tag="manual", frame=None, write=True):
    """expected is a HUMAN observation label, never used to infer selection."""
    if not wx.IsMainThread():
        raise RuntimeError("Run via wx.CallAfter/call_gui_sync on the PCB GUI thread")
    frame = frame or _find_frame()
    board = pcbnew.GetBoard()
    names = set(TARGETS)
    if board is not None:
        for layer_id in range(pcbnew.PCB_LAYER_ID_COUNT):
            try:
                name = board.GetLayerName(layer_id)
                if name:
                    names.add(name)
            except Exception:
                pass
    result = {"schema": 1, "time": datetime.now().astimezone().isoformat(),
              "expected_by_human": expected, "tag": tag, "thread": threading.get_ident(),
              "kicad_version": pcbnew.GetBuildVersion(), "wx_version": wx.version(),
              "frame": _identity(frame), "frame_dir": dir(frame),
              "frame_api": {n: {"present": hasattr(frame, n),
                  "callable": callable(getattr(frame, n, None))} for n in FRAME_METHODS},
              "frame_getter_values": {n: _read(frame, n) for n in FRAME_METHODS
                  if n.startswith("Get") and callable(getattr(frame, n, None))},
              "pcbnew_members": [n for n in dir(pcbnew) if any(t in n.lower()
                  for t in ("layer", "active", "current", "cu", "board"))],
              "board_layer_members": [n for n in dir(board) if any(t in n.lower()
                  for t in ("layer", "active", "current"))] if board is not None else [],
              "rows": [], "prediction": "NOT IMPLEMENTED: investigation only"}
    seen = set()
    for label in _walk(frame):
        if not isinstance(label, wx.StaticText) or label.GetLabel().strip() not in names:
            continue
        row = label.GetParent()
        key = row.GetHandle()
        if key in seen:
            continue
        seen.add(key)
        tree = _control(row, "row")
        grandparent = row.GetParent()
        result["rows"].append({"layer_name": label.GetLabel().strip(), "label": _identity(label),
            "row": tree, "grandparent": _identity(grandparent),
            "row_siblings": [_identity(child) for child in grandparent.GetChildren()] if grandparent else [],
            "bitmaps": list(_bitmaps(tree))})
    for row in result["rows"]:
        row["bitmap_count"] = len(row["bitmaps"])
    if write:
        folder = ROOT / "diagnostics" / "evidence"
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_tag = re.sub(r"[^A-Za-z0-9_.-]", "_", str(tag))[:60]
        path = folder / (stamp + "_" + safe_tag + ".json")
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print("LAYER DIAGNOSTIC saved: {} rows={} expected={!r}".format(path, len(result["rows"]), expected))
    return result


debug_selected_layer_state = dump_layer_selection_state


def show_diagnostic_panel():
    """Manual experiment UI, independent of MacroBK Manager and config."""
    if not wx.IsMainThread():
        raise RuntimeError("Call show_diagnostic_panel on the GUI thread")
    pcb = _find_frame()
    dialog = wx.Frame(pcb, title="MacroBK Layer Diagnostics — read only", size=(600, 260))
    panel = wx.Panel(dialog)
    layout = wx.BoxSizer(wx.VERTICAL)
    layout.Add(wx.StaticText(panel, label="Click a layer in PCB Appearance first.\nThen click its capture button here. No layer changes are sent."), 0, wx.ALL, 12)
    buttons = wx.BoxSizer(wx.HORIZONTAL)
    status = wx.StaticText(panel, label="Ready. Each capture writes JSON under diagnostics/evidence.")
    for name in TARGETS:
        button = wx.Button(panel, label="Capture " + name)
        def capture(event, name=name):
            try:
                result = dump_layer_selection_state(expected=name, tag=name, frame=pcb)
                status.SetLabel("Saved {} rows; observed {} (human label).".format(len(result["rows"]), name))
            except Exception as exc:
                status.SetLabel("Capture failed: " + str(exc))
        button.Bind(wx.EVT_BUTTON, capture)
        buttons.Add(button, 0, wx.ALL, 4)
    layout.Add(buttons, 0, wx.ALL, 8)
    layout.Add(status, 0, wx.ALL, 12)
    panel.SetSizer(layout)
    dialog.Show()
    return dialog
