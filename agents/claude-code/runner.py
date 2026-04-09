"""Claude Code agent runner plugin."""

from __future__ import annotations

import asyncio
import os
import shlex
from datetime import datetime, timezone
from uuid import uuid4

from agentix.agents.protocol import RunResult
from agentix.trajectory import AgentInfo, FinalMetrics, Metrics, Step, Trajectory


async def run(agent_input: dict) -> RunResult:
    """Run Claude Code agent and collect trajectory.

    agent_input: {
        "instruction": str,        # required
        "api_key": str,            # required
        "model": str,              # default "claude-sonnet-4-20250514"
        "output_format": str,      # default "stream-json" (for trajectory)
        "max_turns": int | None,
        "timeout": float | None,
    }
    """
    instruction = agent_input["instruction"]
    api_key = agent_input["api_key"]
    model = agent_input.get("model", "claude-sonnet-4-20250514")
    max_turns = agent_input.get("max_turns")
    timeout = agent_input.get("timeout")

    trajectory = Trajectory(
        session_id=str(uuid4()),
        agent=AgentInfo(name="claude-code", version="", model_name=model),
    )

    # Step 1: user instruction
    trajectory.add_step(Step(
        step_id=1,
        timestamp=datetime.now(timezone.utc).isoformat(),
        source="user",
        message=instruction,
    ))

    # Execute claude with stream-json for trajectory data
    cmd_parts = [
        "claude",
        "-p", shlex.quote(instruction),
        "--output-format", "stream-json",
        "-m", model,
    ]
    if max_turns is not None:
        cmd_parts.extend(["--max-turns", str(max_turns)])

    env = dict(os.environ)
    env["ANTHROPIC_API_KEY"] = api_key

    proc = await asyncio.create_subprocess_shell(
        " ".join(cmd_parts),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return RunResult(
            output={"exit_code": -1, "stdout": "", "stderr": f"Timed out after {timeout}s"},
            trajectory=trajectory,
        )

    stdout = stdout_bytes.decode(errors="replace")
    stderr = stderr_bytes.decode(errors="replace")

    # Step 2: agent response
    # TODO: parse stream-json output for detailed steps, tool calls, and token metrics
    trajectory.add_step(Step(
        step_id=2,
        timestamp=datetime.now(timezone.utc).isoformat(),
        source="agent",
        message=stdout,
        model_name=model,
        metrics=Metrics(),  # TODO: extract from stream-json
    ))

    return RunResult(
        output={
            "exit_code": proc.returncode or 0,
            "stdout": stdout,
            "stderr": stderr,
        },
        trajectory=trajectory,
    )
