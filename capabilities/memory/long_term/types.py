from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field


class MemoryNode(BaseModel):
    """
    长期记忆节点结构。
    """

    id: str = Field(default="", description="长期记忆节点 ID。")
    text: str = Field(default="", description="记忆文本内容。")
    kind: str = Field(default="fact", description="记忆类型，例如 preference / fact / project。")
    source: str = Field(default="chat", description="记忆来源。")
    ts: datetime = Field(description="记忆创建时间。")
    last_seen_ts: datetime | None = Field(default=None, description="最近命中时间。")
    importance: float = Field(default=0.5, description="重要性分数，范围 0~1。")
    hit_count: int = Field(default=0, description="被检索命中的次数。")
    tags: list[str] = Field(default_factory=list, description="标签列表。")
    status: str = Field(default="active", description="状态，支持 active / archived。")
    metadata: dict[str, Any] = Field(default_factory=dict, description="附加元数据。")


class VectorMatch(BaseModel):
    """
    向量召回结果。
    """

    node_id: str = Field(default="", description="命中的节点 ID。")
    score: float = Field(default=0.0, description="相似度分数。")


class RetrievalResult(BaseModel):
    """
    混合检索结果。
    """

    node: MemoryNode = Field(description="命中的记忆节点。")
    semantic_score: float = Field(default=0.0, description="语义相似度分。")
    lexical_score: float = Field(default=0.0, description="关键词重合分。")
    graph_score: float = Field(default=0.0, description="图关系分。")
    recency_score: float = Field(default=0.0, description="时效分。")
    final_score: float = Field(default=0.0, description="综合排序分。")


class LongTermStoreProtocol(Protocol):
    def upsert(self, node: MemoryNode) -> MemoryNode: ...
    def list_active(self) -> list[MemoryNode]: ...
    def get(self, node_id: str) -> MemoryNode | None: ...
    def touch(self, node_id: str, seen_at: datetime | None = None) -> MemoryNode | None: ...


class GraphStoreProtocol(Protocol):
    def get_node(self, node_id: str) -> MemoryNode | None: ...
    def expand(self, seed_ids: list[str], hops: int = 1) -> dict[str, float]: ...


class VectorStoreProtocol(Protocol):
    @property
    def mode(self) -> str: ...

    @property
    def provider_name(self) -> str: ...

    def upsert(self, node_id: str, text: str) -> None: ...
    def search(self, query: str, top_k: int = 20) -> list[VectorMatch]: ...
