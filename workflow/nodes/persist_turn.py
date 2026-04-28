from __future__ import annotations

from workflow.nodes.services import persist_turn
from workflow.state import State


def persist_turn_node(state: State) -> State:
    """
    功能：把本轮对话写入短期记忆。
    输入：当前流程状态 `state`。
    输出：空状态增量，副作用是完成短期记忆持久化。
    """
    persist_turn(
        user_text=str(state.get("user_text", "") or ""),
        assistant_text=str(state.get("reply_text", "") or ""),
    )
    return {}
