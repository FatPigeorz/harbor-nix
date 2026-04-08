"""Claude Code agent runner."""

from __future__ import annotations

import shlex

from hnix.runtime.client import RuntimeClient


async def run(
    client: RuntimeClient,
    instruction: str,
    *,
    api_key: str,
    model: str = "claude-sonnet-4-20250514",
    output_format: str = "text",
    max_turns: int | None = None,
    timeout: float | None = None,
) -> dict:
    """Run Claude Code agent in the sandbox.

    Args:
        client: RuntimeClient connected to the sandbox.
        instruction: Task instruction for the agent.
        api_key: Anthropic API key.
        model: Model to use.
        output_format: Output format (text, json, stream-json).
        max_turns: Max agentic turns.
        timeout: Execution timeout in seconds.

    Returns:
        {"exit_code": int, "stdout": str, "stderr": str}
    """
    cmd_parts = [
        "claude",
        "-p", shlex.quote(instruction),
        "--output-format", output_format,
        "-m", model,
    ]
    if max_turns is not None:
        cmd_parts.extend(["--max-turns", str(max_turns)])

    result = await client.exec(
        command=" ".join(cmd_parts),
        env={"ANTHROPIC_API_KEY": api_key},
        timeout=timeout,
    )
    return result.model_dump()
