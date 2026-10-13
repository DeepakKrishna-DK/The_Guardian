from guardian.security.epss import EPSSClient
from guardian.security.anomaly import AnomalyDetector
from guardian.security.threat import ThreatRecord
from guardian.security.attack_path import AttackPathPredictor
from guardian.core.agents import SubAgent

class ReconAgentImpl(SubAgent):
    pass

class AnalysisAgentImpl(SubAgent):
    def produce_summary(self, session_id: str, current_findings: list[ThreatRecord]) -> dict:
        """
        Consumes EPSS scores and anomaly flags to produce a prioritized summary.
        """
        summary = {"high_priority_cves": [], "anomalies": [], "detections": []}
        
        # 1. Fetch anomalies
        detector = AnomalyDetector()
        flags = detector.detect_anomalies(session_id)
        summary["anomalies"] = flags
        
        # 1.5. Fetch detections
        from guardian.security.detection import RuleEvaluator, DetectionRule
        from guardian.config.settings import settings
        from guardian.audit import get_audit_log
        import json
        
        # Load all yaml rules in .guardian/rules
        rules_dir = settings.project_root / ".guardian" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        det_rules = []
        for p in rules_dir.glob("*.yml"):
            try:
                det_rules.append(DetectionRule.from_yaml(p))
            except Exception:
                pass
                
        evaluator = RuleEvaluator(det_rules)
        audit = get_audit_log()
        c = audit._conn.cursor()
        c.execute("SELECT event_type, payload_json FROM audit_events WHERE session_id=?", (session_id,))
        
        triggered_ids = set()
        for row in c.fetchall():
            try:
                event_type = row[0]
                payload = json.loads(row[1])
                event = {"event_type": event_type, "payload": payload}
                trig = evaluator.evaluate(event)
                for t in trig:
                    if t.id not in triggered_ids:
                        summary["detections"].append(f"{t.id}: {t.title}")
                        triggered_ids.add(t.id)
            except Exception:
                pass
        
        # 2. Extract CVEs with EPSS score > 0.5 (for example)
        for finding in current_findings:
            score_str = finding.context.get("epss_score")
            if score_str and score_str != "unknown":
                try:
                    score = float(score_str)
                    if score > 0.1: # Prioritize anything with some EPSS risk
                        summary["high_priority_cves"].append({
                            "cve": finding.context.get("cve_id"),
                            "epss": score,
                            "title": finding.title
                        })
                except ValueError:
                    pass
                    
        return summary

class ResponseAgentImpl(SubAgent):
    def suggest_next_steps(self, observed_techniques: list[str]) -> list[str]:
        """
        Consumes attack-path predictions to suggest next investigative steps.
        Never executes them.
        """
        predictor = AttackPathPredictor()
        if not observed_techniques:
            return []
            
        current = observed_techniques[-1]
        probs = predictor.predict_next(current)
        
        suggestions = []
        for nxt, p in probs:
            suggestions.append(f"Consider investigating {nxt} (probability {p:.2f})")
            
        return suggestions
