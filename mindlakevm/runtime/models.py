from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field


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
    constraints: list[str] = Field(default_factory=list)
    references: list[ReferenceEntry] = Field(default_factory=list)
    model_config = ConfigDict(populate_by_name=True)


class ECore(BaseModel):
    format: Literal["markdown", "json", "structured_text"]
    target_entropy: str
    hard_constraints: list[str] = Field(default_factory=list)
    soft_constraints: list[str] = Field(default_factory=list)
    meta_ignorance: list[str] = Field(default_factory=list)


class DecisionPoint(BaseModel):
    condition: str
    if_true: str
    if_false: Optional[str] = None


class PathStep(BaseModel):
    id: str
    name: str
    description: str
    decision_points: list[DecisionPoint] = Field(default_factory=list)
    tool_required: Optional[str] = None
    tool_args_schema: Optional[dict] = None
    side_effect_level: Optional[Literal["read_only", "write_optional", "write_required"]] = None
    requires_confirmation: bool = False
    tool_binding_id: Optional[str] = None
    requires_evidence: bool = False


class TCore(BaseModel):
    path: list[PathStep]
    cot_steps: list[str] = Field(default_factory=list)


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
    files_tree: list[SkillFile] = Field(default_factory=list)
    kernel_id: Optional[str] = None
    compiled_at: Optional[str] = None


# ── Tool 接入 ────────────────────────────────────────────────────────────────

class RetryPolicy(BaseModel):
    max_retries: int = 0
    retryable_errors: list[str] = Field(default_factory=list)


class ToolHandle(BaseModel):
    tool_id: str
    name: str
    version: str = "0.1.0"
    provider: str = "cli-anything"
    kind: Literal["cli"] = "cli"
    command: str
    args_schema: dict = Field(default_factory=lambda: {"type": "object", "properties": {}})
    output_schema: dict = Field(default_factory=lambda: {"type": "object"})
    capabilities: list[str] = Field(default_factory=list)
    side_effect_level: Literal["read_only", "write_optional", "write_required"] = "read_only"
    requires_confirmation: bool = False
    supports_json: bool = True
    supports_repl: bool = False
    timeout_ms: int = 30000
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    status: Literal["active", "inactive"] = "active"
    skill_path: Optional[str] = None
    registry_metadata: dict = Field(default_factory=dict)


class ToolBinding(BaseModel):
    binding_id: str
    skill_id: str
    step_id: str
    tool_id: str
    arg_mapping: dict[str, str] = Field(default_factory=dict)
    result_mapping: dict[str, str] = Field(default_factory=dict)
    confirmation_policy: Literal["inherit_tool", "always", "never"] = "inherit_tool"
    enabled: bool = True


class ToolArtifact(BaseModel):
    path: str
    type: str = "artifact"


class ToolExecutionUsage(BaseModel):
    wall_time_ms: int = 0


class ToolExecutionResult(BaseModel):
    invocation_id: str
    tool_id: str
    status: Literal["success", "error"] = "success"
    exit_code: int = 0
    stdout_json: dict = Field(default_factory=dict)
    stderr_text: str = ""
    artifacts: list[ToolArtifact] = Field(default_factory=list)
    usage: ToolExecutionUsage = Field(default_factory=ToolExecutionUsage)


class ToolPolicyDecision(BaseModel):
    tool_id: str
    allowed: bool
    reason: Optional[str] = None
    requires_confirmation: bool = False
    risk_level: Literal["low", "medium", "high"] = "low"


class ToolRegistrySyncRequest(BaseModel):
    registry_path: str
    overwrite: bool = False


class ToolRegistrySyncResponse(BaseModel):
    snapshot_id: str
    imported: int
    skipped: int


class ToolProbeResult(BaseModel):
    tool_id: str
    ok: bool
    version: Optional[str] = None
    supports_json: bool = False
    supports_repl: bool = False
    message: Optional[str] = None


class ToolInvocation(BaseModel):
    invocation_id: str
    tool_id: str
    process_id: str
    step_id: str
    args: dict = Field(default_factory=dict)
    dry_run: bool = False
    timeout_ms: int = 30000


# ── API 请求/响应 ─────────────────────────────────────────────────────────────

class IRValidationResult(BaseModel):
    passed: bool
    coverage_score: float = 1.0
    missing_steps: list[str] = Field(default_factory=list)
    constraint_issues: list[str] = Field(default_factory=list)
    reviewer_notes: str = ""
    skipped: bool = False


class CompileRequest(BaseModel):
    task_description: str
    document_content: Optional[str] = None
    document_id: Optional[str] = None
    strategy: Literal["minimal", "default", "detailed"] = "default"
    force_recompile: bool = False
    enable_probe: bool = False
    validate_ir: bool = False    # True 强制触发 L1 IR 验证（覆盖环境变量）


class CompileResponse(BaseModel):
    kernel_id: str
    cache_hit: bool
    similarity: float = 0.0
    ir: SemanticKernelIR
    artifacts: SkillPackage
    ir_validation: Optional[IRValidationResult] = None


class SkillSummary(BaseModel):
    skill_id: str
    skill_name: str
    description: Optional[str] = None
    domain: str
    object_type: str
    compiled_at: Optional[str] = None


class SkillDetail(SkillSummary):
    ir: SemanticKernelIR
    files_tree: list[SkillFile] = Field(default_factory=list)


class RunRequest(BaseModel):
    skill_id: str
    user_input: str
    execution_mode: Literal["answer_only", "simulate", "live"] = "answer_only"
    allow_side_effects: bool = False
    confirm: bool = False
    input_context: dict = Field(default_factory=dict)


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
    tool_id: Optional[str] = None
    tool_invocation_id: Optional[str] = None
    artifacts: list[str] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    source_path: str
    source_type: Literal["reference", "tool_result"] = "reference"
    excerpt: Optional[str] = None
    relevance: Optional[str] = None


class ValidationResult(BaseModel):
    passed: bool
    schema_valid: Optional[bool] = None
    evidence_sufficient: Optional[bool] = None
    stop_condition_met: Optional[bool] = None
    warnings: list[str] = Field(default_factory=list)


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class RunResponse(BaseModel):
    output_text: str
    blocked: bool
    violations: list[Violation] = Field(default_factory=list)
    trace: list[TraceStep] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    validation: ValidationResult
    usage: Optional[TokenUsage] = None
    tool_results: list[ToolExecutionResult] = Field(default_factory=list)
    artifacts: list[ToolArtifact] = Field(default_factory=list)
    policy_decisions: list[ToolPolicyDecision] = Field(default_factory=list)


class BenchRequest(BaseModel):
    scenario_id: str
    baselines: list[Literal["vanilla", "rag", "mindlakevm"]] = Field(
        default_factory=lambda: ["vanilla", "rag", "mindlakevm"]
    )


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
