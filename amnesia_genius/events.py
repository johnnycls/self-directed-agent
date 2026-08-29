"""Events emitted by the kernel during an agent turn."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Delta:
    """A streamed fragment of assistant text."""

    text: str


@dataclass(frozen=True)
class AssistantMessage:
    """One complete model response, including text and any tool calls."""

    message: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    """The result message of one executed tool call."""

    message: dict[str, Any]


Event = Delta | AssistantMessage | ToolResult
