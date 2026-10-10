import os
import traceback

import wx

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(PLUGIN_DIR, "macrobk_drc.log")

_logger = lambda message: None

def set_logger(logger):
    global _logger
    _logger = logger or (lambda message: None)

def log(message):
    _logger(message)

def norm_label(value):
    if not value:
        return ""
    return (
        str(value)
        .replace("&", "")
        .replace("…", "")
        .replace("...", "")
        .split("\t", 1)[0]
        .strip()
        .lower()
    )


def iter_controls(root):
    for child in root.GetChildren():
        yield child
        yield from iter_controls(child)


def _matches_control_type(control, control_type):
    if control_type is None:
        return True
    if isinstance(control_type, str):
        actual = control.__class__.__name__
        return control_type in (actual, "wx." + actual)
    return isinstance(control, control_type)


def find_controls(root, control_type=None, label=None, name=None, id=None):
    matches = []
    for control in iter_controls(root):
        if not _matches_control_type(control, control_type):
            continue
        if label is not None and norm_label(control.GetLabel()) != norm_label(label):
            continue
        if name is not None and norm_label(control.GetName()) != norm_label(name):
            continue
        if id is not None and control.GetId() != id:
            continue
        matches.append(control)
    return matches


def find_control(root, control_type=None, label=None, name=None, id=None):
    matches = find_controls(
        root, control_type=control_type, label=label, name=name, id=id
    )
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        log(
            "ambiguous control match count={} type={!r} label={!r} name={!r} id={!r}".format(
                len(matches), control_type, label, name, id
            )
        )
    return None


def get_control_value(control):
    if isinstance(control, (wx.CheckBox, wx.RadioButton)):
        return control.GetValue()
    if isinstance(control, (wx.Choice, wx.ComboBox)):
        return control.GetStringSelection()
    if isinstance(control, wx.TextCtrl):
        return control.GetValue()
    return None


def set_control_value(control, value):
    if isinstance(control, (wx.CheckBox, wx.RadioButton)):
        control.SetValue(bool(value))
    elif isinstance(control, (wx.Choice, wx.ComboBox)):
        selected = control.SetStringSelection(str(value))
        if not selected:
            raise ValueError("control item not found: {!r}".format(value))
    elif isinstance(control, wx.TextCtrl):
        control.SetValue(str(value))
    else:
        raise TypeError("unsupported control type: {}".format(control.__class__.__name__))
    control.Refresh()
    control.Update()


def get_control_info(control):
    control_class = control.__class__.__name__
    return {
        "type": "wx." + control_class,
        "class": control_class,
        "name": control.GetName(),
        "label": control.GetLabel(),
        "id": control.GetId(),
        "value": get_control_value(control),
        "enabled": control.IsEnabled(),
        "visible": control.IsShown(),
    }


def is_drc_label(label):
    value = norm_label(label)
    exact = {
        "design rules checker",
        "design rule checker",
        "drc",
        "설계 규칙 검사",
        "설계규칙 검사",
        "디자인 규칙 검사",
    }
    return value in exact or (
        "design" in value and "rule" in value and "checker" in value
    )


def candidate_frames():
    frames = []
    for window in wx.GetTopLevelWindows():
        if not isinstance(window, wx.Frame):
            continue
        try:
            if window.GetMenuBar() is not None:
                frames.append(window)
        except Exception:
            pass
    frames.sort(key=lambda frame: 0 if getattr(frame, "IsActive", lambda: False)() else 1)
    return frames


def find_pcb_frame():
    """Prefer native PCB class/name; menu + PCB hierarchy are fallback evidence."""
    for frame in candidate_frames():
        try:
            native = str(frame.GetClassInfo().GetClassName()).lower()
            name = str(frame.GetName()).lower()
            if "pcb_edit_frame" in native or name in ("pcbframe", "pcb_edit_frame", "pcbnew"):
                return frame
            children = list(iter_controls(frame))
            hierarchy = any("pcb" in (str(child.GetName()) + child.__class__.__name__).lower()
                            for child in children)
            if hierarchy and "pcb editor" in str(frame.GetTitle()).lower():
                return frame
        except (RuntimeError, AttributeError):
            continue
    return None


_callbacks = globals().get("_callbacks", [])
_callback_generation = globals().get("_callback_generation", 0)


def call_later(delay, callback, *args):
    generation = _callback_generation
    holder = []
    def invoke():
        if holder and holder[0] in _callbacks:
            _callbacks.remove(holder[0])
        if generation == _callback_generation:
            callback(*args)
    timer = wx.CallLater(delay, invoke)
    holder.append(timer)
    _callbacks.append(timer)
    return timer


def cancel_callbacks():
    global _callback_generation
    _callback_generation += 1
    timers, _callbacks[:] = list(_callbacks), []
    for timer in timers:
        timer.Stop()


def iter_menu(menu, path=""):
    for position in range(menu.GetMenuItemCount()):
        item = menu.FindItemByPosition(position)
        if item is None:
            continue
        try:
            label = item.GetItemLabelText()
        except Exception:
            try:
                label = item.GetItemLabel()
            except Exception:
                label = ""
        current_path = (path + " > " + label).strip(" >")
        submenu = item.GetSubMenu()
        if submenu is not None:
            yield from iter_menu(submenu, current_path)
        yield menu, item, current_path


def find_menu_command(menu_path):
    wanted = [
        norm_label(part)
        for part in str(menu_path).replace("->", ">").split(">")
        if part.strip()
    ]
    for frame in candidate_frames():
        menu_bar = frame.GetMenuBar()
        if menu_bar is None:
            continue
        for menu_position in range(menu_bar.GetMenuCount()):
            menu = menu_bar.GetMenu(menu_position)
            try:
                top_label = menu_bar.GetMenuLabelText(menu_position)
            except Exception:
                top_label = ""
            for owner_menu, item, path in iter_menu(menu, top_label):
                actual = [norm_label(part) for part in path.split(" > ")]
                if actual == wanted or (not top_label and actual == wanted[1:]):
                    return frame, owner_menu, item, path
    return None, None, None, None


