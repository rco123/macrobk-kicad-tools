import json
from pathlib import Path
import pcbnew
import wx
methods=['GetActiveLayer','SetActiveLayer','GetCanvas','GetToolManager','GetBoard','GetScreen','GetAppearancePanel','GetLayerManager','GetLayerSelector','GetLayerPair','GetCurrentLayer']
result={'scope':'KiCad bundled Python subprocess; NOT the running PCB Editor interpreter', 'kicad_version':pcbnew.GetBuildVersion(),'wx_version':wx.version(), 'pcbnew_members':[n for n in dir(pcbnew) if any(t in n.lower() for t in ['layer','active','current','cu','board'])], 'wx_frame_base_api':{n:hasattr(wx.Frame,n) for n in methods}, 'wx_static_text_state_members':[n for n in dir(wx.StaticText) if any(t in n.lower() for t in ['select','current','active','indicator','client','accessib'])], 'wx_static_bitmap_state_members':[n for n in dir(wx.StaticBitmap) if any(t in n.lower() for t in ['select','current','active','indicator','client','accessib'])], 'board_type_layer_members':[n for n in dir(pcbnew.BOARD) if any(t in n.lower() for t in ['layer','active','current'])]}
Path('diagnostics/evidence/python_api_probe.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(result['scope']); print(result['kicad_version']); print(result['wx_frame_base_api']); print(result['board_type_layer_members'])
