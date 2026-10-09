# MacroBK PCB lifecycle 변경 전 분석

2026-10-09. E: 프로젝트 원본을 실제 읽어 분석. 설치본 수정 금지.

- __init__.py: import마다 MacroBKDRCBridge 생성/register 후 bridge.start_bridge 호출.
- bridge.py: trigger_core lazy import, bind_gui_thread, core.start_bridge. 명시적 reload 없음. Manager도 lazy import. 살아 있는 Worker/Manager는 재시작으로 업데이트하는 정책.
- trigger_core.py: module _started 플래그만 존재. lock 없음. 재import/reload 시 상태 초기화. start 실패에도 _started는 True.
- udp_worker 내부에서 socket 생성. SO_REUSEADDR 유지, wildcard bind :47831, IP_ADD_MEMBERSHIP 239.255.77.77 + 127.0.0.1, timeout 0.5초.
- UDP socket과 listener thread reference를 서비스/module에 보관하지 않음. _service_stop은 생성되지만 PCB 종료 시 set하는 경로 없음.
- ui_manager.py: module _manager_frame, parent=None Frame 생성. 기존 Frame Show/Raise/SetFocus 재사용. Close는 test Action Stop, config 자동 저장, blink timer Stop, Destroy. UDP 종료 호출 없음.
- PCB main Frame 종료 binding 없음. 다른 top-level Frame을 일괄 종료하는 코드도 없음.
- kicad_controls.candidate_frames: wx.Frame + MenuBar 필터, active 순 정렬. main PCB 식별 보강에 활용 가능.
- HotKey: 전용 daemon thread에서 HWND=None, HOTKEY_ID=0x4D42 등록. GetMessageW blocking, finally 동일 thread에서 UnregisterHotKey. stop은 WM_QUIT post + 1초 join. message queue 생성 전 종료 요청 경합 가능.
- Action Worker: _action_workers + lock, stop_event, run_id, latest_runs, daemon thread, trace cooperative stop. GUI helper는 call_gui_sync/async. 재작성 불필요.
- gui_helpers: GUI control snapshot reference registry. 종료 시 reference clear 필요.
- key_picker: Manager-owned modal dialog이며 finally Destroy. 독립 서비스 없음. 변경 불필요.
- kicad_controls: MacroBK가 만든 CallLater callback을 추적하지 않음. 종료 시 자체 timer만 취소하도록 wrapper 필요.
- Phone: parse_phone_packet → find_action_by_trigger → handle_phone_trigger. enabled Actions 전체, canonical 비교, 첫 match 정책. 변경 불필요.
- KiCad 9.0 설치된 pcbnew.py LoadPluginModule 실제 확인: KICAD_PLUGINS[ModuleName][dependencies]의 sys.modules 항목 삭제 후 import_module. dependencies는 해당 package prefix로 수집. 단순 module global 보호만으로 부족.
- 기존 tests/test_worker_engine.py는 KiCad Python + real wx fixture 통합 테스트. UDP test가 udp_worker를 직접 thread로 실행하므로 서비스 API fixture로 변경 필요.
- 원본 config.json SHA256: 550447E879DC0AD28A66F89BCFB9E41DBD456C147FA090314A6DB7739C66B4CE.

최소 수정 방침: process-local sys.modules registry가 서비스와 기존 모듈 generation을 소유. Manager UI 수명 분리. PCB Close Skip + 실제 Frame Destroy 확인 후 shutdown하여 저장 취소를 보호. 자체 socket/thread/worker/hotkey/timer/binding만 정리.
