"""Minimal example front-end: reads one prompt per line and prints raw events.

Run from a configured workspace: python examples/echo.py
"""

import asyncio

from amnesia_genius import Agent, AssistantMessage, Delta, ToolResult


async def main() -> None:
    agent = Agent()
    agent.setup()
    while True:
        try:
            user_input = input("> ")
        except (EOFError, KeyboardInterrupt):
            break
        agent.reload()
        streamed = False
        try:
            async for event in agent.turn(user_input):
                if isinstance(event, Delta):
                    streamed = True
                    print(event.text, end="", flush=True)
                elif isinstance(event, AssistantMessage):
                    if streamed:
                        print()
                    else:
                        print(event.message.get("content") or "")
                    for call in event.message.get("tool_calls") or []:
                        print(f"$ {call['function']['arguments']}")
                elif isinstance(event, ToolResult):
                    content = event.message.get("content") or ""
                    first_line = content.splitlines()[0] if content else ""
                    print(f"[{first_line}]")
        except Exception as e:  # a failed turn returns to the prompt
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
