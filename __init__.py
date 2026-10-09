from .bridge import MacroBKDRCBridge, start_bridge


# Keep plugin registration exactly at package import time, like the original
# working single-file version. Heavy split modules are loaded lazily.
_plugin = MacroBKDRCBridge()
_plugin.register()

# Background services are non-fatal. Even if one split module has a problem,
# the External Plugins menu entry remains registered so the error can be shown.
start_bridge()
