from __future__ import annotations

from context.schemas import MemoryContext
from capabilities.memory.persona.context import build_persona_memory_context
from capabilities.memory.short_term.recent_conversation import build_recent_conversation



def build_chat_context(
    *,
    user_text: str,
) -> MemoryContext:
    """
    拼接当前轮聊天上下文。
    """
    return MemoryContext(
        user_text=str(user_text or "").strip(),
        profile_memory_context=build_recent_conversation(),
        recent_memory_context=build_persona_memory_context(),
    )
