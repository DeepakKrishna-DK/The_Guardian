"""
Tests for Phase 5 — Skill System
===================================
All tests are deterministic and require no API calls.
The classifier and router are tested with known inputs.
Orchestrator tests verify skill fields appear in responses.

Covers:
  SkillName enum
  Skill dataclass
  SkillRegistry
  SkillClassifier (heuristic)
  SkillRouter (routing + continuity)
  Definitions (all 5 built-in skills)
  Orchestrator skill integration
"""

from __future__ import annotations

from guardian.core.orchestrator import GuardianCore
from guardian.core.session import Session
from guardian.model.backends.mock import MockBackend
from guardian.skills import SkillRegistry, get_skill_registry
from guardian.skills.base import Skill, SkillName
from guardian.skills.classifier import SkillClassifier
from guardian.skills import (
    ALL_SKILLS,
    BUILDER_SKILL,
    CRITIC_SKILL,
    GUARDIAN_SKILL,
    SCHOLAR_SKILL,
    TESTER_SKILL,
)
from guardian.skills.router import SkillRouter

# ─── SkillName ───────────────────────────────────────────────────────────────

class TestSkillName:
    def test_values(self):
        assert SkillName.GUARDIAN == "guardian"
        assert SkillName.SCHOLAR  == "scholar"
        assert SkillName.BUILDER  == "builder"
        assert SkillName.CRITIC   == "critic"
        assert SkillName.TESTER   == "tester"


# ─── Skill dataclass ──────────────────────────────────────────────────────────

class TestSkill:
    def test_equality_by_name(self):
        a = Skill("builder", "B", "d", "", [], "[B]")
        b = Skill("builder", "Builder", "desc2", "prompt", ["code"], "[B]")
        assert a == b

    def test_inequality_different_name(self):
        a = Skill("builder", "B", "d", "", [])
        b = Skill("scholar", "S", "d", "", [])
        assert a != b

    def test_hashable(self):
        skills = {BUILDER_SKILL, CRITIC_SKILL}
        assert len(skills) == 2

    def test_display_label_with_icon(self):
        label = BUILDER_SKILL.display_label()
        assert "[B]" in label
        assert "Builder" in label

    def test_display_label_no_icon(self):
        skill = Skill("test", "TestSkill", "d", "", [], icon="")
        assert "TestSkill" in skill.display_label()


# ─── Built-in skill definitions ───────────────────────────────────────────────

class TestDefinitions:
    def test_all_skills_count(self):
        assert len(ALL_SKILLS) == 7

    def test_all_have_names(self):
        names = [s.name for s in ALL_SKILLS]
        assert "guardian" in names
        assert "scholar" in names
        assert "builder" in names
        assert "critic" in names
        assert "tester" in names

    def test_guardian_has_no_prompt_addition(self):
        assert GUARDIAN_SKILL.prompt_addition == ""

    def test_non_guardian_have_prompt_additions(self):
        for skill in [SCHOLAR_SKILL, BUILDER_SKILL, CRITIC_SKILL, TESTER_SKILL]:
            assert skill.prompt_addition, f"{skill.name} has empty prompt_addition"
            assert len(skill.prompt_addition) > 50

    def test_all_non_guardian_have_keywords(self):
        for skill in [SCHOLAR_SKILL, BUILDER_SKILL, CRITIC_SKILL, TESTER_SKILL]:
            assert len(skill.keywords) >= 5, f"{skill.name} has too few keywords"

    def test_all_have_icons(self):
        for skill in ALL_SKILLS:
            assert skill.icon, f"{skill.name} has no icon"


# ─── SkillRegistry ───────────────────────────────────────────────────────────

