"""Run Claude Code on a SWE-bench instance.

Two sandboxes:
  1. Agent sandbox: swebench image + runtime + claude-code closure
     → setup → run agent → collect patch
  2. Eval sandbox: swebench image + runtime + swebench closure
     → verify(instance, patch) → reward

Usage:
    python examples/claude-code-swebench/run.py \
        --instance instance.json \
        --runtime-closure /nix/store/xxx-runtime \
        --agent-closure /nix/store/xxx-claude-code \
        --dataset-closure /nix/store/xxx-swebench \
        --output result.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from pathlib import Path

from agentix.deployment.docker import DockerDeployment
from agentix.models import SandboxConfig
from agentix.runtime.client import RuntimeClient

logger = logging.getLogger("example")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
)


async def run_agent(
    instance: dict,
    deployment: DockerDeployment,
    runtime_closure: str,
    agent_closure: str,
    timeout: float,
) -> str:
    """Sandbox A: run agent, return patch."""
    instance_id = instance["instance_id"]
    logger.info("[%s] starting agent sandbox", instance_id)

    config = SandboxConfig(
        task_image=instance["image"],
        runtime_closure=runtime_closure,
        closures=[agent_closure],
    )

    sandbox = await deployment.create(config)
    try:
        async with RuntimeClient(sandbox.runtime_url, timeout=timeout) as client:
            await client.wait_until_alive(timeout=60)

            # Agent closure is auto-loaded by deployment.create()
            # Call /run with the problem statement
            t = time.monotonic()
            result = await client.call(
                Path(agent_closure).name, "run",
                {
                    "instruction": instance["problem_statement"],
                    "workdir": "/testbed",
                },
            )
            logger.info("[%s] agent done (%.1fs): exit_code=%s, patch=%d chars",
                        instance_id, time.monotonic() - t,
                        result.get("exit_code"), len(result.get("patch", "")))

            return result.get("patch", "")
    finally:
        await deployment.delete(sandbox.sandbox_id)


async def run_eval(
    instance: dict,
    patch: str,
    deployment: DockerDeployment,
    runtime_closure: str,
    dataset_closure: str,
    eval_script: str | None,
) -> dict:
    """Sandbox B: evaluate patch, return result."""
    instance_id = instance["instance_id"]
    logger.info("[%s] starting eval sandbox", instance_id)

    config = SandboxConfig(
        task_image=instance["image"],
        runtime_closure=runtime_closure,
        closures=[dataset_closure],
    )

    sandbox = await deployment.create(config)
    try:
        async with RuntimeClient(sandbox.runtime_url, timeout=600) as client:
            await client.wait_until_alive(timeout=60)

            # Apply the patch first
            if patch.strip():
                await client.exec(
                    f"cd /testbed && git apply --allow-empty -",
                    env={"GIT_DIFF": patch},
                )
                # Alternative: write patch to file and apply
                await client.exec(f"cd /testbed && cat > /tmp/model.patch << 'PATCHEOF'\n{patch}\nPATCHEOF")
                await client.exec("cd /testbed && git apply /tmp/model.patch")

            # Call dataset closure /verify
            t = time.monotonic()
            verify_data = {
                "instance": instance,
                "agent_output": {"patch": patch},
            }
            if eval_script:
                verify_data["eval_script"] = eval_script

            result = await client.call(
                Path(dataset_closure).name, "verify",
                verify_data,
            )
            logger.info("[%s] eval done (%.1fs): pass=%s, reason=%s",
                        instance_id, time.monotonic() - t,
                        result.get("pass"), result.get("reason", ""))

            return result
    finally:
        await deployment.delete(sandbox.sandbox_id)


async def main_async(args):
    instance = json.loads(Path(args.instance).read_text())
    instance_id = instance.get("instance_id", "unknown")
    t0 = time.monotonic()
    logger.info("[%s] starting", instance_id)

    deployment = DockerDeployment(host_port_start=args.port_start)

    # Load eval script if available
    eval_script = None
    if args.eval_script:
        eval_script = Path(args.eval_script).read_text()

    # 1. Run agent → get patch
    patch = await run_agent(
        instance, deployment,
        args.runtime_closure, args.agent_closure,
        args.timeout,
    )

    # 2. Run eval → get reward
    verify_result = await run_eval(
        instance, patch, deployment,
        args.runtime_closure, args.dataset_closure,
        eval_script,
    )

    # Write result
    result = {
        "instance_id": instance_id,
        "model_patch": patch,
        "verify": verify_result,
        "elapsed": round(time.monotonic() - t0, 1),
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, default=str))
    logger.info("[%s] done %.1fs → %s", instance_id, time.monotonic() - t0, args.output)


def main():
    parser = argparse.ArgumentParser(description="Run Claude Code on SWE-bench instance")
    parser.add_argument("--instance", required=True, help="JSON file with SWE-bench instance")
    parser.add_argument("--runtime-closure", required=True, help="Nix store path for agentix runtime")
    parser.add_argument("--agent-closure", required=True, help="Nix store path for claude-code closure")
    parser.add_argument("--dataset-closure", required=True, help="Nix store path for swebench closure")
    parser.add_argument("--eval-script", default=None, help="Path to eval.sh for verification")
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--output", default="result.json")
    parser.add_argument("--port-start", type=int, default=18000)
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
