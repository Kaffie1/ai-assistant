from __future__ import annotations

from datetime import datetime, timezone


def clamp(value: float, lo: float, hi: float) -> float:
    """
    功能：将数值裁剪到指定闭区间。
    输入：原值 `value`，下界 `lo`，上界 `hi`。
    输出：裁剪后的数值。
    """
    return max(lo, min(value, hi))


def recency_score(ts: datetime, now: datetime | None = None, half_life_hours: float = 72.0) -> float:
    """
    功能：根据时间衰减计算时效分。
    输入：记忆时间 `ts`、当前时间 `now`、半衰期小时数。
    输出：0~1 的时效分，越新越高。
    """
    if now is None:
        now = datetime.now(timezone.utc)
    age_hours = max(0.0, (now - ts).total_seconds() / 3600.0)
    # Score ~ 0.5 at half-life.
    return 0.5 ** (age_hours / half_life_hours)
