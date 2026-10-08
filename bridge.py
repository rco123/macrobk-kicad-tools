import ctypes
from ctypes import wintypes
from contextlib import redirect_stdout
import copy
from datetime import datetime
import io
import json
import os
import socket
import sys
import threading
import traceback
import uuid

import pcbnew
import wx
import wx.stc as stc


PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_DIR = os.path.join(PLUGIN_DIR, "icons")
CONFIG_PATH = os.path.join(PLUGIN_DIR, "config.json")
LOG_PATH = os.path.join(PLUGIN_DIR, "macrobk_drc.log")

LOCAL_TRIGGER_GROUP = "239.255.77.77"
LOCAL_TRIGGER_PORT = 47831
LOCAL_TRIGGER_INTERFACE = "127.0.0.1"

DEFAULT_CONFIG = {
    "name": "Open DRC",
    "trigger": {
        "enabled": True,
        "ctrl": True,
        "win": True,
        "alt": False,
        "shift": False,
        "key": "F12",
    },
    "phone": {
        "host": "127.0.0.1",
        "port": 47831,
        "command": "KICAD_DRC",
    },
    "action": {"type": "python", "script": "open_drc_window()"},
}

HOTKEY_ID = 0x4D42
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
ERROR_HOTKEY_ALREADY_REGISTERED = 1409

_started = False
_manager_frame = None
_keyboard_status = "Starting"
_phone_status = "Starting"
_hotkey_thread = None
_hotkey_thread_id = None
_hotkey_generation = 0
_hotkey_lock = threading.Lock()
_log_lock = threading.Lock()


def _default_config_copy():
    return json.loads(json.dumps(DEFAULT_CONFIG))


def log(message):
    line = "[{}] [MacroBK] {}".format(
        datetime.now().strftime("%H:%M:%S"), str(message)
    )
    try:
        sys.__stdout__.write(line + "\n")
        sys.__stdout__.flush()
    except Exception:
        pass

    try:
        with _log_lock:
            with open(LOG_PATH, "a", encoding="utf-8") as file:
                file.write(line + "\n")
    except Exception:
        pass

    manager = _manager_frame
    if manager is not None:
        try:
            wx.CallAfter(manager.append_result, line)
        except Exception:
            pass


def load_config():
    config = _default_config_copy()

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as file:
            loaded = json.load(file)

        if isinstance(loaded.get("name"), str):
            config["name"] = loaded["name"]

        if isinstance(loaded.get("trigger"), dict):
            config["trigger"].update(loaded["trigger"])
        elif isinstance(loaded.get("keyboard"), dict):
            config["trigger"].update(loaded["keyboard"])
            config["trigger"]["enabled"] = bool(
                loaded.get("keyboard_enabled", True)
            )

        if isinstance(loaded.get("phone"), dict):
            config["phone"].update(loaded["phone"])
        else:
            if "udp_host" in loaded:
                config["phone"]["host"] = loaded["udp_host"]
            if "udp_port" in loaded:
                config["phone"]["port"] = loaded["udp_port"]
            if "phone_command" in loaded:
                config["phone"]["command"] = loaded["phone_command"]

        if isinstance(loaded.get("action"), dict):
            config["action"].update(loaded["action"])

        if isinstance(loaded.get("actions"), list):
            config["actions"] = loaded["actions"]
        if isinstance(loaded.get("selected_action_id"), str):
            config["selected_action_id"] = loaded["selected_action_id"]

    except FileNotFoundError:
        pass
    except Exception as exc:
        log("config load error: " + repr(exc))

    actions = config.get("actions")
    if not isinstance(actions, list) or not actions:
        actions = [
            {
                "id": "open-drc",
                "name": str(config.get("name", "Open DRC")),
                "icon": "drc",
                "trigger": copy.deepcopy(config["trigger"]),
                "phone": copy.deepcopy(config["phone"]),
                "action": copy.deepcopy(config["action"]),
            }
        ]

    normalized_actions = []
    for index, item in enumerate(actions):
        if not isinstance(item, dict):
            continue
        normalized_actions.append(
            {
                "id": str(item.get("id") or "action-{}".format(index + 1)),
                "name": str(item.get("name") or "Action {}".format(index + 1)),
                "icon": str(item.get("icon") or "execute"),
                "trigger": dict(item.get("trigger") or config["trigger"]),
                "phone": dict(item.get("phone") or config["phone"]),
                "action": dict(item.get("action") or config["action"]),
            }
        )
    if not normalized_actions:
        normalized_actions = actions
    config["actions"] = normalized_actions

    selected_id = str(config.get("selected_action_id") or normalized_actions[0]["id"])
    selected = next(
        (item for item in normalized_actions if item["id"] == selected_id),
        normalized_actions[0],
    )
    config["selected_action_id"] = selected["id"]
    config["name"] = selected["name"]
    config["trigger"] = copy.deepcopy(selected["trigger"])
    config["phone"] = copy.deepcopy(selected["phone"])
    config["action"] = copy.deepcopy(selected["action"])
    return config


def save_config():
    temporary_path = CONFIG_PATH + ".tmp"
    with open(temporary_path, "w", encoding="utf-8") as file:
        json.dump(CONFIG, file, ensure_ascii=False, indent=2)
        file.write("\n")
    os.replace(temporary_path, CONFIG_PATH)
    log("configuration saved path={}".format(CONFIG_PATH))


CONFIG = load_config()


def system_colour(colour_id):
    return wx.SystemSettings.GetColour(colour_id)