def open_menu(menu_path):
    _frame, owner_menu, item, path = find_menu_command(menu_path)
    if item is None:
        log("menu path not found: {!r}".format(menu_path))
        return False
    log("menu path found: {!r}, id={}".format(path, item.GetId()))
    return dispatch_menu_command(owner_menu, item, _frame)


def _log_preferences_direct_children(baseline_windows, attempts=12):
    windows = list(wx.GetTopLevelWindows())
    candidates = [window for window in windows if window not in baseline_windows]
    preferences = [
        window
        for window in candidates
        if "preferences" in str(getattr(window, "GetTitle", lambda: "")()).lower()
    ]
    if not preferences:
        preferences = [
            window
            for window in windows
            if "preferences" in str(getattr(window, "GetTitle", lambda: "")()).lower()
        ]
    if not preferences:
        if attempts > 0:
            call_later(200, _log_preferences_direct_children, baseline_windows, attempts - 1)
        else:
            log("Preferences window not found")
        return

    window = preferences[0]
    children = list(window.GetChildren())
    log("Preferences window found title={!r}".format(window.GetTitle()))
    for index, child in enumerate(children):
        child_type = "wx." + child.__class__.__name__
        try:
            name = child.GetName()
        except Exception:
            name = ""
        try:
            label = child.GetLabel()
        except Exception:
            label = ""
        try:
            child_id = child.GetId()
        except Exception:
            child_id = ""
        log("[{}]".format(index))
        log("type={}".format(child_type))
        log("name={}".format(name))
        log("label={}".format(label))
        log("id={}".format(child_id))
    log("Preferences direct child count={}".format(len(children)))


def test_preferences_direct_children():
    baseline_windows = tuple(wx.GetTopLevelWindows())
    call_later(200, _log_preferences_direct_children, baseline_windows)
    return open_menu("Preferences -> Preferences")


def _log_control_tree(control, depth=0):
    indent = "  " * depth
    control_type = "wx." + control.__class__.__name__
    try:
        name = control.GetName()
    except Exception:
        name = ""
    try:
        label = control.GetLabel()
    except Exception:
        label = ""
    try:
        control_id = control.GetId()
    except Exception:
        control_id = ""
    log(
        "{}depth={} type={} name={!r} label={!r} id={}".format(
            indent, depth, control_type, name, label, control_id
        )
    )
    for child in control.GetChildren():
        _log_control_tree(child, depth + 1)


def _log_preferences_control_tree(baseline_windows, attempts=12):
    windows = list(wx.GetTopLevelWindows())
    candidates = [window for window in windows if window not in baseline_windows]
    preferences = [
        window
        for window in candidates
        if "preferences" in str(getattr(window, "GetTitle", lambda: "")()).lower()
    ]
    if not preferences:
        preferences = [
            window
            for window in windows
            if "preferences" in str(getattr(window, "GetTitle", lambda: "")()).lower()
        ]
    if not preferences:
        if attempts > 0:
            call_later(200, _log_preferences_control_tree, baseline_windows, attempts - 1)
        else:
            log("Preferences window not found")
        return

    window = preferences[0]
    log("Preferences control tree found title={!r}".format(window.GetTitle()))
    _log_control_tree(window)


def test_preferences_control_tree():
    baseline_windows = tuple(wx.GetTopLevelWindows())
    call_later(200, _log_preferences_control_tree, baseline_windows)
    return open_menu("Preferences -> Preferences")


def _log_preferences_checkbox_value(baseline_windows, attempts=12):
    windows = list(wx.GetTopLevelWindows())
    candidates = [window for window in windows if window not in baseline_windows]
    preferences = [
        window
        for window in candidates
        if "preferences" in str(getattr(window, "GetTitle", lambda: "")()).lower()
    ]
    if not preferences:
        preferences = [
            window
            for window in windows
            if "preferences" in str(getattr(window, "GetTitle", lambda: "")()).lower()
        ]
    if not preferences:
        if attempts > 0:
            call_later(
                200, _log_preferences_checkbox_value, baseline_windows, attempts - 1
            )
        else:
            log("Preferences window not found")
        return

    checkbox = find_control(
        preferences[0], control_type=wx.CheckBox, label="Show icons in menus"
    )
    if checkbox is None:
        log("CheckBox not found label='Show icons in menus'")
        return
    log("Found CheckBox")
    log("label={!r}".format(checkbox.GetLabel()))
    log("value={}".format(get_control_value(checkbox)))


def test_preferences_checkbox_value():
    baseline_windows = tuple(wx.GetTopLevelWindows())
    call_later(200, _log_preferences_checkbox_value, baseline_windows)
    return open_menu("Preferences -> Preferences")


def _restore_preferences_checkbox(checkbox, original_value):
    set_control_value(checkbox, original_value)
    log("restore={}".format(get_control_value(checkbox)))


def _toggle_preferences_checkbox(baseline_windows, attempts=12):
    windows = list(wx.GetTopLevelWindows())
    candidates = [window for window in windows if window not in baseline_windows]
    preferences = [
        window
        for window in candidates
        if "preferences" in str(getattr(window, "GetTitle", lambda: "")()).lower()
    ]
    if not preferences:
        preferences = [
            window
            for window in windows
            if "preferences" in str(getattr(window, "GetTitle", lambda: "")()).lower()
        ]
    if not preferences:
        if attempts > 0:
            call_later(200, _toggle_preferences_checkbox, baseline_windows, attempts - 1)
        else:
            log("Preferences window not found")
        return

    checkbox = find_control(
        preferences[0], control_type=wx.CheckBox, label="Show icons in menus"
    )
    if checkbox is None:
        log("CheckBox not found label='Show icons in menus'")
        return

    before = get_control_value(checkbox)
    log("Found CheckBox label={!r}".format(checkbox.GetLabel()))
    log("before={}".format(before))
    set_control_value(checkbox, not before)
    log("after={}".format(get_control_value(checkbox)))
    preferences[0].Update()
    call_later(5000, _restore_preferences_checkbox, checkbox, before)


def test_preferences_checkbox_toggle_restore():
    baseline_windows = tuple(wx.GetTopLevelWindows())
    call_later(200, _toggle_preferences_checkbox, baseline_windows)
    return open_menu("Preferences -> Preferences")



