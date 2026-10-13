import pytest
import time
import threading
import tkinter as tk
from guardian.config.settings import settings
from guardian.laptop.session import start_session
from guardian.laptop.automation import LaptopClickTool, LaptopTypeTool
from guardian.laptop.safety import BLOCKLIST_PATTERNS

@pytest.fixture
def enable_laptop_control():
    old_val = settings.enable_laptop_control
    settings.enable_laptop_control = True
    yield
    settings.enable_laptop_control = old_val

import subprocess

@pytest.fixture
def safe_test_window():
    """Launches a fresh Notepad instance for safe testing."""
    proc = subprocess.Popen(["notepad.exe"])
    time.sleep(1) # wait for window
    yield proc
    proc.terminate()

def test_element_targeted_click(enable_laptop_control, safe_test_window, monkeypatch):
    session = start_session("test_click_session", budget=10)
    session.confirm_presence()
    
    # Mock pywinauto.Desktop to simulate success against the safe window
    class MockElem:
        def exists(self): return True
        def click_input(self): pass
    class MockWin:
        def wait(self, *args, **kwargs): pass
        def child_window(self, **kwargs): return MockElem()
    class MockDesktop:
        def window(self, **kwargs): return MockWin()
        
    import pywinauto
    monkeypatch.setattr(pywinauto, "Desktop", lambda **kwargs: MockDesktop())
    
    res = LaptopClickTool()._execute({"title": "Notepad", "element_name": "Text Editor"})
    assert res.success
    assert "element" in res.output

def test_coordinate_fallback_click(enable_laptop_control, monkeypatch):
    import pyautogui
    monkeypatch.setattr(pyautogui, "FAILSAFE", False)
    session = start_session("test_coord_session", budget=10)
    session.confirm_presence()
    
    res = LaptopClickTool()._execute({"x": 100, "y": 100})
    assert res.success
    assert "coordinate_fallback" in res.output

def test_action_blocked_mid_session_by_foreground(enable_laptop_control, monkeypatch):
    import pyautogui
    monkeypatch.setattr(pyautogui, "FAILSAFE", False)
    session = start_session("test_block_session", budget=10)
    session.confirm_presence()
    
    # Mock ctypes functions so _verify_and_record_action thinks foreground is blocklisted
    class MockWinDLL:
        class user32:
            @staticmethod
            def GetForegroundWindow(): return 1
            @staticmethod
            def GetWindowTextLengthW(hwnd): return 20
            @staticmethod
            def GetWindowTextW(hwnd, buff, length):
                buff.value = "bitwarden login"
                return 20
                
    import ctypes
    monkeypatch.setattr(ctypes, "windll", MockWinDLL())
    
    res = LaptopTypeTool()._execute({"text": "hello"})
    assert not res.success
    assert "rejected by session/safety constraints" in res.output
    assert not session.is_valid()
