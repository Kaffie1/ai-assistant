from __future__ import annotations

import itertools
from datetime import datetime, timezone

from ..core.contracts import GraphStoreProtocol, VectorStoreProtocol
from .extractor import extract_memory_payload
from ..models.schemas import MemoryEdge, MemoryNode


class MemoryWriter:
    def __init__(self, graph: GraphStoreProtocol, vector: VectorStoreProtocol) -> None:
        """
        功能：初始化记忆写入器并准备时间边缓存。
        输入：图存储 `graph`，向量存储 `vector`。
        输出：无，内部维护节点计数器和最近节点 ID。
        """
        self.graph = graph
        self.vector = vector
        self._counter = itertools.count(1)
        self._last_node_id: str | None = None

    def add_text(self, text: str, source: str = "dialog", ts: datetime | None = None) -> MemoryNode:
        """
        功能：把文本写入为结构化记忆节点并同步索引。
        输入：文本 `text`、来源 `source`、可选时间戳 `ts`。
        输出：创建后的 `MemoryNode`。
        """
        if ts is None:
            ts = datetime.now(timezone.utc)
        node_id = f"m_{next(self._counter):06d}"
        entities, topics, importance = extract_memory_payload(text)
        node = MemoryNode(
            id=node_id,
            text=text,
            ts=ts,
            entities=entities,
            topics=topics,
            source=source,
            importance=importance,
        )
        self.graph.upsert_node(node)
        self.vector.upsert(node.id, node.text)
        self._link_node(node)
        self._link_temporal(node)
        self._last_node_id = node.id
        return node

    def _link_node(self, node: MemoryNode) -> None:
        """
        功能：为新节点建立实体/主题关系边。
        输入：新写入的节点 `node`。
        输出：无，副作用是向图中添加关系边。
        """
        for other in self.graph.iter_nodes():
            if other.id == node.id:
                continue
            shared_entities = set(node.entities).intersection(other.entities)
            shared_topics = set(node.topics).intersection(other.topics)

            if shared_entities:
                self.graph.add_edge(
                    MemoryEdge(
                        src_id=node.id,
                        dst_id=other.id,
                        edge_type="entity",
                        weight=min(1.0, 0.5 + 0.1 * len(shared_entities)),
                    )
                )
            if shared_topics:
                self.graph.add_edge(
                    MemoryEdge(
                        src_id=node.id,
                        dst_id=other.id,
                        edge_type="semantic",
                        weight=min(1.0, 0.4 + 0.2 * len(shared_topics)),
                    )
                )

    def _link_temporal(self, node: MemoryNode) -> None:
        """
        功能：建立稀疏时间边（仅连接到上一条记忆）。
        输入：新写入节点 `node`。
        输出：无，副作用是向图中添加 temporal 边。
        """
        # Keep temporal graph sparse: only connect to immediate previous memory.
        if not self._last_node_id:
            return
        prev = self.graph.get_node(self._last_node_id)
        if prev is None:
            return
        hours = abs((node.ts - prev.ts).total_seconds()) / 3600.0
        weight = max(0.2, 1.0 - hours / 6.0)
        self.graph.add_edge(
            MemoryEdge(
                src_id=node.id,
                dst_id=prev.id,
                edge_type="temporal",
                weight=weight,
            )
        )
