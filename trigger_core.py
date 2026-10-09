import ast
import builtins
import ctypes
from ctypes import wintypes
import copy
from datetime import datetime
import json
import os
import socket
import sys
import threading
import traceback

import pcbnew
import wx

try:
    from . import kicad_controls as kc
except ImportError:
    import kicad_controls as kc

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
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
        "keys": ["F12"],
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
_keyboard_status = "Starting"
_phone_status = "Starting"
_hotkey_thread = None
_hotkey_thread_id = None
_hotkey_generation = 0
_hotkey_lock = threading.Lock()
_log_lock = threading.Lock()
_manager_provider = lambda: None
_action_workers = {}
_action_workers_lock = threading.Lock()


class ActionStopped(Exception):
    """Internal cooperative-stop signal for worker actions."""



def set_manager_provider(provider):
    global _manager_provider
    _manager_provider = provider or (lambda: None)

def get_keyboard_status():
    return _keyboard_status

def get_phone_status():
    return _phone_status

def _default_config_copy():
    return json.loads(json.dumps(DEFAULT_CONFIG))


def _is_gui_thread():
    """Return True when executing on KiCad's primary Python/GUI thread.

    wx.IsMainThread() is not reliable in every embedded KiCad/wxPython build,
    so also use Python's main-thread identity.  This avoids posting a
    CallAfter to ourselves and then waiting for it (GUI deadlock).
    """
    if threading.current_thread() is threading.main_thread():
        return True
    try:
        return bool(wx.IsMainThread())
    except Exception:
        return False


def _append_result(line):
    manager = _manager_provider()
    if manager is not None:
        try:
            if _is_gui_thread():
                manager.append_result(str(line))
            else:
                wx.CallAfter(manager.append_result, str(line))
        except Exception:
            pass


def log(message):
    """Write internal MacroBK diagnostics to console/file only.

    Normal Result output is intentionally kept clean.  Internal diagnostics
    are copied to Result only by debug_log() when the running script has
    DEBUG = True.
    """
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


def debug_log(message, enabled=False):
    """Write an internal diagnostic and optionally show it in Result."""
    log(message)
    if enabled:
        _append_result("[MacroBK] {}".format(message))


def error_result(message):
    """Errors are always visible in Result, even when DEBUG is off."""
    _append_result(message)


def _script_debug_enabled(script):
    """Read a top-level literal DEBUG = True before the script starts."""
    try:
        tree = ast.parse(str(script), mode="exec")
    except Exception:
        return False

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "DEBUG":
                    if isinstance(node.value, ast.Constant):
                        return node.value.value is True
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            if isinstance(target, ast.Name) and target.id == "DEBUG":
                value = node.value
                if isinstance(value, ast.Constant):
                    return value.value is True
    return False




def _script_execution_mode(script):
    """Return explicit script execution mode. Default is GUI for compatibility.

    Supported top-level literals:
        MODE = "GUI"      # default, full wx/pcbnew compatibility
        MODE = "WORKER"   # background thread; use GUI helper APIs only

    EXECUTION_MODE is accepted as an alias.  No automatic wx/AST guessing is
    performed because aliases, dynamic imports and generators make that
    classification unreliable.
    """
    try:
        tree = ast.parse(str(script), mode="exec")
    except Exception:
        return "GUI"

    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue

        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        else:
            targets = [node.target]
            value = node.value

        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            continue

        for target in targets:
            if isinstance(target, ast.Name) and target.id in ("MODE", "EXECUTION_MODE"):
                mode = value.value.strip().upper()
                if mode in ("GUI", "WORKER"):
                    return mode
    return "GUI"


def _legacy_script_namespace(debug=False):
    """Namespace used by legacy/main-thread scripts."""
    return {
        "__builtins__": __builtins__,
        "print": _script_print,
        "DEBUG": debug,
        "open_drc_window": lambda: kc.open_drc_window("script", False),
        "open_menu": kc.open_menu,
        "iter_controls": kc.iter_controls,
        "find_controls": kc.find_controls,
        "find_control": kc.find_control,
        "get_control_info": kc.get_control_info,
        "get_control_value": kc.get_control_value,
        "set_control_value": kc.set_control_value,
        "get_pcb_selection_filter_panel": kc.get_pcb_selection_filter_panel,
        "pcb_select_filter": kc.pcb_select_filter,
        "pcb_select_filter_state": kc.pcb_select_filter_state,
        "test_preferences_direct_children": kc.test_preferences_direct_children,
        "test_preferences_control_tree": kc.test_preferences_control_tree,
        "test_preferences_checkbox_value": kc.test_preferences_checkbox_value,
        "test_preferences_checkbox_toggle_restore": kc.test_preferences_checkbox_toggle_restore,
        "pcbnew": pcbnew,
        "wx": wx,
    }


