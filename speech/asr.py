from __future__ import annotations

import json
import mimetypes
import uuid
from dataclasses import asdict
from time import perf_counter
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from foundation.config import MAMGA_ASR_API_KEY, MAMGA_ASR_BASE_URL, MAMGA_ASR_MODEL, MAMGA_ASR_PROVIDER
from .schemas import ASRResult, AudioInput


class ASRProvider(Protocol):
    """
    功能：约束语音识别提供方接口。
    输入：音频输入对象。
    输出：结构化语音识别结果。
    """

    @property
    def name(self) -> str:
        """返回语音识别提供方名称。"""
        ...

    def transcribe(self, audio: AudioInput) -> ASRResult:
        """执行音频转写。"""
        ...

def _guess_content_type(filename: str, content_type: str) -> str:
    """
    功能：为音频输入推断可用的内容类型。
    输入：文件名 `filename` 和原始内容类型 `content_type`。
    输出：最终使用的 MIME 类型。
    """

    if content_type.strip():
        return content_type.strip()
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def _build_multipart_body(fields: dict[str, str], files: list[tuple[str, str, str, bytes]]) -> tuple[bytes, str]:
    """
    功能：构造 multipart/form-data 请求体。
    输入：普通字段字典 `fields` 与文件列表 `files`。
    输出：`(body, content_type)` 元组。
    """

    boundary = f"----MamgaASR{uuid.uuid4().hex}"
    body = bytearray()

    for key, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")

    for field_name, filename, content_type, data in files:
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8")
        )
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        body.extend(data)
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def _safe_json_loads(text: str) -> dict[str, Any]:
    """
    功能：安全解析 JSON 文本。
    输入：原始文本 `text`。
    输出：字典结果；失败时返回空字典。
    """

    try:
        obj = json.loads(text)
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


class OpenAICompatibleASRClient:
    """
    功能：调用 OpenAI 兼容语音识别接口执行音频转写。
    输入：构造时提供 base_url、api_key、model。
    输出：可调用的 ASR 客户端。
    """

    def __init__(self, *, base_url: str, api_key: str, model: str, provider_name: str = "openai") -> None:
        """
        功能：初始化 OpenAI 兼容 ASR 客户端。
        输入：基础地址、密钥、模型名和提供方名称。
        输出：无。
        """

        self._base_url = base_url.rstrip("/") + "/"
        self._api_key = api_key
        self._model = model
        self._provider_name = provider_name

    @property
    def name(self) -> str:
        """
        功能：返回当前语音识别提供方名称。
        输入：无。
        输出：提供方名称字符串。
        """

        return self._provider_name

    def transcribe(self, audio: AudioInput) -> ASRResult:
        """
        功能：调用云端 ASR 将音频转成文字。
        输入：音频输入对象 `audio`。
        输出：结构化识别结果 `ASRResult`。
        """

        endpoint = urljoin(self._base_url, "audio/transcriptions")
        content_type = _guess_content_type(audio.filename, audio.content_type)
        body, request_content_type = _build_multipart_body(
            fields={"model": self._model},
            files=[("file", audio.filename, content_type, audio.data)],
        )
        request = Request(
            endpoint,
            method="POST",
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": request_content_type,
                "Accept": "application/json",
            },
        )

        start = perf_counter()
        try:
            with urlopen(request, timeout=60) as resp:
                payload = resp.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else str(exc)
            raise RuntimeError(f"asr_http_error:{exc.code}:{detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"asr_network_error:{exc.reason}") from exc
        except Exception as exc:
            raise RuntimeError(f"asr_request_error:{type(exc).__name__}:{exc}") from exc

        duration_ms = (perf_counter() - start) * 1000.0
        obj = _safe_json_loads(payload)
        text = str(obj.get("text", "")).strip()
        language = str(obj.get("language", "")).strip()
        return ASRResult(
            text=text,
            provider=self.name,
            language=language,
            duration_ms=round(duration_ms, 2),
            raw=obj,
        )


def build_asr_client_from_env() -> ASRProvider | None:
    """
    功能：根据统一配置常量构建云端 ASR 客户端。
    输入：无。
    输出：可用的 ASR 客户端；缺少关键配置时返回 `None`。
    """

    if not MAMGA_ASR_API_KEY:
        return None

    if MAMGA_ASR_PROVIDER in {"openai", "openai_compatible"}:
        return OpenAICompatibleASRClient(
            base_url=MAMGA_ASR_BASE_URL or "https://api.openai.com/v1",
            api_key=MAMGA_ASR_API_KEY,
            model=MAMGA_ASR_MODEL,
            provider_name=MAMGA_ASR_PROVIDER,
        )
    return None


def transcribe_audio(
    *,
    audio_bytes: bytes,
    filename: str,
    content_type: str = "",
    sample_rate: int | None = None,
    channels: int | None = None,
    client: ASRProvider | None = None,
) -> ASRResult:
    """
    功能：对音频字节执行语音识别。
    输入：音频字节、文件名、内容类型和可选 ASR 客户端。
    输出：识别结果；若无可用客户端则抛出异常。
    """

    provider = client or build_asr_client_from_env()
    if provider is None:
        raise RuntimeError("asr_unavailable")
    audio = AudioInput(
        filename=filename,
        content_type=content_type,
        data=audio_bytes,
        sample_rate=sample_rate,
        channels=channels,
    )
    return provider.transcribe(audio)


def asr_result_to_dict(result: ASRResult) -> dict[str, Any]:
    """
    功能：把 ASR 结果转换成便于接口返回的字典。
    输入：结构化 ASR 结果 `result`。
    输出：普通字典。
    """

    return asdict(result)
