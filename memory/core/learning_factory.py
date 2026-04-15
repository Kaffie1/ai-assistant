from __future__ import annotations

from dataclasses import dataclass
import os

from .contracts import KnowledgeStoreProtocol, ProfileStoreProtocol, TaskStoreProtocol
from ..facts.sqlite_store import SQLiteKnowledgeStore, SQLiteProfileStore, SQLiteTaskStore
from ..facts.store import InMemoryKnowledgeStore, InMemoryProfileStore, InMemoryTaskStore
from ..learning.pipeline import LearningPipeline


@dataclass(slots=True)
class LearningStack:
    profile_store: ProfileStoreProtocol
    knowledge_store: KnowledgeStoreProtocol
    task_store: TaskStoreProtocol
    pipeline: LearningPipeline


def build_learning_stack() -> LearningStack:
    """
    功能：按配置创建学习流水线与事实存储后端。
    输入：无（读取事实存储相关环境变量）。
    输出：`LearningStack`（profile_store/knowledge_store/pipeline）。
    """
    backend = os.getenv("MAMGA_FACT_STORE_BACKEND", "sqlite").lower()
    db_path = os.getenv("MAMGA_FACT_DB_PATH", "./data/facts.db")

    if backend == "memory":
        profile_store = InMemoryProfileStore()
        knowledge_store = InMemoryKnowledgeStore()
        task_store = InMemoryTaskStore()
    else:
        try:
            profile_store = SQLiteProfileStore(db_path=db_path)
            knowledge_store = SQLiteKnowledgeStore(db_path=db_path)
            task_store = SQLiteTaskStore(db_path=db_path)
        except Exception:
            profile_store = InMemoryProfileStore()
            knowledge_store = InMemoryKnowledgeStore()
            task_store = InMemoryTaskStore()

    pipeline = LearningPipeline(
        profile_store=profile_store,
        knowledge_store=knowledge_store,
        task_store=task_store,
    )
    return LearningStack(
        profile_store=profile_store,
        knowledge_store=knowledge_store,
        task_store=task_store,
        pipeline=pipeline,
    )
