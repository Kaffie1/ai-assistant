from __future__ import annotations

from collections import defaultdict, deque

from ..models.schemas import MemoryEdge, MemoryNode


class GraphStore:
    def __init__(self) -> None:
        """
        功能：初始化图存储的节点与边索引。
        输入：无。
        输出：无，创建内部索引结构。
        """
        self.nodes: dict[str, MemoryNode] = {}
        self.edges_out: dict[str, list[MemoryEdge]] = defaultdict(list)
        self.edges_in: dict[str, list[MemoryEdge]] = defaultdict(list)
        self.edge_index: dict[tuple[str, str, str], MemoryEdge] = {}

    def upsert_node(self, node: MemoryNode) -> None:
        """
        功能：插入或更新记忆节点。
        输入：节点对象 `node`。
        输出：无，副作用是更新节点索引。
        """
        self.nodes[node.id] = node

    def add_edge(self, edge: MemoryEdge) -> None:
        """
        功能：新增关系边并维护入/出边索引。
        输入：边对象 `edge`。
        输出：无，副作用是更新边索引。
        """
        key = (edge.src_id, edge.dst_id, edge.edge_type)
        existing = self.edge_index.get(key)
        if existing is not None:
            # Merge strategy for repeated edges:
            # - refresh timestamp
            # - smooth weight update to avoid abrupt spikes
            existing.weight = min(1.0, max(0.05, 0.7 * existing.weight + 0.3 * edge.weight))
            existing.ts = edge.ts
            return

        self.edge_index[key] = edge
        self.edges_out[edge.src_id].append(edge)
        self.edges_in[edge.dst_id].append(edge)

    def get_node(self, node_id: str) -> MemoryNode | None:
        """
        功能：按 ID 查询节点。
        输入：节点 ID `node_id`。
        输出：节点对象或 `None`。
        """
        return self.nodes.get(node_id)

    def iter_nodes(self) -> list[MemoryNode]:
        """
        功能：返回全部节点快照。
        输入：无。
        输出：节点列表。
        """
        return list(self.nodes.values())

    def neighbors(self, node_id: str) -> list[tuple[str, MemoryEdge]]:
        """
        功能：查询节点的一跳邻居。
        输入：节点 ID `node_id`。
        输出：`(neighbor_id, edge)` 列表，含入边和出边。
        """
        out = [(e.dst_id, e) for e in self.edges_out.get(node_id, [])]
        inc = [(e.src_id, e) for e in self.edges_in.get(node_id, [])]
        return out + inc

    def expand(self, seed_ids: list[str], hops: int = 1) -> dict[str, float]:
        """
        功能：从种子节点做带权 BFS 扩展并累计图分。
        输入：种子 ID 列表 `seed_ids`，跳数上限 `hops`。
        输出：`node_id -> graph_score` 映射。
        """
        # Returns node_id -> graph score induced by weighted BFS.
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
