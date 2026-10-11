"""Worker-facing GUI APIs. wx objects stay inside the GUI callback.

Control snapshots carry an opaque reference, not a wx object. References are
valid only in this PCB Editor session and while the corresponding window lives.
"""
import collections
import uuid

import wx

from . import kicad_controls as kc

_references = collections.OrderedDict()
_session = uuid.uuid4().hex


def _snapshot(control):
    info = kc.get_control_info(control)
    token = "{}:{}".format(_session, id(control))
    _references[token] = control
    _references.move_to_end(token)
    while len(_references) > 10000:
        _references.popitem(last=False)
    info["_control_ref"] = token
    info["title"] = str(getattr(control, "GetTitle", lambda: "")())
    return info


def _resolve(reference=None):
    if isinstance(reference, dict):
        control = _references.get(reference.get("_control_ref"))
        if control is None or not bool(control) or control.IsBeingDeleted():
            raise RuntimeError("Control snapshot has expired; search again")
        return control
    if reference is not None and not isinstance(reference, str):
        raise TypeError("Use a control snapshot or a window title, not a wx object")
    title = reference or "PCB Editor"
    matches = [window for window in wx.GetTopLevelWindows()
               if not window.IsBeingDeleted() and title in str(getattr(window, "GetTitle", lambda: "")())]
    if len(matches) != 1:
        raise RuntimeError("Expected one window matching {!r}; found {}".format(title, len(matches)))
    return matches[0]


def list_controls(root=None):
    # Fully consume the low-level generator on GUI, including GetChildren calls.
    return [_snapshot(control) for control in kc.iter_controls(_resolve(root))]


def find_controls_info(root=None, control_type=None, label=None, name=None, id=None):
    if control_type is not None and not isinstance(control_type, str):
        raise TypeError("control_type must be a class name string, e.g. 'CheckBox'")
    return [_snapshot(control) for control in kc.find_controls(
        _resolve(root), control_type=control_type, label=label, name=name, id=id)]


def find_control_info(root=None, control_type=None, label=None, name=None, id=None):
    matches = find_controls_info(root, control_type, label, name, id)
    if len(matches) > 1:
        raise RuntimeError("Ambiguous control selector: {} matches".format(len(matches)))
    return matches[0] if matches else None


def get_control_info(control):
    return _snapshot(_resolve(control))


def get_control_value(control):
    return kc.get_control_value(_resolve(control))


def set_control_value(control, value):
    target = _resolve(control)
    kc.set_control_value(target, value)
    return kc.get_control_value(target)


def _value_by(root, criterion, selector, value=None, write=False):
    info = find_control_info(root, **{criterion: selector})
    if info is None:
        raise RuntimeError("Control not found: {}={!r}".format(criterion, selector))
    return set_control_value(info, value) if write else get_control_value(info)


def get_control_value_by_label(label, root=None):
    return _value_by(root, "label", label)


def set_control_value_by_label(label, value, root=None):
    return _value_by(root, "label", label, value, True)


def get_control_value_by_name(name, root=None):
    return _value_by(root, "name", name)


def set_control_value_by_name(name, value, root=None):
    return _value_by(root, "name", name, value, True)


def get_control_value_by_id(id, root=None):
    return _value_by(root, "id", id)


def set_control_value_by_id(id, value, root=None):
    return _value_by(root, "id", id, value, True)


def candidate_frames():
    return [_snapshot(frame) for frame in kc.candidate_frames()]


def get_pcb_selection_filter_panel():
    panel = kc.get_pcb_selection_filter_panel()
    return _snapshot(panel) if panel is not None else None


def find_menu_command(path):
    _frame, _menu, item, actual = kc.find_menu_command(path)
    return {"path": actual, "id": item.GetId()} if item is not None else None


def dispatch_menu_command(command):
    if not isinstance(command, dict) or not isinstance(command.get("path"), str):
        raise TypeError("Use the snapshot returned by find_menu_command")
    return bool(kc.open_menu(command["path"]))


def _plain(value):
    if value is None or type(value) in (str, int, float, bool):
        return value
    if isinstance(value, dict):
        return {_plain(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(_plain(item) for item in value)
    raise TypeError("GUI helper attempted to return a non-snapshot value")


def script_api(call_sync, check_stop):
    functions = {
        "list_controls": list_controls,
        "find_control_info": find_control_info,
        "find_controls_info": find_controls_info,
        # Compatibility names now return snapshots instead of native objects.
        "iter_controls": list_controls,
        "find_control": find_control_info,
        "find_controls": find_controls_info,
        "get_control_info": get_control_info,
        "get_control_value": get_control_value,
        "set_control_value": set_control_value,
        "get_control_value_by_label": get_control_value_by_label,
        "set_control_value_by_label": set_control_value_by_label,
        "get_control_value_by_name": get_control_value_by_name,
        "set_control_value_by_name": set_control_value_by_name,
        "get_control_value_by_id": get_control_value_by_id,
        "set_control_value_by_id": set_control_value_by_id,
        "candidate_frames": candidate_frames,
        "get_pcb_selection_filter_panel": get_pcb_selection_filter_panel,
        "find_menu_command": find_menu_command,
        "dispatch_menu_command": dispatch_menu_command,
        "open_menu": kc.open_menu,
        "pcb_select_filter": kc.pcb_select_filter,
        "pcb_select_filter_state": kc.pcb_select_filter_state,
        "pcb_select_layer": kc.pcb_select_layer,
        "pcb_get_selected_layer": kc.pcb_get_selected_layer,
        "pcb_onoff_layer": kc.pcb_onoff_layer,
        "pcb_layer_up": kc.pcb_layer_up,
        "pcb_layer_down": kc.pcb_layer_down,
        "pcb_set_selected_track_width": kc.pcb_set_selected_track_width,
        "pcb_set_routing_track_width": kc.pcb_set_routing_track_width,
        "pcb_set_netclass_track_width": kc.pcb_set_netclass_track_width,
        "pcb_get_snap_settings": kc.pcb_get_snap_settings,
        "pcb_set_snap_settings": kc.pcb_set_snap_settings,

    }

    def wrap(function):
        def invoke(*args, **kwargs):
            check_stop()
            def gui():
                # Validate/materialize return values before leaving GUI.
                return _plain(function(*args, **kwargs))
            result = call_sync(gui)
            check_stop()
            return result
        return invoke
    return {name: wrap(function) for name, function in functions.items()}
