from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from runtime import WebRuntime
from gateway import ChatGatewayResult, WebGateway


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
runtime = WebRuntime()

app = FastAPI(title="AI Assistant Web Chat")
app.mount("/web", StaticFiles(directory="web"), name="web")


@app.get("/")
def home() -> FileResponse:
    return FileResponse(Path("web/index.html"))


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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
