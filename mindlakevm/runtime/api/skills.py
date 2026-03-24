from typing import Literal
from fastapi import APIRouter, HTTPException, Query
from models import SkillDetail
import store
from compiler.tool_export import (
    ir_to_claude_tool,
    ir_to_mcp_tool,
    ir_to_tool_search_metadata,
    export_skill_bundle,
    export_all_tools,
    generate_tool_examples,
)

router = APIRouter()


@router.get("/skills")
def list_skills():
    return {"skills": store.list_all()}


@router.get("/skills/{skill_id}", response_model=SkillDetail)
def get_skill(skill_id: str):
    result = store.get(skill_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' 不存在")
    ir, package = result
    return SkillDetail(
        skill_id=package.skill_id,
        skill_name=package.skill_name,
        description=package.description,
        domain=ir.r.domain,
        object_type=ir.r.object_type,
        compiled_at=ir.compiled_at,
        ir=ir,
        files_tree=package.files_tree,
    )


@router.get("/skills/{skill_id}/file")
def get_skill_file(
    skill_id: str,
    path: str = Query(..., description="Skill 包内相对路径，例如 SKILL.md 或 references/xxx.md"),
):
    result = store.get(skill_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' 不存在")
    try:
        content = store.read_bundle_file(skill_id, path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Skill 文件不存在: {path}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"skill_id": skill_id, "path": path, "content": content}


# ── Layer 4: Tool Definition 导出端点 ────────────────────────────────────────

@router.get("/skills/{skill_id}/tool")
def get_tool_definition(
    skill_id: str,
    format: Literal["claude", "mcp", "search", "bundle"] = Query(
        default="claude",
        description="导出格式: claude (OpenAI function calling) | mcp (MCP Tool) | search (Tool Search metadata) | bundle (全部格式)"
    ),
    include_examples: bool = Query(default=True, description="是否包含 Tool Use Examples"),
    base_url: str = Query(default="", description="MCP 格式的 base URL"),
):
    """导出单个 Skill 的 Claude Tool Definition。

    用途：
    - 外部 Claude Agent 获取 tool definition 后直接注册使用
    - MCP Server 注册时使用 mcp 格式
    - Tool Search 索引时使用 search 格式
    - bundle 一次性获取所有格式
    """
    result = store.get(skill_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' 不存在")
    ir, _ = result

    if format == "bundle":
        return export_skill_bundle(ir, base_url=base_url)
    if format == "mcp":
        return ir_to_mcp_tool(ir, base_url=base_url)
    if format == "search":
        return ir_to_tool_search_metadata(ir)
    return ir_to_claude_tool(ir, include_examples=include_examples)


@router.get("/skills/{skill_id}/examples")
def get_tool_examples(skill_id: str):
    """获取 Skill 自动生成的 Tool Use Examples。

    Claude Advanced Tool Use 的 Tool Use Examples 功能：
    帮助 Claude 更准确判断何时调用此 Skill 以及如何构造参数。
    """
    result = store.get(skill_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' 不存在")
    ir, _ = result
    return {"skill_id": skill_id, "examples": generate_tool_examples(ir)}


@router.get("/tools")
def list_all_tools(
    format: Literal["claude", "mcp", "search"] = Query(
        default="claude",
        description="导出格式: claude | mcp | search"
    ),
    include_examples: bool = Query(default=True),
    base_url: str = Query(default=""),
):
    """批量导出所有已编译 Skills 的 Tool Definitions。

    典型用法：
    1. Claude Agent 启动时调用 GET /tools?format=claude 获取所有可用工具
    2. MCP Server 启动时调用 GET /tools?format=mcp 注册所有工具
    3. Tool Search 索引时调用 GET /tools?format=search 获取元数据
    """
    all_skills = store.list_all()
    irs = []
    for s in all_skills:
        result = store.get(s.skill_id)
        if result:
            irs.append(result[0])

    tools = export_all_tools(irs, format=format, base_url=base_url, include_examples=include_examples)
    return {"count": len(tools), "tools": tools}
