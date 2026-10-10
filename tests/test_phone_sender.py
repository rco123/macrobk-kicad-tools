"""Phone packet sender tests never transmit or execute Actions."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SENDER = Path(__file__).resolve().parents[1] / 'tools' / 'phone_trigger_test.py'
spec = importlib.util.spec_from_file_location('macrobk_phone_sender_fixture', SENDER)
sender = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sender)


class PhoneSenderTests(unittest.TestCase):
    def test_selected_action_and_canonical_order(self):
        config = {'selected_action_id': 'selected', 'actions': [
            {'id': 'other', 'trigger': {'key': 'F1'}},
            {'id': 'selected', 'trigger': {'enabled': True, 'shift': True, 'ctrl': True,
                                          'keys': ['b', 'A', 'b']}}]}
        self.assertEqual(sender.configured_trigger(config), 'CTRL+SHIFT:A,B')

    def test_legacy_single_key(self):
        self.assertEqual(sender.configured_trigger({'trigger': {'win': True, 'key': 'F12'}}), 'WIN:F12')

    def test_disabled_or_empty_trigger_rejected(self):
        for trigger in ({'enabled': False, 'key': 'F12'}, {'keys': [' '], 'key': ''}):
            with self.subTest(trigger=trigger), self.assertRaises(ValueError):
                sender.configured_trigger({'trigger': trigger})

    def test_cli_reads_explicit_config_without_transmitting(self):
        with tempfile.TemporaryDirectory(prefix='macrobk_phone_') as folder:
            path = Path(folder) / 'config.json'
            path.write_text(json.dumps({'trigger': {'ctrl': True, 'key': 'F12'}}), encoding='utf-8')
            result = subprocess.run([sys.executable, '-B', str(SENDER), '--config', str(path), '--dry-run'],
                                    cwd=folder, capture_output=True, text=True, check=True)
        self.assertIn('PACKET=TRIGGER|CTRL:F12', result.stdout)
        self.assertIn('DRY RUN: no packet sent', result.stdout)
        self.assertNotIn('SENT:', result.stdout)

    def test_cli_explicit_trigger_needs_no_config(self):
        result = subprocess.run([sys.executable, '-B', str(SENDER), 'CTRL+SHIFT:F12', '--dry-run',
                                 '--config', '/nonexistent/config.json'],
                                capture_output=True, text=True, check=True)
        self.assertIn('PACKET=TRIGGER|CTRL+SHIFT:F12', result.stdout)


if __name__ == '__main__':
    unittest.main()
