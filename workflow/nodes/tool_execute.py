from __future__ import annotations

from runtime.tool_calling import ToolCall, execute_tool_calls
from workflow.nodes.services import get_llm, get_tool_context, get_tool_registry_instance
from workflow.state import State


def tool_execute_node(state: State) -> State:
    """
    功能：执行已经准备好的工具调用并写回回复文本。
    输入：当前流程状态 `state`。
    输出：工具执行后的回复、命中标记与清理后的调用载荷。
    """
    payloads = list(state.get("tool_calls_payload", []) or [])
    tool_calls = [ToolCall.model_validate(payload) for payload in payloads if isinstance(payload, dict)]
    if not tool_calls:
        return {"used_tool": False}
    tool_reply = execute_tool_calls(
        tool_calls=tool_calls,
        registry=get_tool_registry_instance(),
        ctx=get_tool_context(),
        llm=get_llm(),
        user_text=str(state.get("user_text", "") or ""),
        profile_ctx=str(state.get("profile_ctx", "") or ""),
        memory_ctx=str(state.get("memory_ctx", "") or ""),
        recent_ctx=str(state.get("recent_ctx", "") or ""),
    )
    return {
        "used_tool": True,
        "tool_reply": tool_reply,
        "reply_text": tool_reply,
        "tool_calls_payload": [],
        "needs_tool_confirmation": False,
        "tool_confirmation_message": "",
        "tool_confirmation_decision": "",
    }