PCB_SELECTION_FILTER_ITEMS = [
    "Footprints",
    "Text",
    "Tracks",
    "Vias",
    "Pads",
    "Graphics",
    "Zones",
    "Rule Areas",
    "Dimensions",
    "Other items",
]


def get_pcb_selection_filter_panel():
    """Return the PCB Editor Selection Filter panel.

    The visible 'Selection Filter' title is not exposed as a wx control.
    We therefore use the known 'Tracks' CheckBox as an anchor and return
    its direct parent Panel. Tests confirmed that all 12 filter CheckBoxes
    are direct children of this same Panel.
    """
    for window in wx.GetTopLevelWindows():
        try:
            if window.IsBeingDeleted():
                continue
            title = str(window.GetTitle())
        except Exception:
            continue

        if "PCB Editor" not in title:
            continue

        tracks = find_control(
            window,
            control_type=wx.CheckBox,
            label="Tracks",
        )
        if tracks is not None:
            parent = tracks.GetParent()
            if isinstance(parent, wx.Panel):
                return parent

    return None


def _pcb_selection_filter_control(panel, name):
    control = find_control(
        panel,
        control_type=wx.CheckBox,
        label=name,
    )
    if control is None:
        raise RuntimeError(
            "Selection Filter item not found: {}".format(name)
        )
    return control


def pcb_select_filter(name, value=None):
    """Read or change one PCB Editor Selection Filter item.

    Usage:
        pcb_select_filter("Tracks")          -> read current bool state
        pcb_select_filter("Tracks", True)    -> enable Tracks
        pcb_select_filter("Tracks", False)   -> disable Tracks

        pcb_select_filter("All items", True)
            -> enables every normal item below, but leaves Locked items unchanged.

        pcb_select_filter("All items", False)
            -> disables every normal item below, but leaves Locked items unchanged.

        pcb_select_filter("Locked items", True/False)
            -> changes Locked items directly and independently.

    The 'All items' command intentionally does not modify 'Locked items'.
    """

    valid_items = ["All items", "Locked items"] + PCB_SELECTION_FILTER_ITEMS
    if name not in valid_items:
        raise ValueError(
            "Unknown Selection Filter item: {}".format(name)
        )

    panel = get_pcb_selection_filter_panel()
    if panel is None:
        raise RuntimeError("Selection Filter panel not found")

    # Read.
    if value is None:
        if name == "All items":
            states = [
                bool(
                    get_control_value(
                        _pcb_selection_filter_control(panel, item_name)
                    )
                )
                for item_name in PCB_SELECTION_FILTER_ITEMS
            ]
            return all(states)

        control = _pcb_selection_filter_control(panel, name)
        return bool(get_control_value(control))

    value = bool(value)

    # All items controls every normal item, but never Locked items.
    if name == "All items":
        for item_name in PCB_SELECTION_FILTER_ITEMS:
            control = _pcb_selection_filter_control(panel, item_name)
            set_control_value(control, value)
        return value

    # Locked items and all normal items are individually controlled.
    control = _pcb_selection_filter_control(panel, name)
    set_control_value(control, value)
    return bool(get_control_value(control))


def pcb_select_filter_state():
    """Return all Selection Filter states as a dict."""
    panel = get_pcb_selection_filter_panel()
    if panel is None:
        raise RuntimeError("Selection Filter panel not found")

    result = {}
    for name in ["All items", "Locked items"] + PCB_SELECTION_FILTER_ITEMS:
        if name == "All items":
            result[name] = all(
                bool(
                    get_control_value(
                        _pcb_selection_filter_control(panel, item_name)
                    )
                )
                for item_name in PCB_SELECTION_FILTER_ITEMS
            )
        else:
            result[name] = bool(
                get_control_value(
                    _pcb_selection_filter_control(panel, name)
                )
            )
    return result



def _find_pcb_layer_row(name):
    """Return (PCB frame, row panel, label) for an Appearance/Layers row.

    KiCad builds each layer row as a wx.Panel whose window ID is the PCB layer
    ID.  The row's wx.StaticText uses the same ID and is bound to the native
    layer-selection handler.  Anchoring on the visible label keeps this helper
    independent of KiCad's private C++ class wrappers.
    """
    frame = find_pcb_frame()
    if frame is None:
        raise RuntimeError("PCB Editor frame not found")

    matches = find_controls(frame, control_type=wx.StaticText, label=name)
    rows = []
    for label in matches:
        try:
            parent = label.GetParent()
            if (
                isinstance(parent, wx.Panel)
                and parent.GetId() == label.GetId()
                and parent.IsShown()
            ):
                rows.append((parent, label))
        except (RuntimeError, AttributeError):
            continue

    if len(rows) != 1:
        raise RuntimeError(
            "PCB layer row not found or ambiguous: {!r} (matches={})".format(
                name, len(rows)
            )
        )

    return frame, rows[0][0], rows[0][1]


def _send_mouse_event(control, event_type):
    event = wx.MouseEvent(event_type)
    event.SetEventObject(control)
    try:
        event.SetId(control.GetId())
    except (AttributeError, RuntimeError):
        pass
    return bool(control.GetEventHandler().ProcessEvent(event))


def _process_pending_gui_events():
    """Flush only already-posted wx events generated by KiCad controls."""
    app = wx.GetApp()
    if app is not None and hasattr(app, "ProcessPendingEvents"):
        app.ProcessPendingEvents()


def _find_layer_visibility_bitmap(row, label):
    """Find BITMAP_TOGGLE's inner wx.StaticBitmap for one layer row."""
    children = list(row.GetChildren())
    visibility = None

    # Preferred: KiCad's BITMAP_TOGGLE has this tooltip in English builds.
    for child in children:
        if child is label:
            continue
        try:
            tooltip = child.GetToolTipText()
        except (RuntimeError, AttributeError):
            tooltip = ""
        if "show or hide this layer" in str(tooltip).lower():
            visibility = child
            break

    # Locale-independent fallback.  KiCad creates row controls in this order:
    # indicator, color swatch, visibility toggle, text label.
    if visibility is None:
        try:
            label_index = children.index(label)
        except ValueError:
            label_index = -1
        if label_index > 0:
            candidate = children[label_index - 1]
            try:
                if candidate.GetId() == label.GetId():
                    visibility = candidate
            except (RuntimeError, AttributeError):
                pass

    if visibility is None:
        raise RuntimeError("Layer visibility control not found: {!r}".format(label.GetLabel()))

    bitmaps = []
    for child in visibility.GetChildren():
        if isinstance(child, wx.StaticBitmap):
            bitmaps.append(child)
    if len(bitmaps) != 1:
        raise RuntimeError(
            "Layer visibility bitmap not found: {!r} (matches={})".format(
                label.GetLabel(), len(bitmaps)
            )
        )
    return bitmaps[0]


