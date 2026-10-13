import keyboard
import time

triggered = False
def on_kill():
    global triggered
    triggered = True
    print("KILL SWITCH TRIGGERED!")

keyboard.add_hotkey('ctrl+alt+k', on_kill)

print("Running loop for 3 seconds...")
start = time.time()
while time.time() - start < 3:
    if triggered:
        print("Loop halted by kill switch.")
        break
    time.sleep(0.1)

if not triggered:
    print("Loop finished naturally.")
