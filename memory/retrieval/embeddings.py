from __future__ import annotations

import hashlib
import math
import os
from typing import Protocol

from langchain_core.embeddings import Embeddings


class EmbeddingProvider(Protocol):
    @property
    def name(self) -> str:
        """返回 embedding 提供方名称。"""
        ...

    def embed_query(self, text: str) -> list[float]:
        """对查询文本生成向量。"""
        ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """对文档批量生成向量。"""
        ...

    def as_langchain_embeddings(self) -> Embeddings | None:
        """返回可选的 LangChain Embeddings 适配对象。"""
        ...


def _hash_embed(text: str, dim: int = 128) -> list[float]:
    """使用哈希构造离线向量，作为无依赖兜底方案。"""
    vec = [0.0] * dim
    for token in text.lower().split():
        h = hashlib.sha256(token.encode("utf-8")).digest()
        for i in range(0, min(dim, len(h))):
            vec[i] += (h[i] / 255.0) - 0.5
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


class HashEmbeddingProvider:
    @property
    def name(self) -> str:
        """返回提供方名称。"""
        return "hash"

    def embed_query(self, text: str) -> list[float]:
        """对查询文本生成哈希向量。"""
        return _hash_embed(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """对文档批量生成哈希向量。"""
        return [_hash_embed(t) for t in texts]

    def as_langchain_embeddings(self) -> Embeddings | None:
        """哈希提供方不暴露 LangChain Embeddings 对象。"""
        return None


class LangChainEmbeddingProvider:
    def __init__(self, name: str, embeddings: Embeddings) -> None:
        """包装 LangChain Embeddings，统一到本项目接口。"""
        self._name = name
        self._embeddings = embeddings

    @property
    def name(self) -> str:
        """返回提供方名称。"""
        return self._name

    def embed_query(self, text: str) -> list[float]:
        """对查询文本生成向量。"""
        return self._embeddings.embed_query(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """对文档批量生成向量。"""
        return self._embeddings.embed_documents(texts)

    def as_langchain_embeddings(self) -> Embeddings | None:
        """返回底层 LangChain Embeddings 对象。"""
        return self._embeddings


def build_embedding_provider_from_env() -> EmbeddingProvider:
    """按环境变量选择 embedding 提供方，失败时回退 hash。"""
    provider = os.getenv("MAMGA_EMBED_PROVIDER", "huggingface").lower()
    model = os.getenv("MAMGA_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

    try:
        if provider == "openai":
            from langchain_openai import OpenAIEmbeddings

            return LangChainEmbeddingProvider(
                name=f"openai:{model}",
                embeddings=OpenAIEmbeddings(model=model),
            )

        from langchain_huggingface import HuggingFaceEmbeddings

        return LangChainEmbeddingProvider(
            name=f"huggingface:{model}",
            embeddings=HuggingFaceEmbeddings(
                model_name=model,
                encode_kwargs={"normalize_embeddings": True},
            ),
        )
    except Exception:
        return HashEmbeddingProvider()
