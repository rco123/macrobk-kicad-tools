# MacroBK PCB Tools

**KiCad 9 PCB Editor용 PCB 설계 및 자동화 플러그인**  
개발: **BK Systems** · 라이선스: **MIT** · 소스: https://github.com/rco123/macrobk-kicad-tools

MacroBK PCB Tools는 KiCad PCB Editor에서 **등록된 Python Action**을 키보드 또는 MacroBK Studio/Phone UDP 트리거로 실행하고, KiCad의 PCB 편집 기능을 함수로 제어합니다.

주요 기능: 선택 필터, PCB 레이어 선택·표시·순환, 선택한 트랙 및 라우팅 트랙 폭, SNAP(Magnetic Points), DRC 창 호출, GUI 컨트롤 탐색, 액션 저장·시험 실행·중지.

> **주의:** Python 스크립트는 해당 Windows 사용자 권한으로 실행됩니다. 신뢰할 수 있는 스크립트만 등록하십시오. 이 저장소는 KiCad **PCM 배포 ZIP이 아니라 소스 설치판**입니다. 내부 클래스 이름 'MacroBKDRCBridge'와 설치 폴더명 'macrobk_drc_bridge'는 기존 설치와 호환되도록 남겨 두었습니다.

## 1. 설치 및 시작

대상 환경: Windows / KiCad 9.x PCB Editor. KiCad 내장 pcbnew 및 wxPython을 사용합니다. 일반 Python 인터프리터에서 단독 실행하는 프로그램이 아닙니다.

1. 이 저장소를 Clone/다운로드합니다.
2. Python 파일들과 'icons' 폴더가 함께 들어 있는 전체 폴더를 다음 경로에 배치합니다.

~~~text
%USERPROFILE%\Documents\KiCad\9.0\scripting\plugins\macrobk_drc_bridge\
    __init__.py
    bridge.py
    lifecycle.py
    trigger_core.py
    ui_manager.py
    key_picker.py
    kicad_controls.py
    gui_helpers.py
    snap_panel.py
    snap_preferences.py
    icons\
~~~

3. **PCB Editor를 완전히 종료한 후 다시 실행**합니다. Python 모듈과 실행 중인 worker가 남아 있으므로 코드 변경 후 'Refresh Plugins'만으로 교체하지 마십시오.
4. PCB Editor의 **Tools → External Plugins → MacroBK PCB Tools**를 실행합니다.
5. 새 설치에서는 `open_menu("Inspect -> Design Rules Checker")`를 실행하는 기본 **Open DRC** Action이 준비됩니다. Action을 등록하거나 저장하면 'config.json'에 사용자 설정이 기록됩니다.

**기존 사용자 필독:** 개발 버전에서 추적하던 'config.json'에는 개인 PC 경로와 실험용 Action이 들어 있었습니다. 공개판은 이 파일을 Git에서 제외하며 'config.example.json'만 제공합니다. **기존 설치를 git pull로 갱신하기 전에 현재 'config.json'을 다른 폴더로 백업하고, 업데이트 후 복원**하세요. 기존 저장된 Actions를 잃지 않도록 주의하십시오.

## 2. 플러그인 화면 사용

| 메뉴/버튼 | 사용법 |
| --- | --- |
| Registered Actions | Action 선택, 추가, 복제, 이름 변경, 삭제 |
| Select Key | 수정키(Ctrl/Alt/Shift/Win) 및 일반 키 1~4개 선택 |
| Register | 현재 Action 설정 저장 후 키보드 트리거 재등록 |
| Python Script | 실행할 Python 코드 작성 |
| **Run Test** | 현재 스크립트를 시험 실행; 배포판에서도 제공되는 정상 기능 |
| **Stop** | 실행 중인 Run Test에 중지 요청 |
| Save | 스크립트 및 Action 저장 |
| Result | print 출력과 예외 확인; Copy/Clear 지원 |
| Appearance → SNAP | Pads/Tracks and vias/Graphics의 Magnetic Points 조회·설정 |

### 처음 사용하는 예제

Python Script 영역에 아래 코드를 입력하고 **Run Test**를 누릅니다.

