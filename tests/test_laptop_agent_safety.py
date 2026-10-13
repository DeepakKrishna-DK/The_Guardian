import os
import json
import pytest
from unittest.mock import patch, MagicMock

from guardian.laptop.agent import LaptopAgent, EscalationReason

@pytest.fixture
def agent():
    return LaptopAgent(model_name="mock")

def test_ambiguity_refusal(agent):
    esc = agent.evaluate_instruction("click anywhere")
    assert esc is not None
    assert esc.reason == EscalationReason.UNCLEAR_OUTCOME
    
    esc = agent.evaluate_instruction("type something")
    assert esc is not None
    assert esc.reason == EscalationReason.AMBIGUOUS_SCOPE

def test_is_risky_detection(agent):
    assert agent._is_risky("type", "del C:\\") == True
    assert agent._is_risky("type", "rm -rf /") == True
    assert agent._is_risky("click", "Delete File") == True
    assert agent._is_risky("press", "alt+f4") == True
    assert agent._is_risky("type", "hello world") == False
    assert agent._is_risky("click", "Save") == False

def test_bare_win_allowed(agent):
    # Bare win should not be blocked, but win+r should be
    assert agent._is_risky("press", "win") == False
    assert agent._is_risky("press", "win+r") == True
    assert agent._is_risky("press", "win+x") == True

@patch("guardian.laptop.agent.time.time")
@patch("msvcrt.kbhit", create=True)
def test_timeout_returns_no(mock_kbhit, mock_time, agent):
    mock_kbhit.return_value = False
    # Mock time.time() to simulate 30.1 seconds passing in 2 calls
    mock_time.side_effect = [0, 0, 30.1]
    
    # Should default to False when timeout hits
    result = agent._confirm_risky_action("test action")
    assert result is False

@patch("guardian.laptop.agent.pyautogui.screenshot")
def test_oserror_capture(mock_screenshot, agent):
    mock_screenshot.side_effect = OSError("screen grab failed")
    
    agent.ocr = MagicMock()
    mock_router = MagicMock()
    agent.router = mock_router
    
    log = agent.run("Do something", max_steps=1)
    
    # It should abort gracefully and not crash
    assert len(log) == 1
    assert log[0]["action"] == "abort"
    assert "Screen capture failed" in log[0]["result"]

@patch("guardian.laptop.agent.pyautogui")
@patch("guardian.laptop.agent.OCRAnalyzer")
@patch("guardian.laptop.agent.get_router")
def test_dry_run_does_nothing(mock_router, mock_ocr, mock_pyautogui, agent):
    # Mock router to return a model that outputs click action
    mock_model = MagicMock()
    mock_resp = MagicMock()
    mock_resp.content = '{"action": "click", "target": "Save"}'
    mock_model.complete.side_effect = [mock_resp, MagicMock(content='{"action": "done", "target": "ok"}')]
    mock_router.return_value.route.return_value = mock_model
    
    # Mock OCR
    mock_ocr_instance = MagicMock()
    mock_ocr_instance.extract_text.return_value = [{"text": "Save"}]
    mock_ocr_instance.find_text_coordinates.return_value = [{"bbox": [[0,0],[10,0],[10,10],[0,10]], "confidence": 0.9}]
    mock_ocr.return_value = mock_ocr_instance

    agent.router = mock_router.return_value
    agent.ocr = mock_ocr_instance

    # Run
    log = agent.run("Click save", live=False, max_steps=2)
    
    # PyAutoGUI click should NOT be called in dry run
    mock_pyautogui.click.assert_not_called()
    assert "Dry-run click" in log[0]["result"]

@patch("guardian.laptop.agent.pyautogui")
@patch("guardian.laptop.agent.OCRAnalyzer")
@patch("guardian.laptop.agent.get_router")
def test_json_parsing_retry(mock_router, mock_ocr, mock_pyautogui, agent):
    mock_model = MagicMock()
    # First returns invalid JSON, then valid
    mock_model.complete.side_effect = [
        MagicMock(content='invalid json here'),
        MagicMock(content='{"action": "done", "target": "ok"}')
    ]
    mock_router.return_value.route.return_value = mock_model
    
    agent.router = mock_router.return_value
    agent.ocr = MagicMock()
    
    log = agent.run("Do something", max_steps=5)
    
    # Should only have one logged action because first failed parsing and retried
    assert len(log) == 1
    assert log[0]["action"] == "done"

def test_multiple_match_refusal(agent):
    # If find_text_coordinates returns multiple matches, it should refuse
    agent.ocr = MagicMock()
    agent.ocr.find_text_coordinates.return_value = [
        {"bbox": [[0,0],[10,0],[10,10],[0,10]], "confidence": 0.9},
        {"bbox": [[20,0],[30,0],[30,10],[20,10]], "confidence": 0.8}
    ]
    
    mock_router = MagicMock()
    mock_model = MagicMock()
    mock_model.complete.side_effect = [
        MagicMock(content='{"action": "click", "target": "Save"}'),
        MagicMock(content='{"action": "done", "target": "ok"}')
    ]
    mock_router.route.return_value = mock_model
    agent.router = mock_router
    
    # Needs to bypass pyautogui 
    with patch("guardian.laptop.agent.pyautogui"):
        log = agent.run("Click save", max_steps=2)
        assert "Ambiguous target 'Save'" in log[0]["result"]

def test_wall_clock_limit(agent):
    agent.ocr = MagicMock()
    agent.ocr.extract_text.return_value = []
    
    mock_router = MagicMock()
    mock_model = MagicMock()
    # Always clicks to ensure we hit limits instead of finishing
    mock_model.complete.return_value = MagicMock(content='{"action": "click", "target": "Save"}')
    mock_router.route.return_value = mock_model
    agent.router = mock_router
    
    with patch("guardian.laptop.agent.pyautogui"):
        with patch("guardian.laptop.agent.time.time", side_effect=[0, 10, 130]):
            log = agent.run("Do something", max_steps=5, max_time_s=120)
            assert len(log) == 2
            assert log[-1]["action"] == "abort"
            assert "Wall-clock time limit reached" in log[-1]["result"]
