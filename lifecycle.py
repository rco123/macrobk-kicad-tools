"""Own only MacroBK PCB resources, independently of import generations."""
import atexit
import sys
import threading
import time
import types
import uuid

# An interpreter-local anchor, shared by package aliases and importlib.reload.
# No OS lock, port scan, process termination, or other application's resources.
_KEY = "_macrobk_kicad_pcb_service_v1"
_candidate = types.ModuleType(_KEY)
_candidate.lock = threading.RLock()
_candidate.service = None
_candidate.plugin = None
_registry = sys.modules.setdefault(_KEY, _candidate)


def get_service(core=None):
    with _registry.lock:
        if _registry.service is None:
            if core is None:
                return None
            _registry.service = MacroBKService(core)
        _registry.service.remember_modules()
        return _registry.service


def restore_modules(package):
    """KiCad LoadPluginModule removes package dependencies before reimport."""
    with _registry.lock:
        service = _registry.service
        if service is not None and service.core.__package__ == package:
            for name, module in service.modules.items():
                sys.modules[name] = module


def engine(default):
    service = get_service()
    return service.core if service is not None else default


def register_plugin(factory):
    with _registry.lock:
        if _registry.plugin is None:
            plugin = factory()
            plugin.register()
            _registry.plugin = plugin
        return _registry.plugin


