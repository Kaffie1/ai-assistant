from __future__ import annotations

from workflow.deps import AssistantGraphDeps
from workflow.state import State


def inject_due_task_reminder_node(state: State, deps: AssistantGraphDeps) -> State:
    reply_text = str(state.get("reply_text", "") or "")
    next_reply = deps.app_runtime.inject_due_task_reminder(reply_text)
    return {"reply_text": next_reply} if next_reply is not None else {}
