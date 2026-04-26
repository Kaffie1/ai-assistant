from __future__ import annotations

from time import perf_counter

from langgraph.graph import END, START, StateGraph

from context.schemas import MemoryContext
from runtime.tool_runtime import ToolRuntime
from workflow.nodes import (
    fallback_reply_node,
    inject_due_task_reminder_node,
    load_profile_memory_context_node,
    load_recent_context_node,
    persist_turn_node,
    tool_call_node,
)
from workflow.state import State

def build_assistant_graph():
    """
    构建助手主流程 LangGraph。这里只负责问答流程编排。
    """
    graph = StateGraph(State)
    graph.add_node("load_profile_memory_context", lambda state: load_profile_memory_context_node(state, deps))
    graph.add_node("load_recent_context", lambda state: load_recent_context_node(state, deps))
    graph.add_node("tool_call", lambda state: tool_call_node(state, deps))
    graph.add_node("fallback_reply", lambda state: fallback_reply_node(state, deps))
    graph.add_node("inject_due_task_reminder", lambda state: inject_due_task_reminder_node(state, deps))
    graph.add_node("persist_turn", lambda state: persist_turn_node(state, deps))

    graph.add_edge(START, "load_profile_memory_context")
    graph.add_edge("load_profile_memory_context", "load_recent_context")
    graph.add_edge("load_recent_context", "tool_call")
    graph.add_conditional_edges(
        "tool_call",
        _route_after_tool_call,
        {"persist": "persist_turn", "fallback": "fallback_reply"},
    )
    graph.add_edge("fallback_reply", "inject_due_task_reminder")
    graph.add_edge("inject_due_task_reminder", "persist_turn")
    graph.add_edge("persist_turn", END)
    return graph.compile()


def run_assistant_graph(
    *,
    context: MemoryContext,
) -> State:
    app_runtime, tool_runtime, source = _require_assistant_runtime()
    initial_state: State = {
        "user_text": context.user_text,
        "mode": app_runtime.response_mode(),
        "turn_start": perf_counter(),
    }
    deps = AssistantGraphDeps(source=source, context=context, runtime=tool_runtime, app_runtime=app_runtime)
    graph = build_assistant_graph(deps)
    return graph.invoke(initial_state)
