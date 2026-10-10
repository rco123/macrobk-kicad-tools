"""SNAP UI fixtures use the current popup-free backend contract."""
import copy
import importlib
import unittest
from unittest import mock

from test_worker_engine import core, APP
import wx

panel = importlib.import_module(core.__package__ + '.snap_panel')
kc = core.kc


class SnapPanelTests(unittest.TestCase):
    def setUp(self):
        self.frame = wx.Frame(None, title='PCB Editor fixture')
        self.book = wx.Notebook(self.frame)
        for name in ('Layers', 'Objects', 'Nets'):
            self.book.AddPage(wx.Panel(self.book), name)
        self.values = {'pads': 'Always', 'tracks_vias': 'Never', 'graphics': 'Always'}
        self.options = {'pads': ['Never', 'When routing tracks', 'Always'],
                        'tracks_vias': ['Never', 'When routing tracks', 'Always'],
                        'graphics': ['Always', 'Never']}
        getter = mock.patch.object(kc, 'pcb_get_snap_settings', side_effect=self.read)
        setter = mock.patch.object(kc, 'pcb_set_snap_settings', side_effect=self.write)
        menu = mock.patch.object(kc, 'open_menu', side_effect=AssertionError('SNAP must not open a menu'))
        for patch in (getter, setter, menu):
            patch.start()
            self.addCleanup(patch.stop)

    def read(self, include_choices=False):
        if include_choices:
            return {'values': dict(self.values), 'choices': copy.deepcopy(self.options),
                    'source': 'kicad-pcbnew-json'}
        return dict(self.values)

    def write(self, **changes):
        self.values.update(changes)
        return dict(self.values)

    def tearDown(self):
        panel.remove_snap_tab(self.frame)
        self.frame.Destroy()
        APP.Yield(True)

    def test_attach_is_lazy_duplicate_safe_and_owned_cleanup(self):
        native = [self.book.GetPage(i) for i in range(3)]
        page = panel.attach_snap_tab(self.frame)
        self.assertIs(panel.attach_snap_tab(self.frame), page)
        self.assertEqual(self.book.GetPageCount(), 4)
        kc.pcb_get_snap_settings.assert_not_called()
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
        # Before the queued write, display remains the last verified value.
        self.assertEqual(page.choices['graphics'].GetStringSelection(), 'Always')
        APP.Yield(True)
        self.assertEqual(self.values['graphics'], 'Never')
        self.assertEqual(page.choices['graphics'].GetStringSelection(), 'Never')
        kc.pcb_set_snap_settings.assert_called_once_with(graphics='Never')
        self.assertEqual(self.values['pads'], 'Always')

    def test_failed_panel_change_reads_actual_values(self):
        page = panel.attach_snap_tab(self.frame)
        page._perform({})
        kc.pcb_set_snap_settings.side_effect = RuntimeError('fixture failure')
        page._perform({'pads': 'Never'})
        self.assertEqual(page.choices['pads'].GetStringSelection(), 'Always')
        self.assertIn('fixture failure', page.status.GetLabel())

    def test_failed_recovery_disables_unknown_choices(self):
        page = panel.attach_snap_tab(self.frame)
        page._perform({})
        kc.pcb_set_snap_settings.side_effect = RuntimeError('write failed')
        kc.pcb_get_snap_settings.side_effect = RuntimeError('read failed')
        page._perform({'pads': 'Never'})
        for choice in page.choices.values():
            self.assertFalse(choice.IsEnabled())
            self.assertEqual(choice.GetSelection(), wx.NOT_FOUND)

    def test_external_saved_change_refreshes_values(self):
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

    def test_unowned_snap_page_is_preserved(self):
        unowned = wx.Panel(self.book, name='another-plugin')
        self.book.AddPage(unowned, 'SNAP')
        self.assertIsNone(panel.attach_snap_tab(self.frame))
        panel.remove_snap_tab(self.frame)
        self.assertEqual(self.book.GetPageCount(), 4)
        self.assertIs(self.book.GetPage(3), unowned)

    def test_service_frame_hook_attaches_once_without_reading(self):
        service = core.get_service()
        previous_frame, previous_attempts = service.frame, service.snap_attempts
        try:
            service.frame = self.frame
            service.attach_snap_tab()
            service.attach_snap_tab()
            self.assertEqual(self.book.GetPageCount(), 4)
            kc.pcb_get_snap_settings.assert_not_called()
            self.assertIn(core.__package__ + '.snap_panel', service.modules)
        finally:
            service.frame, service.snap_attempts = previous_frame, previous_attempts


if __name__ == '__main__':
    unittest.main()
