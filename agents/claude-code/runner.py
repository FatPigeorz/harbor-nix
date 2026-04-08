"""Claude Code agent runner."""

from __future__ import annotations

import shlex

from hnix.runtime.client import RuntimeClient


async def run(client: RuntimeClient, agent_input: dict) -> dict:
    """Run Claude Code agent in the sandbox.

    Args:
        client: RuntimeClient connected to the sandbox.
        agent_input: {
            "instruction": str,        # required
            "api_key": str,            # required
            "model": str,              # default "claude-sonnet-4-20250514"
            "output_format": str,      # default "text"
            "max_turns": int | None,   # optional
            "timeout": float | None,   # optional
        }

    Returns:
        {"exit_code": int, "stdout": str, "stderr": str}
    """
    instruction = agent_input["instruction"]
    api_key = agent_input["api_key"]
    model = agent_input.get("model", "claude-sonnet-4-20250514")
    output_format = agent_input.get("output_format", "text")
    max_turns = agent_input.get("max_turns")
    timeout = agent_input.get("timeout")

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
