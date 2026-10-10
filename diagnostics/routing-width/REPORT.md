# pcb_set_routing_track_width 조사 결과 — 2026-10-10

작업 루트는 `C:\Users\sgkim\Documents\KiCad\9.0\scripting\plugins\macrobk_drc_bridge`이다. E: 작업·수정·Git 작업은 수행하지 않았다. 설치된 KiCad 9.0.9의 Python API와 공식 소스 tag 9.0.9를 사용했다. **조사와 detached BOARD 실험은 완료했으나 live routing acceptance는 미완료이며, production 수정은 하지 않았다.**

## 1. 현재 함수 흐름과 호출 위치

`kicad_controls.py`의 현재 행 번호:

| 행 | 실제 처리 |
|---|---|
| 1128–1138 | 함수 및 설명: 새 routing 시작 전 사용, 기존 track 변경 없음 |
| 1141 | pcbnew import |
| 1145 | `_pcb_board()`로 현재 board 취득 |
| 1146 | `_pcb_width_mm_to_iu()`로 입력 검증·FromMM 변환 |
| 1149 | `board.GetDesignSettings()` |
| 1153–1163 | custom setter/getter/mode API 존재 검증 |
| 1167–1170 | 현재 via diameter/drill 조회, 실패 시 둘 다 None |
| 1174–1177 | 사용 가능한 setter로 현재 via 값을 custom slot에 복사 |
| 1179 | `SetCustomTrackWidth(width_iu)` |
| 1180 | `UseCustomTrackViaSize(True)` |
| 1181–1189 | `GetCurrentTrackWidth()` 값 일치 검증 |
| 1192–1194 | 사용 가능하면 `pcbnew.UpdateUserInterface()` |
| 1195–1197 | 사용 가능하면 `pcbnew.Refresh()` |
| 1198 | `_process_pending_gui_events()` → wx app의 ProcessPendingEvents |
| 1201–1203 | ToMM 반환, 변환 실패 시 요청값 반환 |

SetTrackWidthIndex, frame.Update/Refresh, tool/action dispatch는 호출하지 않는다. 현재 getter 검증은 design settings 검증이며 active router head 검증이 아니다. `gui_helpers.py`의 기존 GUI 동기 wrapper 경로는 변경하지 않았다.

## 2. KiCad native 흐름

Custom Track/Via Size: `DIALOG_TRACK_VIA_SIZE::TransferDataFromWindow`에서 custom track/via 값을 기록 → `ROUTER_TOOL::CustomTrackWidthDialog`에서 `m_TempOverrideTrackWidth=true`, `UseCustomTrackViaSize(true)` → `onTrackViaSizeChanged(dummy)` 직접 호출.

Preset toolbar: wx EVT_CHOICE → `Tracks_and_Vias_Size_Event` → `SetTrackWidthIndex` 및 temporary override → Windows canvas focus 복귀 → `TOOL_MANAGER::RunAction(PCB_ACTIONS::trackViaSizeChanged)`.

Router context menu: custom mode 해제/override/index 변경 후 `trackViaSizeChanged.MakeEvent()` 반환. Width cycling: `BOARD_EDITOR_CONTROL::TrackWidthInc/Dec`에서 index 변경, custom mode false, RunAction. 선택 track이 있고 tool stack이 비어 있는 경우에는 선택 항목 편집 분기가 있으므로 routing 중 cycling과 구분해야 한다.

현재 사용자 `user.hotkeys`를 확인했다. `pcbnew.InteractiveRouter.CustomTrackViaSize=Q`, `trackWidthInc=W`, `trackWidthDec=Shift+W`, `trackViaSizeChanged` 자체는 할당 없음. 문자 키를 내부 action 호출로 간주하거나 최종 해결책에 사용하지 않았다. Custom 유지 동작은 custom dialog 경로이며 preset cycling은 custom mode를 해제한다.

## 3. 비교

| 단계 | Native custom change | 현재 MacroBK | 차이 |
|---|---|---|---|
| custom 폭 | dialog setter | setter | 같은 설정값 계층 |
| custom mode | true | true | 일치 |
| 연결 track 폭 override | temporary override=true | 설정 없음 | 기존 track 폭 상속이 우선할 수 있음 |
| router 통보 | onTrackViaSizeChanged | 없음 | 핵심 누락 |
| head 재계산 | ImportSizes → UpdateSizes → Move | 없음 | getter 성공만으로 preview 변경 보장 불가 |
| UI | handler/일반 update UI | 전체 UpdateUserInterface | 범위 다름 |
| Refresh | custom handler에는 없음 | 전체 view 재구성 | 불필요한 view 삭제 발생 |
| state 유지 | 같은 router/placer 사용 | view 초기화+REDRAW reset | 동등하지 않음; live 미검증 |
| 다음 route | 시작 시 ImportSizes | 설정값은 유지 | 연결 track 상속·board minimum 등 조건에 영향받음 |
| preset 추가 | 없음 | 없음 | detached 실험에서도 목록 유지 |

