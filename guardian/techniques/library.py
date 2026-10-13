from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Technique:
    id: str
    name: str
    tactic: str
    description: str
    detection_notes: str
    associated_tools: list[str] = field(default_factory=list)
    associated_skills: list[str] = field(default_factory=list)
    risk_tier: str = "T1"
    requires_scope: bool = False

# A curated subset of MITRE ATT&CK® mapping strictly to Guardian's existing tools
# Note: MITRE ATT&CK® and ATT&CK are registered trademarks of The MITRE Corporation.
_LIBRARY = {
    "T1595": Technique(
        id="T1595",
        name="Active Scanning",
        tactic="Reconnaissance",
        description="Adversaries may execute active reconnaissance scans to gather information that can be used during targeting.",
        detection_notes="Monitor for anomalous network traffic and connection attempts to specific IP ranges or ports.",
        associated_tools=["network_recon"],
        risk_tier="T3",
        requires_scope=True
    ),
    "T1046": Technique(
        id="T1046",
        name="Network Service Discovery",
        tactic="Discovery",
        description="Adversaries may attempt to get a listing of services listening on remote hosts.",
        detection_notes="Look for TCP/UDP port scans across multiple hosts.",
        associated_tools=["network_recon"],
        risk_tier="T3",
        requires_scope=True
    ),
    "T1082": Technique(
        id="T1082",
        name="System Information Discovery",
        tactic="Discovery",
        description="Adversaries may attempt to get detailed information about the operating system and hardware.",
        detection_notes="Monitor commands such as systeminfo, uname.",
        associated_tools=["file_read", "file_write"],
        risk_tier="T2",
        requires_scope=False
    ),
}

class TechniqueLibrary:
    @staticmethod
    def get(technique_id: str) -> Optional[Technique]:
        return _LIBRARY.get(technique_id)

    @staticmethod
    def get_by_tool(tool_name: str) -> list[Technique]:
        return [t for t in _LIBRARY.values() if tool_name in t.associated_tools]
        
    @staticmethod
    def get_all() -> list[Technique]:
        return list(_LIBRARY.values())
