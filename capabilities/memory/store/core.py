from __future__ import annotations

import itertools
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from foundation.time_utils import now_beijing


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


@dataclass(slots=True)
class TaskFact:
    id: str
    content: str
    due_date: str = ""
    confidence: float = 0.6
    source: str = "dialog"
    evidence: list[str] | None = None
    ts: datetime | None = None
    status: str = "active"
    version: int = 1

    def __post_init__(self) -> None:
        if self.evidence is None:
            self.evidence = []
        if self.ts is None:
            self.ts = now_beijing()


@dataclass(slots=True)
class ReminderFact:
    id: str
    content: str
    remind_text: str = ""
    remind_date: str = ""
    remind_at: str = ""
    confidence: float = 0.8
    source: str = "command"
    ts: datetime | None = None
    status: str = "active"
    version: int = 1

    def __post_init__(self) -> None:
        if self.ts is None:
            self.ts = now_beijing()


class TaskStoreProtocol(Protocol):
    def upsert(self, fact: TaskFact) -> TaskFact: ...
    def list(self) -> list[TaskFact]: ...
    def list_all(self) -> list[TaskFact]: ...
    def delete(self, fact_id: str) -> bool: ...
    def get(self, fact_id: str) -> TaskFact | None: ...
    def mark_done(self, fact_id: str) -> bool: ...
    def list_history(self) -> list[TaskFact]: ...


class ReminderStoreProtocol(Protocol):
    def upsert(self, fact: ReminderFact) -> ReminderFact: ...
    def list(self) -> list[ReminderFact]: ...
    def list_all(self) -> list[ReminderFact]: ...
    def delete(self, fact_id: str) -> bool: ...
    def get(self, fact_id: str) -> ReminderFact | None: ...


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
            merged_due = fact.due_date or old.due_date
            merged_conf = max(old.confidence, fact.confidence)
            merged_evidence = list(dict.fromkeys([*(old.evidence or []), *(fact.evidence or [])]))
            if merged_due == old.due_date and merged_conf == old.confidence and merged_evidence == (old.evidence or []):
                return old
            self._facts[old.id] = TaskFact(
                id=old.id,
                content=old.content,
                due_date=old.due_date,
                confidence=old.confidence,
                source=old.source,
                evidence=list(old.evidence or []),
                ts=old.ts,
                status="superseded",
                version=old.version,
            )
            fact_id = fact.id or f"tf_{next(self._counter):06d}"
            created = TaskFact(
                id=fact_id,
                content=old.content,
                due_date=merged_due,
                confidence=merged_conf,
                source=fact.source,
                evidence=merged_evidence,
                ts=fact.ts,
                status="active",
                version=old.version + 1,
            )
            self._facts[created.id] = created
            self._index[norm] = created.id
            return created

        fact_id = fact.id or f"tf_{next(self._counter):06d}"
        created = TaskFact(
            id=fact_id,
            content=fact.content,
            due_date=fact.due_date,
            confidence=fact.confidence,
            source=fact.source,
            evidence=list(fact.evidence or []),
            ts=fact.ts,
            status=fact.status,
            version=fact.version,
        )
        self._facts[created.id] = created
        self._index[norm] = created.id
        return created

    def list(self) -> list[TaskFact]:
        out = [f for f in self._facts.values() if f.status == "active"]
        out.sort(key=lambda x: x.ts or now_beijing(), reverse=True)
        return out

    def list_all(self) -> list[TaskFact]:
        out = list(self._facts.values())
        out.sort(key=lambda x: x.ts or now_beijing(), reverse=True)
        return out

    def delete(self, fact_id: str) -> bool:
        fact = self._facts.get(fact_id)
        if fact is None:
            return False
        self._facts[fact_id] = TaskFact(**{**fact.__dict__, "status": "deleted"})
        return True

    def get(self, fact_id: str) -> TaskFact | None:
        return self._facts.get(fact_id)

    def mark_done(self, fact_id: str) -> bool:
        fact = self._facts.get(fact_id)
        if fact is None:
            return False
        self._facts[fact_id] = TaskFact(**{**fact.__dict__, "status": "done", "version": fact.version + 1})
        return True

    def list_history(self) -> list[TaskFact]:
        return self.list_all()


class InMemoryReminderStore:
    def __init__(self) -> None:
        self._facts: dict[str, ReminderFact] = {}
        self._index: dict[str, str] = {}
        self._counter = itertools.count(1)

    def upsert(self, fact: ReminderFact) -> ReminderFact:
        norm = _normalize_text(f"{fact.remind_text}::{fact.content}")
        existing_id = self._index.get(norm)
        if existing_id and existing_id in self._facts:
            old = self._facts[existing_id]
            merged_at = fact.remind_at or old.remind_at
            merged_date = fact.remind_date or old.remind_date
            merged_conf = max(old.confidence, fact.confidence)
            if merged_at == old.remind_at and merged_date == old.remind_date and merged_conf == old.confidence:
                return old
            self._facts[old.id] = ReminderFact(
                id=old.id,
                content=old.content,
                remind_text=old.remind_text,
                remind_date=old.remind_date,
                remind_at=old.remind_at,
                confidence=old.confidence,
                source=old.source,
                ts=old.ts,
                status=old.status,
                version=old.version,
            )
            fact_id = fact.id or f"rf_{next(self._counter):06d}"
            created = ReminderFact(
                id=fact_id,
                content=fact.content,
                remind_text=fact.remind_text,
                remind_date=merged_date,
                remind_at=merged_at,
                confidence=merged_conf,
                source=fact.source,
                ts=fact.ts,
                status=fact.status,
                version=old.version + 1,
            )
            self._facts[created.id] = created
            self._index[norm] = created.id
            return created

        fact_id = fact.id or f"rf_{next(self._counter):06d}"
        created = ReminderFact(
            id=fact_id,
            content=fact.content,
            remind_text=fact.remind_text,
            remind_date=fact.remind_date,
            remind_at=fact.remind_at,
            confidence=fact.confidence,
            source=fact.source,
            ts=fact.ts,
            status=fact.status,
            version=fact.version,
        )
        self._facts[created.id] = created
        self._index[norm] = created.id
        return created

    def list(self) -> list[ReminderFact]:
        out = [f for f in self._facts.values() if f.status == "active"]
        out.sort(key=lambda x: x.ts or now_beijing(), reverse=True)
        return out

    def list_all(self) -> list[ReminderFact]:
        out = list(self._facts.values())
        out.sort(key=lambda x: x.ts or now_beijing(), reverse=True)
        return out

    def delete(self, fact_id: str) -> bool:
        fact = self._facts.get(fact_id)
        if fact is None:
            return False
        self._facts[fact_id] = ReminderFact(**{**fact.__dict__, "status": "deleted"})
        return True

    def get(self, fact_id: str) -> ReminderFact | None:
        return self._facts.get(fact_id)


@dataclass(slots=True)
class FactStoreStack:
    task_store: TaskStoreProtocol
    remind_store: ReminderStoreProtocol


def build_fact_store_stack() -> FactStoreStack:
    return FactStoreStack(task_store=InMemoryTaskStore(), remind_store=InMemoryReminderStore())
