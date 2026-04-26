from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from context import build_chat_context
from workflow.graph import run_assistant_graph


@dataclass(slots=True)
class ChatGatewayResult:
    """
    对外聊天入口的统一返回结果，供 Web/CLI/API 层直接消费。
    """

    reply: str
    mode: str


@dataclass(slots=True)
class GatewayMessage:
    """
    外部消息的统一内部格式。
    """

    source: str
    text: str = ""
    metadata: dict[str, Any] | None = None

    def run(
        self,
    ) -> ChatGatewayResult:
        """
        统一消息执行入口：由标准化消息负责拼接上下文并驱动 workflow。
        """
        chat_context = build_chat_context(user_text=self.text)
        final_state = run_assistant_graph(
            context=chat_context,
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
        pass

    def process_chat(self, user_text: str) -> ChatGatewayResult:
        return GatewayMessage(source="cli", text=str(user_text or "").strip()).run()


class WebGateway:
    """
    Web 入口网关：负责把 Web 输入转成内部可用调用，并转发到 context/runtime 层。
    """

    def __init__(self) -> None:
        pass

    def process_chat(self, user_text: str) -> "ChatGatewayResult":
        return GatewayMessage(source="web", text=str(user_text or "").strip()).run()
