from __future__ import annotations

import itertools
import re

from ..models.schemas import KnowledgeFact, ProfileFact, TaskFact


def _normalize_text(text: str) -> str:
    """
    功能：规范化文本，供去重键使用。
    输入：原始文本 `text`。
    输出：去空白并小写后的标准化字符串。
    """
    return re.sub(r"\s+", " ", text.strip().lower())


class InMemoryProfileStore:
    def __init__(self) -> None:
        self._facts: dict[str, ProfileFact] = {}
        self._index: dict[str, str] = {}
        self._counter = itertools.count(1)

    def upsert(self, fact: ProfileFact) -> ProfileFact:
        existing_id = self._index.get(fact.key)
        if existing_id and existing_id in self._facts:
            old = self._facts[existing_id]
            if fact.confidence >= old.confidence or fact.source == "user_feedback":
                updated = ProfileFact(
                    id=old.id,
                    key=old.key,
                    value=fact.value,
                    confidence=fact.confidence,
                    source=fact.source,
                    ts=fact.ts,
                    status="active",
                )
                self._facts[old.id] = updated
                return updated
            return old

        fact_id = fact.id or f"pf_{next(self._counter):06d}"
        created = ProfileFact(
            id=fact_id,
            key=fact.key,
            value=fact.value,
            confidence=fact.confidence,
            source=fact.source,
            ts=fact.ts,
            status=fact.status,
        )
        self._facts[created.id] = created
        self._index[created.key] = created.id
        return created

    def list(self) -> list[ProfileFact]:
        out = [f for f in self._facts.values() if f.status == "active"]
        out.sort(key=lambda x: x.ts, reverse=True)
        return out

    def delete(self, fact_id: str) -> bool:
        fact = self._facts.get(fact_id)
        if fact is None:
            return False
        self._facts[fact_id] = ProfileFact(
            id=fact.id,
            key=fact.key,
            value=fact.value,
            confidence=fact.confidence,
            source=fact.source,
            ts=fact.ts,
            status="deleted",
        )
        return True

    def get(self, fact_id: str) -> ProfileFact | None:
        return self._facts.get(fact_id)

    def downgrade_and_mark(self, fact_id: str, factor: float = 0.3, status: str = "superseded") -> bool:
        fact = self._facts.get(fact_id)
        if fact is None:
            return False
        self._facts[fact_id] = ProfileFact(
            id=fact.id,
            key=fact.key,
            value=fact.value,
            confidence=max(0.01, fact.confidence * factor),
            source=fact.source,
            ts=fact.ts,
            status=status,
        )
        if self._index.get(fact.key) == fact_id:
            self._index.pop(fact.key, None)
        return True

    def list_history(self, key: str) -> list[ProfileFact]:
        out = [f for f in self._facts.values() if f.key == key]
        out.sort(key=lambda x: x.ts, reverse=True)
        return out


