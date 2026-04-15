from __future__ import annotations

from dataclasses import dataclass

from .contracts import VectorStoreProtocol
from ..graph.store import GraphStore
from ..graph.writer import MemoryWriter
from ..retrieval.retriever import HybridRetriever
from ..retrieval.vector_store import create_vector_store_from_env


@dataclass(slots=True)
class MemoryStack:
    graph: GraphStore
    vector: VectorStoreProtocol
    writer: MemoryWriter
    retriever: HybridRetriever


def build_memory_stack_from_env() -> MemoryStack:
    """
    功能：按环境变量装配记忆系统运行栈。
    输入：无（读取环境变量选择向量后端）。
    输出：`MemoryStack`（graph/vector/writer/retriever）。
    """
    graph = GraphStore()
    vector = create_vector_store_from_env()
    writer = MemoryWriter(graph=graph, vector=vector)
    retriever = HybridRetriever(graph=graph, vector=vector)
    return MemoryStack(
        graph=graph,
        vector=vector,
        writer=writer,
        retriever=retriever,
    )
