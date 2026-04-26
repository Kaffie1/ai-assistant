from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from capabilities.memory.store.core import FactStoreStack


class AppRuntimeState(BaseModel):
    """
    AppRuntime 的运行时数据。
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    logger_name: str = Field(default="", description="运行时 logger 名称。")
    llm: Any | None = Field(default=None, description="当前 LLM 客户端。")
    fact_store_stack: FactStoreStack | None = Field(default=None, description="事实存储栈。")
    profile_ctx: str = Field(default="", description="个人信息上下文。")
    recent_context_date: str = Field(default="", description="短期上下文缓存对应日期。")
    recent_context_ctx: str = Field(default="", description="短期上下文缓存文本。")
