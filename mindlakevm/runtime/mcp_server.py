"""
Layer 5: MindLakeVM MCP Server

将 MindLakeVM 的编译、执行、Skills 暴露为 MCP 协议，
让任何 MCP 客户端（Claude Desktop、claude.ai、Claude Code、第三方）都能：
- 发现已编译的 Skills
- 编译新文档为 Skill
- 执行 Skill（含 guardrail + Agent 循环）
- 读取 Skill 的 IR、trace 等内部状态

支持两种运行模式：
1. 独立运行：python mcp_server.py（默认 streamable-http，也可 stdio）
2. 挂载到 FastAPI：在 main.py 中 mount 到 /mcp 路径

使用方法：
  # 独立 HTTP 模式（推荐）
  python mcp_server.py

  # stdio 模式（适合 Claude Desktop 本地集成）
  python mcp_server.py --stdio

  # 添加到 Claude Code
  claude mcp add --transport http mindlake-vm http://localhost:9100/mcp
"""
from __future__ import annotations
import json
import os
import sys

from dotenv import load_dotenv
load_dotenv()

# 确保 runtime 目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP

from models import CompileRequest, RunRequest
from compiler.pipeline import compile_document
from compiler.tool_export import ir_to_claude_tool, export_skill_bundle
import store


# ── MCP Server 实例 ──────────────────────────────────────────────────────────

mcp = FastMCP(
    "MindLakeVM",
    instructions=(
        "MindLakeVM 是一个认知编译平台，将企业文档编译为可执行的 AI Skill。"
        "每个 Skill 包含 RNET 四核 IR（表示/标注/熵控/变换），"
        "执行时自动进行合规门禁（guardrail）检查、逐步 trace 和证据收集。"
    ),
)


# ── Tools ────────────────────────────────────────────────────────────────────

