"""
Doc2Skill 编译管线入口
7 阶段：Ingest → Classify → Extract → Synthesize → Package → Validate → (Test)
"""
from __future__ import annotations
import json
import os
import re
from datetime import datetime, timezone
from typing import Optional

from models import (
    SemanticKernelIR, SkillPackage, SkillFile,
    RCore, NCore, ECore, TCore,
    PathStep, DecisionPoint, ReferenceEntry,
    CompileRequest,
)
from compiler.llm import llm_json

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


def compile_document(req: CompileRequest) -> tuple[SemanticKernelIR, SkillPackage]:
    content = req.document_content or ""

    # Phase 0: Ingest — normalise input
    doc_text = _ingest(content, req.task_description)

    # Phase 1: Classify — detect document type
    doc_type = _classify(doc_text, req.task_description)

    # Phase 2-3: Extract + Synthesize — LLM generates SemanticKernelIR
    ir = _extract_ir(doc_text, req.task_description, doc_type, req.strategy, req.enable_probe)

    # Phase 4: Package — build SkillPackage manifest
    package = _build_package(ir, doc_text)

    return ir, package


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
    files: list[SkillFile] = [
        SkillFile(path="SKILL.md", type="skill_main", token_estimate=_estimate_tokens(800))
    ]
    for ref in ir.n.references:
        files.append(SkillFile(
            path=ref.path,
            type="reference",
            token_estimate=_estimate_tokens(300),
        ))

    skill_id = re.sub(r"-v\d+$", "", ir.kernel_id)
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
