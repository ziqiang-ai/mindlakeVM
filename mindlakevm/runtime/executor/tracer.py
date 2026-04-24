"""
T 核执行 Trace 记录器
"""
from __future__ import annotations
from datetime import datetime, timezone
from models import TraceStep, PathStep


def make_trace(
    steps: list[PathStep],
    blocked_at: str | None = None,
    synthetic: bool = False,
) -> list[TraceStep]:
    """
    根据 T.path 步骤列表生成 TraceStep 记录。

    blocked_at: 若某个 step_id 被拦截，该步骤及其后的步骤标记为 blocked/pending。
    synthetic:  True 表示 trace 是在真实执行前预生成的（单次执行模式），
                非 agent 模式下步骤状态不反映实际执行顺序，仅供结构展示。
                agent_runner 实时更新 trace，不应传 synthetic=True。
    """
    trace: list[TraceStep] = []
    now = datetime.now(timezone.utc).isoformat()
    blocked = False
    note_prefix = "[synthetic] " if synthetic else ""

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
                notes=f"{note_prefix}guardrail 拦截",
            ))
            blocked = True
        else:
            trace.append(TraceStep(
                step_id=step.id,
                status="completed",
                started_at=now,
                completed_at=now,
                notes=note_prefix.strip() or None,
            ))

    return trace


def make_pending_trace(steps: list[PathStep]) -> list[TraceStep]:
    """为 agent 模式生成初始全 pending 的 trace，由 agent 运行时逐步更新。"""
    return [TraceStep(step_id=step.id, status="pending") for step in steps]


def mark_step_running(trace: list[TraceStep], step_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    for ts in trace:
        if ts.step_id == step_id:
            ts.status = "running"
            ts.started_at = now
            return


def mark_step_completed(trace: list[TraceStep], step_id: str, notes: str | None = None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    for ts in trace:
        if ts.step_id == step_id:
            ts.status = "completed"
            ts.completed_at = now
            if notes:
                ts.notes = notes
            return


def mark_step_skipped(trace: list[TraceStep], step_id: str) -> None:
    for ts in trace:
        if ts.step_id == step_id and ts.status == "pending":
            ts.status = "skipped"
            return


def update_trace_decision(trace: list[TraceStep], step_id: str, decision: str) -> bool:
    """返回 True 表示成功更新，False 表示未找到对应 step_id。"""
    for ts in trace:
        if ts.step_id == step_id:
            ts.decision_taken = decision
            return True
    return False