def is_dark_theme():
    colour = system_colour(wx.SYS_COLOUR_WINDOW)
    return (colour.Red() * 299 + colour.Green() * 587 + colour.Blue() * 114) < 128000


def icon_bitmap(name, size=20):
    path = os.path.join(ICON_DIR, "{}.png".format(name))
    if os.path.isfile(path):
        image = wx.Image(path, wx.BITMAP_TYPE_PNG)
        if image.IsOk() and (image.GetWidth() != size or image.GetHeight() != size):
            image = image.Scale(size, size, wx.IMAGE_QUALITY_HIGH)
        if image.IsOk():
            return wx.Bitmap(image)

    fallback = {
        "add": wx.ART_PLUS,
        "duplicate": wx.ART_COPY,
        "delete": wx.ART_DELETE,
        "play": wx.ART_GO_FORWARD,
        "save": wx.ART_FILE_SAVE,
        "copy": wx.ART_COPY,
        "clear": wx.ART_DELETE,
        "error": wx.ART_ERROR,
        "success": wx.ART_TICK_MARK,
        "result": wx.ART_REPORT_VIEW,
        "execute": wx.ART_EXECUTABLE_FILE,
        "plugin": wx.ART_INFORMATION,
    }.get(name, wx.ART_NORMAL_FILE)
    return wx.ArtProvider.GetBitmap(fallback, wx.ART_BUTTON, (size, size))


def style_button(button, icon_name=None, min_width=88):
    if icon_name:
        button.SetBitmap(icon_bitmap(icon_name, 16))
        button.SetBitmapMargins((6, 2))
    button.SetMinSize((min_width, 32))
    return button


def action_icon_name(action):
    explicit = str(action.get("icon", "")).strip()
    if explicit:
        return explicit
    name = str(action.get("name", "")).lower()
    if "drc" in name or "rule" in name:
        return "drc"
    if "3d" in name or "viewer" in name:
        return "cube"
    if "setup" in name or "setting" in name:
        return "gear"
    return "execute"


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
    return dispatch_menu_command(owner_menu, item)


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


def dispatch_menu_command(owner_menu, item):
    cmd_id = item.GetId()
    try:
        if hasattr(owner_menu, "SendEvent"):
            result = owner_menu.SendEvent(cmd_id)
            log("menu.SendEvent({}) -> {}".format(cmd_id, repr(result)))
            return bool(result) or result is None
    except Exception as exc:
        log("menu.SendEvent error: " + repr(exc))

    try:
        event = wx.CommandEvent(wx.wxEVT_COMMAND_MENU_SELECTED, cmd_id)
        event.SetEventObject(owner_menu)
        if hasattr(owner_menu, "ProcessEvent"):
            result = owner_menu.ProcessEvent(event)
            log("menu.ProcessEvent -> " + repr(result))
            return bool(result)
    except Exception as exc:
        log("menu.ProcessEvent error: " + repr(exc))
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

        ok = dispatch_menu_command(owner_menu, item)
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


def virtual_key_code(name):
    value = str(name).upper().strip()
    if value.startswith("F") and value[1:].isdigit():
        number = int(value[1:])
        if 1 <= number <= 24:
            return 0x70 + number - 1
    if len(value) == 1:
        return ord(value)
    return None


def hotkey_description(trigger):
    names = []
    if trigger.get("ctrl", False):
        names.append("Ctrl")
    if trigger.get("alt", False):
        names.append("Alt")
    if trigger.get("shift", False):
        names.append("Shift")
    if trigger.get("win", False):
        names.append("Win")
    names.append(str(trigger.get("key", "F12")).upper().strip())
    return " + ".join(names)


def trigger_id(trigger):
    """Return the same canonical trigger ID used by MacroBK Studio."""
    modifiers = []
    if trigger.get("ctrl", False):
        modifiers.append("CTRL")
    if trigger.get("alt", False):
        modifiers.append("ALT")
    if trigger.get("shift", False):
        modifiers.append("SHIFT")
    if trigger.get("win", False):
        modifiers.append("WIN")
    modifiers = sorted(set(modifiers))

    key = str(trigger.get("key", "F12")).upper().strip()
    keys = sorted({key}) if key else []
    return "{}:{}".format("+".join(modifiers), ",".join(keys))


def parse_hotkey_description(value):
    tokens = [token.strip() for token in str(value).split("+") if token.strip()]
    if not tokens:
        raise ValueError("Trigger key is empty")
    trigger = {
        "enabled": True,
        "ctrl": False,
        "win": False,
        "alt": False,
        "shift": False,
        "key": "",
    }
    for token in tokens:
        normalized = token.lower()
        if normalized in ("ctrl", "control"):
            trigger["ctrl"] = True
        elif normalized in ("win", "windows", "meta"):
            trigger["win"] = True
        elif normalized == "alt":
            trigger["alt"] = True
        elif normalized == "shift":
            trigger["shift"] = True
        elif not trigger["key"]:
            trigger["key"] = token.upper()
        else:
            raise ValueError("Only one non-modifier key is allowed")
    if virtual_key_code(trigger["key"]) is None:
        raise ValueError("Supported keys are F1-F24 or one character")
    return trigger


def set_keyboard_status(status):
    global _keyboard_status
    _keyboard_status = status
    manager = _manager_frame
    if manager is not None:
        wx.CallAfter(manager.set_keyboard_status, status)


def set_phone_status(status):
    global _phone_status
    _phone_status = status
    manager = _manager_frame
    if manager is not None:
        wx.CallAfter(manager.set_phone_status, status)


