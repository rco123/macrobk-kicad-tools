# MacroBK KiCad Plugin - UDP Trigger Test

Install the entire `macrobk_drc_bridge` folder under:

`%USERPROFILE%\Documents\KiCad\9.0\scripting\plugins\`

Restart PCB Editor after replacing the plugin.

## Input paths

Physical keyboard:

`Ctrl+Win+F12 -> RegisterHotKey -> plugin action`

Phone/MacroBK Studio:

`Phone -> Dongle Vendor HID -> MacroBK Studio trigger match -> UDP multicast TRIGGER|... -> plugin action`

The plugin does not use the old per-plugin `KICAD_DRC` UDP command anymore.

## UDP transport

- Group: `239.255.77.77`
- Port: `47831`
- Interface: `127.0.0.1`
- Expected message example: `TRIGGER|CTRL+WIN:F12`

The receiver uses `SO_REUSEADDR`, so multiple MacroBK plugins/applications can listen on UDP 47831 at the same time.

## Test A - Plugin menu

Use `Tools > External Plugins > MacroBK Plugin Manager`.
The manager window must open.

## Test B - Physical keyboard

Press `Ctrl + Win + F12`.
The saved Python script must execute and the log must contain `source=keyboard`.

## Test C - UDP trigger

Run `test_phone.cmd`.
It multicasts `TRIGGER|CTRL+WIN:F12` on the loopback interface.
The saved Python script must execute and the log must contain `source=phone`.

If the Trigger Key in the plugin is changed, update the `TRIGGER=` line in `test_phone.cmd` for manual testing.
MacroBK Studio itself should send the matched Studio trigger key automatically.

## Test D - Different key

Send a different trigger, for example `TRIGGER|CTRL+WIN:F11` while the plugin is configured for F12.
It must be ignored and logged as an unmatched UDP trigger.

## Test E - Python script

Enter `open_drc_window()` in Execute and click `Run Test`.
The DRC dialog must open and Test Status must show `SUCCESS`.

Log file: `macrobk_drc.log`

## Script execution mode (2026-10-09)

Default mode is GUI for backward compatibility with direct `wx` / `pcbnew` code.

```python
print("GUI mode")
```

Long-running actions must opt in to the worker thread explicitly:

```python
MODE = "WORKER"
import time
print("A")
time.sleep(0.5)
print("B")
```

For a Stop button that wakes immediately during a delay, use:

```python
MODE = "WORKER"
print("waiting")
if wait_or_stop(5):
    print("stop requested")
```

`DEBUG = True` shows internal MacroBK execution diagnostics in Result. Without it,
Result shows user `print()` output and errors only.

WORKER mode should use MacroBK GUI helpers such as `pcb_select_filter()` and
`open_menu()` rather than direct wx/pcbnew object traversal.
