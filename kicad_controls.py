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
            wx.CallLater(200, _log_preferences_direct_children, baseline_windows, attempts - 1)
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
    wx.CallLater(200, _log_preferences_direct_children, baseline_windows)
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
            wx.CallLater(200, _log_preferences_control_tree, baseline_windows, attempts - 1)
        else:
            log("Preferences window not found")
        return

    window = preferences[0]
    log("Preferences control tree found title={!r}".format(window.GetTitle()))
    _log_control_tree(window)


def test_preferences_control_tree():
    baseline_windows = tuple(wx.GetTopLevelWindows())
    wx.CallLater(200, _log_preferences_control_tree, baseline_windows)
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
            wx.CallLater(
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
    wx.CallLater(200, _log_preferences_checkbox_value, baseline_windows)
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
            wx.CallLater(200, _toggle_preferences_checkbox, baseline_windows, attempts - 1)
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
    wx.CallLater(5000, _restore_preferences_checkbox, checkbox, before)


def test_preferences_checkbox_toggle_restore():
    baseline_windows = tuple(wx.GetTopLevelWindows())
    wx.CallLater(200, _toggle_preferences_checkbox, baseline_windows)
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
