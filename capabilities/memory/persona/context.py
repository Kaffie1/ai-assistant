from __future__ import annotations

import json
from pathlib import Path
from threading import Lock

from foundation.config import MAMGA_PROFILE_MEMORY_PATH

_STORE_LOCK = Lock()
_PERSONA_CONTEXT: list[str] = []


def _store_path() -> Path:
    """
    功能：返回画像记忆统一 JSON 文件路径。
    输入：无。
    输出：画像记忆文件路径。
    """
    return Path(MAMGA_PROFILE_MEMORY_PATH)


def _normalize_persona_text(text: str) -> str:
    """
    功能：清洗一条画像文本。
    输入：原始画像文本 `text`。
    输出：去掉空行后的标准化文本。
    """
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    return "\n".join(lines)


def _load_persona_lines() -> list[str]:
    """
    功能：从统一 JSON 文件读取画像内容。
    输入：无。
    输出：画像文本列表；读取失败时返回空列表。
    """
    path = _store_path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    lines: list[str] = []
    for item in payload:
        text = _normalize_persona_text(str(item))
        if text:
            lines.append(text)
    return lines


def _save_persona_lines(lines: list[str]) -> None:
    """
    功能：把画像内容全量写回统一 JSON 文件。
    输入：画像文本列表 `lines`。
    输出：无，副作用是覆盖写入画像文件。
    """
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(lines, ensure_ascii=False, indent=2))


def _delete_persona_line(index: int) -> bool:
    """
    功能：按序号删除一条画像内容。
    输入：1-based 序号 `index`。
    输出：是否删除成功。
    """
    lines = _load_persona_lines()
    if index < 1 or index > len(lines):
        return False
    del lines[index - 1]
    _save_persona_lines(lines)
    return True


def build_persona_memory_context() -> str:
    """
    功能：读取画像 JSON 文件并输出文本。
    输入：无。
    输出：画像上下文文本；无内容时返回空字符串。
    """

    global _PERSONA_CONTEXT
    with _STORE_LOCK:
        if not _PERSONA_CONTEXT:
            _PERSONA_CONTEXT = _load_persona_lines()
    return "\n".join(_PERSONA_CONTEXT)


def append_persona_memory(text: str) -> None:
    """
    功能：向统一画像 JSON 文件追加一条画像内容。
    输入：画像文本 `text`。
    输出：无，副作用是把画像内容追加写入 JSON 文件。
    """

    global _PERSONA_CONTEXT
    line = _normalize_persona_text(text)
    if not line:
        return
    with _STORE_LOCK:
        if not _PERSONA_CONTEXT:
            _PERSONA_CONTEXT = _load_persona_lines()
        _PERSONA_CONTEXT.append(line)
        _save_persona_lines(_PERSONA_CONTEXT)
