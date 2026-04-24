"""
L1 编译时 IR 验证器（Phase 5）

用 LLM 对照原始文档反向审查编译结果，检测三类问题：
  - 步骤遗漏（T.path 未覆盖原文关键流程）
  - 约束误判（soft/hard 分类错误，或约束内容偏离原文）
  - 知识覆盖率（N.references 是否充分覆盖原文主要知识点）

通过 ENABLE_IR_VALIDATION=1 或在 CompileRequest 中传 validate_ir=True 触发。
默认不触发，避免每次编译多消耗一次 LLM 调用。
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field

from models import SemanticKernelIR


# ── 数据结构 ──────────────────────────────────────────────────────────────────

@dataclass
class IRValidationResult:
    passed: bool
    coverage_score: float          # 0.0 ~ 1.0，知识覆盖率估计
    missing_steps: list[str] = field(default_factory=list)
    constraint_issues: list[str] = field(default_factory=list)
    reviewer_notes: str = ""
    skipped: bool = False          # True 表示因配置未开启而跳过


# ── LLM 工具定义 ──────────────────────────────────────────────────────────────

_IR_REVIEW_TOOL = {
    "type": "function",
    "function": {
        "name": "report_ir_review",
        "description": "报告对编译产出的 SemanticKernelIR 的审查结果",
        "parameters": {
            "type": "object",
            "properties": {
                "coverage_score": {
                    "type": "number",
                    "description": "IR 对原文知识点的覆盖率，0.0（完全未覆盖）到 1.0（完整覆盖）",
                },
                "missing_steps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "原文中存在但 IR T.path 未包含的关键步骤（每条一句话描述）",
                },
                "constraint_issues": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "约束分类错误或内容偏离原文的问题（每条一句话描述）",
                },
                "reviewer_notes": {
                    "type": "string",
                    "description": "总体评价，不超过 100 字",
                },
            },
            "required": ["coverage_score", "missing_steps", "constraint_issues", "reviewer_notes"],
        },
    },
}


# ── 主入口 ────────────────────────────────────────────────────────────────────

def validate_ir(ir: SemanticKernelIR, doc_text: str) -> IRValidationResult:
    """
    对照原始文档审查编译产出的 IR。
    环境变量 ENABLE_IR_VALIDATION=1 时自动触发；否则返回 skipped=True。
    """
    if not _validation_enabled():
        return IRValidationResult(passed=True, coverage_score=1.0, skipped=True)

    if not doc_text or not doc_text.strip():
        return IRValidationResult(
            passed=True,
            coverage_score=1.0,
            reviewer_notes="原文为空，跳过 IR 验证",
            skipped=True,
        )

    try:
        return _run_llm_review(ir, doc_text)
    except Exception as e:
        # 验证失败不应阻塞编译，记录问题后放行
        return IRValidationResult(
            passed=True,
            coverage_score=0.0,
            reviewer_notes=f"IR 验证调用失败（不阻塞编译）: {e}",
            skipped=True,
        )


def _validation_enabled() -> bool:
    return os.environ.get("ENABLE_IR_VALIDATION", "").strip() == "1"


def _run_llm_review(ir: SemanticKernelIR, doc_text: str) -> IRValidationResult:
    from compiler.llm import llm_json

    use_tools = _use_tool_mode()

    steps_summary = "\n".join(
        f"  - [{s.id}] {s.name}：{s.description}"
        for s in ir.t.path
    ) or "  （无步骤）"

    hard_constraints = "\n".join(f"  - {c}" for c in ir.e.hard_constraints) or "  （无）"
    soft_constraints = "\n".join(f"  - {c}" for c in ir.e.soft_constraints) or "  （无）"
    references = "\n".join(f"  - {r.path}（{r.scope}）" for r in ir.n.references) or "  （无）"

    system_prompt = """你是一个严格的认知编译审计员。
你将收到一份原始文档和从它编译出的 SemanticKernelIR。
请审查 IR 是否忠实反映了原文，聚焦三点：
1. T.path 步骤是否遗漏了原文中的关键流程
2. E.hard_constraints / E.soft_constraints 分类是否正确，内容是否贴合原文
3. 整体知识覆盖率（0.0~1.0）

请客观评价，不要过度苛求，允许合理的编译抽象。"""

    if use_tools:
        system_prompt += "\n\n请调用 report_ir_review 工具输出审查结果。"
    else:
        system_prompt += "\n\n请严格返回合法 JSON，格式：{\"coverage_score\": 0.0~1.0, \"missing_steps\": [], \"constraint_issues\": [], \"reviewer_notes\": \"...\"}"

    user_msg = f"""原始文档（前 4000 字）：
{doc_text[:4000]}

---
编译产出的 IR 摘要：

执行路径（T.path）：
{steps_summary}

硬约束（E.hard_constraints）：
{hard_constraints}

软约束（E.soft_constraints）：
{soft_constraints}

引用资源（N.references）：
{references}

领域：{ir.r.domain} | 类型：{ir.r.object_type}
语义空间：{ir.r.semantic_space}"""

    tools = [_IR_REVIEW_TOOL] if use_tools else None
    raw = llm_json(system_prompt, user_msg, tools=tools)

    coverage = float(raw.get("coverage_score", 0.5))
    missing = [str(s) for s in raw.get("missing_steps", [])]
    issues = [str(s) for s in raw.get("constraint_issues", [])]
    notes = str(raw.get("reviewer_notes", ""))

    # 判定是否通过：覆盖率 ≥ 0.6 且严重遗漏步骤 < 3
    passed = coverage >= 0.6 and len(missing) < 3

    return IRValidationResult(
        passed=passed,
        coverage_score=round(coverage, 2),
        missing_steps=missing,
        constraint_issues=issues,
        reviewer_notes=notes,
    )


def _use_tool_mode() -> bool:
    base_url = os.environ.get("OPENAI_BASE_URL", "")
    return "openrouter" in base_url or os.environ.get("ENABLE_TOOL_USE", "") == "1"
