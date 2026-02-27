"""
T 核执行 Trace 记录器
"""
from __future__ import annotations
from datetime import datetime, timezone
from models import TraceStep, PathStep


def make_trace(steps: list[PathStep], blocked_at: str | None = None) -> list[TraceStep]:
    """
    根据 T.path 步骤列表生成 TraceStep 记录。
    blocked_at: 若某个 step_id 被拦截，该步骤及其后的步骤标记为 blocked/pending。
    """
    trace: list[TraceStep] = []
    now = datetime.now(timezone.utc).isoformat()
    blocked = False

    for step in steps:
        if blocked:
            trace.append(TraceStep(step_id=step.id, status="pending"))
            continue

        if blocked_at == step.id:
            trace.append(TraceStep(
                step_id=step.id,
                status="blocked",
                started_at=now,
                completed_at=now,
            ))
            blocked = True
        else:
            trace.append(TraceStep(
                step_id=step.id,
                status="completed",
                started_at=now,
                completed_at=now,
            ))

    return trace


def update_trace_decision(trace: list[TraceStep], step_id: str, decision: str) -> None:
    for ts in trace:
        if ts.step_id == step_id:
            ts.decision_taken = decision
            return
