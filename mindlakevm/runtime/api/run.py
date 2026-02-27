from fastapi import APIRouter, HTTPException
from models import RunRequest, RunResponse
from executor.runner import run_skill
import store

router = APIRouter()


@router.post("/run", response_model=RunResponse)
def run(req: RunRequest):
    result = store.get(req.skill_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Skill '{req.skill_id}' 不存在，请先调用 /compile")
    ir, _ = result
    try:
        return run_skill(ir, req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行失败: {e}")
