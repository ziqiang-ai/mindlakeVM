from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field


# ── IR 四核 ──────────────────────────────────────────────────────────────────

class ReferenceEntry(BaseModel):
    path: str
    scope: str
    required: bool = False


class RCore(BaseModel):
    domain: str
    object_type: Literal["sop", "policy", "rfc", "checklist", "faq", "postmortem", "spec", "other"]
    semantic_space: str
    version: Optional[str] = None


class NCore(BaseModel):
    structure: Literal["step_by_step", "decision_tree", "checklist", "matrix", "faq", "mixed"]
    schema_: Optional[dict] = Field(None, alias="schema")
    constraints: list[str] = []
    references: list[ReferenceEntry] = []

    class Config:
        populate_by_name = True


class ECore(BaseModel):
    format: Literal["markdown", "json", "structured_text"]
    target_entropy: str
    hard_constraints: list[str] = []
    soft_constraints: list[str] = []
    meta_ignorance: list[str] = []


class DecisionPoint(BaseModel):
    condition: str
    if_true: str
    if_false: Optional[str] = None


class PathStep(BaseModel):
    id: str
    name: str
    description: str
    decision_points: list[DecisionPoint] = []
    tool_required: Optional[str] = None
    requires_evidence: bool = False


class TCore(BaseModel):
    path: list[PathStep]
    cot_steps: list[str] = []


class SemanticKernelIR(BaseModel):
    kernel_id: str
    version: str = "0.3"
    compiled_at: Optional[str] = None
    source_doc: Optional[str] = None
    compilation_strategy: Optional[Literal["minimal", "default", "detailed"]] = None
    r: RCore
    n: NCore
    e: ECore
    t: TCore


# ── Skill 包 ─────────────────────────────────────────────────────────────────

class SkillFile(BaseModel):
    path: str
    type: Literal["skill_main", "reference", "asset", "script", "test"]
    size_bytes: Optional[int] = None
    token_estimate: Optional[int] = None


class SkillPackage(BaseModel):
    skill_id: str
    skill_name: str
    description: Optional[str] = None
    files_tree: list[SkillFile] = []
    kernel_id: Optional[str] = None
    compiled_at: Optional[str] = None


# ── API 请求/响应 ─────────────────────────────────────────────────────────────

class CompileRequest(BaseModel):
    task_description: str
    document_content: Optional[str] = None
    document_id: Optional[str] = None
    strategy: Literal["minimal", "default", "detailed"] = "default"
    force_recompile: bool = False
    enable_probe: bool = False


class CompileResponse(BaseModel):
    kernel_id: str
    cache_hit: bool
    similarity: float = 0.0
    ir: SemanticKernelIR
    artifacts: SkillPackage


class SkillSummary(BaseModel):
    skill_id: str
    skill_name: str
    description: Optional[str] = None
    domain: str
    object_type: str
    compiled_at: Optional[str] = None


class SkillDetail(SkillSummary):
    ir: SemanticKernelIR
    files_tree: list[SkillFile] = []


class RunRequest(BaseModel):
    skill_id: str
    user_input: str


class Violation(BaseModel):
    constraint: str
    reason: str
    severity: Literal["hard", "soft"] = "hard"


class TraceStep(BaseModel):
    step_id: str
    status: Literal["pending", "running", "completed", "skipped", "blocked"]
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    decision_taken: Optional[str] = None
    notes: Optional[str] = None


class EvidenceItem(BaseModel):
    source_path: str
    excerpt: Optional[str] = None
    relevance: Optional[str] = None


class ValidationResult(BaseModel):
    passed: bool
    schema_valid: Optional[bool] = None
    evidence_sufficient: Optional[bool] = None
    stop_condition_met: Optional[bool] = None
    warnings: list[str] = []


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class RunResponse(BaseModel):
    output_text: str
    blocked: bool
    violations: list[Violation] = []
    trace: list[TraceStep] = []
    evidence: list[EvidenceItem] = []
    validation: ValidationResult
    usage: Optional[TokenUsage] = None


class BenchRequest(BaseModel):
    scenario_id: str
    baselines: list[Literal["vanilla", "rag", "mindlakevm"]] = ["vanilla", "rag", "mindlakevm"]


class BenchRow(BaseModel):
    baseline: Literal["vanilla", "rag", "mindlakevm"]
    success_rate: float
    token_cost: TokenUsage
    citation_rate: float
    guardrail_block_rate: float
    false_positive_rate: float = 0.0


class BenchSummary(BaseModel):
    token_savings_pct: float = 0.0
    success_rate_delta: float = 0.0
    guardrail_accuracy: float = 0.0
    highlight: str = ""


class BenchResponse(BaseModel):
    scenario_id: str
    results_table: list[BenchRow]
    report_summary: BenchSummary


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[dict] = None
