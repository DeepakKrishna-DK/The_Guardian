import time
import logging
from typing import Any
try:
    import pywinauto
except Exception:
    pywinauto = None

try:
    import pyautogui
except Exception:
    pyautogui = None

from guardian.laptop.session import get_active_session
from guardian.laptop.safety import is_blocklisted, show_indicator
from guardian.audit import get_audit_log
from guardian.config.settings import settings
from guardian.tools.base import Tool, ToolLevel, ToolResult

log = logging.getLogger(__name__)

def _verify_and_record_action(action_type: str, details: dict) -> bool:
    """Check session, re-evaluate blocklist against foreground, and record audit."""
    session = get_active_session()
    if not session:
        log.error("No active, confirmed laptop session.")
        return False
        
    if not session.record_action():
        log.error("Session action rejected (budget/timeout/killswitch).")
        return False

    # Check foreground window against blocklist (M4 requirement)
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
            fg_title = buff.value
            if is_blocklisted(fg_title):
                log.warning(f"Action blocked: foreground window '{fg_title}' matches blocklist.")
                session.end_session()
                return False
    except Exception as e:
        log.warning(f"Failed to check foreground window: {e}")

    # Record individual audit entry
    try:
        get_audit_log().append(
            "laptop.action",
            session_id=session.session_id,
            payload={
                "action_type": action_type,
                "details": details,
                "timestamp": time.time()
            }
        )
    except Exception as e:
        log.error(f"Failed to audit laptop action: {e}")
        # Always fail closed if we can't audit
        return False
        
    return True

class LaptopClickTool(Tool):
    name = "laptop_click"
    level = ToolLevel.DANGEROUS # Max level
    description = "Click an element by name (preferred) or by x,y coordinates (fallback)."

    def schema(self) -> dict[str, Any]:
        return {
            "title": "string (window title)",
            "element_name": "string (element automation ID or name, optional)",
            "text_to_click": "string (text to find visually on screen via OCR, optional)",
            "x": "int (fallback coordinate)",
            "y": "int (fallback coordinate)"
        }

    def _execute(self, params: dict[str, Any]) -> ToolResult:
        if not settings.enable_laptop_control:
            return ToolResult(success=False, output="Laptop control is disabled.")
            
        title = params.get("title")
        element_name = params.get("element_name")
        text_to_click = params.get("text_to_click")
        x = params.get("x")
        y = params.get("y")
        
        if title and is_blocklisted(title):
            return ToolResult(success=False, output=f"Access denied: window '{title}' matches blocklist.")

        method = "element"
        
        if not _verify_and_record_action("click", params):
            return ToolResult(success=False, output="Action rejected by session/safety constraints.")

        try:
            if text_to_click:
                method = "ocr_fallback"
                import tempfile
                import os
                from guardian.vision.ocr import OCRAnalyzer
                
                # Take screenshot to temporary file
                fd, path = tempfile.mkstemp(suffix=".png")
                os.close(fd)
                try:
                    pyautogui.screenshot(path)
                    analyzer = OCRAnalyzer()
                    matches = analyzer.find_text_coordinates(path, text_to_click)
                    if not matches:
                        return ToolResult(success=False, output=f"OCR failed to find text '{text_to_click}' on screen.")
                    
                    # Get center of the highest confidence match
                    bbox = matches[0]["bbox"]
                    # bbox is [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
                    center_x = (int(bbox[0][0]) + int(bbox[2][0])) // 2
                    center_y = (int(bbox[0][1]) + int(bbox[2][1])) // 2
                    
                    pyautogui.click(x=center_x, y=center_y)
                finally:
                    if os.path.exists(path):
                        os.remove(path)

            elif title and element_name:
                # Element-targeted automation (primary)
                app = pywinauto.Desktop(backend="uia")
                win = app.window(title_re=f".*{title}.*")
                win.wait('visible', timeout=3)
                elem = win.child_window(title=element_name, control_type="Button")
                if not elem.exists():
                    elem = win.child_window(auto_id=element_name)
                elem.click_input()
                method = "element"
            elif x is not None and y is not None:
                # Coordinate fallback
                method = "coordinate_fallback"
                pyautogui.click(x=x, y=y)
            else:
                return ToolResult(success=False, output="Must provide text_to_click, element_name + title, OR x, y coordinates.")
                
            # Amend audit with method used
            session = get_active_session()
            if session:
                get_audit_log().append(
                    "laptop.action_completed",
                    session_id=session.session_id,
                    payload={"action_type": "click", "method": method, "flagged": (method == "coordinate_fallback")}
                )

            return ToolResult(success=True, output=f"Clicked successfully via {method}.")
        except Exception as e:
            return ToolResult(success=False, output=f"Click failed: {e}")

class LaptopTypeTool(Tool):
    name = "laptop_type"
    level = ToolLevel.DANGEROUS
    description = "Type text into the foreground window."

    def schema(self) -> dict[str, Any]:
        return {"text": "string"}

    def _execute(self, params: dict[str, Any]) -> ToolResult:
        if not settings.enable_laptop_control:
            return ToolResult(success=False, output="Laptop control is disabled.")
            
        text = params.get("text", "")
        if not text:
            return ToolResult(success=False, output="No text provided.")
            
        if not _verify_and_record_action("type", {"length": len(text)}):
            return ToolResult(success=False, output="Action rejected by session/safety constraints.")
            
        try:
            pyautogui.write(text, interval=0.01)
            
            session = get_active_session()
            if session:
                get_audit_log().append(
                    "laptop.action_completed",
                    session_id=session.session_id,
                    payload={"action_type": "type", "method": "pyautogui"}
                )
                
            return ToolResult(success=True, output="Typed text successfully.")
        except Exception as e:
            return ToolResult(success=False, output=f"Type failed: {e}")

AUTOMATION_TOOLS = [LaptopClickTool(), LaptopTypeTool()]
