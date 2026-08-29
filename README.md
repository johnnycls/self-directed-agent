# amnesia-genius

> **The only harness that never goes stale is the one that barely exists.**

Every harness expires. The moment the model, the environment, or the user changes, its rules go stale. amnesia-genius was born from refusing to ship rules at all.

## Why

Traditional programming means humans define static rules while AI means algorithms compute strategy dynamically from the environment. The power of AI is the ability to solve problems that can hardly solved by static rules. Wrapping dynamic intelligence in a static harness obviously contradicts the very purpose of AI but we are all building harness.

Every feature we make (e.g. plan mode, goal mode, memory system, sub-agents) is static and fair strategy that help stupid llm to perform fairly well. However as models get smarter, these harnesses stop being scaffolding and start being straitjackets.

So this project makes one design decision: make a minimal core that never changes, then design nothing else. Every operating decision belongs to the model, and it keeps re-deciding as conditions change:

- **Its own memory** — there is no memory system here. A static memory manager can't be optimal in every situation; a blank `memory.md` and a free agent can. What to remember, how to organize it, when to read it back — decided by the model, per task.
- **Its own capabilities** — nothing is impossible with bash: install packages, call APIs, compile code, write scripts. Whatever ability the agent lacks, it builds itself into its workspace, not into this code. 
- **Its own workspace** — everything it learns, builds, and improves lives in `~/.amnesia-genius/`. Task after task, the workspace grows while the program running it stays exactly the same.

An agent doesn't need dozens of bespoke tools; it needs **one tool that can do everything**, and the freedom to use it. The harness's only jobs are relaying messages, executing bash, failing loudly when something breaks — and it does them as a **headless kernel**: the terminal CLI is just one front-end, and you can build others (web UIs, bots, voice agents) on the same core.

## Warning

The agent runs arbitrary shell commands with no sandbox, no allowlist, and no confirmation. That is the design: one tool, full control. Run it inside a container or virtual machine unless you are comfortable with whatever the model decides to execute on your machine.

## Install

```
pip install .
```

Requires Python >=3.10,<3.15.

## Configure

First launch seeds `~/.amnesia-genius/config.json`:

```json
{
  "model": "",
  "api_key": "",
  "base_url": "",
  "provider_params": {},
  "max_context_message_chars": 1000
}
```

The agent immediately detects that `model` is not set, prints the error,
and opens this file with your platform's default opener. Fill in `model`
(and usually `api_key`), save, close it, and run `amnesia-genius` again.
Other invalid configuration files are handled the same way.

The configuration file is read at startup and the editable files are reloaded
before each new user input. Invalid values print an error and open the relevant
file in your editor. Provider-specific settings depend on the selected model
and provider. The agent's own numeric settings must be present and positive.
Character limits are measured in characters.

| Setting                     | Purpose                                                                    |
| --------------------------- | -------------------------------------------------------------------------- |
| `model`                     | LiteLLM provider-prefixed model, such as `anthropic/claude-sonnet-4-5`     |
| `api_key`                   | API key passed to LiteLLM when set                                         |
| `base_url`                  | API base URL passed to LiteLLM when set                                    |
| `provider_params`           | Additional provider-specific LiteLLM parameters                            |
| `max_context_message_chars` | Limit for non-user history content sent to the model (positive integer)    |

When character limit is exceeded, the agent keeps the first half and last
half of the text with `\n...\n` between them. User messages are never truncated;
`max_context_message_chars` applies to non-user history content only.

Provider-specific parameters (AWS credentials, Vertex projects, Azure deployments, sampling settings...) go in `provider_params`, a free-form object splatted into every request. Explicit settings (`model`, `api_key`, `base_url`) always win over `provider_params`:

```json
{
  "model": "bedrock/us.anthropic.claude-sonnet-4-5",
  "provider_params": {
    "aws_access_key_id": "AKIA...",
    "aws_secret_access_key": "...",
    "aws_region_name": "us-east-1"
  }
}
```

## Run

```
amnesia-genius
```

Responses stream to the terminal as they arrive. `Ctrl+C` cancels the current
turn (or clears the input line) and returns to the prompt; `Ctrl+D` exits.
A failed turn prints the error and returns to the prompt — your state lives in
the workspace, not in the process. `amnesia-genius --version` prints the
installed version.

## Embed (kernel API)

The terminal UI is just one front-end. `amnesia_genius.Agent` is the headless
kernel: feed text in, consume events out. Build web UIs, bots, or voice agents
(speech-to-text in, text-to-speech on `Delta` events) on top of it:

```python
import asyncio

from amnesia_genius import Agent, AssistantMessage, Delta, ToolResult


async def run() -> None:
    agent = Agent()                 # pass config_dir="..." for a custom workspace
    agent.setup()                   # create and seed the workspace
    agent.reload()                  # load + validate config, prompt, and tool schema
    async for event in agent.turn("hello"):
        if isinstance(event, Delta):
            print(event.text, end="", flush=True)   # stream to a UI or TTS
        elif isinstance(event, AssistantMessage):
            print(event.message["content"])
        elif isinstance(event, ToolResult):
            print(event.message["content"])


asyncio.run(run())
```

- `setup()` seeds the workspace once; `reload()` re-reads it — call it before
  every turn to pick up edits the user (or the agent) made.
- `turn()` returns an async iterator of `Delta`, `AssistantMessage`, and
  `ToolResult` events; the turn runs as the events are consumed.
- Errors raise out of the iteration; catch them in your front-end. The user
  input and every assistant/tool message are already persisted to
  `history.jsonl` as they happen.
- Rendering is entirely yours; the kernel never touches stdout.

See [examples/echo.py](examples/echo.py) for a minimal front-end.
