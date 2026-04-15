from __future__ import annotations

import os
import re
from dataclasses import dataclass

from ..core.contracts import VectorStoreProtocol
from .embeddings import EmbeddingProvider, HashEmbeddingProvider, build_embedding_provider_from_env
from ..models.schemas import VectorMatch


def _cosine(a: list[float], b: list[float]) -> float:
    """
    功能：计算两个向量的余弦相似度。
    输入：向量 `a` 和向量 `b`。
    输出：相似度分数（浮点数）。
    """
    return sum(x * y for x, y in zip(a, b))


def _safe_collection_suffix(provider_name: str) -> str:
    """把 provider 名称转换为可用于 collection 的安全后缀。"""
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", provider_name).strip("_").lower()
    return cleaned or "default"


@dataclass(slots=True)
class HashVectorStore(VectorStoreProtocol):
    embedding_provider: EmbeddingProvider

    def __post_init__(self) -> None:
        """
        功能：初始化 hash 向量后端的内存索引。
        输入：无。
        输出：无，创建内部向量字典。
        """
        self._vecs: dict[str, list[float]] = {}

    @property
    def mode(self) -> str:
        """
        功能：返回向量后端模式。
        输入：无。
        输出：`hash`。
        """
        return "hash"

    @property
    def provider_name(self) -> str:
        """
        功能：返回当前 embedding 提供方名称。
        输入：无。
        输出：提供方名称字符串。
        """
        return self.embedding_provider.name

    def upsert(self, node_id: str, text: str) -> None:
        """
        功能：写入或更新节点向量。
        输入：节点 ID `node_id`，文本 `text`。
        输出：无，副作用是更新内存向量索引。
        """
        self._vecs[node_id] = self.embedding_provider.embed_query(text)

    def search(self, query: str, top_k: int = 20) -> list[VectorMatch]:
        """
        功能：执行 hash 向量检索。
        输入：查询文本 `query`，返回数量 `top_k`。
        输出：按相似度排序的 `VectorMatch` 列表。
        """
        qv = self.embedding_provider.embed_query(query)
        scored = [VectorMatch(node_id=nid, score=_cosine(qv, vec)) for nid, vec in self._vecs.items()]
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:top_k]


class ChromaVectorStore(VectorStoreProtocol):
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        collection_name: str,
        persist_directory: str,
    ) -> None:
        """
        功能：初始化 Chroma 向量后端实例。
        输入：embedding 提供方、集合名、持久化目录。
        输出：无，内部创建 Chroma 客户端。
        """
        from langchain_chroma import Chroma

        embeddings = embedding_provider.as_langchain_embeddings()
        if embeddings is None:
            raise ValueError("ChromaVectorStore requires a LangChain-compatible embedding provider.")
        self._provider = embedding_provider
        self._ids: set[str] = set()
        self._chroma = Chroma(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=persist_directory,
        )

    @property
    def mode(self) -> str:
        """
        功能：返回向量后端模式。
        输入：无。
        输出：`chroma`。
        """
        return "chroma"

    @property
    def provider_name(self) -> str:
        """
        功能：返回当前 embedding 提供方名称。
        输入：无。
        输出：提供方名称字符串。
        """
        return self._provider.name

    def upsert(self, node_id: str, text: str) -> None:
        """
        功能：写入或更新 Chroma 文档。
        输入：节点 ID `node_id`，文本 `text`。
        输出：无，副作用是更新 Chroma 集合。
        """
        if node_id in self._ids:
            self._chroma.delete(ids=[node_id])
        self._chroma.add_texts(
            texts=[text],
            ids=[node_id],
            metadatas=[{"node_id": node_id}],
        )
        self._ids.add(node_id)

    def search(self, query: str, top_k: int = 20) -> list[VectorMatch]:
        """
        功能：执行 Chroma 相似检索并转换分数。
        输入：查询文本 `query`，返回数量 `top_k`。
        输出：`VectorMatch` 列表（距离已映射为相似度）。
        """
        docs_scores = self._chroma.similarity_search_with_score(query, k=top_k)
        out: list[VectorMatch] = []
        for doc, distance in docs_scores:
            node_id = (doc.metadata or {}).get("node_id")
            if not node_id:
                continue
            sim = 1.0 / (1.0 + max(0.0, float(distance)))
            out.append(VectorMatch(node_id=node_id, score=sim))
        return out


def create_vector_store_from_env() -> VectorStoreProtocol:
    """
    功能：按环境变量构建向量存储实例。
    输入：无（读取 `.env` / 环境变量）。
    输出：`VectorStoreProtocol` 实现；失败时回退 hash 后端。
    """
    backend = os.getenv("MAMGA_VECTOR_BACKEND", "chroma").lower()
    collection = os.getenv("MAMGA_COLLECTION", "").strip()

    if backend == "hash":
        return HashVectorStore(embedding_provider=HashEmbeddingProvider())

    provider = build_embedding_provider_from_env()

    try:
        if not collection:
            collection = f"mamga_memory_{_safe_collection_suffix(provider.name)}"
        return ChromaVectorStore(
            embedding_provider=provider,
            collection_name=collection,
            persist_directory=os.getenv("MAMGA_CHROMA_DIR", "./.chroma_mamga"),
        )
    except Exception:
        # Keep system available even when vector backend or model setup fails.
        return HashVectorStore(embedding_provider=HashEmbeddingProvider())
