from __future__ import annotations

"""
memory 目录仅保留四类能力：
1. long_term：长期事实记忆与检索接口。
2. store：任务/提醒存储与时间解析。
3. short_term：最近对话短期记忆。
4. persona：画像/偏好记忆。
"""

from capabilities.memory.long_term import load_long_term_memory_context
from capabilities.memory.persona import append_persona_memory, build_persona_memory_context
from capabilities.memory.short_term import (
    append_recent_conversation,
    build_recent_conversation,
)


def load_profile_memory_context() -> str:
    return build_persona_memory_context()


def load_recent_context() -> str:
    return build_recent_conversation()


def load_long_term_context(user_text: str) -> str:
    return load_long_term_memory_context(user_text)


__all__ = [
    "append_persona_memory",
    "append_recent_conversation",
    "build_persona_memory_context",
    "build_recent_conversation",
    "load_long_term_context",
    "load_long_term_memory_context",
    "load_profile_memory_context",
    "load_recent_context",
]
