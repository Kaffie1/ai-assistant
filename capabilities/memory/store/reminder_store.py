from __future__ import annotations

import itertools
from datetime import datetime
from pathlib import Path
from typing import Protocol

from foundation.config import MAMGA_REMINDER_MEMORY_MD_PATH
from foundation.time_utils import now_beijing
from pydantic import BaseModel, Field

MAX_REMINDER_FACTS = 100


def _normalize_text(text: str) -> str:
    """
    功能：把提醒文本归一化，便于做内容去重。
    输入：原始文本 `text`。
    输出：小写、压缩空白后的标准化文本。
    """
    return " ".join(str(text or "").strip().lower().split())


class ReminderFact(BaseModel):
    """
    提醒事实结构。
    """

    id: str = Field(default="", description="提醒唯一 ID。")
    content: str = Field(default="", description="提醒内容。")
    remind_text: str = Field(default="", description="原始提醒表达。")
    remind_date: str = Field(default="", description="提醒日期。")
    remind_at: str = Field(default="", description="提醒触发时间。")
    confidence: float = Field(default=0.8, description="提醒置信度。")
    source: str = Field(default="command", description="提醒来源。")
    ts: datetime = Field(default_factory=now_beijing, description="提醒创建时间。")
    status: str = Field(default="active", description="提醒状态。")
    version: int = Field(default=1, description="提醒版本号。")


class ReminderStoreProtocol(Protocol):
    def upsert(self, fact: ReminderFact) -> ReminderFact: ...
    def list(self) -> list[ReminderFact]: ...
    def list_all(self) -> list[ReminderFact]: ...
    def delete(self, fact_id: str) -> bool: ...
    def get(self, fact_id: str) -> ReminderFact | None: ...


def _reminder_md_path() -> Path:
    """
    功能：返回提醒 Markdown 持久化文件路径。
    输入：无。
    输出：提醒 Markdown 文件路径。
    """
    return Path(MAMGA_REMINDER_MEMORY_MD_PATH)


def _serialize_reminder_fact(fact: ReminderFact) -> str:
    """
    功能：把提醒事实序列化为 Markdown 块。
    输入：提醒事实 `fact`。
    输出：对应的 Markdown 文本块。
    """
    return "\n".join(
        [
            f"## {fact.id}",
            f"- status: {fact.status}",
            f"- version: {fact.version}",
            f"- remind_date: {fact.remind_date}",
            f"- remind_at: {fact.remind_at}",
            f"- remind_text: {fact.remind_text}",
            f"- confidence: {fact.confidence}",
            f"- source: {fact.source}",
            f"- ts: {fact.ts.isoformat()}",
            f"- content: {fact.content}",
        ]
    )


def _save_reminder_facts(facts: dict[str, ReminderFact]) -> None:
    """
    功能：把提醒事实全量写入 Markdown 文件。
    输入：提醒事实字典 `facts`。
    输出：无，副作用是覆盖写入提醒 Markdown 文件。
    """
    path = _reminder_md_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(facts.values(), key=lambda item: item.ts, reverse=True)
    body = "\n\n---\n\n".join(_serialize_reminder_fact(fact) for fact in ordered)
    if body:
        body += "\n"
    path.write_text(body, encoding="utf-8")


def _load_reminder_facts() -> dict[str, ReminderFact]:
    """
    功能：从 Markdown 文件回载提醒事实。
    输入：无。
    输出：提醒事实字典。
    """
    path = _reminder_md_path()
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    facts: dict[str, ReminderFact] = {}
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
            facts[fact_id] = ReminderFact(
                id=fact_id,
                content=payload.get("content", ""),
                remind_text=payload.get("remind_text", ""),
                remind_date=payload.get("remind_date", ""),
                remind_at=payload.get("remind_at", ""),
                confidence=float(payload.get("confidence", "0.8") or 0.8),
                source=payload.get("source", "command"),
                ts=datetime.fromisoformat(payload.get("ts", now_beijing().isoformat())),
                status=payload.get("status", "active"),
                version=int(payload.get("version", "1") or 1),
            )
        except Exception:
            continue
    return facts


