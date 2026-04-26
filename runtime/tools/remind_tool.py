from __future__ import annotations

import re
from datetime import datetime

from capabilities.memory.store.core import ReminderFact
from capabilities.memory.store.time_parser import resolve_due_date, resolve_remind_at
from foundation.time_utils import now_beijing

from .base import ToolCall, ToolContext, ToolManifest, ToolResult, build_manifest


def _remind_store(ctx: ToolContext):
    """
    功能：从执行上下文中获取提醒存储。
    输入：工具上下文 `ctx`。
    输出：提醒存储对象；不存在时返回 `None`。
    """
    return ctx.remind_store


def _parse_order_ref(text: str) -> int | None:
    """
    功能：把提醒序号引用解析成正整数序号。
    输入：用户给出的引用文本 `text`。
    输出：解析成功返回 1-based 序号，否则返回 `None`。
    """
    raw = (text or "").strip()
    if not raw:
        return None
    digit = re.search(r"第?\s*(\d+)\s*(个|条)?", raw)
    if digit:
        value = int(digit.group(1))
        return value if value > 0 else None

    zh_map = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    zh = re.search(r"第?\s*([一二两三四五六七八九十]+)\s*(个|条)?", raw)
    if not zh:
        return None
    token = zh.group(1)
    if token in zh_map:
        return zh_map[token]
    if token.startswith("十") and len(token) == 2 and token[1] in zh_map:
        return 10 + zh_map[token[1]]
    if token.endswith("十") and len(token) == 2 and token[0] in zh_map:
        return zh_map[token[0]] * 10
    if len(token) == 3 and token[1] == "十" and token[0] in zh_map and token[2] in zh_map:
        return zh_map[token[0]] * 10 + zh_map[token[2]]
    return None


def _ordered_reminders(ctx: ToolContext) -> list[ReminderFact]:
    """
    功能：按提醒触发时间优先排序当前有效提醒。
    输入：工具上下文 `ctx`。
    输出：排序后的提醒列表。
    """
    store = _remind_store(ctx)
    if store is None:
        return []
    facts = list(store.list())

    def sort_key(fact: ReminderFact) -> tuple[int, datetime, datetime]:
        remind_at_raw = str(getattr(fact, "remind_at", "")).strip()
        if remind_at_raw:
            try:
                return (0, datetime.fromisoformat(remind_at_raw), fact.ts)
            except Exception:
                pass
        return (1, fact.ts, fact.ts)

    facts.sort(key=sort_key)
    return facts


def _resolve_reminder_id(ctx: ToolContext, raw_ref: str) -> str:
    """
    功能：把提醒 ID 或序号引用统一解析成真实提醒 ID。
    输入：工具上下文 `ctx`、原始引用 `raw_ref`。
    输出：真实提醒 ID；解析失败返回空字符串。
    """
    ref = (raw_ref or "").strip()
    if not ref:
        return ""
    if ref.startswith("rf_"):
        return ref
    order = _parse_order_ref(ref)
    if order is None:
        return ""
    facts = _ordered_reminders(ctx)
    if 1 <= order <= len(facts):
        return facts[order - 1].id
    return ""


def normalize_remind_delete_call(tool_call: ToolCall, ctx: ToolContext) -> ToolCall:
    """
    功能：在真正执行前把提醒删除参数规范化为真实提醒 ID。
    输入：工具调用 `tool_call`、工具上下文 `ctx`。
    输出：参数已归一化的新 `ToolCall`。
    """
    raw_ref = str(tool_call.arguments.get("id", "")).strip()
    resolved_id = _resolve_reminder_id(ctx, raw_ref)
    if not resolved_id:
        return tool_call
    return ToolCall(
        tool=tool_call.tool,
        arguments={**tool_call.arguments, "id": resolved_id},
        confidence=tool_call.confidence,
        raw=tool_call.raw,
        source=tool_call.source,
    )


