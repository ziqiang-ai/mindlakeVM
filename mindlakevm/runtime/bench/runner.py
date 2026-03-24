"""
Bench 评测入口 — 对应 POST /bench
"""
from __future__ import annotations
import os
from models import (
    BenchRequest, BenchResponse, BenchRow, BenchSummary,
    RunRequest, RunResponse, TokenUsage,
)
from bench.scenario_loader import load_scenario
from bench.judges import evaluate_case, JUDGE_REGISTRY, DEFAULT_JUDGES
from bench.baselines import run_vanilla, run_rag, run_mindlakevm
import store


def run_bench(req: BenchRequest) -> BenchResponse:
    scenario = load_scenario(req.scenario_id)
    test_cases: list[dict] = scenario.get("test_cases", [])
    scenario_type: str = scenario.get("type", "other")

    # 确定 judge 集合
    scenario_judge_defs: list[dict] = scenario.get("judges", [])
    if scenario_judge_defs:
        judge_ids = [j["id"] for j in scenario_judge_defs]
        judge_overrides = {j["id"]: j for j in scenario_judge_defs}
    else:
        judge_ids = DEFAULT_JUDGES.get(scenario_type, DEFAULT_JUDGES["other"])
        judge_overrides = {}

    # 确保 skill 已编译（用场景文档预编译）
    skill_id = scenario.get("skill_id", "")
    _ensure_skill_compiled(scenario, skill_id)

    rows: list[BenchRow] = []
    for baseline in req.baselines:
        row = _run_baseline(baseline, skill_id, test_cases, judge_ids, judge_overrides, scenario)
        rows.append(row)

    summary = _compute_summary(rows)
    return BenchResponse(
        scenario_id=req.scenario_id,
        results_table=rows,
        report_summary=summary,
    )


def _ensure_skill_compiled(scenario: dict, skill_id: str) -> None:
    """如果 skill 尚未编译，用场景文档自动触发编译"""
    if store.exists(skill_id):
        return
    from compiler.pipeline import compile_document
    from models import CompileRequest

    doc = scenario.get("document", {})
    content = doc.get("content_inline", "")
    document_id = None
    if not content:
        content_path = doc.get("content_path", "")
        if content_path:
            scenario_path = scenario.get("__scenario_path__", "")
            if scenario_path and not os.path.isabs(content_path):
                content_path = os.path.realpath(os.path.join(os.path.dirname(scenario_path), content_path))
            document_id = content_path
    req = CompileRequest(
        task_description=scenario.get("name", skill_id),
        document_content=content,
        document_id=document_id,
        strategy="default",
    )
    ir, package = compile_document(req)
    # 强制使用场景中声明的 skill_id
    package.skill_id = skill_id
    store.save(skill_id, ir, package)


def _run_baseline(
    baseline: str,
    skill_id: str,
    test_cases: list[dict],
    judge_ids: list[str],
    judge_overrides: dict,
    scenario: dict,
) -> BenchRow:
    passes = 0
    total_in = 0
    total_out = 0
    citation_hits = 0
    guardrail_hits = 0
    false_positive_hits = 0
    guardrail_applicable = 0
    no_fp_applicable = 0

    for tc in test_cases:
        user_input = tc.get("user_input", "")
        expects = tc.get("expects", {})

        if baseline == "vanilla":
            result = run_vanilla(user_input, scenario)
        elif baseline == "rag":
            result = run_rag(user_input, scenario)
        else:
            result = run_mindlakevm(skill_id, user_input)

        case_pass = evaluate_case(tc, result, judge_ids, judge_overrides)
        if case_pass:
            passes += 1

        usage = result.usage or TokenUsage()
        total_in += usage.input_tokens
        total_out += usage.output_tokens

        # citation rate
        if expects.get("evidence_paths"):
            cited = {e.source_path for e in result.evidence}
            expected = expects["evidence_paths"]
            if all(p in cited for p in expected):
                citation_hits += 1

        # guardrail_block_rate (应拦截 case)
        if expects.get("blocked") is True:
            guardrail_applicable += 1
            if result.blocked:
                guardrail_hits += 1

        # false_positive_rate (不应拦截 case)
        if expects.get("blocked") is False:
            no_fp_applicable += 1
            if result.blocked:
                false_positive_hits += 1

    n = len(test_cases) or 1
    citation_applicable = sum(1 for tc in test_cases if tc.get("expects", {}).get("evidence_paths"))

    return BenchRow(
        baseline=baseline,
        success_rate=round(passes / n, 3),
        token_cost=TokenUsage(
            input_tokens=total_in,
            output_tokens=total_out,
            total_tokens=total_in + total_out,
        ),
        citation_rate=round(citation_hits / max(citation_applicable, 1), 3),
        guardrail_block_rate=round(guardrail_hits / max(guardrail_applicable, 1), 3),
        false_positive_rate=round(false_positive_hits / max(no_fp_applicable, 1), 3),
    )


def _compute_summary(rows: list[BenchRow]) -> BenchSummary:
    vanilla = next((r for r in rows if r.baseline == "vanilla"), None)
    ml = next((r for r in rows if r.baseline == "mindlakevm"), None)

    if not vanilla or not ml:
        return BenchSummary()

    vanilla_tokens = vanilla.token_cost.total_tokens or 1
    savings = round((vanilla_tokens - ml.token_cost.total_tokens) / vanilla_tokens, 3)
    delta = round(ml.success_rate - vanilla.success_rate, 3)

    highlight = (
        f"相比 Vanilla 节省 {int(savings*100)}% token，"
        f"成功率从 {int(vanilla.success_rate*100)}% 提升至 {int(ml.success_rate*100)}%"
        f"（+{int(delta*100)}%），门禁准确率 {int(ml.guardrail_block_rate*100)}%"
    )

    return BenchSummary(
        token_savings_pct=max(savings, 0.0),
        success_rate_delta=delta,
        guardrail_accuracy=ml.guardrail_block_rate,
        highlight=highlight,
    )
