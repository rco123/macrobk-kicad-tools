# MacroBK Manager > Python Script test
# Run with the PCB Editor and Appearance/Layers pane visible.
import time

print("=== Layer Function Test ===")

print("Select F.Cu:", pcb_select_layer("F.Cu"))
time.sleep(0.7)
print("Select B.Adhesive:", pcb_select_layer("B.Adhesive"))
time.sleep(0.7)

print("B.Adhesive current:", pcb_onoff_layer("B.Adhesive"))
print("B.Adhesive OFF:", pcb_onoff_layer("B.Adhesive", False))
time.sleep(0.7)
print("B.Adhesive ON:", pcb_onoff_layer("B.Adhesive", True))

print("=== PASS if the active row moved and eye icon/canvas visibility changed ===")
