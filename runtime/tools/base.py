from __future__ import annotations

import re
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field


class ToolContext(BaseModel):
    """工具执行上下文，封装事实存储与辅助函数。"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    task_store: Any = Field(description="任务事实存储。")
    remind_store: Any = Field(description="提醒事实存储。")


class ToolManifest(BaseModel):
    """工具说明书，供路由、展示和 LLM 理解工具能力使用。"""
    name: str = Field(description="工具注册名。")
    description: str = Field(description="工具用途说明。")
    action: str = Field(description="工具 action 名。")
    object_label: str = Field(default="", description="工具作用对象名称，例如任务、提醒、画像。")
    command_pattern: str = Field(default="", description="命令式调用格式。")
    intent_examples: list[str] = Field(default_factory=list, description="自然语言触发示例。")
    tags: list[str] = Field(default_factory=list, description="工具标签。")
    read_only: bool = Field(default=False, description="是否只读。")
    risk_level: str = Field(default="low", description="风险等级。")
    arg_names: list[str] = Field(default_factory=list, description="参数顺序。")
    required_args: list[str] = Field(default_factory=list, description="必填参数名。")
    args_schema: dict[str, str] = Field(default_factory=dict, description="参数说明。")
    confirm_required: bool = Field(default=False, description="是否需要确认。")
    confirm_message: str = Field(default="", description="确认提示文案。")
    allow_nl_trigger: bool = Field(default=True, description="是否允许自然语言触发。")
    direct_response: bool = Field(default=False, description="是否直接返回工具结果而不再交给 LLM 润色。")

    def to_prompt_block(self) -> str:
        """
        功能：把工具说明转换为可直接注入 prompt 的目录文本。
        输入：无。
        输出：单行工具目录字符串。
        """
        examples = "；".join(self.intent_examples) if self.intent_examples else "无"
        tags = ",".join(self.tags) if self.tags else "-"
        args = ",".join(f"{k}:{v}" for k, v in self.args_schema.items()) if self.args_schema else "-"
        return (
            f"- {self.name}: {self.description} | action={self.action} | "
            f"command={self.command_pattern or '-'} | read_only={str(self.read_only).lower()} | "
            f"risk={self.risk_level} | confirm_required={str(self.confirm_required).lower()} | "
            f"args={args} | tags={tags} | examples={examples}"
        )


class ToolCall(BaseModel):
    """结构化工具调用请求。"""

    tool: str = Field(description="工具名。")
    arguments: dict[str, str] = Field(default_factory=dict, description="工具参数。")
    confidence: float = Field(default=0.0, description="工具选择置信度。")
    raw: str = Field(default="", description="原始模型输出。")
    source: str = Field(default="llm", description="调用来源。")


class ToolResult(BaseModel):
    """结构化工具执行结果。"""

    ok: bool = Field(description="执行是否成功。")
    tool: str = Field(description="工具名。")
    arguments: dict[str, str] = Field(default_factory=dict, description="执行参数。")
    display_text: str = Field(default="", description="给用户展示的文本。")
    data: dict[str, Any] = Field(default_factory=dict, description="结构化结果数据。")
    error: str = Field(default="", description="错误码或错误原因。")


ToolHandler = Callable[[re.Match[str], ToolContext], ToolResult]
ToolNormalizer = Callable[[ToolCall, ToolContext], ToolCall]


class ToolBatchResult(BaseModel):
    """结构化批量工具执行结果。"""

    results: list[ToolResult] = Field(default_factory=list, description="批量执行结果列表。")


def build_manifest(
    name: str,
    *,
    description: str,
    action: str,
    object_label: str = "",
    command_pattern: str,
    intent_examples: list[str],
    tags: list[str],
    read_only: bool,
    risk_level: str = "low",
    arg_names: list[str] | None = None,
    required_args: list[str] | None = None,
    args_schema: dict[str, str] | None = None,
    confirm_required: bool = False,
    confirm_message: str = "",
    allow_nl_trigger: bool = True,
    direct_response: bool = False,
) -> ToolManifest:
    """
    功能：构造统一格式的工具 manifest。
    输入：工具名称、描述、动作名、命令模式、示例、标签与风险信息。
    输出：`ToolManifest` 实例。
    """
    return ToolManifest(
        name=name,
        description=description,
        action=action,
        object_label=object_label,
        command_pattern=command_pattern,
        intent_examples=intent_examples,
        tags=tags,
        read_only=read_only,
        risk_level=risk_level,
        arg_names=list(arg_names or []),
        required_args=list(required_args or []),
        args_schema=dict(args_schema or {}),
        confirm_required=confirm_required,
        confirm_message=confirm_message,
        allow_nl_trigger=allow_nl_trigger,
        direct_response=direct_response,
    )


class _ToolCallMatch:
    """把结构化参数适配成 handler 兼容的 match 接口。"""

    def __init__(self, args: list[str]) -> None:
        self._args = args
        self.lastindex = len(args)

    def group(self, index: int = 0) -> str:
        if index <= 0:
            return ""
        pos = index - 1
        if pos < 0 or pos >= len(self._args):
            return ""
        return self._args[pos]


class ToolRegistry:
    """工具注册表，负责注册、查询和执行工具 handler。"""

    def __init__(self) -> None:
        """
        功能：初始化工具注册表。
        输入：无。
        输出：无，建立 handler 与 manifest 索引。
        """
        self._handlers: dict[str, ToolHandler] = {}
        self._manifests: dict[str, ToolManifest] = {}
        self._normalizers: dict[str, ToolNormalizer] = {}

    def register(self, name: str, handler: ToolHandler, manifest: ToolManifest | None = None) -> None:
        """
        功能：向注册表注册一个工具处理器及其 manifest。
        输入：工具名 `name`、处理函数 `handler`、可选 `manifest`。
        输出：无，副作用是更新注册表索引。
        """
        self._handlers[name] = handler
        if manifest is not None:
            self._manifests[name] = manifest

    def register_normalizer(self, name: str, normalizer: ToolNormalizer) -> None:
        """
        功能：向注册表注册某个工具的参数归一化函数。
        输入：工具名 `name`、归一化函数 `normalizer`。
        输出：无，副作用是更新归一化器索引。
        """
        self._normalizers[name] = normalizer

    def execute(self, name: str, match: re.Match[str], ctx: ToolContext) -> ToolResult:
        """
        功能：执行指定工具。
        输入：工具名 `name`、命令匹配结果 `match`、工具上下文 `ctx`。
        输出：工具返回的结构化执行结果。
        """
        handler = self._handlers.get(name)
        if handler is None:
            return ToolResult(
                ok=False,
                tool=name,
                arguments={},
                display_text="",
                data={},
                error="tool_not_found",
            )
        return handler(match, ctx)

    def validate_tool_call(self, tool_call: ToolCall) -> tuple[bool, str]:
        """
        功能：校验结构化工具调用是否合法。
        输入：工具调用对象 `tool_call`。
        输出：`(是否合法, 错误原因)` 元组。
        """
        manifest = self.get_manifest(tool_call.tool)
        if manifest is None:
            return False, "tool_not_found"
        arguments = tool_call.arguments or {}
        for key in manifest.required_args:
            if not str(arguments.get(key, "")).strip():
                return False, f"missing_arg:{key}"
        return True, ""

    def execute_call(self, tool_call: ToolCall, ctx: ToolContext) -> ToolResult:
        """
        功能：执行结构化工具调用。
        输入：工具调用对象 `tool_call`、工具上下文 `ctx`。
        输出：结构化 `ToolResult`。
        """
        ok, reason = self.validate_tool_call(tool_call)
        if not ok:
            return ToolResult(
                ok=False,
                tool=tool_call.tool,
                arguments=dict(tool_call.arguments),
                display_text="",
                data={},
                error=reason,
            )
        handler = self._handlers.get(tool_call.tool)
        manifest = self.get_manifest(tool_call.tool)
        if handler is None or manifest is None:
            return ToolResult(
                ok=False,
                tool=tool_call.tool,
                arguments=dict(tool_call.arguments),
                display_text="",
                data={},
                error="tool_not_found",
            )
        ordered_args = [str(tool_call.arguments.get(name, "")).strip() for name in manifest.arg_names]
        match = _ToolCallMatch(ordered_args)
        result = handler(match, ctx)
        if not result.tool:
            result.tool = tool_call.tool
        if not result.arguments:
            result.arguments = dict(tool_call.arguments)
        return result

    def execute_calls(self, tool_calls: list[ToolCall], ctx: ToolContext) -> ToolBatchResult:
        """
        功能：批量执行结构化工具调用。
        输入：工具调用列表 `tool_calls`、工具上下文 `ctx`。
        输出：结构化 `ToolBatchResult`。
        """
        results = [self.execute_call(tool_call, ctx) for tool_call in tool_calls]
        return ToolBatchResult(results=results)

    def list_names(self) -> list[str]:
        """
        功能：列出当前已注册的工具名。
        输入：无。
        输出：排序后的工具名列表。
        """
        return sorted(self._handlers.keys())

    def get_manifest(self, name: str) -> ToolManifest | None:
        """
        功能：获取某个工具对应的 manifest。
        输入：工具名 `name`。
        输出：`ToolManifest` 或 `None`。
        """
        return self._manifests.get(name)

    def get_normalizer(self, name: str) -> ToolNormalizer | None:
        """
        功能：获取某个工具对应的参数归一化函数。
        输入：工具名 `name`。
        输出：归一化函数或 `None`。
        """
        return self._normalizers.get(name)

    def list_manifests(self) -> list[ToolManifest]:
        """
        功能：列出所有已注册工具的 manifest。
        输入：无。
        输出：排序后的 manifest 列表。
        """
        return [self._manifests[name] for name in sorted(self._manifests.keys())]

    def render_prompt_catalog(self) -> str:
        """
        功能：把所有工具 manifest 渲染为目录文本。
        输入：无。
        输出：可直接用于 prompt 的多行字符串。
        """
        manifests = self.list_manifests()
        if not manifests:
            return ""
        return "\n".join(manifest.to_prompt_block() for manifest in manifests)
