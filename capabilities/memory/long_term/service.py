from __future__ import annotations

from capabilities.memory.long_term.store import InMemoryLongTermStore
from capabilities.memory.long_term.types import MemoryNode
from capabilities.retrieval.assembler import assemble_context
from capabilities.retrieval.retriever import HybridRetriever
from capabilities.retrieval.vector_store import create_vector_store_from_env
from foundation.time_utils import now_beijing


class LongTermMemoryService:
    def __init__(self) -> None:
        """
        功能：初始化长期记忆服务。
        输入：无。
        输出：无。
        """
        self.store = InMemoryLongTermStore()
        self.vector = create_vector_store_from_env()
        self.retriever = HybridRetriever(graph=self.store, vector=self.vector)
        self._indexed_ids: set[str] = set()
        self._sync_index()

    def _sync_index(self) -> None:
        """
        功能：把当前 active 长期记忆同步到向量索引。
        输入：无。
        输出：无。
        """
        for node in self.store.list_active():
            if node.id in self._indexed_ids:
                continue
            self.vector.upsert(node.id, node.text)
            self._indexed_ids.add(node.id)

    def retrieve_context(self, query: str, max_items: int = 6) -> str:
        """
        功能：按用户查询检索长期记忆并拼接为上下文文本。
        输入：查询文本 `query`、返回条数上限 `max_items`。
        输出：用于 Prompt 的长期记忆上下文。
        """
        self._sync_index()
        normalized = str(query or "").strip()
        if not normalized:
            return ""
        results = self.retriever.retrieve(query=normalized, top_n_final=max_items)
        if not results:
            return ""
        for result in results:
            self.store.touch(result.node.id, seen_at=now_beijing())
        return assemble_context(results=results, max_items=max_items)

    def remember(self, text: str, *, kind: str = "fact", source: str = "chat", importance: float = 0.5, tags: list[str] | None = None) -> MemoryNode:
        """
        功能：写入一条长期记忆节点。
        输入：文本内容及基础元信息。
        输出：保存后的节点对象。
        """
        stored = self.store.upsert(
            MemoryNode(
                text=str(text or "").strip(),
                kind=kind,
                source=source,
                ts=now_beijing(),
                importance=importance,
                tags=list(tags or []),
            )
        )
        self.vector.upsert(stored.id, stored.text)
        self._indexed_ids.add(stored.id)
        return stored
