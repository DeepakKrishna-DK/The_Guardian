"""
Guardian Security Report Formatter
=====================================
Converts ThreatRecord lists into human-readable reports.

Constitution reference: Section 11 (Transparency)
Every finding is presented in full — nothing is hidden or summarised away.
"""

from __future__ import annotations

from datetime import datetime

from guardian.security.threat import Severity, ThreatRecord


def format_report(
    findings: list[ThreatRecord],
    title: str = "Guardian Security Report",
    include_acknowledged: bool = False,
) -> str:
    """
    Return a plain-text security report.
    """
    active = [f for f in findings if not f.acknowledged]
    acked  = [f for f in findings if f.acknowledged]

    if not include_acknowledged:
        shown = active
    else:
        shown = findings

    lines = [
        "=" * 65,
        title,
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Total findings: {len(findings)}  Active: {len(active)}  Acknowledged: {len(acked)}",
        "=" * 65,
    ]

    if not shown:
        lines.append("\nNo findings to report.")
    else:
        by_severity = {s: [] for s in reversed(list(Severity))}
        for f in shown:
            by_severity[f.severity].append(f)

        for sev in reversed(list(Severity)):
            grp = by_severity[sev]
            if not grp:
                continue
            lines.append(f"\n[{sev.value.upper()}] — {len(grp)} finding(s)")
            lines.append("-" * 40)
            for f in grp:
                lines.append(f"  ID:       {f.id[:8]}...")
                lines.append(f"  Title:    {f.title}")
                lines.append(f"  Category: {f.category.value}")
                if "epss_score" in f.context:
                    lines.append(f"  EPSS:     {f.context['epss_score']}")
                lines.append(f"  Source:   {f.source}")
                lines.append(f"  Time:     {f.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                lines.append(f"  Desc:     {f.description}")
                lines.append(f"  Fix:      {f.recommendation}")
                if f.acknowledged:
                    lines.append(f"  Status:   ACKNOWLEDGED by {f.acknowledged_by}")
                lines.append("")

    lines.append("=" * 65)
    return "\n".join(lines)


def severity_summary(findings: list[ThreatRecord]) -> dict[str, int]:
    """Return count per severity level."""
    summary = {s.value: 0 for s in Severity}
    for f in findings:
        summary[f.severity.value] += 1
    return summary
