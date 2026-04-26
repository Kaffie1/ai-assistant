from __future__ import annotations

from collections import defaultdict, deque

from capabilities.memory.long_term.types import MemoryEdge, MemoryNode


class GraphStore:
    def __init__(self) -> None:
        self.nodes: dict[str, MemoryNode] = {}
        self.edges_out: dict[str, list[MemoryEdge]] = defaultdict(list)
        self.edges_in: dict[str, list[MemoryEdge]] = defaultdict(list)
        self.edge_index: dict[tuple[str, str, str], MemoryEdge] = {}

    def upsert_node(self, node: MemoryNode) -> None:
        self.nodes[node.id] = node

    def add_edge(self, edge: MemoryEdge) -> None:
        key = (edge.src_id, edge.dst_id, edge.edge_type)
        existing = self.edge_index.get(key)
        if existing is not None:
            existing.weight = min(1.0, max(0.05, 0.7 * existing.weight + 0.3 * edge.weight))
            existing.ts = edge.ts
            return

        self.edge_index[key] = edge
        self.edges_out[edge.src_id].append(edge)
        self.edges_in[edge.dst_id].append(edge)

    def get_node(self, node_id: str) -> MemoryNode | None:
        return self.nodes.get(node_id)

    def iter_nodes(self) -> list[MemoryNode]:
        return list(self.nodes.values())

    def neighbors(self, node_id: str) -> list[tuple[str, MemoryEdge]]:
        out = [(e.dst_id, e) for e in self.edges_out.get(node_id, [])]
        inc = [(e.src_id, e) for e in self.edges_in.get(node_id, [])]
        return out + inc

    def expand(self, seed_ids: list[str], hops: int = 1) -> dict[str, float]:
        scores: dict[str, float] = defaultdict(float)
        q: deque[tuple[str, int, float]] = deque((sid, 0, 1.0) for sid in seed_ids)
        seen = set()
        while q:
            node_id, depth, carry = q.popleft()
            key = (node_id, depth)
            if key in seen or depth > hops:
                continue
            seen.add(key)
            scores[node_id] += carry
            if depth == hops:
                continue
            for nbr, edge in self.neighbors(node_id):
                next_carry = carry * max(0.05, min(edge.weight, 1.0)) * 0.8
                q.append((nbr, depth + 1, next_carry))
        return dict(scores)
