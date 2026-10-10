# Appearance SNAP feasibility — KiCad 9.0.9

## 判定

**UI ONLY（UI probe 범위）.** 실제 열린 PCB Editor 안에 SNAP page를 추가하고 연속 실행 시 재사용하는 것까지 증명했다. **실제 Snap runtime state 표시/변경 기능은 증명하지 못했다.** 따라서 상태 표시까지 포함하는 완전한 제품 구현에 대한 승인이 아니며 IMPLEMENTABLE 또는 READ ONLY로 판단할 수 없다. native 설정과 연결하는 정식 SNAP 기능은 현재 binding으로 추천하지 않는다.

작업 루트는 지정된 C: plugin 폴더다. production 파일 및 MacroBK config 변경 없음. E: 작업 없음. 사용자 Run Test 실행으로 live wx probe가 실행됐으며 실제 결과 파일을 확인했다. 자동 요소 클릭은 `coordinate input geometry is unavailable`로 fresh state 재시도까지 실패하여 사용자 실행이 필요했다. 화면 좌표나 SendKeys는 사용하지 않았다.

## 실제 runtime hierarchy

```
wx._core.Frame / wxFrame (PcbFrame, id -31953, 1401×931)
  wx._core.Panel / wxPanel (name "", id -31930, 352×605)
    wx._core.Notebook / wxNotebook (name notebook, id -31929, 352×501)
      [0] Layers  wxPanel id -31928
      [1] Objects wxPanel id -31926
      [2] Nets    wxPanel id -31924
      [3] SNAP    wxPanel id -29767 (MacroBK-owned probe)
```

정확한 Python class는 **wx._core.Notebook**이고 native class는 **wxNotebook**이다. wx.aui.AuiNotebook 또는 KiCad custom notebook이 아니다. Appearance dock caption은 부모 panel의 label/name으로 노출되지 않았다. 추정 title 검색 대신 PCB Editor frame과 native 3개 page signature로 notebook을 찾았다. 위 id는 관찰값만 기록했으며 selector에는 사용하지 않았다. 실제 wx parent/children/name/label/size/class/page object 기록은 hierarchy.json과 inspection.json에 있다. Python wrapper repr 주소는 wrapper 재생성/해제로 반복될 수 있으므로 native page 동일성 판정에 단독 사용하지 않았다.

## 14개 질문에 대한 답

| 질문 | 결과와 한계 |
|---|---|
| 1. 정확한 tab control class | live wx._core.Notebook / wxNotebook |
| 2. 기존 3개 탭은 실제 page인가 | PASS. GetPageCount/GetPageText/GetPage로 확인 |
| 3. AddPage/InsertPage 작동 여부 | AddPage/RemovePage PASS. InsertPage/DeletePage method 존재 확인; 해당 두 method는 실제 호출 안 함 |
| 4. SNAP 안정적 추가 | 최소 AddPage PASS, 기존 page 동일성/순서 보존 PASS; 장기 안정성/전체 layout 검증은 별도 |
| 5. reload/repeat 중복 | 연속 두 번 및 runpy module reload PASS. Editor 재시작 뒤 새 SNAP 1개 생성 확인. Manager만 close/reopen하는 단독 경로는 사용자 관찰 대기 |
| 6. Editor close cleanup | PASS: 실제 Editor destroy 로그와 같은 시점의 owned-page destroy 기록 확보. 재시작 확인. timer/frame binding 없음. 모든 native 종료 오류가 없었다는 UI 검증까지 의미하지 않음 |
| 7. runtime Snap 3개 읽기 | 안전한 Python 경로 확보 실패. 실제 frame/SettingsManager binding 검사에서 필요한 접근자 없음 |
| 8. runtime 변경 | FAIL: 안전한 runtime setter 경로 없음. 임의 config/ABI/native memory 접근 안 함 |
| 9. 즉시 snapping 반영 | NOT TESTED. setter가 없으므로 실제 behavior 변경을 주장하지 않음 |
| 10. Preferences 양방향 동기화 | NOT TESTED / 구현 경로 미확보. Preferences draft control 읽기는 runtime getter가 아님 |
| 11. timer/event | 조사한 경로에서 Python에 노출된 magnetic-state notification 없음. timer로 누락된 getter를 해결할 수 없어 설치하지 않음 |
| 12. 공식 API인가 | page 삽입은 wx 내부 UI 접근이며 KiCad 공식 Appearance 확장 API가 아님. SettingsManager 일부 API는 pcbnew binding에 존재하지만 magnetic 설정 접근은 빠짐 |
| 13. 버전 민감도 | native page signature/구조/번역/label에 의존. 9.0.9 외 버전 검증 없음. 불일치/다중 후보/타 소유 SNAP이면 중단 |
| 14. 정식 구현 추천 | UI 실험 가능. native Snap 설정 연동 제품 기능은 현재 Python 접근 경로로 추천하지 않음 |