class MacroBKService:
    def __init__(self, core):
        self.core = core
        self.modules = {}
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.socket = None
        self.thread = None
        self.started = False
        self.shutting_down = False
        self.accepting = True
        self.epoch = 0
        self.id = uuid.uuid4().hex[:12]
        self.manager = None
        self.frame = None
        self.frame_id = None
        self.discovery_timer = None
        self.ui_module = None
        self.gui_cleanup_pending = False
        atexit.register(self.shutdown)

    def remember_modules(self):
        for suffix in ("bridge", "trigger_core", "kicad_controls", "gui_helpers",
                       "ui_manager", "key_picker", "lifecycle"):
            name = self.core.__package__ + "." + suffix
            module = sys.modules.get(name)
            if module is not None:
                self.modules.setdefault(name, module)

    def log(self, message):
        self.core.log("{} service={} epoch={} thread={}".format(
            message, self.id, self.epoch, threading.get_ident()))

    def start(self):
        with self.lock:
            if self.shutting_down:
                return self
            if self.gui_cleanup_pending:
                raise RuntimeError("MacroBK GUI cleanup is still pending")
            if self.started:
                self.log("SERVICE ALREADY RUNNING")
                return self
            # A bounded shutdown may leave a sleeping worker/thread. Never
            # overlap a new listener/hotkey generation with surviving resources.
            if self.thread is not None and self.thread.is_alive():
                raise RuntimeError("Previous MacroBK UDP listener is still stopping")
            hotkey = self.core._hotkey_thread
            if hotkey is not None and hotkey.is_alive():
                raise RuntimeError("Previous MacroBK hotkey is still stopping")
            self.stop_event = threading.Event()
            self.core._service_stop = self.stop_event
            self.epoch += 1
            self.accepting = True
            sock = None
            try:
                socket = self.core.socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                self.log("UDP SOCKET CREATED")
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("", self.core.LOCAL_TRIGGER_PORT))
                membership = socket.inet_aton(self.core.LOCAL_TRIGGER_GROUP) + socket.inet_aton(
                    self.core.LOCAL_TRIGGER_INTERFACE)
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
                sock.settimeout(0.5)
                self.socket = sock
                self.thread = threading.Thread(target=self.core.udp_worker,
                    args=(self, sock, self.stop_event, self.epoch),
                    name="MacroBK-KiCad-DRC-UDP", daemon=True)
                self.started = True
                self.thread.start()
            except BaseException:
                self.stop_event.set()
                if sock is not None:
                    sock.close()
                self.socket = None
                self.thread = None
                self.started = False
                self.accepting = False
                self.core._started = False
                raise
            self.core._started = True
            self.log("SERVICE START")
            try:
                self.core.start_hotkey_listener()
            except Exception as exc:
                self.log("hotkey listener start error: " + repr(exc))
            self.core.call_gui_async(self.attach_frame)
            return self

    def attach_frame(self):
        import wx
        if not self.started or self.shutting_down:
            return
        if self.discovery_timer is not None:
            self.discovery_timer.Stop()
            self.discovery_timer = None
        if self.frame is not None and bool(self.frame) and not self.frame.IsBeingDeleted():
            return
        frame = self.core.kc.find_pcb_frame()
        if frame is None:
            self.discovery_timer = wx.CallLater(500, self.attach_frame)
            return
        self.discovery_timer = None
        self.frame = frame
        self.frame_id = frame.GetId()
        frame.Bind(wx.EVT_CLOSE, self.on_frame_close)
        frame.Bind(wx.EVT_WINDOW_DESTROY, self.on_frame_destroy)
        self.log("PCB FRAME ATTACHED name={!r} class={!r}".format(
            frame.GetName(), frame.GetClassInfo().GetClassName()))

    def on_frame_close(self, event):
        # KiCad can veto Close during its save prompt. Destruction is the
        # confirmation that Close succeeded; never shut down on a vetoed close.
        self.log("PCB FRAME CLOSE DETECTED")
        event.Skip()

    def on_frame_destroy(self, event):
        # wx may invalidate the original Python wrapper before the destroy
        # event and supply a different wrapper. Capture the native ID at bind.
        if event.GetId() == self.frame_id:
            self.log("PCB FRAME DESTROY DETECTED")
            self.shutdown()
        event.Skip()

    def shutdown(self):
        with self.lock:
            if self.shutting_down or (not self.started and not self.accepting):
                return
            self.shutting_down = True
            self.accepting = False
            self.epoch += 1
            self.stop_event.set()
            sock, thread = self.socket, self.thread
        self.log("SERVICE SHUTDOWN START")
        def cleanup(label, function):
            try:
                function()
            except Exception as exc:
                self.log("{} cleanup error: {}".format(label, repr(exc)))
        # Every cleanup is isolated so one deleted wx wrapper cannot prevent
        # socket/hotkey cleanup. GUI cleanup must run on the wx thread.
        def gui_cleanup():
            import wx
            manager, self.manager = self.manager, None
            if manager is not None and bool(manager):
                cleanup("Manager", manager.dispose)
            if self.ui_module is not None:
                self.ui_module._manager_frame = None
            if self.discovery_timer is not None:
                cleanup("Discovery timer", self.discovery_timer.Stop)
                self.discovery_timer = None
            frame, self.frame = self.frame, None
            self.frame_id = None
            if frame is not None and bool(frame):
                cleanup("Close binding", lambda: frame.Unbind(wx.EVT_CLOSE, handler=self.on_frame_close))
                cleanup("Destroy binding", lambda: frame.Unbind(wx.EVT_WINDOW_DESTROY, handler=self.on_frame_destroy))
            cleanup("Helper timers", self.core.kc.cancel_callbacks)
            helpers = sys.modules.get(self.core.__package__ + ".gui_helpers")
            if helpers is not None:
                helpers._references.clear()
            self.gui_cleanup_pending = False
        try:
            import wx
            if wx.IsMainThread():
                gui_cleanup()
            elif wx.GetApp() is not None:
                self.gui_cleanup_pending = True
                wx.CallAfter(gui_cleanup)
        except Exception as exc:
            self.log("GUI cleanup error: " + repr(exc))
        try:
            with self.core._action_workers_lock:
                workers = list(self.core._action_workers.values())
                for worker in workers:
                    worker["stop_event"].set()
            self.log("WORKERS STOP REQUESTED count={}".format(len(workers)))
            deadline = time.monotonic() + 0.5
            for worker in workers:
                worker_thread = worker["thread"]
                if worker_thread is not threading.current_thread() and worker_thread.is_alive():
                    worker_thread.join(max(0, deadline - time.monotonic()))
            if sock is not None:
                cleanup("UDP socket", sock.close)
                self.log("UDP SOCKET CLOSED")
            if thread is not None and thread is not threading.current_thread() and thread.is_alive():
                cleanup("UDP thread", lambda: thread.join(1.0))
            cleanup("Hotkey", self.core.stop_hotkey_listener)
        finally:
            with self.lock:
                self.socket = None
                # Keep a surviving thread reference to prevent duplicate start.
                self.thread = thread if thread is not None and thread.is_alive() else None
                self.started = False
                self.core._started = False
                self.shutting_down = False
            self.log("SERVICE SHUTDOWN COMPLETE")
