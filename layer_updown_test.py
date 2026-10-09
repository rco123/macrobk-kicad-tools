import time

print("=== Native Copper Layer UP/DOWN Test ===")

print("Start: select F.Cu")
pcb_select_layer("F.Cu")
time.sleep(0.5)

print("DOWN 1")
pcb_layer_down()
time.sleep(0.5)

print("DOWN 2")
pcb_layer_down()
time.sleep(0.5)

print("UP 1")
pcb_layer_up()
time.sleep(0.5)

print("UP 2")
pcb_layer_up()
time.sleep(0.5)

print("=== END ===")