## runtime Snap 저장 위치와 Preferences

Native single source of truth는 `Pgm().GetSettingsManager().GetAppSettings<PCBNEW_SETTINGS>("pcbnew")->m_MagneticItems`다. `PCB_BASE_FRAME::GetMagneticItemsSettings()`는 이 멤버의 주소를 반환한다. GRID helper는 전달받은 MAGNETIC_SETTINGS pointer를 snapping 판단에서 읽는다. **C++ 경로가 존재한다고 Python에서 호출 가능하다는 뜻은 아니다.**

| 설정 | native member | enum/선택지 | persistence |
|---|---|---|---|
| Snap to pads | m_MagneticItems.pads | NO_EFFECT=0 Never, CAPTURE_CURSOR_IN_TRACK_TOOL=1 When routing tracks, CAPTURE_ALWAYS=2 Always | editing.magnetic_pads |
| Snap to tracks and vias | m_MagneticItems.tracks | 동일 0/1/2 | editing.magnetic_tracks |
| Snap to graphics | m_MagneticItems.graphics | bool. choice index 0 Always=true, 1 Never=false | editing.magnetic_graphics |

Preferences panel은 TransferDataToWindow에서 native member를 choice에 복사한다. TransferDataFromWindow에서 선택값을 native member로 기록한다. choice 변경만으로 runtime member를 즉시 쓰는 handler는 해당 소스에 없다. Preferences 수락/데이터 transfer 전 선택값은 draft다. native getter로 접근할 수 있다면 별도의 MacroBK 설정값을 만들 이유가 없지만 현재 binding으로는 접근할 수 없다. Preferences OK 후 실제 snapping 갱신 시점/behavior는 이번 live 실행에서 검증하지 않았다.

사용자 KiCad persistence 파일 `C:\Users\sgkim\AppData\Roaming\kicad\9.0\pcbnew.json`에서 read-only 확인한 값은 pads=2, tracks=2, graphics=true였다. **이는 파일 snapshot이며 현재 실행 중인 PCB Editor의 실제 상태 검증이 아니다.** 이 파일도 수정하지 않았다. MacroBK config.json에 Snap 값을 넣지 않았다.

설치된 pcbnew에는 GetSettingsManager와 SETTINGS_MANAGER가 존재한다. 그러나 SETTINGS_MANAGER의 GetAppSettings, PCBNEW_SETTINGS, MAGNETIC_SETTINGS, MAGNETIC_OPTIONS binding은 없다. live wx frame의 GetPcbNewSettings/GetMagneticItemsSettings도 callable이 아니다. binding_inventory.json과 inspection.json이 근거다. SettingsManager의 Save/Load를 호출하거나 SWIG pointer를 임의 cast하지 않았다.

Preferences control getter를 위한 read_preferences_controls()는 열려 있는 dialog에서 label+인접 wx.Choice+선택지를 확인하는 진단 도구다. 기존 control을 이동·수정하지 않는다. 이 결과는 명시적으로 `Preferences draft`이며 SNAP tab에 current runtime truth처럼 표시하지 않는다. 본 probe는 현재 상태 대신 `Runtime snap getter is unverified`를 표시한다.

## UI / lifecycle / focus

새 wx.Panel의 parent는 이미 확인된 notebook이다. 기존 KiCad control Reparent 없음. AddPage 마지막 index에만 삽입한다. source에서 native OnNotebookPageChanged는 Windows에서 추가 page index를 고정 array로 참조하지 않지만 idle focus를 canvas 쪽으로 넘기는 handler를 bind한다. 실제 tab 클릭 이후 focus는 별도로 관찰해야 한다. AddPage 직후 immediate_focus_preserved=true였으며 이것이 tab 클릭/idle 전체 focus 검증은 아니다.

중복 방지는 probe 소유자 name을 실제 page에서 검색하므로 script module globals에 의존하지 않는다. unowned SNAP 발견 시 사용하거나 삭제하지 않고 중단한다. Manager에는 자원을 묶지 않는다. page의 destroy event만 bind하며 timer·frame/Manager event binding·서비스·worker를 추가하지 않는다. 실제 Editor close/destroy가 11:11:06/11:11:11 로그에 있고, page의 destruction.json도 11:11:11에 생성됐다. 새 Editor가 11:11:18에 attach된 로그와 새 window id를 확인했다. 이 close evidence는 후속 명시적 제거가 destruction.json을 덮어쓰기 전에 editor_close_evidence.json으로 보존했다. parent destruction cleanup은 PASS지만 theme/DPI/종료 오류 dialog 전체 검증을 의미하지 않는다.

KiCad는 Appearance selected tab index를 자기 AUI 설정에 저장한다. SNAP 선택 상태로 종료하면 index 3이 남을 수 있어 정식 구현 전 cleanup/save 순서 검증이 필요하다. 테스트 후 제거 함수를 제공하고 native 탭으로 복귀하게 했다. 설정 파일 직접 변경으로 보정하지 않는다.

