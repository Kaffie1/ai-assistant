from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from capabilities.memory.long_term.types import MemoryNode
from foundation.config import MAMGA_LONG_TERM_MEMORY_DB_PATH
from foundation.time_utils import now_beijing


def _long_term_db_path() -> Path:
    """
    功能：返回长期记忆 SQLite 持久化文件路径。
    输入：无。
    输出：长期记忆 SQLite 文件路径。
    """
    return Path(MAMGA_LONG_TERM_MEMORY_DB_PATH)


def _normalize_text(text: str) -> str:
    """
    功能：归一化长期记忆文本，用于内容去重。
    输入：原始文本 `text`。
    输出：压缩空白后的标准化文本。
    """
    return " ".join(str(text or "").strip().lower().split())


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """
    功能：确保长期记忆所需的 SQLite 表结构存在。
    输入：数据库连接 `conn`。
    输出：无。
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS long_term_nodes (
            id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            normalized_text TEXT NOT NULL,
            kind TEXT NOT NULL,
            source TEXT NOT NULL,
            ts TEXT NOT NULL,
            last_seen_ts TEXT,
            importance REAL NOT NULL,
            hit_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            tags_json TEXT NOT NULL,
            metadata_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS long_term_edges (
            edge_id TEXT PRIMARY KEY,
            source_node_id TEXT NOT NULL,
            target_node_id TEXT NOT NULL,
            relation TEXT NOT NULL,
            weight REAL NOT NULL DEFAULT 1.0,
            ts TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_long_term_nodes_status_ts ON long_term_nodes(status, ts DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_long_term_nodes_normalized_text ON long_term_nodes(normalized_text)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_long_term_edges_source ON long_term_edges(source_node_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_long_term_edges_target ON long_term_edges(target_node_id)")
    conn.commit()


def _connect() -> sqlite3.Connection:
    """
    功能：创建长期记忆 SQLite 连接并初始化表结构。
    输入：无。
    输出：SQLite 连接对象。
    """
    path = _long_term_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def _row_to_node(row: sqlite3.Row | None) -> MemoryNode | None:
    """
    功能：把 SQLite 行对象转换为长期记忆节点。
    输入：数据库行 `row`。
    输出：长期记忆节点对象；空行返回 `None`。
    """
    if row is None:
        return None
    try:
        tags = json.loads(str(row["tags_json"] or "[]"))
        if not isinstance(tags, list):
            tags = []
    except Exception:
        tags = []
    try:
        metadata = json.loads(str(row["metadata_json"] or "{}"))
        if not isinstance(metadata, dict):
            metadata = {}
    except Exception:
        metadata = {}
    return MemoryNode(
        id=str(row["id"] or ""),
        text=str(row["text"] or ""),
        kind=str(row["kind"] or "fact"),
        source=str(row["source"] or "chat"),
        ts=datetime.fromisoformat(str(row["ts"])),
        last_seen_ts=datetime.fromisoformat(str(row["last_seen_ts"])) if row["last_seen_ts"] else None,
        importance=float(row["importance"] or 0.5),
        hit_count=int(row["hit_count"] or 0),
        tags=[str(item).strip() for item in tags if str(item).strip()],
        status=str(row["status"] or "active"),
        metadata=metadata,
    )


def _next_node_id(conn: sqlite3.Connection) -> str:
    """
    功能：生成下一个长期记忆节点 ID。
    输入：数据库连接 `conn`。
    输出：节点 ID 字符串。
    """
    row = conn.execute("SELECT id FROM long_term_nodes WHERE id LIKE 'lt_%' ORDER BY id DESC LIMIT 1").fetchone()
    if row is None:
        return "lt_000001"
    try:
        current = int(str(row["id"]).split("_", 1)[1])
    except Exception:
        current = 0
    return f"lt_{current + 1:06d}"


class InMemoryLongTermStore:
    def __init__(self) -> None:
        """
        功能：初始化长期记忆 SQLite 存储。
        输入：无。
        输出：无。
        """
        self._db_path = _long_term_db_path()
        with _connect():
            pass

    def upsert(self, node: MemoryNode) -> MemoryNode:
        """
        功能：写入或更新长期记忆节点，并按文本做简单去重。
        输入：节点对象 `node`。
        输出：最终保存的节点对象。
        """
        normalized = _normalize_text(node.text)
        with _connect() as conn:
            existing = conn.execute(
                """
                SELECT *
                FROM long_term_nodes
                WHERE normalized_text = ?
                ORDER BY ts DESC, id DESC
                LIMIT 1
                """,
                (normalized,),
            ).fetchone()
            old = _row_to_node(existing)
            if old is not None:
                merged = old.model_copy(
                    update={
                        "kind": node.kind or old.kind,
                        "source": node.source or old.source,
                        "importance": max(old.importance, node.importance),
                        "hit_count": max(old.hit_count, node.hit_count),
                        "tags": sorted(set(old.tags).union(node.tags)),
                        "status": node.status or old.status,
                        "metadata": {**old.metadata, **node.metadata},
                        "last_seen_ts": node.last_seen_ts or old.last_seen_ts,
                    }
                )
                conn.execute(
                    """
                    UPDATE long_term_nodes
                    SET text = ?, normalized_text = ?, kind = ?, source = ?, ts = ?, last_seen_ts = ?,
                        importance = ?, hit_count = ?, status = ?, tags_json = ?, metadata_json = ?
                    WHERE id = ?
                    """,
                    (
                        merged.text,
                        normalized,
                        merged.kind,
                        merged.source,
                        merged.ts.isoformat(),
                        merged.last_seen_ts.isoformat() if merged.last_seen_ts else None,
                        merged.importance,
                        merged.hit_count,
                        merged.status,
                        json.dumps(merged.tags, ensure_ascii=False),
                        json.dumps(merged.metadata, ensure_ascii=False),
                        merged.id,
                    ),
                )
                conn.commit()
                return merged

            node_id = node.id or _next_node_id(conn)
            created = MemoryNode(
                id=node_id,
                text=str(node.text or "").strip(),
                kind=node.kind or "fact",
                source=node.source or "chat",
                ts=node.ts,
                last_seen_ts=node.last_seen_ts,
                importance=node.importance,
                hit_count=node.hit_count,
                tags=list(node.tags),
                status=node.status or "active",
                metadata=dict(node.metadata),
            )
            conn.execute(
                """
                INSERT INTO long_term_nodes (
                    id, text, normalized_text, kind, source, ts, last_seen_ts,
                    importance, hit_count, status, tags_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created.id,
                    created.text,
                    normalized,
                    created.kind,
                    created.source,
                    created.ts.isoformat(),
                    created.last_seen_ts.isoformat() if created.last_seen_ts else None,
                    created.importance,
                    created.hit_count,
                    created.status,
                    json.dumps(created.tags, ensure_ascii=False),
                    json.dumps(created.metadata, ensure_ascii=False),
                ),
            )
            conn.commit()
            return created

    def list_active(self) -> list[MemoryNode]:
        """
        功能：返回所有 active 长期记忆节点。
        输入：无。
        输出：按创建时间倒序排列的 active 节点列表。
        """
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM long_term_nodes
                WHERE status = 'active' AND text != ''
                ORDER BY ts DESC, id DESC
                """
            ).fetchall()
        return [node for row in rows if (node := _row_to_node(row)) is not None]

    def get(self, node_id: str) -> MemoryNode | None:
        """
        功能：按 ID 获取长期记忆节点。
        输入：节点 ID `node_id`。
        输出：节点对象或 `None`。
        """
        with _connect() as conn:
            row = conn.execute("SELECT * FROM long_term_nodes WHERE id = ?", (node_id,)).fetchone()
        return _row_to_node(row)

    def touch(self, node_id: str, seen_at: datetime | None = None) -> MemoryNode | None:
        """
        功能：更新节点最近命中时间和命中次数。
        输入：节点 ID `node_id`、命中时间 `seen_at`。
        输出：更新后的节点对象；不存在时返回 `None`。
        """
        current = self.get(node_id)
        if current is None:
            return None
        when = seen_at or now_beijing()
        updated = current.model_copy(update={"last_seen_ts": when, "hit_count": current.hit_count + 1})
        normalized = _normalize_text(updated.text)
        with _connect() as conn:
            conn.execute(
                """
                UPDATE long_term_nodes
                SET last_seen_ts = ?, hit_count = ?, normalized_text = ?
                WHERE id = ?
                """,
                (when.isoformat(), updated.hit_count, normalized, node_id),
            )
            conn.commit()
        return updated

    def get_node(self, node_id: str) -> MemoryNode | None:
        """
        功能：作为检索图接口返回节点对象。
        输入：节点 ID `node_id`。
        输出：节点对象或 `None`。
        """
        return self.get(node_id)

    def expand(self, seed_ids: list[str], hops: int = 1) -> dict[str, float]:
        """
        功能：基于边表返回种子节点的轻量图扩展结果。
        输入：种子节点 ID 列表 `seed_ids`、跳数 `hops`。
        输出：邻接节点权重映射。
        """
        if not seed_ids or hops <= 0:
            return {}
        frontier = {node_id for node_id in seed_ids if node_id}
        visited = set(frontier)
        scores: dict[str, float] = {}
        with _connect() as conn:
            for depth in range(max(1, hops)):
                if not frontier:
                    break
                placeholders = ", ".join("?" for _ in frontier)
                rows = conn.execute(
                    f"""
                    SELECT source_node_id, target_node_id, weight
                    FROM long_term_edges
                    WHERE source_node_id IN ({placeholders})
                    """,
                    tuple(frontier),
                ).fetchall()
                next_frontier: set[str] = set()
                for row in rows:
                    target_id = str(row["target_node_id"] or "").strip()
                    if not target_id or target_id in visited:
                        continue
                    weight = float(row["weight"] or 1.0) / float(depth + 1)
                    scores[target_id] = max(scores.get(target_id, 0.0), weight)
                    next_frontier.add(target_id)
                visited.update(next_frontier)
                frontier = next_frontier
        return scores