def _pcb_board():
    try:
        import pcbnew
    except Exception as exc:
        raise RuntimeError("pcbnew module unavailable: {}".format(exc))
    board = pcbnew.GetBoard()
    if board is None:
        raise RuntimeError("No PCB board is currently open")
    return board


def _pcb_layer_visible(layer_id):
    board = _pcb_board()
    return bool(board.IsLayerVisible(layer_id))


def _find_layer_selector(frame, target_name=None):
    """Best-effort lookup of the top toolbar layer selector for verification."""
    target = norm_label(target_name) if target_name is not None else None
    for control in iter_controls(frame):
        get_count = getattr(control, "GetCount", None)
        get_string = getattr(control, "GetString", None)
        get_selected = getattr(control, "GetStringSelection", None)
        if not (callable(get_count) and callable(get_string) and callable(get_selected)):
            continue
        try:
            count = int(get_count())
            if count <= 0 or count > 256:
                continue
            labels = [norm_label(get_string(index)) for index in range(count)]
        except Exception:
            continue
        # A real PCB layer selector contains at least F.Cu and B.Cu.
        if "f.cu" not in labels or "b.cu" not in labels:
            continue
        if target is not None and target not in labels:
            continue
        return control
    return None


def pcb_select_layer(name):
    """Select the active PCB layer from Appearance > Layers.

    Example:
        pcb_select_layer("F.Cu")
        pcb_select_layer("B.Adhesive")
        pcb_select_layer("Edge.Cuts")

    The function dispatches the same wxEVT_LEFT_DOWN event used by a real click
    on KiCad's layer label, so KiCad itself updates the active layer, toolbar,
    Appearance panel indicator, and canvas state.
    """
    frame, _row, label = _find_pcb_layer_row(name)
    requested = str(label.GetLabel())
    layer_id = label.GetId()

    processed = _send_mouse_event(label, wx.wxEVT_LEFT_DOWN)
    if not processed:
        raise RuntimeError("KiCad did not process layer selection: {!r}".format(requested))
    _process_pending_gui_events()

    # Prefer native active-layer verification when the embedded wrapper exposes
    # the PCB_EDIT_FRAME method.  Otherwise verify through the toolbar selector.
    get_active = getattr(frame, "GetActiveLayer", None)
    if callable(get_active):
        try:
            active = int(get_active())
            if active != int(layer_id):
                raise RuntimeError(
                    "Layer selection did not change: requested={!r} id={} active_id={}".format(
                        requested, layer_id, active
                    )
                )
            return requested
        except TypeError:
            pass

    selector = _find_layer_selector(frame, requested)
    if selector is not None:
        try:
            selected = str(selector.GetStringSelection())
            if norm_label(selected) != norm_label(requested):
                raise RuntimeError(
                    "Layer selection did not change: requested={!r} selected={!r}".format(
                        requested, selected
                    )
                )
        except AttributeError:
            pass

    return requested


def _pcb_layer_rows(frame=None):
    """Return visible Appearance/Layers rows as (y, label_id, name, row, label)."""
    if frame is None:
        frame = find_pcb_frame()
    if frame is None:
        raise RuntimeError("PCB Editor frame not found")

    rows = []
    seen = set()
    for label in find_controls(frame, control_type=wx.StaticText):
        try:
            parent = label.GetParent()
            if not isinstance(parent, wx.Panel):
                continue
            if parent.GetId() != label.GetId() or not parent.IsShown():
                continue
            name = str(label.GetLabel()).strip()
            if not name:
                continue
            key = (int(label.GetId()), norm_label(name))
            if key in seen:
                continue
            seen.add(key)
            try:
                y = int(parent.GetScreenPosition().y)
            except Exception:
                try:
                    y = int(parent.GetPosition().y)
                except Exception:
                    y = len(rows)
            rows.append((y, int(label.GetId()), name, parent, label))
        except (RuntimeError, AttributeError, TypeError, ValueError):
            continue

    rows.sort(key=lambda item: item[0])
    return rows


def _find_layer_indicator_bitmap(row, label):
    """Return the Appearance/Layers active-layer arrow bitmap for one row.

    KiCad creates the row controls in this order:
      active-layer indicator, color swatch, visibility toggle, text label.

    The diagnostic capture for KiCad 9.0.9 confirmed that the indicator is the
    first bitmap path (row/0/0).  Keep the lookup structural rather than relying
    on layer names, IDs, focus, or cached state.
    """
    children = list(row.GetChildren())
    if not children:
        raise RuntimeError("Layer row has no children: {!r}".format(label.GetLabel()))

    try:
        label_index = children.index(label)
    except ValueError:
        label_index = len(children)

    # Only controls before the text label belong to the row decoration area.
    # The first of them is the active-layer indicator control.
    candidates = children[:label_index]
    if not candidates:
        raise RuntimeError("Layer indicator control not found: {!r}".format(label.GetLabel()))

    indicator = candidates[0]
    bitmaps = []
    if isinstance(indicator, wx.StaticBitmap):
        bitmaps.append(indicator)
    for child in iter_controls(indicator):
        if isinstance(child, wx.StaticBitmap):
            bitmaps.append(child)

    if len(bitmaps) != 1:
        raise RuntimeError(
            "Layer indicator bitmap not found: {!r} (matches={})".format(
                label.GetLabel(), len(bitmaps)
            )
        )
    return bitmaps[0]


