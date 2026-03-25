from __future__ import annotations

import json
import shlex
import subprocess
import time
from pathlib import Path

from models import ToolExecutionResult, ToolArtifact, ToolExecutionUsage, ToolHandle, ToolInvocation


def invoke_cli_tool(handle: ToolHandle, invocation: ToolInvocation) -> ToolExecutionResult:
    command = _build_command(handle, invocation)
    started = time.perf_counter()
    proc = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=max(invocation.timeout_ms // 1000, 1),
        check=False,
    )
    duration_ms = int((time.perf_counter() - started) * 1000)

    stdout_json = _parse_stdout_json(proc.stdout)
    artifacts = _extract_artifacts(stdout_json, invocation.args)
    status = "success" if proc.returncode == 0 else "error"

    return ToolExecutionResult(
        invocation_id=invocation.invocation_id,
        tool_id=handle.tool_id,
        status=status,
        exit_code=proc.returncode,
        stdout_json=stdout_json,
        stderr_text=(proc.stderr or "")[:4000],
        artifacts=artifacts,
        usage=ToolExecutionUsage(wall_time_ms=duration_ms),
    )


def _build_command(handle: ToolHandle, invocation: ToolInvocation) -> list[str]:
    command = shlex.split(handle.command)
    for key, value in invocation.args.items():
        flag = f"--{key.replace('_', '-')}"
        if isinstance(value, bool):
            if value:
                command.append(flag)
            continue
        command.extend([flag, json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)])

    if handle.supports_json:
        command.append("--json")
    if invocation.dry_run:
        command.append("--dry-run")
    return command


def _parse_stdout_json(stdout: str) -> dict:
    text = stdout.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw_output": text}


def _extract_artifacts(stdout_json: dict, args: dict) -> list[ToolArtifact]:
    artifacts: list[ToolArtifact] = []
    output_path = stdout_json.get("output_path") or args.get("output_path")
    if output_path:
        artifacts.append(ToolArtifact(path=str(output_path), type=_artifact_type_from_path(str(output_path))))

    for item in stdout_json.get("artifacts", []):
        if isinstance(item, dict) and item.get("path"):
            artifacts.append(ToolArtifact(path=item["path"], type=item.get("type", _artifact_type_from_path(item["path"]))))
    return artifacts


def _artifact_type_from_path(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in {".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".odt", ".odp"}:
        return "document"
    if suffix in {".png", ".jpg", ".jpeg", ".svg"}:
        return "image"
    if suffix in {".pdf"}:
        return "pdf"
    return "artifact"
