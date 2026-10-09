# MacroBK Plugin Manager test

Install the entire `macrobk_drc_bridge` folder under:

`%USERPROFILE%\Documents\KiCad\9.0\scripting\plugins\`

Restart PCB Editor after replacing the plugin.

## Port check

Run `check_port.cmd` before PCB Editor starts to check for an existing UDP 47831 owner.
After PCB Editor loads the plugin, the owner may be `pcbnew.exe` or `kicad.exe`.
Repeated sockets in one process or several KiCad owners indicate old sessions or
repeated plugin loads. Close every KiCad/PCB Editor window (saving boards first),
check that port 47831 is free, and then open one PCB Editor instance.
Copying files or refreshing the plugin list cannot replace running Python modules.

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

Run `test_phone.cmd`. It reads the selected Action from the existing config and sends
`TRIGGER|<canonical ID>` to `239.255.77.77:47831` on interface `127.0.0.1`, matching Studio.
Use `test_phone.cmd CTRL+SHIFT:F12` to test a particular registered Action.
Use `test_phone.cmd --dry-run` to inspect the packet without running an Action.
The old plain `KICAD_DRC` packet is not accepted by the current listener.
The sender reporting SENT does not confirm Action execution; inspect the log for
`PHONE RX`, `PHONE matched`, `ACTION START`, and `SUCCESS` (or the error).
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