~~~python
print("Current layer:", pcb_get_selected_layer())
print("Selection filter:", pcb_select_filter_state())
~~~

Result에서 결과를 확인한 후, 원하는 Action 이름과 Trigger를 지정하고 **Save / Register**합니다.

## 3. 트리거 사용법

- **Keyboard**: Windows 'RegisterHotKey' 사용. **수정키 + 일반 키 한 개**에만 대응합니다. 여러 일반 키를 동시에 지정한 경우는 Studio/Phone 트리거용입니다.
- **Phone / MacroBK Studio**: UDP로 전달된 키 ID를 **등록된 전체 Action**과 대조합니다. 편집 화면에서 선택되지 않은 Action도 실행될 수 있습니다. 동일 ID가 둘 이상이면 설정 목록의 **첫 번째 활성 Action**을 실행합니다.
- 이 소스의 기본 UDP 포트는 **47831**, 트리거 멀티캐스트 주소는 **239.255.77.77**, 인터페이스는 **127.0.0.1**입니다. 다른 장치 또는 호스트 구성에서는 네트워크 설정을 별도로 확인해야 합니다.

패킷 예:

~~~text
TRIGGER|CTRL+WIN:F12
TRIGGER|CTRL+SHIFT:F12
~~~

트리거 ID는 수정키(ALT/CTRL/SHIFT/WIN)와 일반 키들을 정렬해서 결합합니다. 일반 키 다수는 쉼표로 구분합니다. 이전의 평문 'KICAD_DRC'만 보내는 패킷은 현 리스너가 처리하지 않습니다.

**config.example.json**은 공개용 기본 설정 예시이며 실제 사용자 설정은 **config.json**에 저장됩니다.

## 4. Python Action의 실행 방식

Action 스크립트에는 아래 5~7절의 Helper 함수를 **import 없이 직접 사용**할 수 있습니다. Python 코드는 worker thread에서 실행되며 Helper가 wx GUI 접근을 GUI thread로 전달합니다. 고급 코드용 'wx'/'pcbnew' 객체는 제공되지만 **worker에서 wx 위젯에 직접 접근하지 마십시오**.

- 최상위 코드가 실행된 후 스크립트 내 'run()' 함수가 존재하면 추가로 호출합니다.
- 'print(...)' 결과는 Result에 표시됩니다. 스크립트 최상위에 **DEBUG = True**를 적으면 내부 실행 로그도 Result에 표시됩니다.
- **stop_requested()** → bool: Stop 요청 여부
- **wait_or_stop(seconds)** → bool: 최대 seconds초 기다리고 Stop 요청 시 True
- Stop은 스크립트의 실행 줄 및 Helper 호출 전후에서 확인됩니다. 'time.sleep()', 외부 모듈, 네이티브 호출, 모달 창을 강제 종료하지는 못합니다.
- GUI 작업은 중지 또는 시간 제한 이후에도 이미 시작되었다면 취소·롤백되지 않을 수 있습니다.

~~~python
DEBUG = False

def run():
    for n in range(5):
        if wait_or_stop(0.5):
            print("Stopped")
            return
        print("Step", n)
~~~

## 5. PCB 기능별 함수 목록

이 표의 함수는 **Python Script 입력란에서 그대로 호출하는 공개 Helper**입니다.

### 5.1 선택 필터

| 함수 | 파라미터 | 반환값/효과 |
| --- | --- | --- |
| 'pcb_select_filter(name, value=None)' | name: 필터명(str); value: None/True/False | None이면 현재 bool 조회, bool 지정 시 상태 변경 |
| 'pcb_select_filter_state()' | 없음 | 모든 항목의 현재 상태 dict |

지원 name: 'All items', 'Locked items', 'Footprints', 'Text', 'Tracks', 'Vias', 'Pads', 'Graphics', 'Zones', 'Rule Areas', 'Dimensions', 'Other items'. 'All items' 변경은 'Locked items'에 영향을 주지 않습니다.

~~~python
print(pcb_select_filter("Tracks"))
pcb_select_filter("Tracks", False)
print(pcb_select_filter_state())
pcb_select_filter("Tracks", True)
~~~

### 5.2 PCB 레이어

