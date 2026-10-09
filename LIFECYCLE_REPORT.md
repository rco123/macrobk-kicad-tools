# MacroBK PCB lifecycle 수정 보고 (2026-10-09)

1. **기존 문제 원인**: reload/reimport에 취약한 _started, 미보관 UDP socket/thread, PCB 종료 감지 부재, parent 없는 Manager가 서비스 소유권을 불명확하게 함.
2. **기존 lifecycle**: package import → ActionPlugin 생성/register → core.start_bridge → hotkey thread와 UDP thread 생성. Manager는 lazy 생성/Destroy. PCB 종료와 통합된 shutdown 없음.
3. **수정 lifecycle**: package import → 기존 module generation 복원 → plugin 재사용 → process-local service.start. Manager open/close는 UI만 관리. PCB Frame Destroy 확정 → service.shutdown. 중복 start/shutdown은 idempotent.
4. **수정 파일**: __init__.py, bridge.py, trigger_core.py, ui_manager.py, kicad_controls.py, 새 lifecycle.py, tests/test_worker_engine.py, 새 tests/test_lifecycle.py. 분석/보고 문서 추가. gui_helpers.py/key_picker.py 기능 수정 없음.
5. **파일별 주요 내용**: __init__는 모듈 복원과 등록 재사용; bridge는 기존 engine 반환; core는 서비스 위임/worker 상태 보존/GUI epoch guard/HotKey 종료; UI는 서비스 Manager 참조와 PCB parent/dispose; controls는 PCB 식별 및 자체 CallLater 추적; lifecycle은 리소스 소유와 통합 종료; tests는 새 API fixture와 lifecycle 회귀 검증.
6. **Process-local singleton**: sys.modules['_macrobk_kicad_pcb_service_v1']에 RLock, service, plugin 저장. package alias 및 dependency 삭제 후에도 유지. PC 전체 lock 또는 다른 프로그램과의 공유 없음.
7. **start 중복 방지**: registry lock으로 최초 service 생성, service RLock으로 socket/thread 생성 직렬화. 실행 중이면 기존 service 반환. setup/start 예외 시 socket close, stop set, refs/state rollback. 살아 있는 이전 listener/hotkey 또는 대기 중 GUI cleanup이 있으면 새 시작 차단.
8. **PCB Close 감지**: candidate_frames의 wx.Frame/MenuBar 후보에서 native PCB class/name 우선, PCB hierarchy + title 보조. EVT_CLOSE는 Skip하여 KiCad handler와 저장 확인 보존. EVT_WINDOW_DESTROY의 사전 저장 Frame ID로 실제 종료 확정. wx는 Destroy 시 다른 Python wrapper를 전달할 수 있으므로 identity 비교하지 않음. startup Frame 미발견 시 소유 CallLater로 재탐색.
9. **Manager Close vs PCB Close**: Manager Close는 자체 test Stop, blink timer Stop, 자체 Frame Destroy만 수행. UDP 유지. PCB 실제 종료는 Manager/모든 MacroBK worker/UDP/HotKey/자체 callback과 binding 정리. lifecycle Close의 config 자동 저장 제거; 명시 Register/Save 유지.
10. **shutdown 순서**: lock으로 shutting_down/accepting/epoch 설정 및 stop event set → Manager/discovery/helper timers/자체 event binding/control references 정리 → Worker stop 및 bounded wait → socket close → UDP bounded join → HotKey Stop/Unregister → 상태와 종료 reference 정리. 내부 로그에 service ID, epoch, thread ident 기록. GUI 외 호출은 GUI cleanup을 CallAfter하고 완료 전 재시작 차단.
11. **Worker 종료**: 기존 worker registry/stop_event/run_id/trace 유지. 전체 worker stop_event set, 전체 wait 예산 0.5초. native sleep/C extension을 forced kill하지 않음. 지연 worker는 기존 registry에 남아 실제 완료 시 제거되어 stale completion/중복 run 보호.
12. **UDP 종료**: recv timeout 0.5초, stop event, 소유 socket close, 최대 1초 join. listener가 아직 살아 있으면 참조 유지하여 새 listener 중복 차단. 정상 종료 시 socket/thread refs None. SO_REUSEADDR, loopback multicast group/port 유지.
13. **Refresh/Reload**: 실제 KiCad LoadPluginModule dependency 삭제 정책 확인. anchor가 기존 core/controls/helpers/UI/key-picker/bridge/lifecycle 모듈을 보관하고 package init에서 복원. 실행 중 Worker/Manager를 자동 reload하지 않음. explicit core reload는 worker lock/registry/config/counters/stop state를 재초기화하지 않음. 코드 업데이트는 PCB 재시작으로 적용.
14. **config hash 전/후**: SHA256 동일 — 550447E879DC0AD28A66F89BCFB9E41DBD456C147FA090314A6DB7739C66B4CE. 테스트의 config 저장 검증은 별도 임시 파일만 사용.
15. **Syntax 검사**: KiCad 9.0 Python 3.11 py_compile, 요청 7개 파일 및 lifecycle.py 모두 PASS. bytecode 출력은 검토 폴더로 지정.
16. **Unit/fixture tests**: unittest discover로 49개 PASS(기존 Worker/Phone/Helper 32개 + lifecycle 17개). real wx fixture, mock socket/Win32 API, 실제 loopback multicast 테스트 포함. 1회/반복/동시 start, Manager 반복 close/open, shutdown/restart, alias/core reload, KiCad dependency 삭제/복원, PCB destroy, veto Close, 외부 리소스 무간섭, setup/thread start rollback, stale callback, timer/reference cleanup, plugin 등록, HotKey 자기 ID 해제, sleeping worker bounded stop 검증.
17. **실제 KiCad GUI NOT TESTED**: 실제 PCB Editor 최초 실행, Manager Open/Close 뒤 Phone 유지, 재Open, 중복 UDP Action 여부, Refresh 여러 번, Trigger 1회→Action 1회, 실제 PCB 종료 시 Manager 소멸/프로세스 종료, 재실행 후 listener/socket 1개 생성. 실제 keyboard OS shortcut 입력도 NOT TESTED. 실제 PCB native Frame 식별은 배포 전 확인 필요. fixture 테스트 결과를 실제 PCB GUI PASS로 표시하지 않음.
18. **남아 있는 위험**: 실제 KiCad native Frame 식별/Destroy event 순서의 최종 확인 필요. native sleep/C extension worker는 stop 즉시 종료되지 않으나 daemon 및 bounded wait로 PCB를 무한 대기시키지 않음. OS HotKey 충돌 가능성은 기존 status 정책 유지. queued wx callback은 물리적 제거 대신 epoch로 무효화. 과거 설치본이 이미 만든 추적 불가 리소스는 소급 종료하지 않으므로 배포 시 PCB를 재시작해야 함. Register/Save 없이 Manager를 닫은 변경은 자동 저장되지 않음.

아래 체크는 코드 및 unit/wx fixture 검증 기준이며 실제 PCB GUI 완료를 뜻하지 않습니다.

- [x] PCB Process당 UDP Socket 정확히 1개 (running service)
- [x] PCB Process당 UDP Listener 정확히 1개 (running service)
- [x] Manager Close 시 UDP 유지
- [x] Manager 재실행 시 UDP 추가 생성 없음
- [x] Plugin Refresh 시 UDP 추가 생성 없음 (dependency 삭제 simulation)
- [x] PCB Editor 종료 시 Manager 종료 (wx fixture)
- [x] PCB Editor 종료 시 Worker Stop (wx fixture)
- [x] PCB Editor 종료 시 UDP Listener 종료 (wx fixture)
- [x] PCB Editor 종료 시 UDP Socket close (wx fixture)
- [x] PCB Editor 종료 시 HotKey 정리 (Win32 API mock)
- [x] 다른 프로그램 Plugin 리소스에는 영향 없음 (ownership test)
- [x] Phone Trigger 기존 기능 유지
- [x] Keyboard Trigger 기존 기능 유지 (canonicalization/HotKey ownership; 실제 입력 NOT TESTED)
- [x] config.json 변경 없음
- [x] 전체 테스트 PASS
