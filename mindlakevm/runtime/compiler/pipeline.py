"""
Doc2Skill 编译管线入口
7 阶段：Ingest → Classify → Extract → Synthesize → Package → Validate → (Test)
"""
from __future__ import annotations
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from models import (
    SemanticKernelIR, SkillPackage, SkillFile,
    RCore, NCore, ECore, TCore,
    PathStep, DecisionPoint, ReferenceEntry,
    CompileRequest, IRValidationResult,
)
from compiler.llm import llm_json
from compiler.ir_validator import validate_ir

# ── tool_use 定义：generate_semantic_kernel_ir ────────────────────────────────

COMPILE_IR_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_semantic_kernel_ir",
        "description": "将企业文档编译为 SemanticKernelIR（RNET 四核中间表示）。必须调用此工具输出编译结果。",
        "parameters": {
            "type": "object",
            "properties": {
                "kernel_id": {
                    "type": "string",
                    "description": "kebab-case 唯一ID，如 ops-sev1-incident-response-v1"
                },
                "version": {"type": "string", "default": "0.3"},
                "source_doc": {"type": "string", "description": "文档来源标识"},
                "r": {
                    "type": "object",
                    "properties": {
                        "domain": {"type": "string", "description": "命名空间，如 ops.incident"},
                        "object_type": {
                            "type": "string",
                            "enum": ["sop", "policy", "rfc", "checklist", "faq", "postmortem", "spec", "other"]
                        },
                        "semantic_space": {"type": "string", "description": "一句话描述 Skill 面向哪类用户、处理哪类问题"}
                    },
                    "required": ["domain", "object_type", "semantic_space"]
                },
                "n": {
                    "type": "object",
                    "properties": {
                        "structure": {
                            "type": "string",
                            "enum": ["step_by_step", "decision_tree", "checklist", "matrix", "faq", "mixed"]
                        },
                        "constraints": {
                            "type": "array", "items": {"type": "string"},
                            "description": "输出必须包含的字段/信息"
                        },
                        "references": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "path": {"type": "string"},
                                    "scope": {"type": "string"},
                                    "required": {"type": "boolean"}
                                },
                                "required": ["path", "scope", "required"]
                            }
                        }
                    },
                    "required": ["structure"]
                },
                "e": {
                    "type": "object",
                    "properties": {
                        "format": {"type": "string", "enum": ["markdown", "json", "structured_text"]},
                        "target_entropy": {"type": "string", "description": "这个 Skill 要消除哪类不确定性"},
                        "hard_constraints": {
                            "type": "array", "items": {"type": "string"},
                            "description": "触发即拦截的红线"
                        },
                        "soft_constraints": {
                            "type": "array", "items": {"type": "string"},
                            "description": "建议遵守的规则"
                        },
                        "meta_ignorance": {
                            "type": "array", "items": {"type": "string"},
                            "description": "文档未涵盖的相关盲点"
                        }
                    },
                    "required": ["format", "target_entropy"]
                },
                "t": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string", "description": "kebab-case 步骤 ID"},
                                    "name": {"type": "string"},
                                    "description": {"type": "string"},
                                    "tool_required": {"type": "string", "description": "该步骤需要调用的外部工具名"},
                                    "requires_evidence": {"type": "boolean"},
                                    "decision_points": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "condition": {"type": "string"},
                                                "if_true": {"type": "string"},
                                                "if_false": {"type": "string"}
                                            },
                                            "required": ["condition", "if_true"]
                                        }
                                    }
                                },
                                "required": ["id", "name", "description"]
                            }
                        },
                        "cot_steps": {
                            "type": "array", "items": {"type": "string"},
                            "description": "引导 LLM 推理的思维链步骤"
                        }
                    },
                    "required": ["path"]
                }
            },
            "required": ["kernel_id", "r", "n", "e", "t"]
        }
    }
}


def _use_tool_mode() -> bool:
    """当使用 OpenRouter 或显式开启时，启用 tool_use 模式。"""
    base_url = os.environ.get("OPENAI_BASE_URL", "")
    return "openrouter" in base_url or os.environ.get("ENABLE_TOOL_USE", "") == "1"


