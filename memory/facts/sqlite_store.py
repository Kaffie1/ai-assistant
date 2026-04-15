from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone

from ..models.schemas import KnowledgeFact, ProfileFact, TaskFact


def _utc_now_iso() -> str:
    """
    功能：返回 UTC 当前时间 ISO 字符串。
    输入：无。
    输出：UTC 时间字符串。
    """
    return datetime.now(timezone.utc).isoformat()


def _norm_text(text: str) -> str:
    """
    功能：标准化文本用于去重。
    输入：原始文本 `text`。
    输出：规范化后的字符串。
    """
    return " ".join(text.strip().lower().split())


class _SQLiteBase:
    def __init__(self, db_path: str) -> None:
        """
        功能：初始化 SQLite 基类。
        输入：数据库路径 `db_path`。
        输出：无，确保目录存在并初始化 schema。
        """
        self.db_path = db_path
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        """
        功能：创建数据库连接。
        输入：无。
        输出：配置 row_factory 的 SQLite 连接。
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _has_column(self, table: str, column: str) -> bool:
        """
        功能：判断表中是否存在指定列。
        输入：表名 `table`，列名 `column`。
        输出：存在返回 True，否则 False。
        """
        with self._conn() as conn:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return any(r["name"] == column for r in rows)

    def _column_count(self, table: str) -> int:
        """
        功能：返回表的列数量。
        输入：表名 `table`。
        输出：整数列数。
        """
        with self._conn() as conn:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return len(rows)

    def _init_schema(self) -> None:
        raise NotImplementedError

    def _ensure_table(self, table: str) -> None:
        """
        功能：确保目标表存在（用于数据库文件被删除后的自恢复）。
        输入：表名 `table`。
        输出：无，若缺表则自动重建 schema。
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
        if row is None:
            self._init_schema()


