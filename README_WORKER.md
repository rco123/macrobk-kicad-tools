# MacroBK Worker / Helper API

All Action scripts run in a daemon worker. Run Test, keyboard and UDP use the
same engine. No MODE setting or automatic script classification is used.
Restart PCB Editor after manually updating plugin sources; Refresh Plugins
does not reload live engine/Manager modules or abandon existing workers.

## Examples

```python
import time
print("START")
time.sleep(5)  # GUI remains responsive; Stop takes effect when sleep returns.
print("END")
```

```python
print("WAIT")
if wait_or_stop(10):
    print("STOP REQUESTED")
```

```python
import time
original = pcb_select_filter_state()
try:
    pcb_select_filter("Tracks", False)
    time.sleep(0.5)
    pcb_select_filter("Tracks", True)
finally:
    # Cancellation also cancels Helpers; restore required persistent settings
    # in a separate action after Stop rather than relying on this finally.
    print(original)
```

Read the Selection Filter without raw wx access:

```python
panel = get_pcb_selection_filter_panel()  # dict snapshot
for info in list_controls(panel):
    print(info["type"], info["label"], info["value"])
```

## API

GUI work executes only inside a main-thread callback. Worker return values are
plain dict/list/tuple/scalar snapshots. `root` may be a unique window-title
substring (default `PCB Editor`) or a snapshot returned by a previous search.
Ambiguous/expired selectors raise an error rather than changing an arbitrary
control. References last only for this session/window lifetime and may expire
after 10,000 distinct control snapshots.

- `list_controls(root=None)` — materialized descendant snapshots.
- `find_control_info(root=None, control_type=None, label=None, name=None, id=None)`
- `find_controls_info(root=None, control_type=None, label=None, name=None, id=None)`
- `get_control_info(snapshot)`, `get_control_value(snapshot)`
- `set_control_value(snapshot, value)`
- `get_control_value_by_label(label, root=None)`
- `set_control_value_by_label(label, value, root=None)`
- `get_control_value_by_name(name, root=None)`
- `set_control_value_by_name(name, value, root=None)`
- `get_control_value_by_id(id, root=None)`
- `set_control_value_by_id(id, value, root=None)`
- `candidate_frames()` — frame snapshots.
- `get_pcb_selection_filter_panel()` — Tracks CheckBox's parent Panel snapshot.
- `pcb_select_filter(name, value=None)`, `pcb_select_filter_state()`
- `open_menu(path)` — bool result; menu lookup/dispatch stays on GUI.
- `find_menu_command(path)`, `find_drc_command()` — command snapshots.
- `dispatch_menu_command(command_snapshot)`
- `open_drc_window()` — opens DRC, does not run board checks automatically.
- `test_preferences_direct_children()`, `test_preferences_control_tree()`
- `test_preferences_checkbox_value()`, `test_preferences_checkbox_toggle_restore()`
- `stop_requested()`, `wait_or_stop(seconds)`

`control_type` is a string such as `"CheckBox"` or `"wx.CheckBox"`. Compatibility
names `iter_controls`, `find_control`, `find_controls` remain available but now
return snapshots. Existing scripts calling wx methods on their return values
must migrate to dictionary fields or selector Helpers.

All items affects the ten normal Selection Filter items; Locked items remains
independent. Existing SetValue behavior is retained. Whether KiCad's internal
selection model needs an additional checkbox command event has not been
verified against a real KiCad board in this work.

## Stop and output

Stop targets the Action/run that started Run Test, even after selecting another
Action. It never kills a Python/native thread. A lightweight line trace checks
Stop between user-script lines, so after `time.sleep` returns the next line is
not executed. Long native calls/imports are not forcibly interrupted.
`wait_or_stop` returns promptly and allows the script to print a cooperative
shutdown message; a script that acknowledges Stop this way must finish its
own cleanup. Helpers check Stop before/after each GUI operation.

GUI sync waits poll every 50 ms and time out after 10 seconds. A callback that
has not begun is skipped after cancellation/timeout; an already-running GUI
operation cannot be rolled back by Stop. Long/modal GUI functions can outlast
the worker timeout and must be closed by the user.

Result print is delivered asynchronously with no Event wait. Ordinary Result
contains script print and traceback only. Top-level literal `DEBUG = True`
adds source/action/run/thread/helper diagnostics. Imported libraries writing
directly to builtins.print/sys.stdout are not captured by the script's print
replacement. `SystemExit` and `KeyboardInterrupt` terminate with ERROR.

`wx` and `pcbnew` remain available for advanced compatibility, but direct raw
GUI use from the worker is unsafe. The default functions use Helpers; raw
scripts such as wx.GetTopLevelWindows must migrate to the snapshot APIs.

## Test command

```powershell
& 'C:\Program Files\KiCad\9.0\bin\python.exe' -B 'kicad-plugin\tests\test_worker_engine.py'
```

These tests use real wx widgets and the project's Manager in a separate
process. The hidden PCB frame is a test fixture, not a KiCad board. No installed
plugin, existing Action config, board or user Preferences are changed.
