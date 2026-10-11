# MacroBK KiCAD Tools

**Language / 언어:** **English** | [한국어](README.ko.md)

**Python Automation Plugin for KiCad 9 PCB Editor**  
Developed by **BK Systems** · License: [MIT](LICENSE) · [GitHub Repository](https://github.com/rco123/macrobk-kicad-tools)

MacroBK KiCAD Tools lets you write Python scripts for KiCad PCB Editor operations and run them through **Run Test**, keyboard shortcuts, or **MacroBK triggers**. Supported operations include opening the DRC window, switching layers, changing selection filters and track widths, and adjusting SNAP settings.

> This README is a **user guide**. Additional automation examples will be added to [Use Case Examples](#6-use-case-examples) as they become available.

## Contents

1. [Installation and Launch](#1-installation-and-launch)
2. [Main Window and Controls](#2-main-window-and-controls)
3. [Creating Actions and Python Scripts](#3-creating-actions-and-python-scripts)
4. [Opening the DRC Checker](#4-opening-the-drc-checker)
5. [SNAP Settings](#5-snap-settings)
6. [Use Case Examples](#6-use-case-examples)
7. [Functions Available to Users](#7-functions-available-to-users)
8. [Troubleshooting and Precautions](#8-troubleshooting-and-precautions)

## 1. Installation and Launch

**Supported environment:** KiCad 9 PCB Editor on Windows.

1. Download this repository or clone it with Git.
2. Install all plugin source files along with the entire \`icons\` folder in:

   \`\`\`text
   %USERPROFILE%\Documents\KiCad\9.0\scripting\plugins\macrobk_drc_bridge\
   \`\`\`

   To install using Git and name the destination directory correctly:

   \`\`\`powershell
   cd "$env:USERPROFILE\Documents\KiCad\9.0\scripting\plugins"
   git clone https://github.com/rco123/macrobk-kicad-tools.git macrobk_drc_bridge
   \`\`\`

3. **Completely close KiCad PCB Editor and launch it again.**
4. Open **Tools → External Plugins → MacroBK KiCAD Tools**.

![Selecting MacroBK KiCAD Tools from the External Plugins menu](docs/images/external-plugin-menu.png)

**Before updating:** Your Actions and scripts are stored in \`config.json\` inside the plugin folder. Back up this file before updating. The repository's \`config.example.json\` is only a sample; it does not replace your saved settings.

## 2. Main Window and Controls

![MacroBK KiCAD Tools main window](docs/images/main-window.png)

| Area | What it does |
| --- | --- |
| **Registered Actions** | Select a saved automation Action; use **Add** or **Delete**. **Double-click a name** to rename an Action. |
| **Input Monitor** | Indicators show whether a trigger arrived through **Keyboard** or **MacroBK**. |
| **Trigger Key** | Displays the key combination assigned to the selected Action. |
| **Key Change** | Opens the key selection dialog. **Apply** saves the change; **Cancel** discards it. |
| **Python Script** | Enter the Python code to execute for the selected Action. |
| **Run Test / Stop / Save** | Test the script / request that execution stop / save the Action. |
| **Result** | Shows \`print()\` output and script errors; use **Copy** or **Clear**. |

The status beside the buttons below Python Script can show \`IDLE\`, \`RUNNING\`, \`SUCCESS\`, \`ERROR\`, or \`STOPPING\`. Drag the divider between **Python Script** and **Result** to adjust the panel widths.

### 2.1 Registered Actions

- **Add:** Creates an Action named \`New Action\` with the default trigger \`Ctrl + Win + F12\`. The script field initially contains an instructional comment.
- **Rename:** Double-click the Action you want to rename.
- **Delete:** Deletes the selected Action after confirmation.
- Duplicate Action names are permitted, but distinct names are recommended for clarity.

### 2.2 Input Monitor

- **Keyboard:** Flashes when the plugin handles a keyboard trigger.
- **MacroBK:** Flashes when a MacroBK trigger message is received.
- **Waiting for input:** The plugin is waiting for input.

\`MacroBK Ready\` indicates that the message receiver is ready. It **does not confirm that a hardware device is connected**. The monitor reacts to registered triggers, not every key pressed on the PC.

### 2.3 Key Change

1. Select the desired Action under **Registered Actions**.
2. Click **Key Change**.
3. Choose Ctrl / Alt / Shift / Win modifiers and ordinary keys.
4. Click **Apply** to save and update the trigger immediately, or **Cancel** to close without changing it.

A PC keyboard shortcut supports modifier keys plus **one ordinary key**. A combination with **2–4 ordinary keys** is for **MacroBK input only**. If multiple Actions use the same trigger, a **MacroBK trigger executes only the first enabled matching Action in the list**.

## 3. Creating Actions and Python Scripts

1. Click **Add** to create an Action.
2. Double-click \`New Action\` in the list and enter a meaningful name.
3. Write the desired code in **Python Script**.
4. Click **Run Test** and check the behavior and output under Result.
5. If everything works, click **Save** to store the Action and script.
6. If needed, assign a different trigger using **Key Change → Apply**.

For example, to display the currently selected PCB layer, enter:

\`\`\`python
print(pcb_get_selected_layer())
\`\`\`

Click **Run Test**. Result will display a layer name such as \`F.Cu\` or \`B.Cu\`. The functions listed in [Functions Available to Users](#7-functions-available-to-users) can be called directly in Python Script **without an import statement**.

| Button | Action |
| --- | --- |
| **Run Test** | Immediately executes the code currently in the editor. |
| **Stop** | Requests that the running script stop. |
| **Save** | Saves the current Action and script. |
| **Copy / Clear** | Copies / clears the Result output. |

> **Stop** is not a force-quit command. It does not automatically undo KiCad operations or close dialogs that have already opened.

## 4. Opening the DRC Checker

This example opens KiCad's **Design Rules Checker (DRC)** window.

### 4.1 Enter the Script and Run Test

1. Select the \`Open DRC\` Action or create a new Action.
2. Enter the following in Python Script:

   \`\`\`python
   open_menu("Inspect -> Design Rules Checker")
   \`\`\`

3. Click **Run Test**.
4. If the **Design Rules Checker** window appears, the menu command was executed successfully.

### 4.2 Run the DRC Check

![KiCad Design Rules Checker dialog](docs/images/drc-window.png)

1. Review the available DRC options.
2. Click **Run DRC** at the bottom right of the dialog.
3. Review the results under **Violations**, **Unconnected Items**, and other tabs.
4. Close the dialog when finished.

**Important:** \`open_menu("Inspect -> Design Rules Checker")\` **opens the DRC window only**. The check itself does not start until you click **Run DRC** inside that window. If your KiCad menu uses another language, adjust the menu-path string to match the labels shown in your installation.

## 5. SNAP Settings

Open the **Appearance → SNAP** tab on the right side of KiCad PCB Editor to view the Magnetic Points settings.

![SNAP tab in the Appearance panel](docs/images/appearance-snap.png)

| Setting in KiCad | Python parameter | Accepted values |
| --- | --- | --- |
| **Snap to pads** | \`pads\` | \`Never\`, \`When routing tracks\`, \`Always\` |
| **Snap to tracks and vias** | \`tracks_vias\` | \`Never\`, \`When routing tracks\`, \`Always\` |
| **Snap to graphics** | \`graphics\` | \`Never\`, \`Always\` |

To display the current settings:

\`\`\`python
print(pcb_get_snap_settings())
\`\`\`

To change them:

\`\`\`python
pcb_set_snap_settings(
    pads="Always",
    tracks_vias="When routing tracks",
    graphics="Never"
)
\`\`\`

Omit a parameter to leave that setting unchanged. For example, \`pcb_set_snap_settings(pads="Always")\` changes only the Pads setting.

> Before using SNAP control for the first time, back up your KiCad settings or record their current values. Check each change individually.

## 6. Use Case Examples

New examples can be **appended to this section with consecutive numbers**. Use the same format: **goal → script → how to verify**.

### Example 1. Read or Change the Active Layer

Print the currently selected layer:

\`\`\`python
print(pcb_get_selected_layer())
\`\`\`

Switch to the front copper layer:

\`\`\`python
pcb_select_layer("F.Cu")
\`\`\`

Switch to the back copper layer:

\`\`\`python
pcb_select_layer("B.Cu")
\`\`\`

### Example 2. Show or Hide a Layer

Hide and then show the \`B.SilkS\` layer:

\`\`\`python
pcb_onoff_layer("B.SilkS", False)  # Hide
pcb_onoff_layer("B.SilkS", True)   # Show
\`\`\`

### Example 3. Change the Width of Selected Tracks

First select the **track segments** whose widths you want to change in PCB Editor:

\`\`\`python
changed = pcb_set_selected_track_width(0.30)
print("Changed tracks:", changed)
\`\`\`

This sets the selected track segments to **0.30 mm** and prints the number changed.

### Example 4. Set a Routing Width and Restore the Netclass Width

Set the current routing width to **0.40 mm**:

\`\`\`python
pcb_set_routing_track_width(0.40)
\`\`\`

Restore the default Netclass routing width:

\`\`\`python
pcb_set_netclass_track_width()
\`\`\`

This does **not** change the width of every track that has already been routed.

### Example 5. Change the Selection Filter

Disable track selection, then enable it again:

\`\`\`python
pcb_select_filter("Tracks", False)
pcb_select_filter("Tracks", True)
\`\`\`

Print the complete selection-filter state:

\`\`\`python
print(pcb_select_filter_state())
\`\`\`

### Example 6. Change Only One SNAP Setting

\`\`\`python
pcb_set_snap_settings(pads="Always")
print(pcb_get_snap_settings())
\`\`\`

## 7. Functions Available to Users

The following functions can be **called directly from Python Script**. Replace argument strings and numbers with the values needed for your project.

### 7.1 Menu Commands

| Function | Parameters | Purpose |
| --- | --- | --- |
| \`open_menu(path)\` | \`path\`: string containing a KiCad menu path | Runs the menu command and returns a success flag (\`bool\`). |

\`\`\`python
open_menu("Inspect -> Design Rules Checker")
\`\`\`

### 7.2 Layers

| Function | Parameters | Purpose |
| --- | --- | --- |
| \`pcb_select_layer(name)\` | \`name\`: layer name, e.g. \`"F.Cu"\` | Selects a layer. |
| \`pcb_get_selected_layer()\` | None | Returns the active layer name. |
| \`pcb_onoff_layer(name, value=None)\` | \`name\`: layer name; \`value\`: \`True\` show, \`False\` hide, omitted to read | Gets or changes layer visibility. |
| \`pcb_layer_up()\` | None | Moves to the previous enabled copper layer. |
| \`pcb_layer_down()\` | None | Moves to the next enabled copper layer. |

### 7.3 Selection Filters

| Function | Parameters | Purpose |
| --- | --- | --- |
| \`pcb_select_filter(name, value=None)\` | \`name\`: filter item; \`value\`: \`True\` enable, \`False\` disable, omitted to read | Gets or changes a selection filter. |
| \`pcb_select_filter_state()\` | None | Reads all selection-filter states. |

Accepted filter item names: \`All items\`, \`Locked items\`, \`Footprints\`, \`Text\`, \`Tracks\`, \`Vias\`, \`Pads\`, \`Graphics\`, \`Zones\`, \`Rule Areas\`, \`Dimensions\`, \`Other items\`.

### 7.4 Track Widths

| Function | Parameters | Purpose |
| --- | --- | --- |
| \`pcb_set_selected_track_width(width_mm)\` | \`width_mm\`: positive number (mm) | Changes **selected track segments** and returns the number changed. |
| \`pcb_set_routing_track_width(width_mm)\` | \`width_mm\`: positive number (mm) | Sets the width used for subsequent routing. |
| \`pcb_set_netclass_track_width()\` | None | Restores the Netclass routing width. |

### 7.5 SNAP

| Function | Parameters | Purpose |
| --- | --- | --- |
| \`pcb_get_snap_settings(include_choices=False)\` | Set \`include_choices=True\` to also retrieve available choices. | Reads the current SNAP settings. |
| \`pcb_set_snap_settings(pads=None, tracks_vias=None, graphics=None)\` | Supply setting strings for the fields you wish to change; omit the rest. | Updates SNAP and returns the resulting settings. |

See the [SNAP settings table](#5-snap-settings) for accepted values.

### 7.6 Stopping a Script

| Function | Parameters | Purpose |
| --- | --- | --- |
| \`stop_requested()\` | None | Returns whether Stop has been requested. |
| \`wait_or_stop(seconds)\` | \`seconds\`: duration in seconds | Waits for the specified duration, returning \`True\` if Stop is requested while waiting. |

For a repeating script, check for Stop like this:

\`\`\`python
for n in range(10):
    if wait_or_stop(0.5):
        break
    print(n)
\`\`\`

## 8. Troubleshooting and Precautions

- **Plugin does not appear:** Check the installation folder and restart PCB Editor completely.
- **The DRC dialog opens, but no check runs:** Click **Run DRC** inside the dialog.
- **\`open_menu()\` does not work:** Make sure the script path matches the actual KiCad menu text and language.
- **Keyboard trigger is not working:** Check for Windows shortcut conflicts or multiple ordinary keys. Multi-key combinations are intended for MacroBK input.
- **MacroBK reports Ready but no input is received:** Ready means listening, not necessarily that a device is connected. Confirm that the device or Studio sends the expected trigger.
- **Stop does not interrupt immediately:** Stop requests termination; it does not force-close KiCad dialogs or cancel commands already issued.
- **Saved Actions are missing:** Check the \`config.json\` backup you made before updating.
- **Old \`open_drc_window()\` script fails:** That function has been removed. Use \`open_menu("Inspect -> Design Rules Checker")\` instead.

Python Script runs on your computer. **Use only scripts you trust**, and save or back up your PCB project before testing changes to the board or KiCad settings.

---

**Copyright © 2026 BK Systems.** [MIT License](LICENSE).  
KiCad and third-party libraries retain their respective copyrights and licenses. This plugin is not an officially certified KiCad product.
