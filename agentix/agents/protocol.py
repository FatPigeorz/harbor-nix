"""Agent adapter protocol.

runner.py must export:

    async def run(agent_input: AgentInput) -> Trajectory

AgentInput is a TypedDict — adapters receive typed input, return ATIF trajectory.
"""

from __future__ import annotations

from typing import Callable, Coroutine, Any, TypedDict

from agentix.trajectory import Trajectory


class AgentInput(TypedDict, total=False):
    instruction: str          # required — task instruction
    workdir: str              # required — working directory
    env: dict[str, str]       # extra environment variables


RunFn = Callable[[AgentInput], Coroutine[Any, Any, Trajectory]]
