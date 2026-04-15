from __future__ import annotations


def build_chat_system_prompt(persona_ctx: str, memory_ctx: str) -> str:
    """
    功能：构建聊天回复使用的系统提示词。
    输入：画像上下文 `persona_ctx`，记忆上下文 `memory_ctx`。
    输出：拼接后的系统提示词文本。
    """
    system_text = (
        "你是用户的秘书型 AI 助手。请使用中文，简洁但有帮助。"
        "优先遵循 Persona Context，再结合 Memory Context 回答。"
        "当记忆不足时明确说明并给出下一步建议。"
    )
    if persona_ctx:
        system_text += f"\n\n{persona_ctx}"
    if memory_ctx:
        system_text += f"\n\n{memory_ctx}"
    return system_text
