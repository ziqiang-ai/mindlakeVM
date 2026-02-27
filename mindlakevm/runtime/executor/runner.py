"""
Skill 执行器：挂载 Skill → 检查 guardrail → 执行 → 收集 evidence → 验证
"""
from __future__ import annotations
import os
from datetime import datetime, timezone

from models import (
    SemanticKernelIR, RunRequest, RunResponse,
    EvidenceItem, TokenUsage,
)
from executor.guardrail import check_guardrails
from executor.tracer import make_trace, update_trace_decision
from executor.verifier import verify
from compiler.llm import llm_text


def run_skill(ir: SemanticKernelIR, req: RunRequest) -> RunResponse:
    # Step 1: 硬约束检查（E 核 guardrail）
    violations = check_guardrails(ir.e, req.user_input)

    if violations:
        # 被拦截：找到第一个触发拦截的步骤
        blocked_step = ir.t.path[0].id if ir.t.path else None
        trace = make_trace(ir.t.path, blocked_at=blocked_step)

        block_msg = _build_block_message(violations)
        validation = verify(ir, block_msg, [], len(trace))

        return RunResponse(
            output_text=block_msg,
            blocked=True,
            violations=violations,
            trace=trace,
            evidence=[],
            validation=validation,
            usage=TokenUsage(),
        )

    # Step 2: 正常执行 — 构建 Skill prompt 并调用 LLM
    skill_prompt = _build_skill_prompt(ir)
    output_text, in_tok, out_tok = llm_text(skill_prompt, req.user_input)

    # Step 3: 收集 evidence（从 references 中匹配相关片段）
    evidence = _collect_evidence(ir, req.user_input, output_text)

    # Step 4: 生成 trace
    trace = make_trace(ir.t.path)
    if trace:
        update_trace_decision(trace, trace[0].step_id, "正常执行完成")

    # Step 5: 验证
    validation = verify(ir, output_text, evidence, len(trace))

    return RunResponse(
        output_text=output_text,
        blocked=False,
        violations=[],
        trace=trace,
        evidence=evidence,
        validation=validation,
        usage=TokenUsage(
            input_tokens=in_tok,
            output_tokens=out_tok,
            total_tokens=in_tok + out_tok,
        ),
    )


def _build_skill_prompt(ir: SemanticKernelIR) -> str:
    """将 SemanticKernelIR 渲染为 Skill 系统提示词（Meta-Prompt → Prompt Instance）"""
    cot = "\n".join(f"- {s}" for s in ir.t.cot_steps) if ir.t.cot_steps else ""
    steps = "\n".join(
        f"{i+1}. [{s.id}] {s.name}：{s.description}"
        for i, s in enumerate(ir.t.path)
    )
    constraints = "\n".join(f"- 🔴 {c}" for c in ir.e.hard_constraints)
    soft = "\n".join(f"- 🟡 {c}" for c in ir.e.soft_constraints)
    refs = "\n".join(
        f"- {r.path}（{r.scope}，{'必须引用' if r.required else '可选'}）"
        for r in ir.n.references
    )

    return f"""你是一个专业的 AI 助手，挂载了以下 Skill：

## Skill 定位
领域：{ir.r.domain} | 类型：{ir.r.object_type}
语义空间：{ir.r.semantic_space}

## 执行路径
{steps}

## 思维链引导
{cot}

## 硬约束（绝对禁止，若触发必须拒绝执行）
{constraints if constraints else "（无）"}

## 软约束（建议遵守）
{soft if soft else "（无）"}

## 参考资源
{refs if refs else "（无）"}

## 输出要求
- 格式：{ir.e.format}
- 目标：{ir.e.target_entropy}
- 输出时引用相关参考资源中的条款作为证据

请按照执行路径和思维链，回答用户的问题。"""


def _build_block_message(violations) -> str:
    lines = ["⛔ 操作被拦截\n"]
    for v in violations:
        lines.append(f"**触发约束**：{v.constraint}")
        lines.append(f"**原因**：{v.reason}\n")
    lines.append("请满足上述约束条件后重试，或联系相关负责人获取授权。")
    return "\n".join(lines)


def _collect_evidence(ir: SemanticKernelIR, user_input: str, output_text: str) -> list[EvidenceItem]:
    """从输出文本中识别引用了哪些 reference 文件"""
    evidence: list[EvidenceItem] = []
    combined = (user_input + " " + output_text).lower()

    for ref in ir.n.references:
        # 简单启发：文件名关键词是否出现在输出中
        filename = ref.path.split("/")[-1].replace(".md", "").lower().replace("_", " ")
        keywords = filename.split()
        if any(kw in combined for kw in keywords if len(kw) > 3):
            evidence.append(EvidenceItem(
                source_path=ref.path,
                excerpt=f"（来自 {ref.path}，scope: {ref.scope}）",
                relevance=f"输出中引用了与 {ref.scope} 相关的内容",
            ))
    return evidence
