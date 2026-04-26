from __future__ import annotations


def build_chat_system_prompt(profile_ctx: str, memory_ctx: str, recent_ctx: str = "") -> str:
    """
    功能：构建聊天回复使用的系统提示词。
    输入：画像上下文 `profile_ctx`，记忆上下文 `memory_ctx`，最近对话上下文 `recent_ctx`。
    输出：拼接后的系统提示词文本。
    """
    system_text = (
        "你是用户的秘书型 AI 助手。请使用中文，简洁但有帮助。"
        "优先遵循 Profile Context，再结合 Memory Context 回答。"
        "如果 Recent Conversation Context 中存在最近几轮对话，请优先保持上下文连续性。"
        "当记忆不足时明确说明并给出下一步建议。"
        "不要输出任何工具使用过程或工具调用标记，只输出给用户看的最终自然语言结果。"
    )
    if profile_ctx:
        system_text += f"\n\n{profile_ctx}"
    if memory_ctx:
        system_text += f"\n\n{memory_ctx}"
    if recent_ctx:
        system_text += f"\n\nRecent Conversation Context:\n{recent_ctx}"
    return system_text
