"""Claude Code agent adapter.

Calls the claude CLI binary, parses output, returns ATIF Trajectory.
"""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import uuid
from datetime import datetime, timezone

from agentix.agents.protocol import AgentInput
from agentix.trajectory import AgentInfo, Trajectory, Step, Metrics, FinalMetrics


async def run(agent_input: AgentInput) -> Trajectory:
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
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        stdout, stderr = b"", f"Timed out after {timeout}s".encode()

    session_id = uuid.uuid4().hex
    trajectory = Trajectory(
        session_id=session_id,
        agent=AgentInfo(name="claude-code", version="0.1.0", model_name=model),
    )

    # Parse claude JSON output into trajectory steps
    raw = stdout.decode(errors="replace")
    try:
        data = json.loads(raw)
        # Claude --output-format json returns structured output
        trajectory.add_step(Step(
            step_id=0,
            timestamp=datetime.now(timezone.utc).isoformat(),
            source="agent",
            message=data.get("result", raw),
        ))
    except (json.JSONDecodeError, TypeError):
        trajectory.add_step(Step(
            step_id=0,
            timestamp=datetime.now(timezone.utc).isoformat(),
            source="agent",
            message=raw,
        ))

    return trajectory
