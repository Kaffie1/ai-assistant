from __future__ import annotations

"""
功能：统一导出当前仍保留的任务/提醒存储能力。
输入：无。
输出：无，供上层通过 `capabilities.memory.store` 直接导入。
"""

from capabilities.memory.store.core import FactStoreStack, build_fact_store_stack
from capabilities.memory.store.reminder_store import InMemoryReminderStore, ReminderFact, ReminderStoreProtocol
from capabilities.memory.store.task_store import InMemoryTaskStore, TaskFact, TaskStoreProtocol
from capabilities.memory.store.time_parser import resolve_due_date, resolve_remind_at

__all__ = [
    "FactStoreStack",
    "InMemoryReminderStore",
    "InMemoryTaskStore",
    "ReminderFact",
    "ReminderStoreProtocol",
    "TaskFact",
    "TaskStoreProtocol",
    "build_fact_store_stack",
    "resolve_due_date",
    "resolve_remind_at",
]
