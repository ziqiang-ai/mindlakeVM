"""
验证器 V1 / V2 / V3
V1: 输出 schema 校验（当 n.schema 存在时）
V2: 引用充分性校验（n.references[required=true] 必须出现在 evidence 中）
V3: 停止规则（检测循环/超步数）
"""
from __future__ import annotations
import json

from models import (
    SemanticKernelIR, EvidenceItem, ValidationResult,
)


def verify(
    ir: SemanticKernelIR,
    output_text: str,
    evidence: list[EvidenceItem],
    trace_steps_completed: int,
) -> ValidationResult:
    warnings: list[str] = []

    # V1: schema 校验
    schema_valid: bool | None = None
    if ir.e.format == "json" and ir.n.schema_:
        schema_valid = _validate_json_schema(output_text, ir.n.schema_)
        if schema_valid is False:
            warnings.append("V1: 输出未通过 N.schema JSON Schema 校验")

    # V2: 引用充分性
    evidence_sufficient: bool | None = None
    required_refs = [r.path for r in ir.n.references if r.required]
    if required_refs:
        cited_paths = {e.source_path for e in evidence}
        missing = [p for p in required_refs if p not in cited_paths]
        evidence_sufficient = len(missing) == 0
        if not evidence_sufficient:
            warnings.append(f"V2: 以下必须引用的文件未在 evidence 中出现: {missing}")

    # V3: 停止规则（超过最大步数视为异常）
    MAX_STEPS = 10
    stop_condition_met: bool | None = None
    if trace_steps_completed > MAX_STEPS:
        stop_condition_met = True
        warnings.append(f"V3: 执行步骤数 ({trace_steps_completed}) 超过最大限制 ({MAX_STEPS})")
    else:
        stop_condition_met = False

    # 软约束 warning（不影响 passed）
    for sc in ir.e.soft_constraints:
        warnings.append(f"soft_constraint: {sc}")

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
    except (json.JSONDecodeError, Exception):
        return False
