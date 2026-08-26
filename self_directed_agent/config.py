"""Global file locations, seeding, and configuration loading."""

import json
import os
import shutil
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

try:
    from importlib.resources.abc import Traversable
except ImportError:
    from importlib.abc import Traversable

from self_directed_agent.errors import AgentError

CONFIG_DIR: str = os.path.join(os.path.expanduser("~"), ".self-directed-agent")

GLOBAL_FILES: tuple[str, ...] = (
    "config.json",
    "system_prompt.md",
    "bash_tool.json",
    "memory.md",
    "history.jsonl",
)

REQUIRED_CONFIG_KEYS: tuple[str, ...] = ("model",)

REQUIRED_INT_CONFIG_KEYS: tuple[str, ...] = ("history_window", "max_message_chars")

PROVIDER_PARAM_TYPES: tuple[type, ...] = (str, int, float, bool)

ScalarValue = str | int | float | bool


@dataclass(frozen=True)
class Config:
    model: str
    api_key: str | None
    base_url: str | None
    provider_params: dict[str, ScalarValue] | None
    history_window: int
    max_message_chars: int


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
    raw: dict[str, Any] = read_json(path)
    missing: list[str] = [
        key for key in REQUIRED_CONFIG_KEYS + REQUIRED_INT_CONFIG_KEYS if not raw.get(key)
    ]
    if missing:
        raise AgentError(
            f"Missing or empty {', '.join(repr(k) for k in missing)} "
            f"in {path}. Please fill it in.",
            path=path,
        )
    ints: dict[str, int] = {}
    for key in REQUIRED_INT_CONFIG_KEYS:
        value: Any = raw[key]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise AgentError(f"'{key}' must be a positive integer.", path=path)
        ints[key] = value
    api_key: str | None = optional_string(raw.get("api_key"), "api_key", path)
    base_url: str | None = optional_string(raw.get("base_url"), "base_url", path)
    provider_params: dict[str, ScalarValue] | None = load_provider_params(
        raw.get("provider_params"), path
    )
    return Config(
        model=raw["model"],
        api_key=api_key,
        base_url=base_url,
        provider_params=provider_params,
        history_window=ints["history_window"],
        max_message_chars=ints["max_message_chars"],
    )


def optional_string(value: Any, key: str, path: str) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, str):
        raise AgentError(f"'{key}' must be a string.", path=path)
    return value


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
    bash_tool: dict[str, Any] = read_json(global_path("bash_tool.json"))
    return bash_tool
