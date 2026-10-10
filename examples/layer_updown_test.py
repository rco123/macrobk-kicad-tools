import time

print("=== Copper Layer UP/DOWN Test ===")

print("Current:", pcb_get_selected_layer())

print("1. Select F.Cu")
pcb_select_layer("F.Cu")
time.sleep(0.3)
print("   current =", pcb_get_selected_layer())

print("2. DOWN from F.Cu -> next Cu")
print("   result  =", pcb_layer_down())
time.sleep(0.3)
print("   current =", pcb_get_selected_layer())

print("3. UP -> previous Cu")
print("   result  =", pcb_layer_up())
time.sleep(0.3)
print("   current =", pcb_get_selected_layer())

print("4. Select non-Cu B.Mask")
pcb_select_layer("B.Mask")
time.sleep(0.3)
print("   current =", pcb_get_selected_layer())

print("5. UP from non-Cu -> last Cu (normally B.Cu)")
print("   result  =", pcb_layer_up())
time.sleep(0.3)
print("   current =", pcb_get_selected_layer())

print("6. Select non-Cu B.Mask again")
pcb_select_layer("B.Mask")
time.sleep(0.3)

print("7. DOWN from non-Cu -> first Cu (normally F.Cu)")
print("   result  =", pcb_layer_down())
time.sleep(0.3)
print("   current =", pcb_get_selected_layer())

print("=== END ===")
