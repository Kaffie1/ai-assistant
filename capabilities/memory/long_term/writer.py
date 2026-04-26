from __future__ import annotations

import itertools
from datetime import datetime

from foundation.time_utils import now_beijing
from capabilities.memory.long_term.extractor import extract_memory_payload
from capabilities.memory.long_term.types import GraphStoreProtocol, MemoryEdge, MemoryNode, VectorStoreProtocol


class MemoryWriter:
    def __init__(self, graph: GraphStoreProtocol, vector: VectorStoreProtocol) -> None:
        self.graph = graph
        self.vector = vector
        self._counter = itertools.count(1)
        self._last_node_id: str | None = None

    def add_text(self, text: str, source: str = "dialog", ts: datetime | None = None) -> MemoryNode:
        if ts is None:
            ts = now_beijing()
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
