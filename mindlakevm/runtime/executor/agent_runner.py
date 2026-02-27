"""
Agent 执行器 — Layer 3：多轮 tool_use Agent 循环

替代原有 runner.py 的单次 LLM 调用模式。当 tool_use 模式启用时：
1. 将 IR 编译为 system prompt + Claude tool 定义
2. 运行 Agent 循环：Claude 可以调用 cite_reference / report_decision / 外部工具
3. 逐步记录真实 trace（而非假装全部完成）
4. 通过 tool_use 收集 evidence（而非启发式字符串匹配）

向后兼容：当 tool_use 不可用时，回退到原有 runner.run_skill()。
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from typing import Callable

from models import (
    SemanticKernelIR, RunRequest, RunResponse,
    EvidenceItem, TraceStep, TokenUsage, Violation,
)
from executor.guardrail import check_guardrails
from executor.verifier import verify
from compiler.llm import llm_chat


MAX_AGENT_TURNS = 10


# ── 内置 Tool 定义 ───────────────────────────────────────────────────────────

def _build_cite_reference_tool(ir: SemanticKernelIR) -> dict | None:
    """内置工具：让 Claude 显式引用 reference 文件作为证据。"""
    if not ir.n.references:
        return None
    ref_paths = [r.path for r in ir.n.references]
    return {
        "type": "function",
        "function": {
            "name": "cite_reference",
            "description": (
                "引用 Skill 参考资源中的文件作为回答的证据支撑。"
                "在回答中涉及具体规定、流程、条款时，必须调用此工具引用来源。"
                f"可用 references: {ref_paths}"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reference_path": {
                        "type": "string",
                        "enum": ref_paths,
                        "description": "要引用的文件路径"
                    },
                    "relevant_excerpt": {
                        "type": "string",
                        "description": "该文件中与当前问题相关的具体内容摘要"
                    },
                    "relevance": {
                        "type": "string",
                        "description": "为什么引用这个文件（一句话）"
                    }
                },
                "required": ["reference_path", "relevant_excerpt", "relevance"]
            }
        }
    }


def _build_report_decision_tool(ir: SemanticKernelIR) -> dict | None:
    """内置工具：让 Claude 在决策点处记录判断。"""
    has_decisions = any(s.decision_points for s in ir.t.path)
    if not has_decisions:
        return None
    return {
        "type": "function",
        "function": {
            "name": "report_decision",
            "description": "在执行路径的决策点处记录你的判断结果和依据。",
            "parameters": {
                "type": "object",
                "properties": {
                    "step_id": {
                        "type": "string",
                        "description": "当前步骤 ID"
                    },
                    "condition": {
                        "type": "string",
                        "description": "判断的条件"
                    },
                    "result": {
                        "type": "boolean",
                        "description": "条件是否成立"
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "判断依据（1-2句）"
                    }
                },
                "required": ["step_id", "condition", "result", "reasoning"]
            }
        }
    }


def _build_step_complete_tool(ir: SemanticKernelIR) -> dict:
    """内置工具：让 Claude 报告完成了哪个步骤。"""
    step_ids = [s.id for s in ir.t.path]
    return {
        "type": "function",
        "function": {
            "name": "step_complete",
            "description": (
                "报告已完成执行路径中的某个步骤。"
                "在执行每个步骤后调用此工具记录进度。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "step_id": {
                        "type": "string",
                        "enum": step_ids,
                        "description": "已完成的步骤 ID"
                    },
                    "summary": {
                        "type": "string",
                        "description": "该步骤的执行摘要（1-2句）"
                    }
                },
                "required": ["step_id", "summary"]
            }
        }
    }


# ── IR → Tools 编译 ──────────────────────────────────────────────────────────

def compile_ir_to_tools(
    ir: SemanticKernelIR,
    external_tools: dict[str, dict] | None = None,
) -> list[dict]:
    """将 IR 编译为 Claude Tool 定义列表。

    内置工具：
    - cite_reference: 引用 reference 文件
    - report_decision: 记录决策点判断
    - step_complete: 记录步骤完成

    外部工具：
    - 从 T.path[].tool_required 中提取
    - 需要在 external_tools dict 中注册定义
    """
    tools: list[dict] = []

    cite_tool = _build_cite_reference_tool(ir)
    if cite_tool:
        tools.append(cite_tool)

    decision_tool = _build_report_decision_tool(ir)
    if decision_tool:
        tools.append(decision_tool)

    tools.append(_build_step_complete_tool(ir))

    # 外部工具：从 T.path 中提取 tool_required
    ext = external_tools or {}
    seen = set()
    for step in ir.t.path:
        if step.tool_required and step.tool_required not in seen:
            seen.add(step.tool_required)
            if step.tool_required in ext:
                tools.append(ext[step.tool_required])
            else:
                # 未注册的外部工具 — 生成占位定义
                tools.append({
                    "type": "function",
                    "function": {
                        "name": step.tool_required,
                        "description": (
                            f"步骤 [{step.id}] {step.name} 需要的外部工具。"
                            f"当前未注册实现，调用将返回模拟结果。"
                        ),
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "传给工具的查询或参数"
                                }
                            }
                        }
                    }
                })

    return tools


# ── System Prompt 构建（增强版，引导 Claude 使用 tools）────────────────────────

def build_agent_system_prompt(ir: SemanticKernelIR) -> str:
    """构建 Agent 模式的 system prompt，引导 Claude 按步骤执行并使用工具。"""
    cot = "\n".join(f"- {s}" for s in ir.t.cot_steps) if ir.t.cot_steps else ""
    steps = "\n".join(
        f"{i+1}. [{s.id}] {s.name}：{s.description}"
        + (f"  （需要工具: {s.tool_required}）" if s.tool_required else "")
        for i, s in enumerate(ir.t.path)
    )
    constraints = "\n".join(f"- {c}" for c in ir.e.hard_constraints)
    soft = "\n".join(f"- {c}" for c in ir.e.soft_constraints)
    refs = "\n".join(
        f"- {r.path}（{r.scope}，{'必须引用' if r.required else '可选'}）"
        for r in ir.n.references
    )

    tool_instructions = """