## 실제 실행 결과

live_result.json: KiCad version 9.0.9. first_add.created=true, index=3; original_pages_preserved=true; immediate_focus_preserved=true. repeat_add.created=false, index=3. duplicate_test=PASS. native page id 3개는 그대로이며 SNAP만 추가됐다.

live_ui_checks.json: 재시작된 Editor에서 SNAP 1개 생성 → 4개 탭 SetSelection 결과 selected=true/page_shown=true → frame 1401×931에서 1301×851로 변경 시 notebook 352×501에서 352×421로 조정 → 원래 창 크기 복원 → 새로운 runpy module로 같은 page 재사용(created=false) → RemovePage/Destroy 1개 → 다시 제거하면 0개 → 최종 native page 3개. **probe는 테스트 후 제거됐으며 현재 SNAP을 설치해 둔 상태가 아니다.** programmatic selection/resize 결과는 직접 클릭과 눈으로 확인한 clipping/theme 결과와 구분한다.

| 항목 | 상태 |
|---|---|
| live hierarchy 확인 | PASS |
| SNAP AddPage | PASS |
| native page 보존 | PASS |
| immediate focus 유지 | PASS |
| 동일 실행 내 repeat 중복 방지 | PASS |
| module reload 중복 방지 | PASS |
| 4개 탭 programmatic 전환 | PASS: 선택 및 page_shown 확인 |
| frame resize/복원 | PASS: 실제 frame/notebook size 조정; 시각적 layout 미검증 |
| RemovePage/Destroy/반복 제거 | PASS: 제거 1개/0개, 최종 native 3개 |
| Manager 단독 close/reopen 유지 | 미검증. Manager close와 Editor close 로그는 있으나 단독 close/reopen 중 SNAP 유지 관찰은 없음 |
| Editor close/reopen cleanup | PASS: 사용자 종료 후 로그/owned destruction/새 Editor 확인. 종료 오류 dialog 여부는 미확인 |
| Appearance show/hide/collapse, light/dark, DPI | NOT TESTED |
| runtime getter/setter | 안전한 binding 경로 없음; PASS 아님 |
| Preferences sync | NOT TESTED |

## 파일 및 보호 검증

추가 파일은 diagnostics/snap-tab 아래 probe.py, RUN_PROBE.md, REPORT.md, baseline_hashes.json, protected_verification.json, binding_inventory.json, runtime 생성 JSON 및 sources의 9.0.9 공식 source 복사본이다. 기존 production 파일은 수정하지 않았다. 보호 대상 8개 SHA256 모두 동일. config SHA256는 `42D1CA9DC99B7660034E8CCFDCA5AD20C8B0C64D9A007A98B25544FC7B614299` 유지.

기존 unittest 55개 PASS(17.903초). probe AST syntax PASS. Git commit/push 없음. 테스트 실행으로 기존 macrobk_drc.log가 변경될 수 있다. 사용자 Manager script 임시 입력은 Save하지 않는 실행 절차다.

## 공식 9.0.9 근거

- [wxNotebook와 native page 구성](https://github.com/KiCad/kicad-source-mirror/blob/9.0.9/pcbnew/widgets/appearance_controls_base.cpp#L21)
- [Appearance page-change 및 idle focus](https://github.com/KiCad/kicad-source-mirror/blob/9.0.9/pcbnew/widgets/appearance_controls.cpp#L834)
- [Preferences settings transfer](https://github.com/KiCad/kicad-source-mirror/blob/9.0.9/pcbnew/dialogs/panel_edit_options.cpp#L113)
- [Native enum](https://github.com/KiCad/kicad-source-mirror/blob/9.0.9/pcbnew/pcbnew_settings.h#L55)
- [Persistence keys](https://github.com/KiCad/kicad-source-mirror/blob/9.0.9/pcbnew/pcbnew_settings.cpp#L168)
- [Runtime pointer getter](https://github.com/KiCad/kicad-source-mirror/blob/9.0.9/pcbnew/pcb_base_frame.cpp#L917)
- [Grid helper runtime reads](https://github.com/KiCad/kicad-source-mirror/blob/9.0.9/pcbnew/tools/pcb_grid_helper.cpp#L1507)

API 부재는 설치된 Python과 live wx object에서 검사했다. Source 조사만으로 UI/runtime PASS를 부여하지 않았다.

사용자는 두 실행의 예약 메시지(`probe scheduled on GUI thread`, `UI checks scheduled; original size restored and probe removed on completion`)를 회신했다. 예약 메시지만으로 PASS를 부여하지 않고 실제 callback이 쓴 JSON을 읽어 완료를 확인했다. 별도의 시각적 layout/Manager-only 재열기 정상 확인 회신은 없었다. 테스트 후 owned SNAP page는 제거됐고 native 3개 page를 보존했다.
