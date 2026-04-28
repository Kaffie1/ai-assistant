from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from foundation.config import MAMGA_LONG_TERM_MEMORY_RULES_PATH


class LongTermMemoryRuleSet(BaseModel):
    """
    长期记忆抽取规则配置。
    """

    min_text_length: int = Field(default=8, description="候选文本最短长度。")
    max_text_length: int = Field(default=200, description="候选文本最长长度。")
    allow_categories: dict[str, list[str]] = Field(default_factory=dict, description="允许写入的类别关键词。")
    trigger_keywords: list[str] = Field(default_factory=list, description="显式触发长期记忆写入的关键词。")
    reject_keywords: list[str] = Field(default_factory=list, description="直接拒绝写入的关键词。")
    temporary_keywords: list[str] = Field(default_factory=list, description="临时性表达关键词。")
    uncertainty_keywords: list[str] = Field(default_factory=list, description="不确定表达关键词。")
    ignore_exact_texts: list[str] = Field(default_factory=list, description="完全忽略的文本列表。")
    importance_by_category: dict[str, float] = Field(default_factory=dict, description="不同类别默认重要性。")


class LongTermMemoryDecision(BaseModel):
    """
    长期记忆写入决策结果。
    """

    should_write: bool = Field(default=False, description="是否写入长期记忆。")
    text: str = Field(default="", description="待写入的规范化文本。")
    kind: str = Field(default="fact", description="记忆类别。")
    importance: float = Field(default=0.5, description="记忆重要性。")
    tags: list[str] = Field(default_factory=list, description="建议标签。")
    reason: str = Field(default="", description="决策原因。")


def _normalize_text(text: str) -> str:
    """
    功能：规范化用户文本，便于规则判断。
    输入：原始文本 `text`。
    输出：压缩空白后的文本。
    """
    return " ".join(str(text or "").strip().split())


def _contains_any(text: str, keywords: list[str]) -> bool:
    """
    功能：判断文本是否包含任一关键词。
    输入：文本 `text`、关键词列表 `keywords`。
    输出：命中返回 `True`，否则返回 `False`。
    """
    lowered = text.lower()
    for keyword in keywords:
        token = str(keyword or "").strip().lower()
        if token and token in lowered:
            return True
    return False


def _match_category(text: str, categories: dict[str, list[str]]) -> str:
    """
    功能：根据配置判断文本命中的长期记忆类别。
    输入：文本 `text`、类别关键词映射 `categories`。
    输出：命中的类别；未命中返回空字符串。
    """
    lowered = text.lower()
    for category, keywords in categories.items():
        for keyword in keywords:
            token = str(keyword or "").strip().lower()
            if token and token in lowered:
                return str(category or "").strip() or "fact"
    return ""


def load_long_term_memory_rules() -> LongTermMemoryRuleSet:
    """
    功能：从独立配置文件加载长期记忆抽取规则。
    输入：无。
    输出：规则配置对象；读取失败时返回默认规则。
    """
    path = Path(MAMGA_LONG_TERM_MEMORY_RULES_PATH)
    if not path.exists():
        return LongTermMemoryRuleSet()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return LongTermMemoryRuleSet()
        return LongTermMemoryRuleSet.model_validate(payload)
    except Exception:
        return LongTermMemoryRuleSet()


def decide_long_term_memory_write(user_text: str) -> LongTermMemoryDecision:
    """
    功能：判断用户输入是否应写入长期记忆。
    输入：用户输入文本 `user_text`。
    输出：长期记忆写入决策结果。
    """
    rules = load_long_term_memory_rules()
    normalized = _normalize_text(user_text)
    if not normalized:
        return LongTermMemoryDecision(reason="empty")
    if normalized in {item.strip() for item in rules.ignore_exact_texts if str(item).strip()}:
        return LongTermMemoryDecision(reason="ignored_text")
    if len(normalized) < max(1, rules.min_text_length):
        return LongTermMemoryDecision(reason="too_short")
    if len(normalized) > max(rules.min_text_length, rules.max_text_length):
        return LongTermMemoryDecision(reason="too_long")
    if _contains_any(normalized, rules.reject_keywords):
        return LongTermMemoryDecision(reason="reject_keyword")
    if _contains_any(normalized, rules.temporary_keywords):
        return LongTermMemoryDecision(reason="temporary")
    if _contains_any(normalized, rules.uncertainty_keywords):
        return LongTermMemoryDecision(reason="uncertain")

    category = _match_category(normalized, rules.allow_categories)
    explicit_trigger = _contains_any(normalized, rules.trigger_keywords)
    if not category:
        if explicit_trigger:
            return LongTermMemoryDecision(reason="explicit_but_not_long_term")
        return LongTermMemoryDecision(reason="no_signal")

    kind = category
    importance = float(rules.importance_by_category.get(kind, 0.5))
    tags = [kind]
    if explicit_trigger:
        tags.append("explicit")
        importance = max(importance, 0.7)

    return LongTermMemoryDecision(
        should_write=True,
        text=normalized,
        kind=kind,
        importance=importance,
        tags=sorted(set(tags)),
        reason="matched_rule",
    )
