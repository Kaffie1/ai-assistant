from __future__ import annotations

import itertools
from datetime import datetime
from pathlib import Path
from typing import Protocol

from foundation.config import MAMGA_TASK_MEMORY_MD_PATH
from foundation.time_utils import now_beijing
from pydantic import BaseModel, Field


def _normalize_text(text: str) -> str:
    """
    功能：把任务文本归一化，便于做内容去重。
    输入：原始文本 `text`。
    输出：小写、压缩空白后的标准化文本。
    """
    return " ".join(str(text or "").strip().lower().split())


class TaskFact(BaseModel):
    """
    任务事实结构。
    """

    id: str = Field(default="", description="任务唯一 ID。")
    content: str = Field(default="", description="任务内容。")
    due_date: str = Field(default="", description="任务截止日期。")
    confidence: float = Field(default=0.6, description="任务置信度。")
    source: str = Field(default="dialog", description="任务来源。")
    evidence: list[str] = Field(default_factory=list, description="任务证据列表。")
    ts: datetime = Field(default_factory=now_beijing, description="任务创建时间。")
    status: str = Field(default="active", description="任务状态。")
    version: int = Field(default=1, description="任务版本号。")


class TaskStoreProtocol(Protocol):
    def upsert(self, fact: TaskFact) -> TaskFact: ...
    def list(self) -> list[TaskFact]: ...
    def list_all(self) -> list[TaskFact]: ...
    def delete(self, fact_id: str) -> bool: ...
    def get(self, fact_id: str) -> TaskFact | None: ...
    def mark_done(self, fact_id: str) -> bool: ...
    def list_history(self) -> list[TaskFact]: ...


def _task_md_path() -> Path:
    """
    功能：返回任务 Markdown 持久化文件路径。
    输入：无。
    输出：任务 Markdown 文件路径。
    """
    return Path(MAMGA_TASK_MEMORY_MD_PATH)


def _serialize_task_fact(fact: TaskFact) -> str:
    """
    功能：把任务事实序列化为 Markdown 块。
    输入：任务事实 `fact`。
    输出：对应的 Markdown 文本块。
    """
    evidence = "; ".join(fact.evidence or [])
    return "\n".join(
        [
            f"## {fact.id}",
            f"- status: {fact.status}",
            f"- version: {fact.version}",
            f"- due_date: {fact.due_date}",
            f"- confidence: {fact.confidence}",
            f"- source: {fact.source}",
            f"- ts: {fact.ts.isoformat()}",
            f"- evidence: {evidence}",
            f"- content: {fact.content}",
        ]
    )


def _save_task_facts(facts: dict[str, TaskFact]) -> None:
    """
    功能：把任务事实全量写入 Markdown 文件。
    输入：任务事实字典 `facts`。
    输出：无，副作用是覆盖写入任务 Markdown 文件。
    """
    path = _task_md_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(facts.values(), key=lambda item: item.ts, reverse=True)
    body = "\n\n---\n\n".join(_serialize_task_fact(fact) for fact in ordered)
    if body:
        body += "\n"
    path.write_text(body, encoding="utf-8")


def _load_task_facts() -> dict[str, TaskFact]:
    """
    功能：从 Markdown 文件回载任务事实。
    输入：无。
    输出：任务事实字典。
    """
    path = _task_md_path()
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    facts: dict[str, TaskFact] = {}
    for block in text.split("\n\n---\n\n"):
        lines = [line.rstrip() for line in block.splitlines() if line.strip()]
        if not lines or not lines[0].startswith("## "):
            continue
        fact_id = lines[0][3:].strip()
        payload: dict[str, str] = {"id": fact_id}
        for line in lines[1:]:
            if not line.startswith("- ") or ":" not in line:
                continue
            key, value = line[2:].split(":", 1)
            payload[key.strip()] = value.strip()
        try:
            facts[fact_id] = TaskFact(
                id=fact_id,
                content=payload.get("content", ""),
                due_date=payload.get("due_date", ""),
                confidence=float(payload.get("confidence", "0.6") or 0.6),
                source=payload.get("source", "dialog"),
                evidence=[item.strip() for item in payload.get("evidence", "").split(";") if item.strip()],
                ts=datetime.fromisoformat(payload.get("ts", now_beijing().isoformat())),
                status=payload.get("status", "active"),
                version=int(payload.get("version", "1") or 1),
            )
        except Exception:
            continue
    return facts


