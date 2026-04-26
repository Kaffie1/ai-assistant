from __future__ import annotations

from typing import Any

from runtime.command_service import build_tool_context, get_tool_registry
from runtime.tool_calling import try_handle_tool_call


class ToolRuntime:
    """
    运行时执行层：封装工具注册表、工具上下文和工具调用流程。
    """

    def handle_tool_call(
        self,
        *,
        user_text: str,
        fact_store_stack: Any,
        llm: Any | None,
        profile_ctx: str,
        memory_ctx: str,
        recent_ctx: str,
    ) -> str | None:
        return try_handle_tool_call(
            user_text=user_text,
            registry=get_tool_registry(),
            ctx=build_tool_context(fact_store_stack),
            llm=llm,
            profile_ctx=profile_ctx,
            memory_ctx=memory_ctx,
            recent_ctx=recent_ctx,
        )
