import os
from fastapi import APIRouter, HTTPException
from models import RunRequest, RunResponse
from executor.runner import run_skill
import store

router = APIRouter()


def _use_agent_mode() -> bool:
    """当使用 OpenRouter 或显式开启时，启用 Agent 模式（多轮 tool_use）。"""
    base_url = os.environ.get("OPENAI_BASE_URL", "")
    return "openrouter" in base_url or os.environ.get("ENABLE_TOOL_USE", "") == "1"


@router.post("/run", response_model=RunResponse)
def run(req: RunRequest):
    result = store.get(req.skill_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Skill '{req.skill_id}' 不存在，请先调用 /compile")
    ir, _ = result
    try:
        if _use_agent_mode():
            from executor.agent_runner import run_skill_agent
            return run_skill_agent(ir, req)
        return run_skill(ir, req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行失败: {e}")
