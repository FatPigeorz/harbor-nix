"""Abstract deployment interface: sandbox CRUD."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from agentix.models import SandboxConfig, SandboxInfo


@dataclass
class Sandbox:
    """Live sandbox handle — runtime_url is what RuntimeClient connects to."""

    sandbox_id: str
    runtime_url: str
    status: str


class Deployment(ABC):
    """Sandbox lifecycle management.

    Each infrastructure backend (Docker, K8s, Modal, ...) implements this
    interface. The orchestrator doesn't care which one is used.

    Typical usage:

        deployment = DockerDeployment()
        async with deployment.create(config) as sandbox:
            ...
        # sandbox is deleted on context exit
    """

    @abstractmethod
    async def _create(self, config: SandboxConfig) -> Sandbox:
        """Backend-specific create. Users should use `create()` (context manager) instead."""

    @abstractmethod
    async def delete(self, sandbox_id: str) -> None:
        """Destroy sandbox and release resources."""

    @abstractmethod
    async def get(self, sandbox_id: str) -> SandboxInfo:
        """Snapshot of the sandbox's current state."""

    @asynccontextmanager
    async def create(self, config: SandboxConfig) -> AsyncIterator[Sandbox]:
        """Create a sandbox scoped to this context; delete on exit."""
        sandbox = await self._create(config)
        try:
            yield sandbox
        finally:
            await self.delete(sandbox.sandbox_id)