## 4. routing preview 소실 원인

확인된 source 경로: `pcbnew.Refresh → PCB_EDIT_FRAME::RebuildAndRefresh → view.Clear → InitPreview → DisplayBoard → ResetTools(REDRAW) → canvas.Refresh`.

폭 설정에 필요 없는 전체 view 삭제와 preview 재초기화가 실제로 들어 있다. native handler의 재계산 경로는 빠져 있다. 따라서 preview 소실을 설명하는 구체적 소스 근거는 확보했다. **현재 사용자 세션에서 D 단독 호출로 재현하지 못했으므로 실제 증상의 확정된 단일 원인이라고 주장하지 않는다.**

중요한 반증: `TOOL_MANAGER::ResetTools`는 REDRAW에서 DeactivateTool을 하지 않는다. `ROUTER_TOOL::Reset`도 REDRAW에서 PNS::TOOL_BASE::Reset을 호출하지 않는다(RUN에서만 호출). 따라서 “Refresh가 router 객체를 삭제한다” 또는 “반드시 route를 cancel한다”는 설명은 9.0.9 source와 맞지 않는다.

## 5–6. X 실패와 focus 구분

X 실패 원인은 미확정. Manager 클릭으로 canvas focus가 떠나는 경우와 route 내부 상태 이상을 분리해야 한다. Native toolbar 자체도 Windows에서 폭 선택 후 `GetCanvas()->SetFocus()`를 명시적으로 호출한다. 기존 MacroBK 함수는 이를 하지 않는다. 이것만으로 Manager/X 문제를 확정할 수 없으며 Phone 경로에서도 같은 현상인지 실험해야 한다.

현재 열린 PCB Editor 접근성 텍스트에는 `Route Single Track`, blank width/via combo가 표시되었다. 이는 preview·width·focus 정상 여부를 입증하지 않는다. 화면 캡처는 fresh 창으로 재시도했으나 `FrameArrived timed out`, `window capture timed out`으로 실패했다. 확인되지 않은 화면 좌표나 입력을 사용하지 않았다. 현재 board는 이미 unsaved 상태여서 board 파일 저장도 하지 않았다.

## 7–8. Refresh / UpdateUserInterface / wx

Refresh는 위의 view 재구성 경로이며 단순 wx Refresh와 다르다. `UpdateUserInterface`는 BuildConnectivity, layer box, layer visibility 및 appearance/net-inspector 업데이트를 한다. 그 함수 내부에는 ResetTools 또는 trackViaSizeChanged dispatch가 없다. 인접한 BoardSetup 함수의 MODEL_RELOAD를 UpdateUserInterface의 동작으로 혼동하면 안 된다. UI update만으로 active router 폭을 재import하지 않는다.

frame.Update는 일반 wx의 paint 처리, frame.Refresh는 repaint 요청이다. Python에서 취득한 wx frame이 C++ PCB_EDIT_FRAME의 TOOL_MANAGER 접근을 제공한다는 뜻은 아니다. 둘의 실제 routing 영향은 NOT TESTED. `ProcessPendingEvents`는 queued event 처리이며 router 폭 변경 통보 대체가 아니다. 중첩 event 처리 가능성은 있으나 이번 증상 원인으로 검증되지 않았다.

Custom 상태 toolbar 공백은 `OnUpdateSelectTrackWidth`가 custom mode일 때 selection을 `wxNOT_FOUND`로 설정하는 native source 동작이다. 수치 설정 실패의 증거가 아니며 native custom 경로도 같은 조건을 가진다.

## 9. trackViaSizeChanged 역할

발생자: toolbar frame handler, BOARD_EDITOR_CONTROL의 width/via cycling, router/context 메뉴. Custom dialog는 같은 router handler를 직접 호출한다.

수신자: ROUTER_TOOL의 transition 등록 `Go(&ROUTER_TOOL::onTrackViaSizeChanged, PCB_ACTIONS::trackViaSizeChanged.MakeEvent())`.

