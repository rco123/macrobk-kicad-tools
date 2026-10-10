"""Run inside freshly restarted KiCad via Manager; restores all tested settings."""
import json
import sys
import time
from pathlib import Path
import wx

ROOT = Path(__file__).resolve().parent


def run():
    cores = [m for n, m in sys.modules.items() if n.endswith('.trigger_core') and m is not None
             and callable(getattr(m, 'call_gui_sync', None))]
    if len(cores) != 1:
        raise RuntimeError('Expected one live MacroBK worker engine')
    core = cores[0]
    kc = core.kc
    import importlib
    snap = importlib.import_module(core.__package__ + '.snap_panel')
    prefs = importlib.import_module(core.__package__ + '.snap_preferences')
    sync = core.call_gui_sync
    result = {'tests': {}, 'behavior': 'MANUAL TEST REQUIRED', 'original_restored': False}
    def save():
        (ROOT / 'live_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    def attachment():
        frame = kc.find_pcb_frame()
        book = snap.find_appearance_notebook(frame)
        owned = [book.GetPage(i) for i in range(book.GetPageCount()) if book.GetPage(i).GetName() == snap.OWNER]
        result['tests']['startup_auto_attach'] = 'PASS' if len(owned) == 1 else 'FAIL'
        if len(owned) != 1:
            raise RuntimeError('Production SNAP not automatically attached; restart all KiCad windows')
        page = owned[0]
        native = [(book.GetPage(i).GetId(), book.GetPageText(i)) for i in range(3)]
        for _ in range(3):
            if snap.attach_snap_tab(frame) != page: raise AssertionError('duplicate attach')
        result['tests']['duplicate'] = 'PASS'
        result['tests']['native_pages'] = 'PASS' if native == [(book.GetPage(i).GetId(), book.GetPageText(i)) for i in range(3)] else 'FAIL'
        return None
    sync(attachment)
    original = sync(kc.pcb_get_snap_settings)
    result['original'] = original
    save()
    def refresh():
        page = snap.attach_snap_tab(kc.find_pcb_frame())
        page._perform({})
        return {k: c.GetStringSelection() for k, c in page.choices.items()}
    try:
        payload = sync(kc.pcb_get_snap_settings, include_choices=True)
        result['native_choices'] = payload['choices']
        result['tests']['read_all'] = 'PASS'
        for key in ('pads', 'tracks_vias', 'graphics'):
            changed = next(v for v in payload['choices'][key] if v != original[key])
            actual = sync(kc.pcb_set_snap_settings, **{key: changed})
            expected = dict(original, **{key: changed})
            result['tests'][key + '_round_trip'] = 'PASS' if actual == expected else 'FAIL'
            if actual != expected: raise AssertionError('Partial update changed other setting')
            if sync(kc.pcb_set_snap_settings, **original) != original: raise AssertionError('restore failed')
            save()
        def panel_change():
            frame = kc.find_pcb_frame()
            page = snap.attach_snap_tab(frame)
            page._perform({})
            control = page.choices['pads']
            requested = next(v for v in control.GetStrings() if v != original['pads'])
            control.SetStringSelection(requested)
            event = wx.CommandEvent(wx.wxEVT_CHOICE, control.GetId())
            event.SetEventObject(control)
            control.Command(event)
            return requested
        requested = sync(panel_change)
        deadline = time.monotonic() + 10
        def panel_state():
            page = snap.attach_snap_tab(kc.find_pcb_frame())
            return {'busy': page.busy or page.queued,
                    'values': {k: c.GetStringSelection() for k, c in page.choices.items()}}
        while sync(panel_state)['busy']:
            if time.monotonic() > deadline: raise TimeoutError('panel operation timed out')
            time.sleep(.05)
        state = sync(panel_state)
        expected = dict(original, pads=requested)
        result['tests']['panel_choice_event'] = 'PASS' if state['values'] == expected and sync(kc.pcb_get_snap_settings) == expected else 'FAIL'
        sync(kc.pcb_set_snap_settings, **original)
        result['tests']['refresh_actual_values'] = 'PASS' if sync(refresh) == original else 'FAIL'
        # Owned native modal represents a user's already-open Preferences draft.
        def protection():
            baseline = tuple(wx.GetTopLevelWindows())
            check = {}
            def inside():
                dialogs = [d for d in prefs.preferences_windows() if d not in baseline]
                if len(dialogs) != 1: raise AssertionError('Protection fixture dialog missing')
                dialog = dialogs[0]
                try:
                    controls = prefs.magnetic_controls(dialog)
                    controls['pads'].SetStringSelection(requested)
                    before = {k: c.GetStringSelection() for k, c in controls.items()}
                    for operation in (kc.pcb_get_snap_settings, lambda: kc.pcb_set_snap_settings(pads=original['pads'])):
                        try: operation()
                        except prefs.PreferencesBusy: pass
                        else: raise AssertionError('User Preferences not protected')
                    check['pass'] = before == {k: c.GetStringSelection() for k, c in controls.items()} and dialog.IsShown()
                except Exception as exc:
                    check['error'] = repr(exc)
                finally:
                    prefs.cancel_dialog(dialog)
            timer = wx.CallLater(150, inside)
            try: kc.open_menu('Preferences -> Preferences')
            finally: timer.Stop()
            return check.get('pass', False)
        result['tests']['preferences_open_protection'] = 'PASS' if sync(protection) else 'FAIL'
        # Change via the native Preferences controls, bypassing the production setter.
        external_value = next(v for v in payload['choices']['graphics'] if v != original['graphics'])
        def external_change():
            baseline = tuple(wx.GetTopLevelWindows())
            outcome = {}
            def inside():
                dialogs = [d for d in prefs.preferences_windows() if d not in baseline]
                if len(dialogs) != 1: return
                dialog = dialogs[0]
                try:
                    controls = prefs.magnetic_controls(dialog)
                    kc.set_control_value(controls['graphics'], external_value)
                    kc._command_ok_button(dialog)
                    outcome['ok'] = True
                except Exception as exc:
                    outcome['error'] = repr(exc)
                    prefs.cancel_dialog(dialog)
            timer = wx.CallLater(150, inside)
            try: kc.open_menu('Preferences -> Preferences')
            finally: timer.Stop()
            return outcome.get('ok', False)
        external_ok = sync(external_change)
        expected = dict(original, graphics=external_value)
        result['tests']['external_preferences_change_refresh'] = 'PASS' if external_ok and sync(refresh) == expected else 'FAIL'
    except Exception as exc:
        result['error'] = repr(exc)
        raise
    finally:
        try:
            restored = sync(kc.pcb_set_snap_settings, **original)
            result['restored'] = restored
            result['original_restored'] = restored == original
            sync(refresh)
        finally:
            save()
    print('SNAP production tests:', result['tests'], 'restored:', result['original_restored'])
