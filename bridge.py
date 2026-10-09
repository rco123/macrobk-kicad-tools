import importlib
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
        # KiCad's "Refresh Plugins" does not reliably remove already imported
        # Python modules from sys.modules. Reload this split module explicitly
        # so a replaced trigger_core.py is actually read from disk.
        trigger_core = importlib.reload(trigger_core)
        trigger_core.start_bridge()
        return True
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
        # Reload the split UI module for the same reason as trigger_core above.
        # This is useful while iterating with KiCad's Refresh Plugins command.
        try:
            if _show_manager.__module__.startswith("macrobk_drc_bridge."):
                module = importlib.import_module(_show_manager.__module__)
                module = importlib.reload(module)
                _show_manager = module.show_manager
        except Exception:
            pass

        _show_manager()
        return True
    except Exception as exc:
        _show_load_error("MacroBK Plugin Manager error", exc)
        return False


class MacroBKDRCBridge(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "MacroBK Plugin Manager"
        self.category = "MacroBK"
        self.description = "Configure and test the MacroBK KiCad trigger"
        self.show_toolbar_button = False

    def Run(self):
        show_manager()
