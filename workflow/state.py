from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class State(BaseModel):
    """
    LangGraph 问答流程共享状态。
    """

    user_text: str = Field(default="", description="用户本轮输入文本。")
    mode: str = Field(default="", description="当前回复模式，例如 LLM 或 Local Fallback。")
    turn_start: float = Field(default=0.0, description="本轮对话开始时间戳，用于统计耗时。")

    profile_ctx: str = Field(default="", description="画像记忆上下文文本。")
    memory_ctx: str = Field(default="", description="长期记忆上下文文本。")
    recent_ctx: str = Field(default="", description="短期记忆上下文文本，用于保持最近对话连续性。")

    tool_reply: str = Field(default="", description="工具调用产生的回复文本。")
    used_tool: bool = Field(default=False, description="本轮是否命中并使用了运行时工具。")
    reply_text: str = Field(default="", description="最终回复文本。")
    waiting_confirmation: bool = Field(default=False, description="当前是否处于等待高风险操作确认状态。")
    interrupt_message: str = Field(default="", description="图中断时返回给用户的确认提示。")
    tool_calls_payload: list[dict[str, Any]] = Field(default_factory=list, description="待执行的结构化工具调用列表。")
    needs_tool_confirmation: bool = Field(default=False, description="本轮工具调用是否需要确认。")
    tool_confirmation_message: str = Field(default="", description="工具确认提示文案。")
    tool_confirmation_decision: str = Field(default="", description="工具确认结果，支持 confirmed 或 cancelled。")

    reply_ms: float = Field(default=0.0, description="普通回复生成耗时，单位毫秒。")
    tool_call_ms: float = Field(default=0.0, description="工具调用流程耗时，单位毫秒。")

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
