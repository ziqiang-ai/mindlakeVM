"""
持久化 Skill Store — JSON 文件存储，热重启不丢失
存储路径：$SKILLS_DIR/<skill_id>.json
"""
from __future__ import annotations
import json
import os

from models import SemanticKernelIR, SkillPackage, SkillSummary


def _skills_dir() -> str:
    d = os.environ.get("SKILLS_DIR", "./skills")
    os.makedirs(d, exist_ok=True)
    return d


def _skill_path(skill_id: str) -> str:
    return os.path.join(_skills_dir(), f"{skill_id}.json")


def save(skill_id: str, ir: SemanticKernelIR, package: SkillPackage) -> None:
    data = {
        "ir": ir.model_dump(by_alias=True),
        "package": package.model_dump(),
    }
    with open(_skill_path(skill_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get(skill_id: str) -> tuple[SemanticKernelIR, SkillPackage] | None:
    path = _skill_path(skill_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    ir = SemanticKernelIR(**data["ir"])
    package = SkillPackage(**data["package"])
    return ir, package


def list_all() -> list[SkillSummary]:
    d = _skills_dir()
    summaries = []
    for fname in sorted(os.listdir(d)):
        if not fname.endswith(".json"):
            continue
        skill_id = fname[:-5]
        result = get(skill_id)
        if result is None:
            continue
        ir, pkg = result
        summaries.append(SkillSummary(
            skill_id=skill_id,
            skill_name=pkg.skill_name,
            description=pkg.description,
            domain=ir.r.domain,
            object_type=ir.r.object_type,
            compiled_at=ir.compiled_at,
        ))
    return summaries


def exists(skill_id: str) -> bool:
    return os.path.exists(_skill_path(skill_id))