def _rebuild_reminder_index(facts: dict[str, ReminderFact]) -> dict[str, str]:
    """
    功能：根据提醒事实重建内容去重索引。
    输入：提醒事实字典 `facts`。
    输出：归一化文本到提醒 ID 的映射。
    """
    index: dict[str, str] = {}
    ordered = sorted(facts.values(), key=lambda item: item.ts)
    for fact in ordered:
        index[_normalize_text(f"{fact.remind_text}::{fact.content}")] = fact.id
    return index


def _reminder_counter_start(facts: dict[str, ReminderFact]) -> int:
    """
    功能：根据已有提醒 ID 推导下一个计数器起点。
    输入：提醒事实字典 `facts`。
    输出：自增计数器起始值。
    """
    max_num = 0
    for fact_id in facts:
        if fact_id.startswith("rf_"):
            try:
                max_num = max(max_num, int(fact_id.split("_", 1)[1]))
            except Exception:
                continue
    return max_num + 1


def _trim_reminder_facts(
    facts: dict[str, ReminderFact], limit: int = MAX_REMINDER_FACTS
) -> dict[str, ReminderFact]:
    """
    功能：将提醒事实裁剪到固定上限，超出时按最早创建时间淘汰。
    输入：提醒事实字典 `facts`、保留上限 `limit`。
    输出：裁剪后的提醒事实字典。
    """
    if len(facts) <= limit:
        return facts
    ordered = sorted(facts.values(), key=lambda item: (item.ts, item.id))
    kept = ordered[-limit:]
    return {fact.id: fact for fact in kept}


class InMemoryReminderStore:
    def __init__(self) -> None:
        """
        功能：初始化内存版提醒存储。
        输入：无。
        输出：无，建立提醒事实表、去重索引和自增计数器。
        """
        self._facts = _load_reminder_facts()
        self._facts = _trim_reminder_facts(self._facts)
        self._index = _rebuild_reminder_index(self._facts)
        self._counter = itertools.count(_reminder_counter_start(self._facts))

    def _persist(self) -> None:
        """
        功能：持久化提醒存储，并在写入前执行固定上限裁剪。
        输入：无。
        输出：无。
        """
        self._facts = _trim_reminder_facts(self._facts)
        self._index = _rebuild_reminder_index(self._facts)
        _save_reminder_facts(self._facts)

    def upsert(self, fact: ReminderFact) -> ReminderFact:
        """
        功能：写入或更新一条提醒事实，并按提醒表达做合并去重。
        输入：提醒事实 `fact`。
        输出：最终落库后的提醒事实对象。
        """
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
            self._persist()
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
        self._persist()
        return created

    def list(self) -> list[ReminderFact]:
        """
        功能：返回当前所有有效提醒。
        输入：无。
        输出：按时间倒序排列的 active 提醒列表。
        """
        out = [f for f in self._facts.values() if f.status == "active"]
        out.sort(key=lambda x: x.ts or now_beijing(), reverse=True)
        return out

    def list_all(self) -> list[ReminderFact]:
        """
        功能：返回当前所有提醒，包括历史状态。
        输入：无。
        输出：按时间倒序排列的完整提醒列表。
        """
        out = list(self._facts.values())
        out.sort(key=lambda x: x.ts or now_beijing(), reverse=True)
        return out

    def delete(self, fact_id: str) -> bool:
        """
        功能：逻辑删除一条提醒事实。
        输入：提醒 ID `fact_id`。
        输出：删除成功返回 `True`，否则返回 `False`。
        """
        fact = self._facts.get(fact_id)
        if fact is None:
            return False
        self._facts[fact_id] = fact.model_copy(update={"status": "deleted"})
        self._persist()
        return True

    def get(self, fact_id: str) -> ReminderFact | None:
        """
        功能：按 ID 获取单条提醒事实。
        输入：提醒 ID `fact_id`。
        输出：命中时返回提醒事实，否则返回 `None`。
        """
        return self._facts.get(fact_id)
