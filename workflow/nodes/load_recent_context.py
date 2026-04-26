from __future__ import annotations

from workflow.deps import AssistantGraphDeps
from workflow.state import State


def load_recent_context_node(state: State, deps: AssistantGraphDeps) -> State:
    _ = state
    return {"recent_ctx": deps.app_runtime.load_recent_context()}
