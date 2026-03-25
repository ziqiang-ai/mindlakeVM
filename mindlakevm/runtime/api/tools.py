from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models import ToolBinding, ToolHandle, ToolRegistrySyncRequest
import tool_registry

router = APIRouter()


@router.get("/tool-handles")
def list_tool_handles():
    tools = tool_registry.list_tools()
    return {"count": len(tools), "tools": tools}


@router.get("/tool-handles/{tool_id}")
def get_tool_handle(tool_id: str):
    tool = tool_registry.get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' 不存在")
    return tool


@router.post("/tool-handles/register")
def register_tool_handle(tool: ToolHandle):
    tool_registry.save_tool(tool)
    return {"status": "ok", "tool_id": tool.tool_id}


@router.post("/tool-handles/sync/cli-anything")
def sync_cli_anything(req: ToolRegistrySyncRequest):
    try:
        return tool_registry.sync_cli_anything_registry(req.registry_path, overwrite=req.overwrite)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/tool-handles/{tool_id}/probe")
def probe_tool_handle(tool_id: str):
    if not tool_registry.get_tool(tool_id):
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' 不存在")
    return tool_registry.probe_tool(tool_id)


@router.get("/tool-bindings")
def list_tool_bindings():
    bindings = tool_registry.list_bindings()
    return {"count": len(bindings), "bindings": bindings}


@router.post("/tool-bindings")
def create_tool_binding(binding: ToolBinding):
    tool_registry.save_binding(binding)
    return {"status": "ok", "binding_id": binding.binding_id}
