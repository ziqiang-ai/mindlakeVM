"""
Skill 执行器：挂载 Skill → 检查 guardrail → 执行 → 收集 evidence → 验证
"""
from __future__ import annotations
import os
import re
from datetime import datetime, timezone

from models import (
    SemanticKernelIR, RunRequest, RunResponse,
    EvidenceItem, TokenUsage,
)
from executor.guardrail import check_guardrails
from executor.tracer import make_trace, update_trace_decision
from executor.verifier import verify
from compiler.llm import llm_text
import store


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
    reference_contexts = _select_reference_context(ir, req.skill_id, req.user_input)
    skill_prompt = _build_skill_prompt(ir, reference_contexts)
    output_text, in_tok, out_tok = llm_text(skill_prompt, req.user_input)

    # Step 3: 收集 evidence（从 references 中匹配相关片段）
    evidence = _collect_evidence(ir, req.skill_id, req.user_input, output_text, reference_contexts)

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


def _build_skill_prompt(ir: SemanticKernelIR, reference_contexts: list[dict] | None = None) -> str:
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
    ref_context = "\n\n".join(
        f"### {ctx['path']}\n{ctx['snippet']}"
        for ctx in (reference_contexts or [])
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

## 参考片段
{ref_context if ref_context else "（无可用片段）"}

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


def _collect_evidence(
    ir: SemanticKernelIR,
    skill_id: str,
    user_input: str,
    output_text: str,
    reference_contexts: list[dict] | None = None,
) -> list[EvidenceItem]:
    """从引用文件中提取与问答匹配的 evidence。"""
    evidence: list[EvidenceItem] = []
    combined = (user_input + " " + output_text).lower()
    context_by_path = {ctx["path"]: ctx for ctx in (reference_contexts or [])}
    for ref in ir.n.references:
        snippet = context_by_path.get(ref.path, {}).get("snippet")
        if snippet and any(term in combined for term in _reference_terms(ref.path, ref.scope)):
            evidence.append(EvidenceItem(
                source_path=ref.path,
                excerpt=snippet,
                relevance=f"引用了 {ref.scope} 的相关片段",
            ))
            continue

        try:
            content = store.read_bundle_file(skill_id, ref.path)
        except (FileNotFoundError, ValueError):
            continue
        matched = _best_matching_snippet(content, combined)
        if matched and any(term in combined for term in _reference_terms(ref.path, ref.scope)):
            evidence.append(EvidenceItem(
                source_path=ref.path,
                excerpt=matched,
                relevance=f"从 {ref.scope} 中匹配到相关内容",
            ))
    return evidence


def _select_reference_context(ir: SemanticKernelIR, skill_id: str, user_input: str, top_k: int = 3) -> list[dict]:
    contexts: list[dict] = []
    query_terms = _tokenize(user_input)

    for ref in ir.n.references:
        try:
            content = store.read_bundle_file(skill_id, ref.path)
        except (FileNotFoundError, ValueError):
            continue
        snippet = _best_matching_snippet(content, user_input.lower(), query_terms=query_terms)
        if not snippet:
            continue
        score = _score_text(snippet, user_input.lower(), query_terms)
        contexts.append({
            "path": ref.path,
            "scope": ref.scope,
            "required": ref.required,
            "snippet": snippet,
            "score": score + (3 if ref.required else 0),
        })

    contexts.sort(key=lambda item: item["score"], reverse=True)
    return contexts[:top_k]


def _best_matching_snippet(content: str, query_text: str, query_terms: list[str] | None = None) -> str:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
    if not paragraphs:
        return ""

    terms = query_terms or _tokenize(query_text)
    scored = sorted(
        ((_score_text(paragraph, query_text, terms), paragraph) for paragraph in paragraphs),
        key=lambda item: item[0],
        reverse=True,
    )
    best_score, best_paragraph = scored[0]
    if best_score <= 0:
        return ""
    return re.sub(r"\s+", " ", best_paragraph).strip()


def _score_text(text: str, query_text: str, query_terms: list[str]) -> float:
    text_lower = text.lower()
    score = 0.0
    for term in query_terms:
        if term in text_lower:
            score += 2 if len(term) > 4 else 1
    for phrase in re.split(r"[，,。:\n]", query_text):
        phrase = phrase.strip()
        if len(phrase) >= 4 and phrase in text_lower:
            score += 2
    return score


def _tokenize(text: str) -> list[str]:
    raw = re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9_./:-]{2,}", text.lower())
    tokens: list[str] = []
    for token in raw:
        expanded = [token]
        if re.fullmatch(r"[\u4e00-\u9fff]{3,}", token):
            expanded.extend(token[i:i + 2] for i in range(len(token) - 1))
            expanded.extend(token[i:i + 3] for i in range(len(token) - 2))
        for term in expanded:
            if term not in tokens:
                tokens.append(term)
    return tokens


def _reference_terms(path: str, scope: str) -> list[str]:
    base = path.split("/")[-1].replace(".md", "").replace("_", " ").replace("-", " ")
    return _tokenize(f"{base} {scope}")
