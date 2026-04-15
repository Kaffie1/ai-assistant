from __future__ import annotations

import itertools
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

from ..core.contracts import KnowledgeStoreProtocol, ProfileStoreProtocol, TaskStoreProtocol
from ..models.schemas import CandidateFact, KnowledgeFact, LearningEvent, ProfileFact, TaskFact
from ..prompts import LEARNING_EXTRACT_SYSTEM_PROMPT

try:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover - optional dependency guard
    HumanMessage = None  # type: ignore[assignment]
    SystemMessage = None  # type: ignore[assignment]
    ChatOpenAI = None  # type: ignore[assignment]


def _clamp01(value: float) -> float:
    """
    功能：将数值限制在 0~1 区间。
    输入：任意浮点数 `value`。
    输出：归一化后的浮点数。
    """
    return max(0.0, min(1.0, value))


def _safe_float(value: Any, default: float = 0.5) -> float:
    """
    功能：将任意值安全转换为浮点并限制到 0~1。
    输入：原始值 `value` 与默认值 `default`。
    输出：可用的 0~1 浮点数。
    """
    try:
        return _clamp01(float(value))
    except Exception:
        return _clamp01(default)


def _is_profile_candidate_grounded(user_message: str, key: str, value: str) -> bool:
    """
    功能：判断画像候选是否有“长期偏好/设定”语义依据。
    输入：用户消息 `user_message`、画像键 `key`、画像值 `value`。
    输出：可写入返回 True，否则 False。
    """
    text = (user_message or "").strip().lower()
    if not text:
        return False

    explicit_profile_cues = (
        "以后",
        "默认",
        "我希望",
        "我需要",
        "我喜欢",
        "我偏好",
        "我习惯",
        "我通常",
        "我总是",
        "请用",
        "请",
        "请叫我",
        "称呼我",
        "我的时区",
        "我的语言",
        "回答风格",
    )
    if any(cue in text for cue in explicit_profile_cues):
        return True

    # 纯问句通常不应写入画像（除非命中了显式偏好 cue）。
    if "?" in text or "？" in text:
        return False

    key_l = (key or "").strip().lower()
    value_l = (value or "").strip().lower()
    blocked_profile_keys = {
        "interest_topic",
        "current_topic",
        "asked_topic",
        "question_topic",
    }
    if key_l in blocked_profile_keys:
        return False
    if value_l in {"langgraph", "langchain", "rag"} and ("什么是" in text or "how" in text):
        return False
    return False


def _resolve_due_date(user_message: str, llm_due_date: str) -> str:
    """
    功能：将任务截止日期锚定到用户原话，避免模型凭空给日期。
    输入：用户消息与模型给出的 `due_date`。
    输出：规范化 `YYYY-MM-DD` 或空字符串。
    """
    text = (user_message or "").strip()
    if not text:
        return ""
    today = date.today()

    # Explicit absolute date in user text takes highest priority.
    m = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except Exception:
            pass

    if "明天" in text:
        return (today + timedelta(days=1)).isoformat()
    if "后天" in text:
        return (today + timedelta(days=2)).isoformat()
    if "今天" in text:
        return today.isoformat()

    # No explicit due cue in user text -> do not trust LLM date.
    due_cues = ("截止", "到期", "前", "之前", "本周", "下周", "周五", "周末", "明天", "今天", "后天")
    if not any(c in text for c in due_cues):
        return ""

    # If user text has cue but no explicit parse, accept valid LLM date as fallback.
    raw = (llm_due_date or "").strip()
    if not raw:
        return ""
    try:
        return date.fromisoformat(raw[:10]).isoformat()
    except Exception:
        return ""


@lru_cache(maxsize=1)
def _build_learning_llm() -> Any | None:
    """
    功能：按环境变量构建学习抽取专用 LLM 客户端。
    输入：无（读取 `LLM_API_KEY/LLM_BASE_URL/LLM_MODEL`）。
    输出：可调用 LLM 客户端；不可用时返回 `None`。
    """
    if ChatOpenAI is None:
        return None

    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key:
        return None

    model = os.getenv("LLM_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    base_url = os.getenv("LLM_BASE_URL", "").strip() or None

    try:
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=0.0,
            max_tokens=1000,
            streaming=False,
        )
    except Exception:
        return None