def compile_document(
    req: CompileRequest,
) -> tuple[SemanticKernelIR, SkillPackage, IRValidationResult | None]:
    content = resolve_document_content(req)

    # Phase 0: Ingest — normalise input
    doc_text = _ingest(content, req.task_description)

    # Phase 1: Classify — detect document type
    doc_type = _classify(doc_text, req.task_description)

    # Phase 2-3: Extract + Synthesize — LLM generates SemanticKernelIR
    ir = _extract_ir(doc_text, req.task_description, doc_type, req.strategy, req.enable_probe)

    # Phase 4: Package — build SkillPackage manifest
    package = _build_package(ir, doc_text)

    # Phase 5: L1 IR Validation — 对照原文审查 IR 质量（可选）
    ir_validation: IRValidationResult | None = None
    if req.validate_ir:
        import os as _os
        _os.environ["ENABLE_IR_VALIDATION"] = "1"
    result = validate_ir(ir, doc_text)
    if not result.skipped:
        ir_validation = IRValidationResult(
            passed=result.passed,
            coverage_score=result.coverage_score,
            missing_steps=result.missing_steps,
            constraint_issues=result.constraint_issues,
            reviewer_notes=result.reviewer_notes,
            skipped=False,
        )

    return ir, package, ir_validation


def resolve_document_content(req: CompileRequest) -> str:
    """解析编译输入正文，支持直接正文或本地文件路径。"""
    if req.document_content and req.document_content.strip():
        return req.document_content.strip()

    if not req.document_id:
        return ""

    path = Path(req.document_id).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()

    if not path.exists() or not path.is_file():
        raise ValueError(f"document_id 指向的文件不存在: {path}")

    return path.read_text(encoding="utf-8").strip()


def materialize_compile_request(req: CompileRequest) -> CompileRequest:
    """返回一个正文已解析的请求，便于缓存和编译复用。"""
    return req.model_copy(update={
        "document_content": resolve_document_content(req),
    })


