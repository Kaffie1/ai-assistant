from __future__ import annotations

from dataclasses import dataclass

from capabilities.memory.long_term.graph_store import GraphStore
from capabilities.memory.long_term.types import VectorStoreProtocol
from capabilities.memory.long_term.writer import MemoryWriter
from capabilities.retrieval.retriever import HybridRetriever
from capabilities.retrieval.vector_store import create_vector_store_from_env


@dataclass(slots=True)
class LongTermMemoryStack:
    graph: GraphStore
    vector: VectorStoreProtocol
    writer: MemoryWriter
    retriever: HybridRetriever


def build_long_term_memory_stack() -> LongTermMemoryStack:
    """
    功能：按环境变量装配长期记忆运行栈。
    输入：无。
    输出：`LongTermMemoryStack`（graph/vector/writer/retriever）。
    """
    graph = GraphStore()
    vector = create_vector_store_from_env()
    writer = MemoryWriter(graph=graph, vector=vector)
    retriever = HybridRetriever(graph=graph, vector=vector)
    return LongTermMemoryStack(
        graph=graph,
        vector=vector,
        writer=writer,
        retriever=retriever,
    )
