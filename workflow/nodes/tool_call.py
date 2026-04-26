from __future__ import annotations

from time import perf_counter

from workflow.deps import AssistantGraphDeps
from workflow.state import State


def tool_call_node(state: State, deps: AssistantGraphDeps) -> State:
    t_tool_start = perf_counter()
    tool_reply = deps.runtime.handle_tool_call(
        user_text=str(state.get("user_text", "") or ""),
        fact_store_stack=deps.app_runtime.fact_store_stack,
        llm=deps.app_runtime.llm,
        profile_ctx=str(state.get("profile_ctx", "") or ""),
        memory_ctx=str(state.get("memory_ctx", "") or ""),
        recent_ctx=str(state.get("recent_ctx", "") or ""),
    )
    if tool_reply is None:
        return {"used_tool": False, "tool_call_ms": (perf_counter() - t_tool_start) * 1000.0}
    return {
        "used_tool": True,
        "tool_reply": tool_reply,
        "reply_text": tool_reply,
        "tool_call_ms": (perf_counter() - t_tool_start) * 1000.0,
    }
