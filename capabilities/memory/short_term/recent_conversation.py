from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from threading import Lock

from foundation.config import MAMGA_RECENT_CONVERSATION_PATH
from foundation.time_utils import now_beijing

_STORE_LOCK = Lock()
_MAX_INJECTED_MESSAGES = 3
_SHORT_TERM_CONTEXT = ""


def _base_store_path() -> Path:
    """
    功能：返回短期对话缓存的基础路径配置。
    输入：无。
    输出：配置中的路径对象。
    """
    return Path(MAMGA_RECENT_CONVERSATION_PATH)


def _store_dir() -> Path:
    """
    功能：返回短期对话缓存目录。
    输入：无。
    输出：用于存放每日 JSONL 的目录路径。
    """
    return _base_store_path()


def _store_path(target_date: datetime | None = None) -> Path:
    """
    功能：返回指定日期对应的短期对话缓存文件路径。
    输入：可选日期时间 `target_date`。
    输出：当天 JSONL 缓存文件路径。
    """
    current = target_date or now_beijing()
    return _store_dir() / f"{current.date().isoformat()}.jsonl"


def _normalize_message(text: str) -> str:
    """
    功能：清洗一段短期对话文本。
    输入：原始文本 `text`。
    输出：去掉空行后的标准化文本。
    """
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    return "\n".join(lines)


def _parse_message_record(text: str) -> dict[str, str]:
    """
    功能：把单段对话文本解析成短期记忆记录。
    输入：原始对话文本 `text`。
    输出：包含 `user / assistant / ts` 的短期记忆记录。
    """
    normalized = _normalize_message(text)
    user_lines: list[str] = []
    assistant_lines: list[str] = []
    current_role = ""
    for line in normalized.splitlines():
        if line.startswith("用户:"):
            current_role = "user"
            content = line.split(":", 1)[1].strip()
            if content:
                user_lines.append(content)
            continue
        if line.startswith("助手:"):
            current_role = "assistant"
            content = line.split(":", 1)[1].strip()
            if content:
                assistant_lines.append(content)
            continue
        if current_role == "user":
            user_lines.append(line)
        elif current_role == "assistant":
            assistant_lines.append(line)
    return {
        "user": "\n".join(user_lines).strip(),
        "assistant": "\n".join(assistant_lines).strip(),
        "ts": now_beijing().isoformat(),
    }


def _load_messages() -> list[dict[str, str]]:
    """
    功能：读取当天的短期对话列表。
    输入：无。
    输出：短期对话列表；读取失败时返回空列表。
    """
    path = _store_path()
    if not path.exists():
        return []
    messages: list[dict[str, str]] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for raw in f:
                text = raw.strip()
                if not text:
                    continue
                try:
                    obj = json.loads(text)
                except Exception:
                    continue
                if not isinstance(obj, dict):
                    continue
                user_text = _normalize_message(str(obj.get("user", "")))
                assistant_text = _normalize_message(str(obj.get("assistant", "")))
                if not user_text and not assistant_text:
                    legacy_text = _normalize_message(str(obj.get("text", "")))
                    if not legacy_text:
                        continue
                    parsed = _parse_message_record(legacy_text)
                    user_text = parsed["user"]
                    assistant_text = parsed["assistant"]
                if not user_text and not assistant_text:
                    continue
                messages.append(
                    {
                        "ts": str(obj.get("ts", "")).strip(),
                        "user": user_text,
                        "assistant": assistant_text,
                    }
                )
    except Exception:
        return []
    return messages


def _append_message_record(message: dict[str, str]) -> None:
    """
    功能：向当天短期对话文件追加一行 JSONL 记录。
    输入：单条短期对话记录 `message`。
    输出：无，副作用是追加写入当天 JSONL 文件。
    """
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(message, ensure_ascii=False) + "\n")


def _render_recent_messages(messages: list[dict[str, str]]) -> str:
    """
    功能：把最近几条短期对话渲染成可注入 Prompt 的文本。
    输入：短期对话列表 `messages`。
    输出：短期上下文文本；无内容时返回空字符串。
    """
    lines: list[str] = []
    for item in messages[-_MAX_INJECTED_MESSAGES:]:
        user_text = str(item.get("user", "")).strip()
        assistant_text = str(item.get("assistant", "")).strip()
        if user_text:
            lines.append(f"用户: {user_text}")
        if assistant_text:
            lines.append(f"助手: {assistant_text}")
    return "\n".join(lines)


def build_recent_conversation() -> str:
    """
    功能：读取当天 JSONL 文件中的短期对话并输出文本。
    输入：无。
    输出：可直接注入 Prompt 的最近对话文本；无内容时返回空字符串。
    """
    global _SHORT_TERM_CONTEXT
    with _STORE_LOCK:
        if _SHORT_TERM_CONTEXT == "":
            _SHORT_TERM_CONTEXT = _load_messages()
    return _render_recent_messages(_SHORT_TERM_CONTEXT)


def append_recent_conversation(text: str) -> None:
    """
    功能：向当天短期记忆追加一段对话文本。
    输入：单段短期对话文本 `text`。
    输出：无，副作用是把改写后的 JSON 记录追加写入当天文件。
    """

    global _SHORT_TERM_CONTEXT
    message = _parse_message_record(text)
    if not message["user"] and not message["assistant"]:
        return
    with _STORE_LOCK:
        _SHORT_TERM_CONTEXT.append(message)
        _append_message_record(message)