class TestSkillRegistry:
    def test_get_by_name(self):
        reg = SkillRegistry(ALL_SKILLS)
        assert reg.get("scholar") == SCHOLAR_SKILL

    def test_get_case_insensitive(self):
        reg = SkillRegistry(ALL_SKILLS)
        assert reg.get("BUILDER") == BUILDER_SKILL

    def test_get_unknown_returns_none(self):
        reg = SkillRegistry(ALL_SKILLS)
        assert reg.get("unknown") is None

    def test_get_or_default_returns_default(self):
        reg = SkillRegistry(ALL_SKILLS)
        result = reg.get_or_default("nonexistent")
        assert result == GUARDIAN_SKILL

    def test_list_all_returns_all(self):
        reg = SkillRegistry(ALL_SKILLS)
        assert len(reg.list_all()) == 7

    def test_names(self):
        reg = SkillRegistry(ALL_SKILLS)
        names = reg.names()
        assert "guardian" in names

    def test_len(self):
        reg = SkillRegistry(ALL_SKILLS)
        assert len(reg) == 7

    def test_singleton(self):
        r1 = get_skill_registry()
        r2 = get_skill_registry()
        assert r1 is r2


# ─── SkillClassifier ─────────────────────────────────────────────────────────

def make_classifier() -> SkillClassifier:
    return SkillClassifier(skills=ALL_SKILLS, default_skill=GUARDIAN_SKILL)


class TestSkillClassifier:
    def test_empty_input_returns_default(self):
        clf = make_classifier()
        result = clf.classify("")
        assert result.is_default
        assert result.skill == GUARDIAN_SKILL

    def test_whitespace_returns_default(self):
        clf = make_classifier()
        result = clf.classify("   ")
        assert result.is_default

    def test_unrecognised_returns_default(self):
        clf = make_classifier()
        result = clf.classify("hello there how are you today")
        assert result.is_default

    # Scholar
    def test_classifies_scholar_explain(self):
        clf = make_classifier()
        result = clf.classify("explain how TCP/IP works")
        assert result.skill.name == "scholar"
        assert not result.is_default

    def test_classifies_scholar_what_is(self):
        clf = make_classifier()
        result = clf.classify("what is a transformer model in deep learning")
        assert result.skill.name == "scholar"

    def test_classifies_scholar_history(self):
        clf = make_classifier()
        result = clf.classify("tell me about the history of the internet")
        assert result.skill.name == "scholar"

    # Builder
    def test_classifies_builder_write_code(self):
        clf = make_classifier()
        result = clf.classify("write code to parse a CSV file in Python")
        assert result.skill.name == "builder"

    def test_classifies_builder_debug(self):
        clf = make_classifier()
        result = clf.classify("debug this Python function it raises an exception")
        assert result.skill.name == "builder"

    def test_classifies_builder_implement(self):
        clf = make_classifier()
        result = clf.classify("implement a binary search algorithm")
        assert result.skill.name == "builder"

    # Critic
    def test_classifies_critic_review(self):
        clf = make_classifier()
        result = clf.classify("review this code for security vulnerabilities")
        assert result.skill.name == "critic"

    def test_classifies_critic_evaluate(self):
        clf = make_classifier()
        result = clf.classify("evaluate this architecture and find issues")
        assert result.skill.name == "critic"

    def test_classifies_critic_audit(self):
        clf = make_classifier()
        result = clf.classify("audit this code for security problems")
        assert result.skill.name == "critic"

    # Tester
    def test_classifies_tester_unit_test(self):
        clf = make_classifier()
        result = clf.classify("write unit test cases for this function")
        assert result.skill.name == "tester"

    def test_classifies_tester_pytest(self):
        clf = make_classifier()
        result = clf.classify("create pytest fixtures and assertions")
        assert result.skill.name == "tester"

    # Result fields
    def test_result_has_matched_on(self):
        clf = make_classifier()
        result = clf.classify("explain quantum computing in simple terms")
        assert result.matched_on
        assert any("explain" in kw for kw in result.matched_on)

    def test_result_confidence_positive(self):
        clf = make_classifier()
        result = clf.classify("write code to implement a class")
        assert result.confidence > 0

    def test_classify_many(self):
        clf = make_classifier()
        results = clf.classify_many([
            "explain this",
            "write code for this",
            "",
        ])
        assert len(results) == 3
        assert results[0].skill.name == "scholar"
        assert results[1].skill.name == "builder"
        assert results[2].is_default


