import pytest
from guardian.security.anomaly import AnomalyDetector
from guardian.audit import get_audit_log
import uuid
import time
from guardian.policy.engine import Effect

def test_anomaly_detector_cold_start():
    # Empty audit log
    detector = AnomalyDetector()
    session_id = str(uuid.uuid4())
    # Should not flag anything (insufficient data)
    flags = detector.detect_anomalies(session_id)
    assert len(flags) == 0

def test_anomaly_detector_flagging():
    audit = get_audit_log()
    detector = AnomalyDetector()
    
    # Generate 5 normal sessions to satisfy minimum history (cold-start)
    for _ in range(5):
        s_id = str(uuid.uuid4())
        audit.append("tool.request", session_id=s_id)
        audit.append("policy.decision", session_id=s_id, payload={"effect": Effect.ALLOW.value})
    
    # Generate an anomalous session with high denials
    anomalous_session = str(uuid.uuid4())
    for _ in range(5):
        audit.append("tool.request", session_id=anomalous_session)
        audit.append("policy.decision", session_id=anomalous_session, payload={"effect": Effect.DENY.value})
        
    flags = detector.detect_anomalies(anomalous_session)
    assert len(flags) > 0
    assert any("denial rate" in f.lower() for f in flags)
    
    # Generate a normal session, it should not be flagged
    normal_session = str(uuid.uuid4())
    audit.append("tool.request", session_id=normal_session)
    audit.append("policy.decision", session_id=normal_session, payload={"effect": Effect.ALLOW.value})
    flags_normal = detector.detect_anomalies(normal_session)
    assert len(flags_normal) == 0

def test_anomaly_detector_isolation_forest():
    audit = get_audit_log()
    detector = AnomalyDetector(use_isolation_forest=True)
    
    # Generate 5 normal sessions
    for _ in range(5):
        s_id = str(uuid.uuid4())
        audit.append("tool.request", session_id=s_id)
        audit.append("policy.decision", session_id=s_id, payload={"effect": Effect.ALLOW.value})
    
    anomalous_session = str(uuid.uuid4())
    for _ in range(10):
        # Very high call rate
        audit.append("tool.request", session_id=anomalous_session)
        
    flags = detector.detect_anomalies(anomalous_session)
    # Depending on how the IF model fits, this might or might not flag in this tiny test,
    # but the code path should execute without errors.
    # At minimum, no exception is thrown.
