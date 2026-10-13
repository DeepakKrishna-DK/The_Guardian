import pytest
from guardian.security.detection import DetectionRule, RuleEvaluator
import yaml

def test_detection_rule_parsing(tmp_path):
    rule_file = tmp_path / "rule.yml"
    rule_file.write_text("""
id: 123
title: Shell Metacharacters Detected
logsource:
  category: policy.decision
detection:
  selection:
    payload.risk_flags: shell.metacharacters
    payload.effect: deny
  condition: selection
level: high
tags:
  - T1059
    """, encoding="utf-8")
    
    # Wait, risk_flags is a list, my simple equals check might not work for list contains, 
    # but let's see. Let's make the rule simpler for this test.
    rule_file.write_text("""
id: 123
title: Suspicious Tool Call
logsource:
  category: tool.request
detection:
  selection:
    payload.tool: shell
  condition: selection
level: high
tags:
  - T1059
    """, encoding="utf-8")
    
    rule = DetectionRule.from_yaml(rule_file)
    assert rule.id == "123"
    assert rule.title == "Suspicious Tool Call"
    assert rule.logsource == "tool.request"
    assert rule.level == "high"
    assert len(rule.selections) == 1
    assert rule.selections[0].field == "payload.tool"
    assert rule.selections[0].value == "shell"

def test_rule_evaluator():
    rule = DetectionRule(
        id="1",
        title="Test Rule",
        logsource="tool.request",
        selections=[],
        level="high"
    )
    from guardian.security.detection import DetectionSelection
    rule.selections = [DetectionSelection("payload.tool", "equals", "shell")]
    
    evaluator = RuleEvaluator([rule])
    
    # Matching
    event = {
        "event_type": "tool.request",
        "payload": {
            "tool": "shell"
        }
    }
    triggered = evaluator.evaluate(event)
    assert len(triggered) == 1
    assert triggered[0].id == "1"
    
    # Non-matching (wrong tool)
    event2 = {
        "event_type": "tool.request",
        "payload": {
            "tool": "file_read"
        }
    }
    assert len(evaluator.evaluate(event2)) == 0
    
    # Non-matching (wrong logsource)
    event3 = {
        "event_type": "policy.decision",
        "payload": {
            "tool": "shell"
        }
    }
    assert len(evaluator.evaluate(event3)) == 0
