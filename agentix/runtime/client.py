"""Async HTTP client for the agentix runtime server.

Wraps the runtime's built-in endpoints (run/upload/download/ls, /closures,
/closures/{ns}/logs) as typed helpers, plus the generic
`call(namespace, endpoint, ...)` for any closure in the sandbox.
Closures are baked into the sandbox at create time — no /load/unload.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx

from agentix.models import (
    ClosureInfo,
    ExecRequest,
    ExecResponse,
    HealthResponse,
    LogsResponse,
    LsEntry,
    UploadResponse,
)


class RuntimeClient:
    """Async client for the agentix runtime server."""

    def __init__(self, base_url: str, timeout: float = 300):
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    # ── lifecycle ────────────────────────────────────────────────

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    # ── runtime server endpoints ─────────────────────────────────

    async def health(self) -> HealthResponse:
        r = await self._client.get("/health")
        r.raise_for_status()
        return HealthResponse.model_validate(r.json())

    async def closures(self) -> list[ClosureInfo]:
        r = await self._client.get("/closures")
        r.raise_for_status()
        return [ClosureInfo.model_validate(x) for x in r.json()]

    async def logs(self, namespace: str, tail: int | None = None) -> LogsResponse:
        params = {"tail": tail} if tail is not None else None
        r = await self._client.get(f"/closures/{namespace}/logs", params=params)
        r.raise_for_status()
        return LogsResponse.model_validate(r.json())

    # ── generic closure proxy ────────────────────────────────────

    async def call(
        self,
        namespace: str,
        endpoint: str,
        data: dict | None = None,
        method: str = "POST",
    ) -> Any:
        """Call an endpoint on a mounted closure. Returns parsed JSON when the
        closure responds with a JSON content-type; otherwise the raw text body.
        """
        url = f"/{namespace}/{endpoint.lstrip('/')}"
        if method.upper() == "GET":
            r = await self._client.get(url, params=data)
        else:
            r = await self._client.request(method.upper(), url, json=data)
        r.raise_for_status()
        ctype = r.headers.get("content-type", "")
        return r.json() if "json" in ctype else r.text

    async def call_stream(
        self,
        namespace: str,
        endpoint: str,
        data: dict | None = None,
        method: str = "POST",
        accept: str = "text/event-stream",
    ) -> AsyncIterator[bytes]:
        """Stream raw bytes from a closure endpoint (e.g. SSE from `/exec`)."""
        url = f"/{namespace}/{endpoint.lstrip('/')}"
        headers = {"accept": accept}
        async with self._client.stream(
            method.upper(), url, json=data, headers=headers
        ) as r:
            r.raise_for_status()
            async for chunk in r.aiter_bytes():
                yield chunk

    # ── runtime I/O primitives (exec / upload / download / ls) ──

    @staticmethod
    def _exec_body(
        command: str,
        cwd: str | None,
        env: dict[str, str] | None,
        timeout: float | None,
        max_output: int | None = None,
        paths_from: list[str] | None = None,
    ) -> dict[str, Any]:
        return ExecRequest(
            command=command,
            cwd=cwd,
            env=env,
            timeout=timeout,
            max_output=max_output,
            paths_from=paths_from,
        ).model_dump(exclude_none=True)

    async def run(
        self,
        command: str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
        max_output: int | None = None,
        paths_from: list[str] | None = None,
    ) -> ExecResponse:
        """Buffered shell exec: run `command` and return the full captured output.

        `paths_from` prepends the `bin/` of the listed closures to PATH for
        this command only. Pass `["*"]` to include every mounted closure.
        """
        body = self._exec_body(command, cwd, env, timeout, max_output, paths_from)
        r = await self._client.post("/exec", json=body)
        r.raise_for_status()
        return ExecResponse.model_validate(r.json())

    async def run_stream(
        self,
        command: str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
        paths_from: list[str] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream exec output as SSE events.

        Yields decoded event dicts like:
            {"event": "stdout", "stream": "stdout", "data": "..."}
            {"event": "exit",   "exit_code": 0}
        """
        body = self._exec_body(command, cwd, env, timeout, paths_from=paths_from)
        buf = b""
        async with self._client.stream(
            "POST", "/exec", json=body, headers={"accept": "text/event-stream"}
        ) as r:
            r.raise_for_status()
            async for chunk in r.aiter_bytes():
                buf += chunk
                while b"\n\n" in buf:
                    event_bytes, buf = buf.split(b"\n\n", 1)
                    event = _parse_sse_event(event_bytes)
                    if event is not None:
                        yield event

    async def upload(self, local_path: str | Path, dest: str) -> UploadResponse:
        """Upload a local file to `dest` inside the sandbox. `dest` must be
        under the server's AGENTIX_UPLOAD_ROOT (default `/workspace`).
        """
        p = Path(local_path)
        with open(p, "rb") as f:
            r = await self._client.post(
                "/upload",
                files={"file": (p.name, f)},
                data={"path": dest},
            )
        r.raise_for_status()
        return UploadResponse.model_validate(r.json())

    async def download(self, path: str, local_path: str | Path) -> int:
        """Stream a sandbox file down to `local_path`. Paths are resolved under
        AGENTIX_UPLOAD_ROOT on the server.
        """
        r = await self._client.get("/download", params={"path": path})
        r.raise_for_status()
        lp = Path(local_path)
        lp.parent.mkdir(parents=True, exist_ok=True)
        lp.write_bytes(r.content)
        return len(r.content)

    async def ls(self, path: str) -> list[LsEntry]:
        r = await self._client.get("/ls", params={"path": path})
        r.raise_for_status()
        return [LsEntry.model_validate(e) for e in r.json()]


def _parse_sse_event(raw: bytes) -> dict[str, Any] | None:
    """Parse a single SSE event block into a dict. Returns None for keepalives."""
    event: str | None = None
    data_lines: list[str] = []
    for line in raw.decode(errors="replace").splitlines():
        if not line or line.startswith(":"):
            continue
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    if not data_lines:
        return None
    payload = "\n".join(data_lines)
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        parsed = {"data": payload}
    if event:
        parsed.setdefault("event", event)
    return parsed
