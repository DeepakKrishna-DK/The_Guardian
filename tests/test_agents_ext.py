import pytest
from guardian.core.agents import AnalysisAgent, ResponseAgent
from guardian.security.threat import ThreatRecord, Severity, Category
import uuid

def test_analysis_agent_summary(monkeypatch):
    # Mock anomaly detector
    from guardian.security.anomaly import AnomalyDetector
    def mock_detect(*args, **kwargs):
        return ["High policy denial rate (1.00)"]
    monkeypatch.setattr(AnomalyDetector, "detect_anomalies", mock_detect)
    
    findings = []
    
    # 1. High EPSS finding
    rec1 = ThreatRecord.new(Severity.HIGH, Category.GENERAL, "CVE-1", "Test", "rec", "src")
    rec1.context = {"cve_id": "CVE-1", "epss_score": "0.95"}
    findings.append(rec1)
    
    # 2. Low EPSS finding
    rec2 = ThreatRecord.new(Severity.LOW, Category.GENERAL, "CVE-2", "Test", "rec", "src")
    rec2.context = {"cve_id": "CVE-2", "epss_score": "0.01"}
    findings.append(rec2)
    
    # 3. Unknown EPSS finding
    rec3 = ThreatRecord.new(Severity.LOW, Category.GENERAL, "CVE-3", "Test", "rec", "src")
    rec3.context = {"cve_id": "CVE-3", "epss_score": "unknown"}
    findings.append(rec3)
    
    summary = AnalysisAgent.produce_summary("mock_session", findings)
    
    assert summary["anomalies"] == ["High policy denial rate (1.00)"]
    assert len(summary["high_priority_cves"]) == 1
    assert summary["high_priority_cves"][0]["cve"] == "CVE-1"
    assert summary["high_priority_cves"][0]["epss"] == 0.95
    
def test_response_agent_suggestions():
    # Test based on the seeded sequence T1595 -> T1046
    suggestions = ResponseAgent.suggest_next_steps(["T1595"])
    assert len(suggestions) > 0
    assert "T1046" in suggestions[0]