def handle_remind_add(match: re.Match[str], ctx: ToolContext) -> ToolResult:
    """
    功能：新增一条提醒并写入审计。
    输入：命令匹配结果 `match`、工具上下文 `ctx`。
    输出：新增结果文本。
    """
    store = _remind_store(ctx)
    if store is None:
        return ToolResult(ok=False, tool="remind_add", error="unavailable", display_text="提醒创建失败。")
    remind_text = (match.group(1) or "").strip()
    content = (match.group(2) or "").strip()
    now = now_beijing()
    remind_date = resolve_due_date(user_message=remind_text, llm_due_date="")
    remind_at = resolve_remind_at(user_message=remind_text, anchor=now)
    if not remind_at:
        return ToolResult(
            ok=False,
            tool="remind_add",
            arguments={"time_expr": remind_text, "content": content},
            error="invalid_time",
            display_text="提醒创建失败。",
            data={"reason": "invalid_time"},
        )
    stored = store.upsert(
        ReminderFact(
            id="",
            content=content,
            remind_text=remind_text,
            remind_date=remind_date,
            remind_at=remind_at,
            source="command",
            ts=now,
            status="active",
        )
    )
    return ToolResult(
        ok=True,
        tool="remind_add",
        arguments={"time_expr": remind_text, "content": content},
        display_text="提醒创建成功。",
        data={
            "id": stored.id,
            "content": stored.content,
            "remind_text": stored.remind_text,
            "remind_date": stored.remind_date,
            "remind_at": stored.remind_at,
        },
    )


def handle_remind_list(_match: re.Match[str], ctx: ToolContext) -> str:
    """
    功能：列出当前未删除的提醒。
    输入：命令匹配结果 `_match`、工具上下文 `ctx`。
    输出：提醒列表文本。
    """
    store = _remind_store(ctx)
    if store is None:
        return "[Remind] unavailable"
    facts = _ordered_reminders(ctx)
    if not facts:
        return "[Remind] empty"
    lines = ["[Remind]"]
    for idx, fact in enumerate(facts, start=1):
        date_part = f" | date={fact.remind_date}" if fact.remind_date else ""
        at_part = f" | at={fact.remind_at}" if getattr(fact, "remind_at", "") else ""
        lines.append(
            f"- #{idx} | {fact.id} | when={fact.remind_text}{date_part}{at_part} | conf={fact.confidence:.2f} | {fact.content}"
        )
    return "\n".join(lines)


def handle_remind_delete(match: re.Match[str], ctx: ToolContext) -> ToolResult:
    """
    功能：删除一条提醒并写入审计。
    输入：命令匹配结果 `match`、工具上下文 `ctx`。
    输出：删除结果文本。
    """
    store = _remind_store(ctx)
    if store is None:
        return ToolResult(ok=False, tool="remind_delete", error="unavailable", display_text="提醒删除失败。")
    raw_ref = (match.group(1) or "").strip()
    fact_id = _resolve_reminder_id(ctx, raw_ref)
    if not fact_id:
        return ToolResult(
            ok=False,
            tool="remind_delete",
            arguments={"id": raw_ref},
            error="not_found",
            display_text="提醒删除失败。",
            data={"id": raw_ref, "deleted": False},
        )
    ok = store.delete(fact_id)
    return ToolResult(
        ok=ok,
        tool="remind_delete",
        arguments={"id": raw_ref},
        error="" if ok else "not_found",
        display_text="提醒删除成功。" if ok else "提醒删除失败。",
        data={"id": fact_id, "deleted": ok},
    )


REMIND_MANIFESTS: dict[str, ToolManifest] = {
    "remind_add": build_manifest(
        "remind_add",
        description="新增一条提醒，格式为时间表达 | 提醒内容。",
        action="remind_add",
        command_pattern="/remind add <time_expr> | <content>",
        intent_examples=["提醒我明天开会", "新增提醒", "设一个提醒"],
        tags=["reminder", "create", "write"],
        read_only=False,
        risk_level="low",
        arg_names=["time_expr", "content"],
        required_args=["time_expr", "content"],
        args_schema={"time_expr": "提醒时间表达", "content": "提醒内容"},
        confirm_required=False,
        confirm_message="",
    ),
    "remind_list": build_manifest(
        "remind_list",
        description="查看当前未删除的提醒。",
        action="remind_list",
        command_pattern="/remind list",
        intent_examples=["查看提醒", "我有哪些提醒", "提醒列表"],
        tags=["reminder", "list", "read"],
        read_only=True,
        arg_names=[],
        required_args=[],
        args_schema={},
    ),
    "remind_delete": build_manifest(
        "remind_delete",
        description="删除一条提醒。",
        action="remind_delete",
        command_pattern="/remind delete <id>",
        intent_examples=["删除提醒", "移除这个提醒", "删除第一个提醒", "删掉第2条提醒"],
        tags=["reminder", "delete", "write"],
        read_only=False,
        risk_level="low",
        arg_names=["id"],
        required_args=["id"],
        args_schema={"id": "提醒 ID 或序号，支持 rf_xxx、1、第一个等"},
        confirm_required=False,
        confirm_message="",
    ),
}
