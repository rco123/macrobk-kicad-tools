"""Run through MacroBK Manager; verifies saved SNAP values and restores them.

Live snapping on the PCB canvas must still be checked manually. This script
uses the GUI helper bridge and never opens Preferences or accesses removed
Preferences-dialog APIs.
"""
import importlib
import sys


def run():
    cores = [module for name, module in sys.modules.items()
             if name.endswith('.trigger_core') and module is not None
             and callable(getattr(module, 'call_gui_sync', None))]
    if len(cores) != 1:
        raise RuntimeError('Expected one live MacroBK worker engine')
    core = cores[0]
    snap = importlib.import_module(core.__package__ + '.snap_panel')
    original = core.call_gui_sync(core.kc.pcb_get_snap_settings)
    print('Original SNAP:', original)
    try:
        payload = core.call_gui_sync(core.kc.pcb_get_snap_settings, include_choices=True)
        for key, choices in payload['choices'].items():
            changed = next(value for value in choices if value != original[key])
            actual = core.call_gui_sync(core.kc.pcb_set_snap_settings, **{key: changed})
            expected = dict(original, **{key: changed})
            if actual != expected:
                raise AssertionError('Partial SNAP update mismatch: {!r}'.format(actual))
            core.call_gui_sync(core.kc.pcb_set_snap_settings, **original)
            print(key, 'round trip passed')
    finally:
        restored = core.call_gui_sync(core.kc.pcb_set_snap_settings, **original)
        if restored != original:
            raise AssertionError('SNAP restore mismatch: {!r}'.format(restored))
        # Refresh any existing owned SNAP page on the GUI thread.
        def refresh_panel():
            page = snap.attach_snap_tab(core.kc.find_pcb_frame())
            if page is not None:
                page._perform({})
        core.call_gui_sync(refresh_panel)
        print('Original SNAP restored')
    print('MANUAL CHECK: confirm actual snapping on the PCB canvas')


if __name__ == '__main__':
    run()