def _execute_python_script_ui(script, source, action_id, debug):
    """Execute a script synchronously on KiCad's GUI thread.

    GUI is the compatibility/default mode.  It may use raw wx/pcbnew objects.
    Long sleeps or loops will block the KiCad UI and cannot be stopped from the
    Manager while blocked; use MODE = "WORKER" for long-running actions.
    """
    key = _worker_key(action_id, source)
    manager = _manager_provider()
    if manager is not None and source == "test":
        try:
            manager.set_test_status("RUNNING", stoppable=False)
        except TypeError:
            manager.set_test_status("RUNNING")

    debug_log(
        "{} source={} action={} mode=gui".format(
            "TEST RUN" if source == "test" else "ACTION START",
            source,
            key,
        ),
        debug,
    )

    namespace = _legacy_script_namespace(debug)
    terminal = "SUCCESS"
    ok = True
    try:
        exec(compile(script, "<MacroBK Plugin Script>", "exec"), namespace, namespace)
        run_function = namespace.get("run")
        if callable(run_function):
            run_function()
        debug_log("SUCCESS source={} action={} mode=gui".format(source, key), debug)
    except BaseException:
        ok = False
        terminal = "ERROR"
        debug_log("ERROR source={} action={} mode=gui".format(source, key), debug)
        error_result("[ERROR] MacroBK script failed")
        for line in traceback.format_exc().rstrip().splitlines():
            error_result(line)
        if manager is not None:
            try:
                manager.show_result_tab()
            except Exception:
                pass
    finally:
        if manager is not None and source == "test":
            try:
                manager.set_test_status(terminal, stoppable=False)
            except TypeError:
                manager.set_test_status(terminal)
    return ok



def _call_on_ui_thread(function, *args, **kwargs):
    """Run a helper on the wx GUI thread.

    Optional keyword-only transport argument ``_stop_event`` lets a WORKER
    action cancel its wait.  Unlike the previous implementation this never
    performs one unbounded Event.wait().
    """
    stop_event = kwargs.pop("_stop_event", None)

    if _is_gui_thread():
        return function(*args, **kwargs)

    done = threading.Event()
    box = {}

    def invoke():
        try:
            box["result"] = function(*args, **kwargs)
        except BaseException as exc:
            box["error"] = exc
            box["traceback"] = traceback.format_exc()
        finally:
            done.set()

    wx.CallAfter(invoke)

    # Poll instead of waiting forever so Stop can release a worker that is
    # waiting for a GUI callback.  The GUI callback may still run later, but
    # the worker will no longer remain stuck in RUNNING.
    while not done.wait(0.05):
        if stop_event is not None and stop_event.is_set():
            raise ActionStopped()

    if "error" in box:
        error = box["error"]
        try:
            setattr(error, "_macrobk_ui_traceback", box.get("traceback", ""))
        except Exception:
            pass
        raise error
    return box.get("result")


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

def virtual_key_code(name):
    value = str(name).upper().strip()

    special = {
        "ENTER": 0x0D,
        "TAB": 0x09,
        "ESC": 0x1B,
        "ESCAPE": 0x1B,
        "SPACE": 0x20,
        "BACKSPACE": 0x08,
        "DELETE": 0x2E,
        "INSERT": 0x2D,
        "HOME": 0x24,
        "END": 0x23,
        "PAGEUP": 0x21,
        "PAGEDOWN": 0x22,
        "LEFT": 0x25,
        "UP": 0x26,
        "RIGHT": 0x27,
        "DOWN": 0x28,
    }
    if value in special:
        return special[value]

    if value.startswith("F") and value[1:].isdigit():
        number = int(value[1:])
        if 1 <= number <= 24:
            return 0x70 + number - 1

    if len(value) == 1:
        return ord(value)

    return None


def trigger_keys(trigger):
    """Return 1-4 non-modifier keys while keeping old single-key configs compatible."""
    values = trigger.get("keys")
    if isinstance(values, list):
        keys = [str(value).upper().strip() for value in values if str(value).strip()]
    else:
        key = str(trigger.get("key", "")).upper().strip()
        keys = [key] if key else []

    # Preserve order for display, remove duplicates, and cap at four keys.
    unique = []
    for key in keys:
        if key not in unique:
            unique.append(key)
    return unique[:4]


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

    names.extend(trigger_keys(trigger))
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

    keys = sorted(set(trigger_keys(trigger)))
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
        "keys": [],
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
        else:
            key = token.upper()
            if virtual_key_code(key) is None:
                raise ValueError("Unsupported trigger key: {}".format(token))
            if key not in trigger["keys"]:
                trigger["keys"].append(key)

    if not trigger["keys"]:
        raise ValueError("Select at least one trigger key")
    if len(trigger["keys"]) > 4:
        raise ValueError("Up to 4 trigger keys can be registered")

    # Old code/config paths still read trigger["key"].
    trigger["key"] = trigger["keys"][0]
    return trigger


