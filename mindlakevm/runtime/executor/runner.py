"""
Skill 执行器：挂载 Skill → 检查 guardrail → 执行 → 收集 evidence → 验证
"""
from __future__ import annotations
import json
import os
import re
import tempfile
import uuid

from models import (
    SemanticKernelIR, RunRequest, RunResponse,
    EvidenceItem, TokenUsage, ToolExecutionResult,
    ToolInvocation, ToolPolicyDecision, ToolArtifact,
)
from executor.guardrail import check_guardrails
from executor.tool_adapter import invoke_cli_tool
from executor.tracer import make_trace, update_trace_decision
from executor.verifier import verify
from compiler.llm import llm_text
import store
import tool_registry


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

    # 单次执行模式：trace 在 LLM 运行前预生成，步骤状态为 synthetic（非真实执行顺序）
    # 如需真实步骤追踪，请使用 agent_runner.run_skill_agent
    trace = make_trace(ir.t.path, synthetic=True)
    tool_results, artifacts, policy_decisions, tool_evidence = _execute_bound_tools(ir, req, trace)
    denied = next((decision for decision in policy_decisions if not decision.allowed), None)
    if denied:
        block_msg = _build_policy_block_message(denied)
        validation = verify(ir, block_msg, tool_evidence, len(trace))
        return RunResponse(
            output_text=block_msg,
            blocked=True,
            violations=[],
            trace=trace,
            evidence=tool_evidence,
            validation=validation,
            usage=TokenUsage(),
            tool_results=tool_results,
            artifacts=artifacts,
            policy_decisions=policy_decisions,
        )

    # Step 2: 正常执行 — 构建 Skill prompt 并调用 LLM
    reference_contexts = _select_reference_context(ir, req.skill_id, req.user_input)
    skill_prompt = _build_skill_prompt(ir, reference_contexts, tool_results)
    output_text, in_tok, out_tok = llm_text(skill_prompt, req.user_input)

    # Step 3: 收集 evidence（从 references 中匹配相关片段）
    evidence = _collect_evidence(ir, req.skill_id, req.user_input, output_text, reference_contexts)
    evidence.extend(tool_evidence)

    # Step 4: 生成 trace
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
        tool_results=tool_results,
        artifacts=artifacts,
        policy_decisions=policy_decisions,
    )


