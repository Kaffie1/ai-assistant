from __future__ import annotations

from time import perf_counter

from workflow.deps import AssistantGraphDeps
from workflow.state import State


def persist_turn_node(state: State, deps: AssistantGraphDeps) -> State:
    deps.app_runtime.persist_turn(
        user_text=str(state.get("user_text", "") or ""),
        assistant_text=str(state.get("reply_text", "") or ""),
        turn_start=float(state.get("turn_start", perf_counter()) or perf_counter()),
        retrieve_ms=float(state.get("retrieve_ms", 0.0) or 0.0),
        reply_ms=float(state.get("reply_ms", 0.0) or 0.0),
        tool_call_ms=float(state.get("tool_call_ms", 0.0) or 0.0),
    )
    return {}