def _bitmap_alpha_gt_16_count(bitmap):
    """Return effective-alpha pixel count above 16 for a wx.Bitmap.

    The OFF indicator in the tested Windows KiCad build contains one
    near-transparent pixel (alpha=10), while the ON arrow contains 25 pixels
    above alpha 16.  Using a threshold avoids treating that OFF pixel as ON.
    """
    try:
        if not bitmap.IsOk():
            raise RuntimeError("invalid bitmap")
        image = bitmap.ConvertToImage()
        width = int(image.GetWidth())
        height = int(image.GetHeight())
        pixel_count = width * height
        rgb = bytes(image.GetData())
        alpha = bytes(image.GetAlpha()) if image.HasAlpha() else None
        mask = (
            (int(image.GetMaskRed()), int(image.GetMaskGreen()), int(image.GetMaskBlue()))
            if image.HasMask()
            else None
        )
    except Exception as exc:
        raise RuntimeError("Could not read layer indicator bitmap: {}".format(exc))

    if alpha is None and mask is None:
        raise RuntimeError("Layer indicator bitmap has neither alpha nor mask")

    count = 0
    for index in range(pixel_count):
        if mask is not None:
            base = index * 3
            if tuple(rgb[base:base + 3]) == mask:
                continue
        effective_alpha = alpha[index] if alpha is not None else 255
        if effective_alpha > 16:
            count += 1
    return count


def _pcb_selected_layer_from_indicator(frame=None):
    """Return the live active layer from the Appearance selection arrow.

    This intentionally does not use focus, background colour, a MacroBK cache,
    or the requested value previously passed to pcb_select_layer().
    """
    if frame is None:
        frame = find_pcb_frame()
    if frame is None:
        raise RuntimeError("PCB Editor frame not found")

    selected = []
    sampled = []
    for _y, _layer_id, name, row, label in _pcb_layer_rows(frame):
        try:
            bitmap = _find_layer_indicator_bitmap(row, label)
            alpha_gt_16 = _bitmap_alpha_gt_16_count(bitmap.GetBitmap())
        except (RuntimeError, AttributeError) as exc:
            sampled.append((name, "error:{}".format(exc)))
            continue
        sampled.append((name, alpha_gt_16))
        if alpha_gt_16 > 0:
            selected.append((name, alpha_gt_16))

    if len(selected) == 1:
        return selected[0][0]

    raise RuntimeError(
        "Current active PCB layer indicator is ambiguous: selected={} sampled={}".format(
            selected, sampled
        )
    )


def pcb_get_selected_layer():
    """Return the layer that currently has KiCad's active-layer arrow."""
    return _pcb_selected_layer_from_indicator()


def _pcb_active_layer_name(frame=None):
    """Compatibility wrapper for the verified Appearance indicator reader."""
    return _pcb_selected_layer_from_indicator(frame)


def _pcb_copper_layers(frame=None):
    """Return enabled copper layer names in Appearance stack order.

    Only *.Cu rows are returned. Non-copper layers such as Mask, Silkscreen,
    Adhesive, Edge.Cuts, and User layers are excluded.
    """
    if frame is None:
        frame = find_pcb_frame()
    if frame is None:
        raise RuntimeError("PCB Editor frame not found")

    board = _pcb_board()
    is_enabled = getattr(board, "IsLayerEnabled", None)
    result = []
    for _y, layer_id, name, _row, _label in _pcb_layer_rows(frame):
        if not name.lower().endswith(".cu"):
            continue
        if callable(is_enabled):
            try:
                if not bool(is_enabled(layer_id)):
                    continue
            except (RuntimeError, TypeError):
                pass
        result.append(name)

    if not result:
        raise RuntimeError("No enabled copper layers found")
    return result


def _pcb_move_copper_layer(step):
    """Move one step within enabled copper layers and return the new layer.

    step < 0: UP / previous copper layer
    step > 0: DOWN / next copper layer

    Policy when the current layer is not copper:
      UP   -> last copper layer (normally B.Cu)
      DOWN -> first copper layer (normally F.Cu)
    """
    frame = find_pcb_frame()
    if frame is None:
        raise RuntimeError("PCB Editor frame not found")

    copper = _pcb_copper_layers(frame)
    current = _pcb_selected_layer_from_indicator(frame)

    if current in copper:
        index = copper.index(current)
        target = copper[(index - 1) % len(copper)] if step < 0 else copper[(index + 1) % len(copper)]
    else:
        target = copper[-1] if step < 0 else copper[0]

    pcb_select_layer(target)
    _process_pending_gui_events()
    actual = _pcb_selected_layer_from_indicator(frame)
    if norm_label(actual) != norm_label(target):
        raise RuntimeError(
            "Copper layer move did not reach target: current={!r} target={!r} actual={!r}".format(
                current, target, actual
            )
        )
    return actual


def pcb_layer_up():
    """Move to the previous enabled copper layer.

    Copper layers wrap around.  From any non-copper layer, UP enters the last
    copper layer in the stack (normally B.Cu).
    """
    return _pcb_move_copper_layer(-1)


def pcb_layer_down():
    """Move to the next enabled copper layer.

    Copper layers wrap around.  From any non-copper layer, DOWN enters the first
    copper layer in the stack (normally F.Cu).
    """
    return _pcb_move_copper_layer(1)


def _pcb_width_mm_to_iu(width_mm, pcbnew):
    """Validate a millimetre width and convert it to KiCad internal units."""
    try:
        value = float(width_mm)
    except (TypeError, ValueError):
        raise ValueError("Track width must be a number in mm: {!r}".format(width_mm))

    if value <= 0.0:
        raise ValueError("Track width must be greater than 0 mm: {!r}".format(width_mm))

    width_iu = int(pcbnew.FromMM(value))
    if width_iu <= 0:
        raise ValueError("Track width is too small for KiCad internal units: {!r}".format(width_mm))
    return value, width_iu


