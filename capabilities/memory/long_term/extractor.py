from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from foundation.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from prompts import GRAPH_EXTRACT_SYSTEM_PROMPT

try:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover
    HumanMessage = None  # type: ignore[assignment]
    SystemMessage = None  # type: ignore[assignment]
    ChatOpenAI = None  # type: ignore[assignment]


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


@lru_cache(maxsize=1)
def _build_graph_llm() -> Any | None:
    if ChatOpenAI is None or not LLM_API_KEY:
        return None
    try:
        return ChatOpenAI(
            model=LLM_MODEL,
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL or None,
            temperature=0.0,
            max_tokens=500,
            streaming=False,
        )
    except Exception:
        return None


def _extract_json_object(raw_text: str) -> dict[str, Any] | None:
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
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return str(content or "")


def _normalize_str_list(value: Any, max_items: int = 8) -> list[str]:
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
    llm = _build_graph_llm()
    if llm is None:
        return [], [], 0.5
    system_text = GRAPH_EXTRACT_SYSTEM_PROMPT
    messages = (
        [SystemMessage(content=system_text), HumanMessage(content=text)]
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
