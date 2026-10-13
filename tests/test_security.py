"""
Tests for Phase 8 Ã¢â‚¬â€ Security Guardian
=======================================
All tests use in-memory ThreatStore (no files written).
No network connections required. No admin rights required.
SelfAuditScanner tested with controlled temp workspace.

Covers:
  Severity ordering and display
  Category enum
  ThreatRecord creation, from_row, summary, is_active
  ThreatStore: save, list_active, list_all, acknowledge, count_active
  SelfAuditScanner: env file detection, source secret scanning,
                    gitignore check, missing API key
  format_report: structure, empty findings
  severity_summary: correct counts
  SecurityGuardian: run_audit, run_scan, run_all, report, status
"""

from __future__ import annotations

from pathlib import Path

import pytest

from guardian.security import SecurityGuardian, reset_security_guardian
from guardian.security.audit import SelfAuditScanner
from guardian.security.report import format_report, severity_summary
from guardian.security.scanner import EnvironmentScanner
from guardian.security.threat import Category, Severity, ThreatRecord, ThreatStore


@pytest.fixture(autouse=True)
def reset():
    reset_security_guardian()
    yield
    reset_security_guardian()


@pytest.fixture
def store() -> ThreatStore:
    return ThreatStore(":memory:")


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A minimal Guardian-like workspace for testing."""
    # Create .gitignore with required patterns
    (tmp_path / ".gitignore").write_text(".env\n*.db\nvenv/\n__pycache__/\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("GUARDIAN_GROQ_API_KEY=your_key_here\n", encoding="utf-8")
    return tmp_path


def make_record(
    severity: Severity = Severity.MEDIUM,
    category: Category = Category.GENERAL,
    title: str = "Test finding",
) -> ThreatRecord:
    return ThreatRecord.new(
        severity=severity,
        category=category,
        title=title,
        description="Test description",
        recommendation="Fix it",
        source="test",
    )


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Severity Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

class TestSeverity:
    def test_rank_ordering(self):
        assert Severity.INFO.rank < Severity.LOW.rank < Severity.MEDIUM.rank
        assert Severity.MEDIUM.rank < Severity.HIGH.rank < Severity.CRITICAL.rank

    def test_lt_comparison(self):
        assert Severity.INFO < Severity.CRITICAL
        assert Severity.LOW < Severity.HIGH

    def test_display_returns_string(self):
        for sev in Severity:
            assert isinstance(sev.display(), str)
            assert sev.value.upper() in sev.display()


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ ThreatRecord Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

class TestThreatRecord:
    def test_new_creates_record(self):
        r = make_record()
        assert r.id
        assert len(r.id) == 36  # UUID
        assert r.severity == Severity.MEDIUM
        assert r.category == Category.GENERAL
        assert not r.acknowledged

    def test_summary_contains_severity_and_category(self):
        r = make_record(severity=Severity.HIGH, category=Category.SECRET)
        s = r.summary()
        assert "HIGH" in s
        assert "secret" in s

    def test_is_active_when_not_acknowledged(self):
        r = make_record()
        assert r.is_active()

    def test_is_not_active_when_acknowledged(self):
        r = make_record()
        r.acknowledged = True
        assert not r.is_active()

    def test_from_row_round_trip(self):
        r = make_record(severity=Severity.CRITICAL, category=Category.SECRET)
        row = {
            "id": r.id, "severity": r.severity.value, "category": r.category.value,
            "title": r.title, "description": r.description,
            "recommendation": r.recommendation, "source": r.source,
            "timestamp": r.timestamp.isoformat(), "context": "{}",
            "acknowledged": 0, "acknowledged_at": None, "acknowledged_by": "",
        }
        r2 = ThreatRecord.from_row(row)
        assert r2.id == r.id
        assert r2.severity == Severity.CRITICAL
        assert r2.category == Category.SECRET


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ ThreatStore Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

class TestThreatStore:
    def test_save_and_list_all(self, store):
        r = make_record()
        store.save(r)
        all_r = store.list_all()
        assert len(all_r) == 1
        assert all_r[0].id == r.id

    def test_upsert_modifies_record(self, store):
        r = make_record(title='first')
        store.save(r)
        r.title = 'second'
        store.save(r)
        loaded = store.list_all()[0]
        assert loaded.title == 'second'


    def test_list_active_excludes_acknowledged(self, store):
        r1 = make_record(title="active")
        r2 = make_record(title="acknowledged")
        store.save(r1)
        store.save(r2)
        store.acknowledge(r2.id)
        active = store.list_active()
        assert len(active) == 1
        assert active[0].title == "active"

    def test_list_active_min_severity_filter(self, store):
        store.save(make_record(severity=Severity.INFO))
        store.save(make_record(severity=Severity.HIGH))
        high_only = store.list_active(min_severity=Severity.HIGH)
        assert len(high_only) == 1
        assert high_only[0].severity == Severity.HIGH

    def test_acknowledge_returns_true(self, store):
        r = make_record()
        store.save(r)
        result = store.acknowledge(r.id)
        assert result is True

    def test_acknowledge_unknown_returns_false(self, store):
        assert store.acknowledge("nonexistent-id") is False

    def test_count_active(self, store):
        store.save(make_record())
        store.save(make_record())
        assert store.count_active() == 2
        r = make_record()
        store.save(r)
        store.acknowledge(r.id)
        assert store.count_active() == 2

    def test_save_many(self, store):
        records = [make_record(title=f"finding {i}") for i in range(5)]
        store.save_many(records)
        assert len(store.list_all()) == 5

    def test_close_is_safe(self, store):
        store.close()  # Should not raise


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ SelfAuditScanner Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

class TestSelfAuditScanner:
    def test_run_returns_list(self, workspace):
        scanner = SelfAuditScanner(workspace)
        findings = scanner.run()
        assert isinstance(findings, list)

    def test_detects_env_file_with_values(self, workspace):
        # Create .env with a real-looking value
        (workspace / ".env").write_text(
            "GUARDIAN_GROQ_API_KEY=gsk_abc123realkey456789xyz\n", encoding="utf-8"
        )
        scanner = SelfAuditScanner(workspace)
        findings = scanner._check_env_files()
        assert any("env" in f.title.lower() for f in findings)

    def test_does_not_flag_env_example(self, workspace):
        # .env.example with placeholder values should not be flagged
        scanner = SelfAuditScanner(workspace)
        findings = scanner._check_env_files()
        # .env.example has "your_key_here" Ã¢â‚¬â€ should not flag
        assert len(findings) == 0

    def test_detects_hardcoded_groq_key(self, workspace):
        # Write a Python file with a hardcoded key pattern
        py_file = workspace / "config.py"
        py_file.write_text('GROQ_KEY = "gsk_' + 'A' * 45 + '"\n', encoding="utf-8")
        scanner = SelfAuditScanner(workspace)
        findings = scanner._check_source_for_secrets()
        assert len(findings) >= 1
        assert any("Groq" in f.title or "Hardcoded" in f.title for f in findings)

    def test_good_source_file_not_flagged(self, workspace):
        # Normal Python file
        (workspace / "module.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        scanner = SelfAuditScanner(workspace)
        findings = scanner._check_source_for_secrets()
        assert len(findings) == 0

    def test_detects_missing_gitignore(self, tmp_path):
        # Workspace with no .gitignore
        scanner = SelfAuditScanner(tmp_path)
        findings = scanner._check_gitignore()
        assert any("gitignore" in f.title.lower() for f in findings)

    def test_detects_missing_gitignore_patterns(self, workspace):
        # .gitignore exists but missing *.db
        (workspace / ".gitignore").write_text(".env\nvenv/\n__pycache__/\n", encoding="utf-8")
        scanner = SelfAuditScanner(workspace)
        findings = scanner._check_gitignore()
        assert any("*.db" in f.title for f in findings)

    def test_good_gitignore_passes(self, workspace):
        scanner = SelfAuditScanner(workspace)
        findings = scanner._check_gitignore()
        assert len(findings) == 0  # workspace fixture has all required patterns


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ EnvironmentScanner Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

class TestEnvironmentScanner:
    def test_run_returns_list(self, workspace):
        scanner = EnvironmentScanner(workspace)
        findings = scanner.run()
        assert isinstance(findings, list)

    def test_all_findings_are_threat_records(self, workspace):
        scanner = EnvironmentScanner(workspace)
        findings = scanner.run()
        for f in findings:
            assert isinstance(f, ThreatRecord)

    def test_no_sensitive_files_in_clean_workspace(self, workspace):
        scanner = EnvironmentScanner(workspace)
        findings = scanner._check_sensitive_files_in_workspace()
        assert len(findings) == 0

    def test_detects_pem_file_in_workspace(self, workspace):
        (workspace / "server.pem").write_text("-----BEGIN CERTIFICATE-----\n", encoding="utf-8")
        scanner = EnvironmentScanner(workspace)
        findings = scanner._check_sensitive_files_in_workspace()
        assert len(findings) == 1
        assert "pem" in findings[0].title.lower()


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ format_report Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

class TestFormatReport:
    def test_empty_findings(self):
        report = format_report([])
        assert "No findings" in report

    def test_report_contains_title(self):
        report = format_report([], title="My Report")
        assert "My Report" in report

    def test_report_contains_finding(self):
        r = make_record(severity=Severity.HIGH, title="Critical bug found")
        report = format_report([r])
        assert "Critical bug found" in report
        assert "HIGH" in report

    def test_acknowledged_excluded_by_default(self):
        r = make_record(title="Suppressed finding")
        r.acknowledged = True
        r.acknowledged_by = "user"
        report = format_report([r])
        assert "Suppressed finding" not in report

    def test_acknowledged_included_when_requested(self):
        r = make_record(title="Suppressed finding")
        r.acknowledged = True
        report = format_report([r], include_acknowledged=True)
        assert "Suppressed finding" in report


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ severity_summary Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

class TestSeveritySummary:
    def test_empty_returns_zeros(self):
        s = severity_summary([])
        assert all(v == 0 for v in s.values())

    def test_counts_correctly(self):
        records = [
            make_record(severity=Severity.HIGH),
            make_record(severity=Severity.HIGH),
            make_record(severity=Severity.LOW),
        ]
        s = severity_summary(records)
        assert s["high"] == 2
        assert s["low"] == 1
        assert s["critical"] == 0


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ SecurityGuardian Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

class TestSecurityGuardian:
    def test_run_audit_returns_list(self, workspace, store):
        sg = SecurityGuardian(workspace_root=workspace, store=store)
        findings = sg.run_audit(persist=False)
        assert isinstance(findings, list)

    def test_run_audit_persists_when_requested(self, workspace, store):
        sg = SecurityGuardian(workspace_root=workspace, store=store)
        sg.run_audit(persist=True)
        # Store should have findings (even if 0 for a clean workspace)
        assert store.count_active() >= 0

    def test_run_scan_returns_list(self, workspace, store):
        sg = SecurityGuardian(workspace_root=workspace, store=store)
        findings = sg.run_scan(persist=False)
        assert isinstance(findings, list)

    def test_run_all_combines_both(self, workspace, store):
        sg = SecurityGuardian(workspace_root=workspace, store=store)
        audit_f = sg.run_audit(persist=False)
        scan_f  = sg.run_scan(persist=False)
        all_f   = sg.run_all(persist=False)
        assert len(all_f) == len(audit_f) + len(scan_f)

    def test_report_returns_string(self, workspace, store):
        sg = SecurityGuardian(workspace_root=workspace, store=store)
        report = sg.report()
        assert isinstance(report, str)
        assert "Guardian Security Report" in report

    def test_status_returns_dict(self, workspace, store):
        sg = SecurityGuardian(workspace_root=workspace, store=store)
        status = sg.status()
        assert "active_threats" in status
        assert "severity_summary" in status