| 함수 | 파라미터 | 반환값/효과 |
| --- | --- | --- |
| 'pcb_select_layer(name)' | KiCad 레이어 이름(str), 예: 'F.Cu' | 지정 레이어 선택 |
| 'pcb_get_selected_layer()' | 없음 | 현재 활성 레이어명(str) |
| 'pcb_onoff_layer(name, value=None)' | name: 레이어명; value: None/True/False | 레이어 표시 상태 bool 조회/변경 |
| 'pcb_layer_up()' | 없음 | 이전 활성 Cu 레이어로 이동; 새 레이어명 |
| 'pcb_layer_down()' | 없음 | 다음 활성 Cu 레이어로 이동; 새 레이어명 |

~~~python
pcb_select_layer("F.Cu")
print(pcb_get_selected_layer())
pcb_onoff_layer("B.SilkS", True)
pcb_layer_down()
~~~

'pcb_layer_up/down'은 **활성 *.Cu 레이어만 순환**하며, 비구리 레이어에서는 UP → 마지막 구리층, DOWN → 첫 구리층으로 이동합니다. KiCad Appearance 패널 구조·언어가 변경되면 UI 조회 방식에 영향을 줄 수 있습니다.

### 5.3 배선 폭

| 함수 | 파라미터 | 반환값/효과 |
| --- | --- | --- |
| 'pcb_set_selected_track_width(width_mm)' | width_mm: 양수(float), mm | **선택된 트랙 세그먼트**의 폭 변경; 변경 건수(int) |
| 'pcb_set_routing_track_width(width_mm)' | width_mm: 양수(float), mm | 현재 라우팅의 사용자 폭 설정을 요청; 요청값 반환 |
| 'pcb_set_netclass_track_width()' | 없음 | 사용자 폭 해제·Netclass 폭 사용; 사용 가능 시 현재 폭(mm) |

~~~python
count = pcb_set_selected_track_width(0.30)
print("Changed:", count)

pcb_set_routing_track_width(0.40)
pcb_set_netclass_track_width()
~~~

- 라우팅 폭 변경은 KiCad 네이티브 **Q → Custom Track/Via Size → OK** 경로를 사용합니다. 함수 반환 직후 내부 대화상자 처리가 계속될 수 있으므로 연속 요청을 피하십시오.
- 선택된 트랙 폭 변경은 PCB_VIA 및 선택되지 않은 연결 세그먼트에 적용되지 않습니다. **KiCad Ctrl+Z(Undo) 작동은 실환경에서 검증 후 사용**하십시오.
- 라우팅 중 폭 변경은 **PCB Editor가 포커스를 유지하는 Phone 트리거** 방식으로 먼저 확인하는 것이 좋습니다.

### 5.4 SNAP (Magnetic Points)

| 함수 | 파라미터 | 반환값/효과 |
| --- | --- | --- |
| 'pcb_get_snap_settings(include_choices=False)' | include_choices: bool | 현재 'pads'/'tracks_vias'/'graphics' 상태 dict. True이면 values/choices/source 포함 |
| 'pcb_set_snap_settings(pads=None, tracks_vias=None, graphics=None)' | 각 인수: 문자열 또는 None(변경 없음) | 변경 후 확인된 상태 dict |

선택 값:
- 'pads', 'tracks_vias': **Never**, **When routing tracks**, **Always**
- 'graphics': **Always**, **Never**

~~~python
print(pcb_get_snap_settings())
pcb_set_snap_settings(pads="Always", graphics="Never")
print(pcb_get_snap_settings(include_choices=True))
~~~

SNAP 탭은 Preferences 창을 열지 않고 KiCad 사용자 설정 'pcbnew.json'의 Magnetic Points 항목을 수정한 뒤 'SETTINGS_MANAGER.Load()'로 재로드하고 값을 검증합니다. 실패 시 원래 설정을 복원하려고 시도합니다. **초기 사용 전 KiCad 설정 파일을 백업하고, 변경 시 팝업/종료 현상이 없는지 확인**하십시오.

### 5.5 메뉴 명령 실행 (DRC 예제)

