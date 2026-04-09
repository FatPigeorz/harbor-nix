"""Agentix runtime server.

Runs inside the sandbox. Loads agent plugin at startup.
Plugin = Nix closure with bin/ + runner.py.
"""

from __future__ import annotations

import importlib.util
import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import Response

from agentix import __version__
from agentix.models import (
    ExecRequest,
    ExecResponse,
    HealthResponse,
    RunRequest,
    RunResponse,
    UploadResponse,
)
from agentix.runtime.executor import Executor

logger = logging.getLogger("agentix.runtime")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

app = FastAPI(title="agentix", version=__version__)
executor = Executor()

_agent_runner = None
_plugin_path: str | None = None


def load_plugin(plugin_dir: str) -> None:
    """Load agent plugin from a directory containing runner.py + bin/."""
    global _agent_runner, _plugin_path
    _plugin_path = plugin_dir

    runner_path = Path(plugin_dir) / "runner.py"
    if not runner_path.exists():
        logger.warning("No runner.py in plugin dir: %s", plugin_dir)
        return

    spec = importlib.util.spec_from_file_location("agent_runner", runner_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _agent_runner = module

    # Add plugin bin/ to PATH
    bin_dir = Path(plugin_dir) / "bin"
    if bin_dir.exists():
        os.environ["PATH"] = f"{bin_dir}:{os.environ.get('PATH', '')}"

    logger.info("Loaded plugin from %s (bins: %s)", plugin_dir, list(bin_dir.iterdir()) if bin_dir.exists() else "none")


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(version=__version__, plugin=_plugin_path)


@app.post("/run", response_model=RunResponse)
async def run_agent(req: RunRequest):
    if _agent_runner is None:
        raise HTTPException(status_code=503, detail="No agent plugin loaded")
    if not hasattr(_agent_runner, "run"):
        raise HTTPException(status_code=503, detail="Plugin runner.py has no run() function")

    try:
        run_result = await _agent_runner.run(req.agent_input)
    except Exception as e:
        logger.exception("Agent run failed")
        raise HTTPException(status_code=500, detail=str(e))

    return RunResponse(
        output=run_result.output,
        trajectory=run_result.trajectory.model_dump() if run_result.trajectory else None,
    )


@app.post("/exec", response_model=ExecResponse)
async def exec_command(req: ExecRequest):
    exit_code, stdout, stderr = await executor.exec(
        command=req.command,
        timeout=req.timeout,
        cwd=req.cwd,
        extra_env=req.env,
    )
    return ExecResponse(exit_code=exit_code, stdout=stdout, stderr=stderr)


@app.post("/upload", response_model=UploadResponse)
async def upload(
    file: UploadFile = File(...),
    path: str = Form(...),
):
    data = await file.read()
    size = executor.upload(data, path)
    return UploadResponse(path=path, size=size)


@app.get("/download")
async def download(path: str):
    try:
        data = executor.download(path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Not found: {path}")
    return Response(content=data, media_type="application/octet-stream")
