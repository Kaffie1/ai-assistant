from __future__ import annotations

from time import perf_counter

from runtime.tool_calling import prepare_tool_calls
from workflow.nodes.services import get_llm, get_tool_context, get_tool_registry_instance
from workflow.state import State


def tool_call_node(state: State) -> State:
    """
    功能：执行工具识别节点，准备工具调用或确认信息。
    输入：当前流程状态 `state`。
    输出：若命中工具则写回待执行工具调用或确认信息，否则仅写回未命中标记。
    """
    t_tool_start = perf_counter()
    tool_calls, need_confirm, confirm_message = prepare_tool_calls(
        user_text=str(state.get("user_text", "") or ""),
        registry=get_tool_registry_instance(),
        ctx=get_tool_context(),
        llm=get_llm(),
        profile_ctx=str(state.get("profile_ctx", "") or ""),
        memory_ctx=str(state.get("memory_ctx", "") or ""),
        recent_ctx=str(state.get("recent_ctx", "") or ""),
    )
    if not tool_calls:
        return {"used_tool": False, "tool_call_ms": (perf_counter() - t_tool_start) * 1000.0}
    return {
        "used_tool": False,
        "tool_calls_payload": [tool_call.model_dump() for tool_call in tool_calls],
        "needs_tool_confirmation": need_confirm,
        "tool_confirmation_message": confirm_message,
        "tool_confirmation_decision": "",
        "tool_call_ms": (perf_counter() - t_tool_start) * 1000.0,
    }