def pcb_set_selected_track_width(width_mm):
    """Set width of the currently selected routed track segment(s), in mm.

    Only selected PCB_TRACK items are changed.  PCB_VIA is explicitly excluded,
    and connected but unselected track segments are not touched.

    Returns the number of selected track segments whose width actually changed.

    Note: this uses KiCad's public Python item mutation API.  KiCad 9's Python
    bindings do not expose the editor BOARD_COMMIT/undo path used by the native
    Change Track Width command, so this helper should be live-tested for the
    desired Ctrl+Z behaviour before relying on undo.
    """
    try:
        import pcbnew
    except Exception as exc:
        raise RuntimeError("pcbnew module unavailable: {}".format(exc))

    board = _pcb_board()
    _width_mm, width_iu = _pcb_width_mm_to_iu(width_mm, pcbnew)

    try:
        selected_items = list(pcbnew.GetCurrentSelection())
    except Exception as exc:
        raise RuntimeError("Could not read current PCB selection: {}".format(exc))

    selected_tracks = []
    via_type = getattr(pcbnew, "PCB_VIA", None)
    track_type = getattr(pcbnew, "PCB_TRACK", None)
    if track_type is None:
        raise RuntimeError("pcbnew.PCB_TRACK is unavailable")

    for item in selected_items:
        try:
            if via_type is not None and isinstance(item, via_type):
                continue
            if isinstance(item, track_type):
                selected_tracks.append(item)
        except TypeError:
            continue

    if not selected_tracks:
        raise RuntimeError("No routed track segment is currently selected")

    changed = 0
    changed_items = []
    for item in selected_tracks:
        try:
            before = int(item.GetWidth())
            if before == width_iu:
                continue
            item.SetWidth(width_iu)
            actual = int(item.GetWidth())
        except Exception as exc:
            raise RuntimeError("Could not change selected track width: {}".format(exc))

        if actual != width_iu:
            raise RuntimeError(
                "Selected track width verification failed: requested_iu={} actual_iu={}".format(
                    width_iu, actual
                )
            )
        changed += 1
        changed_items.append(item)

    # Notify the board/view about changed geometry.  OnItemChanged is public in
    # KiCad 9 Python and avoids assuming a Python-exposed BOARD_COMMIT object.
    for item in changed_items:
        notify = getattr(board, "OnItemChanged", None)
        if callable(notify):
            try:
                notify(item)
            except Exception:
                pass

    if changed:
        refresh = getattr(pcbnew, "Refresh", None)
        if callable(refresh):
            refresh()
        update_ui = getattr(pcbnew, "UpdateUserInterface", None)
        if callable(update_ui):
            update_ui()
        _process_pending_gui_events()

    return changed


_routing_width_native_state = globals().get("_routing_width_native_state", None)
_routing_width_native_serial = globals().get("_routing_width_native_serial", 0)


def _is_descendant_window(window, ancestor):
    """Return True when *window* belongs to *ancestor*'s wx hierarchy."""
    current = window
    while current is not None:
        if current is ancestor:
            return True
        try:
            current = current.GetParent()
        except (AttributeError, RuntimeError):
            return False
    return False


def _pcb_hotkey_focus_target(frame):
    """Best-effort focus target for a native PCB hotkey.

    Phone-triggered actions normally arrive while the canvas already owns focus;
    preserve that first.  Run Test moves focus to MacroBK Manager, so then prefer
    the PCB child currently under the mouse, followed by a canvas/draw-panel-like
    child.  The frame itself is the final fallback.
    """
    try:
        focus = wx.Window.FindFocus()
        if focus is not None and _is_descendant_window(focus, frame):
            return focus
    except Exception:
        pass

    finder = getattr(wx, "FindWindowAtPointer", None)
    if callable(finder):
        try:
            pointed = finder()
            if isinstance(pointed, tuple):
                pointed = pointed[0]
            if pointed is not None and _is_descendant_window(pointed, frame):
                return pointed
        except Exception:
            pass

    best = None
    best_score = -1
    for control in iter_controls(frame):
        try:
            if not control.IsShown() or not control.IsEnabled():
                continue
            class_name = str(getattr(control, "GetClassName", lambda: "")()).lower()
            native_name = str(control.GetClassInfo().GetClassName()).lower()
            name = str(control.GetName()).lower()
            text = " ".join((class_name, native_name, name))
            size = control.GetClientSize()
            area = max(0, int(size.x)) * max(0, int(size.y))
        except Exception:
            continue

        keyword_score = 0
        if "canvas" in text:
            keyword_score += 100000000
        if "gal" in text:
            keyword_score += 50000000
        if "draw" in text:
            keyword_score += 10000000
        score = keyword_score + min(area, 9000000)
        if score > best_score:
            best_score = score
            best = control

    return best or frame


def _send_native_q_hotkey(frame):
    """Inject one real Windows Q keystroke into KiCad's focused PCB window.

    This intentionally uses the OS input path instead of synthesizing a wx
    KeyEvent.  KiCad's Interactive Router hotkeys are consumed by its tool
    manager, and direct wx ProcessEvent key synthesis does not reach that path.
    """
    if os.name != "nt":
        raise RuntimeError("Native Q routing-width automation currently requires Windows")

    try:
        import ctypes
        from ctypes import wintypes

        target = _pcb_hotkey_focus_target(frame)
        try:
            frame.Raise()
        except Exception:
            pass
        try:
            target.SetFocus()
        except Exception:
            pass

        user32 = ctypes.windll.user32
        try:
            user32.SetForegroundWindow(wintypes.HWND(int(frame.GetHandle())))
        except Exception:
            pass

        # keybd_event goes through the same Windows keyboard path as a physical Q.
        VK_Q = 0x51
        KEYEVENTF_KEYUP = 0x0002
        user32.keybd_event(VK_Q, 0, 0, 0)
        user32.keybd_event(VK_Q, 0, KEYEVENTF_KEYUP, 0)
    except Exception as exc:
        raise RuntimeError("Could not send native Q hotkey to PCB Editor: {}".format(exc))


def _find_custom_track_via_dialog(baseline_windows):
    """Find KiCad's native Custom Track/Via Size dialog after Q."""
    windows = list(wx.GetTopLevelWindows())
    ordered = [window for window in windows if window not in baseline_windows]
    ordered += [window for window in windows if window in baseline_windows]

    for window in ordered:
        try:
            if not window.IsShown():
                continue
            labels = []
            for child in iter_controls(window):
                if isinstance(child, wx.StaticText):
                    labels.append(norm_label(child.GetLabel()))
            has_track = any(label.startswith("track width") for label in labels)
            has_via = any("via" in label for label in labels)
            title = norm_label(getattr(window, "GetTitle", lambda: "")())
            if has_track and (has_via or ("track" in title and "via" in title)):
                return window
        except Exception:
            continue
    return None