def _rebuild_task_index(facts: dict[str, TaskFact]) -> dict[str, str]:
    """
    功能：根据任务事实重建内容去重索引。
    输入：任务事实字典 `facts`。
    输出：归一化文本到任务 ID 的映射。
    """
    index: dict[str, str] = {}
    ordered = sorted(facts.values(), key=lambda item: item.ts)
    for fact in ordered:
        index[_normalize_text(fact.content)] = fact.id
    return index


def _task_counter_start(facts: dict[str, TaskFact]) -> int:
    """
    功能：根据已有任务 ID 推导下一个计数器起点。
    输入：任务事实字典 `facts`。
    输出：自增计数器起始值。
    """
    max_num = 0
    for fact_id in facts:
        if fact_id.startswith("tf_"):
            try:
                max_num = max(max_num, int(fact_id.split("_", 1)[1]))
            except Exception:
                continue
    return max_num + 1


class InMemoryTaskStore:
    def __init__(self) -> None:
        """
        功能：初始化内存版任务存储。
        输入：无。
        输出：无，建立任务事实表、去重索引和自增计数器。
        """
        self._facts = _load_task_facts()
        self._index = _rebuild_task_index(self._facts)
        self._counter = itertools.count(_task_counter_start(self._facts))

    def upsert(self, fact: TaskFact) -> TaskFact:
        """
        功能：写入或更新一条任务事实，并按内容做合并去重。
        输入：任务事实 `fact`。
        输出：最终落库后的任务事实对象。
        """
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
            _save_task_facts(self._facts)
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
        _save_task_facts(self._facts)
        return created

    def list(self) -> list[TaskFact]:
        """
        功能：返回当前所有有效任务。
        输入：无。
        输出：按时间倒序排列的 active 任务列表。
        """
        out = [f for f in self._facts.values() if f.status == "active"]
        out.sort(key=lambda x: x.ts or now_beijing(), reverse=True)
        return out

    def list_all(self) -> list[TaskFact]:
        """
        功能：返回当前所有任务，包括历史状态。
        输入：无。
        输出：按时间倒序排列的完整任务列表。
        """
        out = list(self._facts.values())
        out.sort(key=lambda x: x.ts or now_beijing(), reverse=True)
        return out

    def delete(self, fact_id: str) -> bool:
        """
        功能：逻辑删除一条任务事实。
        输入：任务 ID `fact_id`。
        输出：删除成功返回 `True`，否则返回 `False`。
        """
        fact = self._facts.get(fact_id)
        if fact is None:
            return False
        self._facts[fact_id] = fact.model_copy(update={"status": "deleted"})
        _save_task_facts(self._facts)
        return True

    def get(self, fact_id: str) -> TaskFact | None:
        """
        功能：按 ID 获取单条任务事实。
        输入：任务 ID `fact_id`。
        输出：命中时返回任务事实，否则返回 `None`。
        """
        return self._facts.get(fact_id)

    def mark_done(self, fact_id: str) -> bool:
        """
        功能：把一条任务标记为已完成。
        输入：任务 ID `fact_id`。
        输出：标记成功返回 `True`，否则返回 `False`。
        """
        fact = self._facts.get(fact_id)
        if fact is None:
            return False
        self._facts[fact_id] = fact.model_copy(update={"status": "done", "version": fact.version + 1})
        _save_task_facts(self._facts)
        return True

    def list_history(self) -> list[TaskFact]:
        """
        功能：返回任务历史记录。
        输入：无。
        输出：当前存储中的完整任务历史列表。
        """
        return self.list_all()
