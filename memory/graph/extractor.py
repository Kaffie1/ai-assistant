from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

try:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover - optional dependency guard
    HumanMessage = None  # type: ignore[assignment]
    SystemMessage = None  # type: ignore[assignment]
    ChatOpenAI = None  # type: ignore[assignment]

from ..prompts import GRAPH_EXTRACT_SYSTEM_PROMPT


def _clamp01(value: float) -> float:
    """
    功能：将数值限制在 0~1 区间。
    输入：任意浮点数 `value`。
    输出：归一化后的浮点数。
    """
    return max(0.0, min(1.0, value))


@lru_cache(maxsize=1)
def _build_graph_llm() -> Any | None:
    """
    功能：创建图谱抽取专用 LLM 客户端。
    输入：无（读取 `LLM_API_KEY/LLM_BASE_URL/LLM_MODEL`）。
    输出：可调用 LLM 客户端；不可用返回 `None`。
    """
    if ChatOpenAI is None:
        return None

    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key:
        return None

    model = os.getenv("LLM_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    base_url = os.getenv("LLM_BASE_URL", "").strip() or None

    try:
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=0.0,
            max_tokens=500,
            streaming=False,
        )
    except Exception:
        return None


def _extract_json_object(raw_text: str) -> dict[str, Any] | None:
    """
    功能：从模型输出中提取 JSON 对象。
    输入：模型返回文本 `raw_text`。
    输出：JSON 对象字典；失败返回 `None`。
    """
    text = (raw_text or "").strip()
    if not text:
        return None

    if text.startswith("```"):
        text = text.replace("```json", "").replace("```JSON", "").replace("```", "").strip()

    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            if isinstance(obj, dict):
                return obj
        except Exception:
            return None
    return None


def _content_to_text(content: Any) -> str:
    """
    功能：把模型 content 统一转为字符串。
    输入：任意类型 content。
    输出：拼接后的文本字符串。
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                t = item.get("text")
                if isinstance(t, str):
                    parts.append(t)
        return "\n".join(parts)
    return str(content or "")


def _normalize_str_list(value: Any, max_items: int = 8) -> list[str]:
    """
    功能：将输入标准化为去重后的字符串列表。
    输入：任意值 `value` 与最大数量 `max_items`。
    输出：清洗后的字符串列表。
    """
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= max_items:
            break
    return out


def extract_memory_payload(text: str) -> tuple[list[str], list[str], float]:
    """
    功能：通过 LLM 抽取写入记忆图所需结构化载荷。
    输入：原始文本 `text`。
    输出：`(entities, topics, importance)`。
    """
    llm = _build_graph_llm()
    if llm is None:
        # 不再使用关键词机制；LLM 不可用时仅保留最低可写入默认值。
        return [], [], 0.5

    system_text = GRAPH_EXTRACT_SYSTEM_PROMPT

    messages = (
        [
            SystemMessage(content=system_text),
            HumanMessage(content=text),
        ]
        if HumanMessage is not None and SystemMessage is not None
        else f"{system_text}\n\n{text}"
    )
    try:
        resp = llm.invoke(messages, response_format={"type": "json_object"})
    except Exception:
        try:
            resp = llm.invoke(messages)
        except Exception:
            return [], [], 0.5

    payload = _extract_json_object(_content_to_text(getattr(resp, "content", "")))
    if payload is None:
        return [], [], 0.5

    entities = _normalize_str_list(payload.get("entities"), max_items=8)
    topics = _normalize_str_list(payload.get("topics"), max_items=6)

    importance_raw = payload.get("importance", 0.5)
    try:
        importance = _clamp01(float(importance_raw))
    except Exception:
        importance = 0.5

    return entities, topics, importance
