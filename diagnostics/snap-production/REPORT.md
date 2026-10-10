# SNAP production validation

Production 구현: snap_panel.py(UI), snap_preferences.py(owned native Preferences transaction), kicad_controls.py(API 2개), gui_helpers.py(기존 GUI wrapper 노출), lifecycle.py(attach/cleanup/module ownership 최소 hook). SNAP_FUNCTIONS.md에 동작·한계를 설명한다. 테스트는 tests/test_snap_panel.py와 live_test.py에 분리했다.

| 요구 항목 | 현재 근거 |
|---|---|
| 자동 생성 | lifecycle frame attach hook 구현; 실제 fresh KiCad startup 결과 대기 |
| native 3개 page 보존·중복 | real wx fixture PASS; 실제 KiCad 결과 대기 |
| Pads getter/setter | owned Cancel/read + native OK/reopen 구현, fixture PASS |
| Tracks/Vias getter/setter | runtime choice strings + partial preservation 구현, fixture PASS |
| Graphics getter/setter | runtime choice strings + partial preservation 구현, fixture PASS |
| 실제 panel Choice 변경 | real wx fixture PASS; actual KiCad result 대기 |
| 외부 Preferences 변경 후 Refresh | fixture PASS; native Preferences integration 결과 대기 |
| already-open Preferences 보호 | fixture PASS. 열려 있는 dialog에는 개입하지 않음 |
| Manager close/reopen | Manager와 무관한 page ownership 구현; actual live NOT TESTED |
| Editor close/reopen | existing frame lifetime cleanup에 연결; actual live NOT TESTED |
| resize | native wx sizer UI; actual live NOT TESTED |
| focus/X | Preferences 종료 후 unique PCB GLCanvas focus 복원; X 입력 NOT TESTED |
| snapping behavior | MANUAL TEST REQUIRED |
| 원래 설정 복구 | integration script가 finally에서 모두 복구·재확인; 아직 live 결과 대기 |

자동 테스트: 기존 55개 + 신규 11개 **66 PASS**(18.768초). parent destruction 전에 queued refresh가 들어오는 경우를 검사해 top-level frame 삭제 guard를 추가했다. native Cancel command 및 resize status wrapping 보강 후 관련 11개 재실행 PASS(2.070초). Python root 15개 및 test/live script 포함 총 17개 AST syntax PASS. git diff --check PASS(기존 LF/CRLF 경고만 존재).

보호 검증: 기존 kicad_controls의 모든 기존 function/class AST가 git HEAD와 동일. 새 함수는 pcb_get_snap_settings/pcb_set_snap_settings 두 개뿐이다. routing native Q, selected/netclass width, layer 함수 수정 없음. trigger_core/bridge/Manager/key_picker 등 변경 없음. config.json SHA256 `42D1CA9DC99B7660034E8CCFDCA5AD20C8B0C64D9A007A98B25544FC7B614299` 동일. lifecycle은 명시된 SNAP hook만 변경했으며 UDP/Worker/Manager 설계 변경 없음.

Snap 값 persistence 없음. 진단 결과 JSON은 acceptance evidence이며 production backend가 읽거나 쓰지 않는다. runtime state 파일 또는 MacroBK config snap 키를 만들지 않았다. 사용자가 기존 diagnostic SNAP을 남겨둔 경우 production은 타 소유자 page를 삭제하지 않고 attach를 거부한다. 전체 KiCad 재시작으로 이전 probe가 소멸한다.

실제 GUI 판정은 fixture 결과와 별도로 live_result.json 확인 후 업데이트한다. live script는 사용자 Run Test로 실행하며 모든 API 호출을 기존 call_gui_sync로 GUI thread에 전달한다. 결과는 최초 원래값과 검증값·복구값을 기록한다. 자동 UI 작업은 좌표/키 입력을 사용하지 않는다.

Git commit/push 없음. 변경 파일은 위 production 5개+문서·테스트·진단이며 macrobk_drc.log는 실행 로그로 변경될 수 있다. 모든 코드/테스트/Git 작업은 지정된 C: 루트에서 수행했다.
