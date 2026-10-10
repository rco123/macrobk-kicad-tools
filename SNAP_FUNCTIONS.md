# Appearance SNAP tab

MacroBK adds a `SNAP` page to the PCB Editor Appearance `wx.Notebook`. The native `Layers`, `Objects`, and `Nets` pages are not reparented or modified.

## Popup-free backend

The SNAP page does **not** open `Preferences` for reads or writes.

KiCad 9.0 does not expose `PCBNEW_SETTINGS::m_MagneticItems` directly through the pcbnew Python bindings. It does expose `pcbnew.GetSettingsManager()` and `SETTINGS_MANAGER.Load()`.

The backend therefore uses KiCad's own settings file and settings manager:

1. Read `pcbnew.json` to display `editing.magnetic_pads`, `editing.magnetic_tracks`, and `editing.magnetic_graphics`.
2. When a SNAP choice changes, modify only the requested scalar key(s) in the existing JSON text. The rest of the file is preserved byte-for-byte as far as the scalar substitution allows.
3. Atomically replace the file.
4. Call `pcbnew.GetSettingsManager().Load()` on the GUI thread so KiCad reloads its registered settings objects.
5. Re-read the file and verify the requested values.
6. On failure, restore the original file and reload the original settings.

No `open_menu("Preferences -> Preferences")`, modal dialog, SendKeys, screen coordinates, background polling, or MacroBK setting persistence is used.

## API

```python
values = pcb_get_snap_settings()
# {'pads': 'Always', 'tracks_vias': 'Always', 'graphics': 'Never'}

pcb_set_snap_settings(pads='Never')
pcb_set_snap_settings(
    pads='Always',
    tracks_vias='When routing tracks',
    graphics='Never',
)
```

`None` means leave that setting unchanged.

## UI behavior

Selecting the `SNAP` Appearance page reads the saved KiCad values immediately. No Refresh button is used. Changing one of the three choices invokes `pcb_set_snap_settings()` and then redisplays the verified values.

## KiCad 9.0 values

- Pads: `Never`, `When routing tracks`, `Always`
- Tracks and vias: `Never`, `When routing tracks`, `Always`
- Graphics: `Always`, `Never`

## Lifecycle

The SNAP page is owned by the PCB Editor lifetime, not by the MacroBK Manager. Repeated attachment reuses the owned page. Closing the PCB Editor destroys the child page with its parent notebook.

## Validation note

Static syntax validation can be performed outside KiCad. The important live acceptance check is that changing a SNAP choice:

- opens no additional window,
- does not terminate KiCad,
- updates the displayed selection,
- and changes the actual snapping behavior in the running PCB Editor.