def _find_track_width_text_control(dialog):
    """Locate the text editor paired with the native dialog's Track width label."""
    labels = []
    text_controls = []
    for control in iter_controls(dialog):
        try:
            if isinstance(control, wx.StaticText) and norm_label(control.GetLabel()).startswith("track width"):
                labels.append(control)
            if isinstance(control, wx.TextCtrl) and control.IsShown() and control.IsEnabled():
                text_controls.append(control)
        except (RuntimeError, AttributeError):
            continue

    if len(labels) != 1:
        raise RuntimeError("Custom Track/Via Size Track width label is missing or ambiguous")
    if not text_controls:
        raise RuntimeError("Custom Track/Via Size track-width editor was not found")

    label = labels[0]
    try:
        label_rect = label.GetScreenRect()
        label_cy = label_rect.y + label_rect.height / 2.0

        def score(control):
            rect = control.GetScreenRect()
            cy = rect.y + rect.height / 2.0
            right_penalty = 0 if rect.x >= label_rect.x else 10000
            return abs(cy - label_cy) + right_penalty

        return min(text_controls, key=score)
    except Exception:
        # Generated KiCad dialogs create the Track width editor before the via
        # editors, so traversal order is a safe fallback after label matching.
        return text_controls[0]


def _command_ok_button(dialog):
    """Press the dialog's native OK button so TransferDataFromWindow runs."""
    button = None
    try:
        button = dialog.FindWindowById(wx.ID_OK)
    except Exception:
        pass
    if button is None:
        for control in iter_controls(dialog):
            try:
                if isinstance(control, wx.Button) and control.GetId() == wx.ID_OK:
                    button = control
                    break
            except Exception:
                continue
    if button is None:
        raise RuntimeError("Custom Track/Via Size OK button was not found")

    event = wx.CommandEvent(wx.wxEVT_BUTTON, wx.ID_OK)
    event.SetEventObject(button)
    command = getattr(button, "Command", None)
    if callable(command):
        command(event)
        return
    if not button.GetEventHandler().ProcessEvent(event):
        raise RuntimeError("KiCad did not process Custom Track/Via Size OK")


def _finish_native_routing_width_request(serial, requested_mm, requested_iu):
    global _routing_width_native_state
    state = _routing_width_native_state
    if not state or state.get("serial") != serial:
        return

    try:
        import pcbnew
        board = _pcb_board()
        settings = board.GetDesignSettings()
        custom_iu = int(settings.GetCustomTrackWidth())
        custom_mode = bool(settings.UseCustomTrackViaSize())
        if custom_iu != requested_iu or not custom_mode:
            log(
                "native Q routing width verification failed: requested_mm={} requested_iu={} "
                "custom_iu={} custom_mode={}".format(
                    requested_mm, requested_iu, custom_iu, custom_mode
                )
            )
        else:
            log("native Q routing width applied: {:.6g} mm".format(requested_mm))
    except Exception as exc:
        log("native Q routing width verification error: {}".format(exc))
    finally:
        _routing_width_native_state = None


def _fill_native_routing_width_dialog(serial, attempts=40):
    """Timer callback: fill Q's native dialog and press OK."""
    global _routing_width_native_state
    state = _routing_width_native_state
    if not state or state.get("serial") != serial:
        return

    dialog = _find_custom_track_via_dialog(state["baseline_windows"])
    if dialog is None:
        if attempts > 0:
            call_later(50, _fill_native_routing_width_dialog, serial, attempts - 1)
            return
        _routing_width_native_state = None
        log("native Q routing width failed: Custom Track/Via Size dialog did not appear")
        return

    try:
        editor = _find_track_width_text_control(dialog)
        # An explicit unit suffix makes the API's width_mm contract independent
        # of PCB Editor's currently selected display units (mm/in/mil).
        text = "{:.12g} mm".format(state["requested_mm"])
        change_value = getattr(editor, "ChangeValue", None)
        if callable(change_value):
            change_value(text)
        else:
            editor.SetValue(text)
        editor.SetInsertionPointEnd()
        _command_ok_button(dialog)
        call_later(
            100,
            _finish_native_routing_width_request,
            serial,
            state["requested_mm"],
            state["requested_iu"],
        )
    except Exception as exc:
        _routing_width_native_state = None
        log("native Q routing width dialog automation failed: {}".format(exc))


def pcb_set_routing_track_width(width_mm):
    """Set routing width by executing KiCad's native Q action.

    Unlike directly changing BOARD_DESIGN_SETTINGS, this deliberately follows
    the user's verified KiCad path:

        native Q -> Custom Track/Via Size dialog -> OK
        -> ROUTER_TOOL::CustomTrackWidthDialog
        -> onTrackViaSizeChanged -> UpdateSizes -> Move

    That native router notification is what updates the active routing head
    without rebuilding the whole PCB view.  The requested width is entered with
    an explicit ``mm`` suffix; all via fields are left untouched.

    The helper schedules the modal-dialog fill on wx timers and returns the
    requested width immediately.  Repeated calls are rejected until the current
    native Q dialog transaction finishes.
    """
    global _routing_width_native_state, _routing_width_native_serial

    try:
        import pcbnew
    except Exception as exc:
        raise RuntimeError("pcbnew module unavailable: {}".format(exc))

    requested_mm, width_iu = _pcb_width_mm_to_iu(width_mm, pcbnew)
    frame = find_pcb_frame()
    if frame is None:
        raise RuntimeError("PCB Editor frame not found")

    if _routing_width_native_state is not None:
        raise RuntimeError("A native Q routing-width change is already in progress")

    _routing_width_native_serial += 1
    serial = _routing_width_native_serial
    _routing_width_native_state = {
        "serial": serial,
        "requested_mm": requested_mm,
        "requested_iu": width_iu,
        "baseline_windows": tuple(wx.GetTopLevelWindows()),
    }

    # Queue the dialog observer before Q.  Q itself is a real OS keystroke so
    # KiCad's TOOL_MANAGER, rather than MacroBK, owns the router state change.
    call_later(25, _fill_native_routing_width_dialog, serial, 40)
    try:
        _send_native_q_hotkey(frame)
    except Exception:
        _routing_width_native_state = None
        raise

    return requested_mm

