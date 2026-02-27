"""
三组 Baseline 实现 — 对应 specs/bench/baselines_v0.1.md
"""
from __future__ import annotations
from models import RunRequest, RunResponse, ValidationResult, TokenUsage, EvidenceItem
from executor.runner import run_skill
from compiler.llm import llm_text
import store


# ── Vanilla ───────────────────────────────────────────────────────────────────

_VANILLA_SYSTEM = (
    "You are a helpful assistant. Answer the user's question based on your knowledge. "
    "Be concise and accurate."
)


def run_vanilla(user_input: str, scenario: dict) -> RunResponse:
    output_text, in_tok, out_tok = llm_text(_VANILLA_SYSTEM, user_input)

    blocked = _heuristic_blocked(output_text)
    evidence = _heuristic_evidence(output_text, scenario)

    return RunResponse(
        output_text=output_text,
        blocked=blocked,
        violations=[],
        trace=[],
        evidence=evidence,
        validation=ValidationResult(passed=True),
        usage=TokenUsage(
            input_tokens=in_tok,
            output_tokens=out_tok,
            total_tokens=in_tok + out_tok,
        ),
    )


# ── RAG ───────────────────────────────────────────────────────────────────────

_RAG_SYSTEM = (
    "You are a helpful assistant. Use the provided context documents to answer the user's question. "
    "Always reference the specific document content when relevant. "
    "If the answer is not found in the context, say so clearly."
)


def run_rag(user_input: str, scenario: dict) -> RunResponse:
    doc_content = scenario.get("document", {}).get("content_inline", "")
    chunks = _chunk_document(doc_content, top_k=3)
    context = "\n\n".join(f"[Context Document {i+1}]\n{c}" for i, c in enumerate(chunks))

    full_user_msg = f"{context}\n\n---\n\nUser Question: {user_input}"
    output_text, in_tok, out_tok = llm_text(_RAG_SYSTEM, full_user_msg)

    blocked = _heuristic_blocked(output_text)
    evidence = _heuristic_evidence(output_text, scenario)

    return RunResponse(
        output_text=output_text,
        blocked=blocked,
        violations=[],
        trace=[],
        evidence=evidence,
        validation=ValidationResult(passed=True),
        usage=TokenUsage(
            input_tokens=in_tok,
            output_tokens=out_tok,
            total_tokens=in_tok + out_tok,
        ),
    )


# ── MindLakeOS ────────────────────────────────────────────────────────────────

def run_mindlakevm(skill_id: str, user_input: str) -> RunResponse:
    result = store.get(skill_id)
    if not result:
        return RunResponse(
            output_text=f"[ERROR] Skill '{skill_id}' 未编译",
            blocked=False,
            violations=[],
            trace=[],
            evidence=[],
            validation=ValidationResult(passed=False),
        )
    ir, _ = result
    return run_skill(ir, RunRequest(skill_id=skill_id, user_input=user_input))


# ── Helpers ───────────────────────────────────────────────────────────────────

_BLOCK_SIGNALS = [
    "无法执行", "不能执行", "拒绝", "不建议", "cannot", "should not",
    "not allowed", "prohibited", "forbidden", "不允许", "禁止",
]


def _heuristic_blocked(text: str) -> bool:
    text_lower = text.lower()
    return any(sig in text_lower for sig in _BLOCK_SIGNALS)


def _heuristic_evidence(text: str, scenario: dict) -> list[EvidenceItem]:
    """从输出文本中提取显式引用的 reference 文件名"""
    evidence: list[EvidenceItem] = []
    refs = scenario.get("document", {})
    text_lower = text.lower()
    # 扫描场景中 skill_id 对应的已知 references（从 store 中读取）
    skill_id = scenario.get("skill_id", "")
    stored = store.get(skill_id)
    if stored:
        ir, _ = stored
        for ref in ir.n.references:
            fname = ref.path.split("/")[-1].replace(".md", "").lower().replace("_", " ")
            keywords = [kw for kw in fname.split() if len(kw) > 3]
            if any(kw in text_lower for kw in keywords):
                evidence.append(EvidenceItem(
                    source_path=ref.path,
                    excerpt="（RAG/Vanilla 输出中检测到相关引用）",
                    relevance=ref.scope,
                ))
    return evidence


def _chunk_document(doc: str, top_k: int = 3) -> list[str]:
    """按段落粗切分，取前 top_k 块"""
    paragraphs = [p.strip() for p in doc.split("\n\n") if p.strip()]
    return paragraphs[:top_k]
