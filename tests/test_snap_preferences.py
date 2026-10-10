"""Real temporary JSON files with an injected settings manager; no KiCad needed.

This tests disk transactions and rollback, not live KiCad snapping behavior.
"""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


class SnapPreferencesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='macrobk_snap_')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'pcbnew.json'
        self.original = ('{\n  "editing": {\n    "magnetic_pads": 2,\n'
                         '    "magnetic_tracks": 0, "magnetic_graphics": true\n'
                         '  },\n  "unrelated": {"theme": "keep", "value": 123}\n}\n')
        self.path.write_text(self.original, encoding='utf-8')
        self.manager = mock.Mock()
        self.native = types.ModuleType('pcbnew')
        self.native.GetSettingsManager = mock.Mock(return_value=self.manager)
        self.native.GetBuildVersion = lambda: '9.0.9'
        self.wx = types.ModuleType('wx')
        self.wx.IsMainThread = mock.Mock(return_value=True)
        package = types.ModuleType('_macrobk_snap_fixture')
        package.__path__ = [str(ROOT)]
        self.kc = types.ModuleType(package.__name__ + '.kicad_controls')
        self.kc.log = mock.Mock()
        spec = importlib.util.spec_from_file_location(package.__name__ + '.snap_preferences',
                                                     ROOT / 'snap_preferences.py')
        self.prefs = importlib.util.module_from_spec(spec)
        modules = {'pcbnew': self.native, 'wx': self.wx, package.__name__: package,
                   self.kc.__name__: self.kc, spec.name: self.prefs}
        # Imports are isolated; never replace modules in the integration suite.
        with mock.patch.dict(sys.modules, modules):
            spec.loader.exec_module(self.prefs)
        self.prefs.settings_path = lambda: str(self.path)

    def text(self):
        return self.path.read_text(encoding='utf-8')

    def test_read_payload_has_current_source_and_does_not_reload(self):
        result = self.prefs.request(include_choices=True)
        self.assertEqual(result['values'], {'pads': 'Always', 'tracks_vias': 'Never', 'graphics': 'Always'})
        self.assertEqual(result['source'], 'kicad-pcbnew-json')
        self.assertEqual(result['choices']['graphics'], ['Always', 'Never'])
        self.manager.Load.assert_not_called()
        self.assertEqual(self.text(), self.original)

    def test_partial_write_preserves_all_other_text(self):
        result = self.prefs.request({'pads': 'Never', 'graphics': None})
        self.assertEqual(result, {'pads': 'Never', 'tracks_vias': 'Never', 'graphics': 'Always'})
        self.assertEqual(self.text(), self.original.replace('"magnetic_pads": 2', '"magnetic_pads": 0'))
        self.manager.Load.assert_called_once_with()
        self.assertEqual(list(Path(self.temp.name).glob('*.tmp')), [])

    def test_all_choices_round_trip_and_restore(self):
        original_values = self.prefs.request()
        for pads in self.prefs.CANONICAL_CHOICES['pads']:
            for tracks in self.prefs.CANONICAL_CHOICES['tracks_vias']:
                for graphics in self.prefs.CANONICAL_CHOICES['graphics']:
                    expected = {'pads': pads, 'tracks_vias': tracks, 'graphics': graphics}
                    self.assertEqual(self.prefs.request(expected), expected)
        self.assertEqual(self.prefs.request(original_values), original_values)
        self.assertEqual(self.text(), self.original)

    def test_invalid_batch_is_rejected_before_writing(self):
        with self.assertRaises(ValueError):
            self.prefs.request({'pads': 'Never', 'graphics': 'invalid'})
        self.assertEqual(self.text(), self.original)
        self.manager.Load.assert_not_called()

    def test_unknown_key_is_rejected(self):
        with self.assertRaises(ValueError):
            self.prefs.request({'unknown': 'Always'})
        self.assertEqual(self.text(), self.original)

    def test_unchanged_values_do_not_reload(self):
        self.prefs.request({'pads': 'Always'})
        self.manager.Load.assert_not_called()
        self.assertEqual(self.text(), self.original)

    def test_wrong_thread_cannot_write(self):
        self.wx.IsMainThread.return_value = False
        with self.assertRaisesRegex(RuntimeError, 'GUI thread'):
            self.prefs.request({'pads': 'Never'})
        self.assertEqual(self.text(), self.original)
        self.manager.Load.assert_not_called()

    def test_reload_failure_restores_original_file(self):
        self.manager.Load.side_effect = [RuntimeError('reload failed'), None]
        with self.assertRaisesRegex(RuntimeError, 'reload failed'):
            self.prefs.request({'pads': 'Never'})
        self.assertEqual(self.text(), self.original)
        self.assertEqual(self.manager.Load.call_count, 2)

    def test_verification_failure_restores_original_file(self):
        def external_write():
            if self.manager.Load.call_count == 1:
                self.path.write_text(self.original, encoding='utf-8')
        self.manager.Load.side_effect = external_write
        with self.assertRaisesRegex(RuntimeError, 'verification failed'):
            self.prefs.request({'pads': 'Never'})
        self.assertEqual(self.text(), self.original)
        self.assertEqual(self.manager.Load.call_count, 2)

    def test_missing_settings_manager_restores_original_file(self):
        self.native.GetSettingsManager.return_value = None
        with self.assertRaisesRegex(RuntimeError, 'unavailable'):
            self.prefs.request({'pads': 'Never'})
        self.assertEqual(self.text(), self.original)
        self.kc.log.assert_called_once()

    def test_failed_atomic_replace_leaves_no_temporary_file(self):
        with mock.patch.object(self.prefs.os, 'replace', side_effect=OSError('replace failed')):
            with self.assertRaisesRegex(OSError, 'replace failed'):
                self.prefs.request({'pads': 'Never'})
        self.assertEqual(self.text(), self.original)
        self.assertEqual(list(Path(self.temp.name).glob('*.tmp')), [])
        self.manager.Load.assert_not_called()

    def test_missing_or_duplicate_scalar_fails_without_writing(self):
        for text in (self.original.replace('magnetic_pads', 'missing_pads'),
                     self.original.replace('"theme": "keep"', '"magnetic_pads": 1')):
            with self.subTest(text=text):
                self.path.write_text(text, encoding='utf-8')
                with self.assertRaises(RuntimeError):
                    self.prefs.request({'pads': 'Never'})
                self.assertEqual(self.text(), text)
        self.manager.Load.assert_not_called()

    def test_invalid_json_is_not_overwritten(self):
        self.path.write_text('{broken', encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'Could not read'):
            self.prefs.request({'pads': 'Never'})
        self.assertEqual(self.text(), '{broken')

    def test_version_series_accepts_build_suffix_and_rejects_unknown(self):
        self.native.GetBuildVersion = lambda: '9.0.9-rc1'
        self.assertEqual(self.prefs._version_series(), '9.0')
        self.native.GetBuildVersion = lambda: 'unknown'
        with self.assertRaises(RuntimeError):
            self.prefs._version_series()


if __name__ == '__main__':
    unittest.main()
