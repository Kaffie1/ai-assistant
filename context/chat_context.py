from __future__ import annotations

from capabilities.memory import load_long_term_context
from capabilities.memory.persona.context import build_persona_memory_context
from capabilities.memory.short_term.recent_conversation import build_recent_conversation
from context.schemas import MemoryContext


def build_chat_context(
    *,
    user_text: str,
    source: str = "cli",
) -> MemoryContext:
    """
    拼接当前轮聊天上下文。
    """
    normalized_user_text = str(user_text or "").strip()
    return MemoryContext(
        user_text=normalized_user_text,
        source=source,
        profile_memory_context=build_persona_memory_context(),
        long_term_memory_context=load_long_term_context(normalized_user_text),
        recent_memory_context=build_recent_conversation(),
    )
