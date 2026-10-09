# MacroBK Plugin Manager test

Install the entire `macrobk_drc_bridge` folder under:

`%USERPROFILE%\Documents\KiCad\9.0\scripting\plugins\`

Restart PCB Editor after replacing the plugin.

## Port check

Run `check_port.cmd` before PCB Editor starts to check for an existing UDP 47831 owner.
After PCB Editor loads the plugin, the owner should be `pcbnew.exe`.

Run `check_hotkey.cmd` before PCB Editor starts to verify that `Ctrl+Win+F12` is free.
After the plugin loads successfully, it should report the hotkey as in use.

## Test A: plugin menu

Use `Tools > External Plugins > MacroBK Plugin Manager`.
The manager window must open with a fixed Trigger Register panel and Execute/Result tabs.

## Test B: keyboard

Press `Ctrl + Win + F12` on the physical keyboard.
The input indicator must blink, the saved Python must run, and the log must contain `source=keyboard`.
The startup log reports whether `RegisterHotKey` succeeded or failed because of a conflict.

## Test C: phone/MacroBK command path

Run `test_phone.cmd`. It sends only the UDP text `KICAD_DRC`; it does not synthesize keyboard input.
The input indicator must blink, the saved Python must run, and the log must contain `source=phone`.

## Test D: Python success

Enter `open_drc_window()` in Execute and click `Test Run`.
The DRC dialog must open and Test Status must show `SUCCESS`.

## Test E: Python error

Enter `raise RuntimeError("test error")` and click `Test Run`.
Test Status must show `ERROR`, Result must become active, and the complete traceback must appear.

## Test F/G: saved action

Save `open_drc_window()`, then repeat the keyboard and phone tests. Both inputs must execute the same saved script.

Log file: `macrobk_drc.log`
