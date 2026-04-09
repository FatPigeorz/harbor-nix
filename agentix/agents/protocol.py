"""Agent plugin protocol.

Every plugin closure contains a runner.py with:

    async def run(agent_input: dict) -> RunResult
"""

from __future__ import annotations

from typing import Callable, Coroutine, Any

from pydantic import BaseModel

from agentix.trajectory import Trajectory


class RunResult(BaseModel):
    """Standard return type for agent runners."""

    output: dict
    trajectory: Trajectory | None = None


RunFn = Callable[[dict], Coroutine[Any, Any, RunResult]]
