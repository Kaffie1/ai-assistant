from __future__ import annotations

from datetime import datetime
from typing import Any

from capabilities.memory import load_long_term_context as load_long_term_memory_context
from capabilities.memory.long_term import LongTermMemoryService, decide_long_term_memory_write
from capabilities.memory.persona.context import build_persona_memory_context
from capabilities.memory.short_term import append_recent_conversation, build_recent_conversation
from capabilities.memory.store.core import FactStoreStack, build_fact_store_stack
from foundation.logger import get_backend_logger, setup_backend_logging
from foundation.time_utils import now_beijing
from models.model import get_chat_model
from runtime.command_service import build_tool_context, get_tool_registry

_FACT_STORE_STACK = build_fact_store_stack()
_LONG_TERM_MEMORY = LongTermMemoryService()
_LLM = get_chat_model()


def setup_workflow_services() -> None:
    """
    功能：初始化 workflow 运行所需的基础服务。
    输入：无。
    输出：无，副作用是配置日志系统。
    """
    setup_backend_logging()


def get_llm() -> Any | None:
    """
    功能：返回当前工作流共享的聊天模型实例。
    输入：无。
    输出：模型实例；不可用时返回 `None`。
    """
    return _LLM


def get_fact_store_stack() -> FactStoreStack:
    """
    功能：返回当前工作流共享的事实存储。
    输入：无。
    输出：任务与提醒存储栈。
    """
    return _FACT_STORE_STACK


def get_tool_registry_instance():
    """
    功能：返回工具注册表实例。
    输入：无。
    输出：工具注册表。
    """
    return get_tool_registry()


def get_tool_context():
    """
    功能：构造当前工作流使用的工具上下文。
    输入：无。
    输出：工具执行上下文。
    """
    return build_tool_context(_FACT_STORE_STACK)


def get_logger():
    """
    功能：返回 workflow 专用日志器。
    输入：无。
    输出：日志器实例。
    """
    return get_backend_logger("workflow_graph")


def response_mode() -> str:
    """
    功能：返回当前回复模式。
    输入：无。
    输出：`LLM` 或 `Local Fallback`。
    """
    return "LLM" if _LLM is not None else "Local Fallback"


def load_profile_context() -> str:
    """
    功能：读取画像记忆文本。
    输入：无。
    输出：画像上下文文本。
    """
    return build_persona_memory_context()


def load_recent_context() -> str:
    """
    功能：读取短期记忆文本。
    输入：无。
    输出：短期上下文文本。
    """
    return build_recent_conversation()


def load_long_term_context(user_text: str) -> str:
    """
    功能：按当前用户输入检索长期记忆上下文。
    输入：用户输入文本 `user_text`。
    输出：长期记忆上下文文本。
    """
    return load_long_term_memory_context(user_text)


def persist_turn(user_text: str, assistant_text: str) -> None:
    """
    功能：把一轮问答写入短期记忆，并按规则尝试写入长期记忆。
    输入：用户文本 `user_text`、助手文本 `assistant_text`。
    输出：无，副作用是追加写入短期记忆文件，并可能写入长期记忆。
    """
    short_term_text = f"用户: {user_text}\n助手: {assistant_text}"
    append_recent_conversation(short_term_text)
    decision = decide_long_term_memory_write(user_text)
    if not decision.should_write:
        return
    _LONG_TERM_MEMORY.remember(
        decision.text,
        kind=decision.kind,
        source="chat",
        importance=decision.importance,
        tags=decision.tags,
    )


def inject_due_task_reminder(reply_text: str) -> str | None:
    """
    功能：把已到期任务与已触发提醒补充到当前回复前面。
    输入：当前回复文本 `reply_text`。
    输出：拼接后的提醒文本；没有到期任务和提醒时返回 `None`。
    """
    due_task_items: list[tuple[str, str, str]] = []
    for task_fact in _FACT_STORE_STACK.task_store.list():
        task_id = str(getattr(task_fact, "id", "")).strip()
        if not task_id or str(getattr(task_fact, "status", "")).strip() != "active":
            continue
        due_raw = str(getattr(task_fact, "due_date", "")).strip()
        if not due_raw:
            continue
        try:
            due = datetime.fromisoformat(due_raw[:10]).date()
        except Exception:
            continue
        if due > now_beijing().date():
            continue
        content = str(getattr(task_fact, "content", "")).strip()
        due_task_items.append((task_id, due_raw[:10], content))

    due_reminder_items: list[tuple[str, str, str]] = []
    for remind_fact in _FACT_STORE_STACK.remind_store.list():
        remind_id = str(getattr(remind_fact, "id", "")).strip()
        if not remind_id or str(getattr(remind_fact, "status", "")).strip() != "active":
            continue
        remind_at_raw = str(getattr(remind_fact, "remind_at", "")).strip()
        if not remind_at_raw:
            continue
        try:
            remind_at = datetime.fromisoformat(remind_at_raw)
        except Exception:
            continue
        if remind_at > now_beijing():
            continue
        content = str(getattr(remind_fact, "content", "")).strip() or "到时间了。"
        when = str(getattr(remind_fact, "remind_text", "")).strip()
        due_reminder_items.append((remind_id, when, content))
        _FACT_STORE_STACK.remind_store.delete(remind_id)

    if not due_task_items and not due_reminder_items:
        return None

    lines: list[str] = []
    if due_reminder_items:
        lines.append("提醒：以下提醒已经到时间：")
        for remind_id, when, content in due_reminder_items[:3]:
            when_part = f" | 原设定={when}" if when else ""
            lines.append(f"- [{remind_id}] {content}{when_part}")
        if len(due_reminder_items) > 3:
            lines.append(f"- 还有 {len(due_reminder_items) - 3} 条提醒已触发。")

    if due_task_items:
        if lines:
            lines.append("")
        lines.append("提醒：以下任务已到期或今天截止：")
        for task_id, due_date, content in due_task_items[:3]:
            lines.append(f"- [{task_id}] due={due_date} | {content}")
        if len(due_task_items) > 3:
            lines.append(f"- 还有 {len(due_task_items) - 3} 条，你可以继续问我“还有哪些任务”。")

    reminder_text = "\n".join(lines)
    return f"{reminder_text}\n\n{reply_text}" if reply_text else reminder_text
