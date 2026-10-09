# MacroBK KiCad Plugin - split structure

The original single `bridge.py` has been separated without changing the intended behavior.

- `bridge.py` - KiCad ActionPlugin entry point only
- `ui_manager.py` - main Plugin Manager window/layout
- `key_picker.py` - Select Key dialog and 4-key selection UI
- `kicad_controls.py` - KiCad menu/window/control search and manipulation helpers
- `trigger_core.py` - config, logging, hotkey, UDP trigger, Python script execution
- `__init__.py` - registers the plugin and starts listeners

For design changes, edit mainly `ui_manager.py` and `key_picker.py`.
For KiCad control automation, edit `kicad_controls.py`.
For trigger/communication behavior, edit `trigger_core.py`.


## KiCad loader compatibility
Modules support both package imports and direct .py imports. `bridge.py` self-registers only when loaded directly; `__init__.py` uses the same guarded `register_plugin()` path.


## Loader-safe registration
`bridge.py` now registers with only `pcbnew` loaded. `trigger_core.py` and `ui_manager.py` are lazy-loaded so an error in a split module cannot hide the External Plugins menu item.


## 2026-10-09 split repair

Functional-test findings were applied:

- restored `trigger_core.CONFIG = load_config()`
- restored `trigger_core.start_bridge()`
- restored `kicad_controls.LOG_PATH`
- no UI redesign was performed


## PCB Selection Filter helper

`kicad_controls.py` now provides:

```python
pcb_select_filter("Tracks")
pcb_select_filter("Tracks", True)
pcb_select_filter("Tracks", False)

pcb_select_filter("All items", True)
pcb_select_filter("All items", False)

pcb_select_filter("Locked items", True)
pcb_select_filter("Locked items", False)

pcb_select_filter_state()
```

`All items` controls all normal Selection Filter items but intentionally leaves
`Locked items` unchanged.
