# Track width helpers

## API

```python
pcb_set_selected_track_width(width_mm)
pcb_set_routing_track_width(width_mm)
pcb_set_netclass_track_width()
```

### `pcb_set_selected_track_width(width_mm)`

Changes only already-routed `PCB_TRACK` objects that are selected at call time.
`PCB_VIA` is excluded. Connected but unselected segments are not changed.

### `pcb_set_routing_track_width(width_mm)`

Uses KiCad's native **Q / Custom Track/Via Size** path instead of directly
changing `BOARD_DESIGN_SETTINGS` and forcing `pcbnew.Refresh()`.

The helper:

1. sends a real Windows `Q` keystroke to the PCB Editor,
2. waits for KiCad's native Custom Track/Via Size dialog,
3. changes only the Track width field (explicit `mm` suffix),
4. leaves the via fields untouched,
5. presses the dialog's native OK button.

Therefore KiCad itself executes the router path that includes
`onTrackViaSizeChanged -> UpdateSizes -> Move`. This is the missing path that
updates an already-active routing head.

```python
pcb_set_routing_track_width(0.40)
pcb_set_routing_track_width(0.75)
```

The function returns the requested width immediately while the native dialog is
completed by wx timers. Do not fire another routing-width request until the
first native dialog transaction has finished.

No `pcbnew.Refresh()` or `UpdateUserInterface()` is issued by this helper.

### `pcb_set_netclass_track_width()`

Leaves custom track/via-size mode and selects track-width index 0 (netclass/rule
width). Existing routed tracks are not modified.

## Live test

The important test is performed while routing:

1. Start routing with `X` at the current width.
2. Keep PCB Editor/canvas active.
3. Trigger `pcb_set_routing_track_width(0.40)` from MacroBK Phone input.
4. Confirm that the current routing preview does **not** disappear.
5. Confirm that only the routing head after the change point uses 0.40 mm.
6. Finish the route, start another route, and confirm custom 0.40 mm remains.
7. Repeat with 0.75 mm.

`Run Test` may move focus to MacroBK Manager. The helper tries to restore PCB
focus, but Phone triggering is the preferred acceptance test because it leaves
the routing canvas interaction intact.
