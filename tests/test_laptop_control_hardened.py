"""
Tests for Hardened Laptop Control Safety & Kill-Switch
======================================================
"""

import pytest
from guardian.laptop.safety import (
    is_blocklisted,
    trigger_kill_switch,
    reset_kill_switch,
    is_kill_triggered,
    BLOCKLIST_PATTERNS,
)
from guardian.laptop.agent import LaptopAgent, LAPTOP_TOOL_NAMES
from guardian.core.collab import EscalationReason


def test_blocklist_patterns():
    # Sensitive apps and utilities must be blocked
    assert is_blocklisted("1Password - Vault")
    assert is_blocklisted("Bitwarden Password Manager")
    assert is_blocklisted("Windows Security")
    assert is_blocklisted("Registry Editor (regedit)")
    assert is_blocklisted("Task Manager")
    assert is_blocklisted("C:\\Windows\\System32\\cmd.exe")
    assert is_blocklisted("User Account Control (UAC)")

    # Benign targets must not be blocklisted
    assert not is_blocklisted("Notepad - notes.txt")
    assert not is_blocklisted("Calculator")
    assert not is_blocklisted("Google Chrome - Documentation")


def test_kill_switch_state():
    reset_kill_switch()
    assert not is_kill_triggered()

    trigger_kill_switch()
    assert is_kill_triggered()

    reset_kill_switch()
    assert not is_kill_triggered()


def test_laptop_agent_instruction_evaluation():
    agent = LaptopAgent()

    # Ambiguous scope evaluation
    esc1 = agent.evaluate_instruction("Please click something on the screen")
    assert esc1 is not None
    assert esc1.reason == EscalationReason.AMBIGUOUS_SCOPE

    # Unclear outcome evaluation
    esc2 = agent.evaluate_instruction("click anywhere to dismiss")
    assert esc2 is not None
    assert esc2.reason == EscalationReason.UNCLEAR_OUTCOME

    # Valid specific instruction
    esc3 = agent.evaluate_instruction("Open notepad and write hello")
    assert esc3 is None


def test_risky_keyword_detection():
    agent = LaptopAgent()
    assert agent._is_risky("press", "format c:")
    assert agent._is_risky("type", "del /f /q")
    assert agent._is_risky("click", "delete account")
    assert agent._is_risky("click", "shutdown system")
    assert not agent._is_risky("click", "open file")
    assert not agent._is_risky("type", "hello world")


def test_laptop_agent_tools_scope():
    agent = LaptopAgent()
    assert agent.name == "LaptopControlAgent"
    assert "laptop_screenshot" in agent.scope.allowed_tools
    assert "laptop_click" in agent.scope.allowed_tools
    assert "laptop_type" in agent.scope.allowed_tools
    # Disallowed tools must not be in scope
    assert "shell" not in agent.scope.allowed_tools
    assert "network_recon" not in agent.scope.allowed_tools
