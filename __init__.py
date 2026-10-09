from .lifecycle import restore_modules

# KiCad Refresh deletes package dependencies. Restore the live generation
# before importing the bridge so workers, helpers and Manager keep ownership.
restore_modules(__name__)

from .bridge import MacroBKDRCBridge, start_bridge


# Keep plugin registration exactly at package import time, like the original
# working single-file version. Heavy split modules are loaded lazily.
from .lifecycle import register_plugin

_plugin = register_plugin(MacroBKDRCBridge)

# Background services are non-fatal. Even if one split module has a problem,
# the External Plugins menu entry remains registered so the error can be shown.
start_bridge()