def set_keyboard_status(status):
    global _keyboard_status
    _keyboard_status = status
    manager = _manager_provider()
    if manager is not None:
        wx.CallAfter(manager.set_keyboard_status, status)


def set_phone_status(status):
    global _phone_status
    _phone_status = status
    manager = _manager_provider()
    if manager is not None:
        wx.CallAfter(manager.set_phone_status, status)


def hotkey_worker(trigger, generation):
    global _hotkey_thread_id
    if os.name != "nt":
        set_keyboard_status("Unavailable")
        log("RegisterHotKey failed: Windows only")
        return

    shortcut = hotkey_description(trigger)
    keys = trigger_keys(trigger)

    # Windows RegisterHotKey supports modifiers + one ordinary key only.
    # Multi-key triggers are still valid for the phone/Studio UDP path.
    if len(keys) != 1:
        set_keyboard_status("Phone Only")
        log(
            "RegisterHotKey skipped shortcut={} reason=multi-key phone-trigger".format(
                shortcut
            )
        )
        return

    virtual_key = virtual_key_code(keys[0])
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


def _worker_key(action_id, source):
    return str(action_id or source or "action")


def is_action_running(action_id, source="action"):
    key = _worker_key(action_id, source)
    with _action_workers_lock:
        worker = _action_workers.get(key)
        thread = worker.get("thread") if worker else None
        return bool(thread is not None and thread.is_alive())


def stop_action(action_id, source="action"):
    """Request a running action to stop.

    Python threads cannot be safely killed externally.  The event is exposed
    to scripts through stop_requested() / wait_or_stop().
    """
    key = _worker_key(action_id, source)
    with _action_workers_lock:
        worker = _action_workers.get(key)
        if not worker:
            return False
        thread = worker.get("thread")
        if thread is None or not thread.is_alive():
            return False
        worker["stop_event"].set()
        debug = bool(worker.get("debug", False))

    debug_log("STOP REQUEST action={}".format(key), debug)
    return True


def _script_print(*args, **kwargs):
    """Result-facing print used by MacroBK scripts."""
    sep = kwargs.pop("sep", " ")
    end = kwargs.pop("end", "\n")
    file_obj = kwargs.pop("file", None)
    flush = kwargs.pop("flush", False)

    if kwargs or (file_obj is not None and file_obj not in (sys.stdout, sys.__stdout__)):
        return builtins.print(*args, sep=sep, end=end, file=file_obj, flush=flush, **kwargs)

    text = sep.join(str(value) for value in args) + str(end)
    # Preserve intentional blank lines and multi-line prints.
    parts = text.splitlines()
    if not parts and text:
        parts = [text]
    for line in parts:
        _append_result(line)

    try:
        sys.__stdout__.write(text)
        if flush:
            sys.__stdout__.flush()
    except Exception:
        pass


def _execute_python_script_worker(script, source, action_id, stop_event, debug):
    key = _worker_key(action_id, source)
    manager = _manager_provider()
    terminal = "SUCCESS"
    ok = True

    debug_log(
        "{} source={} action={} mode=worker".format(
            "TEST RUN" if source == "test" else "ACTION START",
            source,
            key,
        ),
        debug,
    )

    def ui(function):
        def wrapped(*args, **kwargs):
            if stop_event.is_set():
                raise ActionStopped()
            return _call_on_ui_thread(
                function, *args, _stop_event=stop_event, **kwargs
            )
        return wrapped

    def script_open_drc_window():
        return _call_on_ui_thread(
            kc.open_drc_window, source, False, _stop_event=stop_event
        )

    def stop_requested():
        return stop_event.is_set()

    def wait_or_stop(seconds):
        return stop_event.wait(float(seconds))

    # WORKER mode intentionally exposes helper APIs, not raw wx/pcbnew control
    # traversal.  Direct GUI object use belongs in the default GUI mode.
    namespace = {
        "__builtins__": __builtins__,
        "print": _script_print,
        "DEBUG": debug,
        "MODE": "WORKER",
        "EXECUTION_MODE": "WORKER",
        "stop_requested": stop_requested,
        "wait_or_stop": wait_or_stop,
        "open_drc_window": script_open_drc_window,
        "open_menu": ui(kc.open_menu),
        "pcb_select_filter": ui(kc.pcb_select_filter),
        "pcb_select_filter_state": ui(kc.pcb_select_filter_state),
        "test_preferences_direct_children": ui(kc.test_preferences_direct_children),
        "test_preferences_control_tree": ui(kc.test_preferences_control_tree),
        "test_preferences_checkbox_value": ui(kc.test_preferences_checkbox_value),
        "test_preferences_checkbox_toggle_restore": ui(
            kc.test_preferences_checkbox_toggle_restore
        ),
    }

    try:
        if stop_event.is_set():
            raise ActionStopped()

        exec(compile(script, "<MacroBK Plugin Script>", "exec"), namespace, namespace)

        if stop_event.is_set():
            raise ActionStopped()

        run_function = namespace.get("run")
        if callable(run_function):
            run_function()

        if stop_event.is_set():
            raise ActionStopped()

        debug_log("SUCCESS source={} action={} mode=worker".format(source, key), debug)
    except ActionStopped:
        terminal = "STOPPED"
        ok = False
        debug_log("STOPPED source={} action={} mode=worker".format(source, key), debug)
    except BaseException:
        terminal = "ERROR"
        ok = False
        debug_log("ERROR source={} action={} mode=worker".format(source, key), debug)
        error_result("[ERROR] MacroBK script failed")
        for line in traceback.format_exc().rstrip().splitlines():
            error_result(line)
        if manager is not None:
            wx.CallAfter(manager.show_result_tab)
    finally:
        # Terminal UI status is guaranteed for every exit path, including
        # SystemExit/KeyboardInterrupt raised by a user script.
        if manager is not None and source == "test":
            wx.CallAfter(manager.set_test_status, terminal)

        with _action_workers_lock:
            current = _action_workers.get(key)
            if current is not None and current.get("thread") is threading.current_thread():
                _action_workers.pop(key, None)

    return ok



