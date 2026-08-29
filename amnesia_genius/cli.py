"""Command-line entry point: one front-end over the kernel."""

import argparse
import asyncio
import importlib.metadata
import subprocess
import sys
from collections.abc import Callable
from typing import TypeVar

from amnesia_genius import display
from amnesia_genius.errors import AgentError
from amnesia_genius.kernel import Agent

try:
    import readline  # noqa: F401 - enables up-arrow input history on POSIX
except ImportError:  # platform dependent
    pass

T = TypeVar("T")


def _open_in_editor(path: str) -> None:
    """Open the given file with the platform's default opener."""
    try:
        if sys.platform == "win32":
            subprocess.run(["notepad.exe", path], check=False, shell=False)
        elif sys.platform == "darwin":
            subprocess.run(["open", "-t", "-W", path], check=False, shell=False)
        else:
            subprocess.run(["xdg-open", path], check=False, shell=False)
    except OSError as e:
        print(f"Cannot open {path}: {e}. Edit it manually and re-run.")


def _load_or_edit(loader: Callable[[], T]) -> T:
    """Run a loader, or open its erroring file in an editor and exit."""
    try:
        return loader()
    except AgentError as e:
        if e.path is None:
            raise
        print(
            f"Error: {e}\n"
            f"Opening {e.path} to fix.\n"
            "Re-run amnesia-genius after saving.",
            file=sys.stderr,
        )
        _open_in_editor(e.path)
        sys.exit(1)


async def _render_turn(
    agent: Agent, user_input: str, renderer: display.TerminalRenderer
) -> None:
    """Run one turn and render its events to the terminal."""
    async for event in agent.turn(user_input):
        renderer.render(event)


def _run() -> None:
    """Seed the workspace, then loop: read input, run the agent turn."""
    agent = Agent()
    agent.setup()
    renderer = display.TerminalRenderer()
    display.clear()
    while True:
        _load_or_edit(agent.reload)
        try:
            user_input: str = input("> ")
        except KeyboardInterrupt:
            print()
            continue
        try:
            asyncio.run(_render_turn(agent, user_input, renderer))
        except KeyboardInterrupt:
            renderer.reset()
            print()
        except Exception as e:  # a failed turn returns to the prompt
            renderer.reset()
            print(f"Error: {e}", file=sys.stderr)


def _version() -> str:
    try:
        return importlib.metadata.version("amnesia-genius")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def main() -> None:
    """Console-script entry point that runs the agent loop with error handling."""
    parser = argparse.ArgumentParser(
        prog="amnesia-genius",
        description="A minimal self-directed agent that runs bash commands.",
    )
    parser.add_argument(
        "--version", action="version", version=f"amnesia-genius {_version()}"
    )
    parser.parse_args()
    try:
        _run()
    except (KeyboardInterrupt, EOFError):
        print()
    except AgentError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # fail loudly but cleanly
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