class SQLiteProfileStore(_SQLiteBase):
    def _init_schema(self) -> None:
        """
        功能：创建画像表并执行旧结构迁移。
        输入：无。
        输出：无。
        """
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS profile_facts (
                    id TEXT PRIMARY KEY,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    source TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_profile_key ON profile_facts(key)")

        # Old schema migration: previous version had one extra identity column.
        if self._column_count("profile_facts") > 7:
            with self._conn() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS profile_facts_new (
                        id TEXT PRIMARY KEY,
                        key TEXT NOT NULL,
                        value TEXT NOT NULL,
                        confidence REAL NOT NULL,
                        source TEXT NOT NULL,
                        ts TEXT NOT NULL,
                        status TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO profile_facts_new(id, key, value, confidence, source, ts, status)
                    SELECT id, key, value, confidence, source, ts, status FROM profile_facts
                    """
                )
                conn.execute("DROP TABLE profile_facts")
                conn.execute("ALTER TABLE profile_facts_new RENAME TO profile_facts")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_profile_key ON profile_facts(key)")

    def upsert(self, fact: ProfileFact) -> ProfileFact:
        """
        功能：按 key 写入或更新画像事实。
        输入：画像事实 `fact`。
        输出：落库后的画像事实。
        """
        self._ensure_table("profile_facts")
        now = _utc_now_iso()
        with self._conn() as conn:
            if fact.id:
                row = conn.execute("SELECT * FROM profile_facts WHERE id = ?", (fact.id,)).fetchone()
                if row:
                    conn.execute(
                        """
                        UPDATE profile_facts
                        SET value=?, confidence=?, source=?, ts=?, status=?
                        WHERE id=?
                        """,
                        (
                            fact.value,
                            float(fact.confidence),
                            fact.source,
                            fact.ts.isoformat() if fact.ts else now,
                            fact.status,
                            fact.id,
                        ),
                    )
                    return fact

            row = conn.execute(
                """
                SELECT * FROM profile_facts
                WHERE key=? AND status='active'
                ORDER BY ts DESC LIMIT 1
                """,
                (fact.key,),
            ).fetchone()
            if row:
                old_conf = float(row["confidence"])
                if fact.confidence >= old_conf or fact.source == "user_feedback":
                    conn.execute(
                        """
                        UPDATE profile_facts
                        SET value=?, confidence=?, source=?, ts=?, status='active'
                        WHERE id=?
                        """,
                        (
                            fact.value,
                            float(fact.confidence),
                            fact.source,
                            fact.ts.isoformat() if fact.ts else now,
                            row["id"],
                        ),
                    )
                    return ProfileFact(
                        id=row["id"],
                        key=fact.key,
                        value=fact.value,
                        confidence=fact.confidence,
                        source=fact.source,
                        ts=fact.ts,
                        status="active",
                    )
                return ProfileFact(
                    id=row["id"],
                    key=row["key"],
                    value=row["value"],
                    confidence=old_conf,
                    source=row["source"],
                    ts=datetime.fromisoformat(row["ts"]),
                    status=row["status"],
                )

            fact_id = fact.id or f"pf_{uuid.uuid4().hex[:12]}"
            ts = fact.ts.isoformat() if fact.ts else now
            conn.execute(
                """
                INSERT INTO profile_facts(id, key, value, confidence, source, ts, status)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fact_id,
                    fact.key,
                    fact.value,
                    float(fact.confidence),
                    fact.source,
                    ts,
                    fact.status,
                ),
            )
            return ProfileFact(
                id=fact_id,
                key=fact.key,
                value=fact.value,
                confidence=fact.confidence,
                source=fact.source,
                ts=datetime.fromisoformat(ts),
                status=fact.status,
            )

    def list(self) -> list[ProfileFact]:
        """
        功能：列出 active 画像事实。
        输入：无。
        输出：画像事实列表。
        """
        self._ensure_table("profile_facts")
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM profile_facts
                WHERE status='active'
                ORDER BY ts DESC
                """
            ).fetchall()
        return [
            ProfileFact(
                id=r["id"],
                key=r["key"],
                value=r["value"],
                confidence=float(r["confidence"]),
                source=r["source"],
                ts=datetime.fromisoformat(r["ts"]),
                status=r["status"],
            )
            for r in rows
        ]

    def delete(self, fact_id: str) -> bool:
        """
        功能：软删除画像事实。
        输入：事实 ID `fact_id`。
        输出：删除成功返回 True，否则 False。
        """
        self._ensure_table("profile_facts")
        with self._conn() as conn:
            cur = conn.execute("UPDATE profile_facts SET status='deleted' WHERE id=?", (fact_id,))
            return cur.rowcount > 0

    def get(self, fact_id: str) -> ProfileFact | None:
        """
        功能：按 ID 获取画像事实。
        输入：事实 ID `fact_id`。
        输出：画像事实或 `None`。
        """
        self._ensure_table("profile_facts")
        with self._conn() as conn:
            r = conn.execute("SELECT * FROM profile_facts WHERE id=?", (fact_id,)).fetchone()
        if not r:
            return None
        return ProfileFact(
            id=r["id"],
            key=r["key"],
            value=r["value"],
            confidence=float(r["confidence"]),
            source=r["source"],
            ts=datetime.fromisoformat(r["ts"]),
            status=r["status"],
        )

    def downgrade_and_mark(self, fact_id: str, factor: float = 0.3, status: str = "superseded") -> bool:
        """
        功能：下调画像事实置信度并标记状态。
        输入：事实 ID、衰减因子、状态。
        输出：更新成功返回 True，否则 False。
        """
        self._ensure_table("profile_facts")
        with self._conn() as conn:
            row = conn.execute("SELECT confidence FROM profile_facts WHERE id=?", (fact_id,)).fetchone()
            if not row:
                return False
            new_conf = max(0.01, float(row["confidence"]) * factor)
            cur = conn.execute(
                "UPDATE profile_facts SET confidence=?, status=? WHERE id=?",
                (new_conf, status, fact_id),
            )
            return cur.rowcount > 0

    def list_history(self, key: str) -> list[ProfileFact]:
        """
        功能：按 key 查询画像历史。
        输入：画像键 `key`。
        输出：历史事实列表。
        """
        self._ensure_table("profile_facts")
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM profile_facts
                WHERE key=?
                ORDER BY ts DESC
                """,
                (key,),
            ).fetchall()
        return [
            ProfileFact(
                id=r["id"],
                key=r["key"],
                value=r["value"],
                confidence=float(r["confidence"]),
                source=r["source"],
                ts=datetime.fromisoformat(r["ts"]),
                status=r["status"],
            )
            for r in rows
        ]


