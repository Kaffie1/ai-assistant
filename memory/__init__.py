from .core.contracts import (
    GraphStoreProtocol,
    KnowledgeStoreProtocol,
    ProfileStoreProtocol,
    TaskStoreProtocol,
    VectorStoreProtocol,
)
from .core.factory import MemoryStack, build_memory_stack_from_env
from .core.learning_factory import LearningStack, build_learning_stack
from .facts.sqlite_store import SQLiteKnowledgeStore, SQLiteProfileStore, SQLiteTaskStore
from .facts.store import InMemoryKnowledgeStore, InMemoryProfileStore, InMemoryTaskStore
from .graph.extractor import extract_memory_payload
from .graph.store import GraphStore
from .graph.writer import MemoryWriter
from .learning.commands import handle_command
from .learning.persona import build_persona_context
from .learning.pipeline import LearningPipeline, extract_candidate_facts, extract_candidate_facts_with_reason
from .models.schemas import (
    CandidateFact,
    KnowledgeFact,
    LearningEvent,
    MemoryEdge,
    MemoryNode,
    ProfileFact,
    TaskFact,
    RetrievalResult,
    VectorMatch,
)
from .retrieval.assembler import assemble_context
from .retrieval.embeddings import build_embedding_provider_from_env
from .retrieval.retriever import HybridRetriever
from .retrieval.vector_store import ChromaVectorStore, HashVectorStore, create_vector_store_from_env

__all__ = [
    "assemble_context",
    "build_embedding_provider_from_env",
    "build_learning_stack",
    "build_memory_stack_from_env",
    "build_persona_context",
    "CandidateFact",
    "ChromaVectorStore",
    "extract_memory_payload",
    "extract_candidate_facts",
    "extract_candidate_facts_with_reason",
    "GraphStoreProtocol",
    "GraphStore",
    "HashVectorStore",
    "HybridRetriever",
    "InMemoryKnowledgeStore",
    "InMemoryProfileStore",
    "InMemoryTaskStore",
    "KnowledgeFact",
    "KnowledgeStoreProtocol",
    "LearningEvent",
    "LearningPipeline",
    "LearningStack",
    "MemoryStack",
    "MemoryEdge",
    "MemoryNode",
    "MemoryWriter",
    "ProfileFact",
    "ProfileStoreProtocol",
    "TaskFact",
    "TaskStoreProtocol",
    "RetrievalResult",
    "SQLiteKnowledgeStore",
    "SQLiteProfileStore",
    "SQLiteTaskStore",
    "VectorMatch",
    "VectorStoreProtocol",
    "create_vector_store_from_env",
    "handle_command",
]
