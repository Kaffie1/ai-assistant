from __future__ import annotations

from dataclasses import replace
from threading import Lock
from uuid import uuid4

from foundation.time_utils import now_beijing
from .tools.base import PendingAction, ToolCall, ToolManifest

_PENDING_LOCK = Lock()
_CURRENT_PENDING: PendingAction | None = None


def _batch_confirm_message(tool_calls: list[ToolCall], manifests: list[ToolManifest]) -> str:
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


def create_pending_action(tool_calls: list[ToolCall], manifests: list[ToolManifest]) -> PendingAction:
    """
    功能：创建新的待确认高风险操作，并覆盖当前旧 pending。
    输入：工具调用列表 `tool_calls`、对应工具 manifest 列表 `manifests`。
    输出：新建的 `PendingAction`。
    """
    global _CURRENT_PENDING
    pending = PendingAction(
        id=f"pa_{uuid4().hex[:12]}",
        tool_calls=[ToolCall(tool=call.tool, arguments=dict(call.arguments), confidence=call.confidence, raw=call.raw, source=call.source) for call in tool_calls],
        confirm_message=_batch_confirm_message(tool_calls, manifests),
        source=tool_calls[0].source if tool_calls else "llm",
    )
    with _PENDING_LOCK:
        _CURRENT_PENDING = pending
    return pending


def get_pending_action() -> PendingAction | None:
    """
    功能：获取当前待确认操作，若已过期则自动清除。
    输入：无。
    输出：`PendingAction` 或 `None`。
    """
    global _CURRENT_PENDING
    with _PENDING_LOCK:
        if _CURRENT_PENDING is None:
            return None
        if _CURRENT_PENDING.expires_at <= now_beijing():
            _CURRENT_PENDING = None
            return None
        return replace(_CURRENT_PENDING)


def clear_pending_action() -> None:
    """
    功能：清除当前待确认操作。
    输入：无。
    输出：无。
    """
    global _CURRENT_PENDING
    with _PENDING_LOCK:
        _CURRENT_PENDING = None


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
