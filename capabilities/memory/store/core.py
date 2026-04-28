from __future__ import annotations

from typing import Any

from capabilities.memory.store.reminder_store import InMemoryReminderStore, ReminderStoreProtocol
from capabilities.memory.store.task_store import InMemoryTaskStore, TaskStoreProtocol
from pydantic import BaseModel, ConfigDict, Field


class FactStoreStack(BaseModel):
    """
    事实存储组合结构。
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    task_store: Any = Field(description="任务存储实例。")
    remind_store: Any = Field(description="提醒存储实例。")


def build_fact_store_stack() -> FactStoreStack:
    return FactStoreStack(task_store=InMemoryTaskStore(), remind_store=InMemoryReminderStore())
