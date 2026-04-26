from __future__ import annotations

import re
from datetime import datetime

from capabilities.memory.long_term.types import GraphStoreProtocol, RetrievalResult, VectorStoreProtocol
from foundation.time_utils import now_beijing
from .policies import recency_score


def _tokenize_for_overlap(text: str) -> set[str]:
    """
    功能：把中英文文本切分为统一 token 集合。
    输入：原始文本 `text`。
    输出：用于关键词重合计算的 token set。
    """
    # Mixed tokenizer for EN/ZH:
    # - keep ascii words
    # - for chinese spans, use char bigrams to improve partial-match sensitivity
    tokens: set[str] = set()
    for part in re.findall(r"[A-Za-z0-9_+-]+|[\u4e00-\u9fff]+", text.lower()):
        if re.match(r"^[\u4e00-\u9fff]+$", part):
            if len(part) == 1:
                tokens.add(part)
            else:
                tokens.update(part[i : i + 2] for i in range(len(part) - 1))
        else:
            tokens.add(part)
    return tokens


def _lexical_overlap_score(query: str, text: str) -> float:
    """
    功能：计算 query 对候选文本的关键词覆盖率。
    输入：查询 `query`，候选文本 `text`。
    输出：0~1 的覆盖率分数。
    """
    q = _tokenize_for_overlap(query)
    t = _tokenize_for_overlap(text)
    if not q or not t:
        return 0.0
    return len(q.intersection(t)) / len(q)


class HybridRetriever:
    def __init__(self, graph: GraphStoreProtocol, vector: VectorStoreProtocol) -> None:
        """
        功能：初始化混合检索器。
        输入：图存储 `graph`，向量存储 `vector`。
        输出：无，保存依赖供后续检索使用。
        """
        self.graph = graph
        self.vector = vector

    def retrieve(
        self,
        query: str,
        top_k_vector: int = 20,
        hops: int = 1,
        top_n_final: int = 10,
        top_seed_graph: int = 3,
        min_semantic: float = 0.25,
        min_lexical: float = 0.05,
        zero_overlap_penalty: float = 0.08,
        weight_semantic: float = 0.65,
        weight_lexical: float = 0.1,
        weight_graph: float = 0.15,
        weight_recency: float = 0.05,
        weight_importance: float = 0.05,
    ) -> list[RetrievalResult]:
        """
        功能：执行混合检索（向量召回 -> 图扩展 -> 过滤重排）。
        输入：查询词与检索参数（top-k、权重、阈值等）。
        输出：按最终分数排序的 `RetrievalResult` 列表。
        """
        now = now_beijing()
        vector_hits = self.vector.search(query, top_k=top_k_vector)
        sem_map = {x.node_id: x.score for x in vector_hits}

        lexical_map: dict[str, float] = {}
        for hit in vector_hits:
            node = self.graph.get_node(hit.node_id)
            if node is None:
                continue
            lexical_map[hit.node_id] = _lexical_overlap_score(query, node.text)

        seed_with_lex = [h.node_id for h in vector_hits if lexical_map.get(h.node_id, 0.0) > 0.0]
        seed_ids = seed_with_lex[:top_seed_graph]
        if not seed_ids:
            seed_ids = [x.node_id for x in vector_hits[: max(1, top_seed_graph - 1)]]

        graph_map = self.graph.expand(seed_ids=seed_ids, hops=hops)
        gmax = max(graph_map.values()) if graph_map else 1.0

        candidate_ids = set(seed_ids).union(graph_map.keys())
        results: list[RetrievalResult] = []
        for nid in candidate_ids:
            node = self.graph.get_node(nid)
            if node is None:
                continue
            semantic = sem_map.get(nid, 0.0)
            lexical = lexical_map.get(nid, _lexical_overlap_score(query, node.text))
            graph = graph_map.get(nid, 0.0) / gmax
            # Query-aware graph gating: weak semantic/lexical match => graph bonus shrinks.
            graph = graph * (0.4 + 0.6 * max(semantic, lexical))
            recent = recency_score(node.ts, now=now)

            # Keep graph-expanded nodes only when they have at least minimal query relevance.
            if nid not in seed_ids and semantic < min_semantic and lexical < min_lexical:
                continue
            # Avoid low-precision vector seeds dominating final results.
            if nid in seed_ids and lexical == 0.0 and semantic < 0.58:
                continue

            final = (
                weight_semantic * semantic
                + weight_lexical * lexical
                + weight_graph * graph
                + weight_recency * recent
                + weight_importance * node.importance
            )
            # Penalize graph-propagated "soft related" items with zero lexical overlap.
            if lexical == 0.0 and semantic < 0.60:
                final -= zero_overlap_penalty
            results.append(
                RetrievalResult(
                    node=node,
                    semantic_score=semantic,
                    lexical_score=lexical,
                    graph_score=graph,
                    recency_score=recent,
                    final_score=final,
                )
            )
        results.sort(key=lambda x: x.final_score, reverse=True)
        return results[:top_n_final]
