from __future__ import annotations

import os
from pathlib import Path
from datetime import date
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from langchain_core.messages import HumanMessage, SystemMessage

try:
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover - optional dependency guard
    ChatOpenAI = None  # type: ignore[assignment]

from memory import (
    MemoryWriter,
    assemble_context,
    build_learning_stack,
    build_memory_stack_from_env,
    build_persona_context,
    handle_command,
)
from memory.prompts import build_chat_system_prompt


def _load_dotenv_file(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        return


def _build_llm_client() -> Any | None:
    if ChatOpenAI is None:
        return None
    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key:
        return None
    base_url = os.getenv("LLM_BASE_URL", "").strip()
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    try:
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=0.2,
            max_tokens=1000,
            streaming=False,
            extra_body={"reasoning_split": True},
        )
    except Exception:
        return None


def _generate_reply(user_text: str, persona_ctx: str, memory_ctx: str) -> str:
    if any(k in user_text for k in ("你是谁", "你是干嘛的", "你能做什么")):
        return "我是你的定制化 AI 助手（秘书型）。我会学习你的偏好并持续个性化。"
    if any(k in user_text for k in ("你记住了什么", "我的偏好", "画像")):
        return f"我当前记住的画像如下：\n{persona_ctx}" if persona_ctx else "我还没有稳定画像。"
    if any(k in user_text for k in ("总结", "回顾", "检索")):
        return f"我根据当前记忆检索到如下信息：\n{memory_ctx}"
    return "我已收到，这条信息会进入学习管道并用于后续个性化回答。"


def _generate_reply_with_llm(llm: Any, user_text: str, persona_ctx: str, memory_ctx: str) -> str:
    system_text = build_chat_system_prompt(persona_ctx=persona_ctx, memory_ctx=memory_ctx)
    resp = llm.invoke(
        [
            SystemMessage(content=system_text),
            HumanMessage(content=user_text),
        ]
    )
    content = getattr(resp, "content", "")
    if isinstance(content, str):
        return content.strip() or "我暂时没有生成到有效回复，请你再说一次。"
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        merged = "\n".join(x.strip() for x in parts if x and x.strip())
        return merged or "我暂时没有生成到有效回复，请你再说一次。"
    return "我暂时没有生成到有效回复，请你再说一次。"


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    mode: str
    learn: dict[str, Any]


_load_dotenv_file(".env")
_learning_stack = build_learning_stack()
_memory_stack: Any | None = None
_writer: MemoryWriter | None = None
_llm = _build_llm_client()
_session_reminded_task_ids: set[str] = set()

app = FastAPI(title="AI Assistant Web Chat")
app.mount("/web", StaticFiles(directory="web"), name="web")


def _build_due_task_reminder(task_facts: list[Any], reminded_ids: set[str], today: date) -> str:
    due_items: list[tuple[str, str, str]] = []
    for t in task_facts:
        tid = str(getattr(t, "id", "")).strip()
        if not tid or tid in reminded_ids:
            continue
        due_raw = str(getattr(t, "due_date", "")).strip()
        if not due_raw:
            continue
        try:
            due = date.fromisoformat(due_raw[:10])
        except Exception:
            continue
        if due > today:
            continue
        content = str(getattr(t, "content", "")).strip()
        due_items.append((tid, due_raw[:10], content))

    if not due_items:
        return ""
    lines = ["提醒：以下任务已到期或今天截止："]
    for tid, due_date, content in due_items[:3]:
        lines.append(f"- [{tid}] due={due_date} | {content}")
        reminded_ids.add(tid)
    if len(due_items) > 3:
        lines.append(f"- 还有 {len(due_items) - 3} 条，请用 /todo list 查看")
    return "\n".join(lines)


def _ensure_memory_stack() -> tuple[Any, MemoryWriter]:
    global _memory_stack, _writer
    if _memory_stack is None:
        _memory_stack = build_memory_stack_from_env()
        _writer = _memory_stack.writer
    return _memory_stack, _writer  # type: ignore[return-value]


@app.get("/")
def home() -> FileResponse:
    return FileResponse(Path("web/index.html"))


@app.get("/api/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "mode": "LLM" if _llm is not None else "Local Fallback",
        "memory": "ready" if _memory_stack is not None else "lazy",
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    user_text = req.message.strip()
    if not user_text:
        return ChatResponse(
            reply="请输入内容。",
            mode="LLM" if _llm is not None else "Local Fallback",
            learn={"extracted": 0, "profile": 0, "knowledge": 0, "tasks": 0, "reason": "empty"},
        )

    if user_text.startswith("/"):
        out = handle_command(user_text, pipeline=_learning_stack.pipeline)
        return ChatResponse(
            reply=out,
            mode="LLM" if _llm is not None else "Local Fallback",
            learn={"extracted": 0, "profile": 0, "knowledge": 0, "tasks": 0, "reason": "command"},
        )

    profile_facts = _learning_stack.profile_store.list()
    persona_ctx = build_persona_context(profile_facts)
    try:
        current_stack, _ = _ensure_memory_stack()
        retrieved = current_stack.retriever.retrieve(
            query=user_text, top_k_vector=8, hops=1, top_n_final=4
        )
        memory_ctx = assemble_context(retrieved, max_items=4)
    except Exception:
        memory_ctx = "[记忆上下文]\n(empty)"

    if _llm is not None:
        try:
            assistant_text = _generate_reply_with_llm(
                llm=_llm,
                user_text=user_text,
                persona_ctx=persona_ctx,
                memory_ctx=memory_ctx,
            )
        except Exception:
            assistant_text = _generate_reply(
                user_text=user_text, persona_ctx=persona_ctx, memory_ctx=memory_ctx
            )
    else:
        assistant_text = _generate_reply(
            user_text=user_text, persona_ctx=persona_ctx, memory_ctx=memory_ctx
        )

    reminder_text = _build_due_task_reminder(
        task_facts=_learning_stack.task_store.list(),
        reminded_ids=_session_reminded_task_ids,
        today=date.today(),
    )
    if reminder_text:
        assistant_text = f"{reminder_text}\n\n{assistant_text}"

    try:
        _, current_writer = _ensure_memory_stack()
        current_writer.add_text(f"用户: {user_text}", source="dialog")
        current_writer.add_text(f"助手: {assistant_text}", source="dialog")
    except Exception:
        pass

    event = _learning_stack.pipeline.learn_from_turn(
        user_message=user_text,
        assistant_message=assistant_text,
    )
    return ChatResponse(
        reply=assistant_text,
        mode="LLM" if _llm is not None else "Local Fallback",
        learn={
            "extracted": event.extracted_count,
            "profile": len(event.upserted_profile_ids),
            "knowledge": len(event.upserted_knowledge_ids),
            "tasks": len(event.upserted_task_ids),
            "reason": event.reason,
        },
    )
