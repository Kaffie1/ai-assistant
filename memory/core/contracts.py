from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from ..models.schemas import KnowledgeFact, MemoryEdge, MemoryNode, ProfileFact, TaskFact, VectorMatch


class GraphStoreProtocol(Protocol):
    def upsert_node(self, node: MemoryNode) -> None:
        """插入或更新记忆节点。"""
        ...

    def add_edge(self, edge: MemoryEdge) -> None:
        """新增记忆关系边。"""
        ...

    def get_node(self, node_id: str) -> MemoryNode | None:
        """按 ID 获取节点。"""
        ...

    def iter_nodes(self) -> Iterable[MemoryNode]:
        """遍历全部节点。"""
        ...

    def expand(self, seed_ids: list[str], hops: int = 1) -> dict[str, float]:
        """从种子节点扩展并返回图分映射。"""
        ...


class VectorStoreProtocol(Protocol):
    @property
    def mode(self) -> str:
        """返回后端模式标识。"""
        ...

    @property
    def provider_name(self) -> str:
        """返回 embedding 提供方名称。"""
        ...

    def upsert(self, node_id: str, text: str) -> None:
        """写入或更新文本向量。"""
        ...

    def search(self, query: str, top_k: int = 20) -> list[VectorMatch]:
        """执行 top-k 向量检索。"""
        ...


class ProfileStoreProtocol(Protocol):
    def upsert(self, fact: ProfileFact) -> ProfileFact:
        """写入或更新画像事实。"""
        ...

    def list(self) -> list[ProfileFact]:
        """列出用户的 active 画像事实。"""
        ...

    def delete(self, fact_id: str) -> bool:
        """软删除画像事实。"""
        ...

    def get(self, fact_id: str) -> ProfileFact | None:
        """按 ID 获取画像事实。"""
        ...

    def downgrade_and_mark(self, fact_id: str, factor: float = 0.3, status: str = "superseded") -> bool:
        """下调置信度并标记状态。"""
        ...

    def list_history(self, key: str) -> list[ProfileFact]:
        """查询某 key 的画像历史。"""
        ...


class KnowledgeStoreProtocol(Protocol):
    def upsert(self, fact: KnowledgeFact) -> KnowledgeFact:
        """写入或更新知识事实。"""
        ...

    def list(self) -> list[KnowledgeFact]:
        """列出用户的 active 知识事实。"""
        ...

    def delete(self, fact_id: str) -> bool:
        """软删除知识事实。"""
        ...

    def get(self, fact_id: str) -> KnowledgeFact | None:
        """按 ID 获取知识事实。"""
        ...

    def downgrade_and_mark(self, fact_id: str, factor: float = 0.3, status: str = "superseded") -> bool:
        """下调置信度并标记状态。"""
        ...

    def list_history(self, topic: str) -> list[KnowledgeFact]:
        """查询某 topic 的知识历史。"""
        ...


class TaskStoreProtocol(Protocol):
    def upsert(self, fact: TaskFact) -> TaskFact:
        """写入或更新任务事实。"""
        ...

    def list(self) -> list[TaskFact]:
        """列出 active 任务。"""
        ...

    def delete(self, fact_id: str) -> bool:
        """软删除任务。"""
        ...

    def get(self, fact_id: str) -> TaskFact | None:
        """按 ID 获取任务。"""
        ...

    def mark_done(self, fact_id: str) -> bool:
        """将任务标记为 done。"""
        ...

    def list_history(self) -> list[TaskFact]:
        """查询任务历史。"""
        ...
