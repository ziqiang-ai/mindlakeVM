from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from models import (
    ToolBinding,
    ToolHandle,
    ToolProbeResult,
    ToolRegistrySyncResponse,
)


def _registry_dir() -> Path:
    path = Path(os.environ.get("TOOL_REGISTRY_DIR", "./tool_registry")).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _tools_path() -> Path:
    return _registry_dir() / "tools.json"


def _bindings_path() -> Path:
    return _registry_dir() / "bindings.json"


def _load_items(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _save_items(path: Path, items: list[dict]) -> None:
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def list_tools() -> list[ToolHandle]:
    return [ToolHandle(**item) for item in _load_items(_tools_path())]


def get_tool(tool_id: str) -> ToolHandle | None:
    for tool in list_tools():
        if tool.tool_id == tool_id:
            return tool
    return None


def save_tool(tool: ToolHandle) -> None:
    tools = _load_items(_tools_path())
    remaining = [item for item in tools if item.get("tool_id") != tool.tool_id]
    remaining.append(tool.model_dump())
    remaining.sort(key=lambda item: item["tool_id"])
    _save_items(_tools_path(), remaining)


def list_bindings() -> list[ToolBinding]:
    return [ToolBinding(**item) for item in _load_items(_bindings_path())]


def save_binding(binding: ToolBinding) -> None:
    bindings = _load_items(_bindings_path())
    remaining = [item for item in bindings if item.get("binding_id") != binding.binding_id]
    remaining.append(binding.model_dump())
    remaining.sort(key=lambda item: item["binding_id"])
    _save_items(_bindings_path(), remaining)


def get_binding_for_step(skill_id: str, step_id: str) -> ToolBinding | None:
    for binding in list_bindings():
        if binding.skill_id == skill_id and binding.step_id == step_id and binding.enabled:
            return binding
    return None


def probe_tool(tool_id: str) -> ToolProbeResult:
    tool = get_tool(tool_id)
    if not tool:
        return ToolProbeResult(tool_id=tool_id, ok=False, message="tool not found")

    command_path = shutil.which(tool.command)
    if not command_path and not Path(tool.command).exists():
        return ToolProbeResult(tool_id=tool_id, ok=False, message=f"command not found: {tool.command}")
    command_path = command_path or tool.command

    try:
        proc = subprocess.run(
            [command_path, "--help"],
            capture_output=True,
            text=True,
            timeout=max(tool.timeout_ms // 1000, 1),
            check=False,
        )
    except Exception as exc:
        return ToolProbeResult(tool_id=tool_id, ok=False, message=str(exc))

    return ToolProbeResult(
        tool_id=tool.tool_id,
        ok=proc.returncode == 0,
        supports_json=tool.supports_json,
        supports_repl=tool.supports_repl,
        version=tool.version,
        message=None if proc.returncode == 0 else (proc.stderr or proc.stdout)[:300],
    )


def sync_cli_anything_registry(registry_path: str, overwrite: bool = False) -> ToolRegistrySyncResponse:
    path = Path(registry_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"registry.json not found: {path}")

    registry = json.loads(path.read_text(encoding="utf-8"))
    existing_ids = {tool.tool_id for tool in list_tools()}
    imported = 0
    skipped = 0

    entries = registry if isinstance(registry, list) else (
        registry.get("tools")
        or registry.get("clis")
        or registry.get("items")
        or []
    )

    for item in entries:
        tool = _tool_from_cli_anything_entry(item)
        if not overwrite and tool.tool_id in existing_ids:
            skipped += 1
            continue
        save_tool(tool)
        imported += 1
        existing_ids.add(tool.tool_id)

    snapshot_id = f"snap_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:6]}"
    return ToolRegistrySyncResponse(snapshot_id=snapshot_id, imported=imported, skipped=skipped)


def _tool_from_cli_anything_entry(item: dict) -> ToolHandle:
    name = item.get("name") or item.get("id") or item.get("package") or "unknown"
    normalized = name.removeprefix("cli-anything-").replace("-", "_")
    category = item.get("category", "software")
    capabilities = item.get("capabilities") or [f"{category}.operate"]
    command = item.get("entry_point") or item.get("command") or name
    install_command = item.get("install_command") or item.get("install_cmd") or item.get("install") or ""
    skill_path = item.get("skill_path") or item.get("skill") or item.get("skill_md")

    return ToolHandle(
        tool_id=f"cli_anything_{normalized}",
        name=item.get("display_name") or name,
        version=item.get("version", "0.1.0"),
        provider="cli-anything",
        command=command,
        capabilities=capabilities,
        side_effect_level=item.get("side_effect_level", "write_optional"),
        requires_confirmation=item.get("requires_confirmation", True),
        supports_json=item.get("supports_json", True),
        supports_repl=item.get("supports_repl", True),
        timeout_ms=item.get("timeout_ms", 30000),
        skill_path=skill_path,
        registry_metadata={
            "install_command": install_command,
            "source": "cli-anything-registry",
            "raw_entry": item,
        },
    )
