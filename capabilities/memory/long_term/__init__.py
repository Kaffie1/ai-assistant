from __future__ import annotations

from capabilities.memory.long_term.service import LongTermMemoryService
from capabilities.memory.long_term.store import InMemoryLongTermStore
from capabilities.memory.long_term.types import (
    GraphStoreProtocol,
    LongTermStoreProtocol,
    MemoryNode,
    RetrievalResult,
    VectorMatch,
    VectorStoreProtocol,
)
from capabilities.memory.long_term.extractor import (
    LongTermMemoryDecision,
    LongTermMemoryRuleSet,
    decide_long_term_memory_write,
    load_long_term_memory_rules,
)

_LONG_TERM_MEMORY = LongTermMemoryService()


def load_long_term_memory_context(user_text: str) -> str:
    """
    功能：按当前用户输入读取长期记忆上下文。
    输入：用户输入文本 `user_text`。
    输出：长期记忆上下文文本。
    """
    return _LONG_TERM_MEMORY.retrieve_context(str(user_text or "").strip())


__all__ = [
    "GraphStoreProtocol",
    "InMemoryLongTermStore",
    "LongTermMemoryService",
    "LongTermMemoryDecision",
    "LongTermMemoryRuleSet",
    "LongTermStoreProtocol",
    "MemoryNode",
    "RetrievalResult",
    "VectorMatch",
    "VectorStoreProtocol",
    "decide_long_term_memory_write",
    "load_long_term_memory_context",
    "load_long_term_memory_rules",
]