| 함수 | 파라미터 | 반환값/효과 |
| --- | --- | --- |
| 'find_menu_command(path)' | path: 메뉴 경로(str) | 메뉴 명령 스냅샷(path/id) 또는 None |
| 'dispatch_menu_command(command)' | find_menu_command 결과(dict) | 명령 실행 결과(bool) |
| 'open_menu(path)' | 메뉴 경로(str) | 명령 실행 결과(bool) |

~~~python
# 현재 PCB Editor의 Inspect 메뉴에서 DRC 창 열기
open_menu("Inspect -> Design Rules Checker")
~~~

**기존 전용 함수 `open_drc_window()`는 제거했습니다.** DRC 창은 위 `open_menu()` 예제로 실행합니다. 메뉴 텍스트는 **KiCad PCB Editor에 표시되는 메뉴 경로**를 사용하며, 한국어 메뉴를 쓰는 경우에는 해당 언어의 메뉴 경로를 입력해야 합니다. DRC 창을 열더라도 검사가 자동으로 시작되는 것은 아닙니다. 메뉴를 여는 함수는 실제 KiCad 창을 열 수 있으며 일부 메뉴는 모달이므로 작업 중 호출 시 주의하십시오.

## 6. GUI 컨트롤 Helper API

GUI 함수는 **실제 wx 객체가 아닌 dict 형태 스냅샷**을 반환합니다. 'root'는 None(기본 PCB Editor), 창 제목(str), 또는 앞서 얻은 스냅샷입니다. 스냅샷은 현재 창 세션에서만 유효하며 닫힌 창의 참조는 만료됩니다.

| 함수 | 인수 | 반환값/용도 |
| --- | --- | --- |
| 'list_controls(root=None)' | root: 창 제목/스냅샷 | 자식 컨트롤 스냅샷 리스트 |
| 'find_control_info(root=None, control_type=None, label=None, name=None, id=None)' | type은 'CheckBox'/'wx.CheckBox' 형태 | 유일한 매치 스냅샷 또는 None; 다중 매치는 오류 |
| 'find_controls_info(root=None, control_type=None, label=None, name=None, id=None)' | 위와 동일 | 일치하는 모든 스냅샷 리스트 |
| 'get_control_info(control)' | control: 스냅샷(dict) | 최신 정보 dict |
| 'get_control_value(control)' | control: 스냅샷 | 현재 값 |
| 'set_control_value(control, value)' | 스냅샷, 변경 값 | 변경 후 값 |
| 'get_control_value_by_label(label, root=None)' | 라벨, 선택적 root | 값 |
| 'set_control_value_by_label(label, value, root=None)' | 라벨, 값, 선택적 root | 변경 후 값 |
| 'get_control_value_by_name(name, root=None)' | 이름, 선택적 root | 값 |
| 'set_control_value_by_name(name, value, root=None)' | 이름, 값, 선택적 root | 변경 후 값 |
| 'get_control_value_by_id(id, root=None)' | 컨트롤 ID, 선택적 root | 값 |
| 'set_control_value_by_id(id, value, root=None)' | ID, 값, 선택적 root | 변경 후 값 |
| 'candidate_frames()' | 없음 | PCB 후보 Frame 스냅샷 리스트 |
| 'get_pcb_selection_filter_panel()' | 없음 | Selection Filter 패널 스냅샷 또는 None |

하위 호환 이름 **'iter_controls'**, **'find_control'**, **'find_controls'**는 각각 list_controls, find_control_info, find_controls_info와 동일한 **스냅샷**을 반환합니다. 과거 코드처럼 wx 원본 메서드를 호출하면 안 됩니다.

~~~python
panel = get_pcb_selection_filter_panel()
for item in list_controls(panel):
    print(item.get("type"), item.get("label"), item.get("value"))

track_checkbox = find_control_info(
    root=panel,
    control_type="CheckBox",
    label="Tracks",
)
if track_checkbox is not None:
    print(get_control_value(track_checkbox))
~~~

## 7. 개발자용 구성 및 함수 흐름

