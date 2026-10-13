"""
Guardian Tool Loop
===================
Orchestrates the request → parse → approve → run → reply cycle.

Constitution reference: Section 3 (Authority Model), Section 12 (Tools),
Section 7 (Work Cycle), Section 11 (Transparency)

Flow for each turn:
  1. GuardianCore.process() sends user input to model
  2. Model response is parsed for tool_call blocks
  3. If tool calls found:
       a. Present the tool call to the user (name + params)
       b. For Level 0: auto-run (no approval needed)
          For Level 1+: ask user [y/N] before running
       c. Run the tool via ToolExecutor
       d. Append tool result to conversation as assistant message
       e. Call model again with updated context (final answer)
  4. Return final GuardianResponse

Limits:
  - MAX_TOOL_ROUNDS = 3 per turn (prevents infinite loops)
  - Each round is logged

The CLI layer controls the approval prompt. ToolLoop accepts an
`approval_callback` so the CLI can inject its own prompt logic.
If approval_callback is None, Level 0 tools auto-run and Level 1+ are rejected.

Never raises — errors are captured in ToolLoopResult.error.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from guardian.core.orchestrator import GuardianCore
from guardian.core.response import GuardianResponse
from guardian.core.session import Session
from guardian.logging.logger import get_logger
from guardian.tools.base import ToolLevel, ToolRequest
from guardian.tools.executor import ToolExecutor
from guardian.model.router import CallType
from guardian.tools.tool_call import (
    ToolCall,
    build_tool_result_message,
    parse_tool_calls,
)

log = get_logger(__name__)

MAX_TOOL_ROUNDS = 3

# Signature: (call: ToolCall) -> bool
# Return True to approve, False to deny.
ApprovalCallback = Callable[[ToolCall], bool]


@dataclass
class ToolRound:
    """Records one tool-call round within a turn."""
    call: ToolCall
    approved: bool
    result_text: str
    success: bool
    round_number: int


@dataclass
class ToolLoopResult:
    """
    The output of ToolLoop.run().

    Fields:
        final_response   The last GuardianResponse (includes tool results)
        rounds           Log of each tool call round
        total_rounds     How many rounds were executed
        error            Set if the loop itself failed (not tool errors)
    """
    final_response: GuardianResponse
    rounds: list[ToolRound] = field(default_factory=list)
    total_rounds: int = 0
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None and self.final_response.success

    def summary(self) -> str:
        return (
            f"[rounds={self.total_rounds} "
            f"tool_calls={len(self.rounds)} "
            f"success={self.success}]"
        )


class ToolLoop:
    """
    Manages the agentic tool-use loop for a single user turn.

    Usage:
        loop = ToolLoop(executor=get_tool_executor(), approval_callback=my_approve_fn)
        result = loop.run(core, user_input, session, active_skill="builder")
    """

    def __init__(
        self,
        executor: ToolExecutor,
        approval_callback: ApprovalCallback | None = None,
        max_rounds: int = MAX_TOOL_ROUNDS,
    ) -> None:
        self._executor = executor
        self._approve = approval_callback or _auto_approve_level0
        self._max_rounds = max_rounds

    def run(
        self,
        core: GuardianCore,
        user_input: str,
        session: Session,
        active_skill: str = "guardian",
        skill_prompt_addition: str = "",
    ) -> ToolLoopResult:
        """
        Execute one user turn with agentic tool use.

        The loop runs until:
          - The model response has no tool calls (done)
          - MAX_TOOL_ROUNDS is reached (safety limit)
          - An error occurs
        """
        rounds: list[ToolRound] = []

        # Round 0: first model call
        response = core.process(
            user_input, session,
            active_skill=active_skill,
            skill_prompt_addition=skill_prompt_addition,
            call_type=CallType.PLANNING,
        )

        if not response.success:
            return ToolLoopResult(
                final_response=response,
                error=f"Initial model call failed: {response.error}",
            )

        parse = parse_tool_calls(response.content)

        if not parse.has_calls:
            # No tool use — standard response path
            return ToolLoopResult(final_response=response, total_rounds=0)

        # Agentic tool-use loop
        for round_num in range(1, self._max_rounds + 1):
            if not parse.has_calls:
                break

            call = parse.calls[0]  # Execute one tool call per round
            log.info(f"Tool loop round {round_num}: {call.summary()}")

            # Authority check and approval
            tool = self._executor.get(call.name)
            if tool is None:
                result_text = f"[Error] Unknown tool: {call.name!r}"
                approved = False
                tool_success = False
            else:
                approved = (
                    tool.level == ToolLevel.READ
                    or self._approve(call)
                )
                if approved:
                    exec_result = self._executor.run(ToolRequest(
                        name=call.name,
                        params=call.params,
                        approved=True,
                        context=f"Tool loop round {round_num}",
                        session_id=str(session.session_id) if hasattr(session, "session_id") else "",
                    ))
                    result_text = exec_result.output if exec_result.success else f"[Tool error] {exec_result.error}"
                    tool_success = exec_result.success
                else:
                    result_text = f"[Tool denied] User did not approve {call.name!r}"
                    tool_success = False

            rounds.append(ToolRound(
                call=call,
                approved=approved,
                result_text=result_text,
                success=tool_success,
                round_number=round_num,
            ))

            # Feed tool result back to the session for the next model call
            tool_msg = build_tool_result_message(call, result_text)
            session.add_raw_assistant_message(tool_msg)

            if round_num >= self._max_rounds:
                log.warning(f"Tool loop hit MAX_TOOL_ROUNDS={self._max_rounds}")
                break

            # Call model again with tool result in context
            follow_up = "[Tool result received. Continue with your answer based on the tool output above.]"
            response = core.process(
                follow_up, session,
                active_skill=active_skill,
                skill_prompt_addition=skill_prompt_addition,
            )

            if not response.success:
                return ToolLoopResult(
                    final_response=response,
                    rounds=rounds,
                    total_rounds=round_num,
                    error=f"Model call failed at round {round_num}: {response.error}",
                )

            parse = parse_tool_calls(response.content)

        log.info(f"Tool loop complete: {len(rounds)} round(s)")
        return ToolLoopResult(
            final_response=response,
            rounds=rounds,
            total_rounds=len(rounds),
        )


def _auto_approve_level0(call: ToolCall) -> bool:
    """Default approval: auto-approve nothing (safe fallback)."""
    return False
