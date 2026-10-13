import threading
import time
import tkinter as tk

class LaptopIndicator:
    def __init__(self):
        self.root = None
        self.thread = None

    def _run(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.geometry("300x30+10+10")
        self.root.configure(bg="red")
        label = tk.Label(self.root, text="GUARDIAN LAPTOP CONTROL ACTIVE", fg="white", bg="red", font=("Arial", 10, "bold"))
        label.pack(expand=True, fill="both")
        self.root.mainloop()

    def show(self):
        if not self.thread or not self.thread.is_alive():
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()

    def hide(self):
        if self.root:
            self.root.quit()
            self.root = None

if __name__ == "__main__":
    ind = LaptopIndicator()
    print("Showing indicator...")
    ind.show()
    time.sleep(3)
    print("Hiding indicator...")
    ind.hide()
    time.sleep(1)
    print("Done")
