from __future__ import annotations

"""
memory 目录仅保留五类能力：
1. store：任务/提醒存储与时间解析。
2. short_term：最近对话短期记忆。
3. persona：画像/偏好记忆。
"""

from capabilities.memory.persona import append_persona_memory, build_persona_memory_context
from capabilities.memory.short_term import (
    append_recent_conversation,
    build_recent_conversation,
)


def load_profile_memory_context() -> str:
    return build_persona_memory_context()


def load_recent_context() -> str:
    return build_recent_conversation()


__all__ = [
    "append_persona_memory",
    "append_recent_conversation",
    "build_persona_memory_context",
    "build_recent_conversation",
    "load_profile_memory_context",
    "load_recent_context",
]
