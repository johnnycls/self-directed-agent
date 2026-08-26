"""Agent loop: request building, response handling, tool dispatch."""

import asyncio
from typing import Any

import litellm
from litellm import acompletion

from self_directed_agent.config import Config, global_path
from self_directed_agent.errors import AgentError
from self_directed_agent.history import Message, build_messages, commit_message
from self_directed_agent.tools import execute_tool_calls


def request_kwargs(config: Config, **extra: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"model": config.model}
    if config.api_key is not None:
        kwargs["api_key"] = config.api_key
    if config.base_url is not None:
        kwargs["api_base"] = config.base_url
    if config.provider_params is not None:
        kwargs.update(config.provider_params)
    kwargs.update(extra)
    return kwargs


def assistant_message(message: Any) -> Message:
    result: Message = {"role": "assistant", "content": message.content or ""}
    tool_calls: list[dict[str, Any]] = [
        {
            "id": call.id,
            "type": "function",
            "function": {"name": call.function.name, "arguments": call.function.arguments},
        }
        for call in (message.tool_calls or [])
    ]
    if tool_calls:
        result["tool_calls"] = tool_calls
    return result


def validate_llm(config: Config) -> None:
    """Cheap presence check; wrong keys fail loudly on the first real call."""
    path: str = global_path("config.json")
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
    ):
        raise AgentError(
            f"LLM config check failed: set {' or '.join(result['missing_keys'])} "
            "in the environment, or fill 'api_key' in config.json.",
            path=path,
        )


def agent_loop(
    config: Config,
    bash_tool: dict[str, Any],
    system_prompt: str,
) -> None:
    while True:
        messages: list[Message] = build_messages(
            system_prompt, config.history_window, config.max_message_chars
        )
        response: Any = asyncio.run(
            acompletion(**request_kwargs(config, messages=messages, tools=[bash_tool]))
        )
        message: Message = assistant_message(response.choices[0].message)
        commit_message(message)
        if not message.get("tool_calls"):
            return
        asyncio.run(execute_tool_calls(message["tool_calls"]))