def hotkey_worker(trigger, generation):
    global _hotkey_thread_id
    if os.name != "nt":
        set_keyboard_status("Unavailable")
        log("RegisterHotKey failed: Windows only")
        return

    shortcut = hotkey_description(trigger)
    virtual_key = virtual_key_code(trigger.get("key", "F12"))
    if virtual_key is None:
        set_keyboard_status("Error")
        log("RegisterHotKey failed shortcut={} reason=unsupported-key".format(shortcut))
        return

    modifiers = MOD_NOREPEAT
    if trigger.get("ctrl", False):
        modifiers |= MOD_CONTROL
    if trigger.get("alt", False):
        modifiers |= MOD_ALT
    if trigger.get("shift", False):
        modifiers |= MOD_SHIFT
    if trigger.get("win", False):
        modifiers |= MOD_WIN

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    user32.RegisterHotKey.restype = wintypes.BOOL
    user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.UnregisterHotKey.restype = wintypes.BOOL
    user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
    user32.GetMessageW.restype = ctypes.c_int

    thread_id = threading.get_native_id()
    with _hotkey_lock:
        if generation != _hotkey_generation:
            return
        _hotkey_thread_id = thread_id

    if not user32.RegisterHotKey(None, HOTKEY_ID, modifiers, virtual_key):
        error = ctypes.get_last_error()
        conflict = error == ERROR_HOTKEY_ALREADY_REGISTERED
        set_keyboard_status("Conflict" if conflict else "Error")
        log(
            "RegisterHotKey failed shortcut={} error={} conflict={}".format(
                shortcut, error, str(conflict).lower()
            )
        )
        return

    set_keyboard_status("Ready")
    log(
        "RegisterHotKey success shortcut={} id={} thread_id={}".format(
            shortcut, HOTKEY_ID, thread_id
        )
    )
    message = wintypes.MSG()
    try:
        while True:
            result = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
            if result == -1:
                log("hotkey message loop failed error={}".format(ctypes.get_last_error()))
                break
            if result == 0:
                break
            if message.message == WM_HOTKEY and message.wParam == HOTKEY_ID:
                log("trigger received source=keyboard trigger={}".format(shortcut))
                wx.CallAfter(handle_trigger, "keyboard")
    finally:
        user32.UnregisterHotKey(None, HOTKEY_ID)
        log("hotkey unregistered shortcut={}".format(shortcut))
        with _hotkey_lock:
            if _hotkey_thread_id == thread_id:
                _hotkey_thread_id = None


