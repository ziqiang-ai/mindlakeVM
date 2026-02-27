"""
E 核硬约束检查器
输入：hard_constraints 列表 + user_input
输出：触发的 Violation 列表
"""
from __future__ import annotations
from models import Violation, ECore
from compiler.llm import llm_json


def check_guardrails(e: ECore, user_input: str) -> list[Violation]:
    """
    用 LLM 判断 user_input 是否触发 e.hard_constraints 中的任意一条。
    返回所有触发的 Violation（可能多条）。
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

必须返回合法 JSON，格式：
{
  "violations": [
    {
      "constraint_index": 0,
      "reason": "触发原因说明（引用用户原话）"
    }
  ]
}
如果没有触发任何约束，返回 {"violations": []}"""

    user_msg = f"""硬约束列表：
{constraints_text}

用户请求：
{user_input}"""

    result = llm_json(system_prompt, user_msg)

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
