from __future__ import annotations

import json
import re
from typing import Any

from runtime.tools.base import ToolBatchResult, ToolCall, ToolContext, ToolRegistry, ToolResult
from prompts.tool_router import build_tool_result_reply_prompt, build_tool_selection_prompt

try:
    from langchain_core.messages import HumanMessage, SystemMessage
except Exception:  # pragma: no cover
    HumanMessage = None  # type: ignore[assignment]
    SystemMessage = None  # type: ignore[assignment]


def is_confirm_text(text: str) -> bool:
    """
    功能：判断输入是否表示确认执行。
    输入：用户文本 `text`。
    输出：确认返回 `True`，否则返回 `False`。
    """
    normalized = (text or "").strip().lower()
    return normalized in {"确认", "执行", "继续", "是", "好的", "好", "yes", "ok", "确认执行"}


def is_cancel_text(text: str) -> bool:
    """
    功能：判断输入是否表示取消待执行操作。
    输入：用户文本 `text`。
    输出：取消返回 `True`，否则返回 `False`。
    """
    normalized = (text or "").strip().lower()
    return normalized in {"取消", "不用了", "否", "不", "停止", "先不要", "cancel", "no"}


def build_tool_catalog_for_llm(registry: ToolRegistry) -> str:
    """
    功能：构建给 LLM 使用的可触发工具目录。
    输入：工具注册表 `registry`。
    输出：工具目录文本。
    """
    manifests = [m for m in registry.list_manifests() if m.allow_nl_trigger]
    if not manifests:
        return ""
    return "\n".join(m.to_prompt_block() for m in manifests)


def _parse_json_payload(text: str) -> dict[str, object] | None:
    """
    功能：从 LLM 原始输出中提取 JSON 对象。
    输入：原始文本 `text`。
    输出：字典对象；失败时返回 `None`。
    """
    raw = re.sub(r"<think>[\s\S]*?</think>", "", (text or "").strip(), flags=re.IGNORECASE).strip()
    if not raw:
        return None
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(raw[start : end + 1])
            if isinstance(obj, dict):
                return obj
        except Exception:
            return None
    return None


def _normalize_tool_call(obj: dict[str, object], raw_text: str) -> ToolCall | None:
    """
    功能：把单个工具调用字典规范化为 `ToolCall`。
    输入：工具调用字典 `obj`、原始输出 `raw_text`。
    输出：`ToolCall`；缺少有效 tool 时返回 `None`。
    """
    tool = str(obj.get("tool", "none") or "none").strip()
    if tool in {"", "none"}:
        return None
    args_raw = obj.get("arguments", {})
    confidence_raw = obj.get("confidence", 0.0)
    arguments: dict[str, str] = {}
    if isinstance(args_raw, dict):
        for key, value in args_raw.items():
            key_s = str(key).strip()
            if not key_s or value is None:
                continue
            arguments[key_s] = str(value).strip()
    try:
        confidence = float(confidence_raw)
    except Exception:
        confidence = 0.0
    return ToolCall(tool=tool, arguments=arguments, confidence=confidence, raw=raw_text, source="llm")


def parse_tool_call_response(raw_text: str) -> list[ToolCall]:
    """
    功能：把 LLM 输出解析为结构化工具调用列表。
    输入：LLM 原始输出 `raw_text`。
    输出：`ToolCall` 列表；无法解析时返回空列表。
    """
    obj = _parse_json_payload(raw_text)
    if not obj:
        return []
    calls_raw = obj.get("tool_calls")
    if isinstance(calls_raw, list):
        out: list[ToolCall] = []
        for item in calls_raw:
            if not isinstance(item, dict):
                continue
            tool_call = _normalize_tool_call(item, raw_text)
            if tool_call is not None:
                out.append(tool_call)
        return out
    single = _normalize_tool_call(obj, raw_text)
    return [single] if single is not None else []


