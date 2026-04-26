from __future__ import annotations


def build_tool_selection_prompt(*, profile_ctx: str, memory_ctx: str, tool_catalog: str, recent_ctx: str = "") -> str:
    """
    功能：构建 LLM 选择工具时使用的系统提示词。
    输入：画像上下文 `profile_ctx`、记忆上下文 `memory_ctx`、工具目录 `tool_catalog`、最近对话上下文 `recent_ctx`。
    输出：系统提示词文本。
    """
    parts = [
        "你是工具选择器。你的任务是根据用户问题，从给定工具目录中选择最合适的工具并填写参数。",
        '只输出 JSON。单个操作时格式为 {"tool":"工具名或none","arguments":{},"confidence":0到1之间的数字}。',
        '如果用户明确要求同时操作多个对象，请输出 {"tool_calls":[{"tool":"工具名","arguments":{},"confidence":0到1之间的数字}]}。',
        "如果用户只是讨论需求、解释概念、进行闲聊，或者参数明显不完整，就返回 tool=none。",
        "当用户说“第三和第四条”“前两个”“第一和第三个”这类多对象表达时，不要只返回第一项，要拆成多个 tool_calls。",
        "不要输出任何 XML、MCP、tool_call 标签，也不要输出解释。",
        "高风险工具也可以选择，但只负责选择，不负责是否确认执行。",
        f"工具目录:\n{tool_catalog or '(empty)'}",
    ]
    if profile_ctx:
        parts.append(f"Profile Context:\n{profile_ctx}")
    if memory_ctx:
        parts.append(f"Memory Context:\n{memory_ctx}")
    if recent_ctx:
        parts.append(f"Recent Conversation Context:\n{recent_ctx}")
    return "\n\n".join(parts)


def build_tool_result_reply_prompt(*, profile_ctx: str, memory_ctx: str, recent_ctx: str = "") -> str:
    """
    功能：构建工具执行后生成最终用户回复的系统提示词。
    输入：画像上下文 `profile_ctx`、记忆上下文 `memory_ctx`、最近对话上下文 `recent_ctx`。
    输出：系统提示词文本。
    """
    parts = [
        "你是用户的秘书型 AI 助手。请用中文自然地向用户说明工具执行结果。",
        "不要展示任何内部路由、JSON、命令名、函数名、tool_call 标记。",
        "如果工具执行失败，要明确说明失败原因并给出下一步建议。",
    ]
    if profile_ctx:
        parts.append(f"Profile Context:\n{profile_ctx}")
    if memory_ctx:
        parts.append(f"Memory Context:\n{memory_ctx}")
    if recent_ctx:
        parts.append(f"Recent Conversation Context:\n{recent_ctx}")
    return "\n\n".join(parts)
