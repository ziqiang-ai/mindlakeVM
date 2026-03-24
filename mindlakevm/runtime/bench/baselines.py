"""
三组 Baseline 实现 — 对应 specs/bench/baselines_v0.1.md
"""
from __future__ import annotations
import re
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
    rag_cfg = scenario.get("baselines", {}).get("rag", {})
    top_k = rag_cfg.get("rag_top_k", 3)
    chunks = _retrieve_chunks(doc_content, user_input, top_k=top_k)
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


def _retrieve_chunks(doc: str, user_input: str, top_k: int = 3) -> list[str]:
    chunks = _chunk_document(doc)
    if not chunks:
        return []

    query_terms = _tokenize(user_input)
    scored: list[tuple[float, int, str]] = []
    for idx, chunk in enumerate(chunks):
        score = _score_chunk(chunk, query_terms, user_input)
        scored.append((score, idx, chunk))

    scored.sort(key=lambda item: (-item[0], item[1]))
    selected = scored[:max(top_k, 1)]
    selected.sort(key=lambda item: item[1])
    return [chunk for _, _, chunk in selected]


def _chunk_document(doc: str) -> list[str]:
    """按标题和段落分块，保留局部上下文。"""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", doc) if p.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current_heading = ""
    buffer: list[str] = []

    for paragraph in paragraphs:
        is_heading = paragraph.startswith("#")
        if is_heading:
            if buffer:
                chunks.append("\n\n".join(buffer))
                buffer = []
            current_heading = paragraph
            continue

        if current_heading and not buffer:
            buffer.append(current_heading)
        buffer.append(paragraph)
        if len(buffer) >= 3:
            chunks.append("\n\n".join(buffer))
            buffer = [current_heading] if current_heading else []

    if buffer:
        chunks.append("\n\n".join(buffer))

    return [chunk for chunk in chunks if chunk.strip()]


def _score_chunk(chunk: str, query_terms: list[str], user_input: str) -> float:
    chunk_lower = chunk.lower()
    score = 0.0
    for term in query_terms:
        if term in chunk_lower:
            score += 3 if len(term) > 4 else 1.5
            if any(ch.isdigit() for ch in term):
                score += 1

    exact_phrases = [phrase.strip().lower() for phrase in re.split(r"[，,。:\n]", user_input) if len(phrase.strip()) >= 4]
    score += sum(2 for phrase in exact_phrases if phrase in chunk_lower)

    if chunk.startswith("#"):
        score += 0.5
    return score


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9_./:-]{2,}", text.lower())
    seen: list[str] = []
    for token in tokens:
        expanded = [token]
        if re.fullmatch(r"[\u4e00-\u9fff]{3,}", token):
            expanded.extend(token[i:i + 2] for i in range(len(token) - 1))
            expanded.extend(token[i:i + 3] for i in range(len(token) - 2))
        for term in expanded:
            if term not in seen:
                seen.append(term)
    return seen