def _extract_json_object(raw_text: str) -> dict[str, Any] | None:
    """
    功能：从模型输出中提取 JSON 对象。
    输入：模型原始字符串 `raw_text`。
    输出：解析成功返回 dict，失败返回 `None`。
    """
    text = (raw_text or "").strip()
    if not text:
        return None

    # Handle fenced output like ```json ... ```
    if text.startswith("```"):
        text = text.replace("```json", "").replace("```JSON", "").replace("```", "").strip()

    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        snippet = text[start : end + 1]
        try:
            obj = json.loads(snippet)
            if isinstance(obj, dict):
                return obj
        except Exception:
            # Some providers may return JSON-like text with single quotes.
            try:
                repaired = (
                    snippet.replace("'", '"')
                    .replace("None", "null")
                    .replace("True", "true")
                    .replace("False", "false")
                )
                obj = json.loads(repaired)
                if isinstance(obj, dict):
                    return obj
            except Exception:
                return None
    return None


def _content_to_text(content: Any) -> str:
    """
    功能：把模型 content 统一转为字符串。
    输入：任意类型 content。
    输出：拼接后的文本字符串。
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return str(content or "")


def _llm_extract_payload_with_status(
    user_message: str, assistant_message: str = ""
) -> tuple[dict[str, Any] | None, str, str]:
    """
    功能：调用 LLM 抽取画像与知识候选结构。
    输入：用户消息与助手消息。
    输出：`(payload, status, raw_output)`；status 为 `ok/llm_unavailable/llm_call_error/llm_parse_error`。
    """
    llm = _build_learning_llm()
    if llm is None:
        return None, "llm_unavailable", ""

    system_text = LEARNING_EXTRACT_SYSTEM_PROMPT

    user_text = (
        "[user_message]\n"
        f"{user_message.strip()}\n\n"
        "[assistant_message]\n"
        f"{assistant_message.strip()}"
    )

    messages = (
        [
            SystemMessage(content=system_text),
            HumanMessage(content=user_text),
        ]
        if HumanMessage is not None and SystemMessage is not None
        else f"{system_text}\n\n{user_text}"
    )
    try:
        # First try strict JSON mode for providers that support OpenAI response_format.
        resp = llm.invoke(messages, response_format={"type": "json_object"})
    except Exception:
        try:
            resp = llm.invoke(messages)
        except Exception:
            return None, "llm_call_error", ""

    raw_output = _content_to_text(getattr(resp, "content", ""))
    payload = _extract_json_object(raw_output)
    if payload is None:
        return None, "llm_parse_error", raw_output
    return payload, "ok", raw_output


def _extract_candidate_facts_full(
    user_message: str, assistant_message: str = ""
) -> tuple[list[CandidateFact], str, str]:
    """
    功能：返回候选事实、原因与原始 LLM 输出（调试用）。
    输入：用户消息 `user_message`，助手消息 `assistant_message`。
    输出：`(候选事实列表, reason, raw_output)`。
    """
    payload, status, raw_output = _llm_extract_payload_with_status(
        user_message=user_message, assistant_message=assistant_message
    )
    if payload is None:
        return [], status, raw_output

    candidates = _parse_candidate_facts(payload, user_message=user_message, assistant_message=assistant_message)

    unique: dict[str, CandidateFact] = {}
    for c in candidates:
        if c.fact_type == "profile":
            sig = f"profile:{c.key}:{c.value}"
        elif c.fact_type == "task":
            sig = f"task:{c.content}:{c.due_date}"
        else:
            sig = f"knowledge:{c.topic}:{c.statement}"
        if sig not in unique or c.confidence > unique[sig].confidence:
            unique[sig] = c
    deduped = list(unique.values())
    if not deduped:
        return [], "llm_ok_no_fact", raw_output
    return deduped, "ok", raw_output


def _parse_candidate_facts(payload: dict[str, Any], user_message: str, assistant_message: str) -> list[CandidateFact]:
    """
    功能：将 LLM 抽取载荷转换为 `CandidateFact` 列表。
    输入：JSON 载荷、用户消息、助手消息。
    输出：候选事实列表。
    """
    out: list[CandidateFact] = []
    default_evidence = [x for x in [user_message.strip(), assistant_message.strip()] if x]

    profile_items = payload.get("profile", [])
    if isinstance(profile_items, list):
        for item in profile_items:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key", "")).strip()
            value = str(item.get("value", "")).strip()
            if not key or not value:
                continue
            if not _is_profile_candidate_grounded(user_message=user_message, key=key, value=value):
                continue
            ev = str(item.get("evidence", "")).strip()
            out.append(
                CandidateFact(
                    fact_type="profile",
                    key=key,
                    value=value,
                    confidence=_safe_float(item.get("confidence", 0.7), default=0.7),
                    category=str(item.get("category", "preference")).strip() or "preference",
                    evidence=[ev] if ev else default_evidence,
                )
            )

    knowledge_items = payload.get("knowledge", [])
    if isinstance(knowledge_items, list):
        for item in knowledge_items:
            if not isinstance(item, dict):
                continue
            statement = str(item.get("statement", "")).strip()
            if not statement:
                continue
            topic = str(item.get("topic", "general")).strip() or "general"
            ev = str(item.get("evidence", "")).strip()
            out.append(
                CandidateFact(
                    fact_type="knowledge",
                    topic=topic,
                    statement=statement,
                    confidence=_safe_float(item.get("confidence", 0.65), default=0.65),
                    category=str(item.get("category", "knowledge")).strip() or "knowledge",
                    evidence=[ev] if ev else default_evidence,
                )
            )

    task_items = payload.get("tasks", [])
    if isinstance(task_items, list):
        for item in task_items:
            if not isinstance(item, dict):
                continue
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            due_date = _resolve_due_date(
                user_message=user_message,
                llm_due_date=str(item.get("due_date", "")).strip(),
            )
            ev = str(item.get("evidence", "")).strip()
            out.append(
                CandidateFact(
                    fact_type="task",
                    content=content,
                    due_date=due_date,
                    task_status="active",
                    confidence=_safe_float(item.get("confidence", 0.7), default=0.7),
                    category=str(item.get("category", "task")).strip() or "task",
                    evidence=[ev] if ev else default_evidence,
                )
            )

    return out


def extract_candidate_facts_with_reason(
    user_message: str, assistant_message: str = ""
) -> tuple[list[CandidateFact], str]:
    """
    功能：基于 LLM 抽取并去重候选事实。
    输入：用户消息 `user_message`，助手消息 `assistant_message`。
    输出：`(候选事实列表, reason)`。
    """
    facts, reason, _ = _extract_candidate_facts_full(
        user_message=user_message, assistant_message=assistant_message
    )
    return facts, reason


def extract_candidate_facts(user_message: str, assistant_message: str = "") -> list[CandidateFact]:
    """
    功能：基于 LLM 抽取并去重候选事实（兼容旧接口）。
    输入：用户消息 `user_message`，助手消息 `assistant_message`。
    输出：去重后的候选事实列表；抽取失败时返回空列表。
    """
    facts, _ = extract_candidate_facts_with_reason(
        user_message=user_message, assistant_message=assistant_message
    )
    return facts


class LearningPipeline:
    def __init__(
        self,
        profile_store: ProfileStoreProtocol,
        knowledge_store: KnowledgeStoreProtocol,
        task_store: TaskStoreProtocol,
        disabled_categories: set[str] | None = None,
    ) -> None:
        """
        功能：初始化学习流水线。
        输入：画像存储、知识存储、可选禁写分类集合。
        输出：无，保存依赖供单轮学习使用。
        """
        self.profile_store = profile_store
        self.knowledge_store = knowledge_store
        self.task_store = task_store
        self.disabled_categories = disabled_categories or set()
        self._counter = itertools.count(1)
        self.last_candidates: list[CandidateFact] = []
        self.last_extract_reason: str = "init"
        self.last_extract_raw_output: str = ""

    def learn_from_turn(
        self,
        user_message: str,
        assistant_message: str = "",
        source: str = "dialog",
    ) -> LearningEvent:
        """
        功能：处理单轮对话学习并写入事实库。
        输入：用户消息、助手消息、来源标识。
        输出：`LearningEvent`（提取数量、写入结果、拒绝项）。
        """
        now = datetime.now(timezone.utc)
        candidates, reason, raw_output = _extract_candidate_facts_full(
            user_message=user_message, assistant_message=assistant_message
        )
        self.last_candidates = list(candidates)
        self.last_extract_reason = reason
        self.last_extract_raw_output = raw_output

        upserted_profile_ids: list[str] = []
        upserted_knowledge_ids: list[str] = []
        upserted_task_ids: list[str] = []
        rejected: list[str] = []

        for c in candidates:
            if c.category in self.disabled_categories:
                rejected.append(f"{c.fact_type}:{c.category}")
                continue

            if c.fact_type == "profile" and c.key and c.value:
                stored = self.profile_store.upsert(
                    ProfileFact(
                        id="",
                        key=c.key,
                        value=c.value,
                        confidence=c.confidence,
                        source=source,
                        ts=now,
                    )
                )
                upserted_profile_ids.append(stored.id)
                continue

            if c.fact_type == "knowledge" and c.statement:
                stored = self.knowledge_store.upsert(
                    KnowledgeFact(
                        id="",
                        topic=c.topic or "general",
                        statement=c.statement,
                        confidence=c.confidence,
                        source=source,
                        evidence=c.evidence,
                        ts=now,
                    )
                )
                upserted_knowledge_ids.append(stored.id)
                continue

            if c.fact_type == "task" and c.content:
                stored = self.task_store.upsert(
                    TaskFact(
                        id="",
                        content=c.content,
                        due_date=c.due_date,
                        confidence=c.confidence,
                        source=source,
                        evidence=c.evidence,
                        ts=now,
                        status="active",
                    )
                )
                upserted_task_ids.append(stored.id)

        if candidates:
            final_reason = "ok"
        else:
            final_reason = reason
        return LearningEvent(
            id=f"le_{next(self._counter):06d}",
            extracted_count=len(candidates),
            upserted_profile_ids=upserted_profile_ids,
            upserted_knowledge_ids=upserted_knowledge_ids,
            upserted_task_ids=upserted_task_ids,
            rejected=rejected,
            reason=final_reason,
            ts=now,
        )

    def feedback_correct(self, fact_id: str, new_value: str) -> bool:
        """
        功能：执行用户纠错并生成新版本事实。
        输入：事实 ID `fact_id`，修正值 `new_value`。
        输出：是否纠错成功（True/False）。
        """
        profile = self.profile_store.get(fact_id)
        if profile is not None:
            self.profile_store.downgrade_and_mark(fact_id=profile.id, factor=0.3, status="superseded")
            self.profile_store.upsert(
                ProfileFact(
                    id="",
                    key=profile.key,
                    value=new_value,
                    confidence=1.0,
                    source="user_feedback",
                    ts=datetime.now(timezone.utc),
                    status="active",
                )
            )
            return True

        knowledge = self.knowledge_store.get(fact_id)
        if knowledge is not None:
            self.knowledge_store.downgrade_and_mark(fact_id=knowledge.id, factor=0.3, status="superseded")
            self.knowledge_store.upsert(
                KnowledgeFact(
                    id="",
                    topic=knowledge.topic,
                    statement=new_value,
                    confidence=1.0,
                    source="user_feedback",
                    evidence=[*knowledge.evidence, "feedback_correct"],
                    ts=datetime.now(timezone.utc),
                    status="active",
                    version=knowledge.version + 1,
                )
            )
            return True
        return False
