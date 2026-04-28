from __future__ import annotations

from pydantic import BaseModel, Field


class MemoryContext(BaseModel):
    """
    当前轮的最终上下文：
    - 输入问题
    - 画像记忆
    - 短期记忆
    - 来源标识
    """

    user_text: str = Field(default="", description="当前轮用户输入文本。")
    source: str = Field(default="cli", description="本轮输入来源。")
    profile_memory_context: str = Field(default="", description="画像记忆上下文。")
    long_term_memory_context: str = Field(default="", description="长期记忆上下文。")
    recent_memory_context: str = Field(default="", description="短期记忆上下文。")
