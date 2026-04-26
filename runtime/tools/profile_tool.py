from __future__ import annotations

import re

from capabilities.memory.persona.context import _delete_persona_line, _load_persona_lines
from .base import ToolCall, ToolContext, ToolManifest, build_manifest


def _parse_order_ref(text: str) -> int | None:
    """
    功能：把画像序号引用解析成正整数序号。
    输入：原始引用文本 `text`。
    输出：解析成功返回 1-based 序号，否则返回 `None`。
    """
    raw = (text or "").strip()
    if not raw:
        return None
    digit = re.search(r"第?\s*(\d+)\s*(个|条|点)?", raw)
    if digit:
        value = int(digit.group(1))
        return value if value > 0 else None
    zh_map = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    zh = re.search(r"第?\s*([一二两三四五六七八九十]+)\s*(个|条|点)?", raw)
    if not zh:
        return None
    token = zh.group(1)
    if token in zh_map:
        return zh_map[token]
    return None


def _ordered_profiles(ctx: ToolContext):
    """
    功能：返回按当前列表顺序排列的画像事实。
    输入：工具上下文 `ctx`。
    输出：画像事实列表。
    """
    _ = ctx
    return list(_load_persona_lines())


def _resolve_profile_id(ctx: ToolContext, raw_ref: str) -> str:
    """
    功能：把画像 ID 或序号引用转换成真实画像 ID。
    输入：工具上下文 `ctx`、原始引用 `raw_ref`。
    输出：真实画像序号；解析失败返回空字符串。
    """
    ref = (raw_ref or "").strip()
    if not ref:
        return ""
    order = _parse_order_ref(ref)
    if order is None:
        return ""
    facts = _ordered_profiles(ctx)
    if 1 <= order <= len(facts):
        return str(order)
    return ""


def normalize_profile_delete_call(tool_call: ToolCall, ctx: ToolContext) -> ToolCall:
    """
    功能：在真正执行前把画像删除参数规范化为真实画像 ID。
    输入：工具调用 `tool_call`、工具上下文 `ctx`。
    输出：参数已归一化的新 `ToolCall`。
    """
    raw_ref = str(tool_call.arguments.get("id", "")).strip()
    resolved_id = _resolve_profile_id(ctx, raw_ref)
    if not resolved_id:
        return tool_call
    return ToolCall(
        tool=tool_call.tool,
        arguments={**tool_call.arguments, "id": resolved_id},
        confidence=tool_call.confidence,
        raw=tool_call.raw,
        source=tool_call.source,
    )


def handle_profile_list(_match: re.Match[str], ctx: ToolContext) -> str:
    """
    功能：列出当前生效的用户画像事实。
    输入：命令匹配结果 `_match`、工具上下文 `ctx`。
    输出：画像列表文本。
    """
    facts = _ordered_profiles(ctx)
    if not facts:
        return "[Profile] empty"
    lines = ["[Profile]"]
    for idx, fact in enumerate(facts, start=1):
        lines.append(f"- #{idx} | {fact}")
    return "\n".join(lines)


def handle_profile_delete(match: re.Match[str], ctx: ToolContext) -> str:
    """
    功能：删除一条画像事实。
    输入：命令匹配结果 `match`、工具上下文 `ctx`。
    输出：删除结果文本。
    """
    raw_ref = (match.group(1) or "").strip()
    fact_id = _resolve_profile_id(ctx, raw_ref)
    if not fact_id:
        return f"[Profile] delete {raw_ref}: not_found"
    ok = _delete_persona_line(int(fact_id))
    return f"[Profile] delete #{fact_id}: {'ok' if ok else 'not_found'}"


PROFILE_MANIFESTS: dict[str, ToolManifest] = {
    "profile_list": build_manifest(
        "profile_list",
        description="查看当前生效的用户画像事实。",
        action="profile_list",
        command_pattern="/profile list",
        intent_examples=["我的偏好有哪些", "查看画像", "当前记住了什么偏好"],
        tags=["profile", "list", "memory"],
        read_only=True,
        arg_names=[],
        required_args=[],
        args_schema={},
    ),
    "profile_delete": build_manifest(
        "profile_delete",
        description="删除一条画像事实。",
        action="profile_delete",
        command_pattern="/profile delete <id>",
        intent_examples=["删除这条画像", "清除偏好记录", "删除第三条画像", "删除第三和第四点画像"],
        tags=["profile", "delete", "memory"],
        read_only=False,
        risk_level="high",
        arg_names=["id"],
        required_args=["id"],
        args_schema={"id": "画像序号，支持 3、第三个等"},
        confirm_required=True,
        confirm_message="将删除这条画像记忆，是否确认？",
    ),
}