def select_tool_call_with_llm(
    *,
    llm: Any | None,
    user_text: str,
    profile_ctx: str,
    memory_ctx: str,
    recent_ctx: str,
    registry: ToolRegistry,
) -> list[ToolCall]:
    """
    功能：调用 LLM 从工具目录中选择工具并抽取参数。
    输入：LLM、用户文本、画像上下文、记忆上下文、工具注册表。
    输出：`ToolCall` 列表；不应执行工具时返回空列表。
    """
    if llm is None:
        return []
    system_text = build_tool_selection_prompt(
        profile_ctx=profile_ctx,
        memory_ctx=memory_ctx,
        tool_catalog=build_tool_catalog_for_llm(registry),
        recent_ctx=recent_ctx,
    )
    user_prompt = f"[user]\n{user_text.strip()}"
    messages = (
        [SystemMessage(content=system_text), HumanMessage(content=user_prompt)]
        if HumanMessage is not None and SystemMessage is not None
        else f"{system_text}\n\n{user_prompt}"
    )
    try:
        resp = llm.invoke(messages, response_format={"type": "json_object"})
    except Exception:
        try:
            resp = llm.invoke(messages)
        except Exception:
            return []
    raw = getattr(resp, "content", "")
    if isinstance(raw, list):
        raw = "\n".join(item.get("text", "") if isinstance(item, dict) else str(item) for item in raw)
    return [call for call in parse_tool_call_response(str(raw)) if call.tool not in {"", "none"}]


def needs_confirmation(tool_calls: list[ToolCall], registry: ToolRegistry) -> bool:
    """
    功能：判断工具调用是否需要用户确认。
    输入：工具调用列表 `tool_calls`、工具注册表 `registry`。
    输出：需要确认返回 `True`，否则返回 `False`。
    """
    for tool_call in tool_calls:
        manifest = registry.get_manifest(tool_call.tool)
        if manifest is None:
            continue
        if manifest.confirm_required or manifest.risk_level.lower() == "high":
            return True
    return False


def _summarize_batch_results(batch_result: ToolBatchResult, registry: ToolRegistry) -> str:
    """
    功能：把批量工具执行结果汇总成简洁文本。
    输入：批量执行结果 `batch_result`。
    输出：面向用户的摘要文本。
    """
    results = batch_result.results
    if not results:
        return "没有执行任何操作。"
    if len(results) == 1:
        result = results[0]
        return result.display_text or ("执行成功。" if result.ok else "执行失败。")

    success_count = sum(1 for result in results if result.ok)
    failed_count = len(results) - success_count
    same_tool = len({result.tool for result in results}) == 1
    noun = ""
    if same_tool:
        manifest = registry.get_manifest(results[0].tool)
        noun = (manifest.object_label if manifest is not None else "") or "项目"
    head = f"已成功处理 {success_count} 项"
    if noun:
        head = f"已成功处理 {success_count} 条{noun}"
    if failed_count:
        head += f"，失败 {failed_count} 项。"
    else:
        head += "。"
    detail_lines = [head]
    for idx, result in enumerate(results, start=1):
        status_text = "成功" if result.ok else f"失败（{result.error or 'unknown'}）"
        target = result.data.get("id") or result.arguments.get("id") or result.tool
        detail_lines.append(f"- 第{idx}项：{target} {status_text}")
    return "\n".join(detail_lines)


def _normalize_tool_calls(tool_calls: list[ToolCall], ctx: ToolContext, registry: ToolRegistry) -> list[ToolCall]:
    """
    功能：在执行前把批量工具调用参数归一化，冻结同批次的引用快照。
    输入：工具调用列表 `tool_calls`、工具上下文 `ctx`、工具注册表 `registry`。
    输出：归一化后的工具调用列表。
    """
    normalized: list[ToolCall] = []
    for tool_call in tool_calls:
        normalizer = registry.get_normalizer(tool_call.tool)
        normalized.append(normalizer(tool_call, ctx) if normalizer else tool_call)
    return normalized


def compose_tool_result_reply_with_llm(
    *,
    llm: Any | None,
    registry: ToolRegistry,
    user_text: str,
    profile_ctx: str,
    memory_ctx: str,
    recent_ctx: str,
    tool_result: ToolResult,
) -> str:
    """
    功能：把工具执行结果回灌给 LLM，生成最终自然语言回复。
    输入：LLM、用户文本、画像上下文、记忆上下文、工具执行结果。
    输出：自然语言回复文本。
    """
    fallback = tool_result.display_text or ("执行成功。" if tool_result.ok else f"执行失败：{tool_result.error}")
    manifest = registry.get_manifest(tool_result.tool)
    if manifest is not None and manifest.direct_response:
        return fallback
    if llm is None:
        return fallback
    system_text = build_tool_result_reply_prompt(profile_ctx=profile_ctx, memory_ctx=memory_ctx, recent_ctx=recent_ctx)
    user_payload = (
        f"[user]\n{user_text.strip()}\n\n"
        f"[tool]\n{tool_result.tool}\n\n"
        f"[arguments]\n{json.dumps(tool_result.arguments, ensure_ascii=False)}\n\n"
        f"[result]\n{json.dumps(tool_result.data, ensure_ascii=False)}\n\n"
        f"[display_text]\n{tool_result.display_text}\n\n"
        f"[ok]\n{str(tool_result.ok).lower()}\n\n"
        f"[error]\n{tool_result.error}"
    )
    messages = (
        [SystemMessage(content=system_text), HumanMessage(content=user_payload)]
        if HumanMessage is not None and SystemMessage is not None
        else f"{system_text}\n\n{user_payload}"
    )
    try:
        resp = llm.invoke(messages)
    except Exception:
        return fallback
    content = getattr(resp, "content", "")
    if isinstance(content, str):
        return content.strip() or fallback
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        merged = "\n".join(part.strip() for part in parts if part and part.strip())
        return merged or fallback
    return fallback


