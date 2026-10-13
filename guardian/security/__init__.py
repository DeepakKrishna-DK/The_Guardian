"""
Guardian Security Module — Public API
=======================================
Usage:
    from guardian.security import SecurityGuardian, get_security_guardian
    sg = get_security_guardian()
    report = sg.run_audit()
"""

from __future__ import annotations

from pathlib import Path

from guardian.logging.logger import get_logger
from guardian.security.audit import SelfAuditScanner
from guardian.security.report import format_report, severity_summary
from guardian.security.scanner import EnvironmentScanner
from guardian.security.threat import (
    Category,
    Severity,
    ThreatRecord,
    ThreatStore,
)

log = get_logger(__name__)

_DEFAULT_DB = Path(__file__).resolve().parent.parent.parent / "memory" / "threats.db"


class SecurityGuardian:
    """
    Facade for all Guardian security capabilities.

    Coordinates:
      - SelfAuditScanner: Guardian configuration self-review
      - EnvironmentScanner: local environment anomalies
      - ThreatStore: persistent finding history
    """

    def __init__(
        self,
        workspace_root: Path,
        store: ThreatStore,
    ) -> None:
        self.workspace = workspace_root
        self.store = store
        self._audit_scanner = SelfAuditScanner(workspace_root)
        self._env_scanner   = EnvironmentScanner(workspace_root)

    def run_audit(self, persist: bool = True) -> list[ThreatRecord]:
        """
        Run the self-audit scanner. Returns findings.
        If persist=True, saves findings to the ThreatStore.
        """
        findings = self._audit_scanner.run()
        if persist:
            self.store.save_many(findings)
        return findings

    def run_scan(self, persist: bool = True) -> list[ThreatRecord]:
        """
        Run the environment scanner. Returns findings.
        If persist=True, saves findings to the ThreatStore.
        """
        findings = self._env_scanner.run()
        if persist:
            self.store.save_many(findings)
        return findings

    def run_all(self, persist: bool = True) -> list[ThreatRecord]:
        """Run both audit and environment scan."""
        all_findings = self.run_audit(persist=False) + self.run_scan(persist=False)
        if persist:
            self.store.save_many(all_findings)
        return all_findings

    def report(self, include_acknowledged: bool = False) -> str:
        """Generate a plain-text report of stored findings."""
        findings = self.store.list_all()
        return format_report(findings, include_acknowledged=include_acknowledged)

    def status(self) -> dict[str, object]:
        """Return a summary dict for guardian status."""
        active = self.store.list_active()
        return {
            "active_threats": len(active),
            "severity_summary": severity_summary(active),
            "db_path": str(self.store._db_path),
        }


_guardian: SecurityGuardian | None = None


def get_security_guardian(
    workspace_root: Path | None = None,
    db_path: str | None = None,
) -> SecurityGuardian:
    """Return the shared SecurityGuardian singleton."""
    global _guardian
    if _guardian is None:
        root = workspace_root or Path(__file__).resolve().parent.parent.parent
        store = ThreatStore(db_path or str(_DEFAULT_DB))
        _guardian = SecurityGuardian(workspace_root=root, store=store)
        log.info(f"SecurityGuardian initialised: workspace={root}")
    return _guardian


def reset_security_guardian() -> None:
    """Reset the singleton (for testing)."""
    global _guardian
    _guardian = None


__all__ = [
    "Category",
    "SecurityGuardian",
    "SelfAuditScanner",
    "EnvironmentScanner",
    "Severity",
    "ThreatRecord",
    "ThreatStore",
    "format_report",
    "get_security_guardian",
    "reset_security_guardian",
    "severity_summary",
]