class SQLiteKnowledgeStore(_SQLiteBase):
    def _init_schema(self) -> None:
        """
        功能：创建知识表并执行旧结构迁移。
        输入：无。
        输出：无。
        """
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_facts (
                    id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    statement TEXT NOT NULL,
                    statement_norm TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    source TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    status TEXT NOT NULL,
                    version INTEGER NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_norm ON knowledge_facts(statement_norm)")

        if self._column_count("knowledge_facts") > 10:
            with self._conn() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS knowledge_facts_new (
                        id TEXT PRIMARY KEY,
                        topic TEXT NOT NULL,
                        statement TEXT NOT NULL,
                        statement_norm TEXT NOT NULL,
                        confidence REAL NOT NULL,
                        source TEXT NOT NULL,
                        evidence_json TEXT NOT NULL,
                        ts TEXT NOT NULL,
                        status TEXT NOT NULL,
                        version INTEGER NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO knowledge_facts_new(id, topic, statement, statement_norm, confidence, source, evidence_json, ts, status, version)
                    SELECT id, topic, statement, statement_norm, confidence, source, evidence_json, ts, status, version
                    FROM knowledge_facts
                    """
                )
                conn.execute("DROP TABLE knowledge_facts")
                conn.execute("ALTER TABLE knowledge_facts_new RENAME TO knowledge_facts")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_norm ON knowledge_facts(statement_norm)")

    def upsert(self, fact: KnowledgeFact) -> KnowledgeFact:
        """
        功能：按规范化 statement 写入或合并知识事实。
        输入：知识事实 `fact`。
        输出：落库后的知识事实。
        """
        self._ensure_table("knowledge_facts")
        now = _utc_now_iso()
        norm = _norm_text(fact.statement)
        with self._conn() as conn:
            if fact.id:
                row = conn.execute("SELECT * FROM knowledge_facts WHERE id=?", (fact.id,)).fetchone()
                if row:
                    conn.execute(
                        """
                        UPDATE knowledge_facts
                        SET topic=?, statement=?, statement_norm=?, confidence=?, source=?, evidence_json=?, ts=?, status=?, version=?
                        WHERE id=?
                        """,
                        (
                            fact.topic,
                            fact.statement,
                            norm,
                            float(fact.confidence),
                            fact.source,
                            json.dumps(fact.evidence, ensure_ascii=False),
                            fact.ts.isoformat() if fact.ts else now,
                            fact.status,
                            int(fact.version),
                            fact.id,
                        ),
                    )
                    return fact

            row = conn.execute(
                """
                SELECT * FROM knowledge_facts
                WHERE statement_norm=? AND status='active'
                ORDER BY ts DESC LIMIT 1
                """,
                (norm,),
            ).fetchone()
            if row:
                merged_conf = max(float(row["confidence"]), float(fact.confidence))
                old_evidence = json.loads(row["evidence_json"]) if row["evidence_json"] else []
                merged_evidence = list(dict.fromkeys([*old_evidence, *fact.evidence]))
                new_version = int(row["version"]) + 1
                conn.execute(
                    """
                    UPDATE knowledge_facts
                    SET topic=?, confidence=?, source=?, evidence_json=?, ts=?, status='active', version=?
                    WHERE id=?
                    """,
                    (
                        fact.topic or row["topic"],
                        merged_conf,
                        fact.source,
                        json.dumps(merged_evidence, ensure_ascii=False),
                        fact.ts.isoformat() if fact.ts else now,
                        new_version,
                        row["id"],
                    ),
                )
                return KnowledgeFact(
                    id=row["id"],
                    topic=fact.topic or row["topic"],
                    statement=row["statement"],
                    confidence=merged_conf,
                    source=fact.source,
                    evidence=merged_evidence,
                    ts=fact.ts,
                    status="active",
                    version=new_version,
                )

            fact_id = fact.id or f"kf_{uuid.uuid4().hex[:12]}"
            ts = fact.ts.isoformat() if fact.ts else now
            conn.execute(
                """
                INSERT INTO knowledge_facts(id, topic, statement, statement_norm, confidence, source, evidence_json, ts, status, version)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fact_id,
                    fact.topic,
                    fact.statement,
                    norm,
                    float(fact.confidence),
                    fact.source,
                    json.dumps(fact.evidence, ensure_ascii=False),
                    ts,
                    fact.status,
                    int(fact.version),
                ),
            )
            return KnowledgeFact(
                id=fact_id,
                topic=fact.topic,
                statement=fact.statement,
                confidence=fact.confidence,
                source=fact.source,
                evidence=fact.evidence,
                ts=datetime.fromisoformat(ts),
                status=fact.status,
                version=fact.version,
            )

    def list(self) -> list[KnowledgeFact]:
        """
        功能：列出 active 知识事实。
        输入：无。
        输出：知识事实列表。
        """
        self._ensure_table("knowledge_facts")
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM knowledge_facts
                WHERE status='active'
                ORDER BY ts DESC
                """
            ).fetchall()
        return [
            KnowledgeFact(
                id=r["id"],
                topic=r["topic"],
                statement=r["statement"],
                confidence=float(r["confidence"]),
                source=r["source"],
                evidence=json.loads(r["evidence_json"]) if r["evidence_json"] else [],
                ts=datetime.fromisoformat(r["ts"]),
                status=r["status"],
                version=int(r["version"]),
            )
            for r in rows
        ]

    def delete(self, fact_id: str) -> bool:
        """
        功能：软删除知识事实。
        输入：事实 ID `fact_id`。
        输出：删除成功返回 True，否则 False。
        """
        self._ensure_table("knowledge_facts")
        with self._conn() as conn:
            cur = conn.execute("UPDATE knowledge_facts SET status='deleted' WHERE id=?", (fact_id,))
            return cur.rowcount > 0

    def get(self, fact_id: str) -> KnowledgeFact | None:
        """
        功能：按 ID 获取知识事实。
        输入：事实 ID `fact_id`。
        输出：知识事实或 `None`。
        """
        self._ensure_table("knowledge_facts")
        with self._conn() as conn:
            r = conn.execute("SELECT * FROM knowledge_facts WHERE id=?", (fact_id,)).fetchone()
        if not r:
            return None
        return KnowledgeFact(
            id=r["id"],
            topic=r["topic"],
            statement=r["statement"],
            confidence=float(r["confidence"]),
            source=r["source"],
            evidence=json.loads(r["evidence_json"]) if r["evidence_json"] else [],
            ts=datetime.fromisoformat(r["ts"]),
            status=r["status"],
            version=int(r["version"]),
        )

    def downgrade_and_mark(self, fact_id: str, factor: float = 0.3, status: str = "superseded") -> bool:
        """
        功能：下调知识事实置信度并标记状态。
        输入：事实 ID、衰减因子、状态。
        输出：更新成功返回 True，否则 False。
        """
        self._ensure_table("knowledge_facts")
        with self._conn() as conn:
            row = conn.execute(
                "SELECT confidence, version FROM knowledge_facts WHERE id=?",
                (fact_id,),
            ).fetchone()
            if not row:
                return False
            new_conf = max(0.01, float(row["confidence"]) * factor)
            new_ver = int(row["version"]) + 1
            cur = conn.execute(
                "UPDATE knowledge_facts SET confidence=?, status=?, version=? WHERE id=?",
                (new_conf, status, new_ver, fact_id),
            )
            return cur.rowcount > 0

    def list_history(self, topic: str) -> list[KnowledgeFact]:
        """
        功能：按 topic 查询知识历史。
        输入：主题 `topic`。
        输出：历史事实列表。
        """
        self._ensure_table("knowledge_facts")
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM knowledge_facts
                WHERE topic=?
                ORDER BY ts DESC
                """,
                (topic,),
            ).fetchall()
        return [
            KnowledgeFact(
                id=r["id"],
                topic=r["topic"],
                statement=r["statement"],
                confidence=float(r["confidence"]),
                source=r["source"],
                evidence=json.loads(r["evidence_json"]) if r["evidence_json"] else [],
                ts=datetime.fromisoformat(r["ts"]),
                status=r["status"],
                version=int(r["version"]),
            )
            for r in rows
        ]


