"""agentix — a Nix-closure runtime for Docker sandboxes."""

from agentix.deployment.base import Sandbox
from agentix.deployment.docker import DockerDeployment
from agentix.models import SandboxConfig, SandboxInfo
from agentix.runtime.client import RuntimeClient

__version__ = "0.1.0"

__all__ = [
    "DockerDeployment",
    "RuntimeClient",
    "Sandbox",
    "SandboxConfig",
    "SandboxInfo",
    "__version__",
]
