"""
Guardian Skill System — Public API
=====================================
Usage:
    from guardian.skills import get_skill_registry, get_skill_router
    registry = get_skill_registry()
    router = get_skill_router(base_prompt)
    decision = router.route("write a pytest unit test")
"""

from __future__ import annotations

from guardian.skills.base import (
    ClassificationResult,
    Skill,
    SkillName,
    SkillResult,
)
from guardian.skills.classifier import SkillClassifier
from guardian.skills.loader import load_skills_from_directory
from guardian.skills.router import RoutingDecision, SkillRouter

from pathlib import Path
LIBRARY_DIR = Path(__file__).parent / "library"
ALL_SKILLS = load_skills_from_directory(LIBRARY_DIR)
GUARDIAN_SKILL = next((s for s in ALL_SKILLS if s.name == "guardian"), None)
SCHOLAR_SKILL = next((s for s in ALL_SKILLS if s.name == "scholar"), None)
BUILDER_SKILL = next((s for s in ALL_SKILLS if s.name == "builder"), None)
CRITIC_SKILL = next((s for s in ALL_SKILLS if s.name == "critic"), None)
TESTER_SKILL = next((s for s in ALL_SKILLS if s.name == "tester"), None)
SECURITY_SKILL = next((s for s in ALL_SKILLS if s.name == "security_guardian"), None)
PENTEST_SKILL = next((s for s in ALL_SKILLS if s.name == "pentest_copilot"), None)

class SkillRegistry:
    """
    Registry of available Guardian skills.
    Provides lookup by name and ordered listing.
    """

    def __init__(self, skills: list[Skill] | None = None) -> None:
        skills = skills or ALL_SKILLS
        self._skills: dict[str, Skill] = {s.name: s for s in skills}
        self._ordered: list[Skill] = list(skills)

    def get(self, name: str) -> Skill | None:
        """Return skill by name (case-insensitive), or None."""
        return self._skills.get(name.lower())

    def get_or_default(self, name: str) -> Skill:
        """Return skill by name, falling back to the guardian (default) skill."""
        return self._skills.get(name.lower(), GUARDIAN_SKILL)

    def list_all(self) -> list[Skill]:
        return list(self._ordered)

    def names(self) -> list[str]:
        return [s.name for s in self._ordered]

    def __len__(self) -> int:
        return len(self._skills)

# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

_registry: SkillRegistry | None = None
_classifier: SkillClassifier | None = None

def get_skill_registry() -> SkillRegistry:
    """Return the shared SkillRegistry (lazy init)."""
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry


def get_skill_classifier() -> SkillClassifier:
    """Return the shared SkillClassifier (lazy init)."""
    global _classifier
    if _classifier is None:
        registry = get_skill_registry()
        _classifier = SkillClassifier(
            skills=registry.list_all(),
            default_skill=GUARDIAN_SKILL,
        )
    return _classifier


def get_skill_router(base_system_prompt: str) -> SkillRouter:
    """
    Create a SkillRouter with the shared classifier and given base prompt.
    A new router is created each time (base_prompt may vary by session).
    """
    return SkillRouter(
        classifier=get_skill_classifier(),
        base_system_prompt=base_system_prompt,
    )


__all__ = [
    "ALL_SKILLS",
    "BUILDER_SKILL",
    "ClassificationResult",
    "CRITIC_SKILL",
    "GUARDIAN_SKILL",
    "RoutingDecision",
    "SCHOLAR_SKILL",
    "Skill",
    "SkillClassifier",
    "SkillName",
    "SkillRegistry",
    "SkillResult",
    "SkillRouter",
    "TESTER_SKILL",
    "get_skill_classifier",
    "get_skill_registry",
    "get_skill_router",
]
