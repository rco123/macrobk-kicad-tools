# 활성 PCB 레이어 조사 결과 — 2026-10-10

결론: 현재 KiCad 9 wx/Python 환경에서는 현재 active layer를 안정적으로 읽는
방법을 아직 확인하지 못함. pcb_get_selected_layer()는 구현하지 않았음.
기존 추정 함수와 UP/DOWN은 변경하지 않았음.

## 1. 조사/실험 방법

- 작업 시작 시 현재 production 코드와 git 상태를 확인함. 기존
  _pcb_active_layer_name()는 GetActiveLayer → toolbar selection → 배경색 순으로
  추정함. 요청에 따라 이 경로를 재채택하거나 수정하지 않음.
- 별도 layer_diagnostics.py 작성. 실제 PCB GUI thread에서 Frame API/컨트롤
  상태/bitmap RGBA 수치를 수집하도록 설계함. 별도 수동 Capture 창 제공.
- 실제 실행 중인 `jjj — PCB Editor`의 접근성 트리를 조회하고 저장함.
- KiCad 내장 Python에서 pcbnew/wx 객체 introspection 수행함.
- 공식 KiCad C++ 소스 문서의 Appearance OnLayerChanged와 INDICATOR_ICON 조사.
- synthetic wx fixture에서 diagnostic read-only 동작/alpha 및 mask 집계/
  비교기/GUI thread 제한 검증. 실제 PCB active-layer 검증과 명확히 구분함.

## 2. 각 방법 결과

| 방법 | 확인된 결과 | 해석/범위 |
|---|---|---|
| 실제 PCB 접근성 트리 | layer row마다 panel 3개/이미지 3개/StaticText label 확인 | 구조 관찰 PASS, bitmap pixel 값은 미수집 |
| 실제 toolbar 표시 | 접근성 값에 F.Cu (Shift+Z)가 표시됨 | 단일 시점 관찰만 확인. GetStringSelection 판정 채택 안 함 |
| Frame API introspection | wx.Frame base에는 요청한 11개 API 모두 없음 | 별도 Python subprocess의 base wrapper 결과. live PCB frame 확정 아님 |
| pcbnew introspection | 9.0.9; GetBoard/GetCurrentSelection 및 Layer 함수/상수 존재 | module에 직접 GetActiveLayer/GetCurrentLayer API 확인되지 않음. item selection과 active layer는 별개 |
| board type introspection | GetEnabledLayers/GetVisibleLayers/GetLayerName/GetLayer 등 존재 | board/item의 GetLayer를 Editor active layer로 오인하지 않음 |
| 공식 source | active 변경 시 indicator를 OFF/ON bitmap으로 바꿈 | 유력한 관찰 후보. 현재 설치본 실측 증명 아님 |
| bitmap fixture | alpha=10인 pixel 하나: nontransparent=1, opaque=0, alpha_gt_16=0, alpha_sum=10 | 비선택을 단순 pixel_count>0으로 판정하면 오탐 가능 |
| live 입력/캡처 | screenshot timeout 두 번, click geometry unavailable; keyboard 메뉴 진입도 확인 못 함 | 실제 마우스 변경 비교 미완료. 진단 실행 요청 전달함 |
| native client data | 타입/소유권 미확인 | Python 객체로 강제 해석하지 않고 API 존재 여부만 기록 |

## 3. 실제로 선택 변경 시 변한 값

실제 PCB의 선택 전/후 bitmap 숫자는 아직 수집되지 않아 **확인된 변화값 없음**.
fixture의 조작된 값은 이 항목의 증거로 사용하지 않음.
검증 후보는 같은 row의 indicator StaticBitmap path에서 alpha/checksum이
일관되게 교체되는지 여부이며 visibility 아이콘/color swatch와 구별해야 함.

## 4. 네 레이어 비교표

| 레이어 | 실제 접근성 label/id | row 내 이미지 수 | 선택 시 alpha/checksum | 실제 선택 판정 |
|---|---:|---:|---|---|
| F.Cu | F.Cu / 0 (트리에는 ID 생략) | 3 | NOT MEASURED | NOT TESTED |
| B.Cu | B.Cu / 2 | 3 | NOT MEASURED | NOT TESTED |
| F.Adhesive | F.Adhesive / 9 | 3 | NOT MEASURED | NOT TESTED |
| Edge.Cuts | Edge.Cuts / 25 | 3 | NOT MEASURED | NOT TESTED |

