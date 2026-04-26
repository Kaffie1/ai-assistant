from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from foundation.time_utils import ensure_beijing, now_beijing


def _safe_build_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except Exception:
        return None


def _resolve_weekday_due_date(text: str, today: date) -> date | None:
    m = re.search(r"(?:(下下周|下周|本周|这周))?[周星期礼拜]\s*([一二三四五六日天])", text)
    if not m:
        if "周末" in text:
            return today + timedelta(days=(5 - today.weekday()) % 7)
        return None
    prefix = (m.group(1) or "").strip()
    weekday_map = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
    target = weekday_map.get(m.group(2), -1)
    if target < 0:
        return None
    week_offset = 14 if prefix == "下下周" else 7 if prefix == "下周" else 0
    base = today + timedelta(days=week_offset)
    return base + timedelta(days=(target - base.weekday()) % 7)


def _resolve_month_day_due_date(text: str, today: date) -> date | None:
    m = re.search(r"(?<!\d)(\d{1,2})\s*(?:月|[-/.])\s*(\d{1,2})(?:日|号)?(?!\d)", text)
    if not m:
        return None
    month = int(m.group(1))
    day = int(m.group(2))
    candidate = _safe_build_date(today.year, month, day)
    if candidate is None:
        return None
    if candidate < today:
        return _safe_build_date(today.year + 1, month, day) or candidate
    return candidate


def resolve_due_date(user_message: str, llm_due_date: str) -> str:
    text = (user_message or "").strip()
    if not text:
        return ""
    today = date.today()
    m = re.search(r"(20\d{2})\s*(?:年|[-/.])\s*(\d{1,2})\s*(?:月|[-/.])\s*(\d{1,2})(?:日|号)?", text)
    if m:
        parsed = _safe_build_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if parsed is not None:
            return parsed.isoformat()
    month_day = _resolve_month_day_due_date(text=text, today=today)
    if month_day is not None:
        return month_day.isoformat()
    if "明天" in text:
        return (today + timedelta(days=1)).isoformat()
    if "后天" in text:
        return (today + timedelta(days=2)).isoformat()
    if "大后天" in text:
        return (today + timedelta(days=3)).isoformat()
    if "今天" in text:
        return today.isoformat()
    week_day = _resolve_weekday_due_date(text=text, today=today)
    if week_day is not None:
        return week_day.isoformat()
    due_cues = ("截止", "到期", "前", "之前", "本周", "这周", "下周", "周", "星期", "礼拜", "周末", "明天", "今天", "后天", "大后天", "月", "号", "/", "-", ".")
    if not any(c in text for c in due_cues):
        return ""
    raw = (llm_due_date or "").strip()
    if not raw:
        return ""
    try:
        return date.fromisoformat(raw[:10]).isoformat()
    except Exception:
        return ""


def _parse_small_chinese_number(text: str) -> int | None:
    raw = (text or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        return int(raw)
    return {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}.get(raw)


def resolve_remind_at(user_message: str, anchor: datetime | None = None) -> str:
    text = (user_message or "").strip()
    if not text:
        return ""
    base = ensure_beijing(anchor) if anchor else now_beijing()
    rel = re.search(r"([0-9一二两三四五六七八九十]+)\s*(分钟|分|小时|钟头|天)后", text)
    if rel:
        amount = _parse_small_chinese_number(rel.group(1))
        unit = rel.group(2)
        if amount and amount > 0:
            if unit in {"分钟", "分"}:
                return (base + timedelta(minutes=amount)).isoformat()
            if unit in {"小时", "钟头"}:
                return (base + timedelta(hours=amount)).isoformat()
            if unit == "天":
                return (base + timedelta(days=amount)).isoformat()
    if "一会儿" in text or "等会" in text:
        return (base + timedelta(minutes=10)).isoformat()
    due_date = resolve_due_date(user_message=text, llm_due_date="")
    if due_date:
        hour = 9
        minute = 0
        hm = re.search(r"(上午|中午|下午|晚上)?\s*(\d{1,2})\s*[:点时]\s*(\d{1,2})?", text)
        if hm:
            prefix = (hm.group(1) or "").strip()
            hour = int(hm.group(2))
            minute = int(hm.group(3) or "0")
            if prefix in {"下午", "晚上"} and hour < 12:
                hour += 12
            if prefix == "中午" and hour < 11:
                hour += 12
        try:
            return ensure_beijing(datetime.fromisoformat(f"{due_date}T{hour:02d}:{minute:02d}:00")).isoformat()
        except Exception:
            return ""
    return ""
