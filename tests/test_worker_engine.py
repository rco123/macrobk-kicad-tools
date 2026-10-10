"""Integration tests with KiCad's Python and real wx widgets, without installation.

Run from the plugin root: <KiCad>/bin/python.exe -B tests/test_worker_engine.py
The hidden test PCB frame is a fixture, not an actual KiCad board.
"""
import importlib
import importlib.util
import json
import copy
import pathlib
import socket
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest import mock

sys.dont_write_bytecode = True
PLUGIN = pathlib.Path(__file__).resolve().parents[1]
package = types.ModuleType("macrobk_integration")
package.__path__ = [str(PLUGIN)]
sys.modules[package.__name__] = package

try:
    import wx
    import pcbnew
except ImportError as exc:
    raise unittest.SkipTest("KiCad Python with wx and pcbnew is required: " + str(exc))

APP = wx.App(False)
# Seed file paths before loading the engine; fixtures never read/write user config.
_FIXTURE_DIRECTORY = tempfile.TemporaryDirectory(prefix="macrobk_tests_")
_FIXTURE_ROOT = pathlib.Path(_FIXTURE_DIRECTORY.name)
(_FIXTURE_ROOT / "config.json").write_text("{}", encoding="utf-8")
_spec = importlib.util.spec_from_file_location(package.__name__ + ".trigger_core", PLUGIN / "trigger_core.py")
core = importlib.util.module_from_spec(_spec)
core.CONFIG_PATH = str(_FIXTURE_ROOT / "config.json")
core.LOG_PATH = str(_FIXTURE_ROOT / "test.log")
sys.modules[_spec.name] = core
_spec.loader.exec_module(core)
core.bind_gui_thread()
ui = importlib.import_module(package.__name__ + ".ui_manager")
helpers = importlib.import_module(package.__name__ + ".gui_helpers")