@mcp.tool()
def mindlake_compile(
    task_description: str,
    document_content: str = "",
    strategy: str = "default",
) -> str:
    """将企业文档编译为可执行的 MindLakeVM Skill。

    输入一段文档（SOP、政策、RFC 等）和任务描述，
    自动提取 RNET 四核 IR 并生成可执行 Skill。

    参数：
    - task_description: 任务描述，如"编译 Sev1 事故响应 SOP"
    - document_content: 文档正文（可选，不提供则仅凭任务描述）
    - strategy: 编译策略 minimal | default | detailed
    """
    req = CompileRequest(
        task_description=task_description,
        document_content=document_content or None,
        strategy=strategy,
    )
    ir, package = compile_document(req)
    store.save(package.skill_id, ir, package)
    return json.dumps({
        "status": "compiled",
        "skill_id": package.skill_id,
        "kernel_id": ir.kernel_id,
        "domain": ir.r.domain,
        "object_type": ir.r.object_type,
        "semantic_space": ir.r.semantic_space,
        "hard_constraints": ir.e.hard_constraints,
        "steps": [s.name for s in ir.t.path],
        "step_count": len(ir.t.path),
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def mindlake_list_skills() -> str:
    """列出所有已编译的 MindLakeVM Skills。

    返回每个 Skill 的 ID、名称、领域、类型和编译时间。
    """
    skills = store.list_all()
    result = []
    for s in skills:
        entry = {
            "skill_id": s.skill_id,
            "skill_name": s.skill_name,
            "domain": s.domain,
            "object_type": s.object_type,
            "compiled_at": s.compiled_at,
        }
        # 补充约束和步骤信息
        data = store.get(s.skill_id)
        if data:
            ir, _ = data
            entry["hard_constraints_count"] = len(ir.e.hard_constraints)
            entry["step_count"] = len(ir.t.path)
        result.append(entry)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def mindlake_run(skill_id: str, user_input: str) -> str:
    """执行一个已编译的 MindLakeVM Skill。

    执行流程：
    1. 合规门禁（guardrail）— 检查硬约束
    2. Agent 循环执行 — 逐步骤处理，收集证据
    3. 验证 — 检查输出是否符合协议

    参数：
    - skill_id: Skill ID（通过 mindlake_list_skills 获取）
    - user_input: 用户的问题或请求
    """
    result = store.get(skill_id)
    if not result:
        return json.dumps({"error": f"Skill '{skill_id}' 不存在，请先调用 mindlake_compile"}, ensure_ascii=False)

    ir, _ = result
    req = RunRequest(skill_id=skill_id, user_input=user_input)

    # 根据环境选择执行器
    base_url = os.environ.get("OPENAI_BASE_URL", "")
    use_agent = "openrouter" in base_url or os.environ.get("ENABLE_TOOL_USE", "") == "1"

    if use_agent:
        from executor.agent_runner import run_skill_agent
        response = run_skill_agent(ir, req)
    else:
        from executor.runner import run_skill
        response = run_skill(ir, req)

    output = {
        "output_text": response.output_text,
        "blocked": response.blocked,
    }
    if response.blocked:
        output["violations"] = [v.model_dump() for v in response.violations]
    if response.trace:
        output["trace"] = [
            {"step_id": t.step_id, "status": t.status, "notes": t.notes}
            for t in response.trace
        ]
    if response.evidence:
        output["evidence"] = [e.model_dump() for e in response.evidence]
    if response.validation:
        output["validation"] = response.validation.model_dump()
    if response.usage:
        output["usage"] = response.usage.model_dump()

    return json.dumps(output, ensure_ascii=False, indent=2)


@mcp.tool()
def mindlake_skill_tool_definition(skill_id: str) -> str:
    """获取 Skill 的 Claude Tool Definition（可直接注册到其他 Agent）。

    返回包含 tool definition、examples、search metadata 的完整工具包。
    """
    result = store.get(skill_id)
    if not result:
        return json.dumps({"error": f"Skill '{skill_id}' 不存在"}, ensure_ascii=False)
    ir, _ = result
    bundle = export_skill_bundle(ir)
    return json.dumps(bundle, ensure_ascii=False, indent=2)


# ── Resources ────────────────────────────────────────────────────────────────

@mcp.resource("skill://{skill_id}/ir")
def get_skill_ir(skill_id: str) -> str:
    """获取 Skill 的完整 SemanticKernel IR（RNET 四核中间表示）。"""
    result = store.get(skill_id)
    if not result:
        return json.dumps({"error": f"Skill '{skill_id}' not found"})
    ir, _ = result
    return ir.model_dump_json(indent=2)


@mcp.resource("skill://{skill_id}/summary")
def get_skill_summary(skill_id: str) -> str:
    """获取 Skill 的摘要信息。"""
    result = store.get(skill_id)
    if not result:
        return json.dumps({"error": f"Skill '{skill_id}' not found"})
    ir, pkg = result
    summary = {
        "skill_id": pkg.skill_id,
        "skill_name": pkg.skill_name,
        "domain": ir.r.domain,
        "object_type": ir.r.object_type,
        "semantic_space": ir.r.semantic_space,
        "target_entropy": ir.e.target_entropy,
        "hard_constraints": ir.e.hard_constraints,
        "soft_constraints": ir.e.soft_constraints,
        "steps": [{"id": s.id, "name": s.name} for s in ir.t.path],
        "references": [{"path": r.path, "scope": r.scope} for r in ir.n.references],
    }
    return json.dumps(summary, ensure_ascii=False, indent=2)


@mcp.resource("skill://{skill_id}/tool")
def get_skill_tool_def(skill_id: str) -> str:
    """获取 Skill 的 Claude Tool Definition。"""
    result = store.get(skill_id)
    if not result:
        return json.dumps({"error": f"Skill '{skill_id}' not found"})
    ir, _ = result
    tool_def = ir_to_claude_tool(ir)
    return json.dumps(tool_def, ensure_ascii=False, indent=2)


# ── Prompts ──────────────────────────────────────────────────────────────────

@mcp.prompt()
def skill_system_prompt(skill_id: str) -> str:
    """将 Skill 渲染为 system prompt（Meta-Prompt → Prompt Instance）。

    可直接用作 Claude 的 system prompt 来挂载此 Skill。
    """
    result = store.get(skill_id)
    if not result:
        return f"Error: Skill '{skill_id}' not found"
    ir, _ = result
    from executor.agent_runner import build_agent_system_prompt
    return build_agent_system_prompt(ir)


@mcp.prompt()
def compile_guide(document_type: str = "SOP") -> str:
    """编译指南 — 告诉 Claude 如何使用 MindLakeVM 编译文档。"""
    return f"""你现在可以使用 MindLakeVM 将 {document_type} 文档编译为可执行的 AI Skill。

使用步骤：
1. 调用 mindlake_compile 工具，传入任务描述和文档内容
2. 编译完成后会返回 Skill ID
3. 调用 mindlake_run 工具，传入 Skill ID 和用户问题来执行

编译策略：
- minimal：最精简，适合简单文档
- default：标准详细度（推荐）
- detailed：最详尽，适合复杂 SOP/政策

示例：
```
mindlake_compile(
    task_description="编译 Sev1 事故响应 SOP",
    document_content="<文档全文>",
    strategy="default"
)
```

编译后的 Skill 包含：
- R 核（表示）：领域、类型、语义空间
- N 核（标注）：输出结构、约束、引用文件
- E 核（熵控）：硬约束（红线）、软约束、盲点
- T 核（变换）：执行路径、决策点、思维链
"""


# ── 入口 ─────────────────────────────────────────────────────────────────────

def get_mcp_app():
    """返回可挂载到 FastAPI/Starlette 的 MCP ASGI app。

    用法（在 main.py 中）：
        from mcp_server import get_mcp_app
        app.mount("/mcp", get_mcp_app())
    """
    return mcp.streamable_http_app()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="MindLakeVM MCP Server")
    parser.add_argument("--stdio", action="store_true", help="使用 stdio 传输（适合 Claude Desktop）")
    parser.add_argument("--port", type=int, default=9100, help="HTTP 端口（默认 9100）")
    args = parser.parse_args()

    if args.stdio:
        print("Starting MindLakeVM MCP Server (stdio mode)...", file=sys.stderr)
        mcp.run(transport="stdio")
    else:
        import uvicorn
        print(f"Starting MindLakeVM MCP Server on http://localhost:{args.port}/mcp", file=sys.stderr)
        uvicorn.run(mcp.streamable_http_app(), host="0.0.0.0", port=args.port)