F.Cu의 0은 접근성에서 ID가 생략된 관찰을 통해 추정하지 않고, 설치된
pcbnew.F_Cu 상수값을 별도 확인한 값임. 실제 row ID는 diagnostic에서 재확인 필요.

## 5. 신뢰 가능한 판정 기준

아직 없음. focus/background/cache는 판정 기준으로 사용하지 않음.
bitmap 존재만으로 indicator라 단정하지 않음. 비선택 blank icon도 Windows에서
근소한 alpha를 가질 수 있으므로 RGB checksum/alpha checksum/alpha 합계/
nontransparent/opaque 수를 모두 비교하도록 구현함. pixel threshold 자체도
실제 설치본에서 검증되지 않았으므로 diagnostic 통계에만 사용함.

공식 source 조사에서 OnLayerChanged는 실제 Frame의 active layer를 읽고
선택 row의 indicator 상태를 바꾼다는 점을 확인함.
[Appearance source](https://docs.kicad.org/doxygen/appearance__controls_8cpp_source.html).
indicator는 내부 StaticBitmap의 bitmap을 교체하며 ON/OFF에 서로 다른 이미지를
사용하고 Windows OFF image는 near-transparent pixel을 포함할 수 있음.
[Indicator source](https://docs.kicad.org/doxygen/indicator__icon_8cpp_source.html).
이 Doxygen 자료는 설치된 9.0.9 tag와 일치하는 소스라고 보증하지 않음.
9.0.9 raw source 조회는 도구 fetch/network 제한으로 완료하지 못함.

## 6. 최종 getter 구현 여부

**미구현**. 새 파일은 진단/비교 도구만 제공함. 실제 화면과의 비교 증명이
없으므로 pcb_get_selected_layer()를 만들어 추정값을 반환하지 않음.

## 7. PASS/FAIL 및 보호 확인

- 진단 helper unit/wx fixture 6개 PASS.
- 기존 전체 + 신규 diagnostic tests: **55개 PASS (17.181초)**.
- 신규 Python 4개 py_compile PASS.
- 기존 8개 production Python 파일의 작업 전후 SHA256 동일.
- config.json 작업 전후 동일:
  F0947EB350FC5F0321E6B3BDE02B0498BDFEDADD377BB1B3BC47CCCC2E07E328.
- 실제 F.Cu/B.Cu/F.Adhesive/Edge.Cuts 판정: **NOT TESTED**.
- 실제 mouse 변경, Manager open/close, PCB 재오픈: **NOT TESTED**.
- 실제 PCB 접근성 row 구조 관찰: **PASS**.
- 실제 화면 capture/클릭 자동화: **실패**. layer helper의 실패로 해석하지 않음.

## 8. 남은 불확실성과 다음 실험

실제 PCB 내부 frame wrapper API 여부, 세 bitmap 중 indicator의 위치/클래스,
현재 DPI/theme의 alpha/checksum 수치, 숨김/비활성 row의 indicator 처리,
마우스 변경 시 즉시 갱신 여부, Manager/focus/재오픈 독립성 확인 필요.

README의 수동 Capture 절차로 실제 JSON을 모은 뒤 compare_layer_dumps.py로
각 bitmap 경로의 변경값을 비교해야 함. 후보를 얻어도 추가 재현성 검증 전에는
getter를 작성하지 않음. raw capture의 expected_by_human은 사람의 관찰값이고
프로그램 판정 결과가 아니므로 서로 혼동하지 않음.

증거 파일:
- evidence/live_pcb_accessibility.txt — 실제 PCB tree, 단일 시점
- evidence/python_api_probe.json — 별도 Python introspection, live Frame 아님
- evidence/baseline_hashes.json — 변경 전 보호 파일 hash
- evidence/diagnostic-tests.txt / all-tests.txt — fixture 및 전체 테스트
