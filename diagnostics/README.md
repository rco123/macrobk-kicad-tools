# 활성 레이어 진단 — 2026-10-10

현재는 조사 단계입니다. pcb_get_selected_layer()를 구현하지 않았으며,
기존 layer 선택/visibility/UP/DOWN/Worker/UDP/Manager/lifecycle 파일을 수정하지 않습니다.

실제 PCB Editor의 Tools → Scripting Console에서 실행하세요.
별도 python.exe는 현재 PCB Editor의 wx 객체에 접근할 수 없습니다.

```python
import sys
sys.path.insert(0, r'C:\Users\sgkim\Documents\KiCad\9.0\scripting\plugins\macrobk_drc_bridge')
import layer_diagnostics as ld
ld.show_diagnostic_panel()
```

콘솔이 GUI thread에서 실행되는 환경에 맞는 호출입니다.
MacroBK Action Worker에서 실행할 경우 GUI 동기 호출을 사용하세요.
새 helper는 별도 파일이므로 Refresh Plugins/reload 없이 import할 수 있습니다.
생산 모듈을 reload하지 마세요.

```python
import sys
sys.path.insert(0, r'C:\Users\sgkim\Documents\KiCad\9.0\scripting\plugins\macrobk_drc_bridge')
import layer_diagnostics as ld
from macrobk_drc_bridge import trigger_core
trigger_core.call_gui_sync(ld.show_diagnostic_panel)
```

기존 Action 설정을 변경/저장하지 마세요. 이미 실행 가능한 임시 테스트 환경이
없으면 위 Scripting Console 방식을 사용하세요.

1. PCB Appearance > Layers에서 F.Cu를 마우스로 선택합니다.
2. 진단 창의 Capture F.Cu를 누릅니다.
3. B.Cu, F.Adhesive, Edge.Cuts도 같은 방식으로 각각 Capture합니다.
4. 같은 순서를 반복하고 canvas/다른 컨트롤을 클릭해 focus가 바뀐 뒤에도 Capture합니다.
5. MacroBK Manager를 열고 닫은 뒤 반복합니다. 진단 창은 Manager와 독립적입니다.
6. 보드를 안전하게 다시 열었을 때도 같은 절차를 반복합니다.

Capture 버튼은 레이어를 바꾸지 않습니다. expected_by_human은 사용자가 화면에서
관찰한 레이어 이름이며 알고리즘의 판정값이 아닙니다. 진단 창 버튼을 클릭하면
focus가 바뀌므로 focus와 active layer를 분리해서 비교할 수 있습니다.

JSON은 이 작업 루트의 diagnostics/evidence/에 저장합니다.
실제 값만 출력하며 unavailable/error/NOT READ를 명시합니다.

- 전체 Frame dir 및 요청 API 존재 여부/가능한 getter 반환값
- pcbnew Layer/Active/Current/Cu/Board 목록과 현재 board의 관련 멤버
- 레이어 label/row/parent/grandparent/sibling, Python ref/ HWND, native wx class
- 배경/전경, enabled/visible/focus, style/tooltip/name/label
- row의 모든 child tree와 각 StaticBitmap의 dimensions/alpha/mask/checksum
- GetValue/GetSelection/GetCurrentSelection 가능 여부 및 오류
- accessible state/role/name이 제공될 경우 값
- event handler 객체 존재 여부 (개별 C++ binding 목록은 public wx에 미노출)
- client data의 API 존재 여부 (타입 불명의 native C++ pointer는 읽지 않음)

비교는 C: 작업 루트에서 실행합니다. 실제 JSON 네 개의 경로를 지정하세요.

```powershell
& 'C:\Program Files\KiCad\9.0\bin\python.exe' -B diagnostics/compare_layer_dumps.py <F.Cu.json> <B.Cu.json> <F.Adhesive.json> <Edge.Cuts.json>
```

comparison.json의 bitmap_changes는 선택 변경 시 실제로 달라진 값을 보여 줍니다.
candidate_fields는 모든 관찰에서 선택 row 하나만 구별한 bitmap 경로/필드의
후보이며, production_getter_verified는 아직 False입니다. 비교만으로 검증이
완료됐다고 판단하지 않습니다. DPI/theme, visibility 변경, 반복/focus/Manager/
reopen에서 재현성 및 ambiguous 상태의 실패 동작까지 확인해야 합니다.

직접 캡처를 호출할 수도 있습니다.

```python
ld.dump_layer_selection_state(expected='F.Cu', tag='mouse_F.Cu_repeat1')
```

expected만 바꿔 같은 상태를 반복 캡처해도 bitmap 값은 변하지 않아야 합니다.
이것은 helper가 관찰값을 만들거나 MacroBK cache에 의존하지 않는지 검사합니다.
