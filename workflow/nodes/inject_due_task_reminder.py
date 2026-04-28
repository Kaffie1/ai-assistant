from __future__ import annotations

from workflow.nodes.services import inject_due_task_reminder
from workflow.state import State


def inject_due_task_reminder_node(state: State) -> State:
    """
    功能：在回复后补充到期任务提醒。
    输入：当前流程状态 `state`。
    输出：若存在到期任务则返回带提醒文本的状态增量，否则返回空字典。
    """
    reply_text = str(state.get("reply_text", "") or "")
    next_reply = inject_due_task_reminder(reply_text)
    return {"reply_text": next_reply} if next_reply is not None else {}
