from __future__ import annotations

from capabilities.memory.store.core import FactStoreStack

from .tool_registry import ToolContext, build_default_tool_registry


def get_tool_registry():
    """
    功能：获取当前最新的工具注册表。
    输入：无。
    输出：支持自动发现与热刷新的工具注册表。
    """
    return build_default_tool_registry()


def build_tool_context(fact_store_stack: FactStoreStack) -> ToolContext:
    """
    功能：构造工具执行上下文。
    输入：事实存储栈 `fact_store_stack`。
    输出：提供给工具 handler 使用的 `ToolContext`。
    """
    return ToolContext(
        task_store=fact_store_stack.task_store,
        remind_store=fact_store_stack.remind_store,
    )
