from __future__ import annotations

import logging
from datetime import datetime
from time import perf_counter
from typing import Any

try:
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover - optional dependency guard
    ChatOpenAI = None  # type: ignore[assignment]

from capabilities.memory.persona.context import build_persona_memory_context
from capabilities.memory.short_term import append_recent_conversation, build_recent_conversation
from capabilities.memory.store.core import FactStoreStack, build_fact_store_stack
from foundation.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from foundation.logger import get_backend_logger, setup_backend_logging
from foundation.time_utils import ensure_beijing, now_beijing
from runtime.schemas import AppRuntimeState
from speech import asr_result_to_dict, transcribe_audio


class AppRuntime:
    """
    应用运行时：负责 LLM、记忆栈与写回逻辑的统一装配。
    """

    def __init__(
        self,
        *,
        logger_name: str,
        fact_store_stack: FactStoreStack | None = None,
    ) -> None:
        setup_backend_logging()
        runtime_fact_store_stack = fact_store_stack or build_fact_store_stack()
        self.runtime = AppRuntimeState(
            logger_name=logger_name,
            fact_store_stack=runtime_fact_store_stack,
            llm=self._build_llm_client(),
        )
        self.logger = get_backend_logger(self.runtime.logger_name)
        self._refresh_recent_context_if_needed(force=True)

    def _build_llm_client(self) -> Any | None:
        if ChatOpenAI is None:
            return None
        if not LLM_API_KEY:
            return None
        try:
            return ChatOpenAI(
                model=LLM_MODEL,
                api_key=LLM_API_KEY,
                base_url=LLM_BASE_URL,
                temperature=0.2,
                max_tokens=1000,
                streaming=False,
                extra_body={"reasoning_split": True},
            )
        except Exception:
            return None

    @property
    def llm(self) -> Any | None:
        return self.runtime.llm

    @llm.setter
    def llm(self, value: Any | None) -> None:
        self.runtime.llm = value

    @property
    def fact_store_stack(self) -> FactStoreStack | None:
        return self.runtime.fact_store_stack

    @fact_store_stack.setter
    def fact_store_stack(self, value: FactStoreStack | None) -> None:
        self.runtime.fact_store_stack = value

    @property
    def recent_context_date(self) -> str:
        return self.runtime.recent_context_date

    @recent_context_date.setter
    def recent_context_date(self, value: str) -> None:
        self.runtime.recent_context_date = str(value or "")

    @property
    def recent_context_ctx(self) -> str:
        return self.runtime.recent_context_ctx

    @recent_context_ctx.setter
    def recent_context_ctx(self, value: str) -> None:
        self.runtime.recent_context_ctx = str(value or "")

    def response_mode(self) -> str:
        return "LLM" if self.runtime.llm is not None else "Local Fallback"

    def load_profile_memory_context(self) -> str:
        return build_persona_memory_context()

    def load_recent_context(self) -> str:
        return self._refresh_recent_context_if_needed()

    def _refresh_recent_context_if_needed(self, *, force: bool = False) -> str:
        """
        功能：仅在启动或跨天时重建短期上下文文本缓存。
        输入：是否强制刷新 `force`。
        输出：当前可直接注入 Prompt 的短期上下文文本。
        """
        today = now_beijing().date().isoformat()
        if not force and self.runtime.recent_context_date == today:
            return self.runtime.recent_context_ctx
        self.runtime.recent_context_ctx = build_recent_conversation()
        self.runtime.recent_context_date = today
        return self.runtime.recent_context_ctx

    def persist_turn(
        self,
        *,
        user_text: str,
        assistant_text: str,
        turn_start: float,
        retrieve_ms: float,
        reply_ms: float = 0.0,
        tool_call_ms: float = 0.0,
    ) -> None:
        t_write_start = perf_counter()
        memory_write_ms = (perf_counter() - t_write_start) * 1000.0
        total_ms = (perf_counter() - turn_start) * 1000.0
        short_term_text = f"用户: {user_text}\n助手: {assistant_text}"
        append_recent_conversation(short_term_text)
        self.runtime.recent_context_ctx = build_recent_conversation()
        self.runtime.recent_context_date = now_beijing().date().isoformat()
        self.logger.info(
            "persist turn finished",
            extra={
                "path": "chat.persist",
                "method": "POST",
                "status_code": 200,
                "duration_ms": round(total_ms, 2),
                "retrieve_ms": round(retrieve_ms, 2),
                "reply_ms": round(reply_ms, 2),
                "tool_call_ms": round(tool_call_ms, 2),
                "memory_write_ms": round(memory_write_ms, 2),
            },
        )

    def inject_due_task_reminder(self, reply_text: str) -> str | None:
        due_items: list[tuple[str, str, str]] = []
        for task_fact in self.fact_store_stack.task_store.list():
            task_id = str(getattr(task_fact, "id", "")).strip()
            if not task_id or str(getattr(task_fact, "status", "")).strip() != "active":
                continue
            due_raw = str(getattr(task_fact, "due_date", "")).strip()
            if not due_raw:
                continue
            try:
                due = datetime.fromisoformat(due_raw[:10]).date()
            except Exception:
                continue
            if due > now_beijing().date():
                continue
            content = str(getattr(task_fact, "content", "")).strip()
            due_items.append((task_id, due_raw[:10], content))

        if not due_items:
            return None

        lines = ["提醒：以下任务已到期或今天截止："]
        for task_id, due_date, content in due_items[:3]:
            lines.append(f"- [{task_id}] due={due_date} | {content}")
        if len(due_items) > 3:
            lines.append(f"- 还有 {len(due_items) - 3} 条，你可以继续问我“还有哪些任务”。")

        reminder_text = "\n".join(lines)
        return f"{reminder_text}\n\n{reply_text}" if reply_text else reminder_text

    def health(self) -> dict[str, str]:
        return {
            "status": "ok",
            "mode": "LLM" if self.runtime.llm is not None else "Local Fallback",
            "memory": "disabled",
        }

