"""Global file locations, seeding, and configuration loading."""

import json
import os
import shutil
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

from importlib.resources.abc import Traversable

from amnesia_genius.errors import AgentError

CONFIG_DIR: str = os.path.join(os.path.expanduser("~"), ".amnesia-genius")

GLOBAL_FILES: tuple[str, ...] = (
    "config.json",
    "system_prompt.md",
    "bash_tool.json",
    "memory.md",
    "history.jsonl",
)

PROVIDER_PARAM_TYPES: tuple[type, ...] = (str, int, float, bool)

ScalarValue = str | int | float | bool


@dataclass(frozen=True)
class Config:
    """Validated agent configuration loaded from the global config.json file."""

    model: str
    api_key: str | None
    base_url: str | None
    provider_params: dict[str, ScalarValue] | None
    max_context_message_chars: int


def _packaged_data(name: str) -> Traversable:
    """Return the packaged data file path for the given resource name."""
    return files("amnesia_genius").joinpath("data", name)


def global_path(filename: str) -> str:
    """Return the absolute path of a global file in the config directory."""
    return os.path.join(CONFIG_DIR, filename)


def read_text(path: str) -> str:
    """Read a UTF-8 text file, raising AgentError on failure."""
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return f.read()
    except OSError as e:
        raise AgentError(f"Cannot read file {path}: {e}", path=path) from e


def _read_json(path: str) -> Any:
    """Read and parse a JSON file, raising AgentError on missing or invalid JSON."""
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
    """Create the config directory and seed packaged files that are missing."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    for filename in GLOBAL_FILES:
        path: str = global_path(filename)
        if not os.path.exists(path):
            try:
                shutil.copyfile(str(_packaged_data(filename)), path)
            except OSError as e:
                raise AgentError(
                    f"Cannot seed global file {path}: {e}", path=path
                ) from e


def load_config() -> Config:
    """Load, validate, and return the agent configuration from config.json."""
    path: str = global_path("config.json")
    raw_value: Any = _read_json(path)
    if not isinstance(raw_value, dict):
        raise AgentError("config.json must contain a JSON object.", path=path)
    raw: dict[str, Any] = raw_value
    context_limit: Any = raw.get("max_context_message_chars")
    missing: list[str] = [
        key
        for key in (
            "model",
            "max_context_message_chars",
        )
        if not raw.get(key)
    ]
    if missing:
        raise AgentError(
            f"Missing or empty {', '.join(repr(k) for k in missing)} "
            f"in {path}. Please fill it in.",
            path=path,
        )
    model: Any = raw["model"]
    if isinstance(model, bool) or not isinstance(model, str) or not model.strip():
        raise AgentError("'model' must be a non-empty string.", path=path)
    api_key: str | None = _optional_string(raw.get("api_key"), "api_key", path)
    base_url: str | None = _optional_string(raw.get("base_url"), "base_url", path)
    provider_params: dict[str, ScalarValue] | None = _load_provider_params(
        raw.get("provider_params"), path
    )
    return Config(
        model=model,
        api_key=api_key,
        base_url=base_url,
        provider_params=provider_params,
        max_context_message_chars=_positive_integer(
            context_limit, "max_context_message_chars", path
        ),
    )


def _optional_string(value: Any, key: str, path: str) -> str | None:
    """Coerce an optional config value to a string, or None when empty."""
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, str):
        raise AgentError(f"'{key}' must be a string.", path=path)
    return value


def _positive_integer(value: Any, key: str, path: str) -> int:
    """Validate and return a positive integer config value."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise AgentError(f"'{key}' must be a positive integer.", path=path)
    return value


def _load_provider_params(
    value: Any, path: str
) -> dict[str, ScalarValue] | None:
    """Validate and return the free-form provider_params object, or None."""
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
    """Load the system prompt text from system_prompt.md."""
    return read_text(global_path("system_prompt.md"))


def load_bash_tool() -> dict[str, Any]:
    """Load and validate the bash tool schema from bash_tool.json."""
    path: str = global_path("bash_tool.json")
    bash_tool: Any = _read_json(path)
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
