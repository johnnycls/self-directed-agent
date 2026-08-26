"""Command-line entry point."""

import os
import shlex
import subprocess
import sys
from typing import Any, Callable, TypeVar

from self_directed_agent.agent import agent_loop, validate_llm
from self_directed_agent.config import (
    Config,
    ensure_global_files,
    load_bash_tool,
    load_config,
    load_system_prompt,
)
from self_directed_agent.errors import AgentError
from self_directed_agent.history import append_history

T = TypeVar("T")


def open_in_editor(path: str) -> None:
    editor: str | None = os.environ.get("EDITOR")
    if editor:
        subprocess.run([*shlex.split(editor), path], check=False)
    elif sys.platform == "win32":
        subprocess.run(["notepad.exe", path], check=False)
    elif sys.platform == "darwin":
        subprocess.run(["open", "-t", "-W", path], check=False)
    else:
        subprocess.run(["xdg-open", path], check=False)


def load_or_edit(loader: Callable[[], T]) -> T:
    try:
        return loader()
    except AgentError as e:
        if e.path is None:
            raise
        print(
            f"Error: {e}\n"
            f"Opening {e.path} in your editor to fix.\n"
            "Re-run self-directed-agent after saving.",
            file=sys.stderr,
        )
        open_in_editor(e.path)
        sys.exit(1)


def run() -> None:
    ensure_global_files()
    config: Config = load_or_edit(load_config)
    load_or_edit(lambda: validate_llm(config))
    while True:
        config = load_or_edit(load_config)
        system_prompt: str = load_or_edit(load_system_prompt)
        bash_tool: dict[str, Any] = load_or_edit(load_bash_tool)
        user_input: str = input("user: ")
        append_history({"role": "user", "content": user_input})
        agent_loop(config, bash_tool, system_prompt)


def main() -> None:
    try:
        run()
    except (KeyboardInterrupt, EOFError):
        print()
    except AgentError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