def build_confirmation_message(tool_calls: list[ToolCall], manifests: list[Any]) -> str:
    """
    功能：为批量高风险操作生成统一确认文案。
    输入：工具调用列表 `tool_calls` 与对应 manifest 列表 `manifests`。
    输出：面向用户的确认文本。
    """
    if len(tool_calls) == 1:
        manifest = manifests[0]
        return manifest.confirm_message.strip() or f"将执行 {tool_calls[0].tool}，是否确认？"
    same_tool = len({call.tool for call in tool_calls}) == 1
    if same_tool:
        manifest = manifests[0]
        action_name = manifest.description.strip() or tool_calls[0].tool
        return f"将批量执行 {len(tool_calls)} 项操作（{action_name}），是否确认？"
    return f"将批量执行 {len(tool_calls)} 项高风险操作，是否确认？"


def execute_tool_calls(
    *,
    tool_calls: list[ToolCall],
    registry: ToolRegistry,
    ctx: ToolContext,
    llm: Any | None,
    user_text: str,
    profile_ctx: str,
    memory_ctx: str,
    recent_ctx: str,
) -> str:
    """
    功能：执行一批已确认的工具调用并生成最终回复。
    输入：工具调用列表、注册表、上下文、LLM 与会话上下文。
    输出：工具执行后的回复文本。
    """
    batch_result = registry.execute_calls(
        [
            ToolCall(
                tool=tool_call.tool,
                arguments=dict(tool_call.arguments),
                confidence=1.0,
                raw=tool_call.raw,
                source="confirm",
            )
            for tool_call in tool_calls
        ],
        ctx,
    )
    if len(batch_result.results) == 1:
        return compose_tool_result_reply_with_llm(
            llm=llm,
            registry=registry,
            user_text=user_text,
            profile_ctx=profile_ctx,
            memory_ctx=memory_ctx,
            recent_ctx=recent_ctx,
            tool_result=batch_result.results[0],
        )
    return _summarize_batch_results(batch_result, registry)


def prepare_tool_calls(
    *,
    user_text: str,
    registry: ToolRegistry,
    ctx: ToolContext,
    llm: Any | None,
    profile_ctx: str,
    memory_ctx: str,
    recent_ctx: str,
) -> tuple[list[ToolCall], bool, str]:
    """
    功能：准备本轮工具调用，并判断是否需要确认。
    输入：用户文本、工具注册表、上下文、LLM、画像上下文、记忆上下文。
    输出：`(归一化工具调用列表, 是否需要确认, 确认文案)`。
    """
    tool_calls = select_tool_call_with_llm(
        llm=llm,
        user_text=user_text,
        profile_ctx=profile_ctx,
        memory_ctx=memory_ctx,
        recent_ctx=recent_ctx,
        registry=registry,
    )
    if not tool_calls:
        return [], False, ""

    validated_calls: list[ToolCall] = []
    for tool_call in tool_calls:
        ok, _reason = registry.validate_tool_call(tool_call)
        if ok:
            validated_calls.append(tool_call)
    if not validated_calls:
        return [], False, ""

    manifests = [registry.get_manifest(tool_call.tool) for tool_call in validated_calls]
    manifests = [manifest for manifest in manifests if manifest is not None]
    if not manifests:
        return [], False, ""

    normalized_calls = _normalize_tool_calls(validated_calls, ctx, registry)
    require_confirmation = needs_confirmation(normalized_calls, registry)
    confirm_message = build_confirmation_message(normalized_calls, manifests) if require_confirmation else ""
    return normalized_calls, require_confirmation, confirm_message
