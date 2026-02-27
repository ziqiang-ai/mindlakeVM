from fastapi import APIRouter, HTTPException
from models import SkillDetail
import store

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
