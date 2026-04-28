from __future__ import annotations

from langgraph.types import interrupt

from runtime.tool_calling import is_cancel_text, is_confirm_text
from workflow.state import State


def tool_confirm_node(state: State) -> State:
    """
    功能：在图节点中处理中高风险工具的确认或取消。
    输入：当前流程状态 `state`。
    输出：确认后写回决策结果；取消时写回取消回复；中断时等待用户恢复。
    """
    confirm_message = str(state.get("tool_confirmation_message", "") or "").strip()
    resume_text = str(interrupt({"confirm_message": confirm_message}) or "").strip()
    if is_cancel_text(resume_text):
        return {
            "used_tool": True,
            "waiting_confirmation": False,
            "tool_confirmation_decision": "cancelled",
            "tool_calls_payload": [],
            "needs_tool_confirmation": False,
            "tool_confirmation_message": "",
            "reply_text": "已取消刚才待执行的操作。",
            "tool_reply": "已取消刚才待执行的操作。",
        }
    if not is_confirm_text(resume_text):
        return {
            "used_tool": True,
            "waiting_confirmation": False,
            "tool_confirmation_decision": "cancelled",
            "tool_calls_payload": [],
            "needs_tool_confirmation": False,
            "tool_confirmation_message": "",
            "reply_text": "未检测到确认，已取消刚才待执行的操作。",
            "tool_reply": "未检测到确认，已取消刚才待执行的操作。",
        }
    return {
        "waiting_confirmation": False,
        "tool_confirmation_decision": "confirmed",
        "interrupt_message": "",
    }