class InMemoryKnowledgeStore:
    def __init__(self) -> None:
        self._facts: dict[str, KnowledgeFact] = {}
        self._index: dict[str, str] = {}
        self._counter = itertools.count(1)

    def upsert(self, fact: KnowledgeFact) -> KnowledgeFact:
        norm = _normalize_text(fact.statement)
        existing_id = self._index.get(norm)
        if existing_id and existing_id in self._facts:
            old = self._facts[existing_id]
            merged = KnowledgeFact(
                id=old.id,
                topic=fact.topic or old.topic,
                statement=old.statement,
                confidence=max(old.confidence, fact.confidence),
                source=fact.source,
                evidence=list(dict.fromkeys([*old.evidence, *fact.evidence])),
                ts=fact.ts,
                status="active",
                version=old.version + 1,
            )
            self._facts[old.id] = merged
            return merged

        fact_id = fact.id or f"kf_{next(self._counter):06d}"
        created = KnowledgeFact(
            id=fact_id,
            topic=fact.topic,
            statement=fact.statement,
            confidence=fact.confidence,
            source=fact.source,
            evidence=fact.evidence,
            ts=fact.ts,
            status=fact.status,
            version=fact.version,
        )
        self._facts[created.id] = created
        self._index[norm] = created.id
        return created

    def list(self) -> list[KnowledgeFact]:
        out = [f for f in self._facts.values() if f.status == "active"]
        out.sort(key=lambda x: x.ts, reverse=True)
        return out

    def delete(self, fact_id: str) -> bool:
        fact = self._facts.get(fact_id)
        if fact is None:
            return False
        self._facts[fact_id] = KnowledgeFact(
            id=fact.id,
            topic=fact.topic,
            statement=fact.statement,
            confidence=fact.confidence,
            source=fact.source,
            evidence=fact.evidence,
            ts=fact.ts,
            status="deleted",
            version=fact.version,
        )
        return True

    def get(self, fact_id: str) -> KnowledgeFact | None:
        return self._facts.get(fact_id)

    def downgrade_and_mark(self, fact_id: str, factor: float = 0.3, status: str = "superseded") -> bool:
        fact = self._facts.get(fact_id)
        if fact is None:
            return False
        self._facts[fact_id] = KnowledgeFact(
            id=fact.id,
            topic=fact.topic,
            statement=fact.statement,
            confidence=max(0.01, fact.confidence * factor),
            source=fact.source,
            evidence=fact.evidence,
            ts=fact.ts,
            status=status,
            version=fact.version + 1,
        )
        norm = _normalize_text(fact.statement)
        if self._index.get(norm) == fact_id:
            self._index.pop(norm, None)
        return True

    def list_history(self, topic: str) -> list[KnowledgeFact]:
        out = [f for f in self._facts.values() if f.topic == topic]
        out.sort(key=lambda x: x.ts, reverse=True)
        return out


class InMemoryTaskStore:
    def __init__(self) -> None:
        self._facts: dict[str, TaskFact] = {}
        self._index: dict[str, str] = {}
        self._counter = itertools.count(1)

    def upsert(self, fact: TaskFact) -> TaskFact:
        norm = _normalize_text(fact.content)
        existing_id = self._index.get(norm)
        if existing_id and existing_id in self._facts:
            old = self._facts[existing_id]
            updated = TaskFact(
                id=old.id,
                content=old.content,
                due_date=fact.due_date or old.due_date,
                confidence=max(old.confidence, fact.confidence),
                source=fact.source,
                evidence=list(dict.fromkeys([*old.evidence, *fact.evidence])),
                ts=fact.ts,
                status="active",
                version=old.version + 1,
            )
            self._facts[old.id] = updated
            return updated

        fact_id = fact.id or f"tf_{next(self._counter):06d}"
        created = TaskFact(
            id=fact_id,
            content=fact.content,
            due_date=fact.due_date,
            confidence=fact.confidence,
            source=fact.source,
            evidence=fact.evidence,
            ts=fact.ts,
            status=fact.status,
            version=fact.version,
        )
        self._facts[created.id] = created
        self._index[norm] = created.id
        return created

    def list(self) -> list[TaskFact]:
        out = [f for f in self._facts.values() if f.status == "active"]
        out.sort(key=lambda x: x.ts, reverse=True)
        return out

    def delete(self, fact_id: str) -> bool:
        fact = self._facts.get(fact_id)
        if fact is None:
            return False
        self._facts[fact_id] = TaskFact(
            id=fact.id,
            content=fact.content,
            due_date=fact.due_date,
            confidence=fact.confidence,
            source=fact.source,
            evidence=fact.evidence,
            ts=fact.ts,
            status="deleted",
            version=fact.version,
        )
        return True

    def get(self, fact_id: str) -> TaskFact | None:
        return self._facts.get(fact_id)

    def mark_done(self, fact_id: str) -> bool:
        fact = self._facts.get(fact_id)
        if fact is None:
            return False
        self._facts[fact_id] = TaskFact(
            id=fact.id,
            content=fact.content,
            due_date=fact.due_date,
            confidence=fact.confidence,
            source=fact.source,
            evidence=fact.evidence,
            ts=fact.ts,
            status="done",
            version=fact.version + 1,
        )
        return True

    def list_history(self) -> list[TaskFact]:
        out = list(self._facts.values())
        out.sort(key=lambda x: x.ts, reverse=True)
        return out
