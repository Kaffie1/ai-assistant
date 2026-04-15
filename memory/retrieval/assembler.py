from __future__ import annotations

from ..models.schemas import RetrievalResult


def _build_reason(r: RetrievalResult) -> str:
    """
    功能：将分项得分转换为可读入选原因。
    输入：单条检索结果 `r`。
    输出：中文原因描述字符串。
    """
    reasons: list[str] = []
    if r.semantic_score >= 0.45:
        reasons.append("语义匹配度高")
    elif r.semantic_score >= 0.25:
        reasons.append("语义相关")

    if r.lexical_score >= 0.15:
        reasons.append("关键词重合明显")
    elif r.lexical_score >= 0.05:
        reasons.append("有关键词重合")

    if r.graph_score >= 0.9:
        reasons.append("图关系连接强")
    elif r.graph_score >= 0.6:
        reasons.append("图关系有支撑")

    if r.recency_score >= 0.9:
        reasons.append("时间上较新")

    if r.node.importance >= 0.7:
        reasons.append("记忆重要性高")

    if not reasons:
        reasons.append("综合分进入候选前列")
    return "，".join(reasons)


def assemble_context(results: list[RetrievalResult], max_items: int = 8) -> str:
    """
    功能：把检索结果组装为 Prompt 上下文文本。
    输入：检索结果列表 `results`，最大条目数 `max_items`。
    输出：格式化后的上下文字符串。
    """
    lines = ["[记忆上下文]"]
    for idx, r in enumerate(results[:max_items], start=1):
        lines.append(
            (
                f"{idx}. ({r.node.id}) 总分={r.final_score:.3f} "
                f"[语义={r.semantic_score:.3f}, 关键词={r.lexical_score:.3f}, 图谱={r.graph_score:.3f}, 时效={r.recency_score:.3f}, 重要性={r.node.importance:.3f}] "
                f"\n   入选原因: {_build_reason(r)}"
                f"\n   记忆内容: {r.node.text}"
            )
        )
    return "\n".join(lines)
