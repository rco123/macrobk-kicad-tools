"""Synthetic wx fixtures validate diagnostic mechanics, not real active layer."""
import copy
import importlib.util
from pathlib import Path
import threading
import unittest
from unittest import mock

from test_worker_engine import APP
import wx

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


diag = load("diagnostic_fixture", ROOT / "tests" / "tools" / "layer_diagnostics.py")
comparison = load("comparison_fixture", ROOT / "tests" / "tools" / "compare_layer_dumps.py")


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.frame = wx.Frame(None, title="Diagnostic fixture")
        bar = wx.MenuBar(); bar.Append(wx.Menu(), "Fixture"); self.frame.SetMenuBar(bar)
        self.rows = {}
        for name in diag.TARGETS:
            row = wx.Panel(self.frame)
            image = wx.Image(4, 4); image.SetData(bytes([128] * 48)); image.SetAlpha(bytes([0] * 16))
            wx.StaticBitmap(row, bitmap=wx.Bitmap(image))
            wx.StaticText(row, label=name)
            self.rows[name] = row
        self.board_patch = mock.patch.object(diag.pcbnew, "GetBoard", return_value=None)
        self.board_patch.start()
    def tearDown(self):
        self.board_patch.stop(); self.frame.Destroy(); APP.Yield(True)
    def test_capture_structure_and_unavailable_api(self):
        result = diag.dump_layer_selection_state(frame=self.frame, write=False)
        self.assertEqual(len(result["rows"]), 4)
        self.assertFalse(result["frame_api"]["GetActiveLayer"]["present"])
        for row in result["rows"]:
            self.assertEqual(row["bitmap_count"], 1)
            self.assertIn("children", row["row"])
            self.assertIn("accessible", row["row"])
            self.assertIn("client_data", row["row"])
    def test_windows_off_near_transparent_pixel_is_not_selected_proof(self):
        image = wx.Image(4, 4); image.SetData(bytes([128] * 48))
        image.SetAlpha(bytes([10] + [0] * 15))
        metrics = diag.bitmap_metrics(wx.Bitmap(image))
        self.assertEqual(metrics["nontransparent_pixel_count"], 1)
        self.assertEqual(metrics["alpha_gt_16_count"], 0)
        self.assertEqual(metrics["opaque_pixel_count"], 0)
        self.assertEqual(metrics["alpha_sum"], 10)
    def test_opaque_bitmap_and_mask(self):
        image = wx.Image(2, 2); image.SetData(bytes([10, 20, 30] * 3 + [0, 0, 0]))
        image.SetMaskColour(0, 0, 0)
        metrics = diag.bitmap_metrics(wx.Bitmap(image))
        self.assertEqual(metrics["nontransparent_pixel_count"], 3)
    def test_wrong_thread_rejected(self):
        errors = []
        def capture():
            try: diag.dump_layer_selection_state(frame=self.frame, write=False)
            except RuntimeError as exc: errors.append(str(exc))
        thread = threading.Thread(target=capture); thread.start(); thread.join(1)
        self.assertEqual(len(errors), 1)
    def test_expected_label_does_not_alter_or_predict_state(self):
        first = diag.dump_layer_selection_state(expected="F.Cu", frame=self.frame, write=False)
        second = diag.dump_layer_selection_state(expected="B.Cu", frame=self.frame, write=False)
        self.assertEqual(first["rows"], second["rows"])
        self.assertTrue(first["prediction"].startswith("NOT IMPLEMENTED"))
        self.assertFalse(comparison.compare([first, second])["candidate_fields"])
    def test_comparator_reports_synthetic_changes_not_verification(self):
        base = diag.dump_layer_selection_state(frame=self.frame, write=False)
        captures = []
        for name in diag.TARGETS:
            capture = copy.deepcopy(base); capture["expected_by_human"] = name
            for row in capture["rows"]:
                row["bitmaps"][0]["metrics"]["opaque_pixel_count"] = 8 if row["layer_name"] == name else 0
            captures.append(capture)
        result = comparison.compare(captures)
        self.assertEqual(len(result["bitmap_changes"]), 6)
        self.assertTrue(result["candidate_fields"])
        self.assertFalse(result["production_getter_verified"])


if __name__ == "__main__": unittest.main(verbosity=2)
