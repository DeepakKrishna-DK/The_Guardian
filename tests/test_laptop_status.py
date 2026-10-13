import pytest
from guardian.cli import _render_status

def test_render_laptop_status(capsys):
    mock_status = {
        "laptop": {
            "enabled": False,
            "kill_switch": "ARMED (ctrl+alt+k)",
            "blocklist_size": 22,
            "allowlist_size": 3,
            "active_session": "None",
            "actions_used": 0
        }
    }
    
    _render_status(mock_status)
    out, _ = capsys.readouterr()
    assert "Laptop Control" in out
    assert "OFF (Feature Flag)" in out
    assert "ARMED (ctrl+alt+k)" in out
    assert "22 patterns" in out
    
