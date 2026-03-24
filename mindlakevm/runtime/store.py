"""
持久化 Skill Store — JSON 文件存储，热重启不丢失
存储路径：$SKILLS_DIR/<skill_id>.json
"""
from __future__ import annotations
import json
import os
from pathlib import Path

from models import SemanticKernelIR, SkillPackage, SkillSummary


def _skills_dir() -> str:
    d = os.environ.get("SKILLS_DIR", "./skills")
    os.makedirs(d, exist_ok=True)
    return d


def _skill_path(skill_id: str) -> str:
    return os.path.join(_skills_dir(), f"{skill_id}.json")


def _compile_cache_path() -> str:
    return os.path.join(_skills_dir(), ".compile_cache.json")


def _load_compile_cache() -> dict[str, str]:
    path = _compile_cache_path()
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_compile_cache(cache: dict[str, str]) -> None:
    with open(_compile_cache_path(), "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)


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
        if fname.startswith("."):
            continue
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


def get_cached_skill_id(fingerprint: str) -> str | None:
    return _load_compile_cache().get(fingerprint)


def save_compile_cache(fingerprint: str, skill_id: str) -> None:
    cache = _load_compile_cache()
    cache[fingerprint] = skill_id
    _save_compile_cache(cache)


def bundle_root(skill_id: str) -> Path:
    return Path(_skills_dir()) / skill_id


def read_bundle_file(skill_id: str, relative_path: str) -> str:
    root = bundle_root(skill_id).resolve()
    target = (root / relative_path).resolve()

    if not str(target).startswith(str(root)):
        raise ValueError(f"非法文件路径: {relative_path}")
    if not target.exists() or not target.is_file():
        raise FileNotFoundError(f"Skill 文件不存在: {relative_path}")

    return target.read_text(encoding="utf-8")
