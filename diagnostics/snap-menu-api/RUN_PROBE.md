# Snap to pads Preferences round trip

현재 KiCad 안의 MacroBK Manager에서 실행한다. 기존 script를 보관하고 아래를 입력한 뒤 **Save 없이 Run Test**한다. 테스트 전에 다른 Preferences 창을 닫는다.

```python
import runpy
p = runpy.run_path(r'C:\Users\sgkim\Documents\KiCad\9.0\scripting\plugins\macrobk_drc_bridge\diagnostics\snap-menu-api\probe.py')
print(p['start']())
```

테스트 중 Preferences를 직접 편집하지 않는다. 기존 open_menu, find_controls, iter_controls, get_control_info, get_control_value, set_control_value, _command_ok_button을 이미 로드된 MacroBK module에서 재사용한다. 새 plugin import/registration 없음. 표준 wx.Treebook page label/parent chain으로 PCB Editor > Editing Options를 선택한다. Snap to pads label 바로 다음 wx.Choice의 native 선택지 3개까지 확인한 후만 수정한다. custom control id/좌표/키 입력 없음. wx.ID_OK는 기존 helper가 사용하는 표준 dialog command다.

현재값을 result.json에 먼저 저장한 후 Always면 Never로, 다른 값이면 Always로 한 번 변경한다. 실제 native OK handler를 호출하여 TransferDataFromWindow를 거친다. 다시 메뉴를 열어 저장된 변경값을 읽고 바로 원래값을 설정·OK한다. 세 번째 재오픈에서 복구값을 확인하고 변경 없이 OK로 닫는다. timer는 modal dialog nested event loop를 위해 bounded 진단 callback에만 사용하며 종료 시 중지한다. Appearance SNAP page는 접근하지 않는다.

예약 메시지는 성공 판정이 아니다. result.json의 verdict, after_reopen, restore_pass, restored_reopen을 확인해야 한다. runtime pad snapping은 별도 행동 검증이 없으면 NOT TESTED다.

예외가 발생하면 result.json에 original/error/restore_required를 기록한다. 원래값 확인이 안 됐으면 Preferences를 닫고 아래를 실행해 **저장된 original을 복구하고 재오픈 확인만** 수행할 수 있다.

```python
print(p['start'](restore_only=True))
```

이 복구 실행은 새 테스트 toggle을 하지 않는다. config 파일을 직접 수정하는 복구는 사용하지 않는다.
