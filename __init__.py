import pcbnew

from .bridge import MacroBKDRCBridge, start_bridge


_plugin = MacroBKDRCBridge()
_plugin.register()
start_bridge()
