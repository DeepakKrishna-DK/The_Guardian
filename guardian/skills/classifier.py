"""
Guardian Skill Classifier
==========================
Classifies user input into the best-matching Guardian skill using
heuristic keyword matching. No API call is made per classification.

Constitution reference: Section 9 (Skills), Section 11 (Transparency)
Transparency guarantee: every classification is logged with matched keywords.

Design:
  Phase 5 uses heuristic classification (fast, deterministic, no token cost).
  Phase 7+ may add model-based classification for ambiguous cases.

Algorithm:
  1. Normalise input (lowercase, remove punctuation extremes)
  2. For each non-default skill, score by counting keyword matches
     (longer phrases scored higher to reduce false positives)
  3. Return the highest-scoring skill above min_confidence
  4. If no skill clears its threshold -> return default (guardian)

Thread safety: classifier is stateless; safe to share across threads.

Inputs:  str (user message)
Outputs: ClassificationResult
Deps:    guardian.skills.base (no model dependency)
"""

from __future__ import annotations

import re
from typing import Sequence

from guardian.logging.logger import get_logger
from guardian.skills.base import ClassificationResult, Skill

log = get_logger(__name__)


def _normalise(text: str) -> str:
    """Lowercase and collapse whitespace for uniform matching."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)  # replace punctuation with space
    return re.sub(r"\s+", " ", text).strip()


def _score_skill(normalised_input: str, skill: Skill) -> tuple[int, list[str]]:
    """
    Return (score, matched_keywords) for one skill.
    Multi-word phrases score higher than single words.
    """
    matched: list[str] = []
    score = 0

    for kw in skill.keywords:
        kw_norm = kw.lower().strip()
        if kw_norm in normalised_input:
            matched.append(kw)
            # Longer keywords are more specific — weight by word count
            word_count = len(kw_norm.split())
            score += word_count

    return score, matched


class SkillClassifier:
    """
    Stateless heuristic skill classifier.

    Usage:
        classifier = SkillClassifier(skills=ALL_SKILLS, default=GUARDIAN_SKILL)
        result = classifier.classify("write a pytest test for this function")
        # result.skill.name == "tester"
    """

    def __init__(self, skills: Sequence[Skill], default_skill: Skill) -> None:
        """
        skills        — ordered list of candidate skills (excluding the default)
        default_skill — returned when no candidate clears its threshold
        """
        self._candidates = [s for s in skills if s.name != default_skill.name]
        self._default = default_skill

    def classify(self, user_input: str) -> ClassificationResult:
        """
        Classify user_input and return a ClassificationResult.
        Never raises — returns the default skill on any error.
        """
        if not user_input or not user_input.strip():
            return ClassificationResult(
                skill=self._default, confidence=0, is_default=True
            )

        normalised = _normalise(user_input)
        best_skill: Skill | None = None
        best_score = 0
        best_matched: list[str] = []

        for skill in self._candidates:
            score, matched = _score_skill(normalised, skill)
            if score > best_score and score >= skill.min_confidence:
                best_score = score
                best_skill = skill
                best_matched = matched

        if best_skill is None:
            result = ClassificationResult(
                skill=self._default,
                confidence=0,
                matched_on=[],
                is_default=True,
            )
        else:
            result = ClassificationResult(
                skill=best_skill,
                confidence=best_score,
                matched_on=best_matched,
                is_default=False,
            )

        log.debug(f"Classified: {result.summary()}")
        return result

    def classify_many(self, inputs: list[str]) -> list[ClassificationResult]:
        """Classify a batch of inputs."""
        return [self.classify(inp) for inp in inputs]
