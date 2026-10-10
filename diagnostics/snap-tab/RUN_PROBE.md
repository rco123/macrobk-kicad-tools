# Live probe 실행

KiCad 9.0.9 안의 MacroBK Manager Python Script에서 아래를 Run Test한다. Save는 누르지 않는다. 기존 script는 먼저 별도로 보관한다. Python Script 편집만으로 config는 저장되지 않는다.

```python
import runpy
p = runpy.run_path(r'C:\Users\sgkim\Documents\KiCad\9.0\scripting\plugins\macrobk_drc_bridge\diagnostics\snap-tab\probe.py')
print(p['start']())
```

GUI thread에 예약된 callback은 실제 hierarchy를 먼저 확인하고 새 MacroBK-owned panel만 추가한다. 동일 함수를 두 번 호출해 duplicate 여부를 기록한다. 원래 page의 순서·부모·label은 바꾸지 않는다. 다른 소유자의 SNAP page가 있거나 notebook 후보가 여러 개면 중단한다. 결과는 inspection.json, hierarchy.json, live_result.json 또는 live_error.json에 저장한다.

같은 script를 다시 Run Test해 reload/repeat를 확인한다. Manager를 닫고 다시 열었을 때 SNAP이 1개인지 확인한다. SNAP과 원래 탭을 직접 클릭하고 창 크기·Appearance 폭·show/hide·theme를 변경하며 레이아웃과 focus를 관찰한다. 이 probe는 해당 행위를 자동 수행하거나 성공으로 가정하지 않는다.

상태 캡처(Manager에서는 wx.CallAfter 필요):

```python
wx.CallAfter(p['capture_state'], 'resize 후 확인')
```

Preferences > PCB Editor > Editing Options를 직접 열어 다음을 실행하면 현재 열린 Preferences의 draft choice만 읽는다. 실제 committed runtime getter로 간주하지 않는다.

```python
wx.CallAfter(p['read_preferences_controls'])
```

삭제:

```python
print(p['remove_snap_probe_tab']())
```

삭제는 소유자 name을 확인한 probe page만 RemovePage 후 Destroy한다. native page는 삭제하지 않는다. 반복 삭제도 가능하다. 테스트 후 이 삭제 함수를 실행하고 native 탭으로 복귀한다. SNAP이 선택된 채 Editor를 닫으면 KiCad가 추가 page index를 자기 UI 설정에 저장할 수 있으므로, close 테스트 전에 probe를 제거한 경로와 parent 자동 destruction 경로를 별도 관찰해야 한다. config 직접 편집은 하지 않는다.

timer 없음. frame/Manager 이벤트 binding 없음. 생성한 panel의 destroy 이벤트만 있으며 parent notebook destruction에 따라 page가 제거되는지 destruction.json으로 확인한다. 이 파일이 존재한다고 정상 Editor 종료가 검증된 것은 아니다(명시적 제거에서도 발생). Editor close/reopen은 사용자가 기존 unsaved PCB의 저장 여부를 판단한 뒤 수행한다.
