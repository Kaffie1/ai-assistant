from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def now_beijing() -> datetime:
    """
    功能：返回当前北京时间。
    输入：无。
    输出：带 `Asia/Shanghai` 时区的 `datetime`。
    """
    return datetime.now(BEIJING_TZ)


def iso_now_beijing() -> str:
    """
    功能：返回当前北京时间 ISO 字符串。
    输入：无。
    输出：ISO 格式时间字符串。
    """
    return now_beijing().isoformat()


def ensure_beijing(dt: datetime) -> datetime:
    """
    功能：把任意时间对象统一转换为北京时间。
    输入：时间对象 `dt`。
    输出：北京时间 `datetime`。
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=BEIJING_TZ)
    return dt.astimezone(BEIJING_TZ)