class WebRuntime(AppRuntime):
    """
    Web 运行时：在通用运行时基础上增加 ASR 与提醒通知能力。
    """

    def __init__(
        self,
        *,
        fact_store_stack: FactStoreStack | None = None,
    ) -> None:
        super().__init__(
            logger_name="web_app",
            fact_store_stack=fact_store_stack,
        )
        logging.getLogger("uvicorn.access").disabled = True
        self.session_pushed_reminder_ids: set[str] = set()

    def transcribe_audio(self, *, payload: bytes, filename: str, content_type: str) -> dict[str, Any]:
        if not payload:
            return {"text": "", "provider": "", "language": "", "duration_ms": 0.0}

        try:
            result = transcribe_audio(audio_bytes=payload, filename=filename, content_type=content_type)
        except Exception as exc:
            self.logger.exception("asr transcribe failed")
            return {"text": "", "provider": "", "language": "", "duration_ms": 0.0}
        data = asr_result_to_dict(result)
        return {
            "text": str(data.get("text", "")),
            "provider": str(data.get("provider", "")),
            "language": str(data.get("language", "")),
            "duration_ms": float(data.get("duration_ms", 0.0) or 0.0),
        }

    def on_asr_read_error(self, *, filename: str, content_type: str) -> dict[str, Any]:
        self.logger.exception("asr audio read failed")
        return {"text": "", "provider": "", "language": "", "duration_ms": 0.0}

    def _collect_due_reminder_messages(
        self,
        *,
        reminder_facts: list[Any],
        pushed_ids: set[str],
        now: datetime,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        remind_store = self.fact_store_stack.remind_store
        for fact in reminder_facts:
            rid = str(getattr(fact, "id", "")).strip()
            if not rid or rid in pushed_ids or str(getattr(fact, "status", "")).strip() != "active":
                continue
            remind_at_raw = str(getattr(fact, "remind_at", "")).strip()
            if not remind_at_raw:
                continue
            try:
                remind_at = datetime.fromisoformat(remind_at_raw)
            except Exception:
                continue
            remind_at = ensure_beijing(remind_at)
            if remind_at > now:
                continue
            content = str(getattr(fact, "content", "")).strip() or "到时间了。"
            when = str(getattr(fact, "remind_text", "")).strip()
            messages.append({"id": rid, "text": f"提醒：{content}" + (f"\n原设定：{when}" if when else "")})
            pushed_ids.add(rid)
            try:
                remind_store.upsert(replace(fact, status="done", version=int(getattr(fact, "version", 1)) + 1))
            except Exception:
                self.logger.exception("reminder mark done failed", extra={"reminder_id": rid})
        return messages

    def notifications(self) -> dict[str, list[dict[str, str]]]:
        remind_store = self.fact_store_stack.remind_store
        messages = self._collect_due_reminder_messages(
            reminder_facts=remind_store.list(),
            pushed_ids=self.session_pushed_reminder_ids,
            now=now_beijing(),
        )
        return {"messages": messages}
