"""Embeddable agent kernel: workspace setup, per-turn reload, and event turns."""

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from amnesia_genius.agent import agent_turn, validate_llm
from amnesia_genius.config import (
    CONFIG_DIR,
    Config,
    ensure_global_files,
    load_bash_tool,
    load_config,
    load_system_prompt,
)
from amnesia_genius.errors import AgentError
from amnesia_genius.events import Event


@dataclass(frozen=True)
class AgentContext:
    """Everything one turn needs, reloaded from the workspace on demand."""

    config: Config
    system_prompt: str
    bash_tool: dict[str, Any]


class Agent:
    """Headless agent core; front-ends feed text in and consume events out."""

    def __init__(self, config_dir: str | None = None) -> None:
        self.config_dir: str = (
            os.path.abspath(os.path.expanduser(config_dir)) if config_dir else CONFIG_DIR
        )
        self._context: AgentContext | None = None

    def setup(self) -> None:
        """Create the workspace directory and seed missing files."""
        ensure_global_files(self.config_dir)

    def reload(self) -> None:
        """Load and validate workspace files for the next turn; raises AgentError."""
        cfg = load_config(self.config_dir)
        validate_llm(cfg, self.config_dir)
        self._context = AgentContext(
            config=cfg,
            system_prompt=load_system_prompt(self.config_dir),
            bash_tool=load_bash_tool(self.config_dir),
        )

    def turn(self, user_input: str) -> AsyncIterator[Event]:
        """Return an async iterator of events for one user turn.

        Call reload() first; the turn runs as the events are consumed, and
        errors raise out of the iteration.
        """
        if self._context is None:
            raise AgentError("Call reload() before turn().")
        context = self._context
        return agent_turn(
            context.config,
            context.bash_tool,
            context.system_prompt,
            user_input,
            self.config_dir,
        )
