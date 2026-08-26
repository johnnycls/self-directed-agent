"""Global file locations, seeding, and configuration loading."""

import json
import math
import os
import shutil
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

from importlib.resources.abc import Traversable

from self_directed_agent.errors import AgentError

CONFIG_DIR: str = os.path.join(os.path.expanduser("~"), ".self-directed-agent")

GLOBAL_FILES: tuple[str, ...] = (
    "config.json",
    "system_prompt.md",
    "bash_tool.json",
    "memory.md",
    "history.jsonl",
)

DEFAULT_COMMAND_TIMEOUT_SECONDS: float = 120.0
DEFAULT_MAX_COMMAND_OUTPUT_CHARS: int = 20_000

PROVIDER_PARAM_TYPES: tuple[type, ...] = (str, int, float, bool)

ScalarValue = str | int | float | bool


@dataclass(frozen=True)
class Config:
    model: str
    api_key: str | None
    base_url: str | None
    provider_params: dict[str, ScalarValue] | None
    history_window: int
    max_context_message_chars: int
    command_timeout_seconds: float = DEFAULT_COMMAND_TIMEOUT_SECONDS
    max_command_output_chars: int = DEFAULT_MAX_COMMAND_OUTPUT_CHARS


def packaged_data(name: str) -> Traversable:
    return files("self_directed_agent").joinpath("data", name)


def global_path(filename: str) -> str:
    return os.path.join(CONFIG_DIR, filename)


def read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return f.read()
    except OSError as e:
        raise AgentError(f"Cannot read file {path}: {e}", path=path) from e


def read_json(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except OSError as e:
        raise AgentError(f"Cannot read file {path}: {e}", path=path) from e
    except json.JSONDecodeError as e:
        raise AgentError(
            f"Malformed JSON in {path} on line {e.lineno}", path=path
        ) from e


def ensure_global_files() -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    for filename in GLOBAL_FILES:
        path: str = global_path(filename)
        if not os.path.exists(path):
            try:
                shutil.copyfile(str(packaged_data(filename)), path)
            except OSError as e:
                raise AgentError(
                    f"Cannot seed global file {path}: {e}", path=path
                ) from e


def load_config() -> Config:
    path: str = global_path("config.json")
    raw_value: Any = read_json(path)
    if not isinstance(raw_value, dict):
        raise AgentError("config.json must contain a JSON object.", path=path)
    raw: dict[str, Any] = raw_value
    context_limit: Any = raw.get("max_context_message_chars")
    missing: list[str] = [
        key
        for key in ("model", "history_window", "max_context_message_chars")
        if not raw.get(key)
    ]
    if missing:
        raise AgentError(
            f"Missing or empty {', '.join(repr(k) for k in missing)} "
            f"in {path}. Please fill it in.",
            path=path,
        )
    history_window = positive_integer(raw["history_window"], "history_window", path)
    model: Any = raw["model"]
    if isinstance(model, bool) or not isinstance(model, str) or not model.strip():
        raise AgentError("'model' must be a non-empty string.", path=path)
    api_key: str | None = optional_string(raw.get("api_key"), "api_key", path)
    base_url: str | None = optional_string(raw.get("base_url"), "base_url", path)
    provider_params: dict[str, ScalarValue] | None = load_provider_params(
        raw.get("provider_params"), path
    )
    command_timeout_seconds: float = positive_number(
        raw.get("command_timeout_seconds", DEFAULT_COMMAND_TIMEOUT_SECONDS),
        "command_timeout_seconds",
        path,
    )
    output_limit: Any = raw.get(
        "max_command_output_chars", DEFAULT_MAX_COMMAND_OUTPUT_CHARS
    )
    max_command_output_chars: int = positive_integer(
        output_limit,
        "max_command_output_chars",
        path,
    )
    return Config(
        model=model,
        api_key=api_key,
        base_url=base_url,
        provider_params=provider_params,
        history_window=history_window,
        max_context_message_chars=positive_integer(
            context_limit, "max_context_message_chars", path
        ),
        command_timeout_seconds=command_timeout_seconds,
        max_command_output_chars=max_command_output_chars,
    )


def optional_string(value: Any, key: str, path: str) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, str):
        raise AgentError(f"'{key}' must be a string.", path=path)
    return value


def positive_integer(value: Any, key: str, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise AgentError(f"'{key}' must be a positive integer.", path=path)
    return value


def positive_number(value: Any, key: str, path: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise AgentError(f"'{key}' must be a positive number.", path=path)
    return float(value)


def load_provider_params(
    value: Any, path: str
) -> dict[str, ScalarValue] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise AgentError("'provider_params' must be a JSON object.", path=path)
    params: dict[str, ScalarValue] = {}
    for name, param in value.items():
        if not isinstance(param, PROVIDER_PARAM_TYPES):
            raise AgentError(
                f"'provider_params.{name}' must be a string, number, or boolean.",
                path=path,
            )
        params[name] = param
    return params


def load_system_prompt() -> str:
    return read_text(global_path("system_prompt.md"))


def load_bash_tool() -> dict[str, Any]:
    path: str = global_path("bash_tool.json")
    bash_tool: Any = read_json(path)
    if not isinstance(bash_tool, dict):
        raise AgentError("bash_tool.json must contain a JSON object.", path=path)
    function: Any = bash_tool.get("function")
    if bash_tool.get("type") != "function" or not isinstance(function, dict):
        raise AgentError(
            "bash_tool.json must define a function tool.", path=path
        )
    if function.get("name") != "bash":
        raise AgentError(
            "bash_tool.json function name must be 'bash'.", path=path
        )
    parameters: Any = function.get("parameters")
    properties: Any = parameters.get("properties") if isinstance(parameters, dict) else None
    command: Any = properties.get("command") if isinstance(properties, dict) else None
    if (
        not isinstance(parameters, dict)
        or parameters.get("type") != "object"
        or not isinstance(parameters.get("required"), list)
        or "command" not in parameters["required"]
        or not isinstance(properties, dict)
        or not isinstance(command, dict)
        or command.get("type") != "string"
    ):
        raise AgentError(
            "bash_tool.json must require a string 'command' parameter.",
            path=path,
        )
    return bash_tool
