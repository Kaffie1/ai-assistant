from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from foundation.time_utils import now_beijing


@dataclass(slots=True)
class MemoryNode:
    id: str
    text: str
    ts: datetime = field(default_factory=now_beijing)
    entities: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    source: str = "dialog"
    importance: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MemoryEdge:
    src_id: str
    dst_id: str
    edge_type: str
    weight: float
    ts: datetime = field(default_factory=now_beijing)


@dataclass(slots=True)
class VectorMatch:
    node_id: str
    score: float


@dataclass(slots=True)
class RetrievalResult:
    node: MemoryNode
    semantic_score: float
    lexical_score: float
    graph_score: float
    recency_score: float
    final_score: float


class GraphStoreProtocol(Protocol):
    def upsert_node(self, node: MemoryNode) -> None: ...
    def add_edge(self, edge: MemoryEdge) -> None: ...
    def get_node(self, node_id: str) -> MemoryNode | None: ...
    def iter_nodes(self) -> list[MemoryNode]: ...
    def expand(self, seed_ids: list[str], hops: int = 1) -> dict[str, float]: ...


class VectorStoreProtocol(Protocol):
    @property
    def mode(self) -> str: ...

    @property
    def provider_name(self) -> str: ...

    def upsert(self, node_id: str, text: str) -> None: ...
    def search(self, query: str, top_k: int = 20) -> list[VectorMatch]: ...