def compile_request_fingerprint(req: CompileRequest) -> str:
    """为编译请求生成稳定指纹，用于跳过重复编译。"""
    payload = json.dumps(
        {
            "task_description": req.task_description.strip(),
            "document_content": (req.document_content or "").strip(),
            "strategy": req.strategy,
            "enable_probe": req.enable_probe,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ── Phase 0: Ingest ───────────────────────────────────────────────────────────

def _ingest(content: str, task_description: str) -> str:
    if content.strip():
        return content.strip()
    return f"# {task_description}\n\n（文档内容未提供，仅凭任务描述编译）"


# ── Phase 1: Classify ─────────────────────────────────────────────────────────

_TYPE_KEYWORDS = {
    "sop":        ["sop", "应急", "响应", "故障", "操作流程", "step", "步骤", "处理流程"],
    "policy":     ["政策", "policy", "报销", "审批", "规定", "制度", "条例", "规范"],
    "rfc":        ["rfc", "设计规范", "技术规格", "接口", "schema", "配置规范", "api design"],
    "checklist":  ["checklist", "清单", "检查项", "核查"],
    "faq":        ["faq", "常见问题", "问答"],
    "postmortem": ["postmortem", "复盘", "事故", "root cause"],
}

def _classify(doc_text: str, task_description: str) -> str:
    combined = (doc_text + " " + task_description).lower()
    scores: dict[str, int] = {t: 0 for t in _TYPE_KEYWORDS}
    for doc_type, keywords in _TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in combined:
                scores[doc_type] += 1
    best = max(scores, key=lambda t: scores[t])
    return best if scores[best] > 0 else "other"


# ── Phase 2+3: Extract & Synthesize → SemanticKernelIR ───────────────────────

_STRATEGY_INSTRUCTIONS = {
    "minimal":  "生成最精简的 IR，只填写必填字段，约束和步骤尽量简洁。",
    "default":  "生成标准详细度的 IR，包含主要约束、步骤和引用文件。",
    "detailed": "生成最详尽的 IR，尽量穷举所有约束、决策点、引用资源和盲点。",
}

def _extract_ir(
    doc_text: str,
    task_description: str,
    doc_type: str,
    strategy: str,
    enable_probe: bool,
) -> SemanticKernelIR:
    probe_instruction = (
        "另外，请在 e.meta_ignorance 中列出文档未涵盖但用户可能会问到的相关领域（盲点探测）。"
        if enable_probe else ""
    )

    use_tools = _use_tool_mode()

    system_prompt = f"""你是一个认知编译器（Doc2Skill Compiler）。
你的任务是将企业文档编译为 SemanticKernelIR（R/N/E/T 四核中间表示）。

编译策略：{strategy}。{_STRATEGY_INSTRUCTIONS[strategy]}
{probe_instruction}

文档类型已识别为：{doc_type}。请据此设置 r.object_type。"""

    if use_tools:
        system_prompt += "\n\n请调用 generate_semantic_kernel_ir 工具输出编译结果。"
    else:
        system_prompt += f"""

必须严格返回合法的 JSON，不要包含任何 Markdown 代码块标记或额外文字。

JSON 结构如下（所有字段含义见注释）：
{{
  "kernel_id": "kebab-case 唯一ID，根据任务描述生成，如 ops-sev1-incident-response-v1",
  "version": "0.3",
  "compiled_at": "ISO8601时间戳",
  "source_doc": "文档来源标识",
  "compilation_strategy": "{strategy}",
  "r": {{
    "domain": "命名空间格式，如 ops.incident / finance.reimbursement / engineering.rfc",
    "object_type": "{doc_type}",
    "semantic_space": "一句话描述：这个 Skill 面向哪类用户，处理哪类问题"
  }},
  "n": {{
    "structure": "step_by_step | decision_tree | checklist | matrix | faq | mixed",
    "schema": null,
    "constraints": ["输出必须包含的字段/信息，如 必须包含受影响用户数量"],
    "references": [
      {{"path": "references/FILENAME.md", "scope": "用途说明", "required": true}}
    ]
  }},
  "e": {{
    "format": "markdown | json | structured_text",
    "target_entropy": "一句话：这个 Skill 要消除哪类不确定性",
    "hard_constraints": ["触发即拦截的红线，如 高峰期禁止扩缩容操作，除非 CTO 书面授权"],
    "soft_constraints": ["不强制但建议遵守的规则"],
    "meta_ignorance": []
  }},
  "t": {{
    "path": [
      {{
        "id": "kebab-case步骤ID",
        "name": "步骤名称",
        "description": "步骤说明",
        "decision_points": [
          {{"condition": "触发条件", "if_true": "真时动作", "if_false": "假时动作"}}
        ],
        "tool_required": "该步骤需要调用的外部工具名（可选）",
        "requires_evidence": true
      }}
    ],
    "cot_steps": ["引导 LLM 推理的思维链步骤1", "步骤2"]
  }}
}}"""

    user_msg = f"""任务描述：{task_description}

文档内容：
{doc_text[:6000]}"""

    tools = [COMPILE_IR_TOOL] if use_tools else None
    raw = llm_json(system_prompt, user_msg, tools=tools)
    raw["compiled_at"] = datetime.now(timezone.utc).isoformat()
    raw.setdefault("compilation_strategy", strategy)

    # normalise NCore: rename "schema" key if present
    if "n" in raw and "schema" in raw["n"]:
        raw["n"]["schema_"] = raw["n"].pop("schema")

    return SemanticKernelIR(**raw)


# ── Phase 4: Package ──────────────────────────────────────────────────────────

def _build_package(ir: SemanticKernelIR, doc_text: str) -> SkillPackage:
    skill_id = re.sub(r"-v\d+$", "", ir.kernel_id)
    files = _materialize_skill_bundle(skill_id, ir, doc_text)
    return SkillPackage(
        skill_id=skill_id,
        skill_name=ir.r.semantic_space[:64],
        description=ir.r.semantic_space,
        files_tree=files,
        kernel_id=ir.kernel_id,
        compiled_at=ir.compiled_at,
    )


def _estimate_tokens(chars: int) -> int:
    return max(1, chars // 4)


def _skills_dir() -> Path:
    return Path(os.environ.get("SKILLS_DIR", "./skills")).expanduser().resolve()


def _materialize_skill_bundle(
    skill_id: str,
    ir: SemanticKernelIR,
    doc_text: str,
) -> list[SkillFile]:
    root = _skills_dir() / skill_id
    root.mkdir(parents=True, exist_ok=True)

    files: list[SkillFile] = []
    skill_content = _render_skill_markdown(skill_id, ir)
    files.append(_write_bundle_file(root / "SKILL.md", "SKILL.md", "skill_main", skill_content))

    for ref in ir.n.references:
        ref_content = _render_reference_markdown(ref.path, ref.scope, ref.required, doc_text, ir)
        files.append(_write_bundle_file(root / ref.path, ref.path, "reference", ref_content))

    return files


def _write_bundle_file(path: Path, relative_path: str, file_type: str, content: str) -> SkillFile:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    size_bytes = path.stat().st_size
    return SkillFile(
        path=relative_path,
        type=file_type,
        size_bytes=size_bytes,
        token_estimate=_estimate_tokens(len(content)),
    )


def _render_skill_markdown(skill_id: str, ir: SemanticKernelIR) -> str:
    keywords = [ir.r.domain, ir.r.object_type]
    keywords.extend(step.name for step in ir.t.path[:3])
    keyword_line = "、".join(dict.fromkeys(filter(None, keywords)))

    steps = "\n".join(
        f"{idx + 1}. **{step.name}**：{step.description}"
        for idx, step in enumerate(ir.t.path)
    ) or "1. 按用户请求执行。"
    decisions = "\n".join(
        f"- `{step.id}`: {dp.condition} -> {dp.if_true}" + (f"；否则 {dp.if_false}" if dp.if_false else "")
        for step in ir.t.path
        for dp in step.decision_points
    ) or "- 无显式决策点"
    constraints = "\n".join(f"- {c}" for c in ir.n.constraints) or "- 无"
    hard = "\n".join(f"- {c}" for c in ir.e.hard_constraints) or "- 无"
    soft = "\n".join(f"- {c}" for c in ir.e.soft_constraints) or "- 无"
    refs = "\n".join(
        f"- [{Path(ref.path).stem.upper()}]({ref.path})：{ref.scope}"
        for ref in ir.n.references
    ) or "- 无"
    validation = "\n".join(f"- [ ] {c}" for c in ir.n.constraints[:5]) or "- [ ] 输出符合 Skill 要求"

    return f"""---
name: {skill_id}
description: |
  {ir.r.semantic_space}。触发关键词：{keyword_line}
metadata:
  org.owner: "mindlakevm"
  org.risk_tier: "{'high' if ir.e.hard_constraints else 'medium'}"
  org.semver: "{ir.version}.0"
  org.approval_status: "draft"
  compiled_at: "{ir.compiled_at or ''}"
---

## 角色与目标
- 领域：{ir.r.domain}
- 类型：{ir.r.object_type}
- 目标：{ir.e.target_entropy}

## 核心流程
{steps}

## 关键决策点
{decisions}

## 输出格式
- 格式：{ir.e.format}
- 必须包含：
{constraints}

## 验证清单（自检）
{validation}

## 边界与例外
### 硬约束
{hard}

### 软约束
{soft}

## 参考资料
{refs}
"""


def _render_reference_markdown(
    reference_path: str,
    scope: str,
    required: bool,
    doc_text: str,
    ir: SemanticKernelIR,
) -> str:
    title = Path(reference_path).stem.replace("_", " ").replace("-", " ").title()
    excerpts = _extract_reference_snippets(doc_text, scope, reference_path)
    excerpt_body = "\n\n".join(f"> {line}" for line in excerpts) if excerpts else "> 未从原文中命中高置信片段，以下为编译摘要。"

    fallback_points = [
        c for c in ir.n.constraints + ir.e.hard_constraints + ir.e.soft_constraints
        if any(term in c.lower() for term in _reference_terms(scope, reference_path))
    ][:6]
    if not fallback_points:
        fallback_points = [step.description for step in ir.t.path[:3]]
    fallback_body = "\n".join(f"- {point}" for point in fallback_points) or "- 无"

    return f"""# {title}

- scope: {scope}
- required: {"true" if required else "false"}

## Extracted Notes
{excerpt_body}

## Compilation Summary
{fallback_body}
"""


def _extract_reference_snippets(doc_text: str, scope: str, reference_path: str) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", doc_text) if p.strip()]
    terms = _reference_terms(scope, reference_path)
    scored: list[tuple[int, str]] = []
    for paragraph in paragraphs:
        para_lower = paragraph.lower()
        score = sum(2 if term in para_lower else 0 for term in terms)
        score += sum(1 for term in terms if term and any(ch.isdigit() for ch in term) and term in para_lower)
        if score > 0:
            scored.append((score, paragraph))

    scored.sort(key=lambda item: item[0], reverse=True)
    unique: list[str] = []
    for _, paragraph in scored:
        cleaned = re.sub(r"\s+", " ", paragraph).strip()
        if cleaned not in unique:
            unique.append(cleaned)
        if len(unique) >= 3:
            break
    return unique


def _reference_terms(scope: str, reference_path: str) -> list[str]:
    base = Path(reference_path).stem.replace("_", " ").replace("-", " ")
    terms = re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9]{2,}", f"{scope.lower()} {base.lower()}")
    return [term for term in terms if term]