def stop_hotkey_listener():
    with _hotkey_lock:
        thread = _hotkey_thread
        thread_id = _hotkey_thread_id

    if thread_id is not None and os.name == "nt":
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.PostThreadMessageW.argtypes = [
            wintypes.DWORD,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        user32.PostThreadMessageW.restype = wintypes.BOOL
        if not user32.PostThreadMessageW(thread_id, WM_QUIT, 0, 0):
            log("hotkey stop message failed error={}".format(ctypes.get_last_error()))

    if thread is not None and thread.is_alive():
        thread.join(timeout=1.0)


def start_hotkey_listener():
    global _hotkey_thread, _hotkey_generation
    trigger = dict(CONFIG.get("trigger", {}))
    if not trigger.get("enabled", True):
        set_keyboard_status("Disabled")
        log("hotkey disabled by config")
        return

    with _hotkey_lock:
        _hotkey_generation += 1
        generation = _hotkey_generation

    set_keyboard_status("Registering")
    thread = threading.Thread(
        target=hotkey_worker,
        args=(trigger, generation),
        name="MacroBK-KiCad-DRC-Hotkey",
        daemon=True,
    )
    with _hotkey_lock:
        _hotkey_thread = thread
    thread.start()


def restart_hotkey_listener():
    stop_hotkey_listener()
    start_hotkey_listener()


def execute_python_script(script, source):
    manager = _manager_frame
    if manager is not None and source == "test":
        manager.set_test_status("RUNNING")

    log("{} source={}".format("TEST RUN" if source == "test" else "ACTION START", source))
    output = io.StringIO()

    def script_open_drc_window():
        return open_drc_window(source, False)

    namespace = {
        "__builtins__": __builtins__,
        "open_drc_window": script_open_drc_window,
        "open_menu": open_menu,
        "iter_controls": iter_controls,
        "find_controls": find_controls,
        "find_control": find_control,
        "get_control_info": get_control_info,
        "get_control_value": get_control_value,
        "set_control_value": set_control_value,
        "test_preferences_direct_children": test_preferences_direct_children,
        "test_preferences_control_tree": test_preferences_control_tree,
        "test_preferences_checkbox_value": test_preferences_checkbox_value,
        "test_preferences_checkbox_toggle_restore": (
            test_preferences_checkbox_toggle_restore
        ),
        "pcbnew": pcbnew,
        "wx": wx,
    }
    try:
        with redirect_stdout(output):
            exec(compile(script, "<MacroBK Plugin Script>", "exec"), namespace, namespace)
            run_function = namespace.get("run")
            if callable(run_function):
                run_function()

        for line in output.getvalue().splitlines():
            log("stdout: " + line)
        log("SUCCESS source={}".format(source))
        if manager is not None and source == "test":
            manager.set_test_status("SUCCESS")
        return True
    except Exception:
        for line in output.getvalue().splitlines():
            log("stdout: " + line)
        log("ERROR source={}".format(source))
        for line in traceback.format_exc().rstrip().splitlines():
            log(line)
        if manager is not None:
            if source == "test":
                manager.set_test_status("ERROR")
            manager.show_result_tab()
        return False


def handle_trigger(source):
    manager = _manager_frame
    if manager is not None:
        manager.blink_input_signal(source)
    trigger_text = hotkey_description(CONFIG.get("trigger", {}))
    log("TRIGGER source={} trigger={}".format(source, trigger_text))
    script = str(CONFIG.get("action", {}).get("script", ""))
    execute_python_script(script, source)


def udp_worker():
    # Do not cache the expected trigger here.
    # Trigger changes made with Register/Save must take effect immediately.
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

    # Multiple applications/plugins must be able to listen on the same multicast port.
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        # Multicast receivers normally bind the wildcard address, then join only
        # the loopback interface. Studio sends with TTL 0 on 127.0.0.1.
        sock.bind(("", LOCAL_TRIGGER_PORT))
        membership = socket.inet_aton(LOCAL_TRIGGER_GROUP) + socket.inet_aton(
            LOCAL_TRIGGER_INTERFACE
        )
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
        sock.settimeout(0.5)
        set_phone_status("Ready")
        log(
            "UDP multicast ready group={}:{} interface={} trigger={}".format(
                LOCAL_TRIGGER_GROUP,
                LOCAL_TRIGGER_PORT,
                LOCAL_TRIGGER_INTERFACE,
                trigger_id(CONFIG.get("trigger", {})),
            )
        )
    except Exception as exc:
        set_phone_status("Port Error")
        log(
            "UDP multicast setup failed group={}:{} interface={} error={}".format(
                LOCAL_TRIGGER_GROUP,
                LOCAL_TRIGGER_PORT,
                LOCAL_TRIGGER_INTERFACE,
                repr(exc),
            )
        )
        sock.close()
        return

    while True:
        try:
            data, address = sock.recvfrom(1024)
        except socket.timeout:
            continue
        except Exception as exc:
            log("UDP recv error: " + repr(exc))
            set_phone_status("Port Error")
            break

        command = data.decode("utf-8", errors="ignore").strip()
        if not command.startswith("TRIGGER|"):
            log("ignored UDP command: " + repr(command))
            continue

        received = command.split("|", 1)[1].strip()

        # Re-read the current trigger for every UDP packet.
        # This avoids stale comparisons after Register/Save changes.
        expected = trigger_id(CONFIG.get("trigger", {}))

        if received == expected:
            log(
                "trigger received source=phone udp={} from={}:{}".format(
                    received, address[0], address[1]
                )
            )
            wx.CallAfter(handle_trigger, "phone")
        else:
            log(
                "ignored UDP trigger received={} expected={}".format(
                    received, expected
                )
            )

    sock.close()


class MacroBKPluginManager(wx.Frame):
    def __init__(self, parent):
        super().__init__(parent, title="MacroBK Plugin Manager", size=(1000, 660))
        self.SetMinSize((960, 620))
        self.SetIcon(wx.Icon(icon_bitmap("plugin", 32)))
        self._blink_timer = None
        self._loading_action = False
        self.actions = copy.deepcopy(CONFIG.get("actions", []))
        self.selected_index = 0

        background = system_colour(wx.SYS_COLOUR_WINDOW)
        panel_background = system_colour(wx.SYS_COLOUR_BTNFACE)
        text_colour = system_colour(wx.SYS_COLOUR_WINDOWTEXT)
        muted_colour = system_colour(wx.SYS_COLOUR_GRAYTEXT)

        root_panel = wx.Panel(self)
        root_panel.SetBackgroundColour(background)
        root_sizer = wx.BoxSizer(wx.VERTICAL)

        header = wx.Panel(root_panel)
        header.SetBackgroundColour(panel_background)
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        header_icon = wx.StaticBitmap(header, bitmap=icon_bitmap("plugin", 28))
        header_sizer.Add(header_icon, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 16)
        title_stack = wx.BoxSizer(wx.VERTICAL)
        product_title = wx.StaticText(header, label="MacroBK Plugin Manager")
        product_font = product_title.GetFont()
        product_font.SetPointSize(13)
        product_font.SetWeight(wx.FONTWEIGHT_BOLD)
        product_title.SetFont(product_font)
        product_subtitle = wx.StaticText(
            header, label="KiCad automation actions and input monitoring"
        )
        product_subtitle.SetForegroundColour(muted_colour)
        title_stack.Add(product_title, 0)
        title_stack.Add(product_subtitle, 0, wx.TOP, 2)
        header_sizer.Add(title_stack, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 12)
        header.SetSizer(header_sizer)
        root_sizer.Add(header, 0, wx.EXPAND)
        root_sizer.Add(wx.StaticLine(root_panel), 0, wx.EXPAND)

        content_sizer = wx.BoxSizer(wx.HORIZONTAL)
        left_panel = wx.Panel(root_panel)
        left_panel.SetBackgroundColour(panel_background)
        left_panel.SetMinSize((360, -1))
        left_sizer = wx.BoxSizer(wx.VERTICAL)

        left_title = wx.StaticText(left_panel, label="REGISTERED ACTIONS")
        left_title_font = left_title.GetFont()
        left_title_font.SetPointSize(9)
        left_title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        left_title.SetFont(left_title_font)
        left_title.SetForegroundColour(muted_colour)
        left_sizer.Add(left_title, 0, wx.LEFT | wx.RIGHT | wx.TOP, 14)

        self.action_images = wx.ImageList(20, 20)
        self.action_image_indexes = {}
        for name in ("drc", "cube", "gear", "execute"):
            self.action_image_indexes[name] = self.action_images.Add(icon_bitmap(name, 20))
        self.action_list = wx.ListCtrl(
            left_panel,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SIMPLE,
        )
        self.action_list.SetMinSize((336, 130))
        self.action_list.AssignImageList(self.action_images, wx.IMAGE_LIST_SMALL)
        self.action_list.InsertColumn(0, "Name", width=150)
        self.action_list.InsertColumn(1, "Trigger", width=160)
        self.action_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_action_selected)
        self.action_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_action_rename)
        left_sizer.Add(self.action_list, 1, wx.EXPAND | wx.ALL, 10)

        action_buttons = wx.BoxSizer(wx.HORIZONTAL)
        add_button = style_button(wx.Button(left_panel, label="Add"), "add", 72)
        duplicate_button = style_button(
            wx.Button(left_panel, label="Duplicate"), "duplicate", 94
        )
        delete_button = style_button(wx.Button(left_panel, label="Delete"), "delete", 78)
        delete_button.SetForegroundColour(wx.Colour(170, 55, 55))
        add_button.Bind(wx.EVT_BUTTON, self.on_add_action)
        duplicate_button.Bind(wx.EVT_BUTTON, self.on_duplicate_action)
        delete_button.Bind(wx.EVT_BUTTON, self.on_delete_action)
        action_buttons.Add(add_button, 0, wx.RIGHT, 6)
        action_buttons.Add(duplicate_button, 0, wx.RIGHT, 6)
        action_buttons.Add(delete_button, 0)
        left_sizer.Add(action_buttons, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        monitor_box = wx.StaticBox(left_panel, label=" Input Monitor ")
        monitor_sizer = wx.StaticBoxSizer(monitor_box, wx.VERTICAL)
        self.keyboard_led, self.keyboard_status_label = self.create_monitor_row(
            monitor_box, monitor_sizer, "keyboard", "Keyboard", _keyboard_status
        )
        self.phone_led, self.phone_status_label = self.create_monitor_row(
            monitor_box, monitor_sizer, "phone", "Phone", _phone_status
        )
        self.signal_source = wx.StaticText(monitor_box, label="Waiting for input")
        self.signal_source.SetForegroundColour(muted_colour)
        monitor_sizer.Add(self.signal_source, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        left_sizer.Add(monitor_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        left_sizer.Add(wx.StaticText(left_panel, label="Trigger Key"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        self.trigger_text = wx.TextCtrl(left_panel)
        self.trigger_text.SetMinSize((-1, 30))
        left_sizer.Add(self.trigger_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)
        register_button = style_button(wx.Button(left_panel, label="Register"), "keyboard", 100)
        register_button.Bind(wx.EVT_BUTTON, self.on_register)
        left_sizer.Add(register_button, 0, wx.EXPAND | wx.ALL, 10)
        left_panel.SetSizer(left_sizer)

        right_panel = wx.Panel(root_panel)
        right_panel.SetBackgroundColour(background)
        right_sizer = wx.BoxSizer(wx.VERTICAL)
        self.action_title = wx.StaticText(right_panel, label="Open DRC")
        action_title_font = self.action_title.GetFont()
        action_title_font.SetPointSize(16)
        action_title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.action_title.SetFont(action_title_font)
        self.action_trigger_summary = wx.StaticText(right_panel, label="Ctrl + Win + F12")
        self.action_trigger_summary.SetForegroundColour(muted_colour)
        right_sizer.Add(self.action_title, 0, wx.LEFT | wx.RIGHT | wx.TOP, 16)
        right_sizer.Add(self.action_trigger_summary, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, 16)

        self.notebook = wx.Notebook(right_panel)
        notebook_images = wx.ImageList(16, 16)
        execute_image = notebook_images.Add(icon_bitmap("execute", 16))
        result_image = notebook_images.Add(icon_bitmap("result", 16))
        self.notebook.AssignImageList(notebook_images)
        self.notebook_images = notebook_images
        execute_panel = wx.Panel(self.notebook)
        result_panel = wx.Panel(self.notebook)
        self.notebook.AddPage(execute_panel, "Execute", True, execute_image)
        self.notebook.AddPage(result_panel, "Result", False, result_image)

        execute_sizer = wx.BoxSizer(wx.VERTICAL)
        script_title = wx.StaticText(execute_panel, label="Python Script")
        script_title_font = script_title.GetFont()
        script_title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        script_title.SetFont(script_title_font)
        execute_sizer.Add(script_title, 0, wx.ALL, 12)
        self.script_text = stc.StyledTextCtrl(execute_panel, style=wx.BORDER_SIMPLE)
        self.configure_python_editor(self.script_text)
        execute_sizer.Add(self.script_text, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 12)
        execute_controls = wx.BoxSizer(wx.HORIZONTAL)
        test_button = style_button(wx.Button(execute_panel, label="Run Test"), "play", 120)
        test_button.Bind(wx.EVT_BUTTON, self.on_test_run)
        test_button.SetDefault()
        self.test_status_icon = wx.StaticBitmap(execute_panel, bitmap=icon_bitmap("execute", 18))
        self.test_status_label = wx.StaticText(execute_panel, label="READY")
        status_font = self.test_status_label.GetFont()
        status_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.test_status_label.SetFont(status_font)
        execute_controls.Add(test_button, 0, wx.RIGHT, 14)
        execute_controls.Add(self.test_status_icon, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        execute_controls.Add(self.test_status_label, 0, wx.ALIGN_CENTER_VERTICAL)
        execute_sizer.Add(execute_controls, 0, wx.ALL, 12)
        execute_panel.SetSizer(execute_sizer)

        result_sizer = wx.BoxSizer(wx.VERTICAL)
        self.result_text = stc.StyledTextCtrl(result_panel, style=wx.BORDER_SIMPLE)
        self.configure_log_editor(self.result_text)
        result_sizer.Add(self.result_text, 1, wx.EXPAND | wx.ALL, 12)
        result_controls = wx.BoxSizer(wx.HORIZONTAL)
        result_controls.AddStretchSpacer(1)
        copy_button = style_button(wx.Button(result_panel, label="Copy"), "copy", 84)
        clear_button = style_button(wx.Button(result_panel, label="Clear"), "clear", 84)
        copy_button.Bind(wx.EVT_BUTTON, self.on_copy)
        clear_button.Bind(wx.EVT_BUTTON, self.on_clear)
        result_controls.Add(copy_button, 0, wx.RIGHT, 8)
        result_controls.Add(clear_button, 0)
        result_sizer.Add(result_controls, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        result_panel.SetSizer(result_sizer)

        right_sizer.Add(self.notebook, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        right_panel.SetSizer(right_sizer)
        content_sizer.Add(left_panel, 0, wx.EXPAND)
        content_sizer.Add(wx.StaticLine(root_panel, style=wx.LI_VERTICAL), 0, wx.EXPAND)
        content_sizer.Add(right_panel, 1, wx.EXPAND)
        root_sizer.Add(content_sizer, 1, wx.EXPAND)
        root_sizer.Add(wx.StaticLine(root_panel), 0, wx.EXPAND)

        bottom_sizer = wx.BoxSizer(wx.HORIZONTAL)
        bottom_sizer.AddStretchSpacer(1)
        save_button = style_button(wx.Button(root_panel, label="Save"), "save", 92)
        close_button = style_button(wx.Button(root_panel, label="Close"), None, 92)
        save_button.Bind(wx.EVT_BUTTON, self.on_save)
        close_button.Bind(wx.EVT_BUTTON, lambda _event: self.Close())
        bottom_sizer.Add(save_button, 0, wx.RIGHT, 8)
        bottom_sizer.Add(close_button, 0)
        root_sizer.Add(bottom_sizer, 0, wx.EXPAND | wx.ALL, 10)

        root_panel.SetSizer(root_sizer)
        self.status_bar = self.CreateStatusBar(4)
        self.status_bar.SetStatusWidths([-2, -2, -2, -1])
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.CentreOnParent()
        self.refresh_action_list()
        selected_id = str(CONFIG.get("selected_action_id", ""))
        self.selected_index = next(
            (i for i, item in enumerate(self.actions) if item["id"] == selected_id), 0
        )
        self.action_list.Select(self.selected_index)
        self.load_action(self.selected_index)
        self.load_file_log()
        self.update_status_bar()

    def create_monitor_row(self, parent, sizer, icon_name, label, status):
        row = wx.BoxSizer(wx.HORIZONTAL)
        icon = wx.StaticBitmap(parent, bitmap=icon_bitmap(icon_name, 18))
        led = wx.StaticText(parent, label="●")
        led_font = led.GetFont()
        led_font.SetPointSize(14)
        led.SetFont(led_font)
        status_label = wx.StaticText(parent, label="{}  {}".format(label, status))
        row.Add(icon, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        row.Add(led, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        row.Add(status_label, 1, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(row, 0, wx.EXPAND | wx.ALL, 8)
        self.set_led_colour(led, status)
        return led, status_label

    def set_led_colour(self, control, status):
        colours = {
            "Ready": wx.Colour(39, 174, 96),
            "Conflict": wx.Colour(230, 126, 34),
            "Error": wx.Colour(192, 57, 43),
            "Port Error": wx.Colour(192, 57, 43),
            "Disabled": wx.Colour(127, 140, 141),
        }
        control.SetForegroundColour(colours.get(str(status), wx.Colour(127, 140, 141)))

    def configure_python_editor(self, editor):
        dark = is_dark_theme()
        foreground = "#E7EAF0" if dark else "#20242A"
        background = "#1F2329" if dark else "#FBFCFE"
        editor.SetLexer(stc.STC_LEX_PYTHON)
        editor.StyleSetSpec(stc.STC_STYLE_DEFAULT, "face:Consolas,size:10,fore:{},back:{}".format(foreground, background))
        editor.StyleClearAll()
        editor.StyleSetSpec(stc.STC_P_COMMENTLINE, "fore:#6A9955,italic")
        editor.StyleSetSpec(stc.STC_P_NUMBER, "fore:#B477DB")
        editor.StyleSetSpec(stc.STC_P_STRING, "fore:#CE9178")
        editor.StyleSetSpec(stc.STC_P_CHARACTER, "fore:#CE9178")
        editor.StyleSetSpec(stc.STC_P_WORD, "fore:#569CD6,bold")
        editor.SetKeyWords(0, "and as assert async await break class continue def del elif else except False finally for from global if import in is lambda None nonlocal not or pass raise return True try while with yield")
        editor.SetMarginType(0, stc.STC_MARGIN_NUMBER)
        editor.SetMarginWidth(0, 42)
        editor.StyleSetSpec(stc.STC_STYLE_LINENUMBER, "face:Consolas,size:9,fore:#7F8792,back:{}".format(background))
        editor.SetTabWidth(4)
        editor.SetUseTabs(False)
        editor.SetIndent(4)
        editor.SetViewWhiteSpace(False)
        editor.SetCaretLineVisible(True)
        editor.SetCaretLineBackground("#2A3038" if dark else "#EEF3FA")
        editor.SetScrollWidthTracking(True)

    def configure_log_editor(self, editor):
        dark = is_dark_theme()
        foreground = "#E7EAF0" if dark else "#20242A"
        background = "#171A1F" if dark else "#FBFCFE"
        editor.SetLexer(stc.STC_LEX_NULL)
        editor.StyleSetSpec(0, "face:Consolas,size:9,fore:{},back:{}".format(foreground, background))
        editor.StyleSetSpec(1, "face:Consolas,size:9,fore:#27AE60,back:{},bold".format(background))
        editor.StyleSetSpec(2, "face:Consolas,size:9,fore:#E74C3C,back:{},bold".format(background))
        editor.SetMarginWidth(0, 0)
        editor.SetReadOnly(True)

    def style_log_range(self, start, text):
        style = 2 if "ERROR" in text or "Traceback" in text else 1 if "SUCCESS" in text else 0
        self.result_text.StartStyling(start)
        self.result_text.SetStyling(len(text), style)

    def load_file_log(self):
        try:
            with open(LOG_PATH, "r", encoding="utf-8") as file:
                for line in file.read().splitlines():
                    self.append_result(line)
        except Exception:
            pass

    def append_result(self, line):
        text = str(line) + "\n"
        start = self.result_text.GetTextLength()
        self.result_text.SetReadOnly(False)
        self.result_text.AppendText(text)
        self.style_log_range(start, text)
        self.result_text.SetReadOnly(True)
        self.result_text.GotoPos(self.result_text.GetTextLength())

    def refresh_action_list(self):
        self.action_list.Freeze()
        self.action_list.DeleteAllItems()
        for action in self.actions:
            icon_name = action_icon_name(action)
            image_index = self.action_image_indexes.get(icon_name, self.action_image_indexes["execute"])
            row = self.action_list.InsertItem(self.action_list.GetItemCount(), action["name"], image_index)
            self.action_list.SetItem(row, 1, hotkey_description(action.get("trigger", {})))
        self.action_list.Thaw()

    def store_current_action(self):
        if self._loading_action or not self.actions:
            return
        action = self.actions[self.selected_index]
        try:
            action["trigger"] = self.read_trigger()
        except Exception:
            pass
        action["action"] = {"type": "python", "script": self.script_text.GetValue()}

    def load_action(self, index):
        if not 0 <= index < len(self.actions):
            return
        self._loading_action = True
        self.selected_index = index
        action = self.actions[index]
        trigger_value = hotkey_description(action.get("trigger", {}))
        self.action_title.SetLabel(action["name"])
        self.action_trigger_summary.SetLabel(trigger_value)
        self.trigger_text.SetValue(trigger_value)
        self.script_text.SetValue(str(action.get("action", {}).get("script", "")))
        self._loading_action = False
        self.update_status_bar()

    def on_action_selected(self, event):
        new_index = event.GetIndex()
        if new_index == self.selected_index:
            return
        self.store_current_action()
        self.load_action(new_index)

    def on_action_rename(self, event):
        index = event.GetIndex()
        current = self.actions[index]["name"]
        dialog = wx.TextEntryDialog(self, "Action name", "Rename Action", current)
        try:
            if dialog.ShowModal() == wx.ID_OK and dialog.GetValue().strip():
                self.actions[index]["name"] = dialog.GetValue().strip()
                self.refresh_action_list()
                self.action_list.Select(index)
                self.load_action(index)
        finally:
            dialog.Destroy()

    def on_add_action(self, _event):
        self.store_current_action()
        new_action = {
            "id": "action-" + uuid.uuid4().hex[:8],
            "name": "New Action",
            "icon": "execute",
            "trigger": copy.deepcopy(DEFAULT_CONFIG["trigger"]),
            "phone": copy.deepcopy(DEFAULT_CONFIG["phone"]),
            "action": {"type": "python", "script": "# Enter KiCad Python here\n"},
        }
        self.actions.append(new_action)
        self.refresh_action_list()
        self.action_list.Select(len(self.actions) - 1)
        self.load_action(len(self.actions) - 1)

    def on_duplicate_action(self, _event):
        self.store_current_action()
        duplicate = copy.deepcopy(self.actions[self.selected_index])
        duplicate["id"] = "action-" + uuid.uuid4().hex[:8]
        duplicate["name"] = duplicate["name"] + " Copy"
        self.actions.append(duplicate)
        self.refresh_action_list()
        self.action_list.Select(len(self.actions) - 1)
        self.load_action(len(self.actions) - 1)

    def on_delete_action(self, _event):
        if len(self.actions) <= 1:
            wx.MessageBox("At least one action must remain.", "MacroBK Plugin Manager", wx.OK | wx.ICON_INFORMATION)
            return
        action = self.actions[self.selected_index]
        answer = wx.MessageBox(
            "Delete '{}'?".format(action["name"]),
            "Delete Action",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
        )
        if answer != wx.YES:
            return
        del self.actions[self.selected_index]
        self.selected_index = min(self.selected_index, len(self.actions) - 1)
        self.refresh_action_list()
        self.action_list.Select(self.selected_index)
        self.load_action(self.selected_index)

    def set_keyboard_status(self, status):
        self.keyboard_status_label.SetLabel("Keyboard  " + str(status))
        self.set_led_colour(self.keyboard_led, status)
        self.update_status_bar()

    def set_phone_status(self, status):
        self.phone_status_label.SetLabel("Phone  " + str(status))
        self.set_led_colour(self.phone_led, status)
        self.update_status_bar()

    def set_test_status(self, status):
        label = str(status)
        self.test_status_label.SetLabel(label)
        if label == "SUCCESS":
            self.test_status_icon.SetBitmap(icon_bitmap("success", 18))
            self.test_status_label.SetForegroundColour(wx.Colour(39, 174, 96))
        elif label == "ERROR":
            self.test_status_icon.SetBitmap(icon_bitmap("error", 18))
            self.test_status_label.SetForegroundColour(wx.Colour(192, 57, 43))
        else:
            self.test_status_icon.SetBitmap(icon_bitmap("execute", 18))
            self.test_status_label.SetForegroundColour(system_colour(wx.SYS_COLOUR_WINDOWTEXT))

    def update_status_bar(self):
        if not hasattr(self, "status_bar"):
            return
        self.status_bar.SetStatusText("●  Plugin Ready", 0)
        self.status_bar.SetStatusText("Keyboard {}".format(_keyboard_status), 1)
        self.status_bar.SetStatusText("Phone {}".format(_phone_status), 2)
        self.status_bar.SetStatusText("{} Actions".format(len(self.actions)), 3)

    def show_result_tab(self):
        self.notebook.SetSelection(1)

    def blink_input_signal(self, source):
        led = self.keyboard_led if source == "keyboard" else self.phone_led
        led.SetForegroundColour(wx.Colour(52, 152, 219))
        self.signal_source.SetLabel("Input received from {}".format(source.title()))
        if self._blink_timer is not None:
            self._blink_timer.Stop()
        self._blink_timer = wx.CallLater(400, self.reset_input_signal)

    def reset_input_signal(self):
        self.set_led_colour(self.keyboard_led, _keyboard_status)
        self.set_led_colour(self.phone_led, _phone_status)
        self.signal_source.SetLabel("Waiting for input")

    def read_trigger(self):
        return parse_hotkey_description(self.trigger_text.GetValue())

    def apply_selected_to_config(self):
        self.store_current_action()
        selected = self.actions[self.selected_index]
        CONFIG["actions"] = copy.deepcopy(self.actions)
        CONFIG["selected_action_id"] = selected["id"]
        CONFIG["name"] = selected["name"]
        CONFIG["trigger"] = copy.deepcopy(selected["trigger"])
        CONFIG["phone"] = copy.deepcopy(selected["phone"])
        CONFIG["action"] = copy.deepcopy(selected["action"])

    def on_register(self, _event):
        try:
            self.apply_selected_to_config()
            self.trigger_text.SetValue(hotkey_description(CONFIG["trigger"]))
            self.action_trigger_summary.SetLabel(self.trigger_text.GetValue())
            log("Register requested shortcut={}".format(self.trigger_text.GetValue()))
            restart_hotkey_listener()
        except Exception as exc:
            self.set_keyboard_status("Error")
            log("Register error: " + str(exc))
            self.show_result_tab()

    def on_test_run(self, _event):
        execute_python_script(self.script_text.GetValue(), "test")

    def on_save(self, _event):
        try:
            self.apply_selected_to_config()
            save_config()
            self.refresh_action_list()
            self.action_list.Select(self.selected_index)
            self.load_action(self.selected_index)
            restart_hotkey_listener()
        except Exception as exc:
            log("Save error: " + repr(exc))
            self.show_result_tab()

    def on_copy(self, _event):
        if wx.TheClipboard.Open():
            try:
                wx.TheClipboard.SetData(wx.TextDataObject(self.result_text.GetValue()))
                wx.TheClipboard.Flush()
            finally:
                wx.TheClipboard.Close()

    def on_clear(self, _event):
        self.result_text.SetReadOnly(False)
        self.result_text.ClearAll()
        self.result_text.SetReadOnly(True)

    def on_close(self, event):
        global _manager_frame
        if self._blink_timer is not None:
            self._blink_timer.Stop()
            self._blink_timer = None
        _manager_frame = None
        self.Destroy()


def show_manager():
    global _manager_frame
    if (
        _manager_frame is not None
        and bool(_manager_frame)
        and not _manager_frame.IsBeingDeleted()
    ):
        try:
            if _manager_frame.IsIconized():
                _manager_frame.Iconize(False)
            _manager_frame.Show(True)
            _manager_frame.Raise()
            _manager_frame.SetFocus()
            return
        except Exception:
            _manager_frame = None

    # Keep the modeless manager independent from transient KiCad child windows.
    # The module-level reference above owns it until the user explicitly closes it.
    _manager_frame = MacroBKPluginManager(None)
    _manager_frame.Show(True)
    _manager_frame.Raise()
    _manager_frame.SetFocus()
    log("Plugin Manager opened")


def start_bridge():
    global _started
    if _started:
        return
    _started = True
    log("plugin bridge starting")
    start_hotkey_listener()
    thread = threading.Thread(
        target=udp_worker,
        name="MacroBK-KiCad-DRC-UDP",
        daemon=True,
    )
    thread.start()


class MacroBKDRCBridge(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "MacroBK Plugin Manager"
        self.category = "MacroBK"
        self.description = "Configure and test the MacroBK KiCad trigger"
        self.show_toolbar_button = False

    def Run(self):
        show_manager()
