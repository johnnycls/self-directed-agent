"""Agent loop: request building, response handling, tool dispatch."""

from typing import Any

import litellm
from litellm import acompletion

from amnesia_genius.config import Config, global_path
from amnesia_genius.errors import AgentError
from amnesia_genius.history import Message, build_messages, commit_message
from amnesia_genius.tools import execute_tool_calls


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


async def agent_loop(
    config: Config,
    bash_tool: dict[str, Any],
    system_prompt: str,
) -> None:
    while True:
        messages: list[Message] = build_messages(
            system_prompt,
            config.history_window,
            config.max_context_message_chars,
        )
        response: Any = await acompletion(
            **request_kwargs(config, messages=messages, tools=[bash_tool])
        )
        message: Message = assistant_message(response.choices[0].message)
        commit_message(message)
        if not message.get("tool_calls"):
            return
        await execute_tool_calls(
            message["tool_calls"],
            max_command_output_chars=config.max_command_output_chars,
        )
