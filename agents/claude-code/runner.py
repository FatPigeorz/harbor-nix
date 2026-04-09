"""Claude Code agent adapter.

Calls the claude CLI binary, parses output, returns AgentOutput.
"""

from __future__ import annotations

import asyncio
import json
import os
import shlex
from datetime import datetime, timezone

from agentix.agents.protocol import AgentInput, AgentOutput, Step


async def run(agent_input: AgentInput) -> AgentOutput:
    instruction = agent_input["instruction"]
    workdir = agent_input.get("workdir", os.getcwd())
    extra_env = agent_input.get("env", {})

    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    max_turns = os.environ.get("CLAUDE_MAX_TURNS")
    timeout = float(os.environ.get("CLAUDE_TIMEOUT", "0")) or None

    cmd_parts = [
        "claude",
        "-p", shlex.quote(instruction),
        "--output-format", "json",
        "-m", model,
    ]
    if max_turns:
        cmd_parts.extend(["--max-turns", max_turns])

    env = {**os.environ, **extra_env}

    proc = await asyncio.create_subprocess_shell(
        " ".join(cmd_parts),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=workdir,
        env=env,
    )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return AgentOutput(exit_code=-1, stdout="", stderr=f"Timed out after {timeout}s")

    stdout = stdout_bytes.decode(errors="replace")
    stderr = stderr_bytes.decode(errors="replace")

    # Parse claude JSON output into trajectory steps
    trajectory: list[Step] = []
    try:
        data = json.loads(stdout)
        trajectory.append(Step(
            timestamp=datetime.now(timezone.utc).isoformat(),
            source="agent",
            message=data.get("result", stdout),
        ))
    except (json.JSONDecodeError, TypeError):
        trajectory.append(Step(
            timestamp=datetime.now(timezone.utc).isoformat(),
            source="agent",
            message=stdout,
        ))

    return AgentOutput(
        exit_code=proc.returncode or 0,
        stdout=stdout,
        stderr=stderr,
        trajectory=trajectory,
    )
