from __future__ import annotations

from time import perf_counter

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from context.schemas import MemoryContext
from workflow.nodes import (
    fallback_reply_node,
    inject_due_task_reminder_node,
    persist_turn_node,
    retrieve_long_term_memory_node,
    tool_call_node,
    tool_confirm_prompt_node,
    tool_confirm_node,
    tool_execute_node,
)
from workflow.nodes.services import load_profile_context, load_recent_context, response_mode, setup_workflow_services
from workflow.state import State

_GRAPH_CHECKPOINTER = MemorySaver()
_ASSISTANT_GRAPH = None


def _route_after_tool_call(state: State) -> str:
    """
    功能：根据本轮工具识别结果决定后续分支。
    输入：当前流程状态 `state`。
    输出：无工具返回 `fallback`，需确认返回 `confirm_prompt`，否则返回 `execute`。
    """
    payloads = list(state.get("tool_calls_payload", []) or [])
    if not payloads:
        return "fallback"
    if state.get("needs_tool_confirmation", False):
        return "confirm_prompt"
    return "execute"


def _route_after_tool_confirm(state: State) -> str:
    """
    功能：根据工具确认结果决定执行或结束。
    输入：当前流程状态 `state`。
    输出：确认后返回 `execute`，否则返回 `remind`。
    """
    return "execute" if state.get("tool_confirmation_decision", "") == "confirmed" else "remind"


def build_assistant_graph():
    """
    功能：构建助手主流程图。
    输入：无。
    输出：可直接执行的 LangGraph 实例。
    """
    graph = StateGraph(State)
    graph.add_node("retrieve_long_term_memory", retrieve_long_term_memory_node)
    graph.add_node("tool_call", tool_call_node)
    graph.add_node("tool_confirm_prompt", tool_confirm_prompt_node)
    graph.add_node("tool_confirm", tool_confirm_node)
    graph.add_node("tool_execute", tool_execute_node)
    graph.add_node("fallback_reply", fallback_reply_node)
    graph.add_node("inject_due_task_reminder", inject_due_task_reminder_node)
    graph.add_node("persist_turn", persist_turn_node)
    graph.add_edge(START, "retrieve_long_term_memory")
    graph.add_edge("retrieve_long_term_memory", "tool_call")
    graph.add_conditional_edges("tool_call", _route_after_tool_call, {"confirm_prompt": "tool_confirm_prompt", "execute": "tool_execute", "fallback": "fallback_reply"})
    graph.add_edge("tool_confirm_prompt", "tool_confirm")
    graph.add_conditional_edges("tool_confirm", _route_after_tool_confirm, {"execute": "tool_execute", "remind": "inject_due_task_reminder"})
    graph.add_edge("tool_execute", "inject_due_task_reminder")
    graph.add_edge("fallback_reply", "inject_due_task_reminder")
    graph.add_edge("inject_due_task_reminder", "persist_turn")
    graph.add_edge("persist_turn", END)
    return graph.compile(checkpointer=_GRAPH_CHECKPOINTER)


def _graph_instance():
    """
    功能：返回带 checkpointer 的单例 LangGraph 实例。
    输入：无。
    输出：可直接执行与恢复的 LangGraph 实例。
    """
    global _ASSISTANT_GRAPH
    if _ASSISTANT_GRAPH is None:
        _ASSISTANT_GRAPH = build_assistant_graph()
    return _ASSISTANT_GRAPH


def run_assistant_graph(*, context: MemoryContext, thread_id: str) -> State:
    """
    功能：执行一次完整的助手问答流程。
    输入：当前轮上下文 `context`、线程 ID `thread_id`。
    输出：包含最终回复和过程信息的状态对象。
    """
    setup_workflow_services()
    graph = _graph_instance()
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = graph.get_state(config)
    if getattr(snapshot, "interrupts", ()):
        result = graph.invoke(Command(resume=context.user_text), config=config)
    else:
        initial_state: State = {
            "user_text": context.user_text,
            "profile_ctx": context.profile_memory_context or load_profile_context(),
            "memory_ctx": context.long_term_memory_context or "",
            "recent_ctx": context.recent_memory_context or load_recent_context(),
            "mode": response_mode(),
            "turn_start": perf_counter(),
        }
        result = graph.invoke(initial_state, config=config)

    return State.model_validate(result)