handler는 기존 router Sizes 복사 → 현재 net이 있으면 ImportSizes → UpdateSizes → updateEndItem → 같은 목적지로 Move → message panel update. PNS::ROUTER::UpdateSizes는 ROUTE_TRACK일 때 기존 placer의 UpdateSizes를 호출한다. 현재 router 객체를 다시 만들거나 이미 확정한 board track 폭을 전부 편집하지 않는다. DRAWING_TOOL 소스의 via 메뉴에도 해당 event를 반환하는 경로가 있지만 track router handler의 대체 함수로 사용할 수는 없다.

ImportSizes는 connected-track inheritance가 켜져 있고 temporary override가 없으면 기존 track 폭을 먼저 상속한다. custom mode만 켠다고 언제나 현재/다음 route가 요청 폭이라는 보장은 없다. Custom native 경로의 temporary override와 현재 Python getter 검증은 서로 다른 역할이다.

## 10. Python 가능 범위와 대안

설치된 `pcbnew`에서 실제 hasattr 검사 결과: TOOL_MANAGER, PCB_ACTIONS, ROUTER_TOOL, TOOL_EVENT, GetToolManager, RunAction, GetPcbEditFrame은 모두 False. SWIG pcbnew.i도 native tool dispatch API를 제공하지 않는다. Settings setter/getter, UpdateUserInterface, Refresh는 제공한다. 결과는 `detached_results.json`에 저장했다. 이 검사는 pcbnew SWIG 모듈 범위이며 다른 모든 Python 연동 방식을 부정하는 검사는 아니다.

wx event 대체는 기술적으로 command event를 보내는 실험이 가능하지만 바로 안전한 해결책이 되지 않는다. toolbar는 EVT_COMBOBOX가 아닌 EVT_CHOICE이며 실제 control id와 타입을 확인해야 한다. 정상 preset 선택 callback은 SetTrackWidthIndex를 실행해 custom mode를 해제한다. blank custom selection=-1을 그 callback에 보내는 방법은 unsigned index 변환 위험이 있다. 사용하지 않는 menu id/하드코딩한 internal id/ABI 포인터로 action을 우회하는 방법도 채택하지 않았다.

가장 안전한 현재 대안은 native Custom Track/Via Size 기능을 직접 사용하여 native handler를 타는 것이다. 자동화를 위해서는 tool action dispatch를 노출하는 검증된 KiCad binding/확장이 필요하다. 별도 GUI event 실험을 검증한 뒤에만 대안으로 평가할 수 있다. 키 simulation은 필요조건이 아니며 최종 해결책으로 채택하지 않았다. IPC API가 해당 router 경로를 제공한다고 이번 조사에서 검증하지 않았으므로 가능하다고 주장하지 않는다.

## 11. 최소 수정 여부

Production 수정 없음. Refresh 제거는 view 재구성을 피하는 후보이나 누락된 router 통보를 해결하지 않는다. Live 재현과 통보 대안이 검증되지 않은 상태에서 완전한 routing 중 변경 기능으로 바꾸지 않았다. 기존 selected-track/netclass/layer/trigger/worker/Manager/lifecycle/config 기능 그대로 유지.

## 12. 실험 결과

`probe.py`는 A setter only, B setter+custom(via 보존), C B+UpdateUserInterface, D B+Refresh, E B+현재 SetTrackWidthIndex, F B+verified frame.Update, G B+verified frame.Refresh, H B+ProcessPendingEvents를 각각 분리한다. A/B/E 및 연속 폭 변경을 설치된 KiCad Python의 **실제 detached BOARD**로 실행했다. fixture는 preset `[0,250000]`과 기존 폭 250000 IU track 1개를 가진다. Fake getter 테스트가 아니다.

| 실험 | 실제 실행 결과 | 범위 |
|---|---|---|
| A | custom slot .4, effective .25, mode false | PASS: setter 단독은 mode를 켜지 않음 |
| B | effective .4, mode true, via/track/preset 그대로 | PASS: settings |
| E | 같은 index 설정 후 mode false, effective .25 | PASS: custom 해제 재현 |
| B .4→.75→.3 | effective 각각 일치; preset/기존 track/via 유지 | PASS: settings |
| C/D/F/G/H | NOT TESTED | live frame/router 필요 |

요청한 acceptance:

| 항목 | Manager Run Test | Phone / Keyboard |
|---|---|---|
| 1: .25 route 중 .4로 head 변경/route 유지 | NOT TESTED | NOT TESTED |
| 2: 완료 후 다음 route .4 | NOT TESTED | NOT TESTED |
| 3: .75 preset 추가 없음 | live NOT TESTED | live NOT TESTED |
| 4: .4/.75/.3 route 유지 | NOT TESTED | NOT TESTED |
| 5: X 정상 | NOT TESTED | NOT TESTED |
| 6: 두 trigger 경로 비교 | NOT TESTED | NOT TESTED |

