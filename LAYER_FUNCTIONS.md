# MacroBK PCB Layer helpers

추가 함수:

```python
pcb_select_layer("F.Cu")
pcb_select_layer("B.Adhesive")
pcb_select_layer("Edge.Cuts")

pcb_onoff_layer("B.Cu")          # 현재 표시 상태 읽기
pcb_onoff_layer("B.Cu", True)    # 표시
pcb_onoff_layer("B.Cu", False)   # 숨김
```

`pcb_select_layer()`는 KiCad Appearance > Layers의 레이어 텍스트에 실제 클릭과 같은 `LEFT_DOWN` 이벤트를 전달합니다.

`pcb_onoff_layer()`는 해당 레이어 행의 visibility bitmap에 실제 클릭과 같은 `LEFT_UP` 이벤트를 전달하고, KiCad board visibility 상태가 목표값으로 변경되었는지 확인합니다.

Manager의 Python Script에서 `layer_function_test.py` 내용을 실행해 화면에서 확인할 수 있습니다.


## Copper layer UP / DOWN

```python
pcb_layer_up()
pcb_layer_down()
```

`pcb_layer_up()` / `pcb_layer_down()`은 현재 활성 레이어를 기준으로 현재 PCB에서 사용 중인 `*.Cu` 레이어만 순환합니다.
Mask, Silkscreen, Adhesive, Edge.Cuts, User 레이어는 순환 대상에서 제외됩니다.

예: 4층 PCB

```text
F.Cu <-> In1.Cu <-> In2.Cu <-> B.Cu
```

끝에서는 반대편으로 순환합니다. 현재 활성 레이어가 Copper 레이어가 아니면 오류를 반환합니다.


## Active layer detection fix

`pcb_layer_up()` / `pcb_layer_down()` now fall back to the highlighted row in Appearance > Layers when KiCad's wx wrapper does not expose `GetActiveLayer()` and the toolbar selector cannot be queried.

## Layer UP/DOWN implementation

`pcb_layer_up()` and `pcb_layer_down()` now dispatch KiCad's native
`Switch to Previous Layer (-)` and `Switch to Next Layer (+)` actions.

This intentionally does not read the active layer in Python. KiCad's own
interactive router owns the current routing layer and cycles through the
enabled copper-layer set.
