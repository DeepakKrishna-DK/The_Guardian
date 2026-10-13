"""
Guardian Skill System — Base Types
====================================
Defines the core data structures for all Guardian skills.

Constitution reference: Section 6 (Agent Roles), Section 9 (Skills Structure)

A Skill is a named, prompt-augmented operating mode that Guardian activates
based on the nature of the user's request. Skills do NOT create independent
agents — they modify how the same model processes the request.

Guardian always retains overall authority (Section 3 — Authority Model).
Active skill is always shown to the user (Section 11 — Transparency).

Built-in skill names (§6):
  guardian  — Default: general assistance, orchestration
  scholar   — Research, knowledge retrieval, explanation
  builder   — Code writing, implementation, debugging
  critic    — Review, evaluation, security analysis
  tester    — Test creation, verification, coverage
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SkillName(str, Enum):
    """Canonical skill identifiers."""
    GUARDIAN = "guardian"
    SCHOLAR  = "scholar"
    BUILDER  = "builder"
    CRITIC   = "critic"
    TESTER   = "tester"
    SECURITY = "security_guardian"
    PENTEST  = "pentest_copilot"


@dataclass
class Skill:
    """
    A Guardian skill definition.

    Fields:
        name          Canonical identifier (SkillName)
        title         Human-readable title for display
        description   What this skill does
        prompt_addition  Text appended to the base system prompt when active.
                         This shapes how the model responds for this skill.
        keywords      Trigger words/phrases for heuristic classification.
                      Case-insensitive. Longer phrases matched before shorter.
        icon          ASCII-safe display character or short label
        min_confidence  Minimum classifier score (keyword matches) to activate.
                        Lower = more easily triggered.
    """
    name: str
    title: str
    description: str
    prompt_addition: str
    keywords: list[str]
    icon: str = ""
    min_confidence: int = 1
    local_only: bool = False
    
    # M1 Extensions
    risk_tier: int = 0
    requires_scope: bool = False
    target_arg: str | None = None
    dependencies: list[str] = field(default_factory=list)

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Skill):
            return self.name == other.name
        return NotImplemented

    def display_label(self) -> str:
        """Short label for chat display."""
        icon = f"{self.icon} " if self.icon else ""
        return f"{icon}{self.title}"


@dataclass
class ClassificationResult:
    """
    Output from SkillClassifier.classify().

    Fields:
        skill        The selected Skill
        confidence   Number of keyword matches that triggered this skill
        matched_on   Which keywords matched (for transparency logging)
        is_default   True if no skill matched and the default was used
    """
    skill: Skill
    confidence: int
    matched_on: list[str] = field(default_factory=list)
    is_default: bool = False

    def __bool__(self) -> bool:
        """True if a specific skill was matched (not just the default)."""
        return not self.is_default

    def summary(self) -> str:
        if self.is_default:
            return "skill=guardian (default, no match)"
        return (
            f"skill={self.skill.name} "
            f"confidence={self.confidence} "
            f"matched={self.matched_on[:3]}"
        )


@dataclass
class SkillResult:
    """
    Wraps a GuardianResponse with skill metadata.
    Used when the orchestrator processes a skill-routed request.
    """
    content: str
    skill: Skill
    classification: ClassificationResult
    model_provider: str
    model_name: str
    session_turn: int
    duration_ms: float
    tokens_used: int = 0
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None and bool(self.content)