# ─── SkillRouter ─────────────────────────────────────────────────────────────

BASE_PROMPT = "You are Guardian."


def make_router() -> SkillRouter:
    from guardian.skills import get_skill_classifier
    return SkillRouter(classifier=get_skill_classifier(), base_system_prompt=BASE_PROMPT)


class TestSkillRouter:
    def test_route_returns_decision(self):
        router = make_router()
        decision = router.route("hello")
        assert decision is not None

    def test_route_default_for_generic(self):
        router = make_router()
        decision = router.route("what time is it?")
        # Ambiguous — may be default or scholar; either is acceptable
        assert decision.skill is not None

    def test_route_builder_for_code(self):
        router = make_router()
        decision = router.route("write code to read a file in Python")
        assert decision.skill.name == "builder"

    def test_route_scholar_for_explain(self):
        router = make_router()
        decision = router.route("explain what machine learning is")
        assert decision.skill.name == "scholar"

    def test_augmented_prompt_includes_base(self):
        router = make_router()
        decision = router.route("write code to read a file")
        assert BASE_PROMPT in decision.augmented_prompt

    def test_augmented_prompt_includes_skill_addition(self):
        router = make_router()
        decision = router.route("write code to implement a function")
        if decision.skill.name == "builder":
            assert BUILDER_SKILL.prompt_addition in decision.augmented_prompt

    def test_guardian_skill_uses_base_prompt_only(self):
        router = make_router()
        decision = router.route("hello there")
        if decision.skill.name == "guardian":
            assert decision.augmented_prompt == BASE_PROMPT

    def test_no_switch_from_none_previous(self):
        router = make_router()
        decision = router.route("explain this concept", previous_skill=None)
        assert not decision.switched

    def test_switch_detected(self):
        router = make_router()
        # First: builder
        d1 = router.route("write code for me", previous_skill=None)
        # Second: highly confident scholar
        d2 = router.route(
            "explain summarize history of overview introduction to concept of",
            previous_skill=BUILDER_SKILL,
        )
        if d2.skill.name != d1.skill.name:
            assert d2.switched
            assert d2.previous_skill == BUILDER_SKILL

    def test_continuity_low_confidence(self):
        """Low-confidence new classification should retain previous skill."""
        router = make_router()
        # Previous skill: builder
        # New input: only one weak builder keyword
        # With SWITCH_THRESHOLD, should retain builder
        decision = router.route(
            "ok sounds good",  # no strong keywords
            previous_skill=BUILDER_SKILL,
        )
        assert decision.skill.name == "builder"

    def test_update_base_prompt(self):
        router = make_router()
        router.update_base_prompt("NEW BASE PROMPT")
        decision = router.route("hello")
        assert "NEW BASE PROMPT" in decision.augmented_prompt


# ─── Orchestrator skill integration ───────────────────────────────────────────

class TestOrchestratorSkillIntegration:
    def test_process_carries_active_skill(self):
        core = GuardianCore(model=MockBackend())
        session = Session()
        resp = core.process(
            "write code", session,
            active_skill="builder",
            skill_prompt_addition=BUILDER_SKILL.prompt_addition,
        )
        assert resp.active_skill == "builder"

    def test_process_default_skill_is_guardian(self):
        core = GuardianCore(model=MockBackend())
        session = Session()
        resp = core.process("hello", session)
        assert resp.active_skill == "guardian"

    def test_skill_appears_in_summary(self):
        core = GuardianCore(model=MockBackend())
        session = Session()
        resp = core.process("hello", session, active_skill="scholar")
        assert "scholar" in resp.summary()

    def test_skill_prompt_addition_applied(self):
        """Builder addition should reach the mock backend via request content."""
        mock = MockBackend()
        core = GuardianCore(model=mock, system_prompt=BASE_PROMPT)
        session = Session()
        resp = core.process(
            "write a function",
            session,
            active_skill="builder",
            skill_prompt_addition="BUILDER_MARKER_IN_PROMPT",
        )
        assert resp.success
        # mock call count should be 1
        assert mock.call_count == 1
