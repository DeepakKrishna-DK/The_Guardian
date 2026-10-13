import pytest
from guardian.techniques.library import TechniqueLibrary
from guardian.security.threat import ThreatRecord, Severity, Category, ThreatStore

def test_technique_library():
    t = TechniqueLibrary.get("T1595")
    assert t is not None
    assert t.name == "Active Scanning"
    assert "network_recon" in t.associated_tools

    t_by_tool = TechniqueLibrary.get_by_tool("network_recon")
    assert len(t_by_tool) >= 2
    assert t in t_by_tool

def test_threat_technique_tagging():
    record = ThreatRecord.new(
        severity=Severity.HIGH,
        category=Category.NETWORK,
        title="Test",
        description="Test desc",
        recommendation="Fix",
        source="tester",
        technique_id="T1595"
    )
    
    assert record.technique_id == "T1595"
    
    store = ThreatStore(":memory:")
    store.save(record)
    
    loaded = store.list_all()[0]
    assert loaded.technique_id == "T1595"
