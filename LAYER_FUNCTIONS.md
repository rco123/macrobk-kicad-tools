# MacroBK PCB Layer helpers

사용 함수:

```python
pcb_select_layer("F.Cu")
pcb_select_layer("B.Adhesive")
pcb_select_layer("Edge.Cuts")

pcb_get_selected_layer()            # 현재 활성 레이어 이름

pcb_onoff_layer("B.Cu")             # 현재 표시 상태 읽기
pcb_onoff_layer("B.Cu", True)       # 표시
pcb_onoff_layer("B.Cu", False)      # 숨김

pcb_layer_up()                       # 이전 Cu 레이어
pcb_layer_down()                     # 다음 Cu 레이어
```

## 현재 활성 레이어 판정

`pcb_get_selected_layer()`는 Appearance > Layers에서 현재 레이어 왼쪽에 표시되는
**선택 화살표 indicator**를 읽습니다.

KiCad 9.0.9 Windows 실측에서 각 레이어 row의 첫 번째 bitmap (`row/0/0`)은:

```text
미선택: alpha_gt_16_count = 0
선택:   alpha_gt_16_count = 25
```

이었습니다. OFF bitmap에는 alpha=10인 near-transparent pixel 하나가 있으므로
`nontransparent_pixel_count > 0`만으로 판정하지 않고, effective alpha가 16보다 큰
픽셀이 존재하는지를 사용합니다.

focus, row 배경색, MacroBK 캐시, 마지막 요청값은 사용하지 않습니다. 동시에 둘 이상
또는 하나도 선택된 indicator를 찾지 못하면 추측하지 않고 오류를 반환합니다.

## Copper layer UP / DOWN

`pcb_layer_up()` / `pcb_layer_down()`은 현재 PCB에서 enabled 상태인 `*.Cu` 레이어만
Appearance의 stack 순서로 순환합니다. Mask, Silkscreen, Adhesive, Edge.Cuts, User
레이어는 Cu 순환 대상에서 제외됩니다.

예: 4층 PCB

```text
F.Cu -> In1.Cu -> In2.Cu -> B.Cu -> F.Cu ...   (DOWN)
F.Cu <- In1.Cu <- In2.Cu <- B.Cu <- F.Cu ...   (UP)
```

현재 레이어가 Cu가 아닌 경우 정책은 다음과 같습니다.

```text
UP   -> 마지막 Cu 레이어 (보통 B.Cu)
DOWN -> 첫 번째 Cu 레이어 (보통 F.Cu)
```

예를 들어 현재 `B.Mask`이면:

```python
pcb_layer_up()    # -> B.Cu
pcb_layer_down()  # -> F.Cu
```

레이어 이동 후 선택 화살표를 다시 읽어서 실제 target으로 바뀌었는지 검증합니다.