| 파일 | 주요 책임 |
| --- | --- |
| '__init__.py' | KiCad 로더, 등록 및 서비스 시작 |
| 'bridge.py' | ActionPlugin 진입점, Manager 열기 |
| 'lifecycle.py' | PCB Editor 수명주기, 등록/Worker 소유권 |
| 'trigger_core.py' | 설정·Hotkey·Phone UDP·Python Action 실행·Stop |
| 'ui_manager.py' | Registered Actions, 편집기, Result UI |
| 'key_picker.py' | 단축키 선택 대화상자 |
| 'kicad_controls.py' | KiCad PCB, 레이어, 배선 폭, SNAP 제어 |
| 'gui_helpers.py' | 스냅샷 함수, worker→GUI thread 래핑 |
| 'snap_panel.py' | Appearance 안의 SNAP 탭 |
| 'snap_preferences.py' | KiCad 'pcbnew.json' Magnetic Points 제어 |
| 'icons/' | UI 이미지 |
| 'config.example.json' | 깨끗한 초기 설정 참고 파일 |

흐름: '__init__.py' → 'register_plugin(MacroBKDRCBridge)' → 'start_bridge()' → 'MacroBKService.start()'. 사용자가 Run Test 또는 Trigger를 발생시키면 'trigger_core.execute_python_script(script, source, action_id=None)'가 별도의 worker에서 코드를 실행합니다. GUI 함수는 'gui_helpers.script_api(...)'에서 래핑되어 'call_gui_sync(...)'로 PCB Editor GUI 스레드에 전달됩니다.

실행 중 worker 강제 종료, 명령 실행 중인 모달 창 자동 닫기, KiCad 내부 상태 복구를 보장하지 않습니다. 소스 변경 후 반드시 PCB Editor를 완전히 다시 시작하십시오.

기존 `config.json`에 `open_drc_window()`가 등록되어 있다면 해당 Action의 Python Script도 **`open_menu("Inspect -> Design Rules Checker")`로 수동 변경**하고 Save를 누르십시오. 사용자 설정은 Git에서 관리하지 않으므로 소스 업데이트만으로 기존 Action 내용은 바뀌지 않습니다.

### Run Test 실행 시 Manager 창 위치

Manager는 PCB Editor를 부모 창으로 가지며, `wx.FRAME_FLOAT_ON_PARENT` 스타일로 **PCB Editor 기본 창보다 앞에 유지**됩니다. 이것은 Windows의 전역 Always on Top 설정이 아니며, DRC 등 KiCad가 여는 대화상자는 필요할 때 Manager보다 앞에 나타날 수 있습니다. 새 설정은 **PCB Editor를 완전히 종료한 뒤 재실행**해야 적용됩니다.

## 8. 오류 해결

- **메뉴에 안 보임**: '__init__.py'와 모듈들이 같은 설치 폴더에 있는지 확인하고 PCB Editor 재시작.
- **키보드 트리거 안 됨**: 키 조합 충돌 여부, Windows RegisterHotKey, 'enabled' 설정 확인. 복수 일반 키는 Phone용입니다.
- **Phone 트리거 안 됨**: UDP 47831, 'TRIGGER|' 접두사, 트리거 ID 및 등록 Action 활성화 확인.
- **스크립트가 멈추지 않음**: 'wait_or_stop(seconds)' 사용; time.sleep/네이티브 함수는 강제 중단 불가.
- **SNAP 설정 오류**: KiCad 'pcbnew.json' 값과 KiCad 9 버전을 확인. 작업 전 설정 백업 권장.
- **업데이트 중 설정 분실 우려**: 기존 'config.json'을 Git 작업 전에 백업하고 복구.
- 내부 동작 로그는 호환성 유지를 위해 여전히 'macrobk_drc.log'에 기록됩니다. 이 실행 로그는 GitHub 배포에서 제외합니다.

## 9. 라이선스

Copyright (c) 2026 **BK Systems**.

본 소프트웨어의 코드는 **MIT License**로 배포합니다. 라이선스 전문은 [LICENSE](LICENSE)를 참조하세요. 외부 라이브러리/ KiCad 자체에는 각각의 저작권과 라이선스가 적용됩니다.

이 프로젝트는 BK Systems의 독립 프로젝트이며 KiCad 공식 프로젝트와 제휴·인증을 의미하지 않습니다.
