"""
E 核硬约束检查器
输入：hard_constraints 列表 + user_input
输出：触发的 Violation 列表

当 LLM 后端支持 tool_use（如 Claude via OpenRouter）时，
优先通过 tool_use 获取结构化输出，比纯 JSON prompt 更稳定。
"""
from __future__ import annotations
import os
from models import Violation, ECore
from compiler.llm import llm_json


# ── tool_use 定义：report_violations ──────────────────────────────────────────

GUARDRAIL_TOOL = {
    "type": "function",
    "function": {
        "name": "report_violations",
        "description": "报告用户请求触发了哪些硬约束（红线）。如果没有触发任何约束，violations 传空数组。",
        "parameters": {
            "type": "object",
            "properties": {
                "violations": {
                    "type": "array",
                    "description": "触发的约束列表，未触发则为空数组 []",
                    "items": {
                        "type": "object",
                        "properties": {
                            "constraint_index": {
                                "type": "integer",
                                "description": "触发的约束在列表中的 0-based 索引"
                            },
                            "reason": {
                                "type": "string",
                                "description": "触发原因说明，必须引用用户输入中的具体词语（1-2句）"
                            }
                        },
                        "required": ["constraint_index", "reason"]
                    }
                }
            },
            "required": ["violations"]
        }
    }
}


def _use_tool_mode() -> bool:
    """当使用 OpenRouter 或显式开启时，启用 tool_use 模式。"""
    base_url = os.environ.get("OPENAI_BASE_URL", "")
    return "openrouter" in base_url or os.environ.get("ENABLE_TOOL_USE", "") == "1"


def check_guardrails(e: ECore, user_input: str) -> list[Violation]:
    """
    用 LLM 判断 user_input 是否触发 e.hard_constraints 中的任意一条。
    返回所有触发的 Violation（可能多条）。

    当后端支持 tool_use 时，通过 report_violations tool 获取结构化输出；
    否则回退到 JSON prompt 模式。
    """
    if not e.hard_constraints:
        return []

    constraints_text = "\n".join(
        f"{i+1}. {c}" for i, c in enumerate(e.hard_constraints)
    )

    system_prompt = """你是一个合规审查员。
你的任务是判断用户的请求是否**明确触发**了以下硬约束（红线）。

规则：
- 只有用户的请求**明确**要求执行被禁止的操作，才标记为触发。
- 如果用户只是在评估、讨论、询问情况，或请求符合约束的操作，不应触发。
- 模糊情况下，优先不触发（减少误报）。
- 对每条触发的约束，解释为什么触发（1-2句），必须引用用户输入中的具体词语。

请调用 report_violations 工具报告结果。如果没有触发任何约束，传 violations: []。"""

    user_msg = f"""硬约束列表：
{constraints_text}

用户请求：
{user_input}"""

    tools = [GUARDRAIL_TOOL] if _use_tool_mode() else None

    if not tools:
        # 回退：JSON prompt 模式（兼容不支持 tool_use 的后端）
        system_prompt += """

必须返回合法 JSON，格式：
{
  "violations": [
    {"constraint_index": 0, "reason": "触发原因说明（引用用户原话）"}
  ]
}
如果没有触发任何约束，返回 {"violations": []}"""

    result = llm_json(system_prompt, user_msg, tools=tools)

    violations: list[Violation] = []
    for v in result.get("violations", []):
        idx = v.get("constraint_index", 0)
        if 0 <= idx < len(e.hard_constraints):
            violations.append(Violation(
                constraint=e.hard_constraints[idx],
                reason=v.get("reason", ""),
                severity="hard",
            ))
    return violations
