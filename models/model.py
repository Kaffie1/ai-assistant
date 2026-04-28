from __future__ import annotations

from typing import Any

from foundation.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

try:
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover
    ChatOpenAI = None  # type: ignore[assignment]


def get_chat_model(
    *,
    temperature: float = 0.2,
    max_tokens: int = 1000,
) -> Any | None:
    """
    功能：构造默认聊天模型。
    输入：温度 `temperature`、最大输出长度 `max_tokens`。
    输出：可调用的聊天模型；不可用时返回 `None`。
    """
    if ChatOpenAI is None or not LLM_API_KEY:
        return None
    try:
        return ChatOpenAI(
            model=LLM_MODEL,
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=False,
            extra_body={"reasoning_split": True},
        )
    except Exception:
        return None