def _build_skill_prompt(
    ir: SemanticKernelIR,
    reference_contexts: list[dict] | None = None,
    tool_results: list[ToolExecutionResult] | None = None,
) -> str:
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
    tool_context = "\n\n".join(
        f"### {result.tool_id}\n状态: {result.status}\n结果: {result.stdout_json if result.stdout_json else {'exit_code': result.exit_code}}\nArtifacts: {[a.path for a in result.artifacts]}"
        for result in (tool_results or [])
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

## 工具执行结果
{tool_context if tool_context else "（本次未执行外部工具）"}

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


def _build_policy_block_message(decision: ToolPolicyDecision) -> str:
    return "\n".join([
        "⛔ 工具执行被策略阻止",
        f"**工具**：{decision.tool_id}",
        f"**原因**：{decision.reason or '策略未放行'}",
        "请确认风险、开放副作用权限，或调整执行模式后重试。",
    ])


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


def _execute_bound_tools(
    ir: SemanticKernelIR,
    req: RunRequest,
    trace,
) -> tuple[list[ToolExecutionResult], list[ToolArtifact], list[ToolPolicyDecision], list[EvidenceItem]]:
    tool_results: list[ToolExecutionResult] = []
    artifacts: list[ToolArtifact] = []
    policy_decisions: list[ToolPolicyDecision] = []
    evidence: list[EvidenceItem] = []
    all_resolved_args: list[dict] = []

    if req.execution_mode == "answer_only":
        return tool_results, artifacts, policy_decisions, evidence

    # batch load to avoid repeated disk IO per step
    all_bindings = {(b.skill_id, b.step_id): b for b in tool_registry.list_bindings() if b.enabled}
    all_tools = {t.tool_id: t for t in tool_registry.list_tools()}

    for step in ir.t.path:
        binding = all_bindings.get((req.skill_id, step.id))
        if not binding:
            continue
        handle = all_tools.get(binding.tool_id)
        if not handle or handle.status != "active":
            continue

        decision = _evaluate_tool_policy(step, handle, req)
        policy_decisions.append(decision)
        _annotate_trace_with_policy(trace, step.id, handle.tool_id, decision)
        if not decision.allowed:
            break

        resolved_args = _resolve_binding_args(binding.arg_mapping, req)
        all_resolved_args.append(resolved_args)
        invocation = ToolInvocation(
            invocation_id=f"invoke_{uuid.uuid4().hex[:8]}",
            tool_id=handle.tool_id,
            process_id=req.skill_id,
            step_id=step.id,
            args=resolved_args,
            dry_run=req.execution_mode == "simulate",
            timeout_ms=handle.timeout_ms,
        )
        result = invoke_cli_tool(handle, invocation)
        tool_results.append(result)
        artifacts.extend(result.artifacts)
        _annotate_trace_with_tool_result(trace, step.id, handle.tool_id, result)
        if result.stdout_json:
            evidence.append(EvidenceItem(
                source_path=f"tool:{handle.tool_id}",
                source_type="tool_result",
                excerpt=json.dumps(result.stdout_json, ensure_ascii=False)[:500],
                relevance=f"工具 {handle.tool_id} 的结构化输出",
            ))

    _cleanup_temp_files(all_resolved_args)
    return tool_results, artifacts, policy_decisions, evidence


def _evaluate_tool_policy(step, handle, req: RunRequest) -> ToolPolicyDecision:
    requires_confirmation = step.requires_confirmation or handle.requires_confirmation
    side_effect = step.side_effect_level or handle.side_effect_level
    if side_effect != "read_only" and not req.allow_side_effects:
        return ToolPolicyDecision(
            tool_id=handle.tool_id,
            allowed=False,
            reason="当前请求未开放副作用执行权限（allow_side_effects=false）",
            requires_confirmation=requires_confirmation,
            risk_level="high",
        )
    if requires_confirmation and not req.confirm and req.execution_mode == "live":
        return ToolPolicyDecision(
            tool_id=handle.tool_id,
            allowed=False,
            reason="该工具步骤需要确认后才能在 live 模式执行",
            requires_confirmation=True,
            risk_level="medium" if side_effect == "write_optional" else "high",
        )
    return ToolPolicyDecision(
        tool_id=handle.tool_id,
        allowed=True,
        requires_confirmation=requires_confirmation,
        risk_level="low" if side_effect == "read_only" else "medium",
    )


def _resolve_binding_args(arg_mapping: dict[str, str], req: RunRequest) -> dict:
    runtime_output_path = _make_temp_output_path()
    resolved = {}
    for key, value in arg_mapping.items():
        resolved[key] = _resolve_binding_value(value, req, runtime_output_path)
    return resolved


def _resolve_binding_value(value, req: RunRequest, runtime_output_path: str):
    if not isinstance(value, str):
        return value
    if value == "$user_input":
        return req.user_input
    if value.startswith("$input."):
        return req.input_context.get(value.split(".", 1)[1])
    if value == "$runtime.temp_output_path":
        return runtime_output_path
    return value


def _annotate_trace_with_policy(trace, step_id: str, tool_id: str, decision: ToolPolicyDecision) -> None:
    for item in trace:
        if item.step_id == step_id:
            item.tool_id = tool_id
            if not decision.allowed:
                item.status = "blocked"
                item.notes = decision.reason
            return


def _annotate_trace_with_tool_result(trace, step_id: str, tool_id: str, result: ToolExecutionResult) -> None:
    for item in trace:
        if item.step_id == step_id:
            item.tool_id = tool_id
            item.tool_invocation_id = result.invocation_id
            item.artifacts = [artifact.path for artifact in result.artifacts]
            item.notes = result.stdout_json.get("summary") or item.notes
            break


def _make_temp_output_path() -> str:
    fd, path = tempfile.mkstemp(prefix="mindlakevm_tool_", suffix=".tmp")
    os.close(fd)
    return path


def _cleanup_temp_files(args_list: list[dict]) -> None:
    for args in args_list:
        for value in args.values():
            if isinstance(value, str) and value.startswith(tempfile.gettempdir()) and "mindlakevm_tool_" in value:
                try:
                    os.unlink(value)
                except OSError:
                    pass
