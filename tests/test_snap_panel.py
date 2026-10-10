"""Real wx dialog transactions; fixture settings, never user's KiCad settings."""
import importlib
import unittest
from unittest import mock
import wx
from test_worker_engine import core, APP

prefs = importlib.import_module(core.__package__ + '.snap_preferences')
panel = importlib.import_module(core.__package__ + '.snap_panel')
kc = core.kc


class SnapTests(unittest.TestCase):
    def setUp(self):
        self.frame = wx.Frame(None, title='PCB Editor fixture')
        self.book = wx.Notebook(self.frame)
        for name in ('Layers', 'Objects', 'Nets'):
            self.book.AddPage(wx.Panel(self.book), name)
        self.values = {'pads': 'Always', 'tracks_vias': 'Never', 'graphics': 'Always'}
        self.options = {'pads': ['Never', 'When routing tracks', 'Always'],
                        'tracks_vias': ['Never', 'When routing tracks', 'Always'],
                        'graphics': ['Always', 'Never']}
        self.accepts = 0
        self.opens = 0
        self.other = True
        self.frame_patch = mock.patch.object(kc, 'find_pcb_frame', return_value=self.frame)
        self.menu_patch = mock.patch.object(kc, 'open_menu', side_effect=self.open_preferences)
        self.frame_patch.start(); self.menu_patch.start()

    def tearDown(self):
        prefs.cleanup()
        panel.remove_snap_tab(self.frame)
        self.frame.Destroy()
        APP.Yield(True)
        self.frame_patch.stop(); self.menu_patch.stop()

    def open_preferences(self, path):
        self.assertEqual(path, 'Preferences -> Preferences')
        self.opens += 1
        dialog = wx.Dialog(self.frame, title='Preferences')
        book = wx.Treebook(dialog)
        book.AddPage(wx.Panel(book), 'PCB Editor')
        page = wx.Panel(book)
        book.AddSubPage(page, 'Editing Options')
        choices = {}
        for key, label in prefs.LABELS.items():
            wx.StaticText(page, label=label)
            choices[key] = wx.Choice(page, choices=self.options[key])
            choices[key].SetStringSelection(self.values[key])
        unrelated = wx.CheckBox(page, label='Unrelated preference')
        unrelated.SetValue(self.other)
        ok = wx.Button(dialog, wx.ID_OK, 'OK')
        cancel = wx.Button(dialog, wx.ID_CANCEL, 'Cancel')
        cancel.Bind(wx.EVT_BUTTON, lambda event: dialog.EndModal(wx.ID_CANCEL))
        def accept(event):
            self.accepts += 1
            self.values = {k: c.GetStringSelection() for k, c in choices.items()}
            self.other = unrelated.GetValue()
            dialog.EndModal(wx.ID_OK)
        ok.Bind(wx.EVT_BUTTON, accept)
        try:
            dialog.ShowModal()
        finally:
            dialog.Destroy()
        return True

    def test_getter_cancels_and_native_options(self):
        original = dict(self.values)
        result = kc.pcb_get_snap_settings(include_choices=True)
        self.assertEqual(result, {'values': original, 'choices': self.options})
        self.assertEqual(self.values, original)
        self.assertEqual(self.accepts, 0)

    def test_partial_setter_preserves_other_values_and_preference(self):
        result = kc.pcb_set_snap_settings(pads='Never')
        self.assertEqual(result, {'pads': 'Never', 'tracks_vias': 'Never', 'graphics': 'Always'})
        self.assertEqual(self.accepts, 1)
        self.assertEqual(self.opens, 2)
        self.assertTrue(self.other)

    def test_all_settings_and_restore(self):
        original = dict(self.values)
        self.assertEqual(kc.pcb_set_snap_settings(pads='Never', tracks_vias='Always', graphics='Never'),
                         {'pads': 'Never', 'tracks_vias': 'Always', 'graphics': 'Never'})
        self.assertEqual(kc.pcb_set_snap_settings(**original), original)

    def test_invalid_value_does_not_accept_any_draft(self):
        original = dict(self.values)
        with self.assertRaises(ValueError):
            kc.pcb_set_snap_settings(pads='Never', graphics='invalid')
        self.assertEqual(self.values, original)
        self.assertEqual(self.accepts, 0)

    def test_existing_preferences_protected(self):
        dialog = wx.Dialog(self.frame, title='Preferences')
        draft = wx.TextCtrl(dialog, value='unsaved user draft')
        dialog.Show()
        try:
            with self.assertRaises(prefs.PreferencesBusy): kc.pcb_get_snap_settings()
            with self.assertRaises(prefs.PreferencesBusy): kc.pcb_set_snap_settings(pads='Never')
            self.assertEqual(draft.GetValue(), 'unsaved user draft')
            self.assertTrue(dialog.IsShown())
            self.assertEqual(self.opens, 0)
        finally:
            dialog.Destroy()
            APP.Yield(True)

    def test_attach_is_lazy_duplicate_safe_and_owned_cleanup(self):
        native = [self.book.GetPage(i) for i in range(3)]
        page = panel.attach_snap_tab(self.frame)
        self.assertIs(panel.attach_snap_tab(self.frame), page)
        self.assertEqual(self.book.GetPageCount(), 4)
        self.assertEqual(self.opens, 0)
        panel.remove_snap_tab(self.frame)
        self.assertEqual(self.book.GetPageCount(), 3)
        self.assertEqual([self.book.GetPage(i) for i in range(3)], native)
        self.assertTrue(page.disposed)

    def test_panel_choice_updates_verified_values(self):
        page = panel.attach_snap_tab(self.frame)
        page._perform({})
        self.assertEqual(page.choices['tracks_vias'].GetStrings(), self.options['tracks_vias'])
        page.choices['graphics'].SetStringSelection('Never')
        page.on_snap_choice_changed(None, 'graphics')
        APP.Yield(True)
        self.assertEqual(self.values['graphics'], 'Never')
        self.assertEqual(page.choices['graphics'].GetStringSelection(), 'Never')
        self.assertEqual(self.values['pads'], 'Always')

    def test_failed_panel_change_never_displays_optimistic_value(self):
        page = panel.attach_snap_tab(self.frame)
        page._perform({})
        with mock.patch.object(kc, 'pcb_set_snap_settings', side_effect=RuntimeError('fixture failure')):
            page._perform({'pads': 'Never'})
        self.assertEqual(page.choices['pads'].GetStringSelection(), 'Always')

    def test_external_change_refreshes_actual_values(self):
        page = panel.attach_snap_tab(self.frame)
        page._perform({})
        self.values['graphics'] = 'Never'
        page._perform({})
        self.assertEqual(page.choices['graphics'].GetStringSelection(), 'Never')

    def test_parent_destroy_disposes_page_and_queued_refresh(self):
        page = panel.attach_snap_tab(self.frame)
        page.refresh_from_kicad()
        self.frame.Destroy()
        APP.Yield(True)
        self.assertTrue(page.disposed)
        self.assertFalse(bool(page))
        self.frame = wx.Frame(None, title='replacement fixture')

    def test_service_frame_hook_attaches_once_without_reading(self):
        lifecycle = importlib.import_module(core.__package__ + '.lifecycle')
        service = core.get_service()
        previous_frame, previous_attempts = service.frame, service.snap_attempts
        try:
            service.frame = self.frame
            service.attach_snap_tab()
            service.attach_snap_tab()
            self.assertEqual(self.book.GetPageCount(), 4)
            self.assertEqual(self.opens, 0)
            self.assertIn(core.__package__ + '.snap_panel', service.modules)
        finally:
            service.frame, service.snap_attempts = previous_frame, previous_attempts


if __name__ == '__main__':
    unittest.main()
