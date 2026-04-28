from __future__ import annotations

from workflow.nodes.services import load_long_term_context
from workflow.state import State


def retrieve_long_term_memory_node(state: State) -> State:
    """
    功能：根据本轮用户输入检索长期记忆上下文。
    输入：当前流程状态 `state`。
    输出：写回 `memory_ctx` 的状态增量。
    """
    existing_memory_ctx = str(state.get("memory_ctx", "") or "").strip()
    if existing_memory_ctx:
        return {"memory_ctx": existing_memory_ctx}
    user_text = str(state.get("user_text", "") or "")
    return {"memory_ctx": load_long_term_context(user_text)}