def execute_python_script(script, source, action_id=None):
    """Execute a MacroBK script using an explicit execution mode.

    Default: MODE = "GUI"
        Preserves legacy wx/pcbnew compatibility.

    Optional: MODE = "WORKER"
        Runs in a daemon worker thread.  Use MacroBK GUI helper functions such
        as pcb_select_filter/open_menu rather than raw wx/pcbnew objects.
    """
    key = _worker_key(action_id, source)
    debug = _script_debug_enabled(script)
    mode = _script_execution_mode(script)
    manager = _manager_provider()

    debug_log("EXECUTION MODE {} action={}".format(mode.lower(), key), debug)

    if mode == "GUI":
        # Run Test and trigger callbacks normally arrive on the wx thread.  If
        # called from elsewhere, schedule asynchronously rather than CallAfter
        # + wait, which can deadlock an embedded GUI.
        if _is_gui_thread():
            return _execute_python_script_ui(script, source, action_id, debug)

        wx.CallAfter(
            _execute_python_script_ui,
            script,
            source,
            action_id,
            debug,
        )
        return True

    with _action_workers_lock:
        existing = _action_workers.get(key)
        existing_thread = existing.get("thread") if existing else None
        if existing_thread is not None and existing_thread.is_alive():
            debug_log("ALREADY RUNNING action={}".format(key), debug)
            return False

        stop_event = threading.Event()
        thread = threading.Thread(
            target=_execute_python_script_worker,
            args=(script, source, action_id, stop_event, debug),
            name="MacroBK-Action-{}".format(key),
            daemon=True,
        )
        _action_workers[key] = {
            "thread": thread,
            "stop_event": stop_event,
            "debug": debug,
            "mode": "WORKER",
        }

        # Set RUNNING before starting the worker.  Otherwise a very short
        # script can queue SUCCESS first and then have RUNNING overwrite it.
        if manager is not None and source == "test":
            try:
                manager.set_test_status("RUNNING", stoppable=True)
            except TypeError:
                manager.set_test_status("RUNNING")

        # Start while still holding the registry lock so another simultaneous
        # trigger cannot observe a registered-but-not-yet-alive thread.
        try:
            thread.start()
        except BaseException:
            _action_workers.pop(key, None)
            if manager is not None and source == "test":
                try:
                    manager.set_test_status("ERROR", stoppable=False)
                except TypeError:
                    manager.set_test_status("ERROR")
            raise

    return True



def handle_trigger(source):
    manager = _manager_provider()
    if manager is not None:
        manager.blink_input_signal(source)
    trigger_text = hotkey_description(CONFIG.get("trigger", {}))
    log("TRIGGER source={} trigger={}".format(source, trigger_text))
    script = str(CONFIG.get("action", {}).get("script", ""))
    action_id = str(CONFIG.get("selected_action_id") or "selected-action")
    execute_python_script(script, source, action_id)


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


def start_bridge():
    """Start the MacroBK hotkey and phone UDP listeners once."""
    global _started

    if _started:
        return True

    _started = True
    log("plugin bridge starting")

    try:
        start_hotkey_listener()
    except Exception as exc:
        log("hotkey listener start error: " + repr(exc))

    try:
        thread = threading.Thread(
            target=udp_worker,
            name="MacroBK-KiCad-DRC-UDP",
            daemon=True,
        )
        thread.start()
    except Exception as exc:
        log("UDP listener start error: " + repr(exc))

    return True


kc.set_logger(log)
