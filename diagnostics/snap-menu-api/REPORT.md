# Snap to pads — 기존 MacroBK GUI API round trip

**판정: PASS.** 실행 중인 KiCad 9.0.9 Preferences에서 실제 Choice를 읽고 변경한 뒤 native OK를 실행했다. 새 Preferences dialog에서 변경값을 확인했고, 원래값으로 복구한 뒤 다시 재오픈해 복구값까지 확인했다. 결과 파일은 result.json이다. 예약 메시지나 Choice의 draft 값만으로 PASS를 부여하지 않았다.

| 항목 | 실제 결과 |
|---|---|
| 기존 helper | open_menu, find_controls, iter_controls, get_control_info, get_control_value, set_control_value, _command_ok_button |
| 메뉴 | open_menu("Preferences -> Preferences") |
| Preferences 이동 | 실제 wx.Treebook page text 및 parent chain에서 PCB Editor > Editing Options 선택 |
| Control 위치 | 실제 Snap to pads: StaticText와 인접한 wx.Choice, native 선택지까지 검증 |
| 실제 class | Python wx.Choice / native wxChoice |
| 최초 id/name/label | id=-29315, name=choice, label="" (관찰 기록이며 id selector 사용 안 함) |
| 선택지 | 0 Never, 1 When routing tracks, 2 Always |
| 최초값 | index=2 / Always |
| 변경값 | index=0 / Never |
| native OK | 기존 _command_ok_button으로 actual button Command/ProcessEvent 수행 |
| 변경 후 재오픈 | 새 control id=-29061, index=0 / Never — PASS |
| 복구 | Always 설정 후 native OK |
| 복구 후 재오픈 | 새 control id=-28807, index=2 / Always — PASS |
| 최종값 | Always, restore_pass=true, restore_required=false |
| runtime pad snap behavior | NOT TESTED |

실제 선택지의 중간 문자열은 사용자가 예상한 `When creating tracks`가 아니라 **When routing tracks**였다. 여러 Editing Options page 중 PCB Editor parent를 가진 page를 정확히 선택했다(관찰된 index 30/parent 26; hardcode 없음). dialog가 재생성될 때 control id가 바뀌어도 매번 label과 sibling 구조로 다시 찾았다.

모든 wx 처리는 GUI thread callback에서 수행했다. modal Preferences가 nested event loop를 돌기 때문에 dialog callback을 먼저 예약한 뒤 기존 메뉴 helper를 호출했다. timer는 bounded 진단 callback에만 사용했고 종료 시 중지했다. production helper를 추가하거나 수정하지 않았다. 현재 존재하는 native OK helper는 표준 wx.ID_OK를 사용하며 임의 KiCad window id를 하드코딩한 것이 아니다.

앞선 SNAP tab 조사에서 확인한 **직접 pcbnew runtime setting binding 부재**와 이번 결과는 범위가 다르다. 직접 magnetic setting pointer에 접근하지 않아도, 기존 Preferences GUI 경로를 통해 native 설정을 반영하고 재오픈해 읽을 수 있다는 것이 이번에 증명됐다. 실제 마우스/라우팅 중 pad snapping 변화 또는 즉시 적용 시점까지 검증한 것은 아니다.

Appearance SNAP 탭 접근/변경 없음. 테스트 대상은 pads Choice 하나뿐이며 tracks/vias 또는 graphics Choice setter를 호출하지 않았다. config 파일 직접 수정, 키 입력, 화면 좌표, control id selector, 새로운 C++/SWIG bridge 없음. Preferences dialog에 남아 있는 다른 사용자의 draft를 수락하지 않도록 테스트 시작 시 이미 열린 dialog는 거부한다.

추가 파일: probe.py, RUN_PROBE.md, REPORT.md, result.json, baseline_hashes.json, protected_verification.json. 모두 지정된 C: 작업 루트의 diagnostics/snap-menu-api 아래다. 기존 production 8개 파일 SHA256 모두 시작 시점과 동일하며 MacroBK config SHA256는 `42D1CA9DC99B7660034E8CCFDCA5AD20C8B0C64D9A007A98B25544FC7B614299`이다. 기존 SNAP probe 파일은 수정하지 않았다.

검증: 기존 unittest **55개 PASS**(16.484초), probe AST syntax PASS. 기존 macrobk_drc.log는 테스트 실행 로그로 변경될 수 있다. Git commit/push 없음. E: 작업 없음.
