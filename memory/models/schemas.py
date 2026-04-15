from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    """返回 UTC 当前时间，供数据结构默认时间戳使用。"""
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class MemoryNode:
    id: str
    text: str
    ts: datetime = field(default_factory=utc_now)
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
    ts: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class RetrievalResult:
    node: MemoryNode
    semantic_score: float
    lexical_score: float
    graph_score: float
    recency_score: float
    final_score: float


@dataclass(slots=True)
class VectorMatch:
    node_id: str
    score: float


@dataclass(slots=True)
class ProfileFact:
    id: str
    key: str
    value: str
    confidence: float
    source: str
    ts: datetime = field(default_factory=utc_now)
    status: str = "active"


@dataclass(slots=True)
class KnowledgeFact:
    id: str
    topic: str
    statement: str
    confidence: float
    source: str
    evidence: list[str] = field(default_factory=list)
    ts: datetime = field(default_factory=utc_now)
    status: str = "active"
    version: int = 1


@dataclass(slots=True)
class TaskFact:
    id: str
    content: str
    due_date: str = ""
    confidence: float = 0.6
    source: str = "dialog"
    evidence: list[str] = field(default_factory=list)
    ts: datetime = field(default_factory=utc_now)
    status: str = "active"  # active | done | deleted | superseded
    version: int = 1


@dataclass(slots=True)
class CandidateFact:
    fact_type: str  # profile | knowledge | task
    key: str = ""
    value: str = ""
    topic: str = ""
    statement: str = ""
    content: str = ""
    due_date: str = ""
    task_status: str = "active"
    confidence: float = 0.5
    category: str = "general"
    evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LearningEvent:
    id: str
    extracted_count: int
    upserted_profile_ids: list[str] = field(default_factory=list)
    upserted_knowledge_ids: list[str] = field(default_factory=list)
    upserted_task_ids: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    reason: str = ""
    ts: datetime = field(default_factory=utc_now)
