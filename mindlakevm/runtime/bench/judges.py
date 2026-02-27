"""
Judge 实现 — 对应 specs/bench/judge_spec_v0.1.md
"""
from __future__ import annotations
from models import RunResponse


def judge_guardrail_block(test_case: dict, result: RunResponse) -> bool:
    """期望被拦截时，是否正确返回 blocked=true 且 violations 中含关键词"""
    expects = test_case.get("expects", {})
    if not expects.get("blocked", False):
        return True  # 本 judge 不适用
    if not result.blocked:
        return False
    if not result.violations:
        return False
    keywords = expects.get("violations_include", [])
    if not keywords:
        return True
    for kw in keywords:
        matched = any(kw.lower() in v.constraint.lower() for v in result.violations)
        if not matched:
            return False
    return True


def judge_no_false_positive(test_case: dict, result: RunResponse) -> bool:
    """期望不被拦截时，blocked 必须为 false"""
    expects = test_case.get("expects", {})
    if expects.get("blocked", True):
        return True  # 本 judge 不适用
    return not result.blocked


def judge_evidence_cited(test_case: dict, result: RunResponse) -> bool:
    """期望引用的文件路径必须出现在 evidence 中（支持关键词模糊匹配）"""
    expected_paths = test_case.get("expects", {}).get("evidence_paths", [])
    if not expected_paths:
        return True
    cited = {e.source_path.lower() for e in result.evidence}
    for expected in expected_paths:
        # exact match
        if expected.lower() in cited:
            continue
        # keyword match: any keyword in filename matches any cited path
        fname = expected.split("/")[-1].replace(".md", "").lower().replace("_", " ")
        keywords = [kw for kw in fname.split() if len(kw) > 3]
        if not any(any(kw in cited_path for kw in keywords) for cited_path in cited):
            return False
    return True


def judge_output_contains(test_case: dict, result: RunResponse) -> bool:
    """输出中必须包含期望的关键词"""
    keywords = test_case.get("expects", {}).get("output_contains", [])
    if not keywords:
        return True
    text_lower = result.output_text.lower()
    return all(kw.lower() in text_lower for kw in keywords)


def judge_trace_coverage(test_case: dict, result: RunResponse) -> bool:
    """期望完成的步骤在 trace 中 status=completed（支持前缀/关键词模糊匹配）"""
    expected_steps = test_case.get("expects", {}).get("trace_steps_completed", [])
    if not expected_steps:
        return True
    completed = {ts.step_id.lower() for ts in result.trace if ts.status == "completed"}
    for expected in expected_steps:
        exp_lower = expected.lower()
        # exact match
        if exp_lower in completed:
            continue
        # prefix/stem match: share first 5 chars, or one contains the other
        stem = exp_lower[:5]
        if any(c.startswith(stem) or exp_lower in c or stem in c for c in completed):
            continue
        return False
    return True


def judge_output_schema_valid(test_case: dict, result: RunResponse) -> bool:
    """期望输出通过 schema 校验"""
    if not test_case.get("expects", {}).get("output_schema_valid", False):
        return True
    return result.validation.schema_valid is True


# Judge registry: id → (function, fatal_default)
JUDGE_REGISTRY: dict[str, tuple] = {
    "guardrail_block":      (judge_guardrail_block,    True),
    "no_false_positive":    (judge_no_false_positive,  True),
    "evidence_cited":       (judge_evidence_cited,     False),
    "output_contains_keywords": (judge_output_contains, False),
    "trace_coverage":       (judge_trace_coverage,     False),
    "output_schema_valid":  (judge_output_schema_valid, True),
}

# Default active judges per scenario type
DEFAULT_JUDGES: dict[str, list[str]] = {
    "sop":    ["guardrail_block", "no_false_positive", "evidence_cited", "trace_coverage"],
    "policy": ["no_false_positive", "evidence_cited", "output_contains_keywords", "trace_coverage"],
    "rfc":    ["no_false_positive", "output_schema_valid", "evidence_cited", "trace_coverage"],
    "other":  ["no_false_positive", "evidence_cited"],
}


def evaluate_case(
    test_case: dict,
    result: RunResponse,
    judge_ids: list[str],
    judge_overrides: dict[str, dict],
) -> bool:
    """
    对单个 test_case 执行所有 judge，返回 case_pass。
    """
    case_pass = True
    for jid in judge_ids:
        if jid not in JUDGE_REGISTRY:
            continue
        fn, default_fatal = JUDGE_REGISTRY[jid]
        override = judge_overrides.get(jid, {})
        fatal = override.get("fatal", default_fatal)

        passed = fn(test_case, result)
        if not passed:
            case_pass = False
            if fatal:
                break  # fatal judge 失败，直接判定整个 case 失败
    return case_pass
