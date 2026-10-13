import threading
import time

try:
    import tkinter as tk
except (ImportError, Exception):
    tk = None

try:
    import keyboard
except (ImportError, Exception):
    keyboard = None

import logging

log = logging.getLogger(__name__)

# Global state
_KILL_TRIGGERED = False
_INDICATOR_THREAD = None
_INDICATOR_ROOT = None

# Hardcoded blocklist patterns (substring match, case insensitive)
BLOCKLIST_PATTERNS = [
    "bitwarden", "1password", "keepass", "lastpass", "dashlane",
    "bank", "paypal", "stripe", "wallet",
    "firewall", "windows defender", "security", "antivirus",
    "registry editor", "regedit", "task manager",
    "uac", "credential", "bios", "firmware",
    "admin", "system32",
]

def trigger_kill_switch():
    """Immediately halt any active laptop control sessions."""
    global _KILL_TRIGGERED
    _KILL_TRIGGERED = True
    log.warning("GLOBAL KILL-SWITCH TRIGGERED. Halting all laptop control actions.")

def reset_kill_switch():
    """Reset the kill switch state."""
    global _KILL_TRIGGERED
    _KILL_TRIGGERED = False

def is_kill_triggered() -> bool:
    return _KILL_TRIGGERED

def register_kill_switch(hotkey: str = "ctrl+alt+k"):
    """Register the global hotkey."""
    if not keyboard:
        log.info("Keyboard module not available in this environment; skipping hotkey registration")
        return
    try:
        keyboard.add_hotkey(hotkey, trigger_kill_switch)
        log.info(f"Laptop control kill-switch registered on {hotkey}")
    except Exception as e:
        log.error(f"Failed to register kill-switch: {e}")

def _run_indicator():
    global _INDICATOR_ROOT
    if not tk:
        log.info("Tkinter not available in this environment; skipping UI indicator")
        return
    _INDICATOR_ROOT = tk.Tk()
    _INDICATOR_ROOT.overrideredirect(True)
    _INDICATOR_ROOT.attributes("-topmost", True)
    _INDICATOR_ROOT.geometry("320x30+10+10")
    _INDICATOR_ROOT.configure(bg="red")
    
    label = tk.Label(
        _INDICATOR_ROOT, 
        text="GUARDIAN LAPTOP CONTROL ACTIVE", 
        fg="white", 
        bg="red", 
        font=("Arial", 10, "bold")
    )
    label.pack(expand=True, fill="both")
    _INDICATOR_ROOT.mainloop()

def show_indicator():
    """Show the on-screen indicator (mandatory during active tools)."""
    global _INDICATOR_THREAD
    if not _INDICATOR_THREAD or not _INDICATOR_THREAD.is_alive():
        _INDICATOR_THREAD = threading.Thread(target=_run_indicator, daemon=True)
        _INDICATOR_THREAD.start()

def hide_indicator():
    """Hide the on-screen indicator."""
    global _INDICATOR_ROOT
    if _INDICATOR_ROOT:
        try:
            _INDICATOR_ROOT.after(0, _INDICATOR_ROOT.destroy)
        except Exception:
            pass
        _INDICATOR_ROOT = None

def is_blocklisted(target: str) -> bool:
    """
    Check if a window title, process name, or execution target matches the blocklist.
    Blocklist is checked case-insensitively.
    """
    if not target:
        return False
    target = target.lower()
    for pattern in BLOCKLIST_PATTERNS:
        if pattern in target:
            log.warning(f"Target '{target}' matches blocklist pattern '{pattern}'")
            return True
    return False
