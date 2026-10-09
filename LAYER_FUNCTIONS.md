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
