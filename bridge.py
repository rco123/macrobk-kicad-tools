import traceback

import pcbnew


def _show_load_error(title, exc):
    message = "{}\n\n{}".format(exc, traceback.format_exc())
    try:
        import wx
        wx.MessageBox(
            message,
            title,
            wx.OK | wx.ICON_ERROR,
        )
    except Exception:
        try:
            print("[MacroBK] {}: {}".format(title, message))
        except Exception:
            pass


def start_bridge():
    """Start background trigger services without preventing plugin registration."""
    try:
        from . import trigger_core
    except Exception:
        try:
            import trigger_core
        except Exception as exc:
            _show_load_error("MacroBK trigger_core load error", exc)
            return False

    try:
        # Bind at the plugin GUI entry point. Do not reload live worker/service
        # modules: restarting PCB Editor applies a new source generation.
        from .lifecycle import engine
        trigger_core = engine(trigger_core)
        trigger_core.bind_gui_thread()
        return trigger_core.start_bridge()
    except Exception as exc:
        _show_load_error("MacroBK start error", exc)
        return False


def show_manager():
    """Load the GUI only when the user actually runs the plugin."""
    try:
        from .ui_manager import show_manager as _show_manager
    except Exception:
        try:
            from ui_manager import show_manager as _show_manager
        except Exception as exc:
            _show_load_error("MacroBK ui_manager load error", exc)
            return False

    try:
        # Keep the existing engine/Manager generation together. Apply source
        # updates by restarting PCB Editor rather than reloading live workers.
        _show_manager()
        return True
    except Exception as exc:
        _show_load_error("MacroBK KiCAD Tools error", exc)
        return False


class MacroBKDRCBridge(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "MacroBK KiCAD Tools"
        self.category = "MacroBK"
        self.description = "PCB design and automation tools for KiCad"
        self.show_toolbar_button = False

    def Run(self):
        show_manager()
