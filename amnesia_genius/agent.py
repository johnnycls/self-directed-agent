"""Agent turn: request building, streaming, tool dispatch, and event emission."""

from collections.abc import AsyncIterator
from typing import Any

import litellm
from litellm import acompletion

from amnesia_genius.config import Config, global_path
from amnesia_genius.errors import AgentError
from amnesia_genius.events import AssistantMessage, Delta, Event, ToolResult
from amnesia_genius.history import Message, append_history
from amnesia_genius.message import build_messages
from amnesia_genius.tools import execute_tool_calls


def _request_kwargs(config: Config, **extra: Any) -> dict[str, Any]:
    """Build litellm kwargs, with explicit config values winning over provider_params."""
    kwargs: dict[str, Any] = (
        dict(config.provider_params) if config.provider_params else {}
    )
    kwargs.update(extra)
    kwargs["model"] = config.model
    if config.api_key is not None:
        kwargs["api_key"] = config.api_key
    if config.base_url is not None:
        kwargs["api_base"] = config.base_url
    return kwargs


def _assistant_message(parts: list[str], calls: dict[int, dict[str, Any]]) -> Message:
    """Build the assistant message from streamed content parts and tool-call slots."""
    message: Message = {"role": "assistant", "content": "".join(parts)}
    tool_calls = [
        {"id": slot["id"], "type": "function", "function": slot["function"]}
        for _, slot in sorted(calls.items())
    ]
    if tool_calls:
        message["tool_calls"] = tool_calls
    return message


def validate_llm(config: Config, config_dir: str | None = None) -> None:
    """Cheap presence check; wrong keys fail loudly on the first real call."""
    path: str = global_path("config.json", config_dir)
    try:
        result: dict[str, Any] = litellm.validate_environment(config.model)
    except Exception as e:
        raise AgentError(
            f"LLM config check failed: {type(e).__name__}: {e}", path=path
        ) from e
    if (
        not result.get("keys_in_environment", True)
        and result.get("missing_keys")
        and config.api_key is None
        and not config.provider_params
    ):
        raise AgentError(
            f"LLM config check failed: set {' or '.join(result['missing_keys'])} "
            "in the environment, or fill 'api_key' in config.json.",
            path=path,
        )


async def agent_turn(
    config: Config,
    bash_tool: dict[str, Any],
    system_prompt: str,
    user_input: str,
    config_dir: str | None = None,
) -> AsyncIterator[Event]:
    """Run one user turn, yielding live events until the model stops calling tools.

    The turn runs as the events are consumed; the user input and every
    assistant/tool message are appended to history as they happen.
    """
    append_history({"role": "user", "content": user_input}, config_dir)
    turn_messages: list[Message] = []
    while True:
        messages: list[Message] = build_messages(
            system_prompt,
            user_input,
            turn_messages,
            config.max_context_message_chars,
            config_dir,
        )
        response: Any = await acompletion(
            **_request_kwargs(config, messages=messages, tools=[bash_tool]),
            stream=True,
        )
        parts: list[str] = []
        calls: dict[int, dict[str, Any]] = {}
        async for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta is None:
                continue
            content = getattr(delta, "content", None)
            if content:
                parts.append(content)
                yield Delta(content)
            for call in getattr(delta, "tool_calls", None) or []:
                index = call.index if call.index is not None else 0
                slot = calls.setdefault(
                    index, {"id": "", "function": {"name": "", "arguments": ""}}
                )
                if call.id:
                    slot["id"] = call.id
                function = getattr(call, "function", None)
                if function is not None:
                    if function.name:
                        slot["function"]["name"] = function.name
                    if function.arguments:
                        slot["function"]["arguments"] += function.arguments
        message = _assistant_message(parts, calls)
        append_history(message, config_dir)
        yield AssistantMessage(message)
        if not message.get("tool_calls"):
            return
        turn_messages.append(message)
        tool_messages: list[Message] = await execute_tool_calls(message["tool_calls"])
        for tool_message in tool_messages:
            append_history(tool_message, config_dir)
            yield ToolResult(tool_message)
        turn_messages.extend(tool_messages)
