from datetime import datetime, timedelta
import json
import collections
from guardian.audit import get_audit_log
from guardian.logging.logger import get_logger

log = get_logger(__name__)

class AnomalyDetector:
    """
    Lightweight anomaly detection over audit log metadata.
    """
    def __init__(self, use_isolation_forest: bool = False):
        self.use_isolation_forest = use_isolation_forest
        self._audit = get_audit_log()
        
    def _fetch_recent_sessions(self, hours: int = 24) -> dict[str, list[dict]]:
        """Fetch audit events from the last N hours, grouped by session_id."""
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        # In a real impl we'd query the SQLite DB directly. 
        # The AuditLog might not have an easy query by time, so we just select all or fetch manually.
        # Since we have access to _conn, we can do a query.
        conn = self._audit._conn
        cursor = conn.cursor()
        cursor.execute("SELECT event_type, actor, session_id, payload_json, ts FROM audit_events WHERE ts >= ?", (since,))
        
        sessions = collections.defaultdict(list)
        for row in cursor.fetchall():
            event_type, actor, db_session_id, payload_str, ts = row
            try:
                payload = json.loads(payload_str)
            except:
                payload = {}
                
            session_id = db_session_id if db_session_id else payload.get("session_id", "unknown")
            sessions[session_id].append({
                "event_type": event_type,
                "actor": actor,
                "payload": payload,
                "timestamp": ts
            })
            
        return sessions

    def extract_features(self, session_events: list[dict]) -> dict[str, float]:
        """Extract features like call rate and denial rate for a session."""
        if not session_events:
            return {"call_rate": 0.0, "denial_rate": 0.0}
            
        calls = sum(1 for e in session_events if e["event_type"] == "tool.request")
        denials = sum(1 for e in session_events if e["event_type"] == "policy.decision" and e["payload"].get("effect") == "deny")
        
        # Calculate session duration
        timestamps = [datetime.fromisoformat(e["timestamp"]) for e in session_events if "timestamp" in e]
        if len(timestamps) > 1:
            duration = (max(timestamps) - min(timestamps)).total_seconds()
        else:
            duration = 1.0
            
        if duration <= 0:
            duration = 1.0
            
        call_rate = calls / duration
        denial_rate = denials / calls if calls > 0 else 0.0
        
        return {"call_rate": call_rate, "denial_rate": denial_rate}

    def detect_anomalies(self, current_session_id: str) -> list[str]:
        """
        Evaluate if the current session is anomalous compared to recent history.
        Returns a list of flagged reasons.
        """
        sessions = self._fetch_recent_sessions(hours=24)
        
        if current_session_id not in sessions:
            return []
            
        current_events = sessions[current_session_id]
        current_features = self.extract_features(current_events)
        
        # Require some minimum amount of history to establish a baseline
        if len(sessions) < 5:
            # Cold-start: insufficient data
            return []
            
        flags = []
        
        if self.use_isolation_forest:
            try:
                from sklearn.ensemble import IsolationForest
                import numpy as np
                
                # Prepare training data
                X = []
                for s_id, evts in sessions.items():
                    if s_id != current_session_id:
                        f = self.extract_features(evts)
                        X.append([f["call_rate"], f["denial_rate"]])
                        
                if len(X) >= 5:
                    clf = IsolationForest(contamination=0.1, random_state=42)
                    clf.fit(X)
                    
                    pred = clf.predict([[current_features["call_rate"], current_features["denial_rate"]]])
                    if pred[0] == -1:
                        flags.append("IsolationForest detected statistical anomaly")
            except ImportError:
                log.warning("scikit-learn not available, falling back to simple stats")
                
        # Simple statistical baseline
        if not flags:
            history = [self.extract_features(evts) for s_id, evts in sessions.items() if s_id != current_session_id]
            if history:
                avg_denial = sum(h["denial_rate"] for h in history) / len(history)
                # Flag if denial rate is unusually high (e.g. > 50% and higher than avg + 0.3)
                if current_features["denial_rate"] > 0.5 and current_features["denial_rate"] > avg_denial + 0.3:
                    flags.append(f"High policy denial rate ({current_features['denial_rate']:.2f})")
                    
        # Log if anomaly found
        for flag in flags:
            log.warning(f"Anomaly detected in session {current_session_id}: {flag}")
            self._audit.append("anomaly.flagged", payload={"session_id": current_session_id, "reason": flag})
            
        return flags
