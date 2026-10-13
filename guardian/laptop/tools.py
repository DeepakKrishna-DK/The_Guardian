import os
import time
import hashlib
from typing import Any
from pathlib import Path

try:
    import mss
except Exception:
    mss = None

try:
    import pywinauto
except Exception:
    pywinauto = None

import psutil

try:
    import pyperclip
except Exception:
    pyperclip = None

from guardian.tools.base import Tool, ToolLevel, ToolResult
from guardian.config.settings import settings
from guardian.laptop.safety import is_blocklisted, show_indicator
from guardian.audit.redact import redact_string

BLOB_DIR = settings.data_dir / "blobs"
BLOB_DIR.mkdir(parents=True, exist_ok=True)

def _store_blob(data: bytes, ext: str = "png") -> str:
    """Store raw data as a content-addressed blob."""
    h = hashlib.sha256(data).hexdigest()
    path = BLOB_DIR / f"{h}.{ext}"
    if not path.exists():
        path.write_bytes(data)
    return h

class LaptopScreenshotTool(Tool):
    name = "laptop_screenshot"
    level = ToolLevel.WRITE  # Upgraded to WRITE (level 1) per observation requirements
    description = "Capture a screenshot of the laptop screen. Returns a content hash."

    def schema(self) -> dict[str, Any]:
        return {}

    def _execute(self, params: dict[str, Any]) -> ToolResult:
        if not settings.enable_laptop_control:
            return ToolResult(success=False, output="Laptop control is disabled by feature flag.")
        show_indicator()
        
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[0]  # All monitors
                sct_img = sct.grab(monitor)
                raw_png = mss.tools.to_png(sct_img.rgb, sct_img.size)
                
                h = _store_blob(raw_png, "png")
                
                metadata = {
                    "width": sct_img.width,
                    "height": sct_img.height,
                    "hash": h
                }
                
                return ToolResult(
                    success=True,
                    output=f"Screenshot captured. Blob hash: {h}",
                    metadata=metadata
                )
        except Exception as e:
            return ToolResult(success=False, output=f"Screenshot failed: {e}")

class LaptopWindowListTool(Tool):
    name = "laptop_window_list"
    level = ToolLevel.WRITE
    description = "List all visible window titles."

    def schema(self) -> dict[str, Any]:
        return {}

    def _execute(self, params: dict[str, Any]) -> ToolResult:
        if not settings.enable_laptop_control:
            return ToolResult(success=False, output="Laptop control is disabled by feature flag.")
        show_indicator()
        
        try:
            titles = []
            def enum_windows_proc(hwnd, lParam):
                import ctypes
                if ctypes.windll.user32.IsWindowVisible(hwnd):
                    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
                        titles.append(buff.value)
                return True
                
            import ctypes
            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
            ctypes.windll.user32.EnumWindows(EnumWindowsProc(enum_windows_proc), 0)
            
            # Redact titles just in case
            safe_titles = [redact_string(t) for t in titles if t.strip()]
            
            return ToolResult(
                success=True,
                output="\n".join(safe_titles)
            )
        except Exception as e:
            return ToolResult(success=False, output=f"Window list failed: {e}")

class LaptopForegroundWindowTool(Tool):
    name = "laptop_foreground_window"
    level = ToolLevel.WRITE
    description = "Get the title of the active foreground window."

    def schema(self) -> dict[str, Any]:
        return {}

    def _execute(self, params: dict[str, Any]) -> ToolResult:
        if not settings.enable_laptop_control:
            return ToolResult(success=False, output="Laptop control is disabled by feature flag.")
        show_indicator()
        
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value
                title = redact_string(title)
                return ToolResult(success=True, output=f"Foreground window: {title}")
            return ToolResult(success=True, output="No active foreground window title.")
        except Exception as e:
            return ToolResult(success=False, output=f"Foreground window failed: {e}")

class LaptopClipboardReadTool(Tool):
    name = "laptop_clipboard_read"
    level = ToolLevel.WRITE
    description = "Read text from the clipboard."

    def schema(self) -> dict[str, Any]:
        return {}

    def _execute(self, params: dict[str, Any]) -> ToolResult:
        if not settings.enable_laptop_control:
            return ToolResult(success=False, output="Laptop control is disabled by feature flag.")
        show_indicator()
        
        try:
            content = pyperclip.paste()
            # Pass through secret-pattern scanner
            safe_content = redact_string(content)
            return ToolResult(success=True, output=safe_content)
        except Exception as e:
            return ToolResult(success=False, output=f"Clipboard read failed: {e}")

