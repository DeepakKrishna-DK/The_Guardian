"""
Guardian Skill Router
======================
Selects the active skill for a request and augments the system prompt.

Constitution reference: Section 6 (Agent Roles), Section 7 (Work Cycle)

The router is the single entry point for skill-aware request processing.
It wraps the SkillClassifier and applies the selected skill's prompt addition.

Usage:
    router = SkillRouter(classifier, base_system_prompt)
    routing = router.route("write a unit test for this class")
    # routing.skill.name == "tester"
    # routing.augmented_prompt == base_prompt + tester.prompt_addition

The router also implements continuity: if the new classification has low
confidence and a previous skill was active, it retains the previous skill.
This prevents rapid skill-switching mid-conversation.

Inputs:  str (user message), optional previous Skill
Outputs: RoutingDecision
Deps:    guardian.skills.classifier, guardian.skills.base
"""

from __future__ import annotations

from dataclasses import dataclass

from guardian.logging.logger import get_logger
from guardian.skills.base import ClassificationResult, Skill
from guardian.skills.classifier import SkillClassifier

log = get_logger(__name__)

# Minimum confidence delta required to switch skills mid-conversation.
# If the new classification's confidence is not at least this much better
# than a previous skill's last confidence, we retain the previous skill.
SWITCH_THRESHOLD = 2


@dataclass
class RoutingDecision:
    """
    Result of SkillRouter.route().

    Fields:
        skill              The selected Skill for this turn
        classification     Raw classification result
        augmented_prompt   System prompt with skill's prompt_addition appended
        switched           True if skill changed from the previous turn
        previous_skill     The skill that was active before (or None)
    """
    skill: Skill
    classification: ClassificationResult
    augmented_prompt: str
    switched: bool = False
    previous_skill: Skill | None = None

    def label(self) -> str:
        """Short display string for terminal output."""
        if self.switched and self.previous_skill:
            return f"{self.previous_skill.icon} -> {self.skill.display_label()}"
        return self.skill.display_label()


class SkillRouter:
    """
    Routes user input to the appropriate skill and builds the augmented prompt.

    Usage:
        router = get_skill_router(base_prompt)
        decision = router.route(user_input, previous_skill=None)
        # use decision.augmented_prompt for the model request
        # use decision.skill as the new active skill
    """

    def __init__(
        self,
        classifier: SkillClassifier,
        base_system_prompt: str,
    ) -> None:
        self._classifier = classifier
        self._base_prompt = base_system_prompt

    def route(
        self,
        user_input: str,
        previous_skill: Skill | None = None,
    ) -> RoutingDecision:
        """
        Select the best skill for user_input and build the augmented prompt.

        Continuity rule: if a previous skill is active and the new
        classification has low confidence (< SWITCH_THRESHOLD), retain the
        previous skill to avoid disruptive mid-conversation switching.
        """
        classification = self._classifier.classify(user_input)
        new_skill = classification.skill

        # Apply continuity: keep previous skill if:
        # (a) new skill differs AND confidence is below threshold, OR
        # (b) the classifier returned the default (no match at all)
        #     and a specific previous skill was active.
        # Rationale: short follow-ups ("ok", "yes", "thanks") return default —
        # we should not drop an active specialist skill for them.
        retain = (
            previous_skill is not None
            and new_skill.name != previous_skill.name
            and (
                classification.is_default
                or classification.confidence < SWITCH_THRESHOLD
            )
        )
        if retain:
            log.debug(
                f"Continuity: retaining {previous_skill.name!r} "
                f"(new={new_skill.name!r} confidence={classification.confidence} "
                f"< threshold={SWITCH_THRESHOLD})"
            )
            new_skill = previous_skill

        switched = (
            previous_skill is not None
            and new_skill.name != previous_skill.name
        )

        augmented = self._build_prompt(new_skill)

        if switched:
            log.info(
                f"Skill switch: {previous_skill.name} -> {new_skill.name} "
                f"(confidence={classification.confidence})"
            )
        else:
            log.debug(f"Skill retained: {new_skill.name}")

        return RoutingDecision(
            skill=new_skill,
            classification=classification,
            augmented_prompt=augmented,
            switched=switched,
            previous_skill=previous_skill,
        )

    def _build_prompt(self, skill: Skill) -> str:
        """Append the skill's prompt_addition to the base system prompt."""
        if not skill.prompt_addition:
            return self._base_prompt
        return f"{self._base_prompt}\n\n{skill.prompt_addition}"

    def update_base_prompt(self, new_base: str) -> None:
        """Update the base prompt (e.g. after memory facts are injected)."""
        self._base_prompt = new_base
