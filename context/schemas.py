from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class MemoryContext:
    """
    当前轮的最终上下文：
    - 输入问题
    - 画像记忆
    - 短期记忆
    """

    user_text: str
    profile_memory_context: str = ""
    recent_memory_context: str = ""