class SQLiteTaskStore(_SQLiteBase):
    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_facts (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    content_norm TEXT NOT NULL,
                    due_date TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    source TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    status TEXT NOT NULL,
                    version INTEGER NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_task_norm ON task_facts(content_norm)")

    def upsert(self, fact: TaskFact) -> TaskFact:
        self._ensure_table("task_facts")
        now = _utc_now_iso()
        norm = _norm_text(fact.content)
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM task_facts
                WHERE content_norm=? AND status='active'
                ORDER BY ts DESC LIMIT 1
                """,
                (norm,),
            ).fetchone()
            if row:
                merged_conf = max(float(row["confidence"]), float(fact.confidence))
                old_evidence = json.loads(row["evidence_json"]) if row["evidence_json"] else []
                merged_evidence = list(dict.fromkeys([*old_evidence, *fact.evidence]))
                new_ver = int(row["version"]) + 1
                conn.execute(
                    """
                    UPDATE task_facts
                    SET due_date=?, confidence=?, source=?, evidence_json=?, ts=?, status='active', version=?
                    WHERE id=?
                    """,
                    (
                        fact.due_date or row["due_date"],
                        merged_conf,
                        fact.source,
                        json.dumps(merged_evidence, ensure_ascii=False),
                        fact.ts.isoformat() if fact.ts else now,
                        new_ver,
                        row["id"],
                    ),
                )
                return TaskFact(
                    id=row["id"],
                    content=row["content"],
                    due_date=fact.due_date or row["due_date"],
                    confidence=merged_conf,
                    source=fact.source,
                    evidence=merged_evidence,
                    ts=fact.ts,
                    status="active",
                    version=new_ver,
                )

            fact_id = fact.id or f"tf_{uuid.uuid4().hex[:12]}"
            ts = fact.ts.isoformat() if fact.ts else now
            conn.execute(
                """
                INSERT INTO task_facts(id, content, content_norm, due_date, confidence, source, evidence_json, ts, status, version)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fact_id,
                    fact.content,
                    norm,
                    fact.due_date,
                    float(fact.confidence),
                    fact.source,
                    json.dumps(fact.evidence, ensure_ascii=False),
                    ts,
                    fact.status,
                    int(fact.version),
                ),
            )
            return TaskFact(
                id=fact_id,
                content=fact.content,
                due_date=fact.due_date,
                confidence=fact.confidence,
                source=fact.source,
                evidence=fact.evidence,
                ts=datetime.fromisoformat(ts),
                status=fact.status,
                version=fact.version,
            )

    def list(self) -> list[TaskFact]:
        self._ensure_table("task_facts")
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM task_facts
                WHERE status='active'
                ORDER BY ts DESC
                """
            ).fetchall()
        return [
            TaskFact(
                id=r["id"],
                content=r["content"],
                due_date=r["due_date"],
                confidence=float(r["confidence"]),
                source=r["source"],
                evidence=json.loads(r["evidence_json"]) if r["evidence_json"] else [],
                ts=datetime.fromisoformat(r["ts"]),
                status=r["status"],
                version=int(r["version"]),
            )
            for r in rows
        ]

    def delete(self, fact_id: str) -> bool:
        self._ensure_table("task_facts")
        with self._conn() as conn:
            cur = conn.execute("UPDATE task_facts SET status='deleted' WHERE id=?", (fact_id,))
            return cur.rowcount > 0

    def get(self, fact_id: str) -> TaskFact | None:
        self._ensure_table("task_facts")
        with self._conn() as conn:
            r = conn.execute("SELECT * FROM task_facts WHERE id=?", (fact_id,)).fetchone()
        if not r:
            return None
        return TaskFact(
            id=r["id"],
            content=r["content"],
            due_date=r["due_date"],
            confidence=float(r["confidence"]),
            source=r["source"],
            evidence=json.loads(r["evidence_json"]) if r["evidence_json"] else [],
            ts=datetime.fromisoformat(r["ts"]),
            status=r["status"],
            version=int(r["version"]),
        )

    def mark_done(self, fact_id: str) -> bool:
        self._ensure_table("task_facts")
        with self._conn() as conn:
            row = conn.execute("SELECT version FROM task_facts WHERE id=?", (fact_id,)).fetchone()
            if not row:
                return False
            new_ver = int(row["version"]) + 1
            cur = conn.execute(
                "UPDATE task_facts SET status='done', version=? WHERE id=?",
                (new_ver, fact_id),
            )
            return cur.rowcount > 0

    def list_history(self) -> list[TaskFact]:
        self._ensure_table("task_facts")
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM task_facts
                ORDER BY ts DESC
                """
            ).fetchall()
        return [
            TaskFact(
                id=r["id"],
                content=r["content"],
                due_date=r["due_date"],
                confidence=float(r["confidence"]),
                source=r["source"],
                evidence=json.loads(r["evidence_json"]) if r["evidence_json"] else [],
                ts=datetime.fromisoformat(r["ts"]),
                status=r["status"],
                version=int(r["version"]),
            )
            for r in rows
        ]
