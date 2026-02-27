"""
LLM 调用封装 — 统一出口，返回解析好的 dict
"""
from __future__ import annotations
import json
import os
import re

from openai import OpenAI

def _get_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    return OpenAI(api_key=api_key, base_url=base_url)


def llm_json(system_prompt: str, user_message: str,
             tools: list[dict] | None = None) -> dict:
    """调用 LLM，强制返回 JSON dict。
    当 tools 不为空时，优先从 tool_use 响应中提取结构化数据（适用于 Claude via OpenRouter）。
    失败时抛出 ValueError。
    """
    client = _get_client()
    model = os.environ.get("OPENAI_MODEL", "gpt-4o")
    extra: dict = {}
    if tools:
        extra["tools"] = tools
        extra["tool_choice"] = "auto"
    elif "openrouter" not in os.environ.get("OPENAI_BASE_URL", ""):
        extra["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(
        model=model,
        temperature=0,
        **extra,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )

    msg = response.choices[0].message

    # 优先从 tool_calls 中提取结构化数据
    if msg.tool_calls:
        try:
            return json.loads(msg.tool_calls[0].function.arguments)
        except (json.JSONDecodeError, AttributeError, IndexError):
            pass

    raw_text = msg.content or "{}"
    raw_text = _strip_markdown_fences(raw_text)

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        extracted = _extract_first_json(raw_text)
        if extracted is not None:
            return extracted
        raise ValueError(f"LLM 返回非法 JSON\n原文: {raw_text[:500]}")


def llm_text(system_prompt: str, user_message: str,
             tools: list[dict] | None = None) -> tuple[str, int, int]:
    """调用 LLM，返回 (output_text, input_tokens, output_tokens)。"""
    client = _get_client()
    model = os.environ.get("OPENAI_MODEL", "gpt-4o")
    extra: dict = {}
    if tools:
        extra["tools"] = tools
        extra["tool_choice"] = "auto"

    response = client.chat.completions.create(  # type: ignore[call-overload]
        model=model,
        temperature=0,
        **extra,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )

    text = response.choices[0].message.content or ""
    usage = response.usage
    in_tok = usage.prompt_tokens if usage else 0
    out_tok = usage.completion_tokens if usage else 0
    return text, in_tok, out_tok


def llm_chat(system_prompt: str, messages: list[dict],
             tools: list[dict] | None = None):
    """多轮对话调用，支持 tool_use Agent 循环。
    返回原始 response 对象，调用方自行处理 tool_calls。
    适用于 Agent Runner 的多轮 tool_use 循环。
    """
    client = _get_client()
    model = os.environ.get("OPENAI_MODEL", "gpt-4o")
    extra: dict = {}
    if tools:
        extra["tools"] = tools
        extra["tool_choice"] = "auto"

    all_messages = [{"role": "system", "content": system_prompt}] + messages

    return client.chat.completions.create(
        model=model,
        temperature=0,
        **extra,
        messages=all_messages,
    )


def _strip_markdown_fences(text: str) -> str:
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text.strip())
    text = re.sub(r"\n?```$", "", text.strip())
    return text.strip()


def _extract_first_json(text: str) -> dict | None:
    """从混合文本中提取第一个完整的 JSON 对象或数组。"""
    start = text.find("{")
    if start == -1:
        start = text.find("[")
    if start == -1:
        return None
    depth = 0
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    for i, ch in enumerate(text[start:], start):
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start: i + 1])
                except json.JSONDecodeError:
                    return None
    return None
