from __future__ import annotations

from typing import Any

from context import build_chat_context
from pydantic import BaseModel, Field
from workflow.graph import run_assistant_graph


class ChatGatewayResult(BaseModel):
    """
    对外聊天入口的统一返回结果，供 Web/CLI/API 层直接消费。
    """

    reply: str = Field(default="", description="最终回复文本。")
    mode: str = Field(default="", description="回复模式。")


class GatewayMessage(BaseModel):
    """
    外部消息的统一内部格式。
    """

    source: str = Field(default="cli", description="消息来源。")
    text: str = Field(default="", description="消息文本。")
    metadata: dict[str, Any] | None = Field(default=None, description="附加元数据。")

    def run(
        self,
    ) -> ChatGatewayResult:
        """
        统一消息执行入口：由标准化消息负责拼接上下文并驱动 workflow。
        """
        thread_id = str((self.metadata or {}).get("thread_id") or f"{self.source}-default").strip()
        chat_context = build_chat_context(user_text=self.text, source=self.source)
        final_state = run_assistant_graph(
            context=chat_context,
            thread_id=thread_id,
        )
        return ChatGatewayResult(
            reply=str(final_state.get("reply_text", "") or ""),
            mode=str(final_state.get("mode", "") or ""),
        )


class CliGateway:
    """
    CLI 来源网关：负责 CLI 输入标准化并转发到统一消息入口。
    """

    def __init__(self) -> None:
        self._thread_id = "cli-default"

    def process_chat(self, user_text: str) -> ChatGatewayResult:
        return GatewayMessage(
            source="cli",
            text=str(user_text or "").strip(),
            metadata={"thread_id": self._thread_id},
        ).run()


class WebGateway:
    """
    Web 入口网关：负责把 Web 输入转成内部可用调用，并转发到 context/runtime 层。
    """

    def __init__(self) -> None:
        self._thread_id = "web-default"

    def process_chat(self, user_text: str) -> "ChatGatewayResult":
        return GatewayMessage(
            source="web",
            text=str(user_text or "").strip(),
            metadata={"thread_id": self._thread_id},
        ).run()
