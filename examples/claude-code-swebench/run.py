"""End-to-end example: Claude Code on SWE-bench via closure protocol.

Demonstrates: load closures → setup → run → verify → unload.
Works with both stubs (local testing) and real closures (Nix builds).

Usage:
    # Start runtime server
    python -m agentix.runtime --port 8000 &

    # Run with stubs (no external deps)
    python examples/claude-code-swebench/run.py \
        --server http://localhost:8000 \
        --agent ./examples/claude-code-swebench/stubs/agent \
        --dataset ./examples/claude-code-swebench/stubs/dataset

    # Run with real closures
    python examples/claude-code-swebench/run.py \
        --server http://localhost:8000 \
        --agent /nix/store/xxx-claude-code \
        --dataset /nix/store/xxx-swebench \
        --instance-file instances/django__django-16139.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from pathlib import Path

from agentix.runtime.client import RuntimeClient

logger = logging.getLogger("example")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
)


async def run_pipeline(
    server_url: str,
    agent_path: str,
    dataset_path: str,
    instance: dict,
    output: str,
):
    t0 = time.monotonic()

    async with RuntimeClient(server_url) as client:
        await client.wait_until_alive(timeout=30)
        logger.info("Connected to runtime server")

        # 1. Load closures
        logger.info("Loading closures...")
        agent_ns = await client.load(agent_path, namespace="claude")
        logger.info("  loaded agent as '%s'", agent_ns)

        dataset_ns = await client.load(dataset_path, namespace="swebench")
        logger.info("  loaded dataset as '%s'", dataset_ns)

        try:
            # 2. Setup — dataset prepares environment
            t = time.monotonic()
            agent_input = await client.call("swebench", "setup", {"instance": instance})
            logger.info("  setup done (%.1fs): instruction=%s..., workdir=%s",
                        time.monotonic() - t,
                        agent_input.get("instruction", "")[:60],
                        agent_input.get("workdir", ""))

            # 3. Run — agent executes
            t = time.monotonic()
            agent_output = await client.call("claude", "run", agent_input)
            logger.info("  agent done (%.1fs): exit_code=%s",
                        time.monotonic() - t,
                        agent_output.get("exit_code"))

            # 4. Verify — dataset evaluates result
            t = time.monotonic()
            verify_result = await client.call("swebench", "verify", {
                "instance": instance,
                "agent_output": agent_output,
            })
            logger.info("  verify done (%.1fs): pass=%s, reason=%s",
                        time.monotonic() - t,
                        verify_result.get("pass"),
                        verify_result.get("reason", ""))

        finally:
            # 5. Unload closures
            await client.unload("claude")
            await client.unload("swebench")
            logger.info("  closures unloaded")

    # Write result
    result = {
        "instance": instance,
        "agent_input": agent_input,
        "agent_output": agent_output,
        "verify": verify_result,
        "elapsed": round(time.monotonic() - t0, 1),
    }

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, default=str))
    logger.info("Result written to %s (%.1fs total)", output, time.monotonic() - t0)

    return result


def main():
    parser = argparse.ArgumentParser(description="Run Claude Code on SWE-bench (closure protocol)")
    parser.add_argument("--server", default="http://localhost:8000", help="Runtime server URL")
    parser.add_argument("--agent", required=True, help="Path to agent closure dir")
    parser.add_argument("--dataset", required=True, help="Path to dataset closure dir")
    parser.add_argument("--instance-file", default=None, help="JSON file with SWE-bench instance")
    parser.add_argument("--output", default="result.json")
    args = parser.parse_args()

    # Load instance data
    if args.instance_file:
        instance = json.loads(Path(args.instance_file).read_text())
    else:
        # Default stub instance for testing
        instance = {
            "instance_id": "test__test-001",
            "problem_statement": "Fix the bug in the frobulator module",
            "repo": "test/test",
        }

    asyncio.run(run_pipeline(args.server, args.agent, args.dataset, instance, args.output))


if __name__ == "__main__":
    main()
