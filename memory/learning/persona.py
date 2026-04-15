from __future__ import annotations

from ..models.schemas import ProfileFact


def build_persona_context(facts: list[ProfileFact], min_confidence: float = 0.7, max_items: int = 6) -> str:
    """
    功能：把高置信画像事实拼接为 Persona 上下文。
    输入：画像事实列表、最小置信度、最大条目数。
    输出：可注入 Prompt 的 Persona 文本。
    """
    selected = [f for f in facts if f.status == "active" and f.confidence >= min_confidence]
    selected = selected[:max_items]
    if not selected:
        return ""
    lines = ["[Persona Context]"]
    for f in selected:
        lines.append(f"- {f.key}: {f.value} (conf={f.confidence:.2f})")
    return "\n".join(lines)
