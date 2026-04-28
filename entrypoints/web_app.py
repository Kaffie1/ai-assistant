from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from foundation.time_utils import ensure_beijing, now_beijing
from gateway import ChatGatewayResult, WebGateway
from workflow.nodes.services import get_fact_store_stack, response_mode


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    mode: str


class ASRResponse(BaseModel):
    text: str
    provider: str
    language: str
    duration_ms: float

gateway = WebGateway()
fact_store_stack = get_fact_store_stack()
_PUSHED_REMINDER_IDS: set[str] = set()

app = FastAPI(title="AI Assistant Web Chat")
app.mount("/web", StaticFiles(directory="web"), name="web")


@app.get("/")
def home() -> FileResponse:
    return FileResponse(Path("web/index.html"))


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": response_mode()}


def _collect_due_reminder_messages() -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    remind_store = fact_store_stack.remind_store
    for fact in remind_store.list():
        rid = str(getattr(fact, "id", "")).strip()
        if not rid or rid in _PUSHED_REMINDER_IDS or str(getattr(fact, "status", "")).strip() != "active":
            continue
        remind_at_raw = str(getattr(fact, "remind_at", "")).strip()
        if not remind_at_raw:
            continue
        try:
            remind_at = ensure_beijing(datetime.fromisoformat(remind_at_raw))
        except Exception:
            continue
        if remind_at > now_beijing():
            continue
        content = str(getattr(fact, "content", "")).strip() or "到时间了。"
        when = str(getattr(fact, "remind_text", "")).strip()
        messages.append({"id": rid, "text": f"提醒：{content}" + (f"\n原设定：{when}" if when else "")})
        _PUSHED_REMINDER_IDS.add(rid)
        try:
            fact_store_stack.remind_store.delete(rid)
        except Exception:
            continue
    return messages


@app.get("/api/notifications")
def notifications() -> dict[str, list[dict[str, str]]]:
    return {"messages": _collect_due_reminder_messages()}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    result: ChatGatewayResult = gateway.process_chat(req.message)
    return ChatResponse(reply=result.reply, mode=result.mode)


@app.post("/api/asr", response_model=ASRResponse)
async def asr(audio: UploadFile = File(...)) -> ASRResponse:
    return ASRResponse(
        text="",
        provider="",
        language="",
        duration_ms=0.0,
    )
