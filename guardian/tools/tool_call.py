"""
Guardian Tool Call Parser
==========================
Parses tool call requests embedded in model responses.

Protocol:
  The model signals tool use by embedding a fenced block with language tag
  "tool_call" containing a JSON object:

      ```tool_call
      {"name": "file_read", "params": {"path": "guardian/cli.py"}}
      ```

  Multiple tool calls per response are supported.
  Invalid or malformed blocks are collected as errors (never silently dropped).

Constitution reference: Section 12 (Tools), Section 11 (Transparency)

Transparency: every parsed tool call is logged with its name and params.
              every parse error is logged at WARNING level.

Design:
  - Stateless — safe to share and reuse
  - No model dependency — pure text parsing
  - Returns both successful parses AND errors for the caller to handle
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from guardian.logging.logger import get_logger

log = get_logger(__name__)

# Regex: finds ```tool_call ... ``` blocks (non-greedy, DOTALL)
_TOOL_CALL_RE = re.compile(
    r"```tool_call\s*\n(.*?)```",
    re.DOTALL,
)


@dataclass
class ToolCall:
    """A parsed tool call request from the model."""
    name: str
    params: dict[str, Any]
    raw: str = ""   # Original JSON block (for debugging)

    def summary(self) -> str:
        params_str = ", ".join(f"{k}={v!r}" for k, v in self.params.items())
        return f"tool_call({self.name}, {params_str})"


@dataclass
class ParseResult:
    """
    Result of parsing a model response for tool calls.

    Fields:
        calls         Validated tool calls (name + params)
        errors        Malformed blocks that could not be parsed
        clean_text    Model response with all tool_call blocks removed
    """
    calls: list[ToolCall] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    clean_text: str = ""

    @property
    def has_calls(self) -> bool:
        return len(self.calls) > 0

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


def parse_tool_calls(model_output: str) -> ParseResult:
    """
    Extract all tool_call blocks from a model response.

    Returns a ParseResult with:
      - calls: list of valid ToolCall objects
      - errors: list of parse error messages
      - clean_text: the original text with tool_call blocks removed
    """
    calls: list[ToolCall] = []
    errors: list[str] = []

    # Find all ```tool_call ... ``` blocks
    matches = list(_TOOL_CALL_RE.finditer(model_output))

    for m in matches:
        raw_json = m.group(1).strip()
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            err = f"Invalid JSON in tool_call block: {exc} | raw={raw_json[:120]}"
            log.warning(err)
            errors.append(err)
            continue

        if not isinstance(data, dict):
            err = f"tool_call block must be a JSON object, got {type(data).__name__}"
            log.warning(err)
            errors.append(err)
            continue

        name = data.get("name", "").strip()
        if not name:
            err = f"tool_call block missing 'name' field: {raw_json[:120]}"
            log.warning(err)
            errors.append(err)
            continue

        params = data.get("params", {})
        if not isinstance(params, dict):
            err = f"tool_call 'params' must be a dict, got {type(params).__name__}"
            log.warning(err)
            errors.append(err)
            continue

        call = ToolCall(name=name, params=params, raw=raw_json)
        calls.append(call)
        log.info(f"Parsed: {call.summary()}")

    # Remove all tool_call blocks from the response text
    clean_text = _TOOL_CALL_RE.sub("", model_output).strip()

    return ParseResult(calls=calls, errors=errors, clean_text=clean_text)


def build_tool_result_message(call: ToolCall, result_text: str) -> str:
    """
    Format a tool result to be appended to the conversation as
    an assistant message, so the model can incorporate the output.
    """
    return (
        f"[Tool result: {call.name}]\n"
        f"{result_text}\n"
        f"[End tool result]"
    )


TOOL_USE_SYSTEM_ADDITION = """
## Tool Use

When you need to read a file, list a directory, or search code to answer a question,
you may request a tool call using this exact format:

```tool_call
{"name": "<tool_name>", "params": {"<param>": "<value>"}}
```

Available tools:
  file_read   — read a file (params: path, start_line, end_line)
  directory   — list a directory (params: path)
  search      — search for text in files (params: pattern, path)
  shell       — run a shell command (params: command) [requires user confirmation]

Rules:
- Only request ONE tool call per response.
- After a tool call, wait for the result before answering.
- If you do not need a tool, respond normally without a tool_call block.
- Never guess at file contents — use file_read to verify.
"""
