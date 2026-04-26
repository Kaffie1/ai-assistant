from __future__ import annotations

from capabilities.memory.persona.context import load_profile_memory_context
from workflow.state import State


def load_profile_memory_context_node(state: State) -> State:
    _ = state
    return {"profile_ctx": deps.app_runtime.load_profile_memory_context()}