OBSERVATION_TOOLS = [
    LaptopScreenshotTool(),
    LaptopWindowListTool(),
    LaptopForegroundWindowTool(),
    LaptopClipboardReadTool(),
]

import subprocess
import json

class LaptopLaunchAppTool(Tool):
    name = "laptop_launch_app"
    level = ToolLevel.DANGEROUS  # Risk tier floored at 2
    description = "Launch an application explicitly allowed in laptop_allowlist.json."

    def schema(self) -> dict[str, Any]:
        return {"name": "string (name of the app in allowlist)"}

    def _execute(self, params: dict[str, Any]) -> ToolResult:
        if not settings.enable_laptop_control:
            return ToolResult(success=False, output="Laptop control is disabled by feature flag.")
            
        app_name = params.get("name")
        if not app_name:
            return ToolResult(success=False, output="Missing app name parameter.")
            
        # Blocklist ALWAYS wins
        if is_blocklisted(app_name):
            return ToolResult(success=False, output=f"Access denied: '{app_name}' matches blocklist.")
            
        # Check allowlist
        allowlist_path = settings.project_root / "guardian" / "config" / "laptop_allowlist.json"
        if not allowlist_path.exists():
            return ToolResult(success=False, output="laptop_allowlist.json not found.")
            
        try:
            allowlist = json.loads(allowlist_path.read_text())
        except Exception as e:
            return ToolResult(success=False, output=f"Failed to read allowlist: {e}")
            
        if app_name not in allowlist:
            return ToolResult(success=False, output=f"App '{app_name}' is not in the explicit allowlist.")
            
        cmd = allowlist[app_name]
        
        # Blocklist double-check against the target command path
        if is_blocklisted(cmd):
            return ToolResult(success=False, output=f"Access denied: command path '{cmd}' matches blocklist.")
            
        show_indicator()
        
        try:
            # We don't block waiting for it to close
            proc = subprocess.Popen(cmd, shell=False)
            return ToolResult(
                success=True, 
                output=f"Launched '{app_name}' successfully.",
                metadata={"pid": proc.pid, "app": app_name, "cmd": cmd}
            )
        except Exception as e:
            return ToolResult(success=False, output=f"Failed to launch app: {e}")

class LaptopCloseAppTool(Tool):
    name = "laptop_close_app"
    level = ToolLevel.DANGEROUS
    description = "Close an application explicitly allowed in laptop_allowlist.json."

    def schema(self) -> dict[str, Any]:
        return {"name": "string (name of the app in allowlist)"}

    def _execute(self, params: dict[str, Any]) -> ToolResult:
        if not settings.enable_laptop_control:
            return ToolResult(success=False, output="Laptop control is disabled by feature flag.")
            
        app_name = params.get("name")
        if not app_name:
            return ToolResult(success=False, output="Missing app name parameter.")
            
        if is_blocklisted(app_name):
            return ToolResult(success=False, output=f"Access denied: '{app_name}' matches blocklist.")
            
        allowlist_path = settings.project_root / "guardian" / "config" / "laptop_allowlist.json"
        if not allowlist_path.exists():
            return ToolResult(success=False, output="laptop_allowlist.json not found.")
            
        try:
            allowlist = json.loads(allowlist_path.read_text())
        except Exception as e:
            return ToolResult(success=False, output=f"Failed to read allowlist: {e}")
            
        if app_name not in allowlist:
            return ToolResult(success=False, output=f"App '{app_name}' is not in the explicit allowlist.")
            
        cmd_str = allowlist[app_name]
        
        show_indicator()
        
        try:
            # Attempt to close the process by matching the command path or executable name
            exe_name = Path(cmd_str).name.lower() if hasattr(Path(cmd_str), 'name') else str(cmd_str).lower()
            if "\\" in exe_name:
                exe_name = exe_name.split("\\")[-1]
                
            closed_count = 0
            for proc in psutil.process_iter(['name', 'exe']):
                try:
                    p_name = proc.info['name']
                    p_exe = proc.info['exe']
                    
                    if p_name and exe_name in p_name.lower():
                        proc.terminate()
                        closed_count += 1
                    elif p_exe and exe_name in p_exe.lower():
                        proc.terminate()
                        closed_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
                    
            if closed_count > 0:
                return ToolResult(success=True, output=f"Closed {closed_count} instances of '{app_name}'.")
            else:
                return ToolResult(success=False, output=f"No running instances found for '{app_name}'.")
        except Exception as e:
            return ToolResult(success=False, output=f"Failed to close app: {e}")

APP_CONTROL_TOOLS = [LaptopLaunchAppTool(), LaptopCloseAppTool()]