class EngineTests(unittest.TestCase):
    def setUp(self):
        # Worker fixtures intentionally run without a background service.
        core.get_service().accepting = True
        # Never depend on, or rewrite, the installed user's selected Action.
        config = core._default_config_copy()
        config["actions"] = [{"id": "open-drc", "name": config["name"], "icon": "drc",
                              "trigger": copy.deepcopy(config["trigger"]),
                              "phone": copy.deepcopy(config["phone"]),
                              "action": copy.deepcopy(config["action"])}]
        config["selected_action_id"] = "open-drc"
        self.config_patch = mock.patch.object(core, "CONFIG", config)
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)
        self.manager = ui.MacroBKPluginManager(None)
        ui._manager_frame = self.manager
        self.frame = wx.Frame(None, title="Integration PCB Editor")
        panel = wx.Panel(self.frame)
        self.checks = {name: wx.CheckBox(panel, label=name) for name in
                       ["All items", "Locked items"] + core.kc.PCB_SELECTION_FILTER_ITEMS}
        for control in self.checks.values():
            control.SetValue(True)
        self.checks["Locked items"].SetValue(False)
        self.gui_id = threading.get_ident()
        self.menu_thread = None
        menu = wx.Menu()
        item = menu.Append(wx.ID_ANY, "Preferences")
        bar = wx.MenuBar()
        bar.Append(menu, "Preferences")
        self.frame.SetMenuBar(bar)
        self.frame.Bind(wx.EVT_MENU, self.menu_called, id=item.GetId())

    def menu_called(self, event):
        self.menu_thread = threading.get_ident()

    def tearDown(self):
        with core._action_workers_lock:
            for worker in core._action_workers.values():
                worker["stop_event"].set()
        self.pump_until(lambda: not core._action_workers, 7)
        ui._manager_frame = None
        self.manager.Destroy()
        self.frame.Destroy()
        APP.Yield(True)

    def pump_until(self, predicate, timeout=7):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            APP.Yield(True)
            if predicate():
                return
            time.sleep(0.005)
        self.fail("Timed out waiting for test condition")

    def start(self, script):
        self.manager.script_text.SetText(script)
        self.manager.on_test_run(None)
        self.assertEqual(self.manager.test_status_label.GetLabel(), "RUNNING")
        self.assertFalse(self.manager.test_button.IsEnabled())
        self.assertTrue(self.manager.stop_button.IsEnabled())

    def finish(self, expected="SUCCESS"):
        self.pump_until(lambda: self.manager.test_status_label.GetLabel() in
                        ("SUCCESS", "ERROR", "STOPPED"))
        self.assertEqual(self.manager.test_status_label.GetLabel(), expected, self.manager.result_text.GetText())
        self.assertTrue(self.manager.test_button.IsEnabled())
        self.assertFalse(self.manager.stop_button.IsEnabled())
        self.pump_until(lambda: not core._action_workers)

    def test_01_hello(self):
        self.start('print("HELLO")')
        self.finish()
        self.assertEqual(self.manager.result_text.GetText().strip(), "HELLO")

    def test_02_realtime_sleep(self):
        self.start('import time\nprint("A")\ntime.sleep(1)\nprint("B")')
        self.pump_until(lambda: "A" in self.manager.result_text.GetText())
        self.assertNotIn("B", self.manager.result_text.GetText())
        self.assertTrue(core.is_action_running("open-drc"))
        self.finish()
        self.assertEqual(self.manager.result_text.GetText().strip(), "A\nB")

    def test_03_long_sleep_stop(self):
        self.start('import time\nprint("START")\ntime.sleep(5)\nprint("END")')
        self.pump_until(lambda: "START" in self.manager.result_text.GetText())
        self.manager.on_stop_test(None)
        self.assertEqual(self.manager.test_status_label.GetLabel(), "STOPPING")
        # GUI event callbacks remain serviceable while the worker sleeps.
        observed = []
        wx.CallAfter(lambda: observed.append(threading.get_ident()))
        self.pump_until(lambda: bool(observed), 0.5)
        self.assertEqual(observed, [self.gui_id])
        self.finish("STOPPED")
        self.assertNotIn("END", self.manager.result_text.GetText())

    def test_04_wait_or_stop(self):
        self.start('print("WAIT")\nif wait_or_stop(10):\n    print("STOP REQUESTED")')
        self.pump_until(lambda: "WAIT" in self.manager.result_text.GetText())
        started = time.monotonic()
        self.manager.on_stop_test(None)
        self.finish("STOPPED")
        self.assertLess(time.monotonic() - started, 0.5)
        self.assertIn("STOP REQUESTED", self.manager.result_text.GetText())

    def test_05_duplicate_cross_source(self):
        self.start('wait_or_stop(3)')
        self.assertFalse(core.execute_python_script('print("SECOND")', "phone", "open-drc"))
        self.assertFalse(core.execute_python_script('print("SECOND")', "keyboard", "open-drc"))
        self.assertEqual(len(core._action_workers), 1)
        self.manager.on_stop_test(None)
        self.finish("STOPPED")

    def test_06_selection_filter(self):
        self.start('import time\npcb_select_filter("Tracks", False)\ntime.sleep(.5)\n'
                   'pcb_select_filter("Tracks", True)\ntime.sleep(.5)\n'
                   'pcb_select_filter("Pads", False)\ntime.sleep(.5)\npcb_select_filter("Pads", True)')
        self.pump_until(lambda: not self.checks["Tracks"].GetValue())
        self.pump_until(lambda: self.checks["Tracks"].GetValue())
        self.pump_until(lambda: not self.checks["Pads"].GetValue())
        self.finish()
        self.assertTrue(self.checks["Pads"].GetValue())

    def test_07_selection_read_all_items(self):
        self.start('pcb_select_filter("All items", False)\nprint(pcb_select_filter_state())')
        self.finish()
        self.assertFalse(self.checks["Locked items"].GetValue())
        self.assertIn("'Tracks': False", self.manager.result_text.GetText())

    def test_08_menu(self):
        self.start('print(open_menu("Preferences -> Preferences"))')
        self.finish()
        self.assertEqual(self.menu_thread, self.gui_id)
        self.assertIn("True", self.manager.result_text.GetText())

    def test_09_snapshots(self):
        self.start('items = list_controls()\nassert isinstance(items, list)\n'
                   'assert all(isinstance(item, dict) for item in items)\n'
                   'c = find_control_info(label="Tracks")\n'
                   'assert c["value"] is True\nset_control_value(c, False)\n'
                   'assert get_control_value(c) is False\nprint(c["label"])')
        self.finish()
        self.assertFalse(self.checks["Tracks"].GetValue())

    def test_10_runtime_error(self):
        self.start('raise RuntimeError("TEST ERROR")')
        self.finish("ERROR")
        self.assertIn("RuntimeError: TEST ERROR", self.manager.result_text.GetText())

    def test_11_base_exception(self):
        for error in ("SystemExit", "KeyboardInterrupt"):
            self.start('raise {}("TEST EXIT")'.format(error))
            self.finish("ERROR")
            self.assertIn(error, self.manager.result_text.GetText())

    def test_12_debug(self):
        self.start('DEBUG = True\nprint("USER")')
        self.finish()
        result = self.manager.result_text.GetText()
        self.assertIn("USER", result)
        self.assertIn("run_id=", result)
        self.assertIn("thread=", result)

    def test_13_stop_original_action(self):
        self.start('wait_or_stop(10)')
        self.manager.actions.append({"id": "action-B"})
        self.manager.selected_index = 1
        self.manager.on_stop_test(None)
        self.finish("STOPPED")

    def test_14_udp(self):
        previous_config = core.CONFIG
        previous_port = core.LOCAL_TRIGGER_PORT
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.bind(("", 0))
            port = probe.getsockname()[1]
        core.LOCAL_TRIGGER_PORT = port
        # Different selected Action and top-level trigger must not affect UDP matching.
        core.CONFIG = self.phone_config('print("UDP OK")')
        core._phone_status = "Starting"
        with mock.patch.object(core, "start_hotkey_listener"):
            service = core.start_bridge()
        receiver = service.thread
        try:
            self.pump_until(lambda: core.get_phone_status() == "Ready")
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sender:
                sender.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton("127.0.0.1"))
                sender.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 0)
                sender.sendto(("TRIGGER|" + core.trigger_id(core.CONFIG["actions"][0]["trigger"])).encode(),
                              (core.LOCAL_TRIGGER_GROUP, port))
            self.pump_until(lambda: "UDP OK" in self.manager.result_text.GetText())
            self.pump_until(lambda: not core._action_workers)
            self.assertNotIn("ACTION_B", self.manager.result_text.GetText())
        finally:
            service.shutdown()
            core.CONFIG = previous_config
            core.LOCAL_TRIGGER_PORT = previous_port
            self.assertFalse(receiver.is_alive())

    def test_cancelled_gui_callback_has_no_late_side_effect(self):
        self.start('pcb_select_filter("Tracks", False)')
        # Do not process GUI callbacks until Stop has released the worker.
        time.sleep(0.1)
        self.manager.on_stop_test(None)
        time.sleep(0.1)
        self.finish("STOPPED")
        self.assertTrue(self.checks["Tracks"].GetValue())

    def test_sync_timeout_and_late_callback(self):
        changes, errors = [], []
        def worker():
            try:
                core.call_gui_sync(lambda: changes.append(True), timeout=0.1)
            except TimeoutError:
                errors.append(True)
        thread = threading.Thread(target=worker)
        thread.start()
        thread.join(0.5)
        self.assertFalse(thread.is_alive())
        APP.ProcessPendingEvents()
        self.assertEqual(errors, [True])
        self.assertEqual(changes, [])

    def test_late_completion_is_ignored(self):
        self.manager.begin_test_run("open-drc", 100)
        self.manager.begin_test_run("open-drc", 101)
        self.manager.finish_test_run("open-drc", 100, "SUCCESS")
        self.assertEqual(self.manager.test_status_label.GetLabel(), "RUNNING")
        self.manager.finish_test_run("open-drc", 101, "SUCCESS")

    def test_thread_start_failure_clears_status(self):
        with mock.patch.object(threading.Thread, "start", side_effect=RuntimeError("start failed")):
            self.assertFalse(core.execute_python_script('print("unused")', "test", "open-drc"))
        self.finish("ERROR")
        self.assertIn("start failed", self.manager.result_text.GetText())

    def test_gui_sync_called_from_gui_never_waits(self):
        self.assertEqual(core.call_gui_sync(lambda: 42), 42)

    def test_snapshot_traversal_executes_only_on_gui(self):
        observed = []
        original = core.kc.get_control_info
        def inspect(control):
            observed.append(threading.get_ident())
            return original(control)
        with mock.patch.object(core.kc, "get_control_info", side_effect=inspect):
            self.start('print(len(iter_controls()))')
            self.finish()
        self.assertTrue(observed)
        self.assertEqual(set(observed), {self.gui_id})

    def test_hotkey_canonical_and_four_key_limit(self):
        trigger = core.parse_hotkey_description("Ctrl + Shift + A + B + C + D")
        self.assertEqual(core.trigger_id(trigger), "CTRL+SHIFT:A,B,C,D")
        with self.assertRaises(ValueError):
            core.parse_hotkey_description("A + B + C + D + E")
        thread = threading.Thread(target=core.hotkey_worker, args=(trigger, 0))
        thread.start()
        thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(core.get_keyboard_status(), "Phone Only")

    def test_key_picker_four_key_limit(self):
        from macrobk_integration.key_picker import TriggerKeyPickerDialog
        dialog = TriggerKeyPickerDialog(self.manager, "Ctrl + Shift + A + B + C + D")
        try:
            self.assertEqual(len(core.trigger_keys(dialog.get_trigger())), 4)
        finally:
            dialog.Destroy()

    def test_config_roundtrip_preserves_action_metadata(self):
        path = pathlib.Path(tempfile.mkdtemp(prefix="macrobk_config_test_")) / "config.json"
        original = copy.deepcopy(core.CONFIG)
        original["custom_metadata"] = {"keep": True}
        original["actions"][0]["custom_action_metadata"] = [1, 2, 3]
        path.write_text(json.dumps(original), encoding="utf-8")
        previous_path, previous_config = core.CONFIG_PATH, core.CONFIG
        try:
            core.CONFIG_PATH = str(path)
            core.CONFIG = core.load_config()
            core.save_config()
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["actions"], original["actions"])
            self.assertEqual(saved["custom_metadata"], original["custom_metadata"])
        finally:
            core.CONFIG_PATH, core.CONFIG = previous_path, previous_config

    def test_long_sleep_normal_success_keeps_gui_serviceable(self):
        self.start('import time\nprint("START")\ntime.sleep(5)\nprint("END")')
        observed = []
        wx.CallAfter(lambda: observed.append(True))
        self.pump_until(lambda: bool(observed), 0.5)
        self.assertEqual(self.manager.test_status_label.GetLabel(), "RUNNING")
        self.finish()
        self.assertIn("END", self.manager.result_text.GetText())

    def test_concurrent_duplicate_reserves_one_worker(self):
        barrier = threading.Barrier(8)
        accepted = []
        def dispatch():
            barrier.wait()
            accepted.append(core.execute_python_script('wait_or_stop(3)', "phone", "concurrent"))
        callers = [threading.Thread(target=dispatch) for _ in range(8)]
        for caller in callers:
            caller.start()
        for caller in callers:
            caller.join(1)
            self.assertFalse(caller.is_alive())
        self.assertEqual(accepted.count(True), 1)
        core.stop_action("concurrent")
        self.pump_until(lambda: not core._action_workers)

    def phone_config(self, script='print("ACTION_A")'):
        a = {"id": "phone-A", "name": "Action A",
             "trigger": core.parse_hotkey_description("Ctrl + Shift + F12"),
             "action": {"script": script}}
        b = {"id": "phone-B", "name": "Action B",
             "trigger": core.parse_hotkey_description("Ctrl + Alt + F12"),
             "action": {"script": 'print("ACTION_B")'}}
        return {"actions": [a, b], "selected_action_id": b["id"],
                "trigger": b["trigger"], "action": b["action"]}

    def test_phone_A_packet_parser(self):
        self.assertEqual(core.parse_phone_packet(b"TRIGGER|CTRL+SHIFT:F12"), "CTRL+SHIFT:F12")
        self.assertEqual(core.parse_phone_packet(b" \tTRIGGER| CTRL+SHIFT:F12\r\n"), "CTRL+SHIFT:F12")
        for packet in (b"OTHER|CTRL+SHIFT:F12", b"TRIGGER|", b"TRIGGER|\xff"):
            self.assertIsNone(core.parse_phone_packet(packet))

    def test_phone_B_canonicalization(self):
        self.assertEqual(core.trigger_id(core.parse_hotkey_description("Ctrl + Shift + F12")),
                         "CTRL+SHIFT:F12")
        # Studio makeTriggerId sorts both sets alphabetically, including ALT before CTRL.
        self.assertEqual(core.trigger_id(core.parse_hotkey_description("Win + Shift + Ctrl + Alt + B + A")),
                         "ALT+CTRL+SHIFT+WIN:A,B")

    def test_phone_C_selected_B_executes_A(self):
        with mock.patch.object(core, "CONFIG", self.phone_config()):
            with mock.patch.object(core, "execute_python_script", wraps=core.execute_python_script) as execute:
                self.assertTrue(core.handle_phone_trigger("CTRL+SHIFT:F12"))
                execute.assert_called_once_with('print("ACTION_A")', source="phone", action_id="phone-A")
                self.pump_until(lambda: "ACTION_A" in self.manager.result_text.GetText())
                self.pump_until(lambda: not core._action_workers)
            self.assertNotIn("ACTION_B", self.manager.result_text.GetText())

    def test_phone_D_no_match(self):
        with mock.patch.object(core, "CONFIG", self.phone_config()):
            with mock.patch.object(core, "execute_python_script", wraps=core.execute_python_script) as execute:
                self.assertFalse(core.handle_phone_trigger("ALT+F9"))
                execute.assert_not_called()
        self.assertIn("PHONE no matching action trigger=ALT+F9",
                      pathlib.Path(core.LOG_PATH).read_text(encoding="utf-8"))

    def test_phone_E_multi_key(self):
        config = self.phone_config()
        config["actions"][0]["trigger"] = core.parse_hotkey_description("Ctrl + Shift + D + C + B + A")
        with mock.patch.object(core, "CONFIG", config):
            self.assertEqual(core.find_action_by_trigger("CTRL+SHIFT:A,B,C,D")["id"], "phone-A")

    def test_phone_duplicate_policy_and_disabled_actions(self):
        config = self.phone_config()
        duplicate = copy.deepcopy(config["actions"][0])
        duplicate["id"] = "duplicate"
        config["actions"].append(duplicate)
        with mock.patch.object(core, "CONFIG", config):
            self.assertEqual(core.find_action_by_trigger("CTRL+SHIFT:F12")["id"], "phone-A")
            config["actions"][0]["trigger"]["enabled"] = False
            self.assertEqual(core.find_action_by_trigger("CTRL+SHIFT:F12")["id"], "duplicate")

    def test_phone_worker_duplicate_and_stop(self):
        script = 'print("PHONE_TEST")\nif wait_or_stop(10):\n    print("PHONE_STOP")'
        with mock.patch.object(core, "CONFIG", self.phone_config(script)):
            self.assertTrue(core.handle_phone_trigger("CTRL+SHIFT:F12"))
            self.pump_until(lambda: "PHONE_TEST" in self.manager.result_text.GetText())
            self.assertEqual(core._action_workers["phone-A"]["source"], "phone")
            self.assertFalse(core.handle_phone_trigger("CTRL+SHIFT:F12"))
            self.assertEqual(len(core._action_workers), 1)
            self.assertTrue(core.stop_action("phone-A"))
            self.pump_until(lambda: not core._action_workers)
            self.pump_until(lambda: "PHONE_STOP" in self.manager.result_text.GetText())
        self.assertIn("STOPPED source=phone action=phone-A", pathlib.Path(core.LOG_PATH).read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