Settings 검사 PASS를 live routing PASS로 보고하지 않는다. 기존 TRACK_WIDTH_FUNCTIONS.md의 live 정상 주장은 이번 실행에서 재검증한 결과가 아니다.

Live 분리 실험용 console 예시(설정 파일 변경 없음):

```python
import runpy
p = runpy.run_path(r'C:\Users\sgkim\Documents\KiCad\9.0\scripting\plugins\macrobk_drc_bridge\diagnostics\routing-width\probe.py')
timer = p['arm_case']('B', 0.4, 10000)
# 10초 안에 console에서 canvas로 돌아가 .25 route를 시작한다.
# 취소하려면 timer.Stop(). D는 view rebuild 실험이므로 별도 실행한다.
```

Delay console 결과는 Phone/Keyboard 결과와 구분한다. 각 실험을 동일한 .25 baseline/native custom 비교에서 반복하고 preview, 마우스 이동, committed 이전 segment, 다음 route, X, toolbar, focus를 기록해야 한다. 이 예시는 실험 준비이며 live 수행 결과가 아니다.

## 13–14. 파일·hash·Git

이번에 새로 작성한 파일은 diagnostics/routing-width 내 probe.py, REPORT.md, detached_results.json, baseline_hashes.json, protected_verification.json 및 공식 source 복사본뿐이다. 주요 production Python 파일은 수정하지 않았다. 보호 대상 9개 파일의 SHA256 대조 결과는 protected_verification.json에 있다. config SHA256: `42D1CA9DC99B7660034E8CCFDCA5AD20C8B0C64D9A007A98B25544FC7B614299`.

작업 시작부터 config.json, gui_helpers.py, kicad_controls.py, macrobk_drc.log, macrobk_drc_bridge.zip은 modified였고 TRACK_WIDTH_FUNCTIONS.md, track_width_test.py는 untracked였다. 기존 사용자 변경을 이번 작업의 변경으로 표시하거나 되돌리지 않았다. lifecycle.py 포함도 확인 대상에 들어 있다. Git commit/push 없음.

## 공식 소스 근거 (tag 9.0.9)

- [Refresh wrapper](https://github.com/KiCad/kicad-source-mirror/blob/9.0.9/pcbnew/python/scripting/pcbnew_scripting_helpers.cpp#L489)
- [RebuildAndRefresh: view clear와 REDRAW](https://github.com/KiCad/kicad-source-mirror/blob/9.0.9/pcbnew/python/scripting/pcbnew_action_plugins.cpp#L427)
- [Native custom dialog와 router handler](https://github.com/KiCad/kicad-source-mirror/blob/9.0.9/pcbnew/router/router_tool.cpp#L2690)
- [Width/Via toolbar callback](https://github.com/KiCad/kicad-source-mirror/blob/9.0.9/pcbnew/edit_track_width.cpp#L94)
- [Width cycling](https://github.com/KiCad/kicad-source-mirror/blob/9.0.9/pcbnew/tools/board_editor_control.cpp#L727)
- [Custom toolbar selection 공백](https://github.com/KiCad/kicad-source-mirror/blob/9.0.9/pcbnew/toolbars_pcb_editor.cpp#L801)
- [Settings index/custom semantics](https://github.com/KiCad/kicad-source-mirror/blob/9.0.9/pcbnew/board_design_settings.cpp#L1360)
- [ImportSizes와 track 상속](https://github.com/KiCad/kicad-source-mirror/blob/9.0.9/pcbnew/router/pns_kicad_iface.cpp#L706)
- [UpdateUserInterface](https://github.com/KiCad/kicad-source-mirror/blob/9.0.9/pcbnew/pcb_edit_frame.cpp#L1819)
- [TOOL_MANAGER REDRAW](https://github.com/KiCad/kicad-source-mirror/blob/9.0.9/common/tool/tool_manager.cpp#L623)

위 소스는 sources 폴더에 해당 tag 원문을 저장했다. C++ 구현 존재와 Python 호출 가능 여부는 별도로 검사했다.

최종 검증: 기존 unittest 55개 PASS(16.652초), root Python 및 probe 총 14개 AST syntax PASS, git diff --check PASS(기존 LF/CRLF 알림만 존재). 보호 대상 9개 SHA256 모두 시작 시점과 일치. lifecycle.py 존재 확인. Git 상태는 시작 시점의 modified/untracked 항목에 새 diagnostics/routing-width 폴더가 추가된 상태이다. 테스트로 기존 log의 내용은 변경될 수 있으므로 log는 보호 대상 production hash에 포함하지 않았다.
