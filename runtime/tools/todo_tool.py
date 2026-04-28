from __future__ import annotations

import re

from .base import ToolCall, ToolContext, ToolManifest, ToolResult, build_manifest


def _parse_order_ref(text: str) -> int | None:
    """
    功能：把任务序号引用解析成正整数序号。
    输入：原始引用文本 `text`。
    输出：解析成功返回 1-based 序号，否则返回 `None`。
    """
    raw = (text or "").strip()
    if not raw:
        return None
    digit = re.search(r"第?\s*(\d+)\s*(个|条|项)?", raw)
    if digit:
        value = int(digit.group(1))
        return value if value > 0 else None
    zh_map = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    zh = re.search(r"第?\s*([一二两三四五六七八九十]+)\s*(个|条|项)?", raw)
    if not zh:
        return None
    token = zh.group(1)
    if token in zh_map:
        return zh_map[token]
    return None


def _ordered_tasks(ctx: ToolContext, *, status: str = "active"):
    """
    功能：返回按当前列表顺序排列的任务事实。
    输入：工具上下文 `ctx`、任务状态 `status`。
    输出：任务事实列表。
    """
    if status == "done":
        return [fact for fact in ctx.task_store.list_history() if str(getattr(fact, "status", "")) == "done"]
    return list(ctx.task_store.list())


def _resolve_task_id(ctx: ToolContext, raw_ref: str, *, status: str = "active") -> str:
    """
    功能：把任务 ID 或序号引用转换成真实任务 ID。
    输入：工具上下文 `ctx`、原始引用 `raw_ref`、任务状态 `status`。
    输出：真实任务 ID；解析失败返回空字符串。
    """
    ref = (raw_ref or "").strip()
    if not ref:
        return ""
    if ref.startswith("tf_"):
        return ref
    order = _parse_order_ref(ref)
    if order is None:
        return ""
    facts = _ordered_tasks(ctx, status=status)
    if 1 <= order <= len(facts):
        return facts[order - 1].id
    return ""


def normalize_todo_done_call(tool_call: ToolCall, ctx: ToolContext) -> ToolCall:
    """
    功能：在真正执行前把任务完成参数规范化为真实任务 ID。
    输入：工具调用 `tool_call`、工具上下文 `ctx`。
    输出：参数已归一化的新 `ToolCall`。
    """
    raw_ref = str(tool_call.arguments.get("id", "")).strip()
    resolved_id = _resolve_task_id(ctx, raw_ref, status="active")
    if not resolved_id:
        return tool_call
    return ToolCall(
        tool=tool_call.tool,
        arguments={**tool_call.arguments, "id": resolved_id},
        confidence=tool_call.confidence,
        raw=tool_call.raw,
        source=tool_call.source,
    )


def normalize_todo_delete_call(tool_call: ToolCall, ctx: ToolContext) -> ToolCall:
    """
    功能：在真正执行前把任务删除参数规范化为真实任务 ID。
    输入：工具调用 `tool_call`、工具上下文 `ctx`。
    输出：参数已归一化的新 `ToolCall`。
    """
    raw_ref = str(tool_call.arguments.get("id", "")).strip()
    resolved_id = _resolve_task_id(ctx, raw_ref, status="active")
    if not resolved_id:
        return tool_call
    return ToolCall(
        tool=tool_call.tool,
        arguments={**tool_call.arguments, "id": resolved_id},
        confidence=tool_call.confidence,
        raw=tool_call.raw,
        source=tool_call.source,
    )


def handle_todo_list(_match: re.Match[str], ctx: ToolContext) -> ToolResult:
    """
    功能：列出当前未完成任务。
    输入：命令匹配结果 `_match`、工具上下文 `ctx`。
    输出：待办任务文本。
    """
    facts = ctx.task_store.list()
    if not facts:
        return ToolResult(ok=True, tool="todo_list", display_text="[Todo] empty", data={"items": []})
    lines = ["[Todo]"]
    for idx, fact in enumerate(facts, start=1):
        due = f" | due={fact.due_date}" if fact.due_date else ""
        lines.append(f"- #{idx} | {fact.id}{due} | conf={fact.confidence:.2f} | {fact.content}")
    return ToolResult(
        ok=True,
        tool="todo_list",
        display_text="\n".join(lines),
        data={
            "items": [
                {
                    "id": fact.id,
                    "content": fact.content,
                    "due_date": fact.due_date,
                    "confidence": fact.confidence,
                    "status": fact.status,
                }
                for fact in facts
            ]
        },
    )


