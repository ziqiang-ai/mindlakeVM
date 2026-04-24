"""
验证器 V1 / V2 / V3
V1: 输出 schema 校验（当 n.schema 存在时）
V2: 引用充分性校验（n.references[required=true] 必须出现在 evidence 中）
V3: 停止规则（检测循环/超步数）

公共工具函数：
  match_reference_path()  —— 统一引用路径匹配逻辑，供 verifier / judges / bench 复用
"""
from __future__ import annotations
import json

from models import (
    SemanticKernelIR, EvidenceItem, ValidationResult,
)

# ── 公共：引用路径匹配 ─────────────────────────────────────────────────────────

def match_reference_path(expected: str, cited_paths: set[str]) -> bool:
    """
    判断 expected 引用路径是否在 cited_paths 中命中。
    匹配策略（优先级递减）：
      1. 精确匹配（大小写不敏感）
      2. 文件名关键词匹配（去掉扩展名和分隔符后，取长度 ≥ 4 的词）
    """
    expected_lower = expected.lower()
    cited_lower = {p.lower() for p in cited_paths}

    # 精确匹配
    if expected_lower in cited_lower:
        return True

    # 关键词匹配：从文件名中提取有意义的词
    fname = expected_lower.split("/")[-1]
    for ext in (".md", ".txt", ".json", ".yaml", ".yml"):
        fname = fname.replace(ext, "")
    keywords = [kw for kw in fname.replace("_", " ").replace("-", " ").split() if len(kw) >= 4]

    if not keywords:
        return False

    return any(
        any(kw in cited_path for kw in keywords)
        for cited_path in cited_lower
    )


# ── 验证器主入口 ───────────────────────────────────────────────────────────────

MAX_TRACE_STEPS = 10


def verify(
    ir: SemanticKernelIR,
    output_text: str,
    evidence: list[EvidenceItem],
    trace_steps_completed: int,
) -> ValidationResult:
    warnings: list[str] = []

    # V1: JSON Schema 校验
    schema_valid: bool | None = None
    if ir.e.format == "json" and ir.n.schema_:
        schema_valid = _validate_json_schema(output_text, ir.n.schema_)
        if schema_valid is False:
            warnings.append("V1: 输出未通过 N.schema JSON Schema 校验")

    # V2: 必须引用文件的充分性校验（使用统一匹配函数）
    evidence_sufficient: bool | None = None
    required_refs = [r.path for r in ir.n.references if r.required]
    if required_refs:
        cited_paths = {e.source_path for e in evidence}
        missing = [p for p in required_refs if not match_reference_path(p, cited_paths)]
        evidence_sufficient = len(missing) == 0
        if not evidence_sufficient:
            warnings.append(f"V2: 以下必须引用的文件未在 evidence 中出现: {missing}")

    # V3: 停止规则
    stop_condition_met: bool | None = None
    if trace_steps_completed > MAX_TRACE_STEPS:
        stop_condition_met = True
        warnings.append(
            f"V3: 执行步骤数 ({trace_steps_completed}) 超过最大限制 ({MAX_TRACE_STEPS})"
        )
    else:
        stop_condition_met = False

    passed = (
        (schema_valid is not False)
        and (evidence_sufficient is not False)
        and (stop_condition_met is not True)
    )

    return ValidationResult(
        passed=passed,
        schema_valid=schema_valid,
        evidence_sufficient=evidence_sufficient,
        stop_condition_met=stop_condition_met,
        warnings=warnings,
    )


def _validate_json_schema(output_text: str, schema: dict) -> bool:
    try:
        import jsonschema
        data = json.loads(output_text)
        jsonschema.validate(data, schema)
        return True
    except json.JSONDecodeError:
        return False
    except Exception:
        return False
