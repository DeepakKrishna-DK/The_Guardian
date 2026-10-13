from dataclasses import dataclass, field
import yaml
from pathlib import Path
from typing import Any

@dataclass
class DetectionSelection:
    field: str
    condition: str
    value: Any

@dataclass
class DetectionRule:
    id: str
    title: str
    logsource: str
    selections: list[DetectionSelection]
    level: str
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: Path) -> "DetectionRule":
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        selections = []
        det = data.get("detection", {})
        for sel_name, sel_data in det.items():
            if sel_name == "condition":
                continue
            for k, v in sel_data.items():
                # simplistic condition parsing for now: field matches value
                selections.append(DetectionSelection(field=k, condition="equals", value=v))
                
        return cls(
            id=str(data.get("id", "")),
            title=data.get("title", ""),
            logsource=data.get("logsource", {}).get("category", ""),
            selections=selections,
            level=data.get("level", "low"),
            tags=data.get("tags", [])
        )

class RuleEvaluator:
    def __init__(self, rules: list[DetectionRule]):
        self.rules = rules
        
    def evaluate(self, event: dict[str, Any]) -> list[DetectionRule]:
        """
        Evaluate a single audit-log event (dictionary form).
        Returns a list of triggered rules.
        """
        triggered = []
        for rule in self.rules:
            if rule.logsource != event.get("event_type", ""):
                continue
                
            matched_all = True
            for sel in rule.selections:
                # Traverse event payload
                val = self._get_field(event, sel.field)
                if sel.condition == "equals":
                    if val != sel.value:
                        matched_all = False
                        break
            
            if matched_all and rule.selections:
                triggered.append(rule)
                
        return triggered

    def _get_field(self, event: dict, field_path: str) -> Any:
        parts = field_path.split('.')
        curr = event
        for p in parts:
            if isinstance(curr, dict) and p in curr:
                curr = curr[p]
            else:
                return None
        return curr
