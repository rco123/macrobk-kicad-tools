"""Lifecycle regressions using real wx frames and instrumented owned sockets."""
import importlib
import importlib.util
import pathlib
import socket
import sys
import threading
import time
import types
import unittest
from unittest import mock
from test_worker_engine import core, ui, APP

lifecycle = importlib.import_module(core.__package__ + '.lifecycle')

class Socket:
    def __init__(self):
        self.closed = False
        self.close_count = 0
        self.options = []
    def setsockopt(self, *args): self.options.append(args)
    def bind(self, address): self.address = address
    def settimeout(self, timeout): self.timeout = timeout
    def recvfrom(self, count):
        time.sleep(.005)
        if self.closed: raise OSError('closed')
        raise socket.timeout()
    def close(self):
        self.closed = True
        self.close_count += 1

class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.service = core.get_service()
        self.service.shutdown()
        APP.Yield(True)
        self.service.accepting = True
        self.service.ui_module = None
        ui._manager_frame = None
        self.frame = __import__('wx').Frame(None, title='Fixture')
        self.frame.SetName('pcbframe')
        wx = __import__('wx')
        bar = wx.MenuBar(); bar.Append(wx.Menu(), 'Fixture'); self.frame.SetMenuBar(bar)
        self.sockets = []
        def factory(*args):
            obj = Socket(); self.sockets.append(obj); return obj
        self.socket_patch = mock.patch.object(core.socket, 'socket', side_effect=factory)
        self.hotkey_patch = mock.patch.object(core, 'start_hotkey_listener')
        self.frame_patch = mock.patch.object(core.kc, 'find_pcb_frame', return_value=self.frame)
        self.socket_patch.start(); self.hotkey_patch.start(); self.frame_patch.start()
        self.config_hash = pathlib.Path(core.CONFIG_PATH).read_bytes()
    def tearDown(self):
        self.service.shutdown(); APP.Yield(True)
        if bool(self.frame): self.frame.Destroy()
        APP.Yield(True)
        self.socket_patch.stop(); self.hotkey_patch.stop(); self.frame_patch.stop()
        self.assertEqual(pathlib.Path(core.CONFIG_PATH).read_bytes(), self.config_hash)
        self.service.accepting = True
        self.service.ui_module = None
        ui._manager_frame = None
    def start(self):
        return core.start_bridge()
    def test_start_once_and_five_times(self):
        service = self.start(); thread = service.thread
        for _ in range(5): self.assertIs(self.start(), service)
        self.assertEqual(len(self.sockets), 1)
        self.assertIs(service.thread, thread); self.assertTrue(thread.is_alive())
        self.assertIn((socket.SOL_SOCKET, socket.SO_REUSEADDR, 1), self.sockets[0].options)
        self.assertTrue(any(option[1] == socket.IP_ADD_MEMBERSHIP for option in self.sockets[0].options))
    def test_concurrent_start(self):
        barrier = threading.Barrier(8)
        def start(): barrier.wait(); self.start()
        callers = [threading.Thread(target=start) for _ in range(8)]
        for thread in callers: thread.start()
        for thread in callers: thread.join(2); self.assertFalse(thread.is_alive())
        APP.Yield(True)
        self.assertEqual(len(self.sockets), 1)
    def test_manager_close_open_keeps_listener(self):
        self.start(); thread = self.service.thread
        for _ in range(3):
            ui.show_manager(); manager = self.service.manager
            self.assertIs(manager.GetParent(), self.frame)
            manager.on_close(None); APP.Yield(True)
            self.assertIsNone(self.service.manager)
            self.assertTrue(self.service.started); self.assertIs(self.service.thread, thread)
        ui.show_manager()
        self.assertEqual(len(self.sockets), 1)
    def test_shutdown_idempotent_and_restart(self):
        self.start(); thread = self.service.thread; stop = self.service.stop_event
        for _ in range(4): self.service.shutdown()
        self.assertTrue(stop.is_set()); self.assertFalse(thread.is_alive())
        self.assertIsNone(self.service.socket); self.assertIsNone(self.service.thread)
        self.assertEqual(self.sockets[0].close_count, 1)
        self.start(); self.assertEqual(len(self.sockets), 2)
        self.assertIsNot(self.service.stop_event, stop)
    def test_reload_and_new_package_generation(self):
        self.start(); thread = self.service.thread
        workers, config = core._action_workers, core.CONFIG
        paths = core.CONFIG_PATH, core.LOG_PATH
        importlib.reload(core); importlib.reload(lifecycle)
        self.assertIs(self.start(), self.service)
        self.assertIs(core._action_workers, workers); self.assertIs(core.CONFIG, config)
        self.assertEqual((core.CONFIG_PATH, core.LOG_PATH), paths)
        package = types.ModuleType('macrobk_refresh_fixture')
        package.__path__ = [str(pathlib.Path(core.__file__).parent)]
        sys.modules[package.__name__] = package
        spec = importlib.util.spec_from_file_location(package.__name__ + '.trigger_core', core.__file__)
        new_core = importlib.util.module_from_spec(spec)
        new_core.CONFIG_PATH, new_core.LOG_PATH = core.CONFIG_PATH, core.LOG_PATH
        sys.modules[spec.name] = new_core
        spec.loader.exec_module(new_core)
        self.assertIs(new_core.start_bridge(), self.service)
        self.assertEqual(len(self.sockets), 1); self.assertIs(self.service.thread, thread)

    def test_kicad_dependency_removal_restores_live_modules(self):
        self.start(); ui.show_manager(); manager = self.service.manager
        self.service.remember_modules()
        original = dict(self.service.modules)
        for name in original:
            sys.modules.pop(name, None)
        refreshed = importlib.import_module(core.__package__ + '.lifecycle')
        refreshed.restore_modules(core.__package__)
        for name, module in original.items():
            self.assertIs(importlib.import_module(name), module)
        self.assertIs(core.start_bridge(), self.service)
        ui.show_manager()
        self.assertIs(self.service.manager, manager)
        self.assertEqual(len(self.sockets), 1)
    def test_pcb_destroy_stops_manager_workers_udp(self):
        self.start(); ui.show_manager(); manager = self.service.manager
        self.assertTrue(core.execute_python_script('wait_or_stop(10)', 'phone', 'shutdown-worker'))
        worker = core._action_workers['shutdown-worker']; thread = self.service.thread
        self.frame.Destroy(); APP.Yield(True)
        self.assertFalse(self.service.started); self.assertTrue(worker['stop_event'].is_set())
        self.assertFalse(thread.is_alive()); self.assertFalse(bool(manager))
        self.assertTrue(self.sockets[0].closed)
    def test_close_veto_keeps_service(self):
        wx = __import__('wx'); self.start()
        event = wx.CloseEvent(wx.wxEVT_CLOSE_WINDOW); event.SetEventObject(self.frame)
        self.service.on_frame_close(event)
        event.Veto()
        self.assertTrue(event.GetSkipped()); self.assertTrue(self.service.started)
        self.assertFalse(self.sockets[0].closed)
    def test_unrelated_resources_not_touched(self):
        wx = __import__('wx'); external = Socket(); frame = wx.Frame(None)
        callback = mock.Mock(); frame.Bind(wx.EVT_CLOSE, callback)
        self.start(); self.service.shutdown()
        self.assertFalse(external.closed); self.assertTrue(bool(frame)); callback.assert_not_called()
        frame.Destroy()
    def test_setup_failure_rolls_back(self):
        with mock.patch.object(Socket, 'bind', side_effect=OSError('fixture bind error')):
            with self.assertRaises(OSError): self.start()
        self.assertFalse(self.service.started); self.assertTrue(self.service.stop_event.is_set())
        self.assertIsNone(self.service.socket); self.assertIsNone(self.service.thread)
        self.assertTrue(self.sockets[0].closed)
        self.start(); self.assertEqual(len(self.sockets), 2)
    def test_thread_start_failure_rolls_back(self):
        with mock.patch.object(threading.Thread, 'start', side_effect=RuntimeError('fixture start error')):
            with self.assertRaises(RuntimeError): self.start()
        self.assertFalse(self.service.started); self.assertTrue(self.sockets[0].closed)
        self.assertIsNone(self.service.thread)
        self.start(); self.assertEqual(len(self.sockets), 2)
    def test_queued_gui_callback_cancelled_on_shutdown_and_restart(self):
        self.start(); observed = []
        caller = threading.Thread(target=lambda: core.call_gui_async(observed.append, 'stale'))
        caller.start(); caller.join()
        self.service.shutdown(); self.start(); APP.Yield(True)
        self.assertEqual(observed, [])
    def test_owned_callbacks_and_references_cleaned(self):
        self.start()
        timer = core.kc.call_later(10000, lambda: None)
        helpers = importlib.import_module(core.__package__ + '.gui_helpers')
        helpers._snapshot(self.frame)
        self.service.shutdown()
        self.assertFalse(timer.IsRunning()); self.assertFalse(core.kc._callbacks)
        self.assertFalse(helpers._references)
    def test_registration_reused(self):
        saved = lifecycle._registry.plugin
        lifecycle._registry.plugin = None
        try:
            plugin = mock.Mock(); factory = mock.Mock(return_value=plugin)
            for _ in range(5): self.assertIs(lifecycle.register_plugin(factory), plugin)
            factory.assert_called_once(); plugin.register.assert_called_once()
        finally: lifecycle._registry.plugin = saved

    def test_hotkey_owner_unregisters_only_its_id(self):
        self.start()
        registered = threading.Event()
        user32 = mock.Mock()
        user32.RegisterHotKey.side_effect = lambda *args: registered.set() or True
        user32.PeekMessageW.return_value = False
        with mock.patch.object(core.ctypes, 'WinDLL', return_value=user32):
            thread = threading.Thread(target=core.hotkey_worker,
                args=(core.parse_hotkey_description('Ctrl + F12'), core._hotkey_generation), daemon=True)
            core._hotkey_thread = thread
            thread.start()
            self.assertTrue(registered.wait(1))
            self.service.shutdown()
            self.assertFalse(thread.is_alive())
            user32.UnregisterHotKey.assert_called_once_with(None, core.HOTKEY_ID)
            self.assertIsNone(core._hotkey_thread)

    def test_shutdown_sleeping_worker_is_bounded(self):
        self.start()
        entered = threading.Event()
        # Native time.sleep is intentionally not interrupted by a forced kill.
        with mock.patch.object(core.time, 'sleep', wraps=time.sleep) as sleep:
            self.assertTrue(core.execute_python_script('import time\ntime.sleep(1.5)', 'phone', 'sleeper'))
            deadline = time.monotonic() + 1
            while mock.call(1.5) not in sleep.call_args_list and time.monotonic() < deadline:
                entered.wait(.005)
            self.assertIn(mock.call(1.5), sleep.call_args_list)
            worker = core._action_workers['sleeper']
            started = time.monotonic()
            self.service.shutdown()
            self.assertLess(time.monotonic() - started, 1.2)
            self.assertTrue(worker['stop_event'].is_set())
            worker['thread'].join(2)
            self.assertFalse(worker['thread'].is_alive())

    def test_frame_identification_uses_name_with_menubar(self):
        self.frame_patch.stop()
        try:
            self.assertIs(core.kc.find_pcb_frame(), self.frame)
            self.frame.SetName('unrelated')
            self.frame.SetTitle('PCB Editor')
            self.assertIsNone(core.kc.find_pcb_frame())
        finally:
            self.frame.SetName('pcbframe')
            self.frame_patch.start()

if __name__ == '__main__': unittest.main(verbosity=2)
