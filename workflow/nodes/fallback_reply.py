from __future__ import annotations

from time import perf_counter
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from prompts import build_chat_system_prompt
from workflow.nodes.services import get_llm, get_logger
from workflow.state import State


def _generate_reply(user_text: str, profile_ctx: str) -> str:
    """
    功能：生成本地兜底回复。
    输入：用户输入 `user_text`、画像上下文 `profile_ctx`。
    输出：兜底回复文本。
    """
    if any(k in user_text for k in ("你是谁", "你是干嘛的", "你能做什么")):
        return "我是你的定制化 AI 助手（秘书型）。我会学习你的偏好并持续个性化。"
    if any(k in user_text for k in ("你记住了什么", "我的偏好", "画像")):
        return f"我当前记住的画像如下：\n{profile_ctx}" if profile_ctx else "我还没有稳定画像。"
    return "我已收到，这条信息会进入后续对话上下文。"


def _generate_reply_with_llm(llm: Any, user_text: str, profile_ctx: str, memory_ctx: str = "", recent_ctx: str = "") -> str:
    """
    功能：调用聊天模型生成回复。
    输入：模型实例 `llm`、用户输入 `user_text`、画像上下文 `profile_ctx`、短期上下文 `recent_ctx`。
    输出：模型生成的回复文本。
    """
    system_text = build_chat_system_prompt(profile_ctx=profile_ctx, memory_ctx=memory_ctx, recent_ctx=recent_ctx)
    resp = llm.invoke([SystemMessage(content=system_text), HumanMessage(content=user_text)])
    content = getattr(resp, "content", "")
    if isinstance(content, str):
        return content.strip() or "我暂时没有生成到有效回复，请你再说一次。"
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        merged = "\n".join(x.strip() for x in parts if x and x.strip())
        return merged or "我暂时没有生成到有效回复，请你再说一次。"
    return "我暂时没有生成到有效回复，请你再说一次。"


def fallback_reply_node(state: State) -> State:
    """
    功能：执行普通回复节点。
    输入：当前流程状态 `state`。
    输出：写回 `reply_text` 和 `reply_ms` 的状态增量。
    """
    t_reply_start = perf_counter()
    user_text = str(state.get("user_text", "") or "")
    profile_ctx = str(state.get("profile_ctx", "") or "")
    memory_ctx = str(state.get("memory_ctx", "") or "")
    recent_ctx = str(state.get("recent_ctx", "") or "")
    llm = get_llm()
    if llm is not None:
        try:
            assistant_text = _generate_reply_with_llm(
                llm=llm,
                user_text=user_text,
                profile_ctx=profile_ctx,
                memory_ctx=memory_ctx,
                recent_ctx=recent_ctx,
            )
        except Exception as exc:
            get_logger().exception("chat llm invoke failed, fallback to local")
            _ = exc
            assistant_text = _generate_reply(user_text=user_text, profile_ctx=profile_ctx)
    else:
        assistant_text = _generate_reply(user_text=user_text, profile_ctx=profile_ctx)
    return {"reply_text": assistant_text, "reply_ms": (perf_counter() - t_reply_start) * 1000.0}