def pcb_set_netclass_track_width():
    """Return routing track width control to the netclass/rule setting.

    This disables KiCad's custom track/via-size mode and selects track-width
    index 0 ("use netclass width"). Existing routed tracks are not modified.
    The return value is the effective current routing width in millimetres when
    KiCad exposes it.

    KiCad 9 exposes one shared custom track/via-size enable flag, so leaving
    custom track-width mode also leaves custom via-size mode.
    """
    try:
        import pcbnew
    except Exception as exc:
        raise RuntimeError("pcbnew module unavailable: {}".format(exc))

    board = _pcb_board()
    try:
        settings = board.GetDesignSettings()
    except Exception as exc:
        raise RuntimeError("Could not access PCB design settings: {}".format(exc))

    required = (
        "UseCustomTrackViaSize",
        "SetTrackWidthIndex",
        "GetCurrentTrackWidth",
    )
    missing = [name for name in required if not callable(getattr(settings, name, None))]
    if missing:
        raise RuntimeError(
            "KiCad netclass-width API unavailable: {}".format(", ".join(missing))
        )

    try:
        # Track-width index 0 is KiCad's "use netclass width" entry.
        settings.UseCustomTrackViaSize(False)
        settings.SetTrackWidthIndex(0)
        actual_iu = int(settings.GetCurrentTrackWidth())
    except Exception as exc:
        raise RuntimeError("Could not restore netclass track width: {}".format(exc))

    # Match KiCad's normal routing-width UI refresh path as closely as the
    # public Python bindings allow. This does not alter any existing track.
    update_ui = getattr(pcbnew, "UpdateUserInterface", None)
    if callable(update_ui):
        update_ui()
    _process_pending_gui_events()

    try:
        return float(pcbnew.ToMM(actual_iu))
    except Exception:
        return actual_iu


def pcb_onoff_layer(name, value=None):
    """Read or change one PCB layer's visibility in Appearance > Layers.

    Examples:
        pcb_onoff_layer("B.Cu")          -> current visibility (bool)
        pcb_onoff_layer("B.Cu", True)    -> show layer
        pcb_onoff_layer("B.Cu", False)   -> hide layer

    When a change is required this sends the same LEFT_UP event to KiCad's
    BITMAP_TOGGLE bitmap that a user click generates.  KiCad then updates its
    own view, board visibility state, layer preset state, and canvas.
    """
    _frame, row, label = _find_pcb_layer_row(name)
    layer_id = label.GetId()
    current = _pcb_layer_visible(layer_id)
    if value is None:
        return current

    wanted = bool(value)
    if current == wanted:
        return current

    bitmap = _find_layer_visibility_bitmap(row, label)
    processed = _send_mouse_event(bitmap, wx.wxEVT_LEFT_UP)
    if not processed:
        raise RuntimeError("KiCad did not process layer visibility click: {!r}".format(name))

    # BITMAP_TOGGLE posts its TOGGLE_CHANGED command event to its parent.
    _process_pending_gui_events()
    actual = _pcb_layer_visible(layer_id)
    if actual != wanted:
        raise RuntimeError(
            "Layer visibility did not change: {!r} requested={} actual={}".format(
                label.GetLabel(), wanted, actual
            )
        )
    return actual


def find_drc_command():
    for frame in candidate_frames():
        menu_bar = frame.GetMenuBar()
        if menu_bar is None:
            continue
        try:
            title = frame.GetTitle()
        except Exception:
            title = "?"

        for menu_position in range(menu_bar.GetMenuCount()):
            menu = menu_bar.GetMenu(menu_position)
            try:
                top_label = menu_bar.GetMenuLabelText(menu_position)
            except Exception:
                top_label = ""

            for owner_menu, item, path in iter_menu(menu, top_label):
                try:
                    label = item.GetItemLabelText()
                except Exception:
                    label = ""
                if is_drc_label(label):
                    log(
                        "DRC menu found: frame={!r}, path={!r}, id={}".format(
                            title, path, item.GetId()
                        )
                    )
                    return frame, owner_menu, item, path
    return None, None, None, None


def dispatch_menu_command(owner_menu, item, frame=None):
    cmd_id = item.GetId()
    try:
        if hasattr(owner_menu, "SendEvent"):
            result = owner_menu.SendEvent(cmd_id)
            log("menu.SendEvent({}) -> {}".format(cmd_id, repr(result)))
            if bool(result) or result is None:
                return True
    except Exception as exc:
        log("menu.SendEvent error: " + repr(exc))

    try:
        event = wx.CommandEvent(wx.wxEVT_COMMAND_MENU_SELECTED, cmd_id)
        event.SetEventObject(owner_menu)
        if hasattr(owner_menu, "ProcessEvent"):
            result = owner_menu.ProcessEvent(event)
            log("menu.ProcessEvent -> " + repr(result))
            if result:
                return True
    except Exception as exc:
        log("menu.ProcessEvent error: " + repr(exc))
    if frame is not None:
        event = wx.CommandEvent(wx.wxEVT_COMMAND_MENU_SELECTED, cmd_id)
        event.SetEventObject(frame)
        return bool(frame.GetEventHandler().ProcessEvent(event))
    return False


def open_drc_window(source="unknown", show_error=True):
    try:
        _frame, owner_menu, item, _path = find_drc_command()
        if item is None:
            log("DRC menu not found")
            if show_error:
                wx.MessageBox(
                    "KiCad의 Design Rules Checker 메뉴를 찾지 못했습니다.\n\n로그:\n"
                    + LOG_PATH,
                    "MacroBK DRC",
                    wx.OK | wx.ICON_ERROR,
                )
            return False

        ok = dispatch_menu_command(owner_menu, item, _frame)
        log("request source={} id={} result={}".format(source, item.GetId(), ok))
        if not ok and show_error:
            wx.MessageBox(
                "DRC 메뉴를 찾았지만 실행하지 못했습니다.\n\n로그:\n" + LOG_PATH,
                "MacroBK DRC",
                wx.OK | wx.ICON_ERROR,
            )
        return ok
    except Exception:
        log(traceback.format_exc())
        if show_error:
            wx.MessageBox(
                "MacroBK DRC 실행 중 예외가 발생했습니다.\n\n로그:\n" + LOG_PATH,
                "MacroBK DRC",
                wx.OK | wx.ICON_ERROR,
            )
        return False
