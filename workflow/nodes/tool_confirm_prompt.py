from __future__ import annotations

from workflow.state import State


def tool_confirm_prompt_node(state: State) -> State:
    """
    功能：写入工具确认提示文本，为后续确认中断节点准备状态。
    输入：当前流程状态 `state`。
    输出：带确认提示的状态更新。
    """
    confirm_message = str(state.get("tool_confirmation_message", "") or "").strip()
    reply_text = f"{confirm_message}\n\n回复“确认”执行，回复“取消”放弃。" if confirm_message else ""
    return {
        "used_tool": True,
        "waiting_confirmation": True,
        "interrupt_message": confirm_message,
        "reply_text": reply_text,
        "tool_reply": reply_text,
    }