def handle_todo_done_list(_match: re.Match[str], ctx: ToolContext) -> ToolResult:
    """
    功能：列出已完成任务。
    输入：命令匹配结果 `_match`、工具上下文 `ctx`。
    输出：已完成任务文本。
    """
    facts = [fact for fact in ctx.task_store.list_history() if str(getattr(fact, "status", "")) == "done"]
    if not facts:
        return ToolResult(ok=True, tool="todo_done_list", display_text="[Todo Done] empty", data={"items": []})
    lines = ["[Todo Done]"]
    for idx, fact in enumerate(facts, start=1):
        due = f" | due={fact.due_date}" if fact.due_date else ""
        lines.append(f"- #{idx} | {fact.id}{due} | conf={fact.confidence:.2f} | {fact.content}")
    return ToolResult(
        ok=True,
        tool="todo_done_list",
        display_text="\n".join(lines),
        data={
            "items": [
                {
                    "id": fact.id,
                    "content": fact.content,
                    "due_date": fact.due_date,
                    "confidence": fact.confidence,
                    "status": fact.status,
                }
                for fact in facts
            ]
        },
    )


def handle_todo_done(match: re.Match[str], ctx: ToolContext) -> ToolResult:
    """
    功能：将任务标记为完成。
    输入：命令匹配结果 `match`、工具上下文 `ctx`。
    输出：完成结果文本。
    """
    raw_ref = (match.group(1) or "").strip()
    fact_id = _resolve_task_id(ctx, raw_ref, status="active")
    if not fact_id:
        return ToolResult(
            ok=False,
            tool="todo_done",
            arguments={"id": raw_ref},
            display_text=f"[Todo] done {raw_ref}: not_found",
            data={"id": raw_ref, "done": False},
            error="not_found",
        )
    ok = ctx.task_store.mark_done(fact_id)
    return ToolResult(
        ok=ok,
        tool="todo_done",
        arguments={"id": raw_ref},
        display_text=f"[Todo] done {fact_id}: {'ok' if ok else 'not_found'}",
        data={"id": fact_id, "done": ok},
        error="" if ok else "not_found",
    )


def handle_todo_delete(match: re.Match[str], ctx: ToolContext) -> ToolResult:
    """
    功能：删除任务。
    输入：命令匹配结果 `match`、工具上下文 `ctx`。
    输出：删除结果文本。
    """
    raw_ref = (match.group(1) or "").strip()
    fact_id = _resolve_task_id(ctx, raw_ref, status="active")
    if not fact_id:
        return ToolResult(
            ok=False,
            tool="todo_delete",
            arguments={"id": raw_ref},
            display_text=f"[Todo] delete {raw_ref}: not_found",
            data={"id": raw_ref, "deleted": False},
            error="not_found",
        )
    ok = ctx.task_store.delete(fact_id)
    return ToolResult(
        ok=ok,
        tool="todo_delete",
        arguments={"id": raw_ref},
        display_text=f"[Todo] delete {fact_id}: {'ok' if ok else 'not_found'}",
        data={"id": fact_id, "deleted": ok},
        error="" if ok else "not_found",
    )


TODO_MANIFESTS: dict[str, ToolManifest] = {
    "todo_list": build_manifest(
        "todo_list",
        description="查看当前未完成的任务。",
        action="todo_list",
        object_label="任务",
        command_pattern="/todo list",
        intent_examples=["还有哪些任务", "查看待办", "今日未完成事项"],
        tags=["task", "todo", "list"],
        read_only=True,
        arg_names=[],
        required_args=[],
        args_schema={},
        direct_response=False,
    ),
    "todo_done_list": build_manifest(
        "todo_done_list",
        description="查看已完成任务。",
        action="todo_done_list",
        object_label="任务",
        command_pattern="/todo done-list",
        intent_examples=["查看已完成任务", "今日完成了什么", "完成列表"],
        tags=["task", "todo", "done"],
        read_only=True,
        arg_names=[],
        required_args=[],
        args_schema={},
        direct_response=False,
    ),
    "todo_done": build_manifest(
        "todo_done",
        description="将任务标记为完成。",
        action="todo_done",
        object_label="任务",
        command_pattern="/todo done <id>",
        intent_examples=["完成这个任务", "标记任务完成", "完成第三个任务", "完成前两个任务"],
        tags=["task", "done", "write"],
        read_only=False,
        risk_level="high",
        arg_names=["id"],
        required_args=["id"],
        args_schema={"id": "任务 ID 或序号，支持 tf_xxx、3、第三个等"},
        confirm_required=True,
        confirm_message="将把这项任务标记为已完成，是否确认？",
        direct_response=True,
    ),
    "todo_delete": build_manifest(
        "todo_delete",
        description="删除任务。",
        action="todo_delete",
        object_label="任务",
        command_pattern="/todo delete <id>",
        intent_examples=["删除这个任务", "移除待办", "删除第三个任务", "删除前两个任务"],
        tags=["task", "delete", "write"],
        read_only=False,
        risk_level="high",
        arg_names=["id"],
        required_args=["id"],
        args_schema={"id": "任务 ID 或序号，支持 tf_xxx、3、第三个等"},
        confirm_required=True,
        confirm_message="将删除这项任务，是否确认？",
        direct_response=True,
    ),
}
