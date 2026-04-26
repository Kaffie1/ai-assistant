from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AudioInput:
    """
    功能：描述一次待转写的音频输入。
    输入：文件名、内容类型、原始字节以及可选音频元信息。
    输出：结构化音频输入对象。
    """

    filename: str
    content_type: str
    data: bytes
    sample_rate: int | None = None
    channels: int | None = None


@dataclass(slots=True)
class ASRResult:
    """
    功能：描述一次语音识别结果。
    输入：识别文本、提供方、语言、耗时和原始返回。
    输出：结构化 ASR 结果对象。
    """

    text: str
    provider: str = ""
    language: str = ""
    duration_ms: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)