## 工具使用规则
- 按执行路径逐步执行，每完成一个步骤调用 step_complete 记录进度
- 涉及具体规定、流程、条款时，调用 cite_reference 引用来源文件
- 遇到决策点时，调用 report_decision 记录判断结果和依据
- 如果某步骤需要外部工具，调用对应工具获取数据
- 所有工具调用完成后，输出最终回答"""

    return f"""你是一个专业的 AI 助手，挂载了以下 Skill，以 Agent 模式运行。

## Skill 定位
领域：{ir.r.domain} | 类型：{ir.r.object_type}
语义空间：{ir.r.semantic_space}

## 执行路径（必须按顺序执行）
{steps}

## 思维链引导
{cot}

## 硬约束（已通过预检，但执行过程中仍需遵守）
{constraints if constraints else "（无）"}

## 软约束（建议遵守）
{soft if soft else "（无）"}

## 参考资源
{refs if refs else "（无）"}

## 输出要求
- 格式：{ir.e.format}
- 目标：{ir.e.target_entropy}
{tool_instructions}

请开始按执行路径逐步处理用户的问题。"""


# ── Agent 循环 ───────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _handle_tool_call(
    tool_name: str,
    tool_input: dict,
    ir: SemanticKernelIR,
    trace: list[TraceStep],
    evidence: list[EvidenceItem],
    external_handlers: dict[str, Callable] | None = None,
) -> str:
    """处理单个 tool call，返回 tool result 文本。同时更新 trace 和 evidence。"""
    handlers = external_handlers or {}

    if tool_name == "cite_reference":
        ref_path = tool_input.get("reference_path", "")
        excerpt = tool_input.get("relevant_excerpt", "")
        relevance = tool_input.get("relevance", "")
        evidence.append(EvidenceItem(
            source_path=ref_path,
            excerpt=excerpt,
            relevance=relevance,
        ))
        return f"已引用 {ref_path}：{excerpt[:100]}"

    if tool_name == "report_decision":
        step_id = tool_input.get("step_id", "")
        condition = tool_input.get("condition", "")
        result = tool_input.get("result", False)
        reasoning = tool_input.get("reasoning", "")
        # 更新对应步骤的 trace
        for t in trace:
            if t.step_id == step_id:
                t.decision_taken = f"{'✓' if result else '✗'} {condition} — {reasoning}"
                break
        return f"决策记录完成：{condition} → {'成立' if result else '不成立'}"

    if tool_name == "step_complete":
        step_id = tool_input.get("step_id", "")
        summary = tool_input.get("summary", "")
        # 标记步骤完成
        found = False
        for t in trace:
            if t.step_id == step_id:
                t.status = "completed"
                t.completed_at = _now()
                t.notes = summary
                found = True
                break
        if not found:
            trace.append(TraceStep(
                step_id=step_id,
                status="completed",
                started_at=_now(),
                completed_at=_now(),
                notes=summary,
            ))
        return f"步骤 [{step_id}] 已完成：{summary[:100]}"

    # 外部工具
    if tool_name in handlers:
        try:
            result = handlers[tool_name](**tool_input)
            return str(result)
        except Exception as exc:
            return f"工具 {tool_name} 执行失败: {exc}"

    # 未注册的外部工具 — 返回模拟结果
    return f"[模拟] 工具 {tool_name} 未注册实现，参数: {json.dumps(tool_input, ensure_ascii=False)}"


def run_skill_agent(
    ir: SemanticKernelIR,
    req: RunRequest,
    external_tools: dict[str, dict] | None = None,
    external_handlers: dict[str, Callable] | None = None,
) -> RunResponse:
    """
    Agent 循环执行器。

    参数：
    - ir: 编译好的 SemanticKernel IR
    - req: 运行请求
    - external_tools: 外部工具的 Claude Tool 定义 dict（name → tool_def）
    - external_handlers: 外部工具的执行函数 dict（name → callable）

    流程：
    1. guardrail 预检（E 核）
    2. 编译 IR → system prompt + tools
    3. Agent 循环（多轮 tool_use）
    4. 返回结构化 RunResponse（含真实 trace + evidence + validation）
    """
    # Step 1: guardrail 预检
    violations = check_guardrails(ir.e, req.user_input)
    if violations:
        blocked_step = ir.t.path[0].id if ir.t.path else None
        from executor.tracer import make_trace
        trace = make_trace(ir.t.path, blocked_at=blocked_step)
        block_msg = _build_block_message(violations)
        validation = verify(ir, block_msg, [], len(trace))
        return RunResponse(
            output_text=block_msg, blocked=True, violations=violations,
            trace=trace, evidence=[], validation=validation, usage=TokenUsage(),
        )

    # Step 2: 编译 IR → tools + system prompt
    system_prompt = build_agent_system_prompt(ir)
    tools = compile_ir_to_tools(ir, external_tools)

    # Step 3: 初始化 trace（所有步骤标记为 pending）
    trace: list[TraceStep] = [
        TraceStep(step_id=s.id, status="pending", started_at=_now())
        for s in ir.t.path
    ]
    evidence: list[EvidenceItem] = []
    total_in, total_out = 0, 0

    # Step 4: Agent 循环
    messages: list[dict] = [{"role": "user", "content": req.user_input}]
    output_text = ""

    for turn in range(MAX_AGENT_TURNS):
        response = llm_chat(system_prompt, messages, tools=tools)
        usage = response.usage
        total_in += usage.prompt_tokens if usage else 0
        total_out += usage.completion_tokens if usage else 0

        msg = response.choices[0].message

        # 检查是否有 tool calls
        if msg.tool_calls:
            # 将 assistant message（含 tool_calls）加入对话历史
            messages.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in msg.tool_calls
                ],
            })

            # 处理每个 tool call
            for tc in msg.tool_calls:
                try:
                    tool_input = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    tool_input = {}

                result_text = _handle_tool_call(
                    tc.function.name, tool_input, ir, trace, evidence,
                    external_handlers,
                )

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_text,
                })

            # 如果 assistant 同时也有文本输出，累积
            if msg.content:
                output_text += msg.content

        else:
            # 没有 tool call — Agent 完成
            output_text += msg.content or ""
            break
    else:
        # 超过最大轮次
        output_text += "\n\n[警告：Agent 执行达到最大轮次限制]"

    # Step 5: 将未执行的步骤标记为 skipped
    for t in trace:
        if t.status == "pending":
            t.status = "skipped"

    # Step 6: 验证
    validation = verify(ir, output_text, evidence, len(trace))

    return RunResponse(
        output_text=output_text.strip(),
        blocked=False,
        violations=[],
        trace=trace,
        evidence=evidence,
        validation=validation,
        usage=TokenUsage(
            input_tokens=total_in,
            output_tokens=total_out,
            total_tokens=total_in + total_out,
        ),
    )


def _build_block_message(violations: list[Violation]) -> str:
    lines = ["⛔ 操作被拦截\n"]
    for v in violations:
        lines.append(f"**触发约束**：{v.constraint}")
        lines.append(f"**原因**：{v.reason}\n")
    lines.append("请满足上述约束条件后重试，或联系相关负责人获取授权。")
    return "\n".join(lines)
