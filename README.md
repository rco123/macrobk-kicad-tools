# MacroBK KiCad Tools

KiCad PCB Editor에서 Python Action을 등록하고, Windows 단축키 또는 MacroBK Studio의 Phone 명령으로 실행하는 플러그인입니다. DRC 창 열기, 선택 필터, 레이어 선택·표시, 트랙 폭, SNAP 설정을 위한 함수를 제공합니다.

현재 소스 기준 대상은 **Windows / KiCad 9.x PCB Editor**입니다. 다른 버전·운영체제의 실기 동작은 별도 검증이 필요합니다. 라이선스는 [MIT](LICENSE)입니다.

## 목차

- [설치와 실행](#설치와-실행)
- [Action 등록과 실행](#action-등록과-실행)
- [구조와 실행 흐름](#구조와-실행-흐름)
- [스크립트 함수 사용법](#스크립트-함수-사용법)
- [설정과 통신](#설정과-통신)
- [테스트와 문제 해결](#테스트와-문제-해결)
- [정리 범위와 라이선스](#정리-범위와-라이선스)
- [개발자 함수 목록](#개발자-함수-목록)

## 설치와 실행

1. 이 저장소를 내려받습니다.
2. 폴더 이름을 `macrobk_drc_bridge`로 지정하고, 다음 경로 아래에 넣습니다.

   ```text
   %USERPROFILE%\Documents\KiCad\9.0\scripting\plugins\macrobk_drc_bridge\
   ```

3. `__init__.py`, `bridge.py`, 나머지 루트 Python 모듈, `icons/`가 같은 플러그인 폴더 안에 있어야 합니다. `examples/`, `tools/`, `tests/`는 개발·점검용입니다. 저장된 Action이 예제를 참조하는 경우 그 예제도 함께 유지합니다.
4. 기존 설치를 업데이트할 때는 PCB를 저장하고 KiCad 창을 모두 닫은 뒤 파일을 교체합니다. **기존 `config.json`은 백업하고 보존하세요.** 저장소의 파일로 덮어쓰면 개인 Action 설정이 바뀝니다. 신규 설치에서 `config.json` 없이 시작하면 기본 `Open DRC` Action을 메모리에 만들며, Save/Register 시 설정 파일을 저장합니다.
5. PCB Editor를 다시 열고 **Tools → External Plugins → MacroBK Plugin Manager**를 실행합니다. 플러그인 이름은 기존 설치 호환성을 위해 그대로 유지합니다.

플러그인 목록 Refresh는 살아 있는 worker·listener·Manager 모듈을 교체하지 않습니다. 소스 업데이트는 PCB Editor 재시작으로 적용합니다. 저장소에는 아직 PCM 배포용 `metadata.json`이나 패키징 작업이 없습니다. 이 README는 폴더 설치 방식에 대한 설명입니다.

## Action 등록과 실행

1. Manager의 Action 목록에서 기존 항목을 고르거나 Add로 추가합니다. Duplicate는 선택 항목을 복제하고 Delete는 제거합니다.
2. Select Key에서 Ctrl/Alt/Shift/Win과 일반 키를 선택합니다. 일반 키는 최대 4개입니다.
3. Python 편집기에 아래와 같은 스크립트를 넣습니다.

   ```python
   print("DRC 열기:", open_drc_window())
   ```

4. Run Test로 현재 편집 내용을 시험합니다. Save는 설정을 저장하고, Register는 선택된 Action 설정을 반영·저장한 뒤 키보드 listener를 다시 등록합니다.
5. Result 탭에서 출력·traceback을 확인합니다. 실행 중인 Run Test는 Stop으로 협력 중단할 수 있습니다.

**키보드와 Phone의 차이:** Windows `RegisterHotKey`는 수정 키와 일반 키 1개를 지원하므로 키보드는 현재 선택·등록된 Action의 경로를 사용합니다. 일반 키 2~4개 조합은 Phone 전용입니다. Phone은 편집 중인 Action과 관계없이 등록 목록의 모든 enabled Action에서 canonical trigger를 찾아 실행합니다. 중복 trigger는 목록 순서상 첫 enabled Action을 실행하고 로그에 경고를 기록합니다.

스크립트의 최상위 코드는 한 번 실행합니다. 이어서 같은 namespace에 `run`이라는 호출 가능한 함수가 있으면 인자 없이 한 번 호출합니다. 다음 두 패턴 중 하나를 사용하세요. `run()`을 직접 호출하면서 같은 이름의 함수를 남기면 자동 호출과 합쳐 두 번 실행될 수 있습니다.

```python
# 패턴 1: 최상위 코드
print(pcb_get_selected_layer())
```

```python
# 패턴 2: run 함수 정의만 작성
DEBUG = True

def run():
    print(pcb_select_filter_state())
```

## 구조와 실행 흐름

| 파일·폴더 | 역할 |
| --- | --- |
| `__init__.py` | 라이브 모듈 복구, 플러그인 등록, 서비스 시작 |
| `bridge.py` | `pcbnew.ActionPlugin` 진입점. 무거운 모듈은 지연 로드 |
| `lifecycle.py` | 프로세스 단위 서비스, 중복 등록 방지, PCB 창 수명과 종료 정리 |
| `trigger_core.py` | 설정, 로그, 단축키, UDP, Action worker, GUI 호출 bridge |
| `gui_helpers.py` | worker용 GUI 함수 래퍼, plain snapshot, 세션 내 컨트롤 참조 |
| `kicad_controls.py` | GUI thread에서 실행하는 메뉴·필터·레이어·트랙 폭 제어 |
| `snap_preferences.py` | KiCad 자체 `pcbnew.json`의 Magnetic Points 읽기·수정·복구 |
| `snap_panel.py` | Appearance Notebook에 붙이는 SNAP 페이지 |
| `ui_manager.py`, `key_picker.py` | Action 관리 창과 키 선택 대화상자 |
| `icons/` | Manager에서 사용하는 PNG 아이콘 |
| `examples/` | Manager에 넣어 실행하는 레이어·트랙 폭·SNAP 예제 |
| `tools/` | 독립 실행 Phone 패킷 sender와 Windows 점검 명령 |
| `tests/` | worker·수명·UI·설정 transaction·sender 회귀 테스트 |
| `tests/tools/` | 레이어 조사·캡처 비교 도구. 런타임이 import하지 않음 |
| `diagnostics/snap-production/live_test.py` | 기존 config의 절대 경로를 위한 호환 진입점 |
| `config.json` | 사용자 Action과 선택된 항목. 기존 내용을 보존 |

Keyboard / Phone / Run Test → 같은 daemon worker engine → worker용 Helper → GUI thread callback → KiCad 제어 → plain 반환값과 Result 출력 순서입니다. 같은 Action ID가 이미 실행 중이면 추가 실행을 거절합니다. Manager를 닫아도 PCB Editor의 listener와 SNAP 페이지는 유지됩니다. PCB Editor 파괴가 확정되면 소켓·hotkey·타이머·Manager를 정리하고 worker에 중단을 요청합니다. 저장 확인 창에서 Close가 취소되면 서비스는 유지됩니다.

## 스크립트 함수 사용법

아래 함수는 **Manager의 Python Action 안에서 import 없이 호출**할 수 있습니다. `gui_helpers.script_api()`가 GUI 함수를 main thread로 전달합니다. 일반 Python에서 저장소 모듈을 import하는 것만으로 실행 가능한 함수들은 아닙니다.

GUI Helper의 반환값은 `dict`, `list`, `tuple`, 문자열·숫자·bool·None으로 한정합니다. worker로 wx 객체를 반환하지 않습니다. 고급 호환용으로 `wx`, `pcbnew`도 namespace에 있지만, worker에서 wx 창을 직접 조작하는 코드는 안전하지 않습니다.

### DRC와 메뉴

| 함수 | 파라미터 | 반환값·동작 |
| --- | --- | --- |
| `open_drc_window()` | 없음 | 성공 여부 `bool`. DRC 창을 열며, 보드 검사를 자동 실행하지 않음 |
| `open_menu(path)` | `path: str`, 예: `"Preferences -> Preferences"` | 메뉴 검색·이벤트 전달의 성공 여부 `bool` |
| `find_menu_command(path)` | `path: str` | `{"path": 실제경로, "id": 메뉴ID}` 또는 `None` |
| `find_drc_command()` | 없음 | DRC command snapshot 또는 `None` |
| `dispatch_menu_command(command)` | 앞의 검색 함수가 반환한 `dict` | snapshot의 `path`를 다시 검색하여 실행, 성공 여부 `bool` |

```python
command = find_drc_command()
if command is not None:
    print(dispatch_menu_command(command))
```

메뉴 경로는 UI의 실제 메뉴 이름과 맞아야 합니다. 저수준 검색은 `&`, 말줄임표, 탭 뒤 단축키 표기를 정규화합니다. `open_menu()`로 modal 창을 열면 사용자가 닫을 때까지 GUI callback이 끝나지 않을 수 있습니다. **SNAP Helper는 Preferences 메뉴를 열지 않습니다.**

### Selection Filter

| 함수 | 파라미터 | 반환값·동작 |
| --- | --- | --- |
| `pcb_select_filter(name, value=None)` | `name: str`; `value=None`이면 읽기, `True/False`이면 변경 | 현재·변경된 상태 `bool` |
| `pcb_select_filter_state()` | 없음 | 모든 항목의 상태 `dict[str, bool]` |
| `get_pcb_selection_filter_panel()` | 없음 | Tracks CheckBox 부모 Panel의 snapshot 또는 `None` |

지원 이름: `All items`, `Locked items`, `Footprints`, `Text`, `Tracks`, `Vias`, `Pads`, `Graphics`, `Zones`, `Rule Areas`, `Dimensions`, `Other items`.

`All items`는 일반 10개 항목만 제어하며 `Locked items`는 변경하지 않습니다. 읽을 때는 일반 10개가 모두 True인지 반환합니다. 알 수 없는 이름은 `ValueError`, 찾을 수 없는 패널·항목은 `RuntimeError`입니다.

```python
print(pcb_select_filter("Tracks"))
pcb_select_filter("Tracks", False)
pcb_select_filter("All items", True)
pcb_select_filter("Locked items", False)
print(pcb_select_filter_state())
```

현재 구현은 CheckBox `SetValue()`를 사용합니다. 실제 KiCad 선택 모델까지 반영되는지는 보드에서 확인해야 하며, 이 정리 작업에서 추가 이벤트 동작을 바꾸지 않았습니다.

### 레이어

| 함수 | 파라미터 | 반환값·동작 |
| --- | --- | --- |
| `pcb_select_layer(name)` | `name: str`, 예: `F.Cu`, `B.Adhesive`, `Edge.Cuts` | 선택한 레이어 이름 `str`; KiCad 레이블에 native 클릭 이벤트 전달 |
| `pcb_get_selected_layer()` | 없음 | Appearance의 활성 indicator로 판정한 레이어 이름 `str` |
| `pcb_onoff_layer(name, value=None)` | `name: str`; `None` 읽기, `True` 표시, `False` 숨기기 | 실제 표시 상태 `bool` |
| `pcb_layer_up()` | 없음 | enabled Cu stack에서 이전 레이어를 선택하고 이름 `str` 반환 |
| `pcb_layer_down()` | 없음 | enabled Cu stack에서 다음 레이어를 선택하고 이름 `str` 반환 |

```python
print(pcb_select_layer("F.Cu"))
print(pcb_get_selected_layer())
print(pcb_onoff_layer("B.Cu", False))
print(pcb_onoff_layer("B.Cu", True))
print(pcb_layer_down())
```

Cu 이동은 Appearance 순서로 순환합니다. 4층 예: DOWN은 `F.Cu → In1.Cu → In2.Cu → B.Cu → F.Cu`. 현재 레이어가 Cu가 아니면 UP은 마지막 Cu, DOWN은 첫 Cu입니다. 이동 후 선택 indicator를 다시 읽어 검증합니다.

활성 레이어 getter는 첫 indicator bitmap의 effective alpha가 16보다 큰 픽셀을 확인합니다. near-transparent 픽셀, focus, 배경색, 마지막 요청값을 선택 근거로 사용하지 않습니다. 선택 indicator가 없거나 둘 이상이면 `RuntimeError`로 실패합니다. 테마·DPI·KiCad 버전에서 재검증이 필요합니다.

### 트랙 폭

| 함수 | 파라미터 | 반환값·동작 |
| --- | --- | --- |
| `pcb_set_selected_track_width(width_mm)` | `width_mm`: 0보다 큰 mm 숫자 | 실제 폭이 바뀐 선택 트랙 수 `int`. VIA와 미선택 연결 세그먼트 제외 |
| `pcb_set_routing_track_width(width_mm)` | `width_mm`: 0보다 큰 mm 숫자 | 요청 폭 `float`. native Q 대화상자 처리는 wx 타이머로 비동기 진행 |
| `pcb_set_netclass_track_width()` | 없음 | 현재 폭을 mm `float`로 반환; 변환 실패 시 내부 단위 숫자. netclass/rule 폭으로 복귀 |

```python
# 이미 배선된 트랙을 선택한 후
print(pcb_set_selected_track_width(0.40))
```

```python
# 라우팅 중 Phone Action으로 실행 권장
print(pcb_set_routing_track_width(0.75))
```

`pcb_set_routing_track_width()`는 Windows Q 키 → KiCad Custom Track/Via Size → Track width 필드에 mm 명시 → native OK 순서로 처리합니다. VIA 필드는 보존하고 전체 `pcbnew.Refresh()`를 호출하지 않습니다. 반환은 **완료 확인이 아니라 접수된 요청값**이며, 완료 전 다음 요청은 거절됩니다. 이후 실패는 로그에서 확인합니다. Phone 입력은 Manager로 focus를 옮기지 않아 라우팅 중 시험에 적합합니다.

`pcb_set_netclass_track_width()`는 기존 트랙을 바꾸지 않지만 KiCad의 공유 custom track/via flag를 해제하므로 custom via-size 모드도 해제됩니다. 선택 트랙 폭 변경은 public item mutation API를 사용하며, native undo transaction을 보장하지 않습니다. 필요한 Ctrl+Z 동작은 실기에서 확인하세요.

### SNAP / Magnetic Points

| 함수 | 파라미터 | 반환값·동작 |
| --- | --- | --- |
| `pcb_get_snap_settings(include_choices=False)` | `include_choices: bool` | 기본: 세 설정의 문자열 `dict`. True: `values`, `choices`, `source`가 있는 payload |
| `pcb_set_snap_settings(pads=None, tracks_vias=None, graphics=None)` | 각 값은 아래 지원 문자열 또는 `None` | 변경을 저장·검증한 세 설정의 문자열 `dict`. `None`은 유지 |

| 키 | 허용 값 |
| --- | --- |
| `pads` | `Never`, `When routing tracks`, `Always` |
| `tracks_vias` | `Never`, `When routing tracks`, `Always` |
| `graphics` | `Always`, `Never` |

```python
print(pcb_get_snap_settings())
# 예: {'pads': 'Always', 'tracks_vias': 'Never', 'graphics': 'Always'}
print(pcb_get_snap_settings(include_choices=True))
pcb_set_snap_settings(pads="Never")
pcb_set_snap_settings(tracks_vias="When routing tracks", graphics="Never")
```

Appearance의 `Layers`, `Objects`, `Nets`에 `SNAP` 페이지를 추가합니다. native 페이지는 재배치하지 않습니다. SNAP 진입 시 저장값을 읽으며 Refresh 버튼이 없습니다. Choice 변경 후 검증된 값을 다시 표시합니다. 기존의 다른 플러그인이 소유한 SNAP 페이지는 덮어쓰지 않습니다.

backend는 `%APPDATA%\kicad\9.0\pcbnew.json`의 `magnetic_pads`, `magnetic_tracks`, `magnetic_graphics` scalar만 수정하고 atomic replace 뒤 `pcbnew.GetSettingsManager().Load()`를 GUI thread에서 호출합니다. unrelated JSON 텍스트를 보존하며, reload·파일 검증 실패 시 원문을 복구하고 재로드를 시도합니다. 복구 자체가 실패하면 로그에 남깁니다.

반환값은 **파일을 다시 읽어 확인한 값**입니다. 실제 canvas의 snapping 동작을 측정한 결과는 아닙니다. 동시에 열린 Preferences의 저장 전 초안과 별도 편집기 쓰기 간 충돌을 조정하는 기능은 없습니다. 실제 동작·modal dialog 미발생·KiCad가 종료되지 않는지는 실기 acceptance 항목입니다.

### GUI 컨트롤 검색·읽기·쓰기

공통 `root`는 `None`, 고유한 top-level 창 제목 부분 문자열, 또는 앞서 검색한 control snapshot입니다. 기본 제목은 `PCB Editor`입니다. 제목이 중복되면 `RuntimeError`입니다. `control_type`은 `"CheckBox"` 또는 `"wx.CheckBox"` 같은 문자열이고, `label`·`name`은 정규화된 정확 일치, `id`는 정수 ID 일치입니다. 여러 조건은 모두 만족해야 합니다.

| 함수 | 파라미터 | 반환값·동작 |
| --- | --- | --- |
| `list_controls(root=None)` | 공통 root | 모든 하위 컨트롤 snapshot `list[dict]`; root 자체는 제외 |
| `find_controls_info(root=None, control_type=None, label=None, name=None, id=None)` | root와 선택 필터 | 일치 snapshot 목록; 없으면 `[]` |
| `find_control_info(root=None, control_type=None, label=None, name=None, id=None)` | 위와 같음 | 1개면 `dict`, 0개면 `None`, 2개 이상이면 오류 |
| `get_control_info(control)` | snapshot 또는 창 제목 | 새 snapshot `dict` |
| `get_control_value(control)` | snapshot 또는 창 제목 | CheckBox/RadioButton: `bool`; Choice/ComboBox/TextCtrl: `str`; 기타: `None` |
| `set_control_value(control, value)` | snapshot 또는 창 제목, 지원 값 | 변경 후 읽은 값; 미지원 타입·없는 Choice 항목은 오류 |
| `get_control_value_by_label(label, root=None)` | `label: str`, root | 고유 컨트롤의 값 |
| `set_control_value_by_label(label, value, root=None)` | 위와 값 | 변경 후 값 |
| `get_control_value_by_name(name, root=None)` | `name: str`, root | 고유 컨트롤의 값 |
| `set_control_value_by_name(name, value, root=None)` | 위와 값 | 변경 후 값 |
| `get_control_value_by_id(id, root=None)` | `id: int`, root | 고유 컨트롤의 값 |
| `set_control_value_by_id(id, value, root=None)` | 위와 값 | 변경 후 값 |
| `candidate_frames()` | 없음 | 메뉴를 가진 후보 frame snapshot 목록 |

snapshot 필드: `type`, `class`, `name`, `label`, `id`, `value`, `enabled`, `visible`, `title`, `_control_ref`.`_control_ref`는 opaque 참조이며 session/window 수명 동안만 유효합니다. 창 파괴나 10,000개 참조 제한의 오래된 항목 제거 후에는 재검색해야 합니다. snapshot을 파일에 저장해서 다음 실행의 컨트롤 핸들로 쓰지 마세요.

```python
panel = get_pcb_selection_filter_panel()
if panel is not None:
    for info in list_controls(panel):
        print(info["type"], info["label"], info["value"])
    tracks = find_control_info(panel, control_type="CheckBox", label="Tracks")
    if tracks is not None:
        print(get_control_value(tracks))
        print(set_control_value(tracks, True))
```

호환 별칭 `iter_controls(root=None)`, `find_control(...)`, `find_controls(...)`는 각각 `list_controls`, `find_control_info`, `find_controls_info`와 같은 파라미터·반환 규칙을 사용합니다. 예전처럼 반환값에 `GetValue()` 등 wx 메서드를 직접 호출하지 마세요.

### 중단과 출력

| 함수·변수 | 파라미터 | 동작 |
| --- | --- | --- |
| `stop_requested()` | 없음 | 해당 worker의 Stop event 상태 `bool` |
| `wait_or_stop(seconds)` | 숫자 초 | 시간이 끝나면 False, Stop 요청으로 깨어나면 True |
| `print(*args, sep=" ", end="\n", file=None, flush=False)` | 일반 print 인자 | Action print를 Result에 비동기 출력. 별도 file 출력은 builtins.print 사용 |
| `DEBUG = True` | 최상위 literal 대입 | Action 시작 전에 읽고 source/action/run/thread/helper 진단 출력 활성화 |

```python
print("WAIT")
if wait_or_stop(10):
    print("STOP REQUESTED")
```

Stop은 강제로 Python/native thread를 죽이지 않습니다. 사용자 스크립트 줄 사이에서 trace로 확인하며, `time.sleep()`나 native call이 끝나야 중단될 수 있습니다. `wait_or_stop()`로 Stop을 확인한 스크립트는 자체적으로 신속히 종료해야 합니다. Helper는 GUI 호출 전후에도 중단을 확인하므로 Stop 뒤 `finally`에서 GUI 복구를 실행한다고 보장할 수 없습니다. 필요한 영구 설정 복구는 별도 Action으로 실행합니다.

GUI 동기 호출은 50 ms 간격으로 기다리고 기본 10초 timeout입니다. 아직 시작하지 않은 callback은 중단/timeout 이후 생략되지만 이미 실행 중인 GUI 작업은 되돌릴 수 없습니다. Run Test의 Stop 대상은 실행 시작한 Action/run이며 다른 항목을 선택해도 바뀌지 않습니다. `SystemExit`, `KeyboardInterrupt`는 ERROR로 보고됩니다. imported library의 `sys.stdout` 직접 출력은 Result print 대체로 잡히지 않을 수 있습니다.

### 기존 Preferences 조사 함수

이미 저장된 스크립트 호환성을 위해 다음 diagnostic Helper를 유지합니다. SNAP 설정에는 사용하지 않습니다. 모두 인자 없이 호출하며 Preferences 메뉴를 여는 요청의 성공 여부 `bool`을 반환합니다. 조사·출력은 타이머로 이어집니다.

| 함수 | 동작 |
| --- | --- |
| `test_preferences_direct_children()` | Preferences의 직접 자식 컨트롤을 로그에 출력 |
| `test_preferences_control_tree()` | Preferences 컨트롤 트리를 로그에 출력 |
| `test_preferences_checkbox_value()` | `Show icons in menus` CheckBox 값을 로그에 출력 |
| `test_preferences_checkbox_toggle_restore()` | 해당 CheckBox를 변경한 뒤 원래 값 복구 시도 |

이 함수들은 locale·창 이름과 lifetime에 의존하는 개발 조사 코드입니다. 일반 Action은 위의 기능별 Helper를 사용하세요.

## 설정과 통신

`config.json`은 plugin root에서 읽고 Save/Register 시 `.tmp` 후 `os.replace()`로 저장합니다. 기존 설정의 확장 metadata를 유지합니다. 주요 구조는 다음과 같습니다.

| 필드 | 설명 |
| --- | --- |
| `actions` | Action dict 목록 |
| `actions[].id` | worker 실행·선택을 식별하는 문자열 |
| `actions[].name`, `icon` | 표시 이름, `icons/`의 아이콘 이름 |
| `actions[].trigger.enabled` | trigger 매칭·등록 활성 여부 |
| `actions[].trigger.ctrl/alt/shift/win` | modifier bool |
| `actions[].trigger.keys` | 일반 키 1~4개 문자열 목록 |
| `actions[].trigger.key` | 기존 single-key 호환 필드 |
| `actions[].action.type/script` | Python 실행 유형과 script 문자열 |
| `selected_action_id` | 선택·등록한 Action ID |
| 최상위 `name/trigger/phone/action` | 선택 Action을 반영하는 기존 호환 필드 |
| `phone` / `actions[].phone` | 이전 설정 호환 metadata. 현재 listener 주소는 아래 코드 상수 사용 |

저장소에 포함된 config는 기존 사용자 설정이므로 일반 배포 기본값이라고 가정하지 않습니다. 특정 Windows 절대 경로를 포함한 TEST Action이 있습니다. 다른 PC에서는 자신의 설치 경로로 해당 Action을 수정하거나 새 Action을 등록하세요.

Phone UDP 설정:

| 항목 | 값 |
| --- | --- |
| multicast group | `239.255.77.77` |
| UDP port | `47831` |
| 가입 interface | `127.0.0.1` |
| payload | UTF-8 `TRIGGER\|<canonical ID>` |
| canonical 예 | `CTRL+SHIFT:F12`, `ALT+CTRL+SHIFT+WIN:A,B,C,F2` |

modifier와 일반 키는 대문자로 정렬·중복 제거합니다. receiver는 `TRIGGER|` 뒤 문자열을 canonical ID와 직접 비교하며 임의의 표기 순서를 자동 정규화하지 않습니다. 예전 plain `KICAD_DRC` 패킷은 받지 않습니다.

```powershell
# 실제 전송 없이 설정에서 고른 packet 확인
& 'C:\Program Files\KiCad\9.0\bin\python.exe' -B tools/phone_trigger_test.py --dry-run

# 직접 trigger 지정, 또는 --config로 별도 설정 지정 가능
& 'C:\Program Files\KiCad\9.0\bin\python.exe' -B tools/phone_trigger_test.py 'CTRL+SHIFT:F12' --dry-run

# 실제 Action 실행을 시험할 때 --dry-run 제거
.\tools\test_phone.cmd 'CTRL+SHIFT:F12'
```

sender의 `SENT`는 datagram 전송만 의미합니다. 수신·매칭·실행 결과는 `macrobk_drc.log`와 Result를 확인합니다. `ACTION START`·종료 진단은 `DEBUG=True`인 script에서 추가됩니다.

## 테스트와 문제 해결

### 자동 테스트

일반 Python에서 실행 가능한 테스트:

```powershell
python -B -m unittest discover -s tests -p 'test_snap_preferences.py' -v
python -B -m unittest discover -s tests -p 'test_phone_sender.py' -v
```

KiCad Python과 wx 환경에서 전체 테스트:

```powershell
& 'C:\Program Files\KiCad\9.0\bin\python.exe' -B -m unittest discover -s tests -p 'test_*.py' -v
```

| 테스트 파일 | 검증 내용 |
| --- | --- |
| `test_snap_preferences.py` | 임시 JSON의 부분 변경·모든 Choice·unrelated 텍스트 보존·atomic write·reload/검증 실패 복구·GUI thread 제한 |
| `test_phone_sender.py` | canonical ID, selected Action, disabled/empty trigger, `--config`, dry-run CLI |
| `test_worker_engine.py` | 실제 wx fixture Manager, worker·Result·Stop·snapshot·Phone 전체 목록 매칭 |
| `test_lifecycle.py` | 서비스 중복 시작, reload, 창 수명, socket/hotkey/worker 정리 |
| `test_snap_panel.py` | JSON backend 계약을 모사한 UI fixture, verified 표시, 실패·파괴·중복 탭 |
| `test_layer_diagnostics.py` | 실제 wx bitmap fixture와 캡처 비교 mechanics |

테스트는 임시 config/log/settings를 사용합니다. wx/pcbnew가 없는 환경에서 전체 discover를 실행하면 해당 integration 모듈은 **skip**으로 표시되며, 실제 KiCad 검증 통과를 뜻하지 않습니다. SNAP backend 단독 테스트의 native manager는 주입된 mock이며 canvas 동작을 검증하지 않습니다.

이 정리 브랜치의 검증 환경은 KiCad/wx가 없는 Linux 작업 환경입니다. portable 테스트 19개 통과, integration 모듈 4개 skip입니다. 전체 Python 구문, 문서 API 목록, config 원문 보존 및 diff도 확인합니다. Windows KiCad에서 전체 suite와 다음 acceptance 항목은 별도로 실행해야 합니다.

### 실제 PCB acceptance

1. Manager 열기, Action 저장/복제/삭제, Run Test 출력·traceback·Stop을 확인합니다.
2. 키보드와 Phone 입력을 각각 시험합니다. Phone은 현재 편집 항목이 아닌 enabled Action도 매칭되는지 확인합니다.
3. SNAP 페이지를 선택·변경하여 추가 창이 열리지 않고 실제 pad/track/graphics snapping이 바뀌는지 확인합니다.
4. `examples/layer_function_test.py`와 `examples/layer_updown_test.py`의 내용을 Manager에 넣어 실행합니다. 활성 indicator, 표시 eye와 canvas 변화를 확인합니다.
5. 라우팅을 X로 시작한 상태에서 Phone으로 `pcb_set_routing_track_width(0.40)`를 실행합니다. preview가 유지되고 변경 지점 이후 폭만 바뀌는지 확인합니다. native transaction 완료 후 0.75 mm로 반복합니다.
6. Manager 닫기/다시 열기, PCB 닫기 취소, PCB 닫기/다시 열기를 시험합니다.

SNAP round trip은 Manager Action에서 다음처럼 실행할 수도 있습니다. 원래 설정 복구를 시도하므로 실행 중 Stop하지 말고 완료를 기다리세요.

```python
import runpy
runpy.run_path(
    r"C:\Users\YOUR_USER\Documents\KiCad\9.0\scripting\plugins\macrobk_drc_bridge\examples\snap_settings.py",
    run_name="__main__",
)
```

### 점검 도구

```powershell
.\tools\check_port.cmd
.\tools\check_hotkey.cmd
```

`check_port.cmd`는 UDP 47831 사용 프로세스를 보여 줍니다. `check_hotkey.cmd`는 기본 `Ctrl+Win+F12`만 검사하며 사용자 설정의 임의 조합을 읽지는 않습니다. 충돌하면 PCB를 저장하고 KiCad 창을 모두 닫은 뒤 포트가 해제됐는지 확인하고 하나의 PCB Editor를 다시 엽니다.

레이어 read-only 조사 도구는 `tests/tools/layer_diagnostics.py`, 캡처 비교기는 `tests/tools/compare_layer_dumps.py`입니다. Scripting Console에서 tools 폴더를 `sys.path`에 넣고 `layer_diagnostics.show_diagnostic_panel()`을 호출합니다. JSON은 `tests/tools/evidence/`에 저장합니다. 비교 예:

```powershell
python -B tests/tools/compare_layer_dumps.py F.Cu.json B.Cu.json F.Adhesive.json Edge.Cuts.json
```

비교기의 candidate는 관찰 후보이며 실제 getter 검증을 대신하지 않습니다.

| 증상 | 확인할 내용 |
| --- | --- |
| 메뉴에 플러그인이 없음 | 폴더 구조, `pcbnew` 로딩, PCB 재시작, 로딩 오류 메시지 |
| 키보드가 안 됨 | enabled, 일반 키 수, HotKey Conflict/Phone Only/Unavailable, 다른 앱의 키 점유 |
| Phone이 안 됨 | packet prefix, canonical ID, enabled Action 목록, UDP port/다른 KiCad 인스턴스 |
| 소스를 교체했는데 이전 동작 | 모든 KiCad 창을 닫고 재시작; Refresh만으로 live engine을 교체하지 않음 |
| SNAP 값 오류 | 해당 버전 `pcbnew.json`, 키 유일성, SettingsManager API와 로그 |
| 레이어 선택 오류 | Appearance visible, 실제 레이어 이름, bitmap indicator의 theme/DPI 차이 |
| routing width 중복 오류 | 이전 Q 대화상자 transaction이 끝났는지, 실제 canvas focus |

## 정리 범위와 라이선스

- 루트의 수동 테스트 스크립트는 `examples/`, 독립 점검 명령은 `tools/`로 이동했습니다.
- 레이어 조사 코드는 `tests/tools/`로 이동하고 테스트 참조·출력 경로를 맞췄습니다.
- 중복 README·함수 설명·이전 수명 분석·작업 경로 보고서는 이 README로 통합했습니다.
- 실행 로그, 지난 테스트 결과, 캡처 JSON, 조사 중 내려받은 KiCad C++/헤더 소스 사본과 오래된 probe를 제거했습니다. 필요하면 Git 이력에서 확인할 수 있습니다.
- 기존 `config.json`과 공개 Action Helper를 보존했습니다. config가 참조하는 legacy SNAP live-test 경로는 얇은 호환 wrapper로 유지하고, 제거된 Preferences API를 호출하던 예제를 현재 backend로 바꿨습니다.
- 예전 Preferences dialog backend용 SNAP tests는 현재 backend·UI 계약으로 교체했습니다. worker/lifecycle 회귀 테스트는 유지하고 테스트 설정 파일은 임시 경로로 격리했습니다.
- 사용되지 않는 private `_pcb_active_layer_name` 별칭을 제거했습니다.

MacroBK 소스는 [MIT License](LICENSE)로 제공합니다. 제거한 KiCad 소스 조사 사본을 MIT로 재라이선스하지 않습니다. KiCad와 wxPython 등 외부 프로그램·라이브러리는 각자의 라이선스를 따릅니다. 이 변경은 PCM 배포 완료나 KiCad 실기 검증 완료를 의미하지 않습니다.

## 개발자 함수 목록

위의 사용법은 **Action namespace에 공개된 모든 GUI Helper와 worker 제어 함수**를 다룹니다. 아래는 유지보수용 runtime 모듈의 전체 module-level 함수와 class method signature 목록입니다. `_`로 시작하는 구현 함수와 event handler는 일반 Action API가 아니며, 직접 worker에서 호출하지 않습니다. 시험·도구 함수는 해당 파일의 CLI 또는 fixture를 통해 사용합니다.

- `bridge`: KiCad 등록 시 GUI entry에서 `start_bridge()`, `show_manager()`를 호출합니다.
- `lifecycle`: `register_plugin(factory)`는 ActionPlugin factory, `get_service(core=None)`는 engine을 받습니다. `MacroBKService`가 socket/thread/frame을 소유합니다. Refresh 때 살아 있는 모듈 generation을 복구합니다.
- `trigger_core`: `execute_python_script(script, source, action_id=None)`는 비동기 시작 성공 `bool`; `is_action_running(action_id, source="action")`, `stop_action(action_id, source="action", run_id=None)`는 실행 조회·중단 요청입니다. source는 `test`, `keyboard`, `phone`을 사용합니다. `call_gui_sync(function, *args, timeout=10.0, **kwargs)`는 callback 결과를 반환하고 `call_gui_async(...)`는 큐잉만 합니다. user script는 이 구현 대신 공개 Helper를 사용합니다.
- `gui_helpers`: `script_api(call_sync, check_stop)`는 두 callback으로 GUI Helper name→wrapper dict를 만듭니다.
- `kicad_controls`: 아래 low-level 함수는 raw wx 객체를 사용하며 GUI thread 전용입니다. 동일한 이름의 Action Helper와 파라미터가 다를 수 있습니다. 예를 들어 low-level `dispatch_menu_command(owner_menu, item, frame=None)`는 Action snapshot 버전과 다릅니다.
- `snap_preferences`: `request(changes=None, include_choices=False)`는 GUI 전용 transaction; `read_saved_settings(include_choices=False)`는 저장값 reader; `settings_path()`는 버전별 경로입니다.
- `snap_panel`: `attach_snap_tab(frame)`은 owned page/None, `remove_snap_tab(frame)`은 owned page만 정리합니다.
- `ui_manager`, `key_picker`: 생성자 `parent`는 wx 부모 창이며 `current_value`는 표시용 단축키 문자열입니다. `on_*` 함수의 event 인자는 wx binding에서 전달합니다.


### bridge.py

| 함수·메서드 signature | 코드 |
| --- | --- |
| `_show_load_error(title, exc)` | [bridge.py:6](bridge.py#L6) |
| `start_bridge()` | [bridge.py:22](bridge.py#L22) |
| `show_manager()` | [bridge.py:45](bridge.py#L45) |
| `MacroBKDRCBridge.defaults(self)` | [bridge.py:67](bridge.py#L67) |
| `MacroBKDRCBridge.Run(self)` | [bridge.py:73](bridge.py#L73) |

### lifecycle.py

| 함수·메서드 signature | 코드 |
| --- | --- |
| `get_service(core=None)` | [lifecycle.py:19](lifecycle.py#L19) |
| `restore_modules(package)` | [lifecycle.py:29](lifecycle.py#L29) |
| `engine(default)` | [lifecycle.py:38](lifecycle.py#L38) |
| `register_plugin(factory)` | [lifecycle.py:43](lifecycle.py#L43) |
| `release_plugin_registration()` | [lifecycle.py:59](lifecycle.py#L59) |
| `MacroBKService.__init__(self, core)` | [lifecycle.py:74](lifecycle.py#L74) |
| `MacroBKService.remember_modules(self)` | [lifecycle.py:95](lifecycle.py#L95) |
| `MacroBKService.log(self, message)` | [lifecycle.py:103](lifecycle.py#L103) |
| `MacroBKService.start(self)` | [lifecycle.py:107](lifecycle.py#L107) |
| `MacroBKService.attach_frame(self)` | [lifecycle.py:163](lifecycle.py#L163) |
| `MacroBKService.attach_snap_tab(self)` | [lifecycle.py:187](lifecycle.py#L187) |
| `MacroBKService.on_frame_close(self, event)` | [lifecycle.py:199](lifecycle.py#L199) |
| `MacroBKService.on_frame_destroy(self, event)` | [lifecycle.py:205](lifecycle.py#L205) |
| `MacroBKService.shutdown(self)` | [lifecycle.py:213](lifecycle.py#L213) |

### trigger_core.py

| 함수·메서드 signature | 코드 |
| --- | --- |
| `set_manager_provider(provider)` | [trigger_core.py:89](trigger_core.py#L89) |
| `get_keyboard_status()` | [trigger_core.py:93](trigger_core.py#L93) |
| `get_phone_status()` | [trigger_core.py:96](trigger_core.py#L96) |
| `_default_config_copy()` | [trigger_core.py:99](trigger_core.py#L99) |
| `bind_gui_thread()` | [trigger_core.py:103](trigger_core.py#L103) |
| `_is_gui_thread()` | [trigger_core.py:109](trigger_core.py#L109) |
| `_check_stop()` | [trigger_core.py:115](trigger_core.py#L115) |
| `get_service()` | [trigger_core.py:121](trigger_core.py#L121) |
| `_callback_epoch()` | [trigger_core.py:126](trigger_core.py#L126) |
| `_callbacks_allowed(epoch)` | [trigger_core.py:132](trigger_core.py#L132) |
| `shutdown_service()` | [trigger_core.py:138](trigger_core.py#L138) |
| `call_gui_async(function, *args, **kwargs)` | [trigger_core.py:142](trigger_core.py#L142) |
| `call_gui_sync(function, *args, timeout=10.0, **kwargs)` | [trigger_core.py:158](trigger_core.py#L158) |
| `_append_result(line)` | [trigger_core.py:199](trigger_core.py#L199) |
| `log(message)` | [trigger_core.py:209](trigger_core.py#L209) |
| `debug_log(message, enabled=False)` | [trigger_core.py:233](trigger_core.py#L233) |
| `error_result(message)` | [trigger_core.py:240](trigger_core.py#L240) |
| `_script_debug_enabled(script)` | [trigger_core.py:245](trigger_core.py#L245) |
| `load_config()` | [trigger_core.py:269](trigger_core.py#L269) |
| `save_config()` | [trigger_core.py:361](trigger_core.py#L361) |
| `virtual_key_code(name)` | [trigger_core.py:373](trigger_core.py#L373) |
| `trigger_keys(trigger)` | [trigger_core.py:408](trigger_core.py#L408) |
| `hotkey_description(trigger)` | [trigger_core.py:425](trigger_core.py#L425) |
| `trigger_id(trigger)` | [trigger_core.py:440](trigger_core.py#L440) |
| `parse_hotkey_description(value)` | [trigger_core.py:457](trigger_core.py#L457) |
| `set_keyboard_status(status)` | [trigger_core.py:499](trigger_core.py#L499) |
| `set_phone_status(status)` | [trigger_core.py:507](trigger_core.py#L507) |
| `hotkey_worker(trigger, generation)` | [trigger_core.py:515](trigger_core.py#L515) |
| `stop_hotkey_listener()` | [trigger_core.py:610](trigger_core.py#L610) |
| `start_hotkey_listener()` | [trigger_core.py:637](trigger_core.py#L637) |
| `restart_hotkey_listener()` | [trigger_core.py:665](trigger_core.py#L665) |
| `_worker_key(action_id, source)` | [trigger_core.py:670](trigger_core.py#L670) |
| `is_action_running(action_id, source='action')` | [trigger_core.py:674](trigger_core.py#L674) |
| `stop_action(action_id, source='action', run_id=None)` | [trigger_core.py:682](trigger_core.py#L682) |
| `_script_print(*args, **kwargs)` | [trigger_core.py:702](trigger_core.py#L702) |
| `_notify_test(manager, key, run_id, status)` | [trigger_core.py:728](trigger_core.py#L728) |
| `_execute_python_script_worker(script, source, key, run_id, stop_event, debug, manager)` | [trigger_core.py:744](trigger_core.py#L744) |
| `execute_python_script(script, source, action_id=None)` | [trigger_core.py:806](trigger_core.py#L806) |
| `handle_trigger(source)` | [trigger_core.py:845](trigger_core.py#L845) |
| `parse_phone_packet(data)` | [trigger_core.py:856](trigger_core.py#L856) |
| `find_action_by_trigger(received_trigger)` | [trigger_core.py:869](trigger_core.py#L869) |
| `handle_phone_trigger(received)` | [trigger_core.py:892](trigger_core.py#L892) |
| `udp_worker(service, sock, stop_event, epoch)` | [trigger_core.py:912](trigger_core.py#L912) |
| `start_bridge()` | [trigger_core.py:943](trigger_core.py#L943) |

### gui_helpers.py

| 함수·메서드 signature | 코드 |
| --- | --- |
| `_snapshot(control)` | [gui_helpers.py:17](gui_helpers.py#L17) |
| `_resolve(reference=None)` | [gui_helpers.py:29](gui_helpers.py#L29) |
| `list_controls(root=None)` | [gui_helpers.py:45](gui_helpers.py#L45) |
| `find_controls_info(root=None, control_type=None, label=None, name=None, id=None)` | [gui_helpers.py:50](gui_helpers.py#L50) |
| `find_control_info(root=None, control_type=None, label=None, name=None, id=None)` | [gui_helpers.py:57](gui_helpers.py#L57) |
| `get_control_info(control)` | [gui_helpers.py:64](gui_helpers.py#L64) |
| `get_control_value(control)` | [gui_helpers.py:68](gui_helpers.py#L68) |
| `set_control_value(control, value)` | [gui_helpers.py:72](gui_helpers.py#L72) |
| `_value_by(root, criterion, selector, value=None, write=False)` | [gui_helpers.py:78](gui_helpers.py#L78) |
| `get_control_value_by_label(label, root=None)` | [gui_helpers.py:85](gui_helpers.py#L85) |
| `set_control_value_by_label(label, value, root=None)` | [gui_helpers.py:89](gui_helpers.py#L89) |
| `get_control_value_by_name(name, root=None)` | [gui_helpers.py:93](gui_helpers.py#L93) |
| `set_control_value_by_name(name, value, root=None)` | [gui_helpers.py:97](gui_helpers.py#L97) |
| `get_control_value_by_id(id, root=None)` | [gui_helpers.py:101](gui_helpers.py#L101) |
| `set_control_value_by_id(id, value, root=None)` | [gui_helpers.py:105](gui_helpers.py#L105) |
| `candidate_frames()` | [gui_helpers.py:109](gui_helpers.py#L109) |
| `get_pcb_selection_filter_panel()` | [gui_helpers.py:113](gui_helpers.py#L113) |
| `find_menu_command(path)` | [gui_helpers.py:118](gui_helpers.py#L118) |
| `find_drc_command()` | [gui_helpers.py:123](gui_helpers.py#L123) |
| `dispatch_menu_command(command)` | [gui_helpers.py:128](gui_helpers.py#L128) |
| `open_drc_window()` | [gui_helpers.py:134](gui_helpers.py#L134) |
| `_plain(value)` | [gui_helpers.py:138](gui_helpers.py#L138) |
| `script_api(call_sync, check_stop)` | [gui_helpers.py:148](gui_helpers.py#L148) |

### kicad_controls.py

| 함수·메서드 signature | 코드 |
| --- | --- |
| `set_logger(logger)` | [kicad_controls.py:11](kicad_controls.py#L11) |
| `log(message)` | [kicad_controls.py:15](kicad_controls.py#L15) |
| `norm_label(value)` | [kicad_controls.py:18](kicad_controls.py#L18) |
| `iter_controls(root)` | [kicad_controls.py:32](kicad_controls.py#L32) |
| `_matches_control_type(control, control_type)` | [kicad_controls.py:38](kicad_controls.py#L38) |
| `find_controls(root, control_type=None, label=None, name=None, id=None)` | [kicad_controls.py:47](kicad_controls.py#L47) |
| `find_control(root, control_type=None, label=None, name=None, id=None)` | [kicad_controls.py:62](kicad_controls.py#L62) |
| `get_control_value(control)` | [kicad_controls.py:77](kicad_controls.py#L77) |
| `set_control_value(control, value)` | [kicad_controls.py:87](kicad_controls.py#L87) |
| `get_control_info(control)` | [kicad_controls.py:102](kicad_controls.py#L102) |
| `pcb_get_snap_settings(include_choices=False)` | [kicad_controls.py:116](kicad_controls.py#L116) |
| `pcb_set_snap_settings(pads=None, tracks_vias=None, graphics=None)` | [kicad_controls.py:126](kicad_controls.py#L126) |
| `is_drc_label(label)` | [kicad_controls.py:137](kicad_controls.py#L137) |
| `candidate_frames()` | [kicad_controls.py:152](kicad_controls.py#L152) |
| `find_pcb_frame()` | [kicad_controls.py:166](kicad_controls.py#L166) |
| `call_later(delay, callback, *args)` | [kicad_controls.py:188](kicad_controls.py#L188) |
| `cancel_callbacks()` | [kicad_controls.py:202](kicad_controls.py#L202) |
| `iter_menu(menu, path='')` | [kicad_controls.py:210](kicad_controls.py#L210) |
| `find_menu_command(menu_path)` | [kicad_controls.py:229](kicad_controls.py#L229) |
| `open_menu(menu_path)` | [kicad_controls.py:252](kicad_controls.py#L252) |
| `_log_preferences_direct_children(baseline_windows, attempts=12)` | [kicad_controls.py:261](kicad_controls.py#L261) |
| `test_preferences_direct_children()` | [kicad_controls.py:307](kicad_controls.py#L307) |
| `_log_control_tree(control, depth=0)` | [kicad_controls.py:313](kicad_controls.py#L313) |
| `_log_preferences_control_tree(baseline_windows, attempts=12)` | [kicad_controls.py:337](kicad_controls.py#L337) |
| `test_preferences_control_tree()` | [kicad_controls.py:363](kicad_controls.py#L363) |
| `_log_preferences_checkbox_value(baseline_windows, attempts=12)` | [kicad_controls.py:369](kicad_controls.py#L369) |
| `test_preferences_checkbox_value()` | [kicad_controls.py:403](kicad_controls.py#L403) |
| `_restore_preferences_checkbox(checkbox, original_value)` | [kicad_controls.py:409](kicad_controls.py#L409) |
| `_toggle_preferences_checkbox(baseline_windows, attempts=12)` | [kicad_controls.py:414](kicad_controls.py#L414) |
| `test_preferences_checkbox_toggle_restore()` | [kicad_controls.py:451](kicad_controls.py#L451) |
| `get_pcb_selection_filter_panel()` | [kicad_controls.py:472](kicad_controls.py#L472) |
| `_pcb_selection_filter_control(panel, name)` | [kicad_controls.py:504](kicad_controls.py#L504) |
| `pcb_select_filter(name, value=None)` | [kicad_controls.py:517](kicad_controls.py#L517) |
| `pcb_select_filter_state()` | [kicad_controls.py:578](kicad_controls.py#L578) |
| `_find_pcb_layer_row(name)` | [kicad_controls.py:605](kicad_controls.py#L605) |
| `_send_mouse_event(control, event_type)` | [kicad_controls.py:641](kicad_controls.py#L641) |
| `_process_pending_gui_events()` | [kicad_controls.py:651](kicad_controls.py#L651) |
| `_find_layer_visibility_bitmap(row, label)` | [kicad_controls.py:658](kicad_controls.py#L658) |
| `_pcb_board()` | [kicad_controls.py:706](kicad_controls.py#L706) |
| `_pcb_layer_visible(layer_id)` | [kicad_controls.py:717](kicad_controls.py#L717) |
| `_find_layer_selector(frame, target_name=None)` | [kicad_controls.py:722](kicad_controls.py#L722) |
| `pcb_select_layer(name)` | [kicad_controls.py:747](kicad_controls.py#L747) |
| `_pcb_layer_rows(frame=None)` | [kicad_controls.py:800](kicad_controls.py#L800) |
| `_find_layer_indicator_bitmap(row, label)` | [kicad_controls.py:838](kicad_controls.py#L838) |
| `_bitmap_alpha_gt_16_count(bitmap)` | [kicad_controls.py:880](kicad_controls.py#L880) |
| `_pcb_selected_layer_from_indicator(frame=None)` | [kicad_controls.py:919](kicad_controls.py#L919) |
| `pcb_get_selected_layer()` | [kicad_controls.py:953](kicad_controls.py#L953) |
| `_pcb_copper_layers(frame=None)` | [kicad_controls.py:958](kicad_controls.py#L958) |
| `_pcb_move_copper_layer(step)` | [kicad_controls.py:988](kicad_controls.py#L988) |
| `pcb_layer_up()` | [kicad_controls.py:1023](kicad_controls.py#L1023) |
| `pcb_layer_down()` | [kicad_controls.py:1032](kicad_controls.py#L1032) |
| `_pcb_width_mm_to_iu(width_mm, pcbnew)` | [kicad_controls.py:1041](kicad_controls.py#L1041) |
| `pcb_set_selected_track_width(width_mm)` | [kicad_controls.py:1057](kicad_controls.py#L1057) |
| `_is_descendant_window(window, ancestor)` | [kicad_controls.py:1148](kicad_controls.py#L1148) |
| `_pcb_hotkey_focus_target(frame)` | [kicad_controls.py:1161](kicad_controls.py#L1161) |
| `_send_native_q_hotkey(frame)` | [kicad_controls.py:1217](kicad_controls.py#L1217) |
| `_find_custom_track_via_dialog(baseline_windows)` | [kicad_controls.py:1256](kicad_controls.py#L1256) |
| `_find_track_width_text_control(dialog)` | [kicad_controls.py:1280](kicad_controls.py#L1280) |
| `_command_ok_button(dialog)` | [kicad_controls.py:1316](kicad_controls.py#L1316) |
| `_finish_native_routing_width_request(serial, requested_mm, requested_iu)` | [kicad_controls.py:1344](kicad_controls.py#L1344) |
| `_fill_native_routing_width_dialog(serial, attempts=40)` | [kicad_controls.py:1371](kicad_controls.py#L1371) |
| `pcb_set_routing_track_width(width_mm)` | [kicad_controls.py:1411](kicad_controls.py#L1411) |
| `pcb_set_netclass_track_width()` | [kicad_controls.py:1464](kicad_controls.py#L1464) |
| `pcb_onoff_layer(name, value=None)` | [kicad_controls.py:1518](kicad_controls.py#L1518) |
| `find_drc_command()` | [kicad_controls.py:1557](kicad_controls.py#L1557) |
| `dispatch_menu_command(owner_menu, item, frame=None)` | [kicad_controls.py:1589](kicad_controls.py#L1589) |
| `open_drc_window(source='unknown', show_error=True)` | [kicad_controls.py:1617](kicad_controls.py#L1617) |

### snap_preferences.py

| 함수·메서드 signature | 코드 |
| --- | --- |
| `_version_series()` | [snap_preferences.py:36](snap_preferences.py#L36) |
| `settings_path()` | [snap_preferences.py:44](snap_preferences.py#L44) |
| `_nested_value(data, key)` | [snap_preferences.py:51](snap_preferences.py#L51) |
| `_decode_saved_values(data)` | [snap_preferences.py:74](snap_preferences.py#L74) |
| `_read_text_and_json()` | [snap_preferences.py:102](snap_preferences.py#L102) |
| `read_saved_settings(include_choices=False)` | [snap_preferences.py:113](snap_preferences.py#L113) |
| `_encoded_value(key, value)` | [snap_preferences.py:125](snap_preferences.py#L125) |
| `_patch_scalar(text, json_key, encoded)` | [snap_preferences.py:134](snap_preferences.py#L134) |
| `_atomic_write(path, text)` | [snap_preferences.py:151](snap_preferences.py#L151) |
| `_reload_live_settings()` | [snap_preferences.py:168](snap_preferences.py#L168) |
| `cleanup()` | [snap_preferences.py:176](snap_preferences.py#L176) |
| `request(changes=None, include_choices=False)` | [snap_preferences.py:181](snap_preferences.py#L181) |

### snap_panel.py

| 함수·메서드 signature | 코드 |
| --- | --- |
| `find_appearance_notebook(frame)` | [snap_panel.py:14](snap_panel.py#L14) |
| `SnapPanel.__init__(self, book)` | [snap_panel.py:27](snap_panel.py#L27) |
| `SnapPanel.set_status(self, text)` | [snap_panel.py:75](snap_panel.py#L75) |
| `SnapPanel.on_size(self, event)` | [snap_panel.py:80](snap_panel.py#L80) |
| `SnapPanel.on_page_changed(self, event)` | [snap_panel.py:86](snap_panel.py#L86) |
| `SnapPanel.display(self, payload)` | [snap_panel.py:97](snap_panel.py#L97) |
| `SnapPanel.refresh_from_kicad(self)` | [snap_panel.py:106](snap_panel.py#L106) |
| `SnapPanel.on_snap_choice_changed(self, event, key)` | [snap_panel.py:112](snap_panel.py#L112) |
| `SnapPanel._perform(self, changes)` | [snap_panel.py:122](snap_panel.py#L122) |
| `SnapPanel.dispose(self)` | [snap_panel.py:155](snap_panel.py#L155) |
| `SnapPanel.on_destroy(self, event)` | [snap_panel.py:162](snap_panel.py#L162) |
| `attach_snap_tab(frame)` | [snap_panel.py:168](snap_panel.py#L168) |
| `remove_snap_tab(frame)` | [snap_panel.py:188](snap_panel.py#L188) |

### ui_manager.py

| 함수·메서드 signature | 코드 |
| --- | --- |
| `system_colour(colour_id)` | [ui_manager.py:23](ui_manager.py#L23) |
| `is_dark_theme()` | [ui_manager.py:26](ui_manager.py#L26) |
| `icon_bitmap(name, size=20)` | [ui_manager.py:30](ui_manager.py#L30) |
| `style_button(button, icon_name=None, min_width=88)` | [ui_manager.py:54](ui_manager.py#L54) |
| `action_icon_name(action)` | [ui_manager.py:61](ui_manager.py#L61) |
| `get_manager_frame()` | [ui_manager.py:74](ui_manager.py#L74) |
| `MacroBKPluginManager.__init__(self, parent)` | [ui_manager.py:80](ui_manager.py#L80) |
| `MacroBKPluginManager.create_monitor_row(self, parent, sizer, icon_name, label, status)` | [ui_manager.py:406](ui_manager.py#L406) |
| `MacroBKPluginManager.set_led_colour(self, control, status)` | [ui_manager.py:421](ui_manager.py#L421) |
| `MacroBKPluginManager.configure_python_editor(self, editor)` | [ui_manager.py:432](ui_manager.py#L432) |
| `MacroBKPluginManager.configure_log_editor(self, editor)` | [ui_manager.py:456](ui_manager.py#L456) |
| `MacroBKPluginManager.style_log_range(self, start, text)` | [ui_manager.py:467](ui_manager.py#L467) |
| `MacroBKPluginManager.load_file_log(self)` | [ui_manager.py:472](ui_manager.py#L472) |
| `MacroBKPluginManager.append_result(self, line)` | [ui_manager.py:480](ui_manager.py#L480) |
| `MacroBKPluginManager.refresh_action_list(self)` | [ui_manager.py:489](ui_manager.py#L489) |
| `MacroBKPluginManager.store_current_action(self)` | [ui_manager.py:499](ui_manager.py#L499) |
| `MacroBKPluginManager.load_action(self, index)` | [ui_manager.py:509](ui_manager.py#L509) |
| `MacroBKPluginManager.on_action_selected(self, event)` | [ui_manager.py:523](ui_manager.py#L523) |
| `MacroBKPluginManager.on_action_rename(self, event)` | [ui_manager.py:530](ui_manager.py#L530) |
| `MacroBKPluginManager.on_add_action(self, _event)` | [ui_manager.py:543](ui_manager.py#L543) |
| `MacroBKPluginManager.on_duplicate_action(self, _event)` | [ui_manager.py:558](ui_manager.py#L558) |
| `MacroBKPluginManager.on_delete_action(self, _event)` | [ui_manager.py:568](ui_manager.py#L568) |
| `MacroBKPluginManager.set_keyboard_status(self, status)` | [ui_manager.py:586](ui_manager.py#L586) |
| `MacroBKPluginManager.set_phone_status(self, status)` | [ui_manager.py:591](ui_manager.py#L591) |
| `MacroBKPluginManager.set_test_status(self, status, stoppable=True)` | [ui_manager.py:596](ui_manager.py#L596) |
| `MacroBKPluginManager.update_status_bar(self)` | [ui_manager.py:613](ui_manager.py#L613) |
| `MacroBKPluginManager.show_result_tab(self)` | [ui_manager.py:621](ui_manager.py#L621) |
| `MacroBKPluginManager.blink_input_signal(self, source)` | [ui_manager.py:625](ui_manager.py#L625) |
| `MacroBKPluginManager.reset_input_signal(self)` | [ui_manager.py:633](ui_manager.py#L633) |
| `MacroBKPluginManager.on_select_trigger_key(self, _event)` | [ui_manager.py:638](ui_manager.py#L638) |
| `MacroBKPluginManager.read_trigger(self)` | [ui_manager.py:649](ui_manager.py#L649) |
| `MacroBKPluginManager.apply_selected_to_config(self)` | [ui_manager.py:652](ui_manager.py#L652) |
| `MacroBKPluginManager.on_register(self, _event)` | [ui_manager.py:662](ui_manager.py#L662) |
| `MacroBKPluginManager.begin_test_run(self, action_id, run_id)` | [ui_manager.py:683](ui_manager.py#L683) |
| `MacroBKPluginManager.finish_test_run(self, action_id, run_id, status)` | [ui_manager.py:688](ui_manager.py#L688) |
| `MacroBKPluginManager.on_test_run(self, _event)` | [ui_manager.py:695](ui_manager.py#L695) |
| `MacroBKPluginManager.on_stop_test(self, _event)` | [ui_manager.py:700](ui_manager.py#L700) |
| `MacroBKPluginManager.on_save(self, _event)` | [ui_manager.py:705](ui_manager.py#L705) |
| `MacroBKPluginManager.on_copy(self, _event)` | [ui_manager.py:717](ui_manager.py#L717) |
| `MacroBKPluginManager.on_clear(self, _event)` | [ui_manager.py:725](ui_manager.py#L725) |
| `MacroBKPluginManager.dispose(self)` | [ui_manager.py:730](ui_manager.py#L730) |
| `MacroBKPluginManager.on_close(self, event)` | [ui_manager.py:749](ui_manager.py#L749) |
| `show_manager()` | [ui_manager.py:754](ui_manager.py#L754) |

### key_picker.py

| 함수·메서드 signature | 코드 |
| --- | --- |
| `system_colour(colour_id)` | [key_picker.py:8](key_picker.py#L8) |
| `TriggerKeyPickerDialog.__init__(self, parent, current_value)` | [key_picker.py:20](key_picker.py#L20) |
| `TriggerKeyPickerDialog._section_title(self, parent, text)` | [key_picker.py:141](key_picker.py#L141) |
| `TriggerKeyPickerDialog._span_width(self, span)` | [key_picker.py:152](key_picker.py#L152) |
| `TriggerKeyPickerDialog._single_key_rows(self, keys)` | [key_picker.py:158](key_picker.py#L158) |
| `TriggerKeyPickerDialog._add_modifier_section(self, parent, sizer)` | [key_picker.py:165](key_picker.py#L165) |
| `TriggerKeyPickerDialog._add_rows_section(self, parent, sizer, title, rows)` | [key_picker.py:205](key_picker.py#L205) |
| `TriggerKeyPickerDialog._add_equal_five_section(self, parent, sizer, title, rows)` | [key_picker.py:257](key_picker.py#L257) |
| `TriggerKeyPickerDialog._load_current(self, current_value)` | [key_picker.py:309](key_picker.py#L309) |
| `TriggerKeyPickerDialog.on_modifier_changed(self, _event)` | [key_picker.py:334](key_picker.py#L334) |
| `TriggerKeyPickerDialog.on_key_clicked(self, event)` | [key_picker.py:337](key_picker.py#L337) |
| `TriggerKeyPickerDialog.get_trigger(self)` | [key_picker.py:359](key_picker.py#L359) |
| `TriggerKeyPickerDialog.update_preview(self)` | [key_picker.py:375](key_picker.py#L375) |
| `TriggerKeyPickerDialog.on_apply(self, _event)` | [key_picker.py:390](key_picker.py#L390) |
